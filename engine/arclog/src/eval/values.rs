//! The values and the bounds of an evaluation: its caps, the other bounds
//! it can reach, the value of a relation or a grid on a request, a stop,
//! a fault of a run, the key columns of a keyed form's output rows, and the
//! flag that cancels evaluations. The driver and the parts of [`super`]
//! share them.

use std::sync::atomic::{AtomicBool, AtomicU64, Ordering};
use std::cell::{Cell, RefCell};
use std::sync::{Arc, Mutex};

use crate::diagnostic::{Diagnostic, DiagnosticKind, Location, Severity};
use crate::hash::StableHashMap;
use crate::program::path::NodePath;
use crate::relations::Relation;
use crate::session::{Counts, ResultKey, TaskSession};
use crate::solver::CaseName;
use crate::task::Grid;
use crate::terms::ReachedMarginBound;

/// The caps of one query's evaluation, independent of the machine. A query
/// evaluates a clause, finished or in progress, on one example at one
/// assignment. No cap here sums the evaluations of a program: the request
/// work cap does ([`RequestWork`]).
#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub struct Caps {
    /// The content one evaluation may count: the rows that the join of one
    /// part of a body or a native construction reads and writes, or that a
    /// read's walk of a product of parts visits ([`super::join::Budget::charge_content`]).
    /// The bindings a search tries are no part of it: the effort guard of the
    /// request counts them ([`RequestWork::charge_effort`]).
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
    /// The binding cap counts content now (the rows an evaluation reads and
    /// writes), and the values below were set from counts of bindings tried,
    /// so they stand until the cap audit sets them again from the content
    /// counts of the gold programs.
    ///
    /// The caps of every task session: the binding cap, the row cap, the
    /// node cap and the assignment cap are each set from the engine's counts
    /// on the corpus, and the model cap from the corpus survey's bound from
    /// Souffle's `out`.
    ///
    /// The binding cap and the row cap are each the least power of two at or
    /// above twice the largest count of one query, finished or in progress, at
    /// an assignment that solves the train pairs, over the concept cases of
    /// `work/arclog/gen/`. Over the train tasks, `corpus_tables` with `bodies`
    /// gave on 2026-11-04 3 276 242 bindings tried and 3 240 000 rows held, of
    /// `&mirror_mismatch` of `47996f11` in progress. Past the train tasks, a
    /// finished query of `a395ee82` reaches 13 832 382 bindings tried, which
    /// sets the binding cap. Over the train tasks, a finished query reaches
    /// 851 286 bindings tried, of `50846271`, and 360 576 rows held, of
    /// `1d0a4b61`, as `arclog-cli speed` gave them. A query at an assignment
    /// that solves no train pair goes far past them: 35 820 150 248 bindings
    /// tried, of `94133066`.
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
    pub const CORPUS: Caps = Caps { bindings: 1 << 25, rows: 1 << 23, models: 1 << 9, nodes: 1 << 10, assignments: 1 << 8 };
}

/// The bound an evaluation reached.
#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub enum ReachedBound {
    Bindings { cap: u64 },
    Rows { cap: u64 },
    Models { cap: u64 },
    Nodes { cap: u64 },
    Assignments { cap: u64 },
    /// The work budget of an observation. `assignment` holds where the count
    /// was one assignment's own ([`TableWork::scoped`]), so that the stop rejects
    /// that assignment alone.
    TableWork { cap: u64, assignment: bool },
    /// A Box with a margin outside a signed byte.
    Margin(ReachedMarginBound),
    /// The work cap of one request, summed over every query and walk of it
    /// ([`RequestWork`]).
    RequestWork { cap: u64 },
    /// The byte budget of one request: the bytes that the request holds at
    /// a time ([`RequestWork::charge_bytes`]).
    RequestBytes { cap: u64 },
    /// The byte budget of one assignment: the bytes that the assignment holds
    /// at a time ([`TableWork::charge_bytes`]).
    AssignmentBytes { cap: u64 },
    Cancelled,
    /// A variable of a search's order that no node of the clause gives values
    /// at any place of the order. The search has no relation to give.
    NoValues,
    /// The effort guard of one request: the bindings that its searches tried
    /// ([`RequestWork::charge_effort`]). It stops a runaway search and is a
    /// fault of the call, never a result: the call raises
    /// `arclog.EffortExhausted` ([`take_effort_fault`]).
    Effort { cap: u64 },
}

impl ReachedBound {
    /// The cap of this bound, where it has one.
    pub fn cap(self) -> Option<u64> {
        match self {
            Self::Bindings { cap }
            | Self::Rows { cap }
            | Self::Models { cap }
            | Self::Nodes { cap }
            | Self::Assignments { cap }
            | Self::TableWork { cap, .. }
            | Self::RequestWork { cap }
            | Self::RequestBytes { cap }
            | Self::AssignmentBytes { cap }
            | Self::Effort { cap } => Some(cap),
            Self::Margin(_) | Self::Cancelled | Self::NoValues => None,
        }
    }

    /// Whether this bound rejects only the assignment being evaluated: the
    /// binding, row, model and node caps, a Box margin, a variable with no
    /// values, a stop at the table work cap of one assignment's own count
    /// ([`TableWork::scoped`]), and a stop at the byte budget of one
    /// assignment ([`TableWork::charge_bytes`]). The request work cap, the
    /// request byte budget, the assignment cap, a cancellation and every
    /// other stop at the table work cap end the walk.
    pub fn is_assignment(self) -> bool {
        match self {
            Self::Bindings { .. } | Self::Rows { .. } | Self::Margin(_) | Self::NoValues | Self::Models { .. } | Self::Nodes { .. } | Self::AssignmentBytes { .. } => true,
            Self::TableWork { assignment, .. } => assignment,
            Self::Assignments { .. } | Self::RequestWork { .. } | Self::RequestBytes { .. } | Self::Cancelled | Self::Effort { .. } => false,
        }
    }

    /// Whether this bound is a budget of the request: its work cap, its
    /// byte budget or its effort guard. Each charge after the request passes
    /// one stops too.
    pub fn is_request(self) -> bool {
        matches!(self, Self::RequestWork { .. } | Self::RequestBytes { .. } | Self::Effort { .. })
    }

    /// Whether this bound limits the time, the rows or the bytes of an
    /// evaluation, and so establishes no property of the program that the
    /// evaluation is of: a prefix check that it stops leaves its decision to
    /// the form's end. The assignment cap, a margin, a variable with no values,
    /// a cancellation and the effort guard are no such bound.
    pub fn is_resource(self) -> bool {
        matches!(
            self,
            Self::Bindings { .. }
                | Self::Rows { .. }
                | Self::Models { .. }
                | Self::Nodes { .. }
                | Self::TableWork { .. }
                | Self::RequestWork { .. }
                | Self::RequestBytes { .. }
                | Self::AssignmentBytes { .. }
        )
    }

    /// Whether this bound stops a query that grew past a cap on its size.
    pub fn is_size(self) -> bool {
        matches!(self, Self::Bindings { .. } | Self::Rows { .. })
    }

    /// Whether a stop of an extent derivation leaves the table's rows complete.
    pub fn is_annotation(self) -> bool {
        self.is_assignment() || matches!(self, Self::TableWork { .. })
    }

