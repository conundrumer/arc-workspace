//! The lib files under `engine/lib/` parse into a registry, so a fault of
//! either file fails the engine's tests.

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
