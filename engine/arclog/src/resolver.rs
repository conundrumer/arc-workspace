//! Name resolution of a case program, and the dependency graph it gives.
//!
//! Implements `work/engine/reader.md`, Solvers: "The resolver then resolves
//! the names of each case program. A relation that no block of the case
//! derives resolves to an undefined relation", and The dependency graph.
//!
//! The registry and resolver stage writes the bodies.

#![allow(unused_variables, dead_code)]

use crate::diagnostic::WithDiagnostics;
use crate::hash::StableHash;
use crate::program::path::NodePath;
use crate::program::{
    ColumnName, InstanceName, Node, PortName, Program, ProgramRelation, RelationName, RigidDetName,
};
use crate::registry::{LibName, Registry};

/// Whether name resolution expands each lib macro into its definition.
///
/// Implements `work/engine/reader.md`: "A lib name that lib-spec.md defines from other lib names can
/// be expanded into its definition, by a config, as a macro. So a program
/// runs in either form."
#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub enum MacroExpansion {
    Keep,
    Expand,
}

/// A node of the dependency graph: its kind and the name scope of its
/// declaration, so that two relations of one name that two `DEMO_RULE`
/// forms declare are two nodes.
///
/// Implements `work/engine/reader.md`, The dependency graph: "After name resolution, a case program is a directed graph."
#[derive(Clone, PartialEq, Eq, Hash, Debug)]
pub struct DependencyNode {
    pub kind: DependencyKind,
    pub scope: crate::program::NameScope,
}

/// The kind of a node of the dependency graph, as The dependency graph
/// lists them.
///
/// Implements `work/engine/reader.md`, The dependency graph: "Its nodes are the fact relations, clause relations, instance inputs and outputs, parameters, chosen relations, `RIGID_DET` assemblies and `DEMONSTRATED` relations".
#[derive(Clone, PartialEq, Eq, Hash, Debug)]
pub enum DependencyKind {
    Fact(crate::program::FactRelation),
    /// A relation a clause derives, an instance relation on a `RULE_OR_DET`
    /// line included.
    Clause(ProgramRelation),
    /// An input of an instance.
    InstanceInput { instance: InstanceName, input: PortName },
    /// An output of an instance.
    InstanceOutput { instance: InstanceName, output: PortName },
    /// A parameter: a `DET` relation with no `ONE` mark, read as one node and never through its
    /// body, as Solvers gives for a `DET` of the concept program, with the
    /// values that `DET` keeps for it. A parameter that several blocks of
    /// the case determine is one node, whose values are those every
    /// determination admits. Each read of the parameter's own `DET` bodies
    /// is an edge into the node, so a `DET` that reads a relation which
    /// depends on its own parameter makes a cycle, as Checker gives.
    Parameter(ProgramRelation),
    /// A chosen relation: a `CHOOSE` form's, or a clause's with `ONE` marks,
    /// a `DET` with `(ONE)` included, which is a chosen relation at the task
    /// level, as `work/engine/cases.md` gives. An open parameter, a `DET`
    /// that ends in `(ONE)`, that several blocks of the case determine is
    /// one node, whose values are those every determination admits, as a
    /// [`DependencyKind::Parameter`] is.
    Chosen(RelationName),
    /// A `RIGID_DET` form: one node for its assemblies, one assembly, or,
    /// for a keyed form, one per key row, as `docs/rigid.md`, Form, gives.
    RigidAssembly(RigidDetName),
    /// A `DEMONSTRATED` relation.
    Demonstrated(RelationName),
    /// An instance of a component with inputs that read its outputs, as
    /// `Unfold`'s `step`, `skip` and `take` do, with those inputs and its
    /// outputs: one node. The registry marks those inputs,
    /// [`crate::registry::InputPort::reads_outputs`], so the resolver names
    /// no component.
    RecursiveInstance(InstanceName),
}

/// The index of a node in a [`DependencyGraph`].
///
/// Implements `work/engine/reader.md`, The dependency graph: "After name resolution, a case program is a directed graph."
#[derive(Clone, Copy, PartialEq, Eq, Hash, Debug)]
pub struct GraphNodeIndex(pub u32);

