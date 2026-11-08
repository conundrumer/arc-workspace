//! What the catalog's shapes read of a train pair's grids, computed once per pair.
//! Plain data with no engine dependency: a table's pass reads these arrays.

pub use crate::cell_sets::{canon, normalized, symmetry_count};
use crate::cell_sets::{grid_neighbor, grid_pieces, relation, Walk, STEPS};

/// A set of cells of one grid, by `row * width + column`. Grids hold at most 900 cells.
#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub struct Bits(pub [u64; 15]);

impl Bits {
    pub const EMPTY: Bits = Bits([0; 15]);

    #[inline]
    pub fn set(&mut self, at: usize) {
        self.0[at >> 6] |= 1 << (at & 63);
    }

    #[inline]
    pub fn get(&self, at: usize) -> bool {
        self.0[at >> 6] >> (at & 63) & 1 == 1
    }

    #[inline]
    pub fn count(&self) -> u32 {
        self.0.iter().map(|word| word.count_ones()).sum()
    }

    #[inline]
    pub fn is_empty(&self) -> bool {
        self.0.iter().all(|word| *word == 0)
    }

    #[inline]
    pub fn and(&self, other: &Bits) -> Bits {
        let mut out = *self;
        for (word, with) in out.0.iter_mut().zip(&other.0) {
            *word &= with;
        }
        out
    }

    #[inline]
    pub fn or(&self, other: &Bits) -> Bits {
        let mut out = *self;
        for (word, with) in out.0.iter_mut().zip(&other.0) {
            *word |= with;
        }
        out
    }

    #[inline]
    pub fn minus(&self, other: &Bits) -> Bits {
        let mut out = *self;
        for (word, with) in out.0.iter_mut().zip(&other.0) {
            *word &= !with;
        }
        out
    }

    #[inline]
    pub fn intersects(&self, other: &Bits) -> bool {
        self.0.iter().zip(&other.0).any(|(a, b)| a & b != 0)
    }

    #[inline]
    pub fn within(&self, other: &Bits) -> bool {
        self.0.iter().zip(&other.0).all(|(a, b)| a & !b == 0)
    }

    pub fn each(&self, mut visit: impl FnMut(usize)) {
        for (index, word) in self.0.iter().enumerate() {
            let mut word = *word;
            while word != 0 {
                visit(index * 64 + word.trailing_zeros() as usize);
                word &= word - 1;
            }
        }
    }
}

/// One color's 8-connected piece of a grid.
#[derive(Clone, Debug)]
pub struct Piece {
    pub color: u8,
    pub cells: Bits,
    pub size: u32,
    /// First row, last row, first column, last column.
    pub span: [u8; 4],
}

/// How two sets stand to each other.
pub fn set_relation(left: bool, right: bool, both: bool) -> &'static str {
    relation(left, right, both, false).word()
}

/// How two sets stand to each other, in a universe.
pub fn set_relation_in(left: bool, right: bool, both: bool, neither: bool) -> &'static str {
    relation(left, right, both, !neither).word()
}

pub const CELL_ROLES: usize = 13;
pub const ROLE_BOUNDARY: usize = 0;
pub const ROLE_CORNER: usize = 1;
pub const ROLE_CENTER: usize = 2;
pub const ROLE_TIP: usize = 3;
pub const ROLE_SINGLE: usize = 4;
pub const ROLE_FULL_LINE: usize = 5;
pub const ROLE_EDGE: usize = 6;
pub const ROLE_GRID_CORNER: usize = 7;
pub const ROLE_NEXT: usize = 8;
pub const ROLE_ENCLOSED: usize = 9;
pub const ROLE_CROSSING: usize = 10;
pub const ROLE_BETWEEN: usize = 11;
pub const ROLE_BREAKS: usize = 12;

