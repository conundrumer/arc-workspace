//! The computations of result-cache entries that the liveness walks of a
//! task session's decodes keep from one walk to the next
//! ([`crate::decode::det_memo::ProbeMemo`]).
//!
//! Each walk runs in a session of its own, whose result cache starts empty,
//! so two walks that evaluate the same body part or the same clause each
//! compute it. A walk that finds no entry in its cache, for a part of a body
//! or for a clause, takes a kept computation of the same [`CarryKey`] where
//! one exists, and replays it. Otherwise it computes the entry, and keeps
//! that computation.
//!
//! A computation is kept with what it did to the walk's result cache and
//! counts, taken as a capture ([`crate::session::ResultCache::begin_capture`]):
//! each lookup it made, with the value it found; each relation it gave an id;
//! each store; its [`Cost`]: the work it charged to the request and to the
//! walk's table work, and the largest counts that it noted and recorded in the
//! session ([`crate::session::TaskSession::record_counts`]).
//! A computation that faults is not kept. A computation that stops is kept
//! where its stop is at the form of its entry and either the result cache
//! stores the stop ([`crate::eval::ReachedBound::is_stored`]) or the stop is at
//! the table work cap: the first stops depend on the computation alone, and the
//! second on where its charges stand against the cap, as the next paragraph
//! gives.
//!
//! The replay takes the kept computation where the walk's request work and
//! table work stay within their caps after the cost of the computation, and where each kept
//! lookup finds in the walk's cache what it found: a value of the same rows,
//! held in parts of the same columns, or nothing where it found nothing
//! ([`crate::session::ResultCache::replay`]). It takes a kept stop at the table
//! work cap instead where the walk's count is within the cap before the charge
//! that took the computation's count past it, and past the cap after that
//! charge ([`TableWork::crossing`]), so that the computation makes the same
//! charges in the walk up to that one, and that one stops it. The replay then
//! makes the lookups, ids and stores, charges the cost, and
//! gives the value, a stop at the walk's own form. Where the cost would take
//! the request past its cap, no kept computation replays, and the walk computes
//! the entry and stops at the charge where it stops with no kept computation. It records the events it
//! makes in each open capture ([`super::cache::replay_recorded`]), so a
//! computation that contains a replay is kept as one that made those events.
//!
//! # Why the key decides the computation
//!
//! An entry's computation is a function of what it reads and of what the
//! walks share. What the walks share is the task, the registry, the
//! constructions and the table work cap, which a memo serves one scope of
//! ([`crate::decode::det_memo::Scope`]), the caps and byte bound of the
//! session, which the walks' sessions take from one task session, and the
//! intern table, which a memo replaces, with the kept computations, where it
//! passes its byte share. The limits of a walk hold no stops held by a
//! decode and no check of copies, and the walk is cancelled by none, so no
//! computation that [`Carry`] serves depends on the time. What
//! the computation reads is:
//!
//! - **Its request** ([`RecordedKey`]): the content of the clause or part,
//!   the example, and the relations it reads and its parameters, each by
//!   its rows. The result cache keys its entries by the same request, so the
//!   rows of the value depend on it alone. Two keys are equal where the
//!   contents are equal and each relation has the same rows as the one
//!   of the other, held in parts of the same columns, so a relation made in
//!   another walk with the same rows and parts stands for it. The parts
//!   count, since the work of a search depends on how its relations split.
//!   The terms of those rows are ids of the shared intern table, which give
//!   the same terms in each walk of one memo.
//! - **The shape of the search** ([`part_shape`], [`body_shape`]): what
//!   the request does not fix, and the search reads. The work that a search
//!   counts depends on the order of its variables, and the order of a body is
//!   made over all of its parts and gives each part the order of its own
//!   variables ([`super::join::Part::order`]), so the key holds that order.
//!   The key also holds the IR of the nodes that the search reads, with their
//!   variables, the types of the part's variables, the columns that the search
//!   projects onto, and the place of the nodes among one another, which breaks
//!   the ties in the order that the nodes are checked in. A search reads no
//!   other node of its clause and no other variable's type. A clause's body is
//!   evaluated over all of its IR, so its shape is the IR of the clause and the
//!   conjunct of each node, which groups the nodes into parts.
//!
//! The digest of a shape has 128 bits, and two shapes that differ are taken to
//! have two digests, as the content hash of a node is.
//!
//! A computation reads nothing else that differs between the walks that
//! share a key: its lookups are the reads of the walk's cache that the
//! replay checks, and the counts of the walk's cache, such as its bytes, do
//! not change a computation that ends with no stop. A walk whose cache
//! evicts, or that reaches the session's byte bound, runs again in a
//! session of its own with no kept computation
//! ([`crate::decode::det_admission`]).
//!
//! The kept computations stand in two tiers, as the domains of the memo do,
//! each with at most half of the memo's share, counting each relation of a tier
//! once, by its rows. A tier turns, and drops the older one, where the younger
//! has no room. A replay of a computation that the older tier holds keeps it in
//! the younger.