    /// Whether the result cache stores a stop at this bound: a stop at the
    /// binding cap, the row cap, a margin or a variable with no values, which
    /// is the same at every later
    /// request of its entry. A stop by a cancellation depends on the caller,
    /// and is stored nowhere. A stop at the model cap, the node cap or the assignment cap is
    /// stored nowhere either, and neither is a stop at the request work cap,
    /// which depends on the work the request did before the entry, and so is
    /// a stop at the request byte budget or at the byte budget of an
    /// assignment, which depend on the bytes charged before the entry. A stop at
    /// the table work cap is held for the requests of one decode alone, in
    /// [`HeldStops`], where the count is no assignment's own.
    pub fn is_stored(self) -> bool {
        match self {
            ReachedBound::Bindings { .. } | ReachedBound::Rows { .. } | ReachedBound::Margin(_) | ReachedBound::NoValues => true,
            ReachedBound::Models { .. }
            | ReachedBound::Nodes { .. }
            | ReachedBound::Assignments { .. }
            | ReachedBound::TableWork { .. }
            | ReachedBound::RequestWork { .. }
            | ReachedBound::RequestBytes { .. }
            | ReachedBound::AssignmentBytes { .. }
            | ReachedBound::Effort { .. }
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
            ReachedBound::TableWork { cap, .. } => format!("the table work cap of {cap} bindings"),
            ReachedBound::Margin(reached) => format!("a Box margin outside a signed byte, {:?}", reached.margins),
            ReachedBound::RequestWork { cap } => format!("the request work cap of {cap} units of work"),
            ReachedBound::RequestBytes { cap } => format!("the request byte budget of {cap} bytes held"),
            ReachedBound::AssignmentBytes { cap } => format!("the assignment byte budget of {cap} bytes held"),
            ReachedBound::Cancelled => "a cancellation".to_owned(),
            ReachedBound::NoValues => "a variable that no node gives values".to_owned(),
            ReachedBound::Effort { cap } => format!("the effort guard of {cap} bindings tried"),
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
/// result-cache key of its entry. A table-work stop is read only by a bounded
/// observation: one that needs that evaluation takes the stop at its form
/// without trying bindings.
#[derive(Debug, Default)]
pub struct HeldStops {
    table_work: Mutex<StableHashMap<ResultKey, Stop>>,
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

    /// Whether no stop is held.
    pub fn is_empty(&self) -> bool {
        self.table_work.lock().expect(UNPOISONED).is_empty()
    }

    /// A store for a fork of a decode: it holds the stops at the table work
    /// cap that this one holds now, in a map of its own, so the tables of the
    /// fork depend on the fork's own history.
    pub fn snapshot(&self) -> HeldStops {
        HeldStops { table_work: Mutex::new(self.table_work.lock().expect(UNPOISONED).clone()) }
    }
}

const UNPOISONED: &str = "a store that no panic poisoned";

/// The default cap of a request's work, in units of work
/// ([`RequestWork`]). Provisional: `docs/engine/synthesis.md#decode-settings`
/// gives how it is to be set from the work of the gold programs' requests.
pub const REQUEST_WORK_CAP: u64 = 1 << 30;

/// The default effort guard of a request, in bindings tried
/// ([`RequestWork::charge_effort`]). It stops a runaway search and no result
/// depends on it, so it stands far above the bindings that any gold program's
/// request tries: 16 times the request work cap that the bindings once
/// counted against. Provisional: the effort of the gold programs' requests,
/// which `request_stats()` gives as the gauge `effort`, sets it.
pub const EFFORT_CAP: u64 = 1 << 34;

/// The default cap on the content that one prefix check counts: the rows it
/// reads and writes, and the rows its joins hold as they produce them. A
/// check that passes it stops, and its token is admitted, since the cap
/// establishes no property of the program: the form's end decides.
/// Provisional until the cap audit; far below the request work cap.
pub const PREFIX_CONTENT_CAP: u64 = 1 << 18;

/// The fault of a request that passed its effort guard.
#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub struct EffortFault {
    /// The gauge that passed its cap: [`Gauge::Effort`].
    pub gauge: Gauge,
    pub cap: u64,
}

/// Where the requests begun on one thread leave their effort fault, for the
/// call on that thread to raise ([`take_effort_fault`]).
type FaultSink = Mutex<Option<EffortFault>>;

thread_local! {
    /// The sink of the requests begun on this thread ([`RequestWork::begin_with`]).
    /// A worker thread takes the sink of the thread that started it
    /// ([`adopt_fault_sink`]).
    static SINK: RefCell<Arc<FaultSink>> = RefCell::new(Arc::default());
}

/// The sink that the requests begun on this thread leave their effort fault
/// in.
fn current_sink() -> Arc<FaultSink> {
    SINK.with(|sink| Arc::clone(&sink.borrow()))
}

/// The sink of the thread that calls it, for the workers that run its work
/// to adopt ([`adopt_fault_sink`]).
#[derive(Clone, Debug)]
pub struct FaultSinkHandle(Arc<FaultSink>);

/// The sink of the requests begun on this thread, to hand to the workers of a
/// call on this thread.
pub fn fault_sink() -> FaultSinkHandle {
    FaultSinkHandle(current_sink())
}

/// Makes the requests begun on this thread leave their effort fault in the
/// sink of `handle`. A worker of a call calls it first, so the fault of a request it
/// begins reaches the thread that made the call ([`take_effort_fault`]).
pub fn adopt_fault_sink(handle: &FaultSinkHandle) {
    SINK.with(|sink| *sink.borrow_mut() = Arc::clone(&handle.0));
}

/// The effort fault that a request begun on this thread left since the last
/// call of this function, and clears it. A call from Python into the engine
/// asks after it ends, and raises `arclog.EffortExhausted` where this gives a
/// fault, in place of giving the result of the call: the stop of the effort
/// guard is a fault, never a result.
pub fn take_effort_fault() -> Option<EffortFault> {
    let sink = current_sink();
    let fault = sink.lock().unwrap_or_else(std::sync::PoisonError::into_inner).take();
    fault
}

/// The bindings tried by the searches of a request, and whether they passed
/// the guard. The candidates of a call share them with the request.
#[derive(Debug, Default)]
struct Effort {
    count: AtomicU64,
    exhausted: AtomicBool,
}

/// The count of [`Gauge`]s.
const GAUGES: usize = 21;

/// A capped quantity of a request, which [`Gauges`] keeps the largest value of
/// and the hits at.
#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub enum Gauge {
    /// The work of the request ([`RequestWork`]).
    RequestWork,
    /// The count of one observation, under the table work cap.
    TableWork,
    /// The bindings of one evaluation, under the binding cap.
    Bindings,
    /// The rows of one evaluation, under the row cap.
    Rows,
    /// The joint assignments of one walk, under the assignment cap.
    Assignments,
    /// The models of one enumeration, under the model cap.
    Models,
    /// The nodes of one constraint search, under the node cap.
    Nodes,
    /// The rows of one projection read, under the projection cap.
    ProjectionRows,
    /// The steps of one completion search of an input's head, under the step
    /// bound of the search.
    ProjectionSteps,
    /// The bytes of the session at a check, under the session's byte bound,
    /// at which the session evicts its caches. A study request runs under its
    /// own bound (`TABLE_BYTES`), which the gauge reports as its cap. The
    /// gauge has no hits: the bound stops nothing.
    SessionBytes,
    /// The bindings of the rows of one table of a study request that skips
    /// the tables a larger one made too large, under `TABLE_ROW_WORK`.
    StudyRowWork,
    /// The row comparisons of one study pair, under the table work cap of the
    /// settings.
    PairComparisons,
    /// The rows of the larger of two relations that a comparison of successor
    /// tables reads row by row, under `COMPARED_ROWS`.
    ComparedRows,
    /// The largest margin of a Box that a term holds, as the bits it takes
    /// (a margin `m` takes `m` for `m >= 0` and `-m - 1` for `m < 0`), under
    /// the 127 that a signed byte holds. The count is of the process, from
    /// the begin of the latest request ([`ambient`]).
    BoxMargin,
    /// The states that the walk of `Decoder::candidate_atoms` checked, under
    /// its `limit`.
    AtomStates,
    /// The most bytes that a request held at a time
    /// ([`RequestWork::charge_bytes`]), under the request byte budget.
    RequestBytes,
    /// The most bytes that one assignment held at a time
    /// ([`TableWork::charge_bytes`]), under the assignment byte budget.
    AssignmentBytes,
    /// The search nodes of the canonical labeling of one label scope, under
    /// [`crate::program::canonical::SEARCH_NODE_CAP`]. A search past the cap
    /// is a hit, and refuses its form
    /// ([`crate::program::canonical::LabelingBound`]). The count is of the
    /// process, from the begin of the latest request ([`ambient`]).
    LabelingNodes,
    /// The bindings that the searches of the request tried
    /// ([`RequestWork::charge_effort`]), under the effort guard. A hit raises
    /// `arclog.EffortExhausted`.
    Effort,
    /// The content that the prefix check of an admitted `DET` counted, under
    /// the prefix content cap ([`PREFIX_CONTENT_CAP`]). A hit is a check left
    /// open: the token is admitted and the form's end decides.
    PrefixContent,
    /// The work of the search for the order of the tied columns of one table at
    /// one assignment, in units (a cell hashed is a unit, a search node is
    /// 2^18), under the search work cap
    /// (`arclog_tables::summary::SEARCH_WORK_CAP`). A search past the cap is a
    /// hit: the table at that assignment has no TableHash, and its reason is
    /// `ColumnSearch`. The count is of the request that ran the search.
    ColumnSearch,
}

impl Gauge {
    /// Each gauge, in the order of [`Gauges::each`].
    pub const ALL: [Gauge; GAUGES] = [
        Gauge::RequestWork,
        Gauge::TableWork,
        Gauge::Bindings,
        Gauge::Rows,
        Gauge::Assignments,
        Gauge::Models,
        Gauge::Nodes,
        Gauge::ProjectionRows,
        Gauge::ProjectionSteps,
        Gauge::SessionBytes,
        Gauge::StudyRowWork,
        Gauge::PairComparisons,
        Gauge::ComparedRows,
        Gauge::BoxMargin,
        Gauge::AtomStates,
        Gauge::RequestBytes,
        Gauge::AssignmentBytes,
        Gauge::LabelingNodes,
        Gauge::Effort,
        Gauge::PrefixContent,
        Gauge::ColumnSearch,
    ];

    /// The gauge's name, which is stable.
    pub fn name(self) -> &'static str {
        match self {
            Gauge::RequestWork => "request_work",
            Gauge::TableWork => "table_work",
            Gauge::Bindings => "bindings",
            Gauge::Rows => "rows",
            Gauge::Assignments => "assignments",
            Gauge::Models => "models",
            Gauge::Nodes => "nodes",
            Gauge::ProjectionRows => "projection_rows",
            Gauge::ProjectionSteps => "projection_steps",
            Gauge::SessionBytes => "session_bytes",
            Gauge::StudyRowWork => "study_row_work",
            Gauge::PairComparisons => "pair_comparisons",
            Gauge::ComparedRows => "compared_rows",
            Gauge::BoxMargin => "box_margin",
            Gauge::AtomStates => "atom_states",
            Gauge::RequestBytes => "request_bytes",
            Gauge::AssignmentBytes => "assignment_bytes",
            Gauge::LabelingNodes => "labeling_nodes",
            Gauge::Effort => "effort",
            Gauge::PrefixContent => "prefix_content",
            Gauge::ColumnSearch => "column_search_work",
        }
    }
}

/// For each [`Gauge`], the largest value that a request's quantity reached,
/// its cap, and how often it hit the cap. A note is a load and a compare while
/// the value is no new largest, and each caller notes once per batch or once
/// per evaluation, never per binding or row.
#[derive(Debug, Default)]
pub struct Gauges {
    slots: [GaugeSlot; GAUGES],
}

#[derive(Debug, Default)]
struct GaugeSlot {
    max: AtomicU64,
    cap: AtomicU64,
    hits: AtomicU64,
}

