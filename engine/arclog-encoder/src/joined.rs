//! The rows of a `join`, as the two relations they come from.
//!
//! A `join` pairs the rows of its two sides at some columns. For each value of the paired columns,
//! its rows are every row of the left side at that value with every row of the right side at it. A
//! [`Joined`] holds the two sides and, for each row, the id of its value of the paired columns. The
//! count of the join's rows is the sum over those values of the product of the two sides' counts
//! there, and a count of rows keyed by some columns is the same product per key. An operator whose
//! value depends on the distinct tuples of the rows at some columns reads those tuples from the
//! sides: the tuples of each side at its columns, paired at each value of the paired columns. Any
//! other operator reads the rows written out, once, up to `CELL_CAP` cells.
//!
//! A relation's rows are a set, so the rows of the join are distinct: each holds the left row and
//! the right row's columns that no pair names.

use std::cmp::Ordering;
use std::sync::{Arc, Mutex, OnceLock};

use crate::bounds::Bound;
use crate::boxes::second_columns;
use crate::gen_constants::number_bits;
use crate::gen_parts::PartStep;
use crate::native::{all, hash_words, key_word, project, Cell, FastMap, KeyIndex, Part, Step, Table, Val, CELL_CAP};

/// Marks the hash of a [`Joined`], which no other value's hash has.
const JOINED_WORD: u64 = 0x4a6f_696e_6564_5273;

/// Marks the hash of a [`Joined`] that a `select` makes, which no other value's hash has.
const ACROSS_WORD: u64 = 0x4163_726f_7373_5373;

/// The most cells of the tables of `Joined::rows_at` that one value keeps for later readers.
const SKETCH_KEPT: usize = 1 << 18;

/// The id of a left row that no right row pairs with.
const NO_PARTNER: u32 = u32::MAX;

/// The most rows of a side that a count of distinct tuples reads, over all the tuples it groups.
const COUNT_WORK: usize = 1 << 24;

/// Where a column of the join stands: at a place of the left table or of the right table.
#[derive(Clone, Copy, Debug)]
enum Place {
    Left(usize),
    Right(usize),
}

pub struct Joined {
    left: Arc<Table>,
    right: Arc<Table>,
    /// The places of the paired columns in the left table, and in the right table.
    left_places: Vec<usize>,
    /// The places of the right table's columns that no pair names, in order.
    right_kept: Vec<usize>,
    /// The column of the join that each column of the written rows stands for: the left table's, then the kept right ones.
    columns: Vec<u16>,
    /// For each column of the join, where it stands.
    places: Vec<Place>,
    /// The id of each left row's value of the paired columns, or `NO_PARTNER`.
    left_ids: Vec<u32>,
    /// The id of each right row's value of the paired columns.
    right_ids: Vec<u32>,
    /// For each id, the count of left rows and of right rows at it.
    left_counts: Vec<u32>,
    right_counts: Vec<u32>,
    hash: u128,
    /// The count of rows of the join.
    rows: u64,
    /// The rows, once written: no value where they pass `CELL_CAP` cells.
    written: OnceLock<Val>,
    /// The tables of `rows_at`, by their columns, and the cells that they hold.
    sketches: Mutex<(usize, FastMap<Box<[u16]>, Option<Arc<Table>>>)>,
}

impl std::fmt::Debug for Joined {
    fn fmt(&self, out: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(out, "Joined {{ left rows: {}, right rows: {}, rows: {} }}", self.left.len, self.right.len, self.rows)
    }
}

/// The rows of a sorted table whose first cell is an id, as the runs of one id: the id, and the first row and the end of its run.
fn runs(cells: &[Cell], stride: usize) -> Vec<(u32, usize, usize)> {
    let mut out: Vec<(u32, usize, usize)> = Vec::new();
    for (at, row) in cells.chunks_exact(stride).enumerate() {
        match out.last_mut() {
            Some(last) if last.0 == row[0] => last.2 = at + 1,
            _ => out.push((row[0], at, at + 1)),
        }
    }
    out
}

