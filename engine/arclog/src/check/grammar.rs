//! The grammar check. Over a whole node it passes, since the reader reports the grammar's errors.

use super::{Check, CheckId, CheckInput, CheckResult, Prefix, PrefixResult};

/// [`CheckId::Grammar`].
pub struct GrammarCheck;

impl Check for GrammarCheck {
    fn id(&self) -> CheckId {
        CheckId::Grammar
    }

    fn check(&self, _input: &CheckInput<'_>) -> CheckResult {
        CheckResult::Pass
    }

    fn check_prefix(&self, _prefix: &Prefix<'_>) -> PrefixResult {
        PrefixResult::Undecided
    }
}
