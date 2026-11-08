//! The canonical form of a node and its hash.
//!
//! A body's canonical form is the same under a reorder of unordered atoms and a
//! renaming of its labels, apart
//! from the renaming that [`canonical_hash`] gives. The labeling comes from
//! individualization–refinement: color refinement with the column paths as
//! edge labels, then the first largest cell that is not a singleton, with a
//! cap of [`SEARCH_NODE_CAP`] search nodes on the search of each label
//! scope. A form whose search passes the cap has no canonical labeling that
//! is free of its written order, so the form is refused with a
//! [`LabelingBound`] and no hash of it reaches a caller.
//!
//! A node's canonical hash writes each relation the node reads as the file
//! writes it, [`AsWritten`]. The resolved content of a node in one case program, in
//! which each derived relation stands for its own content, is
//! [`crate::resolver::ResolvedProgram::content`], which writes the same
//! canonical form through a [`NameWriter`] of the resolver. That content
//! holds no name that the node declares, so two forms of equal content
//! under different names have equal resolved content.
//!
//! The byte encoding of a form is in `form`, the graph of a label scope
//! with its color refinement in `graph`, the one walk of a label scope's
//! nodes that both take in `walk`, the canonical order of a form in
//! `order`, and the writes a form's node caches in `replay`. This module holds the search over that graph. Each module
//! writes a column path through the [`NameWriter`] of the write, so the
//! edge labels of the graph and the bytes of the form name each column
//! alike.

mod form;
mod graph;
mod order;
mod replay;
mod walk;

use super::path::{child_index, NodePath, NodeRef, PathStep};
use super::*;
use crate::hash::StableHashMap;
use form::*;
use graph::*;
use order::Recorded;

pub use order::CanonicalOrder;
pub(crate) use replay::cached_write;
pub(crate) use walk::one_scope_labels;

pub(crate) use form::{holds_rigid_det, normalized_constraint,canonical_form, form_scope_labels, prediction, relation_of, scope_labels, shares_rule_scope};
pub use form::{canonical_hash, opens_scope, AsWritten, Canonical, CanonicalForm, CanonicalWriter, NameWriter};
pub(in crate::program) use form::form_of;

/// The provisional cap on the search nodes of individualization–refinement,
/// for the search of each label scope.
///
/// The cap guards synthesized bodies, whose symmetry the corpus does not
/// show. The corpus's search reaches at most 13 nodes, by one reading. The
/// gauge `labeling_nodes` ([`crate::eval::Gauge::LabelingNodes`]) measures
/// the most nodes that a search reaches over the gold requests, and the cap
/// is to be set from that.
pub const SEARCH_NODE_CAP: u32 = 1000;

/// The bound that a form passes where the search for the canonical labeling
/// of one of its label scopes takes more than [`SEARCH_NODE_CAP`] search
/// nodes. The labeling that such a search ends with may depend on the
/// written order of the form, so the form is refused and no hash of it
/// reaches a caller.
#[derive(Clone, Copy, PartialEq, Eq, Hash, Debug)]
pub struct LabelingBound {
    /// The cap that the search passed.
    pub cap: u32,
}

impl LabelingBound {
    /// The bound at [`SEARCH_NODE_CAP`].
    pub fn at_cap() -> Self {
        LabelingBound { cap: SEARCH_NODE_CAP }
    }
}

impl std::fmt::Display for LabelingBound {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(f, "the search for the form's canonical labeling passed its cap of {} search nodes", self.cap)
    }
}

impl std::error::Error for LabelingBound {}

/// The search nodes that the search of the label scope in progress has
/// left, and whether the search of any scope of the value passed the cap.
/// Each scope's search starts with [`SEARCH_NODE_CAP`] nodes, and a search
/// that runs inside a leaf of another spends none of that other's nodes.
#[derive(Clone, Debug)]
pub struct SearchBudget {
    pub remaining: u32,
    /// Set when the search of a scope passed the cap: the value is refused
    /// with a [`LabelingBound`].
    pub reached: bool,
}

impl SearchBudget {
    /// A budget of [`SEARCH_NODE_CAP`] nodes, with no scope at the cap.
    pub fn new() -> Self {
        SearchBudget { remaining: SEARCH_NODE_CAP, reached: false }
    }
}

