//! The safety check, and the bodies of a form with their paths, which
//! the check of the labels that `=` makes and that an `OR` or an `IF`
//! exports and the type inference's scope of a form read too.

use super::reads::forms_within;
use super::types::result;
use super::prefix::{refused, whole};
use super::{Check, CheckId, CheckInput, CheckResult, LabelInScope, Prefix, PrefixResult, Refusal, CheckCacheKey, KeyInput};
use crate::eval::ir::atom_modes;
use crate::safety::{conjunct_labels, each_label_use_at, bound_labels, conjunct_label_set, LabelCounts, list_of, mode_holds, mode_may_hold, orientation_labels, parts_of};
use std::cell::RefCell;

use crate::hash::{StableHashMap, StableHashSet};
use crate::program::canonical::{CanonicalOrder, SearchBudget};
use crate::program::path::{node_at, NodePath, NodeRef};
use crate::program::{
    Atom, Body, ChoosePart, Conjunct, DemonstratedPart, Form, InstanceInput, InstanceInputPart, InstancePart, KeyClause, KeyClausePart, LabelId, LabelUse,
    Negated, Node, RelationColumn, RigidDetPart,
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

    /// Refuses each label of a body of the form, and of each part of a
    /// `RIGID_DET` form read as a body of its atom, that the
    /// body leaves unbound, and each positive atom and each negated atom of an algebra
    /// relation with modes at which no mode holds from the conjuncts written before it: one pass over each list in its written order, each prefix
    /// bound by [`crate::safety::bound_labels`], with the modes of
    /// the algebra relations and relation macros. A label is refused at its first use
    /// in the body, or at the site of an atom that no mode of its relation
    /// binds from the conjuncts written before it, or at that atom itself, or at a `NOT` or an
    /// `ALL` written before the conjuncts that bind its outer label.
    fn check(&self, input: &CheckInput<'_>) -> CheckResult {
        let refused = self.found(input, &|_, _| true);
        if refused.is_empty() {
            return CheckResult::Pass;
        }
        let order = CanonicalOrder::of(input.form, &mut SearchBudget::new());
        result(refused.into_iter().map(|found| Refusal { message: found.fault.message().into(), at: order.canonical_path(&found.at) }).collect())
    }

    /// Refuses at each refusal of [`SafetyCheck::check`] on the partial form
    /// that no completion of the prefix undoes, as `Fault::stands` gives
    /// it for each kind of refusal, at the refusal's source path.
    ///
    /// The refusal of an atom, and the refusal of a `NOT` or an `ALL`
    /// written before the conjuncts that bind its label, stand at a complete
    /// node, as `super::prefix::settled` keeps them: the conjuncts before
    /// that atom, `NOT` or `ALL` are complete, and a node written later adds
    /// labels outside them, which makes a label local to the branches of an
    /// `OR` among them an outer label, and so binds no more labels before it
    /// (the rule of [`crate::safety::bound_labels`] on labels local to a
    /// part).
    fn check_prefix(&self, prefix: &Prefix<'_>) -> PrefixResult {
        let found = self.found(&whole(prefix), &|fault, at| fault.stands(prefix, at));
        refused(found.into_iter().map(|found| Refusal { message: found.fault.message().into(), at: found.at }).collect())
    }
}

impl SafetyCheck {
    /// The refusals of the safety check on the form of `input`, at their
    /// source paths, that `keep` keeps, each label refused once at the first
    /// place of those that `keep` keeps.
    fn found(&self, input: &CheckInput<'_>, keep: &dyn Fn(&Fault, &NodePath) -> bool) -> Vec<Found> {
        let registry = input.scope.registry;
        let bodies = form_bodies(input.form);
        let parts = part_bodies(input.form);
        let mut readings: Vec<Reading<'_>> = bodies.iter().map(Reading::of_body).chain(parts.iter().map(Reading::of_part)).collect();
        readings.sort_by(|a, b| a.at.cmp(b.at));
        let mut refused = Vec::new();
        for reading in &readings {
            let scope = label_scope(input.scope.labels, reading.at);
            let types = |label: LabelId| scope.iter().find(|entry| entry.label == label).and_then(|entry| entry.ty.clone());
            let walk = Walk { registry, types: &types, memo: input.scope.bound };
            refused.extend(walk.refusals(reading, keep));
        }
        refused
    }
}

