//! The lib files under `engine/lib/` parse into a registry, so a fault of
//! either file fails the engine's tests.

use arclog::check::CheckId;
use arclog::diagnostic::DiagnosticKind;
use arclog::registry::{PROPOSERS_TEXT, REGISTRY_TEXT, Registry};

#[test]
fn lib_files_parse() {
    if let Err(error) = Registry::parse(REGISTRY_TEXT, PROPOSERS_TEXT) {
        panic!("the lib files do not parse: {:?}", error.diagnostics);
    }
}

#[test]
fn a_site_at_an_undeclared_column_refuses() {
    let written = "(jump_offset *D *K *V)";
    assert!(REGISTRY_TEXT.contains(written));
    let text = REGISTRY_TEXT.replacen(written, "(jump_offset (:Dir *D) *K *V)", 1);
    assert!(Registry::parse(&text, PROPOSERS_TEXT).is_err());
}

/// Division's `&whole_side` with an `OR` whose first branch makes `Z`, which
/// the later branch does not name.
fn with_branch_local_label() -> String {
    let written = "    (axis_of *D A)\n    (axis_inset D (:K1 0) (:K2 0) (:B *P_whole))";
    assert!(REGISTRY_TEXT.contains(written));
    let local = "    (axis_of *D A)\n    (OR ((self.parts (:key Ky) A (:N *Z))) ((axis_of D A)))\n    (axis_inset D (:K1 0) (:K2 0) (:B *P_whole))";
    REGISTRY_TEXT.replacen(written, local, 1)
}

#[test]
fn a_label_local_to_an_or_branch_of_a_rule_is_no_column() {
    if let Err(error) = Registry::parse(&with_branch_local_label(), PROPOSERS_TEXT) {
        panic!("the rule with a branch-local label does not parse: {:?}", error.diagnostics);
    }
}

#[test]
fn a_read_of_a_rule_at_a_branch_local_label_is_a_site_at_an_undeclared_column() {
    let read = "((&whole_side Ky A) (frame_extent";
    let text = with_branch_local_label();
    assert!(text.contains(read));
    let text = text.replacen(read, "((&whole_side Ky A (:Z *W)) (frame_extent", 1);
    let error = Registry::parse(&text, PROPOSERS_TEXT).err().expect("a read at `Z` refuses");
    let kinds: Vec<&DiagnosticKind> = error.diagnostics.iter().map(|d| &d.kind).collect();
    assert_eq!(kinds, [&DiagnosticKind::Check(CheckId::SiteColumns)], "{:?}", error.diagnostics);
}

/// Connectivity's `INIT` of Quotient, whose `edge` input writes the head
/// columns `a` and `b`, as Quotient declares them.
const QUOTIENT_EDGE: &str = "(edge ((:a Ky P) (:b Ky (:P Q)))";

#[test]
fn an_init_input_its_component_does_not_declare_refuses() {
    assert!(REGISTRY_TEXT.contains(QUOTIENT_EDGE));
    let text = REGISTRY_TEXT.replacen(QUOTIENT_EDGE, "(edgex ((:a Ky P) (:b Ky (:P Q)))", 1);
    assert!(Registry::parse(&text, PROPOSERS_TEXT).is_err());
}

#[test]
fn an_init_head_site_at_an_undeclared_column_refuses() {
    assert!(REGISTRY_TEXT.contains(QUOTIENT_EDGE));
    let text = REGISTRY_TEXT.replacen(QUOTIENT_EDGE, "(edge ((:zz Ky P) (:b Ky (:P Q)))", 1);
    assert!(Registry::parse(&text, PROPOSERS_TEXT).is_err());
}

#[test]
fn a_written_column_at_a_label_local_to_an_or_branch_refuses() {
    let written = "(macro same_dist (columns (D D) (P1 P1) (P2 P2))\n  (margin (:B *P1) *D *K)\n  (margin (:B *P2) D K))";
    assert!(REGISTRY_TEXT.contains(written));
    let local = "(macro same_dist (columns (D D) (P1 P1) (P2 P2) (Z Z))\n  (margin (:B *P1) *D *K)\n  (margin (:B *P2) D K)\n  (OR ((margin (:B *Z) D K)) ((margin (:B P1) D K))))";
    let text = REGISTRY_TEXT.replacen(written, local, 1);
    let error = Registry::parse(&text, PROPOSERS_TEXT).err().expect("a column at `Z` refuses");
    let kinds: Vec<&DiagnosticKind> = error.diagnostics.iter().map(|d| &d.kind).collect();
    assert_eq!(kinds, [&DiagnosticKind::Check(CheckId::Scope)], "{:?}", error.diagnostics);
}

/// The kinds of the diagnostics of the lib files with the arclog proposer
/// form of `ChangedPairs` replaced by `form`.
fn changed_pairs_kinds(form: &str) -> Vec<DiagnosticKind> {
    let written = "(proposer ChangedPairs arclog (columns C_from C_to))";
    assert!(REGISTRY_TEXT.contains(written));
    let text = REGISTRY_TEXT.replacen(written, form, 1);
    let error = Registry::parse(&text, PROPOSERS_TEXT).err().expect("the form refuses");
    error.diagnostics.into_iter().map(|d| d.kind).collect()
}

#[test]
fn an_arclog_proposer_that_names_no_columns_refuses() {
    for form in ["(proposer ChangedPairs arclog)", "(proposer ChangedPairs arclog (columns))"] {
        assert_eq!(changed_pairs_kinds(form), [DiagnosticKind::Check(CheckId::Scope)], "{form}");
    }
}

#[test]
fn an_arclog_proposer_column_its_clause_does_not_keep_refuses() {
    let kinds = changed_pairs_kinds("(proposer ChangedPairs arclog (columns C_from Z))");
    assert_eq!(kinds, [DiagnosticKind::Check(CheckId::Scope)]);
}

#[test]
fn an_arclog_proposer_column_named_twice_refuses() {
    let kinds = changed_pairs_kinds("(proposer ChangedPairs arclog (columns C_from C_from))");
    assert_eq!(kinds, [DiagnosticKind::Check(CheckId::Scope)]);
}

#[test]
fn a_type_fault_of_an_init_binding_gives_the_diagnostics_of_the_init_form_alone() {
    let edits = [
        ("(OR ((self.node (:key *Ky) *P) (= *Q P))", "(OR ((self.node (:key *Ky) *P) (axis_elem (:A P)) (= *Q P))", "the label at `P` of the `INIT` form"),
        ("(source ((:n Origin)))", "(source ((:n Origin)) (axis_elem (:A Origin)))", "the label at `n` of the `INIT` form"),
        ("(self.dir (:key Ky) ^D))", "(self.dir (:key Ky) ^D) (axis_elem (:A D)))", "the label at `D` of the `INIT` form"),
    ];
    for (written, edited, init_label) in edits {
        assert!(REGISTRY_TEXT.contains(written));
        let text = REGISTRY_TEXT.replacen(written, edited, 1);
        let error = Registry::parse(&text, PROPOSERS_TEXT).err().expect("a binding whose type has a fault refuses");
        let messages: Vec<&str> = error.diagnostics.iter().map(|d| &*d.message).collect();
        assert!(messages.iter().all(|m| !m.contains("stands at no site that gives a type")), "{messages:?}");
        assert!(messages.iter().any(|m| m.contains(init_label)), "{messages:?}");
    }
}
