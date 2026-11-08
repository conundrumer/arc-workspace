//! The catalog of named features, in one pass per table: a plain function from a table's
//! types and rows, and a train pair's grids, to the value of each named feature's bindings.
//! It has no engine dependency. Each kind's expression stands in
//! `model/feature_eval/template_shapes.py`, which also checks the two against each other.

use crate::catalog_facts::*;

#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub enum Kind {
    Position,
    Box,
    Offset,
    Color,
    Nat,
    Int,
    Ident,
    Dir,
    DiagDir,
    Dir8,
    Axis,
    DiagAxis,
    Axis4,
    D4,
    C4,
    Sym,
    Sense,
    Other,
}

impl Kind {
    pub fn of(name: &str) -> Kind {
        match name {
            "Position" => Kind::Position,
            "Box" => Kind::Box,
            "Offset" => Kind::Offset,
            "Color" => Kind::Color,
            "Nat" => Kind::Nat,
            "Int" => Kind::Int,
            "Ident" => Kind::Ident,
            "Dir" => Kind::Dir,
            "DiagDir" => Kind::DiagDir,
            "Dir8" => Kind::Dir8,
            "Axis" => Kind::Axis,
            "DiagAxis" => Kind::DiagAxis,
            "Axis4" => Kind::Axis4,
            "D4" => Kind::D4,
            "C4" => Kind::C4,
            "Sym" => Kind::Sym,
            "Sense" => Kind::Sense,
            _ => Kind::Other,
        }
    }

    pub fn name(self) -> &'static str {
        match self {
            Kind::Position => "Position",
            Kind::Box => "Box",
            Kind::Offset => "Offset",
            Kind::Color => "Color",
            Kind::Nat => "Nat",
            Kind::Int => "Int",
            Kind::Ident => "Ident",
            Kind::Dir => "Dir",
            Kind::DiagDir => "DiagDir",
            Kind::Dir8 => "Dir8",
            Kind::Axis => "Axis",
            Kind::DiagAxis => "DiagAxis",
            Kind::Axis4 => "Axis4",
            Kind::D4 => "D4",
            Kind::C4 => "C4",
            Kind::Sym => "Sym",
            Kind::Sense => "Sense",
            Kind::Other => "Other",
        }
    }

    fn is_number(self) -> bool {
        matches!(self, Kind::Nat | Kind::Int)
    }

    fn is_direction(self) -> bool {
        matches!(self, Kind::Dir | Kind::DiagDir | Kind::Dir8)
    }

    fn is_line(self) -> bool {
        self.is_direction() || matches!(self, Kind::Axis | Kind::DiagAxis | Kind::Axis4)
    }
}

pub const DIR_T: i32 = 0;
pub const DIR_B: i32 = 1;
pub const DIR_L: i32 = 2;
pub const DIR_R: i32 = 3;
pub const DIAG_TL: i32 = 4;
pub const DIAG_TR: i32 = 5;
pub const DIAG_BL: i32 = 6;
pub const DIAG_BR: i32 = 7;
pub const AXIS_V: i32 = 8;
pub const AXIS_H: i32 = 9;
pub const DAXIS_DG: i32 = 10;
pub const DAXIS_AD: i32 = 11;
pub const D4_ID: i32 = 12;
pub const D4_LR: i32 = 13;
pub const D4_TB: i32 = 14;
pub const D4_HT: i32 = 15;
pub const D4_CW: i32 = 16;
pub const D4_CC: i32 = 17;
pub const D4_DG: i32 = 18;
pub const D4_AD: i32 = 19;