/// Binding constraints for a mutation domain. Edits keep label ids, heads,
/// scopes and types; this is the same whole-form walk as `SafetyCheck`, not
/// an approximation based on the presence of a fresh marker.
pub(crate) fn mutation_bindings(
    form: &Form,
    top: &NodePath,
    types: &crate::types::ProgramTypes,
    registry: &Registry,
) -> Vec<(&'static str, String)> {
    let bodies = form_bodies(form);
    let parts = part_bodies(form);
    let readings: Vec<_> = bodies.iter().map(Reading::of_body).chain(parts.iter().map(Reading::of_part)).collect();
    let mut errors = Vec::new();
    for reading in &readings {
        let scope = top.join(reading.at);
        let label_type = |label| mutation_label_type(types, &scope, label);
        let walk = Walk { registry, types: &label_type, memo: None };
        for found in walk.refusals(reading, &|_,_| true) {
            let reason = match found.fault {
                Fault::Unbound {..} => "unbound_label",
                Fault::ColumnUnbound {..} => "unbound_column",
                Fault::NoMode {..} | Fault::AtomNoMode => "mode",
                Fault::Misordered => "misordered",
            };
            errors.push((reason, format!("{:?} label {:?}: {}", top.join(&found.at), found.label, found.fault.message())));
        }
    }
    errors
}

fn mutation_label_type(types: &crate::types::ProgramTypes, scope: &NodePath, label: LabelId) -> Option<ValueType> {
    (1..=scope.0.len()).rev().find_map(|n| types.form(&NodePath(scope.0[..n].into())))?.label(label).cloned()
}

/// For deletion-only search, loss of a required head/key/input label cannot
/// be repaired by deleting more atoms. Branch-local uses can disappear
/// together, so they are deliberately not used for this partial-state prune.
pub(crate) fn deletion_preserves_columns(form: &Form, top: &NodePath, types: &crate::types::ProgramTypes, registry: &Registry) -> bool {
    form_bodies(form).iter().all(|body| {
        let outside = body.outside();
        let given = body.given.iter().copied().collect();
        let scope = top.join(&body.at);
        let bound = bound_labels(&body.body.value().conjuncts.iter().collect::<Vec<_>>(), &given, &outside,
            &|atom| atom_modes(registry, atom), &|label| mutation_label_type(types, &scope, label));
        outside.iter().all(|label| bound.contains(label))
    })
}

/// A refusal of the safety check at a source path: the label it is about,
/// where it is about one, why it refuses, and where.
struct Found {
    label: Option<LabelId>,
    fault: Fault,
    at: NodePath,
}

/// Why the safety check refuses, with what decides whether a completion of
/// a prefix undoes it.
enum Fault {
    /// A label used in the body at `body` that the body leaves unbound. A
    /// conjunct written later in the body can bind it.
    Unbound { body: NodePath },
    /// The label of a column of the form that the body at `body` leaves
    /// unbound. A conjunct written later in the body can bind it.
    ColumnUnbound { body: NodePath },
    /// A label at a site of the atom at `atom`, which no mode of its relation
    /// binds from the conjuncts written before it. `completes` is whether
    /// some mode holds where each column at which the atom has no site yet
    /// counts as bound, as [`mode_may_hold`] gives it: a site written later
    /// can bind such a column.
    NoMode { atom: NodePath, completes: bool },
    /// The atom, which no mode of its relation holds at, from the conjuncts
    /// written before it.
    AtomNoMode,
    /// A label at a `NOT` or an `ALL` written before the conjuncts that bind
    /// it.
    Misordered,
}

