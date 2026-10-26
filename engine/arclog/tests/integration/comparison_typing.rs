//! The comparison typing rule of the type check, its rule on the join of a relation's
//! column types, and the pose rule each refuse a file that breaks them, and the
//! Pose type of a keyed assembly's pose at the columns that a derived relation or
//! an instance holds beside its key.

use std::sync::Arc;

use arclog::check::{check_shared_program, CheckCache, CheckId, SolverClauses};
use arclog::diagnostic::{DiagnosticKind, Location};
use arclog::program::path::{NodePath, PathStep};
use arclog::read::read_solver;
use arclog::registry::Registry;
use arclog::resolver::{resolve_cases, DependencyKind, GraphNodeIndex};
use arclog::types::{GraphRelation, KeyRow, ValueType};

/// The checks that refuse the program of `arclog`, each with where it
/// refuses it.
fn refusals(arclog: &str) -> Vec<(CheckId, Location)> {
    let solver = read_solver("rules", arclog, "", &|_| None).expect("the file reads").value;
    let registry = Registry::get();
    let cases = resolve_cases(&solver, registry);
    let clauses = SolverClauses::of_cases(&cases);
    checks_refusing(Arc::clone(&cases.concept().resolved.value), &clauses, registry)
}

/// The checks that refuse each case program of `arclog` other than the
/// concept program.
fn case_refusing_checks(arclog: &str) -> Vec<CheckId> {
    let solver = read_solver("rules", arclog, "", &|_| None).expect("the file reads").value;
    let registry = Registry::get();
    let cases = resolve_cases(&solver, registry);
    let clauses = SolverClauses::of_cases(&cases);
    let concept_name = &cases.concept().case.name;
    cases
        .cases()
        .filter(|resolved| &resolved.case.name != concept_name)
        .flat_map(|resolved| checks_refusing(Arc::clone(&resolved.resolved.value), &clauses, registry))
        .map(|(check, _)| check)
        .collect()
}