impl Gauges {
    fn slot(&self, gauge: Gauge) -> &GaugeSlot {
        &self.slots[gauge as usize]
    }

    /// Records that `gauge` reached `value` under `cap`.
    #[inline]
    pub fn note(&self, gauge: Gauge, value: u64, cap: u64) {
        let slot = self.slot(gauge);
        if value > slot.max.load(Ordering::Relaxed) {
            slot.max.fetch_max(value, Ordering::Relaxed);
        }
        if slot.cap.load(Ordering::Relaxed) != cap {
            slot.cap.store(cap, Ordering::Relaxed);
        }
    }

    /// Records that `gauge` reached `value`, which passes `cap`: a hit.
    #[cold]
    pub fn hit(&self, gauge: Gauge, value: u64, cap: u64) {
        self.note(gauge, value, cap);
        self.slot(gauge).hits.fetch_add(1, Ordering::Relaxed);
    }

    /// The largest value, the cap and the hits of each gauge, in the order of
    /// [`Gauge::ALL`]. A cap of 0 is one that the request never gave.
    pub fn each(&self) -> [(Gauge, u64, u64, u64); GAUGES] {
        Gauge::ALL.map(|gauge| {
            if gauge == Gauge::BoxMargin {
                let (largest, hits) = ambient::margin();
                return (gauge, largest, ambient::MARGIN_CAP, hits);
            }
            if gauge == Gauge::LabelingNodes {
                let (largest, hits) = ambient::labeling();
                return (gauge, largest, ambient::LABELING_CAP, hits);
            }
            let slot = self.slot(gauge);
            (gauge, slot.max.load(Ordering::Relaxed), slot.cap.load(Ordering::Relaxed), slot.hits.load(Ordering::Relaxed))
        })
    }
}

/// The counters of caps that a computation meets where no [`Limits`] are at
/// hand, which the process keeps from the begin of the latest request
/// ([`RequestWork::begin`]) to the next. A request that runs while another
/// begins, on another thread of the process, shares them with it.
pub mod ambient {
    use std::sync::atomic::{AtomicU32, AtomicU64, Ordering};

    /// The largest margin extent that a signed byte holds, which the Box
    /// margin bound is ([`super::Gauge::BoxMargin`]).
    pub const MARGIN_CAP: u64 = 127;

    /// The cap on the search nodes of one canonical labeling
    /// ([`super::Gauge::LabelingNodes`]).
    pub const LABELING_CAP: u64 = crate::program::canonical::SEARCH_NODE_CAP as u64;

    static LARGEST_MARGIN: AtomicU32 = AtomicU32::new(0);
    static MARGIN_HITS: AtomicU64 = AtomicU64::new(0);
    static LARGEST_LABELING: AtomicU32 = AtomicU32::new(0);
    static LABELING_HITS: AtomicU64 = AtomicU64::new(0);

    /// Records the margin `extent` of a Box that a term packs: two compares
    /// while it is no new largest and holds.
    #[inline]
    pub fn note_margin(extent: u32) {
        if extent > LARGEST_MARGIN.load(Ordering::Relaxed) {
            LARGEST_MARGIN.fetch_max(extent, Ordering::Relaxed);
        }
        if u64::from(extent) > MARGIN_CAP {
            MARGIN_HITS.fetch_add(1, Ordering::Relaxed);
        }
    }

    /// The largest margin extent and the count of Boxes past the bound.
    pub fn margin() -> (u64, u64) {
        (u64::from(LARGEST_MARGIN.load(Ordering::Relaxed)), MARGIN_HITS.load(Ordering::Relaxed))
    }

    /// Records that a search for a canonical labeling visited `nodes` search
    /// nodes: two compares while it is no new largest and holds.
    #[inline]
    pub fn note_labeling(nodes: u32) {
        if nodes > LARGEST_LABELING.load(Ordering::Relaxed) {
            LARGEST_LABELING.fetch_max(nodes, Ordering::Relaxed);
        }
        if u64::from(nodes) > LABELING_CAP {
            LABELING_HITS.fetch_add(1, Ordering::Relaxed);
        }
    }

    /// The most search nodes of one labeling search and the count of searches
    /// past the cap.
    pub fn labeling() -> (u64, u64) {
        (u64::from(LARGEST_LABELING.load(Ordering::Relaxed)), LABELING_HITS.load(Ordering::Relaxed))
    }

    /// Starts the counters again from zero.
    pub fn reset() {
        LARGEST_MARGIN.store(0, Ordering::Relaxed);
        MARGIN_HITS.store(0, Ordering::Relaxed);
        LARGEST_LABELING.store(0, Ordering::Relaxed);
        LABELING_HITS.store(0, Ordering::Relaxed);
    }
}

/// The count of the work of one request, a call from a caller into a decoder
/// or a study evaluator, summed over every query, walk and observation the
/// request runs, and its cap, with the [`Gauges`] of its other caps. A unit of
/// work is one binding that a join tries, one row that a walk, a
/// materialization or an index build visits, or one step of a walk of joint
/// assignments, as `docs/engine/synthesis.md#decode-settings` lists.
///
/// The count is a plain sum of the charges. A thread's charges come in an
/// order that the calls alone decide, and the count and the place where it
/// passes the cap do not depend on the machine's speed. The count is the
/// work the request would do with every cache empty: a hit in the result
/// cache, in a memo or in a kept computation charges the [`Cost`] recorded
/// in its entry, which is what the entry's computation charged, so the count
/// does not depend on what the caches held, nor on which thread filled an
/// entry first. Where the recorded cost would not fit under the cap, the hit
/// is no hit: the entry is computed again, and the computation stops at the
/// charge that a computation with empty caches stops at
/// ([`Cost::fits`]). Clones share the count.
#[derive(Clone, Debug)]
pub struct RequestWork {
    count: Arc<AtomicU64>,
    cap: u64,
    /// The bytes that the request holds now ([`RequestWork::charge_bytes`]),
    /// and the budgets they run under.
    bytes: Arc<ByteAccount>,
    byte_caps: ByteCaps,
    gauges: Arc<Gauges>,
    /// The bindings that the request's searches tried, and the guard on them.
    effort: Arc<Effort>,
    effort_cap: u64,
    /// Where the request leaves its effort fault.
    sink: Arc<FaultSink>,
}

/// The default budget of the bytes one request holds at a time
/// ([`RequestWork::charge_bytes`]). Provisional: `docs/engine/synthesis.md#decode-settings`
/// gives how it is to be set from the bytes that the gold programs' requests
/// hold.
pub const REQUEST_BYTES_CAP: u64 = 1 << 32;

/// The default budget of the bytes one assignment holds at a time
/// ([`TableWork::charge_bytes`]). Provisional, as [`REQUEST_BYTES_CAP`] is.
pub const ASSIGNMENT_BYTES_CAP: u64 = 1 << 31;

/// The default budget of the bytes the request of one candidate of a call holds
/// at a time ([`RequestWork::candidate`]). Provisional, as [`REQUEST_BYTES_CAP`]
/// is: the most bytes that one candidate's evaluation and export hold on the
/// gold programs, with a margin, is to set it.
pub const CANDIDATE_BYTES_CAP: u64 = 1 << 31;

/// The byte budgets a request runs under: the request's own, that of each
/// assignment of a table walk in it, and that of the request of each candidate
/// of a call that evaluates several.
#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub struct ByteCaps {
    pub request: u64,
    pub assignment: u64,
    pub candidate: u64,
}

impl Default for ByteCaps {
    fn default() -> Self {
        ByteCaps { request: REQUEST_BYTES_CAP, assignment: ASSIGNMENT_BYTES_CAP, candidate: CANDIDATE_BYTES_CAP }
    }
}

/// The bytes held in one account, the request's or one assignment's.
#[derive(Debug, Default)]
pub(crate) struct ByteAccount {
    held: AtomicU64,
    /// The part of `held` that an allocation of the session owns and frees when
    /// it drops ([`Owner`]).
    owned: AtomicU64,
    /// Whether the account has been past its budget. Each later acquire gives
    /// the stop too, and no hit fits.
    stopped: AtomicBool,
}

/// What an acquire of bytes in a [`ByteAccount`] gave.
enum Acquired {
    /// The account holds `held` bytes, within its budget.
    Within(u64),
    /// The account holds `held` bytes, past its budget, or was past it before;
    /// `first` holds for the acquire that took it past.
    Past { held: u64, first: bool },
}

impl ByteAccount {
    fn acquire(&self, bytes: u64, cap: u64) -> Acquired {
        let before = if bytes == 0 { self.held.load(Ordering::Relaxed) } else { self.held.fetch_add(bytes, Ordering::Relaxed) };
        let held = before.saturating_add(bytes);
        if held > cap {
            Acquired::Past { held, first: !self.stopped.swap(true, Ordering::Relaxed) }
        } else if self.stopped.load(Ordering::Relaxed) {
            Acquired::Past { held, first: false }
        } else {
            Acquired::Within(held)
        }
    }

    fn release(&self, bytes: u64) {
        if bytes > 0 {
            let _ = self.held.fetch_update(Ordering::Relaxed, Ordering::Relaxed, |held| Some(held.saturating_sub(bytes)));
        }
    }

    fn fits(&self, peak: u64, cap: u64) -> bool {
        !self.stopped.load(Ordering::Relaxed) && self.held.load(Ordering::Relaxed).saturating_add(peak) <= cap
    }

    fn held(&self) -> u64 {
        self.held.load(Ordering::Relaxed)
    }

    fn is_stopped(&self) -> bool {
        self.stopped.load(Ordering::Relaxed)
    }
}

