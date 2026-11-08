//! The determination of a solver's `DET`s from the evidence, as
//! `docs/engine/determination.md#det` gives it: per base case, the joint
//! assignments of the `DET`s it reads at which it solves every train pair,
//! restricted across cases to the values they agree on, and the value, the
//! open values or the error of each parameter. The walk of a relation's
//! joint assignments is `descend_assignments`, and `walk`, which the
//! consistency test of [`crate::decode`] runs too, tests the relation
//! test at each; the rows of a prefix in [`crate::decode`] are evaluated
//! at each.

use std::sync::Arc;
use std::ops::ControlFlow;

use crate::check::CheckedProgram;
use crate::eval::determinations::{det_node, det_relation, determinations, is_by_clauses, relation_spelled};
use crate::eval::instance::Constructions;
use crate::eval::join::{each_row, one_part, union};
use crate::eval::{output_relation, Domain, DomainSize, Evaluation, ModelsEnd, RelationValue, Limits, ParameterValues, ReachedBound, RunFault, Stop};
use crate::hash::StableHashSet;
use crate::program::path::{node_at, NodeRef};
use crate::program::{ClauseKeyword, ProgramRelation};
use crate::registry::Registry;
use crate::relations::{Relation, Row, RowSet};
use crate::resolver::{DependencyKind, GraphNodeIndex, Side};
use crate::session::{same_rows, TaskSession};
use crate::solver::CaseName;
use crate::stats::{self, Phase};
use crate::task::{JudgedTask, Task};
use crate::types::GraphRelation;

use super::candidates::{PairCandidates, Section, World};
use super::run::{full_output_set, same_set, AtCap, Found, Observed, Tested};
use super::solves::OutputSet;

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
    /// assignments left, where some input of the evidence separates those
    /// assignments, an error.
    Underdetermined(Vec<Arc<Relation>>),
    /// Several values are left, and no input of the evidence, a train input
    /// or a test input, separates the assignments that hold them. `record`
    /// is the value that the solver's `param` record gives, where one of them
    /// is that value and the End check has found it; a run at determined
    /// values takes it.
    Unseparated { values: Vec<Arc<Relation>>, record: Option<Arc<Relation>> },
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
    /// The case stopped at a bound, the assignment cap or a bound of a run,
    /// with the parameters of several values in a domain it read.
    Stopped { stop: Stop, parameters: Vec<ProgramRelation> },
    /// A fault of a run at an assignment the case keeps.
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
    /// Each parameter that a case with a `DEMONSTRATED` form reads, in the
    /// order of `parameters`' first reads. `arclog-cli determine` and
    /// `arclog-cli decode` leave these to `arclog-cli compare`, as
    /// `docs/engine/cases.md#every-case` gives.
    pub demonstrated: Vec<ProgramRelation>,
    /// Each `DET` that the `OUT` form of some case reads, as
    /// [`read_by_output`] gives, less those [`computed_from_dets`] gives.
    /// Such a `DET` is a parameter, which the program reads as stored facts.
    /// Each other `DET` is part of the determination, so its value may differ
    /// across cases.
    pub read_by_program: StableHashSet<ProgramRelation>,
}

impl Determination {
    /// Gives each parameter of `records` that several values are left of
    /// the value its `param` record gives.
    pub fn set_records(&mut self, records: Vec<(ProgramRelation, Arc<Relation>)>) {
        for (relation, value) in records {
            if let Some((_, Parameter::Unseparated { record, .. })) = self.parameters.iter_mut().find(|(name, _)| *name == relation) {
                *record = Some(value);
            }
        }
    }

    /// What the determination gives `relation`, or `None` where no case
    /// reads it, or no case that reads it keeps an assignment.
    pub fn parameter(&self, relation: &ProgramRelation) -> Option<&Parameter> {
        self.parameters.iter().find(|(name, _)| name == relation).map(|(_, parameter)| parameter)
    }

    /// Whether a case with a `DEMONSTRATED` form reads `relation`.
    pub fn reads_demonstrated(&self, relation: &ProgramRelation) -> bool {
        self.demonstrated.contains(relation)
    }

    /// The values that the case `case` runs at: each `DET` with `(ONE)` its
    /// open values, and each other its determined value.
    pub fn values(&self, case: &CaseName) -> ParameterValues {
        let (_, _, reads) = self.cases.iter().find(|(name, ..)| name == case).expect("a case of the determination");
        let values = reads.iter().filter_map(|relation| match self.parameter(relation)? {
            Parameter::Determined(rows) => Some((relation.clone(), rows.clone())),
            Parameter::Open(values) => Some((relation.clone(), union(values.clone()))),
            Parameter::Unseparated { record: Some(rows), .. } => Some((relation.clone(), rows.clone())),
            Parameter::Underdetermined(_) | Parameter::Unseparated { record: None, .. } | Parameter::Pick => None,
        });
        ParameterValues::determined(values)
    }

