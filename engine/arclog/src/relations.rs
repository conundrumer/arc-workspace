//! Rows, relations and their indexes.
//!
//! A relation is a set of rows of one arity. A body's relation is held as
//! its parts, each stored row after row in one array with a hash table of
//! row numbers over it. An index is a trie over the columns in one order, as
//! sorted arrays, built on first use in the order that a clause's variable
//! order asks for, and kept with the relation.
//!
//! A relation is a set: each function here that gives its rows gives them
//! in an order of encodings and no order of the content.

use crate::hash::{StableHash, StableHashMap, StableHashSet, StableHasher};
use crate::terms::TermId;

/// A row: a fixed-arity array of term ids, with no type tag.
pub type Row = Box<[TermId]>;

/// The position of a column in a relation's rows.
#[derive(Clone, Copy, PartialEq, Eq, Hash, Debug)]
pub struct ColumnIndex(pub u16);

/// The columns of a key or a type parameter bound to several fields: one
/// column per field, side by side in the row, so a component reads the
/// group as a short array of term ids, `&row[start..start + len]`.
#[derive(Clone, Copy, PartialEq, Eq, Hash, Debug)]
pub struct ColumnGroup {
    pub start: ColumnIndex,
    pub len: u16,
}

/// A set of rows of one arity, stored row after row in one array with a hash
/// table of row numbers over it. Its clones share its rows until one of them
/// takes a row.
#[derive(Clone, Debug, Default)]
pub struct RowSet {
    arity: u16,
    rows: std::sync::Arc<Rows>,
}

/// The rows of a [`RowSet`] in the order they were first inserted.
#[derive(Clone, Debug, Default)]
struct Rows {
    /// The values of the rows, row after row.
    values: Vec<TermId>,
    count: u32,
    /// An open-addressing table of 1 + a row's number, 0 in an empty slot.
    /// Its length is 0 or a power of two.
    slots: Box<[u32]>,
}

/// The largest share of a [`Rows`] table's slots in use, as a fraction.
const SLOTS_USED: (usize, usize) = (3, 4);

fn row_hash(row: &[TermId]) -> usize {
    let mut hash = 0x9E37_79B9_7F4A_7C15_u64;
    for value in row {
        hash = (hash.rotate_left(5) ^ u64::from(value.encoding())).wrapping_mul(0x517C_C1B7_2722_0A95);
    }
    (hash ^ (hash >> 32)) as usize
}

impl Rows {
    fn row(&self, number: u32, arity: usize) -> &[TermId] {
        &self.values[number as usize * arity..(number as usize + 1) * arity]
    }

    /// The slot that holds `row`, or the empty slot where it would go. The
    /// table has an empty slot.
    fn slot(&self, row: &[TermId]) -> usize {
        let mask = self.slots.len() - 1;
        let mut at = row_hash(row) & mask;
        while self.slots[at] != 0 && self.row(self.slots[at] - 1, row.len()) != row {
            at = (at + 1) & mask;
        }
        at
    }

    fn grow(&mut self, arity: usize) {
        self.slots = vec![0; (self.slots.len() * 2).max(8)].into();
        for number in 0..self.count {
            let at = self.slot(self.row(number, arity));
            self.slots[at] = number + 1;
        }
    }

    fn bytes(&self) -> usize {
        (self.values.capacity() + self.slots.len()) * 4
    }
}

impl RowSet {
    /// An empty set of rows of `arity` columns.
    pub fn empty(arity: u16) -> Self {
        RowSet { arity, rows: Default::default() }
    }

    /// The arity of the rows.
    pub fn arity(&self) -> u16 {
        self.arity
    }

