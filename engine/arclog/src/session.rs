//! The task session: the engine's state for one task, its result cache and
//! its intern table.
//!
//! The result cache's key and its eviction are the evaluator step's. Step 1
//! fixes only the session that owns the cache, so that the representations
//! of step 1 and the evaluator share one owner.

#![allow(unused_variables, dead_code)]

use std::sync::RwLock;

use crate::eval::RelationValue;
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

/// The memo table of evaluated relations, keyed by content, bounded by bytes.
/// Several threads read and write it at once through a shared reference.
/// An entry holds a relation, `undefined`, or a stop whose
/// [`crate::eval::ReachedBound::is_stored`] holds, and never a partial
/// relation.
#[derive(Debug, Default)]
pub struct ResultCache {
    entries: RwLock<crate::hash::StableHashMap<ResultKey, RelationValue>>,
}

impl ResultCache {
    /// The value cached under `key`, if any.
    pub fn get(&self, key: &ResultKey) -> Option<RelationValue> {
        todo!()
    }

    /// Caches `value` under `key`. A stop that is not stored is a fault of
    /// the caller, so this panics on one.
    pub fn insert(&self, key: ResultKey, value: RelationValue) {
        todo!()
    }
}

/// The engine's state for one task: its result cache and its intern table.
/// The evaluations of the pool's threads share one session through a
/// shared reference: the intern table stands behind a read-write lock,
/// since interning writes it and reading a content reads it, and the
/// result cache synchronizes its own entries.
#[derive(Debug)]
pub struct TaskSession {
    pub intern: RwLock<InternTable>,
    pub results: ResultCache,
    /// The bound on the session's bytes, which the intern table's bytes
    /// count toward.
    pub bound: SessionBound,
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
    /// A session with an empty intern table and an empty result cache.
    pub fn new(bound: SessionBound) -> Self {
        TaskSession { intern: RwLock::default(), results: ResultCache::default(), bound }
    }

    /// Whether the session's bytes, the intern table's and the result
    /// cache's, lie within its bound.
    pub fn within_bound(&self) -> Result<(), ReachedSessionBound> {
        todo!()
    }
}
