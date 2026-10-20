//! The safety check, and the bodies of a form with their paths, which
//! the check of the labels that `=` makes and that an `OR` or an `IF`
//! exports and the type inference's scope of a form read too.

use super::reads::forms_within;
use super::types::result;
use super::{Check, CheckId, CheckInput, CheckResult, LabelInScope, Prefix, PrefixResult, Refusal, CheckCacheKey, KeyInput};
use crate::eval::ir::atom_modes;
use crate::safety::{body_labels, conjunct_labels, each_label_use_at, bound_labels, list_of, parts_of};
use crate::hash::StableHashSet;
use crate::program::canonical::{CanonicalOrder, SearchBudget};
use crate::program::path::{node_at, NodePath, NodeRef};
use crate::program::{
    Body, ChoosePart, Conjunct, DemonstratedPart, Form, InstanceInput, InstanceInputPart, InstancePart, KeyClause, KeyClausePart, LabelId, LabelUse,
    Node, RelationColumn, RigidDetPart,
};
use crate::resolver::column_sources;
use crate::resolver::form_columns;
use crate::registry::Registry;
use crate::types::{use_label, ValueType};

/// [`CheckId::Safety`].
pub struct SafetyCheck;

impl Check for SafetyCheck {
    fn id(&self) -> CheckId {
        CheckId::Safety
    }

    /// The base key with the form's canonical form followed by the written
    /// order of each list of the form, since the check reads each list in
    /// its written order.
    fn cache_key(&self, at: &KeyInput<'_>) -> Option<CheckCacheKey> {
        let canonical_form = super::with_written_order(at.form, at.canonical, at.order);
        Some(CheckCacheKey { check: self.id(), canonical_form, signatures: at.signatures.into() })
    }

    /// Refuses each label of a body of the form that the body leaves
    /// unbound: one pass over each list in its written order, each prefix
    /// bound by [`crate::safety::bound_labels`], with the modes of
    /// the algebra relations and relation macros. A label is refused at its first use
    /// in the body, or at the site of an atom that no mode of its relation
    /// binds from the conjuncts written before it, or at a `NOT` or an
    /// `ALL` written before the conjuncts that bind its outer label.
    fn check(&self, input: &CheckInput<'_>) -> CheckResult {
        let registry = input.scope.registry;
        let mut refused: Vec<(&'static str, NodePath)> = Vec::new();
        for form_body in form_bodies(input.form) {
            let scope = label_scope(input.scope.labels, &form_body.at);
            let types = |label: LabelId| scope.iter().find(|entry| entry.label == label).and_then(|entry| entry.ty.clone());
            let walk = Walk { registry, types: &types };
            refused.extend(walk.refusals(&form_body));
        }
        if refused.is_empty() {
            return CheckResult::Pass;
        }
        let order = CanonicalOrder::of(input.form, &mut SearchBudget::new());
        result(refused.into_iter().map(|(message, at)| Refusal { message: message.into(), at: order.canonical_path(&at) }).collect())
    }

    fn check_prefix(&self, prefix: &Prefix<'_>) -> PrefixResult {
        super::prefix::settled(prefix, self)
    }
}

/// One body of a form: a clause's, a key clause's, an instance input's, or
/// one of a `CHOOSE` or a `RIGID_DET` form, with what its context gives it.
pub(super) struct FormBody<'a> {
    /// The body's path relative to the top-level form.
    pub at: NodePath,
    pub body: &'a Node<Body>,
    pub place: BodyPlace<'a>,
    /// The labels the body reads bound from its context: the key's
    /// labels for a keyed input or an instance clause, and the row's and
    /// the candidate's for a `never` clause.
    pub given: Vec<LabelId>,
    /// The labels of the columns that the body gives. A clause of no
    /// conjuncts, as a case's reading of a `DET_OR_RULE` or `RULE_OR_DET`
    /// line takes it, gives its columns from its proposers or from its
    /// stored parameter (`docs/arclog/arclog.md#the-alts-form`), and its
    /// body gives none.
    pub columns: Vec<LabelId>,
    /// The labels of the fields of the `DEMO_RULE` whose scope the body's
    /// form stands in, which its forms read.
    pub fields: Vec<LabelId>,
}

