//! The grounding check, and the bodies of a form with their paths, which
//! the check of the labels that `=` makes and that an `OR` or an `IF`
//! exports reads too.

use super::reads::forms_within;
use super::types::result;
use super::{Check, CheckId, CheckInput, CheckResult, LabelInScope, Prefix, PrefixResult, Refusal};
use crate::eval::ir::atom_modes;
use crate::grounding::{body_labels, conjunct_labels, grounded_labels};
use crate::hash::StableHashSet;
use crate::program::canonical::{CanonicalOrder, SearchBudget};
use crate::program::path::{node_at, NodePath, NodeRef};
use crate::program::{constraint_second, Body, Conjunct, Form, InstanceInput, KeyClause, LabelId, LabelUse, Negated, Node, RelationColumn};
use crate::registry::Registry;
use crate::types::{use_label, ValueType};

/// [`CheckId::Grounding`].
pub struct GroundingCheck;

impl Check for GroundingCheck {
    fn id(&self) -> CheckId {
        CheckId::Grounding
    }

    /// Refuses each label of a body of the form that the body leaves
    /// ungrounded: one pass over each list in its written order, each prefix
    /// grounded by [`crate::grounding::grounded_labels`], with the modes of
    /// the algebra relations and relation macros. A label is refused at its first use
    /// in the body, or at the site of an atom that no mode of its relation
    /// grounds from the conjuncts written before it, or at a `NOT` or an
    /// `ALL` written before the conjuncts that ground its outer label.
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

    fn check_prefix(&self, _prefix: &Prefix<'_>) -> PrefixResult {
        PrefixResult::Undecided
    }
}

/// One body of a form: a clause's, a key clause's, an instance input's, or
/// one of a `CHOOSE` or a `RIGID_DET` form, with what its context gives it.
pub(super) struct FormBody<'a> {
    /// The body's path relative to the top-level form.
    pub at: NodePath,
    pub body: &'a Body,
    /// The head of an instance input, at its path relative to the
    /// top-level form.
    pub head: Option<(&'a InstanceInput, NodePath)>,
    /// The labels the body reads grounded from its context: the key's
    /// labels for a keyed input or an instance clause, and the row's and
    /// the candidate's for a `never` clause.
    pub given: Vec<LabelId>,
    /// The labels of the columns that the body gives.
    pub columns: Vec<LabelId>,
    /// The labels of the fields of the `DEMO_RULE` whose scope the body's
    /// form stands in, which its forms read.
    pub fields: Vec<LabelId>,
}

impl FormBody<'_> {
    /// The labels that stand outside the body in its context: those
    /// [`FormBody::given`], [`FormBody::columns`] and [`FormBody::fields`]
    /// hold, and the labels of the input's head.
    fn outside(&self) -> StableHashSet<LabelId> {
        let mut outside: StableHashSet<LabelId> = self.given.iter().chain(&self.columns).chain(&self.fields).copied().collect();
        if let Some((input, at)) = &self.head {
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
        let first = out.len();
        match node {
            NodeRef::Clause(clause) => out.push(plain(&clause.body, at.child(0), &[], labels(&clause.columns))),
            NodeRef::Instance(instance) => keyed_bodies(instance.key.as_ref(), &instance.inputs, &at, &mut out),
            NodeRef::Demonstrated(demonstrated) => keyed_bodies(demonstrated.key.as_ref(), &demonstrated.inputs, &at, &mut out),
            NodeRef::Choose(choose) => {
                let rows = choose.rows.as_ref().map(|rows| labels(&rows.columns)).unwrap_or_default();
                let candidate = labels(&choose.candidate_columns);
                let mut index = 0u32;
                if let Some(key) = &choose.rows {
                    out.push(plain(&key.body, at.child(index), &[], rows.clone()));
                    index += 1;
                }
                let from_given = if choose.from_inside_for { rows.clone() } else { Vec::new() };
                out.push(plain(&choose.from, at.child(index), &from_given, candidate.clone()));
                let never_given: Vec<LabelId> = rows.iter().chain(&candidate).copied().collect();
                for (never, offset) in choose.never.iter().zip(index + 1..) {
                    out.push(plain(never, at.child(offset), &never_given, Vec::new()));
                }
            }
            NodeRef::RigidDet(rigid) => {
                let key = rigid.key.as_ref().map(|key| labels(&key.columns)).unwrap_or_default();
                let mut index = 0u32;
                if let Some(clause) = &rigid.key {
                    out.push(plain(&clause.body, at.child(index), &[], key.clone()));
                    index += 1;
                }
                if let Some(clause) = &rigid.instance {
                    out.push(plain(&clause.body, at.child(index), &key, labels(&clause.columns)));
                }
            }
            _ => {}
        }
        if let Some((_, parent)) = at.0.split_last() {
            if let Some(NodeRef::DemoRule(rule)) = node_at(NodeRef::from(form), &NodePath(parent.into())) {
                out[first..].iter_mut().for_each(|body| body.fields = labels(&rule.fields));
            }
        }
    }
    out
}

