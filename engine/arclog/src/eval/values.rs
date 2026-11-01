//! The values and the bounds of an evaluation: its caps, the other bounds
//! it can reach, the value of a relation or a grid on a request, a stop,
//! a fault of a run, the key columns of a keyed form's output rows, and the
//! flag that cancels evaluations. The driver and the parts of [`super`]
//! share them.

use std::sync::atomic::{AtomicBool, AtomicU64, Ordering};
use std::sync::{Arc, Mutex};
use std::time::Duration;

use crate::diagnostic::{Diagnostic, DiagnosticKind, Location, Severity};
use crate::hash::StableHashMap;
use crate::program::path::NodePath;
use crate::relations::Relation;
use crate::session::{ReachedSessionBound, ResultKey};
use crate::solver::CaseName;
use crate::task::Grid;
use crate::terms::ReachedMarginBound;

/// The caps of an evaluation, each a count, so none depends on the
/// machine.
#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub struct Caps {
    /// The bindings the join of one part of a body, a native construction,
    /// or a read's walk of a product of parts may try.
    pub bindings: u64,
    /// The rows one part of a body, or a native construction, may hold.
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
    /// The caps of every task session: the binding cap, the row cap, the
    /// node cap and the assignment cap are each set from the engine's counts
    /// on the corpus, and the model cap from the corpus survey's bound from
    /// Souffle's `out`.
    ///
    /// The binding cap and the row cap are each about twice the largest count
    /// of one evaluation that `arclog-cli speed` gave over `work/arclog/gen/`
    /// on 2026-10-19, in a run under a binding cap of `1 << 32` and a row cap of
    /// `1 << 24`: 474 894 549 bindings tried, of `c3fa4749`, and 995 900
    /// rows held, of `b71a7747`. Those counts are of the 798 solvers of 953
    /// that gave counts, each extreme of the corpus survey's runs among them.
    /// They leave out the outliers: `ac0c5833`, whose 1 956 915 734 bindings
    /// tried go with a Souffle run of 124 s, and `3ad05f52`, `c3f564a4` and
    /// `ca8f78db`, whose runs stopped at the row cap of `1 << 24`.
    ///
    /// The model cap is about twice 256, the largest count of the models of
    /// one case on one input that `arclog-cli row-counts` gave over the 18
    /// solvers of `work/arclog/gen/` with a `CHOOSE` form, on 2026-10-23, in
    /// runs under a model cap of `1 << 24`: 256 models of `&pruning`, of
    /// `b7cb93ac` on `train/2`. The `1 << 7` of 2026-10-19 was about twice 64,
    /// the bound of the models per case per input that
    /// `docs/engine/corpus-survey.md#open-values-and-constraint-search` gives
    /// from Souffle's `out`, which covers `a2d730bd` and `abc82100`, each two
    /// D4 parameters of 8 open values.
    ///
    /// The node cap is about twice the largest count of the same runs: at most
    /// 512 search nodes of one cluster, of `b7cb93ac` on `train/2`, which a
    /// run under `1 << 9` ends with no stop and a run under `1 << 8` stops. A
    /// cluster searches by the group with the fewest open options, one node
    /// per child, so its nodes are at least its models. The 17 other solvers
    /// with a `CHOOSE` form need at most 12.
    ///
    /// The assignment cap is the least power of two above twice the largest
    /// count that `arclog-cli determine` gave over the base cases of
    /// `work/arclog/gen/` on 2026-10-19, in a run under an assignment cap of
    /// `1 << 16`: 81 joint assignments of one case, of `d511f180`. Those
    /// counts are of the 939 solvers of 953 whose determination ran to its
    /// end before the run's bound of 30 minutes; the next largest are 72, of
    /// `ba26e723`, and 64, of `abc82100`.
    pub const CORPUS: Caps = Caps { bindings: 1 << 30, rows: 1 << 21, models: 1 << 9, nodes: 1 << 10, assignments: 1 << 8 };
}

/// The bound an evaluation reached.
#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub enum ReachedBound {
    Bindings { cap: u64 },
    Rows { cap: u64 },
    Models { cap: u64 },
    Nodes { cap: u64 },
    Assignments { cap: u64 },
    /// The bindings that all the evaluations of one table try, a stop of the
    /// table's walk.
    TableWork { cap: u64 },
    /// A Box with a margin outside a signed byte.
    Margin(ReachedMarginBound),
    SessionBytes(ReachedSessionBound),
    Deadline,
    Cancelled,
    /// A variable of a search's order that no node of the clause gives values
    /// at any place of the order. The search has no relation to give.
    NoValues,
}

