//! What a decode gives its caller beside the token mask, as
//! `docs/engine/synthesis.md#decode-interface` gives it: the rows and the
//! counts of the body of the clause in progress, and, at the `END` of an
//! `OUT` form, the consistency of its relation with the train pairs, and,
//! where the decode settings run the rule tests, at the `END` of a `RULE`
//! clause, the consistency of the clause's relation read as an output.

use std::cell::Cell;
use std::sync::Arc;

use super::state::State;
use super::Decoder;
use crate::check::{check_shared_program, check_shared_program_over, CheckCache, CheckedProgram, SolverClauses};
use crate::eval::examples::{scope_of, ExampleScope};
use crate::eval::ir::atom_modes;
use crate::eval::{BodyValue, Cancellation, Limits, Outcome, ParameterValues, RelationValue, RunFault, Stop, TableWork};
use crate::registry::Registry;
use crate::judge::candidates::PairCandidates;
use crate::judge::run::{AtCap, Found, Tested};
use crate::judge::determination::{dets_read, descend_scoped, distinct_values, walk, Assignment, Det, Domains, End, EvaluationInputs, Walked};
use super::det_memo::SessionMemo;
use crate::program::path::{NodePath, PathStep};
use crate::program::{InstanceInput, InstanceInputPart, InstancePart, KeyClausePart, Atom, Body, Choose, ChoosePart, Clause, ClauseKeyword, Conjunct, ConstraintLabel, Constraint, DeclaredName, Form, Instance, LabelId, LabelUse, Negated, Node, Operand, PortName, Program, ProgramRelation, RelationName, RelationRef, Site, SiteArg, SiteValue};
use crate::relations::Relation;
use crate::stream::Token;
use crate::terms::Example;
use crate::resolver::{resolve_last, DependencyKind, GraphNodeIndex, ResolvedProgram};
use crate::trace::{DecodeRecord, RowsSeen};
use crate::types::{each_site_label, each_site_use, use_label, GraphRelation};

/// The consistency of the relation of an `OUT` form that its `END` finishes,
/// or, under the rule tests, of a `RULE` clause that its `END` finishes, with
/// the train pairs, as `docs/engine/synthesis.md#decode-interface` gives.
#[derive(Clone, Debug)]
pub enum Consistency {
    /// M_open over these joint assignments solves every train pair. Of an
    /// `OUT` form, the decode ends at it.
    Consistent { assignments: Vec<Vec<(ProgramRelation, Arc<Relation>)>>, stop: Option<Stop> },
    /// M_open does not solve every train pair.
    NotConsistent,
    /// Of a rule test: a `DET` without `(ONE)` that the relation reads takes
    /// more than one value over the consistent assignments. An `OUT` form
    /// gives no such verdict: M_open reads those values, as
    /// `docs/engine/synthesis.md#open-parameters` gives.
    SeveralValues { relation: ProgramRelation, values: Vec<Arc<Relation>> },
    /// A run faults, or, in a rule test, the grid columns of M_open are
    /// underdetermined.
    Fault(RunFault),
    /// The test reached a bound: the assignment cap, a cap of a run, the
    /// deadline or a cancellation.
    Stopped(Stop),
}

/// What a step of a decode gives: the tokens that the engine emits after
/// the token, and, where the token ends an `OUT` form of a decode that
/// judges the train pairs, the consistency of its relation; and, where it
/// ends a `RULE` clause of such a decode that runs the rule tests, the
/// consistency of the clause's relation.
#[derive(Clone, Debug)]
pub struct Step {
    pub forced: Box<[Token]>,
    /// The consistency of the `OUT` form that the token ends.
    pub consistency: Option<Consistency>,
    /// The consistency of the relation of the `RULE` clause that the token
    /// ends, an observation that ends no decode.
    pub rule_test: Option<Consistency>,
    /// The output sets of the test of `consistency` that ended at the model
    /// cap with the grids found so far.
    pub capped_sets: u64,
    /// The same count for the test of `rule_test`.
    pub rule_capped_sets: u64,
}

/// What a prefix gives at each joint assignment of the `DET`s it reads, in
/// the order of the walk, as `docs/engine/synthesis.md#decode-interface`
/// gives it: a prefix that reads no `DET` of several values gives one
/// entry, at the empty assignment.
#[derive(Clone, Debug)]
pub struct Assigned<T> {
    pub at: Vec<(Vec<Assignment>, T)>,
    /// The stop that ended the walk, or else the first stop of one assignment's
    /// path, whose bound is [`crate::eval::ReachedBound::is_assignment`] and which
    /// leaves the other assignments' entries available.
    pub stop: Option<Stop>,
}

impl<T> Assigned<T> {
    fn map<U>(self, mut f: impl FnMut(T) -> U) -> Assigned<U> {
        Assigned { at: self.at.into_iter().map(|(assigned, value)| (assigned, f(value))).collect(), stop: self.stop }
    }
}

/// The sub-body of the clause in progress, as a complete clause of its own
/// that ends a program of the finished forms.
pub struct SubBody {
    pub program: CheckedProgram,
    /// The path of that clause.
    pub form: NodePath,
    /// The indexes of its conjuncts.
    kept: Box<[u32]>,
    pub scope: ExampleScope,
}

impl SubBody {
    /// The column of the body's relation that holds the label `label`, a label
    /// that the body makes: the label's row position.
    pub fn column_of(&self, label: LabelId) -> Option<usize> {
        self.program.program.label_position(&self.form, label).map(|position| usize::from(position.0))
    }
}

/// What identifies the sub-body of the clause in progress at a state of a
/// decode ([`Decoder::sub_body_key`]).
#[derive(Clone, PartialEq, Eq, Debug)]
pub struct SubBodyKey {
    /// The source of the clause with the sub-body's conjuncts as its body: two
    /// states with equal finished forms and equal sources give equal sub-bodies.
    pub source: Vec<u8>,
    /// The conjunct in progress where the sub-body leaves it out.
    pub left_out: Option<LeftOut>,
}

/// A conjunct in progress that a sub-body leaves out.
#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub enum LeftOut {
    /// An atom of a relation with modes, no mode of which has a site at each
    /// of its bound columns yet.
    Atom,
    /// A conjunct that is no atom: a `NOT`, an `OR`, an `IF`, an `ALL` or a
    /// constraint, before its end.
    Conjunct,
}

/// A widening operation bound to its checked owner's evaluation scope.
/// Its fields are private: callers obtain it from [`Decoder::widening`],
/// never from a guessed clause keyword or the reads left in one branch.
pub struct BodyWidening<'d, 'a> {
    decoder: &'d Decoder<'a>,
    scope: ExampleScope,
}

impl BodyWidening<'_, '_> {
    fn keyword(&self) -> ClauseKeyword {
        match self.scope {
            ExampleScope::PerExample => ClauseKeyword::Rule,
            ExampleScope::TaskWide => ClauseKeyword::Det,
        }
    }

