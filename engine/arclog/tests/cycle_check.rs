//! The cycle check refuses a case program whose alts close a cycle of the
//! dependency graph, at each form on the cycle, and passes the case that
//! leaves it open.

use std::sync::Arc;

use arclog::check::{check_cycles, CheckResult};
use arclog::program::path::{NodePath, PathStep};
use arclog::read::read_solver;
use arclog::registry::Registry;
use arclog::resolver::{resolve, ConceptReads};
use arclog::solver::Exclusion;

const ARCLOG: &str = "
(RULE &a (input *P))

(RULE &b (&a *P))

(ALTS $loop \"whether &a reads &b\" $Open
  (ALT $Closed
    (RULE &a (&b *P))))
";

fn form(index: u32) -> NodePath {
    NodePath(Box::new([PathStep(index)]))
}

#[test]
fn a_cycle_is_refused_at_each_form_on_it() {
    let solver = read_solver("cycle", ARCLOG, "", &|_| None).expect("the files read").value;
    let registry = Registry::get();
    let derived = solver.derived_relations();
    let concept_case = solver.concept_case();
    let concept = Arc::new(resolve(&concept_case.program, None, &derived, registry).value);
    assert_eq!(check_cycles(&concept.graph, &concept), CheckResult::Pass);

    let case = solver.cases(Exclusion::WithExcluded).find(|case| case.name != concept_case.name).expect("the case of `$Closed`");
    let reads = ConceptReads { concept: &concept, determinations: case.concept_determinations() };
    let closed = resolve(&case.program, Some(reads), &derived, registry).value;
    let CheckResult::Refuse(refusals) = check_cycles(&closed.graph, &closed) else {
        panic!("the case of `$Closed` holds a cycle");
    };
    let mut at: Vec<NodePath> = refusals.iter().map(|refusal| refusal.at.clone()).collect();
    at.sort();
    assert_eq!(at, vec![form(0), form(1)]);
}
