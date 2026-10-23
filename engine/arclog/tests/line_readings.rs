//! A `DET_OR_RULE` line splits only the cases whose forms read its relation,
//! and its derived reading by a proposer gives the relation the columns that
//! the proposer declares, as `docs/engine/cases.md#cases` and
//! `docs/arclog/arclog.md#the-alts-form` give.

use std::sync::Arc;

use arclog::check::{check_shared_program, CheckCache, SolverClauses};
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
