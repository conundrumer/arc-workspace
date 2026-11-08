//! The domain of a `DET` from the evidence refuses a `DET` that reads a
//! pick of more than one model.
//! The determination reports a `DET` without `(ONE)` that keeps two values
//! as underdetermined, and stops a case whose joint assignments pass the
//! assignment cap.

use arclog::check::{check_program, CheckCache, SolverClauses};
use arclog::eval::instance::Constructions;
use arclog::eval::determinations::Domain;
use arclog::eval::{relation_of, Cancellation, Caps, Evaluation, Limits, Outcome, ParameterValues};
use arclog::program::{DeclaredName, ProgramRelation, RelationName};
use arclog::read::read_solver;
use arclog::registry::Registry;
use arclog::resolver::resolve;
use arclog::session::{SessionBound, TaskSession};
use arclog::task::{Grid, Task, TrainPair};
use arclog::terms::Color;

/// The domain of the `DET` of `&<name>` in `solver`, at determined values,
/// on a task of one train pair of one row of the colors `colors`.
fn domain_of(solver: &str, name: &str, colors: &[u8]) -> Outcome<Domain> {
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
    let limits = Limits::new(None, Cancellation::default());
    let constructions = Constructions::new(Vec::new(), registry).expect("an empty table");
    let evaluation = Evaluation { program: &program, concept: None, task: &task, parameters: &parameters, session: &session, registry, constructions: &constructions, limits: &limits };
    let relation = relation_of(&program, &ProgramRelation::Declared(RelationName(DeclaredName::Written(format!("&{name}").into())))).expect("the relation");
    evaluation.domain(relation.node)
}

/// Whether the domain of the `DET` of `&<name>` in `solver`, at
/// determined values, on a task of one train pair of one row of the colors
/// `colors`, are a fault.
fn domain_fault(solver: &str, name: &str, colors: &[u8]) -> bool {
    domain_of(solver, name, colors).is_err()
}

/// The number of values in the domain of the `DET` of `&<name>` in
/// `solver`, on a task of one train pair of one row of the colors `colors`.
fn domain_size(solver: &str, name: &str, colors: &[u8]) -> usize {
    match domain_of(solver, name, colors).expect("a domain") {
        Domain::Rows(values) => values.len(),
        other => panic!("a domain of rows, not {other:?}"),
    }
}

const READS_A_PICK: &str = "(RULE &pick (input *P *Col)\n  (ONE))\n(DET &x\n  (&pick *P *Col))\n";

#[test]
fn a_det_that_reads_a_pick_of_two_models_is_refused() {
    assert!(domain_fault(READS_A_PICK, "x", &[1, 2]), "the pick has a model per cell, and the `DET` reads it");
}

#[test]
fn a_det_that_reads_a_pick_of_one_model_is_kept() {
    assert!(!domain_fault(READS_A_PICK, "x", &[1]), "the pick has one model");
}

const BOTH_COLORS_UNCHANGED: &[u8] = &[1, 2];

#[test]
fn a_det_by_a_one_column_proposer_has_one_value_per_row() {
    assert_eq!(domain_size("(DET &c UnchangedColor)\n", "c", BOTH_COLORS_UNCHANGED), 2, "two rows, two values");
}

#[test]
fn a_set_mark_gives_a_det_by_a_one_column_proposer_one_value() {
    assert_eq!(domain_size("(DET &c UnchangedColor (SET))\n", "c", BOTH_COLORS_UNCHANGED), 1, "the whole set of rows is the one value");
}

#[test]
fn a_det_by_a_two_column_proposer_has_one_value() {
    assert_eq!(domain_size("(DET &p ChangedPairs)\n", "p", &[1, 2]), 1, "the proposer's whole set of rows");
}
