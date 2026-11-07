//! The rows of `inside`, as the boxes they come from.
//!
//! `inside` gives each row of a relation with each cell of the grid that lies in the row's box.
//! A [`Boxes`] holds the relation and the grid, and the count of those rows, which is the sum of
//! the clipped box areas. It writes the rows only where an operator reads a cell of a box, and
//! then once, up to `CELL_CAP` cells. An operator that reads the columns of the relation alone
//! takes what it needs from the relation's rows whose box has a cell in the grid.

use std::sync::{Arc, OnceLock};

use crate::gen_constants::{box_bits, margins_of};
use crate::gen_parts::GridView;
use crate::native::{hash_words, project, select, Cell, FastMap, Step, Table, Val, CELL_CAP};

/// Marks the hash of a [`Boxes`], which no other value's hash has.
const BOXES_WORD: u64 = 0x426f_7865_7352_6f77;

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
    /// The rows of `inside`, once written: no value where they pass `CELL_CAP` cells.
    written: OnceLock<Val>,
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
        Val::Boxes(Arc::new(Boxes { table: table.clone(), at, grid, grid_hash, hash, rows, support: OnceLock::new(), written: OnceLock::new() }))
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

    /// Whether the rows of `inside` can be written out, in at most `CELL_CAP` cells.
    pub fn fits(&self) -> bool {
        self.rows.saturating_mul(self.table.arity as u64 + 2) <= CELL_CAP as u64
    }

    /// The rows of `inside` written out, or no value where they pass `CELL_CAP` cells.
    pub fn written(&self) -> Val {
        let held = self.written.get_or_init(|| self.write());
        if matches!(held, Val::None) {
            crate::bounds::mark(crate::bounds::Bound::InsideCells);
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

    /// Whether `step` takes what it needs from the relation's rows, with no cell of a box.
    pub fn reads(&self, step: &Step) -> bool {
        let width = self.table.arity as u16;
        match step {
            Step::Project { columns } => columns.iter().all(|column| *column < width),
            Step::Select { at, other, drop, .. } => *at < width && other.is_none_or(|other| other < width) && *drop != Some(self.at),
            Step::Part(part) => part.reads_boxes(width),
            _ => false,
        }
    }

    /// What `step` gives over these rows, where `reads` holds of it.
    pub fn read(&self, step: &Step, children: &[&Val]) -> Option<Val> {
        if !self.reads(step) {
            return None;
        }
        match step {
            Step::Project { columns } => Some(project(&Val::of_table(self.support()), columns)),
            Step::Select { at, op, other, drop } => {
                // The rows that stay are those of the relation, which keep the box column's place unless a column before it goes.
                let Some(kept) = select(&Val::of_table(self.support()), *at, *op, *other, *drop) else { return Some(Val::None) };
                let table = match &kept {
                    Val::Empty => return Some(Val::Empty),
                    Val::Rows(parts) => match parts.as_slice() {
                        [one] if one.columns.iter().enumerate().all(|(place, column)| usize::from(*column) == place) => one.table.clone(),
                        _ => return None,
                    },
                    _ => return None,
                };
                let moved = if drop.is_some_and(|dropped| dropped < self.at) { self.at - 1 } else { self.at };
                Some(Boxes::of(&table, moved, self.grid.clone(), self.grid_hash))
            }
            Step::Part(part) => part.read_boxes(self, children),
            _ => None,
        }
    }
}
