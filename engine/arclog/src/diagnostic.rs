//! The diagnostic that the lint and the evaluator share. A diagnostic
//! reports an error once per place in the files, with the cases it holds
//! in, so an error at a node that stands in several places is reported at
//! each of them. The evaluator reports a run's faults, such as an
//! underdetermined parameter or a reached bound, as the same type.

use crate::layout::FilePlace;
use crate::program::path::NodePath;
use crate::solver::CaseName;

/// What a diagnostic reports: a check's refusal, a reached bound, or a fault
/// of a run.
#[derive(Clone, Copy, PartialEq, Eq, Hash, Debug)]
pub enum DiagnosticKind {
    Check(crate::check::CheckId),
    /// A bound reached: an alert, except the labeling bound
    /// ([`crate::program::canonical::LabelingBound`]), which is an error.
    Bound,
    /// A fault of a run, reported by the evaluator, or by the writer of a
    /// token stream.
    Run,
}

/// Whether a diagnostic refuses the program or is an alert on a bound. A
/// bound that is reached is an alert, not a refusal, except the labeling
/// bound, which refuses the form that passes it.
#[derive(Clone, Copy, PartialEq, Eq, Hash, Debug)]
pub enum Severity {
    Error,
    Alert,
}

/// A value with the diagnostics found as it was made: what a reader or the
/// resolver could make of its input, with the diagnostics of the rest.
#[derive(Clone, Debug)]
pub struct WithDiagnostics<T> {
    pub value: T,
    pub diagnostics: Vec<Diagnostic>,
}

/// Where a diagnostic stands. A diagnostic at a node that stands in several
/// places stands at each of them.
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
