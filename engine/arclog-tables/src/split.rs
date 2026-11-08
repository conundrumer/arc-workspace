//! Timers for the parts of the export by assignment that
//! [`arclog::stats`] has no phase for. They are on while the statistics are on
//! (`arclog::stats::enabled`), cost one atomic load otherwise, and change no
//! result. A part's time includes the parts called inside it.

use std::sync::atomic::{AtomicU64, Ordering};
use arclog::clock::Stopwatch;

/// A part of the export by assignment.
#[derive(Clone, Copy)]
pub enum Part {
    /// The QueryHash of each table of the step.
    OwnQueryHash,
    /// The QueryHash of a table that an assignment names as a `DET`, looked up by name.
    DetQuery,
    /// The look-up of a summary in the cache, with the copy that spells its `DET`s where it is found.
    SummaryHit,
    /// A summary that the rows give, where the cache has none.
    SummaryMiss,
    /// The columns of the step's tables, as the layout of `stream_tables` has them.
    StepColumns,
    /// The regrouping of those columns by assignment, with the `DET` lookups.
    Regroup,
    /// The wait to hold the GIL again after the work that runs without it.
    GilWait,
    /// The successors of `successor_tables`, with the evaluation of their bodies ([`crate::tables::successors::successor_tables`]).
    SuccessorTables,
    /// The columns of the tables of `successor_tables`, summaries included.
    SuccessorColumns,
    /// The Python objects of the result of `successor_tables`.
    SuccessorObjects,
}

const NAMES: [&str; 10] = ["own_query_hash", "det_query", "summary_hit", "summary_miss", "step_columns", "regroup", "gil_wait", "successor_tables", "successor_columns", "successor_objects"];

static CALLS: [AtomicU64; NAMES.len()] = [const { AtomicU64::new(0) }; NAMES.len()];
static NS: [AtomicU64; NAMES.len()] = [const { AtomicU64::new(0) }; NAMES.len()];

/// A running timer: dropping it adds the time since [`span`].
#[must_use = "a span times the part until it is dropped"]
pub struct Span {
    part: Part,
    start: Stopwatch,
}

impl Drop for Span {
    fn drop(&mut self) {
        add(self.part, self.start.elapsed().nanos());
    }
}

/// Counts a call of `part` and times it until the result is dropped; `None`
/// while the statistics are off.
#[inline(always)]
pub fn span(part: Part) -> Option<Span> {
    arclog::stats::enabled().then(|| Span { part, start: Stopwatch::start() })
}

/// Counts a call of `part` that took `nanos` nanoseconds.
pub fn add(part: Part, nanos: u128) {
    CALLS[part as usize].fetch_add(1, Ordering::Relaxed);
    NS[part as usize].fetch_add(u64::try_from(nanos).unwrap_or(u64::MAX), Ordering::Relaxed);
}

/// The name, calls and nanoseconds of each part; with `reset`, the counters start again from zero.
pub fn snapshot(reset: bool) -> Vec<(&'static str, u64, u64)> {
    let read = |counters: &[AtomicU64; NAMES.len()], at: usize| if reset { counters[at].swap(0, Ordering::Relaxed) } else { counters[at].load(Ordering::Relaxed) };
    NAMES.iter().enumerate().map(|(at, &name)| (name, read(&CALLS, at), read(&NS, at))).collect()
}
