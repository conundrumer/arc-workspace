//! The values and the bounds of an evaluation: its caps, the other bounds
//! it can reach, the value of a relation or a grid on a request, a stop,
//! a fault of a run, the key columns of a keyed form's output rows, and the
//! flag that cancels evaluations. The driver and the parts of [`super`]
//! share them.

use std::sync::atomic::{AtomicBool, AtomicU64, Ordering};
use std::cell::RefCell;
use std::sync::{Arc, Mutex};

use crate::diagnostic::{Diagnostic, DiagnosticKind, Location, Severity};
use crate::hash::StableHashMap;
use crate::program::path::NodePath;
use crate::relations::Relation;
use crate::session::{Counts, ReachedSessionBound, ResultKey, TaskSession};
use crate::solver::CaseName;
use crate::task::Grid;
use crate::terms::ReachedMarginBound;

/// The caps of one query's evaluation, independent of the machine. A query
/// evaluates a clause, finished or in progress, on one example at one
/// assignment. No cap here sums the evaluations of a program: the request
/// work cap does ([`RequestWork`]).
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
    /// The work budget of an observation.
    TableWork { cap: u64 },
    /// A Box with a margin outside a signed byte.
    Margin(ReachedMarginBound),
    SessionBytes(ReachedSessionBound),
    /// The work cap of one request, summed over every query and walk of it
    /// ([`RequestWork`]).
    RequestWork { cap: u64 },
    Cancelled,
    /// A variable of a search's order that no node of the clause gives values
    /// at any place of the order. The search has no relation to give.
    NoValues,
}

