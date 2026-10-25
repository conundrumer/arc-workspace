//! A body's evaluation does not depend on where its `NOT` stands, a `NOT` of
//! an atom that reads no column holds where the relation holds no row, and
//! a pick's search branches by group.

use arclog::check::{check_program, CheckCache, CheckedProgram, SolverClauses};
use arclog::constraints::Pick;
use arclog::eval::instance::Constructions;
use arclog::eval::{Cancellation, Caps, Evaluation, Limits, ParameterValues, RelationValue};
use arclog::program::path::{NodePath, PathStep};
use arclog::read::read_solver;
use arclog::registry::Registry;
use arclog::resolver::resolve;
use arclog::session::{SessionBound, TaskSession};
use arclog::task::{Grid, Task, TrainPair};
use arclog::terms::{Color, Example};

/// The input grid of the one train pair.
const GRID: &[&[u8]] = &[&[1, 2, 0, 0], &[2, 2, 1, 1], &[0, 3, 3, 3], &[1, 1, 1, 2]];
/// A grid of 100 cells, of which 50 are color 0, a wall.
const WIDE: &[&[u8]] = &[
    &[1, 0, 1, 0, 1, 0, 1, 0, 1, 0],
    &[0, 1, 0, 1, 0, 1, 0, 1, 0, 1],
    &[1, 0, 1, 0, 1, 0, 1, 0, 1, 0],
    &[0, 1, 0, 1, 0, 1, 0, 1, 0, 1],
    &[1, 0, 1, 0, 1, 0, 1, 0, 1, 0],
    &[0, 1, 0, 1, 0, 1, 0, 1, 0, 1],
    &[1, 0, 1, 0, 1, 0, 1, 0, 1, 0],
    &[0, 1, 0, 1, 0, 1, 0, 1, 0, 1],
    &[1, 0, 1, 0, 1, 0, 1, 0, 1, 0],
    &[0, 1, 0, 1, 0, 1, 0, 1, 0, 1],
];

fn checked(text: &str) -> CheckedProgram {
    let solver = read_solver("bounds", text, "", &|_| None).unwrap_or_else(|error| panic!("{text}: {error:?}")).value;
    let registry = Registry::get();
    let case = solver.concept_case();
    let program = resolve(&case.program, None, &solver.derived_relations(), registry).value;
    check_program(program, &SolverClauses::of(&solver, registry), registry, &mut CheckCache::default()).expect("every check passes")
}

fn task(grid: &[&[u8]]) -> Task {
    let rows = grid.iter().map(|row| row.iter().map(|&digit| Color::from_digit(digit).expect("a color digit")).collect()).collect();
    let input = Grid::from_rows(rows).expect("a grid");
    Task { train: Box::new([TrainPair { input: input.clone(), output: input }]), test: Box::new([]) }
}

/// The count of rows of the program's last clause on the train pair under
/// `caps`, or the bound it stopped at.
fn last_clause(text: &str, conjuncts: u32, grid: &[&[u8]], caps: Caps) -> Result<u64, String> {
    let program = checked(text);
    let task = task(grid);
    let session = TaskSession::new(SessionBound { bytes: 1 << 26 }, caps);
    let registry = Registry::get();
    let parameters = ParameterValues::default();
    let limits = Limits::new(None, Cancellation::default());
    let constructions = Constructions::new(Vec::new(), registry).expect("an empty table");
    let evaluation = Evaluation { program: &program, concept: None, task: &task, parameters: &parameters, session: &session, registry, constructions: &constructions, limits: &limits };
    let path = NodePath(Box::new([PathStep(program.program.program.value().forms.len() as u32 - 1)]));
    let value = evaluation.body(&path, &(0..conjuncts).collect::<Vec<_>>(), Some(Example::at(0))).map_err(|fault| format!("{fault:?}"))?;
    match &value.0 {
        RelationValue::Rows(_) => Ok(value.count().expect("a count")),
        other => Err(format!("{other:?}")),
    }
}

fn caps(bindings: u64, rows: u64) -> Caps {
    Caps { bindings, rows, ..Caps::CORPUS }
}

#[test]
fn the_position_of_a_not_does_not_change_the_rows_or_the_bounds() {
    let outcomes: Vec<_> = [1, 3, 6]
        .into_iter()
        .map(|at| {
            let mut conjuncts = vec![
                "(opposite *D (:Opp *D_opp))",
                "(neighbor P D *Q)",
                "(&wall (:P Q))",
                "(neighbor P (:D D_opp) (:Q *Q_opp))",
                "(&wall (:P Q_opp))",
            ];
            conjuncts.insert(at - 1, "(NOT (&wall P))");
            let text = format!("(RULE &wall (input *P (:Col 0)))\n(RULE &body (input *P) {})\n", conjuncts.join(" "));
            last_clause(&text, 7, WIDE, caps(1 << 30, 3000))
        })
        .collect();
    assert!(outcomes.windows(2).all(|pair| pair[0] == pair[1]), "{outcomes:?}");
}

#[test]
fn a_not_of_an_atom_with_no_column_holds_where_the_relation_holds_no_row() {
    let empty = "(RULE &none (input *P *Col) (!= P P))\n";
    assert_eq!(last_clause(&format!("{empty}(RULE &body (input *P *Col) (NOT (&none)))\n"), 2, GRID, Caps::CORPUS), Ok(16));
    let full = "(RULE &some (input *P *Col))\n";
    assert_eq!(last_clause(&format!("{full}(RULE &body (input *P *Col) (NOT (&some)))\n"), 2, GRID, Caps::CORPUS), Ok(0));
}

#[test]
fn a_pick_of_three_groups_of_two_passes_14_nodes() {
    let groups: Vec<Box<[usize]>> = vec![Box::new([0, 1]), Box::new([2, 3]), Box::new([4, 5])];
    let pick = Pick::new(6, &groups, &[]).expect("a pick");
    let models: Vec<_> = pick.models(14, false).collect();
    assert_eq!(models.len(), 8);
    assert!(models.iter().all(Result::is_ok));
}
