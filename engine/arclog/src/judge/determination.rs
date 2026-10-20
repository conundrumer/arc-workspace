//! The determination of a solver's `DET`s from the evidence, as
//! `docs/engine/determination.md#det` gives it: per base case, the joint
//! assignments of the `DET`s it reads at which it solves every train pair,
//! restricted across cases to the values they agree on, and the value, the
//! open values or the error of each parameter. The walk of a relation's
//! joint assignments, with the search for its grid columns at each, is
//! `walk`, which the consistency test of [`crate::decode`] runs too.

use std::sync::Arc;

use crate::check::CheckedProgram;
use crate::eval::determinations::{det_relation, determinations};
use crate::eval::instance::Constructions;
use crate::eval::join::{each_row, one_part, union};
use crate::eval::{output_relation, Domain, Evaluation, Limits, ParameterValues, ReachedBound, RunFault, Stop};
use crate::hash::StableHashSet;
use crate::program::path::{node_at, NodeRef};
use crate::program::{ClauseKeyword, ProgramRelation};
use crate::registry::Registry;
use crate::relations::{Relation, Row, RowSet};
use crate::resolver::{DependencyKind, GraphNodeIndex};
use crate::session::{same_rows, TaskSession};
use crate::solver::CaseName;
use crate::task::{JudgedTask, Task};
use crate::types::GraphRelation;

use super::candidates::{PairCandidates, Section, World};
use super::run::{grid_columns, Found};

/// A case that the determination runs: its name, its checked program, the
/// checked concept program, in which the `DET` forms the case takes from
/// it are evaluated, and the parts of an [`Evaluation`] other than its
/// parameter values. The cases of one determination share one task
/// session, so equal rows hold equal term ids across them.
#[derive(Clone, Copy, Debug)]
pub struct DeterminedCase<'a> {
    pub name: &'a CaseName,
    pub program: &'a CheckedProgram,
    pub concept: &'a CheckedProgram,
    pub task: &'a Task,
    pub session: &'a TaskSession,
    pub registry: &'a Registry,
    pub constructions: &'a Constructions,
    pub limits: &'a Limits,
}

impl<'a> DeterminedCase<'a> {
    /// The evaluation of the case at `parameters`, with the concept program
    /// where the case program takes forms from it.
    pub fn evaluation<'p>(&'p self, parameters: &'p ParameterValues) -> Evaluation<'p> {
        self.inputs().at(parameters)
    }

    fn inputs(&self) -> EvaluationInputs<'a> {
        EvaluationInputs {
            program: self.program,
            concept: self.program.program.concept().is_some().then_some(self.concept),
            task: self.task,
            session: self.session,
            registry: self.registry,
            constructions: self.constructions,
            limits: self.limits,
        }
    }
}

/// The fields of an [`Evaluation`] other than its parameter values, which
/// the walk of the joint assignments sets at each assignment.
#[derive(Clone, Copy, Debug)]
pub(crate) struct EvaluationInputs<'a> {
    pub(crate) program: &'a CheckedProgram,
    pub(crate) concept: Option<&'a CheckedProgram>,
    pub(crate) task: &'a Task,
    pub(crate) session: &'a TaskSession,
    pub(crate) registry: &'a Registry,
    pub(crate) constructions: &'a Constructions,
    pub(crate) limits: &'a Limits,
}

impl<'a> EvaluationInputs<'a> {
    /// The evaluation at `parameters`.
    pub(crate) fn at<'p>(&self, parameters: &'p ParameterValues) -> Evaluation<'p>
    where
        'a: 'p,
    {
        Evaluation {
            program: self.program,
            concept: self.concept,
            task: self.task,
            parameters,
            session: self.session,
            registry: self.registry,
            constructions: self.constructions,
            limits: self.limits,
        }
    }
}

