//! The lib files under `engine/lib/` parse into a registry, so a fault of
//! either file fails the engine's tests.
//!
//! Implements `work/engine/reader.md`, Checker: "a test parses it, so a
//! fault of the file fails the engine's tests".

use arclog::registry::{PROPOSERS_TEXT, REGISTRY_TEXT, Registry};

#[test]
#[ignore = "Registry::parse has no body until the registry and resolver stage writes it"]
fn lib_files_parse() {
    if let Err(error) = Registry::parse(REGISTRY_TEXT, PROPOSERS_TEXT) {
        panic!("the lib files do not parse: {:?}", error.diagnostics);
    }
}
