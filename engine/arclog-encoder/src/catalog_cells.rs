//! The catalog's kinds over one Position column, and over the groups of its cells.

use crate::catalog::*;
use crate::catalog_facts::*;
use crate::grid_walks::{enclosed_regions, for_each_enclosed_region, walk_outward};

pub(crate) const MAX_ROWS: usize = 5000;
pub(crate) const MAX_CELLS: usize = 900;
pub(crate) const MAX_GROUPS: u32 = 60;

/// What the kinds read of a Position column.
pub(crate) struct Pos {
    pub col: usize,
    pub in_frame: bool,
    pub frame_input: bool,
    pub frame_output: bool,
    /// The column's cells lie in a frame of the output's size.
    pub on_output: bool,
    /// Per row, the output cell at its first row and first column, where those lie in the output.
    pub at_output: Vec<i32>,
    pub at_input: Vec<i32>,
    /// Per row, the output cell where the row's value is exactly a cell of the output.
    pub cell_output: Vec<i32>,
    pub cell_input: Vec<i32>,
    pub set_output: Bits,
    pub set_input: Bits,
    /// The column's distinct (row, column) places, on the grid or off it.
    pub places: Vec<(i32, i32)>,
    pub no_negative: bool,
}

pub(crate) fn pos_of(t: &TableAt<'_>, f: &PairFacts, col: usize) -> Pos {
    let (hi, wi, ho, wo) = (f.input.h as i32, f.input.w as i32, f.output.h as i32, f.output.w as i32);
    let rows = t.rows;
    let mut at_output = Vec::with_capacity(rows);
    let mut at_input = Vec::with_capacity(rows);
    let mut cell_output = Vec::with_capacity(rows);
    let mut cell_input = Vec::with_capacity(rows);
    let (mut set_output, mut set_input) = (Bits::EMPTY, Bits::EMPTY);
    let (mut fits_input, mut fits_output) = (true, true);
    let mut implied: Option<(i32, i32)> = None;
    let mut one_extent = true;
    let mut no_negative = true;
    let mut places = Vec::with_capacity(rows);
    for row in 0..rows {
        let [top, bottom, left, right] = t.at(row, col);
        let (eh, ew) = (top + bottom + 1, left + right + 1);
        fits_input &= eh == hi && ew == wi;
        fits_output &= eh == ho && ew == wo;
        match implied {
            None => implied = Some((eh, ew)),
            Some(held) => one_extent &= held == (eh, ew),
        }
        no_negative &= top >= 0 && bottom >= 0 && left >= 0 && right >= 0;
        let in_out = top >= 0 && left >= 0 && top < ho && left < wo;
        let in_in = top >= 0 && left >= 0 && top < hi && left < wi;
        let out_at = if in_out { top * wo + left } else { -1 };
        let in_at = if in_in { top * wi + left } else { -1 };
        at_output.push(out_at);
        at_input.push(in_at);
        let whole = top >= 0 && bottom >= 0 && left >= 0 && right >= 0;
        cell_output.push(if whole && eh == ho && ew == wo { out_at } else { -1 });
        cell_input.push(if whole && eh == hi && ew == wi { in_at } else { -1 });
        if out_at >= 0 {
            set_output.set(out_at as usize);
        }
        if in_at >= 0 {
            set_input.set(in_at as usize);
        }
        places.push((top, left));
    }
    places.sort_unstable();
    places.dedup();
    let own = !fits_input && !fits_output && one_extent && no_negative;
    let in_frame = fits_input || fits_output || own;
    let on_output = (fits_input && f.same) || (fits_output && !fits_input) || (fits_input && (hi, wi) == (ho, wo));
    Pos { col, in_frame, frame_input: fits_input, frame_output: fits_output && !fits_input, on_output, at_output, at_input, cell_output, cell_input, set_output, set_input, places, no_negative }
}

/// A cell set with each cell's eight neighbors, in a grid.
pub(crate) fn dilated(cells: &Bits, h: usize, w: usize) -> Bits {
    let mut out = Bits::EMPTY;
    cells.each(|at| {
        let (r, c) = (at / w, at % w);
        for nr in r.saturating_sub(1)..(r + 2).min(h) {
            for nc in c.saturating_sub(1)..(c + 2).min(w) {
                out.set(nr * w + nc);
            }
        }
    });
    out
}

