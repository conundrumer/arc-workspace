//! The check of an instance's input order, defaults and head sites, and the
//! inputs of an `INIT` form by their paths, which the check of an `Unfold`
//! instance's reads reads too.

use super::reads::{form_reads, forms_within, FormRead};
use super::types::{component, result};
use super::{each_node, Check, CheckId, CheckInput, CheckResult, Prefix, PrefixResult, Refusal, CheckCacheKey, KeyInput};
use crate::safety::body_labels;
use crate::program::path::{NodePath, NodeRef};
use crate::program::{Form, Instance, InstanceInput, InstancePart, KeyBody, KeyClausePart, LabelId, OutputName, OutputOwner, PortName, RelationRef};
use crate::registry::{binding_sites, is_key, unbound, Column, ColumnType, Component, InputPort, LibName, Need, Registry, TypeParameter};
use crate::resolver::ResolvedProgram;
use crate::types::{each_site_label, use_label};

/// [`CheckId::InstanceInputs`].
pub struct InstanceInputsCheck;

impl Check for InstanceInputsCheck {
    fn id(&self) -> CheckId {
        CheckId::InstanceInputs
    }

    fn cache_key(&self, at: &KeyInput<'_>) -> Option<CheckCacheKey> {
        Some(at.base(self.id()))
    }

    /// Refuses, in each `INIT` form of the form, each input that its
    /// component does not declare, each input written after another clause of
    /// the same input, each input that stands before an input of its
    /// group that the component declares before it, each input that
    /// writes no head site on a column of its port other than `key`, other
    /// than a column of an unbounded type parameter that no place of the form binds,
    /// and each input whose rows its component counts, a `Cardinality`
    /// instance's `member` input or an `Excess` instance's `plus` or `minus`
    /// input, whose head holds no site, and each input its component
    /// requires, and each `one-of` group of its component, that the form
    /// leaves with no row ([`left_needs`]), as
    /// `docs/arclog/arclog.md#instance` gives. In a keyed instance, it
    /// refuses as well each input that stands in a group other than its
    /// own: an input after the key clause that reads an output of its
    /// instance, where the key has a column, and a broadcast inside the key
    /// clause.
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
            let sites = binding_sites(instance, &component.inputs);
            let unit = unbound(&component.type_parameters, &sites);
            for (path, keyed, written_input) in inputs_at(instance) {
                if group != Some(keyed) {
                    group = Some(keyed);
                    latest = None;
                }
                let name = &written_input.name;
                let index = declared(name);
                let message = match index {
                    None => Some("the component declares no input of this name".to_owned()),
                    Some(_) if written.contains(&name) => Some("the input is written in another clause; a union is one clause whose body is an `OR`".to_owned()),
                    Some(index) if latest.is_some_and(|latest| index < latest) => {
                        Some("the input stands before an input of its group that the component declares before it".to_owned())
                    }
                    Some(_) => None,
                };
                let headless = index.and_then(|index| headless_column(&component.inputs[index], written_input, &unit));
                let counted_head = empty_counted_head(&instance.component, written_input).map(str::to_owned);
                latest = latest.max(index);
                written.push(name);
                let input_at = at.join(&path);
                let within = reads.iter().filter(|read| read.form == instance_at && read.at.0.starts_with(&input_at.0));
                let group = instance.key.as_ref().and_then(|key| group_fault(program, input.path, keyed, written_input, &key.value().key, within));
                let group = group.map(str::to_owned);
                for message in [message, headless, counted_head, group].into_iter().flatten() {
                    refusals.push((message, input_at.clone()));
                }
            }
            for message in left_needs(&component, &written, instance.key.as_ref().is_some_and(|key| !key.value().key.columns.is_empty())) {
                refusals.push((message, at.clone()));
            }
        }
        if refusals.is_empty() {
            return CheckResult::Pass;
        }
        result(refusals.into_iter().map(|(message, at)| Refusal { message: message.into(), at: input.refusal_path(&at) }).collect())
    }

    /// Refuses each refusal of [`Check::check`] at a complete input. A
    /// refusal of an input reads the input itself, the inputs written before
    /// it, the key clause, which stands before its inputs, and the
    /// component, so no node written after the input undoes it.
    fn check_prefix(&self, prefix: &Prefix<'_>) -> PrefixResult {
        super::prefix::settled(prefix, self)
    }
}

