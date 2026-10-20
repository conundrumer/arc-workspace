//! The checks that the engine's lint takes from the Python lint refuse a
//! program that breaks them, at the line of the node that breaks it, and
//! each prefix form refuses a prefix at the node that breaks it.

use arclog::check::lint::lint;
use arclog::check::prefix::{check_prefix, prefixes};
use arclog::check::{CheckId, PrefixResult, SolverClauses};
use arclog::diagnostic::{DiagnosticKind, Location};
use arclog::program::path::{NodePath, PathStep};
use arclog::program::{Node, Program};
use arclog::read::read_solver;
use arclog::registry::Registry;
use arclog::resolver::{resolve, resolve_cases};

/// The lines of the errors of `check` that the lint finds in `arclog`.
fn refused_lines(arclog: &str, check: CheckId) -> Vec<u32> {
    let solver = read_solver("lint", arclog, "", &|_| None).expect("the file reads").value;
    let mut lines: Vec<u32> = lint(&solver, Registry::get())
        .into_iter()
        .filter(|diagnostic| diagnostic.kind == DiagnosticKind::Check(check))
        .flat_map(|diagnostic| match diagnostic.location {
            Location::Places(places) => places.iter().map(|at| at.place.line).collect::<Vec<_>>(),
            Location::Path(_) => panic!("the lint gives each error at its places"),
        })
        .collect();
    lines.sort();
    lines
}

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

const ZERO_COLUMN: &str = "(RULE &w (input *P (:Col *C))\n  (= *Z 0))";

#[test]
fn a_column_that_is_zero_in_every_clause_is_refused() {
    assert_eq!(refused_lines(ZERO_COLUMN, CheckId::EqualityAndZero), vec![2]);
    assert_eq!(first_refused(ZERO_COLUMN, CheckId::EqualityAndZero), Some((path(&[0, 1]), vec![path(&[0, 1])])));
}

const ZERO_ON_A_DIRECTION: &str = "(RULE &w (input *P (:Col *C))\n  (dir_elem (:D 0)))";

#[test]
fn a_zero_on_a_column_with_no_zero_is_refused() {
    assert_eq!(refused_lines(ZERO_ON_A_DIRECTION, CheckId::EqualityAndZero), vec![2]);
    assert_eq!(first_refused(ZERO_ON_A_DIRECTION, CheckId::EqualityAndZero), Some((path(&[0, 1, 0]), vec![path(&[0, 1, 0])])));
}

const SECOND_LABEL_MADE: &str = "(RULE &w (input *P (:Col *C))\n  (= C *D))";

#[test]
fn an_equality_that_makes_its_second_label_is_refused() {
    assert_eq!(refused_lines(SECOND_LABEL_MADE, CheckId::EqualityAndZero), vec![2]);
    assert_eq!(first_refused(SECOND_LABEL_MADE, CheckId::EqualityAndZero), Some((path(&[0, 1]), vec![path(&[0, 1])])));
}

const SITE_MADE_LABEL_EQUATED: &str = "(RULE &w (input *P (:Col *C)) (input *Q (:Col *D))\n  (= C D))";

#[test]
fn an_equality_on_a_label_a_site_of_its_list_makes_is_refused() {
    assert_eq!(refused_lines(SITE_MADE_LABEL_EQUATED, CheckId::EqualityAndZero), vec![2]);
    assert_eq!(first_refused(SITE_MADE_LABEL_EQUATED, CheckId::EqualityAndZero), Some((path(&[0, 2]), vec![path(&[0, 2])])));
}

const MADE_FROM_A_SITE_LABEL: &str = "(RULE &w (input *P (:Col *C))\n  (OR ((input P (:Col *D))\n       (= *E D))\n      ((input P (:Col E)))))";