    /// Each widened branch of a clause, evaluated in the owner's scope.
    /// Retains the existing widening and binding rules; only the synthetic
    /// wrapper's execution context comes from the checked owner.
    pub fn clause(&self, clause: &Clause) -> Vec<Outcome<SubBody>> {
        let decoder = self.decoder;
        let registry = decoder.context.registry;
        let finished = &decoder.state.program().value().forms;
        let reads = |atom: &Atom| match &atom.relation {
            RelationRef::Declared(_) | RelationRef::Output(_) => true,
            RelationRef::Lib(name) => registry.algebra_relation(name).is_some_and(|relation| relation.frames.iter().any(|(_, rule)| rule.makes)),
            RelationRef::Fact(_) | RelationRef::DefinedPort(_) => false,
        };
        let mut lists = Vec::new();
        if !widen(clause.body.value().conjuncts.to_vec(), false, &reads, &mut lists) {
            let form = NodePath::top(finished.len() as u32);
            return vec![Err(RunFault { message: format!("the clause widens to more than {WIDENED_BODIES} bodies").into(), form })];
        }
        let own = Clause { keyword: self.keyword(), derives: decoder.fresh_relation(), ones: Arc::from([]), set: false, ..clause.clone() };
        let made = |kept: &[Conjunct]| crate::read::columns::made_labels(&Body { conjuncts: kept.into() });
        lists.into_iter().map(|kept| decoder.body_of(finished, own.clone(), kept, made)).collect()
    }

    /// Each written input clause, including its key context, widened in
    /// the checked instance's scope. No input can choose its own scope.
    pub fn input(&self, instance: &Instance, input: &PortName) -> Vec<Vec<Outcome<SubBody>>> {
        let key = instance.key.as_ref();
        let keyed = key.into_iter().flat_map(|key| key.value().inputs.iter()).map(|own| (true, own));
        let plain = instance.inputs.iter().map(|own| (false, own));
        keyed.chain(plain).filter(|(_, own)| own.value().name == *input).map(|(in_key, own)| {
            let before = key.filter(|_| in_key).into_iter().flat_map(|key| key.value().key.body.value().conjuncts.iter().map(unkeyed));
            let conjuncts = before.chain(own.value().body.value().conjuncts.iter().cloned()).collect();
            let clause = Clause { keyword: self.keyword(), derives: self.decoder.fresh_relation(), gloss: None, proposers: Arc::from([]), body: Node::new(Body { conjuncts }), ones: Arc::from([]), set: false, columns: Arc::from([]) };
            self.clause(&clause)
        }).collect()
    }
}

/// The most bodies that [`BodyWidening::clause`] gives for one clause.
pub const WIDENED_BODIES: usize = 32;

impl<'a> Decoder<'a> {
    /// The decode, judging the train pairs of `train`, the candidates of
    /// the task's train pairs under the world of its task data: at the `END`
    /// of each `OUT` form, [`Decoder::step`] gives the consistency of its
    /// relation, and, under the rule tests, at the `END` of each `RULE`
    /// clause that of the clause's relation.
    pub fn judging(mut self, train: Arc<[PairCandidates<'a>]>) -> Decoder<'a> {
        self.train = Some(train);
        self
    }

    /// The flag that cancels the evaluations of this decode. A fork takes a
    /// flag of its own.
    pub fn cancellation(&self) -> &crate::eval::Cancellation {
        &self.cancellation
    }

    /// The path of the `OUT` form at which the decode ended, where an `OUT`
    /// form was consistent.
    pub fn output(&self) -> Option<&NodePath> {
        self.output.as_ref()
    }

    /// The grid columns of the `OUT` form at which the decode ended, none
    /// until it ends.
    pub fn grid_columns(&self) -> Option<crate::eval::output::GridColumns> {
        self.output.as_ref().map(|_| crate::eval::output::GridColumns::OUT)
    }

    /// The attempts on each test input, or none until the decode ends at
    /// a consistent `OUT` form, as `docs/engine/synthesis.md#open-parameters` gives.
    pub fn attempts(&self) -> Option<Outcome<Box<[crate::judge::attempts::Attempts]>>> {
        Some(self.attempts_counted()?.map(|(attempts, _)| attempts))
    }

    /// [`Decoder::attempts`], with the count of the output sets on the test
    /// inputs that ended at the model cap with the grids found so far.
    pub fn attempts_counted(&self) -> Option<Outcome<(Box<[crate::judge::attempts::Attempts]>, u64)>> {
        let _request = self.begin_request();
        let form = self.output.as_ref()?;
        let capped = Cell::new(0);
        Some((|| {
            let checked = self.checked(self.state.resolved(self.context.registry), form)?;
            let relation = derived_at(&checked, form);
            let limits = self.limits();
            let parameters: Vec<_> = self.assignments.iter().map(|values| ParameterValues::determined(values.clone())).collect();
            let inputs = self.inputs(&checked, &limits);
            let evaluations: Vec<_> = parameters.iter().map(|values| inputs.at(values)).collect();
            let attempts = crate::judge::attempts::attempts(&evaluations, &relation, self.at_cap(&capped))?;
            Ok((attempts, capped.get()))
        })())
    }

    /// The rows of the sub-body of the clause in progress on `example`, at
    /// each joint assignment of the `DET`s that it reads, less the picks, which
    /// no clause reads before its form ends,
    /// `None` for a task-wide clause, such as a `DET`'s: the conjuncts of
    /// its body that are positive atoms, the open one with the sites given
    /// so far, and the complete conjuncts, from their entries in the result
    /// cache, as `docs/engine/reader.md#programs-as-values` gives. Their
    /// relation holds a column for each label of the positive atoms. A
    /// `ONE` mark is left out. Where the form in progress is a `CHOOSE`
    /// form, the clause in progress is its open `for`, `from` or `never`
    /// clause, and the conjuncts of a `for` clause that a `from` clause
    /// inside it follows are complete conjuncts of that sub-body. `None`
    /// where no clause is in progress. Where the sub-body does not check or
    /// does not compile, this gives a [`RunFault`] at the clause.
    ///
    /// Asking a per-example clause with `None`, or a task-wide clause on an
    /// example, is a fault of the caller, so this panics on one.
    pub fn rows(&self, example: Option<Example>) -> Option<Outcome<Assigned<BodyValue>>> {
        let _request = self.begin_request();
        Some(self.sub_body()?.and_then(|sub| self.assigned_rows(&sub, example, None)))
    }

    /// The [`ExampleScope`] of the sub-body that [`Decoder::rows`]
    /// evaluates, or the fault that the sub-body gives; `None` where no
    /// clause is in progress. It evaluates no body.
    pub fn rows_scope(&self) -> Option<Outcome<ExampleScope>> {
        Some(self.sub_body()?.map(|sub| sub.scope))
    }

    /// The count of the rows of the sub-body that [`Decoder::rows`] gives on
    /// each example of the task, or once for a task-wide clause, at each
    /// assignment, `None` in a count where the body is undefined or
    /// stopped. `None` where no clause is in progress.
    pub fn counts(&self) -> Option<Box<[Outcome<Assigned<Option<u64>>>]>> {
        let _request = self.begin_request();
        Some(self.sub_body_values()?.into_vec().into_iter().map(|value| value.map(|rows| rows.map(|value| value.count()))).collect())
    }

    /// [`Decoder::rows`], with its count at the first assignment and its
    /// stop, if any, recorded on the last record of the trace. This
    /// decode's trace alone changes.
    pub fn observe_rows(&mut self, example: Option<Example>) -> Option<Outcome<Assigned<BodyValue>>> {
        let _request = self.begin_request();
        let rows = self.rows(example)?;
        let (count, stop) = rows.as_ref().map_or((None, None), seen);
        self.annotate(|record| record.rows.push(RowsSeen { example, count }), stop);
        Some(rows)
    }

    /// [`Decoder::counts`], with the counts at the first assignment and the
    /// first stop, if any, recorded on the last record of the trace. This
    /// decode's trace alone changes.
    pub fn observe_counts(&mut self) -> Option<Box<[Outcome<Assigned<Option<u64>>>]>> {
        let _request = self.begin_request();
        let values = self.sub_body_values()?;
        let seen: Vec<_> = values.iter().map(|value| value.as_ref().map_or((None, None), seen)).collect();
        let counts: Box<[Option<u64>]> = seen.iter().map(|(count, _)| *count).collect();
        let stop = seen.iter().find_map(|(_, stop)| *stop);
        self.annotate(|record| record.counts = Some(counts), stop);
        Some(values.into_vec().into_iter().map(|value| value.map(|rows| rows.map(|value| value.count()))).collect())
    }

    /// Changes the last record of the trace, and sets its stop where it has
    /// none and `stop` is one.
    fn annotate(&mut self, change: impl FnOnce(&mut DecodeRecord), stop: Option<crate::trace::Stop>) {
        let Some(last) = self.trace.len().checked_sub(1) else { return };
        self.trace.update(last, |record| {
            change(record);
            record.stop = record.stop.or(stop);
        });
    }

    /// The value of the sub-body of the clause in progress on each example
    /// of the task, or once for a task-wide clause, at each assignment;
    /// `None` where no clause is in progress.
    pub(super) fn sub_body_values(&self) -> Option<Box<[Outcome<Assigned<BodyValue>>]>> {
        let sub = match self.sub_body()? {
            Ok(sub) => sub,
            Err(fault) => return Some(Box::new([Err(fault)])),
        };
        Some(self.values_of(&sub, None))
    }

    /// The value of `sub` on each example of the task, or once for a
    /// task-wide clause, at each assignment, counted in `work` where it is
    /// given.
    pub fn values_of(&self, sub: &SubBody, work: Option<&TableWork>) -> Box<[Outcome<Assigned<BodyValue>>]> {
        self.examples_of(sub.scope).into_iter().map(|example| self.assigned_rows(sub, example, work)).collect()
    }

    /// The examples a relation of `scope` is evaluated on: each example of
    /// the task, or the one task-wide request.
    pub fn examples_of(&self, scope: ExampleScope) -> Vec<Option<Example>> {
        match scope {
            ExampleScope::PerExample => self.task.examples().map(Some).collect(),
            ExampleScope::TaskWide => vec![None],
        }
    }

    fn assigned_rows(&self, sub: &SubBody, example: Option<Example>, work: Option<&TableWork>) -> Outcome<Assigned<BodyValue>> {
        let root = derived_at(&sub.program, &sub.form).node;
        self.assigned(&sub.program, root, &walked_dets(&sub.program, root), work, &mut |evaluation| evaluation.body(&sub.form, &sub.kept, example).map_err(End::Fault))
    }

    /// What `at` gives at each joint assignment of `dets`, in the order of
    /// the walk, for the relation at `root` of `program`. `dets` is the
    /// list of [`walked_dets`] for a body, as [`Decoder::rows`] gives it, and
    /// that of [`relation_dets`] for a relation table. Each evaluation of the
    /// walk, a domain or a leaf, counts its bindings in a count of its own
    /// under the cap of `work`, where that is given, and adds them to `work`: a
    /// batch that takes that count past the cap stops the evaluation it is in,
    /// and no other. An evaluation that stops at that cap, or at the byte
    /// budget of its assignment, rejects its assignment alone
    /// ([`crate::eval::ReachedBound::is_assignment`]).
    pub fn assigned<T>(&self, program: &CheckedProgram, root: GraphNodeIndex, dets: &[Det], work: Option<&TableWork>, at: &mut dyn FnMut(&crate::eval::Evaluation<'_>) -> Result<T, End>) -> Outcome<Assigned<T>> {
        let limits = match work {
            Some(work) => self.limits().counted_in(work.clone()),
            None => self.limits(),
        };
        let inputs = self.inputs(program, &limits);
        let mut found = Vec::new();
        let mut leaf = |evaluation: &crate::eval::Evaluation<'_>, assigned: &[Assignment]| {
            found.push((assigned.to_vec(), at(evaluation)?));
            Ok(())
        };
        // A table's walk takes the domains that the session's table walks
        // kept (`det_memo::SessionMemo`), where they would compute the same.
        let memo = work.map(|_| self.session.det_domains().get_or_init(|| SessionMemo::new(self.det_scope(), self.session)));
        let domains = memo.and_then(|memo| memo.domains(self.det_scope(), program, dets));
        let (_, end, first) = descend_scoped(inputs, dets, root, self.context.settings.caps.assignments, &mut leaf, domains.as_ref().map(|domains| domains as &dyn Domains));
        match end {
            Ok(()) => Ok(Assigned { at: found, stop: first }),
            Err(End::Stop(stop)) => Ok(Assigned { at: found, stop: Some(stop) }),
            Err(End::Fault(fault)) => Err(fault),
        }
    }

    /// The bounds of the request this decode is in ([`Decoder::request_work`]):
    /// its work count, the decode's cancellation, and the stops that the
    /// decode holds.
    pub fn limits(&self) -> Limits {
        let mut limits=self.operation_limits.clone().unwrap_or_else(||Limits::new(Some(self.context.settings.request_work_cap),Cancellation::default()).in_request(self.request_work()));
        limits.cancellation=self.cancellation.clone();
        let limits=limits.holding_in(Arc::clone(&self.held_stops));
        match &self.copies {
            Some(violations) => limits.checking_copies(violations.clone()),
            None => limits,
        }
    }

    pub(super) fn inputs<'p>(&'p self, program: &'p CheckedProgram, limits: &'p Limits) -> EvaluationInputs<'p> {
        let registry = self.context.registry;
        EvaluationInputs { program, concept: None, task: self.task, session: self.session, registry, constructions: self.constructions, limits }
    }

