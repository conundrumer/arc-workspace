//! The check of an `Unfold` instance's reads of its outputs.

use super::instance_inputs::inputs_at;
use super::reads::form_reads;
use super::types::{component, result};
use super::{Check, CheckId, CheckInput, CheckResult, Prefix, PrefixResult, Refusal, CheckCacheKey, KeyInput};
use crate::program::canonical::{CanonicalOrder, SearchBudget};
use crate::program::path::{node_at, NodePath, NodeRef};
use crate::program::LabelUse;
use crate::types::each_site_label;

/// [`CheckId::UnfoldReads`].
pub struct UnfoldReadsCheck;

impl Check for UnfoldReadsCheck {
    fn id(&self) -> CheckId {
        CheckId::UnfoldReads
    }

    fn cache_key(&self, at: &KeyInput<'_>) -> Option<CheckCacheKey> {
        Some(at.base(self.id()))
    }

    /// Refuses each read by an `INIT` form of the form of an output of its
    /// own instance, as `docs/lib-spec.md#construction` gives: a read in an
    /// input that [`crate::registry::InputPort::reads_outputs`] does not
    /// mark, or in the key clause's body, and a read in a marked input with
    /// a site that makes a label, since another atom of the clause binds
    /// each label of such a read.
    fn check(&self, input: &CheckInput<'_>) -> CheckResult {
        let program = input.scope.program;
        let mut refusals = Vec::new();
        for read in form_reads(input.form, input.path) {
            let Some((_, true)) = read.node(program, input.path) else { continue };
            let form_at = NodePath(read.form.0[input.path.0.len()..].into());
            let Some(NodeRef::Instance(instance)) = node_at(NodeRef::from(input.form), &form_at) else { continue };
            let Some(component) = component(input.scope.registry, &instance.component) else { continue };
            let within = &read.at.0[form_at.0.len()..];
            let port = inputs_at(instance).into_iter().find(|(path, _, _)| within.starts_with(&path.0)).map(|(_, _, written)| &written.name);
            let marked = port.is_some_and(|port| component.inputs.iter().any(|declared| declared.port.name == *port && declared.reads_outputs));
            let mut makes = false;
            for site in read.atom.sites.iter() {
                each_site_label(site, &mut Vec::new(), &mut |use_, _| makes |= matches!(use_, LabelUse::Fresh(_)));
            }
            let message = if !marked {
                "the read is of an output of its own instance, which only an input that reads the instance's outputs, as `Unfold`'s `step`, `skip` and `take`, makes"
            } else if makes {
                "a site of a read of an output of its own instance makes a label, where each site joins a label that another atom of the clause binds"
            } else {
                continue;
            };
            refusals.push(Refusal { message: message.into(), at: read.at });
        }
        if refusals.is_empty() {
            return CheckResult::Pass;
        }
        let order = CanonicalOrder::of(input.form, &mut SearchBudget::new());
        result(refusals.into_iter().map(|refusal| Refusal { at: order.canonical_path(&refusal.at), ..refusal }).collect())
    }

    /// Refuses each refusal of [`Check::check`] at a complete read. A
    /// refusal of a read reads the read's sites, which only grow by sites
    /// that make no fewer labels, the name of the input that holds it, which
    /// stands in the input's head, and the component of the instance, so no
    /// node written after the read undoes it.
    fn check_prefix(&self, prefix: &Prefix<'_>) -> PrefixResult {
        super::prefix::settled(prefix, self)
    }
}