/// The bytes that one assignment holds, and the most it may hold.
#[derive(Debug)]
pub(crate) struct AssignmentBytes {
    account: ByteAccount,
    cap: u64,
    /// The gauges that the assignment's bytes are noted in.
    gauges: Arc<Gauges>,
}

impl AssignmentBytes {
    /// Notes the bytes held in the gauge, and gives the stop where an acquire
    /// passed the budget.
    fn reached(&self, acquired: Acquired) -> Result<(), ReachedBound> {
        match acquired {
            Acquired::Within(held) => {
                self.gauges.note(Gauge::AssignmentBytes, held, self.cap);
                Ok(())
            }
            Acquired::Past { held, first } => {
                if first {
                    self.gauges.hit(Gauge::AssignmentBytes, held, self.cap);
                } else {
                    self.gauges.note(Gauge::AssignmentBytes, held, self.cap);
                }
                Err(ReachedBound::AssignmentBytes { cap: self.cap })
            }
        }
    }
}

/// The handle with which an allocation of the session frees the bytes it owns
/// in the accounts of the request and of the assignment that held them, when
/// it drops or gives some back.
#[derive(Debug)]
pub(crate) struct Owner {
    request: Arc<ByteAccount>,
    assignment: Option<Arc<AssignmentBytes>>,
}

impl Owner {
    pub(crate) fn free(&self, bytes: u64) {
        let bytes = bytes.min(1 << 50);
        let own = |account: &ByteAccount| {
            account.release(bytes);
            let _ = account.owned.fetch_update(Ordering::Relaxed, Ordering::Relaxed, |owned| Some(owned.saturating_sub(bytes)));
        };
        own(self.request.as_ref());
        if let Some(assignment) = &self.assignment {
            own(&assignment.account);
        }
    }
}

/// The units that every request of the process has charged ([`RequestWork::total`]).
static TOTAL: AtomicU64 = AtomicU64::new(0);

thread_local! {
    /// The depth of the [`uncounted`] scopes open on this thread.
    static UNCOUNTED: Cell<u32> = const { Cell::new(0) };
    /// The request most recently begun on this thread ([`RequestWork::begin`]).
    static LATEST: RefCell<Option<RequestWork>> = const { RefCell::new(None) };
    /// What this thread charges, for the costs of entries ([`Tally`]).
    static TALLY: RefCell<Tally> = const { RefCell::new(Tally { frames: Vec::new(), unbilled: 0 }) };
}

/// Runs `run` with the sums that cut results turned off on this thread: a
/// charge to the request's work ([`RequestWork::charge`]) or to an
/// observation's count ([`TableWork::charge`]) adds to neither, and adds
/// nothing to the effort of the request either, which counts the bindings that
/// searches try ([`RequestWork::charge_effort`]), and no cost fits or misfits
/// against them. The measurements open still record the charges, so
/// the cost of an entry that `run` computes is what it is anywhere, and a
/// later hit on it, outside, charges that cost.
///
/// The mask of a decode runs its prefix checks in this scope: their work
/// depends on the forms that the decode has finished, which are no part of the
/// form that a count is the count of, so no count that cuts a result holds it.
/// The one count that adds in the scope is the prefix check's own
/// ([`TableWork::prefix`]), which caps the content of that check and whose
/// stop admits the token.
/// The scope passes to the tasks that [`super::pool::Pool::map`] runs.
pub fn uncounted<T>(run: impl FnOnce() -> T) -> T {
    struct Close;
    impl Drop for Close {
        fn drop(&mut self) {
            UNCOUNTED.with(|depth| depth.set(depth.get().saturating_sub(1)));
        }
    }
    UNCOUNTED.with(|depth| depth.set(depth.get() + 1));
    let _close = Close;
    run()
}

/// Whether this thread runs in an [`uncounted`] scope.
pub fn is_uncounted() -> bool {
    UNCOUNTED.with(|depth| depth.get() > 0)
}

/// What a thread has charged, for the cost of an entry ([`Cost`]).
///
/// An entry is computed on one thread, which runs no task of the pool while
/// it computes (`super::pool`), so the charges of an entry are the charges
/// that its thread makes between its begin and its end, and a tally for each
/// thread gives the cost of an entry when several threads share a request.
struct Tally {
    /// The measurements open on the thread ([`RequestWork::measure`]), the
    /// innermost last.
    frames: Vec<Frame>,
    /// The rows that index builds on this thread walked, for which no call had
    /// a request at hand ([`RequestWork::note_unbilled`]).
    unbilled: u64,
}

/// One open measurement.
struct Frame {
    /// The identity of the request that the measurement counts the charges
    /// to.
    request: usize,
    /// The rows that were unbilled when the measurement began, which belong
    /// to the work around it.
    held: u64,
    /// The account of the assignment whose bytes the measurement counts, once
    /// it counts any ([`TableWork::charge_bytes`]).
    assignment: Option<Arc<AssignmentBytes>>,
    cost: Cost,
}

fn tally<R>(with: impl FnOnce(&mut Tally) -> R) -> R {
    TALLY.with(|tally| with(&mut tally.borrow_mut()))
}

/// Notes in the innermost open measurement the `bindings` that a batch charged
/// to the observation's count, whichever count the evaluation has.
pub(crate) fn tally_table(bindings: u64) {
    tally(|tally| {
        if let Some(top) = tally.frames.last_mut() {
            top.cost.table = top.cost.table.saturating_add(bindings);
        }
    });
}

/// Notes in the innermost open measurement the account of the assignment that
/// holds its bytes, so that the measurement frees them there when it ends. A
/// measurement frees the bytes in the first assignment that holds any.
fn note_assignment(account: &Arc<AssignmentBytes>) {
    tally(|tally| {
        if let Some(top) = tally.frames.last_mut() {
            top.assignment.get_or_insert_with(|| Arc::clone(account));
        }
    });
}

/// Notes in the innermost open measurement the largest bindings and rows of
/// an evaluation that ended, as its [`Gauges`] hold them.
pub(crate) fn tally_gauges(bindings: u64, rows: u64) {
    tally(|tally| {
        if let Some(top) = tally.frames.last_mut() {
            top.cost.bindings = top.cost.bindings.max(bindings);
            top.cost.rows = top.cost.rows.max(rows);
        }
    });
}

/// Notes in the innermost open measurement the counts that a session recorded
/// ([`TaskSession::record_counts`]).
pub(crate) fn tally_counts(counts: Counts) {
    tally(|tally| {
        if let Some(top) = tally.frames.last_mut() {
            top.cost.counts.bindings = top.cost.counts.bindings.max(counts.bindings);
            top.cost.counts.rows = top.cost.counts.rows.max(counts.rows);
        }
    });
}

/// The bytes that a computation holds, counted from its start: the most it
/// held at a time, and what it still holds at its end.
#[derive(Clone, Copy, PartialEq, Eq, Debug, Default)]
pub struct ByteSpan {
    pub peak: u64,
    pub net: u64,
}

impl ByteSpan {
    /// The computation allocates `bytes`, which it holds.
    fn acquire(&mut self, bytes: u64) {
        self.net = self.net.saturating_add(bytes);
        self.peak = self.peak.max(self.net);
    }

    /// The computation frees `bytes` that it held.
    fn release(&mut self, bytes: u64) {
        self.net = self.net.saturating_sub(bytes);
    }

    /// The computation holds `bytes` more for a moment and frees them.
    fn transient(&mut self, bytes: u64) {
        self.peak = self.peak.max(self.net.saturating_add(bytes));
    }

    /// The computation runs `inner` as a part of it, from where it stands.
    fn absorb(&mut self, inner: ByteSpan) {
        self.peak = self.peak.max(self.net.saturating_add(inner.peak));
        self.net = self.net.saturating_add(inner.net);
    }
}

/// What the computation of an entry charged, which a hit on the entry charges
/// again: the units in the request, the bindings in the observation's count,
/// the bytes it held, and the largest counts that its evaluations noted. A
/// cost includes the costs of the entries that the computation read, so it is
/// the cost of the computation with every cache empty. It is a function of the
/// entry alone. A hit holds the bytes that the entry's value holds ([`ByteSpan::net`]),
/// after it checks the budgets against the most the computation held
/// ([`ByteSpan::peak`]).
#[derive(Clone, Copy, PartialEq, Eq, Debug, Default)]
pub struct Cost {
    /// The units of work charged to the request.
    pub request: u64,
    /// The bindings charged to the observation's count.
    pub table: u64,
    /// The bytes held, under the request's byte budget
    /// ([`RequestWork::charge_bytes`]) and under the byte budget of the
    /// assignment where the computation ran in one ([`TableWork::charge_bytes`]).
    /// A cost holds them whether or not the computation ran in an assignment,
    /// so a hit holds them in any.
    pub bytes: ByteSpan,
    /// The largest bindings and rows that an evaluation noted in the request's
    /// gauges.
    bindings: u64,
    rows: u64,
    /// The largest counts that the session recorded.
    counts: Counts,
}

impl Cost {
    /// This cost with no units for the request and none for the observation's
    /// count: the cost of a computation that no count which cuts a result
    /// holds ([`uncounted`]), whose hit charges its bytes alone.
    pub fn without_counts(self) -> Cost {
        Cost { request: 0, table: 0, ..self }
    }

    /// Adds what a computation inside the one this cost counts charged.
    fn absorb(&mut self, inner: &Cost, same_request: bool) {
        if same_request {
            self.request = self.request.saturating_add(inner.request);
            self.bytes.absorb(inner.bytes);
        }
        self.table = self.table.saturating_add(inner.table);
        self.bindings = self.bindings.max(inner.bindings);
        self.rows = self.rows.max(inner.rows);
        self.counts.bindings = self.counts.bindings.max(inner.counts.bindings);
        self.counts.rows = self.counts.rows.max(inner.counts.rows);
    }

