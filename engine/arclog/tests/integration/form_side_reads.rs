//! The pooled and lifted reads check refuses a read of a form that is not
//! its node's first by the side of that form.

use arclog::check::{check_program, CheckCache, CheckId, SolverClauses};
use arclog::diagnostic::{DiagnosticKind, Location};
use arclog::program::path::{NodePath, PathStep};
use arclog::read::read_solver;
use arclog::registry::Registry;
use arclog::resolver::resolve;

#[test]
fn a_task_wide_clause_after_a_per_input_clause_of_its_relation_may_not_read_input() {
    let text = "(RULE &r (input *P *Col))\n(DET &r (input *P *Col))\n(RULE &output (input *P *Col) (&r *P *Col))\n";
    let solver = read_solver("form_side", text, "", &|_| None).expect("the file reads").value;
    let registry = Registry::get();
    let program = resolve(&solver.concept_case().program, None, &solver.derived_relations(), registry).value;
    let clauses = SolverClauses::of(&solver, registry);
    let refused = check_program(program, &clauses, registry, &mut CheckCache::default()).expect_err("a check refuses");
    let read = Location::Path(NodePath([1, 0, 0].map(PathStep).into()));
    assert!(refused.iter().any(|found| found.kind == DiagnosticKind::Check(CheckId::PooledAndLiftedReads) && found.location == read), "{refused:?}");
}
