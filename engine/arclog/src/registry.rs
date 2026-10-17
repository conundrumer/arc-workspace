//! The lib registry: the names of the lib, and what each declares.
//!
//! Implements `work/engine/reader.md`, Checker: "The lib registry supplies
//! the names of the lib. It is embedded from a tracked file under
//! `engine/lib/` when the engine is compiled, so the wheel reads no file for
//! it, and a test parses it, so a fault of the file fails the engine's
//! tests." and "A new lib element adds a registry entry and changes no
//! checker code."
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
//!   included. Each mode lists the columns that must be grounded for the
//!   relation to ground the others; a relation over a finite domain has no
//!   `modes` form.
//! - `(component <name> <construction|detector|task-structure> (type-parameters <t> ...)
//!   (inputs (<input> (<column> <type>) ... [(default <row> ...)] [reads-outputs]) ...)
//!   (outputs (<output> (<column> <type>) ...) ...))`: a construction, a
//!   detector or a task-structure component, its inputs in the order the component declares them. An
//!   input marked `reads-outputs` reads the instance's outputs, as
//!   `Unfold`'s `step`, `skip` and `take` do.
//! - `(proposer <name> native (columns (<Column> <type>) ...))`: a native
//!   proposer, such as a domain proposer.
//! - `(proposer <name> arclog)`: a proposer written in arclog, whose clause
//!   stands in `engine/lib/proposers.arclog`, as `work/engine/determination.md`,
//!   Proposers, gives. Its columns are its clause's labels, in the order
//!   they first stand in the clause.
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
//! - `(macro <name> (columns (<Column> <type> <Label>) ...) (modes ...) <body>)`:
//!   a lib relation that `docs/lib-spec.md`, Conventions, defines from other
//!   lib names, each column with its type and the label of the definition
//!   it stands for, its modes as a `relation` form gives them, and its
//!   definition.
//! - `(macro <name> (component ...) [(INIT ...)] (output <port> (<Label> ...) <body>) ...)`:
//!   a cell instance, its declaration as a `component` form gives it, the
//!   `INIT` form of the underlying construction where it has one, and a body
//!   for each of its outputs, as [`Macro::CellInstance`] gives. Within these
//!   bodies an atom `(self.<port> <sites>)` reads the cell instance's own
//!   input `<port>`, as [`crate::program::RelationRef::DefinedPort`] holds it.
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
//!
//! The registry and resolver stage writes the bodies and the file's entries.

#![allow(unused_variables, dead_code)]

use crate::hash::StableHashMap;
use crate::program::{Body, ColumnName, Node, PortName};
use crate::terms::{OrientationConstant, OrientationType};
use crate::types::ValueType;

/// The text of the registry file, put into the crate when it is compiled.
///
/// Implements `work/engine/reader.md`, Checker: "It is embedded from a tracked file under `engine/lib/` when the engine is compiled, so the wheel reads no file for it".
pub const REGISTRY_TEXT: &str = include_str!("../../lib/registry.sexpr");

/// The text of `engine/lib/proposers.arclog`, put into the crate when it is
/// compiled, and read by [`crate::read::read_sexprs`] with
/// [`crate::layout::SourceFile::LibProposers`] and [`crate::read::read_body`].
///
/// Implements `work/engine/reader.md`, Checker: "so the wheel reads no file for it", and `work/engine/determination.md`, Proposers.
pub const PROPOSERS_TEXT: &str = include_str!("../../lib/proposers.arclog");

/// A name of the lib: a relation, a component, a proposer, a derivation or
/// a macro, as the file writes it: `margin`, `Connectivity`,
/// `DominantColor`, `Frame`. An orientation constant is named by
/// [`Registry::orientation_constant`] instead.
///
/// Implements `work/engine/reader.md`, Checker: "The lib registry supplies the names of the lib."
#[derive(Clone, PartialEq, Eq, Hash, Debug)]
pub struct LibName(pub Box<str>);

/// The name of a component's type parameter, such as `t` or `key`.
///
/// Implements `work/engine/reader.md`, Checker: "A construction or a detector declares its type parameters".
#[derive(Clone, PartialEq, Eq, Hash, Debug)]
pub struct TypeParameter(pub Box<str>);

