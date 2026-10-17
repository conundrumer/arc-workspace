//! Name resolution of a case program, and the dependency graph it gives.
//!
//! Implements `work/engine/reader.md`, Solvers: "The resolver then resolves
//! the names of each case program. A relation that no block of the case
//! derives resolves to an undefined relation", and The dependency graph.
//!
//! The registry and resolver stage writes the bodies.

#![allow(unused_variables, dead_code)]

use crate::diagnostic::Diagnostic;
use crate::hash::StableHash;
use crate::program::path::NodePath;
use crate::program::{ColumnName, InstanceName, PortName, Program, RelationName};
use crate::registry::{LibName, Registry};

/// Whether name resolution expands each lib macro into its definition.
///
/// Implements "A lib name that lib-spec.md defines from other lib names can
/// be expanded into its definition, by a config, as a macro. So a program
/// runs in either form."
#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub enum MacroExpansion {
    Keep,
    Expand,
}

/// A node of the dependency graph, as The dependency graph lists them.
///
/// Implements `work/engine/reader.md`, The dependency graph: "After name resolution, a case program is a directed graph."
#[derive(Clone, PartialEq, Eq, Hash, Debug)]
pub enum DependencyNode {
    Fact(crate::program::FactRelation),
    /// A relation a clause derives.
    Clause(RelationName),
    /// An input of an instance.
    InstanceInput { instance: InstanceName, input: PortName },
    /// An output of an instance.
    InstanceOutput { instance: InstanceName, output: PortName },
    /// A parameter: a `DET` relation, read as one node and never through its
    /// body, as Solvers gives for a `DET` of the concept program.
    Parameter(RelationName),
    /// A chosen relation: a `CHOOSE` form's, or a clause's with `ONE` marks.
    Chosen(RelationName),
    /// A `RIGID_DET` assembly.
    RigidAssembly(InstanceName),
    /// A `DEMONSTRATED` relation.
    Demonstrated(RelationName),
    /// An `Unfold` instance with its `step`, `skip` and `take` inputs, which
    /// is one node.
    Unfold(InstanceName),
}

/// The index of a node in a [`DependencyGraph`].
///
/// Implements `work/engine/reader.md`, The dependency graph: "After name resolution, a case program is a directed graph."
#[derive(Clone, Copy, PartialEq, Eq, Hash, Debug)]
pub struct NodeIndex(pub u32);

/// The dependency graph of a case program: each read is an edge from the
/// node read to the node that reads it.
///
/// Implements `work/engine/reader.md`, The dependency graph: "After name resolution, a case program is a directed graph."
#[derive(Clone, Debug, Default)]
pub struct DependencyGraph {
    pub nodes: Box<[DependencyNode]>,
    /// For each node, the nodes it reads.
    pub reads: Box<[Box<[NodeIndex]>]>,
}

impl DependencyGraph {
    /// A cycle of the graph, as the nodes on it, or `None` where the graph is
    /// acyclic.
    ///
    /// Implements `work/engine/reader.md`, Checker: "The checker refuses a cycle in the dependency graph of a case program".
    pub fn find_cycle(&self) -> Option<Vec<NodeIndex>> {
        todo!()
    }
}

/// What a name read in a case program resolves to.
///
/// Implements `work/engine/reader.md`, Solvers: "A relation that no block of the case derives resolves to an undefined relation".
#[derive(Clone, Debug)]
pub enum Resolution {
    /// A node of the case program's dependency graph.
    Node(NodeIndex),
    /// A name of the lib.
    Lib(LibName),
    /// A relation that no block of the case derives: the case is undefined
    /// on each input where a clause reads it.
    Undefined(RelationName),
}

/// A column of a derived relation, resolved to its position.
///
/// Implements "the resolver turns each column name that a read gives into
/// its position".
#[derive(Clone, Copy, PartialEq, Eq, Hash, Debug)]
pub struct ColumnPosition(pub u16);

/// The signature of a name a form reads: the hash of what the name resolves
/// to, its columns and their types. A form's check result is cached on its
/// canonical hash and the signatures of the names it reads, as Checker gives.
///
/// Implements `work/engine/reader.md`, Checker: "the signatures of the names it reads".
#[derive(Clone, Copy, PartialEq, Eq, Hash, Debug)]
pub struct Signature(pub StableHash);

/// A case program after name resolution.
///
/// Implements `work/engine/reader.md`, The dependency graph: "After name resolution, a case program is a directed graph."
#[derive(Clone, Debug)]
pub struct ResolvedProgram {
    pub program: Program,
    pub graph: DependencyGraph,
}

impl ResolvedProgram {
    /// What the name read at `path` resolves to.
    ///
    /// Implements `work/engine/reader.md`, Solvers: "The resolver then resolves the names of each case program."
    pub fn resolution(&self, path: &NodePath) -> Option<&Resolution> {
        todo!()
    }

    /// The position of `column` in the relation that the atom at `atom`
    /// reads.
    ///
    /// Implements `work/engine/reader.md`, Programs as values: "the resolver turns each column name that a read gives into its position".
    pub fn column_position(&self, atom: &NodePath, column: &ColumnName) -> Option<ColumnPosition> {
        todo!()
    }

    /// The signature of the name read at `path`.
    ///
    /// Implements `work/engine/reader.md`, Checker: "the signatures of the names it reads".
    pub fn signature(&self, path: &NodePath) -> Option<Signature> {
        todo!()
    }

    /// The hash of the resolved content of the form at `path`: its canonical
    /// form, with each name it reads standing for what it resolves to.
    ///
    /// Implements "Two values are equal when their resolved content is
    /// equal, whatever file or decode they came from."
    pub fn content_hash(&self, path: &NodePath) -> StableHash {
        todo!()
    }
}

/// Resolves the names of `case`, a case program that `crate::solver` gives,
/// or a synthesized program.
///
/// Fails with a diagnostic of the scope at each name that resolves to
/// nothing and is no relation a block could derive.
///
/// Implements `work/engine/reader.md`, Solvers: "The resolver then resolves the names of each case program."
pub fn resolve(case: &Program, registry: &Registry, macros: MacroExpansion) -> Result<ResolvedProgram, Vec<Diagnostic>> {
    todo!()
}
