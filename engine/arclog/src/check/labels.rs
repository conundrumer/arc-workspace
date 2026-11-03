//! The check of the labels that `=` makes and that an `OR` or an `IF` exports.

use super::safety::{each_head_use, form_bodies, FormBody};
use crate::safety::{each_label_use_at, list_of, parts_of};
use super::types::result;
use super::{Check, CheckId, CheckInput, CheckResult, Prefix, PrefixResult, Refusal, CheckCacheKey, KeyInput};
use crate::hash::StableHashSet;
use crate::program::canonical::{CanonicalOrder, SearchBudget};
use crate::program::path::{NodePath, NodeRef};
use crate::program::{Body, Conjunct, Constraint, ConstraintOp, Form, LabelId, LabelUse, Negated};
use crate::read::columns::exports;

/// [`CheckId::MadeAndExportedLabels`].
pub struct MadeAndExportedLabelsCheck;

impl Check for MadeAndExportedLabelsCheck {
    fn id(&self) -> CheckId {
        CheckId::MadeAndExportedLabels
    }

    fn cache_key(&self, at: &KeyInput<'_>) -> Option<CheckCacheKey> {
        Some(at.base(self.id()))
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
    ///   atom at the key body's top level binds the key's column;
    /// - a `(= *X Y)` or `(= *X 0)` in a later branch of an `OR`, in the
    ///   test or the else of an `IF`, or in a list of an `ALL`, and one in
    ///   the first branch of an `OR` or the then of an `IF` whose label `X`
    ///   the form does not export, as
    ///   `docs/arclog/arclog.md#negation-and-constraints` gives. A union
    ///   `OR`, a body's one conjunct, exports by the same rule.
    fn check(&self, input: &CheckInput<'_>) -> CheckResult {
        let refused = body_refusals(input.form, &|_| true, &|_| false);
        if refused.is_empty() {
            return CheckResult::Pass;
        }
        let order = CanonicalOrder::of(input.form, &mut SearchBudget::new());
        result(refused.into_iter().map(|refusal| Refusal { at: order.canonical_path(&refusal.at), ..refusal }).collect())
    }

    /// The refusals of each complete body of the partial form, since a node
    /// written later in an open body may make or export the label it reads;
    /// and, of the refusals of `=`, each at a node that is complete, since
    /// a later branch of an `OR` may yet name the label of a `=` in its
    /// first branch. In an open body of an `INIT` form, a `^` label that a
    /// form of the body holds and can no longer export is refused as well,
    /// as [`local_key_labels`] gives.
    fn check_prefix(&self, prefix: &Prefix<'_>) -> PrefixResult {
        let mut refused = body_refusals(prefix.partial, &|body| !prefix.is_open(&body.at), &|at| prefix.is_open(at));
        if let Form::Instance(_) = prefix.partial {
            for form_body in form_bodies(prefix.partial).iter().filter(|body| prefix.is_open(&body.at)) {
                refused.extend(local_key_labels(form_body, &|at| prefix.is_open(at)));
            }
        }
        super::prefix::refused(refused)
    }
}

/// The refusal of each `^` label of `form_body`, an open body, that a form
/// of the body holds and no completion of the body exports from it, so that
/// the body's own list keeps it in no completion: a label that is local to
/// a form of the key body. `open` holds the paths of the open nodes.
///
/// The `^` is the label's one making use, so only the forms that hold it
/// can bring it to the body's list, each through the form around it, and a
/// form exports only a label that its first branch or its then keeps. The
/// label is local where it stands in a `NOT` or an `ALL`, in a later branch
/// of an `OR`, or in the test or the else of an `IF`, or where it stands in
/// the first branch of an `OR` that a later branch does not name, or in the
/// then of an `IF` whose else does not name it, that branch or else being
/// complete and not empty.
fn local_key_labels(form_body: &FormBody<'_>, open: &dyn Fn(&NodePath) -> bool) -> Vec<Refusal> {
    let mut refused = Vec::new();
    each_label_use_at(NodeRef::Body(form_body.body.value()), &form_body.at, &mut |at, use_| {
        if let LabelUse::Key(label) = use_ {
            if held_local(form_body.body.value(), &form_body.at, at, label, open) {
                refused.push(Refusal { message: "the key label is local to a form of the key body, so no atom at the key body's top level binds it".into(), at: at.clone() });
            }
        }
    });
    refused
}

/// Whether the form of `list`, at `list_at`, that holds the node at `at`,
/// or a form inside it, holds `label` there and exports it in no
/// completion, as [`local_key_labels`] gives.
fn held_local(list: &Body, list_at: &NodePath, at: &NodePath, label: LabelId, open: &dyn Fn(&NodePath) -> bool) -> bool {
    let step = |depth: usize| at.0.get(depth).map(|step| step.0);
    let Some(index) = step(list_at.0.len()) else { return false };
    let Some(conjunct) = list.conjuncts.get(index as usize) else { return false };
    let conjunct_at = list_at.child(index);
    // A part that is complete, holds a conjunct, and does not name the label.
    let silent = |part: &Body, part_at: &NodePath| !open(part_at) && !part.conjuncts.is_empty() && !crate::safety::body_labels(part).contains(&label);
    let part = step(conjunct_at.0.len());
    match conjunct {
        Conjunct::Atom(_) | Conjunct::Not(Negated::Atom(_)) | Conjunct::Constraint(_) => false,
        Conjunct::Not(Negated::Form(_)) | Conjunct::All { .. } => true,
        Conjunct::Or(branches) => match part {
            Some(0) => {
                branches.iter().zip(0u32..).skip(1).any(|(branch, index)| silent(branch.value(), &conjunct_at.child(index)))
                    || held_local(branches[0].value(), &conjunct_at.child(0), at, label, open)
            }
            Some(_) => true,
            None => false,
        },
        Conjunct::If { then, otherwise, .. } => match part {
            Some(1) => silent(otherwise.value(), &conjunct_at.child(2)) || held_local(then.value(), &conjunct_at.child(1), at, label, open),
            Some(_) => true,
            None => false,
        },
    }
}

/// The refusals of each body of `form` that `checked` keeps, and the
/// refusals of `=` in each body at a path that `open` does not hold, each at
/// its source path.
fn body_refusals(form: &Form, checked: &dyn Fn(&FormBody<'_>) -> bool, open: &dyn Fn(&NodePath) -> bool) -> Vec<Refusal> {
    let mut refused: Vec<(&'static str, NodePath)> = Vec::new();
    for form_body in form_bodies(form) {
        if checked(&form_body) {
            refusals(&form_body, &mut refused);
        }
        let mut made = Vec::new();
        made_by_equality(form_body.body.value(), &form_body.at, &Making::Any, &mut made);
        refused.extend(made.into_iter().filter(|(_, at)| !open(at)));
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

/// Where a list stands, as to the label a `=` of it makes.
enum Making {
    /// A form's body: a `=` makes a label of the body.
    Any,
    /// The first branch of an `OR` or the then of an `IF`, at the path
    /// given, which exports the labels given: a `=` makes only a label of
    /// those.
    Exports(NodePath, Vec<LabelId>),
    /// A later branch of an `OR`, the test or the else of an `IF`, or a list
    /// of an `ALL`: a `=` makes no label.
    Nothing,
}

/// Pushes onto `refused` each refusal of a `(= *X Y)` or a `(= *X 0)` in the
/// list `body`, at `at`, which stands as `making` gives, and so for each
/// list below it.
fn made_by_equality(body: &Body, at: &NodePath, making: &Making, refused: &mut Vec<(&'static str, NodePath)>) {
    for (at, conjunct) in list_of(body, at) {
        made_in_conjunct(conjunct, &at, making, refused);
    }
}

/// [`made_by_equality`] on the conjunct `conjunct` at `at` of a list that
/// stands as `making` gives.
fn made_in_conjunct(conjunct: &Conjunct, at: &NodePath, making: &Making, refused: &mut Vec<(&'static str, NodePath)>) {
    let mut push = |refusal: (&'static str, NodePath)| {
        if !refused.contains(&refusal) {
            refused.push(refusal);
        }
    };
    match conjunct {
        Conjunct::Constraint(Constraint { op: ConstraintOp::Eq, first, .. }) if first.fresh => match making {
            Making::Any => {}
            Making::Exports(form, exported) => {
                if !exported.contains(&first.label) {
                    push(("the form does not export the label that `=` makes", form.clone()));
                }
            }
            Making::Nothing => push(("`=` makes a label only in an `OR`'s first branch or an `IF`'s then", at.clone())),
        },
        Conjunct::Or(branches) => {
            let later: Vec<&Body> = branches[1..].iter().map(|branch| branch.value()).collect();
            let mut exported = Vec::new();
            exports(branches[0].value(), &later, &mut exported);
            for (branch, index) in branches.iter().zip(0u32..) {
                let making = if index == 0 { Making::Exports(at.clone(), exported.clone()) } else { Making::Nothing };
                made_by_equality(branch.value(), &at.child(index), &making, refused);
            }
        }
        Conjunct::If { test, then, otherwise } => {
            let mut exported = Vec::new();
            exports(then.value(), &[otherwise.value()], &mut exported);
            made_by_equality(test.value(), &at.child(0), &Making::Nothing, refused);
            made_by_equality(then.value(), &at.child(1), &Making::Exports(at.clone(), exported), refused);
            made_by_equality(otherwise.value(), &at.child(2), &Making::Nothing, refused);
        }
        Conjunct::All { domain, body } => {
            made_by_equality(domain.value(), &at.child(0), &Making::Nothing, refused);
            made_by_equality(body.value(), &at.child(1), &Making::Nothing, refused);
        }
        Conjunct::Not(Negated::Form(form)) => made_in_conjunct(form, &at.child(0), &Making::Any, refused),
        Conjunct::Atom(_) | Conjunct::Not(Negated::Atom(_)) | Conjunct::Constraint(_) => {}
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
