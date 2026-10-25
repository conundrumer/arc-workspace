//! The checks refuse a body atom that reads a proposer, and a label that is
//! no Pose at a `(pose-or <type>)` column whose type meets the label's
//! type in nothing; a box relation gives no row at a bound orientation
//! value outside its column's type.

use arclog::check::{check_program, CheckCache};
use arclog::read::read_solver;
use arclog::registry::Registry;
use arclog::resolver::resolve;

/// The refusals of the checks of the concept case of the arclog file `arclog`.
fn refusals(arclog: &str) -> String {
    let solver = read_solver("refused", arclog, "", &|_| None).expect("the file reads").value;
    let registry = Registry::get();
    let program = resolve(&solver.concept_case().program, None, &solver.derived_relations(), registry).value;
    let clauses = arclog::check::SolverClauses::of(&solver, registry);
    check_program(program, &clauses, registry, &mut CheckCache::default()).err().map(|found| format!("{found:?}")).unwrap_or_default()
}

#[test]
fn a_rule_body_that_reads_a_proposer_is_refused() {
    assert!(refusals("(RULE &output (input *P *Col) (SepThickness (:G *N)))").contains("a body atom reads a lib relation"));
}

#[test]
fn a_dir8_label_at_a_d4_elem_column_is_refused() {
    let found = refusals("(RULE &output (input *P *Col) (d4_elem *D) (corner_dist P (:Diag D) (:K *K)))"); assert!(found.contains("meets no type"), "{found}");
}

#[test]
fn a_bound_value_outside_the_columns_type_gives_no_row() {
    use arclog::algebra::geometry::Geometry;
    use arclog::types::ValueType;
    let geometry = Geometry::get();
    let dir = geometry.domain(&ValueType::Dir)[0];
    let diag = geometry.domain(&ValueType::DiagDir)[0];
    assert_eq!(geometry.each(Some(dir), &ValueType::DiagDir).count(), 0);
    assert_eq!(geometry.each(Some(diag), &ValueType::DiagDir).collect::<Vec<_>>(), vec![diag]);
    assert_eq!(geometry.each(None, &ValueType::DiagDir).count(), geometry.domain(&ValueType::DiagDir).len());
}
