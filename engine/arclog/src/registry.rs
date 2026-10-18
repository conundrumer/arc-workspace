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
//!   type's, that must be grounded for the relation to ground the others; a
//!   relation over a finite domain has no `modes` form, and no mode is empty.
//! - `(component <name> <construction|detector|task-structure> (type-parameters <t> ...)
//!   (inputs (<input> (<column> <type>) ... [(default <rows>)] [reads-outputs]) ...)
//!   (outputs (<output> (<column> <type>) ...) ...))`: a construction, a
//!   detector or a task-structure component, its inputs in the order the component declares them. An
//!   input's `default` writes its rows as a `param` form writes them after
//!   its types (`docs/arclog/arcdata.md#params`): each row as a list of its
//!   values, and the rows of a relation with a Position or an Offset column
//!   as a grid. An
//!   input marked `reads-outputs` reads the instance's outputs, as
//!   `Unfold`'s `step`, `skip` and `take` do. An output may share its name
//!   with an input of the same form: an instance's output of that name reads
//!   the input's relation, as `Unfold`'s `take`, where the instance writes no
//!   clause for it, holds the item of least `score`.
//! - `(proposer <name> native (columns (<Column> <type>) ...))`: a native
//!   proposer, such as a domain proposer.
//! - `(proposer <name> arclog)`: a proposer written in arclog, whose clause
//!   stands in `engine/lib/proposers.arclog`. Its columns are its clause's
//!   labels, in the order they first stand in the clause.
//! - `(derivation <Name> (fields (<Field> <type>) ...) (columns (<Column> <type>) ...))`:
//!   a fixed derivation of a table, its row's fields and the table's columns.
//!   A derivation may share its name with a component, as `Frame` and
//!   `Division` do.
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
//! - `(macro <name> (component ...) [(INIT ...)] (RULE &<rule> <body>) ... (output <port> (<Label> ...) <body>) ...)`:
//!   a cell instance, its declaration as a `component` form gives it, the
//!   `INIT` form of the underlying construction where it has one, its local
//!   relations, and a body for each of its outputs, as [`Macro::CellInstance`]
//!   gives. Within the `INIT`'s bodies, the `RULE` forms' and the outputs',
//!   an atom `(self.<port> <sites>)` reads the cell instance's own input
//!   `<port>`, as [`crate::program::RelationRef::DefinedPort`] holds it.
//!   A `RULE` form is a local relation, written as a solver's `RULE` clause
//!   (`docs/arclog/arclog.md#program`), which the macro's expansion makes
//!   into a clause of the solver: its body may read the `INIT`'s outputs,
//!   and the output bodies, the `INIT`'s input bodies and the other `RULE`
//!   forms read it as `(&<rule> <sites>)`. Each site of the cell instance
//!   has its own expansion, and a name that the macro's `INIT` or a `RULE`
//!   form declares stands for its declaration within that expansion alone,
//!   as a name that a `DEMO_RULE` form declares does
//!   ([`crate::program::NameScope`]).
//!   The `INIT` binds the type parameters of the underlying construction as
//!   a solver's `INIT` binds them (`docs/arclog/arclog.md#instance`), to a
//!   record where a projection has several sites, and may hold a key clause
//!   over the cell instance's own inputs. One definition holds for each set
//!   of inputs a site writes clauses for: a `self.<port>` atom of an input
//!   the site writes no clause for reads that input's default rows alone,
//!   and no row where the input has no default.
//!
//! An atom of a body of either file reads a name that a form declares, at
//! columns that name declares: a lib name, a macro, a fact, and within a
//! cell instance its own input `self.<port>`, a `RULE` form `&<rule>` or an
//! output of its `INIT` form. An atom that reads another name or column is a
//! fault of the file.
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
//! `engine/lib/proposers.arclog` holds one form `(proposer <Name> <atom> ...)`
//! per proposer of the form `(proposer <name> arclog)`, its name in the
//! spelling of a proposer, as `(proposer DominantColor ...)`, then the atoms
//! of its clause's body, which [`crate::read::read_body`] reads.

#![allow(unused_variables, dead_code)]

use crate::check::CheckId;
use crate::grounding::{body_labels, grounded_labels};
use crate::hash::{StableHashMap, StableHashSet};
use crate::layout::{SourceFile, SourcePlace};
use crate::program::{
    Atom, Body, ClauseKeyword, ColumnName, Conjunct, DeclaredName, FactRelation, InstanceName, LabelId, Negated, Node,
    OutputOwner, OutputStep, PortName, RelationName, RelationRef, TypeName,
};
use crate::read::spelling;
use crate::read::{check_error, head_of, read_body, read_instance, read_param_value, read_sexprs, SExpr};
use crate::terms::{OrientationConstant, OrientationType};
use crate::types::{each_conjunct, label_type, LabelFault, ValueType};

/// The text of the registry file, which [`Registry::get`] reads.
pub const REGISTRY_TEXT: &str = include_str!("../../lib/registry.sexpr");

/// The text of the proposers file, read by
/// [`crate::read::read_sexprs`] with
/// [`crate::layout::SourceFile::LibProposers`] and [`crate::read::read_body`].
pub const PROPOSERS_TEXT: &str = include_str!("../../lib/proposers.arclog");

/// A name of the lib: a relation, a component, a proposer, a derivation or
/// a macro, as the file writes it: `margin`, `Connectivity`,
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
    /// The given type, or the Pose type of the label at the column's site,
    /// as `d4_elem`'s column is D4 or takes its label's Pose type, since
    /// every D4 element is a pose (`docs/arclog/rigid.md#the-pose`).
    PoseOr(ValueType),
    /// A type parameter of the component, made concrete by an instance's
    /// binding.
    Parameter(TypeParameter),
}

/// A declared column: its name and type.
#[derive(Clone, PartialEq, Eq, Hash, Debug)]
pub struct Column {
    pub name: ColumnName,
    pub ty: ColumnType,
}

