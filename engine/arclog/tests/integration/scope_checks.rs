//! The type check of a top-level form refuses a label fault in each label
//! scope within the form, and the check cache serves two forms of equal
//! content the same types only where the clauses that type a head label
//! that only `(= *X 0)` gives a type are equal.

use arclog::check::{check_program, CheckCache, CheckId, CheckedProgram, SolverClauses};
use arclog::diagnostic::{Diagnostic, DiagnosticKind, Location};
use arclog::program::path::{NodePath, PathStep};
use arclog::program::{Atom, Body, Clause, Conjunct, DeclaredName, Form, Node, Program, RelationName, RelationRef};
use arclog::read::read_solver;
use arclog::registry::Registry;
use arclog::resolver::resolve;
use arclog::types::ValueType;
use std::sync::Arc;

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

(DET &counts NumberDomain)
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
    let boxes = check(&zero_typed_clause("(input (:P *D))"), &mut cache).expect("every check passes");
    let numbers = check(&zero_typed_clause("(&counts (:N *D))"), &mut cache).expect("every check passes");
    assert_eq!((first_head_type(&boxes), first_head_type(&numbers)), (Some(ValueType::Position), Some(ValueType::Number)));
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

#[test]
fn a_read_of_an_undeclared_slot_gives_a_scope_diagnostic_that_names_the_slot() {
    let solver = read_solver("scopes", "(RULE &output\n  (input *P *Col)\n  (&gone *P))\n", "", &|_| None).expect("the file reads").value;
    let read = &solver.concept_case().program;
    let Form::Clause(clause) = &read.value().forms[0] else { panic!("the first form is a clause") };
    let mut conjuncts = clause.value().body.value().conjuncts.to_vec();
    let Conjunct::Atom(atom) = &conjuncts[1] else { panic!("the second conjunct is an atom") };
    let slot = Atom { relation: RelationRef::Declared(RelationName(DeclaredName::Slot(7))), sites: atom.value().sites.clone() };
    conjuncts[1] = Conjunct::Atom(Node::new(slot));
    let body = Node::new(Body { conjuncts: conjuncts.into() });
    let program = Node::new(Program { forms: Arc::new([Form::Clause(Node::new(Clause { body, ..clause.value().clone() }))]) });
    let resolved = resolve(&program, None, &solver.derived_relations(), Registry::get());
    let scope: Vec<_> = resolved.diagnostics.iter().filter(|d| d.kind == DiagnosticKind::Check(CheckId::Scope)).collect();
    assert_eq!(scope.len(), 1, "{:?}", resolved.diagnostics);
    assert!(scope[0].message.contains("slot 7"), "{}", scope[0].message);
}

#[test]
fn a_second_init_of_one_name_in_one_scope_gives_a_scope_diagnostic_and_no_panic() {
    let solver = read_solver("scopes", "(INIT &state Unfold)\n\n(INIT &state Unfold\n  (start ((:t P))\n    (input *P)))\n", "", &|_| None).expect("the file reads").value;
    let resolved = resolve(&solver.concept_case().program, None, &solver.derived_relations(), Registry::get());
    let scope: Vec<_> = resolved.diagnostics.iter().filter(|d| d.kind == DiagnosticKind::Check(CheckId::Scope)).collect();
    assert_eq!(scope.len(), 1, "{:?}", resolved.diagnostics);
    assert_eq!(scope[0].location, Location::Path(path(&[1])));
    assert!(scope[0].message.contains("state"), "{}", scope[0].message);
}
