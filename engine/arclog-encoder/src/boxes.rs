//! The rows of `inside`, as the boxes they come from.
//!
//! `inside` gives each row of a relation with each cell of the grid that lies in the row's box.
//! A [`Boxes`] holds the relation and the grid, and the count of those rows, which is the sum of
//! the clipped box areas. An operator whose value depends on the distinct tuples of the rows at
//! some columns reads those tuples from the boxes: from the relation's rows whose box has a cell
//! in the grid where the columns are the relation's, and otherwise from a union of boxes per
//! tuple of the relation's columns. An operator that keeps rows whole, over the relation's
//! columns, keeps the relation's rows, and gives boxes again. A `select` that compares the cell
//! column or the color column writes only the pairs of a row and a cell that pass. Any other
//! operator reads the rows written out, once. A write that passes the walker's budget of cells for
//! one term ([`walk_cells`]) gives no value.

use std::sync::{Arc, Mutex, OnceLock};

use crate::gen_constants::{box_bits, margins_of};
use crate::gen_parts::GridView;
use crate::expression::Op;
use crate::generate::walk_cells;
use crate::native::{all, antijoin, hash_words, holds, project, select, semijoin, Cell, FastMap, Step, Table, Val};

/// Marks the hash of a [`Boxes`], which no other value's hash has.
const BOXES_WORD: u64 = 0x426f_7865_7352_6f77;

/// The most cells of the tables of `Boxes::sketch` that one value keeps for later readers.
const SKETCH_KEPT: usize = 1 << 18;

pub struct Boxes {
    /// The relation: its rows, each with a box at `at`.
    table: Arc<Table>,
    at: u16,
    grid: Arc<GridView>,
    /// A hash of the grid's table.
    grid_hash: u128,
    hash: u128,
    /// The count of rows that `inside` gives: the sum of the clipped areas of the rows' boxes.
    rows: u64,
    /// The rows of the relation whose box has a cell in the grid.
    support: OnceLock<Arc<Table>>,
    /// The rows of `inside`, once written: no value where they pass one term's budget of cells.
    written: OnceLock<Val>,
    /// The tables of `sketch`, by their columns, and the cells that they hold.
    sketches: Mutex<(usize, FastMap<Box<[u16]>, Option<Arc<Table>>>)>,
}

impl Drop for Boxes {
    fn drop(&mut self) {
        crate::native::lazy_dropped(self.written.get());
    }
}

impl std::fmt::Debug for Boxes {
    fn fmt(&self, out: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(out, "Boxes {{ relation rows: {}, box column: {}, rows: {} }}", self.table.len, self.at, self.rows)
    }
}

/// The rows and the columns of a box that lie in a grid of `h` rows and `w` columns: the first and last row, and the first and last column.
fn span(held: Cell, h: i32, w: i32) -> (i32, i32, i32, i32) {
    let m = margins_of(held);
    (m[0].max(0), h - 1 - m[1].max(0), m[2].max(0), w - 1 - m[3].max(0))
}

/// The count of cells of a grid of `h` rows and `w` columns in a box.
fn area_of(held: Cell, h: i32, w: i32) -> u64 {
    let (r0, r1, c0, c1) = span(held, h, w);
    ((r1 - r0 + 1).max(0) * (c1 - c0 + 1).max(0)) as u64
}

impl Boxes {
    /// The rows of `inside` over `table`, whose boxes stand at column `at`, in the grid `grid`, whose table hashes as `grid_hash`.
    pub fn of(table: &Arc<Table>, at: u16, grid: Arc<GridView>, grid_hash: u128) -> Val {
        let rows: u64 = table.rows().map(|row| area_of(row[usize::from(at)], grid.h, grid.w)).sum();
        if rows == 0 {
            return Val::Empty;
        }
        let relation = table.hash();
        let hash = hash_words([BOXES_WORD, relation as u64, (relation >> 64) as u64, u64::from(at), grid_hash as u64, (grid_hash >> 64) as u64]);
        Val::Boxes(Arc::new(Boxes { table: table.clone(), at, grid, grid_hash, hash, rows, support: OnceLock::new(), written: OnceLock::new(), sketches: Mutex::new((0, FastMap::default())) }))
    }

    /// The count of rows of `inside`.
    pub fn rows(&self) -> u64 {
        self.rows
    }

    /// The column of the relation that holds the boxes.
    pub fn at(&self) -> u16 {
        self.at
    }