    /// Adds `row`. The row's length is the set's arity.
    pub fn insert(&mut self, row: Row) -> bool {
        assert_eq!(row.len(), usize::from(self.arity), "a row of the set's arity");
        let rows = std::sync::Arc::make_mut(&mut self.rows);
        if (rows.count as usize + 1) * SLOTS_USED.1 > rows.slots.len() * SLOTS_USED.0 {
            rows.grow(row.len());
        }
        let at = rows.slot(&row);
        if rows.slots[at] != 0 {
            return false;
        }
        rows.values.extend_from_slice(&row);
        rows.count = rows.count.checked_add(1).expect("a set of fewer than 2^32 rows");
        rows.slots[at] = rows.count;
        true
    }

    /// Whether the set holds `row`.
    pub fn contains(&self, row: &[TermId]) -> bool {
        !self.rows.slots.is_empty() && row.len() == usize::from(self.arity) && self.rows.slots[self.rows.slot(row)] != 0
    }

    /// Each row of the set, in the order of their first insertion, which is
    /// an order of encodings and no order of the content.
    pub fn rows(&self) -> impl Iterator<Item = &[TermId]> + '_ {
        let arity = usize::from(self.arity);
        (0..self.rows.count).map(move |number| self.rows.row(number, arity))
    }

    /// The count of rows.
    pub fn len(&self) -> usize {
        self.rows.count as usize
    }

    /// Whether the set holds no row.
    pub fn is_empty(&self) -> bool {
        self.rows.count == 0
    }

    /// The heap bytes of the rows.
    pub fn bytes(&self) -> usize {
        self.rows.bytes()
    }

    /// Gives back the spare capacity of the rows, where no clone shares them.
    fn shrink(&mut self) {
        if let Some(rows) = std::sync::Arc::get_mut(&mut self.rows) {
            rows.values.shrink_to_fit();
        }
    }

    /// The identity of the rows this set shares with its clones: two sets
    /// with equal identities hold the same rows, so a count of bytes counts
    /// them once.
    pub fn shared(&self) -> SharedRows {
        SharedRows(std::sync::Arc::as_ptr(&self.rows) as usize)
    }

    /// Whether `other` holds its rows as this set does: the same rows in the
    /// same order, so that each read of either, and each set made from a
    /// clone of either by the same changes, gives the same rows in the same
    /// order.
    pub(crate) fn laid_out_as(&self, other: &RowSet) -> bool {
        std::sync::Arc::ptr_eq(&self.rows, &other.rows) || (self.arity == other.arity && self.rows.count == other.rows.count && self.rows.values == other.rows.values)
    }
}

/// The identity of the rows that the clones of a [`RowSet`] share, valid
/// while one of them is held.
#[derive(Clone, Copy, PartialEq, Eq, Hash, Debug)]
pub struct SharedRows(usize);

/// One part of a body's relation: the rows of one connected component of the
/// body's atoms, where two atoms are connected when they share a variable.
#[derive(Clone, Debug)]
pub struct RelationPart {
    /// The body's columns that the part holds, in the order of its rows.
    pub columns: Box<[ColumnIndex]>,
    pub rows: RowSet,
}

/// A relation: a set of rows of one arity, held as the product of its parts.
///
/// A fact relation, a lib relation's rows and an evaluated relation of one
/// part each hold one part. The rows are the product of the parts' rows, so
/// the count of rows is the product of the parts' counts, and the relation
/// is empty when any part is empty.
///
/// A relation is a value that can't be changed once [`Relation::from_parts`]
/// builds it, so each index it keeps holds its rows. A relation with other
/// rows is a new relation.
#[derive(Clone, Debug)]
pub struct Relation {
    arity: u16,
    parts: Box<[RelationPart]>,
    /// The indexes built so far, one per column order, each added on its
    /// first use and kept, shared by the clones of the relation.
    indexes: std::sync::Arc<std::sync::RwLock<StableHashMap<ColumnOrder, std::sync::Arc<Index>>>>,
    /// The bytes of the indexes built so far, shared by the clones of the
    /// relation.
    index_bytes: std::sync::Arc<std::sync::atomic::AtomicUsize>,
    /// The rows hash, computed on first use and shared by the clones of the
    /// relation.
    rows_hash: std::sync::Arc<std::sync::OnceLock<StableHash>>,
}

