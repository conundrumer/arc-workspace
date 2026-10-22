//! What a decode gives its caller beside the token mask, as
//! `docs/engine/synthesis.md#decode-interface` gives it: the rows and the
//! counts of the body of the clause in progress, and, at the `END` of a
//! `RULE` clause, the consistency of the new relation, read as `&output`,
//! with the train pairs.

use std::sync::Arc;
use std::time::Instant;

use super::Decoder;
use crate::check::{check_shared_program, CheckCache, CheckedProgram, SolverClauses};
use crate::eval::examples::{scope_of, ExampleScope};
use crate::eval::{BodyValue, Limits, Outcome, ParameterValues, RunFault, Stop};
use crate::judge::candidates::PairCandidates;
use crate::judge::determination::{dets_read, distinct_values, walk, End, EvaluationInputs, Walked};
use crate::program::path::{NodePath, PathStep};
use crate::program::{Body, Clause, ClauseKeyword, Conjunct, Form, Node, Program, ProgramRelation};
use crate::relations::Relation;
use crate::stream::Token;
use crate::terms::Example;
use crate::resolver::{DependencyKind, GraphNodeIndex};
use crate::types::{each_site_label, use_label, GraphRelation};

/// The consistency of a relation that a `RULE` clause's `END` finishes,
/// read as `&output`, with the train pairs, as
/// `docs/engine/synthesis.md#decode-interface` gives.
#[derive(Clone, Debug)]
pub enum Consistency {
    /// M_open over these joint assignments solves every train pair.
    /// The decode ends at this relation.
    Consistent { assignments: Vec<Vec<(ProgramRelation, Arc<Relation>)>> },
    /// M_open does not solve every train pair.
    NotConsistent,
    /// A `DET` without `(ONE)` that the relation reads takes more than one
    /// value over the consistent assignments.
    SeveralValues { relation: ProgramRelation, values: Vec<Arc<Relation>> },
    /// The grid columns of M_open are underdetermined, or a run faults.
    Fault(RunFault),
    /// The test reached a bound: the assignment cap, a cap of a run, the
    /// deadline or a cancellation.
    Stopped(Stop),
}

/// What a step of a decode gives: the tokens that the engine emits after
/// the token, and, where the token ends a `RULE` clause of a decode that
/// judges the train pairs, the consistency of its relation.
#[derive(Clone, Debug)]
pub struct Step {
    pub forced: Box<[Token]>,
    pub consistency: Option<Consistency>,
    pub(super) columns: Option<crate::eval::output::GridColumns>,
}

/// The sub-body of the clause in progress, as a complete clause of its own
/// that ends a program of the finished forms.
struct SubBody {
    program: CheckedProgram,
    /// The path of that clause.
    form: NodePath,
    /// The indexes of its conjuncts.
    kept: Box<[u32]>,
    scope: ExampleScope,
}

