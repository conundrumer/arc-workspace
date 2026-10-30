//! The type check of a form: its refusals and the types of each label
//! scope of the form, on a whole form and on a prefix.

use super::super::inference::FormInference;
use super::super::{Check, CheckId, CheckInput, CheckResult, Prefix, PrefixResult, Refusal, CheckCacheKey, KeyInput};
use super::{map_labels, pose_of_fault, result, rule_scope_forms, rule_within, form_within};
use crate::program::canonical::{CanonicalOrder, SearchBudget};
use crate::program::path::NodePath;
use crate::program::{ConstraintOp, Form, LabelId, Operand};
use crate::types::{label_fault_message, FormRelation, FormTypes, LabelFault, ValueType};

/// [`CheckId::Types`].
pub struct TypesCheck;

impl Check for TypesCheck {
    fn id(&self) -> CheckId {
        CheckId::Types
    }

    fn cache_key(&self, at: &KeyInput<'_>) -> Option<CheckCacheKey> {
        Some(at.base(self.id()))
    }

    fn check(&self, input: &CheckInput<'_>) -> CheckResult {
        infer_form(input, &CanonicalOrder::of(input.form, &mut SearchBudget::new())).0
    }

    /// The refusals of the partial form at its complete nodes, since a
    /// meet only narrows as sites are added and a join of branches only
    /// widens, but those of a label that takes its type from a column of
    /// `(pose-or <type>)` alone, which a later site may give a Pose type,
    /// until the form is complete.
    fn check_prefix(&self, prefix: &Prefix<'_>) -> PrefixResult {
        let input = super::super::prefix::whole(prefix);
        let order = CanonicalOrder::of(prefix.partial, &mut SearchBudget::new());
        let complete = prefix.open.is_none();
        let (result, _) = infer_form_where(&input, &order, &|form, label| complete || !form.is_given(label), !input.scope.inference.is_mask());
        super::super::prefix::settled_result(prefix, result)
    }
}

/// The [`FormTypes`] of each label scope of a form, by the scope's
/// canonical path relative to the form, in the order of those paths, as
/// [`crate::check::CheckCache`] keeps them.
pub type ScopeTypes = Box<[(NodePath, FormTypes)]>;

/// The type check's result on the form of `input`, and the [`FormTypes`] of
/// each label scope of the form that `order` gives, each by the scope's
/// canonical path, with each label at its canonical position in its scope.
///
/// The result is the union of the refusals of the inference of each label
/// scope of the form, as [`CanonicalOrder::label_scopes`] gives them, each scope inferred
/// at its source path joined to the form's path, and, for a clause, of the
/// refusals at the columns of its relation. A fault of a label whose sites
/// give it a Pose type and another type is the pose rule's, which
/// [`crate::check::pose`] refuses.
pub fn infer_form(input: &CheckInput<'_>, order: &CanonicalOrder) -> (CheckResult, ScopeTypes) {
    infer_form_where(input, order, &|_, _| true, true)
}

/// [`infer_form`], with a refusal of a label only where `refuses` holds
/// for the label in its scope's inference, and the types of the scopes
/// only where `collect_types` holds: a prefix in mask mode reads the
/// refusals alone.
fn infer_form_where(input: &CheckInput<'_>, order: &CanonicalOrder, refuses: &dyn Fn(&FormInference<'_>, LabelId) -> bool, collect_types: bool) -> (CheckResult, ScopeTypes) {
    let inference = input.scope.inference;
    let mut found = Vec::new();
    let mut scopes = Vec::new();
    for source in inferred_scopes(order) {
        let form = inference.infer(&input.path.join(&source)).expect(SCOPE_FORM);
        found.extend(refusals(&form, order, &source, refuses));
        if collect_types {
            let relations = scope_forms_within(input.form, &source).into_iter().flat_map(|(at, form)| {
                let relations = inference.form_relations(&input.path.join(&at), form);
                let canonical = order.canonical_path(&at);
                relations.into_iter().map(move |(output, columns)| (FormRelation { form: canonical.clone(), output }, columns))
            });
            scopes.push((order.canonical_path(&source), scope_types(&form, order, &source, relations.collect::<Vec<_>>())));
        }
    }
    if let (Form::Clause(clause), Some(form)) = (input.form, inference.infer(input.path)) {
        found.extend(inference.column_refusals(&form, clause.value(), input.path, order));
    }
    (result(found), scopes.into())
}