use std::hash::{Hash, Hasher};
use std::sync::{Arc, RwLock};

use super::cache::{self, relation_estimate, EntryRequest, Recorded, RecordedKey};
use super::ir::{ClauseIr, CompiledBody};
use super::join::Part;
use super::plan::VariableOrder;
use super::{Cost, Limits, Outcome, ReachedBound, RelationValue, Stop, TableWork};
use crate::program::path::NodePath;
use crate::hash::{StableHash, StableHashMap, StableHashSet, StableHasher};
use crate::relations::{ColumnIndex, Relation};
use crate::session::{same_rows, CachedValue, TaskSession};

/// The most computations kept for one key, each with its own lookups.
const PER_KEY: usize = 4;

/// The bytes that the store counts for an event, beside its relations.
const EVENT_BYTES: usize = 256;

/// The kept computations that a walk's limits carry, for the evaluation of
/// the walk's entries ([`CarryStore`]).
#[derive(Clone)]
pub struct Carry {
    store: Arc<CarryStore>,
}

impl std::fmt::Debug for Carry {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.debug_struct("Carry").finish_non_exhaustive()
    }
}

impl Carry {
    pub(crate) fn new(store: Arc<CarryStore>) -> Self {
        Carry { store }
    }

    /// The value of the entry of `key`, made at `form`, where a kept
    /// computation of it replays in `session`, with the cost that the replay
    /// charged to `limits`, the cost that the computation charged when it was
    /// kept. The cache of `session` found no entry of the key's request just
    /// before. `None` where no kept computation replays, which includes the
    /// case that the kept cost would take the request or the observation past
    /// its cap: the caller computes the entry, and its charges stop where they
    /// stop with empty caches.
    pub(crate) fn replay(&self, limits: &Limits, session: &TaskSession, key: &CarryKey, form: &NodePath) -> Option<(RelationValue, Cost)> {
        let work = limits.table_work.as_ref()?;
        let request = &limits.request;
        for (carried, older) in self.store.carried(key) {
            let within = carried.cost.fits(request, None)
                && match carried.crossing {
                    None => work.fits(carried.cost.table),
                    Some(crossing) => crossing.at(work),
                };
            if within && cache::replay_recorded(session, &carried.events) {
                let charged = match carried.crossing {
                    None => carried.cost.charge(request, Some(work), session),
                    Some(Crossing { before, after }) => {
                        work.charge_crossing(carried.cost.table, before, after);
                        carried.cost.charge(request, None, session)
                    }
                };
                if older {
                    self.store.promote(key, &carried);
                }
                let value = match charged {
                    Ok(()) => given(carried.value.clone(), form),
                    Err(bound) => RelationValue::Stopped(Stop { bound, form: form.clone() }),
                };
                return Some((value, carried.cost));
            }
        }
        None
    }