/// The dependency graph of a case program: each read is an edge from the
/// node read to the node that reads it.
///
/// Implements `work/engine/reader.md`, The dependency graph: "After name resolution, a case program is a directed graph."
#[derive(Clone, Debug, Default)]
pub struct DependencyGraph {
    pub nodes: Box<[DependencyNode]>,
    /// For each node, the nodes it reads.
    pub reads: Box<[Box<[GraphNodeIndex]>]>,
}

impl DependencyGraph {
    /// A cycle of the graph, as the nodes on it, or `None` where the graph is
    /// acyclic.
    ///
    /// Implements `work/engine/reader.md`, Checker: "The checker refuses a cycle in the dependency graph of a case program".
    pub fn find_cycle(&self) -> Option<Vec<GraphNodeIndex>> {
        todo!()
    }
}

/// What a name read in a case program resolves to.
///
/// Implements `work/engine/reader.md`, Solvers: "A relation that no block of the case derives resolves to an undefined relation".
#[derive(Clone, Debug)]
pub enum Resolution {
    /// A node of the case program's dependency graph.
    Node(GraphNodeIndex),
    /// A name of the lib.
    Lib(LibName),
    /// A relation that no block of the case derives: the case is undefined
    /// on each input where a clause reads it.
    Undefined(ProgramRelation),
    /// A name that resolves to nothing and is no relation a block could
    /// derive: a scope error, which the resolver reports.
    Unresolved,
}

/// A column of a derived relation, resolved to its canonical position: the
/// position of its label in the canonical labeling of the clause, as
/// [`crate::program::canonical::CanonicalLabeling`] gives it.
///
/// Implements `work/engine/reader.md`: "with its columns in the canonical positions of their labels, and the resolver turns each column name that a read gives into its position".
#[derive(Clone, Copy, PartialEq, Eq, Hash, Debug)]
pub struct ColumnPosition(pub u16);

/// The signature of a name a form reads: the hash of what the name resolves
/// to, its columns and their types. A form's check result is cached on its
/// canonical hash and the signatures of the names it reads, as Checker gives.
///
/// Implements `work/engine/reader.md`, Checker: "the signatures of the names it reads".
#[derive(Clone, Copy, PartialEq, Eq, Hash, Debug)]
pub struct Signature(pub StableHash);

/// The resolved content of a node of a case program: its canonical form,
/// with each name it reads standing for the resolved content of what it
/// resolves to. Two contents are equal when their hashes match and then
/// their canonical forms do.
///
/// Implements `work/engine/reader.md`, Programs as values: "Two values are equal when their resolved content is equal, whatever file or decode they came from."
#[derive(Clone, Debug)]
pub struct ResolvedContent {
    form: crate::program::canonical::CanonicalForm,
}

impl ResolvedContent {
    /// The hash of the content's canonical form.
    ///
    /// Implements `work/engine/reader.md`, Programs as values: "Each syntax node holds a hash of its canonical form".
    pub fn content_hash(&self) -> StableHash {
        todo!()
    }
}

impl PartialEq for ResolvedContent {
    fn eq(&self, other: &Self) -> bool {
        todo!()
    }
}

impl Eq for ResolvedContent {}

impl std::hash::Hash for ResolvedContent {
    fn hash<H: std::hash::Hasher>(&self, state: &mut H) {
        todo!()
    }
}

/// A case program after name resolution.
///
/// Implements `work/engine/reader.md`, The dependency graph: "After name resolution, a case program is a directed graph."
#[derive(Clone, Debug)]
pub struct ResolvedProgram {
    pub program: Node<Program>,
    pub graph: DependencyGraph,
    /// The path of the form of each node of the graph, by its index.
    forms: Box<[NodePath]>,
    resolutions: crate::hash::StableHashMap<NodePath, Resolution>,
    signatures: crate::hash::StableHashMap<NodePath, Signature>,
    positions: crate::hash::StableHashMap<NodePath, ColumnPosition>,
    groups: crate::hash::StableHashMap<NodePath, crate::relations::ColumnGroup>,
    proposer_columns: crate::hash::StableHashMap<(NodePath, usize), Box<[ColumnName]>>,
}

impl ResolvedProgram {
    /// What the name read at `path` resolves to. Each path that a method of
    /// `ResolvedProgram` takes walks as [`crate::program::path::node_at`]
    /// gives.
    ///
    /// Implements `work/engine/reader.md`, Solvers: "The resolver then resolves the names of each case program."
    pub fn resolution(&self, path: &NodePath) -> Option<&Resolution> {
        todo!()
    }