impl<'a> Decoder<'a> {
    /// The decode, judging the train pairs of `train`, the candidates of
    /// the task's train pairs under the world of its task data: at the `END`
    /// of each `RULE` clause, [`Decoder::step`] gives the consistency of its
    /// relation.
    pub fn judging(mut self, train: Arc<[PairCandidates<'a>]>) -> Decoder<'a> {
        self.train = Some(train);
        self
    }

    /// The flag that cancels the evaluations of this decode. A fork takes a
    /// flag of its own.
    pub fn cancellation(&self) -> &crate::eval::Cancellation {
        &self.cancellation
    }

    /// The relation at which the decode ended, its `&output`, where a
    /// relation was consistent.
    pub fn output(&self) -> Option<&ProgramRelation> {
        self.output.as_ref()
    }

    /// The attempts on each test input, or none until the decode ends at
    /// a consistent relation, as `docs/engine/synthesis.md#open-parameters` gives.
    pub fn attempts(&self) -> Option<Outcome<Box<[crate::judge::attempts::Attempts]>>> {
        self.output.as_ref()?;
        let form = NodePath::top(self.program().value().forms.len() as u32 - 1);
        Some((|| {
            let checked = self.checked(self.program(), &form)?;
            let relation = derived_at(&checked, &form);
            let limits = self.limits();
            let parameters: Vec<_> = self.assignments.iter().map(|values| ParameterValues::determined(values.clone())).collect();
            let inputs = self.inputs(&checked, &limits);
            let evaluations: Vec<_> = parameters.iter().map(|values| inputs.at(values)).collect();
            crate::judge::attempts::attempts(&evaluations, &relation, self.columns.expect("a consistent decode has grid columns"))
        })())
    }

    /// The rows of the sub-body of the clause in progress on `example`,
    /// `None` for a task-wide clause, such as a `DET`'s: the conjuncts of
    /// its body that are positive atoms, the open one with the sites given
    /// so far, and the complete conjuncts, from their entries in the result
    /// cache, as `docs/engine/reader.md#programs-as-values` gives. Their
    /// relation holds a column for each label of the positive atoms. A
    /// `ONE` mark is left out. `None` where no clause is in progress. Where
    /// the sub-body does not check or does not compile, this gives a
    /// [`RunFault`] at the clause.
    ///
    /// Asking a per-example clause with `None`, or a task-wide clause on an
    /// example, is a fault of the caller, so this panics on one.
    pub fn rows(&self, example: Option<Example>) -> Option<Outcome<BodyValue>> {
        Some(self.sub_body()?.and_then(|sub| self.sub_body_rows(&sub, example)))
    }

    /// The count of the rows of the sub-body that [`Decoder::rows`] gives on
    /// each example of the task, or once for a task-wide clause, `None` in
    /// a count where the body is undefined or stopped. `None` where no
    /// clause is in progress.
    pub fn counts(&self) -> Option<Box<[Outcome<Option<u64>>]>> {
        let sub = match self.sub_body()? {
            Ok(sub) => sub,
            Err(fault) => return Some(Box::new([Err(fault)])),
        };
        let examples: Vec<Option<Example>> = match sub.scope {
            ExampleScope::PerExample => self.task.examples().map(Some).collect(),
            ExampleScope::TaskWide => vec![None],
        };
        Some(examples.into_iter().map(|example| self.sub_body_rows(&sub, example).map(|value| value.count())).collect())
    }

    fn sub_body_rows(&self, sub: &SubBody, example: Option<Example>) -> Outcome<BodyValue> {
        let parameters = ParameterValues::determined([]);
        let limits = self.limits();
        self.inputs(&sub.program, &limits).at(&parameters).body(&sub.form, &sub.kept, example)
    }

    /// The bounds of one request: the deadline of the decode settings from
    /// now, and the decode's cancellation.
    fn limits(&self) -> Limits {
        Limits { deadline: Some(Instant::now() + self.context.settings.deadline), cancellation: self.cancellation.clone() }
    }

    fn inputs<'p>(&'p self, program: &'p CheckedProgram, limits: &'p Limits) -> EvaluationInputs<'p> {
        let registry = self.context.registry;
        EvaluationInputs { program, concept: None, task: self.task, session: self.session, registry, constructions: self.constructions, limits }
    }

    /// The sub-body of the clause in progress, or `None` where none is in
    /// progress.
    fn sub_body(&self) -> Option<Outcome<SubBody>> {
        let (program, open) = self.state.partial()?;
        let open = open?;
        let (last, finished) = program.value().forms.split_last().expect("a partial program holds its partial form");
        let Form::Clause(clause) = last else { return None };
        let clause = clause.value();
        let form = NodePath::top(finished.len() as u32);
        let kept: Vec<Conjunct> = clause.body.value().conjuncts.iter().enumerate().filter(|(index, conjunct)| complete_or_atom(&open, *index, conjunct)).map(|(_, conjunct)| conjunct.clone()).collect();
        let mut labels = Vec::new();
        for conjunct in &kept {
            if let Conjunct::Atom(atom) = conjunct {
                for site in atom.value().sites.iter() {
                    each_site_label(site, &mut Vec::new(), &mut |label, _| labels.extend(use_label(label)));
                }
            }
        }
        let mut distinct = Vec::new();
        for label in labels {
            if !distinct.contains(&label) {
                distinct.push(label);
            }
        }
        let columns = super::state::slot_columns(distinct, 0);
        let count = u32::try_from(kept.len()).expect("fewer than 2^32 conjuncts");
        let sub = Clause { body: Node::new(Body { conjuncts: kept.into() }), ones: Arc::from([]), columns, ..clause.clone() };
        let forms = finished.iter().cloned().chain([Form::Clause(Node::new(sub))]).collect();
        let checked = self.checked(&Node::new(Program { forms }), &form);
        Some(checked.map(|program| {
            let relation = derived_at(&program, &form);
            let scope = scope_of(&program, &relation);
            SubBody { program, form, kept: (0..count).collect(), scope }
        }))
    }

