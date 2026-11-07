//! What each feature family reads of one group of rows, one column or one pair
//! of columns at a time. A summary depends on the rows of the group and on the
//! columns it names, and on nothing else: not on the other columns of the
//! table, and not on the task's train pairs. The families combine summaries
//! with the pairs (`family.rs`), so a summary made once serves each table that
//! has the same column over the same rows.
//!
//! A summary reads each distinct row of the group once. A summary that a
//! feature reads as a set does not depend on how often a row occurs; the one
//! that counts rows (`SuitSummary::out`) takes the count of each distinct row.

use std::cell::OnceCell;

use crate::cells::{each_cell, frame_index, pack, parts, parts_in_frame, unpack, Frame, Parts};
use crate::group::Group;

/// A Color column over a group: its distinct values.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct ColorSummary {
    /// The colors 0 to 9 that the column has, as a bit set.
    pub mask: u16,
    /// The count of distinct values outside 0 to 9.
    pub other: u32,
}

impl ColorSummary {
    pub fn of(group: &Group<'_>, at: usize) -> ColorSummary {
        let mut mask = 0u16;
        let mut other: Vec<i32> = Vec::new();
        group.each_distinct(|row, _| {
            let color = row[at];
            if (0..10).contains(&color) {
                mask |= 1 << color;
            } else {
                other.push(color);
            }
        });
        other.sort_unstable();
        other.dedup();
        ColorSummary { mask, other: other.len() as u32 }
    }

    /// The count of distinct values.
    pub fn distinct(&self) -> usize {
        self.mask.count_ones() as usize + self.other as usize
    }
}

/// A Position column over a group: its distinct cells (the first and the third value of the column).
#[derive(Debug)]
pub struct CellsSummary {
    /// The distinct cells in the 32 by 32 corner of a grid.
    pub frame: Frame,
    /// The distinct cells elsewhere, packed and sorted.
    pub far: Vec<u64>,
    /// The count of distinct cells.
    pub len: usize,
    shapes: OnceCell<Parts>,
}

impl CellsSummary {
    pub fn of(group: &Group<'_>, at: usize) -> CellsSummary {
        let mut frame: Frame = [0; 32];
        let mut far: Vec<u64> = Vec::new();
        group.each_distinct(|row, _| {
            let (i, j) = (row[at], row[at + 2]);
            if frame_index(i, j).is_some() {
                frame[i as usize] |= 1 << j;
            } else {
                far.push(pack(i, j));
            }
        });
        far.sort_unstable();
        far.dedup();
        let len = frame.iter().map(|bits| bits.count_ones() as usize).sum::<usize>() + far.len();
        CellsSummary { frame, far, len, shapes: OnceCell::new() }
    }

    /// Calls `visit(row, column)` for each cell, in no particular order.
    pub fn each(&self, mut visit: impl FnMut(i32, i32)) {
        each_cell(&self.frame, &mut visit);
        for &cell in &self.far {
            let (i, j) = unpack(cell);
            visit(i, j);
        }
    }

    /// The 8-connected parts of at least 3 cells of the cells, each moved to the top left corner of its box.
    pub fn shapes(&self) -> &Parts {
        self.shapes.get_or_init(|| {
            if self.far.is_empty() {
                parts_in_frame(&self.frame, 3).moved_to_corner()
            } else {
                let mut all: Vec<u64> = Vec::with_capacity(self.len);
                each_cell(&self.frame, |i, j| all.push(pack(i, j)));
                all.extend_from_slice(&self.far);
                all.sort_unstable();
                parts(&all, 3).moved_to_corner()
            }
        })
    }
}

/// One cell of a Position column and the colors that a Color column has at the rows of the cell.
#[derive(Clone, Copy, Debug)]
pub struct PaintCell {
    pub row: i32,
    pub column: i32,
    /// The color, where the cell has one color; any of them otherwise.
    pub color: i32,
    /// Whether the cell has more than one color.
    pub conflict: bool,
}

/// A Position column and a Color column over a group: the colors at each cell.
#[derive(Debug)]
pub struct PaintSummary {
    /// The first color at each cell of the 32 by 32 corner; 0 where the cell has none.
    first: Vec<i32>,
    /// For each cell of the corner: 0 where it has no color, 1 where it has one color, 2 where it has more.
    state: Vec<u8>,
    /// The cells of the corner that have a color.
    touched: Vec<u16>,
    /// The cells elsewhere, each once.
    far: Vec<PaintCell>,
}

