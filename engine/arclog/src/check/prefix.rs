//! The prefixes of a form, the run of the checks of [`super::checks`] on a
//! prefix, and the rule by which a check's refusals of a partial form stand
//! as refusals of the prefix.

use std::cell::{OnceCell, RefCell};
use std::sync::Arc;

use super::{checks, inference, labels_in_scopes, typed_labels, types, Check, CheckId, CheckInput, CheckResult, Prefix, PrefixResult, Refusal, Scope, SolverClauses};
use super::safety::{BoundCache, BoundMemo};
use super::LabelInScope;
use crate::eval::ir::relation_modes;
use crate::hash::StableHashMap;
use crate::program::canonical::{CanonicalOrder, SearchBudget};
use crate::program::path::{node_at, NodePath, NodeRef, PathStep};
use crate::program::{Atom, Body, Choose, Clause, Conjunct, Form, Instance, InstanceInput, KeyBody, KeyClause, LabelUse, Negated, Node, Out, Program, RigidDet, Site, SiteArg, SiteValue};
use crate::registry::{LibEntry, Mode, Registry};
use crate::program::{OutputName, OutputOwner, RelationRef};
use crate::resolver::{resolve_last, DependencyKind, ResolvedProgram, Side};
use crate::stream::write::reads_example_column;
use crate::types::each_site_label;

/// A prefix of a form: its partial form, as [`Prefix`] gives it, and the
/// path there of the node at whose end the prefix stands.
#[derive(Clone, Debug)]
pub struct FormPrefix {
    pub partial: Form,
    pub end: NodePath,
}

impl FormPrefix {
    /// The open node, as [`Prefix`] gives it: the node above the end, or
    /// none where the prefix ends at the form.
    pub fn open(&self) -> Option<NodePath> {
        self.end.0.split_last().map(|(_, above)| NodePath(above.into()))
    }
}

/// Each prefix of `form`, one at the end of each of its nodes, in the order
/// in which a token stream ends them: the nodes the stream writes before
/// that node and the node itself, with each node above it open, and the
/// last prefix `form` itself. The stream writes the source's order, but for
/// an instance input's body, which it writes before the head sites that
/// project its labels. A node of a claim, an `ALTS` form or a
/// `DEMONSTRATED` form ends no prefix of its own, since no token stream
/// holds one.
///
/// A list that the prefix has not reached stands empty, and an open clause,
/// key body or `CHOOSE` form holds no columns yet, since the columns of a
/// clause follow its body.
pub fn prefixes(form: &Form) -> Vec<FormPrefix> {
    let mut ends = Vec::new();
    each_end(NodeRef::from(form), NodePath::default(), &mut ends);
    let prefix = |at: NodePath| FormPrefix { partial: cut_form(form, &at.0), end: partial_path(form, &at) };
    ends.into_iter().map(prefix).collect()
}

/// Pushes onto `out` the path of each node of `node`, at `at`, after the
/// paths of its children, each input's body before its head sites.
fn each_end(node: NodeRef<'_>, at: NodePath, out: &mut Vec<NodePath>) {
    if !matches!(node, NodeRef::Claim(_) | NodeRef::Alts(_) | NodeRef::Demonstrated(_)) {
        let mut children: Vec<(NodeRef<'_>, u32)> = node.children().into_iter().zip(0u32..).collect();
        if let NodeRef::InstanceInput(_) = node {
            children.rotate_right(1);
        }
        for (child, index) in children {
            each_end(child, at.child(index), out);
        }
    }
    out.push(at);
}

/// The path, in the prefix of `form` that ends at the node at `at`, of that
/// node: `at`, but at an input whose body the prefix ends in, which stands
/// first while the input holds no head site.
fn partial_path(form: &Form, at: &NodePath) -> NodePath {
    let mut within = Vec::new();
    for (depth, step) in at.0.iter().enumerate() {
        let above = node_at(NodeRef::from(form), &NodePath(at.0[..depth].into()));
        match above {
            Some(NodeRef::InstanceInput(input)) if step.0 as usize == input.head.len() => within.push(PathStep(0)),
            _ => within.push(*step),
        }
    }
    NodePath(within.into())
}

/// The result of each check of [`checks`] on the prefix whose partial form
/// is the last top-level form of `program`, with the earlier forms
/// complete, and whose open node is at `open`. `clauses` holds the clauses
/// of `program`'s solver, or of `program` alone for a synthesized program.
pub fn check_prefix(program: &ResolvedProgram, clauses: &SolverClauses, registry: &Registry, open: Option<&NodePath>) -> Vec<(CheckId, PrefixResult)> {
    with_prefix(program, clauses, registry, None, None, None, open, |prefix| checks().iter().map(|check| (check.id(), check.check_prefix(prefix))).collect())
}

/// The checks of the prefixes of a decode's state, each over a program
/// whose forms before its last are one set of complete forms: the types of
/// the complete forms are inferred once, and each check of a prefix infers
/// the types of its last form alone.
pub struct PrefixChecks<'a> {
    clauses: &'a SolverClauses,
    registry: &'a Registry,
    /// The inference of the complete forms.
    inference: &'a inference::Inference<'a>,
    /// What the prefixes checked as [`Candidate::AtomHead`] share.
    head: AtomHead,
    /// The labels that the prefixes of a list bind, for the candidates of
    /// the mask.
    bound: BoundCache,
}

