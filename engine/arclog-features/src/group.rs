//! A group of rows: the rows of one TableRows at one example, with the
//! distinct rows among them.

use std::borrow::Cow;
use std::cell::OnceCell;

/// A hash of a row's cells. Rows with different cells may have one hash.
pub(crate) fn row_hash(row: &[i32]) -> u64 {
    const K: u64 = 0x517c_c1b7_2722_0a95;
    let mut hash = 0u64;
    let mut pairs = row.chunks_exact(2);
    for pair in &mut pairs {
        let word = u64::from(pair[0] as u32) | u64::from(pair[1] as u32) << 32;
        hash = (hash.rotate_left(5) ^ word).wrapping_mul(K);
    }
    if let [last] = pairs.remainder() {
        hash = (hash.rotate_left(5) ^ u64::from(*last as u32)).wrapping_mul(K);
    }
    (hash ^ hash >> 32).wrapping_mul(0x9e37_79b9_7f4a_7c15)
}

/// A row that a group has, with the count of rows of the group that have the same cells.
#[derive(Clone, Copy, Debug)]
struct DistinctRow {
    /// The index of the first row with these cells.
    row: u32,
    /// The count of rows with these cells.
    count: u32,
    /// The hash of the cells.
    hash: u64,
}

/// The distinct rows of a group.
#[derive(Clone)]
enum Distinct {
    /// The rows are in strictly increasing order, so each is distinct.
    Sorted,
    /// The distinct rows, found by the hash of their cells.
    Hashed {
        found: Vec<DistinctRow>,
        /// For each slot of a hash table: 0 where it is empty, else 1 plus the index of the row in `found`.
        table: Vec<u32>,
        shift: u32,
    },
}

/// The rows of a group, as one run of cells.
pub struct Group<'a> {
    /// The value of the Example column that the rows share, or the example that the TableRows names.
    pub(crate) key: usize,
    cells: Cow<'a, [i32]>,
    /// The count of cells of a row.
    width: usize,
    /// The count of rows.
    len: usize,
    distinct: OnceCell<Distinct>,
}

fn same_cells(a: &[i32], b: &[i32]) -> bool {
    a.len() == b.len() && a.iter().zip(b).all(|(x, y)| x == y)
}

/// Each distinct row of a group once, with the count of rows that have its cells.
#[derive(Clone)]
pub struct DistinctRows<'g> {
    cells: &'g [i32],
    width: usize,
    next: usize,
    end: usize,
    found: Option<std::slice::Iter<'g, DistinctRow>>,
}

impl<'g> Iterator for DistinctRows<'g> {
    type Item = (&'g [i32], usize);

    fn next(&mut self) -> Option<Self::Item> {
        if let Some(found) = &mut self.found {
            let held = found.next()?;
            Some((&self.cells[held.row as usize * self.width..(held.row as usize + 1) * self.width], held.count as usize))
        } else if self.next < self.end {
            let row = &self.cells[self.next * self.width..(self.next + 1) * self.width];
            self.next += 1;
            Some((row, 1))
        } else {
            None
        }
    }
}

impl<'a> Group<'a> {
    /// A group of `len` rows of `width` cells each. Where `width` is 0, `cells` is empty.
    pub(crate) fn new(key: usize, cells: Cow<'a, [i32]>, width: usize, len: usize) -> Group<'a> {
        Group { key, cells, width, len, distinct: OnceCell::new() }
    }

    /// The count of rows.
    pub fn len(&self) -> usize {
        self.len
    }

    pub fn is_empty(&self) -> bool {
        self.len == 0
    }

    /// The cells of row `at`.
    pub fn row(&self, at: usize) -> &[i32] {
        &self.cells[at * self.width..(at + 1) * self.width]
    }

    fn kind(&self) -> &Distinct {
        self.distinct.get_or_init(|| self.find_distinct())
    }

    /// Whether each row is less than the next.
    pub fn is_sorted(&self) -> bool {
        matches!(self.kind(), Distinct::Sorted)
    }

    /// The count of distinct rows.
    pub fn distinct_count(&self) -> usize {
        match self.kind() {
            Distinct::Sorted => self.len,
            Distinct::Hashed { found, .. } => found.len(),
        }
    }

    /// Each distinct row once, with its count.
    pub fn distinct_rows(&self) -> DistinctRows<'_> {
        let found = match self.kind() {
            Distinct::Sorted => None,
            Distinct::Hashed { found, .. } => Some(found.iter()),
        };
        DistinctRows { cells: &self.cells, width: self.width, next: 0, end: self.len, found }
    }

