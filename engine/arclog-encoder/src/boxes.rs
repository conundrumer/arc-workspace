//! The rows of `inside`, as the boxes they come from.
//!
//! `inside` gives each row of a relation with each cell of the grid that lies in the row's box.
//! A [`Boxes`] holds the relation and the grid, and the count of those rows, which is the sum of
//! the clipped box areas. An operator whose value depends on the distinct tuples of the rows at
//! some columns reads those tuples from the boxes: from the relation's rows whose box has a cell
//! in the grid where the columns are the relation's, and otherwise from a union of boxes per
//! tuple of the relation's columns. An operator that keeps rows whole, over the relation's
//! columns, keeps the relation's rows, and gives boxes again. A `select` that compares the cell
//! column or the color column writes only the pairs of a row and a cell that pass. The count of
//! rows that a part, a `semijoin`, an `antijoin`, a `join` or an `inside` gives is read from the
//! distinct tuples of the rows at the columns it reads, each with the count of rows that hold it.
//! Any other operator reads the rows written out, once. The pairs that a `select` keeps, where
//! they pass the output limit of cells, give no value.

use std::cmp::Ordering;
use std::sync::{Arc, Mutex, OnceLock};

use crate::columns::Columns;
use crate::expression::Op;
use crate::gen_constants::{box_bits, margins_of};
use crate::gen_parts::{grid_of, GridView, PartStep};
use crate::native::{all, antijoin, hash_words, holds, project, select, semijoin, Cell, FastMap, Part, Step, Table, Val};

/// Marks the hash of a [`Boxes`], which no other value's hash has.
const BOXES_WORD: u64 = 0x426f_7865_7352_6f77;

/// The most cells of the tables of `Boxes::sketch` that one value keeps for later readers.
const SKETCH_KEPT: usize = 1 << 18;

/// The most cells of the tuples, counts and rows of `Boxes::counted` that one value keeps for later readers.
const COUNTED_KEPT: usize = 1 << 19;

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
    /// The rows of `inside`, once written: no value where they pass the output limit.
    written: OnceLock<Val>,
    /// The tuples of `sketch`, by their columns, and the cells that the kept tables hold.
    sketches: Mutex<(usize, FastMap<Box<[u16]>, Arc<Sketch>>)>,
    /// The tuples of `counted`, by their columns, and the cells that the kept values hold.
    counts: Mutex<(usize, FastMap<Box<[u16]>, Arc<Counted>>)>,
}

/// The distinct tuples of the rows of `inside` at some columns, in order, each with the count of rows of `inside` that hold it.
struct Counted {
    /// The tuples, one cell for each column of the key, in ascending order.
    tuples: Vec<Cell>,
    weights: Vec<u64>,
    /// The tuples as rows of the arity of `inside`, with 0 at each column that is not in the key, once something has read them.
    wide: OnceLock<Arc<Table>>,
}

impl Counted {
    /// The tuples as rows of `arity` cells, with 0 at each column that is not in `key`.
    fn wide(&self, key: &[u16], arity: usize) -> Arc<Table> {
        self.wide
            .get_or_init(|| {
                let mut cells: Vec<Cell> = vec![0; self.weights.len() * arity];
                for (row, tuple) in cells.chunks_exact_mut(arity).zip(self.tuples.chunks_exact(key.len())) {
                    for (column, cell) in key.iter().zip(tuple) {
                        row[usize::from(*column)] = *cell;
                    }
                }
                Table::new(arity, cells)
            })
            .clone()
    }

    /// The count of rows of `inside` that hold the tuple that `row` has at the columns `key`.
    fn weight_of(&self, key: &[u16], row: &[Cell]) -> Option<u64> {
        let stride = key.len();
        let (mut low, mut high) = (0, self.weights.len());
        while low < high {
            let middle = low + (high - low) / 2;
            let order = self.tuples[middle * stride..(middle + 1) * stride].iter().zip(key).map(|(cell, column)| cell.cmp(&row[usize::from(*column)])).find(|order| order.is_ne()).unwrap_or(Ordering::Equal);
            match order {
                Ordering::Equal => return Some(self.weights[middle]),
                Ordering::Less => low = middle + 1,
                Ordering::Greater => high = middle,
            }
        }
        None
    }
}