fn labels(columns: &[RelationColumn]) -> Vec<LabelId> {
    columns.iter().map(|column| column.label).collect()
}

fn plain<'a>(body: &'a Node<Body>, at: NodePath, given: &[LabelId], columns: Vec<LabelId>) -> FormBody<'a> {
    FormBody { at, body: body.value(), head: None, given: given.to_vec(), columns, fields: Vec::new() }
}

/// The bodies of an `INIT` or a `DEMONSTRATED` form at `at`: its key
/// body, each keyed input, with the key's labels given, and each other
/// input.
fn keyed_bodies<'a>(key: Option<&'a Node<KeyClause>>, inputs: &'a [Node<InstanceInput>], at: &NodePath, out: &mut Vec<FormBody<'a>>) {
    let input = |input: &'a InstanceInput, input_at: NodePath, given: &[LabelId]| FormBody {
        at: input_at.child(input.head.len() as u32),
        body: input.body.value(),
        head: Some((input, input_at)),
        given: given.to_vec(),
        columns: Vec::new(),
        fields: Vec::new(),
    };
    let mut index = 0u32;
    if let Some(key) = key {
        let key = key.value();
        let key_at = at.child(0);
        let key_labels = labels(&key.key.columns);
        out.push(plain(&key.key.body, key_at.child(0), &[], key_labels.clone()));
        for (keyed, offset) in key.inputs.iter().zip(1u32..) {
            out.push(input(keyed.value(), key_at.child(offset), &key_labels));
        }
        index = 1;
    }
    for (other, offset) in inputs.iter().zip(index..) {
        out.push(input(other.value(), at.child(offset), &[]));
    }
}

/// The entries of `labels` of the label scope that holds the body at
/// `at`: the scope whose form's path is the longest prefix of `at`.
fn label_scope<'l>(labels: &'l [LabelInScope], at: &NodePath) -> Vec<&'l LabelInScope> {
    let holds = |entry: &&LabelInScope| at.0.starts_with(&entry.scope.0);
    let Some(depth) = labels.iter().filter(holds).map(|entry| entry.scope.0.len()).max() else { return Vec::new() };
    labels.iter().filter(holds).filter(|entry| entry.scope.0.len() == depth).collect()
}

/// Visits each label use of `node`, at `at`, at any depth, in source
/// order, with its path: a use at a site at the path of its label, and a
/// constraint's at the path of the constraint.
pub(super) fn each_use(node: NodeRef<'_>, at: &NodePath, visit: &mut dyn FnMut(&NodePath, LabelUse)) {
    match node {
        NodeRef::Label(use_) => visit(at, *use_),
        NodeRef::Conjunct(Conjunct::Constraint(constraint)) => {
            visit(at, constraint.first.into());
            if let Some(second) = constraint_second(constraint) {
                visit(at, second.into());
            }
        }
        _ => {
            for (child, index) in node.children().into_iter().zip(0u32..) {
                each_use(child, &at.child(index), visit);
            }
        }
    }
}

/// Visits each label use at the head sites of `input`, at `at`.
pub(super) fn each_head_use(input: &InstanceInput, at: &NodePath, visit: &mut dyn FnMut(&NodePath, LabelUse)) {
    for (site, index) in input.head.iter().zip(0u32..) {
        each_use(NodeRef::Site(site), &at.child(index), visit);
    }
}

/// The conjuncts of `body`, at `at`, each with its path.
pub(super) fn list_of<'a>(body: &'a Body, at: &NodePath) -> Vec<(NodePath, &'a Conjunct)> {
    body.conjuncts.iter().zip(0u32..).map(|(conjunct, index)| (at.child(index), conjunct)).collect()
}