/// The cells outside a nonempty cell set that it encloses, on the grid.
fn holes(cells: &Bits, all: &Bits, h: usize, w: usize) -> Bits {
    let free = all.minus(cells);
    let mut out = Bits::EMPTY;
    for_each_enclosed_region((0..h * w).map(|at| !free.get(at)).collect(), h, w, |region| {
        for at in region {
            out.set(*at);
        }
    });
    out
}

/// The rows and the columns that hold a cell of the set, each as a mask with a bit per line.
fn occupied_rows_and_columns(cells: &Bits, w: usize) -> (u32, u32) {
    let (mut rows, mut cols) = (0u32, 0u32);
    cells.each(|at| {
        rows |= 1 << (at / w);
        cols |= 1 << (at % w);
    });
    (rows, cols)
}

fn cell_list(cells: &Bits, w: usize) -> Vec<(u8, u8)> {
    let mut out = Vec::with_capacity(cells.count() as usize);
    cells.each(|at| out.push(((at / w) as u8, (at % w) as u8)));
    out
}

/// The fewest eight-neighbor steps from a nonempty cell set to each cell.
fn distances(cells: &Bits, h: usize, w: usize) -> Vec<u16> {
    let mut out = vec![u16::MAX; h * w];
    let mut start = Vec::new();
    cells.each(|at| {
        out[at] = 0;
        start.push(at);
    });
    walk_outward(start, h, w, true, |at, steps| {
        out[at] = steps;
        false
    });
    out
}

const ROLE_NAMES: [&str; CELL_ROLES] = [
    "C cells on the boundary of their component in the output, proportion",
    "C cells at a corner of the box of their component in the output, proportion",
    "C cells at the center of the box of their component in the output, proportion",
    "C cells at a tip of their component in the output, proportion",
    "C cells in a component of one cell in the output, proportion",
    "C cells on a full line of one color in the output, proportion",
    "C cells on the grid edge in the output, proportion",
    "C cells at a grid corner in the output, proportion",
    "C cells of the background next to the foreground in the output, proportion",
    "C cells of the background enclosed by the foreground in the output, proportion",
    "C cells at a crossing of two lines in the output, proportion",
    "C cells of the background between the foreground on a line in the output, proportion",
    "C cells that break the grid's periods in the output, proportion",
];
const NEEDS_BACKGROUND: [usize; 4] = [ROLE_NEXT, ROLE_ENCLOSED, ROLE_CROSSING, ROLE_BETWEEN];

/// The kinds of every Position column, with its pairs with the other columns.
pub(crate) fn position_columns(view: &mut View<'_>) {
    let t = view.t;
    let f = view.f;
    // The groups: by the table's Ident, Color and key columns.
    let group_columns: Vec<usize> = (0..t.kinds.len()).filter(|c| matches!(t.kinds[*c], Kind::Ident | Kind::Color) || t.keys[*c]).collect();
    let (group_of, groups) = if group_columns.is_empty() {
        (Vec::new(), 0)
    } else {
        let parts: Vec<&[u32]> = group_columns.iter().map(|c| view.dense[*c].0.as_slice()).collect();
        dense_over(&parts, t.rows)
    };
    for col in 0..t.kinds.len() {
        if t.kinds[col] != Kind::Position {
            continue;
        }
        let pos = pos_of(t, f, col);
        if t.rows <= MAX_ROWS {
            one_column(view, &pos, &group_of, groups);
            crate::catalog_pairs::pairs_of(view, &pos, &group_of, groups);
        }
        let _ = f;
    }
}