    /// `program`, checked, or a fault at `form` where a check refuses it.
    fn checked(&self, program: &Node<Program>, form: &NodePath) -> Outcome<CheckedProgram> {
        let registry = self.context.registry;
        let resolved = self.context.resolved(program);
        let clauses = SolverClauses::of_program((*resolved).clone());
        check_shared_program(resolved, &clauses, registry, &mut CheckCache::default()).map_err(|refusals| {
            let messages: Vec<&str> = refusals.iter().map(|refusal| &*refusal.message).collect();
            RunFault { message: format!("a check refuses the program: {}", messages.join("; ")).into(), form: form.clone() }
        })
    }

    /// The consistency of the relation of the `RULE` clause that ends
    /// `program`, where `before`, the program before the step, holds fewer
    /// forms and the decode judges the train pairs.
    pub(super) fn consistency(&self, before: &Node<Program>, program: &Node<Program>) -> Option<(Consistency, Option<crate::eval::output::GridColumns>)> {
        let train = self.train.as_ref()?;
        let forms = &program.value().forms;
        if forms.len() == before.value().forms.len() {
            return None;
        }
        let Some(Form::Clause(clause)) = forms.last() else { return None };
        if clause.value().keyword != ClauseKeyword::Rule {
            return None;
        }
        let form = NodePath::top(forms.len() as u32 - 1);
        let checked = match self.checked(program, &form) {
            Ok(checked) => checked,
            Err(fault) => return Some((Consistency::Fault(fault), None)),
        };
        let output = derived_at(&checked, &form);
        Some(self.test(&checked, &output, train))
    }

    /// The consistency test of `output` in `program`, at each joint
    /// assignment of the `DET`s it reads, under the assignment cap of the
    /// decode settings.
    fn test(&self, program: &CheckedProgram, output: &GraphRelation, train: &[PairCandidates<'_>]) -> (Consistency, Option<crate::eval::output::GridColumns>) {
        let dets: Vec<_> = dets_read(program, output.node);
        let limits = self.limits();
        let Walked { kept, end, .. } = walk(self.inputs(program, &limits), &dets, output, train, self.context.settings.caps.assignments);
        match end {
            Err(End::Stop(stop)) => return (Consistency::Stopped(stop), None),
            Err(End::Fault(fault)) => return (Consistency::Fault(fault), None),
            Ok(()) => {}
        }
        if kept.is_empty() {
            return (Consistency::NotConsistent, None);
        }
        for det in dets.iter().filter(|det| !det.open) {
            let values = distinct_values(&kept, &det.relation);
            if values.len() > 1 {
                return (Consistency::SeveralValues { relation: det.relation.clone(), values }, None);
            }
        }
        let parameters: Vec<_> = kept.iter().map(|assignment| ParameterValues::determined(assignment.values.clone())).collect();
        let inputs = self.inputs(program, &limits);
        let evaluations: Vec<_> = parameters.iter().map(|values| inputs.at(values)).collect();
        match crate::judge::run::grid_columns_observed(&evaluations, &mut kept.iter().map(|assignment| assignment.observed.clone()).collect::<Vec<_>>(), output, train) {
            Ok(crate::judge::run::Found::Columns(columns)) => (Consistency::Consistent { assignments: kept.into_iter().map(|assignment| assignment.values).collect() }, Some(columns)),
            Ok(crate::judge::run::Found::None) => (Consistency::NotConsistent, None),
            Ok(crate::judge::run::Found::Stopped(stop)) => (Consistency::Stopped(stop), None),
            Err(fault) => (Consistency::Fault(fault), None),
        }
    }
}

/// Whether the conjunct at `index` of the body of a clause whose innermost
/// open node is at `open` is complete or is a positive atom.
fn complete_or_atom(open: &NodePath, index: usize, conjunct: &Conjunct) -> bool {
    let open_at = match &*open.0 {
        [PathStep(0), PathStep(at), ..] => Some(*at as usize),
        _ => None,
    };
    open_at != Some(index) || matches!(conjunct, Conjunct::Atom(_))
}

/// The relation that the clause at `form` derives in `program`: a clause
/// relation, or a chosen relation where the clause has `ONE` marks.
fn derived_at(program: &CheckedProgram, form: &NodePath) -> GraphRelation {
    let resolved = &program.program;
    let node = (0..resolved.graph.nodes.len())
        .map(|index| GraphNodeIndex(u32::try_from(index).expect("fewer than 2^32 nodes")))
        .find(|&node| {
            matches!(resolved.graph.nodes[node.0 as usize].kind, DependencyKind::Clause(_) | DependencyKind::Chosen(_)) && resolved.forms_of(node).contains(form)
        })
        .expect("a checked clause derives its relation");
    GraphRelation { node, output: None }
}
