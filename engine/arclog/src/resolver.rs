//! Name resolution of a case program, and the dependency graph it gives,
//! and the resolution of each case of a solver. A relation that no block of
//! the case derives resolves to an undefined relation.
//!
//! The registry and resolver stage writes the bodies.

use std::sync::Arc;

use crate::diagnostic::WithDiagnostics;
use crate::hash::StableHash;
use crate::program::canonical::LabelingBound;
use crate::program::path::{node_at, NodePath, NodeRef};
use crate::program::{
    ColumnName, InstanceName, LabelId, Node, OutputStep, PortName, RelationRef, Program, ProgramRelation, RelationName, RigidDetName,
};
use crate::registry::{LibName, Registry};

/// A node of the dependency graph: its kind and the name scope of its
/// declaration, so that two relations of one name that two `DEMO_RULE`
/// forms declare are two nodes.
#[derive(Clone, PartialEq, Eq, Hash, Debug)]
pub struct DependencyNode {
    pub kind: DependencyKind,
    pub scope: crate::program::NameScope,
}

/// The kind of a node of the dependency graph: a fact relation, a clause
/// relation, an instance input or output, a parameter, a chosen relation, a
/// `RIGID_DET` assembly, a `DEMONSTRATED` relation or an `OUT` form.
#[derive(Clone, PartialEq, Eq, Hash, Debug)]
pub enum DependencyKind {
    Fact(crate::program::FactRelation),
    /// A relation a clause derives, an instance relation on a `RULE_OR_DET`
    /// line included.
    Clause(ProgramRelation),
    /// An input of an instance. The node reads the input's clause in its
    /// `INIT` form, or, where the case holds a `DET` of
    /// `&<instance>.<input>`, that `DET`'s [`DependencyKind::Parameter`]
    /// node, as `docs/engine/arclog-expansion.md#stored-readings` gives.
    InstanceInput { instance: InstanceName, input: PortName },
    /// An output of an instance. Where the case holds a `DET` of
    /// `&<instance>.<output>`, each read of that relation resolves to the
    /// `DET`'s [`DependencyKind::Parameter`] node, and none to this node, as
    /// `docs/engine/arclog-expansion.md#stored-readings` gives.
    InstanceOutput { instance: InstanceName, output: PortName },
    /// A parameter: a `DET` relation with no `ONE` mark, read as one node and
    /// never through its body, as a `DET` of the concept program is read in
    /// each case, with the values that `DET` keeps for it. A parameter that
    /// several blocks of the case determine is one node, with the values
    /// `docs/arclog/arclog.md#the-alts-form` gives it. Each read of the
    /// parameter's own `DET` bodies is an edge into the node, so a `DET` that
    /// reads a relation which depends on its own parameter makes a cycle.
    /// For a `DET` of a port of an instance, `&<instance>.<port>`, each read
    /// of the relation resolves to this node, and on an input the input's
    /// [`DependencyKind::InstanceInput`] node reads it, as
    /// `docs/engine/arclog-expansion.md#stored-readings` gives.
    Parameter(ProgramRelation),
    /// A chosen relation: a `CHOOSE` form's, or a clause's with `ONE` marks,
    /// a `DET` with `(ONE)` included, which is a chosen relation at the task
    /// level. An open parameter, a `DET` that ends in `(ONE)`, that several
    /// blocks of the case determine is one node, as a
    /// [`DependencyKind::Parameter`] is, and the relation of a `DET` has as
    /// its columns the labels of its clause that its reads name and the
    /// labels its marks name, as a parameter's has those its reads name.
    Chosen(RelationName),
    /// A `RIGID_DET` form: one node for its assemblies
    /// (`docs/arclog/rigid.md#form`).
    RigidAssembly(RigidDetName),
    /// A `DEMONSTRATED` relation.
    Demonstrated(RelationName),
    /// An instance of a component with inputs that read its outputs, as
    /// `Unfold`'s `step`, `skip` and `take` do, with those inputs and its
    /// outputs: one node. The registry marks those inputs,
    /// [`crate::registry::InputPort::reads_outputs`], so the resolver names
    /// no component.
    RecursiveInstance(InstanceName),
    /// An `OUT` form, by its path: the rows of its two selected columns, per
    /// input (`docs/arclog/arclog.md#the-out-form`). No atom reads it.
    Out(NodePath),
}

/// The side of a node of the dependency graph, as
/// `docs/arclog/arclog.md#program` and `docs/arclog/arclog.md#instance` give:
/// per input, as a `RULE` relation is, or task-wide, as a `DET` relation is.
#[derive(Clone, Copy, PartialEq, Eq, Hash, Debug)]
pub enum Side {
    PerInput,
    TaskWide,
}

/// The index of a node in a [`DependencyGraph`].
#[derive(Clone, Copy, PartialEq, Eq, Hash, Debug)]
pub struct GraphNodeIndex(pub u32);

/// The entries of one list per node of a resolution, by the node's index, in
/// layers: the entries of the nodes of an earlier resolution, which this list
/// shares with that resolution's list and does not copy, and then the entries
/// of the nodes after them. A lookup of an entry of an earlier node falls
/// through to the earlier list, so the list reads as one list of every node
/// and holds the entries of the nodes after those of the earlier list alone.
#[derive(Debug)]
pub struct NodeList<T> {
    /// The list of the nodes before the first of `own`.
    earlier: Option<Arc<NodeList<T>>>,
    /// The count of the nodes of `earlier`, which is the index of the first
    /// node of `own`.
    first: usize,
    /// The entries of the nodes from index `first` on.
    own: Box<[T]>,
}

impl<T> Default for NodeList<T> {
    fn default() -> Self {
        NodeList { earlier: None, first: 0, own: Box::default() }
    }
}

impl<T: Clone> Clone for NodeList<T> {
    fn clone(&self) -> Self {
        NodeList { earlier: self.earlier.clone(), first: self.first, own: self.own.clone() }
    }
}

impl<T> NodeList<T> {
    /// The list of the entries `own`, the first node's first.
    pub fn new(own: impl Into<Box<[T]>>) -> Self {
        NodeList { earlier: None, first: 0, own: own.into() }
    }

    /// The list of every entry of `earlier`, shared, and then `own`.
    pub fn over(earlier: Arc<NodeList<T>>, own: impl Into<Box<[T]>>) -> Self {
        let first = earlier.len();
        NodeList { earlier: Some(earlier), first, own: own.into() }
    }

    /// The count of the entries, those of the earlier list included.
    pub fn len(&self) -> usize {
        self.first + self.own.len()
    }

    pub fn is_empty(&self) -> bool {
        self.len() == 0
    }

    /// The index of the first entry that this list holds itself.
    pub fn first(&self) -> usize {
        self.first
    }

    /// The entries that this list holds itself, those of the nodes from
    /// [`NodeList::first`] on.
    pub fn own(&self) -> &[T] {
        &self.own
    }

    /// The entry of the node at `index`.
    pub fn get(&self, index: usize) -> Option<&T> {
        match index.checked_sub(self.first) {
            Some(own) => self.own.get(own),
            None => self.earlier.as_ref()?.get(index),
        }
    }

    /// Every entry, those of the earlier list first.
    pub fn iter(&self) -> NodeListIter<'_, T> {
        NodeListIter { list: self, front: 0, back: self.len() }
    }
}

impl<T: Clone> NodeList<T> {
    /// Replaces the entry at `index`, which this list holds itself.
    fn set_own(&mut self, index: usize, entry: T) {
        let own = index.checked_sub(self.first).expect("an entry that this list holds itself");
        self.own[own] = entry;
    }
}

impl<T> std::ops::Index<usize> for NodeList<T> {
    type Output = T;

    fn index(&self, index: usize) -> &T {
        match self.get(index) {
            Some(entry) => entry,
            None => panic!("the node {index} is out of the {} nodes of the list", self.len()),
        }
    }
}

impl<'l, T> IntoIterator for &'l NodeList<T> {
    type Item = &'l T;
    type IntoIter = NodeListIter<'l, T>;

    fn into_iter(self) -> NodeListIter<'l, T> {
        self.iter()
    }
}

