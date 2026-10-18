//! The type check gives the labels of each label scope within a top-level
//! form their types, and `ProgramTypes::form` gives them at each scope's
//! path in the program. A constraint gives its two labels each other's
//! sites only in the list that holds it and in the lists nested in it.

use arclog::check::{check_program, CheckCache, CheckedProgram, SolverClauses};
use arclog::program::path::{NodePath, PathStep};
use arclog::program::{ColumnName, Form};
use arclog::read::read_solver;
use arclog::registry::Registry;
use arclog::resolver::resolve;
use arclog::types::ValueType;

/// The checked program of the concept case of the arclog file `arclog`.
fn checked(arclog: &str) -> CheckedProgram {
    let solver = read_solver("scopes", arclog, "", &|_| None).expect("the file reads").value;
    let registry = Registry::get();
    let program = resolve(&solver.concept_case().program, None, &solver.derived_relations(), registry).value;
    let clauses = SolverClauses::of(&solver, registry);
    check_program(program, &clauses, registry, &mut CheckCache::default()).expect("every check passes")
}

fn path(steps: &[u32]) -> NodePath {
    NodePath(steps.iter().map(|step| PathStep(*step)).collect())
}

const PROGRAM: &str = "
(INPUT stage \"the cells\"
  (RULE &stage (input *P *Col)))

(DEMONSTRATED &catalog
  (value ((:o P) (:v Col))
    (&stage *P *Col))
  (demonstration ((:o P) (:o2 P2))
    (&stage *P *Col)
    (&stage *P2 Col))
  (DEMO_RULE $Same
    (RULE &prediction (&stage (:Col *Col) (:P *P)))))
";

#[test]
fn a_label_of_one_id_in_the_key_scope_and_a_demo_rule_takes_the_type_of_each_scope() {
    let checked = checked(PROGRAM);
    let key = checked.types.form(&path(&[1])).expect("the key clause and inputs are a label scope");
    let rule = checked.types.form(&path(&[1, 2])).expect("the DEMO_RULE is a label scope");
    let shared: Vec<(&ValueType, &ValueType)> = rule.labels().filter_map(|(label, ty)| Some((key.label(label)?, ty))).collect();
    assert!(shared.contains(&(&ValueType::Box, &ValueType::Color)), "{shared:?}");
}

#[test]
fn an_equality_in_one_branch_gives_no_site_to_a_label_of_another_branch() {
    checked(
        "
(RULE &block_dir
  (OR ((corner_dir (:C *Diag) *D))
      ((diag_dir_elem (:D Diag))
       (= D Diag))))
",
    );
}

#[test]
fn a_label_equal_to_another_in_one_branch_takes_the_join_of_the_branches() {
    let checked = checked(
        "
(RULE &dir8
  (OR ((dir_elem *D) (= *M D))
      ((diag_dir_elem (:D M)))))
",
    );
    let Form::Clause(clause) = &checked.program.program.value().forms[0] else { panic!("the first form is a clause") };
    let column = clause.value().columns.iter().find(|column| column.name == ColumnName::Written("M".into())).expect("the clause has a column M");
    let types = checked.types.form(&path(&[0])).expect("the clause is a label scope");
    assert_eq!(types.label(column.label), Some(&ValueType::Dir8));
}
