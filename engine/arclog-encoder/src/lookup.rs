//! Hash maps and hash sets of the encoder whose iteration order can reach no
//! output.
//!
//! A hash map iterates in an order that follows from its hasher, its seed, the
//! order of its insertions and the layout of the standard library's table, so
//! no feature value, no record, no list and no byte of output may follow it.
//! The types of this module have no way to iterate in that order:
//! [`LookupMap`] and [`LookupSet`] answer lookups, and nothing else about their
//! order. What they give about all their entries is a sorted view
//! (`sorted_*`, `into_sorted_*`), a reduction that does not depend on the
//! order (`sum_of`, `max_of`, `any`, ...), or a minimum with a key as the tie
//! break.
//!
//! The hasher of both is the encoder's fast hasher. Where the environment
//! variable `ARCLOG_MAP_SEED` holds a `u64` other than 0, it starts each
//! hasher from a state that follows from that number, so the buckets of every
//! key move. Unset, or 0, the hasher starts from 0. Equal outputs of runs with
//! and without a seed show that no output follows a map's buckets.
#![allow(clippy::disallowed_types)]

use std::borrow::Borrow;
use std::collections::hash_map::Entry;
use std::collections::{HashMap, HashSet};
use std::fmt;
use std::hash::{BuildHasher, Hash};
use std::ops::Index;
use std::sync::OnceLock;

use crate::native::FastHasher;

/// The finalizer of MurmurHash3's 64-bit hash.
fn mix(mut k: u64) -> u64 {
    k ^= k >> 33;
    k = k.wrapping_mul(0xff51_afd7_ed55_8ccd);
    k ^= k >> 33;
    k = k.wrapping_mul(0xc4ce_b9fe_1a85_ec53);
    k ^ (k >> 33)
}

/// The state that each hasher of a map starts from: 0 where `ARCLOG_MAP_SEED` is unset or 0, and a mix of that number otherwise.
///
/// # Panics
///
/// At the first call, where the variable is set and is no `u64`.
fn start_state() -> u64 {
    static START: OnceLock<u64> = OnceLock::new();
    *START.get_or_init(|| match std::env::var("ARCLOG_MAP_SEED") {
        Err(_) => 0,
        Ok(text) => {
            let seed: u64 = text.parse().unwrap_or_else(|_| panic!("ARCLOG_MAP_SEED is `{text}`; it must be unset or a u64"));
            if seed == 0 { 0 } else { mix(seed) }
        }
    })
}

/// The [`BuildHasher`] of the maps and sets of this module.
#[derive(Clone, Copy, Debug)]
pub struct SeededState {
    start: u64,
}

impl Default for SeededState {
    fn default() -> Self {
        SeededState { start: start_state() }
    }
}

impl BuildHasher for SeededState {
    type Hasher = FastHasher;

    fn build_hasher(&self) -> FastHasher {
        FastHasher::starting_at(self.start)
    }
}

/// A number type whose sum does not depend on the order of its terms.
pub trait Exact: Copy {
    const ZERO: Self;
    fn plus(self, other: Self) -> Self;
}

macro_rules! exact {
    ($($ty:ty),*) => {
        $(impl Exact for $ty {
            const ZERO: Self = 0;
            fn plus(self, other: Self) -> Self {
                self + other
            }
        })*
    };
}

exact!(u8, u16, u32, u64, u128, usize, i32, i64);

/// A hash map that answers lookups. It has no iteration; see the module's text for what it gives about all its entries.
#[derive(Clone)]
pub struct LookupMap<K, V> {
    inner: HashMap<K, V, SeededState>,
}

impl<K, V> Default for LookupMap<K, V> {
    fn default() -> Self {
        LookupMap { inner: HashMap::with_hasher(SeededState::default()) }
    }
}

impl<K, V> LookupMap<K, V> {
    pub fn new() -> Self {
        LookupMap::default()
    }

    pub fn with_capacity(capacity: usize) -> Self {
        LookupMap { inner: HashMap::with_capacity_and_hasher(capacity, SeededState::default()) }
    }

    pub fn len(&self) -> usize {
        self.inner.len()
    }

    pub fn is_empty(&self) -> bool {
        self.inner.is_empty()
    }

    pub fn clear(&mut self) {
        self.inner.clear();
    }

    /// The sum of `value` over the entries.
    pub fn sum_of<T: Exact>(&self, value: impl Fn(&K, &V) -> T) -> T {
        self.inner.iter().fold(T::ZERO, |sum, (key, held)| sum.plus(value(key, held)))
    }

    /// The sum of `value` over the entries, held at `u64::MAX`.
    pub fn saturating_sum_of(&self, value: impl Fn(&K, &V) -> u64) -> u64 {
        self.inner.iter().fold(0u64, |sum, (key, held)| sum.saturating_add(value(key, held)))
    }

