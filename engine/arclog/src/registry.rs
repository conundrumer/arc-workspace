//! The lib registry: the names of the lib, and what each declares. It is
//! embedded from the registry file and the proposers file, as
//! [`REGISTRY_TEXT`] and [`PROPOSERS_TEXT`], when the engine is compiled, so
//! the wheel reads no file for it. A new lib element adds a
//! registry entry and changes no checker code.
//!
//! # The file
//!
//! The file is `engine/lib/registry.sexpr`. It is s-expressions, read by the
//! reader of [`crate::read::read_sexprs`], so the engine has one reader for
//! every s-expression file. `include_str!` puts its text into the compiled
//! crate, and [`Registry::get`] reads that text once, on first use. The test
//! `registry_file` under `engine/arclog/tests/` parses both lib files, so a
//! fault of either fails `cargo test`.
//!
//! Each top-level form declares one lib element, by its head:
//!
//! - `(relation <name> (columns (<Column> <type>) ...) (modes (<Column> ...) ...))`:
//!   an algebra relation, the group relations and `pose_difference`
//!   included. Each mode lists the columns, other than an orientation
//!   type's, that must be bound for the relation to bind the others; a
//!   relation over a finite domain has no `modes` form, and no mode is empty.
//! - `(component <name> <construction|detector|task-structure> (type-parameters <t> ...)
//!   (inputs (<input> (<column> <type>) ... [(default <rows>)] [reads-outputs] [from-key]) ...)
//!   (outputs (<output> (<column> <type>) ...) ...))`: a construction, a
//!   detector or a task-structure component, its inputs in the order the component declares them. An
//!   input's `default` writes its rows as a `param` form writes them after
//!   its types (`docs/arclog/arcdata.md#params`). An input marked
//!   `reads-outputs` reads the instance's outputs, as `Unfold`'s `step`,
//!   `skip` and `take` do. An input marked `from-key`, which writes no
//!   `default`, is filled from the key where the instance writes no clause
//!   for it, as Cardinality's `domain`; an input with neither mark nor
//!   `default` holds no row there. An output may share its name with an input of
//!   the same form, as `Unfold`'s `take` does: an instance's output of that
//!   name, where the instance writes no clause for it, reads the input's
//!   relation.
//! - `(proposer <name> native [domain] (columns (<Column> <type>) ...))`: a
//!   native proposer, marked `domain` where it is a type-domain proposer, as
//!   `docs/arclog/arclog.md#program` gives one.
//! - `(proposer <name> arclog (columns <Label> ...))`: a proposer written
//!   in arclog, whose clause stands in `engine/lib/proposers.arclog`. Its
//!   columns are the labels the form names, in the order the form gives.
//!   Each is a label that its clause keeps, and each other label of the
//!   clause is projected away. Each column has the type that
//!   [`macro_column_types`] gives a relation macro's column whose label is
//!   the column's, over the clause.
//! - `(constants <type> <NAME> ...)`: the constants of an orientation type,
//!   and `(constants C4 <NAME> ...)`: the D4 constants that are C4, the
//!   rotations.
//! - `(fact <name> (columns (<Column> <type>) ...))`: the columns of a fact
//!   relation, `input`, `ex_input` or `ex_output`, the Example column `E`
//!   first in the two of the examples.
//! - `(macro <name> (columns (<Column> <Label>) ...) <body>)`:
//!   a lib relation that the lib defines from other lib names, each column
//!   with the label of the definition it stands for, and its definition. A
//!   [`Macro::Relation`]'s column types and modes are the ones
//!   [`macro_column_types`] gives.
//!
//! An atom of a body of either file reads a name that a form declares, at
//! columns that name declares: a lib name, a macro or a fact. An atom that
//! reads another name or column is a fault of the file.
//!
//! A `<type>` is a type name of [`crate::program::TypeName`], `Pose` for
//! the assembly the read names, `shared-pose` for one assembly's Pose type
//! at each such column of the relation, `(pose-or <type>)` for the type or
//! the Pose type of the label at the site, or a type parameter of its
//! component. The file declares no `representative`. The file and
//! `engine/lib/proposers.arclog` are named in diagnostics as
//! [`crate::layout::SourceFile::LibRegistry`] and
//! [`crate::layout::SourceFile::LibProposers`].
//!
//! # The modules
//!
//! The reader of the two files, the spellings of the registry file's forms, the records of a form the reader reads, the reader of the registry file's other
//! forms, the reader of its macro form, the reader of the proposers file's clauses, the check of the reads of their bodies, the derivation of the
//! macros' column types, the declaration of the macros and of the proposers written in arclog from it, and the rule by which an `INIT` form binds its
//! component's type parameters each stand in a module of their own. The derivations take the forms as the reader gives them, and
//! read no file.
//!
//! `engine/lib/proposers.arclog` holds one form `(proposer <Name> <atom> ...)`
//! per proposer of the form `(proposer <name> arclog (columns ...))`, its name in the
//! spelling of a proposer, as `(proposer DominantColor ...)`, then the atoms
//! of its clause's body, which [`crate::read::read_body`] reads.