/// What a prefix is among the candidates of one mask.
#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub enum Candidate {
    /// A prefix of any form.
    Any,
    /// A prefix whose last token opens an atom of no site yet. The prefixes
    /// of a [`PrefixChecks`] given this are one program but for the
    /// relation of that atom, at one open path.
    AtomHead,
}

/// What the atom-head candidates of one [`PrefixChecks`] share. They are
/// one program but for the relation of the open atom, which holds no site.
/// A label's type reads an atom only through its sites, so the first
/// candidate infers the types of its last form and the labels of its
/// scopes, and each other takes them. A check that [`atom_reading`] says
/// ignores the relation of such an atom gives each candidate the first
/// candidate's result, and so does the safety check, where the atoms'
/// relations have equal modes, and so does a check that reads the relation
/// itself, where the candidates' relations are of one [`RelationClass`];
/// and the conjuncts written before the atom bind the same labels in every
/// candidate.
#[derive(Default)]
struct AtomHead {
    /// The path of the open atom of the first candidate, the path of the
    /// open atom of each candidate that shares.
    open: OnceCell<NodePath>,
    types: RefCell<Option<inference::InferredTypes>>,
    labels: OnceCell<Vec<LabelInScope>>,
    results: RefCell<StableHashMap<(CheckId, Shared), PrefixResult>>,
    /// The resolution of the candidates that open an atom of a relation
    /// ([`PrefixChecks::check_atom_head`]): the one of the candidate
    /// checked last, retargeted to the next.
    resolution: RefCell<Option<HeldResolution>>,
}

/// The resolution of the form in progress for a candidate that opens, at
/// `at`, an atom of `relation`.
struct HeldResolution {
    at: NodePath,
    relation: RelationRef,
    resolved: ResolvedProgram,
}

/// How a check reads the relation of an atom of no site.
#[derive(Clone, Copy, PartialEq, Eq, Debug)]
enum AtomReading {
    /// Not at all: the check reads an atom through its sites, or reads no
    /// atom.
    Ignored,
    /// Through its modes alone, which a relation of none leaves unread.
    Modes,
    /// Through the relation itself, which the candidates whose relations
    /// are of one [`RelationClass`] read alike.
    Relation,
    /// Through the types of the relation's columns, which no two candidates
    /// read alike.
    Columns,
}

/// What a check's result on an atom-head candidate is shared by: the
/// candidates that give a check one value of it give it one result.
#[derive(Clone, PartialEq, Eq, Hash, Debug)]
enum Shared {
    /// All candidates.
    Ignored,
    /// The candidates whose open atoms' relations have these modes.
    Modes(Box<[Mode]>),
    /// The candidates whose open atoms' relations are of this class.
    Relation(RelationClass),
}

