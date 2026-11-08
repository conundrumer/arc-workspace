//! The parts with no hole: what a train pair's grids give, as relations.
//!
//! Each part has a name, its columns, and whether it reads the input or the output. Its rows
//! come from `catalog_facts`, encoded as the engine encodes cells, so they join with a table's.

use std::sync::{Arc, OnceLock};

use arclog::registry::Registry;
use arclog::terms::{Color, Constant, Term};
use arclog::types::ValueType;

use crate::catalog_facts::*;
use crate::native::{Cell, FastMap, Table};

/// How cells are written: the bits of each color and orientation.
pub struct Encoding {
    pub colors: [Cell; 10],
    pub dirs: [Cell; 8],
    pub axes: [Cell; 2],
    pub d4: [Cell; 8],
}

fn constant_bits(name: &str) -> Cell {
    let constant = Registry::get().orientation_constant(name).expect("a constant of the registry");
    Term::Constant(Constant::Orientation(constant)).encode().expect("a constant has bits").encoding()
}

pub fn encoding() -> &'static Encoding {
    static HELD: OnceLock<Encoding> = OnceLock::new();
    HELD.get_or_init(|| Encoding {
        colors: std::array::from_fn(|digit| Term::Constant(Constant::Color(Color::from_digit(digit as u8).expect("a digit"))).encode().expect("a color has bits").encoding()),
        dirs: ["DIR_T", "DIR_B", "DIR_L", "DIR_R", "DIAG_TL", "DIAG_TR", "DIAG_BL", "DIAG_BR"].map(constant_bits),
        axes: ["AXIS_V", "AXIS_H"].map(constant_bits),
        d4: ["D4_ID", "D4_LR", "D4_TB", "D4_HT", "D4_CW", "D4_CC", "D4_DG", "D4_AD"].map(constant_bits),
    })
}

/// The bits of a number: its low 32 bits, as the engine encodes a `number`.
#[inline]
pub fn number_bits(n: i64) -> Cell {
    n as i32 as u32
}

#[inline]
pub fn number_of(bits: Cell) -> i64 {
    i64::from(bits as i32)
}

#[inline]
pub fn box_bits(top: i32, bottom: i32, left: i32, right: i32) -> Cell {
    // The four margins as signed bytes, the top in the low byte, as a Box's term id packs them. A margin outside a signed byte has no id.
    let byte = |margin: i32| i8::try_from(margin).map(|margin| u32::from(margin as u8));
    match (byte(top), byte(bottom), byte(left), byte(right)) {
        (Ok(t), Ok(b), Ok(l), Ok(r)) => t | (b << 8) | (l << 16) | (r << 24),
        _ => u32::MAX,
    }
}

#[inline]
pub fn margins_of(bits: Cell) -> [i32; 4] {
    let byte = |shift: u32| i32::from((bits >> shift) as u8 as i8);
    [byte(0), byte(8), byte(16), byte(24)]
}

/// The bits of a cell of a grid.
#[inline]
fn cell_bits(h: usize, w: usize, at: usize) -> Cell {
    let (r, c) = ((at / w) as i32, (at % w) as i32);
    box_bits(r, h as i32 - 1 - r, c, w as i32 - 1 - c)
}

fn span_bits(h: usize, w: usize, span: [u8; 4]) -> Cell {
    box_bits(i32::from(span[0]), h as i32 - 1 - i32::from(span[1]), i32::from(span[2]), w as i32 - 1 - i32::from(span[3]))
}

