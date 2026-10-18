//! The column of a proposer written in arclog takes the type its clause
//! gives its label, so the type check refuses a read of it at a site of
//! another type; and the registry reader refuses a relation macro that
//! names one column twice.

use arclog::check::{check_program, CheckCache, CheckId, SolverClauses};
use arclog::diagnostic::DiagnosticKind;
use arclog::read::read_solver;
use arclog::registry::{Registry, PROPOSERS_TEXT, REGISTRY_TEXT};
use arclog::resolver::resolve;

/// The checks that refuse the concept program of `arclog`.
fn refusing_checks(arclog: &str) -> Vec<CheckId> {
    let solver = read_solver("rules", arclog, "", &|_| None).expect("the file reads").value;
    let registry = Registry::get();
    let program = resolve(&solver.concept_case().program, None, &solver.derived_relations(), registry).value;
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
fn a_color_of_an_arclog_proposer_at_a_number_site_is_refused() {
    let at = |site: &str| {
        format!(
            "
(RULE &cell
  (input *P *Col))

(DET &bg ChangedColor)

(RULE &out
  (&cell (:P *Q))
  (&bg *C)
  {site})
"
        )
    };
    let color = refusing_checks(&at("(input (:P Q) (:Col C))"));
    assert!(!color.contains(&CheckId::Types), "{color:?}");
    let number = refusing_checks(&at("(frame_extent (:P Q) (:A *A) (:N C))"));
    assert!(number.contains(&CheckId::Types), "{number:?}");
}

#[test]
fn a_relation_macro_that_names_a_column_twice_refuses() {
    let written = "(macro same_dist (columns (D D) (P1 P1) (P2 P2))";
    assert!(REGISTRY_TEXT.contains(written));
    let text = REGISTRY_TEXT.replacen(written, "(macro same_dist (columns (D D) (P1 P1) (P1 P2))", 1);
    let error = Registry::parse(&text, PROPOSERS_TEXT).err().expect("the column `P1` named twice refuses");
    let kinds: Vec<&DiagnosticKind> = error.diagnostics.iter().map(|d| &d.kind).collect();
    assert!(kinds.contains(&&DiagnosticKind::Check(CheckId::Scope)), "{:?}", error.diagnostics);
}