/// The runs of the same id in two lists of runs, each in order of id.
fn common(a: &[(u32, usize, usize)], b: &[(u32, usize, usize)]) -> Vec<((usize, usize), (usize, usize))> {
    let (mut i, mut j) = (0, 0);
    let mut out = Vec::new();
    while i < a.len() && j < b.len() {
        match a[i].0.cmp(&b[j].0) {
            Ordering::Less => i += 1,
            Ordering::Greater => j += 1,
            Ordering::Equal => {
                out.push(((a[i].1, a[i].2), (b[j].1, b[j].2)));
                i += 1;
                j += 1;
            }
        }
    }
    out
}

/// The rows of `flat`, which stand `stride` cells wide, in order, each once, and how many times it stood, or the sum of its `weights`.
fn sum_runs(flat: &[Cell], stride: usize, weights: Option<&[u64]>) -> (Vec<Cell>, Vec<u64>) {
    let count = flat.len() / stride;
    let mut order: Vec<u32> = (0..count as u32).collect();
    order.sort_unstable_by(|a, b| flat[*a as usize * stride..(*a as usize + 1) * stride].cmp(&flat[*b as usize * stride..(*b as usize + 1) * stride]));
    let mut rows: Vec<Cell> = Vec::new();
    let mut sums: Vec<u64> = Vec::new();
    for at in order {
        let row = &flat[at as usize * stride..(at as usize + 1) * stride];
        let weight = weights.map_or(1, |weights| weights[at as usize]);
        if !sums.is_empty() && rows[rows.len() - stride..] == *row {
            let last = sums.len() - 1;
            sums[last] = sums[last].saturating_add(weight);
        } else {
            rows.extend_from_slice(row);
            sums.push(weight);
        }
    }
    (rows, sums)
}

impl Joined {
    /// The join of `left` and `right` on the paired columns `left_at` and `right_at`, where `left_columns` and `right_columns` give the column of each table's columns, `kept` is the right columns that no pair names, and the left has `left_arity` columns: no rows where no row of one side has a partner. No value where a column is not at a table.
    #[allow(clippy::too_many_arguments)]
    pub fn of(left: Arc<Table>, left_columns: Vec<u16>, right: Arc<Table>, right_columns: Vec<u16>, left_at: &[u16], right_at: &[u16], kept: &[u16], left_arity: u16) -> Option<Val> {
        let place = |columns: &[u16], at: u16| columns.iter().position(|column| *column == at);
        if left_columns.len() != usize::from(left_arity) {
            return None;
        }
        let left_places: Vec<usize> = left_at.iter().map(|at| place(&left_columns, *at)).collect::<Option<_>>()?;
        let right_places: Vec<usize> = right_at.iter().map(|at| place(&right_columns, *at)).collect::<Option<_>>()?;
        let right_kept: Vec<usize> = (0..right_columns.len()).filter(|at| !right_places.contains(at)).collect();
        if right_kept.len() != kept.len() {
            return None;
        }
        // The kept right columns stand after the left ones, in the order of `kept`.
        let new_column = |column: u16| kept.iter().position(|own| *own == column).map(|at| left_arity + at as u16);
        let mut columns = left_columns.clone();
        for at in &right_kept {
            columns.push(new_column(right_columns[*at])?);
        }
        let mut places: Vec<Place> = Vec::with_capacity(columns.len());
        for column in 0..columns.len() as u16 {
            places.push(if column < left_arity {
                Place::Left(place(&left_columns, column)?)
            } else {
                Place::Right(place(&right_columns, *kept.get(usize::from(column - left_arity))?)?)
            });
        }
        let tail: Vec<u64> = left_columns
            .iter()
            .map(|column| u64::from(*column))
            .chain([u64::MAX])
            .chain(right_columns.iter().map(|column| u64::from(*column)))
            .chain([u64::MAX])
            .chain(left_places.iter().map(|at| *at as u64))
            .chain([u64::MAX])
            .chain(right_places.iter().map(|at| *at as u64))
            .chain([u64::MAX])
            .chain(columns.iter().map(|column| u64::from(*column)))
            .collect();
        Self::assemble(left, right, left_places, &right_places, right_kept, columns, places, &tail)
    }