pub const COLOR_ROLES: usize = 11;
pub const COLOR_WHOLE_LINES: usize = 0;
pub const COLOR_SINGLES: usize = 1;
pub const COLOR_ONE_PIECE: usize = 2;
pub const COLOR_EVERY_EDGE: usize = 3;
pub const COLOR_NO_EDGE: usize = 4;
pub const COLOR_ENCLOSES: usize = 5;
pub const COLOR_ENCLOSED: usize = 6;
pub const COLOR_FILLS_BOXES: usize = 7;
pub const COLOR_LARGEST: usize = 8;
pub const COLOR_MOST_PIECES: usize = 9;
pub const COLOR_SYMMETRIC: usize = 10;

/// A grid and what the shapes read of it.
#[derive(Clone, Debug)]
pub struct GridFacts {
    pub h: usize,
    pub w: usize,
    pub color: Vec<u8>,
    pub by_color: [Bits; 10],
    pub counts: [u32; 10],
    pub colors: u16,
    pub all: Bits,
    pub background: Option<u8>,
    /// The cells off the one most frequent color, where one color is the most frequent.
    pub foreground: Option<Bits>,
    pub pieces: Vec<Piece>,
    pub piece_of: Vec<u16>,
    pub foreground_parts: Vec<Bits>,
    pub roles: [Bits; CELL_ROLES],
    pub color_roles: [u16; COLOR_ROLES],
    pub line_colors: [Vec<u16>; 4],
    pub moore: Vec<u32>,
    pub neighbor_colors: Vec<u32>,
    pub same_neighbors: Vec<u8>,
    /// Cell counts per color over the rectangles from the top left: `(h + 1) * (w + 1)` per color.
    pub prefix: Vec<u16>,
    pub periods: u32,
    pub rows_one_color: bool,
    pub columns_one_color: bool,
}

impl crate::occurrence::Canvas for GridFacts {
    fn height(&self) -> i32 {
        self.h as i32
    }

    fn width(&self) -> i32 {
        self.w as i32
    }

    fn color_at(&self, row: i32, column: i32) -> u32 {
        u32::from(self.color[row as usize * self.w + column as usize])
    }

    fn count(&self, color: u32) -> usize {
        self.counts.get(color as usize).map_or(0, |count| *count as usize)
    }

    fn each_place(&self, color: u32, mut each: impl FnMut(i32, i32)) {
        if let Some(cells) = self.by_color.get(color as usize) {
            cells.each(|at| each((at / self.w) as i32, (at % self.w) as i32));
        }
    }
}

/// The 8-connected pieces of a cell set, as cell sets.
pub fn parts(cells: &Bits, h: usize, w: usize) -> Vec<Bits> {
    let mut out = Vec::new();
    grid_pieces(h, w, &STEPS, |at| cells.get(at), |piece| {
        let mut part = Bits::EMPTY;
        for at in piece {
            part.set(*at);
        }
        out.push(part);
    });
    out
}

/// The count of 8-connected pieces of a cell set.
pub fn part_count(cells: &Bits, h: usize, w: usize) -> u32 {
    let mut count = 0;
    grid_pieces(h, w, &STEPS, |at| cells.get(at), |_| count += 1);
    count
}

/// The cells of `free` that no walk of four steps through `free` reaches from the grid's edge.
pub fn walk_in(free: &Bits, h: usize, w: usize) -> Bits {
    let mut edge: Vec<usize> = Vec::new();
    free.each(|at| {
        let (r, c) = (at / w, at % w);
        if r == 0 || c == 0 || r == h - 1 || c == w - 1 {
            edge.push(at);
        }
    });
    let mut walk = Walk::default();
    let seen = walk.reach(h * w, &STEPS[..4], &edge, |at, dr, dc| grid_neighbor(h, w, at, dr, dc).filter(|next| free.get(*next)));
    let mut out = Bits::EMPTY;
    free.each(|at| {
        if !seen[at] {
            out.set(at);
        }
    });
    out
}

/// The dense id of each value, in the order of the values.
fn dense<T: Ord>(values: Vec<T>) -> Vec<u32> {
    let mut distinct: Vec<&T> = values.iter().collect();
    distinct.sort_unstable();
    distinct.dedup();
    values.iter().map(|value| distinct.binary_search(&value).map_or(0, |at| at as u32)).collect()
}

