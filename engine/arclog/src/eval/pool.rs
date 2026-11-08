//! The work-stealing thread pool over independent entries: examples, cases,
//! values of a `DET`'s domain and models.
//!
//! A thread that asks for an entry another thread is computing blocks
//! until that computation ends, and runs no other task of the pool while
//! it waits. A task run on the waiting thread's own stack could ask for an
//! entry that a computation lower on that stack holds in flight, and so
//! wait on itself. A blocking wait follows only the reads of the entries,
//! which form no cycle, so the pool cannot deadlock, while a computation
//! runs no task of the pool itself: nested parallel work in a computation
//! would let its thread take other tasks onto its stack. Where that
//! computation is cancelled, a waiting thread computes the entry itself.
//! The rows an entry gives do not depend on the thread that computed it, so
//! an evaluation gives the same rows at any thread count.

use std::sync::{Arc, Condvar, Mutex};

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
    ///
    /// A call inside an [`super::uncounted`] scope runs its tasks in that scope.
    pub fn map<T: Sync, R: Send>(&self, items: &[T], f: impl Fn(&T) -> R + Sync) -> Vec<R> {
        let uncounted = super::values::is_uncounted();
        let unmetered = super::values::is_effort_unmetered();
        // A task notes the quantities that no limits reach in the request of the thread that asked for it.
        let ambient = super::values::ambient_gauges();
        self.threads.install(|| {
            items.par_iter().map(|item| super::values::with_ambient(ambient.clone(), || {
                let run = || if uncounted { super::uncounted(|| f(item)) } else { f(item) };
                if unmetered { super::unmetered_effort(run) } else { run() }
            })).collect()
        })
    }
}

/// The entries in flight on the pool's threads, by key, so a thread that
/// asks for an entry another thread computes waits for that computation.
#[derive(Debug)]
pub struct InFlight<K, V> {
    entries: Mutex<StableHashMap<K, Arc<Slot<V>>>>,
}

/// One computation in flight: its end, with its value where it has one,
/// and the condition its waiters block on.
#[derive(Debug)]
struct Slot<V> {
    end: Mutex<Option<Option<V>>>,
    ended: Condvar,
}

const UNPOISONED: &str = "a table of entries in flight that no panic poisoned";

impl<K: Eq + std::hash::Hash + Clone, V: Clone> InFlight<K, V> {
    pub fn new() -> Self {
        InFlight { entries: Mutex::new(StableHashMap::default()) }
    }

    /// The value of `key`: `compute`'s, where no other thread computes it,
    /// or the other thread's, waited for by a blocking wait. `compute` gives
    /// `None` where it is cancelled, and a thread that waited on it then
    /// computes the value itself.
    ///
    /// A computation leaves the table once it ends, by a value, a
    /// cancellation or a panic, so a waiter whose computation ended with no
    /// value asks again.
    pub fn get_or_compute(&self, key: K, compute: impl FnOnce() -> Option<V>) -> Option<V> {
        let mut compute = Some(compute);
        loop {
            let (slot, computes) = {
                let mut entries = self.entries.lock().expect(UNPOISONED);
                match entries.get(&key) {
                    Some(slot) => (slot.clone(), false),
                    None => {
                        let slot = Arc::new(Slot { end: Mutex::new(None), ended: Condvar::new() });
                        entries.insert(key.clone(), slot.clone());
                        (slot, true)
                    }
                }
            };
            if computes {
                let mut leave = Leave { table: self, key: &key, slot: &slot, value: None };
                let compute = compute.take().expect("a thread computes an entry at most once in one call");
                let value = compute()?;
                leave.value = Some(value.clone());
                return Some(value);
            }
            if let Some(value) = slot.wait() {
                return Some(value);
            }
        }
    }
}

impl<V: Clone> Slot<V> {
    /// The value of this computation once it ends, or `None` where it ended
    /// with no value.
    fn wait(&self) -> Option<V> {
        let end = self.end.lock().unwrap_or_else(std::sync::PoisonError::into_inner);
        let end = self.ended.wait_while(end, |end| end.is_none()).unwrap_or_else(std::sync::PoisonError::into_inner);
        end.clone().flatten()
    }
}

/// The end of a computation, when it returns or panics: its slot takes its
/// value, where it has one, and wakes its waiters, then the computation
/// leaves the table.
struct Leave<'t, K: Eq + std::hash::Hash, V> {
    table: &'t InFlight<K, V>,
    key: &'t K,
    slot: &'t Arc<Slot<V>>,
    value: Option<V>,
}

impl<K: Eq + std::hash::Hash, V> Drop for Leave<'_, K, V> {
    fn drop(&mut self) {
        {
            let mut end = self.slot.end.lock().unwrap_or_else(std::sync::PoisonError::into_inner);
            *end = Some(self.value.take());
            self.slot.ended.notify_all();
        }
        let mut entries = self.table.entries.lock().unwrap_or_else(std::sync::PoisonError::into_inner);
        if entries.get(self.key).is_some_and(|held| Arc::ptr_eq(held, self.slot)) {
            entries.remove(self.key);
        }
    }
}

impl<K: Eq + std::hash::Hash + Clone, V: Clone> Default for InFlight<K, V> {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::sync::atomic::{AtomicUsize, Ordering};

    /// A waiter on a computation that is cancelled computes the entry
    /// itself. The computation ends only once the waiter holds its slot.
    #[test]
    fn a_waiter_computes_a_cancelled_entry() {
        let table: InFlight<u32, u32> = InFlight::new();
        let computed = AtomicUsize::new(0);
        let started = std::sync::Barrier::new(2);
        std::thread::scope(|scope| {
            let first = scope.spawn(|| {
                table.get_or_compute(7, || {
                    started.wait();
                    // The table, this computation and the waiter hold the slot.
                    while table.entries.lock().unwrap().get(&7).map(Arc::strong_count) != Some(3) {
                        std::thread::yield_now();
                    }
                    None
                })
            });
            started.wait();
            let second = table.get_or_compute(7, || {
                computed.fetch_add(1, Ordering::SeqCst);
                Some(70)
            });
            assert_eq!(first.join().unwrap(), None);
            assert_eq!(second, Some(70));
        });
        assert_eq!(computed.load(Ordering::SeqCst), 1);
    }

    /// The entries of a chain, each of which reads the one before it, asked
    /// for on many threads at once, give their values, and the run ends.
    #[test]
    fn a_chain_of_reads_on_many_threads_ends() {
        const LENGTH: u32 = 64;
        fn entry(table: &InFlight<u32, u32>, key: u32) -> u32 {
            table
                .get_or_compute(key, || Some(if key == 0 { 0 } else { entry(table, key - 1) + 1 }))
                .expect("an entry that no computation cancels")
        }
        let table: InFlight<u32, u32> = InFlight::new();
        let keys: Vec<u32> = (0..LENGTH * 8).map(|item| (item * 37) % LENGTH).collect();
        let values = Pool::new(Some(8)).map(&keys, |&key| entry(&table, key));
        assert_eq!(values, keys);
    }
}