    /// The sub-body of the clause in progress, or `None` where none is in
    /// progress. The clause in progress of an `INIT` form is as
    /// [`Decoder::open_clause_in`] gives it.
    pub fn sub_body(&self) -> Option<Outcome<SubBody>> {
        let _timed = crate::stats::span(crate::stats::Phase::TableSubBody);
        let (program, open) = self.state.partial()?;
        let open = open?;
        let (_, finished) = program.value().forms.split_last().expect("a partial program holds its partial form");
        let OpenClause { clause, kept, .. } = self.open_clause_in(&self.state, &program, &open, || self.form_keyword(&self.state, &program))?;
        Some(self.body_of(finished, clause, kept, atom_labels))
    }

    /// The clause in progress of the form in progress of `program`, the
    /// partial program of `state`, whose innermost open node is at `open`, as
    /// [`open_clause`] gives it for a clause or a `CHOOSE` form. For an `INIT`
    /// form it is the clause of its open key body, or of its open input's
    /// body, with the key body's conjuncts before the input's where the input
    /// is keyed, and each `^` label of the key read as a label of the body.
    /// Where the engine has named a body and no token has opened it, that body
    /// is the clause in progress, and its conjuncts are those of the key body
    /// or none. `keyword` gives the keyword of an `INIT` form's clause, which
    /// its side gives, and is called for an `INIT` form alone. `None` where no
    /// clause is in progress.
    pub fn open_clause_in(&self, state: &State, program: &Node<Program>, open: &NodePath, keyword: impl FnOnce() -> Option<ClauseKeyword>) -> Option<OpenClause> {
        let registry = self.context.registry;
        let last = program.value().forms.last()?;
        let Form::Instance(instance) = last else { return open_clause(last, open, registry) };
        let keyword = keyword()?;
        let derives = ProgramRelation::Declared(RelationName(DeclaredName::Slot(state.open_slot())));
        let found = match open_instance_clause(instance.value(), open, keyword, derives.clone(), registry) {
            Some(found) => found,
            // The next token may open the body that the engine named.
            None => {
                let kept: Vec<Conjunct> = state.named_body_before()?.to_vec();
                let empty = Node::new(Body { conjuncts: Arc::from([]) });
                let clause = Clause { keyword, derives, gloss: None, proposers: Arc::from([]), body: empty, ones: Arc::from([]), set: false, columns: Arc::from([]) };
                OpenClause { clause, kept, open_at: None, below: Vec::new() }
            }
        };
        Some(OpenClause { kept: found.kept.iter().map(crate::study_clause::unkeyed).collect(), ..found })
    }

