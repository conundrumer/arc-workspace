//! A computation in flight that panics ends for the threads that wait on it.

use arclog::eval::pool::InFlight;
use std::sync::atomic::{AtomicBool, Ordering};

/// A waiter on a computation that panics asks again and computes the entry itself.
#[test]
fn a_waiter_computes_an_entry_whose_computation_panicked() {
    let table: InFlight<u32, u32> = InFlight::new();
    let computing = AtomicBool::new(false);
    std::thread::scope(|scope| {
        let first = scope.spawn(|| {
            std::panic::catch_unwind(std::panic::AssertUnwindSafe(|| {
                table.get_or_compute(7, || {
                    computing.store(true, Ordering::SeqCst);
                    std::thread::sleep(std::time::Duration::from_millis(100));
                    panic!("boom")
                })
            }))
        });
        while !computing.load(Ordering::SeqCst) {
            std::thread::yield_now();
        }
        let second = table.get_or_compute(7, || Some(70));
        assert!(first.join().expect("the thread ends").is_err());
        assert_eq!(second, Some(70));
    });
}