/// The entries of a [`NodeList`], in the order of the nodes' indices.
pub struct NodeListIter<'l, T> {
    list: &'l NodeList<T>,
    front: usize,
    back: usize,
}

impl<'l, T> Iterator for NodeListIter<'l, T> {
    type Item = &'l T;

    fn next(&mut self) -> Option<&'l T> {
        if self.front == self.back {
            return None;
        }
        self.front += 1;
        self.list.get(self.front - 1)
    }

    fn size_hint(&self) -> (usize, Option<usize>) {
        (self.back - self.front, Some(self.back - self.front))
    }
}

impl<T> DoubleEndedIterator for NodeListIter<'_, T> {
    fn next_back(&mut self) -> Option<Self::Item> {
        if self.front == self.back {
            return None;
        }
        self.back -= 1;
        self.list.get(self.back)
    }
}

impl<T> ExactSizeIterator for NodeListIter<'_, T> {}

/// The dependency graph of a case program: each read is an edge from the
/// node read to the node that reads it. The graph of [`resolve_last`] holds
/// the nodes and reads of the forms before the last by sharing those of the
/// earlier resolution's graph, so it holds the entries of the last form's
/// nodes alone ([`NodeList`]); each lookup reads as one list of every node.
#[derive(Clone, Debug, Default)]
pub struct DependencyGraph {
    pub nodes: Arc<NodeList<DependencyNode>>,
    /// For each node, the nodes it reads.
    pub reads: Arc<NodeList<Box<[GraphNodeIndex]>>>,
}

impl DependencyGraph {
    /// The graph of every node of `earlier`, shared, and then `nodes`, whose
    /// reads are `reads`.
    pub(crate) fn over(earlier: &DependencyGraph, nodes: Vec<DependencyNode>, reads: Vec<Box<[GraphNodeIndex]>>) -> Self {
        DependencyGraph {
            nodes: Arc::new(NodeList::over(Arc::clone(&earlier.nodes), nodes)),
            reads: Arc::new(NodeList::over(Arc::clone(&earlier.reads), reads)),
        }
    }

    /// Sets the nodes `node` reads, where the graph holds the entry of `node`
    /// itself, as a node of the last form of a layered graph.
    pub(crate) fn set_reads(&mut self, node: GraphNodeIndex, reads: Box<[GraphNodeIndex]>) {
        Arc::make_mut(&mut self.reads).set_own(node.0 as usize, reads);
    }

    /// Whether each node of the graph is read by `root`, at any depth, or is
    /// `root`.
    pub fn reached(&self, root: GraphNodeIndex) -> Vec<bool> {
        let mut seen = vec![false; self.nodes.len()];
        let mut stack = vec![root];
        while let Some(node) = stack.pop() {
            if std::mem::replace(&mut seen[node.0 as usize], true) {
                continue;
            }
            stack.extend(self.reads[node.0 as usize].iter().copied());
        }
        seen
    }

    /// A cycle of the graph, as the nodes on it, or `None` where the graph is
    /// acyclic.
    pub fn find_cycle(&self) -> Option<Vec<GraphNodeIndex>> {
        const NEW: u8 = 0;
        const OPEN: u8 = 1;
        const CLOSED: u8 = 2;
        let mut state = vec![NEW; self.nodes.len()];
        for root in 0..self.nodes.len() {
            if state[root] != NEW {
                continue;
            }
            state[root] = OPEN;
            let mut stack: Vec<(usize, usize)> = vec![(root, 0)];
            while let Some(&(node, next)) = stack.last() {
                let Some(&GraphNodeIndex(read)) = self.reads[node].get(next) else {
                    state[node] = CLOSED;
                    stack.pop();
                    continue;
                };
                stack.last_mut().expect("the stack holds `node`").1 += 1;
                let read = read as usize;
                match state[read] {
                    NEW => {
                        state[read] = OPEN;
                        stack.push((read, 0));
                    }
                    OPEN => {
                        let start = stack.iter().position(|&(open, _)| open == read).expect("an open node stands on the stack");
                        let mut cycle: Vec<GraphNodeIndex> = stack[start..].iter().map(|&(n, _)| GraphNodeIndex(n as u32)).collect();
                        cycle.sort_by_key(|index| index.0);
                        return Some(cycle);
                    }
                    _ => {}
                }
            }
        }
        None
    }
}

/// What a name read in a case program resolves to.
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

/// The identity of a query: its resolved content, and the canonical order of
/// its form through the resolver's writer, which gives the canonical path
/// of each of its nodes and the canonical position of each of its labels,
/// as [`ResolvedProgram::query_identity`] gives them. Both are free of the
/// names the program declares and of the order of its forms, of the
/// conjuncts of a body, of the branches of an `OR` and of the columns a
/// clause writes. The paths and labels are those of the form in the program
/// that was resolved, since the order is of the form itself.
#[derive(Clone, Debug)]
pub struct QueryIdentity {
    pub content: ResolvedContent,
    pub order: crate::program::canonical::CanonicalOrder,
}

/// A column of a derived relation, resolved to its canonical position: the
/// position of its label in the canonical labeling of the clause, as
/// [`crate::program::canonical::CanonicalLabeling`] gives it. The resolver
/// turns each column name that a read gives into its position.
#[derive(Clone, Copy, PartialEq, Eq, Hash, Debug)]
pub struct ColumnPosition(pub u16);

/// The signature of a name a form reads: the canonical form of what the
/// name resolves to, its columns and their types. It compares as a key of
/// canonical parts does ([`crate::program`]).
#[derive(Clone, PartialEq, Eq, Hash, Debug)]
pub struct Signature(pub crate::program::canonical::CanonicalForm);

/// The version of the QueryHash's definition: the hash of a query's
/// resolved content ([`ResolvedContent::content_hash`]), which `query_hash`
/// gives, and the canonical hash of a query with its names as written,
/// which `written_query_hash` gives. A change to either hash of any query
/// adds one. A store keyed by QueryHash holds the version that wrote it
/// (`arclog.query_hash_version()`), and two QueryHashes compare only under
/// one version.
pub const QUERY_HASH_VERSION: u32 = 1;

/// The resolved content of a node of a case program: its canonical form,
/// with each name it reads standing for the resolved content of what it
/// resolves to, and, for a clause whose node keeps columns that differ, in
/// count or in order, from the clause's columns in their canonical
/// positions, followed by the names of the columns it keeps, in their
/// order. Two contents are equal when their hashes match and then
/// their canonical forms do, whatever file or decode they came from.
#[derive(Clone, PartialEq, Eq, Hash, Debug)]
pub struct ResolvedContent {
    form: crate::program::canonical::CanonicalForm,
}

impl ResolvedContent {
    /// The bytes of the content's canonical form.
    pub fn bytes(&self) -> usize {
        self.form.bytes.len()
    }

    /// The bytes of the content's canonical form.
    pub fn canonical_bytes(&self) -> &[u8] {
        &self.form.bytes
    }

    /// The hash of the content's canonical form.
    pub fn content_hash(&self) -> StableHash {
        self.form.hash
    }
}