/// A mode of an algebra relation: the columns whose labels must be grounded
/// for its other columns to be grounded.
#[derive(Clone, PartialEq, Eq, Hash, Debug)]
pub struct Mode {
    pub grounded: Box<[ColumnName]>,
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

/// An input of a component, with its default rows, which hold where the
/// instance writes no clause for the input.
#[derive(Clone, Debug)]
pub struct InputPort {
    pub port: Port,
    pub default: Option<DefaultRows>,
    /// Whether the input reads the instance's outputs, as `Unfold`'s `step`,
    /// `skip` and `take` do, through atoms whose every variable another atom
    /// of the clause grounds.
    pub reads_outputs: bool,
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

/// A proposer: a native one, or one written in arclog.
#[derive(Clone, Debug)]
pub enum Proposer {
    /// A native proposer and its columns.
    Native { columns: Box<[Column]> },
    /// A proposer written in arclog: the body of its clause, and its
    /// columns, the names of the clause's labels in the order they first
    /// stand in it.
    Arclog { columns: Box<[ColumnName]>, body: Node<Body> },
}

/// What a lib name declares.
#[derive(Clone, Debug)]
pub enum LibEntry {
    Relation(AlgebraRelation),
    Component(Component),
    Proposer(Proposer),
    Macro(Macro),
}

/// A fixed derivation of a table, such as `Frame` or `Division`: the fields
/// of each row of the values a `param` form writes for it, and the columns
/// of the table it derives. A `DET` names the derivation in place of a
/// proposer, `(DET &frame Frame)` (`docs/arclog/arclog.md#program`), and
/// the parameter's value is written as the values the table derives from
/// (`docs/arclog/arcdata.md#params`).
#[derive(Clone, Debug)]
pub struct Derivation {
    pub fields: Box<[Column]>,
    pub columns: Box<[Column]>,
}

/// A lib name that the lib defines from other lib names, a relation or a
/// cell instance, with its declaration and its definition, which the
/// resolver expands under [`crate::resolver::MacroExpansion::Expand`]. The
/// declaration serves the checks under
/// [`crate::resolver::MacroExpansion::Keep`], the form the corpus is written
/// in. A program runs in either form. A relation macro's column types and
/// modes are its definition's, as [`macro_column_types`] gives them.
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
    /// A cell instance: its declaration as a component, its type
    /// parameters, inputs in order with their defaults, and outputs; its
    /// definition over the underlying construction or relation; its local
    /// relations, each a `RULE` form's name and body; and a body for each of
    /// its outputs.
    CellInstance {
        component: Component,
        definition: CellDefinition,
        rules: Box<[CellRule]>,
        outputs: Box<[CellOutput]>,
    },
}

/// What a cell instance is defined over: Connectivity over Quotient, Flood
/// over Propagation, and CellDistance and Ray over Distance.
#[derive(Clone, Debug)]
pub enum CellDefinition {
    /// An `INIT` form of the underlying construction with its domain inputs
    /// populated, whose other input bodies read the cell instance's inputs
    /// by their port names, as Connectivity over Quotient.
    Instance(Node<crate::program::Instance>),
    /// No instance: the outputs' bodies read the underlying relation over
    /// the cell instance's inputs.
    Relation,
}

/// A local relation of a cell instance, a `RULE` form: the relation's name,
/// which the instance's bodies read it by, and its body, whose labels are
/// its columns.
#[derive(Clone, Debug)]
pub struct CellRule {
    pub name: crate::program::RelationName,
    pub body: Node<Body>,
}

/// An output of a cell instance, as a body over the outputs of its
/// definition's instance, where it has one, and its own inputs: the output's
/// port, the label of the body that each of its columns stands for, in the
/// order of the port's columns, and the body.
#[derive(Clone, Debug)]
pub struct CellOutput {
    pub port: PortName,
    pub labels: Box<[crate::program::LabelId]>,
    pub body: Node<Body>,
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
    /// The derivations, apart from the entries, since a name such as
    /// `Frame` or `Division` is both a component and a derivation.
    derivations: StableHashMap<LibName, Derivation>,
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
        reader.declare_relation_macros();
        reader.check_complete();
        reader.registry()
    }

    /// What `name` declares, or `None` where the lib has no such name.
    pub fn entry(&self, name: &LibName) -> Option<&LibEntry> {
        self.entries.get(name)
    }

    /// The derivation that `name` declares, which a `DET` names in place of
    /// a proposer, or `None` where the lib declares no derivation of that
    /// name.
    pub fn derivation(&self, name: &LibName) -> Option<&Derivation> {
        self.derivations.get(name)
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

    /// The constants of `ty`, for a domain proposer and for `<ty>_elem`.
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
    /// `ex_input` and `ex_output` have the Example column `E` first
    /// (`docs/arclog/arclog.md#program`).
    pub fn fact_columns(&self, fact: crate::program::FactRelation) -> &[Column] {
        self.facts.get(&fact).expect("`parse` fails on a fact relation with no `fact` form")
    }

    fn type_constants(&self, ty: OrientationType) -> &TypeConstants {
        self.constants.get(&ty).expect("`parse` fails on an orientation type with no `constants` form")
    }
}

// The words of the registry file's forms.
const RELATION: &str = "relation";
const COMPONENT: &str = "component";
const PROPOSER: &str = "proposer";
const DERIVATION: &str = "derivation";
const CONSTANTS: &str = "constants";
const FACT: &str = "fact";
const MACRO: &str = "macro";
const COLUMNS: &str = "columns";
const MODES: &str = "modes";
const FIELDS: &str = "fields";
const TYPE_PARAMETERS: &str = "type-parameters";
const INPUTS: &str = "inputs";
const OUTPUTS: &str = "outputs";
const DEFAULT: &str = "default";
const READS_OUTPUTS: &str = "reads-outputs";
const NATIVE: &str = "native";
const ARCLOG: &str = "arclog";
const OUTPUT: &str = "output";
const POSE: &str = "Pose";
const SHARED_POSE: &str = "shared-pose";
const POSE_OR: &str = "pose-or";
const C4: &str = "C4";

const COMPONENT_KINDS: &[(ComponentKind, &str)] = &[
    (ComponentKind::Construction, "construction"),
    (ComponentKind::Detector, "detector"),
    (ComponentKind::TaskStructure, "task-structure"),
];

/// The orientation type whose constants a column of `name` holds, where
/// `name` is one: `C4` is a part of `D4`, and `Dir8` and `Axis4` are unions.
fn orientation_type(name: TypeName) -> Option<OrientationType> {
    match name {
        TypeName::Dir => Some(OrientationType::Dir),
        TypeName::DiagDir => Some(OrientationType::DiagDir),
        TypeName::Axis => Some(OrientationType::Axis),
        TypeName::DiagAxis => Some(OrientationType::DiagAxis),
        TypeName::D4 => Some(OrientationType::D4),
        TypeName::Sym => Some(OrientationType::Sym),
        TypeName::Sense => Some(OrientationType::Sense),
        TypeName::Number
        | TypeName::Color
        | TypeName::Example
        | TypeName::Unit
        | TypeName::Box
        | TypeName::Position
        | TypeName::Offset
        | TypeName::Ident
        | TypeName::C4
        | TypeName::Dir8
        | TypeName::Axis4 => None,
    }
}

/// The items of `expr` after its head, where it is a list headed by `head`.
fn headed<'e>(expr: &'e SExpr, head: &str) -> Option<&'e [SExpr]> {
    match expr {
        SExpr::List { items, .. } => match items.split_first() {
            Some((SExpr::Symbol { text, .. }, rest)) if &**text == head => Some(rest),
            _ => None,
        },
        _ => None,
    }
}

/// The place of the start of `file`, where a fault of no one form stands.
fn file_start(file: SourceFile) -> SourcePlace {
    SourcePlace { file, start: 0, end: 0, line: 1, column: 1 }
}

/// A relation macro as its form writes it, before its declaration.
struct WrittenMacro {
    name: LibName,
    place: SourcePlace,
    columns: Box<[(ColumnName, LabelId)]>,
    definition: Node<Body>,
}

/// What a body of a cell instance reads beside the names of the lib: the
/// instance's own inputs, its `RULE` forms with their columns, and its
/// `INIT` form's name with the component it instantiates.
struct CellScope {
    inputs: Box<[Port]>,
    rules: Box<[(RelationName, Box<[ColumnName]>)]>,
    init: Option<(InstanceName, LibName)>,
}

/// A body of either file, whose reads [`FileReader::check_reads`] checks
/// once every form is read: the place of its form, and the index of the
/// cell instance it stands in, where it stands in one.
struct BodyInFile {
    body: Node<Body>,
    place: SourcePlace,
    cell: Option<usize>,
}

