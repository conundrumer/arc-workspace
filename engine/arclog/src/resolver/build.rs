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
    /// The columns of each read-named node whose relation is listed, in place
    /// of the columns its reads name: those of the reads in a use closure.
    exact: StableHashMap<ProgramRelation, Vec<ColumnName>>,
    /// The nodes this build gives, in the order of their indices. Each
    /// per-node list below holds the entries of these nodes alone, in the same
    /// order: the entry of the node at index `node` is at `node - offset`.
    /// The nodes of `earlier`, whose indices come first, have no entry in
    /// them; a lookup of such a node falls through to `earlier`.
    nodes: Vec<DependencyNode>,
    /// The index of each of `nodes`.
    index: StableHashMap<DependencyNode, GraphNodeIndex>,
    /// The count of the nodes of `earlier`, none for a build with no
    /// `earlier`.
    offset: usize,
    /// The paths of the forms of each node.
    forms: Vec<Vec<NodePath>>,
    /// The relations that the forms of each node give it.
    relations: Vec<Vec<FormRelation>>,
    /// The nodes that each node reads.
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
    /// The side of each node.
    sides: Vec<Side>,
    /// The columns of each node that hold an Example.
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
    /// Whether the resolution holds the signature of each read.
    signed: bool,
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
    /// last, whose nodes come first in the indices of the nodes.
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
            exact: StableHashMap::default(),
            nodes: Vec::new(),
            index: StableHashMap::default(),
            offset: 0,
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
            signed: true,
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
            builder.offset = earlier.graph.nodes.len();
            builder.names.earlier = Some(Arc::clone(earlier));
            builder.earlier = Some(Arc::clone(earlier));
        }
        builder
    }

    /// The count of the nodes of the earlier forms' resolution.
    fn offset(&self) -> usize {
        self.offset
    }

    /// The count of the nodes of the program so far, those of the earlier
    /// forms' resolution included.
    fn node_count(&self) -> usize {
        self.offset + self.nodes.len()
    }

    /// The position of `node` in this build's per-node lists, or `None` for a
    /// node of the earlier forms' resolution.
    fn slot(&self, node: usize) -> Option<usize> {
        node.checked_sub(self.offset)
    }

    /// The kind and the scope of `node`, a node of this build or of the earlier
    /// forms' resolution.
    fn node_def(&self, node: usize) -> &DependencyNode {
        match self.slot(node) {
            Some(slot) => &self.nodes[slot],
            None => &self.earlier.as_ref().expect("an earlier resolution holds the nodes before the offset").graph.nodes[node],
        }
    }

    /// The paths of the forms of `node` that this build reads: those of a
    /// node of this build, and none for a node of the earlier forms'
    /// resolution, whose forms are all before the last.
    fn forms_at(&self, node: usize) -> &[NodePath] {
        self.slot(node).map_or(&[], |slot| &self.forms[slot])
    }

    /// The side of `node`, once [`Builder::sides`] has decided it.
    fn side_of(&self, node: usize) -> Side {
        match self.slot(node) {
            Some(slot) => self.sides[slot],
            None => self.earlier.as_ref().expect("an earlier resolution holds the nodes before the offset").side(GraphNodeIndex(node as u32)),
        }
    }
}