/// The identity of a relation's storage ([`Relation::shares_storage`]), which
/// keeps none of its rows or indexes.
#[derive(Clone, Debug)]
pub(crate) struct StorageTag(std::sync::Weak<std::sync::OnceLock<StableHash>>);

impl StorageTag {
    /// The bytes a tag keeps: its own, and the allocation of the rows hash
    /// that the tag points at, its two counts and the hash's cell, which
    /// stays until the tag goes, also after the last relation on that storage
    /// goes.
    pub(crate) const BYTES: usize =
        std::mem::size_of::<StorageTag>() + 2 * std::mem::size_of::<usize>() + std::mem::size_of::<std::sync::OnceLock<StableHash>>();

    /// Whether some relation still stands on this storage.
    pub(crate) fn live(&self) -> bool {
        self.0.strong_count() > 0
    }
}

impl Relation {
    /// Exact storage identity of immutable Relation clones. The OnceLock's
    /// owner is allocated only by from_parts and shared only by Clone;
    /// comparing its address neither computes nor compares a rows hash.
    pub(crate) fn shares_storage(&self, other: &Self) -> bool {
        std::sync::Arc::ptr_eq(&self.rows_hash, &other.rows_hash)
    }

    /// The tag of this relation's storage, which its clones share.
    pub(crate) fn storage_tag(&self) -> StorageTag {
        StorageTag(std::sync::Arc::downgrade(&self.rows_hash))
    }

    /// Whether `tag` is the tag of this relation's storage. A tag keeps its
    /// address from being given to any later relation, so an equal address
    /// is the same storage, and so the same rows.
    pub(crate) fn has_storage(&self, tag: &StorageTag) -> bool {
        std::ptr::eq(std::sync::Arc::as_ptr(&self.rows_hash), tag.0.as_ptr())
    }

    /// The relation that `parts` hold. The parts' columns are disjoint and
    /// cover `0..arity`.
    pub fn from_parts(arity: u16, parts: Box<[RelationPart]>) -> Self {
        let mut covered = vec![false; usize::from(arity)];
        for part in &parts {
            assert_eq!(part.columns.len(), usize::from(part.rows.arity()), "a part's rows hold its columns");
            for column in &part.columns {
                let seen = covered.get_mut(usize::from(column.0)).expect("a column within the arity");
                assert!(!std::mem::replace(seen, true), "parts with disjoint columns");
            }
        }
        assert!(covered.iter().all(|&c| c), "parts that cover every column");
        let mut parts = parts;
        parts.iter_mut().for_each(|part| part.rows.shrink());
        Relation { arity, parts, indexes: Default::default(), index_bytes: Default::default(), rows_hash: Default::default() }
    }

    /// The hash of the relation's rows, which depends on its rows alone: no order
    /// of its rows, and no split of its columns into parts. Each row hashes as
    /// the product, modulo `MODULUS`, of a hash of each of its values at its
    /// column, and the relation as the sum of its rows' hashes. Since a row of
    /// the product of parts hashes as the product of its parts' rows' hashes,
    /// that sum is the product of each part's sum, which reads each part's rows
    /// once.
    pub fn rows_hash(&self) -> StableHash {
        *self.rows_hash.get_or_init(|| {
            let sum = self.parts().iter().fold(1u64, |product, part| {
                let rows = part.rows.rows().fold(0u64, |sum, row| {
                    let hash = part.columns.iter().zip(row).fold(1u64, |hash, (column, value)| times(hash, value_hash(column.0, value.encoding())));
                    (sum + hash) % MODULUS
                });
                times(product, rows)
            });
            let mut hasher = StableHasher::new();
            std::hash::Hash::hash(&(self.arity(), sum), &mut hasher);
            hasher.finish128()
        })
    }

