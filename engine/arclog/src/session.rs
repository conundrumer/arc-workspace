//! The task session: the engine's state for one task, its result cache,
//! its intern table, and the largest counts of its evaluations.
//!
//! The result cache keys an entry by its content, a [`ResultKey`], and
//! gives each relation it holds an id by its rows. It evicts the entries
//! least recently used while its bytes exceed its share of the session's
//! byte bound, [`crate::eval::cache::cache_bytes_bound`].

use std::collections::BTreeMap;
use std::sync::atomic::{AtomicU64, Ordering};
use std::sync::{Arc, Mutex, RwLock};

use crate::eval::pool::InFlight;
use crate::eval::{Caps, ReachedBound, RelationValue};
use crate::hash::{StableHash, StableHashMap, StableHasher};
use crate::relations::{Relation, RelationPart};
use crate::terms::InternTable;

/// The key of a result-cache entry: the resolved clause IR, the identity of
/// each relation it reads, the grid it runs on, where it runs on one, and
/// the parameter values it reads. It compares as a key of canonical parts
/// does ([`crate::program`]).
#[derive(Clone, PartialEq, Eq, Hash, Debug)]
pub struct ResultKey {
    pub clause: crate::resolver::ResolvedContent,
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

/// The memo table of evaluated relations, keyed by content, bounded by bytes.
/// Several threads read and write it at once through a shared reference.
/// An entry holds a relation, `undefined`, or a bound whose
/// [`crate::eval::ReachedBound::is_stored`] holds, with no form, and never
/// a partial relation. The cache holds no path of a program, since the
/// programs that share an entry hold its clause at different paths.
///
/// The cache holds each relation that an entry's key reads or that an
/// entry's value is once, under its id, and counts its bytes once. A
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
    in_flight: InFlight<ResultKey, CachedValue>,
}

#[derive(Debug, Default)]
struct CacheState {
    entries: StableHashMap<ResultKey, Entry>,
    /// The key of each entry by the tick of its last use.
    recency: BTreeMap<u64, ResultKey>,
    clock: u64,
    relations: StableHashMap<RelationId, HeldRelation>,
    /// The ids of the held relations by the hash of their rows.
    by_rows: StableHashMap<StableHash, Vec<RelationId>>,
    next_id: u32,
    /// The bytes of the held relations and of the entries.
    bytes: usize,
}

#[derive(Debug)]
struct Entry {
    value: CachedValue,
    /// The id of the value's relation, where the value is one.
    rows: Option<RelationId>,
    used: u64,
}

#[derive(Debug)]
struct HeldRelation {
    relation: Arc<Relation>,
    hash: StableHash,
    bytes: usize,
    /// The count of entries whose key reads the relation or whose value it
    /// is.
    holders: usize,
}

const UNPOISONED: &str = "a result cache that no panic poisoned";

impl ResultCache {
    /// The value cached under `key`, if any. A value found counts as a use
    /// of its entry.
    pub fn get(&self, key: &ResultKey) -> Option<CachedValue> {
        let mut state = self.state.lock().expect(UNPOISONED);
        let value = state.touch(key)?;
        self.found.fetch_add(1, Ordering::Relaxed);
        Some(value)
    }

    /// Caches `value` under `key`. A stop that is not stored is a fault of
    /// the caller, so this panics on one.
    pub fn insert(&self, key: ResultKey, value: CachedValue) {
        if let RelationValue::Stopped(bound) = &value {
            assert!(bound.is_stored(), "a stop at a bound that the cache stores");
        }
        self.state.lock().expect(UNPOISONED).insert(key, value);
    }

    /// The id of a relation that the cache holds with the rows of
    /// `relation`, or `None` where it holds none.
    pub fn find_id(&self, relation: &Relation) -> Option<RelationId> {
        let hash = rows_hash(relation);
        self.state.lock().expect(UNPOISONED).find(hash, relation)
    }

    /// The id of `relation`: that of a relation the cache holds with its
    /// rows, or a new id, under which the cache holds a copy of it until an
    /// entry holds it or an eviction drops it.
    pub fn relation_id(&self, relation: &Relation) -> RelationId {
        let hash = rows_hash(relation);
        let mut state = self.state.lock().expect(UNPOISONED);
        match state.find(hash, relation) {
            Some(id) => id,
            None => state.add(hash, Arc::new(relation.clone())),
        }
    }