    /// The value of `compute`, the evaluation of the entry of `key`, made at
    /// `form`, which stores its value in `session`; its computation is kept
    /// where it ends with a value of rows or `undefined`, or with a stop at
    /// `form` that is stored in the result cache, or with a stop at the table
    /// work cap at `form` that a charge of the computation caused.
    pub(crate) fn capture(&self, limits: &Limits, session: &TaskSession, key: CarryKey, form: &NodePath, compute: impl FnOnce() -> Outcome<RelationValue>) -> Outcome<RelationValue> {
        let Some(work) = limits.table_work.as_ref() else { return compute() };
        let capture = session.results.begin_capture();
        let before = work.count();
        let (found, cost) = limits.request.measure(compute);
        let (events, _) = session.results.end_capture(capture);
        let Ok(value) = &found else { return found };
        let kept = match value {
            RelationValue::Stopped(stop) if stop.form != *form => None,
            RelationValue::Stopped(stop) if stop.bound.is_stored() => Some((RelationValue::Stopped(stop.bound), None)),
            RelationValue::Stopped(stop) if matches!(stop.bound, ReachedBound::TableWork { .. }) => {
                let crossing = work.crossing().filter(|&(at, _)| at >= before).map(|(at, past)| Crossing { before: at - before, after: past - before });
                crossing.map(|crossing| (RelationValue::Stopped(stop.bound), Some(crossing)))
            }
            RelationValue::Stopped(_) => None,
            value => cache::cached(value).map(|value| (value, None)),
        };
        let Some((value, crossing)) = kept else { return found };
        let stopped = matches!(value, RelationValue::Stopped(_));
        match self.store.keep(key, Carried { events: events.into(), cost, crossing, value }) {
            Some(_) if stopped => found,
            Some(kept) => Ok(given(kept, form)),
            None => found,
        }
    }
}

/// `value`, a kept value, as the value of an entry made at `form`: a stop
/// stands at `form`.
fn given(value: CachedValue, form: &NodePath) -> RelationValue {
    value.map_stop(|bound| Stop { bound, form: form.clone() })
}

/// The table work, from the start of a computation, at the two sides of the
/// charge that took the count past its cap: before it the count was within
/// the cap, and after it past.
#[derive(Clone, Copy, PartialEq, Eq, Debug)]
struct Crossing {
    before: u64,
    after: u64,
}

impl Crossing {
    /// Whether a computation that begins with the count of `work` makes the
    /// charge that takes it past the cap at the same place of its work.
    fn at(self, work: &TableWork) -> bool {
        work.fits(self.before) && !work.fits(self.after)
    }
}

/// A computation that a walk made, and what it did there.
struct Carried {
    events: Box<[Recorded]>,
    /// What it charged, and the largest counts it recorded in the session.
    cost: Cost,
    /// Where it took the count past the cap, where its value is a stop at the
    /// table work cap. Its charges are then those that it made until that
    /// stop, and a walk takes the computation where its own count would be
    /// past the cap at the same charge.
    crossing: Option<Crossing>,
    /// Its value: rows, `undefined`, or a stop with no form.
    value: CachedValue,
}

impl Carried {
    /// This computation with each relation it holds replaced by `one` of it.
    fn with_relations(&self, one: &mut impl FnMut(&Arc<Relation>) -> Arc<Relation>) -> Carried {
        let value = match &self.value {
            RelationValue::Rows(rows) => RelationValue::Rows(one(rows)),
            other => other.clone(),
        };
        Carried { events: self.events.iter().map(|event| event.with_relations(&mut *one)).collect(), cost: self.cost, crossing: self.crossing, value }
    }
}

/// The key of a kept computation: the request of its entry, and the digest of
/// the shape of its search, as the module gives them.
#[derive(Clone)]
pub(crate) struct CarryKey {
    request: RecordedKey,
    shape: StableHash,
    digest: u64,
}

impl CarryKey {
    pub(crate) fn new(request: &EntryRequest<'_>, shape: StableHash) -> Self {
        let request = RecordedKey::of(request);
        let digest = request.digest();
        CarryKey { request, shape, digest }
    }

    fn with_relations(&self, one: &mut impl FnMut(&Arc<Relation>) -> Arc<Relation>) -> CarryKey {
        CarryKey { request: self.request.with_relations(one), shape: self.shape, digest: self.digest }
    }
}

impl Hash for CarryKey {
    fn hash<H: Hasher>(&self, state: &mut H) {
        self.digest.hash(state);
        self.shape.hash(state);
    }
}

