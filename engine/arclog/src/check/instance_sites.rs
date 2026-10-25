//! The check of the sites of an instance's keyed inputs
//! (`docs/arclog/arclog.md#instance`).

use super::types::result;
use super::{each_node, Check, CheckId, CheckInput, CheckResult, Prefix, PrefixResult, Refusal, CheckCacheKey, KeyInput};
use crate::program::canonical::{CanonicalOrder, SearchBudget};
use crate::program::path::{NodePath, NodeRef};
use crate::program::{
    Atom, DemonstratedPart, Form, InstanceInput, InstanceName, InstancePart, KeyClause, KeyClausePart, LabelUse, Node, OutputName, OutputOwner, RelationRef,
};
use crate::safety::each_label_use_at;

/// [`CheckId::InstanceSites`].
pub struct InstanceSitesCheck;

impl Check for InstanceSitesCheck {
    fn id(&self) -> CheckId {
        CheckId::InstanceSites
    }

    fn cache_key(&self, at: &KeyInput<'_>) -> Option<CheckCacheKey> {
        Some(at.base(self.id()))
    }

    /// Refuses, in an `INIT` or a `DEMONSTRATED` form with a key clause:
    ///
    /// - a keyed input that joins no label of the key and, in an `INIT`,
    ///   reads no output of its own instance: an input that holds for every
    ///   key is a broadcast, and stands after the key clause.
    fn check(&self, input: &CheckInput<'_>) -> CheckResult {
        let refused = refusals(input.form);
        if refused.is_empty() {
            return CheckResult::Pass;
        }
        let order = CanonicalOrder::of(input.form, &mut SearchBudget::new());
        result(refused.into_iter().map(|refusal| Refusal { at: order.canonical_path(&refusal.at), ..refusal }).collect())
    }

    fn check_prefix(&self, prefix: &Prefix<'_>) -> PrefixResult {
        super::prefix::settled(prefix, self)
    }
}

/// The refusals of `form`, a form of the program whose forms are `forms`,
/// at their source paths.
fn refusals(form: &Form) -> Vec<Refusal> {
    let (key, at, own) = match form {
        Form::Instance(instance) => {
            let instance = instance.value();
            let Some(key) = &instance.key else { return Vec::new() };
            (key, NodePath::default().child(instance.position(InstancePart::Key)), Some(&instance.name))
        }
        Form::Demonstrated(demonstrated) => {
            let demonstrated = demonstrated.value();
            let Some(key) = &demonstrated.key else { return Vec::new() };
            (key, NodePath::default().child(demonstrated.position(DemonstratedPart::Key)), None)
        }
        _ => return Vec::new(),
    };
    let key = key.value();
    let mut refused = Vec::new();
    for (index, keyed) in key.inputs.iter().enumerate() {
        let input_at = at.child(key.position(KeyClausePart::Input(index)));
        if is_broadcast(keyed.value(), &input_at, key, own) {
            refused.push(Refusal { message: "the input reads no key label, so it holds for every key and stands after the key clause".into(), at: input_at.clone() });
        }
    }
    refused
}

/// Whether `input`, at `at`, a keyed input of the key clause `key`, joins
/// no key label, at a site or in its body, and reads no output of `own`.
fn is_broadcast(input: &InstanceInput, at: &NodePath, key: &KeyClause, own: Option<&InstanceName>) -> bool {
    let mut joins_key = false;
    each_label_use_at(NodeRef::InstanceInput(input), at, &mut |_, use_| {
        if let LabelUse::Join(label) = use_ {
            joins_key |= key.key.columns.iter().any(|column| column.label == label);
        }
    });
    let mut keyed_read = false;
    each_read(input, at, &mut |name, _, _| keyed_read |= own == Some(name));
    !joins_key && !keyed_read
}

/// Visits each atom of `input`, at `at`, that reads an output of an
/// instance, with the instance's name and the atom's path.
fn each_read<'a>(input: &'a InstanceInput, at: &NodePath, visit: &mut dyn FnMut(&'a InstanceName, &'a Atom, &NodePath)) {
    each_node(NodeRef::InstanceInput(input), at, &mut |node, at| {
        let NodeRef::Conjunct(conjunct) = node else { return };
        let Some(atom) = conjunct.atom() else { return };
        let atom: &'a Node<Atom> = atom;
        if let RelationRef::Output(OutputName { of: OutputOwner::Instance(name), .. }) = &atom.value().relation {
            visit(name, atom.value(), at);
        }
    });
}
