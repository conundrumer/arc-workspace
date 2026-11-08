//! Rows, relations and their indexes.
//!
//! A relation is a set of rows of one arity. A body's relation is held as
//! its parts, each stored row after row in one array with a hash table of
//! row numbers and hashes over it. An index is a trie over the columns in one order, as
//! sorted arrays, built on first use in the order that a clause's variable
//! order asks for, and kept with the relation.
//!
//! A relation is a set: each function here that gives its rows gives them
//! in an order of encodings and no order of the content.

use crate::hash::{StableHash, StableHashMap, StableHashSet, StableHasher};
use crate::terms::TermId;

/// A row: a fixed-arity array of term ids, with no type tag.
pub type Row = Box<[TermId]>;

/// The order of two rows of one arity by their encodings, column by column.
/// Where Ident numbers are the same in every run, so is this order; it is no
/// order of the content.
pub fn encoding_order(a: &[TermId], b: &[TermId]) -> std::cmp::Ordering {
    a.iter().map(|id| id.encoding()).cmp(b.iter().map(|id| id.encoding()))
}

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
///
/// The table is a lookup over `values` and no part of the rows' content: the
/// rows, and their order, are `values` and `count` alone. A row's number is
/// where `values` puts it, which the first insertion of the row decides, so
/// no layout of the table changes which rows the set holds or the order that
/// [`RowSet::rows`] gives them in.
#[derive(Clone, Debug, Default)]
struct Rows {
    /// The values of the rows, row after row.
    values: Vec<TermId>,
    count: u32,
    /// An open-addressing table, 0 in an empty slot. A slot in use holds the
    /// row's [`row_hash`] in its upper 32 bits and 1 + the row's number in its
    /// lower 32 bits, so a probe of a slot that holds another row ends at the
    /// compare of two hashes in the table, with no read of `values`, unless
    /// the hashes are equal. Its length is 0 or a power of two.
    slots: Box<[u64]>,
}

/// The largest share of a [`Rows`] table's slots in use, as a fraction. A
/// probe that passes a slot of another row reads one 8-byte slot of a run that
/// the table holds side by side, so a longer run of probes costs far less than
/// a read of `values` for each. At three quarters, a row not in the table takes
/// about 8.5 probes, and the table holds 11 to 21 bytes for each row.
const SLOTS_USED: (usize, usize) = (3, 4);

/// The hash of `row`. Two equal rows have equal hashes.
fn row_hash(row: &[TermId]) -> u32 {
    let mut hash = 0x9E37_79B9_7F4A_7C15_u64;
    for value in row {
        hash = (hash.rotate_left(5) ^ u64::from(value.encoding())).wrapping_mul(0x517C_C1B7_2722_0A95);
    }
    (hash ^ (hash >> 32)) as u32
}

/// The slot entry of the row `number`, whose hash is `hash`.
fn entry(hash: u32, number: u32) -> u64 {
    u64::from(hash) << 32 | u64::from(number + 1)
}

/// Puts `entry` in the first empty slot of its probe, with no check of the
/// rows the table holds. The table has an empty slot.
fn place(slots: &mut [u64], entry: u64) {
    let mask = slots.len() - 1;
    let mut at = (entry >> 32) as usize & mask;
    while slots[at] != 0 {
        at = (at + 1) & mask;
    }
    slots[at] = entry;
}

impl Rows {
    fn row(&self, number: u32, arity: usize) -> &[TermId] {
        &self.values[number as usize * arity..(number as usize + 1) * arity]
    }

    /// The slot that holds `row`, whose hash is `hash`, or the empty slot
    /// where it would go. The table has an empty slot.
    ///
    /// A slot of the row has the row's hash, so a slot with another hash holds
    /// another row, and the probe passes it with no compare of rows. A slot
    /// with the same hash holds the row or another row of that hash, which the
    /// compare of rows tells. So the slot found is the one that a probe that
    /// compares every row finds.
    fn slot(&self, row: &[TermId], hash: u32) -> usize {
        let mask = self.slots.len() - 1;
        let mut at = hash as usize & mask;
        loop {
            let slot = self.slots[at];
            if slot == 0 || ((slot >> 32) as u32 == hash && self.row(slot as u32 - 1, row.len()) == row) {
                return at;
            }
            at = (at + 1) & mask;
        }
    }