    /// The position, in the rows of the relation its atom reads, of the
    /// column that the site at `site` names. A site on a field of a record,
    /// such as `(:P P2)` in `(:key (:P P2))`, names that field's column of
    /// the record's column group, so it is told apart from a column of the
    /// same name, `(:P P2)` beside it.
    ///
    /// Implements `work/engine/reader.md`, Programs as values: "the resolver turns each column name that a read gives into its position", and Terms: "A key or a type parameter bound to several fields takes one column per field, as a site names them by projection".
    pub fn column_position(&self, site: &NodePath) -> Option<ColumnPosition> {
        todo!()
    }

    /// The column group that the site at `site` reads, where the site is on
    /// a column of a record, the key's or a type parameter's.
    ///
    /// Implements `work/engine/reader.md`, Terms: "A component works over a short array of term ids at each such column group."
    pub fn column_group(&self, site: &NodePath) -> Option<crate::relations::ColumnGroup> {
        todo!()
    }

    /// The signature of the name read at `path`.
    ///
    /// Implements `work/engine/reader.md`, Checker: "the signatures of the names it reads".
    pub fn signature(&self, path: &NodePath) -> Option<Signature> {
        todo!()
    }

    /// The path of the form that gives `node` of the graph, so that the cycle
    /// check reports each form on a cycle.
    ///
    /// Implements `work/engine/reader.md`, Checker: "The checker refuses a cycle in the dependency graph of a case program".
    pub fn form_of(&self, node: GraphNodeIndex) -> &NodePath {
        todo!()
    }

    /// The resolved content of the node at `path`, or `None` where `path`
    /// names no node. The empty path names the whole program, whose content
    /// is that of its forms, with no order and no names.
    ///
    /// Implements `work/engine/reader.md`: "Two values are equal when their resolved content is
    /// equal, whatever file or decode they came from."
    pub fn content(&self, path: &NodePath) -> Option<ResolvedContent> {
        todo!()
    }

    /// The name of the stored parameter's column that each column of the
    /// proposer at `index` of the clause at `clause` stands for, in the
    /// proposer's column order.
    ///
    /// Implements `work/engine/reader.md`, Checker: "A `DET_OR_RULE` line maps a proposer's columns by that order onto the stored parameter's columns, ... and name resolution then gives each the stored parameter's name."
    pub fn proposer_columns(&self, clause: &NodePath, index: usize) -> Option<&[ColumnName]> {
        todo!()
    }
}

/// The concept program's resolution, which the `DET` forms that a case
/// takes from the concept program read through: each of those forms, at its
/// path in the case program, resolves its reads in `concept`, so it reads the
/// concept program's derivation in every case, and the case reads its
/// parameter as one node.
///
/// Implements `work/engine/reader.md`, Solvers: "A `DET` of the concept program reads the concept program's derivation in every case".
#[derive(Clone, Copy, Debug)]
pub struct ConceptReads<'a> {
    pub concept: &'a ResolvedProgram,
    /// The paths in the case program of the concept program's `DET` forms,
    /// as [`crate::solver::Case::concept_determinations`] gives them.
    pub determinations: &'a [NodePath],
}

/// Resolves the names of `case`, a case program that `crate::solver` gives,
/// or a synthesized program. `concept` is `None` for a synthesized program
/// and for the concept case. `derived` holds the relations that some block
/// of the solver derives, as [`crate::solver::Solver::derived_relations`]
/// gives, or a synthesized program's own: a name among them that no block of
/// the case derives is [`Resolution::Undefined`], and a name among none is
/// [`Resolution::Unresolved`].
///
/// Gives a diagnostic of the scope at each name that resolves to nothing and
/// is no relation a block could derive, which resolves to
/// [`Resolution::Unresolved`], so that every other check still runs over
/// the case.
///
/// Implements `work/engine/reader.md`, Solvers: "The resolver then resolves the names of each case program."
pub fn resolve(
    case: &Node<Program>,
    concept: Option<ConceptReads<'_>>,
    derived: &crate::hash::StableHashSet<ProgramRelation>,
    registry: &Registry,
    macros: MacroExpansion,
) -> WithDiagnostics<ResolvedProgram> {
    todo!()
}