/// The checks that refuse `program`, each with where it refuses it.
fn checks_refusing(program: Arc<arclog::resolver::ResolvedProgram>, clauses: &SolverClauses, registry: &Registry) -> Vec<(CheckId, Location)> {
    match check_shared_program(program, clauses, registry, &mut CheckCache::default()) {
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

/// The top-level forms at which the type check refuses each case program
/// of `arclog` other than the concept program, in the order of the cases,
/// with one [`CheckCache`] across the cases.
fn case_type_refused_forms(arclog: &str) -> Vec<Vec<u32>> {
    let solver = read_solver("rules", arclog, "", &|_| None).expect("the file reads").value;
    let registry = Registry::get();
    let cases = resolve_cases(&solver, registry);
    let clauses = SolverClauses::of_cases(&cases);
    let concept_name = &cases.concept().case.name;
    let mut cache = CheckCache::default();
    cases
        .cases()
        .filter(|resolved| &resolved.case.name != concept_name)
        .map(|resolved| {
            let program = Arc::clone(&resolved.resolved.value);
            let Err(diagnostics) = check_shared_program(program, &clauses, registry, &mut cache) else { return Vec::new() };
            let mut forms: Vec<u32> = diagnostics
                .into_iter()
                .filter(|diagnostic| diagnostic.kind == DiagnosticKind::Check(CheckId::Types))
                .map(|diagnostic| match diagnostic.location {
                    Location::Path(path) => path.0[0].0,
                    Location::Places(places) => panic!("a refusal of a program with no file stands at a path, not at {places:?}"),
                })
                .collect();
            forms.dedup();
            forms
        })
        .collect()
}

#[test]
fn a_column_that_two_alts_give_a_dir_and_a_d4_passes_in_each_case() {
    let forms = case_type_refused_forms(
        "
(ALTS $turn \"what turns a cell\" $None
  (ALT $Step
    (RULE &turn
      (input *P *Col)
      (neighbor (:P P) *D (:Q *Q))))
  (ALT $Pose
    (RULE &turn
      (input *P *Col)
      (input *Q Col)
      (d4_identity *D))))
",
    );
    assert_eq!(forms, vec![Vec::<u32>::new(), Vec::new()]);
}

#[test]
fn a_clause_that_two_alts_hold_is_refused_only_where_its_sibling_has_no_join() {
    let forms = case_type_refused_forms(
        "
(RULE &cell
  (input *P *Col))

(ALTS $mixed \"what &mixed holds\" $None
  (ALT $Colors
    (RULE &mixed
      (&cell (:Col *X)))
    (RULE &mixed
      (&cell (:P *Q) (:Col *X))))
  (ALT $Numbers
    (RULE &mixed
      (&cell (:Col *X)))
    (RULE &mixed
      (&cell (:P *Q))
      (frame_extent (:P Q) (:A *A) (:N *X)))))
",
    );
    assert_eq!(forms.len(), 2, "{forms:?}");
    assert!(forms[0].is_empty(), "{forms:?}");
    assert_eq!(forms[1].len(), 2, "{forms:?}");
}

/// A keyed assembly, read at the key `Col`, a `Frame` instance whose key
/// holds a pose of that assembly and the key label, and a derived relation
/// that holds both.
const KEYED_POSE: &str = "
(RULE &cell
  (input *P *Col))

(RIGID_DET &piece
  (key ((&cell ^Col))
    (&cell Col *P)))

(INIT &frame Frame
  (key ((&piece.cell (:Pose ^D) (:key ^Col) *P)
        (axis_elem *A)
        (frame_extent P A *N))
    (extent (A N)
      (&piece.cell (:Pose D) (:key Col) *P)
      (axis_elem *A)
      (frame_extent P A *N))))

(RULE &placed
  (&piece.cell (:Pose *D) (:key *Col) *P))
";

#[test]
fn a_pose_of_a_keyed_assembly_at_a_column_of_an_instances_key_takes_the_pose_type_at_the_key_that_the_key_holds() {
    let read = "
(RULE &outside
  (&placed *Col *D *P)
  (&frame.cell (:key Col D) (:P *Q)))
";
    assert_eq!(refusing_checks(&format!("{KEYED_POSE}{read}")), vec![]);
}

#[test]
fn a_pose_of_a_keyed_assembly_at_a_column_of_a_derived_relation_takes_the_pose_type_at_the_key_that_the_relation_holds() {
    let read = "
(RULE &outside
  (&placed *Col *D *P)
  (&piece.cell (:Pose D) (:key Col) (:P *Q)))
";
    assert_eq!(refusing_checks(&format!("{KEYED_POSE}{read}")), vec![]);
}

#[test]
fn a_pose_of_a_keyed_assembly_joined_at_two_key_labels_is_refused() {
    let read = "
(RULE &outside
  (&placed *Col *D *P)
  (&piece.cell (:Pose D) (:key *Col2) (:P *Q)))
";
    assert!(!refusing_checks(&format!("{KEYED_POSE}{read}")).is_empty());
}

#[test]
fn a_read_of_an_instances_key_that_gives_no_label_at_the_pose_key_gives_the_pose_no_pose_type() {
    let read = "
(RULE &outside
  (&placed *Col *D *P)
  (&frame.cell (:key (:D D)) (:P *Q)))
";
    assert!(refusing_checks(&format!("{KEYED_POSE}{read}")).contains(&CheckId::PoseRule));
}

#[test]
fn the_columns_of_an_instance_output_that_holds_a_pose_of_a_keyed_assembly_name_its_key_by_position() {
    let solver = read_solver("rules", KEYED_POSE, "", &|_| None).expect("the file reads").value;
    let registry = Registry::get();
    let cases = resolve_cases(&solver, registry);
    let clauses = SolverClauses::of_cases(&cases);
    let program = Arc::clone(&cases.concept().resolved.value);
    let checked = check_shared_program(program, &clauses, registry, &mut CheckCache::default()).expect("every check passes");
    let outputs = checked.program.graph.nodes.iter().enumerate().filter(|(_, node)| matches!(node.kind, DependencyKind::InstanceOutput { .. }));
    let columns: Vec<_> = outputs.map(|(node, _)| checked.types.columns(&GraphRelation { node: GraphNodeIndex(node as u32), output: None })).collect();
    assert!(!columns.is_empty() && columns.iter().all(Option::is_some), "{columns:?}");
    let keys: Vec<&KeyRow> = columns.iter().flatten().flat_map(|types| types.iter()).filter_map(|ty| if let ValueType::Pose(id) = ty { Some(&id.key) } else { None }).collect();
    assert_eq!(keys, [&KeyRow::Columns(Box::new([1]))]);
}