#![allow(unused_variables, dead_code)]

use crate::check::CheckId;
use crate::safety::{body_labels, bound_labels, own_labels};
use crate::hash::{StableHashMap, StableHashSet};
use crate::layout::{SourceFile, SourcePlace};
use crate::program::{
    Atom, Body, ColumnName, FactRelation, LabelId, Node, PortName, RelationRef, TypeName,
};
use crate::read::spelling;
use crate::read::{check_error, head_of, read_body, read_param_value, read_sexprs, SExpr};
use crate::terms::{OrientationConstant, OrientationType};
use crate::types::{each_atom, each_conjunct, label_type, LabelFault, ValueType};

/// The text of the registry file, which [`Registry::get`] reads.
pub const REGISTRY_TEXT: &str = include_str!("../../lib/registry.sexpr");

/// The text of the proposers file, read by
/// [`crate::read::read_sexprs`] with
/// [`crate::layout::SourceFile::LibProposers`] and [`crate::read::read_body`].
pub const PROPOSERS_TEXT: &str = include_str!("../../lib/proposers.arclog");

/// A name of the lib: a relation, a component, a proposer or a macro, as the file writes it: `margin`, `Connectivity`,
/// `DominantColor`, `Frame`. An orientation constant is named by
/// [`Registry::orientation_constant`] instead.
#[derive(Clone, PartialEq, Eq, Hash, Debug)]
pub struct LibName(pub Box<str>);

/// The name of a component's type parameter, such as `t` or `key`.
#[derive(Clone, PartialEq, Eq, Hash, Debug)]
pub struct TypeParameter(pub Box<str>);

/// The type a lib column declares. A `:Pose` column has the type Pose of its
/// assembly.
#[derive(Clone, PartialEq, Eq, Hash, Debug)]
pub enum ColumnType {
    Fixed(ValueType),
    /// The Pose type of the assembly the read names.
    Pose,
    /// The Pose type of one assembly, the same at each column of the
    /// relation that declares it, as `pose_difference(a, b, d)` reads two
    /// poses of one assembly.
    SharedPose,
    /// The given type, or the Pose type of the label at the column's site, as
    /// `d4_elem`'s column is D4 or takes its label's Pose type
    /// (`docs/arclog/rigid.md#the-pose`).
    PoseOr(ValueType),
    /// A type parameter of the component, made concrete by an instance's
    /// binding.
    Parameter(TypeParameter),
}

impl ColumnType {
    /// The type the column gives its site in every read: that of a
    /// `Fixed` or a `PoseOr` column.
    pub fn fixed(&self) -> Option<&ValueType> {
        match self {
            ColumnType::Fixed(ty) | ColumnType::PoseOr(ty) => Some(ty),
            ColumnType::Pose | ColumnType::SharedPose | ColumnType::Parameter(_) => None,
        }
    }
}

