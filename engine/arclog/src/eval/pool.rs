//! The work-stealing thread pool over independent entries: examples, cases,
//! candidates and models.
//!
//! A thread that asks for an entry another thread is computing waits for
//! it, and runs other tasks while it waits, so the pool cannot deadlock.
//! Where that computation is cancelled, a waiting thread computes the entry
//! itself. The rows an entry gives do not depend on the thread that
//! computed it, so an evaluation gives the same rows at any thread count.

use std::sync::{Arc, Mutex, OnceLock};

use rayon::prelude::*;

use crate::hash::StableHashMap;

#[derive(Debug)]
pub struct Pool {
    threads: rayon::ThreadPool,
}

impl Pool {
    /// A pool of `threads` threads, or of as many as the machine has where
    /// `threads` is `None`.
    pub fn new(threads: Option<usize>) -> Self {
        let builder = rayon::ThreadPoolBuilder::new().num_threads(threads.unwrap_or(0));
        Pool { threads: builder.build().expect("the threads of a pool start") }
    }

    /// `f` of each of `items`, in parallel, in the order of `items`.
    pub fn map<T: Sync, R: Send>(&self, items: &[T], f: impl Fn(&T) -> R + Sync) -> Vec<R> {
        self.threads.install(|| items.par_iter().map(|item| f(item)).collect())
    }

    /// Runs one other task of the pool where the calling thread is one of
    /// its threads and a task waits, and otherwise yields the thread.
    fn run_other_task(&self) {
        if !matches!(self.threads.yield_now(), Some(rayon::Yield::Executed)) {
            std::thread::yield_now();
        }
    }
}

/// The entries in flight on the pool's threads, by key, so a thread that
/// asks for an entry another thread computes waits for that computation.
#[derive(Debug)]
pub struct InFlight<K, V> {
    entries: Mutex<StableHashMap<K, Arc<OnceLock<V>>>>,
}

const UNPOISONED: &str = "a table of entries in flight that no panic poisoned";

impl<K: Eq + std::hash::Hash + Clone, V: Clone> InFlight<K, V> {
    pub fn new() -> Self {
        InFlight { entries: Mutex::new(StableHashMap::default()) }
    }

    /// The value of `key`: `compute`'s, where no other thread computes it,
    /// or the other thread's, waited for while this thread runs other
    /// tasks of `pool`. `compute` gives `None` where it is cancelled, and a
    /// thread that waited on it then computes the value itself.
    ///
    /// A computation leaves the table once it ends, by a value, a
    /// cancellation or a panic, so a waiter whose entry left the table with
    /// no value asks again.
    pub fn get_or_compute(&self, pool: &Pool, key: K, compute: impl Fn() -> Option<V>) -> Option<V> {
        loop {
            let (cell, computes) = {
                let mut entries = self.entries.lock().expect(UNPOISONED);
                match entries.get(&key) {
                    Some(cell) => (cell.clone(), false),
                    None => {
                        let cell = Arc::new(OnceLock::new());
                        entries.insert(key.clone(), cell.clone());
                        (cell, true)
                    }
                }
            };
            if computes {
                let _leave = Leave { table: self, key: &key, cell: &cell };
                let value = compute()?;
                let _ = cell.set(value.clone());
                return Some(value);
            }
            if let Some(value) = self.wait(pool, &key, &cell) {
                return Some(value);
            }
        }
    }

    /// The value another thread computes in `cell` for `key`, or `None`
    /// where that computation left the table with no value.
    fn wait(&self, pool: &Pool, key: &K, cell: &Arc<OnceLock<V>>) -> Option<V> {
        loop {
            if let Some(value) = cell.get() {
                return Some(value.clone());
            }
            let in_table = self.entries.lock().expect(UNPOISONED).get(key).is_some_and(|held| Arc::ptr_eq(held, cell));
            if !in_table {
                return cell.get().cloned();
            }
            pool.run_other_task();
        }
    }
}

/// The removal of a computation from the table when it ends, after its
/// value, where it has one, is set.
struct Leave<'t, K: Eq + std::hash::Hash, V> {
    table: &'t InFlight<K, V>,
    key: &'t K,
    cell: &'t Arc<OnceLock<V>>,
}

impl<K: Eq + std::hash::Hash, V> Drop for Leave<'_, K, V> {
    fn drop(&mut self) {
        let mut entries = self.table.entries.lock().unwrap_or_else(std::sync::PoisonError::into_inner);
        if entries.get(self.key).is_some_and(|held| Arc::ptr_eq(held, self.cell)) {
            entries.remove(self.key);
        }
    }
}

impl<K: Eq + std::hash::Hash + Clone, V: Clone> Default for InFlight<K, V> {
    fn default() -> Self {
        Self::new()
    }
}