    /// The values that the case `case` runs at, or why none stand. A case
    /// of the determination takes its own values, as [`Self::values`]
    /// gives them, and is refused where it is not solved. Another case
    /// takes the values of the parameters it runs, and is refused where one
    /// of them is underdetermined.
    pub fn case_values(&self, case: &DeterminedCase<'_>) -> Result<ParameterValues, String> {
        if let Some((_, outcome, _)) = self.cases.iter().find(|(name, ..)| name == case.name) {
            return match outcome {
                CaseOutcome::Solved => Ok(self.values(case.name)),
                CaseOutcome::Stopped { stop, .. } => Err(format!("the determination stops at {:?} at the form {:?}", stop.bound, stop.form)),
                CaseOutcome::Fault(fault) => Err(format!("the determination faults at {:?}: {}", fault.form, fault.message)),
                CaseOutcome::Unsolved => Err("no assignment solves every train pair".to_owned()),
            };
        }
        let mut values = Vec::new();
        for (relation, parameter) in &self.parameters {
            if det_node(case.program, relation).is_none() {
                continue;
            }
            match parameter {
                Parameter::Determined(rows) => values.push((relation.clone(), rows.clone())),
                Parameter::Open(rows) => values.push((relation.clone(), union(rows.clone()))),
                Parameter::Underdetermined(_) => return Err(format!("the parameter {} is underdetermined", relation_spelled(relation))),
                Parameter::Unseparated { record: Some(rows), .. } => values.push((relation.clone(), rows.clone())),
                Parameter::Unseparated { record: None, .. } => return Err(format!("the parameter {} has several values left, and none is its record", relation_spelled(relation))),
                Parameter::Pick => {}
            }
        }
        Ok(ParameterValues::determined(values))
    }
}

/// A `DET` that a relation reads, at any depth.
#[derive(Clone, Debug)]
pub struct Det {
    pub node: GraphNodeIndex,
    pub relation: ProgramRelation,
    /// Whether it ends in `(ONE)`.
    pub open: bool,
    /// Whether it ends in `(ONE)` and names no proposer, so that the models
    /// of the constraint module give its values. A solver determination and
    /// a decode's consistency test leave it unassigned.
    pub pick: bool,
}

/// Each `DET` that the relation at `root` reads in `program`, at any depth,
/// in dependency order.
pub(crate) fn dets_read(program: &CheckedProgram, root: GraphNodeIndex) -> Vec<Det> {
    let read = program.program.graph.reached(root);
    let all = determinations(program);
    if program.program.concept().is_none() {
        return all.into_iter().filter(|node| read[node.0 as usize]).map(|node| det(program, node)).collect();
    }
    let mut placed = vec![false; read.len()];
    let mut order = Vec::new();
    for node in all.iter().copied().filter(|node| read[node.0 as usize]) {
        place(program, &all, node, &mut placed, &mut order);
    }
    order.into_iter().map(|node| det(program, node)).collect()
}

/// Adds to `order` the `DET` node `node`, after each `DET` of `all` that it
/// reads: at any depth in the case's graph, and, where the case takes it from
/// the concept program, there too. Such a `DET` resolves its reads in the
/// concept program, so the case's graph holds none of them, and the
/// evaluation there takes their values from the assignment.
fn place(program: &CheckedProgram, all: &[GraphNodeIndex], node: GraphNodeIndex, placed: &mut [bool], order: &mut Vec<GraphNodeIndex>) {
    if std::mem::replace(&mut placed[node.0 as usize], true) {
        return;
    }
    let resolved = &program.program;
    let read = resolved.graph.reached(node);
    let through_concept = read_in_concept(program, node);
    for &other in all {
        let in_case = read[other.0 as usize];
        let in_concept = det_relation(&resolved.graph.nodes[other.0 as usize].kind).is_some_and(|(found, _)| through_concept.contains(&found));
        if other != node && (in_case || in_concept) {
            place(program, all, other, placed, order);
        }
    }
    order.push(node);
}

/// The relation of each `DET` that the `DET` at `node` reads in the concept
/// program, at any depth, where the case takes it from there.
fn read_in_concept(program: &CheckedProgram, node: GraphNodeIndex) -> Vec<ProgramRelation> {
    let resolved = &program.program;
    let (Some(concept), Some(_), Some((relation, _))) = (resolved.concept(), resolved.concept_path(resolved.form_of(node)), det_relation(&resolved.graph.nodes[node.0 as usize].kind)) else {
        return Vec::new();
    };
    let nodes = &concept.graph.nodes;
    let Some(at) = nodes.iter().position(|other| det_relation(&other.kind).is_some_and(|(found, _)| found == relation)) else {
        return Vec::new();
    };
    let reached = concept.graph.reached(GraphNodeIndex(at as u32));
    nodes.iter().zip(reached).filter(|(_, reached)| *reached).filter_map(|(other, _)| det_relation(&other.kind).map(|(found, _)| found)).collect()
}