/// The reader of the two lib files. It reads each form whatever an earlier
/// one gave, and adds each fault of either file to one list.
#[derive(Default)]
struct FileReader {
    diagnostics: Vec<crate::diagnostic::Diagnostic>,
    entries: StableHashMap<LibName, LibEntry>,
    /// Each name that a form of the entries declares, a relation macro's and
    /// an arclog proposer's among them, which take their entries later.
    declared: StableHashSet<LibName>,
    derivations: StableHashMap<LibName, Derivation>,
    constants: StableHashMap<OrientationType, TypeConstants>,
    /// The names of the `C4` form, and its place.
    c4: Option<(Box<[Box<str>]>, SourcePlace)>,
    facts: StableHashMap<FactRelation, Box<[Column]>>,
    relation_macros: Vec<WrittenMacro>,
    /// Each `(proposer <name> arclog)` form's name and place, in file order.
    arclog_proposers: Vec<(LibName, SourcePlace)>,
    cells: Vec<CellScope>,
    bodies: Vec<BodyInFile>,
}

impl FileReader {
    fn fault(&mut self, check: CheckId, message: impl Into<Box<str>>, place: SourcePlace) {
        self.diagnostics.push(check_error(check, message, place));
    }

    /// Gives a diagnostic of the grammar, and `None`.
    fn refuse<T>(&mut self, message: impl Into<Box<str>>, place: SourcePlace) -> Option<T> {
        self.fault(CheckId::Grammar, message, place);
        None
    }

    /// `result`'s value, or `None` with its diagnostics added.
    fn read<T>(&mut self, result: Result<T, Vec<crate::diagnostic::Diagnostic>>) -> Option<T> {
        result.map_err(|diagnostics| self.diagnostics.extend(diagnostics)).ok()
    }

    /// The s-expressions of `text`, none where it does not read.
    fn sexprs(&mut self, text: &str, file: SourceFile) -> Vec<SExpr> {
        self.read(read_sexprs(text, file)).map(|(exprs, _)| exprs).unwrap_or_default()
    }

