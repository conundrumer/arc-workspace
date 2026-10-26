//! At the stored `param` records, a `DET` whose every form is a `DET` clause
//! with a body, no proposer and no `ONE` mark reads the rows its clause
//! gives, not its record, and a witness's `assign` of it gives its rows in
//! place of its clause's. A `DET` by a proposer reads its record.

use arclog::check::{check_program, CheckCache, SolverClauses};
use arclog::eval::instance::Constructions;
use arclog::eval::{relation_of, Cancellation, Caps, Evaluation, Limits, ParameterValues, RelationValue};
use arclog::program::{DeclaredName, ProgramRelation, RelationName};
use arclog::read::read_solver;
use arclog::registry::Registry;
use arclog::resolver::resolve;
use arclog::session::{SessionBound, TaskSession};
use arclog::task::{Grid, Task, TrainPair};
use arclog::terms::Color;

/// `&colors` is bodied: the colors `1 2` of the task's one input. `&rare` is
/// by a proposer: the rarest color, `2`.
const ARCLOG: &str = "(RULE &color\n  (input (:Col *Col)))\n\
(DET &colors\n  (&color (:Col *Col)))\n\
(DET &rare RarestColor)\n\
(RULE &output\n  (input *P *Col)\n  (&colors (:Col Col))\n  (&rare (:C Col)))\n";

/// The records of `&colors` and `&rare`, each with other rows than the
/// `DET` gives: one row for `&colors`, two for `&rare`.
const RECORDS: &str = "(param &colors Color (3))\n(param &rare Color (3) (4))\n";

/// An assign of `&colors`, with three rows.
const ASSIGN: &str = "(param &colors Color (4) (5) (6))\n";

/// The number of rows of the `DET` of `&<name>` of `ARCLOG`, read at the
/// stored `RECORDS`, with the assigns of `ASSIGN` where `assigned` holds, on a
/// task of one train pair whose input is `1 2 1`.
fn rows_of(name: &str, assigned: bool) -> u64 {
    let solver = read_solver("stored", ARCLOG, RECORDS, &|_| None).unwrap_or_else(|error| panic!("{error:?}")).value;
    let registry = Registry::get();
    let case = solver.concept_case();
    let program = resolve(&case.program, None, &solver.derived_relations(), registry).value;
    let program = check_program(program, &SolverClauses::of(&solver, registry), registry, &mut CheckCache::default()).expect("every check passes");
    let colors = [1, 2, 1].map(|digit| Color::from_digit(digit).expect("a color digit"));
    let input = Grid::from_rows(Box::new([Box::new(colors) as Box<[Color]>])).expect("a grid");
    let task = Task { train: Box::new([TrainPair { input: input.clone(), output: input }]), test: Box::new([]) };
    let mut parameters = ParameterValues::stored(solver.arcdata.value());
    if assigned {
        let assigning = read_solver("assign", ARCLOG, ASSIGN, &|_| None).unwrap_or_else(|error| panic!("{error:?}")).value;
        let assigns: Vec<_> = assigning.arcdata.value().params.iter().map(|param| (param.value().name.clone(), param.value().value.clone())).collect();
        parameters = parameters.with_assigns(&assigns);
    }
    let session = TaskSession::new(SessionBound { bytes: 1 << 26 }, Caps::CORPUS);
    let limits = Limits::new(None, Cancellation::default());
    let constructions = Constructions::new(Vec::new(), registry).expect("an empty table");
    let evaluation = Evaluation { program: &program, concept: None, task: &task, parameters: &parameters, session: &session, registry, constructions: &constructions, limits: &limits };
    let relation = relation_of(&program, &ProgramRelation::Declared(RelationName(DeclaredName::Written(format!("&{name}").into())))).expect("the relation");
    match evaluation.relation(&relation, None) {
        Ok(RelationValue::Rows(rows)) => rows.len(),
        other => panic!("`&{name}` gives {other:?}"),
    }
}

#[test]
fn stored_det_by_its_clause_reads_the_rows_of_its_clause_not_its_record() {
    assert_eq!(rows_of("colors", false), 2, "the clause gives the colors 1 and 2, the record one row");
}

#[test]
fn stored_det_by_its_clause_reads_its_assign_in_place_of_its_clause() {
    assert_eq!(rows_of("colors", true), 3, "the assign gives three rows");
}

#[test]
fn stored_det_by_a_proposer_reads_its_record() {
    assert_eq!(rows_of("rare", false), 2, "the record gives two rows, the proposer one");
}