/// The class of the relation of an atom of no site, within which the checks
/// that `atom_reading` says read the relation give one result: they read,
/// of a lib name, the kind of its registry entry and whether it is `ONE`;
/// of a relation that the forms before the last resolve to a node, only
/// what that node's side is, where the node is no fact and the relation is
/// no output of a `RIGID_DET` form.
#[derive(Clone, PartialEq, Eq, Hash, Debug)]
pub enum RelationClass {
    /// A lib name: the kind of its registry entry, and whether it is `ONE`.
    Lib { entry: std::mem::Discriminant<LibEntry>, one: bool },
    /// A declared relation or an output that the forms before the last
    /// resolve to a node of this side.
    Earlier { side: Side },
}

/// The class of `relation`, the relation of an atom of no site that the
/// last form of `held` holds, where `earlier` resolves the forms before
/// the last; none for a relation whose candidates share no such result,
/// a fact relation or a relation that the last form declares included.
fn relation_class(registry: &Registry, earlier: &ResolvedProgram, held: &ResolvedProgram, relation: &RelationRef) -> Option<RelationClass> {
    match relation {
        RelationRef::Lib(name) => registry.entry(name).map(|entry| RelationClass::Lib { entry: std::mem::discriminant(entry), one: *name.0 == *crate::read::spelling::ONE }),
        RelationRef::Output(OutputName { of: OutputOwner::RigidDet(_), .. }) => None,
        RelationRef::Declared(_) | RelationRef::Output(_) => {
            let node = earlier.program_read(relation).filter(|node| held.program_read(relation) == Some(*node))?;
            let fact = matches!(earlier.graph.nodes[node.0 as usize].kind, DependencyKind::Fact(_));
            (!fact).then(|| RelationClass::Earlier { side: earlier.side(node) })
        }
        RelationRef::Fact(_) | RelationRef::DefinedPort(_) => None,
    }
}

/// What `check`'s result on a candidate that opens an atom of `relation`,
/// of `class`, is shared by, where it is shared.
fn shared(registry: &Registry, check: CheckId, relation: Option<&RelationRef>, class: Option<&RelationClass>) -> Option<Shared> {
    match atom_reading(check) {
        AtomReading::Ignored => Some(Shared::Ignored),
        AtomReading::Modes => relation.map(|relation| Shared::Modes(relation_modes(registry, relation).into())),
        AtomReading::Relation => class.cloned().map(Shared::Relation),
        AtomReading::Columns => None,
    }
}

/// How `check` reads the relation of an atom of no site.
fn atom_reading(check: CheckId) -> AtomReading {
    match check {
        CheckId::Grammar
        | CheckId::Types
        | CheckId::MadeAndExportedLabels
        | CheckId::EqualityAndZero
        | CheckId::ConstraintMarks
        | CheckId::PoseRule
        | CheckId::OneClause
        | CheckId::Spelling => AtomReading::Ignored,
        CheckId::Safety => AtomReading::Modes,
        CheckId::SiteColumns
        | CheckId::Scope
        | CheckId::UnfoldReads
        | CheckId::Cycles
        | CheckId::InstanceInputs
        | CheckId::PooledAndLiftedReads
        | CheckId::InstanceSites
        | CheckId::Picks
        | CheckId::RigidPartsAndProposers => AtomReading::Relation,
        CheckId::Out => AtomReading::Columns,
    }
}