/// The resolution of `program`, whose forms before its last are the forms
/// of `earlier`, by the passes of [`resolve`] over the last form alone, or
/// `None` where the last form is one this resolution does not handle. A
/// `DEMONSTRATED` last form is handled where `demonstrated` is true.
///
/// `earlier` may be a layered resolution, up to [`super::MAX_LAYERS`] layers.
///
/// The builder holds the entries of the last form's nodes alone, and finds
/// a node, a side or an Example column of `earlier` by a lookup there; the
/// result shares the graph of `earlier` ([`ResolvedProgram`] says what each
/// layer holds). A read of the last form that names a column of a `DET`
/// parameter that `earlier` does not keep is the one case that builds on
/// `earlier.widened`, a resolution of the whole program that takes the content
/// of the nodes it does not reach from `earlier` ([`resolve_reusing`]).
fn layered(earlier: &Arc<ResolvedProgram>, program: &Node<Program>, registry: &Registry, demonstrated: bool, signed: bool, proposers: bool) -> Option<WithDiagnostics<ResolvedProgram>> {
    let scope = SolverScope::default();
    let (last, complete) = program.value().forms.split_last()?;
    if earlier.concept().is_some() || earlier.layers() >= super::MAX_LAYERS || earlier.program.value().forms.len() != complete.len() {
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
    builder.signed = signed;
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
        return layered(&widened, program, registry, demonstrated, signed, proposers);
    }
    builder.sides();
    builder.contents();
    builder.sites();
    if proposers {
        builder.proposers();
    }
    Some(builder.finish(None))
}

pub(super) fn resolve_last(earlier: &Arc<ResolvedProgram>, program: &Node<Program>, registry: &Registry) -> WithDiagnostics<ResolvedProgram> {
    layered(earlier, program, registry, false, true, true).unwrap_or_else(|| resolve(program, None, &SolverScope::default(), registry))
}

pub(super) fn resolve_in_progress(earlier: &Arc<ResolvedProgram>, program: &Node<Program>, registry: &Registry) -> ResolvedProgram {
    layered(earlier, program, registry, true, true, true).map_or_else(|| resolve(program, None, &SolverScope::default(), registry).value, |resolved| resolved.value)
}

/// [`resolve_in_progress`] for the checks of a prefix: a layered resolution
/// holds no signature of a read, which only the check of a finished program
/// reads.
pub(super) fn resolve_prefix(earlier: &Arc<ResolvedProgram>, program: &Node<Program>, registry: &Registry) -> ResolvedProgram {
    layered(earlier, program, registry, true, false, true).map_or_else(|| resolve(program, None, &SolverScope::default(), registry).value, |resolved| resolved.value)
}

/// [`resolve_prefix`] for the checks alone, which read no proposer's columns:
/// a layered resolution holds none.
pub(super) fn resolve_for_checks(earlier: &Arc<ResolvedProgram>, program: &Node<Program>, registry: &Registry) -> ResolvedProgram {
    layered(earlier, program, registry, true, false, false).map_or_else(|| resolve(program, None, &SolverScope::default(), registry).value, |resolved| resolved.value)
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
        !builder.is_fact(*node) && !builder.forms_at(node.0 as usize).contains(&form_path)
            && builder.side_of(node.0 as usize) == super::Side::PerInput
    } else {
        let Some(atom) = builder.atoms.iter().find(|atom| atom.path == *read) else { return false };
        sides::lifted(builder.is_fact(*node), builder.form_sides[&atom.form], builder.side_of(node.0 as usize))
    }
}