    /// Whether `request` and `table`, the observation's count where there is
    /// one, stay within their caps and byte budgets after this cost. A hit
    /// whose cost does not fit is no hit: the caller computes the entry again,
    /// and the computation stops at the charge that a computation with empty
    /// caches stops at. The bytes count against `assignment`, the observation
    /// whose assignment budget they belong to.
    fn fits(&self, request: &RequestWork, table: Option<&TableWork>, assignment: Option<&TableWork>) -> bool {
        (is_uncounted() || request.count().saturating_add(self.request) <= request.cap())
            && request.fits_bytes(self.bytes.peak)
            && table.is_none_or(|table| (is_uncounted() && !table.counts_uncounted()) || table.fits(self.table))
            && assignment.is_none_or(|work| work.fits_bytes(self.bytes.peak))
    }

    /// Charges this cost for a hit: the units and the bytes to `request`, the
    /// bindings to `table`, the bytes to `assignment`, and the counts to the
    /// gauges of `request` and to `session`. The rows and the bytes of index
    /// builds that wait for a charge stay waiting for the next one, as they do
    /// around a computation.
    fn charge(&self, request: &RequestWork, table: Option<&TableWork>, assignment: Option<&TableWork>, session: &TaskSession) -> Result<(), ReachedBound> {
        let held = tally(|tally| std::mem::take(&mut tally.unbilled));
        tally_table(self.table);
        let charged = request
            .charge(self.request)
            .and_then(|()| request.charge_hit_bytes(self.bytes))
            .and_then(|()| table.map_or(Ok(()), |table| table.charge(self.table)))
            .and_then(|()| assignment.map_or(Ok(()), |work| work.charge_hit_bytes(self.bytes)));
        let caps = session.caps;
        request.gauges().note(Gauge::Bindings, self.bindings, caps.bindings);
        request.gauges().note(Gauge::Rows, self.rows, caps.rows);
        tally_gauges(self.bindings, self.rows);
        session.record_counts(self.counts);
        tally(|tally| tally.unbilled = tally.unbilled.saturating_add(held));
        charged
    }
}

/// A value that a cache holds, with the [`Cost`] that its computation charged.
///
/// The value comes out of a hit only through [`Hit::charge`] or
/// [`Hit::charge_if`], which charge the cost again, so a caller cannot use a
/// cached value and leave its cost out of the counts. `Cost::fits` and
/// `Cost::charge` are private to this module for the same reason. A caller
/// that has no request to charge says so with [`Hit::without_request`].
#[derive(Clone, Debug)]
pub struct Hit<T> {
    value: T,
    cost: Cost,
}

/// What charging a [`Hit`] gave.
#[derive(Debug)]
pub enum Charged<T> {
    /// The cost fit under the caps and was charged: the value.
    Value(T),
    /// The cost was charged and took a count past its cap: the value, and the
    /// stop.
    Stopped(T, ReachedBound),
    /// The cost would take a count past its cap, or the entry could not be
    /// replayed, so the hit is no hit and nothing was charged: the caller
    /// computes the entry, and its charges stop where they stop with every
    /// cache empty.
    Misfit,
}

impl<T> Charged<T> {
    /// The value, where the hit was charged, whether or not the charge took a
    /// count past its cap, and `None` for a misfit.
    pub fn value(self) -> Option<T> {
        match self {
            Charged::Value(value) | Charged::Stopped(value, _) => Some(value),
            Charged::Misfit => None,
        }
    }
}

impl<T> Hit<T> {
    /// `value`, whose computation charged `cost`.
    pub fn new(value: T, cost: Cost) -> Self {
        Hit { value, cost }
    }

    /// What the computation of the value charged.
    pub fn cost(&self) -> Cost {
        self.cost
    }

    /// The value held, for the record of a lookup that charges no cost.
    pub(crate) fn recorded(&self) -> &T {
        &self.value
    }

    /// Charges the cost to `request`, to `table` where there is one, and to
    /// `session`, as [`Cost::charge`] does, where the cost fits under the caps.
    pub fn charge(self, request: &RequestWork, table: Option<&TableWork>, session: &TaskSession) -> Charged<T> {
        self.charge_if(request, table, session, || true)
    }

    /// [`Hit::charge`] where the cost fits and `admit`, which runs after the
    /// fit is known and before the charge, gives true.
    pub fn charge_if(self, request: &RequestWork, table: Option<&TableWork>, session: &TaskSession, admit: impl FnOnce() -> bool) -> Charged<T> {
        self.charge_if_in(request, table, table, session, admit)
    }

    /// [`Hit::charge_if`], where the bindings count in `table` and the bytes
    /// in `assignment`, which are one count except where a kept computation
    /// that stopped at the table work cap charges its bindings as the crossing
    /// gives them.
    pub fn charge_if_in(self, request: &RequestWork, table: Option<&TableWork>, assignment: Option<&TableWork>, session: &TaskSession, admit: impl FnOnce() -> bool) -> Charged<T> {
        if !self.cost.fits(request, table, assignment) || !admit() {
            return Charged::Misfit;
        }
        match self.cost.charge(request, table, assignment, session) {
            Ok(()) => Charged::Value(self.value),
            Err(bound) => Charged::Stopped(self.value, bound),
        }
    }

    /// The value, for a lookup made where no request counts work.
    pub fn without_request(self) -> T {
        self.value
    }
}

/// Pops the measurement that [`RequestWork::measure`] opened, where its
/// computation panicked.
struct Unwind(bool);

impl Drop for Unwind {
    fn drop(&mut self) {
        if self.0 {
            let _ = TALLY.try_with(|tally| {
                if let Ok(mut tally) = tally.try_borrow_mut()
                    && let Some(frame) = tally.frames.pop()
                {
                    tally.unbilled = frame.held;
                }
            });
        }
    }
}

impl RequestWork {
    /// A count of no work, under `cap` and the default byte budgets.
    pub fn new(cap: u64) -> Self {
        Self::with_byte_caps(cap, ByteCaps::default())
    }

    /// A count of no work and no bytes, under `cap` and the byte budgets
    /// `byte_caps`.
    pub fn with_byte_caps(cap: u64, byte_caps: ByteCaps) -> Self {
        RequestWork { count: Arc::new(AtomicU64::new(0)), cap, bytes: Arc::default(), byte_caps, gauges: Arc::default(), effort: Arc::default(), effort_cap: EFFORT_CAP, sink: current_sink() }
    }

    /// This count with the effort guard `effort_cap` in place of
    /// [`EFFORT_CAP`].
    pub fn with_effort_cap(self, effort_cap: u64) -> Self {
        RequestWork { effort_cap, ..self }
    }

    /// A count of no work for a request that begins now, under `cap`, which
    /// [`RequestWork::latest`] gives on this thread until another request
    /// begins on it.
    pub fn begin(cap: u64) -> Self {
        Self::begin_with(cap, ByteCaps::default())
    }

    /// [`RequestWork::begin`], under the byte budgets `byte_caps`.
    pub fn begin_with(cap: u64, byte_caps: ByteCaps) -> Self {
        Self::begin_capped(cap, byte_caps, EFFORT_CAP)
    }

    /// [`RequestWork::begin_with`], under the effort guard `effort_cap`.
    pub fn begin_capped(cap: u64, byte_caps: ByteCaps, effort_cap: u64) -> Self {
        let work = Self::with_byte_caps(cap, byte_caps).with_effort_cap(effort_cap);
        ambient::reset();
        tally(|tally| tally.unbilled = 0);
        LATEST.with(|latest| *latest.borrow_mut() = Some(work.clone()));
        work
    }

    /// A count of no work and no bytes for one candidate of a call that
    /// evaluates several, such as the successors of a decode, under the same
    /// work cap and with the same gauges, and with the byte budget of a
    /// candidate ([`ByteCaps::candidate`]) in place of the request's. The
    /// candidate's charges are not added to this count, and its stop at a cap
    /// ends its own evaluations alone.
    pub fn candidate(&self) -> Self {
        RequestWork { count: Arc::new(AtomicU64::new(0)), cap: self.cap, bytes: Arc::default(), byte_caps: ByteCaps { request: self.byte_caps.candidate, ..self.byte_caps }, gauges: Arc::clone(&self.gauges), effort: Arc::clone(&self.effort), effort_cap: self.effort_cap, sink: Arc::clone(&self.sink) }
    }

    /// The request most recently begun on this thread, or `None` where none
    /// has begun.
    pub fn latest() -> Option<RequestWork> {
        LATEST.with(|latest| latest.borrow().clone())
    }

    /// The units that the requests of this process have charged since it
    /// started, on every thread: the sum of their counts.
    pub fn total() -> u64 {
        TOTAL.load(Ordering::Relaxed)
    }