    /// Drops the relations that no entry holds, then the entries least
    /// recently used, while the cache's bytes exceed `bound`.
    pub fn evict(&self, bound: usize) {
        self.state.lock().expect(UNPOISONED).evict(bound);
    }

    /// The bytes the cache holds, which count toward the task session's
    /// bound.
    pub fn bytes(&self) -> usize {
        self.state.lock().expect(UNPOISONED).bytes
    }

    /// The count of requests that found their entry in the cache.
    pub fn found(&self) -> u64 {
        self.found.load(Ordering::Relaxed)
    }

    /// The entries in flight on the pool's threads.
    pub fn in_flight(&self) -> &InFlight<ResultKey, CachedValue> {
        &self.in_flight
    }
}

impl CacheState {
    fn touch(&mut self, key: &ResultKey) -> Option<CachedValue> {
        let tick = self.tick();
        let entry = self.entries.get_mut(key)?;
        let last = std::mem::replace(&mut entry.used, tick);
        let value = entry.value.clone();
        let key = self.recency.remove(&last).expect("a recency tick for each entry");
        self.recency.insert(tick, key);
        Some(value)
    }

    fn tick(&mut self) -> u64 {
        self.clock += 1;
        self.clock
    }

    fn find(&self, hash: StableHash, relation: &Relation) -> Option<RelationId> {
        let ids = self.by_rows.get(&hash)?;
        ids.iter().copied().find(|id| same_rows(&self.relations[id].relation, relation))
    }

    fn add(&mut self, hash: StableHash, relation: Arc<Relation>) -> RelationId {
        let id = RelationId(self.next_id);
        self.next_id = self.next_id.checked_add(1).expect("fewer than 2^32 relations in a session");
        let bytes = relation_bytes(&relation);
        self.bytes += bytes;
        self.by_rows.entry(hash).or_default().push(id);
        self.relations.insert(id, HeldRelation { relation, hash, bytes, holders: 0 });
        id
    }

    fn insert(&mut self, key: ResultKey, value: CachedValue) {
        if self.entries.contains_key(&key) {
            return;
        }
        let (value, rows) = match value {
            RelationValue::Rows(relation) => {
                let hash = rows_hash(&relation);
                let id = self.find(hash, &relation).unwrap_or_else(|| self.add(hash, relation));
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
        self.recency.insert(used, key.clone());
        self.entries.insert(key, Entry { value, rows, used });
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
        let ids = self.by_rows.get_mut(&held.hash).expect("the ids of a held relation's hash");
        ids.retain(|&other| other != id);
        if ids.is_empty() {
            self.by_rows.remove(&held.hash);
        }
    }

    fn evict(&mut self, bound: usize) {
        if self.bytes <= bound {
            return;
        }
        let unheld: Vec<RelationId> = self.relations.iter().filter(|(_, held)| held.holders == 0).map(|(&id, _)| id).collect();
        for id in unheld {
            self.drop_relation(id);
        }
        while self.bytes > bound {
            let Some((_, key)) = self.recency.pop_first() else { break };
            let entry = self.entries.remove(&key).expect("an entry for each recency tick");
            self.bytes -= entry_bytes(&key);
            for id in entry.rows.into_iter().chain(key.reads.iter().copied()).chain(key.parameters.iter().copied()) {
                self.release(id);
            }
        }
    }
}

/// The modulus of the rows hash, the Mersenne prime 2^61 - 1.
const MODULUS: u64 = (1 << 61) - 1;

/// The hash of `relation`'s rows, which depends on its rows alone: no order
/// of its rows, and no split of its columns into parts. Each row hashes as
/// the product, modulo [`MODULUS`], of a hash of each of its values at its
/// column, and the relation as the sum of its rows' hashes. Since a row of
/// the product of parts hashes as the product of its parts' rows' hashes,
/// that sum is the product of each part's sum, which reads each part's rows
/// once.
fn rows_hash(relation: &Relation) -> StableHash {
    let sum = relation.parts().iter().fold(1u64, |product, part| {
        let rows = part.rows.rows().fold(0u64, |sum, row| {
            let hash = part.columns.iter().zip(row).fold(1u64, |hash, (column, value)| times(hash, value_hash(column.0, value.encoding())));
            (sum + hash) % MODULUS
        });
        times(product, rows)
    });
    let mut hasher = StableHasher::new();
    std::hash::Hash::hash(&(relation.arity(), sum), &mut hasher);
    hasher.finish128()
}

/// The hash of `value` at `column`, in `1..MODULUS`.
fn value_hash(column: u16, value: u32) -> u64 {
    let mut hasher = StableHasher::new();
    std::hash::Hash::hash(&(column, value), &mut hasher);
    1 + (hasher.finish128().0 as u64) % (MODULUS - 1)
}

fn times(a: u64, b: u64) -> u64 {
    ((u128::from(a) * u128::from(b)) % u128::from(MODULUS)) as u64
}

/// Whether `a` and `b` hold the same rows. Where their parts split the
/// columns alike, the parts' rows are compared; otherwise each row of `a`
/// is looked up in `b`'s parts.
pub(crate) fn same_rows(a: &Relation, b: &Relation) -> bool {
    if std::ptr::eq(a, b) {
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
            counterpart(part).is_some_and(|other| part.rows.rows().all(|row| other.rows.contains(row)))
        });
    }
    let mut same = true;
    crate::eval::join::each_row(a, &mut |row| {
        same = same
            && b.parts().iter().all(|part| {
                let projected: Vec<_> = part.columns.iter().map(|column| row[usize::from(column.0)]).collect();
                part.rows.contains(&projected)
            });
    });
    same
}

