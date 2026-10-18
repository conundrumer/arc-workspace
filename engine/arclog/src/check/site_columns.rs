//! The check of the columns of each site.

use super::{Check, CheckId, CheckInput, CheckResult, Prefix, PrefixResult};

/// [`CheckId::SiteColumns`].
pub struct SiteColumnsCheck;

impl Check for SiteColumnsCheck {
    fn id(&self) -> CheckId {
        CheckId::SiteColumns
    }

    fn check(&self, _input: &CheckInput<'_>) -> CheckResult {
        CheckResult::Pass
    }

    fn check_prefix(&self, _prefix: &Prefix<'_>) -> PrefixResult {
        PrefixResult::Undecided
    }
}