impl GridFacts {
    pub fn new(h: usize, w: usize, color: Vec<u8>) -> GridFacts {
        let n = h * w;
        let mut by_color = [Bits::EMPTY; 10];
        let mut counts = [0u32; 10];
        let mut all = Bits::EMPTY;
        for (at, col) in color.iter().enumerate() {
            by_color[*col as usize].set(at);
            counts[*col as usize] += 1;
            all.set(at);
        }
        let colors = (0..10).filter(|col| counts[*col] > 0).fold(0u16, |mask, col| mask | 1 << col);
        let most = counts.iter().copied().max().unwrap_or(0);
        let tops: Vec<usize> = (0..10).filter(|col| counts[*col] == most && most > 0).collect();
        let background = (tops.len() == 1).then(|| tops[0] as u8);
        let foreground = background.map(|col| all.minus(&by_color[col as usize]));
        // Pieces of one color, and each cell's piece.
        let mut pieces = Vec::new();
        let mut piece_of = vec![0u16; n];
        for col in 0..10 {
            for part in parts(&by_color[col], h, w) {
                let mut span = [255u8, 0, 255, 0];
                let mut size = 0;
                part.each(|at| {
                    let (r, c) = ((at / w) as u8, (at % w) as u8);
                    span = [span[0].min(r), span[1].max(r), span[2].min(c), span[3].max(c)];
                    piece_of[at] = pieces.len() as u16;
                    size += 1;
                });
                pieces.push(Piece { color: col as u8, cells: part, size, span });
            }
        }
        let foreground_parts = foreground.as_ref().map_or_else(Vec::new, |cells| parts(cells, h, w));
        // The colors on each row, column and diagonal.
        let mut line_colors = [vec![0u16; h], vec![0u16; w], vec![0u16; h + w], vec![0u16; h + w]];
        for r in 0..h {
            for c in 0..w {
                let bit = 1u16 << color[r * w + c];
                line_colors[0][r] |= bit;
                line_colors[1][c] |= bit;
                line_colors[2][r + w - 1 - c] |= bit;
                line_colors[3][r + c] |= bit;
            }
        }
        let mut facts = GridFacts {
            h,
            w,
            color,
            by_color,
            counts,
            colors,
            all,
            background,
            foreground,
            pieces,
            piece_of,
            foreground_parts,
            roles: [Bits::EMPTY; CELL_ROLES],
            color_roles: [0; COLOR_ROLES],
            line_colors,
            moore: Vec::new(),
            neighbor_colors: Vec::new(),
            same_neighbors: Vec::new(),
            prefix: Vec::new(),
            periods: 0,
            rows_one_color: false,
            columns_one_color: false,
        };
        facts.rows_one_color = facts.line_colors[0].iter().all(|mask| mask.count_ones() == 1);
        facts.columns_one_color = facts.line_colors[1].iter().all(|mask| mask.count_ones() == 1);
        facts.neighbors();
        facts.cell_roles();
        facts.color_roles();
        facts.prefix_counts();
        facts.periods();
        facts
    }

    #[inline]
    pub fn at(&self, r: usize, c: usize) -> u8 {
        self.color[r * self.w + c]
    }

    /// Per cell, a dense id of its Moore neighborhood, of the multiset of its neighbors'
    /// colors, and its count of neighbors of its own color.
    fn neighbors(&mut self) {
        let (h, w) = (self.h, self.w);
        let mut around = Vec::with_capacity(h * w);
        let mut multiset = Vec::with_capacity(h * w);
        let mut same = Vec::with_capacity(h * w);
        for r in 0..h as i32 {
            for c in 0..w as i32 {
                let mut word = [255u8; 9];
                let mut per = [0u8; 11];
                let mut own = 0u8;
                let mine = self.color[r as usize * w + c as usize];
                let mut slot = 0;
                for a in -1..=1 {
                    for b in -1..=1 {
                        let (nr, nc) = (r + a, c + b);
                        let col = if nr >= 0 && nc >= 0 && (nr as usize) < h && (nc as usize) < w { self.color[nr as usize * w + nc as usize] } else { 10 };
                        word[slot] = col;
                        slot += 1;
                        if a != 0 || b != 0 {
                            per[col as usize] += 1;
                            own += u8::from(col == mine);
                        }
                    }
                }
                around.push(word);
                multiset.push(per);
                same.push(own);
            }
        }
        self.moore = dense(around);
        self.neighbor_colors = dense(multiset);
        self.same_neighbors = same;
    }