/// The code of an orientation's name, or a code past the orientations for any other name.
pub fn orientation(name: &str) -> i32 {
    match name {
        "DIR_T" => DIR_T,
        "DIR_B" => DIR_B,
        "DIR_L" => DIR_L,
        "DIR_R" => DIR_R,
        "DIAG_TL" => DIAG_TL,
        "DIAG_TR" => DIAG_TR,
        "DIAG_BL" => DIAG_BL,
        "DIAG_BR" => DIAG_BR,
        "AXIS_V" => AXIS_V,
        "AXIS_H" => AXIS_H,
        "DAXIS_DG" => DAXIS_DG,
        "DAXIS_AD" => DAXIS_AD,
        "D4_ID" => D4_ID,
        "D4_LR" => D4_LR,
        "D4_TB" => D4_TB,
        "D4_HT" => D4_HT,
        "D4_CW" => D4_CW,
        "D4_CC" => D4_CC,
        "D4_DG" => D4_DG,
        "D4_AD" => D4_AD,
        _ => 20,
    }
}

/// A cell of a table: a box's four margins, or a value in the first place.
pub type Cell = [i32; 4];

/// A table's rows at one train pair.
pub struct TableAt<'a> {
    pub kinds: &'a [Kind],
    pub keys: &'a [bool],
    pub rows: usize,
    pub cells: &'a [Cell],
}

impl TableAt<'_> {
    #[inline]
    pub fn at(&self, row: usize, column: usize) -> Cell {
        self.cells[row * self.kinds.len() + column]
    }
}

/// The value of one binding of a kind. A kind with no value at a pair gives no record.
#[derive(Clone, Copy, PartialEq, Debug)]
pub enum Value {
    Null,
    Bool(bool),
    Num(i64),
    /// An exact fraction, as two counts.
    Share(u32, u32),
    Word(&'static str),
}

#[derive(Clone, Copy, Debug)]
pub struct Record {
    pub kind: &'static str,
    /// The bound columns, with `NONE` past them.
    pub holes: [u8; 3],
    pub value: Value,
}

pub const NONE: u8 = 255;

#[inline]
pub(crate) fn compare(a: i64, b: i64) -> &'static str {
    if a < b {
        "<"
    } else if a == b {
        "="
    } else {
        ">"
    }
}

/// `share(flags)`: a fraction of the flags, or Null where there are none.
#[inline]
pub(crate) fn share(hits: u32, of: u32) -> Value {
    if of == 0 {
        Value::Null
    } else {
        Value::Share(hits, of)
    }
}

/// The dense id of each row's value of one column, and how many there are.
pub(crate) fn dense_column(t: &TableAt<'_>, column: usize) -> (Vec<u32>, u32) {
    let mut ids = Vec::with_capacity(t.rows);
    let kind = t.kinds[column];
    // A column of small values reads an array, and any other column a hash.
    if matches!(kind, Kind::Color | Kind::Dir | Kind::DiagDir | Kind::Dir8 | Kind::Axis | Kind::DiagAxis | Kind::Axis4 | Kind::D4 | Kind::C4) {
        let mut seen = [u32::MAX; 32];
        let mut next = 0;
        for row in 0..t.rows {
            let value = (t.at(row, column)[0] & 31) as usize;
            if seen[value] == u32::MAX {
                seen[value] = next;
                next += 1;
            }
            ids.push(seen[value]);
        }
        return (ids, next);
    }
    let mut seen: crate::lookup::LookupMap<Cell, u32> = crate::lookup::LookupMap::with_capacity(t.rows.min(256));
    for row in 0..t.rows {
        let next = seen.len() as u32;
        ids.push(*seen.entry(t.at(row, column)).or_insert(next));
    }
    let count = seen.len() as u32;
    (ids, count)
}

/// A dense id per row over several dense columns.
pub(crate) fn dense_over(columns: &[&[u32]], rows: usize) -> (Vec<u32>, u32) {
    let mut ids = vec![0u32; rows];
    let mut count = 1u32;
    for column in columns {
        let mut seen: crate::lookup::LookupMap<u64, u32> = crate::lookup::LookupMap::with_capacity(rows.min(256));
        for row in 0..rows {
            let key = u64::from(ids[row]) << 32 | u64::from(column[row]);
            let next = seen.len() as u32;
            ids[row] = *seen.entry(key).or_insert(next);
        }
        count = seen.len() as u32;
    }
    (ids, count)
}