impl PaintSummary {
    pub fn of(group: &Group<'_>, position: usize, color: usize) -> PaintSummary {
        let mut first = vec![0i32; 1024];
        let mut state = vec![0u8; 1024];
        let mut touched: Vec<u16> = Vec::new();
        let mut elsewhere: Vec<(u64, i32)> = Vec::new();
        group.each_distinct(|row, _| {
            let (i, j, c) = (row[position], row[position + 2], row[color]);
            if let Some(at) = frame_index(i, j) {
                match state[at] {
                    0 => {
                        state[at] = 1;
                        first[at] = c;
                        touched.push(at as u16);
                    }
                    1 if first[at] != c => state[at] = 2,
                    _ => {}
                }
            } else {
                elsewhere.push((pack(i, j), c));
            }
        });
        elsewhere.sort_unstable();
        let mut far: Vec<PaintCell> = Vec::new();
        let mut from = 0;
        while from < elsewhere.len() {
            let mut to = from + 1;
            while to < elsewhere.len() && elsewhere[to].0 == elsewhere[from].0 {
                to += 1;
            }
            let (row, column) = unpack(elsewhere[from].0);
            far.push(PaintCell { row, column, color: elsewhere[from].1, conflict: elsewhere[to - 1].1 != elsewhere[from].1 });
            from = to;
        }
        PaintSummary { first, state, touched, far }
    }

    /// Each distinct cell once, in no particular order.
    pub fn cells(&self) -> impl Iterator<Item = PaintCell> + '_ {
        let corner = self.touched.iter().map(|&at| PaintCell { row: i32::from(at >> 5), column: i32::from(at & 31), color: self.first[at as usize], conflict: self.state[at as usize] == 2 });
        corner.chain(self.far.iter().copied())
    }
}

/// Which columns a `SuitSummary` reads.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum SuitKind {
    /// A Position or Box column and a Color column.
    CellColor,
    /// A Position or Box column alone.
    Cell,
    /// A Color column alone.
    Color,
}

impl SuitKind {
    /// The count of places: the cells of a 30 by 30 grid times 10 colors, the cells, or the colors.
    pub const fn places(self) -> usize {
        match self {
            SuitKind::CellColor => 9000,
            SuitKind::Cell => 900,
            SuitKind::Color => 10,
        }
    }
}

/// A Position or Box column, a Color column or both, over a group, as the cells of a 30 by 30 grid with 10 colors.
#[derive(Debug)]
pub struct SuitSummary {
    pub kind: SuitKind,
    /// A bit set of the distinct places inside the grid: 30 * row + column, times 10 plus the color where there is a Color column.
    pub places: Vec<u64>,
    /// The count of rows outside the grid, or with a color outside 0 to 9.
    pub out: usize,
}

impl SuitSummary {
    /// `position` is the first cell of a Position or Box column, `color` that of a Color column; either may be None.
    pub fn of(group: &Group<'_>, position: Option<usize>, color: Option<usize>) -> SuitSummary {
        let kind = match (position, color) {
            (Some(_), Some(_)) => SuitKind::CellColor,
            (Some(_), None) => SuitKind::Cell,
            _ => SuitKind::Color,
        };
        let mut places = vec![0u64; kind.places().div_ceil(64)];
        let mut out = 0;
        match (position, color) {
            (Some(p), Some(c)) => {
                group.each_distinct(|row, count| {
                    let (i, j, color) = (row[p] as u32, row[p + 2] as u32, row[c] as u32);
                    if i < 30 && j < 30 && color < 10 {
                        let key = (30 * i + j) * 10 + color;
                        places[key as usize >> 6] |= 1 << (key & 63);
                    } else {
                        out += count;
                    }
                });
            }
            (Some(p), None) => {
                group.each_distinct(|row, count| {
                    let (i, j) = (row[p] as u32, row[p + 2] as u32);
                    if i < 30 && j < 30 {
                        let key = 30 * i + j;
                        places[key as usize >> 6] |= 1 << (key & 63);
                    } else {
                        out += count;
                    }
                });
            }
            (None, Some(c)) => {
                group.each_distinct(|row, count| {
                    let color = row[c] as u32;
                    if color < 10 {
                        places[0] |= 1 << color;
                    } else {
                        out += count;
                    }
                });
            }
            (None, None) => {}
        }
        SuitSummary { kind, places, out }
    }
}

