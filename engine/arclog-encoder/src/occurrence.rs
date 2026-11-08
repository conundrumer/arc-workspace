//! Where a colored pattern occurs in a grid, for the catalog's `occurs` kinds and the generator's `occurs` parts.
//!
//! A pattern is a sorted list of (row, column, color) with no repeats. A translation takes it into a grid where each
//! of its cells lands on a cell of the grid of the same color.

use crate::lookup::LookupMap;
use std::hash::Hash;

/// A cell of a pattern: (row, column, color).
pub type PatternCell = (i32, i32, u32);

/// A grid whose cells have colors.
pub trait Canvas {
    fn height(&self) -> i32;
    fn width(&self) -> i32;
    /// The color of the cell at a row and column that lie in the grid.
    fn color_at(&self, row: i32, column: i32) -> u32;
    /// How many cells have the color.
    fn count(&self, color: u32) -> usize;
    /// Calls `each` with the row and column of each cell of the color.
    fn each_place(&self, color: u32, each: impl FnMut(i32, i32));
}

/// Calls `each` with each translation (rows down, columns right) that takes the pattern into the grid.
pub fn for_each_move<G: Canvas>(grid: &G, pattern: &[PatternCell], mut each: impl FnMut(i32, i32)) {
    let (h, w) = (grid.height(), grid.width());
    let Some(anchor) = pattern.iter().min_by_key(|cell| (grid.count(cell.2), cell.0, cell.1)) else { return };
    let (top, bottom) = pattern.iter().fold((i32::MAX, i32::MIN), |(low, high), cell| (low.min(cell.0), high.max(cell.0)));
    let (left, right) = pattern.iter().fold((i32::MAX, i32::MIN), |(low, high), cell| (low.min(cell.1), high.max(cell.1)));
    if bottom - top >= h || right - left >= w {
        return;
    }
    grid.each_place(anchor.2, |row, column| {
        let (dr, dc) = (row - anchor.0, column - anchor.1);
        let fits = pattern.iter().all(|cell| {
            let (r, c) = (cell.0 + dr, cell.1 + dc);
            r >= 0 && c >= 0 && r < h && c < w && grid.color_at(r, c) == cell.2
        });
        if fits {
            each(dr, dc);
        }
    });
}

/// The translations that take the pattern into the grid, in order of the cell that the pattern's rarest-colored cell lands on.
pub fn moves<G: Canvas>(grid: &G, pattern: &[PatternCell]) -> Vec<(i32, i32)> {
    let mut out = Vec::new();
    for_each_move(grid, pattern, |dr, dc| out.push((dr, dc)));
    out
}

/// The last row and the last column of a pattern.
pub fn extent_of(pattern: &[PatternCell]) -> (i32, i32) {
    (pattern.iter().map(|cell| cell.0).max().unwrap_or(0), pattern.iter().map(|cell| cell.1).max().unwrap_or(0))
}

/// Calls `visit` with the number of each element of D4 other than the identity, in the order LR, TB, HT, CW, CC, DG, AD
/// (1 to 7), and the pattern's image under it, sorted. `extent` is the last row and the last column of the frame that the
/// pattern turns in. An image equal to the pattern or to an earlier image is not visited. Where `frame_matters`, an image
/// counts as equal only if it also turns the frame the same way: a quarter turn swaps the frame's height and width, so
/// on a frame that is not square its image differs from the cells' image under a half turn or a reflection.
/// It stops where `visit` gives true, and gives whether that happened.
pub fn each_turned_image(pattern: &[PatternCell], extent: (i32, i32), frame_matters: bool, mut visit: impl FnMut(usize, &[PatternCell]) -> bool) -> bool {
    let (r1, c1) = extent;
    let same_frame = |a: bool, b: bool| !frame_matters || r1 == c1 || a == b;
    let mut seen: Vec<(bool, Vec<PatternCell>)> = Vec::new();
    for which in 1..8 {
        let mut image: Vec<PatternCell> = pattern.iter().map(|&(r, c, color)| {
            let (y, z) = match which {
                1 => (r, c1 - c),
                2 => (r1 - r, c),
                3 => (r1 - r, c1 - c),
                4 => (c, r1 - r),
                5 => (c1 - c, r),
                6 => (c, r),
                _ => (c1 - c, r1 - r),
            };
            (y, z, color)
        }).collect();
        image.sort_unstable();
        let quarter = which >= 4;
        if (image == pattern && same_frame(quarter, false)) || seen.iter().any(|(held, cells)| *cells == image && same_frame(quarter, *held)) {
            continue;
        }
        if visit(which, &image) {
            return true;
        }
        seen.push((quarter, image));
    }
    false
}

/// The distinct patterns among the patterns of groups, each as sorted cells without repeats and the patterns in sorted order, and for each group the place of its pattern among them.
pub fn distinct_patterns<T: Ord + Hash>(groups: Vec<Vec<T>>) -> (Vec<Vec<T>>, Vec<u32>) {
    // Each pattern gets a number as it comes, and the numbers are then replaced by the places of the patterns in sorted order.
    let mut seen: LookupMap<Vec<T>, u32> = LookupMap::default();
    let mut of_group = Vec::with_capacity(groups.len());
    for mut pattern in groups {
        pattern.sort_unstable();
        pattern.dedup();
        let next = seen.len() as u32;
        of_group.push(*seen.entry(pattern).or_insert(next));
    }
    let mut place = vec![0u32; seen.len()];
    let mut distinct = Vec::with_capacity(seen.len());
    for (at, (pattern, number)) in seen.into_sorted_vec().into_iter().enumerate() {
        place[number as usize] = at as u32;
        distinct.push(pattern);
    }
    for which in &mut of_group {
        *which = place[*which as usize];
    }
    (distinct, of_group)
}