/// A case program after name resolution.
///
/// From [`resolve_last`] it is a layered resolution: the layer of the
/// program's last form over the layer of the forms before it, which is the
/// `earlier` resolution that `resolve_last` took. Each lookup that names a
/// path or a node of the forms before the last falls through to `earlier`.
/// `earlier` may be a layered resolution too, so a chain of layers stands over
/// one lowest layer. The layers hold:
/// - the lowest layer: every entry of the forms it resolves, as a resolution
///   that no `resolve_last` made holds every entry of its program.
/// - each layer over it: the entries of its last form alone, that is, those
///   keyed by a path in that form or by a node that the form gives, and, in
///   the graph, a reference to the graph below. Its size and its build cost
///   follow its last form, not the program.
///
/// A layer leaves the content of a node that no read of its last form
/// resolves to unwritten, and writes it on the first read of the node, from
/// any layer ([`ResolvedProgram::node_content`]).
///
/// The graph is the one list of every node of the program, as
/// [`DependencyGraph`] says, whichever layer holds a node.
#[derive(Clone, Debug)]
pub struct ResolvedProgram {
    pub program: Node<Program>,
    /// The nodes and the reads of every node of the program. A layered
    /// resolution holds those of the last form's nodes, and shares the rest
    /// with `earlier`.
    pub graph: DependencyGraph,
    /// The paths of the forms of each node that this layer holds, by the
    /// node's index after those of `earlier`.
    forms: Box<[Box<[NodePath]>]>,
    /// The nodes that this layer holds and that each form gives, by the
    /// form's path, in the order of their indices.
    form_nodes: crate::hash::StableHashMap<NodePath, Box<[GraphNodeIndex]>>,
    /// The side of each node that this layer holds, by the node's index after
    /// those of `earlier`.
    sides: Box<[Side]>,
    /// The side of each form whose reads the resolver resolves, by the
    /// form's path.
    form_sides: crate::hash::StableHashMap<NodePath, Side>,
    /// The columns of each node that this layer holds that hold an Example, by
    /// the node's index after those of `earlier`.
    examples: Box<[std::sync::Arc<[ExamplePath]>]>,
    /// The columns that hold an Example of each relation of a node whose
    /// forms give it several, by the node and the relation's path after
    /// the form's name, which a read of that relation reads.
    output_examples: crate::hash::StableHashMap<(GraphNodeIndex, std::sync::Arc<[OutputStep]>), std::sync::Arc<[ExamplePath]>>,
    resolutions: crate::hash::StableHashMap<NodePath, Resolution>,
    signatures: crate::hash::StableHashMap<NodePath, Signature>,
    positions: crate::hash::StableHashMap<NodePath, ColumnPosition>,
    label_positions: crate::hash::StableHashMap<(NodePath, LabelId), ColumnPosition>,
    groups: crate::hash::StableHashMap<NodePath, crate::relations::ColumnGroup>,
    proposer_columns: crate::hash::StableHashMap<(NodePath, usize), Box<[ColumnName]>>,
    /// The path of each read that its form reads in its lifted form.
    lifted: crate::hash::StableHashSet<NodePath>,
    /// The path of each lifted read whose site on the Example column holds a
    /// label that a positive `ex_output` atom binds, which reads the train
    /// examples alone (`docs/arclog/arclog.md#program`).
    train_lifted: crate::hash::StableHashSet<NodePath>,
    /// For each node that this layer holds, by the node's index after those of
    /// `earlier`, the column names
    /// that the sites of the reads of its relation name, with the columns
    /// that its marks name, for a `DET` node that an atom reads, as [`build`]
    /// gives them.
    read_columns: Box<[Option<Vec<ColumnName>>]>,
    /// The resolutions of this program, each over the whole program, with more
    /// columns of some `DET` parameters kept, by the relation and the columns
    /// that its reads name, which [`resolve_last`] builds on when the last
    /// form reads a column that no earlier form's read names. A layered
    /// resolution is never built on, so it holds none.
    widened: Widened,
    names: names::Names,
    concept: Option<ConceptForms>,
    /// The depth of each node of the whole graph, by its index, made on the
    /// first ask ([`ResolvedProgram::depth`]).
    depths: std::sync::OnceLock<Box<[u32]>>,
    /// The index of each node that this layer's graph holds itself, by the
    /// node, made on the first ask ([`ResolvedProgram::find_node`]).
    node_index: std::sync::OnceLock<crate::hash::StableHashMap<DependencyNode, GraphNodeIndex>>,
}

type Widened = Arc<std::sync::Mutex<crate::hash::StableHashMap<Vec<(ProgramRelation, Vec<ColumnName>)>, (Arc<ResolvedProgram>, crate::eval::NoteId)>>>;

/// The concept program of a case, and the path there of each `DET` form
/// that the case takes from it, by the form's path in the case.
#[derive(Clone, Debug)]
struct ConceptForms {
    program: Arc<ResolvedProgram>,
    paths: crate::hash::StableHashMap<NodePath, NodePath>,
}

impl ResolvedProgram {
    /// The node that `relation`, read in the program's scope, resolves to,
    /// where the program declares it.
    pub fn program_read(&self, relation: &RelationRef) -> Option<GraphNodeIndex> {
        self.names.find(&crate::program::NameScope::Program, relation).map(|target| target.node)
    }

    /// What the name read at `path` resolves to. Each path that a method of
    /// `ResolvedProgram` takes walks as [`crate::program::path::node_at`]
    /// gives.
    pub fn resolution(&self, path: &NodePath) -> Option<&Resolution> {
        match self.earlier_of(path) {
            Some(earlier) => earlier.resolution(path),
            None => self.resolutions.get(path),
        }
    }

    /// This program resolved with the read columns of `widening` in place
    /// of those its atoms name, made once for each `widening`. It is the
    /// resolution of the whole program that [`resolve`] gives for the scope
    /// that holds `widening`, and a layered resolution builds on it, so it
    /// holds each form. The passes over the whole program that decide the
    /// nodes, the targets of the names, the reads, the sides and the sites
    /// run again, and the content of a node that the widening does not reach,
    /// with its columns and key ranks, is taken from this resolution
    /// ([`build::resolve_reusing`] says why that gives [`resolve`]'s result);
    /// where that cannot be shown for the program, the call resolves it whole.
    fn widened(&self, widening: Vec<(ProgramRelation, Vec<ColumnName>)>, registry: &Registry) -> Arc<ResolvedProgram> {
        let mut held = self.widened.lock().expect("no thread panics while it holds the cache");
        if let Some((found, notes)) = held.get(&widening) {
            // The notes of the build, in the gauges a cost carries, stand in the request that asks: the build writes the content of each node through the search for a canonical labeling.
            crate::eval::replay_notes(*notes);
            return Arc::clone(found);
        }
        let scope = SolverScope { derived: Default::default(), read_columns: widening.iter().cloned().collect() };
        let (resolved, notes) = crate::eval::noting(|| build::resolve_reusing(self, &scope, registry).unwrap_or_else(|| resolve(&self.program, None, &scope, registry).value));
        let resolved = Arc::new(resolved);
        held.insert(widening, (Arc::clone(&resolved), notes));
        resolved
    }

    /// This program resolved so that each `DET` node that a read in the use
    /// closure of the top-level form at `position` reads
    /// ([`ResolvedProgram::use_closure`]) has the columns that the reads in
    /// that closure name, with the columns that its marks name. A read in
    /// a form outside the closure widens no node, so the columns of a node
    /// are those that the closure and its query fix. `None` where every node
    /// has the columns this resolution gives it, and where this resolution
    /// takes its nodes from a concept program. The resolution is the
    /// whole program's, with the positions of the forms and the nodes of
    /// this one; the checks of the forms outside the closure, which read the
    /// columns they name, are not for it. The positions of the columns of a
    /// relation that reads a narrowed node may differ from this one's, since
    /// they follow the content of what it reads.
    pub(crate) fn narrowed_to_closure(&self, position: usize, registry: &Registry) -> Option<Arc<ResolvedProgram>> {
        if self.concept().is_some() {
            return None;
        }
        let _timed = crate::stats::span(crate::stats::Phase::ResolveNarrowed);
        let keep = self.use_closure(position)?;
        let exact = build::closure_columns(self, &keep)?;
        Some(Arc::new(build::resolve_narrowed(self, &exact, registry)))
    }

    /// An identity for the statistics ([`crate::stats`]) of the forms this
    /// resolution layers over: the resolution that [`resolve_last`] took as
    /// `earlier`, or this one where it is no layered resolution.
    pub fn stats_finished_id(&self) -> usize {
        self.names.earlier.as_deref().map_or(self as *const ResolvedProgram, |earlier| earlier as *const ResolvedProgram) as usize
    }

    /// Whether `path` stands in one of the forms before the last, where
    /// this resolution is [`resolve_last`]'s.
    pub(crate) fn in_earlier_forms(&self, path: &NodePath) -> bool {
        self.earlier_of(path).is_some()
    }

    /// The resolution of the forms before the last, where this resolution
    /// is [`resolve_last`]'s and `path` stands in one of those forms.
    fn earlier_of(&self, path: &NodePath) -> Option<&ResolvedProgram> {
        let earlier = self.names.earlier.as_deref()?;
        let top = path.0.first()?;
        ((top.0 as usize) < earlier.program.value().forms.len()).then_some(earlier)
    }

