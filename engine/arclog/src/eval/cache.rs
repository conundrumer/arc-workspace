//! The driver's way into the result cache: the key of an entry from what
//! the entry reads, the lookup and the store, the ids of relations by
//! their rows, and eviction by least recent use under a share of the
//! session's byte bound.

use super::pool::InFlight;
use super::{RelationValue, Stop};
use crate::program::path::NodePath;
use crate::relations::Relation;
use crate::resolver::ResolvedContent;
use crate::session::{CachedValue, RelationId, ResultKey, TaskSession};
use crate::terms::Example;

/// What an entry reads, from which its [`ResultKey`] is made: its clause's
/// resolved content, the relations it reads in the order of its reads, the
/// example whose input it runs on where it runs on one, and the relation of
/// each parameter it reads, in the order of its reads.
#[derive(Clone, Copy, Debug)]
pub struct EntryRequest<'a> {
    pub clause: &'a ResolvedContent,
    pub reads: &'a [&'a Relation],
    pub example: Option<Example>,
    pub parameters: &'a [&'a Relation],
}

/// The value cached for `request` in `session`, if any, made at `form`, the
/// path in the requesting program of the clause that made the request: a
/// stop the cache holds is given at `form`, so its diagnostic stands at a
/// path of the requesting program.
pub fn lookup(session: &TaskSession, request: &EntryRequest<'_>, form: &NodePath) -> Option<RelationValue> {
    let found = |relations: &[&Relation]| -> Option<Box<[RelationId]>> {
        relations.iter().map(|relation| session.results.find_id(relation)).collect()
    };
    let key = ResultKey {
        clause: request.clause.clone(),
        reads: found(request.reads)?,
        example: request.example,
        parameters: found(request.parameters)?,
    };
    let value = session.results.get(&key)?;
    Some(value.map_stop(|bound| Stop { bound, form: form.clone() }))
}

/// Caches `value` for `request` in `session`, where its stop, if it holds
/// one, is stored: the entry holds the stop's bound and no form. Then
/// evicts the entries least recently used while the cache's bytes exceed
/// its share of the session's byte bound.
pub fn store(session: &TaskSession, request: &EntryRequest<'_>, value: &RelationValue) {
    let Some(value) = cached(value) else {
        return;
    };
    session.results.insert(key(session, request), value);
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
    let ids = |relations: &[&Relation]| -> Box<[RelationId]> {
        relations.iter().map(|relation| relation_id(session, relation)).collect()
    };
    ResultKey {
        clause: request.clause.clone(),
        reads: ids(request.reads),
        example: request.example,
        parameters: ids(request.parameters),
    }
}

/// The id of `relation` in `session`, interned by its rows: the hash
/// combines the hashes of the rows in no order, and two relations whose
/// hashes match are compared by their rows, so two relations share an id
/// only where they hold the same rows.
pub fn relation_id(session: &TaskSession, relation: &Relation) -> RelationId {
    session.results.relation_id(relation)
}

/// The share of the session's byte bound that the result cache may hold:
/// half of it, a provisional share. A relation's bytes count once, however
/// many entries read it.
pub fn cache_bytes_bound(session: &TaskSession) -> usize {
    session.bound.bytes / 2
}

/// The entries that the pool's threads compute, for a thread that asks for
/// one of them to wait on.
pub fn in_flight(session: &TaskSession) -> &InFlight<ResultKey, CachedValue> {
    session.results.in_flight()
}