fn one_column(view: &mut View<'_>, pos: &Pos, group_of: &[u32], groups: u32) {
    let t = view.t;
    let f = view.f;
    let output = &f.output;
    let input = &f.input;
    let col = pos.col;
    let (h, w) = (output.h, output.w);
    let holds = |view: &mut View<'_>, kind: &'static str, value: Value| view.put(kind, &[col], value);
    let s = pos.set_output;
    let on = pos.on_output && !s.is_empty();
    if on {
        let mut mask = 0u16;
        let mut under = [0u32; 10];
        s.each(|at| {
            let color = output.color[at] as usize;
            mask |= 1 << color;
            under[color] += 1;
        });
        holds(view, "C output colors distinct", Value::Num(i64::from(mask.count_ones())));
        holds(view, "C is a union of output colors", Value::Bool((0..10).all(|c| mask >> c & 1 == 0 || under[c] == output.counts[c])));
        let around = dilated(&s, h, w);
        let outer = around.minus(&s);
        if !outer.is_empty() {
            let mut colors = 0u16;
            outer.each(|at| colors |= 1 << output.color[at]);
            holds(view, "C outer boundary output colors distinct", Value::Num(i64::from(colors.count_ones())));
        }
        if !f.changed.is_empty() {
            let of = f.changed.count();
            holds(view, "C changed cells within Chebyshev distance 1, proportion", Value::Share(f.changed.and(&around).count(), of));
            let (rows, cols) = occupied_rows_and_columns(&s, w);
            let (changed_rows, changed_cols) = occupied_rows_and_columns(&f.changed, w);
            let mut on_lines = 0;
            f.changed.each(|at| on_lines += u32::from(rows >> (at / w) & 1 == 1 || cols >> (at % w) & 1 == 1));
            holds(view, "C changed cells on its rows or columns, proportion", Value::Share(on_lines, of));
            let mut with = 0;
            s.each(|at| with += u32::from(changed_rows >> (at / w) & 1 == 1 || changed_cols >> (at % w) & 1 == 1));
            holds(view, "C cells with a changed cell on their rows or columns, proportion", Value::Share(with, s.count()));
            if let Some(span) = span_of(&s, w) {
                let mut inside = 0;
                f.changed.each(|at| {
                    let (r, c) = ((at / w) as u8, (at % w) as u8);
                    inside += u32::from(span[0] <= r && r <= span[1] && span[2] <= c && c <= span[3]);
                });
                holds(view, "C changed cells inside its bounding box, proportion", Value::Share(inside, of));
            }
            let mut spans = vec![(i32::MAX, i32::MIN); 2 * (h + w + h + w)];
            let slot = |which: usize, key: i32| -> usize {
                match which {
                    0 => key as usize,
                    1 => h + key as usize,
                    2 => h + w + (key + w as i32 - 1) as usize,
                    _ => 2 * h + 2 * w + key as usize,
                }
            };
            s.each(|at| {
                let (r, c) = ((at / w) as i32, (at % w) as i32);
                for (which, key, place) in [(0, r, c), (1, c, r), (2, r - c, r), (3, r + c, r)] {
                    let held = &mut spans[slot(which, key)];
                    *held = (held.0.min(place), held.1.max(place));
                }
            });
            let between = |which: usize, key: i32, place: i32| {
                let held = spans[slot(which, key)];
                held.0 < place && place < held.1
            };
            let (mut straight, mut diagonal) = (0, 0);
            f.changed.each(|at| {
                let (r, c) = ((at / w) as i32, (at % w) as i32);
                straight += u32::from(between(0, r, c) || between(1, c, r));
                diagonal += u32::from(between(2, r - c, r) || between(3, r + c, r));
            });
            holds(view, "C changed cells between two of its cells on a line, proportion", Value::Share(straight, of));
            holds(view, "C changed cells between two of its cells on a diagonal, proportion", Value::Share(diagonal, of));
            holds(view, "C changed cells in its holes, proportion", Value::Share(f.changed.and(&holes(&s, &output.all, h, w)).count(), of));
            let away = distances(&s, h, w);
            let mut most = 0;
            f.changed.each(|at| most = most.max(away[at]));
            holds(view, "C greatest distance from a changed cell", Value::Num(i64::from(most)));
        }
        for (role, name) in ROLE_NAMES.iter().enumerate() {
            if output.background.is_none() && NEEDS_BACKGROUND.contains(&role) {
                continue;
            }
            holds(view, name, Value::Share(s.and(&output.roles[role]).count(), s.count()));
        }
        let mut union = true;
        s.each(|at| union &= output.pieces[output.piece_of[at] as usize].cells.within(&s));
        holds(view, "C is a union of components in the output", Value::Bool(union));
        if f.same {
            let mut moved = Bits::EMPTY;
            s.each(|at| {
                if f.changed.get(at) {
                    moved.set(at);
                }
            });
            if !moved.is_empty() {
                let of = moved.count();
                let (mut lines, mut diagonals) = (0, 0);
                moved.each(|at| {
                    let (r, c) = (at / w, at % w);
                    let bit = 1u16 << output.color[at];
                    lines += u32::from(input.line_colors[0][r] & bit != 0 || input.line_colors[1][c] & bit != 0);
                    diagonals += u32::from(input.line_colors[2][r + w - 1 - c] & bit != 0 || input.line_colors[3][r + c] & bit != 0);
                });
                holds(view, "C changed cells whose output color lies on their row or column in the input, proportion", Value::Share(lines, of));
                holds(view, "C changed cells whose output color lies on their diagonals in the input, proportion", Value::Share(diagonals, of));
            }
        }
    }
    if pos.on_output && !pos.places.is_empty() && pos.places.len() as u32 == s.count() {
        alternating_runs(view, pos);
    }
    if on && f.same {
        reflection_across_line(view, pos);
    }
    if groups > 0 && on {
        group_kinds(view, pos, group_of, groups);
    }
    group_properties(view, pos, group_of, groups);
    determined_cells(view, pos);
    column_cells(view, pos, group_of, groups);
}

