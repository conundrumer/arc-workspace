//! An `INIT` instance keyed on a label that reads a column which only
//! `(= *S 0)` types in the case program, the clause that types the column
//! standing in another case, gets the column types of its outputs.

use std::sync::Arc;

use arclog::check::{check_shared_program, CheckCache, SolverClauses};
use arclog::read::read_solver;
use arclog::registry::Registry;
use arclog::resolver::{resolve_cases, DependencyKind, GraphNodeIndex};
use arclog::types::GraphRelation;

const ARCLOG: &str = "
(RULE &mid (&scope *P *S))

(INIT &window Occurrences
  (key ((&mid (:S ^S)))
    (shape ((:P Q) (:v V))
      (&mid (:P *Q))
      (= *V S)))
  (cell (P (:v V))
    (input *P (:Col *V))))

(ALTS $scope \"what &scope holds\" $Still
  (ALT $Still
    (RULE &scope (input *P) (= *S 0)))
  (ALT $Colored
    (RULE &scope (input *P (:Col *S)))))
";

#[test]
fn every_output_of_an_instance_keyed_on_a_zero_typed_column_has_column_types() {
    let solver = read_solver("zero", ARCLOG, "", &|_| None).expect("the file reads").value;
    let registry = Registry::get();
    let cases = resolve_cases(&solver, registry);
    let clauses = SolverClauses::of_cases(&cases);
    let mut cache = CheckCache::default();
    let mut outputs = Vec::new();
    for resolved in cases.cases() {
        let program = Arc::clone(&resolved.resolved.value);
        let checked = check_shared_program(program, &clauses, registry, &mut cache).expect("every check passes");
        let nodes = checked.program.graph.nodes.iter().enumerate();
        for (node, _) in nodes.filter(|(_, node)| matches!(node.kind, DependencyKind::InstanceOutput { .. })) {
            outputs.push(checked.types.columns(&GraphRelation { node: GraphNodeIndex(node as u32), output: None }).is_some());
        }
    }
    assert!(!outputs.is_empty());
    assert!(outputs.iter().all(|typed| *typed), "{outputs:?}");
}
