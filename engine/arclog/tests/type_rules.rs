//! The order rule of the type check and the pose rule each refuse a file
//! that breaks them.

use arclog::check::{check_program, CheckCache, CheckId, SolverClauses};
use arclog::diagnostic::DiagnosticKind;
use arclog::read::read_solver;
use arclog::registry::Registry;
use arclog::resolver::{resolve, MacroExpansion};

/// The checks that refuse the program of `arclog`.
fn refusing_checks(arclog: &str) -> Vec<CheckId> {
    let solver = read_solver("rules", arclog, "", &|_| None).expect("the file reads").value;
    let registry = Registry::get();
    let program = resolve(&solver.concept_case().program, None, &solver.derived_relations(), registry, MacroExpansion::Keep).value;
    let clauses = SolverClauses::of(&solver, registry);
    match check_program(program, &clauses, registry, &mut CheckCache::default()) {
        Ok(_) => Vec::new(),
        Err(diagnostics) => diagnostics
            .into_iter()
            .filter_map(|diagnostic| match diagnostic.kind {
                DiagnosticKind::Check(check) => Some(check),
                _ => None,
            })
            .collect(),
    }
}

#[test]
fn an_order_on_colors_is_refused() {
    let checks = refusing_checks(
        "
(RULE &brighter
  (input *P *Col)
  (input (:P *Q) (:Col *Col2))
  (< Col Col2))
",
    );
    assert!(checks.contains(&CheckId::Types), "{checks:?}");
}

#[test]
fn a_pose_at_a_site_of_a_d4_column_is_refused() {
    let checks = refusing_checks(
        "
(RULE &cell
  (input *P *Col))

(RIGID_DET &piece
  (&cell *P))

(RULE &fixed
  (&piece.cell (:Pose *D) (:P *P))
  (d4_identity D))
",
    );
    assert!(checks.contains(&CheckId::PoseRule), "{checks:?}");
}
