//! The operators of the grammar over materialized rows: a faster evaluation of
//! what an expression's forms compute, which `walk` checks against those forms
//! through the engine's evaluator.
//!
//! A value is a product of parts, as the engine's relations are, so a `join` with
//! no column pair costs nothing, and an operator merges only the parts it reads.
//! An empty relation has no parts to read, and each operator states what it gives
//! on one: most give an empty relation, `antijoin` with an empty right side gives
//! its left, and a component runs on its empty input.
//!
//! The rows of `inside` stand as their boxes ([`Val::Boxes`]), and the rows of a `join` as the tables it joins ([`Val::Joined`]), until an operator needs the rows themselves.

use std::hash::Hasher;
use std::sync::Arc;

use arclog::algebra::Algebra;
use arclog::eval::instance::{Construction, ConstructionContext, GroupInputs};
use arclog::eval::join::Budget;
use arclog::eval::{Cancellation, Limits};
use arclog::registry::Registry;
use arclog::relations::RowSet;
use arclog::session::TaskSession;
use arclog::terms::{Constant, Term, TermId};
use arclog::types::ValueType;

use crate::bounds::Bound;
use crate::columns::Columns;
use crate::expression::Op;

pub type Cell = u32;

/// The most cells that a materialized table holds; a larger one stops, which
/// gives no value.
pub const CELL_CAP: usize = 1 << 21;

/// A hasher for keys that are already well mixed or small.
#[derive(Default, Clone, Copy)]
pub struct FastHasher(u64);

impl FastHasher {
    /// A hasher whose state is `start` before any write.
    pub fn starting_at(start: u64) -> FastHasher {
        FastHasher(start)
    }
}

impl Hasher for FastHasher {
    fn finish(&self) -> u64 {
        self.0
    }
    fn write(&mut self, bytes: &[u8]) {
        for chunk in bytes.chunks(8) {
            let mut word = [0u8; 8];
            word[..chunk.len()].copy_from_slice(chunk);
            self.write_u64(u64::from_le_bytes(word));
        }
    }
    fn write_u32(&mut self, value: u32) {
        self.write_u64(u64::from(value));
    }
    fn write_u64(&mut self, value: u64) {
        self.0 = (self.0.rotate_left(5) ^ value).wrapping_mul(0x517c_c1b7_2722_0a95);
    }
    fn write_u128(&mut self, value: u128) {
        self.write_u64(value as u64);
        self.write_u64((value >> 64) as u64);
    }
    fn write_usize(&mut self, value: usize) {
        self.write_u64(value as u64);
    }
    fn write_u8(&mut self, value: u8) {
        self.write_u64(u64::from(value));
    }
    fn write_u16(&mut self, value: u16) {
        self.write_u64(u64::from(value));
    }
}

/// The map of lookups by the fast hasher. It cannot be iterated; see [`crate::lookup`].
pub type FastMap<K, V> = crate::lookup::LookupMap<K, V>;

/// A 128-bit hash of a sequence of words.
pub fn hash_words(words: impl IntoIterator<Item = u64>) -> u128 {
    let mut a = 0x9e37_79b9_7f4a_7c15u64;
    let mut b = 0xc2b2_ae3d_27d4_eb4fu64;
    for word in words {
        a = (a ^ word).wrapping_mul(0xff51_afd7_ed55_8ccd);
        a ^= a >> 29;
        b = b.wrapping_add(word).wrapping_mul(0xc4ce_b9fe_1a85_ec53);
        b ^= b >> 31;
    }
    (u128::from(a) << 64) | u128::from(b ^ a.rotate_left(17))
}

fn hash_row(row: &[Cell]) -> u128 {
    hash_words(row.iter().map(|cell| u64::from(*cell)))
}

fn next_table_id() -> u64 {
    static NEXT: std::sync::atomic::AtomicU64 = std::sync::atomic::AtomicU64::new(0);
    NEXT.fetch_add(1, std::sync::atomic::Ordering::Relaxed)
}

/// A set of rows of one arity. Its hash depends on the set alone.
#[derive(Debug)]
pub struct Table {
    pub arity: usize,
    pub len: usize,
    pub cells: Box<[Cell]>,
    /// Its hash, once something has read it. A term that counts rows never does.
    hash: std::sync::OnceLock<u128>,
    /// Which table this is, of all a process makes, since two tables of one hash can hold their rows in two orders.
    pub id: u64,
    /// For each column, a 64-bit filter of its values: two columns whose filters
    /// share no bit share no value.
    masks: std::sync::OnceLock<Box<[u64]>>,
    /// For each column, how it groups the rows, once something has read it.
    groupings: std::sync::OnceLock<Box<[std::sync::OnceLock<Arc<Grouping>>]>>,
    /// For each column, its distinct values in order, once something has read it.
    sorted: std::sync::OnceLock<Box<[std::sync::OnceLock<Arc<[Cell]>>]>>,
    /// Its finest split into groups of columns whose product it is, once something has read it.
    factors: std::sync::OnceLock<Arc<Factors>>,
}

/// A table's finest split into groups of columns whose product it is: for each column the place of its group, and for each group the number of distinct rows of its columns.
pub type Factors = (Vec<u8>, Vec<u64>);

/// How keys group a table's rows: the dense id of each row's key in order of first appearance, and the place of the first row at each key.
pub type Grouping = (Vec<u32>, Vec<u32>);

thread_local! {
    static SLOTS: std::cell::RefCell<Vec<u64>> = const { std::cell::RefCell::new(Vec::new()) };
}

/// The ids of `keys` in order of first appearance, and the place of the first appearance of each id. Where the keys span a range of at most `range` values from `least`, an array stands in for a hash table.
pub fn first_ids(keys: &[u64], least: u64, range: u64) -> Grouping {
    let len = keys.len();
    let mut ids: Vec<u32> = Vec::with_capacity(len);
    let mut first: Vec<u32> = Vec::new();
    const EMPTY: u64 = u64::MAX;
    SLOTS.with(|slots| {
        let mut slots = slots.borrow_mut();
        if range <= (4 * len as u64).max(64) {
            // Each slot holds the id of a key, or EMPTY.
            slots.clear();
            slots.resize(range as usize, EMPTY);
            for (place, key) in keys.iter().enumerate() {
                let slot = &mut slots[(*key - least) as usize];
                if *slot == EMPTY {
                    *slot = first.len() as u64;
                    first.push(place as u32);
                }
                ids.push(*slot as u32);
            }
        } else {
            // Each slot holds a key, then its id, in two words.
            let capacity = (2 * len).next_power_of_two().max(16);
            let shift = 64 - capacity.trailing_zeros();
            slots.clear();
            slots.resize(2 * capacity, EMPTY);
            for (place, key) in keys.iter().enumerate() {
                let mut at = (key.wrapping_mul(0x9E37_79B9_7F4A_7C15) >> shift) as usize;
                loop {
                    let held = slots[2 * at];
                    if held == EMPTY {
                        slots[2 * at] = *key;
                        slots[2 * at + 1] = first.len() as u64;
                        ids.push(first.len() as u32);
                        first.push(place as u32);
                        break;
                    }
                    if held == *key {
                        ids.push(slots[2 * at + 1] as u32);
                        break;
                    }
                    at = (at + 1) & (capacity - 1);
                }
            }
        }
    });
    (ids, first)
}

impl Table {
    /// The table of `cells`, whose rows are distinct.
    pub fn new(arity: usize, cells: Vec<Cell>) -> Arc<Table> {
        let len = cells.len().checked_div(arity).unwrap_or(0);
        Arc::new(Table { arity, len, cells: cells.into_boxed_slice(), hash: std::sync::OnceLock::new(), id: next_table_id(), masks: std::sync::OnceLock::new(), groupings: std::sync::OnceLock::new(), sorted: std::sync::OnceLock::new(), factors: std::sync::OnceLock::new() })
    }

    /// The table of `cells`, whose rows are distinct and whose hash is `hash`, which a read of the hash would give.
    pub fn with_hash(arity: usize, cells: Vec<Cell>, hash: u128) -> Arc<Table> {
        let table = Table::new(arity, cells);
        let _ = table.hash.set(hash);
        table
    }

    /// A hash of the set of rows, which their order does not change.
    pub fn hash(&self) -> u128 {
        *self.hash.get_or_init(|| {
            let mut hash = 0u128;
            if self.arity > 0 {
                for row in self.cells.chunks_exact(self.arity) {
                    hash = hash.wrapping_add(hash_row(row));
                }
            }
            hash.wrapping_add(hash_words([self.arity as u64, self.len as u64]))
        })
    }

    /// The filter of the column at `place`.
    pub fn mask(&self, place: usize) -> u64 {
        self.masks.get_or_init(|| {
            let mut masks = vec![0u64; self.arity];
            for row in self.rows() {
                for (mask, cell) in masks.iter_mut().zip(row) {
                    *mask |= 1 << (mix(u64::from(*cell)) >> 58);
                }
            }
            masks.into_boxed_slice()
        })[place]
    }

    /// How the values of the column at `place` group the rows. A key is never `u64::MAX`, since a cell has 32 bits.
    pub fn column_grouping(&self, place: usize) -> Arc<Grouping> {
        if self.len == 0 {
            return Arc::new((Vec::new(), Vec::new()));
        }
        let columns = self.groupings.get_or_init(|| (0..self.arity).map(|_| std::sync::OnceLock::new()).collect());
        columns[place].get_or_init(|| {
            let mut least = u32::MAX;
            let mut most = 0u32;
            let keys: Vec<u64> = self.rows().map(|row| {
                least = least.min(row[place]);
                most = most.max(row[place]);
                u64::from(row[place])
            }).collect();
            Arc::new(first_ids(&keys, u64::from(least), u64::from(most.saturating_sub(least)) + 1))
        }).clone()
    }

    /// The distinct values of the column at `place`, in order, sorted once for all that read them.
    pub fn sorted_column(&self, place: usize) -> Arc<[Cell]> {
        if self.len == 0 {
            return Arc::from(Vec::new());
        }
        let columns = self.sorted.get_or_init(|| (0..self.arity).map(|_| std::sync::OnceLock::new()).collect());
        columns[place].get_or_init(|| {
            let mut held: Vec<Cell> = self.rows().map(|row| row[place]).collect();
            held.sort_unstable();
            held.dedup();
            held.into()
        }).clone()
    }

    /// The table of `cells`, whose rows may repeat.
    pub fn distinct(arity: usize, cells: Vec<Cell>) -> Arc<Table> {
        Table::new(arity, distinct_rows(arity, cells))
    }

    /// The table of no columns, with one row where `holds`.
    pub fn unit(holds: bool) -> Arc<Table> {
        let len = usize::from(holds);
        Arc::new(Table { arity: 0, len, cells: Box::new([]), hash: std::sync::OnceLock::new(), id: next_table_id(), masks: std::sync::OnceLock::new(), groupings: std::sync::OnceLock::new(), sorted: std::sync::OnceLock::new(), factors: std::sync::OnceLock::new() })
    }

    pub fn rows(&self) -> impl Iterator<Item = &[Cell]> {
        self.cells.chunks_exact(self.arity.max(1))
    }

    /// The table's finest split into groups of columns whose product it is, which `make` gives the first time something asks.
    pub fn factors(&self, make: impl FnOnce() -> Factors) -> Arc<Factors> {
        self.factors.get_or_init(|| Arc::new(make())).clone()
    }
}