impl ReachedBound {
    /// Whether this bound rejects only the assignment being evaluated.
    pub fn is_assignment(self) -> bool {
        matches!(self, Self::Bindings { .. } | Self::Rows { .. } | Self::Margin(_) | Self::NoValues | Self::Models { .. } | Self::Nodes { .. })
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
    /// request of its entry. A stop at the session's byte bound or by a
    /// cancellation depends on the machine or the caller, and is stored
    /// nowhere. A stop at the model cap, the node cap or the assignment cap is
    /// stored nowhere either, and neither is a stop at the request work cap,
    /// which depends on the work the request did before the entry. A stop at
    /// the table work cap is held for the requests of one decode alone, in
    /// [`HeldStops`].
    pub fn is_stored(self) -> bool {
        match self {
            ReachedBound::Bindings { .. } | ReachedBound::Rows { .. } | ReachedBound::Margin(_) | ReachedBound::NoValues => true,
            ReachedBound::Models { .. }
            | ReachedBound::Nodes { .. }
            | ReachedBound::Assignments { .. }
            | ReachedBound::TableWork { .. }
            | ReachedBound::SessionBytes(_)
            | ReachedBound::RequestWork { .. }
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
            ReachedBound::RequestWork { cap } => format!("the request work cap of {cap} units of work"),
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

/// The count of [`Gauge`]s.
const GAUGES: usize = 15;

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
    /// bound of `ARCLOG_PROJECTION_STEPS`.
    ProjectionSteps,
    /// The bytes of the session at a check, under the session's byte bound;
    /// the room of an index build or a reservation counts as a hit alone. A
    /// study request runs under its own bound (`TABLE_BYTES`), which the
    /// gauge reports as its cap.
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

    static LARGEST_MARGIN: AtomicU32 = AtomicU32::new(0);
    static MARGIN_HITS: AtomicU64 = AtomicU64::new(0);

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

    /// Starts the counters again from zero.
    pub fn reset() {
        LARGEST_MARGIN.store(0, Ordering::Relaxed);
        MARGIN_HITS.store(0, Ordering::Relaxed);
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
    gauges: Arc<Gauges>,
}

/// The units that every request of the process has charged ([`RequestWork::total`]).
static TOTAL: AtomicU64 = AtomicU64::new(0);

thread_local! {
    /// The request most recently begun on this thread ([`RequestWork::begin`]).
    static LATEST: RefCell<Option<RequestWork>> = const { RefCell::new(None) };
    /// What this thread charges, for the costs of entries ([`Tally`]).
    static TALLY: RefCell<Tally> = const { RefCell::new(Tally { frames: Vec::new(), unbilled: 0 }) };
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

/// What the computation of an entry charged, which a hit on the entry charges
/// again: the units in the request, the bindings in the observation's count,
/// and the largest counts that its evaluations noted. A cost includes the
/// costs of the entries that the computation read, so it is the cost of the
/// computation with every cache empty. It is a function of the entry alone.
#[derive(Clone, Copy, PartialEq, Eq, Debug, Default)]
pub struct Cost {
    /// The units of work charged to the request.
    pub request: u64,
    /// The bindings charged to the observation's count.
    pub table: u64,
    /// The largest bindings and rows that an evaluation noted in the request's
    /// gauges.
    bindings: u64,
    rows: u64,
    /// The largest counts that the session recorded.
    counts: Counts,
}

impl Cost {
    /// Adds what a computation inside the one this cost counts charged.
    fn absorb(&mut self, inner: &Cost, same_request: bool) {
        if same_request {
            self.request = self.request.saturating_add(inner.request);
        }
        self.table = self.table.saturating_add(inner.table);
        self.bindings = self.bindings.max(inner.bindings);
        self.rows = self.rows.max(inner.rows);
        self.counts.bindings = self.counts.bindings.max(inner.counts.bindings);
        self.counts.rows = self.counts.rows.max(inner.counts.rows);
    }

    /// Whether `request` and `table`, the observation's count where there is
    /// one, stay within their caps after this cost. A hit whose cost does not
    /// fit is no hit: the caller computes the entry again, and the
    /// computation stops at the charge that a computation with empty caches
    /// stops at.
    fn fits(&self, request: &RequestWork, table: Option<&TableWork>) -> bool {
        request.count().saturating_add(self.request) <= request.cap() && table.is_none_or(|table| table.fits(self.table))
    }

    /// Charges this cost for a hit: the units to `request`, the bindings to
    /// `table`, and the counts to the gauges of `request` and to `session`.
    /// The rows of index builds that wait for a charge stay waiting for the
    /// next one, as they do around a computation.
    fn charge(&self, request: &RequestWork, table: Option<&TableWork>, session: &TaskSession) -> Result<(), ReachedBound> {
        let held = tally(|tally| std::mem::take(&mut tally.unbilled));
        tally_table(self.table);
        let charged = request.charge(self.request).and_then(|()| table.map_or(Ok(()), |table| table.charge(self.table)));
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
        if !self.cost.fits(request, table) || !admit() {
            return Charged::Misfit;
        }
        match self.cost.charge(request, table, session) {
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
    /// A count of no work, under `cap`.
    pub fn new(cap: u64) -> Self {
        RequestWork { count: Arc::new(AtomicU64::new(0)), cap, gauges: Arc::default() }
    }

    /// A count of no work for a request that begins now, under `cap`, which
    /// [`RequestWork::latest`] gives on this thread until another request
    /// begins on it.
    pub fn begin(cap: u64) -> Self {
        let work = Self::new(cap);
        ambient::reset();
        tally(|tally| tally.unbilled = 0);
        LATEST.with(|latest| *latest.borrow_mut() = Some(work.clone()));
        work
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
        let units = tally(|tally| {
            let units = units.saturating_add(std::mem::take(&mut tally.unbilled));
            // Past 2^40 a charge is past every cap, and the clamp keeps the sum of a request's charges from wrapping.
            let units = units.min(1 << 40);
            if units > 0
                && let Some(top) = tally.frames.last_mut()
                && top.request == key
            {
                top.cost.request = top.cost.request.saturating_add(units);
            }
            units
        });
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

    /// Holds `rows`, which an index build on this thread walked where no
    /// request was at hand to charge, for the next charge of a request on this
    /// thread. A request runs on one thread, so the rows go to the request
    /// that built the index.
    pub fn note_unbilled(rows: u64) {
        tally(|tally| tally.unbilled = tally.unbilled.saturating_add(rows));
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
    /// belong to the work around and not to `run`.
    pub fn measure<T>(&self, run: impl FnOnce() -> T) -> (T, Cost) {
        tally(|tally| {
            let held = std::mem::take(&mut tally.unbilled);
            tally.frames.push(Frame { request: self.key(), held, cost: Cost::default() });
        });
        let mut open = Unwind(true);
        let value = run();
        // The rows of builds that no charge in `run` took are the work of `run`.
        let _ = self.charge(0);
        open.0 = false;
        let cost = tally(|tally| {
            let frame = tally.frames.pop().expect("the measurement this call opened");
            tally.unbilled = tally.unbilled.saturating_add(frame.held);
            if let Some(outer) = tally.frames.last_mut() {
                outer.cost.absorb(&frame.cost, frame.request == outer.request);
            }
            frame.cost
        });
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

    /// Whether the count is past the cap.
    pub fn is_past_cap(&self) -> bool {
        self.count() > self.cap
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
    cap: u64,
    crossing: Arc<Crossing>,
    /// The gauges of the request that the count's observation runs in, once
    /// [`Limits::counted_in`] gives them; the clones of the count share them.
    gauges: Arc<std::sync::OnceLock<Arc<Gauges>>>,
    /// The gauge that the count's notes and hits go to.
    gauge: Gauge,
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
        TableWork { count: Arc::new(AtomicU64::new(0)), cap, crossing: Arc::new(Crossing { set: AtomicBool::new(false), before: AtomicU64::new(0), after: AtomicU64::new(0) }), gauges: Arc::default(), gauge: Gauge::TableWork }
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

    /// Adds `bindings` to the count, and gives the stop once the count is past
    /// the cap. Each later call gives it too.
    pub fn charge(&self, bindings: u64) -> Result<(), ReachedBound> {
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
            Err(ReachedBound::TableWork { cap: self.cap })
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
        let Ok(from) = self.count.try_update(Ordering::Relaxed, Ordering::Relaxed, |count| Some(count.saturating_add(bindings))) else {
            unreachable!("an update that always gives a count")
        };
        if from.saturating_add(before) <= self.cap && from.saturating_add(after) > self.cap {
            self.cross(from.saturating_add(before), from.saturating_add(after));
        }
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
    /// under these limits, as [`crate::session::TaskSession::within_bound`]
    /// reads them. The clones of these limits share them.
    pub heap_starts: crate::session::HeapStarts,
    /// The bound on the session's bytes under these limits, where it is not
    /// the session's own.
    pub byte_bound: Option<crate::session::SessionBound>,
    /// What a materialization of the rows of an exported relation reserves
    /// for each row at the least; none where the operation's export is not
    /// known to reserve. See [`RowReserve`].
    pub row_reserve: Option<RowReserve>,
    /// The relation that the operation exports, which
    /// [`Limits::row_reserve`] applies to, as the address of the resolution
    /// it is a node of and the node: the evaluation of that node's clauses
    /// stops as soon as the rows it has found would take a reservation past
    /// the session's room ([`crate::eval::join::Budget::charge_rows`]). An
    /// evaluation of another program under these limits, such as a
    /// proposer's, holds no node of it.
    pub exported: Option<(usize, crate::resolver::GraphNodeIndex)>,
    /// The computations of entries that the evaluation takes from the walks
    /// before it and keeps for those after it ([`super::carry`]); none where
    /// the evaluation is not a liveness walk of a decode.
    pub carry: Option<super::carry::Carry>,
}

/// The bytes that the export of a relation's rows reserves for each row at
/// the least, as `per_column` for each column and `fixed` for the row. A
/// column holds at least one cell, so a caller gives the reservation's bytes
/// for one cell of each column.
#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub struct RowReserve {
    pub per_column: usize,
    pub fixed: usize,
}

impl RowReserve {
    /// The bytes reserved for each row of `arity` columns at the least.
    pub fn bytes_per_row(self, arity: usize) -> usize {
        self.per_column.saturating_mul(arity).saturating_add(self.fixed)
    }
}

impl Limits {
    /// The limits of an evaluation outside a table and outside a decode, with
    /// a request of no work counted under `request_cap`, or under
    /// [`REQUEST_WORK_CAP`] where it is `None`. The request is no request
    /// that [`RequestWork::latest`] gives: a caller begins one with
    /// [`crate::stream::DecodeSettings::operation_limits`] or a decoder's call.
    pub fn new(request_cap: Option<u64>, cancellation: Cancellation) -> Self {
        Limits { request: RequestWork::new(request_cap.unwrap_or(REQUEST_WORK_CAP)), cancellation, table_work: None, held_stops: None, copies: None, heap_starts: Default::default(), byte_bound: None, row_reserve: None, exported: None, carry: None }
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

    /// These limits with the export of the rows of a relation reserving
    /// `reserve` for each row at the least.
    pub fn reserving_rows(self, reserve: RowReserve) -> Self {
        Limits { row_reserve: Some(reserve), ..self }
    }

    /// These limits with the relation of `node` of `program` exported: where
    /// [`Limits::row_reserve`] is set, the evaluation of its clauses stops at
    /// the rows whose reservation would pass the session's room.
    pub fn exporting(self, program: &crate::resolver::ResolvedProgram, node: crate::resolver::GraphNodeIndex) -> Self {
        Limits { exported: Some((std::ptr::from_ref(program) as usize, node)), ..self }
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