    /// The join of `left` and `right` that a `select` makes of two parts, where it equates the column at `left_at` of the left table with the column at `right_at` of the right table, and drops the right one. `left_out` and `right_out` give the column of the select's rows for each column of each table; the right column at `right_at` has none. They name each column of the select's rows once. No value where they do not.
    pub fn across(left: Arc<Table>, left_out: &[u16], right: Arc<Table>, right_out: &[u16], left_at: usize, right_at: usize) -> Option<Val> {
        if left_out.len() != left.arity || right_out.len() != right.arity || left_at >= left.arity || right_at >= right.arity {
            return None;
        }
        let right_kept: Vec<usize> = (0..right.arity).filter(|place| *place != right_at).collect();
        let mut columns: Vec<u16> = left_out.to_vec();
        columns.extend(right_kept.iter().map(|place| right_out[*place]));
        let mut slots: Vec<Option<Place>> = vec![None; columns.len()];
        for (written, column) in columns.iter().enumerate() {
            let place = if written < left.arity { Place::Left(written) } else { Place::Right(right_kept[written - left.arity]) };
            let slot = slots.get_mut(usize::from(*column))?;
            if slot.is_some() {
                return None;
            }
            *slot = Some(place);
        }
        let places: Vec<Place> = slots.into_iter().collect::<Option<_>>()?;
        let tail: Vec<u64> = [ACROSS_WORD]
            .into_iter()
            .chain(left_out.iter().map(|column| u64::from(*column)))
            .chain([u64::MAX])
            .chain(right_out.iter().map(|column| u64::from(*column)))
            .chain([u64::MAX, left_at as u64, u64::MAX, right_at as u64])
            .collect();
        Self::assemble(left, right, vec![left_at], &[right_at], right_kept, columns, places, &tail)
    }

    /// The join of the tables whose paired places are `left_places` and `right_places`, where `columns` and `places` say where the columns of its rows come from, and `tail` is what its hash holds beyond the two tables.
    #[allow(clippy::too_many_arguments)]
    fn assemble(left: Arc<Table>, right: Arc<Table>, left_places: Vec<usize>, right_places: &[usize], right_kept: Vec<usize>, columns: Vec<u16>, places: Vec<Place>, tail: &[u64]) -> Option<Val> {
        let right_keys: Vec<u64> = right.rows().map(|row| key_word(row, right_places)).collect();
        let (index, right_ids) = KeyIndex::of(&right_keys);
        let groups = right_ids.iter().max().map_or(0, |last| *last as usize + 1);
        let mut right_counts = vec![0u32; groups];
        for id in &right_ids {
            right_counts[*id as usize] += 1;
        }
        let mut left_counts = vec![0u32; groups];
        let mut left_ids: Vec<u32> = Vec::with_capacity(left.len);
        let mut rows = 0u64;
        for row in left.rows() {
            match index.get(key_word(row, &left_places)) {
                Some(id) => {
                    left_counts[id as usize] += 1;
                    rows += u64::from(right_counts[id as usize]);
                    left_ids.push(id);
                }
                None => left_ids.push(NO_PARTNER),
            }
        }
        if rows == 0 {
            return Some(Val::Empty);
        }
        let (left_hash, right_hash) = (left.hash(), right.hash());
        let words = [JOINED_WORD, left_hash as u64, (left_hash >> 64) as u64, right_hash as u64, (right_hash >> 64) as u64].into_iter().chain(tail.iter().copied());
        let hash = hash_words(words);
        Some(Val::Joined(Arc::new(Joined { left, right, left_places, right_kept, columns, places, left_ids, right_ids, left_counts, right_counts, hash, rows, written: OnceLock::new(), sketches: Mutex::new((0, FastMap::default())) })))
    }

    /// The count of rows of the join.
    pub fn rows(&self) -> u64 {
        self.rows
    }

