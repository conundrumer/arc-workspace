//! Rows, relations and their indexes.
//!
//! A relation is a set of rows of one arity. A body's relation is held as
//! its parts, each stored row by row with a hash set over the rows. An index
//! is a trie over the columns in one order, built on first use in the order
//! that a clause's variable order asks for, and kept with the relation.
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

/// A set of rows of one arity, stored row by row with a hash set over the
/// rows. Its clones share its rows until one of them takes a row.
#[derive(Clone, Debug, Default)]
pub struct RowSet {
    arity: u16,
    rows: std::sync::Arc<StableHashSet<Row>>,
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
        std::sync::Arc::make_mut(&mut self.rows).insert(row)
    }

    /// Whether the set holds `row`.
    pub fn contains(&self, row: &[TermId]) -> bool {
        self.rows.contains(row)
    }

    /// Each row of the set, in an order of encodings and no order of the
    /// content.
    pub fn rows(&self) -> impl Iterator<Item = &[TermId]> + '_ {
        self.rows.iter().map(|row| &**row)
    }

    /// The count of rows.
    pub fn len(&self) -> usize {
        self.rows.len()
    }

    /// Whether the set holds no row.
    pub fn is_empty(&self) -> bool {
        self.rows.is_empty()
    }

    /// The identity of the rows this set shares with its clones: two sets
    /// with equal identities hold the same rows, so a count of bytes counts
    /// them once.
    pub fn shared(&self) -> SharedRows {
        SharedRows(std::sync::Arc::as_ptr(&self.rows) as usize)
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
    /// The rows hash, computed on first use and shared by the clones of the
    /// relation.
    rows_hash: std::sync::Arc<std::sync::OnceLock<StableHash>>,
}

impl Relation {
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
        Relation { arity, parts, indexes: Default::default(), rows_hash: Default::default() }
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

    /// The count of rows, the product of the parts' counts, `u64::MAX` where
    /// the product passes it.
    pub fn len(&self) -> u64 {
        self.parts.iter().fold(1, |count: u64, part| count.saturating_mul(part.rows.len() as u64))
    }

    /// Whether the relation holds no row: some part is empty.
    pub fn is_empty(&self) -> bool {
        self.parts.iter().any(|part| part.rows.is_empty())
    }

    /// The index of the relation in `order`, built on first use and kept
    /// with the relation.
    pub fn index(&self, order: &ColumnOrder) -> std::sync::Arc<Index> {
        if let Some(index) = self.indexes.read().expect(UNPOISONED).get(order) {
            return index.clone();
        }
        let mut indexes = self.indexes.write().expect(UNPOISONED);
        indexes.entry(order.clone()).or_insert_with(|| std::sync::Arc::new(self.build_index(order))).clone()
    }

    /// The index of the relation in `order`. It reads the parts that hold a
    /// column of `order` and no other. Where several parts do, it reads
    /// each part that holds a column outside `order` by its distinct
    /// projections onto the columns of `order`, so the walk takes one step
    /// for each combination of them.
    ///
    /// Each level of the index holds its keys in the order of their first
    /// insertion. A key of `order` first occurs in the walk of the product of
    /// all parts where each part that holds no column of `order` stands at
    /// its first row and each read part stands at its first row with that
    /// key's projection. So the walk of the read parts' first projections
    /// inserts the keys in the order in which the walk of all parts first
    /// inserts them.
    fn build_index(&self, order: &ColumnOrder) -> Index {
        for column in &order.0 {
            assert!(column.0 < self.arity, "an order of the relation's columns");
        }
        let mut index = Index::default();
        if self.is_empty() {
            return index;
        }
        let read: Vec<&RelationPart> = self.parts.iter().filter(|part| part.columns.iter().any(|column| order.0.contains(column))).collect();
        let walked: Vec<WalkedPart> = match read[..] {
            [only] => vec![WalkedPart { columns: only.columns.clone(), rows: WalkedRows::All(&only.rows) }],
            _ => read.iter().map(|part| WalkedPart::new(part, order)).collect(),
        };
        let mut row = vec![TermId::from_encoding(0); usize::from(self.arity)];
        Self::each_row(&walked, &mut row, &mut |row| {
            let mut level = &mut index;
            for column in &order.0 {
                level = level.children.entry(row[usize::from(column.0)]).or_default();
            }
        });
        index
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

/// A trie over a relation's columns in one [`ColumnOrder`], as a hash trie of
/// Free Join (<https://arxiv.org/abs/2301.10841>) is: each level maps a value
/// of its column to the trie of the rows that hold it.
#[derive(Debug, Default)]
pub struct Index {
    children: StableHashMap<TermId, Index>,
}

impl Index {
    /// The subtrie at `value` of the first column, or `None` where no row
    /// holds it.
    pub fn child(&self, value: TermId) -> Option<&Index> {
        self.children.get(&value)
    }

    /// Each value at this level, with its subtrie, for a join that walks
    /// the level, in an order of encodings and no order of the content.
    pub fn entries(&self) -> impl Iterator<Item = (TermId, &Index)> + '_ {
        self.children.iter().map(|(&value, child)| (value, child))
    }

    /// The count of values at this level.
    pub fn len(&self) -> usize {
        self.children.len()
    }

    /// Whether no value stands at this level.
    pub fn is_empty(&self) -> bool {
        self.children.is_empty()
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