impl PrefixChecks<'_> {
    /// Runs `body` with the checks over the prefixes whose complete forms
    /// are those of `complete`, `clauses` being the clauses of `complete`.
    pub fn with<R>(complete: &ResolvedProgram, clauses: &SolverClauses, registry: &Registry, body: impl FnOnce(&PrefixChecks<'_>) -> R) -> R {
        let cases = inference::CaseInferences::new(clauses, registry);
        let inference = inference::Inference::new(complete, &cases);
        body(&PrefixChecks { clauses, registry, inference: &inference, head: AtomHead::default(), bound: BoundCache::default() })
    }

    /// Holds the form in progress at the mask's state, `program` with that
    /// form as its last, over `earlier`, the resolution of the forms before
    /// it: a candidate that differs from it by what its token adds to the
    /// sites of some atoms takes the types of the other labels from the
    /// state's inference.
    pub fn hold_state(&self, earlier: Arc<ResolvedProgram>, program: Node<Program>) {
        self.inference.hold_state(earlier, program);
    }

    /// The first check of [`checks`], in their order, that refuses the
    /// prefix whose partial form is the last form of `program`, a
    /// resolution by [`crate::resolver::resolve_last`] over the complete
    /// forms, and whose open node is at `open`, with its refusals; `None`
    /// where none refuses. No check after it runs. Where `candidate` is
    /// [`Candidate::AtomHead`], a refusal of a check that ignores the open
    /// atom's relation is the first such candidate's, whatever the
    /// candidate's own relation; which candidates refuse is the same. So is
    /// a refusal of a check that reads the relation, where `class` is the
    /// class of the candidate's relation: the refusal of the first
    /// candidate of that class. A candidate of no class shares no such
    /// result.
    pub fn check(&self, program: &ResolvedProgram, open: Option<&NodePath>, candidate: Candidate, class: Option<&RelationClass>) -> Option<(CheckId, Box<[Refusal]>)> {
        let same_open = |open: &NodePath| self.head.open.get_or_init(|| open.clone()) == open;
        let head = (candidate == Candidate::AtomHead && open.is_some_and(same_open)).then_some(&self.head);
        with_prefix(program, self.clauses, self.registry, Some(self.inference), head, Some(&self.bound), open, |prefix| {
            checks().iter().find_map(|check| match self.check_prefix(*check, prefix, head, class) {
                PrefixResult::Refuse(refusals) => Some((check.id(), refusals)),
                PrefixResult::Undecided => None,
            })
        })
    }

    /// [`PrefixChecks::check`] with [`Candidate::AtomHead`] for the prefix
    /// whose last token opens, at `open`, an atom of `relation`, a lib
    /// relation or relation macro, or a relation declared or
    /// output by a form of `program`, where `earlier` is the resolution of
    /// the forms before the last of `program`. The candidates of one mask
    /// at one open path share one resolution of the form in progress,
    /// retargeted to each one's relation
    /// ([`ResolvedProgram::retarget_atom`]); where that gives no retarget,
    /// the resolution is [`resolve_last`]'s. They share as well the result
    /// of each check, as `AtomHead` states: a candidate for which the
    /// checks, in their order up to the first that refuses, all hold a
    /// result that a candidate of its [`RelationClass`] gave takes the
    /// first refusal of those, or none, with no retarget and no check run.
    pub fn check_atom_head(&self, earlier: &Arc<ResolvedProgram>, program: &Node<Program>, open: &NodePath, relation: &RelationRef) -> Option<(CheckId, Box<[Refusal]>)> {
        let last = program.value().forms.len() as u32 - 1;
        let full = NodePath(std::iter::once(PathStep(last)).chain(open.0.iter().copied()).collect());
        if !self.head.resolution.borrow().as_ref().is_some_and(|held| held.at == full) {
            self.hold_atom_head(earlier, program, &full, relation);
        }
        let class = {
            let held = self.head.resolution.borrow();
            relation_class(self.registry, earlier, &held.as_ref().expect("the resolution is set").resolved, relation)
        };
        if self.head.open.get() == Some(open) {
            if let Some(result) = self.held_result(relation, class.as_ref()) {
                return result;
            }
        }
        self.hold_atom_head(earlier, program, &full, relation);
        let held = self.head.resolution.borrow();
        let resolved = &held.as_ref().expect("the resolution is set").resolved;
        self.check(resolved, Some(open), Candidate::AtomHead, class.as_ref())
    }

    /// What [`PrefixChecks::check`] gives for a candidate that opens an
    /// atom of `relation`, of `class`, where `head` holds the result of each
    /// check up to the first that refuses: `Some` of the first refusal, or
    /// of none; `None` where a check before that refusal has no result held.
    fn held_result(&self, relation: &RelationRef, class: Option<&RelationClass>) -> Option<Option<(CheckId, Box<[Refusal]>)>> {
        let results = self.head.results.borrow();
        for check in checks() {
            let key = (check.id(), shared(self.registry, check.id(), Some(relation), class)?);
            if let PrefixResult::Refuse(refusals) = results.get(&key)? {
                return Some(Some((check.id(), refusals.clone())));
            }
        }
        Some(None)
    }

    /// Whether the read at `at`, the path in `program` of an atom of
    /// `relation` that a candidate opens, reads an Example column, as
    /// `reads_example_column` gives it on the resolution that
    /// [`PrefixChecks::check_atom_head`] holds for that candidate.
    pub fn reads_example_column(&self, earlier: &Arc<ResolvedProgram>, program: &Node<Program>, at: &NodePath, relation: &RelationRef) -> bool {
        self.hold_atom_head(earlier, program, at, relation);
        let held = self.head.resolution.borrow();
        reads_example_column(&held.as_ref().expect("the resolution is set").resolved, at)
    }

    /// Holds the resolution of `program` for the candidate that opens, at
    /// `at`, an atom of `relation`: the held one retargeted, or
    /// [`resolve_last`]'s. A resolution already held for that candidate
    /// stays.
    fn hold_atom_head(&self, earlier: &Arc<ResolvedProgram>, program: &Node<Program>, at: &NodePath, relation: &RelationRef) {
        let mut held = self.head.resolution.borrow_mut();
        if held.as_ref().is_some_and(|held| held.at == *at && held.relation == *relation) {
            return;
        }
        let retargeted = held.as_mut().is_some_and(|held| held.at == *at && held.resolved.retarget_atom(program, at, relation, self.registry));
        match held.as_mut().filter(|_| retargeted) {
            Some(held) => held.relation = relation.clone(),
            None => *held = Some(HeldResolution { at: at.clone(), relation: relation.clone(), resolved: resolve_last(earlier, program, self.registry) }),
        }
    }

    /// The result of `check` on `prefix`, which is the result of the first
    /// candidate of `head` that [`shared`] gives the same value, where
    /// `check` reads nothing of the open atom that the candidates of that
    /// value differ in.
    fn check_prefix(&self, check: &dyn Check, prefix: &Prefix<'_>, head: Option<&AtomHead>, class: Option<&RelationClass>) -> PrefixResult {
        let key = head.and_then(|head| Some((head, shared(self.registry, check.id(), open_atom(prefix).map(|atom| &atom.relation), class)?)));
        let Some((head, key)) = key else { return check.check_prefix(prefix) };
        let key = (check.id(), key);
        if let Some(found) = head.results.borrow().get(&key) {
            return found.clone();
        }
        let result = check.check_prefix(prefix);
        head.results.borrow_mut().insert(key, result.clone());
        result
    }
}

