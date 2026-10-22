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
use crate::judge::determination::{dets_read, descend_assignments, distinct_values, walk, Assignment, End, EvaluationInputs, Walked};
use crate::program::path::{NodePath, PathStep};
use crate::program::{Body, Choose, ChoosePart, Clause, ClauseKeyword, Conjunct, Form, Node, Program, ProgramRelation};
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

/// What a prefix gives at each joint assignment of the `DET`s it reads, in
/// the order of the walk, as `docs/engine/synthesis.md#decode-interface`
/// gives it: a prefix that reads no `DET` of several values gives one
/// entry, at the empty assignment.
#[derive(Clone, Debug)]
pub struct Assigned<T> {
    pub at: Vec<(Vec<Assignment>, T)>,
    /// The bound that ended the walk before its last assignment: the
    /// assignment cap, a bound of a run, the deadline or a cancellation.
    pub stop: Option<Stop>,
}

impl<T> Assigned<T> {
    fn map<U>(self, mut f: impl FnMut(T) -> U) -> Assigned<U> {
        Assigned { at: self.at.into_iter().map(|(assigned, value)| (assigned, f(value))).collect(), stop: self.stop }
    }
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
        Some(self.sub_body()?.and_then(|sub| self.assigned_rows(&sub, example)))
    }

    /// The count of the rows of the sub-body that [`Decoder::rows`] gives on
    /// each example of the task, or once for a task-wide clause, at each
    /// assignment, `None` in a count where the body is undefined or
    /// stopped. `None` where no clause is in progress.
    pub fn counts(&self) -> Option<Box<[Outcome<Assigned<Option<u64>>>]>> {
        let sub = match self.sub_body()? {
            Ok(sub) => sub,
            Err(fault) => return Some(Box::new([Err(fault)])),
        };
        let examples: Vec<Option<Example>> = match sub.scope {
            ExampleScope::PerExample => self.task.examples().map(Some).collect(),
            ExampleScope::TaskWide => vec![None],
        };
        Some(examples.into_iter().map(|example| self.assigned_rows(&sub, example).map(|rows| rows.map(|value| value.count()))).collect())
    }

    fn assigned_rows(&self, sub: &SubBody, example: Option<Example>) -> Outcome<Assigned<BodyValue>> {
        let limits = self.limits();
        let inputs = self.inputs(&sub.program, &limits);
        let root = derived_at(&sub.program, &sub.form).node;
        let dets: Vec<_> = dets_read(&sub.program, root).into_iter().filter(|det| !det.pick).collect();
        let mut at = Vec::new();
        let mut leaf = |evaluation: &crate::eval::Evaluation<'_>, assigned: &[Assignment]| {
            at.push((assigned.to_vec(), evaluation.body(&sub.form, &sub.kept, example).map_err(End::Fault)?));
            Ok(())
        };
        match descend_assignments(inputs, &dets, root, self.context.settings.caps.assignments, &mut leaf).1 {
            Ok(()) => Ok(Assigned { at, stop: None }),
            Err(End::Stop(stop)) => Ok(Assigned { at, stop: Some(stop) }),
            Err(End::Fault(fault)) => Err(fault),
        }
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
        let form = NodePath::top(finished.len() as u32);
        let (clause, kept) = open_clause(last, &open)?;
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
        let sub = Clause { body: Node::new(Body { conjuncts: kept.into() }), columns, ..clause };
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

/// The clause in progress of `form`, whose innermost open node is at
/// `open`, as a clause to build the sub-body on, and the conjuncts of the
/// sub-body: a clause's own body, or the open clause of a `CHOOSE` form,
/// which a `from` clause inside a `for` clause follows with the conjuncts
/// of that `for` clause. `None` where `form` is neither or holds no open
/// clause.
fn open_clause(form: &Form, open: &NodePath) -> Option<(Clause, Vec<Conjunct>)> {
    match form {
        Form::Clause(clause) => {
            let clause = clause.value();
            let open_at = match &*open.0 {
                [PathStep(0), PathStep(at), ..] => Some(*at as usize),
                _ => None,
            };
            Some((clause.clone(), complete_or_atoms(&clause.body, open_at)))
        }
        Form::Choose(choose) => {
            let choose = choose.value();
            let [PathStep(at), within @ ..] = &*open.0 else { return None };
            let open_at = within.first().map(|step| step.0 as usize);
            let (body, before) = open_part(choose, choose.parts().nth(*at as usize)?)?;
            let conjuncts = before.iter().flat_map(|body| body.conjuncts.iter().cloned()).chain(complete_or_atoms(body, open_at)).collect();
            let clause = Clause {
                keyword: ClauseKeyword::Rule,
                derives: ProgramRelation::Declared(choose.name.clone()),
                gloss: None,
                proposers: Arc::from([]),
                body: body.clone(),
                ones: Arc::from([]),
                columns: Arc::from([]),
            };
            Some((clause, conjuncts))
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

/// The conjuncts of `body` that are complete or are positive atoms, where
/// the conjunct at `open_at` is the one in progress.
fn complete_or_atoms(body: &Node<Body>, open_at: Option<usize>) -> Vec<Conjunct> {
    let kept = |(index, conjunct): &(usize, &Conjunct)| open_at != Some(*index) || matches!(conjunct, Conjunct::Atom(_));
    body.value().conjuncts.iter().enumerate().filter(kept).map(|(_, conjunct)| conjunct.clone()).collect()
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
        open_clause(&form, &open).map_or(0, |(_, conjuncts)| conjuncts.len())
    }

    #[test]
    fn a_choose_gives_the_conjuncts_of_its_open_clause() {
        let (for_clause, from_inside_for, never) = (conjuncts_open_at(&[0, 0]), conjuncts_open_at(&[1, 1]), conjuncts_open_at(&[2, 2]));
        assert_eq!(for_clause, 1, "the `for` clause");
        assert_eq!(from_inside_for, 2, "the `for` conjunct, then the `from` atom, and not the open comparison");
        assert_eq!(never, 2, "the `never` clause");
    }
}