    /// What identifies the sub-body that [`Decoder::sub_body`] gives at this
    /// state, with no evaluation; `None` where no clause is in progress.
    pub fn sub_body_key(&self) -> Option<SubBodyKey> {
        let (program, open) = self.state.partial()?;
        let open = open?;
        let OpenClause { clause, kept, open_at, .. } = self.open_clause_in(&self.state, &program, &open, || self.form_keyword(&self.state, &program))?;
        let body = &clause.body;
        let left_out = match open_at.and_then(|at| body.value().conjuncts.get(at)) {
            Some(open) if complete_or_atoms(body, open_at, self.context.registry).len() < body.value().conjuncts.len() => Some(match open {
                Conjunct::Atom(_) => LeftOut::Atom,
                _ => LeftOut::Conjunct,
            }),
            _ => None,
        };
        Some(SubBodyKey { source: super::prefix_key::sub_body_key(&clause, &kept), left_out })
    }

    /// The sub-body of the clause in progress with its conjunct in progress
    /// as a complete conjunct: its value is the table of the body once a token
    /// closes that conjunct. Where that conjunct is an `OR` with a branch in
    /// progress, the branch's conjuncts stand in the place of the `OR`. The inner
    /// `None` stands for a body of no conjunct, and the outer one where no clause
    /// is in progress.
    pub fn closed_sub_body(&self) -> Option<Option<Outcome<SubBody>>> {
        let (program, open) = self.state.partial()?;
        let open = open?;
        let (last, finished) = program.value().forms.split_last()?;
        let registry = self.context.registry;
        let OpenClause { clause, mut kept, open_at, below } = self.open_clause_in(&self.state, &program, &open, || self.form_keyword(&self.state, &program))?;
        if let Some(at) = open_at {
            let conjuncts = clause.body.value().conjuncts.get(at);
            // A body keeps its open conjunct only where the conjunct binds what its mode asks.
            if let Some(open) = conjuncts.filter(|_| complete_or_atoms(&clause.body, Some(at), registry).len() < clause.body.value().conjuncts.len()) {
                // A branch of an `OR` in progress is a body of its own, around the conjuncts that stand around the `OR`.
                let mut branch = Vec::new();
                if branch_conjuncts(open, &below, &mut branch) {
                    kept.extend(branch);
                } else {
                    kept.push(open.clone());
                }
            }
        }
        if matches!(last, Form::Instance(_)) {
            kept = kept.iter().map(crate::study_clause::unkeyed).collect();
        }
        if kept.is_empty() {
            return Some(None);
        }
        Some(Some(self.body_of(finished, clause, kept, atom_labels)))
    }

    /// The keyword of a clause of the side of the form in progress of
    /// `program`, the partial program of `state`, whose side what it reads so
    /// far gives.
    fn form_keyword(&self, state: &State, program: &Node<Program>) -> Option<ClauseKeyword> {
        let registry = self.context.registry;
        let resolved = crate::resolver::resolve_prefix(&state.resolved(registry), program, registry);
        let at = NodePath::top(u32::try_from(program.value().forms.len().checked_sub(1)?).ok()?);
        Some(match resolved.form_side(&at)? {
            crate::resolver::Side::TaskWide => ClauseKeyword::Det,
            crate::resolver::Side::PerInput => ClauseKeyword::Rule,
        })
    }

    /// Whether a body in progress at this state is evaluated once for the task.
    pub(super) fn body_is_task_wide(&self) -> bool {
        match self.state.partial() {
            Some((program, _)) if matches!(program.value().forms.last(), Some(Form::Instance(_))) => self.form_keyword(&self.state, &program) == Some(ClauseKeyword::Det),
            _ => self.state.clause_is_task_wide(),
        }
    }

    /// Whether a read of the atom just opened at `opened`, the state after a
    /// step from this one, leaves the side of an `INIT` form as `task_wide`.
    pub(super) fn keeps_side(&self, opened: &super::state::State, task_wide: bool) -> bool {
        let registry = self.context.registry;
        let Some((program, _)) = opened.partial() else { return true };
        if !matches!(program.value().forms.last(), Some(Form::Instance(_))) {
            return true;
        }
        let resolved = crate::resolver::resolve_prefix(&opened.resolved(registry), &program, registry);
        let at = NodePath::top(program.value().forms.len() as u32 - 1);
        (resolved.form_side(&at) == Some(crate::resolver::Side::TaskWide)) == task_wide
    }

    /// The sub-body of the clause in progress less its open conjunct, where
    /// [`Decoder::sub_body`] holds that conjunct: the sub-body of its complete
    /// conjuncts, as `sub_body` builds one. `None` where no clause is in
    /// progress, no conjunct of it is open, `sub_body` leaves the open
    /// conjunct out, or the open conjunct is the only one.
    pub fn complete_sub_body(&self) -> Option<Outcome<SubBody>> {
        let (program, open) = self.state.partial()?;
        let open = open?;
        let (_, finished) = program.value().forms.split_last()?;
        let OpenClause { clause, mut kept, open_at, .. } = self.open_clause_in(&self.state, &program, &open, || self.form_keyword(&self.state, &program))?;
        let conjuncts = clause.body.value().conjuncts.len();
        // The open conjunct is the last of its body, and so the last of the sub-body where the sub-body holds it.
        let open_at = open_at.filter(|&at| at + 1 == conjuncts)?;
        if complete_or_atoms(&clause.body, Some(open_at), self.context.registry).len() < conjuncts {
            return None;
        }
        kept.pop();
        if kept.is_empty() {
            return None;
        }
        Some(self.body_of(finished, clause, kept, atom_labels))
    }

