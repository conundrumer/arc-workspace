//! The one hash function of the arclog engine: a fixed function with no
//! random seed, so hashes are the same from run to run.
//!
//! Every hash map and hash set of the engine is built with [`StableState`],
//! and every content hash is a [`StableHash`]. The standard library's
//! `RandomState` is never used, since its seed differs from run to run.

#![allow(unused_variables, dead_code)]

use std::hash::{BuildHasher, Hasher};

/// A 128-bit hash of a content, computed by [`StableHasher`].
///
/// Two equal contents have equal hashes. Two contents whose hashes match are
/// compared by content before they are taken as equal.
#[derive(Clone, Copy, PartialEq, Eq, Hash, Debug)]
pub struct StableHash(pub u128);

/// The engine's fixed hash function, with no seed.
///
/// The same bytes written in the same order give the same hash in every run,
/// on every platform.
#[derive(Clone, Debug, Default)]
pub struct StableHasher {
    state: [u64; 2],
}

impl StableHasher {
    /// A hasher in its fixed initial state.
    pub fn new() -> Self {
        todo!()
    }

    /// The 128-bit hash of the bytes written so far.
    pub fn finish128(&self) -> StableHash {
        todo!()
    }
}

impl Hasher for StableHasher {
    fn finish(&self) -> u64 {
        todo!()
    }

    fn write(&mut self, bytes: &[u8]) {
        todo!()
    }
}

/// The [`BuildHasher`] of every hash map and hash set of the engine.
#[derive(Clone, Copy, Debug, Default)]
pub struct StableState;

impl BuildHasher for StableState {
    type Hasher = StableHasher;

    fn build_hasher(&self) -> StableHasher {
        todo!()
    }
}

/// A hash map under the engine's fixed hash function.
///
/// Its iteration order follows from its keys and the order they were
/// inserted in, so it is the same from run to run only where both are, and
/// not where the keys hold an Ident, whose number depends on the order of
/// interning. It is an order of encodings either way, so no output may
/// depend on it.
pub type StableHashMap<K, V> = std::collections::HashMap<K, V, StableState>;

/// A hash set under the engine's fixed hash function, with the iteration rule
/// of [`StableHashMap`].
pub type StableHashSet<T> = std::collections::HashSet<T, StableState>;
