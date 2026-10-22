//! Each check's prefix form refuses a prefix of a form at the first prefix
//! of [`prefixes`] that no completion passes, and at no prefix before it.

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
fn a_read_of_a_name_that_resolves_to_nothing_is_refused_once_the_atom_stands() {
    let found = first_refused("(RULE &x (&nothing *A) (input *P (:Col *C)))", CheckId::Scope);
    assert_eq!(found, Some((path(&[0, 0, 0, 0]), vec![path(&[0, 0])])));
}

#[test]
fn a_site_on_a_column_its_relation_lacks_is_refused_once_the_site_stands() {
    let found = first_refused("(RULE &x (input *P (:Nope *C)))", CheckId::SiteColumns);
    assert_eq!(found, Some((path(&[0, 0, 1, 0]), vec![path(&[0, 0, 1])])));
}

#[test]
fn an_empty_meet_is_refused_at_the_site_that_empties_it() {
    let found = first_refused("(RULE &x (input *P (:Col *C)) (dir_elem (:D C)))", CheckId::Types);
    assert_eq!(found, Some((path(&[0, 1, 0, 0]), vec![path(&[0, 0, 1, 0])])));
}

#[test]
fn an_order_on_a_color_is_refused_at_its_constraint() {
    let found = first_refused("(RULE &x (input *P (:Col *C)) (input *Q (:Col *E)) (< C E))", CheckId::Types);
    assert_eq!(found, Some((path(&[0, 2]), vec![path(&[0, 2]), path(&[0, 2])])));
}

#[test]
fn a_label_local_to_a_branch_and_read_outside_it_is_refused_once_the_body_is_complete() {
    let arclog = "(RULE &x (input *P (:Col *C)) (OR ((input P (:Col *D))) ((input P (:Col *E)))) (input *Q (:Col D)))";
    let found = first_refused(arclog, CheckId::MadeAndExportedLabels);
    assert_eq!(found, Some((path(&[0]), vec![path(&[0, 2, 1, 0])])));
}

#[test]
fn a_label_no_mode_binds_is_refused_at_its_site() {
    let found = first_refused("(RULE &x (input *P (:Col *C)) (compose *A *B *Q) (input Q (:Col C)))", CheckId::Safety);
    assert_eq!(found, Some((path(&[0, 1, 0, 0]), vec![path(&[0, 1, 0, 0])])));
}

#[test]
fn a_per_input_read_of_ex_input_is_refused_at_its_atom() {
    let found = first_refused("(RULE &x (ex_input *E *P (:Col *C)))", CheckId::PooledAndLiftedReads);
    assert_eq!(found, Some((path(&[0, 0]), vec![path(&[0, 0])])));
}

#[test]
fn an_input_its_component_does_not_declare_is_refused_at_the_input() {
    let found = first_refused("(DET &arr_dim ScaleRatio)\n(INIT &f Frame (nope (A) (axis_elem *A)))", CheckId::InstanceInputs);
    assert_eq!(found, Some((path(&[0]), vec![path(&[0])])));
}

#[test]
fn an_order_on_a_label_that_only_zero_types_is_refused_once_the_form_is_complete() {
    let found = first_refused("(RULE &w (dir_elem *D))\n(RULE &w (= *D 0) (< D D))", CheckId::Types);
    assert_eq!(found, Some((path(&[]), vec![path(&[0, 1]), path(&[0, 1])])));
}

#[test]
fn an_algebra_atom_that_leaves_out_an_input_no_mode_leaves_out_is_refused_once_the_atom_stands() {
    let arclog = "(RULE &x (input *P (:Col *C)) (dir_elem *D) (axis_inset D (:K1 C) (:B P)))";
    let found = first_refused(arclog, CheckId::Safety);
    assert_eq!(found, Some((path(&[0, 2]), vec![path(&[0, 2])])));
}