    /// The arity of the rows.
    pub fn arity(&self) -> u16 {
        self.arity
    }

    /// The parts, whose product is the relation's rows.
    pub fn parts(&self) -> &[RelationPart] {
        &self.parts
    }

    /// Whether `other` holds its rows as this relation does: parts of the
    /// same columns, each with its rows laid out as this one's
    /// ([`RowSet::laid_out_as`]).
    pub(crate) fn laid_out_as(&self, other: &Relation) -> bool {
        self.arity == other.arity
            && self.parts.len() == other.parts.len()
            && self.parts.iter().zip(other.parts.iter()).all(|(a, b)| a.columns == b.columns && a.rows.laid_out_as(&b.rows))
    }

    /// The count of rows, the product of the parts' counts, `u64::MAX` where
    /// the product passes it.
    pub fn len(&self) -> u64 {
        self.parts.iter().fold(1, |count: u64, part| count.saturating_mul(part.rows.len() as u64))
    }

    /// Whether the relation holds no row: some part is empty.
    pub fn is_empty(&self) -> bool {
        self.parts.iter().any(|part| part.rows.is_empty())
    }

    /// The count of indexes built so far and their bytes, an estimate from
    /// the capacity of each level's hash table.
    pub fn index_bytes(&self) -> (usize, usize) {
        (self.indexes.read().expect(UNPOISONED).len(), self.index_bytes.load(std::sync::atomic::Ordering::Relaxed))
    }

    /// Drops the indexes built so far, in the clones of the relation too. An
    /// index that an evaluation holds lives until that evaluation ends, and
    /// the next read of an order builds its index again.
    pub fn drop_indexes(&self) {
        self.indexes.write().expect(UNPOISONED).clear();
        self.index_bytes.store(0, std::sync::atomic::Ordering::Relaxed);
    }

    /// The index of the relation in `order`, built on first use and kept
    /// with the relation.
    pub fn index(&self, order: &ColumnOrder) -> std::sync::Arc<Index> {
        if let Some(index) = self.indexes.read().expect(UNPOISONED).get(order) {
            return index.clone();
        }
        let mut indexes = self.indexes.write().expect(UNPOISONED);
        indexes
            .entry(order.clone())
            .or_insert_with(|| {
                let index = self.build_index(order);
                self.index_bytes.fetch_add(index.bytes(), std::sync::atomic::Ordering::Relaxed);
                std::sync::Arc::new(index)
            })
            .clone()
    }

    /// The index of the relation in `order`. It reads the parts that hold a
    /// column of `order` and no other. Where several parts do, it reads
    /// each part that holds a column outside `order` by its distinct
    /// projections onto the columns of `order`, so the walk takes one step
    /// for each combination of them.
    ///
    fn build_index(&self, order: &ColumnOrder) -> Index {
        for column in &order.0 {
            assert!(column.0 < self.arity, "an order of the relation's columns");
        }
        if self.is_empty() || order.0.is_empty() {
            return Index::default();
        }
        let read: Vec<&RelationPart> = self.parts.iter().filter(|part| part.columns.iter().any(|column| order.0.contains(column))).collect();
        let walked: Vec<WalkedPart> = match read[..] {
            [only] => vec![WalkedPart { columns: only.columns.clone(), rows: WalkedRows::All(&only.rows) }],
            _ => read.iter().map(|part| WalkedPart::new(part, order)).collect(),
        };
        let mut flat: Vec<TermId> = Vec::new();
        let mut row = vec![TermId::from_encoding(0); usize::from(self.arity)];
        Self::each_row(&walked, &mut row, &mut |row| {
            flat.extend(order.0.iter().map(|column| row[usize::from(column.0)]));
        });
        Index::from_rows(&flat, order.0.len())
    }