/// `cells` with each row once.
fn distinct_rows(arity: usize, mut cells: Vec<Cell>) -> Vec<Cell> {
    match arity {
        0 => cells,
        1 => {
            cells.sort_unstable();
            cells.dedup();
            cells
        }
        2 => {
            let mut packed: Vec<u64> = cells.chunks_exact(2).map(|row| (u64::from(row[0]) << 32) | u64::from(row[1])).collect();
            packed.sort_unstable();
            packed.dedup();
            let mut out = Vec::with_capacity(packed.len() * 2);
            for row in packed {
                out.push((row >> 32) as u32);
                out.push(row as u32);
            }
            out
        }
        3 | 4 => {
            // A row of up to four cells packs into one number whose order is the rows' order.
            let mut packed: Vec<u128> = cells.chunks_exact(arity).map(|row| row.iter().fold(0u128, |held, cell| (held << 32) | u128::from(*cell))).collect();
            packed.sort_unstable();
            packed.dedup();
            let mut out = Vec::with_capacity(packed.len() * arity);
            for row in packed {
                for place in (0..arity).rev() {
                    out.push((row >> (32 * place)) as u32);
                }
            }
            out
        }
        _ => {
            let mut rows: Vec<&[Cell]> = cells.chunks_exact(arity).collect();
            rows.sort_unstable();
            rows.dedup();
            let mut out = Vec::with_capacity(rows.len() * arity);
            for row in rows {
                out.extend_from_slice(row);
            }
            out
        }
    }
}

/// A factor of a value: a table, and the position in the value of each of its
/// columns.
#[derive(Clone, Debug)]
pub struct Part {
    pub table: Arc<Table>,
    pub columns: Box<[u16]>,
}

/// The rows of a relation at one grid.
#[derive(Clone, Debug)]
pub enum Val {
    /// A bound stopped it, or it is undefined.
    None,
    Empty,
    /// The product of the parts, each with a row. No parts is the one row of
    /// no columns.
    Rows(Arc<Vec<Part>>),
    /// The rows of `inside`, as the relation and the grid they come from. An operator that needs
    /// the rows themselves writes them out; the others, and the count of rows, read the boxes.
    Boxes(Arc<crate::boxes::Boxes>),
    /// The rows of a `join`, as the tables it joins and the equalities between their columns. An operator that needs the rows themselves writes them out; the others, and the count of rows, read the tables.
    Joined(Arc<crate::joined::Joined>),
}

impl Val {
    /// The value with any `inside` rows written out: no value where they pass `CELL_CAP` cells.
    pub fn written(&self) -> Val {
        match self {
            Val::Boxes(boxes) => boxes.written(),
            Val::Joined(joined) => joined.written(),
            other => other.clone(),
        }
    }

    /// Whether the value stands as the relations its rows come from, until an operator needs the rows.
    pub fn is_lazy(&self) -> bool {
        matches!(self, Val::Boxes(_) | Val::Joined(_))
    }

    /// Whether `step` takes what it needs from a lazy value as its first relation or, where `first` is false, as its second, without writing the rows.
    pub fn lazy_reads(&self, step: &Step, first: bool) -> bool {
        match self {
            Val::Boxes(boxes) => if first { boxes.reads(step) } else { boxes.reads_second(step) },
            Val::Joined(joined) => if first { joined.reads(step) } else { joined.reads_second(step) },
            _ => false,
        }
    }

    /// Whether `step` takes a lazy value as its first relation or, where `first` is false, its second, either by reading what it needs from it (`lazy_reads`) or, for the rows of a `join`, as a part of the join or select that `step` makes of it, which `crate::joined::extend` gives where the form allows it and otherwise leaves the rows to be written out.
    pub fn lazy_takes(&self, step: &Step, first: bool) -> bool {
        self.lazy_reads(step, first) || (matches!(self, Val::Joined(_)) && crate::joined::Joined::extends(step))
    }

    /// Whether the rows of a lazy value can be written out, in at most `CELL_CAP` cells.
    pub fn lazy_fits(&self) -> bool {
        match self {
            Val::Boxes(boxes) => boxes.fits(),
            Val::Joined(joined) => joined.fits(),
            _ => true,
        }
    }

    fn of_parts(parts: Vec<Part>) -> Val {
        Val::Rows(Arc::new(parts))
    }

    /// The value of one table whose columns stand in order.
    pub fn of_table(table: Arc<Table>) -> Val {
        if table.len == 0 {
            return Val::Empty;
        }
        if table.arity == 0 {
            return Val::of_parts(Vec::new());
        }
        let columns: Box<[u16]> = (0..table.arity as u16).collect();
        Val::of_parts(vec![Part { table, columns }])
    }

    /// The product of two tables, unbuilt, with the first's columns before the second's.
    pub fn of_pair(first: Arc<Table>, second: Arc<Table>) -> Val {
        let split = first.arity as u16;
        let (before, after): (Box<[u16]>, Box<[u16]>) = ((0..split).collect(), (split..split + second.arity as u16).collect());
        Val::of_parts(vec![Part { table: first, columns: before }, Part { table: second, columns: after }])
    }

    /// A hash of what the value holds, where each factor counts.
    pub fn hash(&self) -> u128 {
        match self {
            Val::None => 1,
            Val::Empty => 2,
            Val::Boxes(boxes) => boxes.hash(),
            Val::Joined(joined) => joined.hash(),
            Val::Rows(parts) => {
                let mut hash = hash_words([parts.len() as u64 + 3]);
                for part in parts.iter() {
                    let columns = hash_words(part.columns.iter().map(|column| u64::from(*column)));
                    hash = hash.wrapping_add(hash_words([part.table.hash() as u64, (part.table.hash() >> 64) as u64, columns as u64, (columns >> 64) as u64]));
                }
                hash
            }
        }
    }

    /// The rows, each in the order of the value's columns; `None` past `cap`.
    pub fn rows(&self, arity: usize, cap: usize) -> Option<Vec<Vec<Cell>>> {
        if self.is_lazy() {
            return self.written().rows(arity, cap);
        }
        let Val::Rows(parts) = self else { return Some(Vec::new()) };
        let total: usize = parts.iter().map(|part| part.table.len).try_fold(1usize, |total, len| total.checked_mul(len))?;
        if total > cap {
            return None;
        }
        let mut rows = vec![vec![0; arity]];
        for part in parts.iter() {
            let mut next = Vec::with_capacity(rows.len() * part.table.len);
            for row in &rows {
                for own in part.table.rows() {
                    let mut with = row.clone();
                    for (column, cell) in part.columns.iter().zip(own) {
                        with[usize::from(*column)] = *cell;
                    }
                    next.push(with);
                }
            }
            rows = next;
        }
        Some(rows)
    }
}

/// What a value gives for a lib relation at a row.
pub struct LibRelation {
    /// A hash of its name, the same in each op table.
    pub code: u64,
    pub algebra: &'static dyn Algebra,
    pub arity: usize,
}

/// An operator over the values of its children, each column by its position.
#[derive(Clone, Debug, serde::Serialize, serde::Deserialize)]
pub enum Step {
    Project { columns: Columns },
    Select { at: u16, op: Op, other: Option<u16>, drop: Option<u16> },
    Join { left: Box<[u16]>, right: Box<[u16]>, kept: Box<[u16]>, left_arity: u16 },
    Antijoin { left: Box<[u16]>, right: Columns },
    Semijoin { left: Box<[u16]>, right: Columns },
    /// The outer columns' values at which the first relation has a row, and each of its rows
    /// there has a match in the second. With no outer column, a relation of no columns.
    /// `reads` holds the `left_len` columns of the first relation that are matched, then its outer
    /// columns.
    All { reads: Columns, left_len: u16, right: Columns },
    Part(Box<crate::gen_parts::PartTerm>),
    Union { map: Box<[Option<u16>]> },
    LibJoin { relation: u32, bound: Box<[Option<u16>]>, left_arity: u16 },
    Component { instance: u32, port: u16 },
}

impl Step {
    /// A `project` at `columns`; a panic that names `text`, the term's text, where one stands twice.
    pub fn project(columns: &[u16], text: &str) -> Step {
        Step::Project { columns: Columns::of_term(columns, text) }
    }

    /// A `semijoin` of rows matched at `left` against the second relation's `right`.
    pub fn semijoin(left: &[u16], right: &[u16], text: &str) -> Step {
        Step::Semijoin { left: left.into(), right: Columns::of_term(right, text) }
    }

    /// An `antijoin` of rows matched at `left` against the second relation's `right`.
    pub fn antijoin(left: &[u16], right: &[u16], text: &str) -> Step {
        Step::Antijoin { left: left.into(), right: Columns::of_term(right, text) }
    }

    /// An `all` of rows matched at `left` against the second relation's `right`, over the `outer` columns of the first.
    pub fn all(left: &[u16], right: &[u16], outer: &[u16], text: &str) -> Step {
        let reads: Vec<u16> = left.iter().chain(outer).copied().collect();
        Step::All { reads: Columns::of_term(&reads, text), left_len: left.len() as u16, right: Columns::of_term(right, text) }
    }

    /// Whether the value is empty where its one or first child is empty.
    pub fn empty_on_empty(&self) -> bool {
        matches!(self, Step::Project { .. } | Step::Select { .. } | Step::Join { .. } | Step::Antijoin { .. } | Step::LibJoin { .. } | Step::Semijoin { .. } | Step::All { .. } | Step::Part(_))
    }
}

/// How an input of a component takes its rows.
#[derive(Clone, Debug)]
pub enum InputFill {
    /// From a binding: its key columns stand first where it is keyed.
    Bound { keyed: bool },
    /// These rows at every key.
    Rows(Vec<Box<[TermId]>>),
    /// One row at each key, with these places of the key.
    FromKey(Vec<usize>),
}

/// An input of a component as a construction reads it.
#[derive(Clone, Debug)]
pub struct InputShape {
    pub fill: InputFill,
    pub types: Box<[ValueType]>,
    pub columns: Box<[ValueType]>,
}

/// What an instance of a component is, apart from where its bound inputs read:
/// two instances of one shape on equal rows give equal rows.
pub struct CompShape {
    /// A hash of what the shape is, the same in each op table.
    pub code: u64,
    pub name: String,
    pub construction: &'static dyn Construction,
    pub inputs: Vec<InputShape>,
    pub key_width: usize,
    /// For each output: its width after the key, and whether it has the key.
    pub outputs: Vec<(usize, bool)>,
}

/// A bound input: the child it reads, and the positions it reads there, the key's
/// first. A position of `None` holds `0`.
#[derive(Clone, Debug, PartialEq, Eq, Hash)]
pub struct BoundInput {
    /// The input of the component, in the order the component declares them.
    pub input: u8,
    pub child: u8,
    pub positions: Box<[Option<u16>]>,
}

/// An instance of a component.
#[derive(Clone, Debug, PartialEq, Eq, Hash)]
pub struct CompInstance {
    pub shape: u32,
    pub bound: Box<[BoundInput]>,
}

/// The rows of each output of an instance, or no value.
pub type Outputs = Option<Vec<Arc<Table>>>;

/// The modulus of the hash of a set of rows.
const MODULUS: u128 = (1u128 << 61) - 1;

fn mix(value: u64) -> u64 {
    let mut x = value;
    x ^= x >> 33;
    x = x.wrapping_mul(0xff51_afd7_ed55_8ccd);
    x ^= x >> 33;
    x = x.wrapping_mul(0xc4ce_b9fe_1a85_ec53);
    x ^ (x >> 33)
}

/// The kind of a root's word, in its top bits; the word 0 is no value.
pub const WORD_NONEMPTY: u64 = 1 << 62;
pub const WORD_COUNT: u64 = 2 << 62;
pub const WORD_SET: u64 = 3 << 62;
const PAYLOAD: u64 = (1 << 62) - 1;

