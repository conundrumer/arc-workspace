//! The driver's way into the result cache: the key of an entry from what
//! the entry reads, the lookup and the store, the ids of relations by
//! their rows, and eviction by least recent use under a share of the
//! session's byte bound.
//!
//! [`lookup`] finds nothing and [`store`] stores nothing until the result
//! cache's stage writes them, so no result depends on the cache before
//! then.

#![allow(unused_variables, dead_code)]

use super::RelationValue;
use crate::relations::Relation;
use crate::resolver::ResolvedContent;
use crate::session::{RelationId, ResultKey, TaskSession};
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

/// The value cached for `request` in `session`, if any.
pub fn lookup(session: &TaskSession, request: &EntryRequest<'_>) -> Option<RelationValue> {
    None
}

/// Caches `value` for `request` in `session`, where its stop, if it holds
/// one, is stored, and evicts the entries least recently used while the
/// cache's bytes exceed its share of the session's byte bound.
pub fn store(session: &TaskSession, request: &EntryRequest<'_>, value: &RelationValue) {}

/// The key of `request`, each relation it reads by its id.
pub fn key(session: &TaskSession, request: &EntryRequest<'_>) -> ResultKey {
    todo!()
}

/// The id of `relation` in `session`, interned by its rows: the hash
/// combines the hashes of the rows in no order, and two relations whose
/// hashes match are compared by their rows, so two relations share an id
/// only where they hold the same rows.
pub fn relation_id(session: &TaskSession, relation: &Relation) -> RelationId {
    todo!()
}

/// The share of the session's byte bound that the result cache may hold.
/// A relation's bytes count once, however many entries read it.
pub fn cache_bytes_bound(session: &TaskSession) -> usize {
    todo!()
}
