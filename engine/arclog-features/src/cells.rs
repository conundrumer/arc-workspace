//! Cells packed into one integer, and the 8-connected parts of a set of cells.

const SIGN: u32 = 0x8000_0000;

/// The cell (row, column) as one integer. The order of the integers is the
/// order of the (row, column) pairs.
pub(crate) fn pack(row: i32, column: i32) -> u64 {
    (u64::from(row as u32 ^ SIGN) << 32) | u64::from(column as u32 ^ SIGN)
}

/// The (row, column) of a packed cell.
pub(crate) fn unpack(key: u64) -> (i32, i32) {
    (((key >> 32) as u32 ^ SIGN) as i32, (key as u32 ^ SIGN) as i32)
}

/// Whether the cell (row, column) is inside a grid of `height` by `width`; if so, its index in the grid's cells.
pub(crate) fn index_in(row: i32, column: i32, height: usize, width: usize) -> Option<usize> {
    if row >= 0 && column >= 0 && (row as usize) < height && (column as usize) < width {
        Some(row as usize * width + column as usize)
    } else {
        None
    }
}

/// A list of parts, each a run of packed cells, one after another.
#[derive(Debug, Default)]
pub struct Parts {
    cells: Vec<u64>,
    /// The end of each part in `cells`.
    ends: Vec<usize>,
}

impl Parts {
    pub fn iter(&self) -> impl Iterator<Item = &[u64]> + '_ {
        let mut start = 0;
        self.ends.iter().map(move |&end| {
            let part = &self.cells[start..end];
            start = end;
            part
        })
    }

    pub fn is_empty(&self) -> bool {
        self.ends.is_empty()
    }

    /// The parts that the lists give, each of at least one cell.
    pub fn from_lists(lists: &[Vec<u64>]) -> Parts {
        let mut parts = Parts::default();
        for list in lists {
            parts.cells.extend_from_slice(list);
            parts.ends.push(parts.cells.len());
        }
        parts
    }

    /// Each part moved to the top left corner of its box. A part that is sorted stays sorted.
    pub fn moved_to_corner(mut self) -> Parts {
        let mut start = 0;
        for &end in &self.ends {
            let part = &mut self.cells[start..end];
            let top = unpack(part[0]).0;
            let left = part.iter().map(|&cell| unpack(cell).1).min().unwrap_or(0);
            for cell in part.iter_mut() {
                let (row, column) = unpack(*cell);
                *cell = pack(row.wrapping_sub(top), column.wrapping_sub(left));
            }
            start = end;
        }
        self
    }
}

fn root(parent: &mut [u32], mut at: u32) -> u32 {
    while parent[at as usize] != at {
        let up = parent[parent[at as usize] as usize];
        parent[at as usize] = up;
        at = up;
    }
    at
}

/// The 8-connected parts of at least `least` cells of the cells `cells`, which are sorted and distinct. Each part is sorted.
pub(crate) fn parts(cells: &[u64], least: usize) -> Parts {
    let n = cells.len();
    if n < least.max(1) {
        return Parts::default();
    }
    let mut parent: Vec<u32> = (0..n as u32).collect();
    for k in 0..n {
        let (row, column) = unpack(cells[k]);
        // The neighbors after the cell in the sorted order; the others find the cell as their neighbor.
        for (down, right) in [(0i32, 1i32), (1, -1), (1, 0), (1, 1)] {
            let key = pack(row.wrapping_add(down), column.wrapping_add(right));
            if key > cells[k] {
                if let Ok(found) = cells[k + 1..].binary_search(&key) {
                    let (a, b) = (root(&mut parent, k as u32), root(&mut parent, (k + 1 + found) as u32));
                    if a != b {
                        parent[a.max(b) as usize] = a.min(b);
                    }
                }
            }
        }
    }
    let mut size = vec![0u32; n];
    let mut top = vec![0u32; n];
    for k in 0..n {
        let at = root(&mut parent, k as u32);
        top[k] = at;
        size[at as usize] += 1;
    }
    let mut start = vec![u32::MAX; n];
    let mut ends = Vec::new();
    let mut total = 0u32;
    for k in 0..n {
        let at = top[k] as usize;
        if size[at] as usize >= least && start[at] == u32::MAX {
            start[at] = total;
            total += size[at];
            ends.push(total as usize);
        }
    }
    let mut out = vec![0u64; total as usize];
    for k in 0..n {
        let at = top[k] as usize;
        if start[at] != u32::MAX {
            out[start[at] as usize] = cells[k];
            start[at] += 1;
        }
    }
    Parts { cells: out, ends }
}

