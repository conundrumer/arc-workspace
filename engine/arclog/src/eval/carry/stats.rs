//! Counters of the carry's hits and misses and the causes of the misses, for
//! a measurement of a replay. Off unless the environment variable
//! `ARCLOG_CARRY_STATS` is set (to anything but the empty string and `0`).
//!
//! The counters change no result, no key and no digest: the engine never
//! reads them, and the extra digests that they take of a shape are not
//! part of the key. While they are off, each call of this module costs one
//! relaxed load.
//!
//! The report goes to standard error, as lines that start with
//! `carry-stats @<calls>`, each cumulative since the start of the process, at
//! each power of two of the count of calls from 1024 and at each multiple of
//! 131072. The lines with the greatest `<calls>` are the last report. Each
//! line is `<kind>.<name> n=<count> work=<table work> ms=<time>`, where
//! `<kind>` is `part` or `clause`:
//!
//! - `call`: the calls that found no entry in the walk's own cache.
//! - `hit`: a kept computation replayed; `work` is the table work it counted.
//! - `miss`: no kept computation replayed. Then exactly one of `miss.noentry`
//!   (nothing is kept under the key), `miss.work` (a kept computation would
//!   pass the cap on table work) and `miss.lookups` (the lookups of each kept
//!   computation found other values in the walk's cache).
//! - `noentry.<cause>`: why nothing is kept, by what the process saw before
//!   under the same request (its content, example, and the rows and layout of
//!   its reads and parameters):
//!   - `again.<kept|dropped|unkept|open>`: a capture ended under the same key
//!     before, and its computation is kept (but not in this store), not kept
//!     for a full key or for size, not kept as it stopped or faulted, or
//!     not ended;
//!   - `shape.raw[<components>].canon[<components>]`: the same request has been
//!     seen with another shape; the components of the shape that differ from
//!     the nearest shape seen, as the digests of the key's shape hold them
//!     (`raw`), and as a digest with each variable renamed by its rank among
//!     the variables of the nodes holds them (`canon`; `-` where the two shapes
//!     are equal);
//!   - `reads`: the content and example were seen, with other relations;
//!   - `new`: the content was not seen.
//! - `capture.<outcome>`: the end of a computation that the walk made. The
//!   outcomes are `kept`, `dropped.full` (too many kept under the key),
//!   `dropped.big` (more than a tier's share), `stopped` (a value that is not
//!   kept) and `fault`. `work` is the table work counted and `ms` the time
//!   of the computation, with the computations nested in it.
//! - `captured.<noentry cause class>`: the same, by the class of the cause
//!   above: `again`, `shape`, `reads`, `new`, `entries` (some are kept, and
//!   none replayed).

use std::cell::{Cell, RefCell};
use std::collections::BTreeMap;
use std::hash::{Hash, Hasher};
use std::sync::atomic::{AtomicU64, AtomicU8, Ordering};
use std::sync::{Mutex, OnceLock};
use std::time::Instant;

use super::names::{digest, Names};
use super::CarryKey;
use crate::eval::ir::{ClauseIr, CompiledBody};
use crate::eval::join::Part;
use crate::eval::plan::VariableOrder;
use crate::hash::{StableHashMap, StableHashSet, StableHasher};
use crate::relations::ColumnIndex;

static STATE: AtomicU8 = AtomicU8::new(UNSET);
const UNSET: u8 = 0;
const OFF: u8 = 1;
const ON: u8 = 2;

/// Whether the counters are on.
#[inline(always)]
pub(super) fn enabled() -> bool {
    match STATE.load(Ordering::Relaxed) {
        OFF => false,
        ON => true,
        _ => read_environment(),
    }
}

#[cold]
fn read_environment() -> bool {
    let on = std::env::var_os("ARCLOG_CARRY_STATS").is_some_and(|value| !value.is_empty() && value != "0");
    STATE.store(if on { ON } else { OFF }, Ordering::Relaxed);
    on
}