/// All assignable DETs, without a relation-specific dependency traversal.
pub(crate) fn held_dets(program: &CheckedProgram) -> Vec<Det> {
    written_dets(program).into_iter().filter(|det| !det.pick).collect()
}

/// Every written DET, including model picks that the held-parameter walk leaves unassigned.
pub(crate) fn written_dets(program: &CheckedProgram) -> Vec<Det> {
    determinations(program).into_iter().map(|node| det(program, node)).collect()
}

fn det(program: &CheckedProgram, node: GraphNodeIndex) -> Det {
    let resolved = &program.program;
    let (relation, open) = det_relation(&resolved.graph.nodes[node.0 as usize].kind).expect("a `DET` node");
    Det { node, relation, open, pick: open && !names_proposer(resolved, node) }
}

/// An assignment the walk keeps: a value for each `DET` it assigns, and the
/// fault of the run at it, which is the case's error where the assignment is
/// left after the restriction.
#[derive(Clone, Debug)]
pub(crate) struct Kept {
    pub(crate) values: Vec<Assignment>,
    pub(crate) fault: Option<RunFault>,
    pub(crate) observed: Observed,
}

/// What ends the walk of the assignments before its last assignment.
#[derive(Clone, Debug)]
pub enum End {
    Stop(Stop),
    Fault(RunFault),
}

/// The walk of the joint assignments of a relation's `DET`s.
pub(crate) struct Walked {
    /// The assignments at which the relation solves every train pair, in
    /// the order of the walk.
    pub(crate) kept: Vec<Kept>,
    /// The `DET`s met with several values in the domain, in the order met.
    pub(crate) branching: Vec<ProgramRelation>,
    pub(crate) end: Result<(), End>,
    pub(crate) stop: Option<Stop>,
}

/// The walk of the joint assignments of `dets`, the `DET`s that `output`
/// reads, depth-first in their dependency order, under the
/// assignment cap `cap`: at each assignment, the test of `output`, as
/// `tested` gives it, over the train pairs whose candidates are `train`,
/// with the output sets of a case that reaches the model cap as `at_cap`
/// gives.
pub(crate) fn walk(inputs: EvaluationInputs<'_>, dets: &[Det], output: &GraphRelation, train: &[PairCandidates<'_>], cap: u64, tested: Tested, at_cap: AtCap<'_>) -> Walked {
    let mut kept = Vec::new();
    let mut leaf = |evaluation: &Evaluation<'_>, assigned: &[Assignment]| {
        let (found, observed) = tested.recorded(evaluation, output, train, at_cap);
        let fault = match found {
            Ok(Found::Columns(_)) => None,
            Ok(Found::None) => return Ok(()),
            Ok(Found::Stopped(stop)) => return Err(End::Stop(stop)),
            Err(fault) => Some(fault),
        };
        kept.push(Kept { values: assigned.to_vec(), fault, observed });
        Ok(())
    };
    let (branching, end, stop) = descend_assignments(inputs, dets, output.node, cap, &mut leaf);
    Walked { kept, branching, end, stop }
}

