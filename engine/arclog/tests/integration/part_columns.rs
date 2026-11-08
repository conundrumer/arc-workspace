//! The rows of a body are the same with an empty result cache and with a
//! cache that other bodies of its clause filled. A part of a body has an
//! entry in the cache whose cells stand in the order of the part's columns
//! in the canonical order of the part, which differs from the order of the
//! columns of the body as written, so a body that reads an entry another
//! body made reads each cell under its own column.

use std::collections::HashSet;

use arclog::check::{check_program, CheckCache, CheckedProgram, SolverClauses};
use arclog::eval::instance::Constructions;
use arclog::eval::join;
use arclog::eval::{Cancellation, Caps, Evaluation, Limits, ParameterValues, RelationValue};
use arclog::program::path::{NodePath, PathStep};
use arclog::read::read_solver;
use arclog::registry::Registry;
use arclog::resolver::resolve;
use arclog::session::{SessionBound, TaskSession};
use arclog::task::{Grid, Task, TrainPair};
use arclog::terms::{Color, Example, TermId};

/// The input grid of the one train pair.
const GRID: &[&[u8]] = &[&[1, 2, 0], &[2, 2, 1], &[0, 3, 3]];

/// The conjuncts of the one clause. The parts of the whole body, and of each
/// subset of its conjuncts, hold columns of two types in several orders.
const CONJUNCTS: [&str; 4] = ["(input *P)", "(input (:P *Q) (:Col *B))", "(input (:P *R) (:Col B))", "(input (:P Q) (:Col *C))"];

/// A program whose last clause has the conjuncts of `conjuncts`.
fn checked(conjuncts: &[&str]) -> CheckedProgram {
    let text = format!("(RULE &body\n  {})\n", conjuncts.join("\n  "));
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

/// The rows of the conjuncts at `kept` of the clause, from `session`'s
/// entries, in the order of the columns of the body that `kept` makes; none
/// where `kept` leaves a label unbound.
fn body_rows(program: &CheckedProgram, task: &Task, session: &TaskSession, kept: &[u32]) -> Option<HashSet<Vec<TermId>>> {
    let registry = Registry::get();
    let parameters = ParameterValues::default();
    let limits = Limits::new(None, Cancellation::default());
    let constructions = Constructions::new(Vec::new(), registry).expect("an empty table");
    let evaluation = Evaluation { program, concept: None, task, parameters: &parameters, session, registry, constructions: &constructions, limits: &limits };
    match evaluation.body(&clause_path(program), kept, Some(Example::at(0))) {
        Ok(value) => match &value.0 {
            RelationValue::Rows(relation) => {
                let mut found = HashSet::new();
                join::each_row(relation, &mut |row| {
                    found.insert(row.to_vec());
                });
                Some(found)
            }
            other => panic!("the conjuncts {kept:?} give {other:?}"),
        },
        Err(_) => None,
    }
}

/// The subsets of the conjuncts' indexes, none empty, in the order of their
/// bits.
fn subsets() -> Vec<Vec<u32>> {
    (1u32..(1 << CONJUNCTS.len())).map(|mask| (0..CONJUNCTS.len() as u32).filter(|&bit| (mask >> bit) & 1 == 1).collect()).collect()
}

/// Asserts that the rows of every subset of the conjuncts of `conjuncts`, from
/// one session that holds the entries of the subsets before it, in each of
/// three orders of the subsets, are those from a session of no entry.
fn same_rows_cold_and_warm(conjuncts: &[&str]) {
    let program = checked(conjuncts);
    let task = task();
    let subsets = subsets();
    let cold: Vec<Option<HashSet<Vec<TermId>>>> = subsets.iter().map(|kept| body_rows(&program, &task, &session(), kept)).collect();
    assert!(cold.iter().flatten().count() > 1, "some subsets of the conjuncts compile");
    let count = subsets.len();
    let forward: Vec<usize> = (0..count).collect();
    let backward: Vec<usize> = (0..count).rev().collect();
    // 4 and 15 share no factor, so the stride visits each subset once.
    let strided: Vec<usize> = (0..count).map(|at| (at * 4) % count).collect();
    for (name, order) in [("forward", forward), ("backward", backward), ("strided", strided)] {
        let warm = session();
        for index in order {
            let found = body_rows(&program, &task, &warm, &subsets[index]);
            assert_eq!(found, cold[index], "the conjuncts {:?}, read in the {name} order from the entries of the subsets before them", subsets[index]);
        }
    }
}

#[test]
fn a_body_has_the_same_rows_from_entries_that_other_bodies_of_its_clause_made() {
    same_rows_cold_and_warm(&CONJUNCTS);
}

#[test]
fn a_body_has_the_same_rows_where_its_conjuncts_are_written_in_another_order() {
    same_rows_cold_and_warm(&["(input (:P *R) (:Col *B))", "(input (:P *Q) (:Col B))", "(input *P)", "(input (:P Q) (:Col *C))"]);
}