    /// Calls `visit` on each combination of a row of each of `parts`, the
    /// first part outermost, with the columns of `parts` as `row` holds them.
    fn each_row(parts: &[WalkedPart], row: &mut [TermId], visit: &mut impl FnMut(&[TermId])) {
        let Some((this, rest)) = parts.split_first() else {
            visit(row);
            return;
        };
        this.rows.each(|part_row| {
            for (column, &value) in this.columns.iter().zip(part_row) {
                row[usize::from(column.0)] = value;
            }
            Self::each_row(rest, row, visit);
        });
    }
}

/// A part of a relation as the build of an index walks it: the columns that
/// its rows give, and the rows.
struct WalkedPart<'a> {
    columns: Box<[ColumnIndex]>,
    rows: WalkedRows<'a>,
}

impl<'a> WalkedPart<'a> {
    /// The part's rows, where each of its columns is in `order`, and its
    /// distinct projections onto the columns of `order` otherwise, in the
    /// order in which they first occur among its rows.
    fn new(part: &'a RelationPart, order: &ColumnOrder) -> Self {
        if part.columns.iter().all(|column| order.0.contains(column)) {
            return WalkedPart { columns: part.columns.clone(), rows: WalkedRows::All(&part.rows) };
        }
        let held: Vec<usize> = (0..part.columns.len()).filter(|&at| order.0.contains(&part.columns[at])).collect();
        let mut seen: StableHashSet<Row> = StableHashSet::default();
        let mut projections: Vec<Row> = Vec::new();
        for part_row in part.rows.rows() {
            let projection: Row = held.iter().map(|&at| part_row[at]).collect();
            if seen.insert(projection.clone()) {
                projections.push(projection);
            }
        }
        WalkedPart { columns: held.iter().map(|&at| part.columns[at]).collect(), rows: WalkedRows::Projected(projections) }
    }
}

/// The rows of a [`WalkedPart`].
enum WalkedRows<'a> {
    /// Each row of a part.
    All(&'a RowSet),
    /// Projections of a part's rows, each once.
    Projected(Vec<Row>),
}

impl WalkedRows<'_> {
    /// Calls `visit` on each row, in the order that [`RowSet::rows`] gives
    /// for `All` and in the order of the list for `Projected`.
    fn each(&self, mut visit: impl FnMut(&[TermId])) {
        match self {
            WalkedRows::All(rows) => rows.rows().for_each(visit),
            WalkedRows::Projected(rows) => rows.iter().for_each(|row| visit(row)),
        }
    }
}

const UNPOISONED: &str = "an index lock that no panic of a builder poisoned";

/// An order of a relation's columns, in which an [`Index`] is built: the
/// order that a clause's variable order asks for.
#[derive(Clone, PartialEq, Eq, Hash, Debug)]
pub struct ColumnOrder(pub Box<[ColumnIndex]>);

/// A trie over a relation's columns in one [`ColumnOrder`], as sorted arrays
/// with one level per column: a node of a level is a run of that level's
/// keys, ascending by encoding, and a key's subtrie is a run of the next
/// level's keys. A lookup is a binary search of a run.
#[derive(Debug, Default)]
pub struct Index {
    levels: Box<[Level]>,
}

#[derive(Debug, Default)]
struct Level {
    /// The keys of the level's nodes, node after node.
    keys: Box<[TermId]>,
    /// For each key, the end of its subtrie in the next level's keys, which
    /// the end for the key before it starts. The last level holds none.
    ends: Box<[u32]>,
}

