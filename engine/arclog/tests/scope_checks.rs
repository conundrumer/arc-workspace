//! The type check of a top-level form refuses a label fault in each label
//! scope within the form, and the check cache serves two forms of equal
//! content the same types only where the clauses that type a head label
//! that only `(= *X 0)` gives a type are equal.

use arclog::check::{check_program, CheckCache, CheckId, CheckedProgram, SolverClauses};
use arclog::diagnostic::{Diagnostic, DiagnosticKind, Location};
use arclog::program::path::{NodePath, PathStep};
use arclog::program::{Conjunct, Form};
use arclog::read::read_solver;
use arclog::registry::Registry;
use arclog::resolver::resolve;
use arclog::types::ValueType;

/// The check of the concept case of the arclog file `arclog`, through
/// `cache`.
fn check(arclog: &str, cache: &mut CheckCache) -> Result<CheckedProgram, Vec<Diagnostic>> {
    let solver = read_solver("scopes", arclog, "", &|_| None).expect("the file reads").value;
    let registry = Registry::get();
    let program = resolve(&solver.concept_case().program, None, &solver.derived_relations(), registry).value;
    let clauses = SolverClauses::of(&solver, registry);
    check_program(program, &clauses, registry, cache)
}

fn path(steps: &[u32]) -> NodePath {
    NodePath(steps.iter().map(|step| PathStep(*step)).collect())
}

/// A program whose first clause is one of `&way` whose head label only
/// `(= *X 0)` gives a type, and whose other clause of `&way` is `other`.
fn zero_typed_clause(other: &str) -> String {
    format!(
        "
(RULE &way (= *D 0))

(RULE &way {other})

(RULE &output
  (input *P *Col)
  (&way *D))
"
    )
}

/// The type of the head label of the first clause of `checked`.
fn first_head_type(checked: &CheckedProgram) -> Option<ValueType> {
    let Form::Clause(clause) = &checked.program.program.value().forms[0] else { panic!("the first form is a clause") };
    let [Conjunct::Constraint(constraint)] = &clause.value().body.value().conjuncts[..] else { panic!("the clause's body is one constraint") };
    let types = checked.types.form(&path(&[0])).expect("the clause is a label scope");
    types.label(constraint.first.label).cloned()
}

#[test]
fn a_clause_of_equal_content_takes_the_types_of_its_own_relation_s_clauses() {
    let mut cache = CheckCache::default();
    let colors = check(&zero_typed_clause("(input (:Col *D))"), &mut cache).expect("every check passes");
    let dirs = check(&zero_typed_clause("(dir_elem *D)"), &mut cache).expect("every check passes");
    assert_eq!((first_head_type(&colors), first_head_type(&dirs)), (Some(ValueType::Color), Some(ValueType::Dir)));
}

#[test]
fn a_label_of_a_clause_with_two_types_with_no_join_is_refused() {
    let refused = check(
        "
(RULE &stage
  (input *P *Col)
  (input (:P Col)))
",
        &mut CheckCache::default(),
    )
    .expect_err("the type check refuses the label");
    let at: Vec<&Location> = refused.iter().filter(|found| found.kind == DiagnosticKind::Check(CheckId::Types)).map(|found| &found.location).collect();
    assert_eq!(at, vec![&Location::Path(path(&[0, 0, 0, 1, 0]))]);
}
