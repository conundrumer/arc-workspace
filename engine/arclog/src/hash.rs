//! The one hash function of the arclog engine: a fixed function with no
//! random seed, so hashes are the same from run to run.
//!
//! Every hash map and hash set of the engine is built with [`StableState`],
//! and every content hash is a [`StableHash`]. The standard library's
//! `RandomState` is never used, since its seed differs from run to run.

use std::hash::{BuildHasher, Hasher};

/// A 128-bit hash of a content, computed by [`StableHasher`].
///
/// Two equal contents have equal hashes. Two unequal contents can have
/// equal hashes.
#[derive(Clone, Copy, PartialEq, Eq, Hash, Debug)]
pub struct StableHash(pub u128);

/// The engine's fixed hash function, with no seed.
///
/// The same bytes written in the same order give the same hash in every run,
/// on every platform.
#[derive(Clone, Debug)]
pub struct StableHasher {
    state: [u64; 2],
    /// The bytes written since the last full word, little-endian.
    tail: u64,
    /// The count of bytes written.
    len: u64,
}

const LANE_0: u64 = 0x9e37_79b9_7f4a_7c15;
const LANE_1: u64 = 0xc2b2_ae3d_27d4_eb4f;
const MUL_0: u64 = 0x87c3_7b91_1142_53d5;
const MUL_1: u64 = 0x4cf5_ad43_2745_937f;

/// The finalizer of MurmurHash3's 64-bit hash.
fn fmix64(mut k: u64) -> u64 {
    k ^= k >> 33;
    k = k.wrapping_mul(0xff51_afd7_ed55_8ccd);
    k ^= k >> 33;
    k = k.wrapping_mul(0xc4ce_b9fe_1a85_ec53);
    k ^ (k >> 33)
}

impl Default for StableHasher {
    fn default() -> Self {
        StableHasher::new()
    }
}

impl StableHasher {
    /// A hasher in its fixed initial state.
    pub fn new() -> Self {
        StableHasher { state: [LANE_0, LANE_1], tail: 0, len: 0 }
    }

    fn absorb(state: &mut [u64; 2], word: u64) {
        let [a, b] = *state;
        let a = (a ^ word.wrapping_mul(MUL_0)).rotate_left(31).wrapping_mul(MUL_1).wrapping_add(b);
        let b = (b ^ word.wrapping_mul(MUL_1)).rotate_left(33).wrapping_mul(MUL_0).wrapping_add(a);
        *state = [a, b];
    }

    /// The 128-bit hash of the bytes written so far.
    pub fn finish128(&self) -> StableHash {
        let mut state = self.state;
        StableHasher::absorb(&mut state, self.tail);
        StableHasher::absorb(&mut state, self.len);
        let [a, b] = state;
        let a = fmix64(a.wrapping_add(b));
        let b = fmix64(b.wrapping_add(a));
        StableHash((u128::from(a) << 64) | u128::from(b))
    }
}

impl Hasher for StableHasher {
    fn finish(&self) -> u64 {
        self.finish128().0 as u64
    }

    /// Writes `bytes` as their concatenation with the bytes written before,
    /// so the hash does not depend on how the bytes are split into writes.
    fn write(&mut self, bytes: &[u8]) {
        let mut rest = bytes;
        while !rest.is_empty() {
            if self.len % 8 == 0 && rest.len() >= 8 {
                let (word, after) = rest.split_at(8);
                let word = u64::from_le_bytes(word.try_into().expect("a slice of 8 bytes"));
                StableHasher::absorb(&mut self.state, word);
                self.len += 8;
                rest = after;
            } else {
                self.tail |= u64::from(rest[0]) << (8 * (self.len % 8));
                self.len += 1;
                rest = &rest[1..];
                if self.len % 8 == 0 {
                    StableHasher::absorb(&mut self.state, self.tail);
                    self.tail = 0;
                }
            }
        }
    }

    // Each integer is written little-endian, and a `usize` or an `isize` as
    // 64 bits, so the hash is the same on every platform.
    fn write_u8(&mut self, i: u8) {
        self.write(&[i]);
    }
    fn write_u16(&mut self, i: u16) {
        self.write(&i.to_le_bytes());
    }
    fn write_u32(&mut self, i: u32) {
        self.write(&i.to_le_bytes());
    }
    fn write_u64(&mut self, i: u64) {
        self.write(&i.to_le_bytes());
    }
    fn write_u128(&mut self, i: u128) {
        self.write(&i.to_le_bytes());
    }
    fn write_usize(&mut self, i: usize) {
        self.write_u64(i as u64);
    }
    fn write_i8(&mut self, i: i8) {
        self.write_u8(i as u8);
    }
    fn write_i16(&mut self, i: i16) {
        self.write_u16(i as u16);
    }
    fn write_i32(&mut self, i: i32) {
        self.write_u32(i as u32);
    }
    fn write_i64(&mut self, i: i64) {
        self.write_u64(i as u64);
    }
    fn write_i128(&mut self, i: i128) {
        self.write_u128(i as u128);
    }
    fn write_isize(&mut self, i: isize) {
        self.write_u64(i as i64 as u64);
    }
}

/// The [`BuildHasher`] of every hash map and hash set of the engine.
#[derive(Clone, Copy, Debug, Default)]
pub struct StableState;

impl BuildHasher for StableState {
    type Hasher = StableHasher;

    fn build_hasher(&self) -> StableHasher {
        StableHasher::new()
    }
}

/// A hash map under the engine's fixed hash function.
///
/// Its iteration order follows from its keys and the order they were
/// inserted in, so it is the same from run to run only where both are, and
/// not where the keys hold an Ident, whose number depends on the order of
/// interning. It is an order of encodings either way, and no order of the
/// content.
pub type StableHashMap<K, V> = std::collections::HashMap<K, V, StableState>;

/// A hash set under the engine's fixed hash function, with the iteration rule
/// of [`StableHashMap`].
pub type StableHashSet<T> = std::collections::HashSet<T, StableState>;