/// The type a lib column declares.
///
/// Implements `work/engine/equivariance.md`, The `RIGID_DET` frame: "A `:Pose` column has the type Pose of its assembly."
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
    /// as `d4_elem`'s column is D4 or takes its label's Pose type, as
    /// `docs/rigid.md`, The pose, gives: "every D4 element is a pose".
    PoseOr(ValueType),
    /// A type parameter of the component, made concrete by an instance's
    /// binding.
    Parameter(TypeParameter),
}

/// A declared column: its name and type.
///
/// Implements `work/engine/reader.md`, Checker: "The lib registry supplies the names of the lib."
#[derive(Clone, PartialEq, Eq, Hash, Debug)]
pub struct Column {
    pub name: ColumnName,
    pub ty: ColumnType,
}

/// A mode of an algebra relation: the columns whose labels must be grounded
/// for its other columns to be grounded, as Grounding gives.
///
/// Implements `work/engine/reader.md`, Checker: "An algebra relation ... declares its columns, types and modes."
#[derive(Clone, PartialEq, Eq, Hash, Debug)]
pub struct Mode {
    pub grounded: Box<[ColumnName]>,
}

/// An algebra relation, a relation of the box algebra or the orientation
/// algebra.
///
/// Implements `work/engine/reader.md`, Checker: "An algebra relation ... declares its columns, types and modes."
#[derive(Clone, Debug)]
pub struct AlgebraRelation {
    pub columns: Box<[Column]>,
    /// Empty for a relation over a finite domain.
    pub modes: Box<[Mode]>,
}

/// The kind of a component, as `docs/lib-spec.md`, Kinds of content, gives.
/// A task-structure component, `Choose` or `DemonstrationConsistency`, is
/// the component of a `CHOOSE` or a `DEMONSTRATED` form, whose ports the
/// registry declares as it declares a construction's.
#[derive(Clone, Copy, PartialEq, Eq, Hash, Debug)]
pub enum ComponentKind {
    Construction,
    Detector,
    TaskStructure,
}

/// One input or output of a component.
///
/// Implements `work/engine/reader.md`, Checker: "A construction or a detector declares its type parameters, its inputs in the order the component declares them, with their defaults, and its outputs."
#[derive(Clone, Debug)]
pub struct Port {
    pub name: PortName,
    pub columns: Box<[Column]>,
}

/// An input of a component, with its default rows, which hold where the
/// instance writes no clause for the input.
///
/// Implements `work/engine/reader.md`, Checker: "its inputs in the order the component declares them, with their defaults".
#[derive(Clone, Debug)]
pub struct InputPort {
    pub port: Port,
    pub default: Option<DefaultRows>,
    /// Whether the input reads the instance's outputs, under the rule of
    /// `docs/lib-spec.md`, Construction: "its `step`, `skip` and `take` read
    /// its outputs through atoms whose every variable another atom of the
    /// clause grounds".
    pub reads_outputs: bool,
}

/// The default rows of an input, as a set: it gives membership and each row,
/// and no position of a row, so no caller can pick one default by its place
/// in the file.
///
/// Implements `work/engine/code-design-plan.md`, Rules: "no lib interface makes a free choice".
#[derive(Clone, Debug, Default)]
pub struct DefaultRows {
    rows: crate::hash::StableHashSet<Box<[crate::program::DataValue]>>,
}

impl DefaultRows {
    /// Each default row. No output may read the order they come in.
    ///
    /// Implements `work/engine/reader.md`, Checker: "its inputs in the order the component declares them, with their defaults".
    #[allow(unreachable_code)]
    pub fn each(&self) -> impl Iterator<Item = &[crate::program::DataValue]> + '_ {
        todo!();
        std::iter::empty()
    }
}

/// A construction or a detector.
///
/// Implements `work/engine/reader.md`, Checker: "A construction or a detector declares its type parameters, its inputs in the order the component declares them, with their defaults, and its outputs."
#[derive(Clone, Debug)]
pub struct Component {
    pub kind: ComponentKind,
    pub type_parameters: Box<[TypeParameter]>,
    /// The inputs in the order the component declares them.
    pub inputs: Box<[InputPort]>,
    pub outputs: Box<[Port]>,
}