/// What the determination gives a parameter.
#[derive(Clone, Debug)]
pub enum Parameter {
    /// The one value of a `DET` without `(ONE)`.
    Determined(Arc<Relation>),
    /// The values of a `DET` with `(ONE)` that names a proposer, one row
    /// each, in the order of the assignments.
    Open(Vec<Arc<Relation>>),
    /// The values of a `DET` without `(ONE)` that differ across the
    /// assignments left, an error.
    Underdetermined(Vec<Arc<Relation>>),
    /// A parameter that a case with a `DEMONSTRATED` form reads, left to
    /// Every case.
    Demonstrated,
    /// A `DET` whose body ends in `ONE` marks and names no proposer, which
    /// the models of the constraint module solve, left to Every case.
    Pick,
}

/// What the determination gives a case.
#[derive(Clone, Debug)]
pub enum CaseOutcome {
    /// The case keeps at least one assignment after the restriction across
    /// cases.
    Solved,
    /// The case holds a `DEMONSTRATED` form, and is not run.
    Demonstrated,
    /// The case stopped at a bound, the assignment cap or a bound of a run,
    /// with the parameters of several values in a domain it read.
    Stopped { stop: Stop, parameters: Vec<ProgramRelation> },
    /// A fault of a run, or underdetermined grid columns at an assignment
    /// the case keeps.
    Fault(RunFault),
    /// The case solves no train pair at any assignment, or keeps none after
    /// the restriction across cases.
    Unsolved,
}

/// The determination of a solver's `DET`s on one task.
#[derive(Clone, Debug)]
pub struct Determination {
    /// Each parameter that a case reads, in the order the cases first read
    /// them, each case's in dependency order.
    pub parameters: Vec<(ProgramRelation, Parameter)>,
    /// Each case, in the order of the cases given, with the parameters it
    /// reads.
    pub cases: Vec<(CaseName, CaseOutcome, Vec<ProgramRelation>)>,
}

impl Determination {
    /// What the determination gives `relation`, or `None` where no case
    /// reads it, or no case that reads it keeps an assignment.
    pub fn parameter(&self, relation: &ProgramRelation) -> Option<&Parameter> {
        self.parameters.iter().find(|(name, _)| name == relation).map(|(_, parameter)| parameter)
    }

    /// The values that the case `case` runs at: each `DET` with `(ONE)` its
    /// open values, and each other its determined value.
    pub fn values(&self, case: &CaseName) -> ParameterValues {
        let (_, _, reads) = self.cases.iter().find(|(name, ..)| name == case).expect("a case of the determination");
        let values = reads.iter().filter_map(|relation| match self.parameter(relation)? {
            Parameter::Determined(rows) => Some((relation.clone(), rows.clone())),
            Parameter::Open(values) => Some((relation.clone(), union(values.clone()))),
            Parameter::Underdetermined(_) | Parameter::Demonstrated | Parameter::Pick => None,
        });
        ParameterValues::determined(values)
    }
}

/// A `DET` that a relation reads, at any depth.
#[derive(Clone, Debug)]
pub(crate) struct Det {
    pub(crate) node: GraphNodeIndex,
    pub(crate) relation: ProgramRelation,
    /// Whether it ends in `(ONE)`.
    pub(crate) open: bool,
    /// Whether it ends in `(ONE)` and names no proposer, so that the models
    /// of the constraint module give its values, and the walk of the
    /// assignments assigns it nothing.
    pub(crate) pick: bool,
}

/// Each `DET` that the relation at `root` reads in `program`, at any depth,
/// in dependency order.
pub(crate) fn dets_read(program: &CheckedProgram, root: GraphNodeIndex) -> Vec<Det> {
    let resolved = &program.program;
    let read = reached(resolved, root);
    let nodes = determinations(program).into_iter().filter(|node| read[node.0 as usize]);
    nodes
        .map(|node| {
            let (relation, open) = det_relation(&resolved.graph.nodes[node.0 as usize].kind).expect("a `DET` node");
            Det { node, relation, open, pick: open && !names_proposer(resolved, node) }
        })
        .collect()
}