/// What a kept computation is of.
#[derive(Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Debug)]
pub(super) enum Kind {
    Part,
    Clause,
}

impl Kind {
    fn name(self) -> &'static str {
        match self {
            Kind::Part => "part",
            Kind::Clause => "clause",
        }
    }

    fn components(self) -> &'static [&'static str] {
        match self {
            Kind::Part => &["ranks", "nodes", "types", "order", "columns", "clause_columns"],
            Kind::Clause => &["clause", "conjuncts"],
        }
    }
}

/// The digest of each component of a shape, as the key holds it and as it is
/// with its variables renamed.
pub(super) struct Components {
    kind: Kind,
    raw: Vec<u64>,
    canon: Vec<u64>,
}

/// The components of the shape of `part`, as [`super::part_shape`] gives it.
pub(super) fn part_components(clause: &ClauseIr, part: &Part, order: &VariableOrder, columns: &[ColumnIndex]) -> Components {
    let mut ranks: Vec<usize> = (0..part.nodes.len()).collect();
    ranks.sort_unstable_by_key(|&at| part.nodes[at]);
    let own = part.order(order, &[]);
    let projected: Vec<_> = columns.iter().map(|column| clause.columns[usize::from(column.0)]).collect();
    let held: Vec<_> = clause.columns.iter().copied().filter(|variable| part.variables.contains(variable)).collect();
    let raw = vec![
        digest(|h| ranks.hash(h)),
        digest(|h| part.nodes.iter().for_each(|&node| clause.nodes[node].hash(h))),
        digest(|h| {
            part.variables.len().hash(h);
            part.variables.iter().for_each(|variable| (variable, &clause.variables[usize::from(variable.0)].ty).hash(h));
        }),
        digest(|h| own.hash(h)),
        digest(|h| projected.hash(h)),
        digest(|h| held.hash(h)),
    ];
    let names = Names::of(clause, part.nodes.iter().map(|&node| &clause.nodes[node]), &part.variables);
    let canon = vec![
        digest(|h| ranks.hash(h)),
        digest(|h| part.nodes.iter().for_each(|&node| names.node(&clause.nodes[node], h))),
        digest(|h| {
            names.variables(&part.variables, h);
            names.types(clause, h);
        }),
        digest(|h| names.variables(&own, h)),
        digest(|h| names.variables(&projected, h)),
        digest(|h| names.variables(&held, h)),
    ];
    Components { kind: Kind::Part, raw, canon }
}

/// The components of the shape of `body`, as [`super::body_shape`] gives it.
pub(super) fn body_components(body: &CompiledBody) -> Components {
    let clause = &body.clause;
    let raw = vec![digest(|h| clause.hash(h)), digest(|h| body.conjuncts.hash(h))];
    let names = Names::of(clause, clause.nodes.iter(), &clause.columns);
    let canon = vec![
        digest(|h| {
            names.clause(clause, h);
            names.types(clause, h);
        }),
        digest(|h| body.conjuncts.hash(h)),
    ];
    Components { kind: Kind::Clause, raw, canon }
}

/// Offers the components of the shape that the next call of [`begin`] on
/// this thread takes.
pub(super) fn offer(components: impl FnOnce() -> Components) {
    if enabled() {
        PENDING.with(|pending| *pending.borrow_mut() = Some(components()));
    }
}

/// Why a key found no replay.
#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub(super) enum Reason {
    NoEntry,
    Work,
    Lookups,
}

/// What the capture of a miss needs to say of its call.
#[derive(Clone, Copy)]
pub(super) struct Note {
    kind: Kind,
    content: u64,
    request: u64,
    shape: u128,
    class: &'static str,
}

struct Current {
    note: Option<Note>,
    components: Option<Components>,
    reason: Reason,
}

/// What the process saw of a shape under one request.
struct Seen {
    raw: Vec<u64>,
    canon: Vec<u64>,
}