/// Where a body stands in the scope of its form.
pub(super) enum BodyPlace<'a> {
    /// In the form's own list, with the form's other bodies of this place.
    List,
    /// In a branch of its own, as a `never` clause.
    Branch,
    /// In a branch of its own, after the head of the instance input whose
    /// body it is, at its path relative to the top-level form.
    Input(&'a InstanceInput, NodePath),
}

impl FormBody<'_> {
    /// The head of the instance input whose body this is, at its path
    /// relative to the top-level form.
    pub fn head(&self) -> Option<(&InstanceInput, &NodePath)> {
        match &self.place {
            BodyPlace::Input(input, at) => Some((input, at)),
            BodyPlace::List | BodyPlace::Branch => None,
        }
    }

    /// The labels that stand outside the body in its context: those
    /// [`FormBody::given`], [`FormBody::columns`] and [`FormBody::fields`]
    /// hold, and the labels of the input's head.
    fn outside(&self) -> StableHashSet<LabelId> {
        let mut outside: StableHashSet<LabelId> = self.given.iter().chain(&self.columns).chain(&self.fields).copied().collect();
        if let Some((input, at)) = self.head() {
            each_head_use(input, at, &mut |_, use_| outside.extend(use_label(use_)));
        }
        outside
    }
}

/// Each body of `form` and of each form of a `DEMO_RULE` it holds, in the
/// order of their paths.
pub(super) fn form_bodies(form: &Form) -> Vec<FormBody<'_>> {
    let mut out = Vec::new();
    for (at, node) in forms_within(form) {
        let fields = match at.0.split_last() {
            Some((_, parent)) => match node_at(NodeRef::from(form), &NodePath(parent.into())) {
                Some(NodeRef::DemoRule(rule)) => labels(&rule.fields),
                _ => Vec::new(),
            },
            None => Vec::new(),
        };
        out.extend(bodies(node).into_iter().map(|body| FormBody { at: at.join(&body.at), place: match body.place {
                BodyPlace::Input(input, head) => BodyPlace::Input(input, at.join(&head)),
                place => place,
            },
            fields: fields.clone(), ..body }));
    }
    out
}

/// The bodies of the form `form`, in the order of their paths, each at its
/// path relative to `form`. The key clause and its labels are those
/// [`column_sources::key_clause`] gives, and the columns of a clause's body and of
/// a `CHOOSE` form's `from` those [`form_columns::form_columns`] gives after the
/// key's.
pub(super) fn bodies(form: NodeRef<'_>) -> Vec<FormBody<'_>> {
    let at = NodePath::default();
    let key = column_sources::key_clause(form);
    let key_labels = key.as_ref().map(|(key, _)| labels(&key.columns)).unwrap_or_default();
    let own_columns = || form_columns::form_columns(form).skip(key_labels.len()).map(|column| column.label).collect::<Vec<_>>();
    let mut out: Vec<FormBody<'_>> = key.iter().map(|(key, body)| plain(&key.body, body.clone(), &[], key_labels.clone())).collect();
    match form {
        NodeRef::Clause(clause) => {
            let columns = if clause.body.value().conjuncts.is_empty() { Vec::new() } else { own_columns() };
            out.push(plain(&clause.body, at.child(0), &[], columns));
        }
        NodeRef::Instance(instance) => {
            let key = instance.key.as_ref().map(|key| (key, at.child(instance.position(InstancePart::Key))));
            let inputs = instance.inputs.iter().enumerate().map(|(index, input)| (input, at.child(instance.position(InstancePart::Input(index)))));
            keyed_inputs(key, inputs, &key_labels, &mut out);
        }
        NodeRef::Demonstrated(demonstrated) => {
            let key = demonstrated.key.as_ref().map(|key| (key, at.child(demonstrated.position(DemonstratedPart::Key))));
            let inputs = demonstrated.inputs.iter().enumerate();
            let inputs = inputs.map(|(index, input)| (input, at.child(demonstrated.position(DemonstratedPart::Input(index)))));
            keyed_inputs(key, inputs, &key_labels, &mut out);
        }
        NodeRef::Choose(choose) => {
            let candidate = own_columns();
            let from_given = if choose.from_inside_for { key_labels.clone() } else { Vec::new() };
            out.push(plain(&choose.from, at.child(choose.position(ChoosePart::From)), &from_given, candidate.clone()));
            let never_given: Vec<LabelId> = key_labels.iter().chain(&candidate).copied().collect();
            for (index, never) in choose.never.iter().enumerate() {
                let never_at = at.child(choose.position(ChoosePart::Never(index)));
                out.push(FormBody { place: BodyPlace::Branch, ..plain(never, never_at, &never_given, Vec::new()) });
            }
        }
        NodeRef::RigidDet(rigid) => {
            if let Some(clause) = &rigid.instance {
                out.push(plain(&clause.body, at.child(rigid.position(RigidDetPart::Instance)), &key_labels, labels(&clause.columns)));
            }
        }
        _ => {}
    }
    out
}

fn labels(columns: &[RelationColumn]) -> Vec<LabelId> {
    columns.iter().map(|column| column.label).collect()
}

fn plain<'a>(body: &'a Node<Body>, at: NodePath, given: &[LabelId], columns: Vec<LabelId>) -> FormBody<'a> {
    FormBody { at, body, place: BodyPlace::List, given: given.to_vec(), columns, fields: Vec::new() }
}

