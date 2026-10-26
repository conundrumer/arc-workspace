//! The relation of a `DET` form has as its columns the labels of its clause
//! that a site of a read of the relation names, a read in an `ALT` block
//! included, in the order the clause gives them, so a stored `param` record
//! of one column type per such label reads at them.

use arclog::check::{check_program, CheckCache, SolverClauses};
use arclog::eval::relation_of;
use arclog::program::path::{NodePath, PathStep};
use arclog::program::{DeclaredName, ProgramRelation, RelationName};
use arclog::read::read_solver;
use arclog::registry::Registry;
use arclog::resolver::{resolve, ColumnPosition};
use arclog::terms::{encode_param_value, InternTable};

/// be03b35f's `&template`, whose label `E` no read names, read by
/// `&output` at `Diag` and `D4`.
const ARCLOG: &str = "
(RULE &cell
  (input *P *Col))

(DET &d4m_src
  (ex_input *E (:P *P))
  (diag_dir_elem (:D *Diag)))

(DET &mismatch
  (&d4m_src *E *Diag)
  (d4_elem (:D *D4))
  (NOT (diag_dir_elem (:D Diag))))

(DET &broken
  (&mismatch *E *Diag *D4)
  (ex_output E))

(DET &template
  (&d4m_src *E *Diag)
  (d4_elem (:D *D4))
  (NOT (&mismatch E Diag D4))
  (ex_output E)
  (NOT (&broken Diag D4)))

(RULE &output
  (&cell *P *Col)
  (&template *Diag (:D4 *D)))
";

const ARCDATA: &str = "(param &template (DiagDir D4) (DIAG_TL D4_CC) (DIAG_TR D4_HT) (DIAG_BL D4_CW))\n";

fn path(steps: &[u32]) -> NodePath {
    NodePath(steps.iter().copied().map(PathStep).collect())
}

/// The number of column types of the concept program's `&template`, for
/// the solver of `arclog`.
fn template_types(arclog: &str) -> usize {
    let solver = read_solver("be03b35f", arclog, ARCDATA, &|_| None).expect("the files read").value;
    let registry = Registry::get();
    let program = resolve(&solver.concept_case().program, None, &solver.derived_relations(), registry).value;
    let clauses = SolverClauses::of(&solver, registry);
    let checked = check_program(program, &clauses, registry, &mut CheckCache::default()).expect("the program checks");
    let template = ProgramRelation::Declared(RelationName(DeclaredName::Written("&template".into())));
    let relation = relation_of(&checked, &template).expect("the program derives `&template`");
    checked.types.columns(&relation).expect("the columns have types").len()
}

#[test]
fn a_det_has_the_columns_that_an_alt_s_read_names() {
    let alts = "
(ALTS $choice \"Whether the output reads the example.\" $Plain
  (ALT $Plain)
  (ALT $ByExample
    (RULE &output
      (&cell *P *Col)
      (&template *Diag (:D4 *D) (:E *E)))))
";
    assert_eq!(template_types(ARCLOG), 2);
    assert_eq!(template_types(&format!("{ARCLOG}{alts}")), 3);
}

#[test]
fn a_det_has_the_columns_that_its_reads_name_and_its_stored_rows_read_at_them() {
    let solver = read_solver("be03b35f", ARCLOG, ARCDATA, &|_| None).expect("the files read").value;
    let registry = Registry::get();
    let program = resolve(&solver.concept_case().program, None, &solver.derived_relations(), registry);
    assert!(program.diagnostics.is_empty(), "{:?}", program.diagnostics);
    let read_at = |site: u32| program.value.column_position(&path(&[5, 0, 1, site])).expect("the site has a position");
    assert_eq!((read_at(0), read_at(1)), (ColumnPosition(0), ColumnPosition(1)));
    let clauses = SolverClauses::of(&solver, registry);
    let checked = check_program(program.value, &clauses, registry, &mut CheckCache::default()).expect("the program checks");
    let template = ProgramRelation::Declared(RelationName(DeclaredName::Written("&template".into())));
    let relation = relation_of(&checked, &template).expect("the program derives `&template`");
    assert!(checked.program.example_columns(relation.node, None).is_empty());
    let types = checked.types.columns(&relation).expect("the columns have types");
    assert_eq!(types.len(), 2, "{types:?}");
    let param = solver.arcdata.value().params.iter().find(|param| param.value().name == template).expect("the stored record");
    let rows = encode_param_value(&param.value().value, types, registry, &mut InternTable::default());
    assert_eq!(rows.expect("the stored rows read at the columns' types").len(), 3);
}

/// A `DET` that ends in a mark, with the labels `Diag` and `D4`, read by
/// `&output` at `Diag` alone.
const MARKED: &str = "
(RULE &cell
  (input *P *Col))

(DET &pick
  (diag_dir_elem (:D *Diag))
  (d4_elem (:D *D4))
  MARK)

(RULE &output
  (&cell *P *Col)
  (&pick *Diag))
";

/// The column types of `&pick` for `MARKED` with `mark` in place of `MARK`,
/// and whether its stored record `data` reads at them.
fn pick_types(mark: &str, data: &str) -> (usize, bool) {
    let arclog = MARKED.replace("MARK", mark);
    let solver = read_solver("0000aaaa", &arclog, data, &|_| None).expect("the files read").value;
    let registry = Registry::get();
    let program = resolve(&solver.concept_case().program, None, &solver.derived_relations(), registry).value;
    let clauses = SolverClauses::of(&solver, registry);
    let checked = check_program(program, &clauses, registry, &mut CheckCache::default()).expect("the program checks");
    let pick = ProgramRelation::Declared(RelationName(DeclaredName::Written("&pick".into())));
    let relation = relation_of(&checked, &pick).expect("the program derives `&pick`");
    let types = checked.types.columns(&relation).expect("the columns have types");
    let param = solver.arcdata.value().params.iter().find(|param| param.value().name == pick).expect("the stored record");
    let rows = encode_param_value(&param.value().value, types, registry, &mut InternTable::default());
    (types.len(), rows.is_ok())
}

#[test]
fn a_det_that_ends_in_one_has_the_columns_that_its_reads_name() {
    let (columns, reads) = pick_types("(ONE)", "(param &pick DiagDir (DIAG_TL))\n");
    assert_eq!((columns, reads), (1, true));
}

#[test]
fn a_det_has_the_columns_that_a_one_mark_names_besides_those_its_reads_name() {
    let (columns, reads) = pick_types("(ONE D4)", "(param &pick (DiagDir D4) (DIAG_TL D4_CC))\n");
    assert_eq!((columns, reads), (2, true));
}