/// A part's name and columns, and what it reads.
pub struct ConstantPart {
    pub name: String,
    pub columns: Vec<(&'static str, ValueType)>,
    pub reads_output: bool,
    pub reads_input: bool,
    /// Whether a table meets the part. A part with no such meeting is a feature of the base tables alone.
    pub meets_table: bool,
}

const CELL_ROLE_NAMES: [&str; CELL_ROLES] = ["boundary", "box-corner", "box-center", "tip", "single-cell", "full-line", "grid-edge", "grid-corner", "next-to-foreground", "enclosed-by-foreground", "crossing", "between-foreground", "breaks-period"];
const COLOR_ROLE_NAMES: [&str; COLOR_ROLES] = ["whole-lines", "single-cells", "one-component", "every-edge", "no-edge", "encloses", "enclosed", "fills-boxes", "largest-component", "most-components", "symmetric"];

fn id_of(source: u8) -> ValueType {
    let _ = source;
    ValueType::OPEN_IDENT
}

/// Each constant part, in the order that `constant_tables` gives their rows.
pub fn constant_parts() -> Vec<ConstantPart> {
    let mut out = Vec::new();
    let (p, col, n, b) = (ValueType::Position, ValueType::Color, ValueType::Nat, ValueType::Box);
    for (grid, is_output) in [("input", false), ("output", true)] {
        let mut part = |name: String, columns: Vec<(&'static str, ValueType)>| out.push(ConstantPart { name, columns, reads_output: is_output, reads_input: !is_output, meets_table: true });
        part(format!("{grid}-color-counts"), vec![("Col", col.clone()), ("N", n.clone())]);
        part(format!("{grid}-most-colors"), vec![("Col", col.clone())]);
        part(format!("{grid}-least-colors"), vec![("Col", col.clone())]);
        part(format!("{grid}-foreground"), vec![("P", p.clone()), ("Col", col.clone())]);
        part(format!("{grid}-background-cells"), vec![("P", p.clone()), ("Col", col.clone())]);
        part(format!("{grid}-components"), vec![("P", p.clone()), ("Col", col.clone()), ("Id", id_of(1))]);
        part(format!("{grid}-foreground-components"), vec![("P", p.clone()), ("Id", id_of(2))]);
        part(format!("{grid}-component-boxes"), vec![("Col", col.clone()), ("Id", id_of(1)), ("B", b.clone())]);
        part(format!("{grid}-component-shapes"), vec![("P", p.clone()), ("Id_2", id_of(1))]);
        part(format!("{grid}-component-shapes-d4"), vec![("P", p.clone()), ("Id_2", id_of(1))]);
        part(format!("{grid}-component-sizes"), vec![("P", p.clone()), ("N", n.clone())]);
        part(format!("{grid}-full-lines"), vec![("A", ValueType::Axis), ("Along", b.clone()), ("Col", col.clone())]);
        part(format!("{grid}-extents"), vec![("A", ValueType::Axis), ("N", ValueType::Int)]);
        for side in ["longer-side", "shorter-side"] {
            part(format!("{grid}-{side}"), vec![("N", ValueType::Int)]);
        }
        for side in ["area", "color-count"] {
            part(format!("{grid}-{side}"), vec![("N", n.clone())]);
        }
        for role in CELL_ROLE_NAMES {
            part(format!("{grid}-cells-{role}"), vec![("P", p.clone())]);
        }
        for role in COLOR_ROLE_NAMES {
            part(format!("{grid}-colors-{role}"), vec![("Col", col.clone())]);
        }
        part(format!("{grid}-foreground-count"), vec![("N", n.clone())]);
        part(format!("{grid}-foreground-component-count"), vec![("N", n.clone())]);
        part(format!("{grid}-component-count"), vec![("N", n.clone())]);
        part(format!("{grid}-foreground-box"), vec![("B", b.clone())]);
        part(format!("{grid}-foreground-box-margins"), vec![("D", ValueType::Dir), ("K", ValueType::Int)]);
        part(format!("{grid}-foreground-box-extents"), vec![("A", ValueType::Axis), ("N", ValueType::Int)]);
        part(format!("{grid}-symmetries"), vec![("D", ValueType::D4)]);
        part(format!("{grid}-periods"), vec![("A", ValueType::Axis), ("K", n.clone())]);
        part(format!("{grid}-fundamental-periods"), vec![("A", ValueType::Axis), ("K", n.clone())]);
        part(format!("{grid}-approximate-periods"), vec![("A", ValueType::Axis), ("K", n.clone())]);
    }
    let mut pair = |name: &str, columns: Vec<(&'static str, ValueType)>| out.push(ConstantPart { name: name.to_string(), columns, reads_output: true, reads_input: true, meets_table: true });
    pair("changed", vec![("P", p.clone()), ("Col", col.clone()), ("Col_2", col.clone())]);
    pair("kept", vec![("P", p.clone()), ("Col", col.clone())]);
    pair("changed-components", vec![("P", p.clone()), ("Id", id_of(3))]);
    pair("colors-added", vec![("Col", col.clone())]);
    pair("colors-dropped", vec![("Col", col.clone())]);
    pair("colors-changed-from", vec![("Col", col.clone())]);
    pair("colors-changed-to", vec![("Col", col.clone())]);
    pair("changed-box", vec![("B", b.clone())]);
    pair("changed-box-margins", vec![("D", ValueType::Dir), ("K", ValueType::Int)]);
    pair("changed-box-extents", vec![("A", ValueType::Axis), ("N", ValueType::Int)]);
    pair("changed-component-boxes", vec![("Id", id_of(3)), ("B", b.clone())]);
    pair("changed-count", vec![("N", n.clone())]);
    pair("changed-component-count", vec![("N", n.clone())]);
    pair("kept-count", vec![("N", n.clone())]);
    pair("input-output-images", vec![("D", ValueType::D4)]);
    pair("output-in-input", vec![("B", b.clone())]);
    pair("input-in-output", vec![("B", b.clone())]);
    pair("output-in-input-d4", vec![("D", ValueType::D4), ("B", b.clone())]);
    pair("input-in-output-d4", vec![("D", ValueType::D4), ("B", b.clone())]);
    pair("output-diff", vec![("P", p.clone()), ("Col", col.clone())]);
    pair("input-diff", vec![("P", p.clone()), ("Col", col.clone())]);
    pair("diff-moves", vec![("V", ValueType::Offset), ("N", n.clone())]);
    pair("best-moves", vec![("V", ValueType::Offset)]);
    pair("best-move-landed", vec![("N", n.clone())]);
    pair("best-move-size", vec![("K", ValueType::Int)]);
    pair("best-move-cells", vec![("P", p.clone()), ("Col", col.clone()), ("V", ValueType::Offset)]);
    pair("shared-periods", vec![("A", ValueType::Axis), ("K", n.clone())]);
    pair("shared-fundamental-periods", vec![("K", n.clone())]);
    for kind in ["scale-up", "tile", "scale-down"] {
        out.push(ConstantPart { name: kind.to_string(), columns: vec![("P_in", p.clone()), ("P_out", p.clone()), ("Col", col.clone()), ("Col_2", col.clone())], reads_output: true, reads_input: true, meets_table: false });
        out.push(ConstantPart { name: format!("{kind}-kept"), columns: vec![("P_in", p.clone()), ("P_out", p.clone()), ("Col", col.clone())], reads_output: true, reads_input: true, meets_table: false });
        out.push(ConstantPart { name: format!("{kind}-changed"), columns: vec![("P_in", p.clone()), ("P_out", p.clone()), ("Col", col.clone()), ("Col_2", col.clone())], reads_output: true, reads_input: true, meets_table: false });
    }
    let mut lib = |name: &str, columns: Vec<(&'static str, ValueType)>| out.push(ConstantPart { name: name.to_string(), columns, reads_output: false, reads_input: false, meets_table: true });
    lib("dir_elem", vec![("D", ValueType::Dir)]);
    lib("diag_dir_elem", vec![("D", ValueType::DiagDir)]);
    lib("axis_elem", vec![("A", ValueType::Axis)]);
    lib("d4_elem", vec![("D", ValueType::D4)]);
    lib("d4-identity", vec![("D", ValueType::D4)]);
    lib("axis_of", vec![("D", ValueType::Dir), ("A", ValueType::Axis)]);
    lib("opposite", vec![("D", ValueType::Dir), ("Opp", ValueType::Dir)]);
    out
}

/// The D4 image of a cell of a frame of `h` by `w`, in the order ID, LR, TB, HT, CW, CC, DG, AD.
pub fn image_cell(which: usize, r: usize, c: usize, h: usize, w: usize) -> (usize, usize) {
    match which {
        0 => (r, c),
        1 => (r, w - 1 - c),
        2 => (h - 1 - r, c),
        3 => (h - 1 - r, w - 1 - c),
        4 => (c, h - 1 - r),
        5 => (w - 1 - c, r),
        6 => (c, r),
        _ => (w - 1 - c, h - 1 - r),
    }
}

/// Where a shape's D4 image equals a grid at every cell of the image: the box of each place,
/// in the grid's frame. A D4 image that a symmetry of the shape repeats gives each of its elements.
fn occurrences(shape: &GridFacts, grid: &GridFacts, which: usize) -> Vec<Cell> {
    let (h, w) = if which >= 4 { (shape.w, shape.h) } else { (shape.h, shape.w) };
    let mut out = Vec::new();
    if h > grid.h || w > grid.w {
        return out;
    }
    let mut image = vec![0u8; h * w];
    for r in 0..shape.h {
        for c in 0..shape.w {
            let (y, z) = image_cell(which, r, c, shape.h, shape.w);
            image[y * w + z] = shape.color[r * shape.w + c];
        }
    }
    for dr in 0..=grid.h - h {
        for dc in 0..=grid.w - w {
            if (0..h).all(|y| (0..w).all(|z| grid.color[(y + dr) * grid.w + z + dc] == image[y * w + z])) {
                out.push(box_bits(dr as i32, (grid.h - h - dr) as i32, dc as i32, (grid.w - w - dc) as i32));
            }
        }
    }
    out
}

/// A cell list as three parts: every pair with both colors, those with one color, and those with two.
fn read_tables(pairs: &[(usize, usize)], input: &GridFacts, output: &GridFacts, e: &Encoding, out: &mut Vec<Arc<Table>>) {
    let (mut all, mut kept, mut changed) = (Vec::with_capacity(pairs.len() * 4), Vec::new(), Vec::new());
    for (at_in, at_out) in pairs {
        let (from, to) = (input.color[*at_in], output.color[*at_out]);
        let (p_in, p_out) = (cell_bits(input.h, input.w, *at_in), cell_bits(output.h, output.w, *at_out));
        all.extend_from_slice(&[p_in, p_out, e.colors[from as usize], e.colors[to as usize]]);
        if from == to {
            kept.extend_from_slice(&[p_in, p_out, e.colors[from as usize]]);
        } else {
            changed.extend_from_slice(&[p_in, p_out, e.colors[from as usize], e.colors[to as usize]]);
        }
    }
    out.push(Table::new(4, all));
    out.push(Table::new(3, kept));
    out.push(Table::new(4, changed));
}

/// The output's cells, each with the input cell its block, its copy or its place gives.
/// `Division`: where the parts do not fill an extent, no cell has a row.
fn scale_up_pairs(input: &GridFacts, output: &GridFacts) -> Vec<(usize, usize)> {
    if output.h % input.h != 0 || output.w % input.w != 0 {
        return Vec::new();
    }
    let (k, m) = (output.h / input.h, output.w / input.w);
    (0..output.h * output.w).map(|at| {
        let (r, c) = (at / output.w, at % output.w);
        ((r / k) * input.w + c / m, at)
    }).collect()
}

fn tile_pairs(input: &GridFacts, output: &GridFacts) -> Vec<(usize, usize)> {
    if output.h % input.h != 0 || output.w % input.w != 0 {
        return Vec::new();
    }
    (0..output.h * output.w).map(|at| {
        let (r, c) = (at / output.w, at % output.w);
        ((r % input.h) * input.w + c % input.w, at)
    }).collect()
}

fn scale_down_pairs(input: &GridFacts, output: &GridFacts) -> Vec<(usize, usize)> {
    if input.h % output.h != 0 || input.w % output.w != 0 {
        return Vec::new();
    }
    let (k, m) = (input.h / output.h, input.w / output.w);
    (0..input.h * input.w).map(|at| {
        let (r, c) = (at / input.w, at % input.w);
        (at, (r / k) * output.w + c / m)
    }).collect()
}

fn margin_rows(span: [u8; 4], h: usize, w: usize, e: &Encoding) -> Vec<Cell> {
    let margins = [i64::from(span[0]), h as i64 - 1 - i64::from(span[1]), i64::from(span[2]), w as i64 - 1 - i64::from(span[3])];
    let mut out = Vec::with_capacity(8);
    for at in 0..4 {
        out.push(e.dirs[at]);
        out.push(number_bits(margins[at]));
    }
    out
}

fn extent_rows(span: [u8; 4], e: &Encoding) -> Vec<Cell> {
    vec![e.axes[0], number_bits(i64::from(span[1]) - i64::from(span[0]) + 1), e.axes[1], number_bits(i64::from(span[3]) - i64::from(span[2]) + 1)]
}


fn color_rows(mask: u16, e: &Encoding) -> Vec<Cell> {
    (0..10).filter(|col| mask >> col & 1 == 1).map(|col| e.colors[col]).collect()
}

fn grid_tables(g: &GridFacts, e: &Encoding, out: &mut Vec<Arc<Table>>) {
    let (h, w) = (g.h, g.w);
    let present: Vec<usize> = (0..10).filter(|col| g.counts[*col] > 0).collect();
    let mut counts = Vec::with_capacity(present.len() * 2);
    for col in &present {
        counts.push(e.colors[*col]);
        counts.push(number_bits(i64::from(g.counts[*col])));
    }
    out.push(Table::new(2, counts));
    let most = present.iter().map(|col| g.counts[*col]).max().unwrap_or(0);
    let least = present.iter().map(|col| g.counts[*col]).min().unwrap_or(0);
    out.push(Table::new(1, present.iter().filter(|col| g.counts[**col] == most).map(|col| e.colors[*col]).collect()));
    out.push(Table::new(1, present.iter().filter(|col| g.counts[**col] == least).map(|col| e.colors[*col]).collect()));
    // Under a tie, every most common color is background, as `Order`'s `maximal` gives.
    let is_background = |color: u8| g.counts[color as usize] == most;
    let mut foreground = Vec::new();
    let mut background = Vec::new();
    let mut foreground_cells = Bits::EMPTY;
    for at in 0..h * w {
        let row = [cell_bits(h, w, at), e.colors[g.color[at] as usize]];
        if is_background(g.color[at]) {
            background.extend_from_slice(&row);
        } else {
            foreground.extend_from_slice(&row);
            foreground_cells.set(at);
        }
    }
    out.push(Table::new(2, foreground));
    out.push(Table::new(2, background));
    let mut components = Vec::with_capacity(h * w * 3);
    let mut boxes = Vec::with_capacity(g.pieces.len() * 3);
    for (id, piece) in g.pieces.iter().enumerate() {
        piece.cells.each(|at| {
            components.push(cell_bits(h, w, at));
            components.push(e.colors[piece.color as usize]);
            components.push(id as u32);
        });
        boxes.push(e.colors[piece.color as usize]);
        boxes.push(id as u32);
        boxes.push(span_bits(h, w, piece.span));
    }
    out.push(Table::new(3, components));
    let mut parts = Vec::new();
    let foreground_parts = crate::catalog_facts::parts(&foreground_cells, h, w);
    for (id, part) in foreground_parts.iter().enumerate() {
        part.each(|at| {
            parts.push(cell_bits(h, w, at));
            parts.push(id as u32);
        });
    }
    out.push(Table::new(2, parts));
    out.push(Table::new(3, boxes));
    // Each cell with a class per shape of its piece, with that up to D4, and with its piece's size.
    let mut shapes = Vec::with_capacity(h * w * 2);
    let mut turned = Vec::with_capacity(h * w * 2);
    let mut sizes = Vec::with_capacity(h * w * 2);
    for piece in &g.pieces {
        let mut cells: Vec<(u8, u8)> = Vec::with_capacity(piece.size as usize);
        piece.cells.each(|at| cells.push(((at / w) as u8, (at % w) as u8)));
        let (own, all) = (crate::cell_sets::shape_hash(&cells, false), crate::cell_sets::shape_hash(&cells, true));
        piece.cells.each(|at| {
            let cell = cell_bits(h, w, at);
            shapes.extend_from_slice(&[cell, own]);
            turned.extend_from_slice(&[cell, all]);
            sizes.extend_from_slice(&[cell, number_bits(i64::from(piece.size))]);
        });
    }
    out.push(Table::new(2, shapes));
    out.push(Table::new(2, turned));
    out.push(Table::new(2, sizes));
    let mut lines = Vec::new();
    for (r, mask) in g.line_colors[0].iter().enumerate() {
        if mask.count_ones() == 1 {
            lines.extend_from_slice(&[e.axes[0], box_bits(r as i32, h as i32 - 1 - r as i32, 0, 0), e.colors[mask.trailing_zeros() as usize]]);
        }
    }
    for (c, mask) in g.line_colors[1].iter().enumerate() {
        if mask.count_ones() == 1 {
            lines.extend_from_slice(&[e.axes[1], box_bits(0, 0, c as i32, w as i32 - 1 - c as i32), e.colors[mask.trailing_zeros() as usize]]);
        }
    }
    out.push(Table::new(3, lines));
    out.push(Table::new(2, vec![e.axes[0], number_bits(h as i64), e.axes[1], number_bits(w as i64)]));
    out.push(Table::new(1, vec![number_bits(h.max(w) as i64)]));
    out.push(Table::new(1, vec![number_bits(h.min(w) as i64)]));
    out.push(Table::new(1, vec![number_bits((h * w) as i64)]));
    out.push(Table::new(1, vec![number_bits(present.len() as i64)]));
    for role in &g.roles {
        let mut cells = Vec::with_capacity(role.count() as usize);
        role.each(|at| cells.push(cell_bits(h, w, at)));
        out.push(Table::new(1, cells));
    }
    for mask in &g.color_roles {
        out.push(Table::new(1, color_rows(*mask, e)));
    }
    out.push(Table::new(1, vec![number_bits(i64::from(foreground_cells.count()))]));
    out.push(Table::new(1, vec![number_bits(foreground_parts.len() as i64)]));
    out.push(Table::new(1, vec![number_bits(g.pieces.len() as i64)]));
    let span = span_of(&foreground_cells, w);
    out.push(Table::new(1, span.map_or_else(Vec::new, |held| vec![span_bits(h, w, held)])));
    out.push(Table::new(2, span.map_or_else(Vec::new, |held| margin_rows(held, h, w, e))));
    out.push(Table::new(2, span.map_or_else(Vec::new, |held| extent_rows(held, e))));
    out.push(Table::new(1, (0..8).filter(|which| crate::catalog_facts::image_is(g, g, *which)).map(|which| e.d4[which]).collect()));
    let periods = periods_of(g);
    let rows_of = |lists: [Vec<usize>; 2]| -> Vec<Cell> {
        let mut rows = Vec::new();
        for (axis, list) in lists.iter().enumerate() {
            for k in list {
                rows.extend_from_slice(&[e.axes[axis], number_bits(*k as i64)]);
            }
        }
        rows
    };
    let fundamental = [periods.exact[0].first().copied().into_iter().collect(), periods.exact[1].first().copied().into_iter().collect()];
    out.push(Table::new(2, rows_of(periods.exact.clone())));
    out.push(Table::new(2, rows_of(fundamental)));
    out.push(Table::new(2, rows_of(periods.approximate)));
}

/// A grid's periods along each axis, the rows first, and those read through damage.
struct Periods {
    exact: [Vec<usize>; 2],
    approximate: [Vec<usize>; 2],
}

fn periods_of(g: &GridFacts) -> Periods {
    let mut out = Periods { exact: [Vec::new(), Vec::new()], approximate: [Vec::new(), Vec::new()] };
    for axis in 0..2 {
        let (n, m) = if axis == 0 { (g.h, g.w) } else { (g.w, g.h) };
        let cell = |line: usize, place: usize| if axis == 0 { g.color[line * g.w + place] } else { g.color[place * g.w + line] };
        for k in 1..n {
            let lines = n - k;
            let broken = (0..lines).filter(|a| (0..m).any(|place| cell(*a, place) != cell(*a + k, place))).count();
            if broken == 0 {
                out.exact[axis].push(k);
            }
            if broken <= lines - broken {
                out.approximate[axis].push(k);
            }
        }
    }
    out
}

/// How the input's diff stands to the output's: each move, with the input's diff cells that it lands on
/// output diff cells of their color, in the order of `from`.
fn moves_between(from: &[(usize, Cell, [i32; 4])], to: &[(usize, Cell, [i32; 4])]) -> FastMap<Cell, Vec<usize>> {
    let mut by_color: FastMap<Cell, Vec<[i32; 4]>> = FastMap::default();
    for (_, color, margins) in to {
        by_color.entry(*color).or_default().push(*margins);
    }
    let mut out: FastMap<Cell, Vec<usize>> = FastMap::default();
    for (at, color, margins) in from {
        for held in by_color.get(color).into_iter().flatten() {
            let v = box_bits(held[0] - margins[0], held[1] - margins[1], held[2] - margins[2], held[3] - margins[3]);
            out.entry(v).or_default().push(*at);
        }
    }
    out
}

/// Each constant part's rows at one pair, in the order of `constant_parts`.
pub fn constant_tables(f: &PairFacts) -> Vec<Arc<Table>> {
    let e = encoding();
    let mut out = Vec::with_capacity(90);
    grid_tables(&f.input, e, &mut out);
    grid_tables(&f.output, e, &mut out);
    let (h, w) = (f.output.h, f.output.w);
    let mut changed = Vec::new();
    let mut kept = Vec::new();
    if f.same {
        for at in 0..h * w {
            let (from, to) = (f.input.color[at], f.output.color[at]);
            if from == to {
                kept.extend_from_slice(&[cell_bits(h, w, at), e.colors[from as usize]]);
            } else {
                changed.extend_from_slice(&[cell_bits(h, w, at), e.colors[from as usize], e.colors[to as usize]]);
            }
        }
    }
    out.push(Table::new(3, changed));
    out.push(Table::new(2, kept));
    let mut parts = Vec::new();
    if !f.changed.is_empty() {
        for (id, part) in crate::catalog_facts::parts(&f.changed, h, w).iter().enumerate() {
            part.each(|at| {
                parts.push(cell_bits(h, w, at));
                parts.push(id as u32);
            });
        }
    }
    out.push(Table::new(2, parts));
    out.push(Table::new(1, color_rows(f.output.colors & !f.input.colors, e)));
    out.push(Table::new(1, color_rows(f.input.colors & !f.output.colors, e)));
    out.push(Table::new(1, color_rows(f.changed_from, e)));
    out.push(Table::new(1, color_rows(f.changed_to, e)));
    let span = f.changed_span;
    out.push(Table::new(1, span.map_or_else(Vec::new, |held| vec![span_bits(h, w, held)])));
    out.push(Table::new(2, span.map_or_else(Vec::new, |held| margin_rows(held, h, w, e))));
    out.push(Table::new(2, span.map_or_else(Vec::new, |held| extent_rows(held, e))));
    let mut boxes = Vec::new();
    if !f.changed.is_empty() {
        for (id, part) in crate::catalog_facts::parts(&f.changed, h, w).iter().enumerate() {
            if let Some(held) = span_of(part, w) {
                boxes.push(id as u32);
                boxes.push(span_bits(h, w, held));
            }
        }
    }
    out.push(Table::new(2, boxes));
    let changed_count = i64::from(f.changed.count());
    out.push(Table::new(1, if f.same && changed_count > 0 { vec![number_bits(changed_count)] } else { Vec::new() }));
    out.push(Table::new(1, if f.same && changed_count > 0 { vec![number_bits(i64::from(f.changed_parts))] } else { Vec::new() }));
    let kept_count = (h * w) as i64 - changed_count;
    out.push(Table::new(1, if f.same && kept_count > 0 { vec![number_bits(kept_count)] } else { Vec::new() }));
    out.push(Table::new(1, (0..8).filter(|which| f.maps[*which]).map(|which| e.d4[which]).collect()));
    out.push(Table::new(1, occurrences(&f.output, &f.input, 0)));
    out.push(Table::new(1, occurrences(&f.input, &f.output, 0)));
    let turned = |shape: &GridFacts, grid: &GridFacts| -> Vec<Cell> {
        let mut rows = Vec::new();
        for which in 0..8 {
            for held in occurrences(shape, grid, which) {
                rows.push(e.d4[which]);
                rows.push(held);
            }
        }
        rows
    };
    out.push(Table::new(2, turned(&f.output, &f.input)));
    out.push(Table::new(2, turned(&f.input, &f.output)));
    // A grid's cells that the other does not hold with their color. Two frames of other extents share no cell.
    let diff = |one: &GridFacts, other: &GridFacts| -> Vec<Cell> {
        let mut rows = Vec::new();
        for at in 0..one.h * one.w {
            if !f.same || one.color[at] != other.color[at] {
                rows.extend_from_slice(&[cell_bits(one.h, one.w, at), e.colors[one.color[at] as usize]]);
            }
        }
        rows
    };
    out.push(Table::new(2, diff(&f.output, &f.input)));
    out.push(Table::new(2, diff(&f.input, &f.output)));
    // Grids of other extents have no move between them, and the crop, tile and scale parts stand there.
    let side = |one: &GridFacts, other: &GridFacts| -> Vec<(usize, Cell, [i32; 4])> {
        if !f.same {
            return Vec::new();
        }
        (0..one.h * one.w).filter(|at| one.color[*at] != other.color[*at]).map(|at| (at, e.colors[one.color[at] as usize], margins_of(cell_bits(one.h, one.w, at)))).collect()
    };
    let moves = moves_between(&side(&f.input, &f.output), &side(&f.output, &f.input));
    let most = moves.max_of(|_, cells| cells.len()).unwrap_or(0);
    let mut move_rows = Vec::with_capacity(moves.len() * 2);
    let mut best_rows = Vec::new();
    let mut best_cells = Vec::new();
    let mut farthest = None;
    // The moves stand in the order of their value.
    for (v, cells) in moves.sorted_entries() {
        move_rows.extend_from_slice(&[*v, number_bits(cells.len() as i64)]);
        if cells.len() == most {
            best_rows.push(*v);
            let steps = margins_of(*v).into_iter().max().unwrap_or(0);
            farthest = farthest.max(Some(steps));
            for at in cells {
                best_cells.extend_from_slice(&[cell_bits(f.input.h, f.input.w, *at), e.colors[f.input.color[*at] as usize], *v]);
            }
        }
    }
    out.push(Table::new(2, move_rows));
    out.push(Table::new(1, best_rows));
    out.push(Table::new(1, if most > 0 { vec![number_bits(most as i64)] } else { Vec::new() }));
    out.push(Table::new(1, farthest.map(|steps| number_bits(i64::from(steps))).into_iter().collect()));
    out.push(Table::distinct(3, best_cells));
    let (in_periods, out_periods) = (periods_of(&f.input), periods_of(&f.output));
    let mut shared = Vec::new();
    for axis in 0..2 {
        for k in &in_periods.exact[axis] {
            if out_periods.exact[axis].contains(k) {
                shared.extend_from_slice(&[e.axes[axis], number_bits(*k as i64)]);
            }
        }
    }
    out.push(Table::new(2, shared));
    let least = |held: &Periods| -> Vec<usize> { held.exact.iter().filter_map(|list| list.first().copied()).collect() };
    let (one, two) = (least(&in_periods), least(&out_periods));
    let mut both: Vec<Cell> = one.iter().filter(|k| two.contains(k)).map(|k| number_bits(*k as i64)).collect();
    both.sort_unstable();
    both.dedup();
    out.push(Table::new(1, both));
    read_tables(&scale_up_pairs(&f.input, &f.output), &f.input, &f.output, e, &mut out);
    read_tables(&tile_pairs(&f.input, &f.output), &f.input, &f.output, e, &mut out);
    read_tables(&scale_down_pairs(&f.input, &f.output), &f.input, &f.output, e, &mut out);
    lib_tables(e, &mut out);
    out
}

/// The parts that no grid gives.
fn lib_tables(e: &Encoding, out: &mut Vec<Arc<Table>>) {
    out.push(Table::new(1, e.dirs[..4].to_vec()));
    out.push(Table::new(1, e.dirs[4..].to_vec()));
    out.push(Table::new(1, e.axes.to_vec()));
    out.push(Table::new(1, e.d4.to_vec()));
    out.push(Table::new(1, vec![e.d4[0]]));
    out.push(Table::new(2, vec![e.dirs[0], e.axes[0], e.dirs[1], e.axes[0], e.dirs[2], e.axes[1], e.dirs[3], e.axes[1]]));
    out.push(Table::new(2, vec![e.dirs[0], e.dirs[1], e.dirs[1], e.dirs[0], e.dirs[2], e.dirs[3], e.dirs[3], e.dirs[2]]));
}

/// Each constant part's rows at an example with no output: those of its input and those that no
/// grid gives, in the order of `constant_parts`, and no value for the others.
pub fn input_only_tables(g: &GridFacts) -> Vec<Option<Arc<Table>>> {
    let e = encoding();
    let parts = constant_parts();
    let mut own = Vec::with_capacity(64);
    grid_tables(g, e, &mut own);
    let mut lib = Vec::with_capacity(8);
    lib_tables(e, &mut lib);
    let mut own = own.into_iter();
    let mut lib = lib.into_iter();
    parts.iter().map(|part| match (part.reads_input, part.reads_output) {
        (true, false) => own.next(),
        (false, false) => lib.next(),
        _ => None,
    }).collect()
}

/// Whether a term's token names a part of the base tables.
pub fn is_part_name(name: &str) -> bool {
    static NAMES: OnceLock<crate::lookup::LookupSet<String>> = OnceLock::new();
    NAMES.get_or_init(|| constant_parts().into_iter().map(|part| part.name).collect()).contains(name)
}

/// The call of a part of the base tables, in the feature library or as a lib relation.
pub fn part_call(name: &str) -> String {
    const LIB: [&str; 6] = ["dir_elem", "diag_dir_elem", "axis_elem", "d4_elem", "axis_of", "opposite"];
    if LIB.contains(&name) {
        return name.to_string();
    }
    if name == "input-full-lines" || name == "output-full-lines" {
        return format!("(full-lines-of {})", &name[..name.find('-').unwrap_or(0)]);
    }
    for grid in ["input", "output"] {
        let (pieces, word) = (format!("(components {grid})"), name.strip_prefix(grid).unwrap_or(""));
        match word {
            "-component-shapes" => return format!("(project (join {pieces} (shape-class {pieces} (Col Id) P) (Col Col) (Id Id)) P Id_2)"),
            "-component-shapes-d4" => return format!("(project (join {pieces} (shape-class-d4 {pieces} (Col Id) P) (Col Col) (Id Id)) P Id_2)"),
            "-component-sizes" => return format!("(project (join {pieces} (count {pieces} (Col Id)) (Col Col) (Id Id)) P N)"),
            _ => {}
        }
    }
    for grid in ["input", "output"] {
        if let Some(rest) = name.strip_prefix(grid).and_then(|rest| rest.strip_prefix('-')) {
            if !matches!(name, "input-in-output" | "output-in-input" | "input-in-output-d4" | "output-in-input-d4" | "input-output-images" | "output-diff" | "input-diff") {
                return format!("({rest} {grid})");
            }
        }
    }
    format!("({name})")
}