impl PartialEq for CarryKey {
    /// The keys are equal where their shapes are, and their requests: the
    /// same content and example, and relations of the same rows, each held in
    /// parts of the same columns as the one of the other key, since the work
    /// of a search depends on how its relations split into parts.
    fn eq(&self, other: &CarryKey) -> bool {
        let layout = |a: &[Arc<Relation>], b: &[Arc<Relation>]| {
            a.iter().zip(b).all(|(a, b)| a.parts().len() == b.parts().len() && a.parts().iter().zip(b.parts()).all(|(a, b)| a.columns == b.columns))
        };
        self.digest == other.digest
            && self.shape == other.shape
            && self.request.same(&other.request)
            && layout(&self.request.reads, &other.request.reads)
            && layout(&self.request.parameters, &other.request.parameters)
    }
}

impl Eq for CarryKey {}

/// The kept computations of one generation of the memo's intern table, in two
/// tiers.
pub(crate) struct CarryStore {
    /// The bytes that both tiers may hold.
    share: usize,
    tiers: RwLock<Tiers>,
}

#[derive(Default)]
struct Tiers {
    /// The computations kept since the last turn, and those kept before it
    /// that a replay took since.
    young: Tier,
    /// The computations kept before the last turn that no replay has taken
    /// since. The next turn drops them.
    old: Tier,
}

/// The kept computations of one span of the store's life, with one relation
/// for each rows and columns of parts that they hold, so that the relations a
/// later walk compares share their storage, and the bytes they hold.
#[derive(Default)]
struct Tier {
    entries: StableHashMap<CarryKey, Vec<Arc<Carried>>>,
    relations: StableHashMap<StableHash, Vec<Arc<Relation>>>,
    bytes: usize,
}

const UNPOISONED: &str = "the kept computations are not poisoned";

impl CarryStore {
    /// A store with nothing kept, which holds at most `bytes`.
    pub(crate) fn new(bytes: usize) -> Self {
        CarryStore { share: bytes, tiers: RwLock::default() }
    }

    /// The computations kept under `key`, each with whether the older tier
    /// holds it.
    fn carried(&self, key: &CarryKey) -> Vec<(Arc<Carried>, bool)> {
        let tiers = self.tiers.read().expect(UNPOISONED);
        let young = tiers.young.entries.get(key).into_iter().flatten().map(|carried| (Arc::clone(carried), false));
        let old = tiers.old.entries.get(key).into_iter().flatten().map(|carried| (Arc::clone(carried), true));
        young.chain(old).collect()
    }

    /// Keeps `carried` under `key`, each relation it holds replaced by the
    /// kept relation of the same rows and columns of parts, where one is
    /// kept, and gives its value so replaced. `None` where it keeps none.
    fn keep(&self, key: CarryKey, carried: Carried) -> Option<CachedValue> {
        let mut tiers = self.tiers.write().expect(UNPOISONED);
        let tiers = &mut *tiers;
        if tiers.young.entries.get(&key).is_some_and(|kept| kept.len() >= PER_KEY) {
            return None;
        }
        let share = self.share / 2;
        let (alone, mut fresh) = tiers.young.bytes_of(&key, &carried);
        if alone > share {
            return None;
        }
        if tiers.young.bytes + fresh > share {
            tiers.old = std::mem::take(&mut tiers.young);
            fresh = alone;
        }
        let young = &mut tiers.young;
        let mut one = |relation: &Arc<Relation>| kept_relation(&mut young.relations, relation);
        let key = key.with_relations(&mut one);
        let kept = carried.with_relations(&mut one);
        let value = kept.value.clone();
        young.entries.entry(key).or_default().push(Arc::new(kept));
        young.bytes += fresh;
        Some(value)
    }

    /// Keeps in the younger tier the computation `carried` of `key` that the
    /// older tier holds, where the younger tier has room for it.
    fn promote(&self, key: &CarryKey, carried: &Arc<Carried>) {
        let mut tiers = self.tiers.write().expect(UNPOISONED);
        let young = &mut tiers.young;
        if young.entries.get(key).is_some_and(|kept| kept.len() >= PER_KEY || kept.iter().any(|held| same_computation(held, carried))) {
            return;
        }
        let (_, fresh) = young.bytes_of(key, carried);
        if young.bytes + fresh > self.share / 2 {
            return;
        }
        let mut one = |relation: &Arc<Relation>| kept_relation(&mut young.relations, relation);
        let moved = carried.with_relations(&mut one);
        let key = key.with_relations(&mut one);
        young.entries.entry(key).or_default().push(Arc::new(moved));
        young.bytes += fresh;
    }
}