impl Fault {
    fn message(&self) -> &'static str {
        match self {
            Fault::Unbound { .. } => "the body leaves the label unbound",
            Fault::ColumnUnbound { .. } => "the body leaves the label of a column unbound",
            Fault::NoMode { .. } => "no mode of the atom's relation has its columns bound by the conjuncts written before it",
            Fault::AtomNoMode => "no mode of the atom's relation has its columns written and bound by the conjuncts written before it",
            Fault::Misordered => "the `NOT` or the `ALL` stands before the conjuncts that bind the label",
        }
    }

    /// Whether no completion of `prefix` undoes the refusal, found at `at`:
    /// a refusal that reads the whole body stands once that body is
    /// complete, and one at a site of an atom stands once the atom is
    /// complete, or while it is open, where no mode holds even with the
    /// columns that the atom has no site at bound. The other refusals
    /// stand where the node at `at` is complete.
    fn stands(&self, prefix: &Prefix<'_>, at: &NodePath) -> bool {
        match self {
            Fault::Unbound { body } | Fault::ColumnUnbound { body } => !prefix.is_open(body),
            Fault::NoMode { atom, completes } => !prefix.is_open(atom) || !completes,
            Fault::AtomNoMode | Fault::Misordered => !prefix.is_open(at),
        }
    }
}

/// One body of a form: a clause's, a key clause's, an instance input's, or
/// one of a `CHOOSE` or a `RIGID_DET` form, with what its context gives it.
pub(crate) struct FormBody<'a> {
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
pub(crate) enum BodyPlace<'a> {
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
    pub(crate) fn outside(&self) -> StableHashSet<LabelId> {
        let mut outside: StableHashSet<LabelId> = self.given.iter().chain(&self.columns).chain(&self.fields).copied().collect();
        if let Some((input, at)) = self.head() {
            each_head_use(input, at, &mut |_, use_| outside.extend(use_label(use_)));
        }
        outside
    }
}

/// Each body of `form` and of each form of a `DEMO_RULE` it holds, in the
/// order of their paths.
pub(crate) fn form_bodies(form: &Form) -> Vec<FormBody<'_>> {
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

/// A part of a `RIGID_DET` form, read as a body of its atom alone: the
/// evaluator compiles each part as a clause of its own, the key's body, the
/// instance's body other than for a frame part, and the part's atom, so the
/// part reads no label that another part makes
/// (`docs/arclog/rigid.md#form`).
struct PartBody {
    /// The part's path relative to the top-level form.
    at: NodePath,
    atom: Conjunct,
    /// The labels the part reads bound from the key and instance clauses:
    /// the key's, and the instance's other than for a frame part.
    given: Vec<LabelId>,
    /// The labels of the clause's columns: those in `given`, and then the
    /// part's own, as `Assembly::columns` gives them.
    columns: Vec<LabelId>,
}

/// The parts of each `RIGID_DET` form of `form` and of each form of a
/// `DEMO_RULE` it holds, in the order of their paths.
fn part_bodies(form: &Form) -> Vec<PartBody> {
    let mut out = Vec::new();
    for (at, node) in forms_within(form) {
        let NodeRef::RigidDet(rigid) = node else { continue };
        let key = rigid.key.iter().flat_map(|key| labels(&key.columns)).collect::<Vec<_>>();
        let instance = rigid.instance.iter().flat_map(|instance| labels(&instance.columns)).collect::<Vec<_>>();
        for (index, atom) in rigid.parts.iter().enumerate() {
            let frame = form_columns::is_frame_part(rigid, atom.value());
            let given: Vec<LabelId> = key.iter().copied().chain(instance.iter().copied().filter(|_| !frame)).collect();
            let columns = given.iter().copied().chain(form_columns::part_labels(rigid, atom.value())).collect();
            out.push(PartBody { at: at.child(rigid.position(RigidDetPart::Part(index))), atom: Conjunct::Atom(atom.clone()), given, columns });
        }
    }
    out
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

/// The labels that the conjuncts written before a point of a list bind,
/// kept for the programs that differ from one another in the conjuncts
/// from that point on: a run of the walk over such a program reads the
/// bindings of the prefixes of conjuncts that all programs hold alike.
#[derive(Default, Debug)]
pub(super) struct BoundCache {
    bound: RefCell<StableHashMap<BoundKey, StableHashSet<LabelId>>>,
}

/// What the labels that a prefix of a list binds read: the prefix, which
/// its last conjunct's path and its length give where each of its
/// conjuncts is the state's; the labels given to the list; of the labels
/// outside it, those that the parts of its forms hold; and the labels of
/// the prefix whose type is an orientation.
#[derive(PartialEq, Eq, Hash, Debug)]
struct BoundKey {
    last: NodePath,
    len: usize,
    given: Vec<LabelId>,
    outside: Vec<LabelId>,
    orientation: Vec<LabelId>,
}

/// A [`BoundCache`] with the form in progress at the state of the mask
/// whose candidates share it.
#[derive(Clone, Copy, Debug)]
pub(super) struct BoundMemo<'a> {
    pub cache: &'a BoundCache,
    pub state: &'a Form,
}

