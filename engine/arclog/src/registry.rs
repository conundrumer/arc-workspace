//! The lib registry: the names of the lib, and what each declares.
//!
//! Implements `work/engine/reader.md`, Checker: "The lib registry supplies
//! the names of the lib. It is built from a tracked file under `engine/lib/`
//! when the engine is compiled, so the wheel reads no file for it." and "A
//! new lib element adds a registry entry and changes no checker code."
//!
//! # The file
//!
//! The file is `engine/lib/registry.sexpr`. It is s-expressions, read by the
//! reader of [`crate::read::read_sexprs`], so the engine has one reader for
//! every s-expression file. `include_str!` puts its text into the compiled
//! crate, and [`Registry::get`] reads that text once, on first use. A build
//! script could load it into Rust code at compile time only through a second
//! reader, since a build script cannot call the crate it builds.
//!
//! Each top-level form declares one lib element, by its head:
//!
//! - `(relation <name> (columns (<Column> <type>) ...) (modes (<Column> ...) ...))`:
//!   an algebra relation, the group relations and `pose_difference`
//!   included. Each mode lists the columns that must be grounded for the
//!   relation to ground the others; a relation over a finite domain has no
//!   `modes` form.
//! - `(component <name> <construction|detector> (type-parameters <t> ...)
//!   (inputs (<input> (<column> <type>) ... [(default <row> ...)]) ...)
//!   (outputs (<output> (<column> <type>) ...) ...))`: a construction or a
//!   detector, its inputs in the order the component declares them.
//! - `(proposer <name> native (columns (<Column> <type>) ...))`: a native
//!   proposer, such as a domain proposer.
//! - `(proposer <name> arclog)`: a proposer written in arclog, whose clause
//!   stands in `engine/lib/proposers.arclog`, as `work/engine/determination.md`,
//!   Proposers, gives. Its columns are its clause's labels, in the order
//!   they first stand in the clause.
//! - `(constants <type> <NAME> ...)`: the constants of an orientation type.
//! - `(macro <name> <body>)`: a lib name that `docs/lib-spec.md`,
//!   Conventions, defines from other lib names, and its definition.
//!
//! A `<type>` is a type name of [`crate::types::ValueType`], `Pose`, or a
//! type parameter of its component. The file declares no `representative`.
//!
//! The registry and resolver stage writes the bodies and the file's entries.

#![allow(unused_variables, dead_code)]

use crate::hash::StableHashMap;
use crate::program::{Body, ColumnName, Node, PortName};
use crate::terms::{OrientationConstant, OrientationType};
use crate::types::ValueType;

/// The text of the registry file, put into the crate when it is compiled.
///
/// Implements `work/engine/reader.md`, Checker: "It is built from a tracked file under `engine/lib/` when the engine is compiled, so the wheel reads no file for it."
pub const REGISTRY_TEXT: &str = include_str!("../../lib/registry.sexpr");

/// A name of the lib: a relation, a component, a proposer, a constant or a
/// macro, as the file writes it: `margin`, `Connectivity`, `DominantColor`.
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

/// Whether a component is a construction or a detector, as
/// `docs/lib-spec.md`, Kinds of content, gives.
#[derive(Clone, Copy, PartialEq, Eq, Hash, Debug)]
pub enum ComponentKind {
    Construction,
    Detector,
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
    pub default: Option<Box<[Box<[crate::program::DataValue]>]>>,
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
    /// A proposer written in arclog: its clause, whose labels in the order
    /// they first stand are its columns.
    Arclog { clause: Node<Body> },
}

/// What a lib name declares.
///
/// Implements `work/engine/reader.md`, Checker: "A lib name that lib-spec.md defines from other lib names can be expanded into its definition".
#[derive(Clone, Debug)]
pub enum LibEntry {
    Relation(AlgebraRelation),
    Component(Component),
    Proposer(Proposer),
    /// A lib name defined from other lib names, and its definition.
    Macro { definition: Node<Body> },
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
    constants: StableHashMap<Box<str>, OrientationConstant>,
}

impl Registry {
    /// The registry of [`REGISTRY_TEXT`], read on first use.
    ///
    /// A fault of the file is a fault of the build, so this panics on one.
    ///
    /// Implements `work/engine/reader.md`, Checker: "so the wheel reads no file for it".
    pub fn get() -> &'static Registry {
        todo!()
    }

    /// The registry that `text` declares.
    ///
    /// Implements `work/engine/reader.md`, Checker: "The lib registry supplies the names of the lib."
    pub fn parse(text: &str) -> Result<Registry, RegistryError> {
        todo!()
    }

    /// What `name` declares, or `None` where the lib has no such name.
    ///
    /// Implements `work/engine/reader.md`, Checker: "The lib registry supplies the names of the lib."
    pub fn entry(&self, name: &LibName) -> Option<&LibEntry> {
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
    pub fn constants_of(&self, ty: OrientationType) -> &[OrientationConstant] {
        todo!()
    }
}