    pub fn hash(&self) -> u128 {
        self.hash
    }

    /// The count of columns of the join.
    pub fn width(&self) -> usize {
        self.places.len()
    }

    /// The cells that the sides and the ids of the join hold, which a walker counts as held.
    pub fn held_cells(&self) -> usize {
        self.left.cells.len() + self.right.cells.len() + self.left_ids.len() + self.right_ids.len() + self.left_counts.len() + self.right_counts.len()
    }

    /// Whether the rows of the join can be written out, in at most `CELL_CAP` cells.
    pub fn fits(&self) -> bool {
        self.rows.saturating_mul(self.width() as u64) <= CELL_CAP as u64
    }

    /// The rows of the join written out, or no value where they pass `CELL_CAP` cells.
    pub fn written(&self) -> Val {
        let held = self.written.get_or_init(|| self.write());
        if matches!(held, Val::None) {
            crate::bounds::mark(Bound::JoinOutput);
        }
        held.clone()
    }

    fn write(&self) -> Val {
        if !self.fits() {
            return Val::None;
        }
        // The right rows of each id, in the order the right rows stand.
        let mut starts: Vec<usize> = vec![0; self.right_counts.len() + 1];
        for id in &self.right_ids {
            starts[*id as usize + 1] += 1;
        }
        for at in 1..starts.len() {
            starts[at] += starts[at - 1];
        }
        let mut next = starts.clone();
        let mut by_id: Vec<u32> = vec![0; self.right_ids.len()];
        for (row, id) in self.right_ids.iter().enumerate() {
            by_id[next[*id as usize]] = row as u32;
            next[*id as usize] += 1;
        }
        let right_width = self.right.arity;
        let mut cells: Vec<Cell> = Vec::with_capacity(self.rows as usize * self.width());
        for (row, id) in self.left.rows().zip(&self.left_ids) {
            if *id == NO_PARTNER {
                continue;
            }
            for at in &by_id[starts[*id as usize]..starts[*id as usize + 1]] {
                let other = &self.right.cells[*at as usize * right_width..(*at as usize + 1) * right_width];
                cells.extend_from_slice(row);
                cells.extend(self.right_kept.iter().map(|place| other[*place]));
            }
        }
        Val::Rows(Arc::new(vec![Part { table: Table::new(self.width(), cells), columns: self.columns.clone().into_boxed_slice() }]))
    }

    /// The places of the table of each side that hold the columns `key` of the join, and for each column of `key` the side and the index into its places: no value where a column is not one of the join.
    #[allow(clippy::type_complexity)]
    fn split(&self, key: &[u16]) -> Option<(Vec<usize>, Vec<usize>, Vec<(bool, usize)>)> {
        let (mut lefts, mut rights, mut at) = (Vec::new(), Vec::new(), Vec::new());
        for column in key {
            match self.places.get(usize::from(*column))? {
                Place::Left(place) => {
                    at.push((true, lefts.len()));
                    lefts.push(*place);
                }
                Place::Right(place) => {
                    at.push((false, rights.len()));
                    rights.push(*place);
                }
            }
        }
        Some((lefts, rights, at))
    }

    /// The left rows that have a partner, as the id and the cells at `picks`, each once, in order.
    fn left_tuples(&self, picks: &[usize]) -> Arc<Table> {
        let mut flat: Vec<Cell> = Vec::new();
        for (row, id) in self.left.rows().zip(&self.left_ids) {
            if *id != NO_PARTNER {
                flat.push(*id);
                flat.extend(picks.iter().map(|place| row[*place]));
            }
        }
        Table::distinct(1 + picks.len(), flat)
    }

    /// The right rows that have a partner, as the id and the cells at `picks`, each once, in order.
    fn right_tuples(&self, picks: &[usize]) -> Arc<Table> {
        let mut flat: Vec<Cell> = Vec::new();
        for (row, id) in self.right.rows().zip(&self.right_ids) {
            if self.left_counts[*id as usize] > 0 {
                flat.push(*id);
                flat.extend(picks.iter().map(|place| row[*place]));
            }
        }
        Table::distinct(1 + picks.len(), flat)
    }

