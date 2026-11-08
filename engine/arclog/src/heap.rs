//! The live bytes of the process's heap, where the global allocator is a
//! [`Counted`] one, as the Python extension's is.
//!
//! A task session's bound counts these bytes, as
//! [`crate::session::TaskSession::within_bound`] gives, so that it bounds the
//! rows, indexes and buffers that its ledger does not count, such as a
//! relation that the result cache evicted while a table or a driver still
//! holds it.
//!
//! Each thread adds its allocations to a count of its own and adds that count
//! to the shared count once it passes [`FLUSH`] bytes either way, so the
//! shared count is off by less than [`FLUSH`] bytes per thread.

use std::alloc::{GlobalAlloc, Layout};
use std::cell::Cell;
use std::sync::atomic::{AtomicBool, AtomicIsize, Ordering};

/// A global allocator that allocates by `A` and counts the bytes it holds.
pub struct Counted<A>(pub A);

/// The bytes that a thread's count passes before it is added to [`LIVE`].
const FLUSH: isize = 64 << 10;

/// The live bytes that the threads' counts have added.
static LIVE: AtomicIsize = AtomicIsize::new(0);

/// Whether a [`Counted`] allocator has added a count to [`LIVE`].
static COUNTED: AtomicBool = AtomicBool::new(false);

thread_local! {
    /// The bytes this thread allocated, less those it freed, since it last
    /// added them to [`LIVE`]. The cell needs no allocation and no destructor,
    /// so the allocator can read it at any time.
    static PENDING: Cell<isize> = const { Cell::new(0) };
}

/// Adds `bytes` to [`LIVE`]. A thread takes this path once its count passes
/// [`FLUSH`] bytes either way.
#[cold]
#[inline(never)]
fn flush(bytes: isize) {
    LIVE.fetch_add(bytes, Ordering::Relaxed);
    if !COUNTED.load(Ordering::Relaxed) {
        COUNTED.store(true, Ordering::Relaxed);
    }
}

/// Adds `delta` to the calling thread's count, and the count to [`LIVE`] once
/// it passes [`FLUSH`].
///
/// This runs for each allocation and each free of the process, so it stands
/// inline in the allocator's methods, which are in the crate of the global
/// allocator, and the rare flush stands apart.
#[inline(always)]
fn add(delta: isize) {
    let held = PENDING.try_with(|pending| {
        let next = pending.get() + delta;
        if next.unsigned_abs() >= FLUSH as usize {
            pending.set(0);
            flush(next);
        } else {
            pending.set(next);
        }
    });
    if held.is_err() {
        flush(delta);
    }
}

#[inline(always)]
fn size(bytes: usize) -> isize {
    isize::try_from(bytes).unwrap_or(isize::MAX)
}

// SAFETY: each method calls the same method of `A` with the same arguments
// and returns its result; the count reads and writes no allocated memory.
unsafe impl<A: GlobalAlloc> GlobalAlloc for Counted<A> {
    #[inline]
    unsafe fn alloc(&self, layout: Layout) -> *mut u8 {
        let block = unsafe { self.0.alloc(layout) };
        if !block.is_null() {
            add(size(layout.size()));
        }
        block
    }

    #[inline]
    unsafe fn alloc_zeroed(&self, layout: Layout) -> *mut u8 {
        let block = unsafe { self.0.alloc_zeroed(layout) };
        if !block.is_null() {
            add(size(layout.size()));
        }
        block
    }

    #[inline]
    unsafe fn dealloc(&self, block: *mut u8, layout: Layout) {
        unsafe { self.0.dealloc(block, layout) };
        add(-size(layout.size()));
    }

    #[inline]
    unsafe fn realloc(&self, block: *mut u8, layout: Layout, new_size: usize) -> *mut u8 {
        let moved = unsafe { self.0.realloc(block, layout, new_size) };
        if !moved.is_null() {
            add(size(new_size) - size(layout.size()));
        }
        moved
    }
}

/// The live bytes of the heap, or `None` where the global allocator counts
/// none, which is not a [`Counted`] one.
pub fn live() -> Option<usize> {
    COUNTED.load(Ordering::Relaxed).then(|| usize::try_from(LIVE.load(Ordering::Relaxed)).unwrap_or(0))
}