/// The fact relations that a feature's forms in `program` read, each once: no
/// other program reads them.
fn feature_facts(program: &Node<Program>) -> Vec<FactRelation> {
    let mut facts = Vec::new();
    for (index, form) in program.value().forms.iter().enumerate() {
        for read in crate::check::reads::form_reads(form, &NodePath::top(index as u32)) {
            if let RelationRef::Fact(fact @ (FactRelation::Output | FactRelation::Program(_) | FactRelation::Name(_) | FactRelation::Stored(_))) = &read.atom.relation {
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
    builder.declare_and_read_whole(case, concept, registry);
    builder.contents();
    builder.sites();
    builder.proposers();
    let concept = concept.map(|concept| {
        builder.copy_concept(concept);
        ConceptForms { program: Arc::clone(concept.concept), paths: std::mem::take(&mut builder.concept_forms) }
    });
    builder.finish(concept)
}

/// The resolution of `earlier`'s program with the scope `scope`, which is
/// [`resolve`]'s on that program with that scope, made by writing again the
/// content of the nodes that `scope` changes, and of the nodes that read them
/// ([`Builder::contents_reusing`]), and taking the content of every other
/// node from `earlier`, an exact resolution of the program. `None` where this
/// cannot be shown for the program, so the caller resolves it whole.
pub(super) fn resolve_reusing(earlier: &ResolvedProgram, scope: &SolverScope, registry: &Registry) -> Option<ResolvedProgram> {
    if earlier.concept().is_some() {
        return None;
    }
    let mut builder = Builder::new(&earlier.program, scope, registry, None);
    builder.declare_and_read_whole(&earlier.program, None, registry);
    builder.contents_reusing(earlier)?;
    builder.sites();
    builder.proposers();
    Some(builder.finish(None).value)
}

/// The resolution of `earlier`'s program in which each read-named node whose
/// relation `exact` lists has the columns listed, in place of those its reads
/// name. It is made as [`resolve_reusing`] makes a resolution, and, where
/// that cannot be shown for the program, whole.
pub(super) fn resolve_narrowed(earlier: &ResolvedProgram, exact: &[(ProgramRelation, Vec<ColumnName>)], registry: &Registry) -> ResolvedProgram {
    let scope = SolverScope::default();
    let exact: StableHashMap<ProgramRelation, Vec<ColumnName>> = exact.iter().cloned().collect();
    let mut builder = Builder::new(&earlier.program, &scope, registry, None);
    builder.exact = exact.clone();
    builder.declare_and_read_whole(&earlier.program, None, registry);
    if builder.contents_reusing(earlier).is_some() {
        builder.sites();
        builder.proposers();
        return builder.finish(None).value;
    }
    let mut builder = Builder::new(&earlier.program, &scope, registry, None);
    builder.exact = exact;
    builder.declare_and_read_whole(&earlier.program, None, registry);
    builder.contents();
    builder.sites();
    builder.proposers();
    builder.finish(None).value
}

impl<'a> Builder<'a> {
    /// The passes of [`resolve`] before the content of the nodes: the facts
    /// and the declarations and the reads of each form of `case`, the columns
    /// that the reads decide, and the sides.
    fn declare_and_read_whole(&mut self, case: &'a Node<Program>, concept: Option<ConceptReads<'_>>, registry: &Registry) {
        for fact in [FactRelation::Input, FactRelation::ExInput, FactRelation::ExOutput].into_iter().chain(feature_facts(case)) {
            let node = self.node(DependencyKind::Fact(fact), &NameScope::Program, None);
            let columns = Columns::of_names(registry.fact_columns(fact).iter().map(|column| column.name.clone()));
            self.target(&NameScope::Program, RelationRef::Fact(fact), Target { node, columns: ColumnsOf::Fixed(columns) });
        }
        if let Some(concept) = concept {
            self.take_concept(concept);
        }
        let forms = &case.value().forms;
        let mut pending = Vec::new();
        for (index, form) in forms.iter().enumerate() {
            self.declare(form, NodePath::top(index as u32), &NameScope::Program, &mut pending);
        }
        for (scope, relation, target) in pending {
            self.target(&scope, relation, target);
        }
        for (index, form) in forms.iter().enumerate() {
            self.read_form(form, NodePath::top(index as u32), &NameScope::Program);
        }
        self.read_columns();
        self.sides();
    }

    fn is_fact(&self, node: GraphNodeIndex) -> bool {
        matches!(self.node_def(node.0 as usize).kind, DependencyKind::Fact(_))
    }

}

#[path = "build_content.rs"]
mod content;

#[path = "build_graph.rs"]
mod graph;

#[path = "build_read_columns.rs"]
mod read_columns;

pub(super) use read_columns::closure_columns;

#[path = "build_retarget.rs"]
mod retarget;

#[path = "build_sides.rs"]
mod sides;

#[path = "build_sites.rs"]
mod sites;
