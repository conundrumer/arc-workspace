//! An input that an instance writes no clause for is filled from the key
//! where the registry marks it `from-key`, and holds no row otherwise.

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

const SOLVER: &str = "(INIT &card Cardinality\n\
  (key ((input *P ^Col))\n\
    (member (t)\n\
      (input *P Col)\n\
      (= *t Col))))\n\
(INIT &order Order\n\
  (key ((input *P ^Col))\n\
    (member (t)\n\
      (input *P Col)\n\
      (= *t Col))))\n\
(RULE &filled\n\
  (&card.domain (:key *Col)))\n\
(RULE &unfilled\n\
  (&order.probe (:key *Col)))\n";

/// The grid of `rows`, each a row of color digits.
fn grid(rows: &[&[u8]]) -> Grid {
    let rows = rows.iter().map(|row| row.iter().map(|&digit| Color::from_digit(digit).expect("a color digit")).collect()).collect();
    Grid::from_rows(rows).expect("a grid")
}

#[test]
fn an_unwritten_input_is_filled_from_the_key_only_where_the_registry_marks_it() {
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
    let evaluation = Evaluation { program: &program, concept: None, task: &task, parameters: &parameters, session: &session, registry, constructions: &constructions, limits: &limits };
    let rows = |name: &str| {
        let relation = relation_of(&program, &ProgramRelation::Declared(RelationName(DeclaredName::Written(format!("&{name}").into())))).expect("the relation");
        match evaluation.relation(&relation, Some(Example::at(0))) {
            Ok(RelationValue::Rows(rows)) => rows.len(),
            other => panic!("`&{name}` gives {other:?}"),
        }
    };
    assert_eq!(rows("filled"), 3, "Cardinality's `domain`, marked `from-key`, holds a row for each color of the key");
    assert_eq!(rows("unfilled"), 0, "Order's `probe`, unmarked, holds no row");
}
