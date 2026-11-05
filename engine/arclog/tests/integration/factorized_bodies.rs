//! The rows of a body built from the result cache's entries of its parts
//! equal the rows of a join of the whole body with no entry, and a body one
//! conjunct longer than an evaluated one searches its new part alone.

use std::collections::HashSet;

use arclog::check::{check_program, CheckCache, CheckedProgram, SolverClauses};
use arclog::eval::instance::Constructions;
use arclog::eval::join;
use arclog::eval::{Cancellation, Caps, Evaluation, Limits, ParameterValues, RelationValue};
use arclog::program::path::{NodePath, PathStep};
use arclog::read::read_solver;
use arclog::registry::Registry;
use arclog::resolver::resolve;
use arclog::session::{Counts, SessionBound, TaskSession};
use arclog::task::{Grid, Task, TrainPair};
use arclog::terms::{Color, Example, TermId};

/// The input grid of the one train pair.
const GRID: &[&[u8]] = &[&[1, 2, 0], &[2, 2, 1], &[0, 3, 3]];

/// A program whose last clause is `body`.
fn checked(body: &str) -> CheckedProgram {
    let text = format!("(RULE &body\n  {body})\n");
    let solver = read_solver("parts", &text, "", &|_| None).unwrap_or_else(|error| panic!("{text}: {error:?}")).value;
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

fn session() -> TaskSession {
    TaskSession::new(SessionBound { bytes: 1 << 26 }, Caps::CORPUS)
}

/// The path of the clause, the program's last form.
fn clause_path(program: &CheckedProgram) -> NodePath {
    NodePath(Box::new([PathStep(program.program.program.value().forms.len() as u32 - 1)]))
}

/// Each row of `relation`.
fn rows(relation: &arclog::relations::Relation) -> HashSet<Vec<TermId>> {
    let mut found = HashSet::new();
    join::each_row(relation, &mut |row| {
        found.insert(row.to_vec());
    });
    found
}

/// The rows of the conjuncts at `kept` of the clause, from `session`'s
/// entries.
fn body_rows(program: &CheckedProgram, task: &Task, session: &TaskSession, kept: &[u32]) -> HashSet<Vec<TermId>> {
    let registry = Registry::get();
    let parameters = ParameterValues::default();
    let limits = Limits::new(None, Cancellation::default());
    let constructions = Constructions::new(Vec::new(), registry).expect("an empty table");
    let evaluation = Evaluation { program, concept: None, task, parameters: &parameters, session, registry, constructions: &constructions, limits: &limits };
    match evaluation.body(&clause_path(program), kept, Some(Example::at(0))) {
        Ok(value) => match &value.0 {
            RelationValue::Rows(relation) => {
                let found = rows(relation);
                assert_eq!(value.count(), Some(found.len() as u64), "the count of the conjuncts {kept:?} is the product of their parts' counts");
                assert_eq!(value.is_empty(), Some(found.is_empty()), "the conjuncts {kept:?} are empty where a part is");
                found
            }
            other => panic!("the conjuncts {kept:?} give {other:?}"),
        },
        Err(fault) => panic!("the conjuncts {kept:?} give {fault:?}"),
    }
}

#[test]
fn a_body_one_conjunct_longer_searches_its_new_part_alone() {
    let program = checked("(input *P)\n  (input (:P *Q) (:Col *B))\n  (input (:P *R) (:Col B))");
    let task = task();
    let alone = session();
    body_rows(&program, &task, &alone, &[1, 2]);
    let extended = session();
    body_rows(&program, &task, &extended, &[0]);
    let first = extended.largest_counts();
    assert!(first.bindings > 0 && first.bindings < alone.largest_counts().bindings, "the first part costs less than the new one");
    body_rows(&program, &task, &extended, &[0, 1, 2]);
    let counts: Counts = extended.largest_counts();
    assert_eq!(counts, alone.largest_counts(), "the longer body counts the work of its new part alone");
}

#[test]
fn a_union_with_a_branch_of_no_conjunct_and_no_column_gives_one_empty_row() {
    let program = checked("(OR ()\n      ((input *P (:Col *A))))");
    let task = task();
    let session = session();
    assert_eq!(body_rows(&program, &task, &session, &[0]), HashSet::from([Vec::new()]));
}
