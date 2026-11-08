//! The driver's way into the result cache: the key of an entry from what
//! the entry reads, the lookup, which charges the entry's cost, and the
//! store, which keeps the cost with the entry, the ids of relations by
//! their rows, and eviction by least recent use under a share of the
//! session's byte bound.

use std::sync::Arc;

use super::pool::InFlight;
use super::{Charged, Cost, Limits, RelationValue, Stop};
use crate::program::path::NodePath;
use crate::relations::Relation;
use super::ir::ClauseIr;
use crate::resolver::ResolvedContent;
use crate::session::{same_rows, CachedValue, Costed, RelationId, ResultContent, ResultKey, TaskSession};
use crate::terms::Example;

/// What an entry evaluates, by reference: a form's resolved content, the
/// compiled clause of a body of a form over a lib component, or the resolved
/// content of a node of the dependency graph.
#[derive(Clone, Copy, Debug)]
pub enum EntryContent<'a> {
    Form(&'a ResolvedContent),
    Body(&'a ClauseIr),
    Node(&'a ResolvedContent),
}

impl EntryContent<'_> {
    fn owned(self) -> ResultContent {
        match self {
            EntryContent::Form(content) => ResultContent::Form(content.clone()),
            EntryContent::Body(clause) => ResultContent::Body(clause.clone()),
            EntryContent::Node(content) => ResultContent::Node(content.clone()),
        }
    }
}

/// What an entry reads, from which its [`ResultKey`] is made: the resolved
/// content of its clause or of its part of a body, the relations it reads in the order of its reads, the
/// example whose input it runs on where it runs on one, and the relation of
/// each parameter it reads, in the order of its reads.
#[derive(Clone, Copy, Debug)]
pub struct EntryRequest<'a> {
    pub clause: EntryContent<'a>,
    pub reads: &'a [Arc<Relation>],
    pub example: Option<Example>,
    pub parameters: &'a [Arc<Relation>],
}

/// The value cached for `request` in `session`, if any, and the cost of its
/// entry.
#[derive(Clone, Debug)]
pub struct Found {
    /// The value, made at `form`, the path in the requesting program of the
    /// clause that made the request: a stop the cache holds is given at
    /// `form`, so its diagnostic stands at a path of the requesting program.
    /// Where charging the entry's cost took the request or the observation past
    /// its cap, the value is that stop.
    pub value: RelationValue,
    pub cost: Cost,
}

/// The entry cached for `request` in `session`, if any, charged to `limits`
/// as the entry's computation charged: the hit charges the entry's recorded
/// cost, so the counts of the evaluation around it are those of one that
/// computed the entry. `None` where the cache holds no entry, and where the
/// cost would take a count past its cap ([`Charged::Misfit`]): the caller then
/// computes the entry, and its charges stop where they stop with empty caches.
pub fn lookup(session: &TaskSession, limits: &Limits, request: &EntryRequest<'_>, form: &NodePath) -> Option<Found> {
    let found = found_key(session, request.clause.owned(), request.reads, request.example, request.parameters).and_then(|key| session.results.get(&key));
    session.results.record(|| Recorded::Lookup { key: RecordedKey::of(request), found: found.as_ref().map(|hit| hit.recorded().clone()) });
    let hit = found?;
    let cost = hit.cost();
    let value = match hit.charge(&limits.request, limits.table_work.as_ref(), session) {
        Charged::Value(value) => value.map_stop(|bound| Stop { bound, form: form.clone() }),
        Charged::Stopped(_, bound) => RelationValue::Stopped(Stop { bound, form: form.clone() }),
        Charged::Misfit => return None,
    };
    Some(Found { value, cost })
}

/// The key of an entry whose relations the cache holds, each by its id, or
/// `None` where it holds none with the rows of one of them.
fn found_key(session: &TaskSession, clause: ResultContent, reads: &[Arc<Relation>], example: Option<Example>, parameters: &[Arc<Relation>]) -> Option<ResultKey> {
    let found = |relations: &[Arc<Relation>]| -> Option<Box<[RelationId]>> {
        relations.iter().map(|relation| session.results.find_id(relation)).collect()
    };
    Some(ResultKey { clause, reads: found(reads)?, example, parameters: found(parameters)? })
}

