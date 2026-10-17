//! The diagnostic that the lint and the evaluator share.
//!
//! Implements `work/engine/reader.md`, Checker: "It reports each error once
//! per place in the file, with the cases it holds in." and Programs as
//! values: "An error at a node that stands in several places is reported at
//! each of them." The evaluator reports a run's faults, such as an
//! undetermined parameter or a reached bound, as the same type.

use crate::layout::FilePlace;
use crate::program::path::NodePath;
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

/// A value with the diagnostics found as it was made. A reader or the
/// resolver gives what it could make of its input with the diagnostics of
/// the rest, so that the lint runs every check over the rest, as the Python
/// lint does, and reports each error the engine's checks find.
///
/// Implements `work/engine/reader.md`: "each error the lint reports from one of those checks, the engine reports at the same place".
#[derive(Clone, Debug)]
pub struct WithDiagnostics<T> {
    pub value: T,
    pub diagnostics: Vec<Diagnostic>,
}

/// Where a diagnostic stands.
///
/// Implements `work/engine/reader.md`, Programs as values: "An error at a node that stands in several places is reported at each of them."
#[derive(Clone, PartialEq, Eq, Debug)]
pub enum Location {
    /// Each place in the files of the node it reports on: the lint's, and
    /// a reader's.
    Places(Box<[FilePlace]>),
    /// The path of the node in a program that has no file, such as a
    /// synthesized program or a decode's prefix, which the token mask reads.
    Path(NodePath),
}

/// One diagnostic: what it reports, where, with the cases it holds in.
///
/// Implements `work/engine/reader.md`, Checker: "It reports each error once per place in the file, with the cases it holds in."
#[derive(Clone, PartialEq, Eq, Debug)]
pub struct Diagnostic {
    pub kind: DiagnosticKind,
    pub severity: Severity,
    pub message: Box<str>,
    pub location: Location,
    /// The cases in which the diagnostic holds. Empty for a diagnostic of a
    /// file or of a synthesized program, which has one case.
    pub cases: Box<[CaseName]>,
}
