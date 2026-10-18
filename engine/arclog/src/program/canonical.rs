//! The canonical form of a node and its hash.
//!
//! A body's canonical form is the same under a reorder of its atoms, a
//! reorder of the branches of an `OR`, and a renaming of its labels, apart
//! from the renaming that [`canonical_hash`] gives. The labeling comes from
//! individualization–refinement: color refinement with the column paths as
//! edge labels, then the first largest cell that is not a singleton, with a
//! cap of [`SEARCH_NODE_CAP`] search nodes on the search of each label
//! scope. A body that reaches the cap takes the least labeling the search
//! has found.
//!
//! A node's canonical hash names each relation it reads as the file writes
//! it, [`AsWritten`]. The resolved content of a node in one case program, in
//! which each derived relation stands for its own content, is
//! [`crate::resolver::ResolvedProgram::content`], which writes the same
//! canonical form through a [`NameWriter`] of the resolver.
//!
//! The byte encoding of a form is in `form`, and the graph of a label scope
//! with its color refinement in `graph`. This module holds the search over
//! that graph and the canonical order of a form. Each module writes a column
//! path through the [`NameWriter`] of the write, so the edge labels of the
//! graph and the bytes of the form name each column alike.

mod form;
mod graph;

use super::path::{child_index, NodePath, NodeRef, PathStep};
use super::*;
use crate::hash::StableHashMap;
use form::*;
use graph::*;

pub use form::{canonical_hash, AsWritten, Canonical, CanonicalForm, CanonicalWriter, NameWriter};
pub(in crate::program) use form::form_of;

/// The provisional cap on the search nodes of individualization–refinement,
/// for the search of each label scope.
///
/// The cap guards synthesized bodies, whose symmetry the corpus does not
/// show. The corpus's search reaches at most 13 nodes.
pub const SEARCH_NODE_CAP: u32 = 1000;

/// The search nodes that the search of the label scope in progress has
/// left, and whether the search of any scope of the value reached the cap.
/// Each scope's search starts with [`SEARCH_NODE_CAP`] nodes, and a search
/// that runs inside a leaf of another spends none of that other's nodes.
#[derive(Clone, Debug)]
pub struct SearchBudget {
    pub remaining: u32,
    /// Set when the search of a scope reached the cap, which is an alert.
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

/// The canonical labeling of one scope: for each label of the scope, its
/// position in the canonical form.
#[derive(Clone, Debug)]
pub struct CanonicalLabeling {
    pub positions: Box<[(super::LabelId, u32)]>,
    /// Whether the search reached [`SEARCH_NODE_CAP`], so that the labeling
    /// is the least one the search found.
    pub reached_cap: bool,
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
/// resolved content. It takes a scope in place of one body, since a body
/// alone does not give the labels of the scope's head sites.
pub fn canonical_labeling(scope: LabelScope, names: &dyn NameWriter, search: &mut SearchBudget) -> CanonicalLabeling {
    let mut cx = Context::new(search, names);
    let (labels, reached_cap) = cx.labeling(scope);
    CanonicalLabeling { positions: by_position(&labels), reached_cap }
}

/// The canonical order of one form: for each list of the form, the source
/// index at each canonical position, and for each label, its canonical
/// position. A result cached by canonical hash is held in canonical order
/// and served to each form of equal content through its own order, so the
/// cases that share a form share its check.
///
/// The labels are held for each label scope within the form, by the source
/// path of that scope's form relative to the form: the empty path for the
/// form's own scope, a `DEMONSTRATED` form's key clause and inputs among
/// them, the path of each form of a claim or an `ALT`, and the path of each
/// `DEMO_RULE` form.
#[derive(Clone, Debug)]
pub struct CanonicalOrder {
    lists: crate::hash::StableHashMap<super::path::NodePath, Box<[u32]>>,
    labels: crate::hash::StableHashMap<super::path::NodePath, Box<[(super::LabelId, u32)]>>,
}

/// The orders a write records for [`CanonicalOrder`]: each sorted list's,
/// and each scope's labels, by source path.
#[derive(Default)]
struct Recorded {
    lists: StableHashMap<NodePath, Box<[u32]>>,
    labels: StableHashMap<NodePath, Box<[(LabelId, u32)]>>,
}

impl CanonicalOrder {
    /// The canonical order of `form`.
    pub fn of(form: &super::Form, search: &mut SearchBudget) -> Self {
        let mut cx = Context::new(search, &AsWritten);
        cx.order = Some(Recorded::default());
        form_root(&mut cx, &mut CanonicalWriter::default(), form);
        let recorded = cx.order.take().expect("the order is recorded");
        CanonicalOrder { lists: recorded.lists, labels: recorded.labels }
    }

    /// The source path of the node at `canonical`, a path in canonical
    /// order, relative to the form.
    pub fn source_path(&self, canonical: &super::path::NodePath) -> super::path::NodePath {
        let mut source: Vec<PathStep> = Vec::with_capacity(canonical.0.len());
        for step in canonical.0.iter() {
            let mapped = match self.lists.get(&NodePath(source.clone().into())) {
                Some(order) => PathStep(*order.get(step.0 as usize).expect("a canonical path names a member of each list")),
                None => *step,
            };
            source.push(mapped);
        }
        NodePath(source.into())
    }

    /// The canonical path of the node at `source`, a path in source order,
    /// relative to the form.
    pub fn canonical_path(&self, source: &super::path::NodePath) -> super::path::NodePath {
        let mut canonical = Vec::with_capacity(source.0.len());
        for (depth, step) in source.0.iter().enumerate() {
            let mapped = match self.lists.get(&NodePath(source.0[..depth].into())) {
                Some(order) => {
                    let position = order.iter().position(|&index| index == step.0);
                    PathStep(position.expect("a source path names a member of each list") as u32)
                }
                None => *step,
            };
            canonical.push(mapped);
        }
        NodePath(canonical.into())
    }

