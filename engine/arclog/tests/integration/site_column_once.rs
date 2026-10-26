//! An atom with two sites on one column is refused by the checks, and by the
//! prefix form at the second site.

use arclog::check::prefix::{check_prefix, prefixes};
use arclog::check::{check_program, CheckCache, CheckId, PrefixResult, SolverClauses};
use arclog::program::path::{NodePath, PathStep};
use arclog::program::{Node, Program};
use arclog::read::read_solver;
use arclog::registry::Registry;
use arclog::resolver::{resolve, resolve_cases};

const TWICE: &str = "(RULE &x (input *P (:Col *C)) (dir_elem *D) (edge_outset (:D D) (:K 0) (:K *K) (:B *B)))";

#[test]
fn the_checks_refuse_a_rule_body_atom_with_two_sites_on_one_column() {
    let solver = read_solver("once", TWICE, "", &|_| None).expect("the file reads").value;
    let registry = Registry::get();
    let program = resolve(&solver.concept_case().program, None, &solver.derived_relations(), registry).value;
    let clauses = SolverClauses::of(&solver, registry);
    let found = check_program(program, &clauses, registry, &mut CheckCache::default()).err().map(|found| format!("{found:?}"));
    let found = found.expect("the checks refuse");
    assert!(found.contains("the atom has a site on the column of this site already"), "{found}");
}

#[test]
fn the_prefix_form_refuses_at_the_second_site_of_the_column() {
    let solver = read_solver("once", TWICE, "", &|_| None).expect("the file reads").value;
    let registry = Registry::get();
    let cases = resolve_cases(&solver, registry);
    let clauses = SolverClauses::of_cases(&cases);
    let scope = solver.derived_relations();
    let forms = cases.concept().resolved.value.program.value().forms.clone();
    let (last, complete) = forms.split_last().expect("the file holds a form");
    let mut refused_at = None;
    for prefix in prefixes(last) {
        let held: Vec<_> = complete.iter().cloned().chain([prefix.partial.clone()]).collect();
        let program = resolve(&Node::new(Program { forms: held.into() }), None, &scope, registry).value;
        for (id, result) in check_prefix(&program, &clauses, registry, prefix.open().as_ref()) {
            if let (CheckId::SiteColumns, PrefixResult::Refuse(refusals)) = (id, result) {
                refused_at = refused_at.or(Some((prefix.end.clone(), refusals.iter().map(|refusal| refusal.at.clone()).collect::<Vec<_>>())));
            }
        }
    }
    let path = |steps: &[u32]| NodePath(steps.iter().map(|step| PathStep(*step)).collect());
    assert_eq!(refused_at, Some((path(&[0, 2, 2, 0]), vec![path(&[0, 2, 2])])));
}
