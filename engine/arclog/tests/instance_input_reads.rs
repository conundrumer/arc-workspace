//! A clause that reads an input port of an instance reads the rows the
//! instance's construction takes for that input, the key at the port's
//! `key` column, with no construction run.

use arclog::check::{check_program, CheckCache, SolverClauses};
use arclog::eval::instance::Constructions;
use arclog::eval::{relation_of, Cancellation, Caps, Evaluation, Limits, ParameterValues, RelationValue};
use arclog::program::{DeclaredName, ProgramRelation, RelationName};
use arclog::read::read_solver;
use arclog::registry::Registry;
use arclog::resolver::resolve;
use arclog::session::{SessionBound, TaskSession};
use arclog::task::{Grid, Task, TrainPair};
use arclog::terms::{Color, Example};

const SOLVER: &str = "(INIT &bbox BoundingBox\n\
  (key ((input *P ^Col))\n\
    (cell (P)\n\
      (input *P Col))))\n\
(RULE &field\n\
  (&bbox.cell (:key *Col) *P))\n\
(RULE &missing\n\
  (input *P *Col)\n\
  (NOT (&bbox.cell (:key Col) P)))\n";

/// The grid of `rows`, each a row of color digits.
fn grid(rows: &[&[u8]]) -> Grid {
    let rows = rows.iter().map(|row| row.iter().map(|&digit| Color::from_digit(digit).expect("a color digit")).collect()).collect();
    Grid::from_rows(rows).expect("a grid")
}

#[test]
fn a_clause_reads_the_keyed_input_of_an_instance() {
    let solver = read_solver("inputs", SOLVER, "", &|_| None).unwrap_or_else(|error| panic!("{error:?}")).value;
    let registry = Registry::get();
    let case = solver.concept_case();
    let program = resolve(&case.program, None, &solver.derived_relations(), registry).value;
    let program = check_program(program, &SolverClauses::of(&solver, registry), registry, &mut CheckCache::default()).expect("every check passes");
    let input = grid(&[&[1, 2, 0], &[2, 2, 1]]);
    let task = Task { train: Box::new([TrainPair { input: input.clone(), output: input }]), test: Box::new([]) };
    let parameters = ParameterValues::stored(solver.arcdata.value());
    let session = TaskSession::new(SessionBound { bytes: 1 << 26 }, Caps::CORPUS);
    let limits = Limits { deadline: None, cancellation: Cancellation::default() };
    let constructions = Constructions::new(Vec::new(), registry).expect("an empty table");
    let evaluation = Evaluation { program: &program, task: &task, parameters: &parameters, session: &session, registry, constructions: &constructions, limits: &limits };
    let rows = |name: &str| {
        let relation = relation_of(&program, &ProgramRelation::Declared(RelationName(DeclaredName::Written(format!("&{name}").into())))).expect("the relation");
        match evaluation.relation(&relation, Some(Example::at(0))) {
            Ok(RelationValue::Rows(rows)) => rows.len(),
            other => panic!("`&{name}` gives {other:?}"),
        }
    };
    assert_eq!(rows("field"), 6, "`&field` holds one row per cell of the grid");
    assert_eq!(rows("missing"), 0, "every cell stands in `&bbox.cell` at its color's key");
}