/// The distinct tuples of the rows of `inside` at some columns that include a column after the relation's.
struct Sketch {
    /// The tuples in order, as a table of the relation's columns among them, then `P` where it is among them, then `Col` where it is or where `P` is not.
    tuples: Option<Arc<Table>>,
    /// The tuples as rows of the arity of `inside`, with 0 at each other column, once something has read them.
    wide: OnceLock<Arc<Table>>,
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
pub(crate) fn area_of(held: Cell, h: i32, w: i32) -> u64 {
    let (r0, r1, c0, c1) = span(held, h, w);
    ((r1 - r0 + 1).max(0) * (c1 - c0 + 1).max(0)) as u64
}

impl Boxes {
    /// The rows of `inside` over `table`, whose boxes stand at column `at`, in the grid `grid`, whose table hashes as `grid_hash`.
    pub fn of(table: &Arc<Table>, at: u16, grid: Arc<GridView>, grid_hash: u128) -> Val {
        let rows: u64 = table.sum_rows(|row| area_of(row[usize::from(at)], grid.h, grid.w));
        if rows == 0 {
            return Val::Empty;
        }
        let relation = table.hash();
        let hash = hash_words([BOXES_WORD, relation as u64, (relation >> 64) as u64, u64::from(at), grid_hash as u64, (grid_hash >> 64) as u64]);
        Val::Boxes(Arc::new(Boxes { table: table.clone(), at, grid, grid_hash, hash, rows, support: OnceLock::new(), written: OnceLock::new(), sketches: Mutex::new((0, FastMap::default())), counts: Mutex::new((0, FastMap::default())) }))
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
            if self.table.all_rows(|row| self.area(row[at]) > 0) {
                return self.table.clone();
            }
            self.table.filter_rows(|row| self.area(row[at]) > 0)
        }).clone()
    }

    /// Whether the rows of `inside` can be written out, in at most the output limit of cells.
    pub fn fits(&self) -> bool {
        self.rows.saturating_mul(self.table.arity as u64 + 2) <= crate::native::output_limit() as u64
    }

    /// The rows of `inside` written out, or no value where they pass the output limit.
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
    pub fn rows_at(&self, columns: &Columns) -> Option<Arc<Table>> {
        if columns.iter().all(|column| *column < self.width()) {
            return Some(self.support());
        }
        let key = Boxes::key_of(columns);
        let sketch = self.sketch(&key);
        let tuples = sketch.tuples.as_ref()?;
        if let Some(wide) = sketch.wide.get() {
            return Some(wide.clone());
        }
        let width = self.table.arity;
        let (relation, want_p, with_color) = self.layout(&key);
        // The tuples stand in order of the relation's columns, then `P`, then `Col`, so the rows stand in order.
        let mut out: Vec<Cell> = vec![0; tuples.len * (width + 2)];
        for (row, tuple) in out.chunks_exact_mut(width + 2).zip(tuples.rows()) {
            let mut cells = tuple.iter();
            for column in &relation {
                row[*column] = *cells.next().expect("a cell for each column of a tuple");
            }
            if want_p {
                row[width] = *cells.next().expect("a cell for each column of a tuple");
            }
            if with_color {
                row[width + 1] = *cells.next().expect("a cell for each column of a tuple");
            }
        }
        let wide = Table::new(width + 2, out);
        let mut kept = self.sketches.lock().expect("a sketch lock");
        if kept.0 + wide.cell_count() <= SKETCH_KEPT && sketch.wide.set(wide.clone()).is_ok() {
            kept.0 += wide.cell_count();
        }
        Some(wide)
    }

    /// The columns `columns` in order.
    fn key_of(columns: &Columns) -> Box<[u16]> {
        let mut key: Vec<u16> = columns.to_vec();
        key.sort_unstable();
        key.into_boxed_slice()
    }

    /// The places in the relation of the key's columns that are the relation's, whether `P` is among them, and whether `Col` is among the tuples: it is wherever `P` is not.
    fn layout(&self, key: &[u16]) -> (Vec<usize>, bool, bool) {
        let width = self.table.arity;
        let relation: Vec<usize> = key.iter().filter(|column| usize::from(**column) < width).map(|column| usize::from(*column)).collect();
        let want_p = key.contains(&(width as u16));
        (relation, want_p, !want_p || key.contains(&(width as u16 + 1)))
    }

    /// The distinct tuples of the rows of `inside` at the columns `key`, which stand in order.
    fn sketch(&self, key: &[u16]) -> Arc<Sketch> {
        let held = self.sketches.lock().expect("a sketch lock").1.get(key).cloned();
        match held {
            Some(sketch) => sketch,
            None => {
                let started = crate::bounds::started();
                let sketch = Arc::new(Sketch { tuples: self.build_sketch(key), wide: OnceLock::new() });
                crate::bounds::wrote("tuples", sketch.tuples.as_ref().map_or(0, |table| table.cell_count()), started);
                let mut kept = self.sketches.lock().expect("a sketch lock");
                let cells = sketch.tuples.as_ref().map_or(0, |table| table.cell_count());
                if kept.0 + cells <= SKETCH_KEPT {
                    kept.0 += cells;
                    kept.1.insert(key.into(), sketch.clone());
                }
                sketch
            }
        }
    }

    /// What a `project` onto `columns` gives over the rows of `inside`.
    fn project(&self, columns: &Columns) -> Val {
        let arity = usize::from(self.width()) + 2;
        if columns.iter().all(|column| *column < self.width()) || columns.iter().any(|column| usize::from(*column) >= arity) {
            return match self.rows_at(columns) {
                Some(table) => project(&Val::of_table(table), columns),
                None => Val::None,
            };
        }
        let key = Boxes::key_of(columns);
        match &self.sketch(&key).tuples {
            Some(tuples) => project_tuples(tuples, &key, columns, arity),
            None => Val::None,
        }
    }

    /// The distinct tuples of the rows of `inside` at the columns `key`, which stand in order, as a table of the relation's columns among them, then `P` where it is among them, then `Col` where it is or where `P` is not. An operator whose value depends on those tuples alone has the same value on the tuples as on the rows written out.
    fn build_sketch(&self, key: &[u16]) -> Option<Arc<Table>> {
        let grid = &self.grid;
        let width = self.table.arity;
        let at = usize::from(self.at);
        let (relation, want_p, with_color) = self.layout(key);
        let support = self.support();
        // The distinct pairs of the relation's columns and a box, in order, so that the pairs of one tuple stand together.
        let mut pairs: Vec<Cell> = Vec::with_capacity(support.len * (relation.len() + 1));
        for row in support.rows() {
            pairs.extend(relation.iter().map(|column| row[*column]));
            pairs.push(row[at]);
        }
        let stride = relation.len() + 1;
        let pairs = Table::distinct(stride, pairs);
        // The cells of each box in the grid, as bits. The bit of a cell is its column from the last times the grid's height, plus its row from the last, so the bits stand in the order of the cells' `P`.
        let bit = |r: i32, c: i32| ((grid.w - 1 - c) * grid.h + (grid.h - 1 - r)) as usize;
        let words = ((grid.h * grid.w) as usize).div_ceil(64);
        let mut masks_at: FastMap<Cell, usize> = FastMap::default();
        let mut masks: Vec<u64> = Vec::new();
        // The first bit set of each pair's box in `masks`.
        let mask_of: Vec<usize> = pairs
            .rows()
            .map(|pair| {
                let held = pair[relation.len()];
                *masks_at.entry(held).or_insert_with(|| {
                    let from = masks.len();
                    masks.resize(from + words, 0);
                    let (r0, r1, c0, c1) = span(held, grid.h, grid.w);
                    for c in c0..=c1 {
                        set_bits(&mut masks[from..from + words], bit(r1, c), bit(r0, c) + 1);
                    }
                    from
                })
            })
            .collect();
        // The pairs of each tuple of the relation's columns: where its pairs start, and the end of the last.
        let mut starts: Vec<usize> = Vec::new();
        for pair in 0..pairs.len {
            if pair == 0 || pairs.cells()[pair * stride..pair * stride + relation.len()] != pairs.cells()[(pair - 1) * stride..(pair - 1) * stride + relation.len()] {
                starts.push(pair);
            }
        }
        starts.push(pairs.len);
        let mut union = vec![0u64; words];
        let union_of = |tuple: usize, union: &mut [u64]| {
            union.fill(0);
            for from in &mask_of[starts[tuple]..starts[tuple + 1]] {
                for (word, mask) in union.iter_mut().zip(&masks[*from..*from + words]) {
                    *word |= mask;
                }
            }
        };
        let tuples = starts.len() - 1;
        let tuple_at = |tuple: usize| starts[tuple] * stride..starts[tuple] * stride + relation.len();
        let cells_in = |union: &[u64]| union.iter().map(|word| word.count_ones() as usize).sum::<usize>();
        // The colors of the cells, by their bit.
        let mut color_of = vec![0 as Cell; (grid.h * grid.w) as usize];
        for r in 0..grid.h {
            for c in 0..grid.w {
                color_of[bit(r, c)] = grid.colors[(r * grid.w + c) as usize];
            }
        }
        let arity_out = relation.len() + usize::from(want_p) + usize::from(with_color);
        let mut out: Vec<Cell>;
        if want_p {
            // The rows of each tuple are the cells of its boxes' union, so the count of rows is known before they are written.
            let mut total = 0usize;
            for tuple in 0..tuples {
                union_of(tuple, &mut union[..]);
                total += cells_in(&union[..]);
            }
            let mut p_of = vec![0 as Cell; (grid.h * grid.w) as usize];
            for r in 0..grid.h {
                for c in 0..grid.w {
                    p_of[bit(r, c)] = box_bits(r, grid.h - 1 - r, c, grid.w - 1 - c);
                }
            }
            out = Vec::with_capacity(total * arity_out);
            for tuple in 0..tuples {
                union_of(tuple, &mut union[..]);
                let prefix = &pairs.cells()[tuple_at(tuple)];
                for (at, word) in union.iter().enumerate() {
                    let mut bits = *word;
                    while bits != 0 {
                        let place = at * 64 + bits.trailing_zeros() as usize;
                        bits &= bits - 1;
                        out.extend_from_slice(prefix);
                        out.push(p_of[place]);
                        if with_color {
                            out.push(color_of[place]);
                        }
                    }
                }
            }
        } else {
            out = Vec::new();
            let mut colors: Vec<Cell> = Vec::new();
            for tuple in 0..tuples {
                union_of(tuple, &mut union[..]);
                colors.clear();
                for (at, word) in union.iter().enumerate() {
                    let mut bits = *word;
                    while bits != 0 {
                        colors.push(color_of[at * 64 + bits.trailing_zeros() as usize]);
                        bits &= bits - 1;
                    }
                }
                colors.sort_unstable();
                colors.dedup();
                let prefix = &pairs.cells()[tuple_at(tuple)];
                for color in &colors {
                    out.extend_from_slice(prefix);
                    out.push(*color);
                }
            }
        }
        Some(Table::new(arity_out, out))
    }

    /// The distinct tuples of the rows of `inside` at the columns `key`, which stand sorted and distinct, each with the count of rows of `inside` that hold it, from the value's own keep where it holds this read. No value where `key` is empty or names a column past the rows of `inside`.
    fn counted(&self, key: &[u16]) -> Option<Arc<Counted>> {
        if let Some(found) = self.counts.lock().expect("a count lock").1.get(key).cloned() {
            return Some(found);
        }
        let started = crate::bounds::started();
        let built = Arc::new(self.build_counted(key)?);
        crate::bounds::wrote("counts", built.tuples.len(), started);
        let cells = built.tuples.len() + built.weights.len() * (2 + self.table.arity + 2);
        let mut kept = self.counts.lock().expect("a count lock");
        if kept.0 + cells <= COUNTED_KEPT {
            kept.0 += cells;
            kept.1.insert(key.into(), built.clone());
        }
        Some(built)
    }

    /// What `counted` gives, built from the relation's rows. The rows of `inside` are the distinct rows of the relation that have a cell in the grid, each with the cells of its box: a tuple of the relation's columns alone is held by the rows that agree with it, each as often as its box has cells. A tuple that has the cell, or its color, is held by as many rows as have the cell in their box.
    fn build_counted(&self, key: &[u16]) -> Option<Counted> {
        let width = self.table.arity;
        if key.is_empty() || key.iter().any(|column| usize::from(*column) >= width + 2) {
            return None;
        }
        let at = usize::from(self.at);
        let support = self.support();
        let relation: Vec<usize> = key.iter().filter(|column| usize::from(**column) < width).map(|column| usize::from(*column)).collect();
        let want_p = key.contains(&(width as u16));
        let want_color = key.contains(&(width as u16 + 1));
        let stride = key.len();
        if !want_p && !want_color {
            let mut flat: Vec<Cell> = Vec::with_capacity(support.len * stride);
            let mut areas: Vec<u64> = Vec::with_capacity(support.len);
            for row in support.rows() {
                flat.extend(relation.iter().map(|column| row[*column]));
                areas.push(self.area(row[at]));
            }
            let (tuples, weights) = sum_sorted(&flat, stride, &areas);
            return Some(Counted { tuples, weights, wide: OnceLock::new() });
        }
        let grid = &self.grid;
        let prefix = relation.len();
        // The distinct pairs of the relation's columns and a box, in order, each with the count of rows of the relation that hold it, so that the pairs of one tuple stand together.
        let mut flat: Vec<Cell> = Vec::with_capacity(support.len * (prefix + 1));
        for row in support.rows() {
            flat.extend(relation.iter().map(|column| row[*column]));
            flat.push(row[at]);
        }
        let (pairs, repeats) = sum_sorted(&flat, prefix + 1, &vec![1u64; support.len]);
        drop(flat);
        // The bit of a cell is its column from the last times the grid's height, plus its row from the last, so the bits stand in the order of the cells' `P`.
        let cells = (grid.h * grid.w) as usize;
        let bit = |r: i32, c: i32| ((grid.w - 1 - c) * grid.h + (grid.h - 1 - r)) as usize;
        let mut p_of = vec![0 as Cell; if want_p { cells } else { 0 }];
        let mut color_of = vec![0 as Cell; cells];
        for r in 0..grid.h {
            for c in 0..grid.w {
                if want_p {
                    p_of[bit(r, c)] = box_bits(r, grid.h - 1 - r, c, grid.w - 1 - c);
                }
                color_of[bit(r, c)] = grid.colors[(r * grid.w + c) as usize];
            }
        }
        // How many rows of the tuple's group have each cell in their box, by the cell's bit, and the bits that hold a count.
        let mut covered = vec![0u64; cells];
        let mut touched: Vec<usize> = Vec::new();
        // The same counts by the corners of the boxes, which one pass over the grid sums.
        let side = grid.w as usize + 1;
        let mut corners = vec![0i64; (grid.h as usize + 1) * side];
        let mut out: Vec<Cell> = Vec::new();
        let mut counts: Vec<u64> = Vec::new();
        let pair_count = repeats.len();
        let pair_stride = prefix + 1;
        let mut from = 0usize;
        while from < pair_count {
            let head = &pairs[from * pair_stride..from * pair_stride + prefix];
            let mut to = from + 1;
            while to < pair_count && pairs[to * pair_stride..to * pair_stride + prefix] == *head {
                to += 1;
            }
            let area: u64 = (from..to).map(|pair| self.area(pairs[pair * pair_stride + prefix])).sum();
            let mut emit = |place: usize, count: u64| {
                out.extend_from_slice(head);
                if want_p {
                    out.push(p_of[place]);
                }
                if want_color {
                    out.push(color_of[place]);
                }
                counts.push(count);
            };
            if area.saturating_mul(4) <= cells as u64 {
                for pair in from..to {
                    let (r0, r1, c0, c1) = span(pairs[pair * pair_stride + prefix], grid.h, grid.w);
                    for c in c0..=c1 {
                        for r in r0..=r1 {
                            let place = bit(r, c);
                            if covered[place] == 0 {
                                touched.push(place);
                            }
                            covered[place] += repeats[pair];
                        }
                    }
                }
                touched.sort_unstable();
                for place in touched.drain(..) {
                    emit(place, covered[place]);
                    covered[place] = 0;
                }
            } else {
                corners.fill(0);
                for pair in from..to {
                    let (r0, r1, c0, c1) = span(pairs[pair * pair_stride + prefix], grid.h, grid.w);
                    let count = repeats[pair] as i64;
                    corners[r0 as usize * side + c0 as usize] += count;
                    corners[r0 as usize * side + c1 as usize + 1] -= count;
                    corners[(r1 as usize + 1) * side + c0 as usize] -= count;
                    corners[(r1 as usize + 1) * side + c1 as usize + 1] += count;
                }
                for r in 0..=grid.h as usize {
                    for c in 0..side {
                        let above = if r > 0 { corners[(r - 1) * side + c] } else { 0 };
                        let left = if c > 0 { corners[r * side + c - 1] } else { 0 };
                        let both = if r > 0 && c > 0 { corners[(r - 1) * side + c - 1] } else { 0 };
                        corners[r * side + c] += above + left - both;
                    }
                }
                for place in 0..cells {
                    let (r, c) = (grid.h - 1 - (place as i32 % grid.h), grid.w - 1 - (place as i32 / grid.h));
                    let count = corners[r as usize * side + c as usize];
                    if count > 0 {
                        emit(place, count as u64);
                    }
                }
            }
            from = to;
        }
        // Tuples that differ in the cell alone but agree in its color are one tuple where the cell is not asked for.
        let (tuples, weights) = sum_sorted(&out, stride, &counts);
        Some(Counted { tuples, weights, wide: OnceLock::new() })
    }

    /// The count of distinct tuples of the rows of `inside` at `columns`.
    fn distinct_count(&self, columns: &[u16]) -> Option<Option<u64>> {
        let mut key: Vec<u16> = columns.to_vec();
        key.sort_unstable();
        key.dedup();
        Some(Some(self.counted(&key)?.weights.len() as u64))
    }

    /// The count of rows that an `inside` over these rows gives, whose boxes stand at column `at` of them: each distinct tuple of that column counts as many times as the rows of `inside` hold it, and a box counts the cells of the second relation's grid that it holds.
    fn inside_count(&self, at: u16, second: Option<&Val>) -> Option<Option<u64>> {
        if usize::from(at) >= usize::from(self.width()) + 2 {
            return None;
        }
        let Some(grid) = second.and_then(grid_of) else { return Some(None) };
        let counted = self.counted(&[at])?;
        let mut total = 0u64;
        for (tuple, weight) in counted.tuples.iter().zip(&counted.weights) {
            total = total.saturating_add(weight.saturating_mul(area_of(*tuple, grid.h, grid.w)));
        }
        Some(Some(total))
    }

    /// The count of rows of a `join` of these rows with the second relation: for each tuple at the columns the join reads, the count of rows of `inside` that hold it times the count of rows of the second relation that hold the tuple at its columns. No value where the second relation is not one table or a column stands twice.
    fn join_count(&self, left: &[u16], right: &[u16], second: Option<&Val>) -> Option<Option<u64>> {
        let table = match second? {
            Val::None => return Some(None),
            Val::Empty => return Some(Some(0)),
            Val::Rows(parts) => match parts.as_slice() {
                [one] if one.columns.iter().enumerate().all(|(place, column)| usize::from(*column) == place) => one.table.clone(),
                _ => return None,
            },
            Val::Boxes(_) | Val::Joined(_) => return None,
        };
        if left.is_empty() || left.len() != right.len() || right.iter().any(|column| usize::from(*column) >= table.arity) {
            return None;
        }
        let mut order: Vec<usize> = (0..left.len()).collect();
        order.sort_unstable_by_key(|place| left[*place]);
        if order.windows(2).any(|pair| left[pair[0]] == left[pair[1]]) {
            return None;
        }
        let key: Vec<u16> = order.iter().map(|place| left[*place]).collect();
        let counted = self.counted(&key)?;
        let stride = key.len();
        let mut flat: Vec<Cell> = Vec::with_capacity(table.len * stride);
        for row in table.rows() {
            flat.extend(order.iter().map(|place| row[usize::from(right[*place])]));
        }
        let (tuples, repeats) = sum_sorted(&flat, stride, &vec![1u64; table.len]);
        // Both lists of tuples stand in order, so one pass along them pairs the tuples that agree.
        let (mut mine, mut theirs) = (0usize, 0usize);
        let mut total = 0u64;
        while mine < counted.weights.len() && theirs < repeats.len() {
            match counted.tuples[mine * stride..(mine + 1) * stride].cmp(&tuples[theirs * stride..(theirs + 1) * stride]) {
                Ordering::Less => mine += 1,
                Ordering::Greater => theirs += 1,
                Ordering::Equal => {
                    total = total.saturating_add(counted.weights[mine].saturating_mul(repeats[theirs]));
                    mine += 1;
                    theirs += 1;
                }
            }
        }
        Some(Some(total))
    }

    /// The count of rows that `step` gives over the rows of `inside`, where it needs no rows written. `second` is the step's second relation, where it has one. `None` where `step` is not of a form that is counted so, or where the count cannot be read from the tuples.
    pub fn count_of(&self, step: &Step, second: Option<&Val>) -> Option<Option<u64>> {
        let width = self.width();
        match step {
            Step::Part(part) => match part.step() {
                // The rows of a count over keys that are all columns of the relation are read as boxes.
                PartStep::Count { keys } if !keys.is_empty() && keys.iter().any(|key| *key >= width) => self.distinct_count(keys),
                // A class of each key's rows is one row at the key.
                PartStep::ClassOf { keys } if !keys.is_empty() => self.distinct_count(keys),
                PartStep::Inside { b } => self.inside_count(*b, second),
                _ => self.count_over(step, second),
            },
            Step::Join { left, right, .. } => self.join_count(left, right, second),
            Step::Semijoin { .. } | Step::Antijoin { .. } => self.count_over(step, second),
            _ => None,
        }
    }

    /// The count of rows that `step` gives over the rows of `inside`, where every row it gives holds a row of `inside` in the cells it reads, or it keeps whole rows of `inside`: a part that gives each row it takes followed by cells that the cells at some of its columns fix, a `semijoin` or an `antijoin` whose columns include the cell or its color, and a part that keeps the rows whose value is the most frequent of their key and reads the cell or its color. No rows of `inside` are written: the step runs over the distinct tuples at the columns it reads, written as rows of the arity of `inside` with 0 at each other column, and each row it gives counts as many times as `inside` holds its tuple. `second` is the step's second relation, where it has one. `None` where `step` is not of that form.
    fn count_over(&self, step: &Step, second: Option<&Val>) -> Option<Option<u64>> {
        let width = self.width();
        let mut key = match step {
            Step::Part(part) => part.row_columns().or_else(|| part.weighted_columns().filter(|columns| columns.iter().any(|column| *column >= width)))?,
            Step::Semijoin { left, .. } | Step::Antijoin { left, .. } if left.iter().any(|column| *column >= width) => left.to_vec(),
            _ => return None,
        };
        key.sort_unstable();
        key.dedup();
        if key.is_empty() {
            return None;
        }
        // A second relation that stands as the relations it comes from is read at the columns the step reads of it.
        let replaced;
        let second = match second {
            Some(Val::None) => return Some(None),
            Some(Val::Joined(joined)) => {
                replaced = joined.read_second(step)?;
                Some(&replaced)
            }
            Some(Val::Boxes(boxes)) => {
                replaced = boxes.read_second(step)?;
                Some(&replaced)
            }
            other => other,
        };
        if matches!(second, Some(Val::None)) {
            return Some(None);
        }
        let counted = self.counted(&key)?;
        let arity = usize::from(width) + 2;
        let wide = counted.wide(&key, arity);
        let mut total = 0u64;
        if let Step::Part(part) = step {
            if part.row_columns().is_none() {
                let counts: Vec<u64> = wide.rows().map(|row| counted.weight_of(&key, row)).collect::<Option<_>>()?;
                let kept = part.step().kept_rows(&wide, &counts)?;
                for row in kept.chunks_exact(arity) {
                    total = total.saturating_add(counted.weight_of(&key, row)?);
                }
                return Some(Some(total));
            }
        }
        let first = Val::of_table(wide.clone());
        let given = match step {
            Step::Part(part) => {
                let children: Vec<&Val> = std::iter::once(&first).chain(second).collect();
                part.step().run(&wide, &children)
            }
            Step::Semijoin { left, right } => semijoin(&first, second?, left, right),
            Step::Antijoin { left, right } => antijoin(&first, second?, left, right),
            _ => return None,
        };
        let given = match given {
            None | Some(Val::None) => return Some(None),
            Some(Val::Empty) => return Some(Some(0)),
            Some(given) => crate::gen_parts::flat(&given)?,
        };
        for row in given.rows() {
            total = total.saturating_add(counted.weight_of(&key, row)?);
        }
        Some(Some(total))
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

    /// The relation that `step` reads in place of these boxes as its second relation, where `reads_second` holds of it.
    pub fn read_second(&self, step: &Step) -> Option<Val> {
        let columns = second_columns(step)?;
        Some(self.rows_at(columns).map_or(Val::None, Val::of_table))
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

    /// The rows of `inside` that pass a `select`, written out: no value where they pass the output limit. A row of the relation passes with the cells of its box that the comparison keeps. A comparison of the cell column with a column of the relation keeps one cell at most, which is found from the box's extent.
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
            if out.len() > crate::native::output_limit() {
                crate::native::passed_output_limit();
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
            Step::Project { columns } => Some(self.project(columns)),
            Step::Select { at, op, other, drop } => Some(self.select(*at, *op, *other, *drop)),
            Step::Semijoin { left, right } => {
                let kept = semijoin(&Val::of_table(self.support()), children[1], left, right);
                self.kept(kept.unwrap_or(Val::None))
            }
            Step::Antijoin { left, right } => {
                let kept = antijoin(&Val::of_table(self.support()), children[1], left, right);
                self.kept(kept.unwrap_or(Val::None))
            }
            Step::All { reads, left_len, right } => {
                let (left, outer) = reads.split(*left_len);
                Some(match self.rows_at(reads) {
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
pub(crate) fn second_columns(step: &Step) -> Option<&Columns> {
    match step {
        Step::Semijoin { right, .. } | Step::Antijoin { right, .. } | Step::All { right, .. } => Some(right),
        Step::Part(part) => part.second_columns(),
        _ => None,
    }
}

/// What a `project` onto `columns` gives over a relation of `arity` columns, from `tuples`: the distinct tuples of its rows at the columns `key`, which stand in order, each once. `key` holds the columns of `columns`, each once.
pub(crate) fn project_tuples(tuples: &Arc<Table>, key: &[u16], columns: &[u16], arity: usize) -> Val {
    if tuples.len == 0 {
        return Val::Empty;
    }
    let places: Vec<usize> = columns.iter().map(|column| key.binary_search(column).expect("a projected column is one of the key")).collect();
    if key.len() == arity {
        // The tuples are all the relation's columns, so the table stays, and each column goes to its place in `columns`.
        let mut mapped = vec![0u16; places.len()];
        for (position, place) in places.iter().enumerate() {
            mapped[*place] = position as u16;
        }
        return Val::Rows(Arc::new(vec![Part { table: tuples.clone(), columns: mapped.into_boxed_slice() }]));
    }
    let table = if places.iter().enumerate().all(|(position, place)| position == *place) {
        tuples.clone()
    } else {
        let mut cells = Vec::with_capacity(tuples.len * places.len());
        for row in tuples.rows() {
            cells.extend(places.iter().map(|at| row[*at]));
        }
        Table::distinct(places.len(), cells)
    };
    Val::Rows(Arc::new(vec![Part { table, columns: (0..places.len() as u16).collect() }]))
}

/// The rows of `flat`, `stride` cells each, in ascending order, each once, with the sum of the `weights` of the rows that equal it.
fn sum_sorted(flat: &[Cell], stride: usize, weights: &[u64]) -> (Vec<Cell>, Vec<u64>) {
    let row = |at: u32| &flat[at as usize * stride..(at as usize + 1) * stride];
    let mut order: Vec<u32> = (0..weights.len() as u32).collect();
    order.sort_unstable_by(|a, b| row(*a).cmp(row(*b)));
    let mut tuples: Vec<Cell> = Vec::new();
    let mut sums: Vec<u64> = Vec::new();
    for at in order {
        let cells = row(at);
        match sums.last_mut() {
            Some(last) if tuples[tuples.len() - stride..] == *cells => *last += weights[at as usize],
            _ => {
                tuples.extend_from_slice(cells);
                sums.push(weights[at as usize]);
            }
        }
    }
    (tuples, sums)
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