    /// The count of the layers over the lowest one: 0 for a resolution that no
    /// `resolve_last` made, and one more than `earlier`'s for a layered
    /// resolution. A lookup that the layers do not hold falls through one
    /// layer at a time, so [`resolve_last`] makes a full resolution once the
    /// count of `earlier` reaches [`MAX_LAYERS`].
    pub fn layers(&self) -> usize {
        self.names.earlier.as_deref().map_or(0, |earlier| 1 + earlier.layers())
    }

    /// The resolution of the forms before the last, where `node` is one of
    /// their nodes.
    fn earlier_node(&self, node: GraphNodeIndex) -> Option<&ResolvedProgram> {
        self.names.earlier.as_deref().filter(|earlier| (node.0 as usize) < earlier.graph.nodes.len())
    }

    /// The index of the node `key` of this resolution's graph, and of the
    /// resolutions this one layers over, where the graph holds it. The index
    /// of the nodes that this layer holds is made on the first call.
    pub(crate) fn find_node(&self, key: &DependencyNode) -> Option<GraphNodeIndex> {
        if let Some(earlier) = self.names.earlier.as_deref() {
            if let Some(found) = earlier.find_node(key) {
                return Some(found);
            }
        }
        let index = self.node_index.get_or_init(|| {
            let first = self.graph.nodes.first();
            self.graph.nodes.own().iter().enumerate().map(|(slot, node)| (node.clone(), GraphNodeIndex((first + slot) as u32))).collect()
        });
        index.get(key).copied()
    }

    /// The index in this resolution's own per-node entries of `node`, which
    /// [`ResolvedProgram::earlier_node`] gives no resolution for.
    fn own_index(&self, node: GraphNodeIndex) -> usize {
        node.0 as usize - self.names.first_node()
    }

    /// The position, in the rows of the relation its atom reads, of the
    /// column that the site at `site` names. A site on a field of a record,
    /// such as `(:P P2)` in `(:key (:P P2))`, names that field's column of
    /// the record's column group, so it is told apart from a column of the
    /// same name, `(:P P2)` beside it.
    ///
    /// A [`crate::program::SiteArg::NamedLabel`] at `site` maps to the column
    /// of the field its name gives where its site reads a record, and to the
    /// site's own column where it does not, so each field of
    /// `(:key P_intile *Col)` has its own position. The value gives the
    /// field, so the mapping needs no layout.
    pub fn column_position(&self, site: &NodePath) -> Option<ColumnPosition> {
        match self.earlier_of(site) {
            Some(earlier) => earlier.column_position(site),
            None => self.positions.get(site).copied(),
        }
    }

    /// The position in the rows of its node of the column of `label`, a
    /// label of a column that the form at `form` gives: a clause's, or a
    /// `CHOOSE` form's row or candidate column. In a node of several forms,
    /// as a parameter that several blocks of a case determine, each form's
    /// column takes the position of the node's column of its name, as a
    /// site that reads the node names it.
    pub fn label_position(&self, form: &NodePath, label: LabelId) -> Option<ColumnPosition> {
        match self.earlier_of(form) {
            Some(earlier) => earlier.label_position(form, label),
            None => self.label_positions.get(&(form.clone(), label)).copied(),
        }
    }

    /// The column group that the site at `site` reads, where the site is on
    /// a column of a record, the key's or a type parameter's. A
    /// [`crate::program::SiteArg::NamedLabel`] at `site` maps to a column as
    /// [`ResolvedProgram::column_position`] gives.
    pub fn column_group(&self, site: &NodePath) -> Option<crate::relations::ColumnGroup> {
        match self.earlier_of(site) {
            Some(earlier) => earlier.column_group(site),
            None => self.groups.get(site).copied(),
        }
    }

    /// The column names that the sites of the reads of the relation of
    /// `node` name, with the columns that its marks name, for a `DET` node
    /// that an atom reads.
    fn read_columns_of(&self, node: GraphNodeIndex) -> Option<&[ColumnName]> {
        match self.earlier_node(node) {
            Some(earlier) => earlier.read_columns_of(node),
            None => self.read_columns[self.own_index(node)].as_deref(),
        }
    }

    /// The side of `node` of the graph: by the keyword of its clause, and,
    /// for an `INIT`, a `CHOOSE` or a `DEMONSTRATED` form, by its key and
    /// what its bodies read.
    pub fn side(&self, node: GraphNodeIndex) -> Side {
        match self.earlier_node(node) {
            Some(earlier) => earlier.side(node),
            None => self.sides[self.own_index(node)],
        }
    }

    /// The side of the form at `form`, a form that gives no node of its own
    /// included, by what its reads read, or `None` where `form` is the path
    /// of no form whose reads the resolver resolves.
    pub fn form_side(&self, form: &NodePath) -> Option<Side> {
        match self.earlier_of(form) {
            Some(earlier) => earlier.form_side(form),
            None => self.form_sides.get(form).copied(),
        }
    }

    /// The columns that hold an Example of the relation of `node` of the
    /// graph that a read at `output` after the owner's name reads, each by
    /// its path, in no order: those of the relation a form of `node` gives
    /// at `output`, where one does, and otherwise those of each relation of
    /// `node`. [`output_of`] gives a read's `output`.
    pub fn example_columns(&self, node: GraphNodeIndex, output: Option<&[OutputStep]>) -> &[ExamplePath] {
        &self.example_columns_shared(node, output)
    }

    /// [`ResolvedProgram::example_columns`], as the `Arc` that holds them.
    fn example_columns_shared(&self, node: GraphNodeIndex, output: Option<&[OutputStep]>) -> &std::sync::Arc<[ExamplePath]> {
        if let Some(earlier) = self.earlier_node(node) {
            return earlier.example_columns_shared(node, output);
        }
        let at = output.and_then(|output| self.output_examples.get(&(node, std::sync::Arc::from(output))));
        at.unwrap_or(&self.examples[self.own_index(node)])
    }

    /// The name of each row position of the relation of `node`, in row
    /// order: a column's name, and, for a record, `<record>.<field>` once
    /// per field. A name that has no text (`ColumnName::Slot`) is `c<position>`,
    /// its row position. `None` where the columns of `node`
    /// are not known; for an output or an input of an instance, those its
    /// port declares.
    pub fn column_names(&self, node: GraphNodeIndex) -> Option<Vec<String>> {
        let index = node.0 as usize;
        let port = || matches!(self.graph.nodes[index].kind, DependencyKind::InstanceOutput { .. } | DependencyKind::InstanceInput { .. });
        let columns = self.names.node_columns_of(index).or_else(|| self.names.fixed_columns_of(index).filter(|_| port()))?;
        Some(columns.row_names())
    }

    /// The path of each row position of the relation of `node` that a read
    /// names the columns of, in row order, as `Columns::row_paths` gives it:
    /// for a fact relation and for an output or an input of an instance, the
    /// columns its declaration fixes. `None` where they are not known.
    pub fn read_row_paths(&self, node: GraphNodeIndex) -> Option<Vec<Box<[ColumnName]>>> {
        let index = node.0 as usize;
        let fixed = matches!(self.graph.nodes[index].kind, DependencyKind::Fact(_) | DependencyKind::InstanceOutput { .. } | DependencyKind::InstanceInput { .. });
        let columns = self.names.node_columns_of(index).or_else(|| self.names.fixed_columns_of(index).filter(|_| fixed))?;
        Some(columns.row_paths())
    }

    /// The path of each row position of the relation of `node`, in row
    /// order, as `Columns::row_paths` gives it: a position keeps its path
    /// where later forms reorder the columns of `node`. `None` where the
    /// columns of `node` are not known.
    pub fn row_paths(&self, node: GraphNodeIndex) -> Option<Vec<Box<[ColumnName]>>> {
        Some(self.names.node_columns_of(node.0 as usize)?.row_paths())
    }