impl Index {
    /// The trie of the rows of `flat`, each `width` values long and in the
    /// index's column order.
    fn from_rows(flat: &[TermId], width: usize) -> Index {
        let count = flat.len() / width;
        let row = |at: u32| &flat[at as usize * width..(at as usize + 1) * width];
        let mut sorted: Vec<u32> = (0..u32::try_from(count).expect("an index of fewer than 2^32 rows")).collect();
        sorted.sort_unstable_by(|&a, &b| row(a).iter().map(|v| v.encoding()).cmp(row(b).iter().map(|v| v.encoding())));
        let mut keys: Vec<Vec<TermId>> = vec![Vec::new(); width];
        let mut ends: Vec<Vec<u32>> = vec![Vec::new(); width - 1];
        let mut previous: Option<&[TermId]> = None;
        for &at in &sorted {
            let this = row(at);
            let first = previous.map_or(Some(0), |previous| (0..width).find(|&column| previous[column] != this[column]));
            previous = Some(this);
            let Some(first) = first else { continue };
            for column in first..width {
                keys[column].push(this[column]);
                if column + 1 < width {
                    ends[column].push(0);
                }
            }
            for column in first.saturating_sub(1)..width - 1 {
                *ends[column].last_mut().expect("a key at each level above the new key") = u32::try_from(keys[column + 1].len()).expect("an index of fewer than 2^32 keys");
            }
        }
        ends.push(Vec::new());
        Index { levels: keys.into_iter().zip(ends).map(|(keys, ends)| Level { keys: keys.into(), ends: ends.into() }).collect() }
    }

    /// The heap bytes of the trie.
    fn bytes(&self) -> usize {
        let levels = self.levels.len() * std::mem::size_of::<Level>();
        levels + self.levels.iter().map(|level| level.keys.len() * std::mem::size_of::<TermId>() + level.ends.len() * 4).sum::<usize>()
    }

    /// The root of the trie.
    pub fn root(&self) -> IndexNode<'_> {
        IndexNode { index: self, depth: 0, start: 0, end: self.levels.first().map_or(0, |level| level.keys.len()) }
    }
}

/// A node of an [`Index`]: the run of keys of one level.
#[derive(Clone, Copy, Debug)]
pub struct IndexNode<'i> {
    index: &'i Index,
    depth: usize,
    start: usize,
    end: usize,
}

impl<'i> IndexNode<'i> {
    /// The subtrie of the key at `at`.
    fn below(self, at: usize) -> IndexNode<'i> {
        let ends = &self.index.levels[self.depth].ends;
        let (start, end) = match ends.is_empty() {
            true => (0, 0),
            false => (at.checked_sub(1).map_or(0, |before| ends[before] as usize), ends[at] as usize),
        };
        IndexNode { index: self.index, depth: self.depth + 1, start, end }
    }

    /// The subtrie at `value` of the first column, or `None` where no row
    /// holds it.
    pub fn child(self, value: TermId) -> Option<IndexNode<'i>> {
        let keys = &self.index.levels.get(self.depth)?.keys[self.start..self.end];
        let at = keys.binary_search_by_key(&value.encoding(), |key| key.encoding()).ok()?;
        Some(self.below(self.start + at))
    }

    /// Each value at this level, with its subtrie, for a join that walks
    /// the level, ascending by encoding.
    pub fn entries(self) -> impl Iterator<Item = (TermId, IndexNode<'i>)> {
        (self.start..self.end).map(move |at| (self.index.levels[self.depth].keys[at], self.below(at)))
    }

    /// The count of values at this level.
    pub fn len(self) -> usize {
        self.end - self.start
    }

    /// Whether no value stands at this level.
    pub fn is_empty(self) -> bool {
        self.start == self.end
    }
}

/// The modulus of the rows hash, the Mersenne prime 2^61 - 1.
const MODULUS: u64 = (1 << 61) - 1;

/// The hash of `value` at `column`, in `1..MODULUS`.
fn value_hash(column: u16, value: u32) -> u64 {
    let mut hasher = StableHasher::new();
    std::hash::Hash::hash(&(column, value), &mut hasher);
    1 + (hasher.finish128().0 as u64) % (MODULUS - 1)
}

fn times(a: u64, b: u64) -> u64 {
    ((u128::from(a) * u128::from(b)) % u128::from(MODULUS)) as u64
}
