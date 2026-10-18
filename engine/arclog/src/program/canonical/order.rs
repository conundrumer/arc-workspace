//! The canonical order of a form, which a write of the form records, and
//! the mapping of paths and labels between the form's source order and its
//! canonical order.

use super::super::path::{NodePath, PathStep};
use super::super::{Form, LabelId};
use super::{form_root, AsWritten, CanonicalForm, CanonicalWriter, Context, SearchBudget};
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
}

/// The orders a write records for [`CanonicalOrder`]: each sorted list's,
/// and each scope's labels, by source path.
#[derive(Default)]
pub(super) struct Recorded {
    pub(super) lists: StableHashMap<NodePath, Box<[u32]>>,
    pub(super) labels: StableHashMap<NodePath, Box<[(LabelId, u32)]>>,
}

impl CanonicalOrder {
    /// The canonical order of `form`.
    pub fn of(form: &Form, search: &mut SearchBudget) -> Self {
        Self::with_form(form, search).0
    }

    /// The canonical order of `form` and its canonical form under
    /// [`AsWritten`], from one write of `form`.
    pub fn with_form(form: &Form, search: &mut SearchBudget) -> (Self, CanonicalForm) {
        let mut cx = Context::new(search, &AsWritten);
        cx.order = Some(Recorded::default());
        let mut out = CanonicalWriter::default();
        form_root(&mut cx, &mut out, form);
        let recorded = cx.order.take().expect("the order is recorded");
        (CanonicalOrder { lists: recorded.lists, labels: recorded.labels }, out.finish())
    }

    /// The source path of the node at `canonical`, a path in canonical
    /// order, relative to the form.
    pub fn source_path(&self, canonical: &NodePath) -> NodePath {
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
    pub fn canonical_path(&self, source: &NodePath) -> NodePath {
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

    /// Each label scope within the form, as the source path of its form
    /// relative to the form, with its labels and their canonical positions,
    /// in the order of the scopes' canonical paths.
    pub fn label_scopes(&self) -> Vec<(NodePath, &[(LabelId, u32)])> {
        let mut scopes: Vec<(NodePath, NodePath, &[(LabelId, u32)])> =
            self.labels.iter().map(|(source, labels)| (self.canonical_path(source), source.clone(), &labels[..])).collect();
        scopes.sort_by(|(a, _, _), (b, _, _)| a.cmp(b));
        scopes.into_iter().map(|(_, source, labels)| (source, labels)).collect()
    }

    fn scope_labels(&self, scope: &NodePath) -> &[(LabelId, u32)] {
        self.labels.get(scope).expect("the path of a label scope of the form")
    }
}