    /// The signature of the name read at `path`.
    pub fn signature(&self, path: &NodePath) -> Option<&Signature> {
        match self.earlier_of(path) {
            Some(earlier) => earlier.signature(path),
            None => self.signatures.get(path),
        }
    }

    /// The path of the form that gives `node` of the graph, so that the cycle
    /// check reports each form on a cycle: the first of
    /// [`ResolvedProgram::forms_of`], or the empty path for a fact.
    pub fn form_of(&self, node: GraphNodeIndex) -> &NodePath {
        static PROGRAM: std::sync::LazyLock<NodePath> = std::sync::LazyLock::new(NodePath::default);
        self.forms_of(node).first().unwrap_or(&PROGRAM)
    }

    /// The paths of the forms that give `node` of the graph, in the order
    /// the resolver declares them: none for a fact, several for a relation
    /// that several clauses derive.
    pub fn forms_of(&self, node: GraphNodeIndex) -> &[NodePath] {
        match self.earlier_node(node) {
            Some(earlier) => earlier.forms_of(node),
            None => &self.forms[self.own_index(node)],
        }
    }

    /// The nodes of the graph that the form at `form` gives, in the order of
    /// their indices: none for a path that is no form's, several for an
    /// `INIT` form, which gives a node to each output and each input it
    /// writes. The inverse of [`ResolvedProgram::forms_of`].
    pub fn nodes_of(&self, form: &NodePath) -> &[GraphNodeIndex] {
        match self.earlier_of(form) {
            Some(earlier) => earlier.nodes_of(form),
            None => self.form_nodes.get(form).map_or(&[], |nodes| nodes),
        }
    }

    /// Whether the form that holds the read at `read` reads its relation in
    /// its lifted form, as [`Side`] gives it.
    pub fn reads_lifted(&self, read: &NodePath) -> bool {
        match self.earlier_of(read) {
            Some(earlier) => earlier.reads_lifted(read),
            None => self.lifted.contains(read),
        }
    }

    /// Whether the read at `read` is a lifted read of the train examples
    /// alone: its site on the Example column holds a label that a positive
    /// `ex_output` atom of the read's conjunction, or of the guard of the
    /// `ALL` form it stands in, binds.
    pub fn reads_train_examples(&self, read: &NodePath) -> bool {
        match self.earlier_of(read) {
            Some(earlier) => earlier.reads_train_examples(read),
            None => self.train_lifted.contains(read),
        }
    }

    /// The resolved content of the node at `path`, or `None` where `path`
    /// names no node. The empty path names the whole program, whose content
    /// is that of its forms, with no order and no names.
    pub fn content(&self, path: &NodePath) -> Option<ResolvedContent> {
        if let Some(earlier) = self.earlier_of(path) {
            return earlier.content(path);
        }
        self.names.content(&self.program, path).map(|form| ResolvedContent { form })
    }

    /// The resolved content of the finished query at the top-level position
    /// `position`, in the program of its use closure alone: the forms of
    /// the nodes it reads at any depth, in program order, then the query.
    /// A `DET` relation has the columns that the reads of the program name,
    /// so the content of a query would otherwise depend on the forms that
    /// read its inputs and that the query does not read; the same query
    /// has one content in every program. The closure is resolved afresh
    /// whatever this resolution is, since a layered resolution gives a
    /// node's content from the forms it was resolved over.
    ///
    /// The content of a node is that of each form that gives it, and an
    /// `INIT` or `RIGID_DET` form gives several nodes that are written from
    /// the whole form. So the closure holds, for each form it holds, every
    /// node that form gives and what those nodes read, not only the node
    /// that something reads: a read in another input's body is a read of
    /// the content. The content of a `DEMONSTRATED` form writes each node
    /// that its rules declare, read or not, so the closure holds what each
    /// of them reads too. A name that no form of the closure declares
    /// would stand in the content as a name, which a decode gives as a slot
    /// and a file as a spelling.
    ///
    /// The sites of an atom stand in the content in the order of the
    /// program, which a decode takes from its tokens and the text of the
    /// program does not keep. The closure is resolved with those sites in
    /// the order of the text ([`crate::write::in_text_order`]), so a decode
    /// and the reader of its text give one content. A clause's gloss changes
    /// no table and no stream holds it, so the closure's clauses hold none;
    /// nor do a `DEMONSTRATED` form's rule names and texts, and its
    /// `&prediction` clauses hold the columns the stream fills alone
    /// ([`query_form`]). `None` where `position` names no node, and where a
    /// labeling that the content rests on passed its cap, as
    /// [`ResolvedProgram::query_content_or_bound`] gives.
    pub fn query_content(&self, position: usize, registry: &Registry) -> Option<ResolvedContent> {
        self.query_content_or_bound(position, registry)?.ok()
    }

    /// [`ResolvedProgram::query_content`], with the [`LabelingBound`] in
    /// place of the content where the search for a canonical labeling of a
    /// form in the content's closure passed its cap, since the content then
    /// may depend on the written order of the query. `None` where `position`
    /// names no node.
    pub fn query_content_or_bound(&self, position: usize, registry: &Registry) -> Option<Result<ResolvedContent, LabelingBound>> {
        let (closure, last) = self.query_closure(position, registry, false)?;
        let content = closure.content(&last)?;
        Some(match closure.names.labeling_bound() {
            Some(bound) => Err(bound),
            None => Ok(content),
        })
    }

    /// The resolved content of the finished query at the top-level position
    /// `position`, as [`ResolvedProgram::query_content`] gives it, with the
    /// canonical order of the query's form through the resolver's writer of
    /// the same closure, so that the content and the order name the form's
    /// lists and labels alike. A `DEMONSTRATED` form has no
    /// order. `None` where `position` names no node, and where a labeling that
    /// the content rests on passed its cap.
    ///
    /// Unlike [`ResolvedProgram::query_content`], the closure keeps the
    /// columns of each `DET` node that its reads name in the order of their
    /// labels' canonical positions, not in the order the `DET`'s clause writes
    /// them, so the content is also free of the order of those columns. It
    /// therefore differs from `query_content` for a `DET` read in another order.
    pub fn query_identity(&self, position: usize, registry: &Registry) -> Option<QueryIdentity> {
        let (closure, last) = self.query_closure(position, registry, true)?;
        let content = closure.content(&last)?;
        let (order, _) = closure.names.order(&closure.program, &last)?;
        closure.names.labeling_bound().is_none().then_some(QueryIdentity { content, order })
    }

    /// For each part of the `RIGID_DET` form at the top-level position
    /// `position`, the least index of a part it ties with, in the content
    /// that [`ResolvedProgram::query_content`] gives the form: two parts tie
    /// where the swap of the two leaves that content as it is, so that two
    /// programs that list them in either order have one QueryHash. Parts that
    /// tie read relations of one content at sites of one form, and hold the
    /// same rows. `None` where `position` names no `RIGID_DET` form.
    pub fn rigid_part_positions(&self, position: usize, registry: &Registry) -> Option<Box<[u32]>> {
        let (closure, last) = self.query_closure(position, registry, false)?;
        closure.names.part_positions(&closure.program, &last)
    }

    /// For each top-level form, whether it is the form at `position` or a form
    /// of a node that the form at `position` reads at any depth, at or before
    /// `position`. `None` where `position` names no form.
    pub fn use_closure(&self, position: usize) -> Option<Vec<bool>> {
        let forms = &self.program.value().forms;
        let mut keep = vec![false; forms.len()];
        *keep.get_mut(position)? = true;
        let mut reached = vec![false; self.graph.nodes.len()];
        let mut open = vec![position];
        while let Some(top) = open.pop() {
            for root in self.form_roots(top)? {
                for (node, reads) in self.graph.reached(root).into_iter().enumerate() {
                    if !reads || std::mem::replace(&mut reached[node], true) {
                        continue;
                    }
                    for form in self.forms_of(GraphNodeIndex(node as u32)) {
                        let Some(top) = form.0.first().map(|step| step.0 as usize).filter(|top| *top <= position) else { continue };
                        if !std::mem::replace(&mut keep[top], true) {
                            open.push(top);
                        }
                    }
                }
            }
        }
        Some(keep)
    }

