//! The task session: the engine's state for one task.
//!
//! Implements `work/engine/reader.md`, Terms: "A task session is the engine's
//! state for one task: its result cache and its intern table."
//!
//! The result cache's key and its eviction are the evaluator step's, as
//! `work/engine/evaluator.md`, The result cache, gives. Step 1 fixes only the
//! session that owns the cache, so that the representations of step 1 and the
//! evaluator share one owner.

#![allow(unused_variables, dead_code)]

use crate::hash::StableHash;
use crate::relations::Relation;
use crate::terms::InternTable;

/// The key of a result-cache entry: a hash of the resolved clause IR, the
/// identity of each relation it reads, the grid it runs on and the parameter
/// values it reads, as `work/engine/evaluator.md`, The result cache, gives.
#[derive(Clone, Copy, PartialEq, Eq, Hash, Debug)]
pub struct ResultKey(pub StableHash);

/// The memo table of evaluated relations, keyed by content, bounded by bytes.
///
/// Implements `work/engine/evaluator.md`, The result cache.
#[derive(Debug, Default)]
pub struct ResultCache {
    entries: crate::hash::StableHashMap<ResultKey, std::sync::Arc<Relation>>,
}

impl ResultCache {
    /// The relation cached under `key`, if any.
    ///
    /// Implements `work/engine/evaluator.md`, The result cache.
    pub fn get(&self, key: ResultKey) -> Option<std::sync::Arc<Relation>> {
        todo!()
    }

    /// Caches `relation` under `key`.
    ///
    /// Implements `work/engine/evaluator.md`, The result cache.
    pub fn insert(&mut self, key: ResultKey, relation: std::sync::Arc<Relation>) {
        todo!()
    }
}

/// The engine's state for one task.
///
/// Implements `work/engine/reader.md`, Terms: "A task session is the engine's state for one task: its result cache and its intern table."
#[derive(Debug, Default)]
pub struct TaskSession {
    pub intern: InternTable,
    pub results: ResultCache,
}

impl TaskSession {
    /// A session with an empty intern table and an empty result cache.
    ///
    /// Implements `work/engine/reader.md`, Terms: "A task session is the engine's state for one task: its result cache and its intern table."
    pub fn new() -> Self {
        todo!()
    }
}
