//! An `INIT` instance, a `RIGID_DET` form and a `DEMONSTRATED` form with no
//! key clause give relations with no `key` column.

use arclog::layout::SourceFile;
use arclog::read::{read_arclog, read_solver};
use arclog::registry::Registry;
use std::sync::Arc;

use arclog::check::{check_program, CheckCache, SolverClauses};
use arclog::resolver::{resolve, DependencyKind, GraphNodeIndex};
use arclog::program::{OutputStep, PortName};
use arclog::types::GraphRelation;

/// The column names of each node of `text`, in node order.
fn names(text: &str) -> Vec<Vec<String>> {
    let read = read_arclog(text, SourceFile::Arclog).expect("the program reads");
    assert!(read.diagnostics.is_empty(), "{:?}", read.diagnostics);
    let (program, _) = read.value;
    let resolved = resolve(&program, None, &Default::default(), Registry::get());
    assert!(resolved.diagnostics.is_empty(), "{:?}", resolved.diagnostics);
    let program = resolved.value;
    (0..program.graph.nodes.len() as u32).filter_map(|node| program.column_names(GraphNodeIndex(node))).collect()
}

fn has_key_column(names: &[Vec<String>]) -> bool {
    names.iter().any(|columns| columns.iter().any(|name| name == "key" || name.starts_with("key.")))
}

const UNFOLD: &str = "(DET &seed RarestColor)\n\
    (RULE &seed_cell (input *P *Col) (&seed (:C Col)))\n\
    (INIT &state Unfold\n\
      (start ((:t P)) (&seed_cell *P))\n\
      (initial_untaken ((:item P)) (input *P) (NOT (&seed_cell P)))\n\
      (score ((:t P) (:item X) (:S K))\n\
        (&seed_cell *P) (input (:P *X)) (NOT (&seed_cell (:P X))) (= *K 0)))\n\
    (RULE &taken (&state.take (:item *P)))\n";

const DEMONSTRATED: &str = "(RULE &stage (input *P *Col))\n\
    (DEMONSTRATED &catalog\n\
      (value ((:o P) (:v Col))\n\
        (&stage *P *Col))\n\
      (demonstration ((:o P) (:o2 P2))\n\
        (&stage *P *Col)\n\
        (&stage *P2 Col))\n\
      (DEMO_RULE $Same\n\
        (RULE &local (&stage *P *Col))\n\
        (RULE &prediction (&local *P *Col))))\n";

#[test]
fn a_demonstrated_form_with_no_key_clause_has_no_key_column() {
    let names = names(DEMONSTRATED);
    assert!(names.contains(&vec!["P".to_owned(), "Col".to_owned()]), "{names:?}");
    assert!(!has_key_column(&names), "{names:?}");
}

#[test]
fn an_init_instance_with_no_key_clause_has_no_key_column() {
    let solver = read_solver("tied", UNFOLD, "(param &seed Color (2))\n", &|_| None).expect("the files read").value;
    let registry = Registry::get();
    let resolved = resolve(&solver.concept_case().program, None, &solver.derived_relations(), registry).value;
    let clauses = SolverClauses::of(&solver, registry);
    let checked = check_program(resolved, &clauses, registry, &mut CheckCache::default()).expect("the program checks");
    let take: Arc<[OutputStep]> = Arc::from([OutputStep::Port(PortName("take".into()))]);
    let outputs: Vec<usize> = checked
        .program
        .graph
        .nodes
        .iter()
        .enumerate()
        .filter(|(_, node)| matches!(node.kind, DependencyKind::RecursiveInstance(_)))
        .filter_map(|(node, _)| checked.types.columns(&GraphRelation { node: GraphNodeIndex(node as u32), output: Some(take.clone()) }))
        .map(|columns| columns.len())
        .collect();
    assert_eq!(outputs, [2]);
}

#[test]
fn a_rigid_det_form_with_no_key_clause_has_no_key_column() {
    let arclog = "(DET &member (ex_input *E *P (:Col *Id)))\n(RIGID_DET &piece\n  (&member *E *Id *P))\n";
    let solver = read_solver("rigid", arclog, "", &|_| None).expect("the files read").value;
    let registry = Registry::get();
    let resolved = resolve(&solver.concept_case().program, None, &solver.derived_relations(), registry).value;
    let clauses = SolverClauses::of(&solver, registry);
    let checked = check_program(resolved, &clauses, registry, &mut CheckCache::default()).expect("the program checks");
    let pose: Arc<[OutputStep]> = Arc::from([OutputStep::Pose]);
    let outputs: Vec<usize> = checked
        .program
        .graph
        .nodes
        .iter()
        .enumerate()
        .filter(|(_, node)| matches!(node.kind, DependencyKind::RigidAssembly(_)))
        .filter_map(|(node, _)| checked.types.columns(&GraphRelation { node: GraphNodeIndex(node as u32), output: Some(pose.clone()) }))
        .map(|columns| columns.len())
        .collect();
    assert_eq!(outputs, [1], "the Pose output of a form with no instance clause and no key clause has the Pose column alone");
}