#[test]
fn an_equality_that_makes_a_label_a_site_of_its_list_could_make_is_refused() {
    assert_eq!(refused_lines(MADE_FROM_A_SITE_LABEL, CheckId::EqualityAndZero), vec![3]);
    assert_eq!(first_refused(MADE_FROM_A_SITE_LABEL, CheckId::EqualityAndZero), Some((path(&[0, 1, 0, 1]), vec![path(&[0, 1, 0, 1])])));
}

const ORDER_MAKES: &str = "(RULE &w (input *P (:Col *C))\n  (< C *D))";

#[test]
fn a_constraint_other_than_equality_that_makes_a_label_is_refused() {
    assert_eq!(refused_lines(ORDER_MAKES, CheckId::ConstraintMarks), vec![2]);
    assert_eq!(first_refused(ORDER_MAKES, CheckId::ConstraintMarks), Some((path(&[0, 1]), vec![path(&[0, 1])])));
}

const TWO_CLAUSES: &str = "(RULE &w (input *P (:Col *C)))\n(RULE &w (input *Q (:Col *C)))";

#[test]
fn a_second_clause_of_a_relation_in_a_block_is_refused() {
    assert_eq!(refused_lines(TWO_CLAUSES, CheckId::OneClause), vec![2]);
    assert_eq!(first_refused(TWO_CLAUSES, CheckId::OneClause), Some((path(&[0, 0, 0, 0]), vec![path(&[])])));
}

const BROADCAST_INSIDE: &str = "(INIT &bbox BoundingBox\n  (key ((input *P ^Col))\n    (cell (P)\n      (input *P *C))))";

#[test]
fn a_keyed_input_that_reads_no_key_label_is_refused() {
    assert_eq!(refused_lines(BROADCAST_INSIDE, CheckId::InstanceSites), vec![3]);
    assert_eq!(first_refused(BROADCAST_INSIDE, CheckId::InstanceSites), Some((path(&[0, 1]), vec![path(&[0, 1])])));
}

const KEY_SITE: &str = "(INIT &a BoundingBox\n  (key ((input *P ^Col))\n    (cell (P)\n      (input *P Col))))\n\
(INIT &b BoundingBox\n  (key ((input *P ^Col))\n    (cell (P)\n      (&a.cell (:key Col) *P))))";

#[test]
fn a_key_site_at_the_key_in_scope_is_refused() {
    assert_eq!(refused_lines(KEY_SITE, CheckId::InstanceSites), vec![8]);
    assert_eq!(first_refused(KEY_SITE, CheckId::InstanceSites), Some((path(&[0, 1, 0, 0, 0]), vec![path(&[0, 1, 0, 0, 0])])));
}

#[test]
fn a_site_that_elides_is_refused() {
    assert_eq!(refused_lines("(RULE &w\n  (input *P (:Col *Col)))", CheckId::Spelling), vec![2]);
}

#[test]
fn a_label_made_again_in_its_scope_is_refused() {
    assert_eq!(refused_lines("(RULE &w (input *P (:Col *C))\n  (input *P (:Col C)))", CheckId::Spelling), vec![2]);
}

#[test]
fn a_label_made_under_the_name_of_another_label_of_the_body_is_refused() {
    let arclog = "(RULE &w (input *P (:Col *C))\n  (ALL ((input P (:Col *D))) ((input P (:Col C))))\n  (ALL ((input P (:Col *D))) ((input P (:Col C)))))";
    assert_eq!(refused_lines(arclog, CheckId::Spelling), vec![3]);
}

#[test]
fn a_field_name_that_is_not_pascal_case_is_refused() {
    let arclog = "(INIT &bbox BoundingBox\n  (key ((input *P ^Col))\n    (cell (P)\n      (input *P Col))))\n(RULE &w\n  (&bbox.cell (:key (:col *C)) *P))";
    assert_eq!(refused_lines(arclog, CheckId::Spelling), vec![6]);
}

#[test]
fn no_prefix_breaks_the_spelling() {
    assert_eq!(first_refused("(RULE &w (input *P (:Col *C))\n  (input *P (:Col C)))", CheckId::Spelling), None);
}
