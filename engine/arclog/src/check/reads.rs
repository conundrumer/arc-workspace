//! The check of the pooled and lifted reads.

use super::{Check, CheckId, CheckInput, CheckResult, Prefix, PrefixResult};

/// [`CheckId::PooledAndLiftedReads`].
pub struct PooledAndLiftedReadsCheck;

impl Check for PooledAndLiftedReadsCheck {
    fn id(&self) -> CheckId {
        CheckId::PooledAndLiftedReads
    }

    fn check(&self, _input: &CheckInput<'_>) -> CheckResult {
        CheckResult::Pass
    }

    fn check_prefix(&self, _prefix: &Prefix<'_>) -> PrefixResult {
        PrefixResult::Undecided
    }
}
