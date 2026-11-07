//! The task session: the engine's state for one task, its result cache,
//! its intern table, and the largest counts of its evaluations.
//!
//! The result cache keys an entry by its content, a [`ResultKey`], keeps with
//! it the [`crate::eval::Cost`] of its computation, and
//! gives each relation it holds an id by its rows. It evicts the entries
//! least recently used while its bytes exceed its share of the session's
//! byte bound, [`crate::eval::cache::cache_bytes_bound`].

use std::collections::BTreeMap;
use std::sync::atomic::{AtomicBool, AtomicU64, AtomicUsize, Ordering};
use std::sync::{Arc, Mutex, OnceLock, RwLock};

use crate::eval::pool::InFlight;
use crate::eval::{Caps, Cost, ReachedBound, RelationValue};
use crate::hash::{StableHash, StableHashMap};
use crate::relations::{Relation, RelationPart, SharedRows, StorageTag};
use crate::program::FactRelation;
use crate::registry::LibName;
use crate::task::Task;
use crate::terms::{Example, InternTable, TermId};

/// What a result-cache entry evaluates: a form's resolved content, for a
/// clause or a part of a body, the compiled clause of a body of a form
/// over a lib component, or the resolved content of a node of the
/// dependency graph, for an output of an instance. The variants never
/// compare equal.
#[derive(Clone, PartialEq, Eq, Hash, Debug)]
pub enum ResultContent {
    Form(crate::resolver::ResolvedContent),
    Body(crate::eval::ir::ClauseIr),
    Node(crate::resolver::ResolvedContent),
}

/// The key of a result-cache entry: the content of the conjunction
/// it evaluates, a whole clause or a part of a body, the identity of each
/// relation it reads, the grid it runs on, where it runs on one, and
/// the parameter values it reads. It compares as a key of canonical parts
/// does ([`crate::program`]).
#[derive(Clone, PartialEq, Eq, Hash, Debug)]
pub struct ResultKey {
    pub clause: ResultContent,
    /// The relations the clause reads, in the order of its reads.
    pub reads: Box<[RelationId]>,
    /// The example whose input grid the clause runs on, for an entry
    /// evaluated per grid, such as a `RULE` relation's. A task session holds
    /// one task, so the example fixes the grid. `None` is for an entry that
    /// runs on no one grid, such as a `RULE` relation's lifted form or a
    /// `DET` relation, whose grids reach it through the relations it reads.
    pub example: Option<crate::terms::Example>,
    /// The values of each parameter the clause reads, as the relation of
    /// their rows, in the order of its reads.
    pub parameters: Box<[RelationId]>,
}

/// Whether a lookup that finds `a` does what one that found `b` did: values
/// of the same kind, a relation's held in parts of the same columns, and a
/// stop at the same bound. Two values under one key hold the same rows.
fn alike(a: &CachedValue, b: &CachedValue) -> bool {
    match (a, b) {
        (RelationValue::Rows(a), RelationValue::Rows(b)) => a.parts().len() == b.parts().len() && a.parts().iter().zip(b.parts()).all(|(a, b)| a.columns == b.columns),
        (RelationValue::Undefined, RelationValue::Undefined) => true,
        (RelationValue::Stopped(a), RelationValue::Stopped(b)) => a == b,
        _ => false,
    }
}

/// The id of a relation in a task session. The session gives each id once
/// and never gives it again, so two relations with equal ids have equal
/// rows. Two relations with equal rows can have distinct ids, such as a
/// relation made again after the result cache evicted it, which costs a new
/// computation and no correctness.
#[derive(Clone, Copy, PartialEq, Eq, Hash, Debug)]
pub struct RelationId(u32);

/// The value of a result-cache entry: a relation, `undefined`, or the
/// bound of a stop, with no form.
pub type CachedValue = RelationValue<ReachedBound>;

/// What an entry's computation gives the threads that wait for it: the value
/// and the cost of the computation.
pub type Costed = (CachedValue, Cost);

/// The memo table of evaluated relations, keyed by content, bounded by bytes.
/// Several threads read and write it at once through a shared reference.
/// An entry holds a relation, `undefined`, or a bound whose
/// [`crate::eval::ReachedBound::is_stored`] holds, with no form, and never
/// a partial relation. The cache holds no path of a program, since the
/// programs that share an entry hold its clause at different paths.
///
/// The cache holds each relation that an entry's key reads or that an
/// entry's value is once, under its id, and counts its bytes once, and the
/// rows that several of its relations share, such as a part's rows that a
/// body's relation holds too, once. A
/// relation that no entry holds any longer leaves the cache, and a relation
/// made again with its rows then takes a new id.
#[derive(Debug, Default)]
pub struct ResultCache {
    state: Mutex<CacheState>,
    /// The count of requests that found their entry, for a check that the
    /// cases of a session share entries.
    found: AtomicU64,
    /// The entries that a thread of the pool computes, which a thread that
    /// asks for one of them waits for.
    in_flight: InFlight<ResultKey, Costed>,
    /// Whether a capture is open ([`ResultCache::begin_capture`]), so that
    /// [`ResultCache::record`] keeps the lookups, ids and stores that
    /// [`crate::eval::cache`] makes in `recorded`.
    recording: AtomicBool,
    recorded: Mutex<Captured>,
    /// The count of threads that keep the events they make in this cache
    /// ([`ResultCache::record_on_thread`]).
    thread_recorders: AtomicUsize,
}

/// What the open captures of a result cache keep ([`ResultCache::begin_capture`]).
#[derive(Debug, Default)]
struct Captured {
    /// The lookups, ids and stores since the outermost capture began, in
    /// their order.
    events: Vec<crate::eval::cache::Recorded>,
    /// For each open capture, the outermost first, the largest counts that
    /// [`TaskSession::record_counts`] was given since it began.
    counts: Vec<Counts>,
    /// The most events that the outermost capture keeps, where it is limited
    /// ([`ResultCache::begin_capture_limited`]).
    limit: Option<usize>,
    /// Whether the events passed `limit`: the capture then keeps none, and
    /// stops recording.
    overflowed: bool,
}

/// An open capture of a result cache's events and counts
/// ([`ResultCache::begin_capture`]).
#[derive(Debug)]
pub struct Capture {
    /// The place in the cache's events where the capture began.
    mark: usize,
    /// The count of captures open when it began, itself included.
    depth: usize,
}

thread_local! {
    /// The events that this thread makes in one result cache, by the
    /// cache's address, while a [`ThreadRecording`] of it lives.
    static THREAD_RECORDED: std::cell::RefCell<Option<(usize, Vec<crate::eval::cache::Recorded>)>> = const { std::cell::RefCell::new(None) };
}

/// The keeping of the lookups, ids and stores that one thread makes in one
/// result cache ([`ResultCache::record_on_thread`]); dropping it stops the
/// keeping.
pub(crate) struct ThreadRecording<'c> {
    cache: &'c ResultCache,
}