/// A proposer, as `work/engine/determination.md`, Proposers, gives.
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
///
/// Implements `work/engine/reader.md`, Checker: "A lib name that lib-spec.md defines from other lib names can be expanded into its definition".
#[derive(Clone, Debug)]
pub enum LibEntry {
    Relation(AlgebraRelation),
    Component(Component),
    Proposer(Proposer),
    Macro(Macro),
}

/// A fixed derivation of a table, such as `Frame` or `Division`: the fields
/// of each row of the values a `param` form writes for it, and the columns
/// of the table it derives.
///
/// Implements `docs/arcdata.md`, Params: "A parameter whose value is a table that a fixed derivation gives is written as the values the table derives from", and `docs/arclog.md`, Program: "`(DET &frame Frame)`".
#[derive(Clone, Debug)]
pub struct Derivation {
    pub fields: Box<[Column]>,
    pub columns: Box<[Column]>,
}

/// A lib name that `docs/lib-spec.md`, Conventions, defines from other lib
/// names, with its declaration and its definition, which the resolver
/// expands under [`crate::resolver::MacroExpansion::Expand`]. The
/// declaration serves the checks under
/// [`crate::resolver::MacroExpansion::Keep`], the form `gen/` is written in.
///
/// Implements `work/engine/reader.md`, Checker: "A lib name that lib-spec.md defines from other lib names can be expanded into its definition, by a config, as a macro. So a program runs in either form", and `docs/lib-spec.md`, Conventions: "the definition of a relation or cell instance the lib holds".
#[derive(Clone, Debug)]
pub enum Macro {
    /// A lib relation: its declaration, its columns, types and modes, the
    /// label of the definition that each of its columns stands for, in the
    /// order of the declaration's columns, and its definition. The expansion
    /// of an atom of the macro puts the label at each of its sites in the
    /// place of the column's label in the definition.
    Relation {
        relation: AlgebraRelation,
        labels: Box<[crate::program::LabelId]>,
        definition: Node<Body>,
    },
    /// A cell instance: its declaration as a component, its type
    /// parameters, inputs in order with their defaults, and outputs; its
    /// definition over the underlying construction or relation; and a body
    /// for each of its outputs.
    CellInstance {
        component: Component,
        definition: CellDefinition,
        outputs: Box<[CellOutput]>,
    },
}

/// What a cell instance is defined over, as `docs/lib-spec.md`, Cell
/// instances, pairs them.
///
/// Implements `docs/lib-spec.md`, Cell instances: "The pairs: Quotient and Connectivity, Propagation and Flood, Walk and Ray, Distance and CellDistance, `divide` and Division."
#[derive(Clone, Debug)]
pub enum CellDefinition {
    /// An `INIT` form of the underlying construction with its domain inputs
    /// populated, whose other input bodies read the cell instance's inputs
    /// by their port names, as Connectivity over Quotient.
    Instance(Node<crate::program::Instance>),
    /// No instance: the outputs' bodies read the underlying relation over
    /// the cell instance's inputs, as Division over `divide`.
    Relation,
}

/// An output of a cell instance, as a body over the outputs of its
/// definition's instance, where it has one, and its own inputs: the output's
/// port, the label of the body that each of its columns stands for, in the
/// order of the port's columns, and the body.
///
/// Implements `docs/lib-spec.md`, Cell instances: "A composition whose only inputs are the domain its constructions take ... gets a name in the lib".
#[derive(Clone, Debug)]
pub struct CellOutput {
    pub port: PortName,
    pub labels: Box<[crate::program::LabelId]>,
    pub body: Node<Body>,
}

/// The constants of one orientation type, as a set: it gives membership
/// and each constant, and no position of a constant, so no caller can pick
/// one constant by its place in the file.
///
/// Implements `work/engine/code-design-plan.md`, Rules: "no lib interface makes a free choice".
#[derive(Clone, Debug, Default)]
pub struct ConstantSet {
    constants: crate::hash::StableHashSet<OrientationConstant>,
}

impl ConstantSet {
    /// Whether `constant` is in the set.
    ///
    /// Implements `docs/lib-spec.md`, The orientation algebra: "The enumerations".
    pub fn contains(&self, constant: OrientationConstant) -> bool {
        todo!()
    }

