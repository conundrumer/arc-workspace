//! The diagnostic that the lint and the evaluator share.
//!
//! Implements `work/engine/reader.md`, Checker: "It reports each error once
//! per place in the file, with the cases it holds in." and Programs as
//! values: "An error at a node that stands in several places is reported at
//! each of them." The evaluator reports a run's faults, such as an
//! undetermined parameter or a reached bound, as the same type.

use crate::layout::SourcePlace;
use crate::solver::CaseName;

/// What a diagnostic reports: a check's refusal, a reached bound, or a fault
/// of a run.
///
/// Implements `work/engine/reader.md`, Checker: "It reports each error once per place in the file, with the cases it holds in."
#[derive(Clone, Copy, PartialEq, Eq, Hash, Debug)]
pub enum DiagnosticKind {
    Check(crate::check::CheckId),
    /// A bound reached, an alert, as Bounds gives.
    Bound,
    /// A fault of a run, reported by the evaluator.
    Run,
}

/// Whether a diagnostic refuses the program or is an alert on a bound.
///
/// Implements `work/engine/overview.md`, Requirements, Bounds: "A bound that is reached is an alert".
#[derive(Clone, Copy, PartialEq, Eq, Hash, Debug)]
pub enum Severity {
    Error,
    Alert,
}

/// One diagnostic: what it reports, at each place of the node in the files,
/// with the cases it holds in.
///
/// Implements `work/engine/reader.md`, Checker: "It reports each error once per place in the file, with the cases it holds in."
#[derive(Clone, PartialEq, Eq, Debug)]
pub struct Diagnostic {
    pub kind: DiagnosticKind,
    pub severity: Severity,
    pub message: Box<str>,
    pub places: Box<[SourcePlace]>,
    /// The cases in which the diagnostic holds. Empty for a diagnostic of a
    /// file or of a synthesized program, which has one case.
    pub cases: Box<[CaseName]>,
}
