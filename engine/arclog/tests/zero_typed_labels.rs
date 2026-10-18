//! A label that only `(= *X 0)` gives a type takes, in each case of a
//! solver, the join of the types that the relation's other clauses give its
//! column, each clause typed in the case program it stands in.

use arclog::check::{check_program, CheckCache, SolverClauses};
use arclog::program::path::{NodePath, PathStep};
use arclog::program::{Conjunct, Form, Operand};
use arclog::read::read_solver;
use arclog::registry::Registry;
use arclog::resolver::{resolve, ConceptReads};
use arclog::solver::Exclusion;
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
fn a_zero_typed_label_takes_the_join_of_the_clauses_of_each_case() {
    let solver = read_solver("zero", ARCLOG, "", &|_| None).expect("the file reads").value;
    let registry = Registry::get();
    let derived = solver.derived_relations();
    let clauses = SolverClauses::of(&solver, registry);
    let mut cache = CheckCache::default();
    let concept_case = solver.concept_case();
    let concept = resolve(&concept_case.program, None, &derived, registry).value;
    let mut zero_types = Vec::new();
    for case in solver.cases(Exclusion::WithExcluded) {
        let reads = (case.name != concept_case.name).then(|| ConceptReads { concept: &concept, determinations: case.concept_determinations() });
        let program = resolve(&case.program, reads, &derived, registry).value;
        let checked = check_program(program, &clauses, registry, &mut cache).expect("every check passes");
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
    assert_eq!(zero_types, vec![Some(ValueType::Dir8), Some(ValueType::Dir8)]);
}