    /// Calls `visit(row, count)` for each distinct row once, where `count` is the count of rows with the same cells.
    pub fn each_distinct<'g>(&'g self, mut visit: impl FnMut(&'g [i32], usize)) {
        match self.kind() {
            Distinct::Sorted => {
                if self.width == 0 {
                    if self.len == 1 {
                        visit(&[], 1);
                    }
                } else {
                    for row in self.cells.chunks_exact(self.width).take(self.len) {
                        visit(row, 1);
                    }
                }
            }
            Distinct::Hashed { found, .. } => {
                for held in found {
                    visit(&self.cells[held.row as usize * self.width..(held.row as usize + 1) * self.width], held.count as usize);
                }
            }
        }
    }

    /// Calls `visit(hash, row)` for each distinct row once.
    pub(crate) fn each_hashed<'g>(&'g self, mut visit: impl FnMut(u64, &'g [i32])) {
        match self.kind() {
            Distinct::Sorted => self.each_distinct(|row, _| visit(row_hash(row), row)),
            Distinct::Hashed { found, .. } => {
                for held in found {
                    visit(held.hash, &self.cells[held.row as usize * self.width..(held.row as usize + 1) * self.width]);
                }
            }
        }
    }

    /// Takes the distinct rows of `other`, which has the same rows as this group, in place of finding them.
    pub(crate) fn share_distinct(&self, other: &Group<'_>) {
        if self.distinct.get().is_none() {
            let _ = self.distinct.set(other.kind().clone());
        }
    }

    /// Whether the two groups have the same rows, in the same order.
    pub fn same_rows_as(&self, other: &Group<'_>) -> bool {
        self.len == other.len && self.width == other.width && same_cells(&self.cells[..self.len * self.width], &other.cells[..other.len * other.width])
    }

    /// Whether the two groups have the same distinct rows.
    pub fn same_distinct_rows(&self, other: &Group<'_>) -> bool {
        if self.distinct_count() != other.distinct_count() {
            return false;
        }
        if let (Distinct::Sorted, Distinct::Sorted) = (self.kind(), other.kind()) {
            return same_cells(&self.cells[..self.len * self.width], &other.cells[..other.len * other.width]);
        }
        other.distinct_rows().all(|(row, _)| self.has_row(row_hash(row), row))
    }

    /// Whether the group has a row with the cells `row`, whose hash is `hash`.
    pub fn has_row(&self, hash: u64, row: &[i32]) -> bool {
        match self.kind() {
            Distinct::Sorted => {
                let (mut low, mut high) = (0, self.len);
                while low < high {
                    let middle = (low + high) / 2;
                    match self.row(middle).cmp(row) {
                        std::cmp::Ordering::Less => low = middle + 1,
                        std::cmp::Ordering::Equal => return true,
                        std::cmp::Ordering::Greater => high = middle,
                    }
                }
                false
            }
            Distinct::Hashed { found, table, shift } => {
                let mask = table.len() - 1;
                let mut slot = (hash >> shift) as usize;
                loop {
                    let held = table[slot] as usize;
                    if held == 0 {
                        return false;
                    }
                    let other = &found[held - 1];
                    if other.hash == hash && same_cells(self.row(other.row as usize), row) {
                        return true;
                    }
                    slot = (slot + 1) & mask;
                }
            }
        }
    }

