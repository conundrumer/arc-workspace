//! Hash maps and hash sets of the encoder whose iteration order can reach no
//! output.
//!
//! A hash map iterates in an order that follows from its hasher, its seed, the
//! order of its insertions and the layout of the standard library's table, so
//! no feature value, no record, no list and no byte of output may follow it.
//! The types of this module have no way to iterate in that order:
//!
//! - [`LookupMap`] and [`LookupSet`] answer lookups, and nothing else about
//!   their order. What they give about all their entries is a sorted view
//!   (`sorted_*`, `into_sorted_*`), a reduction that does not depend on the
//!   order (`sum_of`, `max_of`, `any`, ...), or a minimum with a key as the
//!   tie break.
//! - [`InsertionMap`] iterates in the order of the first insertion of each key.
//!   That order is the order of the program's own insertions, which no hash
//!   decides.
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
use std::hash::{BuildHasher, Hash, Hasher};
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

/// The empty slot of an [`InsertionMap`]'s table.
const FREE: u32 = u32::MAX;

fn hash_of<Q: Hash + ?Sized>(key: &Q) -> u64 {
    let mut hasher = FastHasher::starting_at(0);
    key.hash(&mut hasher);
    hasher.finish()
}

/// The first slot to try for `hash` in a table of `size` slots, a power of two of at least 8.
fn home(hash: u64, size: usize) -> usize {
    (hash.wrapping_mul(0x9E37_79B9_7F4A_7C15) >> (64 - size.trailing_zeros())) as usize
}

/// A map that iterates in the order of the first insertion of each key. Its order follows from the program's insertions and from no hash, so what a program inserts in a fixed order, it iterates in a fixed order. It has no removal.
#[derive(Clone)]
pub struct InsertionMap<K, V> {
    /// The place in `entries` of each key, at the slot its hash leads to, or [`FREE`]. A power of two in length, at least twice the entries.
    slots: Vec<u32>,
    entries: Vec<(u64, K, V)>,
}

impl<K, V> Default for InsertionMap<K, V> {
    fn default() -> Self {
        InsertionMap { slots: Vec::new(), entries: Vec::new() }
    }
}

/// The entries of an [`InsertionMap`] by reference, in insertion order.
pub struct Entries<'m, K, V>(std::slice::Iter<'m, (u64, K, V)>);

impl<'m, K, V> Iterator for Entries<'m, K, V> {
    type Item = (&'m K, &'m V);

    fn next(&mut self) -> Option<Self::Item> {
        self.0.next().map(|entry| (&entry.1, &entry.2))
    }

    fn size_hint(&self) -> (usize, Option<usize>) {
        self.0.size_hint()
    }
}

/// The entries of an [`InsertionMap`], in insertion order.
pub struct IntoEntries<K, V>(std::vec::IntoIter<(u64, K, V)>);

impl<K, V> Iterator for IntoEntries<K, V> {
    type Item = (K, V);

    fn next(&mut self) -> Option<Self::Item> {
        self.0.next().map(|entry| (entry.1, entry.2))
    }

    fn size_hint(&self) -> (usize, Option<usize>) {
        self.0.size_hint()
    }
}

impl<K, V> InsertionMap<K, V> {
    pub fn new() -> Self {
        InsertionMap::default()
    }

    pub fn len(&self) -> usize {
        self.entries.len()
    }

    pub fn is_empty(&self) -> bool {
        self.entries.is_empty()
    }

    pub fn iter(&self) -> Entries<'_, K, V> {
        Entries(self.entries.iter())
    }

    pub fn keys(&self) -> impl Iterator<Item = &K> {
        self.entries.iter().map(|entry| &entry.1)
    }

    pub fn values(&self) -> impl Iterator<Item = &V> {
        self.entries.iter().map(|entry| &entry.2)
    }

    pub fn values_mut(&mut self) -> impl Iterator<Item = &mut V> {
        self.entries.iter_mut().map(|entry| &mut entry.2)
    }
}

impl<K: Eq + Hash, V> InsertionMap<K, V> {
    /// The place in `entries` of `key`, whose hash is `hash`.
    fn find<Q>(&self, hash: u64, key: &Q) -> Option<usize>
    where
        K: Borrow<Q>,
        Q: Eq + ?Sized,
    {
        if self.slots.is_empty() {
            return None;
        }
        let mask = self.slots.len() - 1;
        let mut at = home(hash, self.slots.len());
        loop {
            let slot = self.slots[at];
            if slot == FREE {
                return None;
            }
            let entry = &self.entries[slot as usize];
            if entry.0 == hash && Borrow::<Q>::borrow(&entry.1) == key {
                return Some(slot as usize);
            }
            at = (at + 1) & mask;
        }
    }

