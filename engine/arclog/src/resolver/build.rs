//! The passes of [`super::resolve`]: the declarations of each scope, the reads and
//! the graph, the content and the columns of each node, then the columns of
//! each site. The declarations and the reads are in `graph`, the sides and
//! the Example columns in `sides`, the content and the columns of each
//! node in `content`, the columns that the reads of a `DET` decide in
//! `read_columns`, and the columns of each site, the signatures, the
//! proposers' columns and the resolved program in `sites`; each pass is a
//! method of one builder, whose state this module holds.

use std::collections::BTreeSet;
use std::sync::Arc;

use super::column_sources;
use super::columns::Columns;
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
    Atom, Clause, ColumnName, FactRelation, Form, InstanceName, NameScope,
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
    listing: column_sources::Listing,
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
    /// relation name, by the node's index, with the columns that its marks
    /// name, for a read-named node that an atom reads
    /// ([`Builder::read_named`]); `None` for every other node.
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
    /// The path of each lifted read that reads the train examples alone.
    train_lifted: StableHashSet<NodePath>,
    diagnostics: Vec<Diagnostic>,
    /// For a layered resolution, the resolution of the forms before the
    /// last, whose nodes come first in every per-node list below, with
    /// empty entries but for `nodes`, `sides` and `examples`, which hold
    /// theirs.
    earlier: Option<Arc<ResolvedProgram>>,
    /// Whether the last form of a layered resolution gave a node that an
    /// earlier form gives, which this resolution does not handle.
    shared_node: bool,
    /// The columns, by earlier read-named node, that the last form of a
    /// layered resolution reads and no earlier read names, which change the
    /// earlier node's entries.
    widenings: Vec<(GraphNodeIndex, Vec<ColumnName>)>,
    /// Whether the columns that a `DET` node keeps stand in the order of their
    /// labels' canonical positions, in place of the order the clause writes
    /// them, so that the content of the node and of each read of it is free of
    /// that order ([`super::ResolvedProgram::query_identity`]).
    canonical_kept: bool,
}

impl<'a> Builder<'a> {
    fn new(case: &'a Node<Program>, scope: &'a SolverScope, registry: &'a Registry, earlier: Option<&Arc<ResolvedProgram>>) -> Self {
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
            train_lifted: StableHashSet::default(),
            diagnostics: Vec::new(),
            earlier: None,
            shared_node: false,
            widenings: Vec::new(),
            canonical_kept: false,
        };
        if let Some(earlier) = earlier {
            let count = earlier.graph.nodes.len();
            builder.nodes = earlier.graph.nodes.to_vec();
            builder.forms = vec![Vec::new(); count];
            builder.relations = (0..count).map(|_| Vec::new()).collect();
            builder.reads = vec![BTreeSet::new(); count];
            builder.read_columns = vec![None; count];
            builder.sides = (0..count).map(|node| earlier.side(GraphNodeIndex(node as u32))).collect();
            builder.examples = (0..count).map(|node| earlier.example_columns_shared(GraphNodeIndex(node as u32), None).clone()).collect();
            builder.names.earlier = Some(Arc::clone(earlier));
            builder.earlier = Some(Arc::clone(earlier));
        }
        builder
    }

    /// The count of the nodes of the earlier forms' resolution.
    fn offset(&self) -> usize {
        self.names.first_node()
    }
}

/// The resolution of `program`, whose forms before its last are the forms
/// of `earlier`, by the passes of [`resolve`] over the last form alone, or
/// `None` where the last form is one this resolution does not handle. A
/// `DEMONSTRATED` last form is handled where `demonstrated` is true.
fn layered(earlier: &Arc<ResolvedProgram>, program: &Node<Program>, registry: &Registry, demonstrated: bool) -> Option<ResolvedProgram> {
    let scope = SolverScope::default();
    let (last, complete) = program.value().forms.split_last()?;
    if earlier.concept().is_some() || earlier.names.earlier.is_some() || earlier.program.value().forms.len() != complete.len() {
        return None;
    }
    match last {
        Form::Clause(clause) if matches!(clause.value().derives, ProgramRelation::Declared(_)) => {}
        Form::Instance(_) | Form::Choose(_) | Form::RigidDet(_) | Form::Out(_) => {}
        Form::Demonstrated(_) if demonstrated => {}
        _ => return None,
    }
    let program_scope = NameScope::Program;
    let mut builder = Builder::new(program, &scope, registry, Some(earlier));
    let path = NodePath::top(complete.len() as u32);
    let mut pending = Vec::new();
    builder.declare(last, path.clone(), &program_scope, &mut pending);
    for (scope, relation, target) in pending {
        builder.target(&scope, relation, target);
    }
    builder.read_form(last, path, &program_scope);
    builder.read_columns();
    if builder.shared_node {
        return None;
    }
    if !builder.widenings.is_empty() {
        let widening: Vec<(ProgramRelation, Vec<ColumnName>)> = builder
            .widenings
            .iter()
            .filter_map(|(node, extra)| {
                let relation = builder.read_named(node.0 as usize)?.relation;
                let mut columns = earlier.read_columns_of(*node).map(<[ColumnName]>::to_vec).unwrap_or_default();
                super::add_columns(&mut columns, extra);
                Some((relation, columns))
            })
            .collect();
        let widened = earlier.widened(widening, registry);
        return layered(&widened, program, registry, demonstrated);
    }
    builder.sides();
    builder.contents();
    builder.sites();
    builder.proposers();
    Some(builder.finish(None).value)
}