impl ThreadRecording<'_> {
    /// The events kept, in their order; the keeping stops.
    pub(crate) fn finish(self) -> Vec<crate::eval::cache::Recorded> {
        THREAD_RECORDED.with(|cell| cell.borrow_mut().take()).map(|(_, events)| events).unwrap_or_default()
    }
}

impl Drop for ThreadRecording<'_> {
    fn drop(&mut self) {
        THREAD_RECORDED.with(|cell| cell.borrow_mut().take());
        self.cache.thread_recorders.fetch_sub(1, Ordering::Relaxed);
    }
}

#[derive(Debug, Default)]
struct CacheState {
    entries: StableHashMap<Arc<ResultKey>, Entry>,
    /// The key of each entry by the tick of its last use.
    recency: BTreeMap<u64, Arc<ResultKey>>,
    clock: u64,
    relations: StableHashMap<RelationId, HeldRelation>,
    /// The ids of the held relations by the hash of their rows.
    by_rows: StableHashMap<StableHash, Vec<RelationId>>,
    next_id: u32,
    /// The rows of the parts of the held relations, by their identity: the
    /// count of the held relations' parts that share them, and their bytes.
    rows: StableHashMap<SharedRows, (usize, usize)>,
    /// The bytes of the held relations, of their rows and of the entries.
    bytes: usize,
    /// The bytes of the held relations' indexes, as of the last sum. An
    /// index is built after its relation is held, so an eviction sums them
    /// where it could matter, see [`SUM_MARGIN`] and [`SUM_INTERVAL`].
    index_bytes: usize,
    /// The evictions since the last sum of `index_bytes`.
    since_sum: usize,
    /// Whether the bytes have passed the bound of an eviction.
    evicted: bool,
    /// The times the bytes have passed the bound of an eviction.
    evictions: u64,
    /// The place that an entry made now takes ([`ResultCache::mark`]).
    mark: u32,
    /// The view of the cache that requests have now ([`ResultCache::begin_view`]).
    view: Option<CacheView>,
    /// The views begun, so that each has an id of its own.
    views: u64,
}

/// What requests find during a view: the entries marked below `below`, and
/// those that the view `id` made or asked to store.
#[derive(Clone, Copy, Debug)]
struct CacheView {
    below: u32,
    id: u64,
}

/// The mark of an entry that a view made, which no later view finds.
const MADE_IN_VIEW: u32 = u32::MAX;

#[derive(Debug)]
struct Entry {
    value: CachedValue,
    /// What the entry's computation charged, which a hit charges again.
    cost: Cost,
    /// The id of the value's relation, where the value is one.
    rows: Option<RelationId>,
    used: u64,
    /// The place of the entry's making ([`ResultCache::mark`]).
    made: u32,
    /// The view that last stored the entry, 0 for none.
    stored_in: u64,
}

impl Entry {
    fn found_under(&self, view: Option<CacheView>) -> bool {
        view.is_none_or(|view| self.made < view.below || self.stored_in == view.id)
    }
}

#[derive(Debug)]
struct HeldRelation {
    relation: Arc<Relation>,
    hash: StableHash,
    bytes: usize,
    /// The count of entries whose key reads the relation or whose value it
    /// is.
    holders: usize,
    /// The storage of relations whose rows a comparison found equal to this
    /// relation's, at most [`SAME_STORAGE`] of them, so that a later lookup
    /// of one of them compares no rows. No relation with these rows has
    /// another id while this one is held, so a lookup gives the id it would
    /// give by comparing. The tags keep no rows, and `bytes` counts each of
    /// them at [`StorageTag::BYTES`].
    same: Vec<StorageTag>,
}

/// The most relations a held relation keeps the storage of. Past it the
/// oldest goes, which costs a comparison of rows and no correctness.
const SAME_STORAGE: usize = 8;

const UNPOISONED: &str = "a result cache that no panic poisoned";

/// An eviction drops the indexes of a relation whose indexes pass this
/// fraction of its bound before it drops an entry. Provisional: one soak run
/// on one task, where one relation's indexes held most of the bound.
const INDEX_SHARE: usize = 16;

/// An eviction sums the held relations' index bytes only where the last
/// known bytes are within `1 / SUM_MARGIN` of the bound or past it, or when
/// [`SUM_INTERVAL`] evictions have passed since the last sum. An index grows
/// after its relation is held, so between sums the bytes can pass the bound
/// unseen: the cache can stay over its bound by the index growth of up to
/// [`SUM_INTERVAL`] stores, until the next sum evicts as usual.
const SUM_MARGIN: usize = 16;
const SUM_INTERVAL: usize = 1024;

/// An eviction that finds the bytes over the bound drops down to
/// `bound - bound / EVICT_MARGIN`. That target lies under the line
/// `bound - bound / SUM_MARGIN` of the quick return, so the stores after an
/// eviction return early until the bytes grow back to that line.
const EVICT_MARGIN: usize = 8;
const _: () = assert!(EVICT_MARGIN < SUM_MARGIN);

impl ResultCache {
    /// The value cached under `key` and its cost, if any. A value found counts
    /// as a use of its entry.
    pub fn get(&self, key: &ResultKey) -> Option<Costed> {
        let mut state = self.state.lock().expect(UNPOISONED);
        let value = state.touch(key)?;
        self.found.fetch_add(1, Ordering::Relaxed);
        Some(value)
    }

    /// Caches `value` under `key`, with the `cost` of its computation. A stop
    /// that is not stored is a fault of the caller, so this panics on one.
    pub fn insert(&self, key: ResultKey, value: CachedValue, cost: Cost) {
        if let RelationValue::Stopped(bound) = &value {
            assert!(bound.is_stored(), "a stop at a bound that the cache stores");
        }
        self.state.lock().expect(UNPOISONED).insert(key, value, cost);
    }

    /// Makes the events `events`, which a cache recorded
    /// ([`ResultCache::begin_capture`]) in a session that shares this
    /// session's intern table, where each would do here what it did there,
    /// and gives whether it made them. They would where each lookup finds
    /// here, after the events before it, an entry whose value has the rows
    /// of the value it found there, held in parts of the same columns, or a
    /// stop at the same bound, and finds no entry where it found none. The
    /// cache then makes them as [`crate::eval::cache`] made them: a lookup
    /// that finds its entry counts as a use of it, an id holds a copy of its
    /// relation where the cache holds none of its rows, and a store caches
    /// its value and evicts under `bound`.
    pub(crate) fn replay(&self, events: &[crate::eval::cache::Recorded], bound: usize) -> bool {
        use crate::eval::cache::Recorded;
        let mut state = self.state.lock().expect(UNPOISONED);
        if !state.replays(events) {
            return false;
        }
        for event in events {
            match event {
                Recorded::Lookup { key, found: Some(_) } => {
                    let key = state.held_key(key).expect("a replayed lookup finds the relations of its key");
                    let found = state.touch(&key);
                    debug_assert!(found.is_some(), "a replayed lookup finds the entry it found");
                    self.found.fetch_add(1, Ordering::Relaxed);
                }
                Recorded::Lookup { found: None, .. } => {}
                Recorded::Id { relation } => {
                    state.id_of(relation);
                }
                Recorded::Store { key, value, cost } => {
                    let reads = key.reads.iter().map(|relation| state.id_of(relation)).collect();
                    let parameters = key.parameters.iter().map(|relation| state.id_of(relation)).collect();
                    state.insert(ResultKey { clause: key.clause.clone(), reads, example: key.example, parameters }, value.clone(), *cost);
                    state.evict(bound);
                }
            }
        }
        true
    }

