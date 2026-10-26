//! A `DET_OR_RULE` line splits only the cases whose forms read its relation,
//! and its derived reading by a proposer gives the relation the columns that
//! the proposer declares, as `docs/engine/cases.md#cases` and
//! `docs/arclog/arclog.md#the-alts-form` give. The stored reading of a
//! `RULE_OR_DET` line is a `DET` over the rows its derivation gives at every
//! train example, and a lifted read bound by `ex_output` reads the train
//! examples alone.

use std::sync::Arc;

use arclog::check::{check_shared_program, CheckCache, SolverClauses};
use arclog::decode::corpus::{solver_verdicts, Verdict};
use arclog::eval::instance::{Construction, ConstructionContext, Constructions, GroupInputs, GroupOutputs};
use arclog::eval::ReachedBound;
use arclog::relations::RowSet;
use arclog::program::{AltsName, ClauseKeyword, DeclaredName, Form, ProgramRelation, RelationName};
use arclog::stream::corpus::{solver_streams, WantedCases};
use arclog::stream::{DecodeSettings, Vocabulary};
use arclog::read::read_solver;
use arclog::registry::Registry;
use arclog::resolver::{resolve_cases, DependencyKind, GraphNodeIndex};
use arclog::solver::{Case, CaseName, Exclusion};
use arclog::types::GraphRelation;

/// `&k` is read by `&v`. `$Own` rederives `&v` from the evidence, so in its
/// cases nothing reads `&k`, and it holds a line `&j` that its `&v` reads.
const ARCLOG: &str = "
(INPUT sides \"a side of at most &k.\"
  (DET_OR_RULE &k \"The longest side.\" SepTileCount TileCount
    (ex_input *E *P)
    (frame_extent P *A *N)
    (ONE))

  (RULE &v
    (&k *N))

  (RULE &output
    (input *P *Col)
    (&v *N)))

(ALTS $source \"where the sides come from\" $FromK
  (ALT $Own
    (INPUT own \"the sides of &j.\"
      (DET_OR_RULE &j \"The longest side.\" SepTileCount TileCount
        (ex_input *E *P)
        (frame_extent P *A *N))

      (RULE &v
        (&j *N)))))
";

fn names() -> Vec<Vec<String>> {
    let solver = read_solver("lines", ARCLOG, "", &|_| None).expect("the file reads").value;
    solver.case_names(Exclusion::WithExcluded).into_iter().map(|name: CaseName| name.0.iter().map(|alt| alt.0.to_string()).collect()).collect()
}

#[test]
fn a_line_that_no_form_of_the_case_reads_does_not_split_it() {
    let names = names();
    let own: Vec<&Vec<String>> = names.iter().filter(|name| name.iter().any(|alt| alt == "$Own")).collect();
    assert_eq!(own.len(), 3, "{names:?}");
    assert!(own.iter().all(|name| name.iter().all(|alt| !alt.starts_with("&k="))), "{own:?}");
    let from_k = names.iter().filter(|name| name.iter().any(|alt| alt == "$FromK")).count();
    assert_eq!(from_k, 3, "{names:?}");
}

#[test]
fn the_concept_alts_hold_the_first_reading_of_a_line_that_a_nested_block_holds() {
    let solver = read_solver("lines", ARCLOG, "", &|_| None).expect("the file reads").value;
    let alt = |text: &str| AltsName(text.into());
    let alts = solver.concept_alts();
    assert!(alts.contains(&alt("&k=$Stored")), "{alts:?}");
    assert!(alts.contains(&alt("&j=$Stored")), "{alts:?}");
    assert!(!alts.contains(&alt("&j=SepTileCount")), "{alts:?}");
    assert!(!alts.contains(&alt("$Own")), "{alts:?}");
}