    /// Doubles the table, or builds it where the rows came without one. The
    /// rows are distinct, so each takes the first empty slot of its probe
    /// with no compare of rows, and a row's slot keeps its hash, so a table
    /// that has slots reads no row to grow.
    fn grow(&mut self, arity: usize) {
        // Rows that came without a table have a table of their count on the first row added.
        let least = (((self.count as usize + 1) * SLOTS_USED.1 / SLOTS_USED.0) + 1).next_power_of_two();
        let old = std::mem::take(&mut self.slots);
        let mut slots = vec![0; (old.len() * 2).max(8).max(least)].into_boxed_slice();
        if old.is_empty() {
            for number in 0..self.count {
                place(&mut slots, entry(row_hash(self.row(number, arity)), number));
            }
        } else {
            for &held in old.iter().filter(|&&held| held != 0) {
                place(&mut slots, held);
            }
        }
        self.slots = slots;
    }

    fn bytes(&self) -> usize {
        self.values.capacity() * std::mem::size_of::<TermId>() + self.slots.len() * std::mem::size_of::<u64>()
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

    /// The set of the rows of `values`, row after row, which differ from each
    /// other. It builds no table over them until a row is added.
    pub fn of_distinct(arity: u16, values: Vec<TermId>) -> Self {
        let count = values.len().checked_div(usize::from(arity)).unwrap_or(0);
        RowSet { arity, rows: std::sync::Arc::new(Rows { values, count: u32::try_from(count).expect("a set of fewer than 2^32 rows"), slots: Box::default() }) }
    }

    /// The row at `number` in the order of [`RowSet::rows`].
    pub fn row(&self, number: usize) -> &[TermId] {
        self.rows.row(number as u32, usize::from(self.arity))
    }

    /// Adds `row`, and tells whether the set did not hold it. The row's length
    /// is the set's arity.
    pub fn insert(&mut self, row: Row) -> bool {
        self.insert_slice(&row)
    }

    /// As [`RowSet::insert`], from a slice, which takes no allocation for the
    /// row. The set copies the values of a row it adds into its one array, so
    /// the rows it holds, and their order, are those that [`RowSet::insert`]
    /// of a box of the same values gives.
    pub fn insert_slice(&mut self, row: &[TermId]) -> bool {
        assert_eq!(row.len(), usize::from(self.arity), "a row of the set's arity");
        let rows = std::sync::Arc::make_mut(&mut self.rows);
        if (rows.count as usize + 1) * SLOTS_USED.1 > rows.slots.len() * SLOTS_USED.0 {
            rows.grow(row.len());
        }
        let hash = row_hash(row);
        let at = rows.slot(row, hash);
        if rows.slots[at] != 0 {
            return false;
        }
        rows.values.extend_from_slice(row);
        rows.count = rows.count.checked_add(1).expect("a set of fewer than 2^32 rows");
        rows.slots[at] = entry(hash, rows.count - 1);
        true
    }

    /// Whether the set holds `row`.
    pub fn contains(&self, row: &[TermId]) -> bool {
        if row.len() != usize::from(self.arity) {
            return false;
        }
        if self.rows.slots.is_empty() {
            return self.rows().any(|held| held == row);
        }
        self.rows.slots[self.rows.slot(row, row_hash(row))] != 0
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

    /// The relation that `parts` hold, whose [`Relation::rows_hash`] is `hash`.
    pub(crate) fn from_parts_hashed(arity: u16, parts: Box<[RelationPart]>, hash: StableHash) -> Self {
        let relation = Self::from_parts(arity, parts);
        relation.rows_hash.set(hash).expect("a new relation holds no hash");
        relation
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
                let rows = part.rows.rows().fold(0u64, |sum, row| hash_plus(sum, row_hash_at(&part.columns, row)));
                hash_times(product, rows)
            });
            rows_hash_of(self.arity(), sum)
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
        self.index_built(order).0
    }

    /// [`Relation::index`], and the rows that this call walked to build the
    /// index: none where the relation held the index already. A build walks
    /// the rows of each part that holds a column of `order`, or, where it reads
    /// several parts, as many as [`Relation::index_work`] gives.
    pub fn index_built(&self, order: &ColumnOrder) -> (std::sync::Arc<Index>, u64) {
        if let Some(index) = self.indexes.read().expect(UNPOISONED).get(order) {
            return (index.clone(), 0);
        }
        let mut indexes = self.indexes.write().expect(UNPOISONED);
        let mut walked = 0;
        let index = indexes
            .entry(order.clone())
            .or_insert_with(|| {
                let mut index = self.build_index(order);
                self.index_bytes.fetch_add(index.bytes(), std::sync::atomic::Ordering::Relaxed);
                walked = match self.index_work(order) {
                    0 => self.parts.iter().filter(|part| part.columns.iter().any(|column| order.0.contains(column))).map(|part| part.rows.len() as u64).sum(),
                    work => work,
                };
                index.walked = walked;
                std::sync::Arc::new(index)
            })
            .clone();
        (index, walked)
    }

