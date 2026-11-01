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

#[test]
fn a_written_column_at_a_label_local_to_an_or_branch_refuses() {
    let written = "(macro same_dist (columns (D D Dir) (P1 P1 Box) (P2 P2 Box)) (modes (P1 P2))\n  (margin (:B *P1) *D *K)\n  (margin (:B *P2) D K))";
    assert!(REGISTRY_TEXT.contains(written));
    let local = "(macro same_dist (columns (D D Dir) (P1 P1 Box) (P2 P2 Box) (Z Z Box)) (modes (P1 P2))\n  (margin (:B *P1) *D *K)\n  (margin (:B *P2) D K)\n  (OR ((margin (:B *Z) D K)) ((margin (:B P1) D K))))";
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
fn a_read_of_an_input_port_in_a_macro_refuses() {
    let written = "(jump_offset *D *K *V)";
    assert!(REGISTRY_TEXT.contains(written));
    let text = REGISTRY_TEXT.replacen(written, "(self.node *D *K *V)", 1);
    assert!(Registry::parse(&text, PROPOSERS_TEXT).is_err());
}

/// The kinds of the diagnostics of the lib files with the `copies` form of Order's `minimal` replaced by `form`.
fn minimal_copies_kinds(form: &str) -> Vec<DiagnosticKind> {
    let written = "(copies (member (t t))))\n    (maximal";
    assert!(REGISTRY_TEXT.contains(written));
    let text = REGISTRY_TEXT.replacen(written, &format!("{form})\n    (maximal"), 1);
    let error = Registry::parse(&text, PROPOSERS_TEXT).err().expect("the form refuses");
    error.diagnostics.into_iter().map(|d| d.kind).collect()
}

#[test]
fn a_declared_row_that_the_component_does_not_support_refuses() {
    for form in [
        "(copies (nope (t t)))",
        "(copies (member (nope t)))",
        "(copies (member (t nope)))",
        "(copies (member (key key)))",
        "(copies (score (S t)))",
        "(copies (member (t t) (t t)))",
        "(copies (either (member (t t)) (probe)))",
    ] {
        assert_eq!(minimal_copies_kinds(form), [DiagnosticKind::Check(CheckId::Grammar)], "{form}");
    }
}