fn sorted(labels: impl IntoIterator<Item = LabelId>) -> Vec<LabelId> {
    let mut sorted: Vec<LabelId> = labels.into_iter().collect();
    sorted.sort_by_key(|label| label.0);
    sorted
}

/// Whether `a` and `b` are one conjunct, label for label.
fn same_conjunct(a: &Conjunct, b: &Conjunct) -> bool {
    let atom = |a: &Atom, b: &Atom| std::ptr::eq(a, b) || (a.relation == b.relation && a.sites[..] == b.sites[..]);
    match (a, b) {
        (Conjunct::Atom(a), Conjunct::Atom(b)) | (Conjunct::Not(Negated::Atom(a)), Conjunct::Not(Negated::Atom(b))) => atom(a.value(), b.value()),
        (Conjunct::Not(Negated::Form(a)), Conjunct::Not(Negated::Form(b))) => same_conjunct(a, b),
        (Conjunct::Constraint(a), Conjunct::Constraint(b)) => a == b,
        (Conjunct::Or(a), Conjunct::Or(b)) => a.len() == b.len() && a.iter().zip(b.iter()).all(|(a, b)| same_body(a, b)),
        (Conjunct::If { test: t, then: n, otherwise: o }, Conjunct::If { test: t2, then: n2, otherwise: o2 }) => same_body(t, t2) && same_body(n, n2) && same_body(o, o2),
        (Conjunct::All { domain: d, body: b }, Conjunct::All { domain: d2, body: b2 }) => same_body(d, d2) && same_body(b, b2),
        _ => false,
    }
}

fn same_body(a: &Node<Body>, b: &Node<Body>) -> bool {
    std::ptr::eq(a.value(), b.value()) || (a.value().conjuncts.len() == b.value().conjuncts.len() && a.value().conjuncts.iter().zip(b.value().conjuncts.iter()).all(|(a, b)| same_conjunct(a, b)))
}

/// The prefixes of a list, grown conjunct by conjunct, that the memo
/// serves: the labels the key reads, kept as the prefix grows, while each
/// conjunct of the prefix is the conjunct at its path of the memo's state.
struct Prefixes<'l, 'c> {
    list: &'l [(NodePath, &'c Conjunct)],
    sets: &'l [StableHashSet<LabelId>],
    /// The number of conjuncts the labels below cover.
    len: usize,
    /// Whether each of the first `len` conjuncts is the state's.
    alike: bool,
    /// The labels that the parts of the forms of the prefix hold.
    parts: StableHashSet<LabelId>,
    orientation: StableHashSet<LabelId>,
}

impl<'l, 'c> Prefixes<'l, 'c> {
    fn new(list: &'l [(NodePath, &'c Conjunct)], sets: &'l [StableHashSet<LabelId>]) -> Self {
        Prefixes { list, sets, len: 0, alike: true, parts: StableHashSet::default(), orientation: StableHashSet::default() }
    }

    /// The key of the prefix of `end` conjuncts, where it is the state's.
    fn key(&mut self, walk: &Walk<'_>, memo: BoundMemo<'_>, end: usize, given: &StableHashSet<LabelId>, outside: &StableHashSet<LabelId>) -> Option<BoundKey> {
        while self.alike && self.len < end {
            let (at, conjunct) = &self.list[self.len];
            self.alike = matches!(node_at(NodeRef::from(memo.state), at), Some(NodeRef::Conjunct(state)) if same_conjunct(state, conjunct));
            if self.alike {
                if matches!(conjunct, Conjunct::Or(_) | Conjunct::If { .. } | Conjunct::All { .. } | Conjunct::Not(Negated::Form(_))) {
                    self.parts.extend(self.sets[self.len].iter().copied());
                }
                self.orientation.extend(self.sets[self.len].iter().copied().filter(|&label| (walk.types)(label).as_ref().is_some_and(|ty| ty.orientation_types().is_some())));
            }
            self.len += 1;
        }
        let served = self.alike && end > 0 && end == self.len;
        served.then(|| BoundKey {
            last: self.list[end - 1].0.clone(),
            len: end,
            given: sorted(given.iter().copied()),
            outside: sorted(outside.iter().copied().filter(|label| self.parts.contains(label))),
            orientation: sorted(self.orientation.iter().copied()),
        })
    }
}