/// The evaluation of steps on one task.
pub struct Evaluator<'a> {
    pub shapes: &'a [CompShape],
    pub instances: &'a [CompInstance],
    pub libs: &'a [LibRelation],
    pub registry: &'static Registry,
    pub session: TaskSession,
    limits: Limits,
    lib_rows: FastMap<(u32, u8, [u32; 3]), Option<Arc<Vec<Cell>>>>,
    outputs: FastMap<(u32, [u128; 3]), Arc<Outputs>>,
    /// The cells that `outputs` holds, which a limit keeps from growing.
    output_cells: usize,
    names: FastMap<u32, u64>,
    sums: FastMap<(u128, u64), u64>,
    /// The count of each kind of evaluation, for a profile.
    pub runs: [u64; 3],
    /// For each shape, its runs and its seconds.
    pub shape_time: FastMap<u32, (u64, f64)>,
    /// The count of distinct rows of a table at some places.
    distinct_counts: FastMap<(u128, u64), u64>,
    /// How many rows of a table hold each key, at some places.
    histograms: FastMap<(u128, u64), Arc<Histogram>>,
    /// The cells that `histograms` holds, which a limit keeps from growing.
    histogram_cells: usize,
    /// The operators a count answered, and those that built their rows.
    pub counted: u64,
    pub built: u64,
}

/// The most cells of component outputs that an evaluation keeps for a later hit.
const HELD_OUTPUT_CELLS: usize = 1 << 22;

/// The most cells of histograms that an evaluation keeps for a later hit.
const HELD_HISTOGRAM_CELLS: usize = 1 << 25;

thread_local! {
    /// The cells of the written rows that the lazy values made on this thread hold, which no walker's count of held cells sees. A value that drops on another thread takes them off that thread's count, so the count can stand below 0.
    static LAZY_WRITTEN_CELLS: std::cell::Cell<isize> = const { std::cell::Cell::new(0) };
}

/// The cells of the written rows that the lazy values of this thread hold now.
pub fn lazy_written_cells() -> usize {
    LAZY_WRITTEN_CELLS.with(|held| held.get().max(0) as usize)
}

/// The cells of the tables of `value`, which a lazy value's written rows hold.
fn cells_of(value: &Val) -> usize {
    match value {
        Val::Rows(parts) => parts.iter().map(|part| part.table.cells.len()).sum::<usize>(),
        _ => 0,
    }
}

/// A lazy value has written its rows, which it holds until it drops.
pub(crate) fn lazy_wrote(value: &Val) {
    LAZY_WRITTEN_CELLS.with(|held| held.set(held.get() + cells_of(value) as isize));
}

/// A lazy value that wrote its rows drops them.
pub(crate) fn lazy_dropped(written: Option<&Val>) {
    if let Some(value) = written {
        LAZY_WRITTEN_CELLS.with(|held| held.set(held.get() - cells_of(value) as isize));
    }
}

impl<'a> Evaluator<'a> {
    pub fn new(shapes: &'a [CompShape], instances: &'a [CompInstance], libs: &'a [LibRelation], session: TaskSession) -> Self {
        Evaluator { shapes, instances, libs, registry: Registry::get(), session, limits: Limits::new(None, Cancellation::default()), lib_rows: FastMap::default(), outputs: FastMap::default(), output_cells: 0, names: FastMap::default(), sums: FastMap::default(), runs: [0; 3], shape_time: FastMap::default(), distinct_counts: FastMap::default(), histograms: FastMap::default(), histogram_cells: 0, counted: 0, built: 0 }
    }

    /// The value of `step` on `children`.
    pub fn apply(&mut self, step: &Step, children: &[&Val]) -> Val {
        if children.iter().any(|child| matches!(child, Val::None)) {
            return Val::None;
        }
        if children.iter().any(|child| child.is_lazy()) {
            // A `join` or a `select` over the rows of a `join` adds to the join where it can.
            if let Some(value) = crate::joined::extend(step, children[0], children.get(1).copied()) {
                return value;
            }
            // The rows of `inside` and of a `join` serve an operator that takes what it needs from the relations they come from as they are. Any other reads them written out.
            let second = match children.get(1) {
                Some(Val::Boxes(boxes)) => boxes.read_second(step),
                Some(Val::Joined(joined)) => joined.read_second(step),
                _ => None,
            };
            let mut held: Vec<&Val> = children.to_vec();
            if let Some(value) = &second {
                held[1] = value;
                if matches!(value, Val::None) {
                    return Val::None;
                }
            }
            let read = match held[0] {
                Val::Boxes(boxes) => boxes.read(step, &held),
                Val::Joined(joined) => joined.read(step, &held),
                _ => None,
            };
            if let Some(value) = read {
                return value;
            }
            let written: Vec<Val> = held.iter().map(|child| child.written()).collect();
            let held: Vec<&Val> = written.iter().collect();
            return self.apply(step, &held);
        }
        match step {
            Step::Project { columns } => project(children[0], columns),
            Step::Select { at, op, other, drop } => select(children[0], *at, *op, *other, *drop).unwrap_or(Val::None),
            Step::Join { left, right, kept, left_arity } => join(children[0], children[1], left, right, kept, *left_arity).unwrap_or(Val::None),
            Step::Antijoin { left, right } => antijoin(children[0], children[1], left, right).unwrap_or(Val::None),
            Step::Semijoin { left, right } => semijoin(children[0], children[1], left, right).unwrap_or(Val::None),
            Step::All { reads, left_len, right } => {
                let (left, outer) = reads.split(*left_len);
                all(children[0], children[1], left, right, outer).unwrap_or(Val::None)
            }
            Step::Part(part) => part.apply(children),
            Step::Union { map } => union(children[0], children[1], map).unwrap_or(Val::None),
            Step::LibJoin { relation, bound, left_arity } => self.lib_join(children[0], *relation, bound, *left_arity),
            Step::Component { instance, port } => {
                let outputs = self.component(*instance, children);
                match outputs.as_ref() {
                    None => Val::None,
                    Some(tables) => Val::of_table(tables[usize::from(*port)].clone()),
                }
            }
        }
    }

    /// The count of rows of `step` on `children`, with no rows built, where its form
    /// allows that. Each case reads what the operator keeps of each part.
    pub fn count(&mut self, step: &Step, children: &[&Val]) -> Option<Option<u64>> {
        if children.iter().any(|child| matches!(child, Val::None)) {
            return Some(None);
        }
        if children.iter().any(|child| child.is_lazy()) {
            return None;
        }
        let parts = |at: usize| -> Option<&Arc<Vec<Part>>> {
            match children.get(at) {
                Some(Val::Rows(parts)) => Some(parts),
                _ => None,
            }
        };
        let product = |parts: &[&Part]| parts.iter().map(|part| part.table.len as u64).fold(1u64, u64::saturating_mul);
        match step {
            Step::Project { columns } => {
                let Some(held) = parts(0) else { return Some(Some(0)) };
                let mut total = 1u64;
                for part in held.iter() {
                    let places: Vec<usize> = columns.iter().filter_map(|column| part.columns.iter().position(|own| own == column)).collect();
                    if places.is_empty() {
                        continue;
                    }
                    total = total.saturating_mul(self.distinct_count(&part.table, &places));
                }
                Some(Some(total))
            }
            Step::Select { at, op, other, .. } => {
                let Some(held) = parts(0) else { return Some(Some(0)) };
                let part = held.iter().find(|part| part.columns.contains(at))?;
                let a = part.columns.iter().position(|column| column == at)?;
                let b = match other {
                    Some(other) => match part.columns.iter().position(|column| column == other) {
                        Some(place) => Some(place),
                        // Two columns of two parts: a dot product of their histograms.
                        None => {
                            let second = held.iter().find(|part| part.columns.contains(other))?;
                            let place = second.columns.iter().position(|column| column == other)?;
                            if !matches!(op, Op::Eq | Op::Ne) {
                                return None;
                            }
                            let both = part.table.len as u64 * second.table.len as u64;
                            let matched = if part.table.mask(a) & second.table.mask(place) == 0 {
                                0
                            } else {
                                let histogram = self.histogram(&second.table, &[place]);
                                part.table.rows().map(|row| histogram.get(u64::from(row[a])).map_or(0, u64::from)).sum()
                            };
                            let kept = if *op == Op::Eq { matched } else { both - matched };
                            let others: Vec<&Part> = held.iter().filter(|own| !std::ptr::eq(*own, part) && !std::ptr::eq(*own, second)).collect();
                            return Some(Some(kept.saturating_mul(product(&others))));
                        }
                    },
                    None => None,
                };
                let others: Vec<&Part> = held.iter().filter(|own| !std::ptr::eq(*own, part)).collect();
                let mut kept = 0u64;
                for row in part.table.rows() {
                    if holds(*op, row[a], b.map_or(0, |b| row[b])) {
                        kept += 1;
                    }
                }
                Some(Some(kept.saturating_mul(product(&others))))
            }
            Step::Join { left, right, .. } => {
                let (Some(left_parts), Some(right_parts)) = (parts(0), parts(1)) else { return Some(Some(0)) };
                if left.is_empty() {
                    let every: Vec<&Part> = left_parts.iter().chain(right_parts.iter()).collect();
                    return Some(Some(product(&every)));
                }
                let (l, l_rest, l_places) = one_part(left_parts, left)?;
                let (r, r_rest, r_places) = one_part(right_parts, right)?;
                if l.table.cells.len() > CELL_CAP || r.table.cells.len() > CELL_CAP {
                    return None;
                }
                if l_places.iter().zip(&r_places).any(|(a, b)| l.table.mask(*a) & r.table.mask(*b) == 0) {
                    return Some(Some(0));
                }
                let histogram = self.histogram(&r.table, &r_places);
                let mut matched = 0u64;
                for row in l.table.rows() {
                    if let Some(count) = histogram.get(key_word(row, &l_places)) {
                        matched += u64::from(count);
                    }
                }
                let rest: Vec<&Part> = l_rest.into_iter().chain(r_rest).collect();
                Some(Some(matched.saturating_mul(product(&rest))))
            }
            Step::Antijoin { left, right } => {
                let Some(left_parts) = parts(0) else { return Some(Some(0)) };
                let every: Vec<&Part> = left_parts.iter().collect();
                let Some(right_parts) = parts(1) else { return Some(Some(product(&every))) };
                if left.is_empty() {
                    return Some(Some(0));
                }
                let (l, l_rest, l_places) = one_part(left_parts, left)?;
                let (r, _, r_places) = one_part(right_parts, right)?;
                if l.table.cells.len() > CELL_CAP || r.table.cells.len() > CELL_CAP {
                    return None;
                }
                if l_places.iter().zip(&r_places).any(|(a, b)| l.table.mask(*a) & r.table.mask(*b) == 0) {
                    return Some(Some(product(&every)));
                }
                let histogram = self.histogram(&r.table, &r_places);
                let mut kept = 0u64;
                for row in l.table.rows() {
                    if histogram.get(key_word(row, &l_places)).is_none() {
                        kept += 1;
                    }
                }
                Some(Some(kept.saturating_mul(product(&l_rest))))
            }
            Step::LibJoin { relation, bound, .. } => {
                let Some(held) = parts(0) else { return Some(Some(0)) };
                let positions: Vec<u16> = bound.iter().flatten().copied().collect();
                let arity = self.libs[*relation as usize].arity;
                if positions.is_empty() {
                    let rows = self.lib_rows_at(*relation, &vec![None; arity])?;
                    let every: Vec<&Part> = held.iter().collect();
                    return Some(Some((rows.len() / arity.max(1)) as u64 * product(&every)));
                }
                let (part, rest, _) = one_part(held, &positions)?;
                let places: Vec<Option<usize>> = bound.iter().map(|at| at.and_then(|at| part.columns.iter().position(|column| *column == at))).collect();
                let mut bindings: Vec<Option<Cell>> = vec![None; arity];
                let mut total = 0u64;
                let held_part = part.clone();
                let others = product(&rest);
                for row in held_part.table.rows() {
                    for (at, place) in places.iter().enumerate() {
                        bindings[at] = place.map(|place| row[place]);
                    }
                    let Some(rows) = self.lib_rows_at(*relation, &bindings) else { return Some(None) };
                    total += (rows.len() / arity.max(1)) as u64;
                }
                Some(Some(total.saturating_mul(others)))
            }
            _ => None,
        }
    }

