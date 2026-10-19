//! A label that only `(= *X 0)` gives a type takes, in each case of a
//! solver, the join of the types that the relation's other clauses in that
//! case give its column, each clause typed in the case program it stands
//! in.

use std::sync::Arc;

use arclog::check::{check_shared_program, CheckCache, SolverClauses};
use arclog::program::path::{NodePath, PathStep};
use arclog::program::{Conjunct, Form, Operand};
use arclog::read::read_solver;
use arclog::registry::Registry;
use arclog::resolver::resolve_cases;
use arclog::types::ValueType;

const ARCLOG: &str = "
(RULE &dirs (dir_elem *D))

(RULE &way (&dirs *D))

(RULE &way (= *D 0))

(RULE &output
  (input *P *Col)
  (&way *D))

(ALTS $ways \"which directions &way holds\" $Straight
  (ALT $Diagonal
    (RULE &diags (diag_dir_elem *D))

    (RULE &way (&diags *D))

    (RULE &way (= *D 0))))
";

#[test]
fn a_zero_typed_label_takes_the_join_of_the_clauses_of_its_own_case() {
    let solver = read_solver("zero", ARCLOG, "", &|_| None).expect("the file reads").value;
    let registry = Registry::get();
    let cases = resolve_cases(&solver, registry);
    let clauses = SolverClauses::of_cases(&cases);
    let mut cache = CheckCache::default();
    let mut zero_types = Vec::new();
    for resolved in cases.cases() {
        let program = Arc::clone(&resolved.resolved.value);
        let checked = check_shared_program(program, &clauses, registry, &mut cache).expect("every check passes");
        let forms = checked.program.program.value().forms.iter().zip(0u32..);
        for (form, index) in forms {
            let Form::Clause(clause) = form else { continue };
            let clause = clause.value();
            let [Conjunct::Constraint(constraint)] = &clause.body.value().conjuncts[..] else { continue };
            if !matches!(constraint.second, Operand::Zero) {
                continue;
            }
            let types = checked.types.form(&NodePath(Box::new([PathStep(index)]))).expect("the clause is a label scope");
            zero_types.push(types.label(constraint.first.label).cloned());
        }
    }
    assert_eq!(zero_types, vec![Some(ValueType::Dir), Some(ValueType::DiagDir)]);
}