/// What stands at the source path of each label scope of a form.
const SCOPE_FORM: &str = "a form or a `DEMO_RULE` stands at the path of each label scope of the form";

/// The source path of each label scope of a form whose canonical order is
/// `order`, relative to the form, in the order of
/// [`CanonicalOrder::label_scopes`]: the scopes that [`infer_form`] infers
/// and whose clauses [`type_clause_signatures`] reads.
pub(super) fn inferred_scopes(order: &CanonicalOrder) -> Vec<NodePath> {
    order.label_scopes().into_iter().map(|(source, _)| source).collect()
}

/// The refusals of the type check on `form`, the label scope whose form
/// stands at `scope`, a source path relative to a form whose canonical
/// order is `order`, each at the canonical path of `scope` joined to its
/// place in the scope's form.
fn refusals(form: &FormInference<'_>, order: &CanonicalOrder, scope: &NodePath, refuses: &dyn Fn(&FormInference<'_>, LabelId) -> bool) -> Vec<Refusal> {
    let place = |at: &NodePath| order.canonical_path(&scope.join(at));
    let mut refusals = Vec::new();
    for (label, ty) in &form.labels {
        let Err(fault) = ty else { continue };
        if !refuses(form, *label) {
            continue;
        }
        if pose_of_fault(fault).is_some() {
            continue;
        }
        let message = match fault {
            LabelFault::NoJoin(a, b) if form.zero_typed.contains(label) => {
                format!("the label here takes the types {a:?} and {b:?} from the other clauses of its relation, which have no join")
            }
            fault => format!("the label here {}", label_fault_message(fault.clone())),
        };
        refusals.push(Refusal { message: message.into(), at: place(form.walk.first_use(*label)) });
    }
    for (at, message) in form.bound_faults() {
        refusals.push(Refusal { message: message.into(), at: place(&at) });
    }
    for (at, constraint) in &form.walk.constraints {
        if !matches!(constraint.op, ConstraintOp::Lt | ConstraintOp::Le | ConstraintOp::Gt | ConstraintOp::Ge) {
            continue;
        }
        let second = match constraint.second {
            Operand::Label(label) => Some(label.label),
            Operand::Zero => None,
        };
        for label in std::iter::once(constraint.first.label).chain(second).filter(|label| refuses(form, *label)) {
            if let Some(ty) = form.label(label).filter(|ty| !ty.admits_order()) {
                let message = format!("the constraint orders a label of the type {ty:?}, and only `Number` has an order");
                refusals.push(Refusal { message: message.into(), at: place(at) });
            }
        }
    }
    refusals
}

/// The types of the labels of `form`, the scope whose form stands at
/// `scope`, a source path relative to the form whose canonical order is
/// `order`, each label at its canonical position in that scope, with the
/// column types of `relations`.
fn scope_types(
    form: &FormInference<'_>,
    order: &CanonicalOrder,
    scope: &NodePath,
    relations: impl IntoIterator<Item = (FormRelation, Box<[ValueType]>)>,
) -> FormTypes {
    let position = |label: LabelId| LabelId(order.canonical_label(scope, label));
    let types = form.labels.iter().filter_map(|(label, ty)| match ty {
        Ok(Some(ty)) => Some((position(*label), map_labels(ty, &position))),
        Ok(None) | Err(_) => None,
    });
    FormTypes::new(types, relations)
}

/// Each form that stands in the label scope at `scope`, a source path
/// relative to `form`, with its path relative to `form`: the scope's own
/// form, or each form of a `DEMO_RULE` that stands in the rule's scope.
pub(super) fn scope_forms_within<'f>(form: &'f Form, scope: &NodePath) -> Vec<(NodePath, &'f Form)> {
    if let Some(found) = form_within(form, scope) {
        return vec![(scope.clone(), found)];
    }
    let rule = rule_within(form, scope).expect(SCOPE_FORM);
    rule_scope_forms(rule).map(|(index, found)| (scope.child(index), found)).collect()
}