impl ReachedBound {
    /// Whether the result cache stores a stop at this bound: a stop at the
    /// binding cap, the row cap, a margin or a variable with no values, which
    /// is the same at every later
    /// request of its entry. A stop at the session's byte bound, at the
    /// deadline or by a cancellation depends on the machine or the
    /// session's history, and is stored nowhere. A stop at the model cap,
    /// the node cap or the assignment cap is stored nowhere either. A stop
    /// at the table work cap, and a stop at the deadline, are held for the
    /// requests of one decode alone, in [`HeldStops`].
    pub fn is_stored(self) -> bool {
        match self {
            ReachedBound::Bindings { .. } | ReachedBound::Rows { .. } | ReachedBound::Margin(_) | ReachedBound::NoValues => true,
            ReachedBound::Models { .. }
            | ReachedBound::Nodes { .. }
            | ReachedBound::Assignments { .. }
            | ReachedBound::TableWork { .. }
            | ReachedBound::SessionBytes(_)
            | ReachedBound::Deadline
            | ReachedBound::Cancelled => false,
        }
    }

    /// The bound as a diagnostic's message describes it.
    fn describe(self) -> String {
        match self {
            ReachedBound::Bindings { cap } => format!("the binding cap of {cap} bindings"),
            ReachedBound::Rows { cap } => format!("the row cap of {cap} rows"),
            ReachedBound::Models { cap } => format!("the model cap of {cap} models"),
            ReachedBound::Nodes { cap } => format!("the node cap of {cap} search nodes"),
            ReachedBound::Assignments { cap } => format!("the assignment cap of {cap} joint assignments"),
            ReachedBound::TableWork { cap } => format!("the table work cap of {cap} bindings"),
            ReachedBound::Margin(reached) => format!("a Box margin outside a signed byte, {:?}", reached.margins),
            ReachedBound::SessionBytes(reached) => {
                format!("the session's byte bound of {} bytes, at {} bytes", reached.bound.bytes, reached.bytes)
            }
            ReachedBound::Deadline => "the deadline".to_owned(),
            ReachedBound::Cancelled => "a cancellation".to_owned(),
            ReachedBound::NoValues => "a variable that no node gives values".to_owned(),
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

/// The value of a sub-body of a clause, the conjuncts a caller keeps, on a
/// request: its rows, held as the product of its parts, `undefined`, or a
/// stop, as [`RelationValue`] gives them.
#[derive(Clone, Debug)]
pub struct BodyValue(pub RelationValue);

impl BodyValue {
    /// The count of the rows, the product of the parts' counts, or `None`
    /// where the value holds no rows.
    pub fn count(&self) -> Option<u64> {
        match &self.0 {
            RelationValue::Rows(relation) => Some(relation.len()),
            RelationValue::Undefined | RelationValue::Stopped(_) => None,
        }
    }

    /// Whether the value holds no row, since some part is empty, or `None`
    /// where the value holds no rows.
    pub fn is_empty(&self) -> Option<bool> {
        match &self.0 {
            RelationValue::Rows(relation) => Some(relation.is_empty()),
            RelationValue::Undefined | RelationValue::Stopped(_) => None,
        }
    }
}

/// The outcome of a request: a value, or a fault of the run.
pub type Outcome<T> = Result<T, RunFault>;

/// The grid of the `OUT` form's relation on one example: the grid, `undefined`, or a stop. A
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

/// The stops of the evaluations of a decode and its forks, each held by the
/// result-cache key of its entry, of two kinds, each with its own rule of
/// use. A stop at the table work cap is held for the tables of one case: a
/// table whose evaluation needs a held evaluation takes its stop, at the
/// form that stopped, and tries no binding for it. A stop at the deadline is
/// held with the time its evaluation ran: a later request takes it, at the
/// form that stopped, where the request has at most [`DEADLINE_STOP_REUSE`]
/// times that time left to its own deadline.
#[derive(Debug, Default)]
pub struct HeldStops {
    table_work: Mutex<StableHashMap<ResultKey, Stop>>,
    /// Shared with the snapshots: a stop at the deadline depends on the
    /// machine, so no fork's result depends on its history alone.
    deadline: Arc<Mutex<StableHashMap<ResultKey, DeadlineStop>>>,
}

/// The factor of the time a held stop at the deadline ran that a request's
/// time left may reach for the request to take the stop. Provisional: a
/// later request reaches the entry sooner than the first, whose upstream
/// entries it evaluated first and the later one finds in the result cache,
/// so a stop held at the time the first run had would rarely be taken.
pub const DEADLINE_STOP_REUSE: f64 = 1.1;

/// A stop at the deadline, with the time the evaluation that reached it ran.
#[derive(Clone, Debug)]
struct DeadlineStop {
    stop: Stop,
    ran: Duration,
}

impl HeldStops {
    /// The stop at the table work cap held for the entry `key`, if any.
    pub fn table_work_stop(&self, key: &ResultKey) -> Option<Stop> {
        self.table_work.lock().expect(UNPOISONED).get(key).cloned()
    }

    /// Holds `stop`, at the table work cap, for the entry `key`. The first
    /// stop held for a key stands.
    pub fn hold_table_work(&self, key: ResultKey, stop: Stop) {
        self.table_work.lock().expect(UNPOISONED).entry(key).or_insert(stop);
    }

    /// The stop at the deadline held for the entry `key`, where the request
    /// has `left` to its deadline and that is at most
    /// [`DEADLINE_STOP_REUSE`] times the time the stop's evaluation ran.
    pub fn deadline_stop(&self, key: &ResultKey, left: Duration) -> Option<Stop> {
        let held = self.deadline.lock().expect(UNPOISONED);
        let held = held.get(key)?;
        (left <= held.ran.mul_f64(DEADLINE_STOP_REUSE)).then(|| held.stop.clone())
    }

    /// Holds `stop`, at the deadline, for the entry `key`, with the time
    /// `ran` its evaluation ran. Where a stop is held for the key, the one
    /// with the larger time stands.
    pub fn hold_deadline(&self, key: ResultKey, stop: Stop, ran: Duration) {
        let mut held = self.deadline.lock().expect(UNPOISONED);
        if held.get(&key).is_none_or(|held| held.ran < ran) {
            held.insert(key, DeadlineStop { stop, ran });
        }
    }

    /// Whether no stop is held.
    pub fn is_empty(&self) -> bool {
        self.table_work.lock().expect(UNPOISONED).is_empty() && self.deadline.lock().expect(UNPOISONED).is_empty()
    }

    /// A store for a fork of a decode: it holds the stops at the table work
    /// cap that this one holds now, in a map of its own, so the tables of the
    /// fork depend on the fork's own history, and shares this one's stops at
    /// the deadline.
    pub fn snapshot(&self) -> HeldStops {
        HeldStops { table_work: Mutex::new(self.table_work.lock().expect(UNPOISONED).clone()), deadline: Arc::clone(&self.deadline) }
    }
}

const UNPOISONED: &str = "a store that no panic poisoned";

/// The bindings that the evaluations of one table try, counted over all its
/// examples, assignments, models and projections, and the rows that the
/// derivation of its extents visits, and the cap on the count. Clones share one
/// count.
#[derive(Clone, Debug)]
pub struct TableWork {
    count: Arc<AtomicU64>,
    cap: u64,
}

impl TableWork {
    /// A table with no bindings counted, under `cap`.
    pub fn new(cap: u64) -> Self {
        TableWork { count: Arc::new(AtomicU64::new(0)), cap }
    }

    /// Adds `bindings` to the count, and gives the stop once the count is past
    /// the cap. Each later call gives it too.
    pub fn charge(&self, bindings: u64) -> Result<(), ReachedBound> {
        let Ok(before) = self.count.try_update(Ordering::Relaxed, Ordering::Relaxed, |count| Some(count.saturating_add(bindings))) else {
            unreachable!("an update that always gives a count")
        };
        let count = before.saturating_add(bindings);
        if count > self.cap { Err(ReachedBound::TableWork { cap: self.cap }) } else { Ok(()) }
    }

    /// Whether the count is past the cap: each batch of an evaluation that
    /// begins now stops at once.
    pub fn is_past_cap(&self) -> bool {
        self.count.load(Ordering::Relaxed) > self.cap
    }

    /// The bindings counted so far.
    pub fn count(&self) -> u64 {
        self.count.load(Ordering::Relaxed)
    }

    /// Whether the count stays within the cap after `bindings` more.
    pub fn fits(&self, bindings: u64) -> bool {
        self.count().saturating_add(bindings) <= self.cap
    }
}

/// The bounds of one evaluation that differ between the evaluations of a
/// session: the deadline where it has one, its cancellation, the work
/// count of its table where it runs for a table, the stops held by the decode
/// it runs for, and whether it checks the declared rows of the outputs it
/// builds. The caps stand in the [`crate::session::TaskSession`].
#[derive(Clone, Debug)]
pub struct Limits {
    pub deadline: Option<std::time::Instant>,
    pub cancellation: Cancellation,
    /// The count that the evaluation's batches of bindings are added to.
    pub table_work: Option<TableWork>,
    /// The stops that the evaluations of the decode hold; none where the
    /// evaluation runs for no decode.
    pub held_stops: Option<Arc<HeldStops>>,
    /// Where the evaluation reports the declared rows that a construction's
    /// outputs break ([`crate::eval::copies`]); the evaluation checks none
    /// where this is `None`.
    pub copies: Option<super::copies::CopyViolations>,
}

impl Limits {
    /// The limits of an evaluation outside a table and outside a decode.
    pub fn new(deadline: Option<std::time::Instant>, cancellation: Cancellation) -> Self {
        Limits { deadline, cancellation, table_work: None, held_stops: None, copies: None }
    }

    /// These limits with the evaluation checking the declared rows of the
    /// outputs it builds, and reporting each violation to `violations`.
    pub fn checking_copies(self, violations: super::copies::CopyViolations) -> Self {
        Limits { copies: Some(violations), ..self }
    }

    /// These limits with the evaluation counted in `work`.
    pub fn counted_in(self, work: TableWork) -> Self {
        Limits { table_work: Some(work), ..self }
    }

    /// These limits with the evaluation taking and holding stops in `stops`.
    pub fn holding_in(self, stops: Arc<HeldStops>) -> Self {
        Limits { held_stops: Some(stops), ..self }
    }
}
