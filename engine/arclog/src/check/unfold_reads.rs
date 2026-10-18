//! The check of an `Unfold` instance's reads of its outputs.

use super::{Check, CheckId, CheckInput, CheckResult, Prefix, PrefixResult};

/// [`CheckId::UnfoldReads`].
pub struct UnfoldReadsCheck;

impl Check for UnfoldReadsCheck {
    fn id(&self) -> CheckId {
        CheckId::UnfoldReads
    }

    fn check(&self, _input: &CheckInput<'_>) -> CheckResult {
        CheckResult::Pass
    }

    fn check_prefix(&self, _prefix: &Prefix<'_>) -> PrefixResult {
        PrefixResult::Undecided
    }
}
