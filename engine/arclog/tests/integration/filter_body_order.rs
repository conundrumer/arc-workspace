//! The variable order of a filter's body takes the variables the filter
//! reads from the enclosing clause as bound, so each output of a lib atom
//! that reads such a variable is placed after the inputs of a mode.

use arclog::check::{check_program, CheckCache, CheckedProgram, SolverClauses};
use arclog::eval::ir::{compile_instance_body, IrNode};
use arclog::eval::plan::variable_order;
use arclog::program::path::{NodePath, PathStep};
use arclog::program::Form;
use arclog::read::read_solver;
use arclog::registry::Registry;
use arclog::resolver::resolve;

/// A filter whose body chains lib atoms from outer variables: `Q`, the
/// output of `compose`, has a lower index than `D1`, the output of `split`
/// that `compose` reads.
const SOLVER: &str = "(RULE &cells (input *P *Col))\n\
(RULE &mark (input *P Col))\n\
(RIGID_DET &piece\n\
  (key ((&cells *P ^Col) (&cells (:P *D) (:Col ^C2))\n\
        (ALL ((axis_elem (:A *Ax))\n\
              (split (:P P) (:A Ax) (:Along *A1))\n\
              (split (:P D) (:A Ax) (:Across *D1))\n\
              (compose (:A A1) (:B D1) (:C *Q)))\n\
             ((&mark (:P Q)))))\n\
    (&cells *P Col)))\n";

fn checked(text: &str) -> CheckedProgram {
    let solver = read_solver("filter", text, "", &|_| None).unwrap_or_else(|error| panic!("{text}: {error:?}")).value;
    let registry = Registry::get();
    let case = solver.concept_case();
    let program = resolve(&case.program, None, &solver.derived_relations(), registry).value;
    check_program(program, &SolverClauses::of(&solver, registry), registry, &mut CheckCache::default()).expect("every check passes")
}

#[test]
fn a_filter_body_orders_its_outputs_after_the_outer_variables() {
    let program = checked(SOLVER);
    let index = program.program.program.value().forms.len() as u32 - 1;
    let path = NodePath(Box::new([PathStep(index)]));
    let Form::RigidDet(rigid) = program.program.program.value().forms.last().expect("the form") else { panic!("a RIGID_DET form") };
    let key = rigid.value().key.as_ref().expect("a key clause");
    let columns: Vec<_> = key.columns.iter().map(|column| column.label).collect();
    let clause = compile_instance_body(&program, &path, &[(key.body.value(), path.child(0))], &columns).expect("compiles");
    // `ALL` compiles to a filter whose body holds a filter over the lib atoms.
    let filter_of = |clause: &arclog::eval::ir::ClauseIr| {
        clause.nodes.iter().find_map(|node| match node {
            IrNode::Not(filter) | IrNode::Counterexample(filter) => Some(filter.clone()),
            _ => None,
        })
    };
    let filter = filter_of(&clause).and_then(|outer| filter_of(&outer.body)).expect("a filter in a filter");
    let body = &filter.body;
    let none = vec![arclog::eval::plan::NodeSize::Unread; body.nodes.len()];
    let order = variable_order(body, &arclog::eval::plan::RelationSizes(none.into()), &filter.outer);
    let expected: Vec<u16> = vec![0, 5, 6, 1];
    assert_eq!(order.0.iter().map(|v| v.0).collect::<Vec<_>>(), expected, "each output of a lib atom stands after the inputs of its mode, and no outer variable stands in the order");
}