#[test]
fn the_derived_reading_of_a_line_with_a_body_has_the_columns_of_its_proposer() {
    let solver = read_solver("lines", ARCLOG, "", &|_| None).expect("the file reads").value;
    let registry = Registry::get();
    let cases = resolve_cases(&solver, registry);
    let clauses = SolverClauses::of_cases(&cases);
    let case = cases.cases().find(|resolved| resolved.case.name.0.contains(&AltsName("&k=SepTileCount".into()))).expect("the case that reads `&k` by its proposer");
    let checked = check_shared_program(Arc::clone(&case.resolved.value), &clauses, registry, &mut CheckCache::default()).expect("the case checks");
    let chosen = checked.program.graph.nodes.iter().position(|node| matches!(node.kind, DependencyKind::Chosen(_))).expect("`&k` is a pick");
    let columns = checked.types.columns(&GraphRelation { node: GraphNodeIndex(chosen as u32), output: None });
    assert_eq!(columns.map(<[_]>::len), Some(1));
}

/// A corpus of one solver `line` over a task of one train pair, whose output
/// is a row of one color, and one test input of two colors.
fn corpus(arclog: &str) -> std::path::PathBuf {
    use std::sync::atomic::{AtomicUsize, Ordering};
    static COUNT: AtomicUsize = AtomicUsize::new(0);
    let dir = std::env::temp_dir().join(format!("arclog-line-readings-{}-{}", std::process::id(), COUNT.fetch_add(1, Ordering::Relaxed)));
    std::fs::create_dir_all(&dir).expect("a temporary directory");
    std::fs::write(dir.join("line.arclog"), arclog).expect("the arclog file");
    std::fs::write(dir.join("line.arcdata"), ";; line\n").expect("the arcdata file");
    let task = r#"{"train": [{"input": [[1, 1]], "output": [[1, 1]]}], "test": [{"input": [[1, 2]], "output": [[1, 2]]}]}"#;
    std::fs::write(dir.join("line.json"), task).expect("the task file");
    dir
}

/// The stored case of the line `relation`, and whether the writer gives it a
/// stream.
fn stored_case(arclog: &str, relation: &str) -> (Case, Result<(), String>) {
    let solver = read_solver("line", arclog, "", &|_| None).expect("the file reads").value;
    let stored = AltsName(format!("{relation}=$Stored").into());
    let name = solver.case_names(Exclusion::WithExcluded).into_iter().find(|name| name.0.contains(&stored)).expect("a case that takes the stored reading");
    let case = solver.case(&name).expect("the case builds");
    let dir = corpus(arclog);
    let vocabulary = Vocabulary::new(Registry::get(), &DecodeSettings::default());
    let spelled = arclog::stream::corpus::case_spelled(&name);
    let streams = solver_streams(&dir, "line", WantedCases::Named(&spelled), &vocabulary);
    std::fs::remove_dir_all(&dir).ok();
    let stream = streams.expect("the case checks").remove(0).stream.map(|_| ());
    (case, stream)
}

/// The keyword of each clause of `case` that derives the relation spelled
/// `relation`, in the order of the program.
fn clauses_of(case: &Case, relation: &str) -> Vec<ClauseKeyword> {
    let declared = ProgramRelation::Declared(RelationName(DeclaredName::Written(relation.into())));
    let forms = case.program.value().forms.iter();
    forms.filter_map(|form| match form {
        Form::Clause(clause) if clause.value().derives == declared => Some(clause.value().keyword),
        _ => None,
    }).collect()
}

const BODY_LINE: &str = "
(INPUT cells \"the cells\"
  (RULE_OR_DET &cell \"The cells.\"
    (input *P *Col))

  (RULE &output
    (input *P *Col)
    (&cell P)))
";

#[test]
fn the_stored_reading_of_a_line_with_a_body_is_a_det_over_a_rule_of_that_body() {
    let (case, stream) = stored_case(BODY_LINE, "&cell");
    assert_eq!(clauses_of(&case, "&cell_derived"), vec![ClauseKeyword::Rule]);
    assert_eq!(clauses_of(&case, "&cell"), vec![ClauseKeyword::Det]);
    assert_eq!(stream, Ok(()));
}