/// `straight_runs`: the longest straight runs of at least three cells, and their colors.
fn alternating_runs(view: &mut View<'_>, pos: &Pos) {
    let output = &view.f.output;
    let s = pos.set_output;
    let (h, w) = (output.h, output.w);
    let (mut hits, mut of) = (0u32, 0u32);
    for (dr, dc) in [(0usize, 1usize), (1, 0)] {
        s.each(|at| {
            let (r, c) = (at / w, at % w);
            let before = (dr == 1 && r > 0 && s.get(at - w)) || (dc == 1 && c > 0 && s.get(at - 1));
            if before {
                return;
            }
            let mut run = vec![output.color[at]];
            let (mut y, mut z) = (r + dr, c + dc);
            while y < h && z < w && s.get(y * w + z) {
                run.push(output.color[y * w + z]);
                y += dr;
                z += dc;
            }
            if run.len() > 2 {
                of += 1;
                hits += u32::from(run[0] != run[1] && run.iter().enumerate().all(|(i, x)| *x == run[i % 2]));
            }
        });
    }
    if of > 0 {
        view.put("C runs that alternate two colors in the output, proportion", &[pos.col], Value::Share(hits, of));
    }
}

/// A column on one line: the input's foreground reflected across it, against the output.
fn reflection_across_line(view: &mut View<'_>, pos: &Pos) {
    let f = view.f;
    let (output, input) = (&f.output, &f.input);
    let Some(foreground) = &input.foreground else { return };
    let s = pos.set_output;
    if foreground.is_empty() || s.count() < 2 {
        return;
    }
    let w = output.w;
    let (rows, cols) = occupied_rows_and_columns(&s, w);
    let (one_row, one_col) = (rows.count_ones() == 1, cols.count_ones() == 1);
    if !one_row && !one_col {
        return;
    }
    let line = if one_row { rows.trailing_zeros() as i32 } else { cols.trailing_zeros() as i32 };
    let (h, wi) = (output.h as i32, w as i32);
    let (mut hits, mut of) = (0u32, 0u32);
    foreground.each(|at| {
        let (r, c) = ((at / w) as i32, (at % w) as i32);
        let (y, z) = if one_row { (2 * line - r, c) } else { (r, 2 * line - c) };
        if y >= 0 && z >= 0 && y < h && z < wi && (y, z) != (r, c) {
            of += 1;
            hits += u32::from(output.color[(y * wi + z) as usize] == input.color[at]);
        }
    });
    if of > 0 {
        view.put("C reflection across it maps the input onto the output, proportion", &[pos.col], Value::Share(hits, of));
    }
}

