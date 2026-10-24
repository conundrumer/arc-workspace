//! The variable order of a clause shaped like a door between two cells
//! places the cell a lib atom's mode gives after the cell it reads, so the
//! join tries a few bindings per cell in place of a cross product of cells.

use std::sync::Arc;

use arclog::check::{check_program, CheckCache, CheckedProgram, SolverClauses};
use arclog::eval::ir::{compile_conjuncts, Argument, AtomSource, ClauseIr, IrNode, Variable};
use arclog::eval::join::{self, Budget, JoinInputs, NodeInput};
use arclog::eval::plan::{variable_order, RelationSizes};
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
    let rows = (0..SIDE).map(|_| (0..SIDE).map(|_| Color::from_digit(1).expect("a color digit")).collect()).collect();
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
    let sizes = RelationSizes(clause.nodes.iter().map(|node| matches!(node, IrNode::Atom(_)).then(|| atom_sizes.next().expect("three atoms"))).collect());
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
    let limits = Limits { deadline: None, cancellation: Cancellation::default() };
    join::join(&clause, &order, &inputs, Registry::get(), &mut Budget::new(&limits, &session)).expect("no bound reached");
    let bindings = session.largest_counts().bindings;
    assert!(bindings < 10_000, "{bindings} bindings tried");
}