    /// Whether each row is less than the next, comparing the cells in order.
    fn is_increasing(&self) -> bool {
        let (cells, width) = (&self.cells[..], self.width);
        let mut at = 0;
        for _ in 1..self.len {
            let next = at + width;
            if cells[at] != cells[next] {
                if cells[at] > cells[next] {
                    return false;
                }
            } else if cells[at..next] >= cells[next..next + width] {
                return false;
            }
            at = next;
        }
        true
    }

    fn find_distinct(&self) -> Distinct {
        if self.len <= 1 || self.width > 0 && self.is_increasing() {
            return Distinct::Sorted;
        }
        if self.width == 0 {
            // All the rows are empty and equal.
            let mut table = vec![0u32; 16];
            table[0] = 1;
            return Distinct::Hashed { found: vec![DistinctRow { row: 0, count: self.len as u32, hash: 0 }], table, shift: 60 };
        }
        let width = self.width;
        let size = (2 * self.len).next_power_of_two().max(16);
        let shift = 64 - size.trailing_zeros();
        let mut table = vec![0u32; size];
        let mut found: Vec<DistinctRow> = Vec::new();
        for (at, row) in self.cells.chunks_exact(width).take(self.len).enumerate() {
            let hash = row_hash(row);
            let mut slot = (hash >> shift) as usize;
            loop {
                let held = table[slot] as usize;
                if held == 0 {
                    found.push(DistinctRow { row: at as u32, count: 1, hash });
                    table[slot] = found.len() as u32;
                    break;
                }
                let other = &mut found[held - 1];
                if other.hash == hash && same_cells(&self.cells[other.row as usize * width..(other.row as usize + 1) * width], row) {
                    other.count += 1;
                    break;
                }
                slot = (slot + 1) & (size - 1);
            }
        }
        Distinct::Hashed { found, table, shift }
    }
}

/// A set of rows, each given with its hash from `row_hash`.
pub(crate) struct RowSet<'r> {
    /// Each slot holds the high half of the hash of its row and 1 plus the index of the row in `found`; 0 where it is empty.
    table: Vec<u64>,
    shift: u32,
    found: Vec<&'r [i32]>,
}

impl<'r> RowSet<'r> {
    /// A set for at most `count` rows.
    pub fn new(count: usize) -> RowSet<'r> {
        let size = (count + count / 2).next_power_of_two().max(16);
        RowSet { table: vec![0u64; size], shift: 64 - size.trailing_zeros(), found: Vec::with_capacity(count) }
    }

    /// Adds the row if the set has no row with the same cells.
    pub fn insert(&mut self, hash: u64, row: &'r [i32]) {
        let mask = self.table.len() - 1;
        let mut slot = (hash >> self.shift) as usize;
        let tag = hash & 0xffff_ffff_0000_0000;
        loop {
            let held = self.table[slot];
            if held == 0 {
                self.found.push(row);
                self.table[slot] = tag | self.found.len() as u64;
                return;
            }
            if held & 0xffff_ffff_0000_0000 == tag && same_cells(self.found[(held & 0xffff_ffff) as usize - 1], row) {
                return;
            }
            slot = (slot + 1) & mask;
        }
    }

    /// The rows in the set, in the order they were added.
    pub fn into_rows(self) -> Vec<&'r [i32]> {
        self.found
    }
}

/// The rows of two lists that are in increasing order, once each, in increasing order.
pub(crate) fn merged<'r>(a: &[&'r [i32]], b: &[&'r [i32]]) -> Vec<&'r [i32]> {
    let mut out: Vec<&'r [i32]> = Vec::with_capacity(a.len() + b.len());
    let (mut x, mut y) = (0, 0);
    while x < a.len() && y < b.len() {
        match a[x].cmp(b[y]) {
            std::cmp::Ordering::Less => {
                out.push(a[x]);
                x += 1;
            }
            std::cmp::Ordering::Greater => {
                out.push(b[y]);
                y += 1;
            }
            std::cmp::Ordering::Equal => {
                out.push(a[x]);
                x += 1;
                y += 1;
            }
        }
    }
    out.extend_from_slice(&a[x..]);
    out.extend_from_slice(&b[y..]);
    out
}
