//! The check of the labels that `=` makes and that an `OR` or an `IF` exports.

use super::safety::{each_head_use, form_bodies, FormBody};
use crate::safety::{each_label_use_at, list_of, parts_of};
use super::types::result;
use super::{Check, CheckId, CheckInput, CheckResult, Prefix, PrefixResult, Refusal};
use crate::hash::StableHashSet;
use crate::program::canonical::{CanonicalOrder, SearchBudget};
use crate::program::path::{NodePath, NodeRef};
use crate::program::{Body, Conjunct, Form, LabelId, LabelUse, Negated};
use crate::read::columns::exports;

/// [`CheckId::MadeAndExportedLabels`].
pub struct MadeAndExportedLabelsCheck;

impl Check for MadeAndExportedLabelsCheck {
    fn id(&self) -> CheckId {
        CheckId::MadeAndExportedLabels
    }

    /// Refuses, in each body of the form:
    ///
    /// - a label that a site or a `=` reads outside each list that keeps it,
    ///   as `crate::read::columns::exports` gives the labels a list keeps,
    ///   and outside the labels its context gives the body: a label local
    ///   to an `OR` branch, an `IF` or an `ALL`, read outside it. A later
    ///   branch of an `OR` may name a label of the first branch, and an
    ///   `IF`'s else a label of its then;
    /// - a label made at a site of a `NOT` atom, where every site joins
    ///   (`docs/arclog/arclog.md#negation-and-constraints`);
    /// - a `^` label that the key body's own list does not keep, so that no
    ///   atom at the key body's top level binds the key's column.
    fn check(&self, input: &CheckInput<'_>) -> CheckResult {
        let refused = body_refusals(input.form, &|_| true);
        if refused.is_empty() {
            return CheckResult::Pass;
        }
        let order = CanonicalOrder::of(input.form, &mut SearchBudget::new());
        result(refused.into_iter().map(|refusal| Refusal { at: order.canonical_path(&refusal.at), ..refusal }).collect())
    }

    /// The refusals of each complete body of the partial form, since a node
    /// written later in an open body may make or export the label it reads.
    fn check_prefix(&self, prefix: &Prefix<'_>) -> PrefixResult {
        super::prefix::refused(body_refusals(prefix.partial, &|body| !prefix.is_open(&body.at)))
    }
}

/// The refusals of each body of `form` that `checked` keeps, each at its
/// source path.
fn body_refusals(form: &Form, checked: &dyn Fn(&FormBody<'_>) -> bool) -> Vec<Refusal> {
    let mut refused: Vec<(&'static str, NodePath)> = Vec::new();
    for form_body in form_bodies(form).iter().filter(|body| checked(body)) {
        refusals(form_body, &mut refused);
    }
    refused.into_iter().map(|(message, at)| Refusal { message: message.into(), at }).collect()
}

/// The labels the list `body` keeps, each that a site or a `=` of its own
/// list makes and each that an `OR` or an `IF` of it exports.
fn kept(body: &Body) -> Vec<LabelId> {
    let mut out = Vec::new();
    exports(body, &[], &mut out);
    out
}

/// Pushes onto `refused` each refusal of `form_body`.
fn refusals(form_body: &FormBody<'_>, refused: &mut Vec<(&'static str, NodePath)>) {
    let top = kept(form_body.body.value());
    let visible: StableHashSet<LabelId> = form_body.given.iter().chain(&form_body.columns).chain(&form_body.fields).chain(&top).copied().collect();
    list(&list_of(form_body.body.value(), &form_body.at), &visible, refused);
    each_label_use_at(NodeRef::Body(form_body.body.value()), &form_body.at, &mut |at, use_| {
        if let LabelUse::Key(label) = use_ {
            if !top.contains(&label) {
                refused.push(("the key label is local to a form of the key body, so no atom at the key body's top level binds it", at.clone()));
            }
        }
    });
    if let Some((input, at)) = form_body.head() {
        each_head_use(input, at, &mut |at, use_| {
            if let LabelUse::Join(label) = use_ {
                read(&visible, label, at, refused);
            }
        });
    }
}

/// Pushes onto `refused` each read in `list` of a label that `visible`
/// does not hold, and each label made at a site of a `NOT` atom, and so for
/// the parts of each form of `list`, each part with the labels it keeps.
fn list(list: &[(NodePath, &Conjunct)], visible: &StableHashSet<LabelId>, refused: &mut Vec<(&'static str, NodePath)>) {
    each_list(list, visible, &[], &mut |list, visible, _| {
        for (at, conjunct) in list {
            match conjunct {
                Conjunct::Atom(_) | Conjunct::Constraint(_) => each_label_use_at(NodeRef::Conjunct(conjunct), at, &mut |at, use_| {
                    if let LabelUse::Join(label) = use_ {
                        read(visible, label, at, refused);
                    }
                }),
                Conjunct::Not(Negated::Atom(_)) => each_label_use_at(NodeRef::Conjunct(conjunct), at, &mut |at, use_| match use_ {
                    LabelUse::Fresh(_) | LabelUse::Key(_) => refused.push(("a site of a `NOT` atom makes the label, where every site of the atom joins", at.clone())),
                    LabelUse::Join(label) => read(visible, label, at, refused),
                    LabelUse::Zero => {}
                }),
                Conjunct::Not(Negated::Form(_)) | Conjunct::All { .. } | Conjunct::Or(_) | Conjunct::If { .. } => {}
            }
        }
    });
}

/// Visits `list` with `visible`, the labels visible in it, and `named`,
/// the labels of an `OR`'s first branch or an `IF`'s then that it may
/// name, then each part of each form of `list`, as
/// [`crate::safety::parts_of`] gives the parts, in the same way: each part
/// with the labels visible in `list`, those it keeps, and the labels of the
/// form's first branch or then, which a later branch or the else may name,
/// as `docs/arclog/arclog.md#disjunction` gives.
pub(super) fn each_list(
    list: &[(NodePath, &Conjunct)],
    visible: &StableHashSet<LabelId>,
    named: &[LabelId],
    visit: &mut dyn FnMut(&[(NodePath, &Conjunct)], &StableHashSet<LabelId>, &[LabelId]),
) {
    visit(list, visible, named);
    for (at, conjunct) in list {
        let named = match conjunct {
            Conjunct::Or(branches) => kept(branches[0].value()),
            Conjunct::If { then, .. } => kept(then.value()),
            Conjunct::Atom(_) | Conjunct::Not(_) | Conjunct::Constraint(_) | Conjunct::All { .. } => Vec::new(),
        };
        for part in parts_of(conjunct, at) {
            let mut inner = visible.clone();
            inner.extend(named.iter().copied());
            part_kept(&part, &mut inner);
            each_list(&part, &inner, &named, visit);
        }
    }
}

/// Pushes onto `refused` a refusal of the read of `label` at `at` where
/// `visible` does not hold it.
fn read(visible: &StableHashSet<LabelId>, label: LabelId, at: &NodePath, refused: &mut Vec<(&'static str, NodePath)>) {
    if !visible.contains(&label) {
        refused.push(("the label is read outside each list that keeps it", at.clone()));
    }
}

/// Adds to `visible` the labels that the conjuncts of `part` keep, as one
/// list.
fn part_kept(part: &[(NodePath, &Conjunct)], visible: &mut StableHashSet<LabelId>) {
    let body = Body { conjuncts: part.iter().map(|(_, conjunct)| (*conjunct).clone()).collect() };
    visible.extend(kept(&body));
}