    /// The count of distinct rows of `table` at `places`.
    fn distinct_count(&mut self, table: &Table, places: &[usize]) -> u64 {
        if places.len() == table.arity {
            return table.len as u64;
        }
        let word = hash_words(places.iter().map(|place| *place as u64)) as u64;
        if let Some(found) = self.distinct_counts.get(&(table.hash(), word)) {
            return *found;
        }
        let count = if let [one] = places {
            table.column_grouping(*one).1.len() as u64
        } else {
            let mut keys: Vec<u64> = table.rows().map(|row| key_word(row, places)).collect();
            keys.sort_unstable();
            keys.dedup();
            keys.len() as u64
        };
        if self.distinct_counts.len() > 1 << 20 {
            self.distinct_counts.clear();
        }
        self.distinct_counts.insert((table.hash(), word), count);
        count
    }

    /// The cells and the entries that the histograms of this evaluator hold.
    pub fn histograms_held(&self) -> (usize, usize) {
        (self.histogram_cells, self.histograms.len())
    }

    /// How many rows of `table` hold each key at `places`.
    fn histogram(&mut self, table: &Table, places: &[usize]) -> Arc<Histogram> {
        let word = hash_words(places.iter().map(|place| *place as u64)) as u64;
        if let Some(found) = self.histograms.get(&(table.hash(), word)) {
            return found.clone();
        }
        let keys: Vec<u64> = table.rows().map(|row| key_word(row, places)).collect();
        let (index, ids) = KeyIndex::of(&keys);
        let mut counts = vec![0u32; ids.iter().max().map_or(0, |last| *last as usize + 1)];
        for id in &ids {
            counts[*id as usize] += 1;
        }
        let counts = Arc::new(Histogram { index, counts });
        let size = counts.index.cells() + counts.counts.len();
        if self.histograms.len() > 1 << 16 || self.histogram_cells + size > HELD_HISTOGRAM_CELLS {
            self.histograms.clear();
            self.histogram_cells = 0;
        }
        self.histogram_cells += size;
        self.histograms.insert((table.hash(), word), counts.clone());
        counts
    }

    /// The rows of `relation` that agree with `bound`: a flat list, all of its
    /// columns. `None` where a bound stopped it.
    fn lib_rows_at(&mut self, relation: u32, bound: &[Option<Cell>]) -> Option<Arc<Vec<Cell>>> {
        let held = bound.iter().flatten().count();
        let key = if held <= 3 {
            let mut mask = 0u8;
            let mut values = [0u32; 3];
            let mut at = 0;
            for (place, value) in bound.iter().enumerate().take(8) {
                if let Some(value) = value {
                    mask |= 1 << place;
                    values[at] = *value;
                    at += 1;
                }
            }
            (bound.len() <= 8).then_some((relation, mask, values))
        } else {
            None
        };
        if let Some(key) = &key {
            if let Some(found) = self.lib_rows.get(key) {
                return found.clone();
            }
        }
        let terms: Vec<Option<TermId>> = bound.iter().map(|value| value.map(TermId::from_encoding)).collect();
        let lib = &self.libs[relation as usize];
        let mut found: Vec<Cell> = Vec::new();
        let done = lib.algebra.evaluate(&terms, self.registry, &mut |row| {
            if terms.iter().zip(row).all(|(held, value)| held.is_none_or(|held| held == *value)) {
                found.extend(row.iter().map(|cell| cell.encoding()));
            }
        });
        let value = done.ok().map(|()| Arc::new(distinct_rows(lib.arity, found)));
        if let Some(key) = key {
            self.lib_rows.insert(key, value.clone());
        }
        value
    }

    /// All rows of `relation`.
    pub fn lib_table(&mut self, relation: u32) -> Option<Arc<Table>> {
        let arity = self.libs[relation as usize].arity;
        let rows = self.lib_rows_at(relation, &vec![None; arity])?;
        Some(Table::new(arity, rows.as_ref().clone()))
    }

    fn lib_join(&mut self, value: &Val, relation: u32, bound: &[Option<u16>], left_arity: u16) -> Val {
        let Val::Rows(parts) = value else { return Val::Empty };
        let arity = self.libs[relation as usize].arity;
        let fresh: Vec<usize> = (0..arity).filter(|at| bound[*at].is_none()).collect();
        let positions: Vec<u16> = bound.iter().flatten().copied().collect();
        let (touched, rest) = split_parts(parts, &positions);
        let Some(merged) = merge(&touched, Bound::LibJoin) else { return Val::None };
        // The place in the merged rows of each lib column that a position binds.
        let places: Vec<Option<usize>> = bound.iter().map(|at| at.map(|at| merged.columns.iter().position(|column| *column == at).expect("a bound column stands in a touched part"))).collect();
        let width = merged.columns.len() + fresh.len();
        let mut out: Vec<Cell> = Vec::new();
        let mut held: Vec<Option<Cell>> = vec![None; arity];
        if merged.columns.is_empty() {
            let Some(rows) = self.lib_rows_at(relation, &held) else { return Val::None };
            for row in rows.chunks_exact(arity.max(1)) {
                out.extend(fresh.iter().map(|at| row[*at]));
            }
        } else {
            for row in merged.cells.chunks_exact(merged.columns.len()) {
                for (at, place) in places.iter().enumerate() {
                    held[at] = place.map(|place| row[place]);
                }
                let Some(rows) = self.lib_rows_at(relation, &held) else { return Val::None };
                for lib_row in rows.chunks_exact(arity.max(1)) {
                    out.extend_from_slice(row);
                    out.extend(fresh.iter().map(|at| lib_row[*at]));
                }
                if out.len() > CELL_CAP {
                    crate::bounds::mark(Bound::LibJoin);
                    return Val::None;
                }
            }
        }
        if out.is_empty() {
            return Val::Empty;
        }
        let mut columns: Vec<u16> = merged.columns.clone();
        columns.extend((0..fresh.len() as u16).map(|at| left_arity + at));
        let mut result = rest;
        if width > 0 {
            result.push(Part { table: Table::distinct(width, out), columns: columns.into_boxed_slice() });
        }
        Val::of_parts(result)
    }

    /// The rows of `positions` of `value`, each row once.
    fn projected(&mut self, value: &Val, positions: &[Option<u16>]) -> Option<Arc<Table>> {
        let width = positions.len();
        let Val::Rows(parts) = value else {
            return Some(if width == 0 { Table::unit(false) } else { Table::new(width, Vec::new()) });
        };
        if width == 0 {
            return Some(Table::unit(true));
        }
        // Where every position reads one part in order, the rows are the part's.
        if let [part] = &parts[..] {
            if part.columns.len() == width && positions.iter().zip(part.columns.iter()).all(|(at, column)| *at == Some(*column)) {
                return Some(part.table.clone());
            }
        }
        // The distinct rows of each part at the positions it holds.
        let mut factors: Vec<(Vec<usize>, Vec<Cell>)> = Vec::new();
        for part in parts.iter() {
            let held: Vec<usize> = positions.iter().enumerate().filter(|(_, at)| at.is_some_and(|at| part.columns.contains(&at))).map(|(place, _)| place).collect();
            if held.is_empty() {
                continue;
            }
            let places: Vec<usize> = held.iter().map(|place| part.columns.iter().position(|column| Some(*column) == positions[*place]).expect("a held position")).collect();
            let mut cells = Vec::with_capacity(part.table.len * places.len());
            for row in part.table.rows() {
                cells.extend(places.iter().map(|at| row[*at]));
            }
            let cells = distinct_rows(places.len(), cells);
            factors.push((held, cells));
        }
        let total = factors.iter().try_fold(1usize, |total, (held, cells)| total.checked_mul(cells.len() / held.len().max(1)));
        let Some(total) = total.filter(|total| total.checked_mul(width).is_some_and(|cells| cells <= CELL_CAP)) else {
            crate::bounds::mark(Bound::Projected);
            return None;
        };
        let mut out: Vec<Cell> = vec![0; total * width];
        let mut repeat = 1usize;
        for (held, cells) in &factors {
            let rows = cells.len() / held.len().max(1);
            for row in 0..total {
                let own = (row / repeat) % rows;
                for (at, place) in held.iter().enumerate() {
                    out[row * width + place] = cells[own * held.len() + at];
                }
            }
            repeat *= rows;
        }
        Some(Table::new(width, out))
    }

    fn component(&mut self, instance: u32, children: &[&Val]) -> Arc<Outputs> {
        let held = &self.instances[instance as usize];
        let mut tables: Vec<Arc<Table>> = Vec::with_capacity(held.bound.len());
        for bound in held.bound.iter() {
            match self.projected(children[usize::from(bound.child)], &bound.positions) {
                Some(table) => tables.push(table),
                None => return Arc::new(None),
            }
        }
        let mut key = [0u128; 3];
        for (at, table) in tables.iter().enumerate().take(3) {
            key[at] = table.hash();
        }
        let shape_id = held.shape;
        if let Some(found) = self.outputs.get(&(shape_id, key)) {
            return found.clone();
        }
        self.runs[0] += 1;
        let started = std::time::Instant::now();
        let shape = &self.shapes[shape_id as usize];
        let found = match fast_component(shape, &tables) {
            Some(found) => found,
            None => self.run_component(shape_id, &tables),
        };
        let spent = self.shape_time.entry(shape_id).or_default();
        spent.0 += 1;
        spent.1 += started.elapsed().as_secs_f64();
        let outputs = Arc::new(found);
        let cells: usize = outputs.iter().flatten().map(|table| table.cells.len()).sum();
        if self.output_cells + cells > HELD_OUTPUT_CELLS {
            self.outputs.clear();
            self.output_cells = 0;
        }
        self.output_cells += cells;
        self.outputs.insert((shape_id, key), outputs.clone());
        outputs
    }