/// The kinds that read a function from a cell's place or neighborhood to its output color.
fn determined_cells(view: &mut View<'_>, pos: &Pos) {
    let f = view.f;
    let output = &f.output;
    let input = &f.input;
    let col = pos.col;
    let (h, w) = (output.h, output.w);
    let mut cells = Bits::EMPTY;
    for at in &pos.cell_output {
        if *at >= 0 {
            cells.set(*at as usize);
        }
    }
    let count = cells.count();
    let lying = pos.cell_output.iter().filter(|at| **at >= 0).count();
    if f.same && lying >= 2 {
        let color = |at: usize| output.color[at];
        let moore = is_function((h * w) as u32, pos.cell_output.iter().filter(|at| **at >= 0).map(|at| (input.moore[*at as usize], color(*at as usize))));
        view.put("C its Moore neighborhood determines the output color", &[col], Value::Bool(moore));
    }
    if count < 2 {
        return;
    }
    let list: Vec<usize> = {
        let mut out = Vec::with_capacity(count as usize);
        cells.each(|at| out.push(at));
        out
    };
    let color = |at: usize| output.color[at];
    let by = |source: &dyn Fn(usize) -> u32, sources: u32| is_function(sources, list.iter().map(|at| (source(*at), color(*at))));
    let rows = by(&|at| (at / w) as u32, h as u32);
    let columns = by(&|at| (at % w) as u32, w as u32);
    view.put("C its row or column determines the output color", &[col], Value::Bool(rows || columns));
    let down = by(&|at| (at / w + w - 1 - at % w) as u32, (h + w) as u32);
    let up = by(&|at| (at / w + at % w) as u32, (h + w) as u32);
    view.put("C its diagonal determines the output color", &[col], Value::Bool(down || up));
    let border = by(&|at| {
        let (r, c) = (at / w, at % w);
        r.min(h - 1 - r).min(c).min(w - 1 - c) as u32
    }, (h + w) as u32);
    view.put("C its distance from the grid border determines the output color", &[col], Value::Bool(border));
    let parity = by(&|at| ((at / w + at % w) % 2) as u32, 2);
    view.put("C its coordinate parity determines the output color", &[col], Value::Bool(parity));
    if f.same {
        let multiset = by(&|at| input.neighbor_colors[at], (h * w) as u32);
        view.put("C its neighbor colors determines the output color", &[col], Value::Bool(multiset));
        let same = by(&|at| u32::from(input.color[at]) * 9 + u32::from(input.same_neighbors[at]), 99);
        view.put("C its color and its same-color neighbor count determines the output color", &[col], Value::Bool(same));
    }
    // `its row or column parity`: one color at the odd lines and another at the even lines.
    if pos.on_output && pos.set_output == cells && pos.places.len() as u32 == count && count > 3 {
        let split = |line: &dyn Fn(usize) -> usize| {
            let (mut even, mut odd) = (0u16, 0u16);
            for at in &list {
                if line(*at) % 2 == 0 {
                    even |= 1 << color(*at);
                } else {
                    odd |= 1 << color(*at);
                }
            }
            even.count_ones() == 1 && odd.count_ones() == 1 && even != odd
        };
        view.put("C its row or column parity determines the output color", &[col], Value::Bool(split(&|at| at / w) || split(&|at| at % w)));
    }
}

