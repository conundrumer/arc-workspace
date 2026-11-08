//! The canonical order of a form, which a write of the form records, and
//! the mapping of paths and labels between the form's source order and its
//! canonical order.

use super::super::path::{NodePath, NodeRef, PathStep};
use super::super::{Form, LabelId};
use super::{form_root, AsWritten, CanonicalForm, CanonicalWriter, Context, NameWriter, SearchBudget};
use crate::hash::StableHashMap;

/// The canonical order of one form: for each list of the form, the source
/// index at each canonical position, and for each label, its canonical
/// position. A result cached by canonical hash is held in canonical order
/// and served to each form of equal content through its own order, so the
/// cases that share a form share its check.
///
/// The labels are held for each label scope within the form, as
/// [`LabelId`] gives a scope, by the source path of that scope's form
/// relative to the form.
#[derive(Clone, Debug)]
pub struct CanonicalOrder {
    lists: StableHashMap<NodePath, Box<[u32]>>,
    labels: StableHashMap<NodePath, Box<[(LabelId, u32)]>>,
    /// For each label scope, by the source path of its form, the other
    /// labelings that its search found whose form is the canonical form.
    symmetries: StableHashMap<NodePath, Box<[Box<[(LabelId, u32)]>]>>,
    /// Whether a list of the form holds a member that repeats an earlier one.
    repeats: bool,
}

/// The write of `form` under [`AsWritten`] that its node keeps, made on the
/// first call for the node.
fn written(form: &Form) -> &(CanonicalOrder, CanonicalForm, bool) {
    crate::eval::once_noted(&super::form::cache(form).order, || write_order(form, &AsWritten, false))
}

/// Both policies use the same walk, labeling search and path recording.
/// Feature writes are never stored in the production form cache.
fn write_order(form: &Form, names: &dyn NameWriter, feature_sites: bool) -> (CanonicalOrder, CanonicalForm, bool) {
    let mut own = SearchBudget::new();
    let mut cx = Context::new(&mut own, names);
    cx.feature_sites = feature_sites;
    cx.order = Some(Recorded::default());
    let mut out = CanonicalWriter::default();
    form_root(&mut cx, &mut out, form);
    let recorded = cx.order.take().expect("the order is recorded");
    (CanonicalOrder { lists: recorded.lists, labels: recorded.labels, symmetries: recorded.symmetries, repeats: recorded.repeats }, out.finish(), own.reached)
}

/// The orders a write records for [`CanonicalOrder`]: each sorted list's,
/// and each scope's labels, by source path, and the other labelings that the
/// search of each scope found.
#[derive(Default)]
pub(super) struct Recorded {
    pub(super) lists: StableHashMap<NodePath, Box<[u32]>>,
    /// Whether a list holds a member that repeats an earlier one, which the canonical form does not write.
    pub(super) repeats: bool,
    pub(super) labels: StableHashMap<NodePath, Box<[(LabelId, u32)]>>,
    pub(super) symmetries: StableHashMap<NodePath, Box<[Box<[(LabelId, u32)]>]>>,
}

impl CanonicalOrder {
    /// Whether a list of the form holds a member that repeats an earlier one.
    /// The canonical form does not write such a member, so it stands for forms
    /// with other counts of it, whose lists differ in length.
    pub fn repeats(&self) -> bool {
        self.repeats
    }