    fn cell_roles(&mut self) {
        let (h, w) = (self.h, self.w);
        let mut roles = [Bits::EMPTY; CELL_ROLES];
        // Under a tie, every most common color is background.
        let most = self.counts.iter().copied().max().unwrap_or(0);
        let mut foreground = Bits::EMPTY;
        for at in 0..h * w {
            if self.counts[self.color[at] as usize] != most {
                foreground.set(at);
            }
        }
        let full_rows: Vec<bool> = self.line_colors[0].iter().map(|mask| mask.count_ones() == 1).collect();
        let full_cols: Vec<bool> = self.line_colors[1].iter().map(|mask| mask.count_ones() == 1).collect();
        for r in 0..h {
            for c in 0..w {
                let at = r * w + c;
                let piece = &self.pieces[self.piece_of[at] as usize];
                let (top, bottom, left, right) = (piece.span[0] as usize, piece.span[1] as usize, piece.span[2] as usize, piece.span[3] as usize);
                let inside = |nr: i32, nc: i32| nr >= 0 && nc >= 0 && (nr as usize) < h && (nc as usize) < w && piece.cells.get(nr as usize * w + nc as usize);
                let (ri, ci) = (r as i32, c as i32);
                if !inside(ri + 1, ci) || !inside(ri - 1, ci) || !inside(ri, ci + 1) || !inside(ri, ci - 1) {
                    roles[ROLE_BOUNDARY].set(at);
                }
                if (r == top || r == bottom) && (c == left || c == right) {
                    roles[ROLE_CORNER].set(at);
                }
                if 2 * r == top + bottom && 2 * c == left + right {
                    roles[ROLE_CENTER].set(at);
                }
                if self.same_neighbors[at] == 1 && piece.size > 1 {
                    roles[ROLE_TIP].set(at);
                }
                if piece.size == 1 {
                    roles[ROLE_SINGLE].set(at);
                }
                if full_rows[r] || full_cols[c] {
                    roles[ROLE_FULL_LINE].set(at);
                }
                if r == 0 || r == h - 1 || c == 0 || c == w - 1 {
                    roles[ROLE_EDGE].set(at);
                }
                if (r == 0 || r == h - 1) && (c == 0 || c == w - 1) {
                    roles[ROLE_GRID_CORNER].set(at);
                }
                if !foreground.get(at) {
                    let near = (r.saturating_sub(1)..(r + 2).min(h)).any(|nr| (c.saturating_sub(1)..(c + 2).min(w)).any(|nc| foreground.get(nr * w + nc)));
                    if near {
                        roles[ROLE_NEXT].set(at);
                    }
                }
            }
        }
        {
            let cells = foreground;
            roles[ROLE_ENCLOSED] = walk_in(&self.all.minus(&cells), h, w);
            let rows: Vec<usize> = (0..h).filter(|r| (0..w).all(|c| cells.get(r * w + c))).collect();
            let cols: Vec<usize> = (0..w).filter(|c| (0..h).all(|r| cells.get(r * w + c))).collect();
            for r in &rows {
                for c in &cols {
                    roles[ROLE_CROSSING].set(r * w + c);
                }
            }
            for r in 0..h {
                let held: Vec<usize> = (0..w).filter(|c| cells.get(r * w + c)).collect();
                if let (Some(first), Some(last)) = (held.first(), held.last()) {
                    for c in first + 1..*last {
                        if !cells.get(r * w + c) {
                            roles[ROLE_BETWEEN].set(r * w + c);
                        }
                    }
                }
            }
            for c in 0..w {
                let held: Vec<usize> = (0..h).filter(|r| cells.get(r * w + c)).collect();
                if let (Some(first), Some(last)) = (held.first(), held.last()) {
                    for r in first + 1..*last {
                        if !cells.get(r * w + c) {
                            roles[ROLE_BETWEEN].set(r * w + c);
                        }
                    }
                }
            }
        }
        roles[ROLE_BREAKS] = self.breaks();
        self.roles = roles;
    }

