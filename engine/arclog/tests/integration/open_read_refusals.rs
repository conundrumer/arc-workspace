//! The pooled and lifted reads check refuses a read whose atom is open
//! where no later token undoes the refusal: at the token that opens a fact
//! atom the form's side does not let it read, and at the column token of a
//! site on an Example column of a per-input read. A refusal that rests on a
//! form's per-input side stands at a prefix only where no later token can
//! make the form task-wide.

use arclog::check::prefix::{check_prefix, prefixes};
use arclog::check::{CheckId, PrefixResult, SolverClauses};
use arclog::program::path::{NodePath, PathStep};
use arclog::program::{Node, Program};
use arclog::read::read_solver;
use arclog::registry::Registry;
use arclog::resolver::{resolve, resolve_cases};

/// The end of the first prefix of the last form of `arclog` that the pooled
/// and lifted reads check refuses, with the paths of its refusals.
fn first_refused(arclog: &str) -> Option<(NodePath, Vec<NodePath>)> {
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
            if let (CheckId::PooledAndLiftedReads, PrefixResult::Refuse(refusals)) = (id, result) {
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
fn a_per_input_read_of_ex_input_is_refused_at_the_first_site_of_its_open_atom() {
    let found = first_refused("(RULE &x (ex_input *E *P (:Col *C)))");
    assert_eq!(found, Some((path(&[0, 0, 0, 0]), vec![path(&[0, 0])])));
}

#[test]
fn a_per_input_site_on_an_example_column_is_refused_at_the_site() {
    let found = first_refused("(DET &cells (ex_input *E *P *Col))\n(RULE &output (input (:P *Q)) (&cells (:E *X)))");
    assert_eq!(found, Some((path(&[0, 1, 0, 0]), vec![path(&[0, 1, 0])])));
}

#[test]
fn a_task_wide_read_of_ex_input_is_admitted() {
    assert_eq!(first_refused("(DET &cells (ex_input *E *P *Col))"), None);
}

#[test]
fn a_per_input_read_of_input_is_admitted() {
    assert_eq!(first_refused("(RULE &x (input *P (:Col *C)))"), None);
}

/// A task-wide relation with an Example column, and a per-input relation.
const RELATIONS: &str = "(DET &cells (ex_input *E *P *Col))\n(RULE &marks (input *P *Col))\n";

#[test]
fn a_read_at_an_example_column_is_admitted_while_a_later_site_on_e_can_make_the_init_task_wide() {
    let arclog = format!("{RELATIONS}(INIT &obj Connectivity\n  (node (P)\n    (&cells (:E *X) *P *Col)\n    (&marks P Col (:E X))))");
    assert_eq!(first_refused(&arclog), None);
}

#[test]
fn a_read_at_an_example_column_is_refused_once_the_init_is_complete_and_per_input() {
    let arclog = format!("{RELATIONS}(INIT &obj Connectivity\n  (node (P)\n    (&cells (:E *X) *P *Col)\n    (&marks P Col)))");
    let found = first_refused(&arclog);
    assert_eq!(found.map(|(end, _)| end), Some(path(&[])));
}

#[test]
fn a_read_in_the_first_branch_of_a_key_is_admitted_while_the_second_branch_can_make_the_init_task_wide() {
    let arclog = format!(
        "{RELATIONS}(INIT &obj Connectivity\n  (key ((OR ((&cells (:E ^Ky) *P *Col)) ((&marks P Col (:E Ky)))))\n    (node (P)\n      (&marks *P *Col))))"
    );
    assert_eq!(first_refused(&arclog), None);
}
