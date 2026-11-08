//! Counters and timers for the phases of a decode, off until a caller turns
//! them on with [`set_enabled`] (the Python binding `engine_stats` does, with
//! its `collect` argument).
//!
//! Each timing point is one call of this module. While the statistics are
//! off, a call costs one relaxed load of an atomic flag and one branch: no clock is
//! read, no key is computed and no lock is taken. They change no result of
//! the engine, which never reads a counter.
//!
//! A [`Phase`] has four counters:
//!
//! - `calls`: the spans entered ([`span`]) and the ticks ([`tick`]).
//! - `new` and `repeated`: how many of the keys given to [`seen`] had not
//!   been given for that phase since the last reset, and how many had. A
//!   phase whose site gives no key reports both as 0.
//! - `ns`: the time spans of the phase took. A span includes the time of the
//!   phases called inside it, and of the same phase where it calls itself.
//! - `units`: the work items the phase's site counts ([`units`]), such as
//!   forms checked or domains computed. `units / calls` shows whether the
//!   work of a call grows with the size of the program.
//!
//! The counters are atomics, so they count the threads that run with the GIL
//! released. A key is a 64-bit digest; a pointer in a key can be reused after
//! its value is freed, so a `repeated` count may be too high by such a reuse.

use std::hash::Hash;
use std::sync::atomic::{AtomicBool, AtomicU64, Ordering};
use std::sync::Mutex;
use crate::clock::Stopwatch;

use crate::hash::{StableHashSet, StableHasher};

/// Whether the statistics are on.
static ENABLED: AtomicBool = AtomicBool::new(false);

/// Whether the statistics are on.
#[inline(always)]
pub fn enabled() -> bool {
    ENABLED.load(Ordering::Relaxed)
}

/// Turns the statistics on or off, for the whole process; the counters keep
/// their values.
pub fn set_enabled(on: bool) {
    ENABLED.store(on, Ordering::Relaxed);
}

macro_rules! phases {
    ($($variant:ident => $name:literal,)*) => {
        /// A phase of the engine's work, whose counters [`snapshot`] gives
        /// under [`Phase::name`].
        #[derive(Clone, Copy, PartialEq, Eq, Debug)]
        pub enum Phase {
            $($variant,)*
        }

        impl Phase {
            /// Each phase, in the order of [`snapshot`].
            pub const ALL: &'static [Phase] = &[$(Phase::$variant,)*];

            /// The phase's name, which is stable: a dotted path whose first
            /// part is the layer (`py`, `decode`, `infer`, `resolve`,
            /// `prefix`, `det`, `check`, `table`, `eval`).
            pub fn name(self) -> &'static str {
                match self {
                    $(Phase::$variant => $name,)*
                }
            }
        }
    };
}

phases! {
    PyStep => "py.step",
    PyForced => "py.forced",
    PyAdmissible => "py.admissible",
    PyAdmits => "py.admits",
    PyFork => "py.fork",
    PyStepTables => "py.step_tables",
    PyPack => "py.pack",
    DecodeNext => "decode.next",
    DecodeWithChecks => "decode.with_checks",
    DecodeStaticPrune => "decode.static_prune",
    DecodeCompletes => "decode.completes",
    DecodePrefixHit => "decode.prefix_hit",
    DecodePrefixMiss => "decode.prefix_miss",
    DecodePrefixClear => "decode.prefix_clear",
    InferFormFinished => "infer.form.finished",
    InferFormOpen => "infer.form.open",
    InferFormKept => "infer.form.kept",
    ResolveLast => "resolve.last",
    PrefixCheckGrammar => "prefix.check.grammar",
    PrefixCheckScope => "prefix.check.scope",
    PrefixCheckSiteColumns => "prefix.check.site_columns",
    PrefixCheckTypes => "prefix.check.types",
    PrefixCheckPoseRule => "prefix.check.pose_rule",
    PrefixCheckMadeAndExportedLabels => "prefix.check.made_and_exported_labels",
    PrefixCheckSafety => "prefix.check.safety",
    PrefixCheckUnfoldReads => "prefix.check.unfold_reads",
    PrefixCheckCycles => "prefix.check.cycles",
    PrefixCheckInstanceInputs => "prefix.check.instance_inputs",
    PrefixCheckPooledAndLiftedReads => "prefix.check.pooled_and_lifted_reads",
    PrefixCheckEqualityAndZero => "prefix.check.equality_and_zero",
    PrefixCheckConstraintMarks => "prefix.check.constraint_marks",
    PrefixCheckOneClause => "prefix.check.one_clause",
    PrefixCheckInstanceSites => "prefix.check.instance_sites",
    PrefixCheckSpelling => "prefix.check.spelling",
    PrefixCheckPicks => "prefix.check.picks",
    PrefixCheckRigidPartsAndProposers => "prefix.check.rigid_parts_and_proposers",
    PrefixCheckOut => "prefix.check.out",
    DetLiveness => "det.liveness",
    CheckProgram => "check.program",
    CheckCacheMiss => "check.cache_miss",
    CheckProgramTypes => "check.program_types",
    TableStep => "table.step",
    TableBody => "table.body",
    TableSubBody => "table.sub_body",
    TableWalk => "table.walk",
    EvalDomain => "eval.domain",
    EvalBody => "eval.body",
    EvalPartCached => "eval.part.cached",
    EvalPartLinked => "eval.part.linked",
    TableRelation => "table.relation",
    TableNames => "table.names",
    TableLabelNames => "table.label_names",
    TableEvidence => "table.evidence",
    TablePack => "table.pack",
}

