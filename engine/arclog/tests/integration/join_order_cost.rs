//! The variable order of a clause shaped like a door between two cells
//! places the cell a lib atom's mode gives after the cell it reads, so the
//! join tries a few bindings per cell in place of a cross product of cells.

use std::sync::Arc;

use arclog::check::{check_program, CheckCache, CheckedProgram, SolverClauses};
use arclog::eval::ir::{compile_conjuncts, Argument, AtomSource, ClauseIr, IrNode, Variable};
use arclog::eval::join::{self, Budget, JoinInputs, NodeInput};
use arclog::eval::plan::{variable_order, NodeSize, RelationSizes};
use arclog::eval::{Cancellation, Caps, Limits};
use arclog::program::path::{NodePath, PathStep};
use arclog::read::read_solver;
use arclog::registry::Registry;
use arclog::resolver::resolve;
use arclog::session::{SessionBound, TaskSession};
use arclog::task::{Grid, Task, TrainPair};
use arclog::terms::{Color, Example};

const SIDE: usize = 24;

const BODY: &str = "(input *P)\n  (opposite *D (:Opp *D_opp))\n  (neighbor P D *Q)\n  (input (:P Q))\n  (neighbor P (:D D_opp) (:Q *Q_opp))\n  (input (:P Q_opp))";

fn checked(body: &str) -> CheckedProgram {
    let text = format!("(RULE &body\n  {body})\n");
    let solver = read_solver("door", &text, "", &|_| None).unwrap_or_else(|error| panic!("{text}: {error:?}")).value;
    let registry = Registry::get();
    let case = solver.concept_case();
    let program = resolve(&case.program, None, &solver.derived_relations(), registry).value;
    check_program(program, &SolverClauses::of(&solver, registry), registry, &mut CheckCache::default()).expect("every check passes")
}

fn task() -> Task {
    square_task(SIDE)
}

fn square_task(side: usize) -> Task {
    let rows = (0..side).map(|_| (0..side).map(|_| Color::from_digit(1).expect("a color digit")).collect()).collect();
    let input = Grid::from_rows(rows).expect("a grid");
    Task { train: Box::new([TrainPair { input: input.clone(), output: input }]), test: Box::new([]) }
}

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
                IrNode::Or(union) => NodeInput::Clauses(union.branches.iter().map(|branch| fact_inputs(branch, task)).collect()),
                _ => NodeInput::Unread,
            })
            .collect(),
    )
}

#[test]
fn a_cell_a_mode_gives_stands_after_the_cell_it_reads_and_the_join_tries_few_bindings() {
    let program = checked(BODY);
    let task = task();
    let path = NodePath(Box::new([PathStep(program.program.program.value().forms.len() as u32 - 1)]));
    let clause = compile_conjuncts(&program, &path, &[0, 1, 2, 3, 4, 5]).expect("the body compiles");
    let inputs = fact_inputs(&clause, &task);
    // The sizes of a door clause: the cells 572, and the wall cells 446 twice.
    let mut atom_sizes = [572u64, 446, 446].into_iter();
    let sizes = RelationSizes(
        clause
            .nodes
            .iter()
            .map(|node| if matches!(node, IrNode::Atom(_)) { NodeSize::Rows(atom_sizes.next().expect("three atoms")) } else { NodeSize::Unread })
            .collect(),
    );
    let order = variable_order(&clause, &sizes, &[]);
    // The variables of the three `input` atoms: P, Q and Q_opp.
    let cells: Vec<Variable> = clause
        .nodes
        .iter()
        .filter_map(|node| match node {
            IrNode::Atom(atom) => atom.arguments.0.iter().find_map(|(_, argument)| match argument {
                Argument::Variable(variable) => Some(*variable),
                Argument::Term(_) => None,
            }),
            _ => None,
        })
        .collect();
    let place = |variable: Variable| order.0.iter().position(|v| *v == variable).expect("in the order");
    assert!(place(cells[0]) < place(cells[1]) && place(cells[0]) < place(cells[2]), "{order:?}");
    let session = TaskSession::new(SessionBound { bytes: 1 << 26 }, Caps::CORPUS);
    let limits = Limits::new(None, Cancellation::default());
    join::join(&clause, &order, &inputs, Registry::get(), &mut Budget::new(&limits, &session)).expect("no bound reached");
    let bindings = limits.request.effort();
    assert!(bindings < 10_000, "{bindings} bindings tried");
}

