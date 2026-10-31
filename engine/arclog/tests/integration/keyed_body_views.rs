//! The BODY of an INIT input outside the key holds at every key group, so its
//! keyed view has the key columns; the BODY of an input in the key already has
//! them, and the plain view of each is unchanged.

use arclog::check::{check_program, CheckCache, SolverClauses};
use arclog::eval::body_view::BodyView;
use arclog::program::path::NodePath;
use arclog::read::read_solver;
use arclog::registry::Registry;
use arclog::resolver::resolve;

const SOLVER: &str = "(INIT &objs Connectivity\n\
  (key ((input (:P *P) (:Col ^Col)))\n\
    (node ((:P P2)) (input (:P *P2) (:Col Col))))\n\
  (step ((:Delta V)) (diag_dir_elem (:D *D)) (step_offset (:D D) (:V *V))))\n";

#[test]
fn a_broadcast_input_is_keyed_and_the_other_views_are_unchanged() {
    let solver = read_solver("inputs", SOLVER, "", &|_| None).unwrap_or_else(|error| panic!("{error:?}")).value;
    let registry = Registry::get();
    let case = solver.concept_case();
    let program = resolve(&case.program, None, &solver.derived_relations(), registry).value;
    let program = check_program(program, &SolverClauses::of(&solver, registry), registry, &mut CheckCache::default()).expect("every check passes");
    let labels = |view: &BodyView| view.clause.columns.iter().map(|v| view.paths.labels[v.0 as usize]).collect::<Vec<_>>();
    let node = NodePath::top(0).child(0).child(1).child(1);
    let step = NodePath::top(0).child(1).child(1);
    let (plain, keyed) = (BodyView::at(&program, &step).expect("plain"), BodyView::keyed_at(&program, &step).expect("keyed"));
    assert_eq!(labels(&keyed).len(), labels(&plain).len() + 1, "the keyed view of `step` adds the key column");
    assert_eq!(labels(&keyed)[1..], labels(&plain)[..], "the key column comes first");
    let (plain, keyed) = (BodyView::at(&program, &node).expect("plain"), BodyView::keyed_at(&program, &node).expect("keyed"));
    assert_eq!(labels(&plain), labels(&keyed), "`node` is in the key, with its key column in both views");
}