    fn symbol<'e>(&mut self, expr: Option<&'e SExpr>, what: &str, at: SourcePlace) -> Option<&'e str> {
        match expr {
            Some(SExpr::Symbol { text, .. }) => Some(text),
            Some(other) => self.refuse(format!("{what} is a symbol"), other.place()),
            None => self.refuse(format!("the form lacks {what}"), at),
        }
    }

    /// The items after the head of `expr`, a list headed by `head`.
    fn headed<'e>(&mut self, expr: Option<&'e SExpr>, head: &str, at: SourcePlace) -> Option<&'e [SExpr]> {
        match expr {
            Some(expr) => match headed(expr, head) {
                Some(rest) => Some(rest),
                None => self.refuse(format!("a `({head} ...)` form stands here"), expr.place()),
            },
            None => self.refuse(format!("the form lacks its `({head} ...)` form"), at),
        }
    }

    /// Gives a diagnostic at each item of `exprs`, which the form has no
    /// place for.
    fn no_more(&mut self, exprs: &[SExpr]) -> Option<()> {
        match exprs.first() {
            Some(expr) => self.refuse("the form has no place for this item", expr.place()),
            None => Some(()),
        }
    }

    /// Records that a form at `place` declares `name`, or gives a fault
    /// where another form declares it.
    fn declare(&mut self, name: &LibName, place: SourcePlace) -> bool {
        if self.declared.insert(name.clone()) {
            return true;
        }
        self.fault(CheckId::Scope, format!("`{}` is declared by two forms", name.0), place);
        false
    }

    fn form(&mut self, expr: &SExpr) {
        let place = expr.place();
        let SExpr::List { items, .. } = expr else {
            self.refuse::<()>("a form of the registry file is a list", place);
            return;
        };
        let rest = items.get(1..).unwrap_or_default();
        match head_of(expr) {
            Some(RELATION) => self.relation(rest, place),
            Some(COMPONENT) => {
                if let Some((name, component)) = self.component(rest, place)
                    && self.declare(&name, place)
                {
                    self.entries.insert(name, LibEntry::Component(component));
                }
                Some(())
            }
            Some(PROPOSER) => self.proposer(rest, place),
            Some(DERIVATION) => self.derivation(rest, place),
            Some(CONSTANTS) => self.constants(rest, place),
            Some(FACT) => self.fact(rest, place),
            Some(MACRO) => self.macro_form(rest, place),
            _ => self.refuse("the form's head is no kind of form of the registry file", place),
        };
    }

    /// The type that `expr` writes, with its type name where it writes one,
    /// for the reader of a default's rows.
    fn column_type(&mut self, expr: &SExpr, parameters: &[TypeParameter]) -> Option<(ColumnType, Option<TypeName>)> {
        if let Some(rest) = headed(expr, POSE_OR) {
            let name = match rest {
                [SExpr::Symbol { text, .. }] => spelling::parse(spelling::TYPE_NAMES, text),
                _ => None,
            };
            return match name {
                Some(name) => Some((ColumnType::PoseOr(name.value_type()), Some(name))),
                None => self.refuse(format!("a `({POSE_OR} <type>)` form holds one type name"), expr.place()),
            };
        }
        let text = self.symbol(Some(expr), "a type", expr.place())?;
        if let Some(name) = spelling::parse(spelling::TYPE_NAMES, text) {
            return Some((ColumnType::Fixed(name.value_type()), Some(name)));
        }
        match text {
            POSE => Some((ColumnType::Pose, None)),
            SHARED_POSE => Some((ColumnType::SharedPose, None)),
            _ => match parameters.iter().find(|p| &*p.0 == text) {
                Some(parameter) => Some((ColumnType::Parameter(parameter.clone()), None)),
                None => self.refuse(format!("`{text}` is no type and no type parameter of the component"), expr.place()),
            },
        }
    }

    /// The column that `expr`, `(<Column> <type>)`, writes.
    fn column(&mut self, expr: &SExpr, parameters: &[TypeParameter]) -> Option<(Column, Option<TypeName>)> {
        let SExpr::List { items, place, .. } = expr else {
            return self.refuse("a column is a list of its name and its type", expr.place());
        };
        let [name, ty] = &items[..] else {
            return self.refuse("a column is a list of its name and its type", *place);
        };
        let name = self.symbol(Some(name), "the column's name", *place)?;
        let (ty, written) = self.column_type(ty, parameters)?;
        Some((Column { name: ColumnName::Written(name.into()), ty }, written))
    }

    /// The columns that `expr`, `(<head> (<Column> <type>) ...)`, writes.
    fn columns(&mut self, expr: Option<&SExpr>, head: &str, parameters: &[TypeParameter], at: SourcePlace) -> Option<Box<[Column]>> {
        let items = self.headed(expr, head, at)?;
        let columns: Option<Vec<Column>> = items.iter().map(|item| self.column(item, parameters).map(|(c, _)| c)).collect();
        columns.map(Into::into)
    }

    /// `(relation <name> (columns ...) [(modes ...)])`, after its head.
    fn relation(&mut self, rest: &[SExpr], place: SourcePlace) -> Option<()> {
        let name = LibName(self.symbol(rest.first(), "the relation's name", place)?.into());
        let columns = self.columns(rest.get(1), COLUMNS, &[], place)?;
        let modes = match rest.get(2) {
            Some(expr) => self.modes(expr, &columns, place)?,
            None => Box::default(),
        };
        self.no_more(rest.get(3..).unwrap_or_default())?;
        if self.declare(&name, place) {
            self.entries.insert(name, LibEntry::Relation(AlgebraRelation { columns, modes }));
        }
        Some(())
    }

    /// `(modes (<Column> ...) ...)`, each mode a nonempty list of columns of
    /// `columns`.
    fn modes(&mut self, expr: &SExpr, columns: &[Column], place: SourcePlace) -> Option<Box<[Mode]>> {
        let items = self.headed(Some(expr), MODES, place)?;
        let mut modes = Vec::new();
        for item in items {
            let SExpr::List { items: names, place, .. } = item else {
                return self.refuse("a mode is a list of columns", item.place());
            };
            if names.is_empty() {
                return self.refuse("a mode is not empty", *place);
            }
            let mut grounded = Vec::new();
            for name in names.iter() {
                let text = self.symbol(Some(name), "a mode's column", *place)?;
                let column = ColumnName::Written(text.into());
                if !columns.iter().any(|c| c.name == column) {
                    return self.refuse(format!("`{text}` is no column of the relation"), name.place());
                }
                grounded.push(column);
            }
            modes.push(Mode { grounded: grounded.into() });
        }
        Some(modes.into())
    }

    /// `(component <Name> <kind> (type-parameters ...) (inputs ...) (outputs ...))`,
    /// after its head.
    fn component(&mut self, rest: &[SExpr], place: SourcePlace) -> Option<(LibName, Component)> {
        let name = LibName(self.symbol(rest.first(), "the component's name", place)?.into());
        let kind_text = self.symbol(rest.get(1), "the component's kind", place)?;
        let Some(kind) = spelling::parse(COMPONENT_KINDS, kind_text) else {
            return self.refuse(format!("`{kind_text}` is no kind of component"), rest[1].place());
        };
        let parameters = self.headed(rest.get(2), TYPE_PARAMETERS, place)?;
        let parameters: Option<Vec<TypeParameter>> =
            parameters.iter().map(|p| self.symbol(Some(p), "a type parameter", place).map(|t| TypeParameter(t.into()))).collect();
        let type_parameters: Box<[TypeParameter]> = parameters?.into();
        let inputs = self.headed(rest.get(3), INPUTS, place)?;
        let inputs: Option<Vec<InputPort>> = inputs.iter().map(|input| self.input(input, &type_parameters)).collect();
        let outputs = self.headed(rest.get(4), OUTPUTS, place)?;
        let outputs: Option<Vec<Port>> = outputs.iter().map(|output| self.port(output, &type_parameters)).collect();
        let (inputs, outputs) = (inputs?.into(), outputs?.into());
        self.no_more(rest.get(5..).unwrap_or_default())?;
        Some((name, Component { kind, type_parameters, inputs, outputs }))
    }

    /// An output, `(<output> (<column> <type>) ...)`.
    fn port(&mut self, expr: &SExpr, parameters: &[TypeParameter]) -> Option<Port> {
        let SExpr::List { items, place, .. } = expr else {
            return self.refuse("a port is a list of its name and its columns", expr.place());
        };
        let name = PortName(self.symbol(items.first(), "the port's name", *place)?.into());
        let columns: Option<Vec<Column>> = items[1..].iter().map(|item| self.column(item, parameters).map(|(c, _)| c)).collect();
        Some(Port { name, columns: columns?.into() })
    }

    /// An input, `(<input> (<column> <type>) ... [(default <rows>)] [reads-outputs])`.
    fn input(&mut self, expr: &SExpr, parameters: &[TypeParameter]) -> Option<InputPort> {
        let SExpr::List { items, place, .. } = expr else {
            return self.refuse("an input is a list of its name and its columns", expr.place());
        };
        let name = PortName(self.symbol(items.first(), "the input's name", *place)?.into());
        let mut rest = &items[1..];
        let reads_outputs = matches!(rest.last(), Some(SExpr::Symbol { text, .. }) if &**text == READS_OUTPUTS);
        if reads_outputs {
            rest = &rest[..rest.len() - 1];
        }
        let default_rows = rest.last().and_then(|last| headed(last, DEFAULT));
        if default_rows.is_some() {
            rest = &rest[..rest.len() - 1];
        }
        let mut columns = Vec::new();
        let mut written = Vec::new();
        for item in rest {
            let (column, name) = self.column(item, parameters)?;
            columns.push(column);
            written.push(name);
        }
        let default = match default_rows {
            Some(rows) => Some(DefaultRows { written: self.read(read_param_value(rows, &written))? }),
            None => None,
        };
        Some(InputPort { port: Port { name, columns: columns.into() }, default, reads_outputs })
    }

    /// `(proposer <name> native (columns ...))` or `(proposer <name> arclog)`,
    /// after its head.
    fn proposer(&mut self, rest: &[SExpr], place: SourcePlace) -> Option<()> {
        let name = LibName(self.symbol(rest.first(), "the proposer's name", place)?.into());
        match self.symbol(rest.get(1), "the proposer's kind", place)? {
            NATIVE => {
                let columns = self.columns(rest.get(2), COLUMNS, &[], place)?;
                self.no_more(rest.get(3..).unwrap_or_default())?;
                if self.declare(&name, place) {
                    self.entries.insert(name, LibEntry::Proposer(Proposer::Native { columns }));
                }
            }
            ARCLOG => {
                self.no_more(rest.get(2..).unwrap_or_default())?;
                if self.declare(&name, place) {
                    self.arclog_proposers.push((name, place));
                }
            }
            other => return self.refuse(format!("`{other}` is no kind of proposer, `{NATIVE}` or `{ARCLOG}`"), rest[1].place()),
        }
        Some(())
    }

    /// `(derivation <Name> (fields ...) (columns ...))`, after its head.
    fn derivation(&mut self, rest: &[SExpr], place: SourcePlace) -> Option<()> {
        let name = LibName(self.symbol(rest.first(), "the derivation's name", place)?.into());
        let fields = self.columns(rest.get(1), FIELDS, &[], place)?;
        let columns = self.columns(rest.get(2), COLUMNS, &[], place)?;
        self.no_more(rest.get(3..).unwrap_or_default())?;
        match self.derivations.entry(name) {
            std::collections::hash_map::Entry::Occupied(entry) => {
                let message = format!("`{}` is declared by two `derivation` forms", entry.key().0);
                self.fault(CheckId::Scope, message, place);
            }
            std::collections::hash_map::Entry::Vacant(entry) => {
                entry.insert(Derivation { fields, columns });
            }
        }
        Some(())
    }

    /// `(constants <type> <NAME> ...)` or `(constants C4 <NAME> ...)`, after
    /// its head.
    fn constants(&mut self, rest: &[SExpr], place: SourcePlace) -> Option<()> {
        let ty_text = self.symbol(rest.first(), "the constants' type", place)?;
        let names: Option<Vec<Box<str>>> =
            rest[1..].iter().map(|name| self.symbol(Some(name), "a constant's name", place).map(Into::into)).collect();
        let names: Box<[Box<str>]> = names?.into();
        if ty_text == C4 {
            if self.c4.is_some() {
                return self.refuse("the file has two `C4` forms", place);
            }
            self.c4 = Some((names, place));
            return Some(());
        }
        let Some(ty) = spelling::parse(spelling::TYPE_NAMES, ty_text).and_then(orientation_type) else {
            return self.refuse(format!("`{ty_text}` is no orientation type and not `{C4}`"), rest[0].place());
        };
        if self.constants.contains_key(&ty) {
            return self.refuse(format!("the file has two `constants` forms of `{ty_text}`"), place);
        }
        if names.len() > usize::from(u8::MAX) + 1 {
            return self.refuse("an orientation type has at most 256 constants", place);
        }
        for (index, name) in names.iter().enumerate() {
            let earlier = names[..index].contains(name) || self.constants.values().any(|c| c.names.contains(name));
            if earlier {
                self.fault(CheckId::Scope, format!("the constant `{name}` is written twice"), place);
            }
        }
        let set = (0..names.len()).map(|index| OrientationConstant::new(ty, index as u8)).collect();
        self.constants.insert(ty, TypeConstants { names, set: ConstantSet { constants: set } });
        Some(())
    }

    /// `(fact <name> (columns ...))`, after its head.
    fn fact(&mut self, rest: &[SExpr], place: SourcePlace) -> Option<()> {
        let text = self.symbol(rest.first(), "the fact's name", place)?;
        let Some(fact) = spelling::parse(spelling::FACT_RELATIONS, text) else {
            return self.refuse(format!("`{text}` is no fact relation"), rest[0].place());
        };
        let columns = self.columns(rest.get(1), COLUMNS, &[], place)?;
        self.no_more(rest.get(2..).unwrap_or_default())?;
        if self.facts.insert(fact, columns).is_some() {
            return self.refuse(format!("the file has two `fact` forms of `{text}`"), place);
        }
        Some(())
    }

    /// `(macro <name> (columns ...) <body>)` or a cell instance,
    /// `(macro <name> (component ...) ...)`, after its head.
    fn macro_form(&mut self, rest: &[SExpr], place: SourcePlace) -> Option<()> {
        let name = LibName(self.symbol(rest.first(), "the macro's name", place)?.into());
        match rest.get(1).and_then(head_of) {
            Some(COLUMNS) => self.relation_macro(name, rest, place),
            Some(COMPONENT) => self.cell_instance(name, rest, place),
            _ => self.refuse(format!("a macro's name stands before its `({COLUMNS} ...)` or its `({COMPONENT} ...)` form"), place),
        }
    }

    /// The label of `labels` named `name`, the first that stands, or a fault
    /// that `what` stands for no label of the body.
    fn label_of(&mut self, labels: &crate::read::LabelNames, name: &str, what: &str, place: SourcePlace) -> Option<LabelId> {
        match labels.iter().find(|(n, _)| &**n == name) {
            Some((_, label)) => Some(*label),
            None => {
                self.fault(CheckId::Scope, format!("{what} stands for the label `{name}`, which its body holds no label of"), place);
                None
            }
        }
    }

    fn relation_macro(&mut self, name: LibName, rest: &[SExpr], place: SourcePlace) -> Option<()> {
        let written = headed(&rest[1], COLUMNS).expect("the form's `columns` form");
        let (definition, labels) = self.read(read_body(&rest[2..], None))?;
        let mut columns = Vec::new();
        for item in written {
            let SExpr::List { items: pair, .. } = item else {
                return self.refuse("a macro's column is a list of its name and its label", item.place());
            };
            let [column, label] = &pair[..] else {
                return self.refuse("a macro's column is a list of its name and its label", item.place());
            };
            let column = self.symbol(Some(column), "the column's name", place)?;
            let label = self.symbol(Some(label), "the column's label", place)?;
            let what = format!("the column `{column}` of the macro `{}`", name.0);
            let label = self.label_of(&labels, label, &what, place)?;
            columns.push((ColumnName::Written(column.into()), label));
        }
        if self.declare(&name, place) {
            self.bodies.push(BodyInFile { body: definition.clone(), place, cell: None });
            self.relation_macros.push(WrittenMacro { name, place, columns: columns.into(), definition });
        }
        Some(())
    }

    /// `(macro <Name> (component ...) [(INIT ...)] (RULE &<rule> <body>) ... (output <port> (<Label> ...) <body>) ...)`.
    fn cell_instance(&mut self, name: LibName, rest: &[SExpr], place: SourcePlace) -> Option<()> {
        let declaration = headed(&rest[1], COMPONENT).expect("the form's `component` form");
        let (component_name, component) = self.component(declaration, rest[1].place())?;
        if component_name != name {
            return self.refuse(format!("the cell instance `{}` declares the component `{}`", name.0, component_name.0), place);
        }
        let mut rest = &rest[2..];
        let init = rest.first().filter(|expr| head_of(expr) == Some(spelling::INIT));
        let cell = self.cells.len();
        let mut bodies = Vec::new();
        let (definition, init_scope) = match init {
            Some(expr) => {
                rest = &rest[1..];
                let (instance, _) = self.read(read_instance(expr))?;
                let value = instance.value();
                let key = value.key.iter().flat_map(|key| {
                    let key = key.value();
                    std::iter::once(key.key.body.clone()).chain(key.inputs.iter().map(|input| input.value().body.clone()))
                });
                bodies.extend(key.chain(value.inputs.iter().map(|input| input.value().body.clone())));
                let scope = (value.name.clone(), value.component.clone());
                (CellDefinition::Instance(instance.clone()), Some(scope))
            }
            None => (CellDefinition::Relation, None),
        };
        let mut rules = Vec::new();
        let mut rule_columns = Vec::new();
        while let Some(rule) = rest.first().and_then(|expr| headed(expr, spelling::spelling(spelling::CLAUSE_KEYWORDS, &ClauseKeyword::Rule))) {
            rest = &rest[1..];
            let text = self.symbol(rule.first(), "the rule's name", place)?;
            if !text.starts_with(spelling::DECLARED_MARK) {
                return self.refuse(format!("`{text}` is not a declared name, `&` and a name"), place);
            }
            let rule_name = RelationName(DeclaredName::Written(text.into()));
            let (body, labels) = self.read(read_body(&rule[1..], init))?;
            let columns = labels.iter().map(|(n, _)| ColumnName::Written(n.clone())).collect();
            bodies.push(body.clone());
            rule_columns.push((rule_name.clone(), columns));
            rules.push(CellRule { name: rule_name, body });
        }
        let mut outputs = Vec::new();
        for expr in rest {
            let Some(output) = headed(expr, OUTPUT) else {
                return self.refuse(format!("a cell instance's form after its `RULE` forms is an `({OUTPUT} ...)` form"), expr.place());
            };
            let port = PortName(self.symbol(output.first(), "the output's port", place)?.into());
            let Some(declared) = component.outputs.iter().find(|p| p.name == port) else {
                return self.refuse(format!("`{}` is no output of the cell instance `{}`", port.0, name.0), expr.place());
            };
            let Some(SExpr::List { items: written, .. }) = output.get(1) else {
                return self.refuse("an output's port stands before the list of its labels", expr.place());
            };
            if written.len() != declared.columns.len() {
                return self.refuse(format!("the output `{}` has {} columns, and the form writes {} labels", port.0, declared.columns.len(), written.len()), expr.place());
            }
            let (body, names) = self.read(read_body(&output[2..], init))?;
            let mut labels = Vec::new();
            for label in written.iter() {
                let label = self.symbol(Some(label), "an output's label", place)?;
                let what = format!("a label of the output `{}` of the cell instance `{}`", port.0, name.0);
                labels.push(self.label_of(&names, label, &what, place)?);
            }
            bodies.push(body.clone());
            outputs.push(CellOutput { port, labels: labels.into(), body });
        }
        if self.declare(&name, place) {
            self.bodies.extend(bodies.into_iter().map(|body| BodyInFile { body, place, cell: Some(cell) }));
            self.cells.push(CellScope { inputs: component.inputs.iter().map(|i| i.port.clone()).collect(), rules: rule_columns.into(), init: init_scope });
            let instance = Macro::CellInstance { component, definition, rules: rules.into(), outputs: outputs.into() };
            self.entries.insert(name, LibEntry::Macro(instance));
        }
        Some(())
    }

    /// Reads the forms of the proposers file, and gives each
    /// `(proposer <name> arclog)` form its clause.
    fn proposer_clauses(&mut self, exprs: &[SExpr]) {
        let mut clauses: Vec<(LibName, SourcePlace, Proposer)> = Vec::new();
        for expr in exprs {
            let place = expr.place();
            let Some(rest) = headed(expr, PROPOSER) else {
                self.refuse::<()>("a form of the proposers file is a `(proposer <Name> <atom> ...)` form", place);
                continue;
            };
            let Some(name) = self.symbol(rest.first(), "the proposer's name", place) else { continue };
            let name = LibName(name.into());
            let Some((body, labels)) = self.read(read_body(&rest[1..], None)) else { continue };
            if clauses.iter().any(|(n, _, _)| *n == name) {
                self.fault(CheckId::Scope, format!("the proposer `{}` has two clauses", name.0), place);
                continue;
            }
            let columns = labels.iter().map(|(n, _)| ColumnName::Written(n.clone())).collect();
            self.bodies.push(BodyInFile { body: body.clone(), place, cell: None });
            clauses.push((name, place, Proposer::Arclog { columns, body }));
        }
        for (name, place) in std::mem::take(&mut self.arclog_proposers) {
            match clauses.iter().position(|(n, _, _)| *n == name) {
                Some(index) => {
                    let (name, _, proposer) = clauses.remove(index);
                    self.entries.insert(name, LibEntry::Proposer(proposer));
                }
                None => self.fault(CheckId::Scope, format!("the proposer `{}` has no clause in the proposers file", name.0), place),
            }
        }
        for (name, place, _) in clauses {
            self.fault(CheckId::Scope, format!("the clause of `{}` stands for no `(proposer {} arclog)` form", name.0, name.0), place);
        }
    }

    /// Gives a diagnostic at each atom of a body of either file that reads a
    /// name no form declares, or a column its name does not declare.
    fn check_reads(&mut self) {
        let mut faults = Vec::new();
        for body in &self.bodies {
            let cell = body.cell.map(|cell| &self.cells[cell]);
            each_conjunct(body.body.value(), &mut |conjunct| {
                let (Conjunct::Atom(atom) | Conjunct::Not(Negated::Atom(atom))) = conjunct else { return };
                let atom = atom.value();
                let relation = crate::write::relation_ref(&atom.relation);
                let columns = match self.columns_of(&atom.relation, cell) {
                    Ok(columns) => columns,
                    Err(fault) => {
                        faults.push((CheckId::Scope, format!("an atom of `{relation}` {fault}"), body.place));
                        return;
                    }
                };
                for site in atom.sites.iter().filter(|site| !columns.contains(&site.column)) {
                    let message = format!("an atom of `{relation}` has a site at `{}`, which is no column of `{relation}`", column_display(&site.column));
                    faults.push((CheckId::SiteColumns, message, body.place));
                }
            });
        }
        for (check, message, place) in faults {
            self.fault(check, message, place);
        }
    }

    /// The columns of the relation that `relation` names, read from a body
    /// of either file, within the cell instance `cell` where it stands in
    /// one, or the fault of a read of a name no form declares.
    fn columns_of(&self, relation: &RelationRef, cell: Option<&CellScope>) -> Result<Vec<ColumnName>, String> {
        let names = |columns: &[Column]| columns.iter().map(|c| c.name.clone()).collect();
        match relation {
            RelationRef::Fact(fact) => self.facts.get(fact).map(|c| names(c)).ok_or_else(|| "reads a fact relation that no `fact` form declares".to_string()),
            RelationRef::Lib(name) => {
                if let Some(m) = self.relation_macros.iter().find(|m| m.name == *name) {
                    return Ok(m.columns.iter().map(|(c, _)| c.clone()).collect());
                }
                match self.entries.get(name) {
                    Some(LibEntry::Relation(relation)) => Ok(names(&relation.columns)),
                    Some(LibEntry::Proposer(Proposer::Native { columns })) => Ok(names(columns)),
                    Some(LibEntry::Proposer(Proposer::Arclog { columns, .. })) => Ok(columns.to_vec()),
                    Some(LibEntry::Macro(Macro::Relation { relation, .. })) => Ok(names(&relation.columns)),
                    Some(LibEntry::Component(_) | LibEntry::Macro(Macro::CellInstance { .. })) => Err("reads a component, which an `INIT` form instantiates and no atom reads".to_string()),
                    None => Err("reads a name that no form of the registry file declares".to_string()),
                }
            }
            RelationRef::DefinedPort(port) => {
                let input = cell.and_then(|cell| cell.inputs.iter().find(|input| input.name == *port));
                input.map(|input| names(&input.columns)).ok_or_else(|| "reads no input of its cell instance".to_string())
            }
            RelationRef::Declared(rule) => {
                let rule = cell.and_then(|cell| cell.rules.iter().find(|(name, _)| name == rule));
                rule.map(|(_, columns)| columns.to_vec()).ok_or_else(|| "reads no `RULE` form of its cell instance".to_string())
            }
            RelationRef::Output(output) => {
                let port = match (&output.of, &output.path[..], cell.and_then(|cell| cell.init.as_ref())) {
                    (OutputOwner::Instance(instance), [OutputStep::Port(port)], Some((init, component))) if instance == init => {
                        self.component_of(component).and_then(|c| c.outputs.iter().find(|output| output.name == *port))
                    }
                    _ => None,
                };
                port.map(|port| names(&port.columns)).ok_or_else(|| "reads no output of its cell instance's `INIT` form".to_string())
            }
        }
    }

    /// The component that `name` declares, a component's or a cell
    /// instance's.
    fn component_of(&self, name: &LibName) -> Option<&Component> {
        match self.entries.get(name)? {
            LibEntry::Component(component) | LibEntry::Macro(Macro::CellInstance { component, .. }) => Some(component),
            LibEntry::Relation(_) | LibEntry::Proposer(_) | LibEntry::Macro(Macro::Relation { .. }) => None,
        }
    }

    /// Gives each relation macro its declaration, as [`macro_column_types`]
    /// derives it from the columns of the other forms' names and the modes
    /// of the `relation` forms.
    fn declare_relation_macros(&mut self) {
        let mut lib: StableHashMap<LibName, Box<[Column]>> = StableHashMap::default();
        let mut modes: StableHashMap<LibName, Box<[Mode]>> = StableHashMap::default();
        for (name, entry) in &self.entries {
            match entry {
                LibEntry::Relation(relation) => {
                    lib.insert(name.clone(), relation.columns.clone());
                    modes.insert(name.clone(), relation.modes.clone());
                }
                LibEntry::Proposer(Proposer::Native { columns }) => {
                    lib.insert(name.clone(), columns.clone());
                }
                LibEntry::Proposer(Proposer::Arclog { .. }) | LibEntry::Component(_) | LibEntry::Macro(_) => {}
            }
        }
        let macros: Vec<RelationMacro<'_>> = self
            .relation_macros
            .iter()
            .map(|m| RelationMacro { name: &m.name, place: m.place, columns: &m.columns, definition: m.definition.value() })
            .collect();
        let declarations = macro_column_types(&macros, &lib, &modes);
        match declarations {
            Ok(mut declarations) => {
                for m in std::mem::take(&mut self.relation_macros) {
                    let relation = declarations.remove(&m.name).expect("each relation macro takes a declaration");
                    let labels = m.columns.iter().map(|(_, label)| *label).collect();
                    self.entries.insert(m.name, LibEntry::Macro(Macro::Relation { relation, labels, definition: m.definition }));
                }
            }
            Err(diagnostics) => self.diagnostics.extend(diagnostics),
        }
    }

    /// Gives a diagnostic where an accessor of the registry would have no
    /// value to give: an orientation type with no `constants` form, no `C4`
    /// form or a `C4` constant that is no D4 constant, or a fact relation
    /// with no `fact` form.
    fn check_complete(&mut self) {
        let start = file_start(SourceFile::LibRegistry);
        for (name, text) in spelling::TYPE_NAMES {
            if orientation_type(*name).is_some_and(|ty| !self.constants.contains_key(&ty)) {
                self.fault(CheckId::Scope, format!("the file has no `constants` form of `{text}`"), start);
            }
        }
        match &self.c4 {
            Some((names, place)) => {
                let d4 = self.constants.get(&OrientationType::D4);
                let outside: Vec<String> = names
                    .iter()
                    .filter(|name| d4.is_none_or(|d4| !d4.names.contains(name)))
                    .map(|name| format!("the `C4` constant `{name}` is no `D4` constant"))
                    .collect();
                let place = *place;
                for message in outside {
                    self.fault(CheckId::Scope, message, place);
                }
            }
            None => self.fault(CheckId::Scope, "the file has no `C4` form", start),
        }
        for (fact, text) in spelling::FACT_RELATIONS {
            if !self.facts.contains_key(fact) {
                self.fault(CheckId::Scope, format!("the file has no `fact` form of `{text}`"), start);
            }
        }
    }

    /// The registry read, or the diagnostics of each fault of either file.
    fn registry(self) -> Result<Registry, RegistryError> {
        if !self.diagnostics.is_empty() {
            return Err(RegistryError { diagnostics: self.diagnostics });
        }
        let d4 = self.constants.get(&OrientationType::D4).expect("`check_complete` faults where `D4` has no `constants` form");
        let (names, _) = self.c4.as_ref().expect("`check_complete` faults where the file has no `C4` form");
        let c4 = names.iter().filter_map(|name| d4.constant(OrientationType::D4, name)).collect();
        Ok(Registry {
            entries: self.entries,
            derivations: self.derivations,
            constants: self.constants,
            c4: ConstantSet { constants: c4 },
            facts: self.facts,
        })
    }
}

