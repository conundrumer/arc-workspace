//! The resolver refuses a `DET` that names a lib name the registry declares
//! no proposer of, such as `Division` or `PositionDomain`, as a name that
//! names nothing visible, and resolves a `DET` that names a type-domain
//! proposer.

use arclog::layout::SourceFile;
use arclog::read::read_arclog;
use arclog::registry::Registry;
use arclog::resolver::resolve;

/// The messages of the resolver's diagnostics of `text`.
fn resolver_messages(text: &str) -> Vec<String> {
    let read = read_arclog(text, SourceFile::Arclog).expect("the program reads");
    assert!(read.diagnostics.is_empty(), "{:?}", read.diagnostics);
    let (program, _) = read.value;
    let resolved = resolve(&program, None, &Default::default(), Registry::get());
    resolved.diagnostics.iter().map(|diagnostic| diagnostic.message.to_string()).collect()
}

#[test]
fn a_det_that_names_division_is_refused_as_an_unresolved_name() {
    let messages = resolver_messages("(DET &tiles Division)\n");
    assert_eq!(messages, ["`Division` names nothing visible here"]);
}

#[test]
fn a_det_that_names_position_domain_is_refused_as_an_unresolved_name() {
    let messages = resolver_messages("(DET &cells PositionDomain)\n");
    assert_eq!(messages, ["`PositionDomain` names nothing visible here"]);
}

#[test]
fn a_det_that_names_a_type_domain_proposer_resolves() {
    let messages = resolver_messages("(DET &axis AxisDomain)\n");
    assert!(messages.is_empty(), "{messages:?}");
}
