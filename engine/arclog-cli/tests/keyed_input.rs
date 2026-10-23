//! A keyed input reads the key's rows and not the key body's bindings.

use arclog::check::{check_program, CheckCache, CheckedProgram, SolverClauses};
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

fn checked(text: &str) -> CheckedProgram {
    let solver = read_solver("bounds", text, "", &|_| None).unwrap_or_else(|error| panic!("{text}: {error:?}")).value;
    let registry = Registry::get();
    let case = solver.concept_case();
    let program = resolve(&case.program, None, &solver.derived_relations(), registry).value;
    check_program(program, &SolverClauses::of(&solver, registry), registry, &mut CheckCache::default()).expect("every check passes")
}

fn task() -> Task {
    let rows = GRID.iter().map(|row| row.iter().map(|&digit| Color::from_digit(digit).expect("a color digit")).collect()).collect();
    let input = Grid::from_rows(rows).expect("a grid");
    Task { train: Box::new([TrainPair { input: input.clone(), output: input }]), test: Box::new([]) }
}

/// The count of rows of the program's last clause on the train pair under
/// `caps`, or the bound it stopped at.
fn last_clause(text: &str, conjuncts: u32, caps: Caps) -> Result<u64, String> {
    let program = checked(text);
    let task = task();
    let session = TaskSession::new(SessionBound { bytes: 1 << 26 }, caps);
    let registry = Registry::get();
    let parameters = ParameterValues::default();
    let limits = Limits { deadline: None, cancellation: Cancellation::default() };
    let evaluation = Evaluation { program: &program, concept: None, task: &task, parameters: &parameters, session: &session, registry, constructions: arclog_constructions::shared().expect("the table of constructions"), limits: &limits };
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
fn a_keyed_input_does_not_multiply_by_the_key_bodys_local_labels() {
    let text = "(INIT &count Cardinality\n  (key ((input *P ^Col))\n    (member ((:m P)) (input *P Col))))\n(RULE &body (&count.size (:key *Col) *N))\n";
    assert_eq!(last_clause(text, 1, caps(1 << 30, 1 << 21)), Ok(4));
    assert_eq!(last_clause(text, 1, caps(40, 1 << 21)), Ok(4), "the input joins the key's rows alone");
}