/// A relation macro of the file, as [`macro_column_types`] reads it.
#[derive(Clone, Copy, Debug)]
pub struct RelationMacro<'a> {
    pub name: &'a LibName,
    /// The place of the macro's form, where a diagnostic on it stands.
    pub place: SourcePlace,
    /// Each column's name and the label of the definition it stands for, in
    /// the order of the macro's columns.
    pub columns: &'a [(ColumnName, LabelId)],
    /// The definition, as [`crate::read::read_body`] gives it.
    pub definition: &'a Body,
}

/// The declaration of each relation macro of `macros`, its columns in order
/// with their types and its modes, or a diagnostic at a macro's form for
/// each fault.
///
/// The type of a column is the type that [`label_type`] gives its label
/// over the definition. A site has the column's type: a column of a lib
/// name that `lib` declares, where the type is fixed or `(pose-or <type>)`,
/// or a column of another macro of `macros`, of the type this gives it. Any
/// other site gives no type.
///
/// The modes are the minimal sets of the columns, other than an orientation
/// type's, whose labels, taken as grounded, let [`grounded_labels`] ground
/// every label of the definition. An atom of a lib relation takes the modes
/// that `modes` gives it, and an atom of another macro of `macros` the modes
/// this gives it. Where the empty set grounds the definition, the macro has
/// no mode, as a relation over a finite domain has none.
///
/// `lib` holds the columns of each lib name that a form other than a
/// relation macro declares, and `modes` the modes of each `relation` form,
/// none for a form with no `modes` form. The macros are read in an order of
/// their reads of one another, so the order of `macros` gives the order of
/// the diagnostics alone. A fault is a cycle of macros that read one
/// another, given at each macro of the cycle; a column whose label's sites
/// have an empty meet, or whose branches give types with no join; a column
/// whose label stands at no site that gives a type; or a definition that no
/// set of the columns grounds. A macro that reads a macro with a fault takes
/// no declaration, and gives no diagnostic of its own for it.
pub fn macro_column_types(
    macros: &[RelationMacro<'_>],
    lib: &StableHashMap<LibName, Box<[Column]>>,
    modes: &StableHashMap<LibName, Box<[Mode]>>,
) -> Result<StableHashMap<LibName, AlgebraRelation>, Vec<crate::diagnostic::Diagnostic>> {
    let mut derivation = MacroDerivation {
        macros,
        lib,
        modes,
        index: macros.iter().enumerate().map(|(i, m)| (m.name.clone(), i)).collect(),
        states: vec![MacroState::Unread; macros.len()],
        stack: Vec::new(),
        diagnostics: Vec::new(),
    };
    for i in 0..macros.len() {
        derivation.read(i);
    }
    if !derivation.diagnostics.is_empty() {
        return Err(derivation.diagnostics);
    }
    let declarations = derivation.states.into_iter().zip(macros).map(|(state, m)| match state {
        MacroState::Declared(relation) => (m.name.clone(), relation),
        _ => unreachable!("a macro with no declaration gives a diagnostic"),
    });
    Ok(declarations.collect())
}

/// Where [`macro_column_types`] stands in its read of one macro.
#[derive(Clone, Debug)]
enum MacroState {
    Unread,
    /// Its reads of other macros are being read, so a read of it now closes
    /// a cycle.
    Reading,
    /// Its declaration, each column of a fixed type.
    Declared(AlgebraRelation),
    /// It has a fault, or reads a macro with one.
    Faulted,
}

struct MacroDerivation<'a, 'b> {
    macros: &'a [RelationMacro<'b>],
    lib: &'a StableHashMap<LibName, Box<[Column]>>,
    modes: &'a StableHashMap<LibName, Box<[Mode]>>,
    index: StableHashMap<LibName, usize>,
    states: Vec<MacroState>,
    /// The macros being read, each reading the next.
    stack: Vec<usize>,
    diagnostics: Vec<crate::diagnostic::Diagnostic>,
}

