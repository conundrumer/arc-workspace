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
use arclog::program::AltsName;
use arclog::read::read_solver;
use arclog::registry::Registry;
use arclog::resolver::{resolve_cases, DependencyKind, GraphNodeIndex};
use arclog::solver::{CaseName, Exclusion};
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

(OUT (&output ^P ^Col))
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

/// The departures of the case of the alts `alts` in `arclog`.
fn departures(arclog: &str, alts: &[&str]) -> Vec<String> {
    let solver = read_solver("lines", arclog, "", &|_| None).expect("the file reads").value;
    let name = CaseName(alts.iter().map(|alt| AltsName((*alt).into())).collect());
    solver.departures(&name).into_iter().map(|alt| alt.0.to_string()).collect()
}

#[test]
fn a_case_departs_by_the_first_reading_of_no_line_and_by_each_other_reading() {
    assert_eq!(departures(ARCLOG, &["$FromK", "&k=$Stored"]), Vec::<String>::new());
    assert_eq!(departures(ARCLOG, &["$FromK", "&k=SepTileCount"]), ["&k=SepTileCount"]);
    // A line that only a nested block holds: the concept case reaches neither it nor its blocks.
    assert_eq!(departures(ARCLOG, &["$Own", "&j=$Stored"]), ["$Own"]);
    assert_eq!(departures(ARCLOG, &["$Own", "&j=SepTileCount"]), ["$Own", "&j=SepTileCount"]);
}

/// `$Plain` is the concept alt of `$inner`, which only `$Nested` reaches.
const NESTED: &str = "
(INPUT sides \"a side.\"
  (RULE &output
    (input *P *Col)))

(ALTS $reading \"how a side is found\" $First
  (ALT $Nested
    (ALTS $inner \"which side\" $Plain
      (ALT $Fancy
        (RULE &extra
          (input *P *Col))))))
";

#[test]
fn the_concept_alt_of_a_nested_point_is_no_departure() {
    assert_eq!(departures(NESTED, &["$First"]), Vec::<String>::new());
    assert_eq!(departures(NESTED, &["$Nested", "$Plain"]), ["$Nested"]);
    assert_eq!(departures(NESTED, &["$Nested", "$Fancy"]), ["$Nested", "$Fancy"]);
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
    let bound = verdict_of("(DET &d (ex_output *E) (&c E *Col))\n(RULE &output (input *P *Col) (&d Col))\n(OUT (&output ^P ^Col))");
    assert_eq!(bound, Verdict::Consistent);
    let unbound = verdict_of("(DET &d (ex_input *E) (&c E *Col))\n(RULE &output (input *P *Col) (&d Col))\n(OUT (&output ^P ^Col))");
    assert_ne!(unbound, Verdict::Consistent);
}
