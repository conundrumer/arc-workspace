//! The checks refuse each site shape that the evaluator's `IrBuilder::site` takes as impossible.

use arclog::check::{check_program, CheckCache, SolverClauses};
use arclog::read::read_solver;
use arclog::registry::Registry;
use arclog::resolver::resolve;

const BBOX: &str = "(INIT &bbox BoundingBox (key ((input *P ^Col)) (cell (P) (input *P Col))))\n";

fn refusal_of(rule: &str) -> String {
    let text = format!("{BBOX}{rule}");
    let solver = read_solver("sites", &text, "", &|_| None).expect("the file reads").value;
    let registry = Registry::get();
    let program = resolve(&solver.concept_case().program, None, &solver.derived_relations(), registry).value;
    let clauses = SolverClauses::of(&solver, registry);
    let found = check_program(program, &clauses, registry, &mut CheckCache::default()).err().map(|found| format!("{found:?}"));
    found.expect("the checks refuse")
}

#[test]
fn a_bare_label_at_a_site_on_a_record_is_refused() {
    let found = refusal_of("(RULE &output (&bbox.box *key *B) (input *P *Col) (inside (:A P) B))");
    assert!(found.contains("column `key` of the relation `&bbox.box`") && found.contains("holds a bare label"), "{found}");
}

#[test]
fn zero_at_a_site_on_a_record_is_refused() {
    let found = refusal_of("(RULE &output (&bbox.box (:key 0) *B) (input *P *Col) (inside (:A P) B))");
    assert!(found.contains("column `key` of the relation `&bbox.box`") && found.contains("holds a bare label"), "{found}");
}

#[test]
fn a_field_site_at_a_site_on_one_column_is_refused() {
    let found = refusal_of("(RULE &output (&bbox.box (:key *Col) (:B (:Col *B))) (input *P Col))");
    assert!(found.contains("column `B` of the relation `&bbox.box`") && found.contains("holds a field site"), "{found}");
}

#[test]
fn a_field_site_on_other_than_one_label_is_refused() {
    let found = refusal_of("(RULE &output (&bbox.box (:key (:Col *Col *C2)) *B) (input *P Col))");
    assert!(found.contains("column `key` of the relation `&bbox.box`") && found.contains("not on one bare label"), "{found}");
}