    /// The canonical order of `form`, which the node of `form` keeps.
    pub fn of<'f>(form: &'f Form, search: &mut SearchBudget) -> &'f Self {
        Self::with_form(form, search).0
    }

    /// The canonical order of `form` and its canonical form under
    /// [`AsWritten`], from one write of `form`.
    ///
    /// The write runs on the first call for the node of `form`, which
    /// caches its result; a search of each label scope starts with
    /// [`super::SEARCH_NODE_CAP`] nodes whatever `search` holds, so the
    /// result reads nothing of `search`, and sets its `reached` where a
    /// search reached the cap.
    pub fn with_form<'f>(form: &'f Form, search: &mut SearchBudget) -> (&'f Self, &'f CanonicalForm) {
        let (order, canonical, reached) = written(form);
        search.reached |= *reached;
        (order, canonical)
    }

    /// The canonical form of `form`, as [`CanonicalOrder::with_form`] gives
    /// it, followed by the source index of each child of each node of
    /// `form`, each node's children in canonical order, so that two forms of
    /// one canonical form are equal under it only where their lists are
    /// written in one order. The node of `form` keeps it from the first
    /// call.
    pub fn with_written_lists(form: &Form) -> CanonicalForm {
        fn write(node: NodeRef<'_>, at: &NodePath, order: &CanonicalOrder, out: &mut CanonicalWriter) {
            let children = node.children();
            for position in 0..children.len() as u32 {
                let child = at.child(position);
                let index = order.source_path(&child).0.last().expect("a child's path ends in its step").0;
                out.write(&index.to_le_bytes());
                write(children[index as usize], &child, order, out);
            }
        }
        let kept = crate::eval::once_noted(&super::form::cache(form).written_lists, || {
            let (order, canonical, _) = written(form);
            let mut out = CanonicalWriter::default();
            out.write(&canonical.bytes);
            write(NodeRef::from(form), &NodePath::default(), order, &mut out);
            out.finish()
        });
        kept.clone()
    }

    /// The canonical order of `form` and its canonical form through `names`,
    /// from one write of `form`, made on each call and kept nowhere: the
    /// orders of its sorted lists and the positions of its labels as the
    /// content that `names` writes gives them, which the order under
    /// [`AsWritten`] does not, since the names a form reads stand in them.
    /// [`CanonicalOrder::with_form`] gives the order under [`AsWritten`]. The
    /// write has the order of the named sites and the head sites outside the
    /// form where `names` says so ([`NameWriter::feature_sites`]), as the
    /// content that `names` writes does, so the order and the content name the
    /// lists and labels alike.
    pub fn with_names(form: &Form, names: &dyn NameWriter, search: &mut SearchBudget) -> (Self, CanonicalForm) {
        let (order, canonical, reached) = write_order(form, names, names.feature_sites());
        search.reached |= reached;
        (order, canonical)
    }

    /// An independent feature write that normalizes named site order. This
    /// never reads or writes the form's production canonical-order cache:
    /// those labels also define callable relation column order.
    pub fn for_features(form: &Form, search: &mut SearchBudget) -> (Self, CanonicalForm) {
        let (order, canonical, reached) = write_order(form, &AsWritten, true);
        search.reached |= reached;
        (order, canonical)
    }

    /// The labels of the scope of `form`, in the order of their canonical
    /// positions under [`AsWritten`], from the one write of `form` that
    /// [`CanonicalOrder::with_form`] keeps; none where `form` is no scope.
    pub(in super::super) fn root_labels(form: &Form) -> Box<[LabelId]> {
        if super::form::form_scope(form).is_none() {
            return Box::default();
        }
        written(form).0.scope_labels(&NodePath::default()).iter().map(|(label, _)| *label).collect()
    }

    /// The canonical path of the node at `source`, as
    /// [`CanonicalOrder::canonical_path`] gives it, and `None` where a step
    /// of `source` names no member of its list.
    pub fn try_canonical_path(&self, source: &NodePath) -> Option<NodePath> {
        let mut canonical = Vec::with_capacity(source.0.len());
        for (depth, step) in source.0.iter().enumerate() {
            let mapped = match self.lists.get(&source.0[..depth]) {
                Some(order) => PathStep(order.iter().position(|&index| index == step.0)? as u32),
                None => *step,
            };
            canonical.push(mapped);
        }
        Some(NodePath(canonical.into()))
    }

    /// The labels of the scope whose form stands at `scope`, a source path
    /// relative to the form, each with its canonical position, and `None`
    /// where the form holds no such scope.
    pub fn labels_of(&self, scope: &NodePath) -> Option<&[(LabelId, u32)]> {
        self.labels.get(scope).map(|labels| &labels[..])
    }

    /// The canonical position of `label` of the scope whose form stands at
    /// `scope`, a source path relative to the form, and `None` where the
    /// form holds no such scope or the scope no such label.
    pub fn label_position(&self, scope: &NodePath, label: LabelId) -> Option<u32> {
        self.labels.get(scope)?.iter().find(|(l, _)| *l == label).map(|(_, position)| *position)
    }

    /// The source path of the node at `canonical`, a path in canonical
    /// order, relative to the form.
    pub fn source_path(&self, canonical: &NodePath) -> NodePath {
        let mut source: Vec<PathStep> = Vec::with_capacity(canonical.0.len());
        for step in canonical.0.iter() {
            let mapped = match self.lists.get(&source[..]) {
                Some(order) => PathStep(*order.get(step.0 as usize).expect("a canonical path names a member of each list")),
                None => *step,
            };
            source.push(mapped);
        }
        NodePath(source.into())
    }

    /// The canonical path of the node at `source`, a path in source order,
    /// relative to the form.
    pub fn canonical_path(&self, source: &NodePath) -> NodePath {
        let mut canonical = Vec::with_capacity(source.0.len());
        for (depth, step) in source.0.iter().enumerate() {
            let mapped = match self.lists.get(&source.0[..depth]) {
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
    pub fn source_label(&self, scope: &NodePath, position: u32) -> LabelId {
        let found = self.scope_labels(scope).iter().find(|(_, p)| *p == position);
        found.expect("a canonical position of a label of the scope").0
    }

    /// The canonical position of `label` of the scope whose form stands at
    /// `scope`, a source path relative to the form.
    pub fn canonical_label(&self, scope: &NodePath, label: LabelId) -> u32 {
        let found = self.scope_labels(scope).iter().find(|(l, _)| *l == label);
        found.expect("a label of the scope").1
    }

    /// Each sorted list of the form, by the source path of the node whose
    /// children it orders, with the canonical position of each member of
    /// the list, indexed by the member's source index.
    pub fn list_positions(&self) -> Vec<(NodePath, Vec<u32>)> {
        self.lists
            .iter()
            .map(|(source, order)| {
                let mut positions = vec![0; order.len()];
                for (position, &index) in order.iter().enumerate() {
                    positions[index as usize] = position as u32;
                }
                (source.clone(), positions)
            })
            .collect()
    }

    /// Each label scope within the form, as the source path of its form
    /// relative to the form, with its labels and their canonical positions,
    /// in the order of the scopes' canonical paths.
    pub fn label_scopes(&self) -> Vec<(NodePath, &[(LabelId, u32)])> {
        let mut scopes: Vec<(NodePath, NodePath, &[(LabelId, u32)])> =
            self.labels.iter().map(|(source, labels)| (self.canonical_path(source), source.clone(), &labels[..])).collect();
        scopes.sort_by(|(a, _, _), (b, _, _)| a.cmp(b));
        scopes.into_iter().map(|(_, source, labels)| (source, labels)).collect()
    }

    /// The permutations of the canonical positions of the labels of the scope
    /// whose form stands at `scope`, a source path relative to the form, under
    /// which the form is the same: one for each other labeling that the
    /// scope's search found whose form is the canonical form, other than the
    /// identity. A permutation `p` has `p[a] = b` where a label has position
    /// `a` in the canonical labeling and `b` in the other. The permutations
    /// are those of the search; where it reached its cap ([`super::SEARCH_NODE_CAP`])
    /// they may not hold every symmetry of the scope. Empty where the form
    /// holds no such scope.
    pub fn label_permutations(&self, scope: &NodePath) -> Vec<Vec<u32>> {
        let (Some(canonical), Some(others)) = (self.labels.get(scope), self.symmetries.get(scope)) else { return Vec::new() };
        let mut found: Vec<Vec<u32>> = Vec::new();
        for other in others.iter() {
            let mut permutation = vec![0; canonical.len()];
            for (label, position) in canonical.iter() {
                let Some((_, moved)) = other.iter().find(|(found, _)| found == label) else { continue };
                permutation[*position as usize] = *moved;
            }
            let identity = permutation.iter().enumerate().all(|(at, to)| *to as usize == at);
            if !identity && !found.contains(&permutation) {
                found.push(permutation);
            }
        }
        found.sort();
        found
    }

    fn scope_labels(&self, scope: &NodePath) -> &[(LabelId, u32)] {
        self.labels.get(scope).expect("the path of a label scope of the form")
    }
}
