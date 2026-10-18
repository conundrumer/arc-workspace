//! `ProgramTypes::columns` gives the type of each column of each relation
//! of a checked program, in the order of its rows: a relation that two
//! clauses give, one whose clause reads a lib relation, a per-input
//! relation that a task-wide form reads lifted, an instance's input and
//! output, and the relation of a clause on that output, whose record
//! column takes a column per field.

use arclog::check::{check_program, CheckCache, CheckedProgram, SolverClauses};
use arclog::program::path::{NodePath, PathStep};
use arclog::program::PortName;
use arclog::read::read_solver;
use arclog::registry::Registry;
use arclog::resolver::{resolve, DependencyKind, GraphNodeIndex};
use arclog::types::{GraphRelation, ValueType};

fn checked(arclog: &str) -> CheckedProgram {
    let solver = read_solver("columns", arclog, "", &|_| None).expect("the file reads").value;
    let registry = Registry::get();
    let program = resolve(&solver.program, None, &solver.derived_relations(), registry).value;
    let clauses = SolverClauses::of(&solver, registry);
    check_program(program, &clauses, registry, &mut CheckCache::default()).expect("every check passes")
}

const PROGRAM: &str = "
(RULE &extent (input *P *Col) (frame_extent P *A *N))
(RULE &cells (input *P *Col))
(RULE &cells (&extent *P *Col))
(DET &lifted (&cells *E *P *Col))
(INIT &obj Connectivity
  (key ((&lifted ^E *P))
    (node (P)
      (&lifted E *P *Col))))
(DET &reads (&obj.component (:key (:E *K)) *P *Id))
(RULE_OR_DET &obj.component \"the components\")
";

/// The column types of the relation of the node whose forms hold the
/// top-level form at `form`, or, with `port`, of the instance's node of
/// that input or output.
fn columns(checked: &CheckedProgram, form: u32, port: Option<&str>) -> Option<Vec<ValueType>> {
    let program = &checked.program;
    let path = NodePath(Box::new([PathStep(form)]));
    let mut nodes = (0..program.graph.nodes.len() as u32).map(GraphNodeIndex).filter(|node| program.forms_of(*node).contains(&path));
    let node = nodes
        .find(|node| match (&program.graph.nodes[node.0 as usize].kind, port) {
            (DependencyKind::InstanceInput { input: found, .. } | DependencyKind::InstanceOutput { output: found, .. }, Some(port)) => *found == PortName(port.into()),
            (_, None) => true,
            _ => false,
        })
        .expect("a node of the form");
    checked.types.columns(&GraphRelation { node, output: None }).map(<[ValueType]>::to_vec)
}

#[test]
fn each_relation_takes_the_type_of_each_of_its_columns() {
    use ValueType::{Axis, Box, Color, Example, Ident, Number};
    let checked = checked(PROGRAM);
    let found: Vec<Option<Vec<ValueType>>> = vec![
        columns(&checked, 0, None),
        columns(&checked, 1, None),
        columns(&checked, 3, None),
        columns(&checked, 4, Some("node")),
        columns(&checked, 4, Some("component")),
        columns(&checked, 5, None),
        columns(&checked, 6, None),
    ];
    let expected = vec![
        Some(vec![Box, Color, Axis, Number]),
        Some(vec![Box, Color]),
        Some(vec![Example, Box, Color]),
        Some(vec![Example, Box]),
        Some(vec![Example, Box, Ident]),
        Some(vec![Example, Box, Ident]),
        Some(vec![Example, Box, Ident]),
    ];
    assert_eq!(found, expected);
}
