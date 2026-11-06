//! The parts with no hole: what a train pair's grids give, as relations.
//!
//! Each part has a name, its columns, and whether it reads the input or the output. Its rows
//! come from `catalog_facts`, encoded as the engine encodes cells, so they join with a table's.

use std::sync::{Arc, OnceLock};

use arclog::registry::Registry;
use arclog::terms::{Color, Constant, Margins, Term, TermId};
use arclog::types::ValueType;

use crate::catalog_facts::*;
use crate::native::{Cell, Table};

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

#[inline]
pub fn number_bits(n: i64) -> Cell {
    Term::encode_number(n as i32).encoding()
}

#[inline]
pub fn number_of(bits: Cell) -> i64 {
    i64::from(Term::decode_number(TermId::from_encoding(bits)))
}

#[inline]
pub fn box_bits(top: i32, bottom: i32, left: i32, right: i32) -> Cell {
    Term::Box(Margins { top, bottom, left, right }).encode().map_or(u32::MAX, TermId::encoding)
}

#[inline]
pub fn margins_of(bits: Cell) -> [i32; 4] {
    let held = Term::decode_box(TermId::from_encoding(bits));
    [held.top, held.bottom, held.left, held.right]
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
        let mut part = |name: String, columns: Vec<(&'static str, ValueType)>| out.push(ConstantPart { name, columns, reads_output: is_output, reads_input: !is_output });
        part(format!("{grid}-color-counts"), vec![("Col", col.clone()), ("N", n.clone())]);
        part(format!("{grid}-background"), vec![("Col", col.clone())]);
        part(format!("{grid}-most-colors"), vec![("Col", col.clone())]);
        part(format!("{grid}-least-colors"), vec![("Col", col.clone())]);
        part(format!("{grid}-foreground"), vec![("P", p.clone()), ("Col", col.clone())]);
        part(format!("{grid}-background-cells"), vec![("P", p.clone()), ("Col", col.clone())]);
        part(format!("{grid}-components"), vec![("P", p.clone()), ("Col", col.clone()), ("Id", id_of(1))]);
        part(format!("{grid}-foreground-components"), vec![("P", p.clone()), ("Id", id_of(2))]);
        part(format!("{grid}-component-boxes"), vec![("Col", col.clone()), ("Id", id_of(1)), ("B", b.clone())]);
        part(format!("{grid}-full-lines"), vec![("A", ValueType::Axis), ("Along", b.clone()), ("Col", col.clone())]);
        part(format!("{grid}-extents"), vec![("A", ValueType::Axis), ("N", n.clone())]);
        for side in ["longer-side", "shorter-side", "area", "color-count"] {
            part(format!("{grid}-{side}"), vec![("N", n.clone())]);
        }
        for role in CELL_ROLE_NAMES {
            part(format!("{grid}-cells-{role}"), vec![("P", p.clone())]);
        }
        for role in COLOR_ROLE_NAMES {
            part(format!("{grid}-colors-{role}"), vec![("Col", col.clone())]);
        }
    }
    let mut pair = |name: &str, columns: Vec<(&'static str, ValueType)>| out.push(ConstantPart { name: name.to_string(), columns, reads_output: true, reads_input: true });
    pair("changed", vec![("P", p.clone()), ("Col", col.clone()), ("Col_2", col.clone())]);
    pair("kept", vec![("P", p.clone()), ("Col", col.clone())]);
    pair("changed-components", vec![("P", p.clone()), ("Id", id_of(3))]);
    pair("colors-added", vec![("Col", col.clone())]);
    pair("colors-dropped", vec![("Col", col.clone())]);
    pair("colors-changed-from", vec![("Col", col.clone())]);
    pair("colors-changed-to", vec![("Col", col)]);
    out
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
    out.push(Table::new(1, g.background.map_or_else(Vec::new, |col| vec![e.colors[col as usize]])));
    let most = present.iter().map(|col| g.counts[*col]).max().unwrap_or(0);
    let least = present.iter().map(|col| g.counts[*col]).min().unwrap_or(0);
    out.push(Table::new(1, present.iter().filter(|col| g.counts[**col] == most).map(|col| e.colors[*col]).collect()));
    out.push(Table::new(1, present.iter().filter(|col| g.counts[**col] == least).map(|col| e.colors[*col]).collect()));
    let mut foreground = Vec::new();
    let mut background = Vec::new();
    for at in 0..h * w {
        let row = [cell_bits(h, w, at), e.colors[g.color[at] as usize]];
        if g.foreground.as_ref().is_some_and(|cells| cells.get(at)) {
            foreground.extend_from_slice(&row);
        } else if g.background == Some(g.color[at]) {
            background.extend_from_slice(&row);
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
    for (id, part) in g.foreground_parts.iter().enumerate() {
        part.each(|at| {
            parts.push(cell_bits(h, w, at));
            parts.push(id as u32);
        });
    }
    out.push(Table::new(2, parts));
    out.push(Table::new(3, boxes));
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
    out
}
