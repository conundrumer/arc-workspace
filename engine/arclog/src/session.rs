//! The task session: the engine's state for one task, its result cache and
//! its intern table.
//!
//! The result cache's key and its eviction are the evaluator step's. Step 1
//! fixes only the session that owns the cache, so that the representations
//! of step 1 and the evaluator share one owner.

#![allow(unused_variables, dead_code)]

use crate::hash::StableHash;
use crate::relations::Relation;
use crate::terms::InternTable;

/// The key of a result-cache entry: a hash of the resolved clause IR, the
/// identity of each relation it reads, the grid it runs on and the parameter
/// values it reads.
#[derive(Clone, Copy, PartialEq, Eq, Hash, Debug)]
pub struct ResultKey(pub StableHash);

/// The memo table of evaluated relations, keyed by content, bounded by bytes.
#[derive(Debug, Default)]
pub struct ResultCache {
    entries: crate::hash::StableHashMap<ResultKey, std::sync::Arc<Relation>>,
}

impl ResultCache {
    /// The relation cached under `key`, if any.
    pub fn get(&self, key: ResultKey) -> Option<std::sync::Arc<Relation>> {
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
        todo!()
    }

    /// Whether the session's bytes, the intern table's and the result
    /// cache's, lie within its bound.
    pub fn within_bound(&self) -> Result<(), ReachedSessionBound> {
        todo!()
    }
}