/// Pushes onto `out` the inputs of an `INIT` or a `DEMONSTRATED` form, the
/// key clause `key` and the inputs `inputs` after it each with its path
/// below the form: each keyed input, with `key_labels`, the labels of the
/// key, given, and each other input.
fn keyed_inputs<'a>(
    key: Option<(&'a Node<KeyClause>, NodePath)>,
    inputs: impl Iterator<Item = (&'a Node<InstanceInput>, NodePath)>,
    key_labels: &[LabelId],
    out: &mut Vec<FormBody<'a>>,
) {
    let input = |input: &'a Node<InstanceInput>, input_at: NodePath, given: &[LabelId]| FormBody {
        at: input_at.child(input.value().position(InstanceInputPart::Body)),
        body: &input.value().body,
        place: BodyPlace::Input(input.value(), input_at),
        given: given.to_vec(),
        columns: Vec::new(),
        fields: Vec::new(),
    };
    if let Some((key, key_at)) = key {
        for (index, keyed) in key.value().inputs.iter().enumerate() {
            out.push(input(keyed, key_at.child(key.value().position(KeyClausePart::Input(index))), key_labels));
        }
    }
    for (other, other_at) in inputs {
        out.push(input(other, other_at, &[]));
    }
}

/// The entries of `labels` of the label scope that holds the body at
/// `at`: the scope whose form's path is the longest prefix of `at`.
pub(super) fn label_scope<'l>(labels: &'l [LabelInScope], at: &NodePath) -> Vec<&'l LabelInScope> {
    let holds = |entry: &&LabelInScope| at.0.starts_with(&entry.scope.0);
    let Some(depth) = labels.iter().filter(holds).map(|entry| entry.scope.0.len()).max() else { return Vec::new() };
    labels.iter().filter(holds).filter(|entry| entry.scope.0.len() == depth).collect()
}

/// Visits each label use at the head sites of `input`, at `at`.
pub(super) fn each_head_use(input: &InstanceInput, at: &NodePath, visit: &mut dyn FnMut(&NodePath, LabelUse)) {
    for (site, index) in input.head.iter().zip(0u32..) {
        each_label_use_at(NodeRef::Site(site), &at.child(index), visit);
    }
}

/// Each label that stands in the conjuncts of `list`, at any depth.
fn list_labels<'c>(list: impl IntoIterator<Item = &'c Conjunct>) -> StableHashSet<LabelId> {
    let mut labels = StableHashSet::default();
    list.into_iter().for_each(|conjunct| conjunct_labels(conjunct, &mut labels));
    labels
}

struct Walk<'a> {
    registry: &'a Registry,
    types: &'a dyn Fn(LabelId) -> Option<ValueType>,
}