    /// A table in which the distinct tuples of the rows of the join stand at `columns`, as rows of the join's width with 0 at each other column: no value where they pass `CELL_CAP` cells. An operator whose value depends on those tuples alone has the same value on this table as on the rows written out.
    pub fn rows_at(&self, columns: &[u16]) -> Option<Arc<Table>> {
        let mut key: Vec<u16> = columns.to_vec();
        key.sort_unstable();
        key.dedup();
        let key = key.into_boxed_slice();
        let held = self.sketches.lock().expect("a sketch lock").1.get(&key).cloned();
        let built = match held {
            Some(built) => built,
            None => {
                let built = self.build_tuples(&key);
                let mut kept = self.sketches.lock().expect("a sketch lock");
                let cells = built.as_ref().map_or(0, |table| table.cells.len());
                if kept.0 + cells <= SKETCH_KEPT {
                    kept.0 += cells;
                    kept.1.insert(key, built.clone());
                }
                built
            }
        };
        if built.is_none() {
            crate::bounds::mark(Bound::JoinOutput);
        }
        built
    }

    fn build_tuples(&self, key: &[u16]) -> Option<Arc<Table>> {
        let width = self.width();
        let (lefts, rights, _) = self.split(key)?;
        if key.is_empty() {
            return Some(Table::new(width, vec![0; width]));
        }
        let (a, b) = (self.left_tuples(&lefts), self.right_tuples(&rights));
        let pairs = common(&runs(&a.cells, a.arity), &runs(&b.cells, b.arity));
        let total: usize = pairs.iter().map(|((a0, a1), (b0, b1))| (a1 - a0) * (b1 - b0)).sum();
        if total.saturating_mul(width) > CELL_CAP {
            return None;
        }
        let from_left: Vec<usize> = key.iter().filter(|column| matches!(self.places[usize::from(**column)], Place::Left(_))).map(|column| usize::from(*column)).collect();
        let from_right: Vec<usize> = key.iter().filter(|column| matches!(self.places[usize::from(**column)], Place::Right(_))).map(|column| usize::from(*column)).collect();
        let mut out: Vec<Cell> = Vec::with_capacity(total * width);
        let mut row = vec![0 as Cell; width];
        for ((a0, a1), (b0, b1)) in pairs {
            for x in a0..a1 {
                let own = &a.cells[x * a.arity..(x + 1) * a.arity];
                for (column, cell) in from_left.iter().zip(&own[1..]) {
                    row[*column] = *cell;
                }
                for y in b0..b1 {
                    let other = &b.cells[y * b.arity..(y + 1) * b.arity];
                    for (column, cell) in from_right.iter().zip(&other[1..]) {
                        row[*column] = *cell;
                    }
                    out.extend_from_slice(&row);
                }
            }
        }
        Some(Table::distinct(width, out))
    }