    /// The program of the use closure of the finished query at the
    /// top-level position `position`, resolved as
    /// [`ResolvedProgram::query_content`] gives, and the path of the query
    /// in it.
    fn query_closure(&self, position: usize, registry: &Registry, canonical_kept: bool) -> Option<(ResolvedProgram, NodePath)> {
        let forms = &self.program.value().forms;
        let keep = self.use_closure(position)?;
        let closure: Vec<_> = forms.iter().zip(&keep).take(position + 1).filter(|(_, keep)| **keep).map(|(form, _)| query_form(form, registry)).collect();
        let last = NodePath::top(closure.len() as u32 - 1);
        let pruned = crate::write::in_text_order(&Node::new(Program { forms: closure.into() }), registry);
        Some((build::resolve_with(&pruned, None, &SolverScope::default(), registry, canonical_kept).value, last))
    }

    /// Whether a top-level form before `end` reads, at any depth, a node that
    /// a form at `end` or later gives.
    pub fn reads_from(&self, end: usize) -> bool {
        let mut seen = vec![false; self.graph.nodes.len()];
        let mut stack: Vec<GraphNodeIndex> = (0..end).filter_map(|top| self.form_roots(top)).flatten().collect();
        while let Some(node) = stack.pop() {
            if std::mem::replace(&mut seen[node.0 as usize], true) {
                continue;
            }
            if self.forms_of(node).iter().any(|form| form.0.first().is_some_and(|step| step.0 as usize >= end)) {
                return true;
            }
            stack.extend(self.graph.reads[node.0 as usize].iter().copied());
        }
        false
    }

    /// The nodes that the top-level form at `top` gives, and, for a
    /// `DEMONSTRATED` form, the nodes its rules declare. `None` where `top`
    /// is out of the range of a path step.
    fn form_roots(&self, top: usize) -> Option<Vec<GraphNodeIndex>> {
        let mut roots = self.nodes_of(&NodePath::top(u32::try_from(top).ok()?)).to_vec();
        if let Some(crate::program::Form::Demonstrated(_)) = self.program.value().forms.get(top) {
            let in_form = |scope: &crate::program::NameScope| matches!(scope, crate::program::NameScope::DemoRule(rule) if rule.0.first().is_some_and(|step| step.0 as usize == top));
            roots.extend((0..self.graph.nodes.len()).filter(|&node| in_form(&self.graph.nodes[node].scope)).map(|node| GraphNodeIndex(node as u32)));
        }
        Some(roots)
    }

    /// The resolved content of the node `node` of the dependency graph, or
    /// `None` where the program holds none for it.
    pub fn node_content(&self, node: GraphNodeIndex) -> Option<ResolvedContent> {
        let form = self.written_content(node.0 as usize)??.clone();
        Some(ResolvedContent { form })
    }

    /// The content of `node`, as the layer of `node` holds it: `None` where
    /// the program has no node `node`, `Some(None)` where the node has no
    /// content (a node on a cycle), and otherwise its content, which a layer
    /// that left it unwritten writes on this first read. A write of a
    /// content reads the content of each node it reads through this, so the
    /// nodes of a layer that no read of its last form resolves to, whose
    /// content a later layer's form may read, have their content then.
    fn written_content(&self, node: usize) -> Option<Option<&crate::program::canonical::CanonicalForm>> {
        if let Some(earlier) = self.earlier_node(GraphNodeIndex(node as u32)) {
            return earlier.written_content(node);
        }
        let slot = node.checked_sub(self.names.first_node())?;
        match self.names.contents.get(slot)? {
            Some(form) => Some(Some(form)),
            None => Some(self.names.unwritten.get(slot)?.as_ref().map(|cell| crate::eval::once_noted(cell, || self.unwritten_content(slot)))),
        }
    }

    /// The content of the node of the entry `slot` of this resolution's
    /// per-node lists, which no pass of the resolution read, so that the
    /// builder left it unwritten.
    fn unwritten_content(&self, slot: usize) -> crate::program::canonical::CanonicalForm {
        let node = slot + self.names.first_node();
        let scope = &self.graph.nodes[node].scope;
        let parts = self.forms[slot].iter().map(|path| names::form_bytes(&self.names, self.program.value(), scope, path));
        names::node_form(&self.graph.nodes[node].kind, parts)
    }

    /// The resolved content of the part of the body of the clause at
    /// `clause` that the conjuncts at `conjuncts`, indexes into the body,
    /// make, whose relation's columns are those of the clause whose labels
    /// `columns` gives, with those labels in the order of the part's
    /// columns. A clause that the case takes from the concept program has
    /// the content of its part there. `None` where `clause` is the path of
    /// no clause.
    pub fn part_content(&self, clause: &NodePath, conjuncts: &[u32], columns: &[LabelId]) -> Option<(ResolvedContent, Box<[LabelId]>)> {
        if let (Some(concept), Some(path)) = (self.concept(), self.concept_path(clause)) {
            return concept.part_content(&path, conjuncts, columns);
        }
        let (form, columns) = self.names.part_content(&self.program, clause, conjuncts, columns)?;
        Some((ResolvedContent { form }, columns))
    }

    /// The name of the stored parameter's column that each column of the
    /// proposer at `index` of the clause at `clause` stands for, in the
    /// proposer's column order. A `DET_OR_RULE` line maps a proposer's
    /// columns by that order onto the stored parameter's columns, and name
    /// resolution gives each the stored parameter's name.
    pub fn proposer_columns(&self, clause: &NodePath, index: usize) -> Option<&[ColumnName]> {
        if let Some(earlier) = self.earlier_of(clause) {
            return earlier.proposer_columns(clause, index);
        }
        self.proposer_columns.get(&(clause.clone(), index)).map(|columns| &columns[..])
    }

    /// The concept program that the case's concept `DET` forms resolve
    /// their reads in, as [`ConceptReads`] gives, or `None` for a program
    /// resolved with no [`ConceptReads`].
    pub fn concept(&self) -> Option<&ResolvedProgram> {
        self.concept.as_ref().map(|concept| &*concept.program)
    }

    /// The path in [`ResolvedProgram::concept`] of what stands at `path`,
    /// where `path` stands at or under a `DET` form that the case takes
    /// from the concept program.
    pub fn concept_path(&self, path: &NodePath) -> Option<NodePath> {
        let concept = self.concept.as_ref()?;
        (1..=path.0.len()).find_map(|len| {
            let form = NodePath(path.0[..len].into());
            rebase(path, &form, concept.paths.get(&form)?)
        })
    }
}

/// `path` with its prefix `from` replaced by `to`, where `from` is a
/// prefix of it.
fn rebase(path: &NodePath, from: &NodePath, to: &NodePath) -> Option<NodePath> {
    path.0.strip_prefix(&from.0[..]).map(|rest| to.join(&NodePath(rest.into())))
}

/// A column of a relation by its path: the column's name, then, on a
/// record, the field's.
pub type ExamplePath = Box<[ColumnName]>;

/// The path after the owner's name of the output that `relation` reads,
/// where it reads one.
pub fn output_of(relation: &RelationRef) -> Option<&[OutputStep]> {
    match relation {
        RelationRef::Output(output) => Some(&output.path),
        RelationRef::Declared(_) | RelationRef::Fact(_) | RelationRef::Lib(_) | RelationRef::DefinedPort(_) => None,
    }
}

/// The concept program's resolution, which the `DET` forms that a case
/// takes from the concept program read through: each of those forms, at its
/// path in the case program, resolves its reads in `concept`, so it reads the
/// concept program's derivation in every case, and the case reads its
/// parameter as one node.
#[derive(Clone, Copy, Debug)]
pub struct ConceptReads<'a> {
    pub concept: &'a Arc<ResolvedProgram>,
    /// The paths in the case program of the concept program's `DET` forms,
    /// as [`crate::solver::Case::concept_determinations`] gives them.
    pub determinations: &'a [NodePath],
}

