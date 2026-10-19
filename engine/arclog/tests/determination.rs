//! The candidates of a `DET` from the evidence refuse a `DET` that reads a
//! pick of more than one model, and a `DET` with no body and no proposer.

use arclog::check::{check_program, CheckCache, SolverClauses};
use arclog::eval::instance::Constructions;
use arclog::eval::{relation_of, Cancellation, Caps, Evaluation, Limits, Outcome, ParameterValues};
use arclog::program::{DeclaredName, ProgramRelation, RelationName};
use arclog::read::read_solver;
use arclog::registry::Registry;
use arclog::resolver::resolve;
use arclog::session::{SessionBound, TaskSession};
use arclog::task::{Grid, Task, TrainPair};
use arclog::terms::Color;

/// Whether the candidates of the `DET` of `&<name>` in `solver`, at
/// determined values, on a task of one train pair of one row of the colors
/// `colors`, are a fault.
fn candidates_fault(solver: &str, name: &str, colors: &[u8]) -> bool {
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
    let evaluation = Evaluation { program: &program, task: &task, parameters: &parameters, session: &session, registry, constructions: &constructions, limits: &limits };
    let relation = relation_of(&program, &ProgramRelation::Declared(RelationName(DeclaredName::Written(format!("&{name}").into())))).expect("the relation");
    let outcome: Outcome<_> = evaluation.candidates(relation.node);
    outcome.is_err()
}

const READS_A_PICK: &str = "(CHOOSE &pick\n  (from (input *P *Col)))\n(DET &x\n  (&pick *P *Col))\n";

#[test]
fn a_det_that_reads_a_pick_of_two_models_is_refused() {
    assert!(candidates_fault(READS_A_PICK, "x", &[1, 2]), "the pick has a model per cell, and the `DET` reads it");
}

#[test]
fn a_det_that_reads_a_pick_of_one_model_is_kept() {
    assert!(!candidates_fault(READS_A_PICK, "x", &[1]), "the pick has one model");
}

#[test]
fn a_det_with_no_body_and_no_proposer_is_refused() {
    assert!(candidates_fault("(DET &x)\n", "x", &[1]), "`(DET &x)` gives no value");
}
