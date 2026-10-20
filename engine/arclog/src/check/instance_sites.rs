//! The check of the sites of an instance's keyed inputs
//! (`docs/arclog/arclog.md#instance`).

use super::types::result;
use super::{each_node, Check, CheckId, CheckInput, CheckResult, Prefix, PrefixResult, Refusal, CheckCacheKey, KeyInput};
use crate::program::canonical::{CanonicalOrder, SearchBudget};
use crate::program::path::{NodePath, NodeRef};
use crate::program::{
    Atom, DemonstratedPart, Form, Instance, InstanceInput, InstanceName, InstancePart, KeyClause, KeyClausePart, LabelUse, Node, OutputName, OutputOwner,
    RelationColumn, RelationRef, Site, SiteArg,
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
    /// - a keyed input that joins no label of the key, reads no output of
    ///   an `INIT` form whose key columns are among the key's, and, in an
    ///   `INIT`, reads no output of its own instance: an input that holds
    ///   for every key is a broadcast, and stands after the key clause;
    /// - in an `INIT`, a key site of a keyed input's read of an `INIT` form
    ///   keyed by the same columns, whose fields are the key's labels in
    ///   order: the read joins on the key in scope without a key site.
    fn check(&self, input: &CheckInput<'_>) -> CheckResult {
        let refused = refusals(input.form, &input.scope.program.program.value().forms);
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
fn refusals(form: &Form, forms: &[Form]) -> Vec<Refusal> {
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
        if is_broadcast(keyed.value(), &input_at, key, own, forms) {
            refused.push(Refusal { message: "the input reads no key label, so it holds for every key and stands after the key clause".into(), at: input_at.clone() });
        }
        if own.is_some() {
            key_sites(keyed.value(), &input_at, key, forms, &mut refused);
        }
    }
    refused
}

/// Whether `input`, at `at`, a keyed input of the key clause `key`, joins
/// no key label and reads no output of an `INIT` form whose key columns are
/// among the key's, nor of `own`.
fn is_broadcast(input: &InstanceInput, at: &NodePath, key: &KeyClause, own: Option<&InstanceName>, forms: &[Form]) -> bool {
    let mut joins_key = false;
    each_label_use_at(NodeRef::InstanceInput(input), at, &mut |_, use_| {
        if let LabelUse::Join(label) = use_ {
            joins_key |= key.key.columns.iter().any(|column| column.label == label);
        }
    });
    let mut keyed_read = false;
    each_read(input, at, &mut |name, _, _| {
        let within = key_columns(forms, name).is_some_and(|columns| !columns.is_empty() && columns.iter().all(|column| key.key.columns.iter().any(|own| own.name == column.name)));
        keyed_read |= within || own == Some(name);
    });
    !joins_key && !keyed_read
}

/// Pushes onto `refused` each key site of a read in `input`, at `at`, of
/// an `INIT` form keyed by the columns of `key`, whose fields are the
/// labels of `key` in order.
fn key_sites(input: &InstanceInput, at: &NodePath, key: &KeyClause, forms: &[Form], refused: &mut Vec<Refusal>) {
    let own: Vec<&RelationColumn> = key.key.columns.iter().collect();
    each_read(input, at, &mut |name, atom, atom_at| {
        let Some(columns) = key_columns(forms, name) else { return };
        if columns.is_empty() || columns.len() != own.len() || columns.iter().zip(&own).any(|(column, own)| column.name != own.name) {
            return;
        }
        for (site, index) in atom.sites.iter().zip(0u32..) {
            if site.column == crate::resolver::columns::key() && reads_key(site, &own) {
                refused.push(Refusal { message: "a read at the key in scope joins on it without a key site".into(), at: atom_at.child(index) });
            }
        }
    });
}

/// Whether the key site `site` reads the fields of the key whose columns
/// are `key`, each by the label of its column, in order.
fn reads_key(site: &Site, key: &[&RelationColumn]) -> bool {
    let field = |arg: &SiteArg, column: &RelationColumn| match arg {
        SiteArg::NamedLabel { name, label: LabelUse::Join(label) } => *name == column.name && *label == column.label,
        SiteArg::Field(field) => field.column == column.name && matches!(&field.value.args[..], [SiteArg::Label(LabelUse::Join(label))] if *label == column.label),
        _ => false,
    };
    site.value.args.len() == key.len() && site.value.args.iter().zip(key).all(|(arg, column)| field(arg, column))
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

/// The key columns of the `INIT` form named `name` among `forms`, or none
/// where no such form stands there. An `INIT` with no key clause has none.
fn key_columns<'f>(forms: &'f [Form], name: &InstanceName) -> Option<&'f [RelationColumn]> {
    forms.iter().find_map(|form| match form {
        Form::Instance(instance) if instance.value().name == *name => Some(instance_key(instance.value())),
        _ => None,
    })
}

fn instance_key(instance: &Instance) -> &[RelationColumn] {
    instance.key.as_ref().map_or(&[], |key| &key.value().key.columns)
}