/// What every case of a solver resolves against, as
/// [`crate::solver::Solver::derived_relations`] gives it, or a synthesized
/// program's own.
#[derive(Clone, Debug, Default)]
pub struct SolverScope {
    /// The relations that some block of the solver derives, as
    /// [`crate::solver::Solver::derived`] gives them.
    pub derived: crate::hash::StableHashSet<ProgramRelation>,
    /// The column names that the sites of the reads of each relation name
    /// across the solver's cases, as [`crate::solver::Solver::read_columns`]
    /// gives them.
    pub read_columns: crate::hash::StableHashMap<ProgramRelation, Vec<ColumnName>>,
}

/// Adds to `names` each of `columns` that it does not hold, in order.
pub(crate) fn add_columns<'c>(names: &mut Vec<ColumnName>, columns: impl IntoIterator<Item = &'c ColumnName>) {
    for column in columns {
        if !names.contains(column) {
            names.push(column.clone());
        }
    }
}

/// Resolves the names of `case`, a case program that `crate::solver` gives,
/// or a synthesized program. `concept` is `None` for a synthesized program
/// and for the concept case. `scope` holds what the cases of the solver
/// share, or a synthesized program's own: a name among its derived relations
/// that no block of the case derives is [`Resolution::Undefined`], and a name among none is
/// [`Resolution::Unresolved`].
///
/// Gives a diagnostic of the scope at each name that resolves to nothing and
/// is no relation a block could derive, which resolves to
/// [`Resolution::Unresolved`], so that every other check still runs over
/// the case.
pub fn resolve(
    case: &Node<Program>,
    concept: Option<ConceptReads<'_>>,
    scope: &SolverScope,
    registry: &Registry,
) -> WithDiagnostics<ResolvedProgram> {
    build::resolve(case, concept, scope, registry)
}

/// The Name that the export of tables gives the output of a `RIGID_DET`
/// form that `read` reads in `program`, as
/// [`crate::program::rigid_output_name`] gives it: `read` is the relation of
/// the read as a file writes it, `&marker.glyph`, `&marker.bbox.box` or
/// `&marker.pose`. A read of a part that ties with an earlier part of the
/// form ([`ResolvedProgram::rigid_part_positions`]) takes the Name of the
/// least part it ties with, which holds the same rows, so two programs of
/// one QueryHash give a read of one output one Name. The error names a read
/// that reads no output of a `RIGID_DET` form of `program`.
pub fn rigid_read_name(program: &Node<Program>, read: &str, registry: &Registry) -> Result<String, String> {
    let unread = || format!("`{read}` reads no output of a `RIGID_DET` form of the program");
    let (owner, rest) = read.split_once('.').ok_or_else(unread)?;
    let found = program.value().forms.iter().enumerate().find_map(|(position, form)| match form {
        crate::program::Form::RigidDet(rigid) if crate::program::declared_spelled(&rigid.value().name.0) == owner => Some((position, rigid.value())),
        _ => None,
    });
    let (position, rigid) = found.ok_or_else(unread)?;
    let path: Vec<OutputStep> = if rest == crate::read::spelling::POSE {
        vec![OutputStep::Pose]
    } else {
        let mut steps = rigid.parts.iter().filter_map(|part| form_columns::part_steps(&part.value().relation));
        steps.find(|steps| crate::program::output_path_spelled(steps) == rest).ok_or_else(unread)?
    };
    let prefix = Node::new(Program { forms: program.value().forms[..=position].into() });
    let positions = resolve(&prefix, None, &SolverScope::default(), registry).value.rigid_part_positions(position, registry).ok_or_else(unread)?;
    crate::program::rigid_output_name(rigid, &path, |part| positions[part]).ok_or_else(unread)
}

/// For each part of the `RIGID_DET` form at the top-level position `position`
/// of `program`, in the order that the form lists its parts: the path of the
/// part's output after the form's name, as a file writes it (`glyph`,
/// `bbox.box`), and the position of the part in the form's canonical form,
/// with a part that ties with an earlier part ([`ResolvedProgram::rigid_part_positions`])
/// at the least such part's position. The Name of the part's output is
/// `slot <position>`, followed by the steps of the path after the part's own,
/// as [`rigid_read_name`] gives it. The error says that `position` names no
/// `RIGID_DET` form of `program`.
pub fn rigid_parts(program: &Node<Program>, position: usize, registry: &Registry) -> Result<Vec<(String, u32)>, String> {
    let Some(crate::program::Form::RigidDet(rigid)) = program.value().forms.get(position) else {
        return Err(format!("the form at position {position} is no `RIGID_DET` form of the program"));
    };
    let prefix = Node::new(Program { forms: program.value().forms[..=position].into() });
    let positions = resolve(&prefix, None, &SolverScope::default(), registry)
        .value
        .rigid_part_positions(position, registry)
        .ok_or_else(|| format!("the form at position {position} has no part positions"))?;
    Ok(rigid
        .value()
        .parts
        .iter()
        .zip(positions.iter())
        .map(|(part, &at)| (form_columns::part_steps(&part.value().relation).map_or_else(String::new, |steps| crate::program::output_path_spelled(&steps)), at))
        .collect())
}

/// The most layers over the lowest that a chain of layered resolutions holds.
/// A lookup of an entry in a lower layer takes one step for each layer above
/// it, so the chain is cut at this count by a full resolution.
pub const MAX_LAYERS: usize = 16;

/// The resolution of `program`, whose forms before its last are the forms of
/// `earlier`'s program, by the passes of [`resolve`] over the last form
/// alone: the result holds the entries of the last form and a reference to
/// `earlier`, and no operation walks or copies the entries of the earlier
/// forms, as [`ResolvedProgram`] says of its layers. Its build time and its
/// size follow the last form. A last form that reads a column of a `DET`
/// parameter that no earlier read names is resolved over `earlier` resolved
/// again with that column kept, once for each such set of columns
/// ([`ResolvedProgram::widened`]), and that resolution of the whole program
/// is the one step whose time follows the program, apart from the content of
/// the nodes that the added columns do not reach, which it takes from `earlier`.
///
/// `earlier` may be a layered resolution, so each form of a program can be
/// resolved from the resolution of the forms before it. A layer holds what
/// the call that made it was asked to hold (a prefix resolution holds no
/// signature of a read, as [`resolve_prefix`] says), so a lookup of an entry
/// that a layer left out finds none, as it does for the last form of that
/// layer's resolution.
///
/// Where the last form is no clause, `INIT`, `CHOOSE` or `RIGID_DET` form that
/// declares a relation no earlier form declares, or `earlier` was resolved with
/// a concept program or already stands on [`MAX_LAYERS`] layers, the result
/// is [`resolve`]'s on `program`, which holds one layer. So the chain stays
/// short, and a full resolution comes once for each `MAX_LAYERS` forms.
///
/// The diagnostics are those of [`resolve`] for the forms it resolved: a
/// program whose name resolves to nothing holds a scope error here, and a
/// caller that checks or evaluates the program takes them with it.
pub fn resolve_last(earlier: &Arc<ResolvedProgram>, program: &Node<Program>, registry: &Registry) -> WithDiagnostics<ResolvedProgram> {
    let _timed = crate::stats::span(crate::stats::Phase::ResolveLast);
    crate::stats::units(crate::stats::Phase::ResolveLast, earlier.graph.nodes.len());
    build::resolve_last(earlier, program, registry)
}

/// [`resolve_last`] for a program whose last form is the form in progress
/// that the prefix checks read: a `DEMONSTRATED` last form is resolved by
/// the passes over the last form alone as well.
pub fn resolve_in_progress(earlier: &Arc<ResolvedProgram>, program: &Node<Program>, registry: &Registry) -> ResolvedProgram {
    let _timed = crate::stats::span(crate::stats::Phase::ResolveLast);
    crate::stats::units(crate::stats::Phase::ResolveLast, earlier.graph.nodes.len());
    build::resolve_in_progress(earlier, program, registry)
}

/// [`resolve_in_progress`] for the checks of a prefix, which read no signature
/// of a read: a layered resolution holds none.
pub fn resolve_prefix(earlier: &Arc<ResolvedProgram>, program: &Node<Program>, registry: &Registry) -> ResolvedProgram {
    let _timed = crate::stats::span(crate::stats::Phase::ResolveLast);
    crate::stats::units(crate::stats::Phase::ResolveLast, earlier.graph.nodes.len());
    build::resolve_prefix(earlier, program, registry)
}

