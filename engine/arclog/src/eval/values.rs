//! The values and the bounds of an evaluation: its caps, the other bounds
//! it can reach, the value of a relation or a grid on a request, a stop,
//! a fault of a run, and the flag that cancels evaluations. The driver and
//! the parts of [`super`] share them.

use std::sync::Arc;
use std::sync::atomic::{AtomicBool, Ordering};

use crate::diagnostic::{Diagnostic, DiagnosticKind, Location, Severity};
use crate::program::path::NodePath;
use crate::relations::Relation;
use crate::session::ReachedSessionBound;
use crate::solver::CaseName;
use crate::task::Grid;
use crate::terms::ReachedMarginBound;

/// The two caps of an evaluation, both counts, so neither depends on the
/// machine. The task session holds them, so every evaluation in a session
/// runs at the same caps, and a stop at either that the result cache
/// stores holds for every later request of the same entry in the session.
#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub struct Caps {
    /// The bindings a clause's join, or a native construction, may try.
    pub work: u64,
    /// The rows the parts of a relation may hold.
    pub rows: u64,
}

impl Caps {
    /// The caps of every task session, set from the engine's counts on the
    /// corpus.
    pub const PROVISIONAL: Caps = Caps { work: 1 << 32, rows: 1 << 24 };
}

/// The bound an evaluation reached.
#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub enum ReachedBound {
    Work { cap: u64 },
    Rows { cap: u64 },
    /// A Box with a margin outside a signed byte.
    Margin(ReachedMarginBound),
    SessionBytes(ReachedSessionBound),
    Deadline,
    Cancelled,
}

impl ReachedBound {
    /// Whether a stop at this bound is the same at every later request of
    /// its entry, so the result cache stores it: a stop at a cap or at a
    /// margin. A stop at the session's byte bound, at the deadline or by a
    /// cancellation depends on the machine or the session's history, and is
    /// stored nowhere.
    pub fn is_stored(self) -> bool {
        match self {
            ReachedBound::Work { .. } | ReachedBound::Rows { .. } | ReachedBound::Margin(_) => true,
            ReachedBound::SessionBytes(_) | ReachedBound::Deadline | ReachedBound::Cancelled => false,
        }
    }

    /// The bound as a diagnostic's message names it.
    fn describe(self) -> String {
        match self {
            ReachedBound::Work { cap } => format!("the work cap of {cap} bindings"),
            ReachedBound::Rows { cap } => format!("the row cap of {cap} rows"),
            ReachedBound::Margin(reached) => format!("a Box margin outside a signed byte, {:?}", reached.margins),
            ReachedBound::SessionBytes(reached) => {
                format!("the session's byte bound of {} bytes, at {} bytes", reached.bound.bytes, reached.bytes)
            }
            ReachedBound::Deadline => "the deadline".to_owned(),
            ReachedBound::Cancelled => "a cancellation".to_owned(),
        }
    }
}

/// An evaluation that reached a bound: the bound, and the form of the
/// clause, the instance or the assembly that reached it. A stop is an alert
/// and no relation, so the case gives no output on the input it stopped
/// on.
#[derive(Clone, PartialEq, Eq, Debug)]
pub struct Stop {
    pub bound: ReachedBound,
    /// The path in the case program of the form that reached the bound.
    pub form: NodePath,
}

impl Stop {
    /// The stop as a diagnostic of kind
    /// [`crate::diagnostic::DiagnosticKind::Bound`], an alert at the form's
    /// path, in `cases`.
    pub fn diagnostic(&self, cases: &[CaseName]) -> Diagnostic {
        Diagnostic {
            kind: DiagnosticKind::Bound,
            severity: Severity::Alert,
            message: format!("the evaluation of the form reached {}", self.bound.describe()).into(),
            location: Location::Path(self.form.clone()),
            cases: cases.into(),
        }
    }
}

/// A fault of a run that is no bound, such as a parameter whose stored
/// rows its column types cannot read, or a lib name that the table of
/// constructions lacks.
#[derive(Clone, PartialEq, Eq, Debug)]
pub struct RunFault {
    pub message: Box<str>,
    /// The path in the case program of the form the fault stands at.
    pub form: NodePath,
}

impl RunFault {
    /// The fault as a diagnostic of kind
    /// [`crate::diagnostic::DiagnosticKind::Run`], an error at the form's
    /// path, in `cases`.
    pub fn diagnostic(&self, cases: &[CaseName]) -> Diagnostic {
        Diagnostic {
            kind: DiagnosticKind::Run,
            severity: Severity::Error,
            message: self.message.clone(),
            location: Location::Path(self.form.clone()),
            cases: cases.into(),
        }
    }
}

/// The value of a relation on a request: its rows, `undefined` where it
/// reads a relation that no block of the case derives
/// (`docs/arclog/arclog.md#alts`), or a stop `S`. An evaluation gives a
/// [`Stop`], at a form of its own program; a result-cache entry holds the
/// [`ReachedBound`] alone, since programs that share the entry hold its
/// clause at different paths.
#[derive(Clone, Debug)]
pub enum RelationValue<S = Stop> {
    Rows(Arc<Relation>),
    Undefined,
    Stopped(S),
}

impl<S> RelationValue<S> {
    /// This value, with `stop` of its stop in the place of the stop.
    pub fn map_stop<T>(self, stop: impl FnOnce(S) -> T) -> RelationValue<T> {
        match self {
            RelationValue::Rows(relation) => RelationValue::Rows(relation),
            RelationValue::Undefined => RelationValue::Undefined,
            RelationValue::Stopped(s) => RelationValue::Stopped(stop(s)),
        }
    }
}

/// The outcome of a request: a value, or a fault of the run.
pub type Outcome<T> = Result<T, RunFault>;

/// The grid of `&output` on one example: the grid, `undefined`, or a stop. A
/// grid is undefined where the relation is, and where
/// `docs/arclog/constraints.md#the-output-set` gives.
#[derive(Clone, Debug)]
pub enum GridValue {
    Grid(Grid),
    Undefined,
    Stopped(Stop),
}

/// A flag that cancels the evaluations that share it. Clones share one
/// flag.
#[derive(Clone, Debug, Default)]
pub struct Cancellation(Arc<AtomicBool>);

impl Cancellation {
    /// Cancels each evaluation that holds this flag. An evaluation checks the
    /// flag per batch of bindings and stops with
    /// [`ReachedBound::Cancelled`].
    pub fn cancel(&self) {
        self.0.store(true, Ordering::Relaxed);
    }

    /// Whether [`Cancellation::cancel`] has been called on the flag.
    pub fn is_cancelled(&self) -> bool {
        self.0.load(Ordering::Relaxed)
    }
}

/// The bounds of one evaluation that differ between the evaluations of a
/// session: the deadline where it has one, and its cancellation. The caps
/// stand in the [`crate::session::TaskSession`].
#[derive(Clone, Debug)]
pub struct Limits {
    pub deadline: Option<std::time::Instant>,
    pub cancellation: Cancellation,
}