pub(super) fn resolve_last(earlier: &Arc<ResolvedProgram>, program: &Node<Program>, registry: &Registry) -> ResolvedProgram {
    layered(earlier, program, registry, false).unwrap_or_else(|| resolve(program, None, &SolverScope::default(), registry).value)
}

pub(super) fn resolve_in_progress(earlier: &Arc<ResolvedProgram>, program: &Node<Program>, registry: &Registry) -> ResolvedProgram {
    layered(earlier, program, registry, true).unwrap_or_else(|| resolve(program, None, &SolverScope::default(), registry).value)
}

/// The grammar's decision at an open relation needs binding and sides,
/// never canonical content, signatures, or placement of sites. In particular
/// it must not canonicalize every completed prefix again at each new form.
pub(super) fn reads_example_column(program: &Node<Program>, read: &NodePath, registry: &Registry) -> bool {
    let Some(top) = read.0.first() else { return false };
    let Some(form) = program.value().forms.get(top.0 as usize) else { return false };
    match form {
        Form::Clause(clause) if matches!(clause.value().keyword, crate::program::ClauseKeyword::Rule | crate::program::ClauseKeyword::RuleOrDet) => return false,
        Form::Out(_) => return false,
        _ => {}
    }
    let scope = SolverScope::default();
    let mut builder = Builder::new(program, &scope, registry, None);
    for fact in [FactRelation::Input, FactRelation::ExInput, FactRelation::ExOutput].into_iter().chain(feature_facts(program)) {
        let node = builder.node(DependencyKind::Fact(fact), &NameScope::Program, None);
        let columns = Columns::of_names(registry.fact_columns(fact).iter().map(|column| column.name.clone()));
        builder.target(&NameScope::Program, RelationRef::Fact(fact), Target { node, columns: ColumnsOf::Fixed(columns) });
    }
    let mut pending = Vec::new();
    for (index, form) in program.value().forms.iter().enumerate() {
        builder.declare(form, NodePath::top(index as u32), &NameScope::Program, &mut pending);
    }
    for (scope, relation, target) in pending {
        builder.target(&scope, relation, target);
    }
    for (index, form) in program.value().forms.iter().enumerate() {
        builder.read_form(form, NodePath::top(index as u32), &NameScope::Program);
    }
    builder.read_columns();
    builder.sides();
    let Some(Resolution::Node(node)) = builder.resolutions.get(read) else { return false };
    // The writer's rule: a read in a `DEMO_RULE` form takes the rule of its
    // own form, and a lifted read is lifted at the form that holds the atom.
    let root = crate::program::path::NodeRef::Program(program.value());
    let Some(form_path) = crate::stream::write::read_form(root, read) else { return false };
    if crate::stream::write::takes_example_column(root, &form_path) {
        !builder.is_fact(*node) && !builder.forms[node.0 as usize].contains(&form_path)
            && builder.sides[node.0 as usize] == super::Side::PerInput
    } else {
        let Some(atom) = builder.atoms.iter().find(|atom| atom.path == *read) else { return false };
        sides::lifted(builder.is_fact(*node), builder.form_sides[&atom.form], builder.sides[node.0 as usize])
    }
}

/// The fact relations that a feature's forms in `program` read, each once: no
/// other program reads them.
fn feature_facts(program: &Node<Program>) -> Vec<FactRelation> {
    let mut facts = Vec::new();
    for (index, form) in program.value().forms.iter().enumerate() {
        for read in crate::check::reads::form_reads(form, &NodePath::top(index as u32)) {
            if let RelationRef::Fact(fact @ (FactRelation::Output | FactRelation::Program(_) | FactRelation::Name(_))) = &read.atom.relation {
                if !facts.contains(fact) {
                    facts.push(*fact);
                }
            }
        }
    }
    facts
}

pub(super) fn resolve(
    case: &Node<Program>,
    concept: Option<ConceptReads<'_>>,
    scope: &SolverScope,
    registry: &Registry,
) -> WithDiagnostics<ResolvedProgram> {
    resolve_with(case, concept, scope, registry, false)
}

/// [`resolve`], with the columns that a `DET` node keeps in the order of their
/// labels' canonical positions where `canonical_kept`.
pub(super) fn resolve_with(
    case: &Node<Program>,
    concept: Option<ConceptReads<'_>>,
    scope: &SolverScope,
    registry: &Registry,
    canonical_kept: bool,
) -> WithDiagnostics<ResolvedProgram> {
    let mut builder = Builder::new(case, scope, registry, None);
    builder.canonical_kept = canonical_kept;
    builder.names.feature_sites = canonical_kept;
    for fact in [FactRelation::Input, FactRelation::ExInput, FactRelation::ExOutput].into_iter().chain(feature_facts(case)) {
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
    fn is_fact(&self, node: GraphNodeIndex) -> bool {
        matches!(self.nodes[node.0 as usize].kind, DependencyKind::Fact(_))
    }

}

#[path = "build_content.rs"]
mod content;

#[path = "build_graph.rs"]
mod graph;

#[path = "build_read_columns.rs"]
mod read_columns;

#[path = "build_retarget.rs"]
mod retarget;

#[path = "build_sides.rs"]
mod sides;

#[path = "build_sites.rs"]
mod sites;