    /// The label at canonical `position` of the scope whose form stands at
    /// `scope`, a source path relative to the form.
    pub fn source_label(&self, scope: &super::path::NodePath, position: u32) -> super::LabelId {
        let found = self.scope_labels(scope).iter().find(|(_, p)| *p == position);
        found.expect("a canonical position of a label of the scope").0
    }

    /// The canonical position of `label` of the scope whose form stands at
    /// `scope`, a source path relative to the form.
    pub fn canonical_label(&self, scope: &super::path::NodePath, label: super::LabelId) -> u32 {
        let found = self.scope_labels(scope).iter().find(|(l, _)| *l == label);
        found.expect("a label of the scope").1
    }

    fn scope_labels(&self, scope: &NodePath) -> &[(LabelId, u32)] {
        self.labels.get(scope).expect("the path of a label scope of the form")
    }
}

/// Each label's canonical position.
type Labels = StableHashMap<LabelId, u32>;

fn by_position(labels: &Labels) -> Box<[(LabelId, u32)]> {
    let mut positions: Vec<(LabelId, u32)> = labels.iter().map(|(l, p)| (*l, *p)).collect();
    positions.sort_by_key(|(_, p)| *p);
    positions.into()
}

/// The state of one write: the labels of the scope being written, the
/// search budget, the name writer, and, for [`CanonicalOrder`], the source
/// path of the node being written, relative to the form, and the orders
/// recorded.
struct Context<'a> {
    labels: Labels,
    search: &'a mut SearchBudget,
    names: &'a dyn NameWriter,
    path: Vec<PathStep>,
    order: Option<Recorded>,
}

impl<'a> Context<'a> {
    fn new(search: &'a mut SearchBudget, names: &'a dyn NameWriter) -> Self {
        Context { labels: Labels::default(), search, names, path: Vec::new(), order: None }
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
        let step = || child_index(parent, child).expect("the children of the node being written hold each child the form writer writes");
        self.at_step(step, write)
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

    /// Writes `members`, each through `write` as the child at its index,
    /// sorted by the bytes of their forms, and records their order.
    fn sorted<T>(&mut self, out: &mut CanonicalWriter, members: &[T], write: impl Fn(&mut Self, &mut CanonicalWriter, &T)) {
        let mut forms: Vec<(Vec<u8>, u32)> = members
            .iter()
            .enumerate()
            .map(|(index, member)| {
                let mut own = CanonicalWriter::default();
                self.at_step(|| index as u32, |cx| write(cx, &mut own, member));
                (own.bytes, index as u32)
            })
            .collect();
        forms.sort();
        if let Some(order) = &mut self.order {
            order.lists.insert(NodePath(self.path.clone().into()), forms.iter().map(|(_, index)| *index).collect());
        }
        out.len(forms.len());
        for (bytes, _) in &forms {
            out.nested(bytes);
        }
    }

    /// Writes `columns` in the order of their labels' canonical positions,
    /// each name through `name`.
    fn columns(&self, out: &mut CanonicalWriter, columns: &[RelationColumn], name: impl Fn(&mut CanonicalWriter, &ColumnName)) {
        let mut ordered: Vec<(u32, &ColumnName)> = columns.iter().map(|c| (self.position(c.label), &c.name)).collect();
        ordered.sort_by_key(|(position, _)| *position);
        out.len(ordered.len());
        for (position, column) in ordered {
            name(out, column);
            out.int(position);
        }
    }

    /// Runs `write` with the labels of `scope`.
    fn in_scope(&mut self, scope: LabelScope, write: impl FnOnce(&mut Self)) {
        let labels = self.labeling(scope).0;
        self.with_labels(labels, write);
    }

    /// Runs `write` with `labels`, the labels of the scope whose form stands
    /// at the node being written, and records them.
    fn with_labels(&mut self, labels: Labels, write: impl FnOnce(&mut Self)) {
        if let Some(order) = &mut self.order {
            order.labels.insert(NodePath(self.path.clone().into()), by_position(&labels));
        }
        let outer = std::mem::replace(&mut self.labels, labels);
        write(self);
        self.labels = outer;
    }

    /// The canonical labeling of `scope`, and whether its search reached
    /// the cap.
    fn labeling(&mut self, scope: LabelScope) -> (Labels, bool) {
        let mut graph = GraphBuilder::new(self.names);
        let root = graph.vertex(Tag::Root, |_| {});
        scope.graph(&mut graph, root);
        let graph = graph.colored();
        let outer = std::mem::replace(&mut self.search.remaining, SEARCH_NODE_CAP);
        let mut best = None;
        let mut cut_short = false;
        let colors = graph.initial.clone();
        self.visit(&graph, colors, scope, &mut best, &mut cut_short);
        self.search.remaining = outer;
        self.search.reached |= cut_short;
        (best.expect("the search reaches a leaf").1, cut_short)
    }

    /// One node of the search: refines `colors`, then individualizes each
    /// label of the first largest cell of labels that is not a singleton, or,
    /// at a leaf, keeps the least form. Where the budget is spent, the search
    /// sets `cut_short` and goes on to its first leaf alone.
    fn visit(&mut self, graph: &ColoredGraph, mut colors: Vec<u32>, scope: LabelScope, best: &mut Option<(Vec<u8>, Labels)>, cut_short: &mut bool) {
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
            if best.as_ref().is_none_or(|(form, _)| out.bytes < *form) {
                *best = Some((out.bytes, labels));
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