    /// Bind body reification to the checked owner before any branch or
    /// input is extracted. A widened branch must retain lifted reads and
    /// evidence access even when the read that decided the owner's side
    /// lies in a different input or branch.
    pub fn widening<'d>(&'d self, program: &CheckedProgram, relation: &GraphRelation) -> BodyWidening<'d, 'a> {
        BodyWidening { decoder: self, scope: scope_of(program, relation) }
    }

    /// A relation that no form of the decode declares: the one the next
    /// declaration would take.
    fn fresh_relation(&self) -> ProgramRelation {
        ProgramRelation::Declared(RelationName(DeclaredName::Slot(self.state.open_slot())))
    }

    /// The sub-body of `clause` with the conjuncts of `kept` that read only
    /// names that the `finished` forms and the lib give: a complete clause that
    /// ends the program of the `finished` forms, whose relation has a column
    /// for each of the labels that `labels` gives for those conjuncts. A
    /// conjunct that reads a name of the form in progress, such as an `Unfold`
    /// instance's read of its own outputs, stands outside the clause's scope
    /// and is left out, so the rows of the sub-body hold the rows of the completion.
    fn body_of(&self, finished: &[Form], clause: Clause, kept: Vec<Conjunct>, labels: impl FnOnce(&[Conjunct]) -> Vec<LabelId>) -> Outcome<SubBody> {
        let form = NodePath::top(finished.len() as u32);
        let registry = self.context.registry;
        let earlier = self.state.resolved(registry);
        let kept: Vec<Conjunct> = kept.into_iter().filter(|conjunct| reads_resolve(conjunct, &earlier, registry)).collect();
        let columns = crate::read::columns::slot_columns(labels(&kept), 0);
        let count = u32::try_from(kept.len()).expect("fewer than 2^32 conjuncts");
        let sub = Clause { body: Node::new(Body { conjuncts: kept.into() }), columns, ..clause };
        let forms = finished.iter().cloned().chain([Form::Clause(Node::new(sub))]).collect();
        let resolved = resolve_last(&earlier, &Node::new(Program { forms }), registry);
        if let Some(fault) = scope_fault(&resolved.diagnostics, &form) {
            return Err(fault);
        }
        let checked = self.checked(Arc::new(resolved.value), &form);
        checked.map(|program| {
            let program = self.over_closure(program, finished.len());
            let relation = derived_at(&program, &form);
            let scope = scope_of(&program, &relation);
            SubBody { program, form, kept: (0..count).collect(), scope }
        })
    }

    /// `checked`, a checked program whose last form, at the top-level
    /// `position`, a query is to evaluate, over the columns of each `DET` that
    /// the reads in the use closure of that form name
    /// ([`ResolvedProgram::narrowed_to_closure`]), so that a read in a form
    /// outside the closure leaves the evaluation as it is. `checked` itself
    /// where the reads of the closure name every column that its resolution
    /// keeps.
    fn over_closure(&self, checked: CheckedProgram, position: usize) -> CheckedProgram {
        match checked.program.narrowed_to_closure(position, self.context.registry) {
            Some((program, narrowed)) => checked.over_narrowed(program, &narrowed),
            None => checked,
        }
    }

    /// The program that `resolved` resolves, checked, or a fault at `form`
    /// where a check refuses it. `resolved` holds the finished forms of the
    /// decode's state, and the check runs with their check cache.
    pub(super) fn checked(&self, resolved: Arc<ResolvedProgram>, form: &NodePath) -> Outcome<CheckedProgram> {
        self.state.checks().with(|cache| self.checked_with(&self.state, resolved, form, cache))
    }

    /// [`Decoder::checked`] with `cache`, which the check fills, and
    /// `finished`, the state whose finished forms `resolved` holds.
    ///
    /// Where `resolved` is the resolution that [`resolve_last`] gives from
    /// the resolution of the finished forms of `finished`, with one form
    /// more, the check stands on what `finished` holds of those forms for
    /// each of its clones: their clauses, and what the checks read of
    /// each of them. Those are the same for each such program, which
    /// resolves the finished forms as the resolution of `finished` does.
    fn checked_with(&self, finished: &State, resolved: Arc<ResolvedProgram>, form: &NodePath, cache: &mut CheckCache) -> Outcome<CheckedProgram> {
        let registry = self.context.registry;
        let earlier = finished.resolved(registry);
        let forms = &earlier.program.value().forms;
        // A resolution that layers over another reports the address of that one, and one that does not reports its own, which is
        // the address of `earlier` where `resolved` is `earlier`, a program of as many forms.
        let layered = resolved.stats_finished_id() == Arc::as_ptr(&earlier) as usize
            && resolved.program.value().forms.len() == forms.len() + 1
            && forms.iter().zip(resolved.program.value().forms.iter()).all(|(held, form)| crate::solver::equal_forms(held, form));
        let extended = layered.then(|| finished.with_clauses(registry, |clauses| SolverClauses::of_last_form(clauses, Arc::clone(&resolved)))).flatten();
        let checked = match &extended {
            Some(clauses) => check_shared_program_over(resolved, clauses, registry, cache, finished.earlier_forms()),
            None => check_shared_program(Arc::clone(&resolved), &SolverClauses::of_shared_program(Arc::clone(&resolved)), registry, cache),
        };
        checked.map_err(|refusals| {
            let messages: Vec<&str> = refusals.iter().map(|refusal| &*refusal.message).collect();
            RunFault { message: format!("a check refuses the program: {}", messages.join("; ")).into(), form: form.clone() }
        })
    }

    /// The program of `after`, whose last form just finished, checked: it
    /// resolves from `before`, the state before the step, and is checked on
    /// the first ask, with the check cache of `after`'s finished forms, then
    /// shared by each clone of `after`.
    pub fn finished_checked<'s>(&self, before: &State, after: &'s State) -> &'s Outcome<CheckedProgram> {
        after.checked_last().get_or_init(|| {
            let program = after.program();
            let form = NodePath::top(program.value().forms.len() as u32 - 1);
            let registry = self.context.registry;
            let resolved = resolve_last(&before.resolved(registry), program, registry);
            if let Some(fault) = scope_fault(&resolved.diagnostics, &form) {
                return Err(fault);
            }
            let resolved = Arc::new(resolved.value);
            after.checks().with(|cache| self.checked_with(before, resolved, &form, cache))
        })
    }

    /// [`Decoder::finished_checked`] over the columns of the use closure of
    /// the last form of `after`, which the tables of that form and a request
    /// that evaluates it read: a `DET` has the columns that the reads in that
    /// closure name, whatever later forms read, so that the evaluation is the
    /// same in each decode that holds the form's QueryHash.
    pub fn finished_evaluated<'s>(&self, before: &State, after: &'s State) -> &'s Outcome<CheckedProgram> {
        after.evaluated_last().get_or_init(|| match self.finished_checked(before, after) {
            Ok(checked) => Ok(self.over_closure(checked.clone(), after.program().value().forms.len() - 1)),
            Err(fault) => Err(fault.clone()),
        })
    }

    /// The consistency of the relation of the form that ends the program of
    /// `after`, where `before`, the state before the step, holds fewer forms
    /// and the decode judges the train pairs: of an `OUT` form when `tested`
    /// is [`Tested::Out`], and of a `RULE` clause when it is
    /// [`Tested::Rule`]; none for a form of the other kind. The count is of
    /// the output sets of the test that ended at the model cap with the
    /// grids found so far.
    pub(super) fn consistency(&self, before: &State, after: &State, tested: Tested) -> Option<(Consistency, u64)> {
        let train = self.train.as_ref().filter(|_| self.evaluates)?;
        let program = after.program();
        let forms = &program.value().forms;
        if forms.len() == before.program().value().forms.len() {
            return None;
        }
        match (forms.last()?, tested) {
            (Form::Out(_), Tested::Out) => {}
            (Form::Clause(clause), Tested::Rule) if clause.value().keyword == ClauseKeyword::Rule => {}
            _ => return None,
        }
        let form = NodePath::top(forms.len() as u32 - 1);
        let checked = match self.finished_checked(before, after) {
            Ok(checked) => checked,
            Err(fault) => return Some((Consistency::Fault(fault.clone()), 0)),
        };
        let output = derived_at(checked, &form);
        let capped = Cell::new(0);
        let consistency = self.test(checked, &output, train, tested, self.at_cap(&capped));
        Some((consistency, capped.get()))
    }

    /// What the output sets of a case that reaches the model cap are: the
    /// grids of the models up to the cap, counting in `capped` each set that
    /// ends there.
    fn at_cap<'c>(&self, capped: &'c Cell<u64>) -> AtCap<'c> {
        AtCap::Grids { capped }
    }

    /// The consistency test of `output` in `program`, at each joint
    /// assignment of the `DET`s it reads, less the picks, whose models the
    /// test judges together, under the assignment cap of the decode settings.
    fn test(&self, program: &CheckedProgram, output: &GraphRelation, train: &[PairCandidates<'_>], tested: Tested, at_cap: AtCap<'_>) -> Consistency {
        let dets = relation_dets(program, output.node);
        let limits = self.limits();
        let Walked { kept, end, stop, .. } = walk(self.inputs(program, &limits), &dets, output, train, self.context.settings.caps.assignments, tested, at_cap);
        match end {
            // The walk ended before its last assignment, so what it kept depends on the order of the walk.
            Err(End::Stop(found)) => return Consistency::Stopped(found),
            Err(End::Fault(fault)) => return Consistency::Fault(fault),
            Ok(()) => {}
        }
        if kept.is_empty() {
            return stop.map_or(Consistency::NotConsistent, Consistency::Stopped);
        }
        if tested == Tested::Rule {
            for det in dets.iter().filter(|det| !det.open) {
                let values = distinct_values(&kept, &det.relation);
                if values.len() > 1 {
                    return Consistency::SeveralValues { relation: det.relation.clone(), values };
                }
            }
        }
        let parameters: Vec<_> = kept.iter().map(|assignment| ParameterValues::determined(assignment.values.clone())).collect();
        let inputs = self.inputs(program, &limits);
        let evaluations: Vec<_> = parameters.iter().map(|values| inputs.at(values)).collect();
        match tested.observed(&evaluations, &mut kept.iter().map(|assignment| assignment.observed.clone()).collect::<Vec<_>>(), output, train, at_cap) {
            Ok(Found::Columns(_)) => Consistency::Consistent { assignments: kept.into_iter().map(|assignment| assignment.values).collect(), stop },
            Ok(Found::None) => Consistency::NotConsistent,
            Ok(Found::Stopped(stop)) => Consistency::Stopped(stop),
            Err(fault) => Consistency::Fault(fault),
        }
    }
}