/// A group's cells in the output, and the kinds over them.
fn group_kinds(view: &mut View<'_>, pos: &Pos, group_of: &[u32], groups: u32) {
    let t = view.t;
    let f = view.f;
    let output = &f.output;
    let input = &f.input;
    let col = pos.col;
    let (h, w) = (output.h, output.w);
    let count = groups as usize;
    let mut masks = vec![0u16; count];
    for row in 0..t.rows {
        let at = pos.at_output[row];
        if at >= 0 {
            masks[group_of[row] as usize] |= 1 << output.color[at as usize];
        }
    }
    let held: Vec<u16> = masks.iter().copied().filter(|mask| *mask != 0).collect();
    if held.is_empty() {
        return;
    }
    let of = held.len() as u32;
    view.put("C groups of its Ident, Color and key columns output colors per group max", &[col], Value::Num(i64::from(held.iter().map(|mask| mask.count_ones()).max().unwrap_or(0))));
    view.put("C groups of its Ident, Color and key columns with one output color, proportion", &[col], Value::Share(held.iter().filter(|mask| mask.count_ones() == 1).count() as u32, of));
    let mut sets = held.clone();
    sets.sort_unstable();
    sets.dedup();
    view.put("C groups of its Ident, Color and key columns output color sets distinct", &[col], Value::Num(sets.len() as i64));
    let mut cells: Vec<Bits> = vec![Bits::EMPTY; count];
    for row in 0..t.rows {
        let at = pos.at_output[row];
        if at >= 0 {
            cells[group_of[row] as usize].set(at as usize);
        }
    }
    if !f.changed.is_empty() {
        let (mut some, mut whole) = (0, 0);
        for cell_set in &cells {
            if !cell_set.is_empty() {
                some += u32::from(cell_set.intersects(&f.changed));
                whole += u32::from(cell_set.within(&f.changed));
            }
        }
        view.put("C groups of its Ident, Color and key columns that change, proportion", &[col], Value::Share(some, of));
        view.put("C groups of its Ident, Color and key columns that change wholly, proportion", &[col], Value::Share(whole, of));
    }
    let components = cells.iter().filter(|cell_set| !cell_set.is_empty()).filter(|cell_set| {
        let mut first = None;
        cell_set.each(|at| {
            if first.is_none() {
                first = Some(at);
            }
        });
        first.is_some_and(|at| output.pieces[output.piece_of[at] as usize].cells == **cell_set)
    }).count() as u32;
    view.put("C groups of its Ident, Color and key columns that are components in the output, proportion", &[col], Value::Share(components, of));
    if f.same {
        // Each group that holds a changed cell: what its changed cells take.
        let (mut holds, mut near, mut one, mut nearest, mut taking) = (0u32, 0u32, 0u32, 0u32, 0u32);
        let foreground = input.foreground;
        let mut near_counted = 0u32;
        for cell_set in &cells {
            let moved = cell_set.and(&f.changed);
            if moved.is_empty() {
                continue;
            }
            taking += 1;
            let mut taken = 0u16;
            moved.each(|at| taken |= 1 << output.color[at]);
            let mut own = 0u16;
            cell_set.each(|at| own |= 1 << input.color[at]);
            holds += u32::from(taken & !own == 0);
            let around = dilated(cell_set, h, w).minus(cell_set);
            let mut nearby = 0u16;
            around.each(|at| nearby |= 1 << input.color[at]);
            near += u32::from(taken & !nearby == 0);
            one += u32::from(taken.count_ones() == 1);
            if let (Some(front), true) = (&foreground, groups <= MAX_GROUPS) {
                near_counted += 1;
                nearest += u32::from(taken & !nearest_colors(cell_set, front, input, h, w) == 0);
            }
        }
        if taking > 0 {
            view.put("C groups of its Ident, Color and key columns whose changed cells take colors they hold, proportion", &[col], Value::Share(holds, taking));
            view.put("C groups of its Ident, Color and key columns whose changed cells take colors around them, proportion", &[col], Value::Share(near, taking));
            view.put("C groups of its Ident, Color and key columns whose changed cells take one color, proportion", &[col], Value::Share(one, taking));
            if near_counted > 0 {
                view.put("C groups of its Ident, Color and key columns whose changed cells take the color of the nearest foreground around them, proportion", &[col], Value::Share(nearest, near_counted));
            }
        }
    }
}