    /// The keys, by the ids of their relations, of the entries that
    /// `events` found, each a lookup that found its entry, where the cache
    /// holds the relations of each key; `None` otherwise.
    pub(crate) fn found_keys(&self, events: &[crate::eval::cache::Recorded]) -> Option<Box<[ResultKey]>> {
        use crate::eval::cache::Recorded;
        let state = self.state.lock().expect(UNPOISONED);
        events
            .iter()
            .map(|event| match event {
                Recorded::Lookup { key, found: Some(_) } => state.held_key(key),
                _ => None,
            })
            .collect()
    }

    /// [`ResultCache::replay`] of `events`, each a lookup that found its
    /// entry, whose keys by the ids of their relations are `keys`
    /// ([`ResultCache::found_keys`]), where the cache holds an entry under
    /// each of `keys`: an id names one relation's rows for the life of the
    /// session, so that entry is the one each lookup would find. Gives
    /// whether it made them; `false` changes nothing.
    pub(crate) fn replay_found(&self, events: &[crate::eval::cache::Recorded], keys: &[ResultKey]) -> bool {
        use crate::eval::cache::Recorded;
        let mut state = self.state.lock().expect(UNPOISONED);
        let held = events.len() == keys.len()
            && events.iter().zip(keys).all(|(event, key)| match (event, state.entries.get(key).filter(|entry| entry.found_under(state.view))) {
                (Recorded::Lookup { found: Some(found), .. }, Some(entry)) => alike(&entry.value, found),
                _ => false,
            });
        if !held {
            return false;
        }
        for key in keys {
            state.touch(key);
            self.found.fetch_add(1, Ordering::Relaxed);
        }
        true
    }

    /// Whether the cache's bytes have passed the bound of an eviction, so
    /// that it dropped the relations no entry holds, and entries.
    pub fn evicted(&self) -> bool {
        self.state.lock().expect(UNPOISONED).evicted
    }

    /// The times the cache's bytes have passed the bound of an eviction.
    pub fn evictions(&self) -> u64 {
        self.state.lock().expect(UNPOISONED).evictions
    }

    /// Gives each entry made from now on the place `mark`: the place of the
    /// form under evaluation in its program.
    pub fn mark(&self, mark: u32) {
        self.state.lock().expect(UNPOISONED).mark = mark;
    }

    /// Until [`ResultCache::end_view`], a request finds only the entries
    /// marked below `below` and those stored since this call. Those are the
    /// entries a cache holds that an evaluation of the forms below `below`
    /// left, with no later form evaluated.
    pub fn begin_view(&self, below: u32) {
        let mut state = self.state.lock().expect(UNPOISONED);
        state.views += 1;
        let id = state.views;
        state.view = Some(CacheView { below, id });
    }

    /// Ends the view of [`ResultCache::begin_view`], and drops the entries
    /// that it alone made and the relations that no entry holds.
    pub fn end_view(&self) {
        let mut state = self.state.lock().expect(UNPOISONED);
        state.view = None;
        let made: Vec<Arc<ResultKey>> = state.entries.iter().filter(|(_, entry)| entry.made == MADE_IN_VIEW).map(|(key, _)| Arc::clone(key)).collect();
        for key in made {
            state.remove_entry(&key);
        }
        let unheld: Vec<RelationId> = state.relations.iter().filter(|(_, held)| held.holders == 0).map(|(&id, _)| id).collect();
        for id in unheld {
            state.drop_relation(id);
        }
    }

    /// Starts keeping each lookup, id and store that [`crate::eval::cache`]
    /// makes, from every thread, and the largest counts that
    /// [`TaskSession::record_counts`] is given, until the capture ends
    /// ([`ResultCache::end_capture`]). A capture may begin while another is
    /// open, and ends before it.
    pub fn begin_capture(&self) -> Capture {
        self.begin(None)
    }

    /// [`ResultCache::begin_capture`], where the capture keeps at most `limit`
    /// events: past them it keeps none and records nothing more, which
    /// [`ResultCache::end_capture_limited`] gives as `None`. A capture that
    /// begins while another is open is not limited, since the other keeps
    /// its events.
    pub fn begin_capture_limited(&self, limit: usize) -> Capture {
        self.begin(Some(limit))
    }

    fn begin(&self, limit: Option<usize>) -> Capture {
        let mut captured = self.recorded.lock().expect(UNPOISONED);
        if captured.counts.is_empty() {
            captured.limit = limit;
            captured.overflowed = false;
        }
        captured.counts.push(Counts::default());
        self.recording.store(true, Ordering::Relaxed);
        Capture { mark: captured.events.len(), depth: captured.counts.len() }
    }

    /// The lookups, ids and stores kept since `capture` began, in their
    /// order, and the largest counts recorded since then. A capture that
    /// was open when this one began keeps them too, and the cache keeps
    /// none once no capture is open.
    pub fn end_capture(&self, capture: Capture) -> (Vec<crate::eval::cache::Recorded>, Counts) {
        let (events, counts, _) = self.end(capture);
        (events, counts)
    }

    /// [`ResultCache::end_capture`] of a capture that
    /// [`ResultCache::begin_capture_limited`] began: `None` where its events
    /// passed the limit.
    pub fn end_capture_limited(&self, capture: Capture) -> Option<(Vec<crate::eval::cache::Recorded>, Counts)> {
        let (events, counts, overflowed) = self.end(capture);
        (!overflowed).then_some((events, counts))
    }

    fn end(&self, capture: Capture) -> (Vec<crate::eval::cache::Recorded>, Counts, bool) {
        let mut captured = self.recorded.lock().expect(UNPOISONED);
        assert_eq!(captured.counts.len(), capture.depth, "a capture ends before the one that was open when it began");
        let counts = captured.counts.pop().expect("an open capture");
        let mut overflowed = false;
        let events = if captured.counts.is_empty() {
            self.recording.store(false, Ordering::Relaxed);
            overflowed = std::mem::take(&mut captured.overflowed);
            captured.limit = None;
            std::mem::take(&mut captured.events)
        } else {
            captured.events[capture.mark..].to_vec()
        };
        (events, counts, overflowed)
    }

    /// Keeps `counts`, as the count of one evaluation that ended with no
    /// stop, in each open capture, each as the larger of it and the count
    /// the capture holds.
    fn capture_counts(&self, counts: Counts) {
        if !self.recording.load(Ordering::Relaxed) {
            return;
        }
        for held in &mut self.recorded.lock().expect(UNPOISONED).counts {
            held.bindings = held.bindings.max(counts.bindings);
            held.rows = held.rows.max(counts.rows);
        }
    }