    fn run_component(&mut self, shape_id: u32, tables: &[Arc<Table>]) -> Outputs {
        let shape = &self.shapes[shape_id as usize];
        let key_width = shape.key_width;
        // The key groups: the key columns of each binding that has them.
        let mut groups: FastMap<Vec<Cell>, usize> = FastMap::default();
        let mut keys: Vec<Vec<Cell>> = Vec::new();
        let mut bound_at = 0usize;
        for input in &shape.inputs {
            if let InputFill::Bound { keyed } = input.fill {
                if keyed {
                    for row in tables[bound_at].rows() {
                        let key = &row[..key_width];
                        if !groups.contains_key(key) {
                            groups.insert(key.to_vec(), keys.len());
                            keys.push(key.to_vec());
                        }
                    }
                }
                bound_at += 1;
            }
        }
        if key_width == 0 {
            keys.push(Vec::new());
        }
        // Each input's rows at each group.
        let mut by_group: Vec<Vec<RowSet>> = vec![Vec::with_capacity(shape.inputs.len()); keys.len()];
        let mut bound_at = 0usize;
        for input in &shape.inputs {
            let width = input.types.len();
            match &input.fill {
                InputFill::Bound { keyed } => {
                    let table = &tables[bound_at];
                    bound_at += 1;
                    if *keyed {
                        let mut sets: Vec<RowSet> = vec![RowSet::empty(width as u16); keys.len()];
                        for row in table.rows() {
                            let group = groups[&row[..key_width]];
                            sets[group].insert(row[key_width..].iter().map(|cell| TermId::from_encoding(*cell)).collect());
                        }
                        for (group, set) in by_group.iter_mut().zip(sets) {
                            group.push(set);
                        }
                    } else {
                        let mut set = RowSet::empty(width as u16);
                        if table.arity == 0 {
                            if table.len > 0 {
                                set.insert(Box::new([]));
                            }
                        } else {
                            for row in table.rows() {
                                set.insert(row.iter().map(|cell| TermId::from_encoding(*cell)).collect());
                            }
                        }
                        for group in by_group.iter_mut() {
                            group.push(set.clone());
                        }
                    }
                }
                InputFill::Rows(rows) => {
                    let mut set = RowSet::empty(width as u16);
                    for row in rows {
                        set.insert(row.clone());
                    }
                    for group in by_group.iter_mut() {
                        group.push(set.clone());
                    }
                }
                InputFill::FromKey(places) => {
                    for (group, key) in by_group.iter_mut().zip(&keys) {
                        let mut set = RowSet::empty(width as u16);
                        set.insert(places.iter().map(|place| TermId::from_encoding(key[*place])).collect());
                        group.push(set);
                    }
                }
            }
        }
        let types: Vec<Box<[ValueType]>> = shape.inputs.iter().map(|input| input.types.clone()).collect();
        let columns: Vec<Box<[ValueType]>> = shape.inputs.iter().map(|input| input.columns.clone()).collect();
        let wanted = vec![true; shape.outputs.len()];
        let mut cells: Vec<Vec<Cell>> = vec![Vec::new(); shape.outputs.len()];
        let mut counts: Vec<usize> = vec![0; shape.outputs.len()];
        let mut budget = Budget::new(&self.limits, &self.session);
        for (key, inputs) in keys.iter().zip(&by_group) {
            let group = GroupInputs { inputs, types: &types, columns: &columns, wanted: &wanted };
            if shape.construction.outside_domain(&group) {
                return None;
            }
            let mut context = ConstructionContext { session: &self.session, registry: self.registry, budget: &mut budget };
            let outputs = shape.construction.evaluate(&group, &mut context).ok()?;
            for (at, rows) in outputs.outputs.iter().enumerate() {
                let (_, has_key) = shape.outputs[at];
                for row in rows.rows() {
                    if has_key {
                        cells[at].extend_from_slice(key);
                    }
                    cells[at].extend(row.iter().map(|cell| cell.encoding()));
                    counts[at] += 1;
                }
                if cells[at].len() > CELL_CAP {
                    crate::bounds::mark(Bound::ComponentOutput);
                    return None;
                }
            }
        }
        let mut out = Vec::with_capacity(cells.len());
        for (at, cells) in cells.into_iter().enumerate() {
            let (width, has_key) = shape.outputs[at];
            let arity = width + if has_key { key_width } else { 0 };
            out.push(if arity == 0 { Table::unit(counts[at] > 0) } else { Table::new(arity, cells) });
        }
        Some(out)
    }

    /// A hash of the value at the place `at` of a root's columns.
    fn cell_hash(&mut self, at: usize, id: Cell, name: bool) -> u64 {
        let value = if name {
            *self.names.entry(id).or_insert_with(|| {
                let Term::Constant(Constant::LibName(text)) = Term::decode(TermId::from_encoding(id), &ValueType::LibName) else { unreachable!("a lib name decodes to a lib name") };
                hash_words(text.text().bytes().map(u64::from)) as u64
            })
        } else {
            u64::from(id)
        };
        let word = mix(value ^ (at as u64 + 1).wrapping_mul(0x9e37_79b9_7f4a_7c15));
        (u128::from(word) % (MODULUS - 1) + 1) as u64
    }

    /// The sum over the distinct rows of `table`, at `places` with their places
    /// among a root's columns, of the product of their values' hashes.
    fn part_sum(&mut self, table: &Table, places: &[(usize, usize, bool)]) -> u64 {
        let key = if table.len > 8 {
            let word = hash_words(places.iter().map(|(place, at, name)| (*place as u64) << 32 | (*at as u64) << 1 | u64::from(*name))) as u64;
            let key = (table.hash(), word);
            if let Some(found) = self.sums.get(&key) {
                return *found;
            }
            Some(key)
        } else {
            None
        };
        let mut sum: u128 = 0;
        let mut product = |row: &[Cell], this: &mut Self| {
            let mut hash: u128 = 1;
            for (place, at, name) in places {
                hash = hash * u128::from(this.cell_hash(*at, row[*place], *name)) % MODULUS;
            }
            sum = (sum + hash) % MODULUS;
        };
        if places.len() == table.arity {
            for row in table.rows() {
                product(row, self);
            }
        } else {
            let mut cells: Vec<Cell> = Vec::with_capacity(table.len * places.len());
            for row in table.rows() {
                cells.extend(places.iter().map(|(place, _, _)| row[*place]));
            }
            let cells = distinct_rows(places.len(), cells);
            let local: Vec<(usize, usize, bool)> = places.iter().enumerate().map(|(place, (_, at, name))| (place, *at, *name)).collect();
            for row in cells.chunks_exact(places.len()) {
                let mut hash: u128 = 1;
                for (place, at, name) in &local {
                    hash = hash * u128::from(self.cell_hash(*at, row[*place], *name)) % MODULUS;
                }
                sum = (sum + hash) % MODULUS;
            }
        }
        let value = sum as u64;
        if let Some(key) = key {
            self.sums.insert(key, value);
        }
        value
    }

    /// The word of each root over `value`: `nonempty`, `cardinality`, and a
    /// `value-set` per nonempty subset of the columns `invariant`, in the order of
    /// their masks. `names` says which positions hold a lib name.
    pub fn words(&mut self, value: &Val, invariant: &[u16], names: &[bool], out: &mut Vec<u64>) {
        let masks = (1u32 << invariant.len().min(12)) - 1;
        if value.is_lazy() {
            return self.words(&value.written(), invariant, names, out);
        }
        match value {
            Val::Boxes(_) | Val::Joined(_) => {}
            Val::None => out.extend(std::iter::repeat_n(0, 2 + masks as usize)),
            Val::Empty => {
                out.push(WORD_NONEMPTY);
                out.push(WORD_COUNT);
                out.extend(std::iter::repeat_n(WORD_SET, masks as usize));
            }
            Val::Rows(parts) => {
                out.push(WORD_NONEMPTY | 1);
                let count = parts.iter().fold(1u128, |count, part| (count * part.table.len as u128).min(u128::from(PAYLOAD)));
                out.push(WORD_COUNT | count as u64);
                let parts = parts.clone();
                for mask in 1..=masks {
                    let chosen: Vec<u16> = (0..invariant.len().min(12)).filter(|at| mask & (1 << at) != 0).map(|at| invariant[at]).collect();
                    let mut product: u128 = 1;
                    for part in parts.iter() {
                        let places: Vec<(usize, usize, bool)> = chosen
                            .iter()
                            .enumerate()
                            .filter_map(|(at, position)| part.columns.iter().position(|column| column == position).map(|place| (place, at, names.get(usize::from(*position)).copied().unwrap_or(false))))
                            .collect();
                        if places.is_empty() {
                            continue;
                        }
                        product = product * u128::from(self.part_sum(&part.table, &places)) % MODULUS;
                    }
                    out.push(WORD_SET | ((product as u64) & PAYLOAD));
                }
            }
        }
    }
}

/// A 64-bit key of the values of `row` at `places`.
pub(crate) fn key_word(row: &[Cell], places: &[usize]) -> u64 {
    match places {
        [one] => u64::from(row[*one]),
        [one, two] => (u64::from(row[*one]) << 32) | u64::from(row[*two]),
        _ => hash_words(places.iter().map(|place| u64::from(row[*place]))) as u64,
    }
}

/// The one part of `parts` that holds every one of `positions`, the other parts, and
/// the place of each position; `None` where they stand in several.
fn one_part<'p>(parts: &'p [Part], positions: &[u16]) -> Option<(&'p Part, Vec<&'p Part>, Vec<usize>)> {
    let first = positions.first()?;
    let part = parts.iter().find(|part| part.columns.contains(first))?;
    let places: Option<Vec<usize>> = positions.iter().map(|at| part.columns.iter().position(|column| column == at)).collect();
    let rest = parts.iter().filter(|own| !std::ptr::eq(*own, part)).collect();
    Some((part, rest, places?))
}

/// The rows of an input at each key: a table keyed by its first `key_width`
/// columns, as a map from a key to its count of rows.
fn key_counts<'t>(table: &'t Table, key_width: usize) -> FastMap<&'t [Cell], u32> {
    let mut counts: FastMap<&[Cell], u32> = FastMap::default();
    if table.arity == 0 {
        return counts;
    }
    for row in table.rows() {
        *counts.entry(&row[..key_width]).or_default() += 1;
    }
    counts
}

/// The frequent components, read straight off their inputs' rows, where their
/// inputs have a simple form: what each construction gives on each key group, with
/// no row sets. `None` leaves the instance to its construction.
fn fast_component<'t>(shape: &CompShape, tables: &'t [Arc<Table>]) -> Option<Outputs> {
    let key_width = shape.key_width;
    match shape.name.as_str() {
        "Cardinality" => {
            let [member, domain] = &shape.inputs[..] else { return None };
            let InputFill::Bound { keyed: member_keyed } = member.fill else { return None };
            let domain_every = match &domain.fill {
                InputFill::FromKey(_) => true,
                InputFill::Rows(rows) if rows.is_empty() => false,
                _ => return None,
            };
            let table = tables.first()?;
            if key_width == 0 {
                let mut cells = Vec::new();
                if table.len > 0 {
                    cells.push(Term::encode_count(table.len).encoding());
                }
                return Some(Some(vec![Table::new(1, cells)]));
            }
            if !member_keyed {
                return None;
            }
            let _ = domain_every;
            let counts = key_counts(table, key_width);
            let mut cells = Vec::with_capacity(counts.len() * (key_width + 1));
            for (key, count) in counts.sorted_entries() {
                cells.extend_from_slice(key);
                cells.push(Term::encode_count(*count as usize).encoding());
            }
            Some(Some(vec![Table::new(key_width + 1, cells)]))
        }
        "Singleton" => {
            let [member] = &shape.inputs[..] else { return None };
            let InputFill::Bound { keyed } = member.fill else { return None };
            let table = tables.first()?;
            let width = shape.outputs[0].0;
            if key_width == 0 {
                let value = if table.len == 1 { table.clone() } else { Table::new(width.max(1), Vec::new()) };
                let value = if width == 0 { Table::unit(table.len == 1) } else { value };
                return Some(Some(vec![value, Table::unit(table.len > 1)]));
            }
            if !keyed {
                return None;
            }
            let counts = key_counts(table, key_width);
            let mut value = Vec::new();
            for row in table.rows() {
                if counts[&row[..key_width]] == 1 {
                    value.extend_from_slice(row);
                }
            }
            let mut plural = Vec::new();
            for (key, count) in counts.sorted_entries() {
                if *count > 1 {
                    plural.extend_from_slice(key);
                }
            }
            Some(Some(vec![Table::new(key_width + width, value), Table::new(key_width, plural)]))
        }
        "Excess" => {
            let [plus, minus] = &shape.inputs[..] else { return None };
            let mut bound_at = 0usize;
            let mut read = |input: &InputShape| -> Option<Option<(&Arc<Table>, bool)>> {
                match &input.fill {
                    InputFill::Bound { keyed } => {
                        let found = tables.get(bound_at)?;
                        bound_at += 1;
                        Some(Some((found, *keyed)))
                    }
                    InputFill::Rows(rows) if rows.is_empty() => Some(None),
                    _ => None,
                }
            };
            let plus = read(plus)?;
            let minus = read(minus)?;
            if key_width == 0 {
                let count = |held: &Option<(&Arc<Table>, bool)>| held.as_ref().map_or(0, |(table, _)| table.len);
                let (a, b) = (count(&plus), count(&minus));
                let cells = if a > b { vec![Term::encode_count(a - b).encoding()] } else { Vec::new() };
                return Some(Some(vec![Table::new(1, cells)]));
            }
            // A key that either keyed input holds, each input's rows at that key.
            let counts = |held: &Option<(&'t Arc<Table>, bool)>| -> Option<(FastMap<&'t [Cell], u32>, u32)> {
                match *held {
                    Some((table, true)) => Some((key_counts(table, key_width), 0)),
                    Some((table, false)) => Some((FastMap::default(), table.len as u32)),
                    None => Some((FastMap::default(), 0)),
                }
            };
            let (plus_keys, plus_all) = counts(&plus)?;
            let (minus_keys, minus_all) = counts(&minus)?;
            let mut cells = Vec::new();
            let mut emit = |key: &[Cell]| {
                let a = plus_keys.get(key).copied().unwrap_or(0) + plus_all;
                let b = minus_keys.get(key).copied().unwrap_or(0) + minus_all;
                if a > b {
                    cells.extend_from_slice(key);
                    cells.push(Term::encode_count((a - b) as usize).encoding());
                }
            };
            // The keys of either input, in order.
            let mut keys: Vec<&[Cell]> = plus_keys.sorted_keys().into_iter().copied().collect();
            keys.extend(minus_keys.sorted_keys().into_iter().copied().filter(|key| !plus_keys.contains_key(*key)));
            keys.sort_unstable();
            for key in keys {
                emit(key);
            }
            Some(Some(vec![Table::new(key_width + 1, cells)]))
        }
        "Inclusion" => {
            let [pattern, observed] = &shape.inputs[..] else { return None };
            let (InputFill::Bound { keyed: false }, InputFill::Bound { keyed: false }) = (&pattern.fill, &observed.fill) else { return None };
            let [pattern_table, observed_table] = tables else { return None };
            let id_width = |input: &InputShape| crate::native::type_width(input.columns.first());
            let (pattern_id, observed_id) = (id_width(pattern), id_width(observed));
            // The members of each set, each member by its key, and each set's size.
            let sizes = |table: &Table, id: usize| -> FastMap<Vec<Cell>, u32> {
                let mut sizes: FastMap<Vec<Cell>, u32> = FastMap::default();
                if table.arity > 0 {
                    for row in table.rows() {
                        *sizes.entry(row[..id].to_vec()).or_default() += 1;
                    }
                }
                sizes
            };
            let pattern_sizes = sizes(pattern_table, pattern_id);
            let observed_sizes = sizes(observed_table, observed_id);
            let mut by_member: FastMap<&[Cell], Vec<&[Cell]>> = FastMap::default();
            if pattern_table.arity > 0 {
                for row in pattern_table.rows() {
                    by_member.entry(&row[pattern_id..]).or_default().push(&row[..pattern_id]);
                }
            }
            let mut shared: FastMap<(&[Cell], &[Cell]), u32> = FastMap::default();
            if observed_table.arity > 0 {
                for row in observed_table.rows() {
                    if let Some(found) = by_member.get(&row[observed_id..]) {
                        for id in found {
                            *shared.entry((&row[..observed_id], *id)).or_default() += 1;
                        }
                    }
                }
            }
            let width = observed_id + pattern_id;
            let (mut superset, mut equal) = (Vec::new(), Vec::new());
            for ((observed_key, pattern_key), count) in shared.sorted_entries() {
                let size = pattern_sizes[*pattern_key];
                if *count == size {
                    superset.extend_from_slice(observed_key);
                    superset.extend_from_slice(pattern_key);
                    if size == observed_sizes[*observed_key] {
                        equal.extend_from_slice(observed_key);
                        equal.extend_from_slice(pattern_key);
                    }
                }
            }
            if width == 0 {
                return None;
            }
            Some(Some(vec![Table::new(width, superset), Table::new(width, equal)]))
        }
        _ => None,
    }
}