    pub fn hash(&self) -> u128 {
        self.hash
    }

    /// The count of cells of the grid in a box.
    pub fn area(&self, held: Cell) -> u64 {
        area_of(held, self.grid.h, self.grid.w)
    }

    /// The rows of the relation whose box has a cell in the grid.
    pub fn support(&self) -> Arc<Table> {
        self.support.get_or_init(|| {
            let at = usize::from(self.at);
            if self.table.rows().all(|row| self.area(row[at]) > 0) {
                return self.table.clone();
            }
            let mut cells = Vec::new();
            for row in self.table.rows() {
                if self.area(row[at]) > 0 {
                    cells.extend_from_slice(row);
                }
            }
            Table::new(self.table.arity, cells)
        }).clone()
    }

    /// Whether the rows of `inside` can be written out, in at most one term's budget of cells.
    pub fn fits(&self) -> bool {
        self.rows.saturating_mul(self.table.arity as u64 + 2) <= walk_cells() as u64
    }

    /// The rows of `inside` written out, or no value where they pass one term's budget of cells.
    pub fn written(&self) -> Val {
        let held = self.written.get_or_init(|| {
            let started = crate::bounds::started();
            let value = self.write();
            crate::native::lazy_wrote(&value);
            crate::bounds::wrote("rows", crate::native::cells_of(&value), started);
            value
        });
        if matches!(held, Val::None) {
            crate::bounds::mark(crate::bounds::Bound::Walk);
        }
        held.clone()
    }

    fn write(&self) -> Val {
        let (t, grid) = (&self.table, &self.grid);
        let at = usize::from(self.at);
        if !self.fits() {
            return Val::None;
        }
        let total = self.rows as usize;
        // A box's cells with their colors, in the order of their `P`: by column from the last, then by row from the last. Each box is read once.
        let mut tails: FastMap<Cell, Vec<Cell>> = FastMap::default();
        for row in t.rows() {
            tails.entry(row[at]).or_insert_with_key(|held| {
                let (r0, r1, c0, c1) = span(*held, grid.h, grid.w);
                let mut tail = Vec::with_capacity(2 * self.area(*held) as usize);
                for c in (c0..=c1).rev() {
                    for r in (r0..=r1).rev() {
                        tail.push(box_bits(r, grid.h - 1 - r, c, grid.w - 1 - c));
                        tail.push(grid.colors[(r * grid.w + c) as usize]);
                    }
                }
                tail
            });
        }
        let mut out: Vec<Cell> = Vec::with_capacity(total * (t.arity + 2));
        for row in t.rows() {
            for cell in tails[&row[at]].chunks_exact(2) {
                out.extend_from_slice(row);
                out.extend_from_slice(cell);
            }
        }
        // Where the rows come in order, so do these: no row repeats, and a sort is not needed.
        if t.rows().is_sorted_by(|a, b| a < b) {
            Val::of_table(Table::new(t.arity + 2, out))
        } else {
            Val::of_table(Table::distinct(t.arity + 2, out))
        }
    }

    /// The count of columns of the relation: `P` stands at this column of `inside`, and `Col` after it.
    pub fn width(&self) -> u16 {
        self.table.arity as u16
    }

    /// These boxes over other rows of the relation, in the same grid.
    pub fn with_rows(&self, table: &Arc<Table>) -> Val {
        Boxes::of(table, self.at, self.grid.clone(), self.grid_hash)
    }

    /// A table in which the rows of `inside` stand at `columns`: the relation's rows whose box has a cell in the grid where every column is the relation's, and otherwise `sketch`.
    pub fn rows_at(&self, columns: &[u16]) -> Option<Arc<Table>> {
        if columns.iter().all(|column| *column < self.width()) {
            return Some(self.support());
        }
        self.sketch(columns)
    }