/// What the walk reads as one body: its conjuncts with their paths, at the
/// body's path, with what its context gives it.
struct Reading<'a> {
    at: &'a NodePath,
    list: Vec<(NodePath, &'a Conjunct)>,
    given: &'a [LabelId],
    /// The labels that stand outside the list.
    outside: StableHashSet<LabelId>,
    columns: &'a [LabelId],
    head: Option<(&'a InstanceInput, &'a NodePath)>,
}

impl<'a> Reading<'a> {
    fn of_body(form_body: &'a FormBody<'_>) -> Self {
        Reading {
            at: &form_body.at,
            list: list_of(form_body.body.value(), &form_body.at),
            given: &form_body.given,
            outside: form_body.outside(),
            columns: &form_body.columns,
            head: form_body.head(),
        }
    }

    fn of_part(part: &'a PartBody) -> Self {
        Reading {
            at: &part.at,
            list: vec![(part.at.clone(), &part.atom)],
            given: &part.given,
            outside: part.given.iter().chain(&part.columns).copied().collect(),
            columns: &part.columns,
            head: None,
        }
    }
}

struct Walk<'a> {
    registry: &'a Registry,
    types: &'a dyn Fn(LabelId) -> Option<ValueType>,
    memo: Option<BoundMemo<'a>>,
}

