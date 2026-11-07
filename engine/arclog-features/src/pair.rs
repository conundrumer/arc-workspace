//! The train pairs of a task, and what the features read of them. Each fact of
//! a pair is made on the first read and kept.

use std::sync::OnceLock;

use crate::cells::{pack, parts, Frame, Parts, ShapeSet};
use crate::summary::{SuitKind, SuitSummary};

/// A grid: `height` rows of `width` colors, row by row, each color its digit.
#[derive(Clone, Debug)]
pub struct Grid {
    pub height: usize,
    pub width: usize,
    pub cells: Vec<u8>,
}

/// A train pair of the task, with what the features read of it, each made on its first read.
#[derive(Debug)]
pub struct Pair {
    pub input: Grid,
    pub output: Grid,
    facts: OnceLock<PairFacts>,
    heavy: OnceLock<Heavy>,
    masks: OnceLock<Masks>,
    fill: OnceLock<Option<FillFrames>>,
}

/// The most common color of `cells`; the first met, on a tie.
fn background(cells: &[u8]) -> u8 {
    let mut counts = [0usize; 10];
    let mut order: Vec<u8> = Vec::new();
    for &color in cells {
        let color = color.min(9);
        if counts[color as usize] == 0 {
            order.push(color);
        }
        counts[color as usize] += 1;
    }
    order.iter().copied().fold(None, |best: Option<u8>, color| match best {
        Some(held) if counts[held as usize] >= counts[color as usize] => Some(held),
        _ => Some(color),
    }).unwrap_or(0)
}

/// What a train pair gives to the features that compare rows with it.
#[derive(Debug)]
pub(crate) struct PairFacts {
    pub area: usize,
    /// Whether the input and the output have one size.
    pub same: bool,
    /// The count of cells where the input and the output differ; 0 where the sizes differ.
    pub changed: usize,
    /// The output's most common color (the first met, on a tie), and the count of output cells off it.
    pub obg: u8,
    pub ofg: usize,
    /// The input's most common color.
    pub bg: u8,
    /// The colors of the output, as a bit set.
    pub ocolors: u16,
    /// The colors of the output that the input lacks, as a bit set.
    pub newcolors: u16,
}

impl PairFacts {
    fn of(pair: &Pair) -> PairFacts {
        let (input, output) = (&pair.input, &pair.output);
        let same = input.height == output.height && input.width == output.width;
        let changed = if same { input.cells.iter().zip(&output.cells).filter(|(a, b)| a != b).count() } else { 0 };
        let obg = background(&output.cells);
        let bg = background(&input.cells);
        let ofg = output.cells.iter().filter(|&&color| color.min(9) != obg).count();
        let bits = |cells: &[u8]| cells.iter().fold(0u16, |bits, &color| bits | 1 << color.min(9));
        let (ocolors, icolors) = (bits(&output.cells), bits(&input.cells));
        PairFacts { area: input.height * input.width, same, changed, obg, ofg, bg, ocolors, newcolors: ocolors & !icolors }
    }

    /// The error before any paint: the cells that differ where the sizes are one, else the output's cells off its background.
    pub fn base_err(&self) -> usize {
        if self.same { self.changed } else { self.ofg }
    }
}

/// A cell of the input that is not of the input's most common color.
pub(crate) const FG: u8 = 1;
/// A cell of the input that the output does not have in place.
pub(crate) const CHANGED: u8 = 2;
/// A cell of the output that is not of the output's most common color.
pub(crate) const OFG: u8 = 1;

/// The cell sets of a pair that the Position features compare with, as flags of the cells of the grids.
#[derive(Debug)]
pub(crate) struct Heavy {
    /// The flags `FG` and `CHANGED` of each cell of the input.
    pub in_flags: Vec<u8>,
    /// The color of each cell of the input, at most 9.
    pub in_color: Vec<u8>,
    /// The count of cells of each color of the input.
    pub color_count: [usize; 10],
    /// The count of cells of the input with the flag `CHANGED`.
    pub changed_len: usize,
    /// The flag `OFG` of each cell of the output.
    pub out_flags: Vec<u8>,
    /// The count of cells of the output with the flag `OFG`.
    pub ofg_len: usize,
    /// The cells of the 32 by 32 corner with the flags `FG`, `CHANGED` of the input and `OFG` of the output, and the cells of each
    /// color of the input.
    pub fg_frame: Frame,
    pub changed_frame: Frame,
    pub ofg_frame: Frame,
    pub color_frames: [Frame; 10],
    /// The shapes of the input's parts, of the output's parts, and of the output's parts that the input does not have in place.
    pub nin: ShapeSet,
    pub nout: ShapeSet,
    pub live: ShapeSet,
}

