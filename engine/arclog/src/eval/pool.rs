//! The work-stealing thread pool over independent entries: examples, cases,
//! candidates and models.
//!
//! A thread that asks for an entry another thread is computing waits for
//! it, and runs other tasks while it waits, so the pool cannot deadlock.
//! Where that computation is cancelled, a waiting thread computes the entry
//! itself. The rows an entry gives do not depend on the thread that
//! computed it, so an evaluation gives the same rows at any thread count.

#![allow(unused_variables, dead_code)]

use std::sync::Arc;

use crate::hash::StableHashMap;

#[derive(Debug)]
pub struct Pool {
    threads: rayon::ThreadPool,
}

impl Pool {
    /// A pool of `threads` threads, or of as many as the machine has where
    /// `threads` is `None`.
    pub fn new(threads: Option<usize>) -> Self {
        todo!()
    }

    /// `f` of each of `items`, in parallel, in the order of `items`.
    pub fn map<T: Sync, R: Send>(&self, items: &[T], f: impl Fn(&T) -> R + Sync) -> Vec<R> {
        todo!()
    }
}

/// The entries in flight on the pool's threads, by key, so a thread that
/// asks for an entry another thread computes waits for that computation.
#[derive(Debug)]
pub struct InFlight<K, V> {
    entries: std::sync::Mutex<StableHashMap<K, Arc<std::sync::OnceLock<V>>>>,
}

impl<K: Eq + std::hash::Hash + Clone, V: Clone> InFlight<K, V> {
    pub fn new() -> Self {
        InFlight { entries: std::sync::Mutex::new(StableHashMap::default()) }
    }

    /// The value of `key`: `compute`'s, where no other thread computes it,
    /// or the other thread's, waited for while this thread runs other
    /// tasks of `pool`. `compute` gives `None` where it is cancelled, and a
    /// thread that waited on it then computes the value itself.
    pub fn get_or_compute(&self, pool: &Pool, key: K, compute: impl Fn() -> Option<V>) -> Option<V> {
        todo!()
    }
}

impl<K: Eq + std::hash::Hash + Clone, V: Clone> Default for InFlight<K, V> {
    fn default() -> Self {
        Self::new()
    }
}