    /// The Cartesian bindings traversed to build an index. Unread factors
    /// contribute no work. A projected factor contributes its distinct
    /// projections, as `build_index` traverses them. A single factor needs
    /// no Cartesian expansion, like a flat relation.
    pub fn index_work(&self, order: &ColumnOrder) -> u64 {
        if self.is_empty() || order.0.is_empty() { return 0; }
        let read: Vec<&RelationPart> = self.parts.iter().filter(|part|part.columns.iter().any(|column|order.0.contains(column))).collect();
        if read.len() < 2 { return 0; }
        read.iter().map(|part|match WalkedPart::new(part,order).rows {
            WalkedRows::All(rows)=>rows.len() as u64,
            WalkedRows::Projected(rows)=>rows.len() as u64,
        }).fold(1,u64::saturating_mul)
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
    /// The rows that the build of the index walked, as [`Relation::index_built`]
    /// counts them.
    walked: u64,
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
    /// The rows that the build of this index walked. A use of the index counts
    /// them whether or not an earlier use built it, so the count of a use does
    /// not depend on what an earlier use built.
    pub fn walked(&self) -> u64 {
        self.walked
    }

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
        Index { levels: keys.into_iter().zip(ends).map(|(keys, ends)| Level { keys: keys.into(), ends: ends.into() }).collect(), walked: 0 }
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
    /// The distinct values at this level, in encoding order. A join can
    /// intersect these runs before creating bindings or moving child cursors.
    pub fn values(self) -> &'i [TermId] {
        let Some(level) = self.index.levels.get(self.depth) else { return &[] };
        &level.keys[self.start..self.end]
    }

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

/// The hash of `row`, a row of a part that holds `columns`, in the sum that
/// [`Relation::rows_hash`] takes.
///
/// The product starts at the first value's hash, which is the product of 1
/// and that hash, since a value's hash is under `MODULUS`. A row of no
/// columns hashes as 1.
pub(crate) fn row_hash_at(columns: &[ColumnIndex], row: &[TermId]) -> u64 {
    let mut values = columns.iter().zip(row).map(|(column, value)| value_hash(column.0, value.encoding()));
    let Some(first) = values.next() else { return 1 };
    values.fold(first, hash_times)
}

/// The rows hash of a relation of `arity` columns from the product of the sums of its parts.
pub(crate) fn rows_hash_of(arity: u16, product: u64) -> StableHash {
    let mut hasher = StableHasher::new();
    std::hash::Hash::hash(&(arity, product), &mut hasher);
    hasher.finish128()
}

/// The sum of two hashes in the sum that [`Relation::rows_hash`] takes.
///
/// It is `(a + b) % MODULUS` for each `a + b` that fits in 64 bits. Since
/// 2^61 is 1 modulo `MODULUS`, a number is equal modulo `MODULUS` to the sum
/// of its low 61 bits and the rest of its bits. For a sum under 2^64 that
/// takes at most `MODULUS + 7`, which is under twice `MODULUS`, so at most one
/// subtraction of `MODULUS` is left.
pub(crate) fn hash_plus(a: u64, b: u64) -> u64 {
    let folded = fold(a + b);
    if folded >= MODULUS { folded - MODULUS } else { folded }
}

/// The sum of the low 61 bits of `x` and the rest of its bits, which is equal
/// to `x` modulo `MODULUS`, since 2^61 is 1 modulo `MODULUS`.
fn fold(x: u64) -> u64 {
    (x & MODULUS) + (x >> 61)
}

/// The hash of `value` at `column`, in `1..MODULUS`.
pub(crate) fn value_hash(column: u16, value: u32) -> u64 {
    let mut hasher = StableHasher::new();
    std::hash::Hash::hash(&(column, value), &mut hasher);
    1 + (hasher.finish128().0 as u64) % (MODULUS - 1)
}

/// The product of two hashes in the sum that [`Relation::rows_hash`] takes.
///
/// It is `a * b % MODULUS` for each `a` and `b`, with no division, which a
/// 128-bit remainder takes as a call. The product is under 2^128. One fold of
/// it ([`fold`] on 128 bits) gives a number under 2^61 + 2^67, a second gives
/// at most `MODULUS + 65`, which is under twice `MODULUS`, so at most one
/// subtraction of `MODULUS` is left.
pub(crate) fn hash_times(a: u64, b: u64) -> u64 {
    const WIDE: u128 = MODULUS as u128;
    let product = u128::from(a) * u128::from(b);
    let once = (product & WIDE) + (product >> 61);
    let twice = ((once & WIDE) + (once >> 61)) as u64;
    if twice >= MODULUS { twice - MODULUS } else { twice }
}