/// The number of row positions of a column of the type `ty`.
pub fn type_width(ty: Option<&ValueType>) -> usize {
    ty.map_or(0, arclog::eval::instance::width)
}

/// The parts of `parts` that hold one of `positions`, and the others.
fn split_parts<'p>(parts: &'p [Part], positions: &[u16]) -> (Vec<&'p Part>, Vec<Part>) {
    let mut touched = Vec::new();
    let mut rest = Vec::new();
    for part in parts {
        if part.columns.iter().any(|column| positions.contains(column)) {
            touched.push(part);
        } else {
            rest.push(part.clone());
        }
    }
    (touched, rest)
}

/// The rows of a product of parts, with the position of each column.
struct Merged<'p> {
    columns: Vec<u16>,
    cells: std::borrow::Cow<'p, [Cell]>,
}

/// The table of the product of `parts`, which `merged` holds.
fn side_table(parts: &[&Part], merged: &Merged) -> Arc<Table> {
    match parts {
        [one] => one.table.clone(),
        _ => Table::new(merged.columns.len(), merged.cells.to_vec()),
    }
}

/// The product of `parts`, or `None` past the cap. One part is its own rows, read in place.
fn merge<'p>(parts: &[&'p Part], site: Bound) -> Option<Merged<'p>> {
    let columns: Vec<u16> = parts.iter().flat_map(|part| part.columns.iter().copied()).collect();
    let total = parts.iter().try_fold(1usize, |total, part| total.checked_mul(part.table.len));
    if parts.is_empty() {
        return Some(Merged { columns, cells: std::borrow::Cow::Borrowed(&[]) });
    }
    let Some(total) = total.filter(|total| total.checked_mul(columns.len()).is_some_and(|cells| cells <= CELL_CAP)) else {
        crate::bounds::mark(site);
        return None;
    };
    if let [one] = parts {
        return Some(Merged { columns, cells: std::borrow::Cow::Borrowed(&one.table.cells) });
    }
    let width = columns.len();
    let mut cells: Vec<Cell> = vec![0; total * width];
    let mut repeat = 1usize;
    let mut offset = 0usize;
    for part in parts {
        let arity = part.table.arity;
        let rows = part.table.len;
        // Each row of the part stands for `repeat` rows in a run, and the run goes round again until the product ends.
        let mut at = 0usize;
        while at < total {
            for own in 0..rows {
                let from = &part.table.cells[own * arity..(own + 1) * arity];
                for _ in 0..repeat {
                    cells[at * width + offset..at * width + offset + arity].copy_from_slice(from);
                    at += 1;
                }
            }
        }
        repeat *= rows;
        offset += arity;
    }
    Some(Merged { columns, cells: std::borrow::Cow::Owned(cells) })
}

/// The rows of the parts that a step reads. One part is its own rows, read in place at any size; several parts are written as a product, which `site` bounds.
fn touched_rows<'p>(parts: &[&'p Part], site: Bound) -> Option<Merged<'p>> {
    if let [one] = parts {
        return Some(Merged { columns: one.columns.to_vec(), cells: std::borrow::Cow::Borrowed(&one.table.cells) });
    }
    merge(parts, site)
}

pub(crate) fn project(value: &Val, columns: &[u16]) -> Val {
    let Val::Rows(parts) = value else { return value.clone() };
    let mut out = Vec::with_capacity(parts.len());
    for part in parts.iter() {
        let mut places: Vec<usize> = Vec::new();
        let mut positions: Vec<u16> = Vec::new();
        for (new, old) in columns.iter().enumerate() {
            if let Some(place) = part.columns.iter().position(|column| column == old) {
                places.push(place);
                positions.push(new as u16);
            }
        }
        if places.is_empty() {
            continue;
        }
        if places.len() == part.table.arity {
            let mut mapped = vec![0u16; places.len()];
            for (place, position) in places.iter().zip(&positions) {
                mapped[*place] = *position;
            }
            out.push(Part { table: part.table.clone(), columns: mapped.into_boxed_slice() });
        } else {
            let mut cells = Vec::with_capacity(part.table.len * places.len());
            for row in part.table.rows() {
                cells.extend(places.iter().map(|at| row[*at]));
            }
            out.push(Part { table: Table::distinct(places.len(), cells), columns: positions.into_boxed_slice() });
        }
    }
    Val::of_parts(out)
}

pub(crate) fn holds(op: Op, a: Cell, b: Cell) -> bool {
    match op {
        Op::Eq => a == b,
        Op::Ne => a != b,
        Op::Lt => (a as i32) < (b as i32),
        Op::Le => (a as i32) <= (b as i32),
        Op::Gt => (a as i32) > (b as i32),
        Op::Ge => (a as i32) >= (b as i32),
    }
}

pub(crate) fn select(value: &Val, at: u16, op: Op, other: Option<u16>, drop: Option<u16>) -> Option<Val> {
    let Val::Rows(parts) = value else { return Some(value.clone()) };
    let mut positions = vec![at];
    positions.extend(other);
    let (touched, rest) = split_parts(parts, &positions);
    // A comparison of a column of one part with a column of another reads the pairs of rows that pass, and never writes the product of the two parts.
    if let ([first, second], Some(other)) = (&touched[..], other) {
        let (from, to) = if first.columns.contains(&at) { (*first, *second) } else { (*second, *first) };
        return select_across(from, to, rest, at, op, other, drop);
    }
    let merged = touched_rows(&touched, Bound::SelectSide)?;
    let place_of = |position: u16| merged.columns.iter().position(|column| *column == position).expect("a selected column stands in a touched part");
    let a = place_of(at);
    let b = other.map(place_of);
    let width = merged.columns.len();
    let drop_place = drop.map(place_of);
    let kept_width = width - usize::from(drop_place.is_some());
    let mut cells: Vec<Cell> = Vec::with_capacity(merged.cells.len());
    for row in merged.cells.chunks_exact(width) {
        let second = b.map_or(0, |b| row[b]);
        if holds(op, row[a], second) {
            match drop_place {
                None => cells.extend_from_slice(row),
                Some(dropped) => {
                    cells.extend_from_slice(&row[..dropped]);
                    cells.extend_from_slice(&row[dropped + 1..]);
                }
            }
        }
    }
    if cells.is_empty() && kept_width > 0 {
        return Some(Val::Empty);
    }
    let shifted = |position: u16| drop.map_or(position, |dropped| if position > dropped { position - 1 } else { position });
    let mut out: Vec<Part> = rest.into_iter().map(|part| Part { columns: part.columns.iter().map(|column| shifted(*column)).collect(), table: part.table }).collect();
    if kept_width == 0 {
        // No column remains: the part held the dropped column alone.
        let any = merged.cells.chunks_exact(width).any(|row| holds(op, row[a], b.map_or(0, |b| row[b])));
        if !any {
            return Some(Val::Empty);
        }
        return Some(Val::of_parts(out));
    }
    let columns: Vec<u16> = merged.columns.iter().enumerate().filter(|(place, _)| Some(*place) != drop_place).map(|(_, column)| shifted(*column)).collect();
    out.push(Part { table: Table::new(kept_width, cells), columns: columns.into_boxed_slice() });
    Some(Val::of_parts(out))
}