/// The distinct values of a column over some rows. A column of one cell has its values as numbers; a column of four cells has
/// each value as the four cells together.
#[derive(Clone, Debug)]
pub enum ValueSet {
    /// Values that lie less than 128 apart: the bit `k` is set where the value `base + k` is held.
    Bits { base: i64, bits: u128 },
    /// The values, distinct, each as its cells one after another, 32 bits each.
    List(Vec<u128>),
}

impl ValueSet {
    /// The values of the column that starts at the cell `at` and has `width` cells.
    pub fn of(rows: &[&[i32]], at: usize, width: usize) -> ValueSet {
        if width == 1 {
            // Values within 64 of the first one are bits of a 128 bit set around it.
            let Some(first) = rows.first().map(|row| i64::from(row[at])) else { return ValueSet::Bits { base: 0, bits: 0 } };
            let base = first - 64;
            let mut bits = 0u128;
            let mut within = true;
            for row in rows {
                let place = i64::from(row[at]) - base;
                if (0..128).contains(&place) {
                    bits |= 1u128 << place;
                } else {
                    within = false;
                    break;
                }
            }
            if within {
                return ValueSet::Bits { base, bits };
            }
            let (mut low, mut high) = (i32::MAX, i32::MIN);
            for row in rows {
                low = low.min(row[at]);
                high = high.max(row[at]);
            }
            if i64::from(high) - i64::from(low) < 128 {
                let bits = rows.iter().fold(0u128, |bits, row| bits | 1u128 << (i64::from(row[at]) - i64::from(low)));
                return ValueSet::Bits { base: i64::from(low), bits };
            }
        }
        let key = |row: &[i32]| row[at..at + width].iter().fold(0u128, |held, &cell| held << 32 | u128::from(cell as u32));
        let mut keys: Vec<u128> = Vec::with_capacity(rows.len());
        // Rows that are in order of this column have its values in runs, so the distinct ones are the first of each run.
        let mut in_order = true;
        for row in rows {
            let value = key(row);
            match keys.last() {
                Some(&last) if last == value => {}
                Some(&last) if last > value => {
                    in_order = false;
                    break;
                }
                _ => keys.push(value),
            }
        }
        if in_order {
            return ValueSet::List(keys);
        }
        let mut set = KeySet::new(rows.len());
        for row in rows {
            set.insert(key(row));
        }
        ValueSet::List(set.into_keys())
    }

    /// The count of distinct values.
    pub fn len(&self) -> usize {
        match self {
            ValueSet::Bits { bits, .. } => bits.count_ones() as usize,
            ValueSet::List(list) => list.len(),
        }
    }
}

/// A set of keys.
struct KeySet {
    /// Each slot holds 1 plus the index of its key in `found`; 0 where it is empty.
    table: Vec<u32>,
    shift: u32,
    found: Vec<u128>,
}

impl KeySet {
    /// A set for at most `count` keys.
    fn new(count: usize) -> KeySet {
        let size = (count + count / 2).next_power_of_two().max(16);
        KeySet { table: vec![0u32; size], shift: 64 - size.trailing_zeros(), found: Vec::with_capacity(count) }
    }

    fn insert(&mut self, key: u128) {
        let mask = self.table.len() - 1;
        let hash = ((key as u64) ^ ((key >> 64) as u64).wrapping_mul(0x517c_c1b7_2722_0a95)).wrapping_mul(0x9e37_79b9_7f4a_7c15);
        let mut slot = (hash >> self.shift) as usize;
        loop {
            let held = self.table[slot] as usize;
            if held == 0 {
                self.found.push(key);
                self.table[slot] = self.found.len() as u32;
                return;
            }
            if self.found[held - 1] == key {
                return;
            }
            slot = (slot + 1) & mask;
        }
    }

    fn into_keys(self) -> Vec<u128> {
        self.found
    }
}
