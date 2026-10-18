//! The grounding check.

use super::{Check, CheckId, CheckInput, CheckResult, Prefix, PrefixResult};

/// [`CheckId::Grounding`].
pub struct GroundingCheck;

impl Check for GroundingCheck {
    fn id(&self) -> CheckId {
        CheckId::Grounding
    }

    fn check(&self, _input: &CheckInput<'_>) -> CheckResult {
        CheckResult::Pass
    }

    fn check_prefix(&self, _prefix: &Prefix<'_>) -> PrefixResult {
        PrefixResult::Undecided
    }
}
