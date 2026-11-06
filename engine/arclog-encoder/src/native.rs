//! The operators of the grammar over materialized rows: a faster evaluation of
//! what an expression's forms compute, which `walk` checks against those forms
//! through the engine's evaluator.
//!
//! A value is a product of parts, as the engine's relations are, so a `join` with
//! no column pair costs nothing, and an operator merges only the parts it reads.
//! An empty relation has no parts to read, and each operator states what it gives
//! on one: most give an empty relation, `antijoin` with an empty right side gives
//! its left, and a component runs on its empty input.

use std::collections::HashMap;
use std::hash::{BuildHasherDefault, Hasher};
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

use crate::expression::Op;

pub type Cell = u32;

/// The most cells that a materialized table holds; a larger one stops, which
/// gives no value.
pub const CELL_CAP: usize = 1 << 21;

/// A hasher for keys that are already well mixed or small.
#[derive(Default, Clone, Copy)]
pub struct FastHasher(u64);

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

pub type FastMap<K, V> = HashMap<K, V, BuildHasherDefault<FastHasher>>;

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

/// A set of rows of one arity. Its hash depends on the set alone.
#[derive(Debug)]
pub struct Table {
    pub arity: usize,
    pub len: usize,
    pub cells: Box<[Cell]>,
    pub hash: u128,
    /// For each column, a 64-bit filter of its values: two columns whose filters
    /// share no bit share no value.
    masks: std::sync::OnceLock<Box<[u64]>>,
}

