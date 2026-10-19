//! The values and the bounds of an evaluation: its caps, the other bounds
//! it can reach, the value of a relation or a grid on a request, a stop,
//! a fault of a run, the key columns of a keyed form's output rows, and the
//! flag that cancels evaluations. The driver and the parts of [`super`]
//! share them.

use std::sync::Arc;
use std::sync::atomic::{AtomicBool, Ordering};

use crate::diagnostic::{Diagnostic, DiagnosticKind, Location, Severity};
use crate::program::path::NodePath;
use crate::relations::Relation;
use crate::session::ReachedSessionBound;
use crate::solver::CaseName;
use crate::task::Grid;
use crate::terms::{Constant, ReachedMarginBound, Term, TermId};

/// The caps of an evaluation, each a count, so none depends on the
/// machine.
#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub struct Caps {
    /// The bindings a clause's join, or a native construction, may try.
    pub work: u64,
    /// The rows the parts of a relation may hold.
    pub rows: u64,
    /// The models of one case on one input.
    pub models: u64,
    /// The search nodes of one cluster of a pick.
    pub nodes: u64,
    /// The joint assignments of the `DET`s of one case that a determination
    /// tries, as `docs/engine/determination.md#det` gives.
    pub assignments: u64,
}

impl Caps {
    /// The caps of every task session: the work cap, the row cap and the node
    /// cap are each set from the engine's counts on the corpus, and the model
    /// cap from the corpus survey's bound from Souffle's `out`.
    ///
    /// The work cap and the row cap are each about twice the largest count
    /// of one evaluation that `arclog-cli speed` gave over `work/arclog/gen/`
    /// on 2026-10-19, in a run under a work cap of `1 << 32` and a row cap of
    /// `1 << 24`: 474 894 549 bindings tried, of `c3fa4749`, and 995 900
    /// rows held, of `b71a7747`. Those counts are of the 798 solvers of 953
    /// that gave counts, each extreme of the corpus survey's runs among them.
    /// They leave out the outliers: `ac0c5833`, whose 1 956 915 734 bindings
    /// tried go with a Souffle run of 124 s, and `3ad05f52`, `c3f564a4` and
    /// `ca8f78db`, whose runs stopped at the row cap of `1 << 24`.
    ///
    /// The node cap is about twice the largest count that `arclog-cli
    /// compare` gave over the concept cases of `work/arclog/gen/` on
    /// 2026-10-19, in a run under a model cap of 1 000 000 and a node cap of
    /// 10 000 000: 14 search nodes of one cluster, of `9f8de559`, whose
    /// largest count of models of one case on one input is 8, the largest of
    /// that run. Those counts are of the 840 solvers of 953 whose concept
    /// case ran to its end. Of the others, 88 stopped at a fault of the run
    /// or at the work cap or the row cap, 19 faulted before the run, and 6
    /// hold a `DEMONSTRATED` form, so are not compared. The counts leave out
    /// the outlier `97a05b5b`, whose 4 147 798 search nodes for its one model
    /// go with an engine run of 22.6 s against Souffle's 0.7 s.
    ///
    /// The model cap is about twice 64, the bound of the models per case per
    /// input that `docs/engine/corpus-survey.md#open-values-and-constraint-search`
    /// gives from Souffle's `out`. That bound covers `a2d730bd` and
    /// `abc82100`, each two D4 parameters of 8 open values, which give no
    /// count of their concept in the engine: `a2d730bd` stops at a fault of
    /// the run, and the rows of `abc82100` differ from its first relation on.
    ///
    /// The assignment cap is the provisional default of
    /// `docs/engine/determination.md#det`.
    pub const CORPUS: Caps = Caps { work: 1 << 30, rows: 1 << 21, models: 1 << 7, nodes: 1 << 5, assignments: 1000 };
}

/// The bound an evaluation reached.
#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub enum ReachedBound {
    Work { cap: u64 },
    Rows { cap: u64 },
    Models { cap: u64 },
    Nodes { cap: u64 },
    Assignments { cap: u64 },
    /// A Box with a margin outside a signed byte.
    Margin(ReachedMarginBound),
    SessionBytes(ReachedSessionBound),
    Deadline,
    Cancelled,
}

impl ReachedBound {
    /// Whether the result cache stores a stop at this bound: a stop at the
    /// work cap, the row cap or a margin, which is the same at every later
    /// request of its entry. A stop at the session's byte bound, at the
    /// deadline or by a cancellation depends on the machine or the
    /// session's history, and is stored nowhere. A stop at the model cap,
    /// the node cap or the assignment cap is stored nowhere either.
    pub fn is_stored(self) -> bool {
        match self {
            ReachedBound::Work { .. } | ReachedBound::Rows { .. } | ReachedBound::Margin(_) => true,
            ReachedBound::Models { .. }
            | ReachedBound::Nodes { .. }
            | ReachedBound::Assignments { .. }
            | ReachedBound::SessionBytes(_)
            | ReachedBound::Deadline
            | ReachedBound::Cancelled => false,
        }
    }

    /// The bound as a diagnostic's message describes it.
    fn describe(self) -> String {
        match self {
            ReachedBound::Work { cap } => format!("the work cap of {cap} bindings"),
            ReachedBound::Rows { cap } => format!("the row cap of {cap} rows"),
            ReachedBound::Models { cap } => format!("the model cap of {cap} models"),
            ReachedBound::Nodes { cap } => format!("the node cap of {cap} search nodes"),
            ReachedBound::Assignments { cap } => format!("the assignment cap of {cap} joint assignments"),
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
/// and no relation.
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

/// The key columns of the output rows of a keyed form, an `INIT` or a
/// `RIGID_DET` form: the key's columns where the form has a key clause, and
/// otherwise the one `Unit` column.
#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub(crate) enum OutputKey {
    /// A key clause of this many columns.
    Keyed(usize),
    Unit,
}

impl OutputKey {
    /// The key columns of a form with a key clause of `columns` columns, or
    /// with none where it is `None`.
    pub(crate) fn of(columns: Option<usize>) -> OutputKey {
        columns.map_or(OutputKey::Unit, OutputKey::Keyed)
    }

    /// The count of an output row's key columns.
    pub(crate) fn width(self) -> usize {
        match self {
            OutputKey::Keyed(columns) => columns,
            OutputKey::Unit => 1,
        }
    }

    /// The key columns of an output row at the key `key`, a row of the key
    /// clause's columns, empty for a form with no key clause.
    pub(crate) fn columns(self, key: &[TermId]) -> std::borrow::Cow<'_, [TermId]> {
        match self {
            OutputKey::Keyed(_) => key.into(),
            OutputKey::Unit => vec![Term::Constant(Constant::Unit).encode().expect("a Unit has a term id")].into(),
        }
    }
}