/// The atom open in the partial form of `prefix`.
fn open_atom<'a>(prefix: &Prefix<'a>) -> Option<&'a Atom> {
    node_at(NodeRef::from(prefix.partial), prefix.open?)?.atom()
}

/// Runs `body` over the prefix of `program`, whose types are inferred over
/// the forms that `earlier` infers, where it is given, and from the start
/// otherwise; and that shares `head` with the other atom-head candidates,
/// where it is given, and whose safety check keeps in `cache` the labels
/// that the prefixes of a list bind.
fn with_prefix<R>(
    program: &ResolvedProgram,
    clauses: &SolverClauses,
    registry: &Registry,
    earlier: Option<&inference::Inference<'_>>,
    head: Option<&AtomHead>,
    cache: Option<&BoundCache>,
    open: Option<&NodePath>,
    body: impl FnOnce(&Prefix<'_>) -> R,
) -> R {
    let (partial, complete) = program.program.value().forms.split_last().expect("a prefix's program holds its partial form");
    let path = NodePath::top(complete.len() as u32);
    let cases = inference::CaseInferences::new(clauses, registry);
    let inference = match earlier {
        Some(earlier) => inference::Inference::layered(program, &cases, earlier),
        None => inference::Inference::new(program, &cases),
    };
    let inference = match head {
        Some(head) => inference.sharing_last(&head.types),
        None => inference,
    };
    let inference = &inference;
    let bound = cache.zip(earlier.and_then(|earlier| earlier.state_form())).map(|(cache, state)| BoundMemo { cache, state });
    let scope = |labels| Scope { program, registry, labels, clauses, inference, files: None, bound };
    let (order, untyped, computed);
    let labels: &[LabelInScope] = match head.and_then(|head| head.labels.get()) {
        Some(labels) => labels,
        None => {
            order = CanonicalOrder::of(partial, &mut SearchBudget::new());
            untyped = labels_in_scopes(&order, &|_, _| None);
            let (_, form_types) = types::infer_form(&CheckInput { form: partial, path: &path, scope: scope(&untyped) }, &order);
            computed = typed_labels(&order, &form_types);
            if let Some(head) = head {
                head.labels.get_or_init(|| computed.clone());
            }
            &computed
        }
    };
    let prefix = Prefix { complete, partial, path: &path, open, scope: scope(labels) };
    body(&prefix)
}

/// The input of a check over the whole partial form of `prefix`.
pub(super) fn whole<'a>(prefix: &Prefix<'a>) -> CheckInput<'a> {
    CheckInput { form: prefix.partial, path: prefix.path, scope: prefix.scope }
}