/// The bytes of `relation`'s rows and parts.
fn relation_bytes(relation: &Relation) -> usize {
    std::mem::size_of::<Relation>()
        + relation
            .parts()
            .iter()
            .map(|part| {
                std::mem::size_of::<RelationPart>()
                    + std::mem::size_of_val(&*part.columns)
                    + part.rows.len()
                        * (std::mem::size_of::<crate::relations::Row>()
                            + usize::from(part.rows.arity()) * std::mem::size_of::<crate::terms::TermId>())
            })
            .sum::<usize>()
}

/// The bytes of an entry beside the relations it holds.
fn entry_bytes(key: &ResultKey) -> usize {
    std::mem::size_of::<ResultKey>()
        + std::mem::size_of::<Entry>()
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
#[derive(Debug)]
pub struct TaskSession {
    pub intern: RwLock<InternTable>,
    pub results: ResultCache,
    /// The caps of every evaluation in the session.
    pub caps: Caps,
    /// The bound on the session's bytes, which the intern table's bytes
    /// count toward.
    pub bound: SessionBound,
    /// The largest bindings tried of any one evaluation that ended with no
    /// stop, an atomic maximum, so it does not depend on the order of the
    /// threads.
    largest_bindings: AtomicU64,
    /// The largest rows held of any one such evaluation, an atomic maximum.
    largest_rows: AtomicU64,
}

/// A count of bindings tried and a count of rows held.
#[derive(Clone, Copy, PartialEq, Eq, Debug, Default)]
pub struct Counts {
    pub bindings: u64,
    pub rows: u64,
}

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

impl TaskSession {
    /// A session with an empty intern table and an empty result cache,
    /// whose evaluations run at `caps`.
    pub fn new(bound: SessionBound, caps: Caps) -> Self {
        TaskSession { intern: RwLock::default(), results: ResultCache::default(), caps, bound, largest_bindings: AtomicU64::new(0), largest_rows: AtomicU64::new(0) }
    }

    /// Whether the session's bytes, the intern table's and the result
    /// cache's, lie within its bound.
    pub fn within_bound(&self) -> Result<(), ReachedSessionBound> {
        let intern = self.intern.read().expect("an intern table that no panic poisoned").bytes();
        let bytes = intern + self.results.bytes();
        if bytes > self.bound.bytes { Err(ReachedSessionBound { bytes, bound: self.bound }) } else { Ok(()) }
    }

    /// Records the `counts` of one evaluation that ended with no stop, each
    /// as the larger of it and the count the session holds.
    pub fn record_counts(&self, counts: Counts) {
        self.largest_bindings.fetch_max(counts.bindings, Ordering::Relaxed);
        self.largest_rows.fetch_max(counts.rows, Ordering::Relaxed);
    }

    /// The largest counts of the session's evaluations that ended with no
    /// stop.
    pub fn largest_counts(&self) -> Counts {
        Counts { bindings: self.largest_bindings.load(Ordering::Relaxed), rows: self.largest_rows.load(Ordering::Relaxed) }
    }
}
