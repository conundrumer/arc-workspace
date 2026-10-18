//! The order rule of the type check, its rule on the join of a relation's
//! column types, and the pose rule each refuse a file that breaks them.

use std::sync::Arc;

use arclog::check::{check_program, CheckCache, CheckId, SolverClauses};
use arclog::diagnostic::{DiagnosticKind, Location};
use arclog::program::path::{NodePath, PathStep};
use arclog::read::read_solver;
use arclog::registry::Registry;
use arclog::resolver::{resolve, ConceptReads};
use arclog::solver::Exclusion;

/// The checks that refuse the program of `arclog`, each with where it
/// refuses it.
fn refusals(arclog: &str) -> Vec<(CheckId, Location)> {
    let solver = read_solver("rules", arclog, "", &|_| None).expect("the file reads").value;
    let registry = Registry::get();
    let program = resolve(&solver.concept_case().program, None, &solver.derived_relations(), registry).value;
    let clauses = SolverClauses::of(&solver, registry);
    checks_refusing(program, &clauses, registry)
}

/// The checks that refuse each case program of `arclog` other than the
/// concept program.
fn case_refusing_checks(arclog: &str) -> Vec<CheckId> {
    let solver = read_solver("rules", arclog, "", &|_| None).expect("the file reads").value;
    let registry = Registry::get();
    let derived = solver.derived_relations();
    let concept_case = solver.concept_case();
    let concept = Arc::new(resolve(&concept_case.program, None, &derived, registry).value);
    let clauses = SolverClauses::of(&solver, registry);
    let cases = solver.cases(Exclusion::WithExcluded).filter(|case| case.name != concept_case.name);
    cases
        .flat_map(|case| {
            let reads = ConceptReads { concept: &concept, determinations: case.concept_determinations() };
            let program = resolve(&case.program, Some(reads), &derived, registry).value;
            checks_refusing(program, &clauses, registry)
        })
        .map(|(check, _)| check)
        .collect()
}

/// The checks that refuse `program`, each with where it refuses it.
fn checks_refusing(program: arclog::resolver::ResolvedProgram, clauses: &SolverClauses, registry: &Registry) -> Vec<(CheckId, Location)> {
    match check_program(program, clauses, registry, &mut CheckCache::default()) {
        Ok(_) => Vec::new(),
        Err(diagnostics) => diagnostics
            .into_iter()
            .filter_map(|diagnostic| match diagnostic.kind {
                DiagnosticKind::Check(check) => Some((check, diagnostic.location)),
                _ => None,
            })
            .collect(),
    }
}

/// The checks that refuse the program of `arclog`.
fn refusing_checks(arclog: &str) -> Vec<CheckId> {
    refusals(arclog).into_iter().map(|(check, _)| check).collect()
}

/// The paths of the top-level forms at which the type check refuses the
/// program of `arclog`.
fn type_refused_forms(arclog: &str) -> Vec<u32> {
    let mut forms: Vec<u32> = refusals(arclog)
        .into_iter()
        .filter(|(check, _)| *check == CheckId::Types)
        .map(|(_, location)| match location {
            Location::Path(path) => path.0[0].0,
            Location::Places(places) => panic!("a refusal of a program with no file stands at a path, not at {places:?}"),
        })
        .collect();
    forms.dedup();
    forms
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

#[test]
fn a_pose_at_a_site_of_a_d4_column_in_a_concept_det_is_refused_in_each_case() {
    let checks = case_refusing_checks(
        "
(RULE &cell
  (input *P *Col))

(RIGID_DET &piece
  (&cell *P))

(DET &fixed
  (&piece.cell (:Pose *D) (:P *P))
  (d4_identity D))

(ALTS $extra \"whether &more holds\" $None
  (ALT $Some
    (RULE &more (input *P *Col))))
",
    );
    assert!(checks.contains(&CheckId::PoseRule), "{checks:?}");
}

#[test]
fn a_column_that_a_color_and_a_number_give_is_refused_at_each_clause() {
    let forms = type_refused_forms(
        "
(RULE &cell
  (input *P *Col))

(RULE &mixed
  (&cell (:Col *X)))

(RULE &mixed
  (&cell (:P *Q))
  (frame_extent (:P Q) (:A *A) (:N *X)))

(RULE &use
  (&mixed *X)
  (< X X))
",
    );
    assert_eq!(forms, vec![1, 2]);
}

#[test]
fn a_column_that_two_assemblies_give_poses_is_refused_at_each_clause() {
    let forms = type_refused_forms(
        "
(RULE &cell
  (input *P *Col))

(RULE &marked
  (input *P *Col)
  (input P Col))

(RIGID_DET &piece
  (&cell *P))

(RIGID_DET &other
  (&marked *P))

(RULE &poses
  (&piece.cell (:Pose *D) (:P *P)))

(RULE &poses
  (&other.marked (:Pose *D) (:P *P)))

(RULE &fixed
  (&poses *D)
  (d4_identity D))
",
    );
    assert_eq!(forms, vec![4, 5]);
}

#[test]
fn a_det_with_a_proposer_and_no_body_is_refused_at_its_own_path() {
    let refused = refusals(
        "
(RULE &cell
  (input *P *Col))

(DET &bg ColorDomain)

(RULE &bg
  (&cell (:P *Q))
  (frame_extent (:P Q) (:A *A) (:N *C)))
",
    );
    let det = Location::Path(NodePath(Box::new([PathStep(1)])));
    assert!(refused.contains(&(CheckId::Types, det)), "{refused:?}");
}