/// A declared column: its name and type.
#[derive(Clone, PartialEq, Eq, Hash, Debug)]
pub struct Column {
    pub name: ColumnName,
    pub ty: ColumnType,
}

/// Whether `column` is the `key` column of its port.
pub fn is_key(column: &Column) -> bool {
    column.name == crate::resolver::columns::key()
}

/// A mode of an algebra relation: the columns whose labels must be bound
/// for its other columns to be bound.
#[derive(Clone, PartialEq, Eq, Hash, Debug)]
pub struct Mode {
    pub bound: Box<[ColumnName]>,
}

/// An algebra relation, a relation of the box algebra or the orientation
/// algebra, with its columns, their types and its modes.
#[derive(Clone, Debug)]
pub struct AlgebraRelation {
    pub columns: Box<[Column]>,
    /// Empty for a relation over a finite domain.
    pub modes: Box<[Mode]>,
}

/// The kind of a component: a construction, a detector or a task-structure
/// component. A task-structure component, `Choose` or
/// `DemonstrationConsistency`, is the component of a `CHOOSE` or a
/// `DEMONSTRATED` form, whose ports the registry declares as it declares a
/// construction's.
#[derive(Clone, Copy, PartialEq, Eq, Hash, Debug)]
pub enum ComponentKind {
    Construction,
    Detector,
    TaskStructure,
}

/// One input or output of a component.
#[derive(Clone, Debug)]
pub struct Port {
    pub name: PortName,
    pub columns: Box<[Column]>,
}

impl Port {
    /// The columns of the port at an instance that has a key clause where
    /// `keyed` holds, and otherwise those other than `key`.
    pub fn columns_at(&self, keyed: bool) -> impl Iterator<Item = &Column> + '_ {
        self.columns.iter().filter(move |column| keyed || !is_key(column))
    }
}

/// An input of a component, with its default rows, which hold where the
/// instance writes no clause for the input.
#[derive(Clone, Debug)]
pub struct InputPort {
    pub port: Port,
    pub default: Option<DefaultRows>,
    /// Whether the input reads the instance's outputs, as `Unfold`'s `step`,
    /// `skip` and `take` do, through atoms whose every variable another atom
    /// of the clause binds.
    pub reads_outputs: bool,
    /// Whether the input, which then has no default, is filled from the
    /// key where the instance writes no clause for it, as Cardinality's
    /// `domain`.
    pub from_key: bool,
}

/// The default rows of an input, as the file writes them, read by
/// [`crate::read::read_param_value`]. It gives its rows as a set, and no
/// position of a row, so no caller can pick one default by its place in the
/// file, and no lib interface makes a free choice.
#[derive(Clone, Debug)]
pub struct DefaultRows {
    written: crate::program::ParamValue,
}

impl DefaultRows {
    /// The default rows, typed by `types`, the types of the input's columns
    /// in order: [`crate::terms::encode_param_value`] of the default's
    /// value, with `table` interning an Ident's values.
    pub fn rows(
        &self,
        types: &[ValueType],
        registry: &Registry,
        table: &mut crate::terms::InternTable,
    ) -> Result<crate::hash::StableHashSet<Box<[crate::terms::TermId]>>, crate::terms::DataValueError> {
        crate::terms::encode_param_value(&self.written, types, registry, table)
    }
}

/// A construction or a detector: its type parameters, its inputs in the
/// order the component declares them, with their defaults, and its outputs.
#[derive(Clone, Debug)]
pub struct Component {
    pub kind: ComponentKind,
    pub type_parameters: Box<[TypeParameter]>,
    /// The inputs in the order the component declares them.
    pub inputs: Box<[InputPort]>,
    pub outputs: Box<[Port]>,
}

impl Component {
    /// Whether an input of the component reads the instance's outputs.
    pub fn reads_outputs(&self) -> bool {
        self.inputs.iter().any(|input| input.reads_outputs)
    }

