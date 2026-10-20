//! The scope check. Over a whole node it passes, since the reader and the resolver report the scope's errors.

use super::{Check, CheckId, CheckInput, CheckResult, Prefix, PrefixResult};

/// [`CheckId::Scope`].
pub struct ScopeCheck;

impl Check for ScopeCheck {
    fn id(&self) -> CheckId {
        CheckId::Scope
    }

    fn check(&self, _input: &CheckInput<'_>) -> CheckResult {
        CheckResult::Pass
    }

    fn check_prefix(&self, prefix: &Prefix<'_>) -> PrefixResult {
        super::prefix::scope(prefix)
    }
}