    /// The count of distinct tuples of the rows of the join at `columns`: no value where it takes more than a bound of work.
    pub fn distinct_count(&self, columns: &[u16]) -> Option<u64> {
        let mut key: Vec<u16> = columns.to_vec();
        key.sort_unstable();
        key.dedup();
        let (lefts, rights, _) = self.split(&key)?;
        if key.is_empty() {
            return Some(1);
        }
        if rights.is_empty() {
            return Some(self.one_side_count(&lefts, true));
        }
        if lefts.is_empty() {
            return Some(self.one_side_count(&rights, false));
        }
        let (a, b) = (self.left_tuples(&lefts), self.right_tuples(&rights));
        let (a_runs, b_runs) = (runs(&a.cells, a.arity), runs(&b.cells, b.arity));
        let pairs = common(&a_runs, &b_runs);
        // Two values of the paired columns that the tuples do not tell apart can give a tuple twice; where the tuples hold each paired column, they cannot.
        if self.left_places.iter().all(|place| lefts.contains(place)) {
            return Some(pairs.iter().map(|((a0, a1), (b0, b1))| ((a1 - a0) as u64).saturating_mul((b1 - b0) as u64)).fold(0u64, u64::saturating_add));
        }
        // A left tuple pairs with the right tuples of each id that it has. Left tuples with the same ids pair with the same right tuples, so each set of ids is counted once.
        let width = a.arity - 1;
        let mut by_tuple: Vec<Cell> = Vec::with_capacity(a.len * a.arity);
        for row in a.rows() {
            by_tuple.extend_from_slice(&row[1..]);
            by_tuple.push(row[0]);
        }
        let by_tuple = Table::distinct(a.arity, by_tuple);
        let mut sets: FastMap<Vec<u32>, u64> = FastMap::default();
        let mut start = 0;
        while start < by_tuple.len {
            let tuple = &by_tuple.cells[start * a.arity..start * a.arity + width];
            let mut end = start;
            let mut ids: Vec<u32> = Vec::new();
            while end < by_tuple.len && by_tuple.cells[end * a.arity..end * a.arity + width] == *tuple {
                ids.push(by_tuple.cells[end * a.arity + width]);
                end += 1;
            }
            *sets.entry(ids).or_default() += 1;
            start = end;
        }
        let range_of = |id: u32| b_runs.binary_search_by(|run| run.0.cmp(&id)).ok().map(|at| (b_runs[at].1, b_runs[at].2));
        let work: usize = sets.sum_of(|ids, _| ids.iter().filter_map(|id| range_of(*id)).map(|(from, to)| to - from).sum::<usize>());
        if work > COUNT_WORK {
            crate::bounds::mark(Bound::CountOutput);
            return None;
        }
        Some(sets.saturating_sum_of(|ids, tuples| {
            let mut flat: Vec<Cell> = Vec::new();
            for (from, to) in ids.iter().filter_map(|id| range_of(*id)) {
                for row in b.cells[from * b.arity..to * b.arity].chunks_exact(b.arity) {
                    flat.extend_from_slice(&row[1..]);
                }
            }
            tuples.saturating_mul(Table::distinct(b.arity - 1, flat).len as u64)
        }))
    }

    /// The count of distinct tuples at `picks` of the rows of one side that have a partner.
    fn one_side_count(&self, picks: &[usize], left: bool) -> u64 {
        let (table, ids) = if left { (&self.left, &self.left_ids) } else { (&self.right, &self.right_ids) };
        let mut flat: Vec<Cell> = Vec::new();
        for (row, id) in table.rows().zip(ids) {
            if (left && *id != NO_PARTNER) || (!left && self.left_counts[*id as usize] > 0) {
                flat.extend(picks.iter().map(|place| row[*place]));
            }
        }
        Table::distinct(picks.len(), flat).len as u64
    }