    /// Keeps the lookup, id or store `event()` where a capture is open,
    /// and where this thread keeps its events in this cache
    /// ([`ResultCache::record_on_thread`]).
    #[inline]
    pub(crate) fn record(&self, event: impl FnOnce() -> crate::eval::cache::Recorded) {
        let recording = self.recording.load(Ordering::Relaxed);
        let threads = self.thread_recorders.load(Ordering::Relaxed) > 0;
        if !recording && !threads {
            return;
        }
        let event = event();
        if threads {
            let address = std::ptr::from_ref(self) as usize;
            THREAD_RECORDED.with(|cell| {
                if let Some((cache, events)) = &mut *cell.borrow_mut()
                    && *cache == address
                {
                    events.push(event.clone());
                }
            });
        }
        if recording {
            let mut captured = self.recorded.lock().expect(UNPOISONED);
            if captured.counts.len() == 1 && captured.limit.is_some_and(|limit| captured.events.len() >= limit) {
                captured.overflowed = true;
                captured.events = Vec::new();
                self.recording.store(false, Ordering::Relaxed);
            } else {
                captured.events.push(event);
            }
        }
    }

    /// Starts keeping each lookup, id and store that this thread makes in
    /// this cache, and no other thread's, until the result is finished or
    /// dropped. `None` where this thread already keeps the events of a
    /// cache.
    pub(crate) fn record_on_thread(&self) -> Option<ThreadRecording<'_>> {
        let address = std::ptr::from_ref(self) as usize;
        let started = THREAD_RECORDED.with(|cell| {
            let mut cell = cell.borrow_mut();
            if cell.is_some() {
                return false;
            }
            *cell = Some((address, Vec::new()));
            true
        });
        if !started {
            return None;
        }
        self.thread_recorders.fetch_add(1, Ordering::Relaxed);
        Some(ThreadRecording { cache: self })
    }

    /// The relation that the cache holds with the rows of `relation`, or
    /// `None` where it holds none.
    pub(crate) fn held_relation(&self, relation: &Relation) -> Option<Arc<Relation>> {
        let hash = relation.rows_hash();
        let mut state = self.state.lock().expect(UNPOISONED);
        let id = state.identify(hash, relation)?;
        Some(Arc::clone(&state.relations[&id].relation))
    }

    /// The id of a relation that the cache holds with the rows of
    /// `relation`, or `None` where it holds none.
    pub fn find_id(&self, relation: &Relation) -> Option<RelationId> {
        let hash = relation.rows_hash();
        self.state.lock().expect(UNPOISONED).identify(hash, relation)
    }

    /// The id of `relation`: that of a relation the cache holds with its
    /// rows, or a new id, under which the cache holds a copy of it until an
    /// entry holds it or an eviction drops it.
    pub fn relation_id(&self, relation: &Relation) -> RelationId {
        self.state.lock().expect(UNPOISONED).id_of(relation)
    }

    /// Where the cache's bytes exceed `bound`, drops the relations that no
    /// entry holds, then the entries least recently used, until the bytes
    /// are under `bound - bound / EVICT_MARGIN`.
    pub fn evict(&self, bound: usize) {
        self.state.lock().expect(UNPOISONED).evict(bound);
    }

    /// Release entries, relations, indexes and hash-table capacities between
    /// cases. The caller must have joined every evaluation using this cache.
    /// Relation IDs remain monotonic within the session.
    pub fn clear(&self) {
        let mut state=self.state.lock().expect(UNPOISONED);
        let next_id=state.next_id;
        *state=CacheState {next_id,..CacheState::default()};
    }

    /// The bytes the cache holds, which count toward the task session's
    /// bound.
    pub fn bytes(&self) -> usize {
        let state = self.state.lock().expect(UNPOISONED);
        state.bytes + state.index_bytes
    }

    /// The cache's entries, its relations, the bytes it counts, the indexes
    /// of its relations and their bytes, which it does not count.
    pub fn stats(&self) -> (usize, usize, usize, usize, usize) {
        let state = self.state.lock().expect(UNPOISONED);
        let (indexes, index_bytes) = state.relations.values().map(|held| held.relation.index_bytes()).fold((0, 0), |a, b| (a.0 + b.0, a.1 + b.1));
        (state.entries.len(), state.relations.len(), state.bytes, indexes, index_bytes)
    }

    /// The count of requests that found their entry in the cache.
    pub fn found(&self) -> u64 {
        self.found.load(Ordering::Relaxed)
    }

    /// The entries in flight on the pool's threads.
    pub fn in_flight(&self) -> &InFlight<ResultKey, Costed> {
        &self.in_flight
    }
}

impl CacheState {
    fn touch(&mut self, key: &ResultKey) -> Option<Costed> {
        let tick = self.tick();
        let view = self.view;
        let entry = self.entries.get_mut(key).filter(|entry| entry.found_under(view))?;
        let last = std::mem::replace(&mut entry.used, tick);
        let value = (entry.value.clone(), entry.cost);
        let key = self.recency.remove(&last).expect("a recency tick for each entry");
        self.recency.insert(tick, key);
        Some(value)
    }

    fn tick(&mut self) -> u64 {
        self.clock += 1;
        self.clock
    }

    /// The id of the relation held with the rows of `relation`, or of a
    /// copy of `relation` that the cache then holds.
    fn id_of(&mut self, relation: &Relation) -> RelationId {
        let hash = relation.rows_hash();
        match self.identify(hash, relation) {
            Some(id) => id,
            None => self.add(hash, Arc::new(relation.clone())),
        }
    }

    /// The key of the entry of `key` by the ids of its relations, where the
    /// cache holds a relation with the rows of each.
    fn held_key(&self, key: &crate::eval::cache::RecordedKey) -> Option<ResultKey> {
        let ids = |relations: &[Arc<Relation>]| -> Option<Box<[RelationId]>> { relations.iter().map(|relation| self.find(relation.rows_hash(), relation)).collect() };
        Some(ResultKey { clause: key.clause.clone(), reads: ids(&key.reads)?, example: key.example, parameters: ids(&key.parameters)? })
    }