/// Appends to `out` the conjunct lists that `list` widens to, in the order of
/// the branches ([`BodyWidening::clause`]): the first `OR` or `IF` of `list`
/// that holds an atom `reads` admits is replaced by each branch in turn, and
/// each result widens again. A list that replaced an `OR` or an `IF` (`split`)
/// makes, at its first use, each label that only the branches it left made
/// ([`made_first`]). Gives `false` once `out` holds more than
/// [`WIDENED_BODIES`] lists.
fn widen(list: Vec<Conjunct>, split: bool, reads: &dyn Fn(&Atom) -> bool, out: &mut Vec<Vec<Conjunct>>) -> bool {
    let Some(at) = list.iter().position(|conjunct| splits(conjunct, reads)) else {
        out.push(if split { made_first(list) } else { list });
        return out.len() <= WIDENED_BODIES;
    };
    let branches: Vec<Vec<Conjunct>> = match &list[at] {
        Conjunct::Or(branches) => branches.iter().map(|branch| branch.value().conjuncts.to_vec()).collect(),
        Conjunct::If { test, then, otherwise } => {
            let negated = match &test.value().conjuncts[..] {
                [Conjunct::Atom(atom)] => Conjunct::Not(Negated::Atom(atom.clone())),
                _ => Conjunct::Not(Negated::Form(Arc::new(Conjunct::Or(Arc::from([test.clone()]))))),
            };
            vec![test.value().conjuncts.iter().chain(then.value().conjuncts.iter()).cloned().collect(), std::iter::once(negated).chain(otherwise.value().conjuncts.iter().cloned()).collect()]
        }
        _ => unreachable!("only an `OR` or an `IF` splits"),
    };
    branches.into_iter().all(|branch| {
        let mut next = list[..at].to_vec();
        next.extend(branch);
        next.extend(list[at + 1..].iter().cloned());
        widen(next, true, reads, out)
    })
}

/// The fault at `form` that the errors among `diagnostics`, those of a
/// resolution, make; none where it gave no error. A program whose name
/// resolves to nothing is no program to check or to evaluate.
fn scope_fault(diagnostics: &[crate::diagnostic::Diagnostic], form: &NodePath) -> Option<RunFault> {
    let errors: Vec<&str> = diagnostics.iter().filter(|diagnostic| diagnostic.severity == crate::diagnostic::Severity::Error).map(|diagnostic| &*diagnostic.message).collect();
    (!errors.is_empty()).then(|| RunFault { message: format!("the resolution refuses the program: {}", errors.join("; ")).into(), form: form.clone() })
}

/// Whether each name that `conjunct` reads, at any depth, resolves in a
/// program that ends the forms of `earlier`: a fact, a lib name of the
/// registry, or a relation that `earlier` declares.
fn reads_resolve(conjunct: &Conjunct, earlier: &ResolvedProgram, registry: &Registry) -> bool {
    let body = |body: &Node<Body>| body.value().conjuncts.iter().all(|conjunct| reads_resolve(conjunct, earlier, registry));
    match conjunct {
        Conjunct::Atom(atom) | Conjunct::Not(Negated::Atom(atom)) => match &atom.value().relation {
            RelationRef::Declared(_) | RelationRef::Output(_) => earlier.program_read(&atom.value().relation).is_some(),
            RelationRef::Lib(name) => registry.entry(name).is_some(),
            RelationRef::Fact(_) => true,
            RelationRef::DefinedPort(_) => false,
        },
        Conjunct::Not(Negated::Form(form)) => reads_resolve(form, earlier, registry),
        Conjunct::Constraint(_) => true,
        Conjunct::Or(branches) => branches.iter().all(body),
        Conjunct::If { test, then, otherwise } => body(test) && body(then) && body(otherwise),
        Conjunct::All { domain, body: inner } => body(domain) && body(inner),
    }
}

/// The distinct labels of the sites of the positive atoms of `conjuncts`, in
/// the order of their first use.
fn atom_labels(conjuncts: &[Conjunct]) -> Vec<LabelId> {
    let mut labels: Vec<LabelId> = Vec::new();
    for conjunct in conjuncts {
        if let Conjunct::Atom(atom) = conjunct {
            for site in atom.value().sites.iter() {
                each_site_label(site, &mut Vec::new(), &mut |label, _| {
                    if let Some(label) = use_label(label)
                        && !labels.contains(&label)
                    {
                        labels.push(label);
                    }
                });
            }
        }
    }
    labels
}

/// `conjunct` with each `^X` label of a key clause's body made `*X`, since a
/// clause has no key.
fn unkeyed(conjunct: &Conjunct) -> Conjunct {
    let body = |body: &Node<Body>| Node::new(Body { conjuncts: body.value().conjuncts.iter().map(unkeyed).collect() });
    let atom = |atom: &Node<Atom>| {
        mapped_atom(atom, &mut |label| match label {
            LabelUse::Key(label) => LabelUse::Fresh(label),
            other => other,
        })
    };
    match conjunct {
        Conjunct::Atom(own) => Conjunct::Atom(atom(own)),
        Conjunct::Not(Negated::Atom(own)) => Conjunct::Not(Negated::Atom(atom(own))),
        Conjunct::Not(Negated::Form(inner)) => Conjunct::Not(Negated::Form(Arc::new(unkeyed(inner)))),
        Conjunct::Constraint(constraint) => Conjunct::Constraint(*constraint),
        Conjunct::Or(branches) => Conjunct::Or(branches.iter().map(body).collect()),
        Conjunct::If { test, then, otherwise } => Conjunct::If { test: body(test), then: body(then), otherwise: body(otherwise) },
        Conjunct::All { domain, body: inner } => Conjunct::All { domain: body(domain), body: body(inner) },
    }
}

/// `atom` with each label use at any depth of its sites replaced by what `map` gives.
fn mapped_atom(atom: &Node<Atom>, map: &mut dyn FnMut(LabelUse) -> LabelUse) -> Node<Atom> {
    Node::new(Atom { relation: atom.value().relation.clone(), sites: atom.value().sites.iter().map(|site| mapped_site(site, map)).collect() })
}