const PHASES: usize = Phase::ALL.len();

static CALLS: [AtomicU64; PHASES] = [const { AtomicU64::new(0) }; PHASES];
static NEW: [AtomicU64; PHASES] = [const { AtomicU64::new(0) }; PHASES];
static REPEATED: [AtomicU64; PHASES] = [const { AtomicU64::new(0) }; PHASES];
static NS: [AtomicU64; PHASES] = [const { AtomicU64::new(0) }; PHASES];
static UNITS: [AtomicU64; PHASES] = [const { AtomicU64::new(0) }; PHASES];

/// The keys given to [`seen`] since the last reset.
static SEEN: Mutex<Option<StableHashSet<(u16, u64)>>> = Mutex::new(None);

/// A running timer of a phase: dropping it adds the time since [`span`].
#[must_use = "a span times the phase until it is dropped"]
pub struct Span {
    phase: Phase,
    start: Stopwatch,
}

impl Drop for Span {
    fn drop(&mut self) {
        let ns = u64::try_from(self.start.elapsed().nanos()).unwrap_or(u64::MAX);
        NS[self.phase as usize].fetch_add(ns, Ordering::Relaxed);
    }
}

/// Counts a call of `phase` and times it until the result is dropped; `None`
/// while the statistics are off.
#[inline(always)]
pub fn span(phase: Phase) -> Option<Span> {
    if !enabled() {
        return None;
    }
    CALLS[phase as usize].fetch_add(1, Ordering::Relaxed);
    Some(Span { phase, start: Stopwatch::start() })
}

/// Counts a call of `phase` that takes no time of its own.
#[inline(always)]
pub fn tick(phase: Phase) {
    if enabled() {
        CALLS[phase as usize].fetch_add(1, Ordering::Relaxed);
    }
}

/// Adds `count` work items to `phase`.
#[inline(always)]
pub fn units(phase: Phase, count: usize) {
    if enabled() {
        UNITS[phase as usize].fetch_add(count as u64, Ordering::Relaxed);
    }
}

/// Counts the key `key()` of a call of `phase` as new, where `phase` has not
/// been given it since the last reset, and as repeated otherwise. The key is
/// computed only while the statistics are on.
#[inline(always)]
pub fn seen(phase: Phase, key: impl FnOnce() -> u64) {
    if enabled() {
        record_key(phase, key());
    }
}

#[cold]
fn record_key(phase: Phase, key: u64) {
    let fresh = SEEN.lock().expect("the key set is not poisoned").get_or_insert_with(StableHashSet::default).insert((phase as u16, key));
    let counter = if fresh { &NEW } else { &REPEATED };
    counter[phase as usize].fetch_add(1, Ordering::Relaxed);
}

/// A 64-bit digest of `value`, for a key.
pub fn digest(value: &impl Hash) -> u64 {
    use std::hash::Hasher;
    let mut hasher = StableHasher::new();
    value.hash(&mut hasher);
    hasher.finish()
}

/// The counters of one phase, as [`snapshot`] gives them.
#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub struct PhaseStats {
    pub phase: Phase,
    pub calls: u64,
    pub new: u64,
    pub repeated: u64,
    pub ns: u64,
    pub units: u64,
}

/// The counters of every phase, in the order of [`Phase::ALL`]. Where `reset`
/// is true, each counter and the set of keys start again from zero, and the
/// counters are those it held. A call that runs while the reset reads the
/// counters is counted in the snapshot or after it, and in no more than one.
pub fn snapshot(reset: bool) -> Vec<PhaseStats> {
    let read = |counters: &[AtomicU64; PHASES], at: usize| if reset { counters[at].swap(0, Ordering::Relaxed) } else { counters[at].load(Ordering::Relaxed) };
    let stats = Phase::ALL
        .iter()
        .map(|&phase| {
            let at = phase as usize;
            PhaseStats { phase, calls: read(&CALLS, at), new: read(&NEW, at), repeated: read(&REPEATED, at), ns: read(&NS, at), units: read(&UNITS, at) }
        })
        .collect();
    if reset {
        *SEEN.lock().expect("the key set is not poisoned") = None;
    }
    stats
}