/// `is_function`: whether each source id has one target, over the rows that `each` gives.
#[inline]
pub(crate) fn is_function(sources: u32, pairs: impl Iterator<Item = (u32, u8)>) -> bool {
    let mut first = vec![255u8; sources as usize];
    for (source, target) in pairs {
        let held = &mut first[source as usize];
        if *held == 255 {
            *held = target;
        } else if *held != target {
            return false;
        }
    }
    true
}

pub(crate) const MEASURES: usize = 8;
pub(crate) const ROWS_VS: [&str; MEASURES] = ["rows vs the output area", "rows vs the longer side of the output", "rows vs the shorter side of the output", "rows vs the output color count", "rows vs the output foreground count", "rows vs the output foreground component count", "rows vs the changed cell count", "rows vs the changed component count"];
pub(crate) const MAX_VS: [&str; MEASURES] = ["C max vs the output area", "C max vs the longer side of the output", "C max vs the shorter side of the output", "C max vs the output color count", "C max vs the output foreground count", "C max vs the output foreground component count", "C max vs the changed cell count", "C max vs the changed component count"];
pub(crate) const INCLUDES: [&str; MEASURES] = ["C includes the output area", "C includes the longer side of the output", "C includes the shorter side of the output", "C includes the output color count", "C includes the output foreground count", "C includes the output foreground component count", "C includes the changed cell count", "C includes the changed component count"];
pub(crate) const DISTINCT_VS: [&str; MEASURES] = ["C distinct vs the output area", "C distinct vs the longer side of the output", "C distinct vs the shorter side of the output", "C distinct vs the output color count", "C distinct vs the output foreground count", "C distinct vs the output foreground component count", "C distinct vs the changed cell count", "C distinct vs the changed component count"];

/// What a pass reads of one table at one pair, once per column.
pub(crate) struct View<'a> {
    pub t: &'a TableAt<'a>,
    pub f: &'a PairFacts,
    pub dense: Vec<(Vec<u32>, u32)>,
    pub out: &'a mut Vec<Record>,
}

impl View<'_> {
    #[inline]
    pub(crate) fn put(&mut self, kind: &'static str, holes: &[usize], value: Value) {
        let mut held = [NONE; 3];
        for (slot, hole) in held.iter_mut().zip(holes) {
            *slot = *hole as u8;
        }
        self.out.push(Record { kind, holes: held, value });
    }
}

/// The value of every kind at every binding, on one table at one pair.
pub fn pass(t: &TableAt<'_>, f: &PairFacts, out: &mut Vec<Record>) {
    let rows = t.rows;
    let columns = t.kinds.len();
    let mut view = View { t, f, dense: Vec::new(), out };
    for (m, name) in ROWS_VS.iter().enumerate() {
        if let Some(value) = f.measures[m] {
            view.put(name, &[], Value::Word(compare(rows as i64, value)));
        }
    }
    if rows == 0 {
        return;
    }
    view.dense = (0..columns).map(|column| dense_column(t, column)).collect();
    for column in 0..columns {
        let kind = t.kinds[column];
        if kind.is_number() {
            number_column(&mut view, column);
        } else if kind == Kind::Ident {
            ident_column(&mut view, column);
        } else if kind == Kind::Color {
            color_column(&mut view, column);
        } else if kind.is_line() {
            crate::catalog_orient::line_column(&mut view, column);
        } else if matches!(kind, Kind::D4 | Kind::C4) {
            crate::catalog_orient::turn_column(&mut view, column);
        } else if kind == Kind::Offset {
            crate::catalog_orient::offset_column(&mut view, column);
        } else if kind == Kind::Box {
            crate::catalog_boxes::box_column(&mut view, column);
        }
    }
    crate::catalog_cells::position_columns(&mut view);
}