/// A body of one `OR` whose export `Piece` is bound by an atom of each branch
/// and whose export `Offset` is bound by a lib atom alone, so only `Piece`
/// has an estimate.
const UNION_BODY: &str = "(OR ((input (:P *Piece)) (axis_elem (:A *Offset)))\n      ((input (:P Piece)) (axis_elem (:A Offset))))";

#[test]
fn an_export_with_an_estimate_stands_before_one_without_whatever_their_positions() {
    let program = checked(UNION_BODY);
    let path = NodePath(Box::new([PathStep(program.program.program.value().forms.len() as u32 - 1)]));
    let clause = compile_conjuncts(&program, &path, &[0]).expect("the body compiles");
    let IrNode::Or(union) = &clause.nodes[0] else { panic!("a union node") };
    let branch_sizes = union
        .branches
        .iter()
        .map(|branch| RelationSizes(branch.nodes.iter().map(|node| if matches!(node, IrNode::Atom(_)) { NodeSize::Rows(100) } else { NodeSize::Unread }).collect()))
        .collect();
    let sizes = RelationSizes(Box::new([NodeSize::Clauses(branch_sizes)]));
    let order = variable_order(&clause, &sizes, &[]);
    // `Piece` is the export an atom of each branch binds: the one the branches' `input` atoms hold.
    let IrNode::Atom(atom) = &union.branches[0].nodes[0] else { panic!("the branch's `input` atom") };
    let Some((_, Argument::Variable(piece))) = atom.arguments.0.first() else { panic!("a variable at the atom's site") };
    let offset = *union.exported.iter().find(|variable| *variable != piece).expect("two exports");
    assert!(offset.0 < piece.0, "the export without an estimate stands at the lower position: {union:?}");
    assert_eq!(order.0.as_ref(), [*piece, offset], "{order:?}");
}

/// A body shaped like a `$Cross` clause: an atom binds `Corner`, and a union
/// exports `Piece`, `Corner` and `Cell`, where its second branch binds `Piece`
/// only by `(= Piece Corner)`.
const EQUAL_BRANCH_BODY: &str = "(input (:P *Corner))\n  (OR ((input (:P *Piece)) (= Corner Piece) (input (:P *Cell)))\n      ((= Piece Corner) (input (:P Cell))))";

#[test]
fn a_union_export_stands_after_the_variable_its_equal_branch_reads_and_the_join_gives_the_rows() {
    let program = checked(EQUAL_BRANCH_BODY);
    let task = square_task(3);
    let path = NodePath(Box::new([PathStep(program.program.program.value().forms.len() as u32 - 1)]));
    let clause = compile_conjuncts(&program, &path, &[0, 1]).expect("the body compiles");
    let inputs = fact_inputs(&clause, &task);
    let IrNode::Or(union) = &clause.nodes[1] else { panic!("a union node") };
    // The atom's rows exceed the estimate of `Cell`, which each branch binds by an atom of 3 rows.
    let branch_sizes = union
        .branches
        .iter()
        .map(|branch| RelationSizes(branch.nodes.iter().map(|node| if matches!(node, IrNode::Atom(_)) { NodeSize::Rows(3) } else { NodeSize::Unread }).collect()))
        .collect();
    let sizes = RelationSizes(Box::new([NodeSize::Rows(572), NodeSize::Clauses(branch_sizes)]));
    let order = variable_order(&clause, &sizes, &[]);
    let IrNode::Atom(atom) = &clause.nodes[0] else { panic!("the `input` atom") };
    let Some((_, Argument::Variable(corner))) = atom.arguments.0.first() else { panic!("a variable at the atom's site") };
    let place = |variable: Variable| order.0.iter().position(|v| *v == variable).expect("in the order");
    for export in union.exported.iter().filter(|export| *export != corner) {
        assert!(place(*corner) < place(*export), "{order:?}");
    }
    let session = TaskSession::new(SessionBound { bytes: 1 << 26 }, Caps::CORPUS);
    let limits = Limits::new(None, Cancellation::default());
    let relation = join::join(&clause, &order, &inputs, Registry::get(), &mut Budget::new(&limits, &session)).expect("no bound reached");
    // Each of the 9 cells as `Corner` with `Piece` the same cell and each of the 9 cells as `Cell`.
    assert_eq!(relation.len(), 81);
}