    /// Each constant of the set. No output may read the order they come in,
    /// as `work/engine/equivariance.md`, Determinism, gives.
    ///
    /// Implements `docs/lib-spec.md`, The orientation algebra: "The enumerations".
    #[allow(unreachable_code)]
    pub fn each(&self) -> impl Iterator<Item = OrientationConstant> + '_ {
        todo!();
        std::iter::empty()
    }
}

/// A fault of the registry file, reported when it is first read.
///
/// Implements `work/engine/reader.md`, Checker: "The lib registry supplies the names of the lib."
#[derive(Clone, Debug)]
pub struct RegistryError {
    pub diagnostics: Vec<crate::diagnostic::Diagnostic>,
}

/// The lib registry.
///
/// Implements `work/engine/reader.md`, Checker: "The lib registry supplies the names of the lib."
#[derive(Debug)]
pub struct Registry {
    entries: StableHashMap<LibName, LibEntry>,
    /// The derivations, apart from the entries, since a name such as
    /// `Frame` or `Division` is both a component and a derivation.
    derivations: StableHashMap<LibName, Derivation>,
    constants: StableHashMap<Box<str>, OrientationConstant>,
    c4: ConstantSet,
    facts: StableHashMap<crate::program::FactRelation, Box<[Column]>>,
}

impl Registry {
    /// The registry of [`REGISTRY_TEXT`], read on first use.
    ///
    /// A fault of the file fails the test `registry_file`, so this panics on
    /// one.
    ///
    /// Implements `work/engine/reader.md`, Checker: "so the wheel reads no file for it".
    pub fn get() -> &'static Registry {
        todo!()
    }

    /// The registry that `text` declares, with the proposers that
    /// `proposers` writes in arclog, which are read with the entries of
    /// `text`. [`Registry::get`] gives it [`REGISTRY_TEXT`] and
    /// [`PROPOSERS_TEXT`].
    ///
    /// Implements `work/engine/reader.md`, Checker: "The lib registry supplies the names of the lib."
    pub fn parse(text: &str, proposers: &str) -> Result<Registry, RegistryError> {
        todo!()
    }

    /// What `name` declares, or `None` where the lib has no such name.
    ///
    /// Implements `work/engine/reader.md`, Checker: "The lib registry supplies the names of the lib."
    pub fn entry(&self, name: &LibName) -> Option<&LibEntry> {
        todo!()
    }

    /// The derivation that `name` declares, which a `DET` names in place of
    /// a proposer, or `None` where the lib declares no derivation of that
    /// name.
    ///
    /// Implements `docs/arclog.md`, Program: "names the derivation in place of a proposer, `(DET &frame Frame)` or `(DET &tile_decompose Division)`".
    pub fn derivation(&self, name: &LibName) -> Option<&Derivation> {
        todo!()
    }

    /// The orientation constant written `name`, such as `DIR_T`.
    ///
    /// Implements `docs/lib-spec.md`, The orientation algebra: "The constants of each type, `DIR_T` through `SYM_D4`."
    pub fn orientation_constant(&self, name: &str) -> Option<OrientationConstant> {
        todo!()
    }

    /// The name of `constant`, for a writer.
    ///
    /// Implements `docs/lib-spec.md`, The orientation algebra: "The constants of each type".
    pub fn constant_name(&self, constant: OrientationConstant) -> &str {
        todo!()
    }

    /// The constants of `ty`, for a domain proposer and for `<ty>_elem`.
    ///
    /// Implements `docs/lib-spec.md`, The orientation algebra: "The enumerations".
    pub fn constants_of(&self, ty: OrientationType) -> &ConstantSet {
        todo!()
    }

    /// The D4 constants that are C4, the rotations, as `C4` stands under
    /// `D4`.
    ///
    /// Implements `work/engine/reader.md`, Checker: "`C4` under `D4`", and `docs/lib-spec.md`, The orientation algebra: "`d4_elem` and `c4_elem`".
    pub fn c4_constants(&self) -> &ConstantSet {
        todo!()
    }

    /// The columns of `fact`, with their types, which the resolver turns a
    /// read's column names into positions by and the checker types by.
    ///
    /// Implements `docs/arclog.md`, Program: "`ex_input` and `ex_output` carry an Example column `E` first", and `work/engine/reader.md`, Checker: "the columns of each site".
    pub fn fact_columns(&self, fact: crate::program::FactRelation) -> &[Column] {
        todo!()
    }
}