/// The parts of `conjunct`, at `at`, each a list of conjuncts with their
/// paths: the branches of an `OR`, the test with the then and the else of
/// an `IF`, the two lists of an `ALL` together, and the inner form of a
/// `NOT` as a list of its own.
pub(super) fn parts_of<'a>(conjunct: &'a Conjunct, at: &NodePath) -> Vec<Vec<(NodePath, &'a Conjunct)>> {
    let lists = |bodies: &[(&'a Node<Body>, u32)]| bodies.iter().flat_map(|(body, index)| list_of(body.value(), &at.child(*index))).collect();
    match conjunct {
        Conjunct::Or(branches) => branches.iter().zip(0u32..).map(|(branch, index)| lists(&[(branch, index)])).collect(),
        Conjunct::If { test, then, otherwise } => vec![lists(&[(test, 0), (then, 1)]), lists(&[(otherwise, 2)])],
        Conjunct::All { domain, body } => vec![lists(&[(domain, 0), (body, 1)])],
        Conjunct::Not(Negated::Form(form)) => vec![vec![(at.child(0), &**form)]],
        Conjunct::Atom(_) | Conjunct::Not(Negated::Atom(_)) | Conjunct::Constraint(_) => Vec::new(),
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
        self.ordered(&list_of(form_body.body, &form_body.at), &given, &outside, &mut found);
        let grounded = grounded_labels(form_body.body, &given, &outside, &|atom| atom_modes(self.registry, atom), self.types);
        let mut ungrounded = |at: &NodePath, use_: LabelUse| {
            if let Some(label) = use_label(use_).filter(|label| !grounded.contains(label)) {
                found.push((label, "the body leaves the label ungrounded", at.clone()));
            }
        };
        each_use(NodeRef::Body(form_body.body), &form_body.at, &mut ungrounded);
        if let Some((input, at)) = &form_body.head {
            each_head_use(input, at, &mut ungrounded);
        }
        let held = body_labels(form_body.body);
        for &label in form_body.columns.iter().filter(|label| !grounded.contains(label) && !held.contains(label)) {
            found.push((label, "the body leaves the label of a column ungrounded", form_body.at.clone()));
        }
        let mut seen = StableHashSet::default();
        found.into_iter().filter(|(label, _, _)| seen.insert(*label)).map(|(_, message, at)| (message, at)).collect()
    }

    /// The labels that the conjuncts of `list` ground from `given`, with
    /// `outside` the labels that stand outside them.
    fn ground(&self, list: &[(NodePath, &Conjunct)], given: &StableHashSet<LabelId>, outside: &StableHashSet<LabelId>) -> StableHashSet<LabelId> {
        let body = Body { conjuncts: list.iter().map(|(_, conjunct)| (*conjunct).clone()).collect() };
        grounded_labels(&body, given, outside, &|atom| atom_modes(self.registry, atom), self.types)
    }

    /// Pushes onto `found` each label that `list`, in its written order,
    /// uses before the conjuncts written before it ground it, from `given`,
    /// with `outside` the labels that stand outside `list`, and so for the
    /// parts of each of its forms.
    fn ordered(&self, list: &[(NodePath, &Conjunct)], given: &StableHashSet<LabelId>, outside: &StableHashSet<LabelId>, found: &mut Vec<(LabelId, &'static str, NodePath)>) {
        for (i, (at, conjunct)) in list.iter().enumerate() {
            let mut from = outside.clone();
            from.extend(list_labels(list[i..].iter().map(|(_, conjunct)| *conjunct)));
            let before = self.ground(&list[..i], given, &from);
            let mut around = outside.clone();
            around.extend(list_labels(list.iter().enumerate().filter(|&(k, _)| k != i).map(|(_, (_, conjunct))| *conjunct)));
            match conjunct {
                Conjunct::Atom(atom) if !atom_modes(self.registry, atom.value()).is_empty() => {
                    let mut after_outside = outside.clone();
                    after_outside.extend(list_labels(list[i + 1..].iter().map(|(_, conjunct)| *conjunct)));
                    let after = self.ground(&list[..=i], given, &after_outside);
                    each_use(NodeRef::Conjunct(conjunct), at, &mut |path, use_| {
                        if let Some(label) = use_label(use_).filter(|label| !after.contains(label)) {
                            found.push((label, "no mode of the atom's relation has its columns grounded by the conjuncts written before it", path.clone()));
                        }
                    });
                }
                Conjunct::Not(_) | Conjunct::All { .. } => {
                    each_use(NodeRef::Conjunct(conjunct), at, &mut |path, use_| {
                        if let Some(label) = use_label(use_).filter(|label| around.contains(label) && !before.contains(label)) {
                            found.push((label, "the `NOT` or the `ALL` stands before the conjuncts that ground the label", path.clone()));
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