/// An assignment the walk keeps: a value for each `DET` it assigns, and the
/// fault of underdetermined grid columns or of the run at it, which is the
/// case's error where the assignment is left after the restriction.
#[derive(Clone, Debug)]
pub(crate) struct Kept {
    pub(crate) values: Vec<(ProgramRelation, Arc<Relation>)>,
    pub(crate) fault: Option<RunFault>,
}

/// What ends the walk of the assignments before its last assignment.
#[derive(Clone, Debug)]
pub(crate) enum End {
    Stop(Stop),
    Fault(RunFault),
}

/// The walk of the joint assignments of a relation's `DET`s.
pub(crate) struct Walked {
    /// The assignments at which the relation, read as `&output`, solves
    /// every train pair, in the order of the walk.
    pub(crate) kept: Vec<Kept>,
    /// The `DET`s met with several values in the domain, in the order met.
    pub(crate) branching: Vec<ProgramRelation>,
    pub(crate) end: Result<(), End>,
}

/// The walk of the joint assignments of `dets`, the `DET`s that `output`
/// reads less the picks, depth-first in their dependency order, under the
/// assignment cap `cap`: at each assignment, the search for the grid
/// columns of `output` over the train pairs whose candidates are `train`.
pub(crate) fn walk(inputs: EvaluationInputs<'_>, dets: &[Det], output: &GraphRelation, train: &[PairCandidates<'_>], cap: u64) -> Walked {
    let mut walk = Walk { inputs, dets, output, train, cap, count: 0, kept: Vec::new(), branching: Vec::new() };
    let end = walk.descend(0, &mut Vec::new());
    Walked { kept: walk.kept, branching: walk.branching, end }
}

/// The determination of the `DET`s of `cases` on the train pairs of
/// `judged`, under `world`.
pub fn determine(cases: &[DeterminedCase<'_>], judged: &JudgedTask, world: World) -> Determination {
    let train: Vec<PairCandidates<'_>> = judged.train.iter().map(|pair| PairCandidates::of(pair, Section::Train, world)).collect();
    let mut order: Vec<ProgramRelation> = Vec::new();
    let mut demonstrated: StableHashSet<ProgramRelation> = StableHashSet::default();
    let mut picks: StableHashSet<ProgramRelation> = StableHashSet::default();
    let mut opens: StableHashSet<ProgramRelation> = StableHashSet::default();
    let mut walked: Vec<(CaseOutcome, Vec<ProgramRelation>, Vec<Kept>)> = Vec::new();
    for case in cases {
        let program = &case.program.program;
        let output = output_relation(case.program).expect("a checked case program derives `&output`");
        let mut dets = Vec::new();
        let mut reads = Vec::new();
        for det in dets_read(case.program, output.node) {
            if !order.contains(&det.relation) {
                order.push(det.relation.clone());
            }
            reads.push(det.relation.clone());
            if det.open {
                opens.insert(det.relation.clone());
            }
            if det.pick {
                picks.insert(det.relation);
                continue;
            }
            dets.push(det);
        }
        let holds_demonstrated = program.graph.nodes.iter().any(|node| matches!(node.kind, DependencyKind::Demonstrated(_)));
        if holds_demonstrated {
            demonstrated.extend(reads.iter().cloned());
            walked.push((CaseOutcome::Demonstrated, reads, Vec::new()));
            continue;
        }
        let Walked { kept, branching, end } = walk(case.inputs(), &dets, &output, &train, case.session.caps.assignments);
        let outcome = match end {
            Ok(()) if kept.is_empty() => CaseOutcome::Unsolved,
            Ok(()) => CaseOutcome::Solved,
            Err(End::Stop(stop)) => CaseOutcome::Stopped { stop, parameters: branching },
            Err(End::Fault(fault)) => CaseOutcome::Fault(fault),
        };
        let kept = if matches!(outcome, CaseOutcome::Solved) { kept } else { Vec::new() };
        walked.push((outcome, reads, kept));
    }
    restrict(&mut walked);
    let mut parameters = Vec::new();
    for relation in order {
        let parameter = if demonstrated.contains(&relation) {
            Parameter::Demonstrated
        } else if picks.contains(&relation) {
            Parameter::Pick
        } else {
            let mut values = distinct_values(walked.iter().flat_map(|(_, _, kept)| kept), &relation);
            match (opens.contains(&relation), values.len()) {
                (_, 0) => continue,
                (true, _) => Parameter::Open(values),
                (false, 1) => Parameter::Determined(values.pop().expect("one value")),
                (false, _) => Parameter::Underdetermined(values),
            }
        };
        parameters.push((relation, parameter));
    }
    let cases = cases.iter().zip(walked).map(|(case, (outcome, reads, _))| (case.name.clone(), outcome, reads)).collect();
    Determination { parameters, cases }
}

/// The walk of one case's joint assignments, depth-first in the
/// dependency order of its `DET`s.
struct Walk<'w, 'a> {
    inputs: EvaluationInputs<'a>,
    dets: &'w [Det],
    output: &'w GraphRelation,
    train: &'w [PairCandidates<'w>],
    cap: u64,
    /// The complete assignments reached.
    count: u64,
    kept: Vec<Kept>,
    /// The `DET`s met with several values in the domain, in the order met.
    branching: Vec<ProgramRelation>,
}