    /// The least approximate period along the rows, or along the columns: the line pairs the move
    /// breaks do not outnumber those it keeps, as `Periods` gives. 0 where the extent has none.
    fn least_move(&self, along_rows: bool) -> usize {
        let (n, m) = if along_rows { (self.h, self.w) } else { (self.w, self.h) };
        let cell = |line: usize, place: usize| if along_rows { self.color[line * self.w + place] } else { self.color[place * self.w + line] };
        for p in 1..n {
            let lines = n - p;
            let broken = (0..lines).filter(|a| (0..m).any(|place| cell(*a, place) != cell(*a + p, place))).count();
            if broken <= lines - broken {
                return p;
            }
        }
        0
    }

    /// The cells off the most frequent color of their class, where a class is the cells that the
    /// grid's least move along each axis takes onto each other.
    fn breaks(&self) -> Bits {
        let (h, w) = (self.h, self.w);
        let (pr, pk) = (self.least_move(true), self.least_move(false));
        let class = |r: usize, c: usize| (if pr > 0 { r % pr } else { r }) * w + if pk > 0 { c % pk } else { c };
        let mut counts = vec![[0u16; 10]; h * w];
        for r in 0..h {
            for c in 0..w {
                counts[class(r, c)][self.color[r * w + c] as usize] += 1;
            }
        }
        let mut out = Bits::EMPTY;
        for r in 0..h {
            for c in 0..w {
                let held = &counts[class(r, c)];
                if held[self.color[r * w + c] as usize] < held.iter().copied().max().unwrap_or(0) {
                    out.set(r * w + c);
                }
            }
        }
        out
    }

    fn color_roles(&mut self) {
        let (h, w) = (self.h, self.w);
        let mut out = [0u16; COLOR_ROLES];
        let per_pieces: Vec<u32> = (0..10).map(|col| self.pieces.iter().filter(|piece| piece.color == col as u8).count() as u32).collect();
        let most_pieces = per_pieces.iter().copied().max().unwrap_or(0);
        // Under a tie, every most common color is background.
        let most_cells = self.counts.iter().copied().max().unwrap_or(0);
        let foreground_largest = self.pieces.iter().filter(|piece| self.counts[piece.color as usize] != most_cells).map(|piece| piece.size).max();
        let full_rows: Vec<bool> = self.line_colors[0].iter().map(|mask| mask.count_ones() == 1).collect();
        let full_cols: Vec<bool> = self.line_colors[1].iter().map(|mask| mask.count_ones() == 1).collect();
        let inside: Vec<Option<Bits>> = (0..10).map(|col| (self.counts[col] > 0).then(|| walk_in(&self.all.minus(&self.by_color[col]), h, w))).collect();
        for col in 0..10usize {
            if self.counts[col] == 0 {
                continue;
            }
            let bit = 1u16 << col;
            let cells = self.by_color[col];
            let mut list = Vec::with_capacity(self.counts[col] as usize);
            cells.each(|at| list.push(((at / w) as u8, (at % w) as u8)));
            let (rmin, rmax) = (list.iter().map(|cell| cell.0).min().unwrap_or(0) as usize, list.iter().map(|cell| cell.0).max().unwrap_or(0) as usize);
            let (cmin, cmax) = (list.iter().map(|cell| cell.1).min().unwrap_or(0) as usize, list.iter().map(|cell| cell.1).max().unwrap_or(0) as usize);
            if list.iter().all(|(r, c)| full_rows[*r as usize] || full_cols[*c as usize]) {
                out[COLOR_WHOLE_LINES] |= bit;
            }
            let own: Vec<&Piece> = self.pieces.iter().filter(|piece| piece.color == col as u8).collect();
            if own.iter().all(|piece| piece.size == 1) {
                out[COLOR_SINGLES] |= bit;
            }
            if own.len() == 1 {
                out[COLOR_ONE_PIECE] |= bit;
            }
            if rmin == 0 && rmax == h - 1 && cmin == 0 && cmax == w - 1 {
                out[COLOR_EVERY_EDGE] |= bit;
            }
            if rmin > 0 && rmax < h - 1 && cmin > 0 && cmax < w - 1 {
                out[COLOR_NO_EDGE] |= bit;
            }
            if inside[col].as_ref().is_some_and(|held| !held.is_empty()) {
                out[COLOR_ENCLOSES] |= bit;
            }
            if (0..10).any(|other| other != col && inside[other].as_ref().is_some_and(|held| cells.within(held))) {
                out[COLOR_ENCLOSED] |= bit;
            }
            if own.iter().all(|piece| piece.size as usize == (piece.span[1] - piece.span[0] + 1) as usize * (piece.span[3] - piece.span[2] + 1) as usize) {
                out[COLOR_FILLS_BOXES] |= bit;
            }
            if self.counts[col] != most_cells && foreground_largest.is_some_and(|size| own.iter().any(|piece| piece.size == size)) {
                out[COLOR_LARGEST] |= bit;
            }
            if per_pieces[col] == most_pieces {
                out[COLOR_MOST_PIECES] |= bit;
            }
            if symmetry_count(&list) > 1 {
                out[COLOR_SYMMETRIC] |= bit;
            }
        }
        self.color_roles = out;
    }

