//! The check of an instance's input order and defaults, and the inputs of
//! an `INIT` form by their paths, which the check of an `Unfold` instance's
//! reads reads too.

use super::reads::{form_reads, forms_within, FormRead};
use super::types::{component, result};
use super::{Check, CheckId, CheckInput, CheckResult, Prefix, PrefixResult, Refusal};
use crate::safety::body_labels;
use crate::program::canonical::{CanonicalOrder, SearchBudget};
use crate::program::path::{node_at, NodePath, NodeRef};
use crate::program::{Instance, InstanceInput, InstancePart, KeyBody, KeyClausePart, PortName};
use crate::resolver::{column_sources, columns, ResolvedProgram};
use crate::types::{each_site_label, use_label};

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
    /// `docs/arclog/arclog.md#instance` gives. In a keyed instance, it
    /// refuses as well each input that stands in a group other than its
    /// own: an input after the key clause that reads an output of its
    /// instance, and a broadcast inside the key clause.
    fn check(&self, input: &CheckInput<'_>) -> CheckResult {
        let program = input.scope.program;
        let reads = form_reads(input.form, input.path);
        let mut refusals = Vec::new();
        for (at, node) in forms_within(input.form) {
            let NodeRef::Instance(instance) = node else { continue };
            let Some(component) = component(input.scope.registry, &instance.component) else { continue };
            let declared = |name: &PortName| component.inputs.iter().position(|declared| declared.port.name == *name);
            let mut written: Vec<&PortName> = Vec::new();
            let mut group = None;
            let mut latest = None;
            let instance_at = input.path.join(&at);
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
                let input_at = at.join(&path);
                let within = reads.iter().filter(|read| read.form == instance_at && read.at.0.starts_with(&input_at.0));
                let group = instance.key.as_ref().and_then(|key| group_fault(program, input.path, keyed, written_input, &key.value().key, within));
                for message in [message, group].into_iter().flatten() {
                    refusals.push((message, input_at.clone()));
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

/// Why `written`, an input of an instance whose key is `key`, stands in the
/// wrong group, where it does, from `reads`, the reads of its body, each at
/// its path relative to the form at `form` in the program, as
/// `docs/arclog/arclog.md#instance` gives: an input after the key clause
/// that reads an output of its instance, and an input inside it that reads
/// no key label and no output of its instance, a broadcast. A label at a head
/// site of the input is a read of it, and a read that joins on labels of
/// `key` with no key site, as `docs/arclog/arclog.md#instance` gives, is a
/// read of them. A `CHOOSE` form has no key column, so a read of one joins
/// on no key.
fn group_fault<'a>(
    program: &ResolvedProgram,
    form: &NodePath,
    keyed: bool,
    written: &InstanceInput,
    key: &KeyBody,
    reads: impl Iterator<Item = &'a FormRead<'a>>,
) -> Option<&'static str> {
    let key_labels = body_labels(key.body.value());
    let in_scope = |read_key: &KeyBody| read_key.columns.iter().all(|column| key.columns.iter().any(|own| own.name == column.name));
    let mut reads_output = false;
    let mut reads_key = false;
    for read in reads {
        let Some((node, own)) = read.node(program, form) else { continue };
        reads_output |= own;
        let read_form = node_at(NodeRef::Program(program.program.value()), program.form_of(node));
        let read_key = read_form.filter(|form| !matches!(form, NodeRef::Choose(_))).and_then(column_sources::key_clause);
        reads_key |= read_key.is_some_and(|(read_key, _)| in_scope(read_key)) && !read.atom.sites.iter().any(|site| site.column == columns::key());
    }
    reads_key |= body_labels(written.body.value()).iter().any(|label| key_labels.contains(label));
    for site in written.head.iter() {
        each_site_label(site, &mut Vec::new(), &mut |use_, _| reads_key |= use_label(use_).is_some_and(|label| key_labels.contains(&label)));
    }
    match keyed {
        false if reads_output => Some("the input reads an output of its instance and stands after the key clause, where only a broadcast stands"),
        true if !reads_key && !reads_output => {
            Some("the input reads no key label and no output of its instance, a broadcast, and stands inside the key clause, where a broadcast stands after it")
        }
        _ => None,
    }
}

/// Each input that `instance` writes, with its path relative to the
/// instance and whether it stands in the key clause, the keyed inputs
/// first, each group in the order it is written.
pub(crate) fn inputs_at(instance: &Instance) -> Vec<(NodePath, bool, &InstanceInput)> {
    let mut out = Vec::new();
    if let Some(key) = &instance.key {
        let key = key.value();
        let key_path = NodePath::default().child(instance.position(InstancePart::Key));
        let keyed = key.inputs.iter().enumerate();
        out.extend(keyed.map(|(index, input)| (key_path.child(key.position(KeyClausePart::Input(index))), true, input.value())));
    }
    let others = instance.inputs.iter().enumerate();
    out.extend(others.map(|(index, input)| (NodePath::default().child(instance.position(InstancePart::Input(index))), false, input.value())));
    out
}