impl Walk<'_> {
    /// The refusals of `reading` that `keep` keeps, each label once, at
    /// the first place that refuses it.
    fn refusals(&self, reading: &Reading<'_>, keep: &dyn Fn(&Fault, &NodePath) -> bool) -> Vec<Found> {
        let given: StableHashSet<LabelId> = reading.given.iter().copied().collect();
        let conjuncts: Vec<&Conjunct> = reading.list.iter().map(|(_, conjunct)| *conjunct).collect();
        let mut found = Vec::new();
        self.ordered(&reading.list, &given, &reading.outside, &mut found);
        let bound = bound_labels(&conjuncts, &given, &reading.outside, &|atom| atom_modes(self.registry, atom), self.types);
        let mut check_use = |at: &NodePath, use_: LabelUse| {
            if let Some(label) = use_label(use_).filter(|label| !bound.contains(label)) {
                found.push(Found { label: Some(label), fault: Fault::Unbound { body: reading.at.clone() }, at: at.clone() });
            }
        };
        for (at, conjunct) in &reading.list {
            each_label_use_at(NodeRef::Conjunct(conjunct), at, &mut check_use);
        }
        if let Some((input, at)) = reading.head {
            each_head_use(input, at, &mut check_use);
        }
        let held = list_labels(conjuncts);
        for &label in reading.columns.iter().filter(|label| !bound.contains(label) && !held.contains(label)) {
            found.push(Found { label: Some(label), fault: Fault::ColumnUnbound { body: reading.at.clone() }, at: reading.at.clone() });
        }
        let mut seen = StableHashSet::default();
        found.into_iter().filter(|found| keep(&found.fault, &found.at)).filter(|found| found.label.is_none_or(|label| seen.insert(label))).collect()
    }

    /// The labels that the conjuncts of `list` bind from `given`, with
    /// `outside` the labels that stand outside them.
    fn bind(&self, list: &[&Conjunct], given: &StableHashSet<LabelId>, outside: &StableHashSet<LabelId>) -> StableHashSet<LabelId> {
        bound_labels(list, given, outside, &|atom| atom_modes(self.registry, atom), self.types)
    }

    /// The labels that the first `end` conjuncts of `list`, `conjuncts` in
    /// order, bind from `given`, with `outside` the labels that stand
    /// outside them: [`Walk::bind`], kept in the memo where each of them
    /// is the state's.
    fn bind_before(&self, prefixes: &mut Prefixes<'_, '_>, conjuncts: &[&Conjunct], end: usize, given: &StableHashSet<LabelId>, outside: &StableHashSet<LabelId>) -> StableHashSet<LabelId> {
        let Some((memo, key)) = self.memo.and_then(|memo| Some((memo, prefixes.key(self, memo, end, given, outside)?))) else { return self.bind(&conjuncts[..end], given, outside) };
        if let Some(found) = memo.cache.bound.borrow().get(&key) {
            return found.clone();
        }
        let bound = self.bind(&conjuncts[..end], given, outside);
        memo.cache.bound.borrow_mut().insert(key, bound.clone());
        bound
    }

    /// Pushes onto `found` each label that `list`, in its written order,
    /// uses before the conjuncts written before it bind it, from `given`,
    /// with `outside` the labels that stand outside `list`, and so for the
    /// parts of each of its forms.
    fn ordered(&self, list: &[(NodePath, &Conjunct)], given: &StableHashSet<LabelId>, outside: &StableHashSet<LabelId>, found: &mut Vec<Found>) {
        let conjuncts: Vec<&Conjunct> = list.iter().map(|(_, conjunct)| *conjunct).collect();
        let sets: Vec<StableHashSet<LabelId>> = conjuncts.iter().map(|conjunct| conjunct_label_set(conjunct)).collect();
        let total = LabelCounts::of(&sets);
        let mut suffix = LabelCounts::of(&sets);
        let mut prefixes = Prefixes::new(list, &sets);
        for (i, (at, conjunct)) in list.iter().enumerate() {
            let from = suffix.around(outside, None);
            let before = self.bind_before(&mut prefixes, &conjuncts, i, given, &from);
            let around = total.around(outside, Some(&sets[i]));
            let moded = match conjunct {
                Conjunct::Atom(atom) | Conjunct::Not(Negated::Atom(atom)) => Some(atom).filter(|atom| !atom_modes(self.registry, atom.value()).is_empty()),
                _ => None,
            };
            let written = moded.map(|atom| {
                let mut written = before.clone();
                written.extend(orientation_labels(atom.value(), self.types));
                written
            });
            if let (Some(atom), Some(written)) = (moded, &written) {
                if !mode_holds(atom.value(), written, atom_modes(self.registry, atom.value())) {
                    found.push(Found { label: None, fault: Fault::AtomNoMode, at: at.clone() });
                }
            }
            match (conjunct, &written) {
                (Conjunct::Atom(atom), Some(written)) => {
                    let after_outside = suffix.around(outside, Some(&sets[i]));
                    let after = self.bind_before(&mut prefixes, &conjuncts, i + 1, given, &after_outside);
                    each_label_use_at(NodeRef::Conjunct(conjunct), at, &mut |path, use_| {
                        if let Some(label) = use_label(use_).filter(|label| !after.contains(label)) {
                            let completes = mode_may_hold(atom.value(), written, atom_modes(self.registry, atom.value()));
                            found.push(Found { label: Some(label), fault: Fault::NoMode { atom: at.clone(), completes }, at: path.clone() });
                        }
                    });
                }
                (Conjunct::Not(_) | Conjunct::All { .. }, _) => {
                    each_label_use_at(NodeRef::Conjunct(conjunct), at, &mut |path, use_| {
                        if let Some(label) = use_label(use_).filter(|label| around.contains(label) && !before.contains(label)) {
                            found.push(Found { label: Some(label), fault: Fault::Misordered, at: path.clone() });
                        }
                    });
                }
                _ => {}
            }
            suffix.remove(&sets[i]);
            let parts = parts_of(conjunct, at);
            for (j, part) in parts.iter().enumerate() {
                let mut part_outside = around.clone();
                part_outside.extend(list_labels(parts.iter().enumerate().filter(|&(k, _)| k != j).flat_map(|(_, other)| other.iter().map(|(_, conjunct)| *conjunct))));
                self.ordered(part, &before, &part_outside, found);
            }
        }
    }
}
