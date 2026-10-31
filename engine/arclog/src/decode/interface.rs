//! What a decode gives its caller beside the token mask, as
//! `docs/engine/synthesis.md#decode-interface` gives it: the rows and the
//! counts of the body of the clause in progress, and, at the `END` of an
//! `OUT` form, the consistency of its relation with the train pairs, and,
//! where the decode settings run the rule tests, at the `END` of a `RULE`
//! clause, the consistency of the clause's relation read as an output.

use std::sync::Arc;

use super::state::State;
use super::Decoder;
use crate::check::{check_shared_program, CheckCache, CheckedProgram, SolverClauses};
use crate::eval::examples::{scope_of, ExampleScope};
use crate::eval::ir::atom_modes;
use crate::eval::{BodyValue, Limits, Outcome, ParameterValues, RelationValue, RunFault, Stop, TableWork};
use crate::registry::Registry;
use crate::judge::candidates::PairCandidates;
use crate::judge::run::{Found, Tested};
use crate::judge::determination::{dets_read, descend_assignments, distinct_values, walk, Assignment, Det, End, EvaluationInputs, Walked};
use crate::program::path::{NodePath, PathStep};
use crate::program::{Atom, Body, Choose, ChoosePart, Clause, ClauseKeyword, Conjunct, ConstraintLabel, Constraint, DeclaredName, Form, Instance, LabelId, LabelUse, Negated, Node, Operand, PortName, Program, ProgramRelation, RelationName, RelationRef, Site, SiteArg, SiteValue};
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
    Consistent { assignments: Vec<Vec<(ProgramRelation, Arc<Relation>)>> },
    /// M_open does not solve every train pair.
    NotConsistent,
    /// A `DET` without `(ONE)` that the relation reads takes more than one
    /// value over the consistent assignments.
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
}