    /// The greatest `value` over the entries.
    pub fn max_of<T: Ord>(&self, value: impl Fn(&K, &V) -> T) -> Option<T> {
        self.inner.iter().map(|(key, held)| value(key, held)).max()
    }

    /// The least `value` over the entries.
    pub fn min_of<T: Ord>(&self, value: impl Fn(&K, &V) -> T) -> Option<T> {
        self.inner.iter().map(|(key, held)| value(key, held)).min()
    }

    /// Whether `test` holds at some entry.
    pub fn any(&self, test: impl Fn(&K, &V) -> bool) -> bool {
        self.inner.iter().any(|(key, held)| test(key, held))
    }

    /// Whether `test` holds at every entry.
    pub fn all(&self, test: impl Fn(&K, &V) -> bool) -> bool {
        self.inner.iter().all(|(key, held)| test(key, held))
    }

    /// The entry with the least `rank`, the least key among those of equal rank.
    pub fn min_entry_by<T: Ord>(&self, rank: impl Fn(&K, &V) -> T) -> Option<(&K, &V)>
    where
        K: Ord,
    {
        self.inner.iter().min_by(|a, b| (rank(a.0, a.1), a.0).cmp(&(rank(b.0, b.1), b.0)))
    }

    /// The entries in the order of their keys.
    pub fn sorted_entries(&self) -> Vec<(&K, &V)>
    where
        K: Ord,
    {
        let mut out: Vec<(&K, &V)> = self.inner.iter().collect();
        out.sort_unstable_by(|a, b| a.0.cmp(b.0));
        out
    }

    /// The keys in order.
    pub fn sorted_keys(&self) -> Vec<&K>
    where
        K: Ord,
    {
        let mut out: Vec<&K> = self.inner.keys().collect();
        out.sort_unstable();
        out
    }

    /// The values in the order of their keys.
    pub fn sorted_values(&self) -> Vec<&V>
    where
        K: Ord,
    {
        self.sorted_entries().into_iter().map(|(_, held)| held).collect()
    }

    /// `make` of each entry, in the order of those items. Two items that compare equal are interchangeable.
    pub fn sorted_map<T: Ord>(&self, make: impl Fn(&K, &V) -> T) -> Vec<T> {
        let mut out: Vec<T> = self.inner.iter().map(|(key, held)| make(key, held)).collect();
        out.sort_unstable();
        out
    }

    /// The entries in the order of their keys.
    pub fn into_sorted_vec(self) -> Vec<(K, V)>
    where
        K: Ord,
    {
        let mut out: Vec<(K, V)> = self.inner.into_iter().collect();
        out.sort_unstable_by(|a, b| a.0.cmp(&b.0));
        out
    }

    /// The keys in order.
    pub fn into_sorted_keys(self) -> Vec<K>
    where
        K: Ord,
    {
        let mut out: Vec<K> = self.inner.into_keys().collect();
        out.sort_unstable();
        out
    }

    /// A map of what `make` gives at each entry that it gives something at. Where it gives two entries the same key, the map keeps the least value.
    pub fn to_map_keeping_least<K2, V2>(&self, make: impl Fn(&K, &V) -> Option<(K2, V2)>) -> LookupMap<K2, V2>
    where
        K2: Eq + Hash,
        V2: Ord,
    {
        let mut out = LookupMap::default();
        for (key, held) in &self.inner {
            let Some((key, value)) = make(key, held) else { continue };
            match out.inner.entry(key) {
                Entry::Vacant(slot) => {
                    slot.insert(value);
                }
                Entry::Occupied(mut slot) => {
                    if value < *slot.get() {
                        *slot.get_mut() = value;
                    }
                }
            }
        }
        out
    }
}

impl<K: Eq + Hash, V> LookupMap<K, V> {
    pub fn get<Q>(&self, key: &Q) -> Option<&V>
    where
        K: Borrow<Q>,
        Q: Hash + Eq + ?Sized,
    {
        self.inner.get(key)
    }

    pub fn get_mut<Q>(&mut self, key: &Q) -> Option<&mut V>
    where
        K: Borrow<Q>,
        Q: Hash + Eq + ?Sized,
    {
        self.inner.get_mut(key)
    }

    pub fn contains_key<Q>(&self, key: &Q) -> bool
    where
        K: Borrow<Q>,
        Q: Hash + Eq + ?Sized,
    {
        self.inner.contains_key(key)
    }

    pub fn insert(&mut self, key: K, value: V) -> Option<V> {
        self.inner.insert(key, value)
    }