/// A set of shapes, each a sorted list of packed cells.
#[derive(Debug, Default)]
pub(crate) struct ShapeSet(Vec<Vec<u64>>);

impl ShapeSet {
    pub fn new(mut shapes: Vec<Vec<u64>>) -> ShapeSet {
        shapes.sort_unstable();
        shapes.dedup();
        ShapeSet(shapes)
    }

    pub fn contains(&self, shape: &[u64]) -> bool {
        self.0.binary_search_by(|held| held.as_slice().cmp(shape)).is_ok()
    }

    pub fn is_empty(&self) -> bool {
        self.0.is_empty()
    }
}

/// The cells of a 32 by 32 corner of a grid: the bit `j` of the entry `i` is the cell (i, j).
pub type Frame = [u32; 32];

/// Whether (row, column) is in a `Frame`, and if so, the bit of that cell in the frame as the index `32 * row + column`.
pub fn frame_index(row: i32, column: i32) -> Option<usize> {
    if (row as u32) < 32 && (column as u32) < 32 { Some((row as usize) << 5 | column as usize) } else { None }
}

/// The count of cells in both frames.
pub(crate) fn both(a: &Frame, b: &Frame) -> usize {
    a.iter().zip(b).map(|(x, y)| (x & y).count_ones() as usize).sum()
}

/// Calls `visit(row, column)` for each cell of the frame, in order.
pub(crate) fn each_cell(frame: &Frame, mut visit: impl FnMut(i32, i32)) {
    for (row, &bits) in frame.iter().enumerate() {
        let mut bits = bits;
        while bits != 0 {
            visit(row as i32, bits.trailing_zeros() as i32);
            bits &= bits - 1;
        }
    }
}

/// The 8-connected parts of at least `least` cells of the cells of a frame, each sorted.
pub(crate) fn parts_in_frame(frame: &Frame, least: usize) -> Parts {
    // The runs of neighboring cells in a row of the frame: row, first column, end column.
    let mut runs: Vec<(u8, u8, u8)> = Vec::new();
    // The runs of each row are runs[row_start[row]..row_start[row + 1]].
    let mut row_start = [0u16; 33];
    for (row, &bits) in frame.iter().enumerate() {
        row_start[row] = runs.len() as u16;
        let mut left = bits;
        while left != 0 {
            let start = left.trailing_zeros();
            let end = start + (left >> start).trailing_ones();
            runs.push((row as u8, start as u8, end as u8));
            left &= !(((1u64 << end) - 1) as u32 & !((1u32 << start) - 1));
        }
    }
    row_start[32] = runs.len() as u16;
    let mask_of = |run: (u8, u8, u8)| (((1u64 << run.2) - 1) as u32) & !((1u32 << run.1) - 1);
    let mut parent: Vec<u32> = (0..runs.len() as u32).collect();
    for row in 1..32 {
        let (above, here) = (row_start[row - 1] as usize..row_start[row] as usize, row_start[row] as usize..row_start[row + 1] as usize);
        for at in here {
            let grown = mask_of(runs[at]);
            let grown = grown | grown << 1 | grown >> 1;
            for up in above.clone() {
                if grown & mask_of(runs[up]) != 0 {
                    let (a, b) = (root(&mut parent, at as u32), root(&mut parent, up as u32));
                    if a != b {
                        parent[a.max(b) as usize] = a.min(b);
                    }
                }
            }
        }
    }
    let mut size = vec![0u32; runs.len()];
    let mut top = vec![0u32; runs.len()];
    for (at, run) in runs.iter().enumerate() {
        let id = root(&mut parent, at as u32);
        top[at] = id;
        size[id as usize] += u32::from(run.2 - run.1);
    }
    let mut start = vec![u32::MAX; runs.len()];
    let mut ends = Vec::new();
    let mut total = 0u32;
    for at in 0..runs.len() {
        let id = top[at] as usize;
        if size[id] as usize >= least && start[id] == u32::MAX {
            start[id] = total;
            total += size[id];
            ends.push(total as usize);
        }
    }
    let mut cells = vec![0u64; total as usize];
    for (at, run) in runs.iter().enumerate() {
        let id = top[at] as usize;
        if start[id] != u32::MAX {
            for column in run.1..run.2 {
                cells[start[id] as usize] = pack(i32::from(run.0), i32::from(column));
                start[id] += 1;
            }
        }
    }
    Parts { cells, ends }
}