/// The kinds that read the input alone, which no kind over the output stands for.
pub fn pass_input(t: &TableAt<'_>, f: &PairFacts, out: &mut Vec<Record>) {
    if t.rows == 0 {
        return;
    }
    let mut view = View { t, f, dense: Vec::new(), out };
    for column in 0..t.kinds.len() {
        let kind = t.kinds[column];
        if kind.is_number() {
            input_numbers(&mut view, column);
        } else if kind.is_line() {
            crate::catalog_orient::input_lines(&mut view, column);
        } else if matches!(kind, Kind::D4 | Kind::C4) {
            crate::catalog_orient::input_turns(&mut view, column);
        } else if matches!(kind, Kind::Position | Kind::Box) {
            crate::catalog_boxes::input_frames(&mut view, column);
            if kind == Kind::Box {
                crate::catalog_boxes::input_borders(&mut view, column);
            }
        }
    }
}

/// A number column against the input's counts.
fn input_numbers(view: &mut View<'_>, n: usize) {
    let t = view.t;
    let g = &view.f.input;
    let mut values: Vec<i64> = (0..t.rows).map(|row| i64::from(t.at(row, n)[0])).collect();
    values.sort_unstable();
    values.dedup();
    let has = |count: i64| values.binary_search(&count).is_ok();
    let full_lines = g.line_colors[0].iter().chain(&g.line_colors[1]).filter(|mask| mask.count_ones() == 1).count() as i64;
    view.put("C includes the input full line count", &[n], Value::Bool(has(full_lines)));
    view.put("C includes the input one-color component count", &[n], Value::Bool(has(g.pieces.len() as i64)));
    view.put("C includes the count of some input color", &[n], Value::Bool(g.counts.iter().any(|count| *count > 0 && has(i64::from(*count)))));
    if g.foreground.is_some() {
        let largest = g.foreground_parts.iter().map(|part| i64::from(part.count())).max().unwrap_or(0);
        view.put("C includes the largest input foreground component", &[n], Value::Bool(has(largest)));
    }
}

fn number_column(view: &mut View<'_>, n: usize) {
    let t = view.t;
    let f = view.f;
    let mut most = i64::MIN;
    let mut values: Vec<i64> = Vec::with_capacity(t.rows.min(64));
    for row in 0..t.rows {
        let value = i64::from(t.at(row, n)[0]);
        most = most.max(value);
        values.push(value);
    }
    values.sort_unstable();
    values.dedup();
    for m in 0..MEASURES {
        if let Some(measure) = f.measures[m] {
            view.put(MAX_VS[m], &[n], Value::Word(compare(most, measure)));
            if values.len() > 1 {
                view.put(INCLUDES[m], &[n], Value::Bool(values.binary_search(&measure).is_ok()));
            }
        }
    }
    // The positive values, against the output's periods and the two grids' sides.
    if values.iter().any(|value| *value > 0) {
        let positive: Vec<i64> = values.iter().copied().filter(|value| *value > 0).collect();
        let of = positive.len() as u32;
        let periods = positive.iter().filter(|value| **value < 32 && f.output.periods >> **value & 1 == 1).count() as u32;
        view.put("C is a period of the output, proportion", &[n], share(periods, of));
        let (hi, wi, ho, wo) = (f.input.h as i64, f.input.w as i64, f.output.h as i64, f.output.w as i64);
        let ratios = positive.iter().filter(|y| ho == *y * hi || wo == *y * wi || hi == *y * ho || wi == *y * wo).count() as u32;
        view.put("C is the ratio of an output side to the input side, proportion", &[n], share(ratios, of));
        let big: Vec<i64> = positive.iter().copied().filter(|value| (2..=30).contains(value)).collect();
        if !big.is_empty() {
            let scaled = |k: i64| -> bool {
                let k = k as usize;
                f.output.h == f.input.h * k && f.output.w == f.input.w * k && (0..f.output.h).all(|r| (0..f.output.w).all(|c| f.output.at(r, c) == f.input.at(r / k, c / k)))
            };
            let hits = big.iter().filter(|k| scaled(**k)).count() as u32;
            view.put("C scales the input to the output, proportion", &[n], share(hits, big.len() as u32));
        }
    }
}