/// Whether `a` and `b` are the one computation, kept in two tiers: they
/// give one value and one count of work, with one count of events.
fn same_computation(a: &Carried, b: &Carried) -> bool {
    a.cost == b.cost && a.events.len() == b.events.len() && a.crossing == b.crossing && match (&a.value, &b.value) {
        (RelationValue::Stopped(a), RelationValue::Stopped(b)) => a == b,
        (RelationValue::Rows(a), RelationValue::Rows(b)) => a.rows_hash() == b.rows_hash(),
        (RelationValue::Undefined, RelationValue::Undefined) => true,
        _ => false,
    }
}

impl Tier {
    /// The bytes that `carried`, kept under `key`, takes of this tier, and the
    /// bytes it adds to it: its events' bytes less those of each relation that
    /// the tier holds already, each relation counted once, by its rows' hash.
    fn bytes_of(&self, key: &CarryKey, carried: &Carried) -> (usize, usize) {
        let mut seen = StableHashSet::default();
        let mut sizes = (0, 0);
        let mut count = |relation: &Arc<Relation>| {
            let hash = relation.rows_hash();
            if !seen.insert(hash) {
                return;
            }
            let bytes = relation_estimate(relation);
            sizes.0 += bytes;
            let held = self.relations.get(&hash).is_some_and(|alike| alike.iter().any(|held| held.arity() == relation.arity() && held.len() == relation.len()));
            if !held {
                sizes.1 += bytes;
            }
        };
        key.request.relations().for_each(&mut count);
        carried.events.iter().for_each(|event| event.each_relation(&mut count));
        if let RelationValue::Rows(rows) = &carried.value {
            count(rows);
        }
        let overhead = 1024 + EVENT_BYTES * carried.events.len();
        (sizes.0 + overhead, sizes.1 + overhead)
    }
}

/// The relation of `relations` with the rows of `relation`, held in parts of
/// the same columns, or `relation`, which `relations` then holds.
pub(crate) fn kept_relation(relations: &mut StableHashMap<StableHash, Vec<Arc<Relation>>>, relation: &Arc<Relation>) -> Arc<Relation> {
    let alike = relations.entry(relation.rows_hash()).or_default();
    let columns = |relation: &Relation| relation.parts().iter().map(|part| part.columns.clone()).collect::<Vec<_>>();
    if let Some(found) = alike.iter().find(|held| columns(held) == columns(relation) && same_rows(held, relation)) {
        return Arc::clone(found);
    }
    alike.push(Arc::clone(relation));
    Arc::clone(relation)
}

/// The digest of the shape of the search of `part`, a part of a body whose
/// IR is `clause`, in `order`, the variable order of the body, over the
/// columns `columns` of `clause`.
pub(super) fn part_shape(clause: &ClauseIr, part: &Part, order: &VariableOrder, columns: &[ColumnIndex]) -> StableHash {
    let mut hasher = StableHasher::new();
    let mut ranks: Vec<usize> = (0..part.nodes.len()).collect();
    ranks.sort_unstable_by_key(|&at| part.nodes[at]);
    ranks.hash(&mut hasher);
    for &node in &part.nodes {
        clause.nodes[node].hash(&mut hasher);
    }
    part.variables.len().hash(&mut hasher);
    for variable in &part.variables {
        variable.hash(&mut hasher);
        clause.variables[usize::from(variable.0)].ty.hash(&mut hasher);
    }
    part.order(order, &[]).hash(&mut hasher);
    columns.iter().map(|column| clause.columns[usize::from(column.0)]).collect::<Vec<_>>().hash(&mut hasher);
    clause.columns.iter().filter(|variable| part.variables.contains(variable)).collect::<Vec<_>>().hash(&mut hasher);
    hasher.finish128()
}

/// The digest of the shape of the evaluation of `body`, the compiled body of
/// a clause, as a whole.
pub(super) fn body_shape(body: &CompiledBody) -> StableHash {
    let mut hasher = StableHasher::new();
    body.clause.hash(&mut hasher);
    body.conjuncts.hash(&mut hasher);
    hasher.finish128()
}