/// What a prefix gives at each joint assignment of the `DET`s it reads, in
/// the order of the walk, as `docs/engine/synthesis.md#decode-interface`
/// gives it: a prefix that reads no `DET` of several values gives one
/// entry, at the empty assignment.
#[derive(Clone, Debug)]
pub struct Assigned<T> {
    pub at: Vec<(Vec<Assignment>, T)>,
    /// The bound that ended the walk before its last assignment: the
    /// assignment cap, the table work cap, a bound of a run, the deadline or a cancellation.
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
        lists.into_iter().map(|kept| decoder.body_of(finished, own.clone(), kept.clone(), made(&kept))).collect()
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
        let form = self.output.as_ref()?;
        Some((|| {
            let checked = self.checked(self.state.resolved(self.context.registry), form)?;
            let relation = derived_at(&checked, form);
            let limits = self.limits();
            let parameters: Vec<_> = self.assignments.iter().map(|values| ParameterValues::determined(values.clone())).collect();
            let inputs = self.inputs(&checked, &limits);
            let evaluations: Vec<_> = parameters.iter().map(|values| inputs.at(values)).collect();
            crate::judge::attempts::attempts(&evaluations, &relation)
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
        Some(self.sub_body_values()?.into_vec().into_iter().map(|value| value.map(|rows| rows.map(|value| value.count()))).collect())
    }

    /// [`Decoder::rows`], with its count at the first assignment and its
    /// stop, if any, recorded on the last record of the trace. This
    /// decode's trace alone changes.
    pub fn observe_rows(&mut self, example: Option<Example>) -> Option<Outcome<Assigned<BodyValue>>> {
        let rows = self.rows(example)?;
        let (count, stop) = rows.as_ref().map_or((None, None), seen);
        self.annotate(|record| record.rows.push(RowsSeen { example, count }), stop);
        Some(rows)
    }

    /// [`Decoder::counts`], with the counts at the first assignment and the
    /// first stop, if any, recorded on the last record of the trace. This
    /// decode's trace alone changes.
    pub fn observe_counts(&mut self) -> Option<Box<[Outcome<Assigned<Option<u64>>>]>> {
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
    /// that of [`relation_dets`] for a relation table. Where `work` is given,
    /// the bindings of each evaluation, the walk's domains included, are
    /// counted in it, and a batch that takes the count past its cap stops the
    /// evaluation it is in.
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
        match descend_assignments(inputs, dets, root, self.context.settings.caps.assignments, &mut leaf).1 {
            Ok(()) => Ok(Assigned { at: found, stop: None }),
            Err(End::Stop(stop)) => Ok(Assigned { at: found, stop: Some(stop) }),
            Err(End::Fault(fault)) => Err(fault),
        }
    }

    /// The bounds of one request: the deadline of the decode settings from
    /// now, the decode's cancellation, and the stops that the decode holds.
    pub fn limits(&self) -> Limits {
        let mut limits=self.operation_limits.clone().unwrap_or_else(||self.context.settings.operation_limits());
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
    /// progress.
    pub fn sub_body(&self) -> Option<Outcome<SubBody>> {
        let _timed = crate::stats::span(crate::stats::Phase::TableSubBody);
        let (program, open) = self.state.partial()?;
        let open = open?;
        let (last, finished) = program.value().forms.split_last().expect("a partial program holds its partial form");
        let OpenClause { clause, kept, .. } = open_clause(last, &open, self.context.registry)?;
        let labels = atom_labels(&kept);
        Some(self.body_of(finished, clause, kept, labels))
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

    /// The sub-body of `clause` with the conjuncts `kept`: a complete clause
    /// that ends the program of the `finished` forms, whose relation has a
    /// column for each of `labels`, the labels `kept` makes.
    fn body_of(&self, finished: &[Form], clause: Clause, kept: Vec<Conjunct>, labels: Vec<LabelId>) -> Outcome<SubBody> {
        let form = NodePath::top(finished.len() as u32);
        let columns = crate::read::columns::slot_columns(labels, 0);
        let count = u32::try_from(kept.len()).expect("fewer than 2^32 conjuncts");
        let sub = Clause { body: Node::new(Body { conjuncts: kept.into() }), columns, ..clause };
        let forms = finished.iter().cloned().chain([Form::Clause(Node::new(sub))]).collect();
        let registry = self.context.registry;
        let resolved = resolve_last(&self.state.resolved(registry), &Node::new(Program { forms }), registry);
        let checked = self.checked(Arc::new(resolved), &form);
        checked.map(|program| {
            let relation = derived_at(&program, &form);
            let scope = scope_of(&program, &relation);
            SubBody { program, form, kept: (0..count).collect(), scope }
        })
    }

    /// The program that `resolved` resolves, checked, or a fault at `form`
    /// where a check refuses it. `resolved` holds the finished forms of the
    /// decode's state, and the check runs with their check cache.
    pub(super) fn checked(&self, resolved: Arc<ResolvedProgram>, form: &NodePath) -> Outcome<CheckedProgram> {
        self.state.checks().with(|cache| self.checked_with(resolved, form, cache))
    }

    /// [`Decoder::checked`] with `cache`, which the check fills.
    fn checked_with(&self, resolved: Arc<ResolvedProgram>, form: &NodePath, cache: &mut CheckCache) -> Outcome<CheckedProgram> {
        let registry = self.context.registry;
        let clauses = SolverClauses::of_shared_program(Arc::clone(&resolved));
        check_shared_program(resolved, &clauses, registry, cache).map_err(|refusals| {
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
            let resolved = Arc::new(resolve_last(&before.resolved(registry), program, registry));
            after.checks().with(|cache| self.checked_with(resolved, &form, cache))
        })
    }

    /// The consistency of the relation of the form that ends the program of
    /// `after`, where `before`, the state before the step, holds fewer forms
    /// and the decode judges the train pairs: of an `OUT` form when `tested`
    /// is [`Tested::Out`], and of a `RULE` clause when it is
    /// [`Tested::Rule`]; none for a form of the other kind.
    pub(super) fn consistency(&self, before: &State, after: &State, tested: Tested) -> Option<Consistency> {
        let train = self.train.as_ref()?;
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
            Err(fault) => return Some(Consistency::Fault(fault.clone())),
        };
        let output = derived_at(checked, &form);
        Some(self.test(checked, &output, train, tested))
    }

    /// The consistency test of `output` in `program`, at each joint
    /// assignment of the `DET`s it reads, under the assignment cap of the
    /// decode settings.
    fn test(&self, program: &CheckedProgram, output: &GraphRelation, train: &[PairCandidates<'_>], tested: Tested) -> Consistency {
        let dets: Vec<_> = dets_read(program, output.node);
        let limits = self.limits();
        let Walked { kept, end, .. } = walk(self.inputs(program, &limits), &dets, output, train, self.context.settings.caps.assignments, tested);
        match end {
            Err(End::Stop(stop)) => return Consistency::Stopped(stop),
            Err(End::Fault(fault)) => return Consistency::Fault(fault),
            Ok(()) => {}
        }
        if kept.is_empty() {
            return Consistency::NotConsistent;
        }
        for det in dets.iter().filter(|det| !det.open) {
            let values = distinct_values(&kept, &det.relation);
            if values.len() > 1 {
                return Consistency::SeveralValues { relation: det.relation.clone(), values };
            }
        }
        let parameters: Vec<_> = kept.iter().map(|assignment| ParameterValues::determined(assignment.values.clone())).collect();
        let inputs = self.inputs(program, &limits);
        let evaluations: Vec<_> = parameters.iter().map(|values| inputs.at(values)).collect();
        match tested.observed(&evaluations, &mut kept.iter().map(|assignment| assignment.observed.clone()).collect::<Vec<_>>(), output, train) {
            Ok(Found::Columns(_)) => Consistency::Consistent { assignments: kept.into_iter().map(|assignment| assignment.values).collect() },
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
            let open_at = match &*open.0 {
                [PathStep(0), PathStep(at), ..] => Some(*at as usize),
                _ => None,
            };
            Some(OpenClause { clause: clause.clone(), kept: complete_or_atoms(&clause.body, open_at, registry), open_at })
        }
        Form::Choose(choose) => {
            let choose = choose.value();
            let [PathStep(at), within @ ..] = &*open.0 else { return None };
            let open_at = within.first().map(|step| step.0 as usize);
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
            Some(OpenClause { clause, kept: conjuncts, open_at })
        }
        _ => None,
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
