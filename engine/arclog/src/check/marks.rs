//! The check of the marks a constraint's labels take.

use super::types::result;
use super::{each_node, Check, CheckId, CheckInput, CheckResult, Prefix, PrefixResult, Refusal, CheckCacheKey, KeyInput};
use crate::program::canonical::{CanonicalOrder, SearchBudget};
use crate::program::path::{NodePath, NodeRef};
use crate::program::{Conjunct, ConstraintOp};

/// [`CheckId::ConstraintMarks`].
pub struct ConstraintMarksCheck;

impl Check for ConstraintMarksCheck {
    fn id(&self) -> CheckId {
        CheckId::ConstraintMarks
    }

    fn cache_key(&self, at: &KeyInput<'_>) -> Option<CheckCacheKey> {
        Some(at.base(self.id()))
    }

    /// Refuses each constraint other than `=` that makes a label, `*X`,
    /// where every label of the constraint joins
    /// (`docs/arclog/arclog.md#negation-and-constraints`). The second label
    /// of `=` is [`CheckId::EqualityAndZero`]'s, and a site of a `NOT` atom
    /// [`CheckId::MadeAndExportedLabels`]'s.
    fn check(&self, input: &CheckInput<'_>) -> CheckResult {
        let mut refused = Vec::new();
        each_node(NodeRef::from(input.form), &NodePath::default(), &mut |node, at| {
            if let NodeRef::Conjunct(Conjunct::Constraint(constraint)) = node {
                if constraint.op != ConstraintOp::Eq && (constraint.first.fresh || super::zero::second_made(constraint)) {
                    refused.push(at.clone());
                }
            }
        });
        if refused.is_empty() {
            return CheckResult::Pass;
        }
        let order = CanonicalOrder::of(input.form, &mut SearchBudget::new());
        let refusal = |at: NodePath| Refusal { message: "a constraint other than `=` makes no label, where every label joins".into(), at: order.canonical_path(&at) };
        result(refused.into_iter().map(refusal).collect())
    }

    /// Refuses each refusal of [`Check::check`] at a complete constraint. A
    /// refusal of a constraint reads its operator and the marks of its own
    /// labels, so no node written after it undoes it.
    fn check_prefix(&self, prefix: &Prefix<'_>) -> PrefixResult {
        super::prefix::settled(prefix, self)
    }
}