    /// Doubles the table, and places each entry again.
    fn grow(&mut self) {
        let size = (self.slots.len() * 2).max(8);
        self.slots.clear();
        self.slots.resize(size, FREE);
        let mask = size - 1;
        for (place, entry) in self.entries.iter().enumerate() {
            let mut at = home(entry.0, size);
            while self.slots[at] != FREE {
                at = (at + 1) & mask;
            }
            self.slots[at] = place as u32;
        }
    }

    /// Adds an entry for a key that the map does not hold, and gives its place.
    fn push(&mut self, hash: u64, key: K, value: V) -> usize {
        if (self.entries.len() + 1) * 2 > self.slots.len() {
            self.grow();
        }
        let mask = self.slots.len() - 1;
        let mut at = home(hash, self.slots.len());
        while self.slots[at] != FREE {
            at = (at + 1) & mask;
        }
        let place = self.entries.len();
        self.slots[at] = place as u32;
        self.entries.push((hash, key, value));
        place
    }

    pub fn get<Q>(&self, key: &Q) -> Option<&V>
    where
        K: Borrow<Q>,
        Q: Hash + Eq + ?Sized,
    {
        self.find(hash_of(key), key).map(|place| &self.entries[place].2)
    }

    pub fn get_mut<Q>(&mut self, key: &Q) -> Option<&mut V>
    where
        K: Borrow<Q>,
        Q: Hash + Eq + ?Sized,
    {
        match self.find(hash_of(key), key) {
            Some(place) => Some(&mut self.entries[place].2),
            None => None,
        }
    }

    pub fn contains_key<Q>(&self, key: &Q) -> bool
    where
        K: Borrow<Q>,
        Q: Hash + Eq + ?Sized,
    {
        self.find(hash_of(key), key).is_some()
    }

    /// Sets the value of `key`, which keeps its place if the map held it. Gives the value it had.
    pub fn insert(&mut self, key: K, value: V) -> Option<V> {
        let hash = hash_of(&key);
        match self.find(hash, &key) {
            Some(place) => Some(std::mem::replace(&mut self.entries[place].2, value)),
            None => {
                self.push(hash, key, value);
                None
            }
        }
    }

    /// The value of `key`, which `make` gives, at the end of the order, where the map does not hold it.
    pub fn get_or_insert_with(&mut self, key: K, make: impl FnOnce() -> V) -> &mut V {
        let hash = hash_of(&key);
        let place = match self.find(hash, &key) {
            Some(place) => place,
            None => self.push(hash, key, make()),
        };
        &mut self.entries[place].2
    }

    pub fn entry(&mut self, key: K) -> InsertionSlot<'_, K, V> {
        InsertionSlot { map: self, key }
    }
}

/// The place of one key in an [`InsertionMap`].
pub struct InsertionSlot<'m, K, V> {
    map: &'m mut InsertionMap<K, V>,
    key: K,
}

impl<'m, K: Eq + Hash, V> InsertionSlot<'m, K, V> {
    pub fn or_insert(self, value: V) -> &'m mut V {
        let map = self.map;
        map.get_or_insert_with(self.key, || value)
    }

    pub fn or_insert_with(self, make: impl FnOnce() -> V) -> &'m mut V {
        let map = self.map;
        map.get_or_insert_with(self.key, make)
    }

    pub fn or_default(self) -> &'m mut V
    where
        V: Default,
    {
        let map = self.map;
        map.get_or_insert_with(self.key, V::default)
    }
}

impl<'m, K, V> IntoIterator for &'m InsertionMap<K, V> {
    type Item = (&'m K, &'m V);
    type IntoIter = Entries<'m, K, V>;

    fn into_iter(self) -> Self::IntoIter {
        self.iter()
    }
}

impl<K, V> IntoIterator for InsertionMap<K, V> {
    type Item = (K, V);
    type IntoIter = IntoEntries<K, V>;

    fn into_iter(self) -> Self::IntoIter {
        IntoEntries(self.entries.into_iter())
    }
}

impl<K: Eq + Hash, V> Extend<(K, V)> for InsertionMap<K, V> {
    fn extend<I: IntoIterator<Item = (K, V)>>(&mut self, items: I) {
        for (key, value) in items {
            self.insert(key, value);
        }
    }
}

impl<K: Eq + Hash, V> FromIterator<(K, V)> for InsertionMap<K, V> {
    fn from_iter<I: IntoIterator<Item = (K, V)>>(items: I) -> Self {
        let mut out = InsertionMap::default();
        out.extend(items);
        out
    }
}

impl<K, Q, V> Index<&Q> for InsertionMap<K, V>
where
    K: Eq + Hash + Borrow<Q>,
    Q: Eq + Hash + ?Sized,
{
    type Output = V;

    fn index(&self, key: &Q) -> &V {
        self.get(key).expect("a key the map holds")
    }
}

impl<K: fmt::Debug, V: fmt::Debug> fmt::Debug for InsertionMap<K, V> {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.debug_map().entries(self.iter()).finish()
    }
}
