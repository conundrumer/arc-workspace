//! The type check gives the labels of each label scope within a top-level
//! form their types, and `ProgramTypes::form` gives them at each scope's
//! path in the program. A constraint gives its two labels each other's
//! sites only in the list that holds it and in the lists nested in it. A
//! read of an instance's input port gives its labels the types of that
//! input's columns, and an `OR` gives a label that it makes the join of the
//! types of the branches that hold it. A branch that holds no label equal to
//! a label made outside the `OR` gives the join no type.

use arclog::check::{check_program, CheckCache, CheckedProgram, SolverClauses};
use arclog::program::path::{NodePath, PathStep};
use arclog::program::canonical::{CanonicalOrder, SearchBudget};
use arclog::program::{ColumnName, Form, LabelId};
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

/// The labels of each label scope of the top-level form `form` of `checked`
/// that the checked program gives no type.
fn untyped_labels(checked: &CheckedProgram, form: u32) -> Vec<LabelId> {
    let top = &checked.program.program.value().forms[form as usize];
    let order = CanonicalOrder::of(top, &mut SearchBudget::new());
    let mut untyped = Vec::new();
    for (scope, labels) in order.label_scopes() {
        let at = path(&[form]).join(&scope);
        let types = checked.types.form(&at);
        untyped.extend(labels.iter().map(|(label, _)| *label).filter(|label| types.and_then(|types| types.label(*label)).is_none()));
    }
    untyped
}

#[test]
fn a_read_of_an_instance_input_gives_its_labels_the_input_column_types() {
    let checked = checked(
        "
(INIT &order Order
  (member ((:t D))
    (dir_elem *D)))
(RULE &read
  (&order.member (:t *D)))
",
    );
    let Form::Clause(clause) = &checked.program.program.value().forms[1] else { panic!("the second form is a clause") };
    let column = clause.value().columns.iter().find(|column| column.name == ColumnName::Written("D".into())).expect("the clause has a column D");
    let types = checked.types.form(&path(&[1])).expect("the clause is a label scope");
    assert_eq!(types.label(column.label), Some(&ValueType::Dir));
}

#[test]
fn a_label_that_one_branch_of_an_or_does_not_hold_takes_the_join_of_the_branches_that_hold_it() {
    let checked = checked(
        "
(RULE &diags
  (diag_dir_elem (:D *C))
  (OR ((dir_elem *D) (corner_dir C (:D D)))
      ((corner_dir C (:D D)))
      ((corner_dir C *A))))
",
    );
    assert_eq!(untyped_labels(&checked, 0), Vec::<LabelId>::new());
}

#[test]
fn a_label_made_outside_an_or_keeps_its_type_when_one_branch_holds_no_label_equal_to_it() {
    let checked = checked(
        "
(RULE &placed
  (d4_elem (:D *D))
  (OR ((c4_elem (:D D)))
      ((dir_elem (:D *X)))))
",
    );
    let Form::Clause(clause) = &checked.program.program.value().forms[0] else { panic!("the first form is a clause") };
    let column = clause.value().columns.iter().find(|column| column.name == ColumnName::Written("D".into())).expect("the clause has a column D");
    let types = checked.types.form(&path(&[0])).expect("the clause is a label scope");
    assert_eq!(types.label(column.label), Some(&ValueType::D4));
}

#[test]
fn an_unfold_key_that_reads_an_order_input_in_one_branch_types_each_label() {
    let checked = checked(
        "
(RULE &corners
  (diag_dir_elem (:D *C)))
(INIT &order Order
  (key ((&corners ^C)))
  (member ((:t D))
    (dir_elem *D)))
(INIT &walk Unfold
  (key ((OR ((&order.minimal (:key ^C) (:t *D)))
            ((&order.member (:key C) (:t D)))
            ((&corners C))))
    (start ((:t D))
      (&order.minimal (:t *D)))
    (initial_untaken ((:item D))
      (&order.member (:t *D)))
    (step ((:t D) (:t2 D2))
      (&order.successor (:a *D) (:b *D2))
      (&walk.untaken (:t D) (:item D)))
    (take ((:t D) (:item D))
      (&order.member (:t *D))
      (&walk.untaken (:t D) (:item D)))))
",
    );
    assert_eq!(untyped_labels(&checked, 2), Vec::<LabelId>::new());
}

#[test]
fn an_or_branch_that_makes_a_label_only_by_zero_adds_no_type() {
    let checked = checked(
        "
(RULE &stretch
  (OR ((diag_dir_elem (:D *K)))
      ((= K 0))))
",
    );
    let Form::Clause(clause) = &checked.program.program.value().forms[0] else { panic!("the first form is a clause") };
    let column = clause.value().columns.iter().find(|column| column.name == ColumnName::Written("K".into())).expect("the clause has a column K");
    let types = checked.types.form(&path(&[0])).expect("the clause is a label scope");
    assert_eq!(types.label(column.label), Some(&ValueType::DiagDir));
}