    /// Whether `events` would do in this cache what they did where they were
    /// recorded, as [`ResultCache::replay`] gives. The check changes nothing.
    fn replays(&self, events: &[crate::eval::cache::Recorded]) -> bool {
        use crate::eval::cache::{Recorded, RecordedKey};
        type Added = StableHashMap<StableHash, Vec<Arc<Relation>>>;
        type Stored<'e> = StableHashMap<u64, Vec<(&'e RecordedKey, CachedValue)>>;
        // The relations and the entries that the events before add.
        let mut relations: Added = StableHashMap::default();
        let mut entries: Stored<'_> = StableHashMap::default();
        let held = |relations: &Added, relation: &Arc<Relation>| -> Option<Arc<Relation>> {
            let hash = relation.rows_hash();
            match self.find(hash, relation) {
                Some(id) => Some(Arc::clone(&self.relations[&id].relation)),
                None => relations.get(&hash)?.iter().find(|held| same_rows(held, relation)).cloned(),
            }
        };
        let entry = |entries: &Stored<'_>, key: &RecordedKey, digest: u64| -> Option<CachedValue> {
            if let Some(found) = self.held_key(key).and_then(|key| self.entries.get(&key)).filter(|entry| entry.found_under(self.view)) {
                return Some(found.value.clone());
            }
            entries.get(&digest)?.iter().find(|(stored, _)| stored.same(key)).map(|(_, value)| value.clone())
        };
        for event in events {
            match event {
                Recorded::Lookup { key, found } => {
                    let alike = match (&entry(&entries, key, key.digest()), found) {
                        (None, None) => true,
                        (Some(a), Some(b)) => alike(a, b),
                        _ => false,
                    };
                    if !alike {
                        return false;
                    }
                }
                Recorded::Id { relation } => {
                    if held(&relations, relation).is_none() {
                        relations.entry(relation.rows_hash()).or_default().push(Arc::clone(relation));
                    }
                }
                Recorded::Store { key, value, .. } => {
                    let digest = key.digest();
                    if entry(&entries, key, digest).is_some() {
                        continue;
                    }
                    let value = match value {
                        RelationValue::Rows(relation) => RelationValue::Rows(held(&relations, relation).unwrap_or_else(|| {
                            relations.entry(relation.rows_hash()).or_default().push(Arc::clone(relation));
                            Arc::clone(relation)
                        })),
                        other => other.clone(),
                    };
                    entries.entry(digest).or_default().push((key, value));
                }
            }
        }
        true
    }

    fn find(&self, hash: StableHash, relation: &Relation) -> Option<RelationId> {
        let ids = self.by_rows.get(&hash)?;
        let same = ids.iter().copied().find(|id| self.relations[id].same.iter().any(|tag| relation.has_storage(tag)));
        same.or_else(|| ids.iter().copied().find(|id| same_rows(&self.relations[id].relation, relation)))
    }

    /// [`CacheState::find`], which keeps the storage of `relation` with the
    /// held relation it found.
    fn identify(&mut self, hash: StableHash, relation: &Relation) -> Option<RelationId> {
        let id = self.find(hash, relation)?;
        let held = self.relations.get_mut(&id).expect("a held relation");
        if !held.relation.shares_storage(relation) && !held.same.iter().any(|tag| relation.has_storage(tag)) {
            let before = held.same.len() * StorageTag::BYTES;
            held.same.retain(StorageTag::live);
            if held.same.len() == SAME_STORAGE {
                held.same.remove(0);
            }
            held.same.push(relation.storage_tag());
            let after = held.same.len() * StorageTag::BYTES;
            held.bytes = held.bytes - before + after;
            self.bytes = self.bytes - before + after;
        }
        Some(id)
    }

    fn add(&mut self, hash: StableHash, relation: Arc<Relation>) -> RelationId {
        let id = RelationId(self.next_id);
        self.next_id = self.next_id.checked_add(1).expect("fewer than 2^32 relations in a session");
        let bytes = relation_bytes(&relation);
        self.bytes += bytes;
        for part in relation.parts() {
            let (holders, rows) = self.rows.entry(part.rows.shared()).or_insert((0, part.rows.bytes()));
            if *holders == 0 {
                self.bytes += *rows;
            }
            *holders += 1;
        }
        self.by_rows.entry(hash).or_default().push(id);
        self.relations.insert(id, HeldRelation { relation, hash, bytes, holders: 0, same: Vec::new() });
        id
    }

    fn insert(&mut self, key: ResultKey, value: CachedValue, cost: Cost) {
        let view = self.view;
        if let Some(entry) = self.entries.get_mut(&key) {
            if let Some(view) = view {
                entry.stored_in = view.id;
            }
            return;
        }
        let (value, rows) = match value {
            RelationValue::Rows(relation) => {
                let hash = relation.rows_hash();
                let id = self.identify(hash, &relation).unwrap_or_else(|| self.add(hash, relation));
                self.hold(id);
                (RelationValue::Rows(self.relations[&id].relation.clone()), Some(id))
            }
            other => (other, None),
        };
        for &id in key.reads.iter().chain(key.parameters.iter()) {
            self.hold(id);
        }
        self.bytes += entry_bytes(&key);
        let used = self.tick();
        let key = Arc::new(key);
        self.recency.insert(used, key.clone());
        let (made, stored_in) = view.map_or((self.mark, 0), |view| (MADE_IN_VIEW, view.id));
        self.entries.insert(key, Entry { value, cost, rows, used, made, stored_in });
    }

    fn remove_entry(&mut self, key: &Arc<ResultKey>) {
        let entry = self.entries.remove(key).expect("the key of an entry");
        self.recency.remove(&entry.used);
        self.bytes -= entry_bytes(key);
        for id in entry.rows.into_iter().chain(key.reads.iter().copied()).chain(key.parameters.iter().copied()) {
            self.release(id);
        }
    }

    /// Adds a holder to `id`, where the cache still holds it: an eviction
    /// can drop a relation that no entry holds between the key that reads
    /// it and the entry's insert.
    fn hold(&mut self, id: RelationId) {
        if let Some(held) = self.relations.get_mut(&id) {
            held.holders += 1;
        }
    }

    fn release(&mut self, id: RelationId) {
        let Some(held) = self.relations.get_mut(&id) else { return };
        held.holders -= 1;
        if held.holders == 0 {
            self.drop_relation(id);
        }
    }

    fn drop_relation(&mut self, id: RelationId) {
        let held = self.relations.remove(&id).expect("a held relation");
        self.bytes -= held.bytes;
        self.index_bytes = self.index_bytes.saturating_sub(held.relation.index_bytes().1);
        for part in held.relation.parts() {
            let shared = part.rows.shared();
            let (holders, rows) = self.rows.get_mut(&shared).expect("the rows of a held relation's part");
            *holders -= 1;
            if *holders == 0 {
                self.bytes -= *rows;
                self.rows.remove(&shared);
            }
        }
        let ids = self.by_rows.get_mut(&held.hash).expect("the ids of a held relation's hash");
        ids.retain(|&other| other != id);
        if ids.is_empty() {
            self.by_rows.remove(&held.hash);
        }
    }

    fn evict(&mut self, bound: usize) {
        self.since_sum += 1;
        if self.bytes + self.index_bytes < bound - bound / SUM_MARGIN && self.since_sum < SUM_INTERVAL {
            return;
        }
        self.since_sum = 0;
        self.index_bytes = self.relations.values().map(|held| held.relation.index_bytes().1).sum();
        if self.bytes + self.index_bytes <= bound {
            return;
        }
        self.evicted = true;
        self.evictions += 1;
        let target = bound - bound / EVICT_MARGIN;
        let unheld: Vec<RelationId> = self.relations.iter().filter(|(_, held)| held.holders == 0).map(|(&id, _)| id).collect();
        for id in unheld {
            self.drop_relation(id);
        }
        // An index is built again from its rows with no evaluation, so the
        // largest go before any entry.
        let mut indexed: Vec<(usize, RelationId)> = self.relations.iter().map(|(&id, held)| (held.relation.index_bytes().1, id)).collect();
        indexed.sort_unstable_by_key(|&(bytes, id)| std::cmp::Reverse((bytes, id.0)));
        for (bytes, id) in indexed {
            if bytes < bound / INDEX_SHARE || self.bytes + self.index_bytes <= target {
                break;
            }
            self.relations[&id].relation.drop_indexes();
            self.index_bytes = self.index_bytes.saturating_sub(bytes);
        }
        while self.bytes + self.index_bytes > target {
            let Some((_, key)) = self.recency.first_key_value().map(|(tick, key)| (*tick, Arc::clone(key))) else { break };
            self.remove_entry(&key);
        }
    }
}