/// The parts of at least 3 cells of each color's cells, as lists of packed cells.
fn objects(by_color: &[Vec<u64>]) -> Vec<Vec<u64>> {
    by_color.iter().flat_map(|cells| parts(cells, 3).iter().map(<[u64]>::to_vec).collect::<Vec<_>>()).collect()
}

fn shapes_of(objects: &[Vec<u64>]) -> Vec<Vec<u64>> {
    let flat = Parts::from_lists(objects).moved_to_corner();
    flat.iter().map(<[u64]>::to_vec).collect()
}

impl Pair {
    pub fn new(input: Grid, output: Grid) -> Pair {
        Pair { input, output, facts: OnceLock::new(), heavy: OnceLock::new(), masks: OnceLock::new(), fill: OnceLock::new() }
    }

    pub(crate) fn facts(&self) -> &PairFacts {
        self.facts.get_or_init(|| PairFacts::of(self))
    }

    /// The cells of the output by color, for a pair that has an output of at most 32 by 32 with colors of at most 9.
    pub(crate) fn fill_frames(&self) -> Option<&FillFrames> {
        self.fill.get_or_init(|| FillFrames::of(self)).as_ref()
    }

    pub(crate) fn masks(&self) -> &Masks {
        self.masks.get_or_init(|| Masks::of(self))
    }

    pub(crate) fn heavy(&self) -> &Heavy {
        self.heavy.get_or_init(|| {
            let facts = self.facts();
            let (input, output) = (&self.input, &self.output);
            let mut in_flags = vec![0u8; input.height * input.width];
            let mut in_color = vec![0u8; input.height * input.width];
            let mut color_count = [0usize; 10];
            let mut changed_len = 0;
            let mut fg_by: Vec<Vec<u64>> = vec![Vec::new(); 10];
            let mut ofg_by: Vec<Vec<u64>> = vec![Vec::new(); 10];
            for i in 0..input.height {
                for j in 0..input.width {
                    let at = i * input.width + j;
                    let a = input.cells[at].min(9);
                    in_color[at] = a;
                    color_count[a as usize] += 1;
                    if a != facts.bg {
                        in_flags[at] |= FG;
                        fg_by[a as usize].push(pack(i as i32, j as i32));
                    }
                    if facts.same && a != output.cells[i * output.width + j] {
                        in_flags[at] |= CHANGED;
                        changed_len += 1;
                    }
                }
            }
            let (mut fg_frame, mut changed_frame, mut ofg_frame): (Frame, Frame, Frame) = ([0; 32], [0; 32], [0; 32]);
            let mut color_frames: [Frame; 10] = [[0; 32]; 10];
            for i in 0..input.height.min(32) {
                for j in 0..input.width.min(32) {
                    let at = i * input.width + j;
                    color_frames[in_color[at] as usize][i] |= 1 << j;
                    if in_flags[at] & FG != 0 {
                        fg_frame[i] |= 1 << j;
                    }
                    if in_flags[at] & CHANGED != 0 {
                        changed_frame[i] |= 1 << j;
                    }
                }
            }
            let mut out_flags = vec![0u8; output.height * output.width];
            let mut ofg_len = 0;
            for i in 0..output.height {
                for j in 0..output.width {
                    let at = i * output.width + j;
                    let b = output.cells[at].min(9);
                    if b != facts.obg {
                        out_flags[at] |= OFG;
                        ofg_len += 1;
                        ofg_by[b as usize].push(pack(i as i32, j as i32));
                    }
                }
            }
            for i in 0..output.height.min(32) {
                for j in 0..output.width.min(32) {
                    if out_flags[i * output.width + j] & OFG != 0 {
                        ofg_frame[i] |= 1 << j;
                    }
                }
            }
            let iobj = objects(&fg_by);
            let oobj = objects(&ofg_by);
            let in_place = ShapeSet::new(iobj.clone());
            let unchanged = |part: &Vec<u64>| {
                part.iter().all(|&cell| {
                    let (i, j) = crate::cells::unpack(cell);
                    input.cells[i as usize * input.width + j as usize] == output.cells[i as usize * output.width + j as usize]
                })
            };
            let live: Vec<Vec<u64>> = oobj.iter().filter(|part| !(facts.same && in_place.contains(part) && unchanged(part))).cloned().collect();
            Heavy {
                in_flags,
                in_color,
                color_count,
                changed_len,
                out_flags,
                ofg_len,
                fg_frame,
                changed_frame,
                ofg_frame,
                color_frames,
                nin: ShapeSet::new(shapes_of(&iobj)),
                nout: ShapeSet::new(shapes_of(&oobj)),
                live: ShapeSet::new(shapes_of(&live)),
            }
        })
    }
}