/// The most shapes kept for one request, and the most requests.
const SEEN_PER_REQUEST: usize = 16;
const MOST_REQUESTS: usize = 6_000_000;

#[derive(Default)]
struct State {
    tally: BTreeMap<String, (u64, u64, u64)>,
    contents: StableHashSet<u64>,
    requests: StableHashMap<u64, Vec<Seen>>,
    /// The end of the capture under a key: 0 none yet, 1 kept, 2 dropped, 3 not kept.
    keys: StableHashMap<(u64, u128), u8>,
}

fn state() -> &'static Mutex<State> {
    static STATE: OnceLock<Mutex<State>> = OnceLock::new();
    STATE.get_or_init(|| Mutex::new(State::default()))
}

thread_local! {
    static PENDING: RefCell<Option<Components>> = const { RefCell::new(None) };
    static CURRENT: RefCell<Current> = const { RefCell::new(Current { note: None, components: None, reason: Reason::NoEntry }) };
    static DROPPED: Cell<&'static str> = const { Cell::new("dropped.full") };
}

static CALLS: AtomicU64 = AtomicU64::new(0);

fn add(state: &mut State, name: String, work: u64, nanos: u64) {
    let entry = state.tally.entry(name).or_default();
    entry.0 += 1;
    entry.1 += work;
    entry.2 += nanos;
}

/// The id of the request of `key`: the content, the example, and the rows and
/// the layout of each relation it reads or takes as a parameter.
fn request_id(key: &CarryKey) -> u64 {
    let mut hasher = StableHasher::new();
    key.digest.hash(&mut hasher);
    for relation in key.request.relations() {
        relation.rows_hash().hash(&mut hasher);
        for part in relation.parts() {
            part.columns.hash(&mut hasher);
        }
    }
    key.request.parameters.len().hash(&mut hasher);
    hasher.finish()
}

fn content_id(key: &CarryKey) -> u64 {
    let mut hasher = StableHasher::new();
    key.request.clause.hash(&mut hasher);
    key.request.example.hash(&mut hasher);
    hasher.finish()
}

/// Starts the count of a call that found no entry in the walk's cache, for
/// `key`, whose shape [`offer`] gave components of.
pub(super) fn begin(key: &CarryKey) {
    if !enabled() {
        return;
    }
    let components = PENDING.with(|pending| pending.borrow_mut().take());
    let Some(kind) = components.as_ref().map(|components| components.kind) else { return };
    let note = Note { kind, content: content_id(key), request: request_id(key), shape: key.shape.0, class: "entries" };
    CURRENT.with(|current| *current.borrow_mut() = Current { note: Some(note), components, reason: Reason::NoEntry });
    let calls = CALLS.fetch_add(1, Ordering::Relaxed) + 1;
    add(&mut state().lock().expect("the counters are not poisoned"), format!("{}.call", kind.name()), 0, 0);
    if (calls >= 1024 && calls.is_power_of_two()) || calls % 131_072 == 0 {
        report(calls);
    }
}

/// Notes why the replay of the call in progress failed.
pub(super) fn reason(reason: Reason) {
    if enabled() {
        CURRENT.with(|current| current.borrow_mut().reason = reason);
    }
}

/// Counts a hit of the call in progress, of a computation that counted `work`.
pub(super) fn hit(work: u64) {
    if !enabled() {
        return;
    }
    let Some(note) = CURRENT.with(|current| current.borrow().note) else { return };
    add(&mut state().lock().expect("the counters are not poisoned"), format!("{}.hit", note.kind.name()), work, 0);
}

