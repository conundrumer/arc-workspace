//! The BODY of an INIT input outside the key holds at every key group. Where
//! its port has a key column, its keyed view has the key columns; the BODY of
//! an input in the key already has them, and a port without a key column does
//! not carry the key. The plain view of each is unchanged.

use arclog::check::{check_program, CheckCache, SolverClauses};
use arclog::eval::body_view::BodyView;
use arclog::program::path::NodePath;
use arclog::read::read_solver;
use arclog::registry::Registry;
use arclog::resolver::resolve;

/// `node` is in the key, `step` is outside it and its port has no key column.
const CONNECTIVITY: &str = "(INIT &objs Connectivity\n\
  (key ((input (:P *P) (:Col ^Col)))\n\
    (node ((:P P2)) (input (:P *P2) (:Col Col))))\n\
  (step ((:Delta V)) (diag_dir_elem (:D *D)) (step_offset (:D D) (:V *V))))\n";

/// `node` is outside the key and its port has a key column.
const RAY: &str = "(INIT &ray Ray\n\
  (key ((dir8_elem (:D ^D)))\n\
    (source ((:P Q)) (input (:P *P)) (neighbor (:P P) (:D D) (:Q *Q)))\n\
    (dir ((:D D))))\n\
  (node ((:P P2)) (input (:P *P2))))\n";

fn labels_of(text: &str, at: &NodePath) -> (Vec<arclog::program::LabelId>, Vec<arclog::program::LabelId>) {
    let solver = read_solver("inputs", text, "", &|_| None).unwrap_or_else(|error| panic!("{error:?}")).value;
    let registry = Registry::get();
    let case = solver.concept_case();
    let program = resolve(&case.program, None, &solver.derived_relations(), registry).value;
    let program = check_program(program, &SolverClauses::of(&solver, registry), registry, &mut CheckCache::default()).expect("every check passes");
    let labels = |view: BodyView| view.clause.columns.iter().map(|v| view.paths.labels[v.0 as usize]).collect::<Vec<_>>();
    (labels(BodyView::at(&program, at).expect("plain")), labels(BodyView::keyed_at(&program, at).expect("keyed")))
}

#[test]
fn a_keyed_broadcast_input_has_the_key_and_the_other_views_are_unchanged() {
    let (plain, keyed) = labels_of(RAY, &NodePath::top(0).child(1).child(1));
    assert_eq!(keyed.len(), plain.len() + 1, "the keyed view of `node` adds the key column");
    assert_eq!(keyed[1..], plain[..], "the key column comes first");
    let (plain, keyed) = labels_of(CONNECTIVITY, &NodePath::top(0).child(1).child(1));
    assert_eq!(plain, keyed, "`step` has no key column in its port");
    let (plain, keyed) = labels_of(CONNECTIVITY, &NodePath::top(0).child(0).child(1).child(1));
    assert_eq!(plain, keyed, "`node` is in the key, with its key column in both views");
}