/// A `select` that compares the column `at` of the part `from` with the column `other` of the part `to`. An equality that drops `other`, over two parts and no others, is the join of the two, which stands as its sides. Any other comparison gives one part with the pairs of rows that pass, beside the parts of `rest`. Where those pairs pass `CELL_CAP` cells, they are the rows of the step and a bound stops it.
fn select_across(from: &Part, to: &Part, rest: Vec<Part>, at: u16, op: Op, other: u16, drop: Option<u16>) -> Option<Val> {
    let a_place = from.columns.iter().position(|column| *column == at).expect("a selected column stands in its part");
    let b_place = to.columns.iter().position(|column| *column == other).expect("a selected column stands in its part");
    let shifted = |position: u16| drop.map_or(position, |dropped| if position > dropped { position - 1 } else { position });
    if op == Op::Eq && drop == Some(other) && rest.is_empty() {
        let left_out: Vec<u16> = from.columns.iter().map(|column| shifted(*column)).collect();
        let right_out: Vec<u16> = to.columns.iter().map(|column| shifted(*column)).collect();
        if let Some(value) = crate::joined::Joined::across(from.table.clone(), &left_out, to.table.clone(), &right_out, a_place, b_place) {
            return Some(value);
        }
    }
    // The rows of `to` in order of the compared column, as a signed number, so that the rows that one row of `from` passes stand in at most two runs. Rows of one value keep their order.
    let (a_arity, b_arity) = (from.table.arity, to.table.arity);
    let mut order: Vec<u32> = (0..to.table.len as u32).collect();
    order.sort_by_key(|row| to.table.cells[*row as usize * b_arity + b_place] as i32);
    let sorted: Vec<i32> = order.iter().map(|row| to.table.cells[*row as usize * b_arity + b_place] as i32).collect();
    let end = sorted.len();
    let runs = |value: Cell| -> [(usize, usize); 2] {
        let value = value as i32;
        let lower = sorted.partition_point(|own| *own < value);
        let upper = sorted.partition_point(|own| *own <= value);
        match op {
            Op::Eq => [(lower, upper), (0, 0)],
            Op::Ne => [(0, lower), (upper, end)],
            Op::Lt => [(upper, end), (0, 0)],
            Op::Le => [(lower, end), (0, 0)],
            Op::Gt => [(0, lower), (0, 0)],
            Op::Ge => [(0, upper), (0, 0)],
        }
    };
    let all_columns: Vec<u16> = from.columns.iter().chain(to.columns.iter()).copied().collect();
    let kept_places: Vec<usize> = (0..all_columns.len()).filter(|place| Some(all_columns[*place]) != drop).collect();
    let width = kept_places.len();
    let pairs: u64 = from.table.rows().map(|row| runs(row[a_place]).iter().map(|(start, stop)| (stop - start) as u64).sum::<u64>()).sum();
    if pairs.saturating_mul(width as u64) > CELL_CAP as u64 {
        crate::bounds::mark(Bound::SelectSide);
        return None;
    }
    if pairs == 0 {
        return Some(Val::Empty);
    }
    let mut cells: Vec<Cell> = Vec::with_capacity(pairs as usize * width);
    let mut pair: Vec<Cell> = vec![0; all_columns.len()];
    for row in from.table.rows() {
        pair[..a_arity].copy_from_slice(row);
        for (start, stop) in runs(row[a_place]) {
            for at_sorted in start..stop {
                let own = order[at_sorted] as usize;
                pair[a_arity..].copy_from_slice(&to.table.cells[own * b_arity..(own + 1) * b_arity]);
                cells.extend(kept_places.iter().map(|place| pair[*place]));
            }
        }
    }
    let columns: Vec<u16> = kept_places.iter().map(|place| shifted(all_columns[*place])).collect();
    let mut out: Vec<Part> = rest.into_iter().map(|part| Part { columns: part.columns.iter().map(|column| shifted(*column)).collect(), table: part.table }).collect();
    out.push(Part { table: Table::new(width, cells), columns: columns.into_boxed_slice() });
    Some(Val::of_parts(out))
}

/// How many rows of a table hold each key.
pub struct Histogram {
    index: KeyIndex,
    counts: Vec<u32>,
}

impl Histogram {
    fn get(&self, key: u64) -> Option<u32> {
        self.index.get(key).map(|id| self.counts[id as usize])
    }
}

/// A hash table from 64-bit keys to dense ids in order of first appearance.
pub struct KeyIndex {
    /// Each slot holds a key and then its id plus one, where 0 is an empty slot.
    slots: Vec<u64>,
    shift: u32,
}

impl KeyIndex {
    /// The index of `keys`, and the id of each key.
    pub(crate) fn of(keys: &[u64]) -> (KeyIndex, Vec<u32>) {
        let capacity = (2 * keys.len()).next_power_of_two().max(16);
        let mut index = KeyIndex { slots: vec![0; 2 * capacity], shift: 64 - capacity.trailing_zeros() };
        let mut ids = Vec::with_capacity(keys.len());
        let mut next = 0u32;
        for key in keys {
            let mut at = index.start(*key);
            loop {
                let held = index.slots[2 * at + 1];
                if held == 0 {
                    index.slots[2 * at] = *key;
                    index.slots[2 * at + 1] = u64::from(next) + 1;
                    ids.push(next);
                    next += 1;
                    break;
                }
                if index.slots[2 * at] == *key {
                    ids.push((held - 1) as u32);
                    break;
                }
                at = (at + 1) & (index.slots.len() / 2 - 1);
            }
        }
        (index, ids)
    }

    /// The cells of 32 bits that the slots hold.
    pub(crate) fn cells(&self) -> usize {
        self.slots.len() * 2
    }

    #[inline]
    fn start(&self, key: u64) -> usize {
        (key.wrapping_mul(0x9E37_79B9_7F4A_7C15) >> self.shift) as usize
    }

    #[inline]
    pub(crate) fn get(&self, key: u64) -> Option<u32> {
        let mut at = self.start(key);
        loop {
            let held = self.slots[2 * at + 1];
            if held == 0 {
                return None;
            }
            if self.slots[2 * at] == key {
                return Some((held - 1) as u32);
            }
            at = (at + 1) & (self.slots.len() / 2 - 1);
        }
    }
}

/// A 64-bit key of the values of `row` at `at`: the cells themselves for up to two columns, and a hash of them past that.
#[inline]
pub fn row_word(row: &[Cell], at: &[u16]) -> u64 {
    match at {
        [one] => u64::from(row[usize::from(*one)]),
        [one, two] => (u64::from(row[usize::from(*one)]) << 32) | u64::from(row[usize::from(*two)]),
        _ => hash_words(at.iter().map(|column| u64::from(row[usize::from(*column)]))) as u64,
    }
}

fn join(left: &Val, right: &Val, left_at: &[u16], right_at: &[u16], kept: &[u16], left_arity: u16) -> Option<Val> {
    let (Val::Rows(left_parts), Val::Rows(right_parts)) = (left, right) else { return Some(Val::Empty) };
    let right_new = |position: u16| kept.iter().position(|column| *column == position).map(|at| left_arity + at as u16);
    if left_at.is_empty() {
        let mut out: Vec<Part> = left_parts.as_ref().clone();
        for part in right_parts.iter() {
            out.push(Part { table: part.table.clone(), columns: part.columns.iter().map(|column| right_new(*column).expect("a column with no pair is kept")).collect() });
        }
        return Some(Val::of_parts(out));
    }
    let (left_touched, left_rest) = split_parts(left_parts, left_at);
    let (right_touched, right_rest) = split_parts(right_parts, right_at);
    // Two columns that share no value join on no row.
    for (l, r) in left_at.iter().zip(right_at) {
        let mask = |parts: &[&Part], at: u16| parts.iter().find_map(|part| part.columns.iter().position(|column| *column == at).map(|place| part.table.mask(place)));
        if let (Some(a), Some(b)) = (mask(&left_touched, *l), mask(&right_touched, *r)) {
            if a & b == 0 {
                return Some(Val::Empty);
            }
        }
    }
    // Paired columns in several parts of a side join those parts one at a time, so no product of parts is written.
    if left_touched.len() > 1 || right_touched.len() > 1 {
        return join_parts(&left_touched, left_rest, &right_touched, right_rest, left_at, right_at, kept, left_arity);
    }
    let tl = touched_rows(&left_touched, Bound::JoinSide)?;
    let tr = touched_rows(&right_touched, Bound::JoinSide)?;
    // Where every part is read, the rows stand as the two sides until an operator needs them.
    if left_rest.is_empty() && right_rest.is_empty() {
        let (left_table, right_table) = (side_table(&left_touched, &tl), side_table(&right_touched, &tr));
        if let Some(value) = crate::joined::Joined::of(left_table, tl.columns.clone(), right_table, tr.columns.clone(), left_at, right_at, kept, left_arity) {
            return Some(value);
        }
    }
    let left_places: Vec<usize> = left_at.iter().map(|at| tl.columns.iter().position(|column| column == at).expect("a paired column")).collect();
    let right_places: Vec<usize> = right_at.iter().map(|at| tr.columns.iter().position(|column| column == at).expect("a paired column")).collect();
    let right_kept: Vec<usize> = (0..tr.columns.len()).filter(|place| !right_places.contains(place)).collect();
    let left_width = tl.columns.len();
    let right_width = tr.columns.len();
    let width = left_width + right_kept.len();
    // The right rows by their key.
    let right_keys: Vec<u64> = tr.cells.chunks_exact(right_width).map(|row| key_word(row, &right_places)).collect();
    let (index, key_of_row) = KeyIndex::of(&right_keys);
    // The rows of each key, in the order the right rows stand.
    let mut starts: Vec<u32> = vec![0; key_of_row.iter().max().map_or(0, |last| *last as usize + 1) + 1];
    for key in &key_of_row {
        starts[*key as usize + 1] += 1;
    }
    for at in 1..starts.len() {
        starts[at] += starts[at - 1];
    }
    let mut next = starts.clone();
    let mut rows_of_key: Vec<u32> = vec![0; key_of_row.len()];
    for (row, key) in key_of_row.iter().enumerate() {
        rows_of_key[next[*key as usize] as usize] = row as u32;
        next[*key as usize] += 1;
    }
    let mut cells: Vec<Cell> = Vec::new();
    for row in tl.cells.chunks_exact(left_width) {
        if let Some(key) = index.get(key_word(row, &left_places)) {
            for at in &rows_of_key[starts[key as usize] as usize..starts[key as usize + 1] as usize] {
                let other = &tr.cells[*at as usize * right_width..(*at as usize + 1) * right_width];
                cells.extend_from_slice(row);
                cells.extend(right_kept.iter().map(|place| other[*place]));
            }
        }
        if cells.len() > CELL_CAP {
            crate::bounds::mark(Bound::JoinOutput);
            return None;
        }
    }
    if cells.is_empty() {
        return Some(Val::Empty);
    }
    let mut columns: Vec<u16> = tl.columns.clone();
    columns.extend(right_kept.iter().map(|place| right_new(tr.columns[*place]).expect("a column with no pair is kept")));
    let mut out = left_rest;
    for part in right_rest {
        out.push(Part { columns: part.columns.iter().map(|column| right_new(*column).expect("a column with no pair is kept")).collect(), table: part.table });
    }
    out.push(Part { table: Table::new(width, cells), columns: columns.into_boxed_slice() });
    Some(Val::of_parts(out))
}

/// The tag of a right column among the tags of the columns of a join in progress, which tell the two sides' columns apart.
const RIGHT_TAG: u32 = 1 << 16;

/// A link of a `join` in progress: a pair of columns, as the left node and the place in it, and the right node and the place in it.
type Link = (usize, usize, usize, usize);

/// The rows of a table by the id of their key: the first position of each id's rows in the list, and the list, which holds the rows of an id in order.
fn rows_by_key(ids: &[u32]) -> (Vec<u32>, Vec<u32>) {
    let mut starts: Vec<u32> = vec![0; ids.iter().max().map_or(0, |last| *last as usize + 1) + 1];
    for id in ids {
        starts[*id as usize + 1] += 1;
    }
    for at in 1..starts.len() {
        starts[at] += starts[at - 1];
    }
    let mut next = starts.clone();
    let mut rows: Vec<u32> = vec![0; ids.len()];
    for (row, id) in ids.iter().enumerate() {
        rows[next[*id as usize] as usize] = row as u32;
        next[*id as usize] += 1;
    }
    (starts, rows)
}