fn ident_column(view: &mut View<'_>, g: usize) {
    let f = view.f;
    let distinct = i64::from(view.dense[g].1);
    for m in 0..MEASURES {
        if let Some(measure) = f.measures[m] {
            view.put(DISTINCT_VS[m], &[g], Value::Word(compare(distinct, measure)));
        }
    }
}

/// How two color sets stand to each other.
#[inline]
fn colors_relation(a: u16, b: u16) -> &'static str {
    set_relation(a & !b != 0, b & !a != 0, a & b != 0)
}

fn color_cells(grid: &GridFacts, mask: u16) -> Bits {
    let mut out = Bits::EMPTY;
    for col in 0..10 {
        if mask >> col & 1 == 1 {
            out = out.or(&grid.by_color[col]);
        }
    }
    out
}

fn cells_relation(f: &PairFacts, cells: &Bits, other: &Bits, universe: &Bits) -> &'static str {
    set_relation_in(!cells.within(other), !other.within(cells), cells.intersects(other), cells.or(other) != *universe)
}

const COLOR_ROLE_NAMES: [&str; COLOR_ROLES] = [
    "C colors that fill whole lines in the output, proportion",
    "C colors that are single cells in the output, proportion",
    "C colors of one component in the output, proportion",
    "C colors that touch every edge in the output, proportion",
    "C colors that touch no edge in the output, proportion",
    "C colors that enclose another color in the output, proportion",
    "C colors enclosed by another color in the output, proportion",
    "C colors that fill their boxes in the output, proportion",
    "C colors of the largest foreground component in the output, proportion",
    "C colors with the most components in the output, proportion",
    "C colors with a symmetric cell set in the output, proportion",
];

