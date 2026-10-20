//! The grammar check. Over a whole node it passes, since the reader reports the grammar's errors.

use super::{Check, CheckId, CheckInput, CheckResult, Prefix, PrefixResult, CheckCacheKey, KeyInput};

/// [`CheckId::Grammar`].
pub struct GrammarCheck;

impl Check for GrammarCheck {
    fn id(&self) -> CheckId {
        CheckId::Grammar
    }

    fn cache_key(&self, at: &KeyInput<'_>) -> Option<CheckCacheKey> {
        Some(at.base(self.id()))
    }

    fn check(&self, _input: &CheckInput<'_>) -> CheckResult {
        CheckResult::Pass
    }

    fn check_prefix(&self, prefix: &Prefix<'_>) -> PrefixResult {
        super::prefix::grammar(prefix)
    }
}