/// `site` with each label use at any depth of it replaced by what `map` gives.
fn mapped_site(site: &Site, map: &mut dyn FnMut(LabelUse) -> LabelUse) -> Site {
    let args = site
        .value
        .args
        .iter()
        .map(|arg| match arg {
            SiteArg::Label(label) => SiteArg::Label(map(*label)),
            SiteArg::NamedLabel { name, label } => SiteArg::NamedLabel { name: name.clone(), label: map(*label) },
            SiteArg::Field(field) => SiteArg::Field(mapped_site(field, map)),
        })
        .collect();
    Site { column: site.column.clone(), value: SiteValue { args } }
}

/// `list`, a list of conjuncts that replaced an `OR` or an `IF`, with the first
/// use at a site of each label that it reads and no conjunct in it makes made:
/// an `OR` exports a label that its first branch makes to the later branches
/// that join it, and a branch alone makes none.
fn made_first(list: Vec<Conjunct>) -> Vec<Conjunct> {
    let mut made: Vec<LabelId> = Vec::new();
    for conjunct in &list {
        each_made(conjunct, &mut made);
    }
    list.into_iter()
        .map(|conjunct| match &conjunct {
            Conjunct::Atom(atom) => Conjunct::Atom(mapped_atom(atom, &mut |label| match label {
                LabelUse::Join(label) if !made.contains(&label) => {
                    made.push(label);
                    LabelUse::Fresh(label)
                }
                other => other,
            })),
            Conjunct::Constraint(constraint) => {
                let mut make = |label: ConstraintLabel| {
                    let fresh = label.fresh || !made.contains(&label.label);
                    made.push(label.label);
                    ConstraintLabel { fresh, ..label }
                };
                let first = make(constraint.first);
                let second = match constraint.second {
                    Operand::Label(label) => Operand::Label(make(label)),
                    Operand::Zero => Operand::Zero,
                };
                Conjunct::Constraint(Constraint { first, second, ..*constraint })
            }
            _ => conjunct,
        })
        .collect()
}

/// Adds to `made` each label that `conjunct` makes, at any depth of it.
fn each_made(conjunct: &Conjunct, made: &mut Vec<LabelId>) {
    let mut add = |label: LabelId| {
        if !made.contains(&label) {
            made.push(label);
        }
    };
    match conjunct {
        Conjunct::Atom(atom) | Conjunct::Not(Negated::Atom(atom)) => {
            for site in atom.value().sites.iter() {
                each_site_use(site, &mut |label| {
                    if let LabelUse::Fresh(label) | LabelUse::Key(label) = label {
                        add(label);
                    }
                });
            }
        }
        Conjunct::Constraint(constraint) => {
            if constraint.first.fresh {
                add(constraint.first.label);
            }
            if let Operand::Label(second) = constraint.second
                && second.fresh
            {
                add(second.label);
            }
        }
        Conjunct::Not(Negated::Form(inner)) => each_made(inner, made),
        Conjunct::Or(branches) => branches.iter().flat_map(|branch| branch.value().conjuncts.iter()).for_each(|inner| each_made(inner, made)),
        Conjunct::If { test, then, otherwise } => [test, then, otherwise].into_iter().flat_map(|body| body.value().conjuncts.iter()).for_each(|inner| each_made(inner, made)),
        Conjunct::All { domain, body } => [domain, body].into_iter().flat_map(|body| body.value().conjuncts.iter()).for_each(|inner| each_made(inner, made)),
    }
}

/// Whether `conjunct` is an `OR` or an `IF` that holds, in its branches or its
/// test, at any depth of `OR` and `IF`, an atom that `reads` admits.
fn splits(conjunct: &Conjunct, reads: &dyn Fn(&Atom) -> bool) -> bool {
    let holds = |body: &Node<Body>| body.value().conjuncts.iter().any(|inner| match inner {
        Conjunct::Atom(atom) => reads(atom.value()),
        other => splits(other, reads),
    });
    match conjunct {
        Conjunct::Or(branches) => branches.iter().any(holds),
        Conjunct::If { test, then, otherwise } => [test, then, otherwise].into_iter().any(holds),
        _ => false,
    }
}

/// The clause in progress of a form: the clause to build the sub-body on,
/// the conjuncts of the sub-body, and the index of the conjunct in
/// progress in the clause's body, if there is one.
pub struct OpenClause {
    pub clause: Clause,
    pub kept: Vec<Conjunct>,
    pub open_at: Option<usize>,
    /// The path of the innermost open node below the conjunct in progress.
    pub below: Vec<PathStep>,
}

/// The clause in progress of `form`, whose innermost open node is at
/// `open`, as a clause to build the sub-body on, and the conjuncts of the
/// sub-body: a clause's own body, or the open clause of a `CHOOSE` form,
/// which a `from` clause inside a `for` clause follows with the conjuncts
/// of that `for` clause. `None` where `form` is neither or holds no open
/// clause.
pub fn open_clause(form: &Form, open: &NodePath, registry: &Registry) -> Option<OpenClause> {
    match form {
        Form::Clause(clause) => {
            let clause = clause.value();
            let (open_at, below) = match &*open.0 {
                [PathStep(0), PathStep(at), below @ ..] => (Some(*at as usize), below.to_vec()),
                _ => (None, Vec::new()),
            };
            Some(OpenClause { clause: clause.clone(), kept: complete_or_atoms(&clause.body, open_at, registry), open_at, below })
        }
        Form::Choose(choose) => {
            let choose = choose.value();
            let [PathStep(at), within @ ..] = &*open.0 else { return None };
            let open_at = within.first().map(|step| step.0 as usize);
            let below = within.get(1..).map_or_else(Vec::new, <[PathStep]>::to_vec);
            let (body, before) = open_part(choose, choose.parts().nth(*at as usize)?)?;
            let conjuncts = before.iter().flat_map(|body| body.conjuncts.iter().cloned()).chain(complete_or_atoms(body, open_at, registry)).collect();
            let clause = Clause {
                keyword: ClauseKeyword::Rule,
                derives: ProgramRelation::Declared(choose.name.clone()),
                gloss: None,
                proposers: Arc::from([]),
                body: body.clone(),
                ones: Arc::from([]),
                set: false,
                columns: Arc::from([]),
            };
            Some(OpenClause { clause, kept: conjuncts, open_at, below })
        }
        _ => None,
    }
}

/// The clause in progress of the `INIT` form `instance`, whose innermost open
/// node is at `open`: a clause of `keyword` that derives `derives`, whose
/// conjuncts are those of the open key body, or those of the open input's body,
/// after the key body's where the input is keyed. `None` where no body of the
/// form is open.
fn open_instance_clause(instance: &Instance, open: &NodePath, keyword: ClauseKeyword, derives: ProgramRelation, registry: &Registry) -> Option<OpenClause> {
    fn input_body<'i>(input: &'i Node<InstanceInput>, steps: &'i [PathStep]) -> Option<(&'i Node<Body>, &'i [PathStep])> {
        let (step, within) = steps.split_first()?;
        match input.value().parts().nth(step.0 as usize)? {
            InstanceInputPart::Body => Some((&input.value().body, within)),
            InstanceInputPart::Head(_) => None,
        }
    }
    let (step, within) = open.0.split_first()?;
    let (before, (body, within)) = match instance.parts().nth(step.0 as usize)? {
        InstancePart::Key => {
            let key = instance.key.as_ref()?.value();
            let (step, within) = within.split_first()?;
            match key.parts().nth(step.0 as usize)? {
                KeyClausePart::Body => (None, (&key.key.body, within)),
                KeyClausePart::Input(index) => (Some(key.key.body.value()), input_body(key.inputs.get(index)?, within)?),
            }
        }
        InstancePart::Input(index) => (None, input_body(instance.inputs.get(index)?, within)?),
    };
    let open_at = within.first().map(|step| step.0 as usize);
    let below = within.get(1..).map_or_else(Vec::new, <[PathStep]>::to_vec);
    let kept = before.iter().flat_map(|body| body.conjuncts.iter().cloned()).chain(complete_or_atoms(body, open_at, registry)).collect();
    let clause = Clause { keyword, derives, gloss: None, proposers: Arc::from([]), body: body.clone(), ones: Arc::from([]), set: false, columns: Arc::from([]) };
    Some(OpenClause { clause, kept, open_at, below })
}