/// Whether `a` and `b` hold the same rows. Where their parts split the
/// columns alike, the parts' rows are compared. Otherwise each part of one
/// relation is compared with the projection of the other onto its columns,
/// which reads only the parts of the other that hold those columns. Immutable
/// clone storage proves equality without visiting rows; part storage proves
/// only its column-matched part.
pub fn same_rows(a: &Relation, b: &Relation) -> bool {
    if std::ptr::eq(a, b) || a.shares_storage(b) {
        return true;
    }
    if a.arity() != b.arity() || a.len() != b.len() {
        return false;
    }
    if a.is_empty() {
        return true;
    }
    let columned = |relation: &Relation| relation.parts().iter().filter(|part| !part.columns.is_empty()).count();
    let counterpart = |part: &RelationPart| b.parts().iter().find(|other| other.columns == part.columns);
    let alike = columned(a) == columned(b)
        && a.parts().iter().filter(|part| !part.columns.is_empty()).all(|part| counterpart(part).is_some());
    if alike {
        return a.parts().iter().filter(|part| !part.columns.is_empty()).all(|part| {
            counterpart(part).is_some_and(|other| part.rows.shared()==other.rows.shared()
                || part.rows.rows().all(|row| other.rows.contains(row)))
        });
    }
    // Two sets of one size are equal where one holds the other, so one
    // direction is enough, the one that reads fewer parts per row. `len`
    // saturates, so a count at its top proves no size.
    let (walked, looked) = if a.parts().len() >= b.parts().len() { (a, b) } else { (b, a) };
    holds_rows(looked, walked) && (a.len() < u64::MAX || holds_rows(walked, looked))
}

/// Whether `holder`, a relation with a row, holds each row of `walked`, also
/// with a row. A row stands in a product where its projection stands in each
/// part, so each part reads only the parts of `walked` that hold its columns.
fn holds_rows(holder: &Relation, walked: &Relation) -> bool {
    /// Whether `part` holds each combination of a row of each of `sources`,
    /// where `row` holds the columns of the sources before them.
    fn projections_held(sources: &[&RelationPart], part: &RelationPart, row: &mut [TermId], projected: &mut [TermId]) -> bool {
        let Some((source, rest)) = sources.split_first() else {
            for (slot, column) in projected.iter_mut().zip(&part.columns) {
                *slot = row[usize::from(column.0)];
            }
            return part.rows.contains(projected);
        };
        source.rows.rows().all(|source_row| {
            for (column, &value) in source.columns.iter().zip(source_row) {
                row[usize::from(column.0)] = value;
            }
            projections_held(rest, part, row, projected)
        })
    }
    let mut row = vec![TermId::from_encoding(0); usize::from(walked.arity())];
    holder.parts().iter().filter(|part| !part.columns.is_empty()).all(|part| {
        let sources: Vec<&RelationPart> = walked.parts().iter().filter(|source| source.columns.iter().any(|column| part.columns.contains(column))).collect();
        let mut projected = vec![TermId::from_encoding(0); part.columns.len()];
        projections_held(&sources, part, &mut row, &mut projected)
    })
}

/// The bytes of `relation`'s parts beside their rows.
fn relation_bytes(relation: &Relation) -> usize {
    std::mem::size_of::<Relation>()
        + relation.parts().iter().map(|part| std::mem::size_of::<RelationPart>() + std::mem::size_of_val(&*part.columns)).sum::<usize>()
}

/// The bytes of an entry beside the relations it holds.
fn entry_bytes(key: &ResultKey) -> usize {
    let clause = match &key.clause {
        ResultContent::Form(content) | ResultContent::Node(content) => content.bytes(),
        ResultContent::Body(ir) => std::mem::size_of_val(&*ir.variables) + std::mem::size_of_val(&*ir.nodes) + std::mem::size_of_val(&*ir.columns),
    };
    std::mem::size_of::<ResultKey>()
        + std::mem::size_of::<Entry>()
        + clause
        + std::mem::size_of_val(&*key.reads)
        + std::mem::size_of_val(&*key.parameters)
}

/// The engine's state for one task: its result cache, its intern table and
/// the caps of its evaluations. The caps are fixed for the session, so each
/// stop that the result cache stores at a cap holds for every later request
/// of that entry in the session.
/// The evaluations of the pool's threads share one session through a
/// shared reference: the intern table stands behind a read-write lock,
/// since interning writes it and reading a content reads it, and the
/// result cache synchronizes its own entries.
#[derive(Clone, Debug)]
pub struct TaskSession {
    pub intern: Arc<RwLock<InternTable>>,
    pub results: Arc<ResultCache>,
    /// The rows of the branches of unions that are a clause's whole body.
    pub(crate) branches: Arc<crate::eval::join::branches::BranchMemo>,
    /// The caps of every evaluation in the session.
    pub caps: Caps,
    /// The bound on the session's bytes.
    pub bound: SessionBound,
    /// Byte reservations owned by transient/materialized buffers outside the
    /// intern and result stores. Shared buffers retain one reservation.
    allocated: Arc<AtomicUsize>,
    /// The largest bindings tried of any one evaluation that ended with no
    /// stop, an atomic maximum, so it does not depend on the order of the
    /// threads.
    largest_bindings: Arc<AtomicU64>,
    /// The largest rows held of any one such evaluation, an atomic maximum.
    largest_rows: Arc<AtomicU64>,
    /// The fact relations built so far, one per fact and example, each
    /// built on its first use. A session serves one task.
    facts: Arc<Mutex<StableHashMap<(FactRelation, Option<Example>), Arc<Relation>>>>,
    /// The rows of the native proposers so far, one relation per proposer
    /// and example, each built on its first use, as `facts` keeps a fact's:
    /// they read the grids of the session's task alone.
    native_rows: Arc<Mutex<StableHashMap<(LibName, Option<Example>), Arc<Relation>>>>,
    /// The domains that the liveness walks of the decodes of this session
    /// keep, made on the first walk.
    det_probes: Arc<OnceLock<crate::decode::det_memo::ProbeMemo>>,
    /// The domains that the table walks of the decodes of this session
    /// keep, made on the first walk.
    det_domains: Arc<OnceLock<crate::decode::det_memo::SessionMemo>>,
    /// The masks that the decodes of the session computed, by the path of
    /// tokens that reached each state.
    pub(crate) path_masks: Arc<Mutex<crate::decode::PathMasks>>,
}