/// Caches `value` for `request` in `session`, with the `cost` of its
/// computation, where its stop, if it holds one, is stored: the entry holds
/// the stop's bound and no form. Then evicts the entries least recently used
/// while the cache's bytes exceed its share of the session's byte bound.
pub fn store(session: &TaskSession, request: &EntryRequest<'_>, value: &RelationValue, cost: Cost) {
    let Some(value) = cached(value) else {
        return;
    };
    let key = key(session, request);
    session.results.record(|| Recorded::Store { key: RecordedKey::of(request), value: value.clone(), cost });
    session.results.insert(key, value, cost);
    session.results.evict(cache_bytes_bound(session));
}

/// The value the cache holds for `value`, its stop's bound with no form, or
/// `None` where `value` stops at a bound that is not stored.
pub fn cached(value: &RelationValue) -> Option<CachedValue> {
    match value {
        RelationValue::Stopped(stop) if !stop.bound.is_stored() => None,
        _ => Some(value.clone().map_stop(|stop| stop.bound)),
    }
}

/// The key of `request`, each relation it reads by its id.
pub fn key(session: &TaskSession, request: &EntryRequest<'_>) -> ResultKey {
    let ids = |relations: &[Arc<Relation>]| -> Box<[RelationId]> {
        relations.iter().map(|relation| relation_id(session, relation)).collect()
    };
    ResultKey {
        clause: request.clause.owned(),
        reads: ids(request.reads),
        example: request.example,
        parameters: ids(request.parameters),
    }
}

/// The id of `relation` in `session`, interned by its rows: the hash
/// combines the hashes of the rows in no order, and two relations whose
/// hashes match are compared by their rows, so two relations share an id
/// only where they hold the same rows.
pub fn relation_id(session: &TaskSession, relation: &Arc<Relation>) -> RelationId {
    session.results.record(|| Recorded::Id { relation: Arc::clone(relation) });
    session.results.relation_id(relation)
}

/// What [`lookup`], [`relation_id`] and [`store`] did to a session's result
/// cache while a capture was open
/// ([`crate::session::ResultCache::begin_capture`]).
#[derive(Clone, Debug)]
pub enum Recorded {
    /// A lookup, and the value it found, if any.
    Lookup { key: RecordedKey, found: Option<CachedValue> },
    /// The id of `relation`, which the cache then holds where it held no
    /// relation of its rows.
    Id { relation: Arc<Relation> },
    /// A store of `value`, with the cost of its computation.
    Store { key: RecordedKey, value: CachedValue, cost: Cost },
}

/// The key of an entry by the relations it reads, and not by their ids in
/// one session, so that it can be looked up in another session that shares
/// the intern table.
#[derive(Clone, Debug)]
pub struct RecordedKey {
    pub(crate) clause: ResultContent,
    pub(crate) reads: Box<[Arc<Relation>]>,
    pub(crate) example: Option<Example>,
    pub(crate) parameters: Box<[Arc<Relation>]>,
}

impl RecordedKey {
    pub(crate) fn of(request: &EntryRequest<'_>) -> Self {
        RecordedKey { clause: request.clause.owned(), reads: request.reads.into(), example: request.example, parameters: request.parameters.into() }
    }

    /// This key with each relation it holds replaced by `one` of it.
    pub(crate) fn with_relations(&self, one: &mut impl FnMut(&Arc<Relation>) -> Arc<Relation>) -> RecordedKey {
        RecordedKey { clause: self.clause.clone(), reads: self.reads.iter().map(&mut *one).collect(), example: self.example, parameters: self.parameters.iter().map(&mut *one).collect() }
    }

    /// Whether `self` and `other` are the key of one entry: the same content
    /// and example, and relations of the same rows.
    pub(crate) fn same(&self, other: &RecordedKey) -> bool {
        let rows = |a: &[Arc<Relation>], b: &[Arc<Relation>]| a.len() == b.len() && a.iter().zip(b).all(|(a, b)| a.rows_hash() == b.rows_hash() && same_rows(a, b));
        self.example == other.example && self.clause == other.clause && rows(&self.reads, &other.reads) && rows(&self.parameters, &other.parameters)
    }

    /// A digest of the key that two keys of one entry share.
    pub(crate) fn digest(&self) -> u64 {
        use std::hash::{Hash, Hasher};
        let mut hasher = crate::hash::StableHasher::new();
        self.clause.hash(&mut hasher);
        self.example.hash(&mut hasher);
        self.reads.len().hash(&mut hasher);
        for relation in self.relations() {
            relation.rows_hash().hash(&mut hasher);
        }
        hasher.finish()
    }