/// The refusals of `check` on the whole partial form of `prefix` that stand
/// at a complete node, as the prefix's refusals.
///
/// A caller meets this condition: each refusal of `check`, found at a node,
/// is one that no node written after that node undoes, so that it stands in
/// every completion of the prefix. A check with a refusal that a later node
/// undoes, such as a label that a conjunct written later binds, gives its own
/// rule of when each refusal stands: [`standing`] keeps the refusals at the
/// paths of a predicate, and the safety check keeps its own, by kind.
pub(super) fn settled(prefix: &Prefix<'_>, check: &dyn Check) -> PrefixResult {
    settled_result(prefix, check.check(&whole(prefix)))
}

/// The refusals of `result`, a check's result on the whole partial form of
/// `prefix`, that stand at a complete node: [`settled`], for a caller whose
/// result is not that of `check`.
pub(super) fn settled_result(prefix: &Prefix<'_>, result: CheckResult) -> PrefixResult {
    standing(prefix, result, &|at| !prefix.is_open(at))
}

/// The refusals of `result`, a check's result on the whole partial form of
/// `prefix`, at each path that `stands` keeps, each at its source path
/// relative to the partial form.
pub(super) fn standing(prefix: &Prefix<'_>, result: CheckResult, stands: &dyn Fn(&NodePath) -> bool) -> PrefixResult {
    let CheckResult::Refuse(refusals) = result else { return PrefixResult::Undecided };
    let order = CanonicalOrder::of(prefix.partial, &mut SearchBudget::new());
    let source = refusals.iter().map(|refusal| Refusal { message: refusal.message.clone(), at: order.source_path(&refusal.at) });
    refused(source.filter(|refusal| stands(&refusal.at)).collect())
}

/// A refusal of each of `refusals`, or undecided where it holds none.
pub(super) fn refused(refusals: Vec<Refusal>) -> PrefixResult {
    if refusals.is_empty() {
        PrefixResult::Undecided
    } else {
        PrefixResult::Refuse(refusals.into())
    }
}

/// `form` cut to the prefix that ends at the node at `path`: the nodes
/// before it in the source, the node itself, and the nodes above it, each
/// open.
fn cut_form(form: &Form, path: &[PathStep]) -> Form {
    let Some((step, rest)) = path.split_first() else { return form.clone() };
    let index = step.0 as usize;
    match form {
        Form::Clause(clause) => {
            let clause = clause.value();
            Form::Clause(Node::new(Clause { body: cut_body(&clause.body, rest), ones: Arc::from([]), set: false, columns: Arc::from([]), ..clause.clone() }))
        }
        Form::Instance(instance) => {
            let instance = instance.value();
            let (key, inputs) = match &instance.key {
                Some(key) if index == 0 => (Some(Node::new(cut_key_clause(key.value(), rest))), Arc::from([])),
                key => (key.clone(), cut_list(&instance.inputs, index - usize::from(key.is_some()), |input| cut_input(input, rest))),
            };
            Form::Instance(Node::new(Instance { key, inputs, ..instance.clone() }))
        }
        Form::Choose(choose) => Form::Choose(Node::new(cut_choose(choose.value(), index, rest))),
        Form::RigidDet(rigid) => Form::RigidDet(Node::new(cut_rigid(rigid.value(), index, rest))),
        Form::Out(out) => Form::Out(Node::new(Out { key: cut_key_body(&out.value().key, rest) })),
        Form::Claim(_) | Form::Alts(_) | Form::Demonstrated(_) => unreachable!("no prefix ends at a node of a claim, an `ALTS` form or a `DEMONSTRATED` form"),
    }
}