    /// Adds `units` to the count, and gives the stop once the count is past
    /// the cap. Each later call gives it too, so a request that reached the
    /// cap stops at each charge after it.
    ///
    /// The add is one relaxed `fetch_add` and a comparison. A call comes once
    /// for each batch of 1024 bindings or rows, beside the byte-bound check
    /// ([`super::join::Budget::charge_work`]) and the table work count, which
    /// cost more.
    #[inline]
    pub fn charge(&self, units: u64) -> Result<(), ReachedBound> {
        let key = self.key();
        let (units, unbilled) = tally(|tally| {
            // The rows of index builds that waited for a charge are effort: which indexes a search builds depends on its order.
            let unbilled = std::mem::take(&mut tally.unbilled);
            // Past 2^40 a charge is past every cap, and the clamp keeps the sum of a request's charges from wrapping.
            let units = units.min(1 << 40);
            if units > 0
                && let Some(top) = tally.frames.last_mut()
                && top.request == key
            {
                top.cost.request = top.cost.request.saturating_add(units);
            }
            (units, unbilled)
        });
        self.charge_effort(unbilled)?;
        // The units are content, or the content that a hit recorded: they try no binding, so they add to no count here, and the effort has only the bindings that searches try ([`RequestWork::charge_effort`]).
        if is_uncounted() {
            return Ok(());
        }
        // A check that adds nothing reads the count alone.
        let count = if units == 0 {
            self.count.load(Ordering::Relaxed)
        } else {
            TOTAL.fetch_add(units, Ordering::Relaxed);
            self.count.fetch_add(units, Ordering::Relaxed).saturating_add(units)
        };
        if count > self.cap {
            // The charge that takes the count past the cap is the one hit.
            if count - units <= self.cap {
                self.gauges.hit(Gauge::RequestWork, count, self.cap);
            }
            Err(ReachedBound::RequestWork { cap: self.cap })
        } else {
            Ok(())
        }
    }

    /// Adds `bindings` to the effort of the request, and gives the stop once
    /// the effort is past the guard. Each later call gives it too, whatever it
    /// adds. The effort counts the bindings that searches try, and no result
    /// depends on it: the guard stops a runaway, and its stop is a fault of
    /// the call ([`take_effort_fault`]). A hit in a cache charges no effort,
    /// since it tries no binding.
    #[inline]
    pub fn charge_effort(&self, bindings: u64) -> Result<(), ReachedBound> {
        let cap = self.effort_cap;
        if self.effort.exhausted.load(Ordering::Relaxed) {
            return Err(ReachedBound::Effort { cap });
        }
        // Past 2^40 a charge is past the guard, and the clamp keeps the sum from wrapping.
        let bindings = bindings.min(1 << 40);
        let effort = if bindings == 0 { self.effort.count.load(Ordering::Relaxed) } else { self.effort.count.fetch_add(bindings, Ordering::Relaxed).saturating_add(bindings) };
        if effort > cap {
            if !self.effort.exhausted.swap(true, Ordering::Relaxed) {
                self.gauges.hit(Gauge::Effort, effort, cap);
                *self.sink.lock().unwrap_or_else(std::sync::PoisonError::into_inner) = Some(EffortFault { gauge: Gauge::Effort, cap });
            }
            return Err(ReachedBound::Effort { cap });
        }
        self.gauges.note(Gauge::Effort, effort, cap);
        Ok(())
    }

    /// The bindings that the request's searches have tried.
    pub fn effort(&self) -> u64 {
        self.effort.count.load(Ordering::Relaxed)
    }

    /// The effort guard.
    pub fn effort_cap(&self) -> u64 {
        self.effort_cap
    }

    /// Whether the request has passed its effort guard.
    pub fn is_effort_exhausted(&self) -> bool {
        self.effort.exhausted.load(Ordering::Relaxed)
    }

    /// Holds `rows`, which an index build on this thread walked where no
    /// request was at hand to charge, for the next charge of a request on this
    /// thread. A request runs on one thread, so the rows go to the request
    /// that built the index.
    pub fn note_unbilled(rows: u64) {
        tally(|tally| tally.unbilled = tally.unbilled.saturating_add(rows));
    }

    /// Holds `bytes` more, which an evaluation allocates, in the request's
    /// bytes, and gives the stop once the request holds more than its byte
    /// budget. The request holds the bytes until [`RequestWork::credit_bytes`]
    /// frees them, or the measurement around the charge ends and frees all but
    /// what its value holds ([`RequestWork::measure_holding`]). Each later call
    /// gives the stop too. The bytes held depend on the charges and the credits
    /// alone, and not on what the session held.
    pub fn charge_bytes(&self, bytes: u64) -> Result<(), ReachedBound> {
        // Past 2^50 a charge is past every budget, and the clamp keeps the sum from wrapping.
        let bytes = bytes.min(1 << 50);
        self.tally_bytes(|span| span.acquire(bytes));
        self.bytes_reached(self.bytes.acquire(bytes, self.byte_caps.request))
    }

    /// Holds `bytes` for a moment: the check of [`RequestWork::charge_bytes`],
    /// and the bytes are freed again.
    pub fn charge_bytes_transient(&self, bytes: u64) -> Result<(), ReachedBound> {
        let bytes = bytes.min(1 << 50);
        self.tally_bytes(|span| span.transient(bytes));
        let acquired = self.bytes.acquire(bytes, self.byte_caps.request);
        if matches!(acquired, Acquired::Within(_)) {
            self.bytes.release(bytes);
        }
        self.bytes_reached(acquired)
    }

    /// Frees `bytes` that [`RequestWork::charge_bytes`] held.
    pub fn credit_bytes(&self, bytes: u64) {
        let bytes = bytes.min(1 << 50);
        self.tally_bytes(|span| span.release(bytes));
        self.bytes.release(bytes);
    }

    /// Holds the bytes that a hit on an entry holds: it checks the budget
    /// against the most the entry's computation held, and keeps what its value
    /// holds.
    fn charge_hit_bytes(&self, span: ByteSpan) -> Result<(), ReachedBound> {
        let peak = span.peak.min(1 << 50);
        self.tally_bytes(|counted| counted.absorb(span));
        let acquired = self.bytes.acquire(peak, self.byte_caps.request);
        if matches!(acquired, Acquired::Within(_)) {
            self.bytes.release(peak.saturating_sub(span.net));
        }
        self.bytes_reached(acquired)
    }

    /// Holds `bytes` that an allocation of the session owns until it drops
    /// ([`Owner`]): no measurement counts them, and the owner frees them.
    pub(crate) fn charge_bytes_owned(&self, bytes: u64) -> Result<(), ReachedBound> {
        let bytes = bytes.min(1 << 50);
        let acquired = self.bytes.acquire(bytes, self.byte_caps.request);
        self.bytes.owned.fetch_add(bytes, Ordering::Relaxed);
        self.bytes_reached(acquired)
    }

    /// Whether the request stays within its byte budget after it holds `peak`
    /// bytes more.
    pub fn fits_bytes(&self, peak: u64) -> bool {
        self.bytes.fits(peak, self.byte_caps.request)
    }

    /// Notes the bytes held in the gauge, and gives the stop where an acquire
    /// passed the budget.
    fn bytes_reached(&self, acquired: Acquired) -> Result<(), ReachedBound> {
        let cap = self.byte_caps.request;
        match acquired {
            Acquired::Within(held) => {
                self.gauges.note(Gauge::RequestBytes, held, cap);
                Ok(())
            }
            Acquired::Past { held, first } => {
                if first {
                    self.gauges.hit(Gauge::RequestBytes, held, cap);
                } else {
                    self.gauges.note(Gauge::RequestBytes, held, cap);
                }
                Err(ReachedBound::RequestBytes { cap })
            }
        }
    }

    /// Applies `with` to the bytes that the innermost open measurement counts
    /// for this request, where it measures this request.
    fn tally_bytes(&self, with: impl FnOnce(&mut ByteSpan)) {
        let key = self.key();
        tally(|tally| {
            if let Some(top) = tally.frames.last_mut()
                && top.request == key
            {
                with(&mut top.cost.bytes);
            }
        });
    }

    /// The identity of the count, which the open measurements name it by.
    fn key(&self) -> usize {
        Arc::as_ptr(&self.count) as usize
    }

    /// The value of `run` and its [`Cost`]: what `run` charges to this
    /// request on this thread, and the bindings it charges to an observation's
    /// count, with the costs of the entries it hits. The cost counts in
    /// the measurement around it too, and the rows of index builds that
    /// waited for a charge when `run` began wait for one after it, so they
    /// belong to the work around and not to `run`. The value holds no bytes:
    /// the bytes that `run` still holds at its end are freed.
    pub fn measure<T>(&self, run: impl FnOnce() -> T) -> (T, Cost) {
        self.measure_holding(run, |_| 0)
    }

    /// [`RequestWork::measure`], where the value of `run` holds the bytes that
    /// `held_by` gives. The request and the assignment keep that many of the
    /// bytes that `run` holds at its end, if it holds so many, and the rest are
    /// freed: they were the scratch of `run` and the values of the entries it
    /// read. A hit on the entry holds the bytes that the value holds.
    pub fn measure_holding<T>(&self, run: impl FnOnce() -> T, held_by: impl FnOnce(&T) -> u64) -> (T, Cost) {
        tally(|tally| {
            let held = std::mem::take(&mut tally.unbilled);
            tally.frames.push(Frame { request: self.key(), held, assignment: None, cost: Cost::default() });
        });
        let mut open = Unwind(true);
        let value = run();
        // The rows of builds that no charge in `run` took are the work of `run`.
        let _ = self.charge(0);
        open.0 = false;
        let kept = held_by(&value);
        let (cost, freed, assignment) = tally(|tally| {
            let mut frame = tally.frames.pop().expect("the measurement this call opened");
            tally.unbilled = tally.unbilled.saturating_add(frame.held);
            let freed = frame.cost.bytes.net.saturating_sub(kept);
            frame.cost.bytes.net -= freed;
            if let Some(outer) = tally.frames.last_mut() {
                let same_request = frame.request == outer.request;
                outer.cost.absorb(&frame.cost, same_request);
                if let Some(account) = &frame.assignment {
                    outer.assignment.get_or_insert_with(|| Arc::clone(account));
                }
            }
            (frame.cost, freed, frame.assignment)
        });
        self.bytes.release(freed);
        if let Some(account) = assignment {
            account.account.release(freed);
        }
        (value, cost)
    }