/// Why an `INIT` form of `component` that writes the inputs `written` is
/// refused where it leaves a need empty, one message for each input that
/// the component requires and the form leaves with no row for certain, and
/// each `one-of` group whose inputs the form leaves so, as
/// `docs/arclog/arclog.md#instance` gives. The decoder refuses the `SKIP`
/// that leaves such a need ([`crate::registry::Component::group_is_empty`],
/// [`crate::registry::InputPort::holds_no_row_unwritten`]), and a `DEMONSTRATED`
/// form is no `INIT` form, so it takes no such refusal. `key_has_column` is
/// whether the form's key has a column.
fn left_needs(component: &Component, written: &[&PortName], key_has_column: bool) -> Vec<String> {
    let mut messages = Vec::new();
    for input in component.inputs.iter() {
        if input.need == Some(Need::Required) && !written.contains(&&input.port.name) && input.holds_no_row_unwritten(key_has_column) {
            messages.push(format!(
                "the form writes no input {:?}, which its component requires and no key column fills: the input holds no row, and the component then gives no output",
                input.port.name.0
            ));
        }
    }
    for group in component.groups() {
        if component.group_is_empty(group, written, key_has_column) {
            messages.push(format!(
                "the form writes no input of the `one-of` group {:?} of its component, and no key column fills one: each input of the group holds no row, and the component then gives no output",
                group.0
            ));
        }
    }
    messages
}

/// Why `written`, an input of the port `port`, writes no head site on a
/// column it must cover, where it does not: the first column of the port other
/// than `key` that has no head site of the input, other than a column of a
/// type parameter in `unit`, which no place of the form binds, as
/// `docs/arclog/arclog.md#instance` gives. The evaluator reads the same
/// columns ([`crate::eval::init_form`]).
fn headless_column(port: &InputPort, written: &InstanceInput, unit: &[&TypeParameter]) -> Option<String> {
    let column = port.port.columns.iter().find(|column| must_have_site(column, unit) && !written.head.iter().any(|site| site.column == column.name))?;
    Some(format!("the input writes no head site on column {:?}", column.name))
}

/// The inputs whose rows their component counts, each by its component and
/// its name.
const COUNTED_INPUTS: [(&str, &str); 3] = [("Cardinality", "member"), ("Excess", "plus"), ("Excess", "minus")];

/// Why `written`, an input of an instance of `component`, is refused, where
/// it is an input of [`COUNTED_INPUTS`] whose head holds no site: such an
/// input holds at most one row at each key, so the count of its rows is 0
/// or 1 (`docs/arclog/arclog.md#instance`).
fn empty_counted_head(component: &LibName, written: &InstanceInput) -> Option<&'static str> {
    let counted = COUNTED_INPUTS.iter().any(|(name, port)| *name == &*component.0 && *port == &*written.name.0);
    (counted && written.head.is_empty()).then_some(
        "the head of a `Cardinality` instance's `member` input, or of an `Excess` instance's `plus` or `minus` input, holds a site, since such an input of no column holds at most one row at each key, so the count of its rows is 0 or 1",
    )
}

/// Whether an input must write a head site on `column`, a column of its
/// port, where `unit` holds the type parameters that no place of its form
/// binds: each column but `key` and a column of an unbounded parameter of
/// `unit`.
fn must_have_site(column: &Column, unit: &[&TypeParameter]) -> bool {
    let binds_nothing = matches!(&column.ty, ColumnType::Parameter(parameter) if parameter.bound.is_none() && unit.contains(&parameter));
    !is_key(column) && !binds_nothing
}

