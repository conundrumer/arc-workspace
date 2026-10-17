//! The task session: the engine's state for one task, its result cache and
//! its intern table.
//!
//! The result cache's key and its eviction are the evaluator step's. Step 1
//! fixes only the session that owns the cache, so that the representations
//! of step 1 and the evaluator share one owner.

#![allow(unused_variables, dead_code)]

use crate::relations::Relation;
use crate::terms::InternTable;

/// The key of a result-cache entry: the resolved clause IR, the identity of
/// each relation it reads, the grid it runs on, where it runs on one, and
/// the parameter values it reads. Two keys are equal where each of these is, so two clauses whose
/// hashes collide take two entries.
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
#[derive(Debug, Default)]
pub struct ResultCache {
    entries: crate::hash::StableHashMap<ResultKey, std::sync::Arc<Relation>>,
}

impl ResultCache {
    /// The relation cached under `key`, if any.
    pub fn get(&self, key: &ResultKey) -> Option<std::sync::Arc<Relation>> {
        todo!()
    }

    /// Caches `relation` under `key`.
    pub fn insert(&mut self, key: ResultKey, relation: std::sync::Arc<Relation>) {
        todo!()
    }
}

/// The engine's state for one task: its result cache and its intern table.
#[derive(Debug)]
pub struct TaskSession {
    pub intern: InternTable,
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
        TaskSession { intern: InternTable::default(), results: ResultCache::default(), bound }
    }

    /// Whether the session's bytes, the intern table's and the result
    /// cache's, lie within its bound.
    pub fn within_bound(&self) -> Result<(), ReachedSessionBound> {
        todo!()
    }
}