fn color_column(view: &mut View<'_>, x: usize) {
    let t = view.t;
    let f = view.f;
    let output = &f.output;
    let input = &f.input;
    let mut mask = 0u16;
    for row in 0..t.rows {
        let value = t.at(row, x)[0];
        if (0..10).contains(&value) {
            mask |= 1 << value;
        }
    }
    let distinct = i64::from(view.dense[x].1);
    for m in [1usize, 2, 3, 0] {
        if let Some(measure) = f.measures[m] {
            view.put(DISTINCT_VS[m], &[x], Value::Word(compare(distinct, measure)));
        }
    }
    if output.rows_one_color || output.columns_one_color {
        view.put("C is the set of output line colors", &[x], Value::Bool(mask == output.colors));
    }
    let present: Vec<u32> = (0..10).filter(|col| output.counts[*col] > 0).map(|col| output.counts[col]).collect();
    let most = present.iter().copied().max().unwrap_or(0);
    let least = present.iter().copied().min().unwrap_or(0);
    let has = |want: u32| (0..10).any(|col| mask >> col & 1 == 1 && output.counts[col] == want && output.counts[col] > 0);
    view.put("C includes the most frequent output color", &[x], Value::Bool(has(most)));
    view.put("C includes the least frequent output color", &[x], Value::Bool(has(least)));
    let out_cells = color_cells(output, mask);
    let in_cells = color_cells(input, mask);
    view.put("C covers the output, proportion", &[x], Value::Share(out_cells.count(), (output.h * output.w) as u32));
    let out_parts = i64::from(part_count(&out_cells, output.h, output.w));
    let in_parts = i64::from(part_count(&in_cells, input.h, input.w));
    view.put("C output cell components", &[x], Value::Num(out_parts));
    view.put("C output cell components vs the input", &[x], Value::Word(compare(out_parts, in_parts)));
    let added = output.colors & !input.colors;
    let dropped = input.colors & !output.colors;
    if added != 0 {
        view.put("C vs the colors the output adds", &[x], Value::Word(colors_relation(mask, added)));
    }
    if dropped != 0 {
        view.put("C vs the colors the output drops", &[x], Value::Word(colors_relation(mask, dropped)));
    }
    let mut signs = [false; 3];
    for col in 0..10 {
        if mask >> col & 1 == 1 {
            let at = match output.counts[col].cmp(&input.counts[col]) {
                std::cmp::Ordering::Less => 0,
                std::cmp::Ordering::Equal => 1,
                std::cmp::Ordering::Greater => 2,
            };
            signs[at] = true;
        }
    }
    let held = signs.iter().filter(|sign| **sign).count();
    if held == 1 {
        view.put("C output count vs the input count", &[x], Value::Word(["<", "=", ">"][signs.iter().position(|sign| *sign).unwrap_or(0)]));
    } else if held > 1 {
        view.put("C output count vs the input count", &[x], Value::Word("mixed"));
    }
    if f.changed_from != 0 {
        view.put("C vs the colors the changed cells had", &[x], Value::Word(colors_relation(mask, f.changed_from)));
        view.put("C vs the colors the changed cells take", &[x], Value::Word(colors_relation(mask, f.changed_to)));
        view.put("C is the set of the colors the changed cells take", &[x], Value::Bool(mask == f.changed_to));
        view.put("C input cells vs the changed cells", &[x], Value::Word(cells_relation(f, &in_cells, &f.changed, &output.all)));
        view.put("C output cells vs the changed cells", &[x], Value::Word(cells_relation(f, &out_cells, &f.changed, &output.all)));
    }
    let mut per_value = [0u32; 10];
    for row in 0..t.rows {
        let value = t.at(row, x)[0];
        if (0..10).contains(&value) {
            per_value[value as usize] += 1;
        }
    }
    let colors_held = mask.count_ones();
    let agree = (0..10).filter(|col| mask >> col & 1 == 1 && per_value[*col] == output.counts[*col]).count() as u32;
    view.put("C rows per value agree with the output color counts, proportion", &[x], share(agree, colors_held));
    view.put("C within the output colors", &[x], Value::Bool(mask & !output.colors == 0));
    view.put("C vs the output colors", &[x], Value::Word(colors_relation(mask, output.colors)));
    let in_output = mask & output.colors;
    if in_output != 0 && t.rows <= 5000 {
        for (role, name) in COLOR_ROLE_NAMES.iter().enumerate() {
            view.put(name, &[x], Value::Share((in_output & output.color_roles[role]).count_ones(), in_output.count_ones()));
        }
    }
    // Pairs of this color column with a number or an Ident column.
    for other in 0..t.kinds.len() {
        if other == x {
            continue;
        }
        if t.kinds[other] == Kind::Color && t.rows <= 5000 && f.same {
            let mut table = [255u8; 10];
            let mut function = true;
            for row in 0..t.rows {
                let (from, to) = (t.at(row, x)[0], t.at(row, other)[0]);
                if (0..10).contains(&from) {
                    let held = &mut table[from as usize];
                    if *held == 255 {
                        *held = to as u8;
                    } else if i32::from(*held) != to {
                        function = false;
                    }
                }
            }
            if function {
                let (mut hits, mut of, mut gives) = (0u32, 0u32, true);
                for at in 0..output.h * output.w {
                    let (from, to) = (input.color[at], output.color[at]);
                    let mapped = table[from as usize];
                    if mapped != 255 {
                        of += 1;
                        hits += u32::from(mapped == to);
                    }
                    gives &= (if mapped == 255 { from } else { mapped }) == to;
                }
                if of > 0 {
                    view.put("C,C maps the input colors to the output, proportion", &[x, other], Value::Share(hits, of));
                }
                view.put("C,C maps the input onto the output", &[x, other], Value::Bool(gives));
            }
        }
        if t.kinds[other].is_number() {
            color_and_number(view, x, other);
        } else if t.kinds[other] == Kind::Ident {
            let mut seen: Vec<(i32, i32)> = (0..t.rows).map(|row| (t.at(row, x)[0], t.at(row, other)[0])).collect();
            seen.sort_unstable();
            seen.dedup();
            let mut hits = 0;
            let mut held = 0;
            let mut at = 0;
            while at < seen.len() {
                let col = seen[at].0;
                let start = at;
                while at < seen.len() && seen[at].0 == col {
                    at += 1;
                }
                held += 1;
                let count = if (0..10).contains(&col) { output.counts[col as usize] } else { 0 };
                hits += u32::from((at - start) as u32 == count);
            }
            view.put("C,C groups per color are the output counts, proportion", &[x, other], share(hits, held));
        }
    }
}