    /// The distinct tuples of the rows of `inside` at `columns`, as rows of the arity of `inside` with 0 at each other column: no value where they pass one term's budget of cells. An operator whose value depends on those tuples alone has the same value on this table as on the rows written out.
    fn sketch(&self, columns: &[u16]) -> Option<Arc<Table>> {
        let mut key: Vec<u16> = columns.to_vec();
        key.sort_unstable();
        key.dedup();
        let key = key.into_boxed_slice();
        let held = self.sketches.lock().expect("a sketch lock").1.get(&key).cloned();
        let built = match held {
            Some(built) => built,
            None => {
                let started = crate::bounds::started();
                let built = self.build_sketch(&key);
                crate::bounds::wrote("tuples", built.as_ref().map_or(0, |table| table.cells.len()), started);
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
            crate::bounds::mark(crate::bounds::Bound::Walk);
        }
        built
    }

    fn build_sketch(&self, key: &[u16]) -> Option<Arc<Table>> {
        let grid = &self.grid;
        let width = self.table.arity;
        let arity = width + 2;
        let at = usize::from(self.at);
        let want_p = key.contains(&(width as u16));
        let want_color = key.contains(&(width as u16 + 1));
        let relation: Vec<usize> = key.iter().filter(|column| usize::from(**column) < width).map(|column| usize::from(*column)).collect();
        let support = self.support();
        // The distinct pairs of the relation's columns and a box, in order, so that the pairs of one tuple stand together.
        let mut pairs: Vec<Cell> = Vec::with_capacity(support.len * (relation.len() + 1));
        for row in support.rows() {
            pairs.extend(relation.iter().map(|column| row[*column]));
            pairs.push(row[at]);
        }
        let stride = relation.len() + 1;
        let pairs = Table::distinct(stride, pairs);
        // The cells of each box in the grid, as bits in the order of the grid's cells.
        let words = ((grid.h * grid.w) as usize).div_ceil(64);
        let mut masks_at: FastMap<Cell, usize> = FastMap::default();
        let mut masks: Vec<u64> = Vec::new();
        let mut out: Vec<Cell> = Vec::new();
        let mut union = vec![0u64; words];
        let mut row = vec![0 as Cell; arity];
        let mut colors: Vec<Cell> = Vec::new();
        let mut start = 0;
        while start < pairs.len {
            let tuple = &pairs.cells[start * stride..start * stride + relation.len()];
            union.fill(0);
            let mut end = start;
            while end < pairs.len && pairs.cells[end * stride..end * stride + relation.len()] == *tuple {
                let held = pairs.cells[end * stride + relation.len()];
                let from = *masks_at.entry(held).or_insert_with(|| {
                    let from = masks.len();
                    masks.resize(from + words, 0);
                    let (r0, r1, c0, c1) = span(held, grid.h, grid.w);
                    for r in r0..=r1 {
                        set_bits(&mut masks[from..from + words], (r * grid.w + c0) as usize, (r * grid.w + c1 + 1) as usize);
                    }
                    from
                });
                for (word, mask) in union.iter_mut().zip(&masks[from..from + words]) {
                    *word |= mask;
                }
                end += 1;
            }
            start = end;
            row.fill(0);
            for (column, cell) in relation.iter().zip(tuple) {
                row[*column] = *cell;
            }
            let cells_of = |union: &[u64]| -> Vec<usize> {
                let mut found = Vec::new();
                for (at, word) in union.iter().enumerate() {
                    let mut bits = *word;
                    while bits != 0 {
                        found.push(at * 64 + bits.trailing_zeros() as usize);
                        bits &= bits - 1;
                    }
                }
                found
            };
            let held = cells_of(&union);
            if want_p {
                if (out.len() / arity + held.len()).saturating_mul(arity) > walk_cells() {
                    return None;
                }
                for place in held {
                    let (r, c) = ((place as i32) / grid.w, (place as i32) % grid.w);
                    row[width] = box_bits(r, grid.h - 1 - r, c, grid.w - 1 - c);
                    if want_color {
                        row[width + 1] = grid.colors[place];
                    }
                    out.extend_from_slice(&row);
                }
            } else {
                colors.clear();
                colors.extend(held.iter().map(|place| grid.colors[*place]));
                colors.sort_unstable();
                colors.dedup();
                if (out.len() / arity + colors.len()).saturating_mul(arity) > walk_cells() {
                    return None;
                }
                for color in &colors {
                    row[width + 1] = *color;
                    out.extend_from_slice(&row);
                }
            }
        }
        Some(Table::new(arity, out))
    }

    /// Whether `step` takes what it needs from the boxes, without writing the rows.
    pub fn reads(&self, step: &Step) -> bool {
        let width = self.width();
        match step {
            Step::Project { .. } | Step::All { .. } => true,
            Step::Select { .. } => true,
            Step::Semijoin { left, .. } | Step::Antijoin { left, .. } => left.iter().all(|column| *column < width),
            Step::Part(part) => part.reads_boxes(width),
            _ => false,
        }
    }

    /// Whether `step` takes what it needs from these boxes as its second relation, without writing the rows.
    pub fn reads_second(&self, step: &Step) -> bool {
        second_columns(step).is_some()
    }

    /// The relation that `step` reads in place of these boxes as its second relation, where `reads_second` holds of it: no value where the rows pass one term's budget of cells.
    pub fn read_second(&self, step: &Step) -> Option<Val> {
        let columns = second_columns(step)?;
        Some(self.rows_at(&columns).map_or(Val::None, Val::of_table))
    }

    /// The boxes of the relation's rows that `value` holds, where `value` gives a set of them whole.
    fn kept(&self, value: Val) -> Option<Val> {
        let table = match &value {
            Val::None | Val::Empty => return Some(value),
            Val::Rows(parts) => match parts.as_slice() {
                [one] if one.table.arity == usize::from(self.width()) && one.columns.iter().enumerate().all(|(place, column)| usize::from(*column) == place) => one.table.clone(),
                _ => return None,
            },
            Val::Boxes(_) | Val::Joined(_) => return None,
        };
        Some(self.with_rows(&table))
    }

    /// What a `select` gives over these rows. A comparison of columns of the relation keeps rows of the relation, as boxes. Where it drops the box column by equating it with another column of the relation, the boxes stand at that column. Any other comparison writes the pairs of a row and a cell that pass.
    fn select(&self, at: u16, op: Op, other: Option<u16>, drop: Option<u16>) -> Val {
        let width = self.width();
        let on_relation = at < width && other.is_none_or(|other| other < width);
        // The box column's place in the rows that stay, where the rows that stay are rows of the relation.
        let moved = if drop != Some(self.at) {
            Some(if drop.is_some_and(|dropped| dropped < self.at) { self.at - 1 } else { self.at })
        } else if op == Op::Eq && other == drop {
            Some(at)
        } else {
            None
        };
        let (true, Some(moved)) = (on_relation, moved) else { return self.select_pairs(at, op, other, drop) };
        let Some(kept) = select(&Val::of_table(self.support()), at, op, other, drop) else { return Val::None };
        let table = match &kept {
            Val::Empty => return Val::Empty,
            Val::Rows(parts) => match parts.as_slice() {
                [one] if one.columns.iter().enumerate().all(|(place, column)| usize::from(*column) == place) => one.table.clone(),
                _ => return self.select_pairs(at, op, other, drop),
            },
            _ => return self.select_pairs(at, op, other, drop),
        };
        Boxes::of(&table, moved, self.grid.clone(), self.grid_hash)
    }

    /// The rows of `inside` that pass a `select`, written out: no value where they pass one term's budget of cells. A row of the relation passes with the cells of its box that the comparison keeps. A comparison of the cell column with a column of the relation keeps one cell at most, which is found from the box's extent.
    fn select_pairs(&self, at: u16, op: Op, other: Option<u16>, drop: Option<u16>) -> Val {
        let grid = &self.grid;
        let width = usize::from(self.width());
        let arity = width + 2;
        let side = |column: u16| match usize::from(column) {
            place if place == width => Side::Cell,
            place if place == width + 1 => Side::Color,
            place => Side::Column(place),
        };
        let (left, right) = (side(at), other.map_or(Side::Zero, side));
        let on_cells = left.is_cell() || right.is_cell();
        let drop = drop.map(usize::from);
        let box_at = usize::from(self.at);
        let started = crate::bounds::started();
        let mut out: Vec<Cell> = Vec::new();
        let mut line: Vec<Cell> = vec![0; arity];
        for row in self.support().rows() {
            line[..width].copy_from_slice(row);
            let value = |side: Side| match side {
                Side::Column(place) => row[place],
                _ => 0,
            };
            let (r0, r1, c0, c1) = span(row[box_at], grid.h, grid.w);
            let mut push = |place: Cell, color: Cell| {
                line[width] = place;
                line[width + 1] = color;
                match drop {
                    None => out.extend_from_slice(&line),
                    Some(dropped) => {
                        out.extend_from_slice(&line[..dropped]);
                        out.extend_from_slice(&line[dropped + 1..]);
                    }
                }
            };
            let single = match (left, right, op) {
                (Side::Cell, Side::Column(_) | Side::Zero, Op::Eq) => Some(value(right)),
                (Side::Column(_) | Side::Zero, Side::Cell, Op::Eq) => Some(value(left)),
                _ => None,
            };
            if let Some(wanted) = single {
                // The one cell that is the box `wanted`, if it lies in this row's box.
                let m = margins_of(wanted);
                let (r, c) = (m[0], m[2]);
                if (r0..=r1).contains(&r) && (c0..=c1).contains(&c) && box_bits(r, grid.h - 1 - r, c, grid.w - 1 - c) == wanted {
                    push(wanted, grid.colors[(r * grid.w + c) as usize]);
                }
            } else if !on_cells {
                if holds(op, value(left), value(right)) {
                    for c in (c0..=c1).rev() {
                        for r in (r0..=r1).rev() {
                            push(box_bits(r, grid.h - 1 - r, c, grid.w - 1 - c), grid.colors[(r * grid.w + c) as usize]);
                        }
                    }
                }
            } else {
                for c in (c0..=c1).rev() {
                    for r in (r0..=r1).rev() {
                        let (place, color) = (box_bits(r, grid.h - 1 - r, c, grid.w - 1 - c), grid.colors[(r * grid.w + c) as usize]);
                        let of = |side: Side| match side {
                            Side::Cell => place,
                            Side::Color => color,
                            plain => value(plain),
                        };
                        if holds(op, of(left), of(right)) {
                            push(place, color);
                        }
                    }
                }
            }
            if out.len() > walk_cells() {
                crate::bounds::mark(crate::bounds::Bound::Walk);
                crate::bounds::wrote("pairs", out.len(), started);
                return Val::None;
            }
        }
        crate::bounds::wrote("pairs", out.len(), started);
        let arity = arity - usize::from(drop.is_some());
        let sorted = out.chunks_exact(arity).is_sorted_by(|a, b| a < b);
        Val::of_table(if sorted { Table::new(arity, out) } else { Table::distinct(arity, out) })
    }

    /// What `step` gives over these rows, where `reads` holds of it.
    pub fn read(&self, step: &Step, children: &[&Val]) -> Option<Val> {
        if !self.reads(step) {
            return None;
        }
        match step {
            Step::Project { columns } => Some(match self.rows_at(columns) {
                Some(table) => project(&Val::of_table(table), columns),
                None => Val::None,
            }),
            Step::Select { at, op, other, drop } => Some(self.select(*at, *op, *other, *drop)),
            Step::Semijoin { left, right } => {
                let kept = semijoin(&Val::of_table(self.support()), children[1], left, right);
                self.kept(kept.unwrap_or(Val::None))
            }
            Step::Antijoin { left, right } => {
                let kept = antijoin(&Val::of_table(self.support()), children[1], left, right);
                self.kept(kept.unwrap_or(Val::None))
            }
            Step::All { left, right, outer } => {
                let columns: Vec<u16> = left.iter().chain(outer.iter()).copied().collect();
                Some(match self.rows_at(&columns) {
                    Some(table) => all(&Val::of_table(table), children[1], left, right, outer).unwrap_or(Val::None),
                    None => Val::None,
                })
            }
            Step::Part(part) => part.read_boxes(self, children),
            _ => None,
        }
    }
}

/// A side of a comparison over the rows of `inside`: a column of the relation, the cell, its color, or 0.
#[derive(Clone, Copy)]
enum Side {
    Column(usize),
    Cell,
    Color,
    Zero,
}

impl Side {
    fn is_cell(self) -> bool {
        matches!(self, Side::Cell | Side::Color)
    }
}

/// The columns of `step`'s second relation that it reads, where what it gives depends on the distinct tuples of the rows at those columns alone.
pub(crate) fn second_columns(step: &Step) -> Option<Vec<u16>> {
    match step {
        Step::Semijoin { right, .. } | Step::Antijoin { right, .. } | Step::All { right, .. } => Some(right.to_vec()),
        Step::Part(part) => part.second_columns(),
        _ => None,
    }
}

/// Sets the bits from `from` up to `to`, in words of 64 bits.
fn set_bits(words: &mut [u64], from: usize, to: usize) {
    let mut at = from;
    while at < to {
        let word = at / 64;
        let end = to.min((word + 1) * 64);
        let count = end - at;
        let mask = if count == 64 { u64::MAX } else { ((1u64 << count) - 1) << (at % 64) };
        words[word] |= mask;
        at = end;
    }
}