/// The properties of each group, against its one color or whether it changes.
fn group_properties(view: &mut View<'_>, pos: &Pos, group_of: &[u32], groups: u32) {
    let t = view.t;
    let f = view.f;
    let output = &f.output;
    let col = pos.col;
    let w = output.w;
    if groups == 0 || groups > MAX_GROUPS || pos.cell_output.iter().filter(|at| **at >= 0).map(|at| *at).collect::<std::collections::BTreeSet<_>>().len() < 2 {
        return;
    }
    let mut cells: Vec<Bits> = vec![Bits::EMPTY; groups as usize];
    let mut whole = vec![std::collections::BTreeSet::new(); groups as usize];
    for row in 0..t.rows {
        let at = pos.at_output[row];
        if at >= 0 {
            cells[group_of[row] as usize].set(at as usize);
        }
        let cell = t.at(row, col);
        whole[group_of[row] as usize].insert((cell[0], cell[2]));
    }
    let of = cells.iter().filter(|cell_set| !cell_set.is_empty()).count();
    let total: usize = whole.iter().map(std::collections::BTreeSet::len).sum();
    if of < 2 || total > MAX_CELLS {
        return;
    }
    // The properties of each group, against its one color or whether it changes.
    let kept: Vec<&Bits> = cells.iter().filter(|cell_set| !cell_set.is_empty()).collect();
    let lists: Vec<Vec<(u8, u8)>> = kept.iter().map(|cell_set| cell_list(cell_set, w)).collect();
    let forms: Vec<Vec<(u8, u8)>> = lists.iter().map(|list| normalized(list)).collect();
    let canons: Vec<Vec<(u8, u8)>> = lists.iter().map(|list| canon(list)).collect();
    let sizes: Vec<u32> = kept.iter().map(|cell_set| cell_set.count()).collect();
    let symmetry: Vec<u32> = lists.iter().map(|list| symmetry_count(list)).collect();
    let enclosed: Vec<u32> = lists.iter().map(|list| enclosed_regions(list)).collect();
    let edge: Vec<u32> = kept.iter().map(|cell_set| u32::from(cell_set.intersects(&output.roles[ROLE_EDGE]))).collect();
    let fills: Vec<u32> = lists.iter().map(|list| {
        let (rmin, rmax) = (list.iter().map(|x| x.0).min().unwrap_or(0), list.iter().map(|x| x.0).max().unwrap_or(0));
        let (cmin, cmax) = (list.iter().map(|x| x.1).min().unwrap_or(0), list.iter().map(|x| x.1).max().unwrap_or(0));
        u32::from(list.len() == (rmax - rmin + 1) as usize * (cmax - cmin + 1) as usize)
    }).collect();
    let dense_forms = |values: &[Vec<(u8, u8)>]| -> Vec<u32> {
        let mut seen: Vec<&Vec<(u8, u8)>> = Vec::new();
        values.iter().map(|value| match seen.iter().position(|held| *held == value) {
            Some(at) => at as u32,
            None => {
                seen.push(value);
                seen.len() as u32 - 1
            }
        }).collect()
    };
    let form_ids = dense_forms(&forms);
    let canon_ids = dense_forms(&canons);
    let unique: Vec<Option<u8>> = kept.iter().map(|cell_set| {
        let mut mask = 0u16;
        cell_set.each(|at| mask |= 1 << output.color[at]);
        (mask.count_ones() == 1).then(|| mask.trailing_zeros() as u8)
    }).collect();
    let properties: [(&[u32], &'static str, &'static str); 7] = [
        (&sizes, "C groups of its Ident, Color and key columns their size determines their output color", "C groups of its Ident, Color and key columns their size determines whether they change"),
        (&enclosed, "C groups of its Ident, Color and key columns their holes determines their output color", "C groups of its Ident, Color and key columns their holes determines whether they change"),
        (&symmetry, "C groups of its Ident, Color and key columns their symmetry determines their output color", "C groups of its Ident, Color and key columns their symmetry determines whether they change"),
        (&form_ids, "C groups of its Ident, Color and key columns their shape determines their output color", "C groups of its Ident, Color and key columns their shape determines whether they change"),
        (&canon_ids, "C groups of its Ident, Color and key columns their shape up to rotation and reflection determines their output color", "C groups of its Ident, Color and key columns their shape up to rotation and reflection determines whether they change"),
        (&edge, "C groups of its Ident, Color and key columns their touching the edge determines their output color", "C groups of its Ident, Color and key columns their touching the edge determines whether they change"),
        (&fills, "C groups of its Ident, Color and key columns their filling its box determines their output color", "C groups of its Ident, Color and key columns their filling its box determines whether they change"),
    ];
    let defined = unique.iter().all(Option::is_some);
    let changes: Vec<bool> = kept.iter().map(|cell_set| cell_set.intersects(&f.changed)).collect();
    let varied = changes.iter().any(|flag| *flag) && changes.iter().any(|flag| !*flag);
    for (values, to_color, to_change) in properties {
        if defined {
            let function = values.iter().enumerate().all(|(a, va)| values.iter().enumerate().all(|(b, vb)| va != vb || unique[a] == unique[b]));
            view.put(to_color, &[col], Value::Bool(function));
        }
        if f.same && varied {
            let function = values.iter().enumerate().all(|(a, va)| values.iter().enumerate().all(|(b, vb)| va != vb || changes[a] == changes[b]));
            view.put(to_change, &[col], Value::Bool(function));
        }
    }
}