fn color_and_number(view: &mut View<'_>, x: usize, n: usize) {
    let t = view.t;
    let output = &view.f.output;
    let mut pairs: Vec<(i32, i32)> = (0..t.rows).map(|row| (t.at(row, x)[0], t.at(row, n)[0])).collect();
    pairs.sort_unstable();
    pairs.dedup();
    let count = |col: i32| if (0..10).contains(&col) { output.counts[col as usize] as i32 } else { 0 };
    let hits = pairs.iter().filter(|(col, value)| *value == count(*col)).count() as u32;
    view.put("C,C is the output count of the color, proportion", &[x, n], share(hits, pairs.len() as u32));
    let values: crate::lookup::LookupSet<i32> = pairs.iter().map(|pair| pair.1).collect();
    let colors: crate::lookup::LookupSet<i32> = pairs.iter().map(|pair| pair.0).collect();
    if values.len() > 1 && colors.len() > 1 {
        let mut ordered: Vec<(i32, i32)> = pairs.iter().map(|(col, value)| (*value, count(*col))).collect();
        ordered.sort_unstable();
        ordered.dedup();
        let ties_equal = ordered.windows(2).all(|pair| pair[0].0 != pair[1].0 || pair[0].1 == pair[1].1);
        let up = ties_equal && ordered.windows(2).all(|pair| pair[0].0 == pair[1].0 || pair[0].1 <= pair[1].1);
        let down = ties_equal && ordered.windows(2).all(|pair| pair[0].0 == pair[1].0 || pair[0].1 >= pair[1].1);
        view.put("C,C output count as it rises", &[x, n], Value::Word(if up { "rises" } else if down { "falls" } else { "neither" }));
    }
    // `{x},{n} orders the output lines`.
    let output_rows = line_sequence(output, true);
    let output_cols = line_sequence(output, false);
    if output_rows.is_some() || output_cols.is_some() {
        let mut by: std::collections::BTreeMap<i32, Vec<i32>> = std::collections::BTreeMap::new();
        for (col, value) in &pairs {
            by.entry(*col).or_default().push(*value);
        }
        if by.len() > 1 && by.values().all(|held| held.len() == 1) {
            let mut order: Vec<(i32, i32)> = by.iter().map(|(col, held)| (held[0], *col)).collect();
            order.sort_unstable();
            if order.windows(2).all(|pair| pair[0].0 != pair[1].0) {
                let ranked: Vec<i32> = order.iter().map(|pair| pair.1).collect();
                let back: Vec<i32> = ranked.iter().rev().copied().collect();
                let fits = |sequence: &Option<Vec<i32>>| sequence.as_ref().is_some_and(|held| {
                    let mut runs = held.clone();
                    runs.dedup();
                    runs == ranked || runs == back
                });
                view.put("C,C orders the output lines", &[x, n], Value::Bool(fits(&output_rows) || fits(&output_cols)));
            }
        }
    }
}

/// The colors along one axis of a grid on which every line holds one color.
fn line_sequence(grid: &GridFacts, along_rows: bool) -> Option<Vec<i32>> {
    if along_rows {
        grid.rows_one_color.then(|| (0..grid.h).map(|r| i32::from(grid.at(r, 0))).collect())
    } else {
        grid.columns_one_color.then(|| (0..grid.w).map(|c| i32::from(grid.at(0, c))).collect())
    }
}