impl MacroDerivation<'_, '_> {
    /// Reads macro `i` after each macro it reads, and sets its state.
    fn read(&mut self, i: usize) {
        match self.states[i] {
            MacroState::Unread => {}
            MacroState::Reading => {
                self.close_cycle(i);
                return;
            }
            MacroState::Declared(_) | MacroState::Faulted => return,
        }
        self.states[i] = MacroState::Reading;
        self.stack.push(i);
        let mut reads = Vec::new();
        each_conjunct(self.macros[i].definition, &mut |conjunct| {
            if let Conjunct::Atom(atom) | Conjunct::Not(Negated::Atom(atom)) = conjunct {
                if let RelationRef::Lib(name) = &atom.value().relation {
                    if let Some(&j) = self.index.get(name) {
                        reads.push(j);
                    }
                }
            }
        });
        for &j in &reads {
            self.read(j);
        }
        self.stack.pop();
        let read_faulted = reads.iter().any(|&j| !matches!(self.states[j], MacroState::Declared(_)));
        if matches!(self.states[i], MacroState::Faulted) || read_faulted {
            self.states[i] = MacroState::Faulted;
            return;
        }
        let m = self.macros[i];
        let declaration = self.column_types(&m).and_then(|types| {
            let modes = self.modes_of(&m)?;
            let columns = m.columns.iter().zip(types).map(|((name, _), ty)| Column { name: name.clone(), ty: ColumnType::Fixed(ty) });
            Some(AlgebraRelation { columns: columns.collect(), modes })
        });
        self.states[i] = match declaration {
            Some(relation) => MacroState::Declared(relation),
            None => MacroState::Faulted,
        };
    }