    /// The ports that are relations of their own at an `INIT` form that
    /// writes the inputs `written`: each output, then each written input
    /// whose name no output shares.
    pub fn relation_ports<'c>(&'c self, written: &'c [&PortName]) -> impl Iterator<Item = &'c Port> + 'c {
        let shares_output = |port: &Port| self.outputs.iter().any(|output| output.name == port.name);
        let inputs = self.inputs.iter().map(|input| &input.port).filter(|port| written.contains(&&port.name));
        self.outputs.iter().chain(inputs.filter(move |port| !shares_output(port)))
    }
}

/// A proposer, native or written in arclog, and its columns with their
/// types.
#[derive(Clone, Debug)]
pub struct Proposer {
    pub columns: Box<[Column]>,
    pub kind: ProposerKind,
}

/// The kind of a proposer: native, a type-domain proposer or another, or written
/// in arclog with its clause.
#[derive(Clone, Debug)]
pub enum ProposerKind {
    Native { domain: bool },
    /// A proposer written in arclog and the body of its clause. Its columns
    /// are the labels its `(columns <Label> ...)` form names, in the order
    /// the form gives. Each is a label the clause keeps, and each other
    /// label of the clause is projected away.
    Arclog { body: Node<Body> },
}

/// What a lib name declares.
#[derive(Clone, Debug)]
pub enum LibEntry {
    Relation(AlgebraRelation),
    Component(Component),
    Proposer(Proposer),
    Macro(Macro),
}

/// A lib name that the lib defines from other lib names, with its
/// declaration and its definition. The checks read the declaration. A
/// relation macro's column types and modes are its definition's, as
/// [`macro_column_types`] gives them.
#[derive(Clone, Debug)]
pub enum Macro {
    /// A lib relation: its declaration, its columns, their types and its
    /// modes, the label of the definition that each of its columns stands
    /// for, in the order of the declaration's columns, and its definition.
    Relation {
        relation: AlgebraRelation,
        labels: Box<[crate::program::LabelId]>,
        definition: Node<Body>,
    },
}

/// The constants of one orientation type, as a set: it gives membership
/// and each constant, and no position of a constant, so no caller can pick
/// one constant by its place in the file, and no lib interface makes a free
/// choice.
#[derive(Clone, Debug, Default)]
pub struct ConstantSet {
    constants: crate::hash::StableHashSet<OrientationConstant>,
}

impl ConstantSet {
    /// Whether `constant` is in the set.
    pub fn contains(&self, constant: OrientationConstant) -> bool {
        self.constants.contains(&constant)
    }

    /// Each constant of the set, in an order of encodings and no order of
    /// the content.
    pub fn each(&self) -> impl Iterator<Item = OrientationConstant> + '_ {
        self.constants.iter().copied()
    }
}

/// A fault of the registry file, reported when it is first read.
#[derive(Clone, Debug)]
pub struct RegistryError {
    pub diagnostics: Vec<crate::diagnostic::Diagnostic>,
}

/// The lib registry: the names of the lib, and what each declares.
#[derive(Debug)]
pub struct Registry {
    entries: StableHashMap<LibName, LibEntry>,
    /// The constants of each orientation type.
    constants: StableHashMap<OrientationType, TypeConstants>,
    c4: ConstantSet,
    facts: StableHashMap<crate::program::FactRelation, Box<[Column]>>,
}

/// The constants of one orientation type: the name of each, at the index
/// [`OrientationConstant::new`] gives it, and the set of them.
#[derive(Debug)]
struct TypeConstants {
    names: Box<[Box<str>]>,
    set: ConstantSet,
}

impl TypeConstants {
    /// The constant written `name`, where the type has one.
    fn constant(&self, ty: OrientationType, name: &str) -> Option<OrientationConstant> {
        let index = self.names.iter().position(|n| &**n == name)?;
        Some(OrientationConstant::new(ty, index as u8))
    }
}