fn cut_key_clause(clause: &KeyClause, path: &[PathStep]) -> KeyClause {
    let Some((step, rest)) = path.split_first() else { return clause.clone() };
    match step.0 {
        0 => KeyClause { key: cut_key_body(&clause.key, rest), inputs: Arc::from([]) },
        index => KeyClause { key: clause.key.clone(), inputs: cut_list(&clause.inputs, index as usize - 1, |input| cut_input(input, rest)) },
    }
}

fn cut_input(input: &Node<InstanceInput>, path: &[PathStep]) -> Node<InstanceInput> {
    let Some((step, rest)) = path.split_first() else { return input.clone() };
    let input = input.value();
    let index = step.0 as usize;
    let cut = if index < input.head.len() {
        InstanceInput { head: cut_list(&input.head, index, |site| cut_site(site, rest)), ..input.clone() }
    } else {
        InstanceInput { head: Arc::from([]), body: cut_body(&input.body, rest), ..input.clone() }
    };
    Node::new(cut)
}

fn cut_choose(choose: &Choose, index: usize, rest: &[PathStep]) -> Choose {
    let open = Choose { candidate_columns: Arc::from([]), ..choose.clone() };
    match (&choose.rows, index) {
        (Some(rows), 0) => Choose { rows: Some(cut_key_body(rows, rest)), from: empty(), never: Arc::from([]), ..open },
        (rows, index) => match index - usize::from(rows.is_some()) {
            0 => Choose { from: cut_body(&choose.from, rest), never: Arc::from([]), ..open },
            never => Choose { never: cut_list(&choose.never, never - 1, |body| cut_body(body, rest)), ..open },
        },
    }
}

fn cut_rigid(rigid: &RigidDet, index: usize, rest: &[PathStep]) -> RigidDet {
    let none = |clause: &Option<KeyBody>| clause.as_ref().map(|_| KeyBody { body: empty(), columns: Arc::from([]) });
    let key = usize::from(rigid.key.is_some());
    let instance = usize::from(rigid.instance.is_some());
    if rigid.key.is_some() && index == 0 {
        let key = rigid.key.as_ref().map(|clause| cut_key_body(clause, rest));
        return RigidDet { key, instance: none(&rigid.instance), parts: Arc::from([]), ..rigid.clone() };
    }
    if rigid.instance.is_some() && index == key {
        let instance = rigid.instance.as_ref().map(|clause| cut_key_body(clause, rest));
        return RigidDet { instance, parts: Arc::from([]), ..rigid.clone() };
    }
    let parts = cut_list(&rigid.parts, index - key - instance, |part| Node::new(cut_atom(part.value(), rest)));
    RigidDet { parts, ..rigid.clone() }
}

/// A key body cut at `path`, which holds no columns yet where it is open.
fn cut_key_body(clause: &KeyBody, path: &[PathStep]) -> KeyBody {
    if path.is_empty() {
        return clause.clone();
    }
    KeyBody { body: cut_body(&clause.body, path), columns: Arc::from([]) }
}

fn cut_body(body: &Node<Body>, path: &[PathStep]) -> Node<Body> {
    let Some((step, rest)) = path.split_first() else { return body.clone() };
    Node::new(Body { conjuncts: cut_list(&body.value().conjuncts, step.0 as usize, |conjunct| cut_conjunct(conjunct, rest)) })
}

fn cut_conjunct(conjunct: &Conjunct, path: &[PathStep]) -> Conjunct {
    let Some((step, rest)) = path.split_first() else { return conjunct.clone() };
    let index = step.0 as usize;
    match conjunct {
        Conjunct::Atom(atom) => Conjunct::Atom(Node::new(cut_atom(atom.value(), path))),
        Conjunct::Not(Negated::Atom(atom)) => Conjunct::Not(Negated::Atom(Node::new(cut_atom(atom.value(), path)))),
        Conjunct::Not(Negated::Form(form)) => Conjunct::Not(Negated::Form(Arc::new(cut_conjunct(form, rest)))),
        Conjunct::Or(branches) => Conjunct::Or(cut_list(branches, index, |branch| cut_body(branch, rest))),
        Conjunct::If { test, then, otherwise } => match index {
            0 => Conjunct::If { test: cut_body(test, rest), then: empty(), otherwise: empty() },
            1 => Conjunct::If { test: test.clone(), then: cut_body(then, rest), otherwise: empty() },
            _ => Conjunct::If { test: test.clone(), then: then.clone(), otherwise: cut_body(otherwise, rest) },
        },
        Conjunct::All { domain, body } => match index {
            0 => Conjunct::All { domain: cut_body(domain, rest), body: empty() },
            _ => Conjunct::All { domain: domain.clone(), body: cut_body(body, rest) },
        },
        Conjunct::Constraint(_) => unreachable!("a constraint has no children"),
    }
}