    pub(crate) fn relations(&self) -> impl Iterator<Item = &Arc<Relation>> {
        self.reads.iter().chain(self.parameters.iter())
    }
}

impl Recorded {
    /// This event with each relation it holds replaced by `one` of it.
    pub fn with_relations(&self, one: &mut impl FnMut(&Arc<Relation>) -> Arc<Relation>) -> Recorded {
        fn key(key: &RecordedKey, one: &mut impl FnMut(&Arc<Relation>) -> Arc<Relation>) -> RecordedKey {
            key.with_relations(one)
        }
        fn value(value: &CachedValue, one: &mut impl FnMut(&Arc<Relation>) -> Arc<Relation>) -> CachedValue {
            match value {
                RelationValue::Rows(relation) => RelationValue::Rows(one(relation)),
                other => other.clone(),
            }
        }
        match self {
            Recorded::Lookup { key: looked, found } => Recorded::Lookup { key: key(looked, one), found: found.as_ref().map(|found| value(found, one)) },
            Recorded::Id { relation } => Recorded::Id { relation: one(relation) },
            Recorded::Store { key: stored, value: kept, cost } => Recorded::Store { key: key(stored, one), value: value(kept, one), cost: *cost },
        }
    }

    /// Calls `each` on each relation this event holds, once for each place
    /// it holds one.
    pub(crate) fn each_relation(&self, each: &mut impl FnMut(&Arc<Relation>)) {
        let value = |value: &CachedValue, each: &mut dyn FnMut(&Arc<Relation>)| {
            if let RelationValue::Rows(relation) = value {
                each(relation);
            }
        };
        match self {
            Recorded::Lookup { key, found } => {
                key.relations().for_each(&mut *each);
                if let Some(found) = found {
                    value(found, each);
                }
            }
            Recorded::Id { relation } => each(relation),
            Recorded::Store { key, value: stored, .. } => {
                key.relations().for_each(&mut *each);
                value(stored, each);
            }
        }
    }

    /// The bytes of the relations this event holds, an estimate.
    pub fn bytes(&self) -> usize {
        let value = |value: &CachedValue| match value {
            RelationValue::Rows(relation) => relation_estimate(relation),
            _ => 0,
        };
        256 + match self {
            Recorded::Lookup { key, found } => key.relations().map(|relation| relation_estimate(relation)).sum::<usize>() + found.as_ref().map_or(0, value),
            Recorded::Id { relation } => relation_estimate(relation),
            Recorded::Store { key, value: stored, .. } => key.relations().map(|relation| relation_estimate(relation)).sum::<usize>() + value(stored),
        }
    }
}

/// The bytes of `relation`'s rows, an estimate.
pub(crate) fn relation_estimate(relation: &Relation) -> usize {
    relation.parts().iter().map(|part| part.rows.bytes()).sum::<usize>() + 256
}

/// Makes in `session` the events `events`, recorded in a session that shares
/// its intern table, where each would do in `session` what it did there, as
/// `ResultCache::replay` gives, and gives whether it made
/// them.
pub fn replay(session: &TaskSession, events: &[Recorded]) -> bool {
    session.results.replay(events, cache_bytes_bound(session))
}

/// [`replay`] of `events`, where the replay also records each event that it
/// makes where a call of [`lookup`], [`relation_id`] or [`store`] would have
/// recorded it: in each open capture
/// ([`crate::session::ResultCache::begin_capture`]) and in the thread's
/// recording. A computation that replays events in place of making them is
/// then captured as one that made them.
pub fn replay_recorded(session: &TaskSession, events: &[Recorded]) -> bool {
    if !replay(session, events) {
        return false;
    }
    for event in events {
        session.results.record(|| event.clone());
    }
    true
}

/// The share of the session's byte bound that the result cache may hold:
/// half of it, a provisional share. A relation's bytes count once, however
/// many entries read it.
pub fn cache_bytes_bound(session: &TaskSession) -> usize {
    session.bound.bytes / 2
}

/// The entries that the pool's threads compute, for a thread that asks for
/// one of them to wait on.
pub fn in_flight(session: &TaskSession) -> &InFlight<ResultKey, Costed> {
    session.results.in_flight()
}