impl Registry {
    /// The registry of [`REGISTRY_TEXT`], read on first use.
    ///
    /// A fault of the file fails the test `registry_file`, so this panics on
    /// one.
    pub fn get() -> &'static Registry {
        static REGISTRY: std::sync::OnceLock<Registry> = std::sync::OnceLock::new();
        REGISTRY.get_or_init(|| match Registry::parse(REGISTRY_TEXT, PROPOSERS_TEXT) {
            Ok(registry) => registry,
            Err(error) => panic!("the lib files do not parse: {:?}", error.diagnostics),
        })
    }

    /// The registry that `text` declares, with the proposers that
    /// `proposers` writes in arclog, which are read with the entries of
    /// `text`. [`Registry::get`] gives it [`REGISTRY_TEXT`] and
    /// [`PROPOSERS_TEXT`].
    ///
    /// Fails with a diagnostic at the form of each fault of either file.
    pub fn parse(text: &str, proposers: &str) -> Result<Registry, RegistryError> {
        let mut reader = FileReader::default();
        for expr in reader.sexprs(text, SourceFile::LibRegistry) {
            reader.form(&expr);
        }
        let clauses = reader.sexprs(proposers, SourceFile::LibProposers);
        reader.proposer_clauses(&clauses);
        reader.check_reads();
        reader.declare_macros();
        reader.check_complete();
        reader.registry()
    }

    /// The name of each entry, in an order of encodings and no order of the
    /// content.
    pub fn names(&self) -> impl Iterator<Item = &LibName> + '_ {
        self.entries.keys()
    }

    /// What `name` declares, or `None` where the lib has no such name.
    pub fn entry(&self, name: &LibName) -> Option<&LibEntry> {
        self.entries.get(name)
    }

    /// The declaration of the algebra relation or relation macro `name`, or
    /// `None` where the lib declares neither of that name.
    pub fn algebra_relation(&self, name: &LibName) -> Option<&AlgebraRelation> {
        match self.entry(name)? {
            LibEntry::Relation(relation) | LibEntry::Macro(Macro::Relation { relation, .. }) => Some(relation),
            _ => None,
        }
    }

    /// The orientation constant written `name`, such as `DIR_T`.
    pub fn orientation_constant(&self, name: &str) -> Option<OrientationConstant> {
        self.constants.iter().find_map(|(&ty, constants)| constants.constant(ty, name))
    }

    /// The name of `constant`, for a writer.
    pub fn constant_name(&self, constant: OrientationConstant) -> &str {
        let names = &self.type_constants(constant.ty()).names;
        let index = (0..names.len())
            .find(|&index| OrientationConstant::new(constant.ty(), index as u8) == constant)
            .expect("each orientation constant is one that the registry numbered");
        &names[index]
    }

    /// The constants of `ty`, for a type-domain proposer and for `<ty>_elem`.
    pub fn constants_of(&self, ty: OrientationType) -> &ConstantSet {
        &self.type_constants(ty).set
    }

    /// The D4 constants that are C4, the rotations, as `C4` stands under
    /// `D4`, for `c4_elem`.
    pub fn c4_constants(&self) -> &ConstantSet {
        &self.c4
    }

    /// The columns of `fact`, with their types, which the resolver turns a
    /// read's column names into positions by and the checker types by.
    pub fn fact_columns(&self, fact: crate::program::FactRelation) -> &[Column] {
        self.facts.get(&fact).expect("`parse` fails on a fact relation with no `fact` form")
    }

    fn type_constants(&self, ty: OrientationType) -> &TypeConstants {
        self.constants.get(&ty).expect("`parse` fails on an orientation type with no `constants` form")
    }
}

mod bindings;
mod column_types;
mod forms;
mod macro_declarations;
mod macro_forms;
mod proposer_clauses;
mod reader;
mod reads;
mod records;
mod spellings;

pub(crate) use bindings::{binding_sites, key_fill, unbound, ParameterSite};
pub use column_types::{macro_column_types, MacroDeclarations, RelationMacro};
use reader::FileReader;