impl Table {
    /// The table of `cells`, whose rows are distinct.
    pub fn new(arity: usize, cells: Vec<Cell>) -> Arc<Table> {
        let len = cells.len().checked_div(arity).unwrap_or(0);
        let mut hash = 0u128;
        if arity > 0 {
            for row in cells.chunks_exact(arity) {
                hash = hash.wrapping_add(hash_row(row));
            }
        }
        hash = hash.wrapping_add(hash_words([arity as u64, len as u64]));
        Arc::new(Table { arity, len, cells: cells.into_boxed_slice(), hash, masks: std::sync::OnceLock::new() })
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

    /// The table of `cells`, whose rows may repeat.
    pub fn distinct(arity: usize, cells: Vec<Cell>) -> Arc<Table> {
        Table::new(arity, distinct_rows(arity, cells))
    }

    /// The table of no columns, with one row where `holds`.
    pub fn unit(holds: bool) -> Arc<Table> {
        let len = usize::from(holds);
        Arc::new(Table { arity: 0, len, cells: Box::new([]), hash: hash_words([0, len as u64]), masks: std::sync::OnceLock::new() })
    }

    pub fn rows(&self) -> impl Iterator<Item = &[Cell]> {
        self.cells.chunks_exact(self.arity.max(1))
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
}

impl Val {
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

    /// A hash of what the value holds, where each factor counts.
    pub fn hash(&self) -> u128 {
        match self {
            Val::None => 1,
            Val::Empty => 2,
            Val::Rows(parts) => {
                let mut hash = hash_words([parts.len() as u64 + 3]);
                for part in parts.iter() {
                    let columns = hash_words(part.columns.iter().map(|column| u64::from(*column)));
                    hash = hash.wrapping_add(hash_words([part.table.hash as u64, (part.table.hash >> 64) as u64, columns as u64, (columns >> 64) as u64]));
                }
                hash
            }
        }
    }

    /// The rows, each in the order of the value's columns; `None` past `cap`.
    pub fn rows(&self, arity: usize, cap: usize) -> Option<Vec<Vec<Cell>>> {
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
#[derive(Clone, Debug)]
pub enum Step {
    Project { columns: Box<[u16]> },
    Select { at: u16, op: Op, other: Option<u16>, drop: Option<u16> },
    Join { left: Box<[u16]>, right: Box<[u16]>, kept: Box<[u16]>, left_arity: u16 },
    Antijoin { left: Box<[u16]>, right: Box<[u16]> },
    Semijoin { left: Box<[u16]>, right: Box<[u16]> },
    /// The outer columns' values at which the first relation has a row, and each of its rows
    /// there has a match in the second. With no outer column, a relation of no columns.
    All { left: Box<[u16]>, right: Box<[u16]>, outer: Box<[u16]> },
    Part(Box<crate::gen_parts::PartStep>),
    Union { map: Box<[Option<u16>]> },
    LibJoin { relation: u32, bound: Box<[Option<u16>]>, left_arity: u16 },
    Component { instance: u32, port: u16 },
}

impl Step {
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
    histograms: FastMap<(u128, u64), Arc<FastMap<u64, u32>>>,
    /// The operators a count answered, and those that built their rows.
    pub counted: u64,
    pub built: u64,
}

/// The most cells of component outputs that an evaluation keeps for a later hit.
const HELD_OUTPUT_CELLS: usize = 1 << 22;

impl<'a> Evaluator<'a> {
    pub fn new(shapes: &'a [CompShape], instances: &'a [CompInstance], libs: &'a [LibRelation], session: TaskSession) -> Self {
        Evaluator { shapes, instances, libs, registry: Registry::get(), session, limits: Limits::new(None, Cancellation::default()), lib_rows: FastMap::default(), outputs: FastMap::default(), output_cells: 0, names: FastMap::default(), sums: FastMap::default(), runs: [0; 3], shape_time: FastMap::default(), distinct_counts: FastMap::default(), histograms: FastMap::default(), counted: 0, built: 0 }
    }

    /// The value of `step` on `children`.
    pub fn apply(&mut self, step: &Step, children: &[&Val]) -> Val {
        if children.iter().any(|child| matches!(child, Val::None)) {
            return Val::None;
        }
        match step {
            Step::Project { columns } => project(children[0], columns),
            Step::Select { at, op, other, drop } => select(children[0], *at, *op, *other, *drop).unwrap_or(Val::None),
            Step::Join { left, right, kept, left_arity } => join(children[0], children[1], left, right, kept, *left_arity).unwrap_or(Val::None),
            Step::Antijoin { left, right } => antijoin(children[0], children[1], left, right).unwrap_or(Val::None),
            Step::Semijoin { left, right } => semijoin(children[0], children[1], left, right).unwrap_or(Val::None),
            Step::All { left, right, outer } => all(children[0], children[1], left, right, outer).unwrap_or(Val::None),
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
                                part.table.rows().map(|row| histogram.get(&u64::from(row[a])).copied().map_or(0, u64::from)).sum()
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
                if l_places.iter().zip(&r_places).any(|(a, b)| l.table.mask(*a) & r.table.mask(*b) == 0) {
                    return Some(Some(0));
                }
                let histogram = self.histogram(&r.table, &r_places);
                let mut matched = 0u64;
                for row in l.table.rows() {
                    if let Some(count) = histogram.get(&key_word(row, &l_places)) {
                        matched += u64::from(*count);
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
                if l_places.iter().zip(&r_places).any(|(a, b)| l.table.mask(*a) & r.table.mask(*b) == 0) {
                    return Some(Some(product(&every)));
                }
                let histogram = self.histogram(&r.table, &r_places);
                let mut kept = 0u64;
                for row in l.table.rows() {
                    if !histogram.contains_key(&key_word(row, &l_places)) {
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
        if let Some(found) = self.distinct_counts.get(&(table.hash, word)) {
            return *found;
        }
        let mut keys: Vec<u64> = table.rows().map(|row| key_word(row, places)).collect();
        keys.sort_unstable();
        keys.dedup();
        let count = keys.len() as u64;
        self.distinct_counts.insert((table.hash, word), count);
        count
    }

    /// How many rows of `table` hold each key at `places`.
    fn histogram(&mut self, table: &Table, places: &[usize]) -> Arc<FastMap<u64, u32>> {
        let word = hash_words(places.iter().map(|place| *place as u64)) as u64;
        if let Some(found) = self.histograms.get(&(table.hash, word)) {
            return found.clone();
        }
        let mut counts: FastMap<u64, u32> = FastMap::default();
        for row in table.rows() {
            *counts.entry(key_word(row, places)).or_default() += 1;
        }
        let counts = Arc::new(counts);
        if self.histograms.len() > 1 << 16 {
            self.histograms.clear();
        }
        self.histograms.insert((table.hash, word), counts.clone());
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
        let Some(merged) = merge(&touched) else { return Val::None };
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
        let total = factors.iter().try_fold(1usize, |total, (held, cells)| total.checked_mul(cells.len() / held.len().max(1)))?;
        if total.checked_mul(width)? > CELL_CAP {
            return None;
        }
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
            key[at] = table.hash;
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
            let key = (table.hash, word);
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
        match value {
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
fn key_word(row: &[Cell], places: &[usize]) -> u64 {
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
fn fast_component(shape: &CompShape, tables: &[Arc<Table>]) -> Option<Outputs> {
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
            for (key, count) in &counts {
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
            for (key, count) in &counts {
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
            let counts = |held: &Option<(&Arc<Table>, bool)>| -> Option<(FastMap<Vec<Cell>, u32>, u32)> {
                match held {
                    Some((table, true)) => Some((key_counts(table, key_width).into_iter().map(|(key, count)| (key.to_vec(), count)).collect(), 0)),
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
            for key in plus_keys.keys() {
                emit(key);
            }
            for key in minus_keys.keys() {
                if !plus_keys.contains_key(key) {
                    emit(key);
                }
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
            for ((observed_key, pattern_key), count) in &shared {
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
struct Merged {
    columns: Vec<u16>,
    cells: Vec<Cell>,
}

/// The product of `parts`, or `None` past the cap.
fn merge(parts: &[&Part]) -> Option<Merged> {
    let columns: Vec<u16> = parts.iter().flat_map(|part| part.columns.iter().copied()).collect();
    let total = parts.iter().try_fold(1usize, |total, part| total.checked_mul(part.table.len))?;
    if parts.is_empty() {
        return Some(Merged { columns, cells: Vec::new() });
    }
    if total.checked_mul(columns.len())? > CELL_CAP {
        return None;
    }
    if let [one] = parts {
        return Some(Merged { columns, cells: one.table.cells.to_vec() });
    }
    let width = columns.len();
    let mut cells: Vec<Cell> = vec![0; total * width];
    let mut repeat = 1usize;
    let mut offset = 0usize;
    for part in parts {
        let arity = part.table.arity;
        let rows = part.table.len;
        for row in 0..total {
            let own = (row / repeat) % rows;
            cells[row * width + offset..row * width + offset + arity].copy_from_slice(&part.table.cells[own * arity..(own + 1) * arity]);
        }
        repeat *= rows;
        offset += arity;
    }
    Some(Merged { columns, cells })
}

fn project(value: &Val, columns: &[u16]) -> Val {
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

fn holds(op: Op, a: Cell, b: Cell) -> bool {
    match op {
        Op::Eq => a == b,
        Op::Ne => a != b,
        Op::Lt => (a as i32) < (b as i32),
        Op::Le => (a as i32) <= (b as i32),
        Op::Gt => (a as i32) > (b as i32),
        Op::Ge => (a as i32) >= (b as i32),
    }
}

fn select(value: &Val, at: u16, op: Op, other: Option<u16>, drop: Option<u16>) -> Option<Val> {
    let Val::Rows(parts) = value else { return Some(value.clone()) };
    let mut positions = vec![at];
    positions.extend(other);
    let (touched, rest) = split_parts(parts, &positions);
    let merged = merge(&touched)?;
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

/// The hash of the values of `row` at `places`.
fn key_hash(row: &[Cell], places: &[usize]) -> u128 {
    hash_words(places.iter().map(|place| u64::from(row[*place])))
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
    let tl = merge(&left_touched)?;
    let tr = merge(&right_touched)?;
    let left_places: Vec<usize> = left_at.iter().map(|at| tl.columns.iter().position(|column| column == at).expect("a paired column")).collect();
    let right_places: Vec<usize> = right_at.iter().map(|at| tr.columns.iter().position(|column| column == at).expect("a paired column")).collect();
    let right_kept: Vec<usize> = (0..tr.columns.len()).filter(|place| !right_places.contains(place)).collect();
    let left_width = tl.columns.len();
    let right_width = tr.columns.len();
    let width = left_width + right_kept.len();
    // The right rows by their key.
    let mut index: Vec<(u128, u32)> = tr.cells.chunks_exact(right_width).enumerate().map(|(at, row)| (key_hash(row, &right_places), at as u32)).collect();
    index.sort_unstable();
    let mut cells: Vec<Cell> = Vec::new();
    for row in tl.cells.chunks_exact(left_width) {
        let key = key_hash(row, &left_places);
        let start = index.partition_point(|(held, _)| *held < key);
        for (held, at) in &index[start..] {
            if *held != key {
                break;
            }
            let other = &tr.cells[*at as usize * right_width..(*at as usize + 1) * right_width];
            cells.extend_from_slice(row);
            cells.extend(right_kept.iter().map(|place| other[*place]));
        }
        if cells.len() > CELL_CAP {
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

#[inline]
fn row_key(row: &[Cell], at: &[u16]) -> u128 {
    hash_words(at.iter().map(|column| u64::from(row[usize::from(*column)])))
}

fn semijoin(left: &Val, right: &Val, left_at: &[u16], right_at: &[u16]) -> Option<Val> {
    if matches!(left, Val::Empty) || matches!(right, Val::Empty) {
        return Some(Val::Empty);
    }
    let table = crate::gen_parts::flat(left)?;
    let keys = crate::gen_parts::keys_of(right, right_at)?;
    let mut cells = Vec::with_capacity(table.cells.len());
    let mut all_kept = true;
    for row in table.rows() {
        if keys.binary_search(&row_key(row, left_at)).is_ok() {
            cells.extend_from_slice(row);
        } else {
            all_kept = false;
        }
    }
    if all_kept {
        return Some(left.clone());
    }
    Some(Val::of_table(Table::new(table.arity, cells)))
}

fn all(domain: &Val, body: &Val, left_at: &[u16], right_at: &[u16], outer: &[u16]) -> Option<Val> {
    if matches!(domain, Val::Empty) {
        return Some(Val::Empty);
    }
    let table = crate::gen_parts::flat(domain)?;
    let keys = if matches!(body, Val::Empty) { Arc::new(Vec::new()) } else { crate::gen_parts::keys_of(body, right_at)? };
    let fails = |row: &[Cell]| keys.binary_search(&row_key(row, left_at)).is_err();
    if outer.is_empty() {
        return Some(if table.rows().any(fails) { Val::Empty } else { Val::of_table(Table::unit(true)) });
    }
    let at = usize::from(outer[0]);
    let mut failing: Vec<Cell> = table.rows().filter(|row| fails(row)).map(|row| row[at]).collect();
    failing.sort_unstable();
    failing.dedup();
    let mut out: Vec<Cell> = table.rows().map(|row| row[at]).filter(|cell| failing.binary_search(cell).is_err()).collect();
    out.sort_unstable();
    out.dedup();
    Some(Val::of_table(Table::new(1, out)))
}

fn antijoin(left: &Val, right: &Val, left_at: &[u16], right_at: &[u16]) -> Option<Val> {
    let Val::Rows(left_parts) = left else { return Some(Val::Empty) };
    let Val::Rows(right_parts) = right else { return Some(left.clone()) };
    if left_at.is_empty() {
        return Some(Val::Empty);
    }
    let (left_touched, left_rest) = split_parts(left_parts, left_at);
    let (right_touched, _) = split_parts(right_parts, right_at);
    let tl = merge(&left_touched)?;
    let tr = merge(&right_touched)?;
    let left_places: Vec<usize> = left_at.iter().map(|at| tl.columns.iter().position(|column| column == at).expect("a paired column")).collect();
    let right_places: Vec<usize> = right_at.iter().map(|at| tr.columns.iter().position(|column| column == at).expect("a paired column")).collect();
    let mut keys: Vec<u128> = tr.cells.chunks_exact(tr.columns.len()).map(|row| key_hash(row, &right_places)).collect();
    keys.sort_unstable();
    keys.dedup();
    let width = tl.columns.len();
    let mut cells: Vec<Cell> = Vec::with_capacity(tl.cells.len());
    for row in tl.cells.chunks_exact(width) {
        if keys.binary_search(&key_hash(row, &left_places)).is_err() {
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
        for row in left.rows(width, CELL_CAP / width.max(1))? {
            cells.extend_from_slice(&row);
        }
    }
    if let Val::Rows(parts) = right {
        let arity = parts.iter().flat_map(|part| part.columns.iter()).map(|column| usize::from(*column) + 1).max().unwrap_or(0);
        for row in right.rows(arity, CELL_CAP / width.max(1))? {
            cells.extend(map.iter().map(|at| at.map_or(0, |at| row[usize::from(at)])));
        }
    }
    if cells.len() > CELL_CAP {
        return None;
    }
    if cells.is_empty() {
        return Some(Val::Empty);
    }
    Some(Val::of_table(Table::distinct(width, cells)))
}
