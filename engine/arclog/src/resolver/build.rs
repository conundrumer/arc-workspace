//! The passes of [`super::resolve`]: the declarations of each scope, the reads and
//! the graph, the content and the columns of each node, then the columns of
//! each site. The declarations and the reads are in `graph`, the sides and
//! the Example columns in `sides`, the content and the columns of each
//! node in `content`, and the columns of each site, the signatures, the
//! proposers' columns and the resolved program in `sites`; each pass is a
//! method of one builder, whose state this module holds.

use std::collections::BTreeSet;
use std::sync::Arc;

use super::columns::{self, Columns};
use super::registry_columns;
use super::names::{ColumnsOf, Names, Target};
use super::{
    rebase, ColumnPosition, ConceptForms, ConceptReads, DependencyKind, DependencyNode, ExamplePath, GraphNodeIndex,
    ResolvedProgram, Resolution, Side, Signature, SolverScope,
};
use crate::diagnostic::{Diagnostic, WithDiagnostics};
use crate::hash::{StableHashMap, StableHashSet};
use crate::program::path::NodePath;
use crate::program::{
    Atom, Clause, ColumnName, FactRelation, InstanceName, NameScope,
    Node, OutputStep, PortName, Program, ProgramRelation, RelationRef,
};
use crate::program::LabelId;
use crate::registry::{Component, Registry};
use crate::relations::ColumnGroup;

/// The nodes of one `INIT` form: the node that reads each input it
/// writes or that a `DET` of the case stores, the node of each output, and
/// its component.
struct InstanceNodes<'r> {
    /// The path of the `INIT` form.
    form: NodePath,
    inputs: Vec<(PortName, GraphNodeIndex)>,
    outputs: Vec<(PortName, GraphNodeIndex)>,
    columns: StableHashMap<PortName, Columns>,
    component: &'r Component,
}

impl InstanceNodes<'_> {
    fn input(&self, name: &PortName) -> Option<GraphNodeIndex> {
        self.inputs.iter().find(|(port, _)| port == name).map(|(_, node)| *node)
    }

    fn every(&self) -> Vec<GraphNodeIndex> {
        let nodes: BTreeSet<u32> = self.inputs.iter().chain(self.outputs.iter()).map(|(_, node)| node.0).collect();
        nodes.into_iter().map(GraphNodeIndex).collect()
    }
}

/// A relation that a form gives a node: the form's path, the relation's
/// path after the form's name where the form gives several relations,
/// and the relation's listing.
struct FormRelation {
    form: NodePath,
    output: Option<Arc<[OutputStep]>>,
    listing: columns::Listing,
}

/// An atom that a form of the case reads: its path, its name scope, and
/// the path of the form whose body holds it.
struct AtomRead<'a> {
    path: NodePath,
    atom: &'a Atom,
    scope: NameScope,
    form: NodePath,
}

struct Builder<'a> {
    case: &'a Node<Program>,
    registry: &'a Registry,
    derived: &'a StableHashSet<ProgramRelation>,
    /// The column names that the reads of each relation name across the
    /// solver's cases.
    solver_reads: &'a StableHashMap<ProgramRelation, Vec<ColumnName>>,
    nodes: Vec<DependencyNode>,
    index: StableHashMap<DependencyNode, GraphNodeIndex>,
    /// The paths of the forms of each node.
    forms: Vec<Vec<NodePath>>,
    /// The relations that the forms of each node give it.
    relations: Vec<Vec<FormRelation>>,
    reads: Vec<BTreeSet<u32>>,
    /// The node of each form that gives one node.
    form_node: StableHashMap<NodePath, GraphNodeIndex>,
    instances: StableHashMap<(NameScope, InstanceName), InstanceNodes<'a>>,
    names: Names,
    /// The path in the concept program of each form that resolves there.
    concept_forms: StableHashMap<NodePath, NodePath>,
    /// The columns of each relation that a form resolving in the concept
    /// program derives, as the concept program gives them.
    concept_columns: StableHashMap<NodePath, Option<Columns>>,
    /// The columns that hold an Example of each relation that a form
    /// resolving in the concept program derives, as the concept program
    /// gives them.
    concept_examples: StableHashMap<NodePath, Arc<[ExamplePath]>>,
    atoms: Vec<AtomRead<'a>>,
    /// The column names that the sites of the reads of each node's
    /// relation name, by the node's index, for a `DET` parameter node
    /// that an atom reads; `None` for every other node.
    read_columns: Vec<Option<Vec<ColumnName>>>,
    /// The side of each node, by its index.
    sides: Vec<Side>,
    /// The columns of each node that hold an Example, by its index.
    examples: Vec<Arc<[ExamplePath]>>,
    /// The columns that hold an Example of each relation of a node whose
    /// forms give it several, by the node and the relation's output path,
    /// which a read of that relation reads.
    output_examples: StableHashMap<(GraphNodeIndex, Arc<[OutputStep]>), Arc<[ExamplePath]>>,
    /// The side of each form whose reads the case resolves.
    form_sides: StableHashMap<NodePath, Side>,
    clauses: Vec<(NodePath, &'a Clause)>,
    resolutions: StableHashMap<NodePath, Resolution>,
    signatures: StableHashMap<NodePath, Signature>,
    positions: StableHashMap<NodePath, ColumnPosition>,
    /// The position in its node's rows of each column a form gives, by
    /// the form's path and the column's label.
    label_positions: StableHashMap<(NodePath, LabelId), ColumnPosition>,
    groups: StableHashMap<NodePath, ColumnGroup>,
    proposer_columns: StableHashMap<(NodePath, usize), Box<[ColumnName]>>,
    /// The path of each read that its form reads in its lifted form.
    lifted: StableHashSet<NodePath>,
    diagnostics: Vec<Diagnostic>,
}