const OUTPUT_PORT: &str = "
(INPUT ring \"the ring\"
  (INIT &ring Singleton
    (member ((:v Col))
      (input *P *Col)))

  (RULE_OR_DET &ring.value \"The one color.\")

  (RULE &output
    (input *P *Col)
    (&ring.value (:v Col))))
";

#[test]
fn the_stored_reading_of_a_line_on_an_output_port_is_a_det_that_each_read_of_the_port_reads() {
    let (case, stream) = stored_case(OUTPUT_PORT, "&ring.value");
    assert_eq!(clauses_of(&case, "&ring_value_stored"), vec![ClauseKeyword::Det]);
    assert!(case.program.value().forms.iter().any(|form| matches!(form, Form::Instance(_))), "the instance stays");
    assert_eq!(stream, Ok(()));
}

const INPUT_PORT: &str = "
(INPUT canvas \"the canvas\"
  (INIT &canvas Frame
    (extent (A N)
      (input *P)
      (axis_elem *A)
      (frame_extent P A *N)))

  (RULE_OR_DET &canvas.extent)

  (RULE &output
    (&canvas.cell *P)))
";

#[test]
fn the_stored_reading_of_a_line_on_an_input_port_is_a_det_over_a_rule_of_the_inputs_clause() {
    let (case, stream) = stored_case(INPUT_PORT, "&canvas.extent");
    assert_eq!(clauses_of(&case, "&canvas_extent_derived"), vec![ClauseKeyword::Rule]);
    assert_eq!(clauses_of(&case, "&canvas_extent_stored"), vec![ClauseKeyword::Det]);
    assert_eq!(stream, Ok(()));
}

const CONCEPT_READ: &str = "
(INPUT cells \"the cells\"
  (RULE_OR_DET &cell \"The cells.\"
    (input *P *Col))

  (DET &gap
    (ex_input *E *P *Col)
    (NOT (&cell E P Col)))

  (RULE &output
    (input *P *Col)
    (&gap P Col)))
";

#[test]
fn a_det_of_the_concept_program_that_reads_a_stored_line_with_a_site_on_e_is_taken_from_the_concept_program() {
    let (case, stream) = stored_case(CONCEPT_READ, "&cell");
    assert_eq!(case.concept_determinations().len(), 1);
    assert_eq!(stream, Ok(()));
}

/// A `Singleton` whose member holds one row, and outside its domain where it
/// does not.
struct OneMember;

impl Construction for OneMember {
    fn name(&self) -> &'static str {
        "Singleton"
    }

    fn outside_domain(&self, group: &GroupInputs<'_>) -> bool {
        group.inputs[0].len() != 1
    }

    fn evaluate(&self, group: &GroupInputs<'_>, _: &mut ConstructionContext<'_, '_>) -> Result<GroupOutputs, ReachedBound> {
        Ok(GroupOutputs { outputs: Box::new([group.inputs[0].clone(), RowSet::empty(0)]) })
    }
}

/// The verdict of the only case of a solver that holds `forms`, a train pair
/// of one color and a test input of two, over `&one`, a construction outside
/// its domain on the test input.
fn verdict_of(forms: &str) -> Verdict {
    let arclog = format!("(INIT &one Singleton (member ((:v Col)) (input *P *Col)))\n(RULE &c (&one.value (:v *Col)))\n{forms}\n");
    let dir = corpus(&arclog);
    let constructions = Constructions::new(vec![Box::new(OneMember)], Registry::get()).expect("a table of one construction");
    let verdicts = solver_verdicts(&dir, &dir, "line", &constructions);
    std::fs::remove_dir_all(&dir).ok();
    let verdicts = verdicts.expect("the solver's verdicts");
    assert_eq!(verdicts.len(), 1, "{verdicts:?}");
    verdicts[0].verdict.clone()
}

#[test]
fn a_lifted_read_bound_by_ex_output_reads_the_train_examples_alone() {
    let bound = verdict_of("(DET &d (ex_output (:E *E)) (&c (:E E) (:Col *Col)))\n(RULE &output (input *P *Col) (&d (:Col Col)))");
    assert_eq!(bound, Verdict::Consistent);
    let unbound = verdict_of("(DET &d (ex_input *E) (&c (:E E) (:Col *Col)))\n(RULE &output (input *P *Col) (&d (:Col Col)))");
    assert_ne!(unbound, Verdict::Consistent);
}

