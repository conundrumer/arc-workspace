//! The safety check refuses a negated atom at which no mode of its relation
//! holds, once the atom closes.

use arclog::check::prefix::{check_prefix, prefixes};
use arclog::check::{CheckId, PrefixResult, SolverClauses};
use arclog::program::path::{NodePath, PathStep};
use arclog::program::{Node, Program};
use arclog::read::read_solver;
use arclog::registry::Registry;
use arclog::resolver::{resolve, resolve_cases};

/// The end of the first prefix of the last form of `arclog` that `check`
/// refuses, with the paths of its refusals.
fn first_refused(arclog: &str, check: CheckId) -> Option<(NodePath, Vec<NodePath>)> {
    let solver = read_solver("prefix", arclog, "", &|_| None).expect("the file reads").value;
    let registry = Registry::get();
    let cases = resolve_cases(&solver, registry);
    let clauses = SolverClauses::of_cases(&cases);
    let scope = solver.derived_relations();
    let forms = cases.concept().resolved.value.program.value().forms.clone();
    let (last, complete) = forms.split_last().expect("the file holds a form");
    for prefix in prefixes(last) {
        let held: Vec<_> = complete.iter().cloned().chain([prefix.partial.clone()]).collect();
        let program = resolve(&Node::new(Program { forms: held.into() }), None, &scope, registry).value;
        for (id, result) in check_prefix(&program, &clauses, registry, prefix.open().as_ref()) {
            if let (true, PrefixResult::Refuse(refusals)) = (id == check, result) {
                return Some((prefix.end, refusals.iter().map(|refusal| refusal.at.clone()).collect()));
            }
        }
    }
    None
}

fn path(steps: &[u32]) -> NodePath {
    NodePath(steps.iter().map(|step| PathStep(*step)).collect())
}

#[test]
fn a_negated_atom_without_a_mode_input_is_refused_once_the_atom_closes() {
    let found = first_refused("(RULE &x (input *P (:Col *C)) (NOT (inside (:A 0))))", CheckId::Safety);
    assert_eq!(found, Some((path(&[0, 1]), vec![path(&[0, 1])])));
}

#[test]
fn a_prefix_inside_a_negated_atom_is_not_refused() {
    // The refusal stands at the conjunct, so no prefix that ends at a site of the atom is refused.
    let found = first_refused("(RULE &x (input *P (:Col *C)) (NOT (inside (:A 0))))", CheckId::Safety);
    let (end, _) = found.expect("the negated atom is refused");
    assert_eq!(end.0.len(), 2, "refused at a site of the atom: {end:?}");
}
