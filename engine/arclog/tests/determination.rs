//! The domain of a `DET` from the evidence refuses a `DET` that reads a
//! pick of more than one model, and a `DET` with no body and no proposer.
//! The determination reports a `DET` without `(ONE)` that keeps two values
//! as underdetermined, and stops a case whose joint assignments pass the
//! assignment cap.

use arclog::check::{check_program, CheckCache, SolverClauses};
use arclog::eval::instance::Constructions;
use arclog::eval::{relation_of, Cancellation, Caps, Evaluation, Limits, Outcome, ParameterValues, ReachedBound};
use arclog::judge::candidates::World;
use arclog::judge::determination::{determine, CaseOutcome, DeterminedCase, Determination, Parameter};
use arclog::program::{DeclaredName, ProgramRelation, RelationName};
use arclog::read::read_solver;
use arclog::registry::Registry;
use arclog::resolver::resolve;
use arclog::session::{SessionBound, TaskSession};
use arclog::task::{Grid, JudgedPair, JudgedTask, Task, TrainPair};
use arclog::terms::Color;

/// Whether the domain of the `DET` of `&<name>` in `solver`, at
/// determined values, on a task of one train pair of one row of the colors
/// `colors`, are a fault.
fn domain_fault(solver: &str, name: &str, colors: &[u8]) -> bool {
    let solver = read_solver("determination", solver, "", &|_| None).unwrap_or_else(|error| panic!("{error:?}")).value;
    let registry = Registry::get();
    let case = solver.concept_case();
    let program = resolve(&case.program, None, &solver.derived_relations(), registry).value;
    let program = check_program(program, &SolverClauses::of(&solver, registry), registry, &mut CheckCache::default()).expect("every check passes");
    let rows: Box<[Box<[Color]>]> = Box::new([colors.iter().map(|&digit| Color::from_digit(digit).expect("a color")).collect()]);
    let input = Grid::from_rows(rows).expect("a grid");
    let task = Task { train: Box::new([TrainPair { input: input.clone(), output: input }]), test: Box::new([]) };
    let parameters = ParameterValues::determined([]);
    let session = TaskSession::new(SessionBound { bytes: 1 << 26 }, Caps::CORPUS);
    let limits = Limits { deadline: None, cancellation: Cancellation::default() };
    let constructions = Constructions::new(Vec::new(), registry).expect("an empty table");
    let evaluation = Evaluation { program: &program, concept: None, task: &task, parameters: &parameters, session: &session, registry, constructions: &constructions, limits: &limits };
    let relation = relation_of(&program, &ProgramRelation::Declared(RelationName(DeclaredName::Written(format!("&{name}").into())))).expect("the relation");
    let outcome: Outcome<_> = evaluation.domain(relation.node);
    outcome.is_err()
}

const READS_A_PICK: &str = "(CHOOSE &pick\n  (from (input *P *Col)))\n(DET &x\n  (&pick *P *Col))\n";

#[test]
fn a_det_that_reads_a_pick_of_two_models_is_refused() {
    assert!(domain_fault(READS_A_PICK, "x", &[1, 2]), "the pick has a model per cell, and the `DET` reads it");
}

#[test]
fn a_det_that_reads_a_pick_of_one_model_is_kept() {
    assert!(!domain_fault(READS_A_PICK, "x", &[1]), "the pick has one model");
}

#[test]
fn a_det_with_no_body_and_no_proposer_is_refused() {
    assert!(domain_fault("(DET &x)\n", "x", &[1]), "`(DET &x)` gives no value");
}

/// `&<name>` as a program relation.
fn declared(name: &str) -> ProgramRelation {
    ProgramRelation::Declared(RelationName(DeclaredName::Written(format!("&{name}").into())))
}

/// The determination of the concept case of `solver`, on a task of one
/// train pair whose output is its input, one row of the colors `colors`,
/// under `caps`.
fn determination(solver: &str, colors: &[u8], caps: Caps) -> Determination {
    let solver = read_solver("determination", solver, "", &|_| None).unwrap_or_else(|error| panic!("{error:?}")).value;
    let registry = Registry::get();
    let case = solver.concept_case();
    let program = resolve(&case.program, None, &solver.derived_relations(), registry).value;
    let program = check_program(program, &SolverClauses::of(&solver, registry), registry, &mut CheckCache::default()).expect("every check passes");
    let rows: Box<[Box<[Color]>]> = Box::new([colors.iter().map(|&digit| Color::from_digit(digit).expect("a color")).collect()]);
    let input = Grid::from_rows(rows).expect("a grid");
    let task = Task { train: Box::new([TrainPair { input: input.clone(), output: input.clone() }]), test: Box::new([]) };
    let judged = JudgedTask { train: Box::new([JudgedPair { output: input, alt: None }]), test: Box::new([]) };
    let session = TaskSession::new(SessionBound { bytes: 1 << 26 }, caps);
    let limits = Limits { deadline: None, cancellation: Cancellation::default() };
    let constructions = Constructions::new(Vec::new(), registry).expect("an empty table");
    let cases = [DeterminedCase { name: &case.name, program: &program, concept: &program, task: &task, session: &session, registry, constructions: &constructions, limits: &limits }];
    determine(&cases, &judged, World::Closed)
}

/// A solver whose `&output` is its input wherever each `DET` it names has
/// a row, so each value of each solves the train pair.
fn copies_input(names: &[&str]) -> String {
    let dets: String = names.iter().map(|name| format!("(DET &{name} ColorDomain)\n")).collect();
    let reads: String = names.iter().map(|name| format!(" (&{name} (:C *C_{name}))")).collect();
    format!("{dets}(RULE &output (input *P *Col){reads})\n")
}

#[test]
fn a_det_without_one_that_keeps_two_values_is_underdetermined() {
    let found = determination(&copies_input(&["c"]), &[1, 2], Caps::CORPUS);
    assert!(matches!(found.parameter(&declared("c")), Some(Parameter::Underdetermined(values)) if values.len() > 1), "{found:?}");
}

#[test]
fn a_product_past_the_assignment_cap_stops_and_names_the_parameters() {
    let found = determination(&copies_input(&["a", "b"]), &[1, 2], Caps { assignments: 3, ..Caps::CORPUS });
    let [(_, CaseOutcome::Stopped { stop, parameters }, _)] = &found.cases[..] else { panic!("one stopped case: {found:?}") };
    assert_eq!(stop.bound, ReachedBound::Assignments { cap: 3 });
    assert_eq!(parameters, &[declared("a"), declared("b")]);
}
