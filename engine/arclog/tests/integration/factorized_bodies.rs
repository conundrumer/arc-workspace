//! The rows of a body built from the result cache's entries of its parts
//! equal the rows of a join of the whole body with no entry, and a body one
//! conjunct longer than an evaluated one searches its new part alone.

use std::collections::HashSet;
use std::sync::Arc;

use arclog::check::{check_program, CheckCache, CheckedProgram, SolverClauses};
use arclog::eval::instance::Constructions;
use arclog::eval::ir::{compile_conjuncts, AtomSource, ClauseIr, IrNode};
use arclog::eval::join::{self, Budget, JoinInputs, NodeInput};
use arclog::eval::plan::variable_order;
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

/// What each node of `clause` reads, for a clause whose atoms read `input`
/// alone.
fn fact_inputs(clause: &ClauseIr, task: &Task) -> JoinInputs {
    JoinInputs(
        clause
            .nodes
            .iter()
            .map(|node| match node {
                IrNode::Atom(atom) => {
                    let AtomSource::Fact(fact) = atom.source else { panic!("an atom of a fact relation") };
                    NodeInput::Relation(Arc::new(task.fact_rows(fact, Some(Example::at(0)))))
                }
                IrNode::Not(filter) | IrNode::Counterexample(filter) => NodeInput::Clauses(Box::new([fact_inputs(&filter.body, task)])),
                IrNode::Or(union) => NodeInput::Clauses(union.branches.iter().map(|branch| fact_inputs(branch, task)).collect()),
                IrNode::Lib(_) | IrNode::Comparison(_) => NodeInput::Unread,
            })
            .collect(),
    )
}

/// The rows of the conjuncts at `kept` by one generic join of the whole
/// body, with no entry, or `None` where they do not compile.
fn joined_rows(program: &CheckedProgram, task: &Task, kept: &[u32]) -> Option<HashSet<Vec<TermId>>> {
    let clause = compile_conjuncts(program, &clause_path(program), kept).ok()?;
    let inputs = fact_inputs(&clause, task);
    let order = variable_order(&clause, &join::sizes(&inputs), &[]);
    let session = session();
    let limits = Limits::new(None, Cancellation::default());
    let relation = join::join(&clause, &order, &inputs, Registry::get(), &mut Budget::new(&limits, &session)).expect("no bound reached");
    Some(rows(&relation))
}

#[test]
fn each_subset_of_a_body_of_three_parts_gives_the_rows_of_its_whole_join() {
    let program = checked("(input *P (:Col *A))\n  (input (:P *Q) (:Col *B))\n  (input (:P *R) (:Col B))\n  (input (:P *S) (:Col *C))\n  (!= C B)\n  (input P (:Col B))");
    let task = task();
    let session = session();
    let count = 6u32;
    let mut compiled = 0;
    for mask in 1u32..(1 << count) {
        let kept: Vec<u32> = (0..count).filter(|index| mask & (1 << index) != 0).collect();
        let Some(expected) = joined_rows(&program, &task, &kept) else { continue };
        compiled += 1;
        assert_eq!(body_rows(&program, &task, &session, &kept), expected, "the conjuncts {kept:?}");
    }
    assert!(compiled > count, "most subsets compile");
}

#[test]
fn a_negated_atom_over_two_parts_gives_the_rows_of_its_whole_join() {
    let program = checked("(input *P (:Col *A))\n  (input (:P *Q) (:Col *B))\n  (NOT (input P (:Col B)))");
    let task = task();
    let session = session();
    body_rows(&program, &task, &session, &[0]);
    body_rows(&program, &task, &session, &[1]);
    let expected = joined_rows(&program, &task, &[0, 1, 2]).expect("the body compiles");
    assert_eq!(body_rows(&program, &task, &session, &[0, 1, 2]), expected);
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
