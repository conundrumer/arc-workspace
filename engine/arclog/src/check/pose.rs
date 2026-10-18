//! The pose rule's check.

use super::{Check, CheckId, CheckInput, CheckResult, Prefix, PrefixResult};

/// [`CheckId::PoseRule`].
pub struct PoseRuleCheck;

impl Check for PoseRuleCheck {
    fn id(&self) -> CheckId {
        CheckId::PoseRule
    }

    fn check(&self, _input: &CheckInput<'_>) -> CheckResult {
        CheckResult::Pass
    }

    fn check_prefix(&self, _prefix: &Prefix<'_>) -> PrefixResult {
        PrefixResult::Undecided
    }
}