    fn prefix_counts(&mut self) {
        let (h, w) = (self.h, self.w);
        let stride = (h + 1) * (w + 1);
        let mut prefix = vec![0u16; 10 * stride];
        for col in 0..10 {
            if self.counts[col] == 0 {
                continue;
            }
            let table = &mut prefix[col * stride..(col + 1) * stride];
            for r in 0..h {
                for c in 0..w {
                    let here = u16::from(self.color[r * w + c] == col as u8);
                    table[(r + 1) * (w + 1) + c + 1] = here + table[r * (w + 1) + c + 1] + table[(r + 1) * (w + 1) + c] - table[r * (w + 1) + c];
                }
            }
        }
        self.prefix = prefix;
    }

    /// The colors in a rectangle of first row, last row, first column and last column.
    pub fn colors_in(&self, top: usize, bottom: usize, left: usize, right: usize) -> u16 {
        let stride = (self.h + 1) * (self.w + 1);
        let mut mask = 0u16;
        let columns = self.w + 1;
        for col in 0..10 {
            if self.counts[col] == 0 {
                continue;
            }
            let table = &self.prefix[col * stride..(col + 1) * stride];
            let held = table[(bottom + 1) * columns + right + 1] + table[top * columns + left] - table[top * columns + right + 1] - table[(bottom + 1) * columns + left];
            if held > 0 {
                mask |= 1 << col;
            }
        }
        mask
    }

    fn periods(&mut self) {
        let (h, w) = (self.h, self.w);
        let mut out = 0u32;
        for k in 1..w {
            if (0..h).all(|r| (0..w - k).all(|c| self.color[r * w + c] == self.color[r * w + c + k])) {
                out |= 1 << k;
            }
        }
        for k in 1..h {
            if (0..h - k).all(|r| (0..w).all(|c| self.color[r * w + c] == self.color[(r + k) * w + c])) {
                out |= 1 << k;
            }
        }
        self.periods = out;
    }
}

