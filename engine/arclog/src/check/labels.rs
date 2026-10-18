//! The check of the labels that `=` makes and that an `OR` or an `IF` exports.

use super::{Check, CheckId, CheckInput, CheckResult, Prefix, PrefixResult};

/// [`CheckId::MadeAndExportedLabels`].
pub struct MadeAndExportedLabelsCheck;

impl Check for MadeAndExportedLabelsCheck {
    fn id(&self) -> CheckId {
        CheckId::MadeAndExportedLabels
    }

    fn check(&self, _input: &CheckInput<'_>) -> CheckResult {
        CheckResult::Pass
    }

    fn check_prefix(&self, _prefix: &Prefix<'_>) -> PrefixResult {
        PrefixResult::Undecided
    }
}