/// The determination of the `DET`s of `cases` on the train pairs of
/// `judged`, under `world`.
pub fn determine(cases: &[DeterminedCase<'_>], judged: &JudgedTask, world: World) -> Determination {
    let train: Vec<PairCandidates<'_>> = judged.train.iter().map(|pair| PairCandidates::of(pair, Section::Train, world)).collect();
    let mut order: Vec<ProgramRelation> = Vec::new();
    let mut demonstrated: StableHashSet<ProgramRelation> = StableHashSet::default();
    let mut picks: StableHashSet<ProgramRelation> = StableHashSet::default();
    let mut opens: StableHashSet<ProgramRelation> = StableHashSet::default();
    let mut read_by_program: StableHashSet<ProgramRelation> = StableHashSet::default();
    let mut walked: Vec<(CaseOutcome, Vec<ProgramRelation>, Vec<Kept>)> = Vec::new();
    let mut walk_stops = Vec::new();
    for case in cases {
        let program = &case.program.program;
        let output = output_relation(case.program).expect("a checked case program holds an `OUT` form");
        let mut dets = Vec::new();
        let mut reads = Vec::new();
        let read = read_by_output(case.program, output.node, false);
        let read_to_compute = read_by_output(case.program, output.node, true);
        for det in dets_read(case.program, output.node) {
            if !order.contains(&det.relation) {
                order.push(det.relation.clone());
            }
            reads.push(det.relation.clone());
            let stored = read_to_compute[det.node.0 as usize] && !is_by_clauses(program, det.node);
            if stored || (read[det.node.0 as usize] && !computed_from_dets(case.program, det.node)) {
                read_by_program.insert(det.relation.clone());
            }
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
        }
        let Walked { kept, branching, end, stop } = walk(case.inputs(), &dets, &output, &train, case.session.caps.assignments, Tested::Out, AtCap::Stop);
        walk_stops.push(stop.clone().or_else(|| match &end {Err(End::Stop(stop)) => Some(stop.clone()), _ => None}).map(|stop|(stop,branching.clone())));
        let outcome = match end {
            Ok(()) if !kept.is_empty() => CaseOutcome::Solved,
            Ok(()) => match stop {
                Some(stop) => CaseOutcome::Stopped { stop, parameters: branching },
                None => CaseOutcome::Unsolved,
            },
            // The walk ended before its last assignment, so what it kept is not the determination.
            Err(End::Stop(found)) => CaseOutcome::Stopped { stop: found, parameters: branching },
            Err(End::Fault(fault)) => CaseOutcome::Fault(fault),
        };
        let kept = if matches!(outcome, CaseOutcome::Solved) { kept } else { Vec::new() };
        walked.push((outcome, reads, kept));
    }
    restrict(&mut walked, &read_by_program);
    for ((outcome, _, _), stop) in walked.iter_mut().zip(walk_stops) {
        if matches!(outcome, CaseOutcome::Unsolved) {
            if let Some((stop, parameters)) = stop { *outcome = CaseOutcome::Stopped {stop, parameters}; }
        }
    }
    let demonstrated: Vec<ProgramRelation> = order.iter().filter(|relation| demonstrated.contains(*relation)).cloned().collect();
    let separating: std::cell::OnceCell<Vec<bool>> = std::cell::OnceCell::new();
    let separated = |relation: &ProgramRelation| {
        let separating = separating.get_or_init(|| cases.iter().zip(&walked).map(|(case, (_, _, kept))| kept.len() > 1 && separates(case, kept)).collect());
        walked.iter().zip(separating).any(|((_, reads, _), separates)| *separates && reads.contains(relation))
    };
    let mut parameters = Vec::new();
    for relation in order {
        let parameter = if picks.contains(&relation) {
            Parameter::Pick
        } else {
            let mut values = distinct_values(walked.iter().flat_map(|(_, _, kept)| kept), &relation);
            match (opens.contains(&relation), values.len()) {
                (_, 0) => continue,
                (true, _) => Parameter::Open(values),
                (false, 1) => Parameter::Determined(values.pop().expect("one value")),
                (false, _) if !read_by_program.contains(&relation) => continue,
                (false, _) if separated(&relation) => Parameter::Underdetermined(values),
                (false, _) => Parameter::Unseparated { values, record: None },
            }
        };
        parameters.push((relation, parameter));
    }
    let cases = cases.iter().zip(walked).map(|(case, (outcome, reads, _))| (case.name.clone(), outcome, reads)).collect();
    Determination { parameters, cases, demonstrated, read_by_program }
}

/// Each node that the `OUT` form at `output` of `program` reads, through
/// clauses, instances and `RIGID_DET` assemblies, and through no `DET`'s
/// body. With `to_compute`, it also goes through the body of a `DET` whose
/// value is computed from other `DET`s (`computed_from_dets`), since a run
/// reads those `DET`s to compute it.
fn read_by_output(program: &CheckedProgram, output: GraphNodeIndex, to_compute: bool) -> Vec<bool> {
    let resolved = &program.program;
    let graph = &resolved.graph;
    let mut seen = vec![false; graph.nodes.len()];
    let mut stack = vec![output];
    while let Some(at) = stack.pop() {
        if std::mem::replace(&mut seen[at.0 as usize], true) {
            continue;
        }
        let kind = &graph.nodes[at.0 as usize].kind;
        if !is_det_kind(resolved, at, kind) || (to_compute && computed_from_dets(program, at)) {
            stack.extend(graph.reads[at.0 as usize].iter().copied());
        }
    }
    seen
}

/// Whether some input of the evidence, a train input or a test input,
/// separates `kept`, the assignments left of `case`: the case's output on it
/// differs at two of them, or a stop or a fault gives one of them no output.
/// No pair's output is read.
fn separates(case: &DeterminedCase<'_>, kept: &[Kept]) -> bool {
    let output = output_relation(case.program).expect("a checked case program holds an `OUT` form");
    let inputs = case.inputs();
    case.task.examples().any(|example| {
        let mut first: Option<OutputSet> = None;
        kept.iter().any(|assignment| {
            let parameters = ParameterValues::determined(assignment.values.clone());
            match full_output_set(&inputs.at(&parameters), &output, example) {
                Ok(OutputSet::Stopped(_)) | Err(_) => true,
                Ok(set) => match &first {
                    Some(first) => !same_set(first, &set),
                    None => {
                        first = Some(set);
                        false
                    }
                },
            }
        })
    })
}

/// Whether the `DET` at `node` of `program` is one by its clauses that reads
/// no fact of the task, other than through a `DET` it reads, so that its
/// value is computed from those `DET`s.
pub fn computed_from_dets(program: &CheckedProgram, node: GraphNodeIndex) -> bool {
    let resolved = &program.program;
    if !is_by_clauses(resolved, node) {
        return false;
    }
    let graph = &resolved.graph;
    let mut seen = vec![false; graph.nodes.len()];
    let mut stack: Vec<GraphNodeIndex> = graph.reads[node.0 as usize].to_vec();
    while let Some(at) = stack.pop() {
        if std::mem::replace(&mut seen[at.0 as usize], true) {
            continue;
        }
        let kind = &graph.nodes[at.0 as usize].kind;
        if matches!(kind, DependencyKind::Fact(_)) {
            return false;
        }
        if !is_det_kind(resolved, at, kind) {
            stack.extend(graph.reads[at.0 as usize].iter().copied());
        }
    }
    true
}

/// Whether the node `at`, of kind `kind`, is a `DET`'s.
fn is_det_kind(resolved: &crate::resolver::ResolvedProgram, at: GraphNodeIndex, kind: &DependencyKind) -> bool {
    matches!(kind, DependencyKind::Parameter(_)) || (matches!(kind, DependencyKind::Chosen(_)) && resolved.side(at) == Side::TaskWide)
}

/// A value for a `DET`.
pub type Assignment = (ProgramRelation, Arc<Relation>);

/// The joint assignments of `dets`, depth-first in their dependency order,
/// under the assignment cap `cap`: `leaf` runs at each, with the
/// evaluation at it and the values. An evaluation stop rejects only its
/// path; other stops and faults end the walk. Also gives the first path stop
/// and the `DET`s met with several values in the domain,
/// in the order met. `root` is the node of the relation evaluated, whose
/// form a stop at the cap names where `dets` is empty.
pub(crate) fn descend_assignments(
    inputs: EvaluationInputs<'_>,
    dets: &[Det],
    root: GraphNodeIndex,
    cap: u64,
    leaf: &mut dyn FnMut(&Evaluation<'_>, &[Assignment]) -> Result<(), End>,
) -> (Vec<ProgramRelation>, Result<(), End>, Option<Stop>) {
    descend_with(inputs, dets, root, cap, leaf, None)
}

/// The domain of the `DET` `dets[at]` at an evaluation whose parameter
/// values are `assigned`, the values of the `DET`s before it, as
/// [`Evaluation::domain`] gives it, with what that computation does to the
/// evaluation's session and table work count.
pub(crate) trait Domains {
    fn domain(&self, evaluation: &Evaluation<'_>, at: usize, assigned: &[Assignment]) -> crate::eval::Outcome<Domain>;

    /// The count of values in that domain, as [`Evaluation::domain_size`]
    /// gives it, with the same effect on the session and the count as
    /// [`Domains::domain`] has. The count is the length of the `Rows` that
    /// `domain` gives, so this method has that for its default.
    fn size(&self, evaluation: &Evaluation<'_>, at: usize, assigned: &[Assignment]) -> crate::eval::Outcome<DomainSize> {
        Ok(match self.domain(evaluation, at, assigned)? {
            Domain::Rows(values) => DomainSize::Count(values.len()),
            Domain::Undefined => DomainSize::Undefined,
            Domain::Stopped(stop) => DomainSize::Stopped(stop),
        })
    }
}

/// [`descend_assignments`], with each domain of a `DET` that is no pick
/// from `domains` where it is given.
pub(crate) fn descend_with(
    inputs: EvaluationInputs<'_>,
    dets: &[Det],
    root: GraphNodeIndex,
    cap: u64,
    leaf: &mut dyn FnMut(&Evaluation<'_>, &[Assignment]) -> Result<(), End>,
    domains: Option<&dyn Domains>,
) -> (Vec<ProgramRelation>, Result<(), End>, Option<Stop>) {
    let (branching, end, stop, _) = walk_dets(inputs, dets, None, root, cap, &mut |evaluation, assigned, _| leaf(evaluation, assigned), domains, false);
    (branching, end, stop)
}

/// [`descend_with`] for a walk of a table, where each step of the walk, a
/// domain or a leaf, is evaluated under limits of its own
/// ([`Limits::for_assignment`]): a step that reaches the table work cap of its
/// own count, or its byte budget, is rejected alone
/// ([`ReachedBound::is_assignment`]), and the other steps go on with counts
/// that start from none.
pub(crate) fn descend_scoped(
    inputs: EvaluationInputs<'_>,
    dets: &[Det],
    root: GraphNodeIndex,
    cap: u64,
    leaf: &mut dyn FnMut(&Evaluation<'_>, &[Assignment]) -> Result<(), End>,
    domains: Option<&dyn Domains>,
) -> (Vec<ProgramRelation>, Result<(), End>, Option<Stop>) {
    let (branching, end, stop, _) = walk_dets(inputs, dets, None, root, cap, &mut |evaluation, assigned, _| leaf(evaluation, assigned), domains, true);
    (branching, end, stop)
}

/// [`descend_with`] for a walk whose `leaf` reads the values that it holds
/// only through the evaluation of `readers`, the picks that it tests.
///
/// A `DET` of `dets` is unread where it is no pick, it has no `(ONE)`, and no
/// later `DET` of `dets` and none of `readers` reads it at any depth. An
/// evaluation reads the value of a `DET` only where the node that it
/// evaluates reaches the node of that `DET` in the dependency graph, and each
/// step after an unread `DET` is a later domain or an evaluation of a node of
/// `readers`, so no step reads the value of an unread `DET`.
///
/// For an unread `DET` the walk asks only for the count of its values
/// ([`Domains::size`]). For each of them it takes the later steps once, with
/// the values it holds and none for that `DET`. Those steps are the same at
/// each value, and the walk takes them as many times as the count, so the
/// leaves, the work counted, the stops and the `DET`s met with several
/// values stand as the values would give them. `leaf` gets, as its last
/// argument, the count of `DET`s of `dets` that `assigned` leaves out in this
/// way.
///
/// The steps after an unread `DET` are the same at each of its values, and
/// the walk takes them once: the later values add the leaves of that one
/// taking to the count, and stop at the assignment cap where the count passes
/// it. `leaf` is called once for those leaves, and the last element of the
/// result is the count of leaves the walk reached, as the walk of each value
/// would count them: more than `cap` where the walk stopped at the cap.
pub(crate) fn descend_unread(
    inputs: EvaluationInputs<'_>,
    dets: &[Det],
    readers: &[Det],
    root: GraphNodeIndex,
    cap: u64,
    leaf: &mut dyn FnMut(&Evaluation<'_>, &[Assignment], usize) -> Result<(), End>,
    domains: Option<&dyn Domains>,
) -> (Vec<ProgramRelation>, Result<(), End>, Option<Stop>, u64) {
    walk_dets(inputs, dets, Some(readers), root, cap, leaf, domains, false)
}

/// For each of `dets`, whether no later `DET` of `dets` and none of `readers`
/// reads it at any depth, and it is no pick and has no `(ONE)`.
fn unread_dets(program: &CheckedProgram, dets: &[Det], readers: &[Det]) -> Vec<bool> {
    let graph = &program.program.graph;
    let reached: Vec<Vec<bool>> = dets.iter().chain(readers).map(|det| graph.reached(det.node)).collect();
    dets.iter().enumerate().map(|(at, det)| !det.pick && !det.open && reached[at + 1..].iter().all(|reached| !reached[det.node.0 as usize])).collect()
}

fn walk_dets(
    inputs: EvaluationInputs<'_>,
    dets: &[Det],
    readers: Option<&[Det]>,
    root: GraphNodeIndex,
    cap: u64,
    leaf: &mut dyn FnMut(&Evaluation<'_>, &[Assignment], usize) -> Result<(), End>,
    domains: Option<&dyn Domains>,
    scoped: bool,
) -> (Vec<ProgramRelation>, Result<(), End>, Option<Stop>, u64) {
    let _timed = stats::span(Phase::TableWalk);
    stats::seen(Phase::TableWalk, || {
        let program = &inputs.program.program;
        stats::digest(&(program.stats_finished_id(), program.program.value().forms.len(), dets.iter().map(|det| &det.relation).collect::<Vec<_>>()))
    });
    let unread = readers.map(|readers| unread_dets(inputs.program, dets, readers)).unwrap_or_default();
    let mut walk = Walk { inputs, dets, root, cap, count: 0, branching: Vec::new(), leaf, domains, unread, skipped: 0, stop: None, scoped };
    let end = walk.descend(0, &mut Vec::new());
    (walk.branching, end, walk.stop, walk.count)
}

/// The walk of one relation's joint assignments.
struct Walk<'w, 'a> {
    inputs: EvaluationInputs<'a>,
    dets: &'w [Det],
    root: GraphNodeIndex,
    cap: u64,
    /// The complete assignments reached.
    count: u64,
    /// The `DET`s met with several values in the domain, in the order met.
    branching: Vec<ProgramRelation>,
    leaf: &'w mut dyn FnMut(&Evaluation<'_>, &[Assignment], usize) -> Result<(), End>,
    domains: Option<&'w dyn Domains>,
    /// For each of `dets`, whether the walk takes only the count of its values,
    /// as [`descend_unread`] gives; empty where it takes each value.
    unread: Vec<bool>,
    /// The count of `DET`s that the walk has left out of the values it holds.
    skipped: usize,
    stop: Option<Stop>,
    /// Whether each step is evaluated under limits of its own ([`descend_scoped`]).
    scoped: bool,
}

impl Walk<'_, '_> {
    /// Each assignment that extends `assigned`, the values of the `DET`s
    /// before `at`, with the domain of each later `DET` at the values
    /// before it.
    fn descend(&mut self, at: usize, assigned: &mut Vec<Assignment>) -> Result<(), End> {
        let end = self.path(at, assigned);
        match end {
            Err(End::Stop(stop)) if stop.bound.is_assignment() => {
                self.stop.get_or_insert(stop);
                Ok(())
            }
            end => end,
        }
    }

    /// Counts the work of one step of the walk: one unit, and one for each
    /// assignment that the step copies. The step's own work is the copy of
    /// `assigned` and the loop over a domain, which no join counts.
    ///
    /// The units of a complete assignment, a leaf, are content: the table of
    /// the walk is its assignments, and the request counts them. The steps
    /// that reach a leaf are the search, and their units are effort, since
    /// the steps to the same leaves follow the order of the `DET`s.
    fn charge(&self, at: usize, units: u64, content: bool) -> Result<(), End> {
        let request = &self.inputs.limits.request;
        (if content { request.charge(units) } else { request.charge_effort(units) }).map_err(|bound| {
            let program = &self.inputs.program.program;
            let form = self.dets.get(at).map_or_else(|| self.dets.last().map_or_else(|| program.form_of(self.root), |det| program.form_of(det.node)), |det| program.form_of(det.node));
            End::Stop(Stop { bound, form: form.clone() })
        })
    }

    fn path(&mut self, at: usize, assigned: &mut Vec<Assignment>) -> Result<(), End> {
        self.charge(at, 1 + assigned.len() as u64, at >= self.dets.len())?;
        let parameters = ParameterValues::determined(assigned.clone());
        let scope;
        let inputs = if self.scoped {
            scope = self.inputs.limits.for_assignment();
            EvaluationInputs {
                program: self.inputs.program,
                concept: self.inputs.concept,
                task: self.inputs.task,
                session: self.inputs.session,
                registry: self.inputs.registry,
                constructions: self.inputs.constructions,
                limits: &scope,
            }
        } else {
            self.inputs
        };
        let Some(det) = self.dets.get(at) else {
            let evaluation = inputs.at(&parameters);
            self.count += 1;
            stats::units(Phase::TableWalk, 1);
            let cap = self.cap;
            let gauges = self.inputs.limits.request.gauges();
            if self.count > cap {
                gauges.hit(crate::eval::Gauge::Assignments, self.count, cap);
                return Err(self.past_cap());
            }
            gauges.note(crate::eval::Gauge::Assignments, self.count, cap);
            return (self.leaf)(&evaluation, assigned, self.skipped);
        };
        if det.open {
            if let Some(fault) = keyed_one(self.inputs.program, det.node) {
                return Err(End::Fault(fault));
            }
        }
        let evaluation = inputs.at(&parameters);
        stats::units(Phase::TableWalk, 1);
        if self.unread.get(at).copied().unwrap_or(false) {
            return self.descend_counted(at, assigned, &evaluation);
        }
        let domain = if det.pick {
            let mut values: Vec<Arc<Relation>> = Vec::new();
            let mut stop = None;
            let mut undefined = false;
            let relation = GraphRelation { node: det.node, output: None };
            let end = evaluation.models(&relation, None, &mut |value| {
                match value {
                    RelationValue::Rows(rows) => {
                        if !values.iter().any(|value| same_rows(value, rows)) {
                            values.push(rows.clone());
                        }
                    },
                    RelationValue::Undefined => undefined = true,
                    RelationValue::Stopped(found) => stop = Some(found.clone()),
                }
                ControlFlow::Continue(())
            }).map_err(End::Fault)?;
            if let ModelsEnd::Stopped(found) = end { stop = Some(found); }
            if let Some(stop) = stop { return Err(End::Stop(stop)); }
            if undefined { return self.descend(at + 1, assigned); }
            values
        } else {
            let domain = match self.domains {
                Some(domains) => domains.domain(&evaluation, at, assigned),
                None => evaluation.domain(det.node),
            };
            match domain.map_err(End::Fault)? {
                Domain::Rows(rows) if det.open => {
                    // `one_row_each` walks each row and compares each with those kept so far: the rows are content, the comparisons are effort.
                    let held = rows.iter().map(|value| value.len()).fold(0u64, u64::saturating_add);
                    self.charge(at, held, true)?;
                    self.charge(at, held.saturating_mul(held), false)?;
                    one_row_each(&rows)
                }
                Domain::Rows(rows) => rows,
                Domain::Undefined => return self.descend(at + 1, assigned),
                Domain::Stopped(stop) => return Err(End::Stop(stop)),
            }
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

impl Walk<'_, '_> {
    /// Each assignment that extends `assigned` with a value of `dets[at]`,
    /// an unread `DET`: the later steps once for each value, with `assigned`
    /// as it is, as [`descend_unread`] gives. The domain's `undefined`, its
    /// stop and the `DET`s met with several values are as the walk of each
    /// value gives them.
    fn descend_counted(&mut self, at: usize, assigned: &mut Vec<Assignment>, evaluation: &Evaluation<'_>) -> Result<(), End> {
        let dets = self.dets;
        let det = &dets[at];
        let size = match self.domains {
            Some(domains) => domains.size(evaluation, at, assigned),
            None => evaluation.domain_size(det.node),
        };
        let count = match size.map_err(End::Fault)? {
            DomainSize::Count(count) => count,
            DomainSize::Undefined => return self.descend(at + 1, assigned),
            DomainSize::Stopped(stop) => return Err(End::Stop(stop)),
        };
        if count > 1 && !self.branching.contains(&det.relation) {
            self.branching.push(det.relation.clone());
        }
        self.skipped += 1;
        let walked = self.repeated(count, at, assigned);
        self.skipped -= 1;
        walked
    }

    /// The steps after `dets[at]` taken `times` times with `assigned` as it
    /// is, which is `times` times the same steps: the walk takes them once,
    /// and the leaves of that one taking stand for the leaves of the others.
    /// A later taking would reach those leaves again, each with the same
    /// verdict from `leaf`, and the same stops, so it adds the leaves to the
    /// count, and ends at the assignment cap where the count passes it.
    fn repeated(&mut self, times: usize, at: usize, assigned: &mut Vec<Assignment>) -> Result<(), End> {
        if times == 0 {
            return Ok(());
        }
        let before = self.count;
        self.descend(at + 1, assigned)?;
        let more = (times as u64 - 1).saturating_mul(self.count - before);
        if more == 0 {
            return Ok(());
        }
        let gauges = self.inputs.limits.request.gauges();
        if self.count.saturating_add(more) > self.cap {
            // The leaf that takes the count past the cap ends the walk, as it does when each taking is walked.
            self.count = self.cap.saturating_add(1);
            gauges.hit(crate::eval::Gauge::Assignments, self.count, self.cap);
            return Err(self.past_cap());
        }
        self.count += more;
        gauges.note(crate::eval::Gauge::Assignments, self.count, self.cap);
        Ok(())
    }

    /// The stop at the assignment cap, at the form of the last `DET` walked.
    fn past_cap(&self) -> End {
        let program = &self.inputs.program.program;
        let form = self.dets.last().map_or_else(|| program.form_of(self.root), |det| program.form_of(det.node));
        End::Stop(Stop { bound: ReachedBound::Assignments { cap: self.cap }, form: form.clone() })
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
/// each parameter in `parameters` they share, with some kept assignment of
/// each other case that keeps one, until no case loses one. A case left
/// with none is unsolved, and a case whose assignments left hold a fault
/// gives it.
fn restrict(walked: &mut [(CaseOutcome, Vec<ProgramRelation>, Vec<Kept>)], parameters: &StableHashSet<ProgramRelation>) {
    loop {
        let mut changed = false;
        for a in 0..walked.len() {
            for b in 0..walked.len() {
                if a == b || walked[b].2.is_empty() {
                    continue;
                }
                let others = walked[b].2.clone();
                let before = walked[a].2.len();
                walked[a].2.retain(|kept| others.iter().any(|other| agree(kept, other, parameters)));
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

/// Whether two assignments give the same rows to each parameter in
/// `parameters` they both assign.
fn agree(a: &Kept, b: &Kept, parameters: &StableHashSet<ProgramRelation>) -> bool {
    a.values.iter().filter(|(name, _)| parameters.contains(name)).all(|(name, value)| b.values.iter().filter(|(other, _)| other == name).all(|(_, other)| same_rows(value, other)))
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