const UNREAD_COLUMN: &str = "
(INPUT cells \"the cells\"
  (RULE_OR_DET &cell \"The cells.\"
    (input *P *Col))

  (RULE &output
    (input *P *Col)
    (&cell (:Col Col))))
";

#[test]
fn the_stored_det_of_a_line_has_the_columns_that_a_read_names() {
    let (case, stream) = stored_case(UNREAD_COLUMN, "&cell");
    let declared = ProgramRelation::Declared(RelationName(DeclaredName::Written("&cell".into())));
    let det = case.program.value().forms.iter().find_map(|form| match form {
        Form::Clause(clause) if clause.value().derives == declared => Some(clause.value().clone()),
        _ => None,
    });
    let det = det.expect("the stored DET");
    let sites_of_derivation = |body: &arclog::program::Body| body.conjuncts.iter().filter_map(|c| c.atom().map(|atom| atom.value().sites.len())).collect::<Vec<_>>();
    // `ex_output (:E)`, then the read of the helper at `E` and `Col` alone.
    assert_eq!(sites_of_derivation(det.body.value()), vec![1, 2], "{det:?}");
    assert_eq!(stream, Ok(()));
}

const READS_IN_THE_BLOCK_THAT_HOLDS_THE_LINE: &str = "
(ALTS $a \"which block\" $Plain
  (ALT $Own
    (INPUT cells \"the cells\"
      (RULE_OR_DET &cell \"The cells.\"
        (input *P *Col))

      (RULE &other
        (&cell (:P *P)))

      (RULE &output
        (input *P *Col)
        (&cell (:Col Col))
        (&other P)))))
";

#[test]
fn the_stored_det_has_the_columns_that_forms_of_the_block_that_holds_the_line_name() {
    let (case, stream) = stored_case(READS_IN_THE_BLOCK_THAT_HOLDS_THE_LINE, "&cell");
    let declared = ProgramRelation::Declared(RelationName(DeclaredName::Written("&cell".into())));
    let det = case.program.value().forms.iter().find_map(|form| match form {
        Form::Clause(clause) if clause.value().derives == declared => Some(clause.value().clone()),
        _ => None,
    });
    let det = det.expect("the stored DET");
    let sites: Vec<usize> = det.body.value().conjuncts.iter().filter_map(|c| c.atom().map(|atom| atom.value().sites.len())).collect();
    assert_eq!(sites, vec![1, 3], "`E`, `P` and `Col`: {det:?}");
    assert_eq!(stream, Ok(()));
}

const KEYED_PORT: &str = "
(INPUT boxes \"the boxes\"
  (INIT &bbox BoundingBox
    (key ((input *P ^Col))
      (cell (P)
        (input *P Col))))

  (RULE_OR_DET &bbox.box \"The boxes.\")

  (RULE &output
    (&bbox.box (:key *Col) *B)))
";

#[test]
fn the_stored_reading_of_a_line_on_a_keyed_port_is_a_det_of_the_value_columns_and_a_rule_that_joins_the_other_columns() {
    let (case, stream) = stored_case(KEYED_PORT, "&bbox.box");
    assert_eq!(clauses_of(&case, "&bbox_box_value"), vec![ClauseKeyword::Det]);
    assert_eq!(clauses_of(&case, "&bbox_box_stored"), vec![ClauseKeyword::Rule]);
    let declared = ProgramRelation::Declared(RelationName(DeclaredName::Written("&bbox_box_stored".into())));
    let rule = case.program.value().forms.iter().find_map(|form| match form {
        Form::Clause(clause) if clause.value().derives == declared => Some(clause.value().clone()),
        _ => None,
    });
    let columns: Vec<String> = rule.expect("the joining RULE").columns.iter().map(|column| format!("{:?}", column.name)).collect();
    assert_eq!(columns, vec!["Written(\"KeyCol\")", "Written(\"B\")"]);
    assert_eq!(stream, Ok(()));
}