/// Adds to `found` the conjuncts of the branch in progress of `conjunct`, an `OR`
/// whose innermost open node is at `below`, with those of each `OR` in that
/// branch that holds the open node. Gives whether the open node stands in such
/// branches alone, with no other form of a body around it.
fn branch_conjuncts(conjunct: &Conjunct, below: &[PathStep], found: &mut Vec<Conjunct>) -> bool {
    let Conjunct::Or(branches) = conjunct else { return false };
    let Some((branch, below)) = below.split_first() else { return false };
    let Some(body) = branches.get(branch.0 as usize) else { return false };
    let conjuncts = &body.value().conjuncts;
    let Some((at, below)) = below.split_first() else {
        found.extend(conjuncts.iter().cloned());
        return true;
    };
    found.extend(conjuncts.iter().take(at.0 as usize).cloned());
    match conjuncts.get(at.0 as usize) {
        None => true,
        Some(open @ (Conjunct::Atom(_) | Conjunct::Not(Negated::Atom(_)))) => {
            found.push(open.clone());
            true
        }
        Some(open) => branch_conjuncts(open, below, found),
    }
}

/// The body of `part` of `choose`, and the `for` body that precedes it
/// where `part` is a `from` clause inside the `for` clause.
fn open_part(choose: &Choose, part: ChoosePart) -> Option<(&Node<Body>, Option<&Body>)> {
    match part {
        ChoosePart::For => Some((&choose.rows.as_ref()?.body, None)),
        ChoosePart::From => Some((&choose.from, choose.rows.as_ref().filter(|_| choose.from_inside_for).map(|rows| rows.body.value()))),
        ChoosePart::Never(index) => Some((choose.never.get(index)?, None)),
    }
}

/// The conjuncts of `body` that are complete, or are positive atoms of a
/// relation with no mode or with a mode that has a site at each of its
/// bound columns, where the conjunct at `open_at` is the one in progress.
/// An atom of an algebra relation bounds the completion's rows only once
/// one of its modes has its sites; a site in progress with no argument yet
/// is no site.
fn complete_or_atoms(body: &Node<Body>, open_at: Option<usize>, registry: &Registry) -> Vec<Conjunct> {
    let kept = |(index, conjunct): &(usize, &Conjunct)| {
        open_at != Some(*index)
            || matches!(conjunct, Conjunct::Atom(atom) if {
                let modes = atom_modes(registry, atom.value());
                modes.is_empty() || modes.iter().any(|mode| mode.bound.iter().all(|column| atom.value().sites.iter().any(|site| &site.column == column && !site.value.args.is_empty())))
            })
    };
    body.value().conjuncts.iter().enumerate().filter(kept).map(|(_, conjunct)| conjunct.clone()).collect()
}

/// The relation that the form at `form` derives in `program`: a clause
/// relation, a chosen relation where the clause has `ONE` marks, the
/// parameter of a `DET` clause with no `ONE` mark, or the relation of an
/// `OUT` form.
pub fn derived_at(program: &CheckedProgram, form: &NodePath) -> GraphRelation {
    let resolved = &program.program;
    let node = (0..resolved.graph.nodes.len())
        .map(|index| GraphNodeIndex(u32::try_from(index).expect("fewer than 2^32 nodes")))
        .find(|&node| {
            matches!(resolved.graph.nodes[node.0 as usize].kind, DependencyKind::Clause(_) | DependencyKind::Parameter(_) | DependencyKind::Chosen(_) | DependencyKind::Out(_)) && resolved.forms_of(node).contains(form)
        })
        .expect("a checked clause or `OUT` form derives its relation");
    GraphRelation { node, output: None }
}

/// The `DET`s whose joint assignments a walk over the body of the clause
/// that derives the relation at `root` of `program` visits: those it
/// reads, less the picks, which no clause reads before its form ends, and
/// `root` itself, which that body does not read.
pub fn walked_dets(program: &CheckedProgram, root: GraphNodeIndex) -> Vec<Det> {
    dets_read(program, root).into_iter().filter(|det| !det.pick && det.node != root).collect()
}

/// The `DET`s whose joint assignments a walk over the relation at `node`
/// of a finished form visits: those it reads, less the picks, with `node`
/// itself, which the walk assigns each value of its domain where it is a
/// `DET`'s parameter.
pub fn relation_dets(program: &CheckedProgram, node: GraphNodeIndex) -> Vec<Det> {
    dets_read(program, node).into_iter().filter(|det| !det.pick).collect()
}

/// Assignable parameter DETs in the full program's native dependency order.
/// Model picks are excluded, including picks outside OUT's dependencies.
pub fn held_dets(program: &CheckedProgram) -> Vec<Det> {
    crate::judge::determination::held_dets(program)
}

/// The count at the first assignment of `rows`, and the stop of that value
/// or of the walk, as the trace records them.
fn seen(rows: &Assigned<BodyValue>) -> (Option<u64>, Option<crate::trace::Stop>) {
    let first = rows.at.first().map(|(_, value)| value);
    let stopped = first.and_then(|value| match &value.0 {
        RelationValue::Stopped(stop) => Some(stop.bound.into()),
        RelationValue::Rows(_) | RelationValue::Undefined => None,
    });
    (first.and_then(BodyValue::count), stopped.or(rows.stop.as_ref().map(|stop| stop.bound.into())))
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::read::read_solver;

    /// The number of conjuncts that the clause in progress of a `CHOOSE`
    /// form with a `for` clause, a `from` clause inside it and a `never`
    /// clause gives when its innermost open node is at `open`; the last
    /// conjunct of each clause is not an atom.
    fn conjuncts_open_at(open: &[u32]) -> usize {
        let text = "(RULE &a (input *P *C))\n(CHOOSE &pick (for ((&a ^P)) (from (&a P *C) (!= P C))) (never (&a *P *C) (&a (:P *Q) C) (!= P Q)))\n";
        let solver = read_solver("t", text, "", &|_| None).expect("the file reads").value;
        let program = solver.concept_case().program.clone();
        let form = program.value().forms.last().expect("a form").clone();
        let open = NodePath(open.iter().copied().map(PathStep).collect());
        open_clause(&form, &open, Registry::get()).map_or(0, |open| open.kept.len())
    }

    #[test]
    fn a_choose_gives_the_conjuncts_of_its_open_clause() {
        let (for_clause, from_inside_for, never) = (conjuncts_open_at(&[0, 0]), conjuncts_open_at(&[1, 1]), conjuncts_open_at(&[2, 2]));
        assert_eq!(for_clause, 1, "the `for` clause");
        assert_eq!(from_inside_for, 2, "the `for` conjunct, then the `from` atom, and not the open comparison");
        assert_eq!(never, 2, "the `never` clause");
    }
}