/// Counts the miss of the call in progress and its cause, and notes what the
/// process saw of its key.
pub(super) fn missed() {
    if !enabled() {
        return;
    }
    let (note, components, reason) = CURRENT.with(|current| {
        let mut current = current.borrow_mut();
        (current.note, current.components.take(), current.reason)
    });
    let (Some(mut note), Some(components)) = (note, components) else { return };
    let kind = note.kind.name();
    let mut state = state().lock().expect("the counters are not poisoned");
    let state = &mut *state;
    add(state, format!("{kind}.miss"), 0, 0);
    let key = (note.request, note.shape);
    match reason {
        Reason::Work => add(state, format!("{kind}.miss.work"), 0, 0),
        Reason::Lookups => add(state, format!("{kind}.miss.lookups"), 0, 0),
        Reason::NoEntry => {
            add(state, format!("{kind}.miss.noentry"), 0, 0);
            let (class, label) = if let Some(&ended) = state.keys.get(&key) {
                ("again", format!("again.{}", ["open", "kept", "dropped", "unkept"][usize::from(ended)]))
            } else if let Some(seen) = state.requests.get(&note.request) {
                let names = note.kind.components();
                let differs = |one: &[u64], other: &[u64]| -> Vec<&'static str> {
                    names.iter().zip(one.iter().zip(other)).filter(|(_, (a, b))| a != b).map(|(name, _)| *name).collect()
                };
                let nearest = seen.iter().min_by_key(|seen| differs(&components.raw, &seen.raw).len()).expect("a shape seen under the request");
                let raw = differs(&components.raw, &nearest.raw).join("+");
                let canon = differs(&components.canon, &nearest.canon).join("+");
                let canon = if canon.is_empty() { "-".to_string() } else { canon };
                ("shape", format!("shape.raw[{raw}].canon[{canon}]"))
            } else if state.contents.contains(&note.content) {
                ("reads", "reads".to_string())
            } else {
                ("new", "new".to_string())
            };
            add(state, format!("{kind}.noentry.{label}"), 0, 0);
            note.class = class;
        }
    }
    if state.requests.len() < MOST_REQUESTS {
        state.contents.insert(note.content);
        let seen = state.requests.entry(note.request).or_default();
        if seen.len() < SEEN_PER_REQUEST && !seen.iter().any(|seen| seen.raw == components.raw) {
            seen.push(Seen { raw: components.raw, canon: components.canon });
        }
        state.keys.entry(key).or_insert(0);
    }
    CURRENT.with(|current| current.borrow_mut().note = Some(note));
}

/// The note of the call in progress, for its capture.
pub(super) fn current() -> Option<Note> {
    if enabled() { CURRENT.with(|current| current.borrow().note) } else { None }
}

/// Notes that the keeping of a computation dropped it, for `why`.
pub(super) fn dropped(why: &'static str) {
    if enabled() {
        DROPPED.with(|dropped| dropped.set(why));
    }
}

/// How a capture ended.
pub(super) enum End {
    Kept,
    Dropped,
    Stopped,
    Fault,
}

/// Counts the end of the capture of `note`'s call, which counted `work` and
/// ran from `started`.
pub(super) fn captured(note: Note, end: End, work: u64, started: Instant) {
    let nanos = u64::try_from(started.elapsed().as_nanos()).unwrap_or(u64::MAX);
    let kind = note.kind.name();
    let (name, mark) = match end {
        End::Kept => ("kept", 1),
        End::Dropped => (DROPPED.with(Cell::get), 2),
        End::Stopped => ("stopped", 3),
        End::Fault => ("fault", 3),
    };
    let mut state = state().lock().expect("the counters are not poisoned");
    add(&mut state, format!("{kind}.capture.{name}"), work, nanos);
    add(&mut state, format!("{kind}.captured.{}", note.class), work, nanos);
    state.keys.insert((note.request, note.shape), mark);
}

fn report(calls: u64) {
    let state = state().lock().expect("the counters are not poisoned");
    for (name, (count, work, nanos)) in &state.tally {
        eprintln!("carry-stats @{calls} {name} n={count} work={work} ms={}", nanos / 1_000_000);
    }
}
