//! The engine's one use of the clock.
//!
//! A request's rows, stops and counts follow from its inputs alone, so no
//! code of a request reads a clock. The `clippy.toml` of each engine library
//! crate refuses `Instant::now`, `Instant::elapsed` and `SystemTime::now`, and
//! this module holds the only calls. What a request may take from it is a
//! [`Stopwatch`] reading for a report of the request's timings, an [`Elapsed`],
//! and the stamp of the process ([`process_stamp`]) for an identity that is
//! local to a process.

#![allow(clippy::disallowed_methods)]

use std::iter::Sum;
use std::ops::{Add, AddAssign};
use std::time::{Duration, Instant, SystemTime, UNIX_EPOCH};

/// A running timer from the moment of [`Stopwatch::start`].
#[derive(Clone, Copy, Debug)]
pub struct Stopwatch {
    start: Instant,
}

impl Stopwatch {
    /// A timer that starts now.
    #[inline(always)]
    pub fn start() -> Self {
        Stopwatch { start: Instant::now() }
    }

    /// The time since [`Stopwatch::start`].
    #[inline(always)]
    pub fn elapsed(&self) -> Elapsed {
        Elapsed(self.start.elapsed())
    }
}

/// A time that a [`Stopwatch`] measured, for a report.
#[derive(Clone, Copy, Debug, Default)]
pub struct Elapsed(Duration);

impl Elapsed {
    /// The time in seconds.
    pub fn seconds(self) -> f64 {
        self.0.as_secs_f64()
    }

    /// The time in nanoseconds.
    pub fn nanos(self) -> u128 {
        self.0.as_nanos()
    }
}

impl Add for Elapsed {
    type Output = Elapsed;

    fn add(self, other: Elapsed) -> Elapsed {
        Elapsed(self.0 + other.0)
    }
}

impl AddAssign for Elapsed {
    fn add_assign(&mut self, other: Elapsed) {
        self.0 += other.0;
    }
}

impl Sum for Elapsed {
    fn sum<I: Iterator<Item = Elapsed>>(times: I) -> Elapsed {
        times.fold(Elapsed::default(), Add::add)
    }
}

/// The nanoseconds from the Unix epoch to the first call of this function in
/// the process, which tells one process from another that has the same id.
pub fn process_stamp() -> u128 {
    static STAMP: std::sync::OnceLock<u128> = std::sync::OnceLock::new();
    *STAMP.get_or_init(|| SystemTime::now().duration_since(UNIX_EPOCH).map_or(0, |since| since.as_nanos()))
}