pub(super) fn resolve(
    case: &Node<Program>,
    concept: Option<ConceptReads<'_>>,
    scope: &SolverScope,
    registry: &Registry,
) -> WithDiagnostics<ResolvedProgram> {
    let mut builder = Builder {
        case,
        registry,
        derived: &scope.derived,
        solver_reads: &scope.read_columns,
        nodes: Vec::new(),
        index: StableHashMap::default(),
        forms: Vec::new(),
        relations: Vec::new(),
        reads: Vec::new(),
        form_node: StableHashMap::default(),
        instances: StableHashMap::default(),
        names: Names::default(),
        concept_forms: StableHashMap::default(),
        concept_columns: StableHashMap::default(),
        concept_examples: StableHashMap::default(),
        atoms: Vec::new(),
        read_columns: Vec::new(),
        sides: Vec::new(),
        examples: Vec::new(),
        output_examples: StableHashMap::default(),
        form_sides: StableHashMap::default(),
        clauses: Vec::new(),
        resolutions: StableHashMap::default(),
        signatures: StableHashMap::default(),
        positions: StableHashMap::default(),
        label_positions: StableHashMap::default(),
        groups: StableHashMap::default(),
        proposer_columns: StableHashMap::default(),
        lifted: StableHashSet::default(),
        diagnostics: Vec::new(),
    };
    for fact in [FactRelation::Input, FactRelation::ExInput, FactRelation::ExOutput] {
        let node = builder.node(DependencyKind::Fact(fact), &NameScope::Program, None);
        let columns = Columns::of_names(registry.fact_columns(fact).iter().map(|column| column.name.clone()));
        builder.target(&NameScope::Program, RelationRef::Fact(fact), Target { node, columns: ColumnsOf::Fixed(columns) });
    }
    if let Some(concept) = concept {
        builder.take_concept(concept);
    }
    let forms = &case.value().forms;
    let mut pending = Vec::new();
    for (index, form) in forms.iter().enumerate() {
        builder.declare(form, NodePath::top(index as u32), &NameScope::Program, &mut pending);
    }
    for (scope, relation, target) in pending {
        builder.target(&scope, relation, target);
    }
    for (index, form) in forms.iter().enumerate() {
        builder.read_form(form, NodePath::top(index as u32), &NameScope::Program);
    }
    builder.read_columns();
    builder.sides();
    builder.contents();
    builder.sites();
    builder.proposers();
    let concept = concept.map(|concept| {
        builder.copy_concept(concept);
        ConceptForms { program: Arc::clone(concept.concept), paths: std::mem::take(&mut builder.concept_forms) }
    });
    builder.finish(concept)
}

impl<'a> Builder<'a> {
    /// The column names that the sites of the reads of each `DET`
    /// parameter node name: the reads of the case, then the reads across
    /// the solver's cases that [`SolverScope::read_columns`] gives.
    fn read_columns(&mut self) {
        let mut named: Vec<Option<Vec<ColumnName>>> = vec![None; self.nodes.len()];
        for read in &self.atoms {
            let Resolution::Node(node) = self.resolutions[&read.path] else { continue };
            if matches!(self.nodes[node.0 as usize].kind, DependencyKind::Parameter(_)) {
                let names = named[node.0 as usize].get_or_insert_with(Vec::new);
                super::add_columns(names, read.atom.sites.iter().map(|site| &site.column));
            }
        }
        for (index, node) in self.nodes.iter().enumerate() {
            let DependencyKind::Parameter(relation) = &node.kind else { continue };
            if let Some(columns) = self.solver_reads.get(relation) {
                super::add_columns(named[index].get_or_insert_with(Vec::new), columns);
            }
        }
        self.read_columns = named;
    }

    /// Whether the relation of `node` keeps the column `column` of its
    /// clause: a column of a `DET` parameter node that an atom reads is
    /// kept where a site of a read of the relation names it, and every
    /// column of every other node is kept.
    fn keeps(&self, node: usize, column: &ColumnName) -> bool {
        self.read_columns[node].as_ref().is_none_or(|names| names.contains(column))
    }

    fn is_fact(&self, node: GraphNodeIndex) -> bool {
        matches!(self.nodes[node.0 as usize].kind, DependencyKind::Fact(_))
    }

}

#[path = "build_content.rs"]
mod content;

#[path = "build_graph.rs"]
mod graph;

#[path = "build_sides.rs"]
mod sides;

#[path = "build_sites.rs"]
mod sites;