/// A count of bindings tried and a count of rows held.
#[derive(Clone, Copy, PartialEq, Eq, Debug, Default)]
pub struct Counts {
    pub bindings: u64,
    pub rows: u64,
}

/// The bound on the bytes of a task session of the engine's runs.
pub const SESSION_BYTES: usize = 1 << 32;

/// The bound on a task session's bytes, which the intern table's and the
/// result cache's bytes count toward. Reaching it is an alert.
#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub struct SessionBound {
    pub bytes: usize,
}

/// A task session whose bytes reached its bound, which is an alert.
#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub struct ReachedSessionBound {
    pub bytes: usize,
    pub bound: SessionBound,
}

/// The most verdicts of atoms that a session holds.

impl TaskSession {
    /// A session with an empty intern table and an empty result cache,
    /// whose evaluations run at `caps`.
    pub fn new(bound: SessionBound, caps: Caps) -> Self {
        TaskSession { intern: Arc::new(RwLock::default()), results: Arc::new(ResultCache::default()), branches: Arc::default(), caps, bound, allocated: Arc::new(AtomicUsize::new(0)), largest_bindings: Arc::new(AtomicU64::new(0)), largest_rows: Arc::new(AtomicU64::new(0)), facts: Arc::new(Mutex::default()), native_rows: Arc::new(Mutex::default()), det_probes: Arc::default(), det_domains: Arc::default(), path_masks: Arc::default() }
    }

    /// A session with this session's intern table and fact relations, and
    /// an empty result cache, no reserved bytes and no counts of its own.
    pub fn sharing_terms(&self) -> Self {
        TaskSession {
            results: Arc::new(ResultCache::default()),
            branches: Arc::default(),
            allocated: Arc::new(AtomicUsize::new(0)),
            largest_bindings: Arc::new(AtomicU64::new(0)),
            largest_rows: Arc::new(AtomicU64::new(0)),
            det_probes: Arc::default(),
            det_domains: Arc::default(),
            path_masks: Arc::default(),
            ..self.clone()
        }
    }

    /// This session with fact relations of its own, built for the task of the
    /// evaluation that uses it. The intern table and the result cache stay
    /// shared: an entry of the result cache is keyed by the rows it reads, so
    /// it holds for every task. [`TaskSession::fact_relation`] keeps one
    /// relation for each fact and example, so an evaluation over a task other
    /// than the session's uses a session from this method.
    pub fn with_own_facts(&self) -> Self {
        TaskSession { facts: Arc::default(), native_rows: Arc::default(), ..self.clone() }
    }

    /// The domains that the liveness walks of this session's decodes keep.
    pub(crate) fn det_probes(&self) -> &OnceLock<crate::decode::det_memo::ProbeMemo> {
        &self.det_probes
    }

    /// What the liveness walks' memo counts ([`crate::decode::det_memo::ProbeMemo::stats`])
    /// and what the table walks' memo counts, each zero where no walk made it.
    pub fn memo_stats(&self) -> ((usize, usize, usize, usize), (usize, usize)) {
        (self.det_probes.get().map_or((0, 0, 0, 0), |memo| memo.stats()), self.det_domains.get().map_or((0, 0), |memo| memo.stats()))
    }

    /// The domains that the table walks of this session's decodes keep.
    pub(crate) fn det_domains(&self) -> &OnceLock<crate::decode::det_memo::SessionMemo> {
        &self.det_domains
    }

    /// The rows of `fact` on `example` of `task`, built on the first request
    /// and shared by each later one, so their rows hash and indexes are built
    /// once. `task` is the session's task.
    pub fn fact_relation(&self, task: &Task, fact: FactRelation, example: Option<Example>) -> Arc<Relation> {
        let mut facts = self.facts.lock().expect(UNPOISONED);
        facts.entry((fact, example)).or_insert_with(|| Arc::new(task.fact_rows(fact, example))).clone()
    }

    /// Gives `fact` the rows `rows` on `example`, or task-wide where `example`
    /// is `None`, for a fact relation that the task does not give: a program
    /// relation of the session's state, or a stored table.
    pub fn provide_fact(&self, fact: FactRelation, example: Option<Example>, rows: Relation) {
        self.facts.lock().expect(UNPOISONED).insert((fact, example), Arc::new(rows));
    }

    /// The rows of the native proposer `proposer` on `example` of the
    /// session's task, or over the whole task where `example` is none, which
    /// `make` gives on the first request or else `None` for a proposer with
    /// no port.
    pub(crate) fn native_proposer_rows(&self, proposer: &LibName, example: Option<Example>, make: impl FnOnce() -> Option<Relation>) -> Option<Arc<Relation>> {
        let key = (proposer.clone(), example);
        if let Some(held) = self.native_rows.lock().expect(UNPOISONED).get(&key) {
            return Some(Arc::clone(held));
        }
        let made = Arc::new(make()?);
        Some(Arc::clone(self.native_rows.lock().expect(UNPOISONED).entry(key).or_insert(made)))
    }

    /// Whether the session's bytes lie within `bound`, or its own bound where
    /// that is none. The bytes are the larger of two counts:
    ///
    /// - the ledger ([`TaskSession::ledger`]): the intern table's, the result
    ///   cache's and the live reservations';
    /// - where the global allocator counts the heap ([`crate::heap::live`]),
    ///   the ledger when the session first checked its bound in the operation
    ///   of `starts`, plus the growth of the heap since then.
    ///
    /// The second count covers the bytes the ledger does not count: the rows
    /// and indexes of relations that a driver, a memo or a table holds, also
    /// after the result cache evicts them, and the scratch of a walk. It
    /// counts the growth of every thread of the process.
    ///
    /// The checks of an operation stand at these places:
    ///
    /// - [`crate::eval::join::Budget::charge_work`], once per batch of
    ///   bindings that a join, a walk or a construction charges, and once per
    ///   batch of rows that a walk of rows passes;
    /// - [`TaskSession::reserve`], before a buffer is allocated, against the
    ///   ledger and the buffer's bytes;
    /// - [`TaskSession::would_reserve`], as the rows of an exported relation
    ///   accrue, against the ledger and the least bytes that the export
    ///   reserves for those rows ([`crate::eval::join::Budget::charge_rows`]);
    /// - [`TaskSession::within_room`], before an index is built, where the
    ///   rows that the build walks give its bytes
    ///   ([`crate::eval::join::Budget::charge_build`]).
    ///
    /// A check reads the intern table's bytes, the result cache's bytes, the
    /// reservations and the heap's live bytes: a few loads and two short
    /// locks. A batch holds enough work to hide that cost, and a build is
    /// checked only where it holds [`crate::eval::join::BUILD_CHECK_MIN`]
    /// bytes or more. So while the session's bytes are far from the bound,
    /// the checks take a small share of the work between them.
    pub fn within_bound(&self, starts: &HeapStarts, bound: Option<SessionBound>) -> Result<usize, ReachedSessionBound> {
        self.within_room(starts, bound, 0)
    }