    pub fn remove<Q>(&mut self, key: &Q) -> Option<V>
    where
        K: Borrow<Q>,
        Q: Hash + Eq + ?Sized,
    {
        self.inner.remove(key)
    }

    pub fn entry(&mut self, key: K) -> Entry<'_, K, V> {
        self.inner.entry(key)
    }

    pub fn reserve(&mut self, additional: usize) {
        self.inner.reserve(additional);
    }
}

impl<K: Eq + Hash, V: PartialEq> PartialEq for LookupMap<K, V> {
    fn eq(&self, other: &Self) -> bool {
        self.inner == other.inner
    }
}

impl<K: Eq + Hash, V: Eq> Eq for LookupMap<K, V> {}

impl<K: Ord + fmt::Debug, V: fmt::Debug> fmt::Debug for LookupMap<K, V> {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.debug_map().entries(self.sorted_entries()).finish()
    }
}

impl<K: Eq + Hash, V> Extend<(K, V)> for LookupMap<K, V> {
    fn extend<I: IntoIterator<Item = (K, V)>>(&mut self, items: I) {
        self.inner.extend(items);
    }
}

impl<K: Eq + Hash, V> FromIterator<(K, V)> for LookupMap<K, V> {
    fn from_iter<I: IntoIterator<Item = (K, V)>>(items: I) -> Self {
        let mut out = LookupMap::default();
        out.inner.extend(items);
        out
    }
}

impl<K, Q, V> Index<&Q> for LookupMap<K, V>
where
    K: Eq + Hash + Borrow<Q>,
    Q: Eq + Hash + ?Sized,
{
    type Output = V;

    fn index(&self, key: &Q) -> &V {
        &self.inner[key]
    }
}

/// A hash set that answers lookups. It has no iteration; see the module's text for what it gives about all its members.
#[derive(Clone)]
pub struct LookupSet<T> {
    inner: HashSet<T, SeededState>,
}

impl<T> Default for LookupSet<T> {
    fn default() -> Self {
        LookupSet { inner: HashSet::with_hasher(SeededState::default()) }
    }
}

impl<T> LookupSet<T> {
    pub fn new() -> Self {
        LookupSet::default()
    }

    pub fn with_capacity(capacity: usize) -> Self {
        LookupSet { inner: HashSet::with_capacity_and_hasher(capacity, SeededState::default()) }
    }

    pub fn len(&self) -> usize {
        self.inner.len()
    }

    pub fn is_empty(&self) -> bool {
        self.inner.is_empty()
    }

    pub fn clear(&mut self) {
        self.inner.clear();
    }

    /// The members in order.
    pub fn sorted(&self) -> Vec<&T>
    where
        T: Ord,
    {
        let mut out: Vec<&T> = self.inner.iter().collect();
        out.sort_unstable();
        out
    }

    /// The members in order.
    pub fn into_sorted_vec(self) -> Vec<T>
    where
        T: Ord,
    {
        let mut out: Vec<T> = self.inner.into_iter().collect();
        out.sort_unstable();
        out
    }
}

impl<T: Eq + Hash> LookupSet<T> {
    /// Whether the set did not hold `value`.
    pub fn insert(&mut self, value: T) -> bool {
        self.inner.insert(value)
    }

    pub fn contains<Q>(&self, value: &Q) -> bool
    where
        T: Borrow<Q>,
        Q: Hash + Eq + ?Sized,
    {
        self.inner.contains(value)
    }

    /// Whether the set held `value`.
    pub fn remove<Q>(&mut self, value: &Q) -> bool
    where
        T: Borrow<Q>,
        Q: Hash + Eq + ?Sized,
    {
        self.inner.remove(value)
    }
}

impl<T: Eq + Hash> PartialEq for LookupSet<T> {
    fn eq(&self, other: &Self) -> bool {
        self.inner == other.inner
    }
}

impl<T: Eq + Hash> Eq for LookupSet<T> {}

impl<T: Ord + fmt::Debug> fmt::Debug for LookupSet<T> {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.debug_set().entries(self.sorted()).finish()
    }
}

impl<T: Eq + Hash> Extend<T> for LookupSet<T> {
    fn extend<I: IntoIterator<Item = T>>(&mut self, items: I) {
        self.inner.extend(items);
    }
}

impl<T: Eq + Hash> FromIterator<T> for LookupSet<T> {
    fn from_iter<I: IntoIterator<Item = T>>(items: I) -> Self {
        let mut out = LookupSet::default();
        out.inner.extend(items);
        out
    }
}

impl<T: Eq + Hash, const N: usize> From<[T; N]> for LookupSet<T> {
    fn from(items: [T; N]) -> Self {
        items.into_iter().collect()
    }
}