/// The colors of the foreground cells outside a cell set that the fewest steps along rows
/// and columns reach from it.
fn nearest_colors(cells: &Bits, foreground: &Bits, input: &GridFacts, h: usize, w: usize) -> u16 {
    let mut start = Vec::new();
    cells.each(|at| start.push(at));
    let mut hit = 0u16;
    walk_outward(start, h, w, false, |at, _| {
        if foreground.get(at) {
            hit |= 1 << input.color[at];
        }
        foreground.get(at)
    });
    hit
}

/// The kinds that read a column's cells in any frame.
fn column_cells(view: &mut View<'_>, pos: &Pos, group_of: &[u32], groups: u32) {
    let f = view.f;
    let output = &f.output;
    let col = pos.col;
    if !pos.in_frame {
        return;
    }
    let cells = pos.places.len() as i64;
    if let Some(cell_set) = &output.foreground {
        view.put("C cells vs the output foreground cells", &[col], Value::Word(compare(cells, i64::from(cell_set.count()))));
        if groups > 0 {
            view.put("C groups of its Ident, Color and key columns vs the output foreground components", &[col], Value::Word(compare(i64::from(groups), output.foreground_parts.len() as i64)));
        }
    }
    let (rmin, rmax) = (pos.places.iter().map(|x| x.0).min().unwrap_or(0), pos.places.iter().map(|x| x.0).max().unwrap_or(0));
    let (cmin, cmax) = (pos.places.iter().map(|x| x.1).min().unwrap_or(0), pos.places.iter().map(|x| x.1).max().unwrap_or(0));
    view.put("C bounding box has the output size", &[col], Value::Bool(((rmax - rmin + 1) as usize, (cmax - cmin + 1) as usize) == (output.h, output.w)));
    let aligned = pos.frame_output || (pos.frame_input && f.same);
    if aligned {
        if let Some(cell_set) = &output.foreground {
            let s = pos.set_output;
            if !cell_set.is_empty() && !pos.places.is_empty() {
                if let Some(span) = span_of(cell_set, output.w) {
                    view.put("C bounding box is the output foreground box", &[col], Value::Bool([rmin, rmax, cmin, cmax] == [i32::from(span[0]), i32::from(span[1]), i32::from(span[2]), i32::from(span[3])]));
                }
            }
            view.put("C vs the output foreground", &[col], Value::Word(set_relation_in(!s.within(cell_set), !cell_set.within(&s), s.intersects(cell_set), s.or(cell_set) != output.all)));
        }
    }
    if pos.frame_input && f.same {
        let s = pos.set_input;
        view.put("C vs the changed cells", &[col], Value::Word(set_relation_in(!s.within(&f.changed), !f.changed.within(&s), s.intersects(&f.changed), s.or(&f.changed) != f.input.all)));
        let either = s.or(&f.changed).count() + pos.places.len() as u32 - s.count();
        view.put("C Jaccard index with the changed cells", &[col], if either == 0 { Value::Share(1, 1) } else { Value::Share(s.and(&f.changed).count(), either) });
    }
    if pos.no_negative && !pos.places.is_empty() {
        crate::catalog_pairs::shape_kinds(view, pos, group_of, groups);
    }
}