    /// Gives a diagnostic at each macro of the cycle that a read of macro
    /// `i`, which is being read, closes, and marks each with a fault.
    fn close_cycle(&mut self, i: usize) {
        let start = self.stack.iter().position(|&j| j == i).expect("a macro being read stands on the stack");
        let cycle: Vec<usize> = self.stack[start..].to_vec();
        let names: Vec<String> = cycle.iter().map(|&j| format!("`{}`", self.macros[j].name.0)).collect();
        for &j in &cycle {
            if matches!(self.states[j], MacroState::Faulted) {
                continue;
            }
            self.states[j] = MacroState::Faulted;
            let message = format!("the macro `{}` reads itself through the macros {}", self.macros[j].name.0, names.join(", "));
            self.diagnostics.push(crate::read::check_error(CheckId::Cycles, message, self.macros[j].place));
        }
    }

    /// The type of each column of `m`, or `None` with a diagnostic for each
    /// column that has a fault.
    fn column_types(&mut self, m: &RelationMacro<'_>) -> Option<Box<[ValueType]>> {
        let mut types = Vec::new();
        let mut faulted = false;
        for (column, label) in m.columns {
            let message = match label_type(m.definition, *label, &|atom, column| self.site_type(atom, column)) {
                Ok(Some(ty)) => {
                    types.push(ty);
                    continue;
                }
                Ok(None) => "stands at no site that gives a type".to_string(),
                Err(LabelFault::EmptyMeet(a, b)) => format!("stands at sites of the types {a:?} and {b:?}, whose meet is empty"),
                Err(LabelFault::NoJoin(a, b)) => format!("takes the types {a:?} and {b:?} from two branches, which have no join"),
            };
            faulted = true;
            let message = format!("the label of the column `{}` of the macro `{}` {message}", column_display(column), m.name.0);
            self.diagnostics.push(crate::read::check_error(CheckId::Types, message, m.place));
        }
        if faulted { None } else { Some(types.into()) }
    }