/// A `join` whose paired columns lie in several parts of a side. Each touched part is a node, and each pair joins a node of the left to a node of the right. The nodes that the pairs connect make one part of the result, joined one node at a time; the other parts stay factors. Where a joined part passes `CELL_CAP` cells, a bound stops it.
#[allow(clippy::too_many_arguments)]
fn join_parts(left_touched: &[&Part], left_rest: Vec<Part>, right_touched: &[&Part], right_rest: Vec<Part>, left_at: &[u16], right_at: &[u16], kept: &[u16], left_arity: u16) -> Option<Val> {
    let right_new = |position: u16| kept.iter().position(|column| *column == position).map(|at| left_arity + at as u16).expect("a column with no pair is kept");
    let nodes: Vec<(&Part, u32)> = left_touched.iter().map(|part| (*part, 0u32)).chain(right_touched.iter().map(|part| (*part, RIGHT_TAG))).collect();
    let node_of = |side: u32, position: u16| nodes.iter().position(|(part, own)| *own == side && part.columns.contains(&position)).expect("a paired column stands in a touched part");
    let place_in = |node: usize, position: u16| nodes[node].0.columns.iter().position(|column| *column == position).expect("a paired column stands in its part");
    let links: Vec<Link> = left_at
        .iter()
        .zip(right_at)
        .map(|(l, r)| {
            let (a, b) = (node_of(0, *l), node_of(RIGHT_TAG, *r));
            (a, place_in(a, *l), b, place_in(b, *r))
        })
        .collect();
    // Each node takes the smallest number of a node it is linked to, until the nodes of a part of the result share one.
    let mut group: Vec<usize> = (0..nodes.len()).collect();
    loop {
        let mut changed = false;
        for (a, _, b, _) in &links {
            let low = group[*a].min(group[*b]);
            for node in [*a, *b] {
                if group[node] != low {
                    group[node] = low;
                    changed = true;
                }
            }
        }
        if !changed {
            break;
        }
    }
    let mut out: Vec<Part> = left_rest;
    for part in right_rest {
        out.push(Part { columns: part.columns.iter().map(|column| right_new(*column)).collect(), table: part.table });
    }
    let mut labels: Vec<usize> = group.clone();
    labels.sort_unstable();
    labels.dedup();
    for label in labels {
        let members: Vec<usize> = (0..nodes.len()).filter(|node| group[*node] == label).collect();
        match join_nodes(&nodes, &members, &links, right_at, &right_new)? {
            Some(part) => out.push(part),
            None => return Some(Val::Empty),
        }
    }
    Some(Val::of_parts(out))
}

/// The part that joins the `members` among `nodes` on the `links` between them: no part where no row joins, and `None` where a bound stops it. It starts at the smallest node and takes in the smallest node linked to those it has, with every link between the two as the key.
fn join_nodes(nodes: &[(&Part, u32)], members: &[usize], links: &[Link], right_at: &[u16], right_new: &dyn Fn(u16) -> u16) -> Option<Option<Part>> {
    let mut joined: Vec<usize> = Vec::new();
    let mut tags: Vec<u32> = Vec::new();
    let mut cells: Vec<Cell> = Vec::new();
    let mut remaining: Vec<usize> = members.to_vec();
    while !remaining.is_empty() {
        let linked = |node: usize| links.iter().any(|(a, _, b, _)| (*a == node && joined.contains(b)) || (*b == node && joined.contains(a)));
        let (at, node) = remaining.iter().copied().enumerate().filter(|(_, node)| joined.is_empty() || linked(*node)).min_by_key(|(_, node)| nodes[*node].0.table.len).expect("the nodes of a part of the result are linked");
        remaining.swap_remove(at);
        let (part, side) = nodes[node];
        if joined.is_empty() {
            tags = part.columns.iter().map(|column| side | u32::from(*column)).collect();
            cells = part.table.cells.to_vec();
        } else {
            // The places of the key in the rows so far, and in this node's rows.
            let (mut have, mut own): (Vec<usize>, Vec<usize>) = (Vec::new(), Vec::new());
            for (a, a_place, b, b_place) in links {
                let (other, mine, theirs) = if *a == node && joined.contains(b) {
                    (*b, *a_place, *b_place)
                } else if *b == node && joined.contains(a) {
                    (*a, *b_place, *a_place)
                } else {
                    continue;
                };
                let tag = nodes[other].1 | u32::from(nodes[other].0.columns[theirs]);
                have.push(tags.iter().position(|own_tag| *own_tag == tag).expect("a column of a joined node stands in the rows so far"));
                own.push(mine);
            }
            let width = tags.len();
            let arity = part.table.arity;
            let keys: Vec<u64> = part.table.rows().map(|row| key_word(row, &own)).collect();
            let (index, ids) = KeyIndex::of(&keys);
            let (starts, by_key) = rows_by_key(&ids);
            let mut next: Vec<Cell> = Vec::new();
            for row in cells.chunks_exact(width) {
                if let Some(key) = index.get(key_word(row, &have)) {
                    for at in &by_key[starts[key as usize] as usize..starts[key as usize + 1] as usize] {
                        next.extend_from_slice(row);
                        next.extend_from_slice(&part.table.cells[*at as usize * arity..(*at as usize + 1) * arity]);
                    }
                }
                if next.len() > CELL_CAP {
                    crate::bounds::mark(Bound::JoinOutput);
                    return None;
                }
            }
            cells = next;
            tags.extend(part.columns.iter().map(|column| side | u32::from(*column)));
        }
        if cells.is_empty() {
            return Some(None);
        }
        joined.push(node);
    }
    // A paired column of the right holds the value of the left column it pairs with, so it is left out.
    let keep: Vec<(usize, u16)> = tags
        .iter()
        .enumerate()
        .filter_map(|(place, tag)| {
            let position = (tag & (RIGHT_TAG - 1)) as u16;
            if tag & RIGHT_TAG == 0 {
                Some((place, position))
            } else if right_at.contains(&position) {
                None
            } else {
                Some((place, right_new(position)))
            }
        })
        .collect();
    let width = tags.len();
    let mut out: Vec<Cell> = Vec::with_capacity(cells.len() / width * keep.len());
    for row in cells.chunks_exact(width) {
        out.extend(keep.iter().map(|(place, _)| row[*place]));
    }
    Some(Some(Part { table: Table::new(keep.len(), out), columns: keep.iter().map(|(_, position)| *position).collect() }))
}

/// Whether the key of each row of `table` at `at` is among `keys`, which stand sorted. A key at one column is read once per distinct value of the column.
fn rows_in(table: &Table, at: &[u16], keys: &[u64]) -> Vec<bool> {
    if table.arity == 0 {
        return Vec::new();
    }
    if let [one] = at {
        let place = usize::from(*one);
        let grouping = table.column_grouping(place);
        let present: Vec<bool> = grouping.1.iter().map(|first| keys.binary_search(&u64::from(table.cells[*first as usize * table.arity + place])).is_ok()).collect();
        return grouping.0.iter().map(|id| present[*id as usize]).collect();
    }
    table.rows().map(|row| keys.binary_search(&row_word(row, at)).is_ok()).collect()
}

pub(crate) fn semijoin(left: &Val, right: &Val, left_at: &[u16], right_at: &[u16]) -> Option<Val> {
    if matches!(left, Val::Empty) || matches!(right, Val::Empty) {
        return Some(Val::Empty);
    }
    let table = crate::gen_parts::flat(left)?;
    let keys = crate::gen_parts::keys_of(right, right_at)?;
    let held = rows_in(&table, left_at, &keys);
    if held.iter().all(|kept| *kept) {
        return Some(left.clone());
    }
    let mut cells = Vec::with_capacity(table.cells.len());
    for (row, kept) in table.rows().zip(&held) {
        if *kept {
            cells.extend_from_slice(row);
        }
    }
    Some(Val::of_table(Table::new(table.arity, cells)))
}

pub(crate) fn all(domain: &Val, body: &Val, left_at: &[u16], right_at: &[u16], outer: &[u16]) -> Option<Val> {
    if matches!(domain, Val::Empty) {
        return Some(Val::Empty);
    }
    let table = crate::gen_parts::flat(domain)?;
    let keys = if matches!(body, Val::Empty) { Arc::new(Vec::new()) } else { crate::gen_parts::keys_of(body, right_at)? };
    let held = rows_in(&table, left_at, &keys);
    if outer.is_empty() {
        return Some(if held.iter().any(|kept| !*kept) { Val::Empty } else { Val::of_table(Table::unit(true)) });
    }
    // A value of the outer column stays where every row at it has its key.
    let at = usize::from(outer[0]);
    let grouping = table.column_grouping(at);
    let mut fails = vec![false; grouping.1.len()];
    for (id, kept) in grouping.0.iter().zip(&held) {
        fails[*id as usize] |= !*kept;
    }
    let mut out: Vec<Cell> = grouping.1.iter().zip(&fails).filter(|(_, fails)| !**fails).map(|(first, _)| table.cells[*first as usize * table.arity + at]).collect();
    out.sort_unstable();
    Some(Val::of_table(Table::new(1, out)))
}

pub(crate) fn antijoin(left: &Val, right: &Val, left_at: &[u16], right_at: &[u16]) -> Option<Val> {
    let Val::Rows(left_parts) = left else { return Some(Val::Empty) };
    let Val::Rows(right_parts) = right else { return Some(left.clone()) };
    if left_at.is_empty() {
        return Some(Val::Empty);
    }
    let (left_touched, left_rest) = split_parts(left_parts, left_at);
    let (right_touched, _) = split_parts(right_parts, right_at);
    // One part of the left is read in place. Paired columns in several parts of the left make the rows of their product the rows to keep from, which a bound limits.
    let tl = touched_rows(&left_touched, Bound::AntijoinSide)?;
    let left_places: Vec<usize> = left_at.iter().map(|at| tl.columns.iter().position(|column| column == at).expect("a paired column")).collect();
    // The right holds a key when each of its touched parts holds the piece of the key at its own paired columns, since the parts are independent. Each part gives the places of its piece in a left row, and the pieces that it holds.
    let mut tests: Vec<(Vec<usize>, Vec<u64>)> = Vec::new();
    for part in &right_touched {
        let slots: Vec<usize> = (0..right_at.len()).filter(|slot| part.columns.contains(&right_at[*slot])).collect();
        let own: Vec<usize> = slots.iter().map(|slot| part.columns.iter().position(|column| *column == right_at[*slot]).expect("a paired column")).collect();
        let mut keys: Vec<u64> = part.table.rows().map(|row| key_word(row, &own)).collect();
        keys.sort_unstable();
        keys.dedup();
        tests.push((slots.iter().map(|slot| left_places[*slot]).collect(), keys));
    }
    let width = tl.columns.len();
    let mut cells: Vec<Cell> = Vec::with_capacity(tl.cells.len());
    for row in tl.cells.chunks_exact(width) {
        if !tests.iter().all(|(places, keys)| keys.binary_search(&key_word(row, places)).is_ok()) {
            cells.extend_from_slice(row);
        }
    }
    if cells.is_empty() {
        return Some(Val::Empty);
    }
    let mut out = left_rest;
    out.push(Part { table: Table::new(width, cells), columns: tl.columns.into_boxed_slice() });
    Some(Val::of_parts(out))
}

fn union(left: &Val, right: &Val, map: &[Option<u16>]) -> Option<Val> {
    let width = map.len();
    let mut cells: Vec<Cell> = Vec::new();
    if let Val::Rows(_) = left {
        let Some(rows) = left.rows(width, CELL_CAP / width.max(1)) else {
            crate::bounds::mark(Bound::Union);
            return None;
        };
        for row in rows {
            cells.extend_from_slice(&row);
        }
    }
    if let Val::Rows(parts) = right {
        let arity = parts.iter().flat_map(|part| part.columns.iter()).map(|column| usize::from(*column) + 1).max().unwrap_or(0);
        let Some(rows) = right.rows(arity, CELL_CAP / width.max(1)) else {
            crate::bounds::mark(Bound::Union);
            return None;
        };
        for row in rows {
            cells.extend(map.iter().map(|at| at.map_or(0, |at| row[usize::from(at)])));
        }
    }
    if cells.len() > CELL_CAP {
        crate::bounds::mark(Bound::Union);
        return None;
    }
    if cells.is_empty() {
        return Some(Val::Empty);
    }
    Some(Val::of_table(Table::distinct(width, cells)))
}
