//! Computations over sets of cells that the catalog's facts and the generator's parts both make: the class of a
//! cell set up to a move or up to D4, its symmetries, the connected pieces of a set of places, and how two sets
//! stand to each other.

use crate::native::hash_words;

/// The eight steps to a neighbor: four along a row or column, then four diagonal.
pub const STEPS: [(i32, i32); 8] = [(-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (-1, 1), (1, -1), (1, 1)];

/// The image of a cell under element `which` of D4 (0 to 7, the identity first) in a box with the last row `r1` and
/// the last column `c1`, where the cell is given relative to the box's first row and column.
#[inline]
fn turned_cell(which: usize, r: u8, c: u8, r1: u8, c1: u8) -> (u8, u8) {
    match which {
        0 => (r, c),
        1 => (r, c1 - c),
        2 => (r1 - r, c),
        3 => (r1 - r, c1 - c),
        4 => (c, r),
        5 => (c, r1 - r),
        6 => (c1 - c, r),
        _ => (c1 - c, r1 - r),
    }
}

/// The first row, the first column, and the last row and last column relative to those, of the box of the cells.
fn frame_of(cells: &[(u8, u8)]) -> (u8, u8, u8, u8) {
    let r0 = cells.iter().map(|cell| cell.0).min().unwrap_or(0);
    let c0 = cells.iter().map(|cell| cell.1).min().unwrap_or(0);
    let r1 = cells.iter().map(|cell| cell.0 - r0).max().unwrap_or(0);
    let c1 = cells.iter().map(|cell| cell.1 - c0).max().unwrap_or(0);
    (r0, c0, r1, c1)
}

/// One cell set per class of cell sets equal up to a move, and with `turned` also up to a rotation or a reflection:
/// the smallest sorted image of the cells, moved so that its box starts at (0, 0).
pub fn class_of(cells: &[(u8, u8)], turned: bool) -> Vec<(u8, u8)> {
    let (r0, c0, r1, c1) = frame_of(cells);
    let mut best: Vec<(u8, u8)> = Vec::new();
    let mut image: Vec<(u8, u8)> = Vec::with_capacity(cells.len());
    // Cells that stand sorted without repeats make images that are written in order from the cells by row and the cells by column, with no sort.
    let ordered = cells.windows(2).all(|pair| pair[0] < pair[1]);
    let by_columns = if ordered && turned {
        let mut by_columns = cells.to_vec();
        by_columns.sort_unstable_by_key(|&(r, c)| (c, r));
        by_columns
    } else {
        Vec::new()
    };
    for which in 0..if turned { 8 } else { 1 } {
        image.clear();
        if ordered {
            write_ordered_image(which, cells, &by_columns, (r0, c0, r1, c1), &mut image);
        } else {
            image.extend(cells.iter().map(|(r, c)| turned_cell(which, r - r0, c - c0, r1, c1)));
            image.sort_unstable();
        }
        if which == 0 || image < best {
            std::mem::swap(&mut best, &mut image);
        }
    }
    best
}

/// Writes to `image` the sorted image of cells under element `which` of D4, as `class_of` makes it. `by_rows` holds the cells sorted by row then column without repeats, and `by_columns` holds them sorted by column then row. The images of 0 to 3 sort by the cells' rows and the images of 4 to 7 by their columns. Within each run of cells of one row, or of one column, a turn keeps the order or reverses it, and it keeps the order of the runs or reverses it.
fn write_ordered_image(which: usize, by_rows: &[(u8, u8)], by_columns: &[(u8, u8)], (r0, c0, r1, c1): (u8, u8, u8, u8), image: &mut Vec<(u8, u8)>) {
    let along_rows = which < 4;
    let list = if along_rows { by_rows } else { by_columns };
    let reverse_runs = matches!(which, 2 | 3 | 6 | 7);
    let reverse_within = matches!(which, 1 | 3 | 5 | 7);
    let write_run = |run: &[(u8, u8)], image: &mut Vec<(u8, u8)>| {
        let turn = |&(r, c): &(u8, u8)| turned_cell(which, r - r0, c - c0, r1, c1);
        if reverse_within {
            image.extend(run.iter().rev().map(turn));
        } else {
            image.extend(run.iter().map(turn));
        }
    };
    let runs = list.chunk_by(|a, b| if along_rows { a.0 == b.0 } else { a.1 == b.1 });
    if reverse_runs {
        for run in runs.rev() {
            write_run(run, image);
        }
    } else {
        for run in runs {
            write_run(run, image);
        }
    }
}

/// A cell set moved so that its box starts at (0, 0), sorted.
pub fn normalized(cells: &[(u8, u8)]) -> Vec<(u8, u8)> {
    class_of(cells, false)
}

/// One form per class of cell sets equal up to a move, a rotation or a reflection.
pub fn canon(cells: &[(u8, u8)]) -> Vec<(u8, u8)> {
    class_of(cells, true)
}

/// A hash per class of cell sets, up to a move, and with `turned` also up to a rotation or a reflection.
pub fn shape_hash(cells: &[(u8, u8)], turned: bool) -> u32 {
    hash_words(class_of(cells, turned).iter().map(|cell| u64::from(cell.0) << 8 | u64::from(cell.1))) as u32
}

/// The eight symmetries that map a cell set onto itself, up to a move. The cells stand without repeats.
pub fn symmetry_count(cells: &[(u8, u8)]) -> u32 {
    let (r0, c0, r1, c1) = frame_of(cells);
    let (h, w) = (usize::from(r1) + 1, usize::from(c1) + 1);
    let mut held = vec![false; h * w];
    for (r, c) in cells {
        held[usize::from(r - r0) * w + usize::from(c - c0)] = true;
    }
    (0..8).filter(|which| cells.iter().all(|(r, c)| {
        let (a, b) = turned_cell(*which, r - r0, c - c0, r1, c1);
        usize::from(a) < h && usize::from(b) < w && held[usize::from(a) * w + usize::from(b)]
    })).count() as u32
}

/// The place that a step from a place in a grid of `h` rows and `w` columns lands on, where it lands in the grid.
#[inline]
pub fn grid_neighbor(h: usize, w: usize, at: usize, dr: i32, dc: i32) -> Option<usize> {
    let (nr, nc) = ((at / w) as i32 + dr, (at % w) as i32 + dc);
    (nr >= 0 && nc >= 0 && (nr as usize) < h && (nc as usize) < w).then(|| nr as usize * w + nc as usize)
}

/// The memory of a walk over places 0 to `count`, which one walk after another reuse.
#[derive(Default)]
pub struct Walk {
    seen: Vec<bool>,
    stack: Vec<usize>,
    piece: Vec<usize>,
}

impl Walk {
    /// Takes every step from each place on the stack, and from each place that a step reaches. `neighbor(at, dr, dc)` gives the
    /// place that the step reaches from `at`, if the walk may enter it. `visit` gets each place on the stack and each place reached.
    fn grow(&mut self, steps: &[(i32, i32)], neighbor: &impl Fn(usize, i32, i32) -> Option<usize>, mut visit: impl FnMut(usize)) {
        while let Some(at) = self.stack.pop() {
            visit(at);
            for (dr, dc) in steps {
                if let Some(next) = neighbor(at, *dr, *dc) {
                    if !self.seen[next] {
                        self.seen[next] = true;
                        self.stack.push(next);
                    }
                }
            }
        }
    }

    /// The places among 0 to `count` that a walk reaches from the seeds, the seeds included. `neighbor` is as for a piece.
    pub fn reach(&mut self, count: usize, steps: &[(i32, i32)], seeds: &[usize], neighbor: impl Fn(usize, i32, i32) -> Option<usize>) -> &[bool] {
        self.seen.clear();
        self.seen.resize(count, false);
        self.stack.clear();
        for seed in seeds {
            if !self.seen[*seed] {
                self.seen[*seed] = true;
                self.stack.push(*seed);
            }
        }
        self.grow(steps, &neighbor, |_| {});
        &self.seen
    }

    /// Calls `each` with the connected pieces of the places among 0 to `count` that `holds` accepts: the places of a piece in the
    /// order that a walk reaches them, and the pieces in order of their least place. `neighbor(at, dr, dc)` gives the held place
    /// that the step reaches from the held place `at`, if there is one.
    pub fn pieces(&mut self, count: usize, steps: &[(i32, i32)], holds: impl Fn(usize) -> bool, neighbor: impl Fn(usize, i32, i32) -> Option<usize>, mut each: impl FnMut(&[usize])) {
        self.seen.clear();
        self.seen.resize(count, false);
        let mut piece = std::mem::take(&mut self.piece);
        for start in 0..count {
            if self.seen[start] || !holds(start) {
                continue;
            }
            self.seen[start] = true;
            self.stack.clear();
            self.stack.push(start);
            piece.clear();
            self.grow(steps, &neighbor, |at| piece.push(at));
            each(&piece);
        }
        self.piece = piece;
    }
}

/// Calls `each` with the places of each connected piece of the places of an `h` by `w` grid that `holds` accepts, by the steps given.
pub fn grid_pieces(h: usize, w: usize, steps: &[(i32, i32)], holds: impl Fn(usize) -> bool, each: impl FnMut(&[usize])) {
    Walk::default().pieces(h * w, steps, &holds, |at, dr, dc| grid_neighbor(h, w, at, dr, dc).filter(|next| holds(*next)), each);
}

/// How two sets of values stand to each other.
#[derive(Clone, Copy, Debug, PartialEq, Eq, serde::Serialize, serde::Deserialize)]
pub enum SetRelation {
    Equal,
    Subset,
    Superset,
    Overlap,
    Disjoint,
    Complement,
}

impl SetRelation {
    pub fn word(self) -> &'static str {
        match self {
            SetRelation::Equal => "equal",
            SetRelation::Subset => "subset",
            SetRelation::Superset => "superset",
            SetRelation::Overlap => "overlap",
            SetRelation::Disjoint => "disjoint",
            SetRelation::Complement => "complement",
        }
    }
}

/// How two sets stand to each other, given whether the first has a value outside the second (`left`), whether the second has one
/// outside the first (`right`), whether they share a value (`both`), and whether together they fill the universe (`covers`).
/// Disjoint sets that fill the universe are complements.
pub fn relation(left: bool, right: bool, both: bool, covers: bool) -> SetRelation {
    if !left && !right {
        SetRelation::Equal
    } else if !both {
        if covers { SetRelation::Complement } else { SetRelation::Disjoint }
    } else if !left {
        SetRelation::Subset
    } else if !right {
        SetRelation::Superset
    } else {
        SetRelation::Overlap
    }
}
