//! The labels of an `INIT` form and of a read of an instance's input port
//! take the types that the program gives them: a field of the first
//! projection onto a type parameter that only `(= *X 0)` makes, a label
//! that a constraint makes equal to a key label, and a read of an input
//! port that the instance writes no clause for.

use std::sync::Arc;

use arclog::check::{check_shared_program, CheckCache, SolverClauses};
use arclog::program::path::{NodePath, PathStep};
use arclog::program::Form;
use arclog::read::read_solver;
use arclog::registry::Registry;
use arclog::resolver::resolve_cases;
use arclog::types::ValueType;

/// The types of the labels of the scope of each top-level form of the
/// solver's one case program that `keep` selects, in the order of the forms.
fn scope_types(arclog: &str, keep: &dyn Fn(&Form) -> bool) -> Vec<Vec<ValueType>> {
    let solver = read_solver("instance", arclog, "", &|_| None).expect("the file reads").value;
    let registry = Registry::get();
    let cases = resolve_cases(&solver, registry);
    let clauses = SolverClauses::of_cases(&cases);
    let mut cache = CheckCache::default();
    let mut found = Vec::new();
    for resolved in cases.cases() {
        let program = Arc::clone(&resolved.resolved.value);
        let checked = check_shared_program(program, &clauses, registry, &mut cache).expect("every check passes");
        for (form, index) in checked.program.program.value().forms.iter().zip(0u32..) {
            if keep(form) {
                let types = checked.types.form(&NodePath(Box::new([PathStep(index)]))).expect("the form is a label scope");
                found.push(types.labels().map(|(_, ty)| ty.clone()).collect());
            }
        }
    }
    found
}

const FIELD_ARCLOG: &str = "
(RULE &halt (input (:P *Delta)) (input (:P *Delta2)))

(INIT &journey Propagation
  (source ((:n N))
    (= *N 0))
  (edge ((:a Delta) (:b Delta2))
    (&halt *Delta *Delta2)))
";

#[test]
fn a_zero_made_label_of_a_first_projection_takes_the_type_of_the_later_sites() {
    let types = scope_types(FIELD_ARCLOG, &|form| matches!(form, Form::Instance(_)));
    assert_eq!(types, vec![vec![ValueType::Box; 3]]);
}

const KEY_ARCLOG: &str = "
(RULE &ink (input *P *Col))

(RULE &bg (input *P (:Col *C)))

(RULE &hole (input *P (:Col *C)))

(RULE &wall (input *P (:Col *C)))

(INIT &window Occurrences
  (key ((&ink (:Col ^Col)))
    (shape ((:P S) (:v V))
      (OR ((&hole (:P *S))
           (&bg (:C *V)))
          ((&wall (:P S))
           (= V Col)))))
  (cell (P (:v V))
    (input *P (:Col *V))))
";

#[test]
fn a_label_equal_to_a_key_label_takes_the_type_of_the_key_clause() {
    let types = scope_types(KEY_ARCLOG, &|form| matches!(form, Form::Instance(_)));
    assert_eq!(types[0].len(), 5, "{types:?}");
}

const PORT_ARCLOG: &str = "
(RULE &passable (input *P (:Col *C)))

(RULE &seed (input *P (:Col *C)))

(INIT &flood4 Flood
  (node (P) (&passable *P))
  (source (P) (&seed *P)))

(RULE &walk_step
  (&flood4.step (:Delta *V)))
";

#[test]
fn a_read_of_an_input_port_with_no_clause_takes_the_port_types() {
    let types = scope_types(PORT_ARCLOG, &|form| matches!(form, Form::Clause(clause) if clause.value().columns.len() == 1));
    assert_eq!(types.last(), Some(&vec![ValueType::Box]));
}