impl Walk<'_, '_> {
    /// Each assignment that extends `assigned`, the values of the `DET`s
    /// before `at`, with the domain of each later `DET` at the values
    /// before it.
    fn descend(&mut self, at: usize, assigned: &mut Vec<(ProgramRelation, Arc<Relation>)>) -> Result<(), End> {
        let parameters = ParameterValues::determined(assigned.clone());
        let Some(det) = self.dets.get(at) else {
            let evaluation = self.inputs.at(&parameters);
            self.count += 1;
            let cap = self.cap;
            if self.count > cap {
                let program = &self.inputs.program.program;
                let form = self.dets.last().map_or_else(|| program.form_of(self.output.node), |det| program.form_of(det.node));
                return Err(End::Stop(Stop { bound: ReachedBound::Assignments { cap }, form: form.clone() }));
            }
            let fault = match grid_columns(&evaluation, self.output, self.train) {
                Ok(Found::Columns(_)) => None,
                Ok(Found::None) => return Ok(()),
                Ok(Found::Stopped(stop)) => return Err(End::Stop(stop)),
                Err(fault) => Some(fault),
            };
            self.kept.push(Kept { values: assigned.clone(), fault });
            return Ok(());
        };
        if det.open {
            if let Some(fault) = keyed_one(self.inputs.program, det.node) {
                return Err(End::Fault(fault));
            }
        }
        let domain = match self.inputs.at(&parameters).domain(det.node).map_err(End::Fault)? {
            Domain::Rows(rows) if det.open => one_row_each(&rows),
            Domain::Rows(rows) => rows,
            Domain::Undefined => return self.descend(at + 1, assigned),
            Domain::Stopped(stop) => return Err(End::Stop(stop)),
        };
        if domain.len() > 1 && !self.branching.contains(&det.relation) {
            self.branching.push(det.relation.clone());
        }
        for value in domain {
            assigned.push((det.relation.clone(), value));
            let walked = self.descend(at + 1, assigned);
            assigned.pop();
            walked?;
        }
        Ok(())
    }
}

/// The values that `assignments` give `relation`, each once, in the order
/// of `assignments`.
pub(crate) fn distinct_values<'k>(assignments: impl IntoIterator<Item = &'k Kept>, relation: &ProgramRelation) -> Vec<Arc<Relation>> {
    let mut values: Vec<Arc<Relation>> = Vec::new();
    for (name, value) in assignments.into_iter().flat_map(|assignment| &assignment.values) {
        if name == relation && !values.iter().any(|seen| same_rows(seen, value)) {
            values.push(value.clone());
        }
    }
    values
}