    /// What the innermost measurement open on this thread has charged to this
    /// request so far.
    pub fn spent(&self) -> Cost {
        let _ = self.charge(0);
        let key = self.key();
        tally(|tally| tally.frames.last().filter(|frame| frame.request == key).map_or_else(Cost::default, |frame| frame.cost))
    }

    /// The work counted so far.
    pub fn count(&self) -> u64 {
        self.count.load(Ordering::Relaxed)
    }

    /// The cap on the count.
    pub fn cap(&self) -> u64 {
        self.cap
    }

    /// Whether the count is past the cap, or the bytes have been past the
    /// byte budget, or the effort is past its guard: a result that a stop of
    /// the request cut short is kept nowhere.
    pub fn is_past_cap(&self) -> bool {
        self.count() > self.cap || self.bytes.is_stopped() || self.is_effort_exhausted()
    }

    /// Whether the request has been past its byte budget.
    pub fn is_past_byte_budget(&self) -> bool {
        self.bytes.is_stopped()
    }

    /// The bytes that the request holds now.
    pub fn byte_count(&self) -> u64 {
        self.bytes.held()
    }

    /// The request's byte budget.
    pub fn byte_cap(&self) -> u64 {
        self.byte_caps.request
    }

    /// The byte budget of each assignment of a table walk in the request.
    pub fn assignment_byte_cap(&self) -> u64 {
        self.byte_caps.assignment
    }

    /// The gauges of the request's other caps.
    pub fn gauges(&self) -> &Gauges {
        &self.gauges
    }
}

/// A shared count of work. Row queries count without an observation budget;
/// projections, extents, mask walks and row comparisons supply their own cap.
/// Clones share the count.
#[derive(Clone, Debug)]
pub struct TableWork {
    count: Arc<AtomicU64>,
    /// The count that this one adds its charges to as well, where this is one
    /// assignment's own ([`TableWork::scoped`]). The parent's cap is not
    /// checked against them.
    parent: Option<Arc<AtomicU64>>,
    /// The bytes that the assignment owning this count holds, and the most it
    /// may hold, where this count is one assignment's own
    /// ([`TableWork::scoped`]).
    bytes: Option<Arc<AssignmentBytes>>,
    cap: u64,
    crossing: Arc<Crossing>,
    /// The gauges of the request that the count's observation runs in, once
    /// [`Limits::counted_in`] gives them; the clones of the count share them.
    gauges: Arc<std::sync::OnceLock<Arc<Gauges>>>,
    /// The gauge that the count's notes and hits go to.
    gauge: Gauge,
    /// Whether this is the count of a prefix check ([`TableWork::prefix`]),
    /// which counts the content of its evaluation inside an [`uncounted`]
    /// scope too.
    prefix: bool,
}

/// The counts on the two sides of the charge that first took a count past
/// its cap, where that charge began within the cap.
#[derive(Debug)]
struct Crossing {
    set: AtomicBool,
    before: AtomicU64,
    after: AtomicU64,
}

impl TableWork {
    /// An observation with no work counted, under `cap`.
    pub fn new(cap: u64) -> Self {
        TableWork { count: Arc::new(AtomicU64::new(0)), parent: None, bytes: None, cap, crossing: Arc::new(Crossing { set: AtomicBool::new(false), before: AtomicU64::new(0), after: AtomicU64::new(0) }), gauges: Arc::default(), gauge: Gauge::TableWork, prefix: false }
    }

    /// The count of one prefix check: no content counted, under `cap`, with
    /// the gauge [`Gauge::PrefixContent`] of `request`. Its charges count
    /// inside an [`uncounted`] scope, where no other count does, and its stop
    /// is a [`ReachedBound::TableWork`] that no cache stores.
    pub fn prefix(cap: u64, request: &RequestWork) -> Self {
        let work = Self::counted_as(cap, Gauge::PrefixContent, request);
        TableWork { prefix: true, ..work }
    }

    /// Whether a charge to this count adds to it where the thread runs in an
    /// [`uncounted`] scope.
    fn counts_uncounted(&self) -> bool {
        self.prefix
    }

    /// An observation with no work counted, under `cap`, whose count the
    /// gauge `gauge` of `request` keeps, where the budget is no table work
    /// cap of the settings.
    pub fn counted_as(cap: u64, gauge: Gauge, request: &RequestWork) -> Self {
        let work = Self::new(cap);
        let _ = work.gauges.set(Arc::clone(&request.gauges));
        TableWork { gauge, ..work }
    }

    /// A count with no observation budget.
    pub fn uncapped() -> Self {
        Self::new(u64::MAX)
    }

    /// A count of no work for one assignment of the observation that this
    /// counts, under the same cap, with the same gauge, and a byte budget of
    /// `byte_cap` bytes held at a time for the assignment. Its stop at the cap
    /// or at the byte budget rejects that assignment alone
    /// ([`ReachedBound::is_assignment`]); the work it counts is added to this
    /// count too, which this count's cap does not check.
    pub fn scoped(&self, byte_cap: u64, byte_gauges: Arc<Gauges>) -> Self {
        TableWork { count: Arc::new(AtomicU64::new(0)), parent: Some(Arc::clone(&self.count)), bytes: Some(Arc::new(AssignmentBytes { account: ByteAccount::default(), cap: byte_cap, gauges: byte_gauges })), cap: self.cap, crossing: Arc::new(Crossing { set: AtomicBool::new(false), before: AtomicU64::new(0), after: AtomicU64::new(0) }), gauges: Arc::clone(&self.gauges), gauge: self.gauge, prefix: self.prefix }
    }

    /// Holds `bytes` more in the assignment that owns this count, and gives
    /// the stop once the assignment holds more than its byte budget. The
    /// assignment holds them until [`TableWork::credit_bytes`] frees them, the
    /// measurement around the charge ends and frees all but what its value
    /// holds ([`RequestWork::measure_holding`]), or the assignment ends
    /// ([`TableWork::settle_bytes`]). Each later call gives the stop too. The
    /// bytes held depend on that assignment's charges and credits alone, and
    /// not on what the session held. A count that is no assignment's own has no
    /// budget.
    pub fn charge_bytes(&self, bytes: u64) -> Result<(), ReachedBound> {
        let Some(assignment) = &self.bytes else { return Ok(()) };
        let bytes = bytes.min(1 << 50);
        note_assignment(assignment);
        assignment.reached(assignment.account.acquire(bytes, assignment.cap))
    }

    /// Holds `bytes` for a moment: the check of [`TableWork::charge_bytes`],
    /// and the bytes are freed again.
    pub fn charge_bytes_transient(&self, bytes: u64) -> Result<(), ReachedBound> {
        let Some(assignment) = &self.bytes else { return Ok(()) };
        let bytes = bytes.min(1 << 50);
        let acquired = assignment.account.acquire(bytes, assignment.cap);
        if matches!(acquired, Acquired::Within(_)) {
            assignment.account.release(bytes);
        }
        assignment.reached(acquired)
    }

    /// Frees `bytes` that [`TableWork::charge_bytes`] held.
    pub fn credit_bytes(&self, bytes: u64) {
        let Some(assignment) = &self.bytes else { return };
        let bytes = bytes.min(1 << 50);
        assignment.account.release(bytes);
    }

    /// Holds the bytes that a hit on an entry holds, as
    /// [`RequestWork::charge_hit_bytes`] does for the request.
    fn charge_hit_bytes(&self, span: ByteSpan) -> Result<(), ReachedBound> {
        let Some(assignment) = &self.bytes else { return Ok(()) };
        let peak = span.peak.min(1 << 50);
        note_assignment(assignment);
        let acquired = assignment.account.acquire(peak, assignment.cap);
        if matches!(acquired, Acquired::Within(_)) {
            assignment.account.release(peak.saturating_sub(span.net));
        }
        assignment.reached(acquired)
    }

    /// Holds `bytes` that an allocation of the session owns until it drops, as
    /// [`RequestWork::charge_bytes_owned`] does for the request.
    pub(crate) fn charge_bytes_owned(&self, bytes: u64) -> Result<(), ReachedBound> {
        let Some(assignment) = &self.bytes else { return Ok(()) };
        let bytes = bytes.min(1 << 50);
        let acquired = assignment.account.acquire(bytes, assignment.cap);
        assignment.account.owned.fetch_add(bytes, Ordering::Relaxed);
        assignment.reached(acquired)
    }

    /// Whether the assignment owning this count stays within its byte budget
    /// after it holds `peak` bytes more. A count that is no assignment's own
    /// has none.
    pub fn fits_bytes(&self, peak: u64) -> bool {
        self.bytes.as_ref().is_none_or(|assignment| assignment.account.fits(peak, assignment.cap))
    }

    /// Ends the assignment that owns this count: the bytes it still holds,
    /// but those that an allocation of the session owns, are freed in
    /// `request`, which they were held in too.
    pub fn settle_bytes(&self, request: &RequestWork) {
        let Some(assignment) = &self.bytes else { return };
        let owned = assignment.account.owned.load(Ordering::Relaxed);
        let held = assignment.account.held.swap(owned, Ordering::Relaxed);
        request.bytes.release(held.saturating_sub(owned));
    }

    /// Whether this count is one assignment's own ([`TableWork::scoped`]).
    pub fn is_scoped(&self) -> bool {
        self.parent.is_some()
    }

    /// Adds `bindings` to the parent's count, where there is one.
    fn charge_parent(&self, bindings: u64) {
        if let Some(parent) = &self.parent {
            let _ = parent.try_update(Ordering::Relaxed, Ordering::Relaxed, |count| Some(count.saturating_add(bindings)));
        }
    }