/// [`resolve_prefix`] for the checks alone, which read no proposer's columns
/// ([`ResolvedProgram::proposer_columns`]): it holds none, so an evaluation
/// reads no such resolution.
pub fn resolve_for_checks(earlier: &Arc<ResolvedProgram>, program: &Node<Program>, registry: &Registry) -> ResolvedProgram {
    let _timed = crate::stats::span(crate::stats::Phase::ResolveLast);
    crate::stats::units(crate::stats::Phase::ResolveLast, earlier.graph.nodes.len());
    build::resolve_for_checks(earlier, program, registry)
}

/// Whether a complete-program grammar must insert the lifted Example
/// column at an open relation. Runs only binding and side analysis; the
/// completed AST still goes through the full resolver and checker.
pub(crate) fn grammar_reads_example_column(program: &Node<Program>, read: &NodePath, registry: &Registry) -> bool {
    build::reads_example_column(program, read, registry)
}

/// A case of a solver with its resolution and the diagnostics of that
/// resolution.
#[derive(Debug)]
pub struct ResolvedCase {
    pub case: crate::solver::Case,
    pub resolved: WithDiagnostics<Arc<ResolvedProgram>>,
}

/// The resolution of each case of a solver, as [`resolve_cases`] gives it:
/// the concept case's, with no [`ConceptReads`], and each other case's, with
/// the [`ConceptReads`] of the concept case's resolution and the case's
/// [`crate::solver::Case::concept_determinations`].
#[derive(Debug)]
pub struct ResolvedCases {
    concept: ResolvedCase,
    /// Whether [`crate::solver::Solver::cases`] gives the concept case,
    /// which it does not where a `representative` line names another case.
    concept_is_a_case: bool,
    /// The cases of [`crate::solver::Solver::cases`] other than the concept
    /// case, in its order.
    others: Box<[ResolvedCase]>,
}

impl ResolvedCases {
    /// The concept case and its resolution.
    pub fn concept(&self) -> &ResolvedCase {
        &self.concept
    }

    /// Each case that [`crate::solver::Solver::cases`] gives with
    /// [`crate::solver::Exclusion::WithExcluded`], with its resolution, in
    /// its order, the concept case first.
    pub fn cases(&self) -> impl Iterator<Item = &ResolvedCase> {
        self.concept_is_a_case.then_some(&self.concept).into_iter().chain(self.others.iter())
    }

    /// Each case resolved: the concept case, then each other case of
    /// [`ResolvedCases::cases`].
    pub fn resolved(&self) -> impl Iterator<Item = &ResolvedCase> {
        std::iter::once(&self.concept).chain(self.others.iter())
    }
}

/// Resolves the concept case of `solver`, and then each other case of
/// [`crate::solver::Solver::cases`] with
/// [`crate::solver::Exclusion::WithExcluded`], with the [`ConceptReads`] of
/// the concept case's resolution, against
/// [`crate::solver::Solver::derived_relations`].
pub fn resolve_cases(solver: &crate::solver::Solver, registry: &Registry) -> ResolvedCases {
    let scope = solver.derived_relations();
    let concept_case = solver.concept_case();
    let shared = |resolved: WithDiagnostics<ResolvedProgram>| WithDiagnostics { value: Arc::new(resolved.value), diagnostics: resolved.diagnostics };
    let concept = shared(resolve(&concept_case.program, None, &scope, registry));
    let mut concept_is_a_case = false;
    let mut others = Vec::new();
    for case in solver.cases(crate::solver::Exclusion::WithExcluded) {
        if case.name == concept_case.name {
            concept_is_a_case = true;
            continue;
        }
        let reads = ConceptReads { concept: &concept.value, determinations: case.concept_determinations() };
        let resolved = shared(resolve(&case.program, Some(reads), &scope, registry));
        others.push(ResolvedCase { case, resolved });
    }
    ResolvedCases { concept: ResolvedCase { case: concept_case, resolved: concept }, concept_is_a_case, others: others.into() }
}

/// Each `DEMO_RULE` form of the `DEMONSTRATED` form at `path`, with its
/// path: its children after the key clause and the inputs.
fn demo_rules<'d>(
    demonstrated: &'d crate::program::Demonstrated,
    path: &NodePath,
) -> impl Iterator<Item = (NodePath, &'d crate::program::DemoRule)> + 'd {
    let path = path.clone();
    let rules = demonstrated.rules.iter().enumerate();
    rules.map(move |(index, rule)| (path.child(demonstrated.position(crate::program::DemonstratedPart::Rule(index))), rule.value()))
}

/// `form` as the content of a query holds it: a clause with no gloss, and
/// a `DEMONSTRATED` form as [`crate::stream::demonstrated::as_streamed`]
/// gives it.
fn query_form(form: &crate::program::Form, registry: &Registry) -> crate::program::Form {
    use crate::program::{Clause, Form};
    match form {
        Form::Clause(clause) if clause.value().gloss.is_some() => Form::Clause(Node::new(Clause { gloss: None, ..clause.value().clone() })),
        Form::Demonstrated(demonstrated) => Form::Demonstrated(Node::new(crate::stream::demonstrated::as_streamed(demonstrated.value(), registry))),
        form => form.clone(),
    }
}

pub(crate) mod column_sources;
pub(crate) mod columns;
pub(crate) mod form_columns;
pub mod registry_columns;

pub mod given;

mod names;

mod build;

impl ResolvedProgram {
    /// The depth of `node` in the dependency graph: 0 for a fact relation,
    /// and otherwise one more than the largest depth among the nodes it
    /// reads, 1 for a node that reads none. A lib relation is no node and
    /// adds nothing.
    pub fn depth(&self, node: GraphNodeIndex) -> u32 {
        let depths = self.depths.get_or_init(|| {
            let mut depths: Vec<Option<u32>> = vec![None; self.graph.nodes.len()];
            let mut open = vec![false; depths.len()];
            for start in 0..depths.len() {
                self.depth_of(start, &mut depths, &mut open);
            }
            depths.into_iter().map(|depth| depth.unwrap_or(0)).collect()
        });
        depths[node.0 as usize]
    }

    fn depth_of(&self, node: usize, depths: &mut [Option<u32>], open: &mut [bool]) -> u32 {
        if let Some(depth) = depths[node] {
            return depth;
        }
        if matches!(self.graph.nodes[node].kind, DependencyKind::Fact(_)) {
            depths[node] = Some(0);
            return 0;
        }
        open[node] = true;
        let mut deepest = 0;
        for &read in self.graph.reads[node].iter() {
            let read = read.0 as usize;
            if !open[read] {
                deepest = deepest.max(self.depth_of(read, depths, open));
            }
        }
        open[node] = false;
        depths[node] = Some(deepest + 1);
        deepest + 1
    }

    /// The candidate keys of the relation of `node` that the program text
    /// gives, each as the row positions of its columns in increasing order:
    /// the columns of each `ONE` mark of a clause, none for `(ONE)`, and
    /// the row's columns of a `CHOOSE` form.
    pub fn column_keys(&self, node: GraphNodeIndex) -> Vec<Vec<u16>> {
        let root = NodeRef::Program(self.program.value());
        let mut keys: Vec<Vec<u16>> = Vec::new();
        for form in self.forms_of(node) {
            let positions = |labels: &mut dyn Iterator<Item = LabelId>| {
                let mut key: Vec<u16> = labels.filter_map(|label| self.label_position(form, label)).map(|position| position.0).collect();
                key.sort_unstable();
                key
            };
            let found: Vec<Vec<u16>> = match node_at(root, form) {
                Some(NodeRef::Clause(clause)) => clause.ones.iter().map(|mark| positions(&mut mark.key.iter().copied())).collect(),
                Some(NodeRef::Choose(choose)) => choose.rows.iter().map(|rows| positions(&mut rows.columns.iter().map(|column| column.label))).collect(),
                _ => Vec::new(),
            };
            for key in found {
                if !keys.contains(&key) {
                    keys.push(key);
                }
            }
        }
        keys
    }
}