impl Default for SearchBudget {
    fn default() -> Self {
        SearchBudget::new()
    }
}

/// What the canonical form of a form gives, kept on the form's node from
/// its first use, so that each case program that holds the node, and each
/// check of it, reads it once: the labels of its scope, as
/// [`form_scope_labels`] gives them, and its canonical order and form, as
/// [`CanonicalOrder::with_form`] gives them, with whether a search reached
/// the cap; that form with the written order of its lists, as
/// [`CanonicalOrder::with_written_lists`] gives it; whether a `RIGID_DET`
/// form stands in it, as [`holds_rigid_det`] gives it; and its writes through
/// name writers other than [`AsWritten`], as [`cached_write`] gives them.
#[derive(Debug, Default)]
pub(super) struct FormCache {
    holds_rigid_det: std::sync::OnceLock<bool>,
    scope_labels: std::sync::OnceLock<(Box<[LabelId]>, crate::eval::NoteId)>,
    order: std::sync::OnceLock<((CanonicalOrder, CanonicalForm, bool), crate::eval::NoteId)>,
    written_lists: std::sync::OnceLock<(CanonicalForm, crate::eval::NoteId)>,
    writes: replay::WriteCache,
}

/// The canonical labeling of one scope: for each label of the scope, its
/// position in the canonical form.
#[derive(Clone, Debug)]
pub struct CanonicalLabeling {
    pub positions: Box<[(super::LabelId, u32)]>,
    /// Whether the search passed [`SEARCH_NODE_CAP`], so that the labeling
    /// is no canonical labeling: a form with such a scope is refused with a
    /// [`LabelingBound`].
    pub reached_cap: bool,
    /// The other labelings the search found whose form is the canonical
    /// form, each as `positions` gives a labeling: those that a symmetry of
    /// the scope maps the labeling onto.
    pub others: Box<[Box<[(super::LabelId, u32)]>]>,
}