    /// The modes of `m`, as [`macro_column_types`] gives them, or `None`
    /// with a diagnostic where no set of its columns grounds its definition.
    /// A set that holds a column of an orientation type grounds what the set
    /// without it grounds, so no mode holds one.
    fn modes_of(&mut self, m: &RelationMacro<'_>) -> Option<Box<[Mode]>> {
        let definition_labels = body_labels(m.definition);
        let label_types = |label: LabelId| label_type(m.definition, label, &|atom, column| self.site_type(atom, column)).ok().flatten();
        let atom_modes = |atom: &Atom| self.atom_modes(atom);
        let columns: Vec<usize> = (0..m.columns.len()).collect();
        let grounds = |set: &[usize]| {
            let grounded: StableHashSet<LabelId> = set.iter().map(|&c| m.columns[c].1).collect();
            let reached = grounded_labels(m.definition, &grounded, &atom_modes, &label_types);
            definition_labels.iter().all(|label| reached.contains(label))
        };
        let mut found: Vec<Vec<usize>> = Vec::new();
        for size in 0..=columns.len() {
            for set in subsets_of_size(&columns, size) {
                if found.iter().any(|mode| mode.iter().all(|c| set.contains(c))) {
                    continue;
                }
                if grounds(&set) {
                    found.push(set);
                }
            }
            if found.first().is_some_and(|mode| mode.is_empty()) {
                return Some(Box::default());
            }
        }
        if found.is_empty() {
            let message = format!("no set of the columns of the macro `{}` grounds every label of its definition", m.name.0);
            self.diagnostics.push(crate::read::check_error(CheckId::Grounding, message, m.place));
            return None;
        }
        let modes = found.into_iter().map(|set| Mode { grounded: set.into_iter().map(|c| m.columns[c].0.clone()).collect() });
        Some(modes.collect())
    }

    /// The modes of the relation `atom` reads: a macro's that has its
    /// declaration, or a lib relation's, and none for any other relation.
    fn atom_modes(&self, atom: &Atom) -> &[Mode] {
        let RelationRef::Lib(name) = &atom.relation else { return &[] };
        if let Some(&j) = self.index.get(name) {
            return &self.declared(j).modes;
        }
        self.modes.get(name).map_or(&[], |modes| modes)
    }

    /// The declaration of macro `j`, which a macro that reads it reads once
    /// it has one.
    fn declared(&self, j: usize) -> &AlgebraRelation {
        let MacroState::Declared(relation) = &self.states[j] else {
            unreachable!("a macro takes its declaration only after each macro it reads has one")
        };
        relation
    }

    /// The type of the column `path` gives of the relation `atom` reads,
    /// where that relation is a lib name of `lib` or a macro with its
    /// declaration and `path` is one column. A longer path, a field of a
    /// type parameter's column, gives no type.
    fn site_type(&self, atom: &Atom, path: &[ColumnName]) -> Option<ValueType> {
        let [column] = path else { return None };
        let RelationRef::Lib(name) = &atom.relation else { return None };
        let columns: &[Column] = match self.index.get(name) {
            Some(&j) => &self.declared(j).columns,
            None => self.lib.get(name)?,
        };
        match &columns.iter().find(|c| &c.name == column)?.ty {
            ColumnType::Fixed(ty) | ColumnType::PoseOr(ty) => Some(ty.clone()),
            ColumnType::Pose | ColumnType::SharedPose | ColumnType::Parameter(_) => None,
        }
    }
}

/// The subsets of `items` of `size` elements, each in the order of `items`.
fn subsets_of_size(items: &[usize], size: usize) -> Vec<Vec<usize>> {
    if size == 0 {
        return vec![Vec::new()];
    }
    let mut subsets = Vec::new();
    for (i, &item) in items.iter().enumerate() {
        for mut rest in subsets_of_size(&items[i + 1..], size - 1) {
            rest.insert(0, item);
            subsets.push(rest);
        }
    }
    subsets
}

/// The name of `column`, for a diagnostic.
fn column_display(column: &ColumnName) -> String {
    match column {
        ColumnName::Written(name) => name.to_string(),
        ColumnName::Slot(slot) => format!("slot {slot}"),
    }
}