    /// Adds `bindings` to the count, and gives the stop once the count is past
    /// the cap. Each later call gives it too.
    pub fn charge(&self, bindings: u64) -> Result<(), ReachedBound> {
        if is_uncounted() && !self.counts_uncounted() {
            return Ok(());
        }
        self.charge_parent(bindings);
        let Ok(before) = self.count.try_update(Ordering::Relaxed, Ordering::Relaxed, |count| Some(count.saturating_add(bindings))) else {
            unreachable!("an update that always gives a count")
        };
        let count = before.saturating_add(bindings);
        if count > self.cap {
            if before <= self.cap {
                self.cross(before, count);
            }
            if let Some(gauges) = self.gauges.get() {
                gauges.hit(self.gauge, count, self.cap);
            }
            Err(ReachedBound::TableWork { cap: self.cap, assignment: self.parent.is_some() })
        } else {
            if let Some(gauges) = self.gauges.get() {
                gauges.note(self.gauge, count, self.cap);
            }
            Ok(())
        }
    }

    fn cross(&self, before: u64, after: u64) {
        if !self.crossing.set.swap(true, Ordering::Relaxed) {
            self.crossing.before.store(before, Ordering::Relaxed);
            self.crossing.after.store(after, Ordering::Relaxed);
        }
    }

    /// The counts before and after the charge that first took the count past
    /// the cap, where that charge began within the cap, and `None` where no
    /// charge did.
    pub fn crossing(&self) -> Option<(u64, u64)> {
        self.crossing.set.load(Ordering::Relaxed).then(|| (self.crossing.before.load(Ordering::Relaxed), self.crossing.after.load(Ordering::Relaxed)))
    }

    /// Adds `bindings` to a count that stays within the cap before `before`
    /// more of them and passes it with `after` more, as the charges of an
    /// evaluation that stopped at the cap did: the count then passes the cap,
    /// at the charge that [`TableWork::crossing`] gives, `before` and `after`
    /// bindings from the count now.
    pub fn charge_crossing(&self, bindings: u64, before: u64, after: u64) {
        if is_uncounted() && !self.counts_uncounted() {
            return;
        }
        self.charge_parent(bindings);
        let Ok(from) = self.count.try_update(Ordering::Relaxed, Ordering::Relaxed, |count| Some(count.saturating_add(bindings))) else {
            unreachable!("an update that always gives a count")
        };
        if from.saturating_add(before) <= self.cap && from.saturating_add(after) > self.cap {
            self.cross(from.saturating_add(before), from.saturating_add(after));
        }
    }

    /// For the count of a prefix check ([`TableWork::prefix`]), gives the stop
    /// once `rows`, the rows that an evaluation holds as it produces them,
    /// would take the count past the cap with what it counts when it ends.
    /// It adds nothing to the count, so a join that produces rows stops
    /// before it holds the rows that the cap leaves no room for. Any other
    /// count gives no stop here.
    pub fn check_rows(&self, rows: u64) -> Result<(), ReachedBound> {
        if !self.prefix {
            return Ok(());
        }
        let reached = self.count.load(Ordering::Relaxed).saturating_add(rows);
        if reached > self.cap {
            if let Some(gauges) = self.gauges.get() {
                gauges.hit(self.gauge, reached, self.cap);
            }
            return Err(ReachedBound::TableWork { cap: self.cap, assignment: false });
        }
        Ok(())
    }

    /// Whether the count is past the cap: each batch of an evaluation that
    /// begins now stops at once.
    pub fn is_past_cap(&self) -> bool {
        self.count.load(Ordering::Relaxed) > self.cap
    }

    /// Whether this count has an observation budget.
    pub fn is_capped(&self) -> bool {
        self.cap != u64::MAX
    }

    /// The cap on the count.
    pub fn cap(&self) -> u64 {
        self.cap
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
/// session: the work of its request, its cancellation, the work
/// count of its query or observation, the stops held by the decode
/// it runs for, and whether it checks the declared rows of the outputs it
/// builds. The caps stand in the [`crate::session::TaskSession`].
#[derive(Clone, Debug)]
pub struct Limits {
    /// The work of the request that the evaluation runs in, which every
    /// evaluation of the request adds to, and which stops each of them once
    /// past its cap.
    pub request: RequestWork,
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
    /// Where each session's bytes stood when it first checked its bound
    /// under these limits, as [`crate::session::TaskSession::relieve`]
    /// reads them. The clones of these limits share them.
    pub heap_starts: crate::session::HeapStarts,
    /// The bound on the session's bytes under these limits, where it is not
    /// the session's own. A session over its bound evicts its caches, and
    /// stops nothing.
    pub byte_bound: Option<crate::session::SessionBound>,
    /// The computations of entries that the evaluation takes from the walks
    /// before it and keeps for those after it ([`super::carry`]); none where
    /// the evaluation is not a liveness walk of a decode.
    pub carry: Option<super::carry::Carry>,
}

/// The limits of one assignment ([`Limits::for_assignment`]). Where the scope
/// ends, the bytes that the assignment still holds are freed in the request.
#[derive(Debug)]
pub struct AssignmentScope(Limits);

impl std::ops::Deref for AssignmentScope {
    type Target = Limits;

    fn deref(&self) -> &Limits {
        &self.0
    }
}

impl Drop for AssignmentScope {
    fn drop(&mut self) {
        if let Some(work) = &self.0.table_work {
            work.settle_bytes(&self.0.request);
        }
    }
}

impl Limits {
    /// The limits of an evaluation outside a table and outside a decode, with
    /// a request of no work counted under `request_cap`, or under
    /// [`REQUEST_WORK_CAP`] where it is `None`. The request is no request
    /// that [`RequestWork::latest`] gives: a caller begins one with
    /// [`crate::stream::DecodeSettings::operation_limits`] or a decoder's call.
    pub fn new(request_cap: Option<u64>, cancellation: Cancellation) -> Self {
        Limits { request: RequestWork::new(request_cap.unwrap_or(REQUEST_WORK_CAP)), cancellation, table_work: None, held_stops: None, copies: None, heap_starts: Default::default(), byte_bound: None, carry: None }
    }

    /// These limits with the evaluation adding to `request`, the work of the
    /// request it runs in, in place of a request of its own.
    pub fn in_request(self, request: RequestWork) -> Self {
        Limits { request, ..self }
    }

    /// These limits with the evaluation checking the declared rows of the
    /// outputs it builds, and reporting each violation to `violations`.
    pub fn checking_copies(self, violations: super::copies::CopyViolations) -> Self {
        Limits { copies: Some(violations), ..self }
    }

    /// These limits for the evaluation of one assignment, or of one step of
    /// the walk of assignments: where these limits count table work, a count of
    /// its own under the same cap ([`TableWork::scoped`]) and, where these
    /// limits count none, an uncapped one, with the byte budget of the
    /// assignment that the request gives ([`RequestWork::assignment_byte_cap`]).
    /// The stop of such an evaluation at its count or at its byte budget
    /// rejects that assignment alone ([`ReachedBound::is_assignment`]). The
    /// request's work and bytes and the cancellation stay shared, so the stops
    /// at the request's budgets end the walk. The scope frees the bytes that
    /// the assignment held in the request when it drops.
    pub fn for_assignment(&self) -> AssignmentScope {
        // Limits that count no table work get an uncapped count, so that the assignment has its byte budget too.
        let work = self.table_work.clone().unwrap_or_else(TableWork::uncapped).scoped(self.request.assignment_byte_cap(), Arc::clone(&self.request.gauges));
        AssignmentScope(Limits { table_work: Some(work), ..self.clone() })
    }

    /// These limits for one candidate of a call that evaluates several
    /// ([`RequestWork::candidate`]): the work and the bytes of the candidate
    /// count from none, under the request's caps.
    pub fn for_candidate(&self) -> Self {
        Limits { request: self.request.candidate(), ..self.clone() }
    }

    /// Holds `bytes` in the request and in the assignment of these limits for
    /// an allocation of the session, and gives the owner that frees them where
    /// the allocation drops ([`crate::session::SessionAllocation::owned_by`]).
    /// No measurement counts these bytes.
    pub(crate) fn hold_bytes_owned(&self, bytes: u64) -> Result<Owner, ReachedBound> {
        let bytes = bytes.min(1 << 50);
        let owner = Owner { request: Arc::clone(&self.request.bytes), assignment: self.table_work.as_ref().and_then(|work| work.bytes.clone()) };
        let held = self.request.charge_bytes_owned(bytes).and_then(|()| self.table_work.as_ref().map_or(Ok(()), |work| work.charge_bytes_owned(bytes)));
        match held {
            Ok(()) => Ok(owner),
            Err(bound) => {
                owner.free(bytes);
                Err(bound)
            }
        }
    }

    /// These limits with the evaluation counted in `work`.
    pub fn counted_in(self, work: TableWork) -> Self {
        // The first request that counts an observation keeps its gauges.
        let _ = work.gauges.set(Arc::clone(&self.request.gauges));
        Limits { table_work: Some(work), ..self }
    }

    /// These limits with the session's bytes bound by `bound` in place of the
    /// session's own bound.
    pub fn bound_by(self, bound: crate::session::SessionBound) -> Self {
        Limits { byte_bound: Some(bound), ..self }
    }

    /// These limits with the evaluation taking and keeping computations of
    /// entries in `carry`.
    pub fn carrying(self, carry: super::carry::Carry) -> Self {
        Limits { carry: Some(carry), ..self }
    }

    /// These limits with the evaluation taking and holding stops in `stops`.
    pub fn holding_in(self, stops: Arc<HeldStops>) -> Self {
        Limits { held_stops: Some(stops), ..self }
    }
}
