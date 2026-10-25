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
fn a_key_site_at_the_key_in_scope_is_accepted() {
    assert_eq!(first_refused(KEY_SITE, CheckId::InstanceSites), None);
}

#[test]
fn a_read_of_a_form_keyed_by_the_same_labels_with_no_key_site_is_a_broadcast() {
    let no_site = KEY_SITE.replace(" (:key Col)", "");
    assert_eq!(refused_lines(&no_site, CheckId::InstanceSites), vec![7]);
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

const MARK_ON_NO_COLUMN: &str = "(RULE &w (input *P (:Col *C))\n  (OR ((input P (:Col *D)))\n      ((input P (:Col C))))\n  (ONE D))";

#[test]
fn a_one_mark_on_a_label_that_is_no_column_is_refused() {
    assert_eq!(refused_lines(MARK_ON_NO_COLUMN, CheckId::Picks), vec![1]);
    assert_eq!(first_refused(MARK_ON_NO_COLUMN, CheckId::Picks), Some((path(&[]), vec![path(&[])])));
}

#[test]
fn a_set_mark_after_a_one_column_proposer_is_kept() {
    assert_eq!(refused_lines("(DET &c UnchangedColor (SET))", CheckId::Picks), Vec::<u32>::new());
}

#[test]
fn a_set_mark_after_a_type_domain_proposer_is_refused() {
    assert_eq!(refused_lines("(DET &c ColorDomain (SET))", CheckId::Picks), vec![1]);
}

#[test]
fn a_set_mark_after_a_two_column_proposer_is_refused() {
    assert_eq!(refused_lines("(DET &p ChangedPairs (SET))", CheckId::Picks), vec![1]);
}

const ONE_IN_A_BODY: &str = "(RULE &w (input *P (:Col *C))\n  (OR ((ONE P))\n      ((input P (:Col C)))))";

#[test]
fn a_one_inside_a_body_is_refused() {
    assert_eq!(refused_lines(ONE_IN_A_BODY, CheckId::Picks), vec![2]);
    assert_eq!(first_refused(ONE_IN_A_BODY, CheckId::Picks), Some((path(&[0, 1, 0, 0]), vec![path(&[0, 1, 0, 0])])));
}

const CHOOSE_WITH_NO_NEVER: &str = "(RULE &cell (input *P (:Col *C)))\n(CHOOSE &pick\n  (from (&cell *P *C)))";

#[test]
fn a_choose_with_no_never_is_refused_at_its_end() {
    assert_eq!(refused_lines(CHOOSE_WITH_NO_NEVER, CheckId::Picks), vec![2, 2]);
    assert_eq!(first_refused(CHOOSE_WITH_NO_NEVER, CheckId::Picks).map(|(end, _)| end), Some(path(&[])));
}

const NEVER_READS_ONCE: &str = "(RULE &cell (input *P (:Col *C)))\n(CHOOSE &pick\n  (from (&cell *P *C))\n  (never\n    (&cell *P *C)\n    (input P (:Col C))))";

#[test]
fn a_never_that_reads_the_candidate_once_is_refused_at_its_clause() {
    assert_eq!(refused_lines(NEVER_READS_ONCE, CheckId::Picks), vec![4]);
    assert_eq!(first_refused(NEVER_READS_ONCE, CheckId::Picks), Some((path(&[]), vec![path(&[1])])));
}

const ONE_MARKS_STATE_IT: &str = "(RULE &cell (input *P (:Col *C)))\n(CHOOSE &pick\n  (from (&cell *P *C))\n  (never\n    (&cell *P *C)\n    (&cell P (:C *C2))\n    (!= C C2)))";

#[test]
fn a_choose_that_one_marks_state_is_refused_at_its_end() {
    assert_eq!(refused_lines(ONE_MARKS_STATE_IT, CheckId::Picks), vec![2]);
    assert_eq!(first_refused(ONE_MARKS_STATE_IT, CheckId::Picks), Some((path(&[]), vec![path(&[])])));
}

const NO_SUCH_PART: &str = "(RULE &cell (input *P (:Col *C)))\n(RIGID_DET &m (&cell *P *C))\n(RULE &w\n  (&m.nope *P))";

#[test]
fn a_read_of_no_part_of_a_rigid_det_is_refused() {
    assert_eq!(refused_lines(NO_SUCH_PART, CheckId::RigidPartsAndProposers), vec![4]);
    assert_eq!(first_refused(NO_SUCH_PART, CheckId::RigidPartsAndProposers), Some((path(&[0, 0, 0, 0]), vec![path(&[0, 0])])));
}

const LOWERCASE_PROPOSER: &str = "(DET &d dirDomain)";

#[test]
fn a_proposer_name_that_is_not_pascal_case_is_refused() {
    assert_eq!(refused_lines(LOWERCASE_PROPOSER, CheckId::RigidPartsAndProposers), vec![1]);
    assert!(first_refused(LOWERCASE_PROPOSER, CheckId::RigidPartsAndProposers).is_some());
}