    /// The rows of `Count` over `keys`: each tuple of the keys' columns, with the count of the join's rows that hold it.
    pub fn counts(&self, keys: &[u16]) -> Val {
        if keys.is_empty() {
            return Val::of_table(Table::new(1, vec![number_bits(i64::try_from(self.rows).unwrap_or(i64::MAX))]));
        }
        let Some((lefts, rights, at)) = self.split(keys) else { return Val::None };
        // The rows of each side, grouped by id and the cells at the side's keys, with the count of each group.
        let side = |table: &Table, ids: &[u32], picks: &[usize], left: bool| -> (Vec<Cell>, Vec<u64>) {
            let mut flat: Vec<Cell> = Vec::new();
            for (row, id) in table.rows().zip(ids) {
                if (left && *id != NO_PARTNER) || (!left && self.left_counts[*id as usize] > 0) {
                    flat.push(*id);
                    flat.extend(picks.iter().map(|place| row[*place]));
                }
            }
            sum_runs(&flat, 1 + picks.len(), None)
        };
        let (a, a_counts) = side(&self.left, &self.left_ids, &lefts, true);
        let (b, b_counts) = side(&self.right, &self.right_ids, &rights, false);
        let (a_stride, b_stride) = (1 + lefts.len(), 1 + rights.len());
        let pairs = common(&runs(&a, a_stride), &runs(&b, b_stride));
        let total: usize = pairs.iter().map(|((a0, a1), (b0, b1))| (a1 - a0) * (b1 - b0)).sum();
        if total.saturating_mul(keys.len() + 1) > CELL_CAP {
            crate::bounds::mark(Bound::CountOutput);
            return Val::None;
        }
        let mut flat: Vec<Cell> = Vec::with_capacity(total * keys.len());
        let mut weights: Vec<u64> = Vec::with_capacity(total);
        for ((a0, a1), (b0, b1)) in pairs {
            for x in a0..a1 {
                for y in b0..b1 {
                    for (left, index) in &at {
                        flat.push(if *left { a[x * a_stride + 1 + index] } else { b[y * b_stride + 1 + index] });
                    }
                    weights.push(a_counts[x] * b_counts[y]);
                }
            }
        }
        let (tuples, counts) = sum_runs(&flat, keys.len(), Some(&weights));
        let mut out: Vec<Cell> = Vec::with_capacity(counts.len() * (keys.len() + 1));
        for (tuple, count) in tuples.chunks_exact(keys.len()).zip(&counts) {
            // A count past a number's range has no value.
            let Ok(count) = i32::try_from(*count) else { return Val::None };
            out.extend_from_slice(tuple);
            out.push(number_bits(i64::from(count)));
        }
        Val::of_table(Table::new(keys.len() + 1, out))
    }

    /// Whether `step` takes what it needs from the join's sides as its first relation, without writing the rows.
    pub fn reads(&self, step: &Step) -> bool {
        match step {
            Step::Project { .. } | Step::All { .. } => true,
            Step::Part(part) => matches!(**part, PartStep::Count { .. }) || part.set_columns().is_some(),
            _ => false,
        }
    }

    /// Whether `step` takes what it needs from the join's sides as its second relation, without writing the rows.
    pub fn reads_second(&self, step: &Step) -> bool {
        second_columns(step).is_some()
    }

    /// The relation that `step` reads in place of the join as its second relation, where `reads_second` holds of it: no value where the tuples pass `CELL_CAP` cells.
    pub fn read_second(&self, step: &Step) -> Option<Val> {
        let columns = second_columns(step)?;
        Some(self.rows_at(&columns).map_or(Val::None, Val::of_table))
    }

    /// What `step` gives over the join's rows, where `reads` holds of it.
    pub fn read(&self, step: &Step, children: &[&Val]) -> Option<Val> {
        match step {
            Step::Project { columns } => Some(match self.rows_at(columns) {
                Some(table) => project(&Val::of_table(table), columns),
                None => Val::None,
            }),
            Step::All { left, right, outer } => {
                let columns: Vec<u16> = left.iter().chain(outer.iter()).copied().collect();
                Some(match self.rows_at(&columns) {
                    Some(table) => all(&Val::of_table(table), children[1], left, right, outer).unwrap_or(Val::None),
                    None => Val::None,
                })
            }
            Step::Part(part) => match &**part {
                PartStep::Count { keys } => Some(self.counts(keys)),
                other => {
                    let columns = other.set_columns()?;
                    Some(match self.rows_at(&columns) {
                        Some(table) => other.run(&table, children).unwrap_or(Val::None),
                        None => Val::None,
                    })
                }
            },
            _ => None,
        }
    }

    /// The count of rows that `step` gives over the join's rows, where it is a count of distinct tuples of its columns and needs no tuples written: no value where a bound stops it. `None` where `step` is not of that form.
    pub fn count_of(&self, step: &Step) -> Option<Option<u64>> {
        match step {
            Step::Project { columns } => Some(self.distinct_count(columns)),
            // A count past a number's range has no value, which only a join of more rows than a number holds can reach.
            Step::Part(part) => match &**part {
                PartStep::Count { keys } if !keys.is_empty() && self.rows <= i32::MAX as u64 => Some(self.distinct_count(keys)),
                _ => None,
            },
            _ => None,
        }
    }
}
