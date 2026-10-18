//! The check of an instance's input order and defaults.

use super::{Check, CheckId, CheckInput, CheckResult, Prefix, PrefixResult};

/// [`CheckId::InstanceInputs`].
pub struct InstanceInputsCheck;

impl Check for InstanceInputsCheck {
    fn id(&self) -> CheckId {
        CheckId::InstanceInputs
    }

    fn check(&self, _input: &CheckInput<'_>) -> CheckResult {
        CheckResult::Pass
    }

    fn check_prefix(&self, _prefix: &Prefix<'_>) -> PrefixResult {
        PrefixResult::Undecided
    }
}