/// A train pair's grids, and what the shapes read of the two together.
#[derive(Clone, Debug)]
pub struct PairFacts {
    pub input: GridFacts,
    pub output: GridFacts,
    pub same: bool,
    pub changed: Bits,
    pub changed_to: u16,
    pub changed_from: u16,
    pub changed_span: Option<[u8; 4]>,
    pub changed_parts: u32,
    /// The output's area, longer side, shorter side, color count, foreground count, foreground
    /// part count, changed cell count and changed part count, where the pair has them.
    pub measures: [Option<i64>; 8],
    /// Per element of D4, in the order ID, LR, TB, HT, CW, CC, DG, AD: whether its image of the
    /// output is the output, and whether its image of the input is the output.
    pub keeps: [bool; 8],
    pub maps: [bool; 8],
}

/// Whether the image of a grid under an element of D4 is another grid.
pub fn image_is(from: &GridFacts, to: &GridFacts, which: usize) -> bool {
    let (h, w) = (from.h, from.w);
    let swaps = which >= 4;
    if (if swaps { (w, h) } else { (h, w) }) != (to.h, to.w) {
        return false;
    }
    (0..h).all(|r| (0..w).all(|c| {
        let (y, z) = match which {
            0 => (r, c),
            1 => (r, w - 1 - c),
            2 => (h - 1 - r, c),
            3 => (h - 1 - r, w - 1 - c),
            4 => (c, h - 1 - r),
            5 => (w - 1 - c, r),
            6 => (c, r),
            _ => (w - 1 - c, h - 1 - r),
        };
        from.color[r * w + c] == to.color[y * to.w + z]
    }))
}

/// The cells of a grid that hold the color of the same cell of its image under an element of D4; none where the image has another shape.
pub fn image_agreement(from: &GridFacts, which: usize) -> u32 {
    let (h, w) = (from.h, from.w);
    if which >= 4 && h != w {
        return 0;
    }
    let mut kept = 0;
    for r in 0..h {
        for c in 0..w {
            let (y, z) = match which {
                0 => (r, c),
                1 => (r, w - 1 - c),
                2 => (h - 1 - r, c),
                3 => (h - 1 - r, w - 1 - c),
                4 => (c, h - 1 - r),
                5 => (w - 1 - c, r),
                6 => (c, r),
                _ => (w - 1 - c, h - 1 - r),
            };
            kept += u32::from(from.color[r * w + c] == from.color[y * w + z]);
        }
    }
    kept
}

pub fn span_of(cells: &Bits, w: usize) -> Option<[u8; 4]> {
    if cells.is_empty() {
        return None;
    }
    let mut span = [255u8, 0, 255, 0];
    cells.each(|at| {
        let (r, c) = ((at / w) as u8, (at % w) as u8);
        span = [span[0].min(r), span[1].max(r), span[2].min(c), span[3].max(c)];
    });
    Some(span)
}

impl PairFacts {
    pub fn new(input: GridFacts, output: GridFacts) -> PairFacts {
        let same = input.h == output.h && input.w == output.w;
        let (mut changed, mut changed_to, mut changed_from) = (Bits::EMPTY, 0u16, 0u16);
        if same {
            for at in 0..output.h * output.w {
                if input.color[at] != output.color[at] {
                    changed.set(at);
                    changed_to |= 1 << output.color[at];
                    changed_from |= 1 << input.color[at];
                }
            }
        }
        let changed_span = span_of(&changed, output.w);
        let changed_parts = part_count(&changed, output.h, output.w);
        let (h, w) = (output.h as i64, output.w as i64);
        let measures = [
            Some(h * w),
            Some(h.max(w)),
            Some(h.min(w)),
            Some(i64::from(output.colors.count_ones())),
            output.foreground.as_ref().map(|cells| i64::from(cells.count())),
            output.foreground.as_ref().map(|_| output.foreground_parts.len() as i64),
            (!changed.is_empty()).then(|| i64::from(changed.count())),
            (!changed.is_empty()).then_some(i64::from(changed_parts)),
        ];
        let keeps = std::array::from_fn(|which| image_is(&output, &output, which));
        let maps = std::array::from_fn(|which| image_is(&input, &output, which));
        PairFacts { input, output, same, changed, changed_to, changed_from, changed_span, changed_parts, measures, keeps, maps }
    }
}