    /// [`TaskSession::within_bound`], where `growth` more bytes are about to
    /// be built: whether the session's bytes now, as that method counts them,
    /// plus `growth`, lie within the bound. A stop gives the bytes that the
    /// build would bring the session to. A caller gives the bytes that the
    /// build holds at the least, so a stop comes only where the build passes
    /// the bound.
    pub fn within_room(&self, starts: &HeapStarts, bound: Option<SessionBound>, growth: usize) -> Result<usize, ReachedSessionBound> {
        let bound = bound.unwrap_or(self.bound);
        let intern = self.intern.read().expect("an intern table that no panic poisoned").bytes();
        let ledger = intern.saturating_add(self.results.bytes()).saturating_add(self.allocated.load(Ordering::Relaxed));
        let now = match crate::heap::live() {
            None => ledger,
            Some(heap) => ledger.max(starts.grown(Arc::as_ptr(&self.allocated) as usize, heap, ledger)),
        };
        let bytes = now.saturating_add(growth);
        if bytes > bound.bytes { Err(ReachedSessionBound { bytes, bound }) } else { Ok(bytes) }
    }

    /// Reserves a buffer before allocation, together with all live buffer
    /// reservations and the current intern/result stores, within `bound`, or
    /// the session's own bound where that is none. Dropping the returned owner
    /// releases its bytes; sharing an owner does not reserve again.
    pub fn reserve(&self, bytes: usize, bound: Option<SessionBound>) -> Result<SessionAllocation, ReachedSessionBound> {
        let bound = bound.unwrap_or(self.bound);
        let mut held = self.allocated.load(Ordering::Relaxed);
        loop {
            let next = held.checked_add(bytes).ok_or(ReachedSessionBound {bytes:usize::MAX,bound})?;
            self.check_bytes(self.intern.read().expect("an intern table that no panic poisoned").bytes(), next, bound)?;
            match self.allocated.compare_exchange_weak(held, next, Ordering::Relaxed, Ordering::Relaxed) {
                Ok(_) => return Ok(SessionAllocation { bytes, allocated: Arc::clone(&self.allocated) }),
                Err(actual) => held = actual,
            }
        }
    }

    /// Whether [`TaskSession::reserve`] of `bytes` would pass now: it makes
    /// the same check against the ledger and reserves nothing. A stop gives
    /// the bytes that the reservation would bring the ledger to.
    pub fn would_reserve(&self, bytes: usize, bound: Option<SessionBound>) -> Result<(), ReachedSessionBound> {
        let bound = bound.unwrap_or(self.bound);
        let held = self.allocated.load(Ordering::Relaxed);
        let intern = self.intern.read().expect("an intern table that no panic poisoned").bytes();
        self.check_bytes(intern, held.saturating_add(bytes), bound)
    }

    /// The bytes that the session's bound counts: its charged intern storage,
    /// result cache's, and those of the live reservations
    /// ([`TaskSession::reserve`]).
    pub fn ledger(&self) -> (usize, usize, usize) {
        let intern = self.intern.read().expect("an intern table that no panic poisoned").bytes();
        (intern, self.results.bytes(), self.allocated.load(Ordering::Relaxed))
    }

    fn check_bytes(&self, intern: usize, allocated: usize, bound: SessionBound) -> Result<(), ReachedSessionBound> {
        let bytes = intern.saturating_add(self.results.bytes()).saturating_add(allocated);
        if bytes > bound.bytes { Err(ReachedSessionBound { bytes, bound }) } else { Ok(()) }
    }

    /// Records the `counts` of one evaluation that ended with no stop, each
    /// as the larger of it and the count the session holds.
    pub fn record_counts(&self, counts: Counts) {
        self.largest_bindings.fetch_max(counts.bindings, Ordering::Relaxed);
        self.largest_rows.fetch_max(counts.rows, Ordering::Relaxed);
        self.results.capture_counts(counts);
        crate::eval::tally_counts(counts);
    }

    /// The largest counts of the session's evaluations that ended with no
    /// stop.
    pub fn largest_counts(&self) -> Counts {
        Counts { bindings: self.largest_bindings.load(Ordering::Relaxed), rows: self.largest_rows.load(Ordering::Relaxed) }
    }
}

/// The live bytes of the heap and the ledger of each session when it first
/// checked its bound in one operation, by the session's ledger of
/// reservations. The clones of an operation's [`crate::eval::Limits`] share
/// them.
#[derive(Clone, Debug, Default)]
pub struct HeapStarts {
    /// The first session's start, read with no lock.
    first: Arc<OnceLock<HeapStart>>,
    /// The start of each other session.
    others: Arc<Mutex<Vec<HeapStart>>>,
}

#[derive(Clone, Copy, Debug)]
struct HeapStart {
    session: usize,
    heap: usize,
    ledger: usize,
}

impl HeapStarts {
    /// The ledger at the start of `session`, plus the heap's growth from its
    /// start to `heap`. A session's first check is its start, at `heap` and
    /// `ledger`.
    fn grown(&self, session: usize, heap: usize, ledger: usize) -> usize {
        let fresh = HeapStart { session, heap, ledger };
        let start = match self.first.get_or_init(|| fresh) {
            first if first.session == session => *first,
            _ => {
                let mut others = self.others.lock().expect("heap starts that no panic poisoned");
                match others.iter().find(|start| start.session == session) {
                    Some(start) => *start,
                    None => {
                        others.push(fresh);
                        fresh
                    }
                }
            }
        };
        (start.ledger + heap).saturating_sub(start.heap)
    }
}

/// Ownership of bytes admitted under a task session's existing byte bound.
/// A shared buffer keeps this in its shared owner, so clones do not multiply
/// the charge and the last drop releases it, including an aborted build.
#[derive(Debug)]
pub struct SessionAllocation {
    bytes: usize,
    allocated: Arc<AtomicUsize>,
}

impl SessionAllocation {
    /// The bytes still owned by this reservation.
    pub fn bytes(&self)->usize {self.bytes}

    /// Release a completed phase's unused allowance after its scratch drops.
    /// Mutable access excludes shared Arc owners; a retained shared buffer
    /// cannot have its reservation reduced by another owner. Never grows it.
    pub fn shrink_to(&mut self,bytes:usize) {
        let retained=bytes.min(self.bytes);
        self.allocated.fetch_sub(self.bytes-retained,Ordering::Relaxed);
        self.bytes=retained;
    }
}

impl Drop for SessionAllocation {
    fn drop(&mut self) { self.allocated.fetch_sub(self.bytes, Ordering::Relaxed); }
}