/// Restricts the kept assignments of each case to those that agree, on
/// each parameter they share, with some kept assignment of each other case
/// that keeps one, until no case loses one. A case left with none is
/// unsolved, and a case whose assignments left hold a fault gives it.
fn restrict(walked: &mut [(CaseOutcome, Vec<ProgramRelation>, Vec<Kept>)]) {
    loop {
        let mut changed = false;
        for a in 0..walked.len() {
            for b in 0..walked.len() {
                if a == b || walked[b].2.is_empty() {
                    continue;
                }
                let others = walked[b].2.clone();
                let before = walked[a].2.len();
                walked[a].2.retain(|kept| others.iter().any(|other| agree(kept, other)));
                changed |= walked[a].2.len() != before;
            }
        }
        if !changed {
            break;
        }
    }
    for (outcome, _, kept) in walked.iter_mut() {
        if !matches!(outcome, CaseOutcome::Solved) {
            continue;
        }
        if let Some(fault) = kept.iter().find_map(|assignment| assignment.fault.clone()) {
            *outcome = CaseOutcome::Fault(fault);
            kept.clear();
        } else if kept.is_empty() {
            *outcome = CaseOutcome::Unsolved;
        }
    }
}

/// Whether two assignments give the same rows to each parameter they both
/// assign.
fn agree(a: &Kept, b: &Kept) -> bool {
    a.values.iter().all(|(name, value)| b.values.iter().filter(|(other, _)| other == name).all(|(_, other)| same_rows(value, other)))
}

/// Each row of each of `domain` as a value of its own, the
/// domain of a `DET` with `(ONE)` that names a proposer, in the order
/// of `domain`, each row once.
fn one_row_each(domain: &[Arc<Relation>]) -> Vec<Arc<Relation>> {
    let mut split: Vec<Arc<Relation>> = Vec::new();
    for value in domain {
        let mut rows: Vec<Row> = Vec::new();
        each_row(value, &mut |row| rows.push(row.into()));
        for row in rows {
            let mut set = RowSet::empty(value.arity());
            set.insert(row);
            let one = Arc::new(one_part(set));
            if !split.iter().any(|seen| same_rows(seen, &one)) {
                split.push(one);
            }
        }
    }
    split
}

/// Whether a `DET` form of the chosen relation `node` names a proposer.
fn names_proposer(program: &crate::resolver::ResolvedProgram, node: GraphNodeIndex) -> bool {
    let root = NodeRef::Program(program.program.value());
    program.forms_of(node).iter().any(|at| matches!(node_at(root, at), Some(NodeRef::Clause(clause)) if clause.keyword == ClauseKeyword::Det && !clause.proposers.is_empty()))
}

/// The fault of a `(ONE)` with a key on a `DET` form of `node` that names a
/// proposer, whose domain is one row each of its proposer's rows.
fn keyed_one(program: &CheckedProgram, node: GraphNodeIndex) -> Option<RunFault> {
    let program = &program.program;
    let root = NodeRef::Program(program.program.value());
    program.forms_of(node).iter().find_map(|at| match node_at(root, at) {
        Some(NodeRef::Clause(clause)) if !clause.proposers.is_empty() && clause.ones.iter().any(|mark| !mark.key.is_empty()) => {
            Some(RunFault { message: "a `(ONE)` with a key on a `DET` that names a proposer".into(), form: at.clone() })
        }
        _ => None,
    })
}

/// Whether each node of `program` is read by `root`, at any depth, or is
/// `root`.
fn reached(program: &crate::resolver::ResolvedProgram, root: GraphNodeIndex) -> Vec<bool> {
    let graph = &program.graph;
    let mut seen = vec![false; graph.nodes.len()];
    let mut stack = vec![root];
    while let Some(node) = stack.pop() {
        if std::mem::replace(&mut seen[node.0 as usize], true) {
            continue;
        }
        stack.extend(graph.reads[node.0 as usize].iter().copied());
    }
    seen
}