impl Walk<'_> {
    /// The refusals of `form_body`, each label once, at the first place
    /// that refuses it.
    fn refusals(&self, form_body: &FormBody<'_>) -> Vec<(&'static str, NodePath)> {
        let given: StableHashSet<LabelId> = form_body.given.iter().copied().collect();
        let outside = form_body.outside();
        let mut found = Vec::new();
        self.ordered(&list_of(form_body.body.value(), &form_body.at), &given, &outside, &mut found);
        let bound = bound_labels(form_body.body.value(), &given, &outside, &|atom| atom_modes(self.registry, atom), self.types);
        let mut check_use = |at: &NodePath, use_: LabelUse| {
            if let Some(label) = use_label(use_).filter(|label| !bound.contains(label)) {
                found.push((label, "the body leaves the label unbound", at.clone()));
            }
        };
        each_label_use_at(NodeRef::Body(form_body.body.value()), &form_body.at, &mut check_use);
        if let Some((input, at)) = form_body.head() {
            each_head_use(input, at, &mut check_use);
        }
        let held = body_labels(form_body.body.value());
        for &label in form_body.columns.iter().filter(|label| !bound.contains(label) && !held.contains(label)) {
            found.push((label, "the body leaves the label of a column unbound", form_body.at.clone()));
        }
        let mut seen = StableHashSet::default();
        found.into_iter().filter(|(label, _, _)| seen.insert(*label)).map(|(_, message, at)| (message, at)).collect()
    }

    /// The labels that the conjuncts of `list` bind from `given`, with
    /// `outside` the labels that stand outside them.
    fn bind(&self, list: &[(NodePath, &Conjunct)], given: &StableHashSet<LabelId>, outside: &StableHashSet<LabelId>) -> StableHashSet<LabelId> {
        let body = Body { conjuncts: list.iter().map(|(_, conjunct)| (*conjunct).clone()).collect() };
        bound_labels(&body, given, outside, &|atom| atom_modes(self.registry, atom), self.types)
    }

    /// Pushes onto `found` each label that `list`, in its written order,
    /// uses before the conjuncts written before it bind it, from `given`,
    /// with `outside` the labels that stand outside `list`, and so for the
    /// parts of each of its forms.
    fn ordered(&self, list: &[(NodePath, &Conjunct)], given: &StableHashSet<LabelId>, outside: &StableHashSet<LabelId>, found: &mut Vec<(LabelId, &'static str, NodePath)>) {
        for (i, (at, conjunct)) in list.iter().enumerate() {
            let mut from = outside.clone();
            from.extend(list_labels(list[i..].iter().map(|(_, conjunct)| *conjunct)));
            let before = self.bind(&list[..i], given, &from);
            let mut around = outside.clone();
            around.extend(list_labels(list.iter().enumerate().filter(|&(k, _)| k != i).map(|(_, (_, conjunct))| *conjunct)));
            match conjunct {
                Conjunct::Atom(atom) if !atom_modes(self.registry, atom.value()).is_empty() => {
                    let mut after_outside = outside.clone();
                    after_outside.extend(list_labels(list[i + 1..].iter().map(|(_, conjunct)| *conjunct)));
                    let after = self.bind(&list[..=i], given, &after_outside);
                    each_label_use_at(NodeRef::Conjunct(conjunct), at, &mut |path, use_| {
                        if let Some(label) = use_label(use_).filter(|label| !after.contains(label)) {
                            found.push((label, "no mode of the atom's relation has its columns bound by the conjuncts written before it", path.clone()));
                        }
                    });
                }
                Conjunct::Not(_) | Conjunct::All { .. } => {
                    each_label_use_at(NodeRef::Conjunct(conjunct), at, &mut |path, use_| {
                        if let Some(label) = use_label(use_).filter(|label| around.contains(label) && !before.contains(label)) {
                            found.push((label, "the `NOT` or the `ALL` stands before the conjuncts that bind the label", path.clone()));
                        }
                    });
                }
                _ => {}
            }
            let parts = parts_of(conjunct, at);
            for (j, part) in parts.iter().enumerate() {
                let mut part_outside = around.clone();
                part_outside.extend(list_labels(parts.iter().enumerate().filter(|&(k, _)| k != j).flat_map(|(_, other)| other.iter().map(|(_, conjunct)| *conjunct))));
                self.ordered(part, &before, &part_outside, found);
            }
        }
    }
}