fn cut_atom(atom: &Atom, path: &[PathStep]) -> Atom {
    let Some((step, rest)) = path.split_first() else { return atom.clone() };
    Atom { relation: atom.relation.clone(), sites: cut_list(&atom.sites, step.0 as usize, |site| cut_site(site, rest)) }
}

fn cut_site(site: &Site, path: &[PathStep]) -> Site {
    let Some((step, rest)) = path.split_first() else { return site.clone() };
    let arg = |arg: &SiteArg| match arg {
        SiteArg::Field(field) => SiteArg::Field(cut_site(field, rest)),
        arg => arg.clone(),
    };
    Site { column: site.column.clone(), value: SiteValue { args: cut_list(&site.value.args, step.0 as usize, arg) } }
}

/// The items of `items` before `index`, then `last` of the item at `index`.
fn cut_list<T: Clone>(items: &[T], index: usize, last: impl FnOnce(&T) -> T) -> Arc<[T]> {
    items[..index].iter().cloned().chain([last(&items[index])]).collect()
}

/// A list the prefix has not reached.
fn empty() -> Node<Body> {
    Node::new(Body { conjuncts: Arc::from([]) })
}

/// The refusals of the grammar on `prefix`: each complete node of its
/// partial form that no reader gives, as `crate::read::arclog` refuses
/// it: an `OR` of no branch, a site of no argument, and a head site that
/// makes its label or holds `0`.
pub(super) fn grammar(prefix: &Prefix<'_>) -> PrefixResult {
    let mut refusals = Vec::new();
    grammar_node(prefix, NodeRef::from(prefix.partial), NodePath::default(), &mut refusals);
    refused(refusals)
}

fn grammar_node(prefix: &Prefix<'_>, node: NodeRef<'_>, at: NodePath, out: &mut Vec<Refusal>) {
    let complete = !prefix.is_open(&at);
    let mut refuse = |message: &str, at: NodePath| out.push(Refusal { message: message.into(), at });
    match node {
        NodeRef::Conjunct(Conjunct::Or(branches)) if complete && branches.is_empty() => refuse("an `OR` holds its branches", at.clone()),
        NodeRef::Site(site) if complete && site.value.args.is_empty() => refuse("a site holds a label or a field site", at.clone()),
        NodeRef::InstanceInput(input) => {
            for (site, index) in input.head.iter().zip(0u32..) {
                let site_at = at.child(index);
                each_site_label(site, &mut Vec::new(), &mut |use_, _| match use_ {
                    LabelUse::Fresh(_) => refuse("a head site carries no `*`: the body or the key makes its label", site_at.clone()),
                    LabelUse::Zero => refuse("a head site holds no `0`: the body makes its label with `(= *X 0)`", site_at.clone()),
                    LabelUse::Join(_) | LabelUse::Key(_) => {}
                });
            }
        }
        _ => {}
    }
    for (child, index) in node.children().into_iter().zip(0u32..) {
        grammar_node(prefix, child, at.child(index), out);
    }
}

/// The refusals of the scope on `prefix`: each read of its partial form
/// whose name resolves to nothing, which no node written later declares,
/// since a form reads only the relations declared before it.
pub(super) fn scope(prefix: &Prefix<'_>) -> PrefixResult {
    let path = prefix.path;
    let program = prefix.scope.program;
    let unresolved = super::reads::form_reads(prefix.partial, path).into_iter().filter(|read| {
        matches!(program.resolution(&path.join(&read.at)), Some(crate::resolver::Resolution::Unresolved))
    });
    refused(unresolved.map(|read| Refusal { message: "the name resolves to nothing visible".into(), at: read.at }).collect())
}