/// The labels that one canonical labeling numbers: those of a label scope,
/// as [`LabelId`] gives a scope, or those of a node whose own hash is taken
/// apart from its scope.
#[derive(Clone, Copy, Debug)]
pub enum LabelScope<'a> {
    Clause(&'a Clause),
    Instance(&'a Instance),
    Choose(&'a Choose),
    RigidDet(&'a RigidDet),
    Out(&'a Out),
    /// A `DEMONSTRATED` form's key clause and inputs, apart from its
    /// `DEMO_RULE` forms.
    DemonstratedKey(&'a Demonstrated),
    DemoRule(&'a DemoRule),
    Body(&'a Body),
    Atom(&'a Atom),
    KeyClause(&'a KeyClause),
    InstanceInput(&'a InstanceInput),
}

/// The canonical labeling of `scope`, by individualization–refinement, with
/// the column paths as edge labels as `names` writes them: as written for a
/// node's hash, [`AsWritten`], or as the resolved positions for the
/// resolved content.
pub fn canonical_labeling(scope: LabelScope, names: &dyn NameWriter, search: &mut SearchBudget) -> CanonicalLabeling {
    let mut cx = Context::new(search, names);
    let (labelings, reached_cap) = cx.labelings(scope);
    let mut labelings = labelings.iter().map(by_position);
    let positions = labelings.next().expect("the search reaches a leaf");
    CanonicalLabeling { positions, reached_cap, others: labelings.collect() }
}

/// Each label's canonical position.
type Labels = StableHashMap<LabelId, u32>;

fn by_position(labels: &Labels) -> Box<[(LabelId, u32)]> {
    let mut positions: Vec<(LabelId, u32)> = labels.iter().map(|(l, p)| (*l, *p)).collect();
    positions.sort_by_key(|(_, p)| *p);
    positions.into()
}

/// The panic text for a child the form writer writes that the children of
/// its parent do not hold at its step.
const CHILD_FAULT: &str = "the children of the node being written hold each child the form writer writes";

/// The step of `child` among the children of `parent`.
fn child_step(parent: NodeRef<'_>, child: NodeRef<'_>) -> u32 {
    child_index(parent, child).expect(CHILD_FAULT)
}

/// The state of one write: the labels of the scope being written, the
/// search budget, the name writer, and, for [`CanonicalOrder`], the source
/// path of the node being written, relative to the form, and the orders
/// recorded.
struct Context<'a> {
    labels: Labels,
    /// The bytes of the node being written, while the walk of a label
    /// scope's nodes writes it ([`Context::walk_into`]).
    out: CanonicalWriter,
    search: &'a mut SearchBudget,
    names: &'a dyn NameWriter,
    path: Vec<PathStep>,
    order: Option<Recorded>,
    /// Feature-only site normalization never participates in resolver/check caches.
    feature_sites: bool,
    /// The order of the columns of the relation of the atom being written,
    /// as [`NameWriter::write_column_in`] takes it.
    column_order: usize,
    /// The field names of the head sites of the instance being written, by
    /// order of first use.
    head_fields: HeadFields,
    /// The other labelings of the scope whose canonical labeling was found
    /// last, for [`Context::with_labels`] to record with the labels.
    others: Option<Box<[Box<[(LabelId, u32)]>]>>,
    /// The search nodes that the search of the label scope in progress has
    /// visited, those past the cap included.
    visited: u32,
}

impl<'a> Context<'a> {
    fn new(search: &'a mut SearchBudget, names: &'a dyn NameWriter) -> Self {
        Context { labels: Labels::default(), out: CanonicalWriter::default(), search, names, path: Vec::new(), order: None, feature_sites: names.feature_sites(), column_order: 0, head_fields: HeadFields::default(), others: None, visited: 0 }
    }

    fn position(&self, label: LabelId) -> u32 {
        *self.labels.get(&label).expect("each label of a scope has a position in its labeling")
    }

    fn label(&self, out: &mut CanonicalWriter, label: LabelId) {
        out.tag(Tag::Label);
        out.int(self.position(label));
    }

    /// Runs `write` on `child`, a child of `parent`, the node being
    /// written, at the step of its index among the children of `parent`.
    ///
    /// # Panics
    ///
    /// Where the write records a [`CanonicalOrder`] and the children of
    /// `parent` do not hold `child`, a fault of the path table or of the
    /// form writer.
    fn child<'n, R>(&mut self, parent: NodeRef<'n>, child: NodeRef<'n>, write: impl FnOnce(&mut Self) -> R) -> R {
        self.at_step(|| child_step(parent, child), write)
    }

    /// Runs `write` on the child at the step `step` gives. The path is read
    /// only to record a [`CanonicalOrder`], so `step` runs only in a write
    /// that records one.
    fn at_step<R>(&mut self, step: impl FnOnce() -> u32, write: impl FnOnce(&mut Self) -> R) -> R {
        let recording = self.order.is_some();
        if recording {
            self.path.push(PathStep(step()));
        }
        let result = write(self);
        if recording {
            self.path.pop();
        }
        result
    }

    /// Runs `walk` with `out` as the bytes it writes.
    fn walk_into(&mut self, out: &mut CanonicalWriter, walk: impl FnOnce(&mut Self)) {
        std::mem::swap(&mut self.out, out);
        walk(self);
        std::mem::swap(&mut self.out, out);
    }

    /// Writes `columns` in the order of their labels' canonical positions,
    /// each name through `name`. Keys and OUT retain their positional order.
    fn columns(&self, out: &mut CanonicalWriter, columns: &[RelationColumn], preserve_order: bool, name: impl Fn(&mut CanonicalWriter, &ColumnName)) {
        let mut ordered: Vec<(u32, &ColumnName)> = columns.iter().map(|c| (self.position(c.label), &c.name)).collect();
        if !preserve_order { ordered.sort_by_key(|(position, _)| *position); }
        out.len(ordered.len());
        for (position, column) in ordered {
            name(out, column);
            out.int(position);
        }
    }

    /// Runs `write` with the labels of `scope`.
    fn in_scope(&mut self, scope: LabelScope, write: impl FnOnce(&mut Self)) {
        let labels = self.recorded_labeling(scope);
        self.with_labels(labels, write);
    }

    /// The canonical labeling of `scope`; where the write records a
    /// [`CanonicalOrder`], it keeps the other labelings the search found for
    /// the next [`Context::with_labels`].
    fn recorded_labeling(&mut self, scope: LabelScope) -> Labels {
        let (labelings, _) = self.labelings(scope);
        let mut labelings = labelings.into_iter();
        let labels = labelings.next().expect("the search reaches a leaf");
        if self.order.is_some() {
            self.others = Some(labelings.map(|other| by_position(&other)).collect());
        }
        labels
    }

    /// Runs `write` with `labels`, the labels of the scope whose form stands
    /// at the node being written, and records them.
    fn with_labels(&mut self, labels: Labels, write: impl FnOnce(&mut Self)) {
        if let Some(order) = &mut self.order {
            let path = NodePath(self.path.clone().into());
            if let Some(others) = self.others.take() {
                order.symmetries.insert(path.clone(), others);
            }
            order.labels.insert(path, by_position(&labels));
        }
        let outer = std::mem::replace(&mut self.labels, labels);
        write(self);
        self.labels = outer;
    }

    /// The canonical labeling of `scope`, and whether its search reached
    /// the cap.
    fn labeling(&mut self, scope: LabelScope) -> (Labels, bool) {
        let (mut labelings, cut_short) = self.labelings(scope);
        (labelings.swap_remove(0), cut_short)
    }

    /// The canonical labeling of `scope`, then each other labeling the
    /// search found whose form is the canonical form, and whether its
    /// search reached the cap.
    fn labelings(&mut self, scope: LabelScope) -> (Vec<Labels>, bool) {
        let mut graph = GraphBuilder::new(self.names, self.feature_sites);
        let root = graph.vertex(Tag::Root, |_| {});
        walk::scope(&mut graph, root, scope);
        let graph = graph.colored();
        let outer = std::mem::replace(&mut self.search.remaining, SEARCH_NODE_CAP);
        let outer_visited = std::mem::take(&mut self.visited);
        let mut best = None;
        let mut cut_short = false;
        let colors = graph.initial.clone();
        // A refinement that leaves no cell to split has one leaf, whose labels are the labeling: no write of the scope is compared.
        let mut refined = colors.clone();
        graph.refine(&mut refined);
        if graph.target_cell(&refined).is_none() {
            self.search.remaining = outer;
            self.visited = outer_visited;
            return (vec![graph.leaf_labels(&refined)], false);
        }
        self.visit(&graph, colors, scope, &mut best, &mut cut_short);
        self.search.remaining = outer;
        crate::eval::ambient::note_labeling(self.visited);
        self.visited = outer_visited;
        self.search.reached |= cut_short;
        if cut_short {
            self.names.labeling_bound_reached();
        }
        (best.expect("the search reaches a leaf").1, cut_short)
    }

    /// One node of the search: refines `colors`, then individualizes each
    /// label of the first largest cell of labels that is not a singleton, or,
    /// at a leaf, keeps the least form with each labeling that gives it, the
    /// first found first. Where the budget is spent, the search sets
    /// `cut_short` and goes on to its first leaf alone. The labeling it ends
    /// with then is no canonical labeling, and the caller refuses the form
    /// ([`LabelingBound`]).
    fn visit(&mut self, graph: &ColoredGraph, mut colors: Vec<u32>, scope: LabelScope, best: &mut Option<(Vec<u8>, Vec<Labels>)>, cut_short: &mut bool) {
        self.visited = self.visited.saturating_add(1);
        if self.search.remaining == 0 {
            *cut_short = true;
            if best.is_some() {
                return;
            }
        } else {
            self.search.remaining -= 1;
        }
        graph.refine(&mut colors);
        let Some(cell) = graph.target_cell(&colors) else {
            let labels = graph.leaf_labels(&colors);
            let order = self.order.take();
            let mut out = CanonicalWriter::default();
            self.with_labels(labels.clone(), |cx| scope.write(cx, &mut out));
            self.order = order;
            match best {
                Some((form, labelings)) if out.bytes == *form => labelings.push(labels),
                Some((form, _)) if out.bytes > *form => {}
                _ => *best = Some((out.bytes, vec![labels])),
            }
            return;
        };
        for vertex in cell {
            let mut split = colors.clone();
            let color = colors[vertex];
            for c in split.iter_mut() {
                if *c >= color {
                    *c += 1;
                }
            }
            split[vertex] = color;
            self.visit(graph, split, scope, best, cut_short);
            if *cut_short && best.is_some() {
                return;
            }
        }
    }
}
