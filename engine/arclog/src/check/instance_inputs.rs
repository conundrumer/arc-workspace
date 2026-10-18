//! The check of an instance's input order and defaults, and the inputs of
//! an `INIT` form by their paths, which the check of an `Unfold` instance's
//! reads reads too.

use super::reads::forms_within;
use super::types::{component, result};
use super::{Check, CheckId, CheckInput, CheckResult, Prefix, PrefixResult, Refusal};
use crate::program::canonical::{CanonicalOrder, SearchBudget};
use crate::program::path::{NodePath, NodeRef};
use crate::program::{Instance, InstanceInput, PortName};

/// [`CheckId::InstanceInputs`].
pub struct InstanceInputsCheck;

impl Check for InstanceInputsCheck {
    fn id(&self) -> CheckId {
        CheckId::InstanceInputs
    }

    /// Refuses, in each `INIT` form of the form, each input that its
    /// component does not declare, each input written after another clause of
    /// the same input, and each input that stands before an input of its
    /// group that the component declares before it, as
    /// `docs/arclog/arclog.md#instance` gives.
    fn check(&self, input: &CheckInput<'_>) -> CheckResult {
        let mut refusals = Vec::new();
        for (at, node) in forms_within(input.form) {
            let NodeRef::Instance(instance) = node else { continue };
            let Some(component) = component(input.scope.registry, &instance.component) else { continue };
            let declared = |name: &PortName| component.inputs.iter().position(|declared| declared.port.name == *name);
            let mut written: Vec<&PortName> = Vec::new();
            let mut group = None;
            let mut latest = None;
            for (path, keyed, written_input) in inputs_at(instance) {
                if group != Some(keyed) {
                    group = Some(keyed);
                    latest = None;
                }
                let name = &written_input.name;
                let index = declared(name);
                let message = match index {
                    None => Some("the component declares no input of this name"),
                    Some(_) if written.contains(&name) => Some("the input is written in another clause; a union is one clause whose body is an `OR`"),
                    Some(index) if latest.is_some_and(|latest| index < latest) => {
                        Some("the input stands before an input of its group that the component declares before it")
                    }
                    Some(_) => None,
                };
                latest = latest.max(index);
                written.push(name);
                if let Some(message) = message {
                    refusals.push((message, at.join(&path)));
                }
            }
        }
        if refusals.is_empty() {
            return CheckResult::Pass;
        }
        let order = CanonicalOrder::of(input.form, &mut SearchBudget::new());
        result(refusals.into_iter().map(|(message, at)| Refusal { message: message.into(), at: order.canonical_path(&at) }).collect())
    }

    fn check_prefix(&self, _prefix: &Prefix<'_>) -> PrefixResult {
        PrefixResult::Undecided
    }
}

/// Each input that `instance` writes, with its path relative to the
/// instance and whether it stands in the key clause, the keyed inputs
/// first, each group in the order it is written.
pub(super) fn inputs_at(instance: &Instance) -> Vec<(NodePath, bool, &InstanceInput)> {
    let mut out = Vec::new();
    let mut first = 0;
    if let Some(key) = &instance.key {
        let key_path = NodePath::default().child(0);
        out.extend(key.value().inputs.iter().zip(1u32..).map(|(input, index)| (key_path.child(index), true, input.value())));
        first = 1;
    }
    out.extend(instance.inputs.iter().zip(first..).map(|(input, index)| (NodePath::default().child(index), false, input.value())));
    out
}