/// What the form's other nodes fix of the head of the input written last in
/// an `INIT` form, which the search of `Decoder::completes_projection` reads
/// before it writes the head.
#[derive(Clone, Debug)]
pub struct HeadNeeds {
    /// For each column of the input's port, in the port's order, whether the
    /// head must hold a site on it in every completion.
    ///
    /// [`headless_column`] refuses a head with no site on a column for which
    /// [`must_have_site`] holds. That predicate reads the column and `unit`,
    /// the parameters onto which no place of the form projects. A site
    /// written later in the head, or in a later input, makes a place of the
    /// form project onto its parameter, and no node removes one, so `unit`
    /// of a completion is a subset of `unit` of the form as it stands. A
    /// column that must have a site at the form as it stands must have one in
    /// each completion, and a head that closes the column with no site is
    /// refused in each completion, whatever sites follow. A column of an
    /// unbounded parameter that `unit` holds is marked as one that needs
    /// no site, since a site on another column of that parameter, written
    /// later, makes it need one.
    pub required: Vec<bool>,
    /// The labels of the key body, where the input stands in the key clause
    /// and the form's other nodes leave it a broadcast: its body names no
    /// label of the key body and reads no output of any instance, so
    /// [`group_fault`] refuses it unless a label of its head is one of these.
    /// None where its body names such a label or reads such an output, or
    /// where it stands outside the key clause.
    ///
    /// [`group_fault`] reads the labels of the input's body and of its head
    /// sites against the labels of the key body, and the reads of the input's
    /// atoms for an output of the instance. A head label is the only
    /// reading that the head adds. The body's labels are those the form
    /// holds, and no node written after the body changes them. A body that
    /// reads no output of any instance reads none of its own instance's.
    pub key_labels: Option<Vec<LabelId>>,
}

/// The needs of the head of the input written last in `form`, where `form`
/// is an `INIT` form whose component declares the input; none otherwise.
pub fn head_needs(registry: &Registry, form: &Form) -> Option<HeadNeeds> {
    let Form::Instance(instance) = form else { return None };
    let instance = instance.value();
    let component = component(registry, &instance.component)?;
    let (_, keyed, written) = inputs_at(instance).into_iter().last()?;
    let port = component.inputs.iter().find(|declared| declared.port.name == written.name)?;
    let sites = binding_sites(instance, &component.inputs);
    let unit = unbound(&component.type_parameters, &sites);
    let required = port.port.columns.iter().map(|column| must_have_site(column, &unit)).collect();
    let key_labels = instance.key.as_ref().filter(|_| keyed).and_then(|key| {
        let key_labels = body_labels(key.value().key.body.value());
        let named_in_body = body_labels(written.body.value());
        let mut reads_output = false;
        each_node(NodeRef::Body(written.body.value()), &NodePath::default(), &mut |node, _| {
            let NodeRef::Conjunct(conjunct) = node else { return };
            let Some(atom) = conjunct.atom() else { return };
            reads_output |= matches!(&atom.value().relation, RelationRef::Output(OutputName { of: OutputOwner::Instance(_), .. }));
        });
        if reads_output || named_in_body.iter().any(|label| key_labels.contains(label)) {
            return None;
        }
        let mut labels: Vec<LabelId> = key_labels.into_iter().collect();
        labels.sort_by_key(|label| label.0);
        Some(labels)
    });
    Some(HeadNeeds { required, key_labels })
}

/// Why `written`, an input of an instance whose key is `key`, stands in the
/// wrong group, where it does, from `reads`, the reads of its body, each at
/// its path relative to the form at `form` in the program, as
/// `docs/arclog/arclog.md#instance` gives: an input after the key clause
/// that reads an output of its instance, and an input inside it that reads
/// no key label and no output of its instance, a broadcast. A key of no column
/// has one key, so each of its inputs stands after the key clause, and none
/// is in the wrong group. A label at a head site of the input is a read of
/// it, and so is a label of its body, a key site's labels included.
fn group_fault<'a>(
    program: &ResolvedProgram,
    form: &NodePath,
    keyed: bool,
    written: &InstanceInput,
    key: &KeyBody,
    reads: impl Iterator<Item = &'a FormRead<'a>>,
) -> Option<&'static str> {
    let key_labels = body_labels(key.body.value());
    let mut reads_output = false;
    for read in reads {
        let Some((_, own)) = read.node(program, form) else { continue };
        reads_output |= own;
    }
    let mut reads_key = body_labels(written.body.value()).iter().any(|label| key_labels.contains(label));
    for site in written.head.iter() {
        each_site_label(site, &mut Vec::new(), &mut |use_, _| reads_key |= use_label(use_).is_some_and(|label| key_labels.contains(&label)));
    }
    match keyed {
        false if reads_output && !key.columns.is_empty() => Some("the input reads an output of its instance and stands after the key clause, where only a broadcast stands"),
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