/// The cells that a train output wants, as `Gate`'s cell masks have them: for a mask of size 9000 the cell (y, x, color),
/// for 900 the cell, for 10 the color. Each mask is a bit set.
#[derive(Debug)]
pub(crate) struct Masks {
    want: Vec<u64>,
    right: Vec<u64>,
    want_cell: Vec<u64>,
    want_color: Vec<u64>,
    /// The count of bits set in `want`, `want_cell` and `want_color`.
    wanted: [usize; 3],
}

fn bit_set(of: &[bool]) -> Vec<u64> {
    let mut bits = vec![0u64; of.len().div_ceil(64)];
    for (at, &on) in of.iter().enumerate() {
        if on {
            bits[at >> 6] |= 1 << (at & 63);
        }
    }
    bits
}

impl Masks {
    fn of(pair: &Pair) -> Masks {
        let (input, output) = (&pair.input, &pair.output);
        let same = input.height == output.height && input.width == output.width;
        let (mut want, mut right) = (vec![false; 9000], vec![false; 9000]);
        for i in 0..output.height.min(30) {
            for j in 0..output.width.min(30) {
                let c = output.cells[i * output.width + j].min(9);
                let at = 300 * i + 10 * j + c as usize;
                right[at] = true;
                want[at] = !same || input.cells[i * input.width + j] != c;
            }
        }
        let mut want_cell = vec![false; 900];
        let mut want_color = vec![false; 10];
        for (at, &w) in want.iter().enumerate() {
            if w {
                want_cell[at / 10] = true;
                want_color[at % 10] = true;
            }
        }
        let count = |of: &[bool]| of.iter().filter(|w| **w).count();
        let wanted = [count(&want), count(&want_cell), count(&want_color)];
        Masks { want: bit_set(&want), right: bit_set(&right), want_cell: bit_set(&want_cell), want_color: bit_set(&want_color), wanted }
    }

    /// How well the rows of `suit` fit the pair: the wanted cells hit over the cells wanted plus the wrong cells.
    pub fn overlap(&self, suit: &SuitSummary) -> f64 {
        let (want, right, wanted) = match suit.kind {
            SuitKind::CellColor => (&self.want, &self.right, self.wanted[0]),
            SuitKind::Cell => (&self.want_cell, &self.want_cell, self.wanted[1]),
            SuitKind::Color => (&self.want_color, &self.want_color, self.wanted[2]),
        };
        let hit: usize = suit.places.iter().zip(want).map(|(seen, want)| (seen & want).count_ones() as usize).sum();
        let wrong: usize = suit.places.iter().zip(right).map(|(seen, right)| (seen & !right).count_ones() as usize).sum();
        hit as f64 / (wanted + wrong + suit.out).max(1) as f64
    }
}

/// The cells of an output that has at most 32 by 32 cells, of colors 0 to 9, as frames.
#[derive(Debug)]
pub(crate) struct FillFrames {
    /// The cells of the output.
    pub inside: Frame,
    /// The output's cells of each color.
    pub out_color: [Frame; 10],
    /// The cells where the color before any paint is the output's color.
    pub was: Frame,
    /// The cells where the color before any paint is each color.
    pub base_color: [Frame; 10],
}

impl FillFrames {
    fn of(pair: &Pair) -> Option<FillFrames> {
        let (input, output) = (&pair.input, &pair.output);
        if output.height > 32 || output.width > 32 || output.cells.iter().any(|&color| color > 9) {
            return None;
        }
        let facts = pair.facts();
        let mut frames = FillFrames { inside: [0; 32], out_color: [[0; 32]; 10], was: [0; 32], base_color: [[0; 32]; 10] };
        for i in 0..output.height {
            for j in 0..output.width {
                let at = i * output.width + j;
                let want = output.cells[at];
                let base = if facts.same { input.cells[at] } else { facts.obg };
                frames.inside[i] |= 1 << j;
                frames.out_color[want as usize][i] |= 1 << j;
                if base == want {
                    frames.was[i] |= 1 << j;
                }
                if base <= 9 {
                    frames.base_color[base as usize][i] |= 1 << j;
                }
            }
        }
        Some(frames)
    }
}
