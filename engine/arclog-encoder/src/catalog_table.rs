//! The catalog's kinds that read a table alone: the values of each column, the cells and the groups of a
//! Position column, the boxes of a Box column, what two columns of one row state together, and a column of
//! cells with a column of colors.

use std::collections::{BTreeMap, BTreeSet, HashMap};

use crate::catalog::*;
use crate::catalog_cells::{pos_of, Pos, MAX_ROWS};
use crate::catalog_facts::*;

type At = (i32, i32);

fn sorted_cells(cells: impl IntoIterator<Item = At>) -> Vec<At> {
    let mut out: Vec<At> = cells.into_iter().collect();
    out.sort_unstable();
    out.dedup();
    out
}

const STEPS_8: [At; 8] = [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)];
const STEPS_4: [At; 4] = [(-1, 0), (0, -1), (0, 1), (1, 0)];

/// The connected parts of a sorted set of cells.
fn parts_of(cells: &[At], diagonal: bool) -> Vec<Vec<At>> {
    let steps: &[At] = if diagonal { &STEPS_8 } else { &STEPS_4 };
    let mut seen = vec![false; cells.len()];
    let mut out = Vec::new();
    for start in 0..cells.len() {
        if seen[start] {
            continue;
        }
        seen[start] = true;
        let mut todo = vec![start];
        let mut part = Vec::new();
        while let Some(at) = todo.pop() {
            part.push(cells[at]);
            for step in steps {
                if let Ok(next) = cells.binary_search(&(cells[at].0 + step.0, cells[at].1 + step.1)) {
                    if !seen[next] {
                        seen[next] = true;
                        todo.push(next);
                    }
                }
            }
        }
        out.push(part);
    }
    out
}

fn spans(cells: &[At]) -> (i32, i32, i32, i32) {
    let mut span = (i32::MAX, i32::MIN, i32::MAX, i32::MIN);
    for (r, c) in cells {
        span = (span.0.min(*r), span.1.max(*r), span.2.min(*c), span.3.max(*c));
    }
    span
}

fn normalized(cells: &[At]) -> Vec<At> {
    let (r0, _, c0, _) = spans(cells);
    sorted_cells(cells.iter().map(|(r, c)| (r - r0, c - c0)))
}

/// The eight images of a cell set under the symmetries of the square, each normalized.
fn images(cells: &[At]) -> [Vec<At>; 8] {
    [
        normalized(cells),
        normalized(&cells.iter().map(|(r, c)| (*r, -*c)).collect::<Vec<_>>()),
        normalized(&cells.iter().map(|(r, c)| (-*r, *c)).collect::<Vec<_>>()),
        normalized(&cells.iter().map(|(r, c)| (-*r, -*c)).collect::<Vec<_>>()),
        normalized(&cells.iter().map(|(r, c)| (*c, *r)).collect::<Vec<_>>()),
        normalized(&cells.iter().map(|(r, c)| (*c, -*r)).collect::<Vec<_>>()),
        normalized(&cells.iter().map(|(r, c)| (-*c, *r)).collect::<Vec<_>>()),
        normalized(&cells.iter().map(|(r, c)| (-*c, -*r)).collect::<Vec<_>>()),
    ]
}

fn symmetric_images(cells: &[At]) -> i64 {
    let all = images(cells);
    all.iter().filter(|image| **image == all[0]).count() as i64
}

fn canonical(cells: &[At]) -> Vec<At> {
    images(cells).into_iter().min().unwrap_or_default()
}

fn fills_box(cells: &[At]) -> bool {
    let (r0, r1, c0, c1) = spans(cells);
    cells.len() as i64 == i64::from(r1 - r0 + 1) * i64::from(c1 - c0 + 1)
}

fn outlines_box(cells: &[At]) -> bool {
    let (r0, r1, c0, c1) = spans(cells);
    if r1 - r0 < 2 || c1 - c0 < 2 {
        return false;
    }
    let mut count = 0;
    for r in r0..=r1 {
        for c in c0..=c1 {
            if r == r0 || r == r1 || c == c0 || c == c1 {
                if cells.binary_search(&(r, c)).is_err() {
                    return false;
                }
                count += 1;
            }
        }
    }
    count == cells.len()
}

/// The free cells of a cell's box, one cell wider on each side, that a set encloses, as their parts.
fn free_parts(cells: &[At]) -> Vec<Vec<At>> {
    let (r0, r1, c0, c1) = spans(cells);
    let mut free = Vec::new();
    for r in r0 - 1..=r1 + 1 {
        for c in c0 - 1..=c1 + 1 {
            if cells.binary_search(&(r, c)).is_err() {
                free.push((r, c));
            }
        }
    }
    parts_of(&free, false)
}

fn enclosed_regions(cells: &[At]) -> i64 {
    free_parts(cells).len() as i64 - 1
}

/// The enclosed free cells: those no part of `free_parts` reaches from the ring around the box.
fn holes_of(cells: &[At]) -> Vec<At> {
    let (r0, r1, c0, c1) = spans(cells);
    let mut out = Vec::new();
    for part in free_parts(cells) {
        if !part.iter().any(|(r, c)| *r == r0 - 1 || *r == r1 + 1 || *c == c0 - 1 || *c == c1 + 1) {
            out.extend(part);
        }
    }
    sorted_cells(out)
}

fn straight(cells: &[At]) -> bool {
    let first = cells[0];
    cells.iter().all(|at| at.0 == first.0) || cells.iter().all(|at| at.1 == first.1) || cells.iter().all(|at| at.0 - at.1 == first.0 - first.1) || cells.iter().all(|at| at.0 + at.1 == first.0 + first.1)
}

fn full_lines(cells: &[At], h: i32, w: i32) -> i64 {
    let (mut rows, mut columns): (HashMap<i32, i32>, HashMap<i32, i32>) = (HashMap::new(), HashMap::new());
    for (r, c) in cells {
        if 0 <= *c && *c < w {
            *rows.entry(*r).or_insert(0) += 1;
        }
        if 0 <= *r && *r < h {
            *columns.entry(*c).or_insert(0) += 1;
        }
    }
    rows.values().filter(|count| **count == w).count() as i64 + columns.values().filter(|count| **count == h).count() as i64
}

fn cells_per_line_max(cells: &[At]) -> i64 {
    let (mut rows, mut columns): (HashMap<i32, i64>, HashMap<i32, i64>) = (HashMap::new(), HashMap::new());
    for (r, c) in cells {
        *rows.entry(*r).or_insert(0) += 1;
        *columns.entry(*c).or_insert(0) += 1;
    }
    rows.values().chain(columns.values()).copied().max().unwrap_or(0)
}

/// Whether the cells of an H by W frame outside a set form one 4-connected part.
fn complement_is_connected(cells: &[At], h: i32, w: i32) -> bool {
    let mut free = Vec::new();
    for r in 0..h {
        for c in 0..w {
            if cells.binary_search(&(r, c)).is_err() {
                free.push((r, c));
            }
        }
    }
    parts_of(&free, false).len() == 1
}

macro_rules! box_names {
    ($($measure:literal),* $(,)?) => {
        [$((concat!("C bounding box ", $measure), concat!("C bounding box per group of its Ident, Color and key columns ", $measure), concat!("C ", $measure))),*]
    };
}

const LEAST_MARGIN: usize = 0;
const EDGES_MAX: usize = 1;
const EDGES_MIN: usize = 2;
const CENTERED: usize = 3;
const ALIGNED: usize = 4;
const ONE_SIZE: usize = 5;
const OVERLAP: usize = 6;
const NESTED: usize = 7;
const COVER: usize = 8;
const EVEN: usize = 9;
const SHORT: usize = 10;
const LONG: usize = 11;
const SQUARE: usize = 12;
const PROPORTION: usize = 13;
const MORE: usize = 14;
const WHOLE: usize = 15;
const BOX_NAMES: [(&str, &str, &str); 16] = box_names!["least margin", "edges touched max", "edges touched min", "centered axes max", "aligned", "boxes of one size", "some boxes overlap", "nested boxes", "boxes cover the grid", "evenly spaced along an axis", "shorter side min", "longer side max", "every box is square", "proportion of the grid", "more than one cell along each axis", "is the whole grid"];

/// `box_features` of a set of boxes in an H by W frame, each as its margins (top, bottom, left, right).
fn box_values(boxes: &BTreeSet<[i32; 4]>, h: i32, w: i32) -> Vec<(usize, Value)> {
    let mut out = Vec::new();
    let sides: Vec<(i32, i32)> = boxes.iter().map(|[t, b, l, r]| (h - t - b, w - l - r)).filter(|(side_h, side_w)| *side_h > 0 && *side_w > 0).collect();
    if !boxes.is_empty() {
        out.push((LEAST_MARGIN, Value::Num(i64::from(boxes.iter().map(|at| *at.iter().min().unwrap_or(&0)).min().unwrap_or(0)))));
        let edges: Vec<i64> = boxes.iter().map(|at| at.iter().filter(|margin| **margin == 0).count() as i64).collect();
        out.push((EDGES_MAX, Value::Num(edges.iter().copied().max().unwrap_or(0))));
        out.push((EDGES_MIN, Value::Num(edges.iter().copied().min().unwrap_or(0))));
        out.push((CENTERED, Value::Num(boxes.iter().map(|[t, b, l, r]| i64::from(t == b) + i64::from(l == r)).max().unwrap_or(0))));
    }
    if boxes.len() > 1 {
        let tops: BTreeSet<(i32, i32)> = boxes.iter().map(|[t, b, _, _]| (*t, *b)).collect();
        let lefts: BTreeSet<(i32, i32)> = boxes.iter().map(|[_, _, l, r]| (*l, *r)).collect();
        out.push((ALIGNED, Value::Bool(tops.len() == 1 || lefts.len() == 1)));
        out.push((ONE_SIZE, Value::Bool(sides.iter().collect::<BTreeSet<_>>().len() == 1)));
        let boxes_at: Vec<[i32; 4]> = boxes.iter().map(|[t, b, l, r]| [*t, h - 1 - b, *l, w - 1 - r]).filter(|[r0, r1, c0, c1]| r0 <= r1 && c0 <= c1).collect();
        if boxes_at.len() <= 200 {
            let (mut overlap, mut nested) = (false, false);
            for x in &boxes_at {
                for y in &boxes_at {
                    if x != y {
                        overlap |= x[0] <= y[1] && y[0] <= x[1] && x[2] <= y[3] && y[2] <= x[3];
                        nested |= y[0] <= x[0] && x[1] <= y[1] && y[2] <= x[2] && x[3] <= y[3];
                    }
                }
            }
            out.push((OVERLAP, Value::Bool(overlap)));
            out.push((NESTED, Value::Bool(nested)));
            if h * w <= 900 {
                let mut covered = BTreeSet::new();
                for x in &boxes_at {
                    for r in x[0].max(0)..=x[1].min(h - 1) {
                        for c in x[2].max(0)..=x[3].min(w - 1) {
                            covered.insert((r, c));
                        }
                    }
                }
                out.push((COVER, Value::Bool(covered.len() as i32 == h * w)));
            }
        }
        if boxes_at.len() >= 3 {
            let mut even = false;
            for (lo, hi) in [(0, 1), (2, 3)] {
                let lines: Vec<(i32, i32)> = boxes_at.iter().map(|x| (x[lo], x[hi])).collect::<BTreeSet<_>>().into_iter().collect();
                if lines.len() >= 3 && lines.windows(2).all(|pair| pair[0].1 < pair[1].0) {
                    even |= lines.windows(2).map(|pair| pair[1].0 - pair[0].1).collect::<BTreeSet<_>>().len() == 1;
                }
            }
            out.push((EVEN, Value::Bool(even)));
        }
    }
    if !sides.is_empty() {
        out.push((SHORT, Value::Num(i64::from(sides.iter().map(|(a, b)| *a.min(b)).min().unwrap_or(0)))));
        out.push((LONG, Value::Num(i64::from(sides.iter().map(|(a, b)| *a.max(b)).max().unwrap_or(0)))));
        out.push((SQUARE, Value::Bool(sides.iter().all(|(a, b)| a == b))));
    }
    if let (1, Some([t, b, l, r])) = (boxes.len(), boxes.iter().next()) {
        let (side_h, side_w) = (h - t - b, w - l - r);
        out.push((PROPORTION, if side_h > 0 && side_w > 0 { Value::Share((side_h * side_w) as u32, (h * w) as u32) } else { Value::Share(0, (h * w).max(1) as u32) }));
        out.push((MORE, Value::Bool(side_h > 1 && side_w > 1)));
        out.push((WHOLE, Value::Bool([*t, *b, *l, *r] == [0, 0, 0, 0])));
    }
    out
}

fn bounding_box(cells: &[At], h: i32, w: i32) -> [i32; 4] {
    let (r0, r1, c0, c1) = spans(cells);
    [r0, h - 1 - r1, c0, w - 1 - c1]
}

fn top_two(mut values: Vec<i64>) -> Option<Value> {
    values.sort_unstable_by(|a, b| b.cmp(a));
    (values.len() >= 2 && values[1] > 0 && values[0] >= 0).then(|| Value::Share(values[0] as u32, values[1] as u32))
}

/// Each value's count of rows in one column of dense ids.
fn frequencies(ids: &[u32], count: u32) -> Vec<i64> {
    let mut out = vec![0i64; count as usize];
    for id in ids {
        out[*id as usize] += 1;
    }
    out
}

fn all_distinct(values: &[i64]) -> bool {
    values.iter().collect::<BTreeSet<_>>().len() == values.len()
}

/// The frame of a column's cells: its grid's extents, or the extents its values imply.
fn frame_of(t: &TableAt<'_>, f: &PairFacts, pos: &Pos) -> Option<(i32, i32)> {
    if !pos.in_frame || t.rows == 0 {
        return None;
    }
    if pos.frame_input {
        return Some((f.input.h as i32, f.input.w as i32));
    }
    if pos.frame_output {
        return Some((f.output.h as i32, f.output.w as i32));
    }
    let [top, bottom, left, right] = t.at(0, pos.col);
    Some((top + bottom + 1, left + right + 1))
}

fn axis_of(code: i32) -> i32 {
    match code {
        DIR_T | DIR_B => 0,
        DIR_L | DIR_R => 1,
        DIAG_TL | DIAG_BR => 2,
        _ => 3,
    }
}

fn opposite(code: i32) -> i32 {
    match code {
        DIR_T => DIR_B,
        DIR_B => DIR_T,
        DIR_L => DIR_R,
        DIR_R => DIR_L,
        DIAG_TL => DIAG_BR,
        DIAG_BR => DIAG_TL,
        DIAG_TR => DIAG_BL,
        _ => DIAG_TR,
    }
}

fn type_size(kind: Kind) -> Option<i64> {
    match kind {
        Kind::Dir | Kind::DiagDir | Kind::Axis4 | Kind::C4 => Some(4),
        Kind::Dir8 | Kind::D4 => Some(8),
        Kind::Axis | Kind::DiagAxis | Kind::Sense => Some(2),
        _ => None,
    }
}

/// What a table's rows state of each column.
pub(crate) fn column_kinds(view: &mut View<'_>) {
    let t = view.t;
    let columns = t.kinds.len();
    for column in 0..columns {
        let kind = t.kinds[column];
        let (ids, count) = (view.dense[column].0.clone(), view.dense[column].1);
        let values: BTreeSet<i32> = (0..t.rows).map(|row| t.at(row, column)[0]).collect();
        let counts = frequencies(&ids, count);
        match kind {
            Kind::Color => {
                view.put("C distinct", &[column], Value::Num(i64::from(count)));
                if let Some(value) = top_two(counts.clone()) {
                    view.put("C top-two count ratio", &[column], value);
                }
            }
            Kind::Nat | Kind::Int => {
                view.put("C distinct", &[column], Value::Num(i64::from(count)));
                let list: Vec<i64> = (0..t.rows).map(|row| i64::from(t.at(row, column)[0])).collect();
                let (least, most) = (list.iter().copied().min().unwrap_or(0), list.iter().copied().max().unwrap_or(0));
                view.put("C max", &[column], Value::Num(most));
                view.put("C min", &[column], Value::Num(least));
                if let Some(value) = top_two(list.clone()) {
                    view.put("C top-two ratio", &[column], value);
                }
                view.put("C is a range of consecutive integers", &[column], Value::Bool(most - least + 1 == values.len() as i64));
                if values.len() >= 3 {
                    let held: Vec<i32> = values.iter().copied().collect();
                    view.put("C is an arithmetic progression", &[column], Value::Bool(held.windows(2).map(|pair| pair[1] - pair[0]).collect::<BTreeSet<_>>().len() == 1));
                }
                view.put("C rows per value max", &[column], Value::Num(counts.iter().copied().max().unwrap_or(0)));
                view.put("C rows per value min", &[column], Value::Num(counts.iter().copied().min().unwrap_or(0)));
                if counts.len() > 1 {
                    view.put("C rows per value all distinct", &[column], Value::Bool(all_distinct(&counts)));
                }
            }
            Kind::Dir | Kind::DiagDir | Kind::Dir8 | Kind::Axis | Kind::DiagAxis | Kind::Axis4 | Kind::D4 | Kind::C4 | Kind::Sym | Kind::Sense | Kind::Ident => {
                view.put("C distinct", &[column], Value::Num(i64::from(count)));
                if let Some(size) = type_size(kind) {
                    view.put("C covers its type", &[column], Value::Bool(i64::from(count) == size));
                }
                if kind.is_direction() {
                    view.put("C on one axis", &[column], Value::Bool(values.iter().map(|code| axis_of(*code)).collect::<BTreeSet<_>>().len() == 1));
                    view.put("C includes an opposite pair", &[column], Value::Bool(values.iter().any(|code| values.contains(&opposite(*code)))));
                }
                if matches!(kind, Kind::D4 | Kind::C4) {
                    view.put("C all rotations", &[column], Value::Bool(values.iter().all(|code| matches!(*code, D4_ID | D4_CW | D4_HT | D4_CC))));
                    view.put("C includes the identity", &[column], Value::Bool(values.contains(&D4_ID)));
                }
                if kind == Kind::Ident {
                    view.put("rows per C min", &[column], Value::Num(counts.iter().copied().min().unwrap_or(0)));
                    view.put("rows per C max", &[column], Value::Num(counts.iter().copied().max().unwrap_or(0)));
                    if counts.len() > 1 {
                        view.put("rows per C all distinct", &[column], Value::Bool(all_distinct(&counts)));
                    }
                    for x in 0..columns {
                        if t.kinds[x] == Kind::Color {
                            let mut sets: BTreeMap<u32, BTreeSet<i32>> = BTreeMap::new();
                            for row in 0..t.rows {
                                sets.entry(ids[row]).or_default().insert(t.at(row, x)[0]);
                            }
                            view.put("C values per C max", &[x, column], Value::Num(sets.values().map(|set| set.len() as i64).max().unwrap_or(0)));
                            view.put("C value sets per C distinct", &[x, column], Value::Num(sets.values().collect::<BTreeSet<_>>().len() as i64));
                        }
                    }
                }
            }
            Kind::Offset => {
                let moves: BTreeSet<At> = (0..t.rows).map(|row| {
                    let cell = t.at(row, column);
                    (cell[0], cell[2])
                }).collect();
                let lengths: BTreeSet<i32> = moves.iter().map(|(a, b)| a.abs().max(b.abs())).collect();
                view.put("C distinct", &[column], Value::Num(moves.len() as i64));
                view.put("C includes the zero translation", &[column], Value::Bool(moves.contains(&(0, 0))));
                view.put("C along rows or columns", &[column], Value::Bool(moves.iter().all(|(a, b)| *a == 0 || *b == 0)));
                view.put("C longest translation", &[column], Value::Num(i64::from(lengths.iter().copied().max().unwrap_or(0))));
                view.put("C translations of one length", &[column], Value::Bool(lengths.len() == 1));
            }
            Kind::Box => {
                let boxes: BTreeSet<[i32; 4]> = (0..t.rows).map(|row| t.at(row, column)).collect();
                let (h, w) = (view.f.input.h as i32, view.f.input.w as i32);
                view.put("C distinct", &[column], Value::Num(boxes.len() as i64));
                for (measure, value) in box_values(&boxes, h, w) {
                    view.put(BOX_NAMES[measure].2, &[column], value);
                }
            }
            _ => {}
        }
        if t.rows > 1 {
            view.put("C is unique", &[column], Value::Bool(count as usize == t.rows));
        }
    }
    if t.keys.iter().any(|key| *key) && t.keys.iter().any(|key| !*key) {
        let parts: Vec<&[u32]> = (0..columns).filter(|column| t.keys[*column]).map(|column| view.dense[column].0.as_slice()).collect();
        let (keys, _) = dense_over(&parts, t.rows);
        let whole: Vec<&[u32]> = (0..columns).map(|column| view.dense[column].0.as_slice()).collect();
        let (rows, _) = dense_over(&whole, t.rows);
        let mut seen: HashMap<u32, u32> = HashMap::new();
        let holds = keys.iter().zip(&rows).all(|(key, row)| *seen.entry(*key).or_insert(*row) == *row);
        view.put("key determines the row", &[], Value::Bool(holds));
    }
}

/// The groups of a column's cells.
fn groups_of(t: &TableAt<'_>, column: usize, group_of: &[u32], groups: u32) -> Vec<Vec<At>> {
    let mut out: Vec<Vec<At>> = vec![Vec::new(); groups as usize];
    for row in 0..t.rows {
        let cell = t.at(row, column);
        out[group_of[row] as usize].push((cell[0], cell[2]));
    }
    out.into_iter().map(sorted_cells).filter(|cells| !cells.is_empty()).collect()
}

fn distance(a: At, b: At) -> i32 {
    (a.0 - b.0).abs().max((a.1 - b.1).abs())
}

/// The least Chebyshev distance between the cells of two groups, and each group's least distance to another's cells.
fn group_distances(groups: &[Vec<At>]) -> (i32, Vec<i32>) {
    let mut near = vec![i32::MAX; groups.len()];
    for (at, cells) in groups.iter().enumerate() {
        for (other, others) in groups.iter().enumerate().skip(at + 1) {
            let mut best = i32::MAX;
            for a in cells {
                for b in others {
                    best = best.min(distance(*a, *b));
                }
                if best == 0 {
                    break;
                }
            }
            near[at] = near[at].min(best);
            near[other] = near[other].min(best);
        }
    }
    (near.iter().copied().min().unwrap_or(i32::MAX), near)
}

/// What a column's cells and their groups state.
pub(crate) fn cell_kinds(view: &mut View<'_>, pos: &Pos, group_of: &[u32], groups: u32) {
    let t = view.t;
    let f = view.f;
    let col = pos.col;
    let Some((h, w)) = frame_of(t, f, pos) else {
        view.put("C values distinct", &[col], Value::Num(pos.places.len() as i64));
        let extents: BTreeSet<At> = (0..t.rows).map(|row| {
            let [top, bottom, left, right] = t.at(row, col);
            (top + bottom + 1, left + right + 1)
        }).collect();
        view.put("C extents distinct", &[col], Value::Num(extents.len() as i64));
        return;
    };
    let cells = sorted_cells(pos.places.iter().copied());
    if cells.is_empty() {
        return;
    }
    let put = |view: &mut View<'_>, kind: &'static str, value: Value| view.put(kind, &[col], value);
    put(view, "C cells", Value::Num(cells.len() as i64));
    put(view, "C covers the grid", Value::Bool(cells.len() as i64 == i64::from(h) * i64::from(w)));
    let parts = parts_of(&cells, true);
    put(view, "C components", Value::Num(parts.len() as i64));
    put(view, "C on one line", Value::Bool(cells.iter().map(|at| at.0).collect::<BTreeSet<_>>().len() <= 1 || cells.iter().map(|at| at.1).collect::<BTreeSet<_>>().len() <= 1));
    put(view, "C touches the grid edge", Value::Bool(cells.iter().any(|(r, c)| *r == 0 || *r == h - 1 || *c == 0 || *c == w - 1)));
    if h * w <= 900 {
        put(view, "C complement is 4-connected", Value::Bool(complement_is_connected(&cells, h, w)));
    }
    put(view, "C 4-connected components", Value::Num(parts_of(&cells, false).len() as i64));
    put(view, "C every component is a straight line", Value::Bool(parts.iter().all(|part| straight(part))));
    put(view, "C full lines", Value::Num(full_lines(&cells, h, w)));
    put(view, "C cells per line max", Value::Num(cells_per_line_max(&cells)));
    put(view, "C fills its bounding box", Value::Bool(fills_box(&cells)));
    put(view, "C is the outline of its bounding box", Value::Bool(outlines_box(&cells)));
    put(view, "C symmetry count", Value::Num(symmetric_images(&cells)));
    put(view, "C enclosed regions", Value::Num(enclosed_regions(&cells)));
    let (r0, r1, c0, c1) = spans(&cells);
    put(view, "C box proportion of the grid", Value::Share(((r1 - r0 + 1) * (c1 - c0 + 1)) as u32, (h * w).max(1) as u32));
    if !pos.frame_input {
        let (hi, wi) = (f.input.h as i32, f.input.w as i32);
        put(view, "C frame is the input size", Value::Bool((h, w) == (hi, wi)));
        put(view, "C frame is square", Value::Bool(h == w));
        put(view, "C frame proportion of the input", Value::Share((h * w) as u32, (hi * wi).max(1) as u32));
        put(view, "C frame is a multiple of the input size", Value::Bool((h, w) != (hi, wi) && h % hi == 0 && w % wi == 0));
        put(view, "C frame divides the input size", Value::Bool((h, w) != (hi, wi) && h > 0 && w > 0 && hi % h == 0 && wi % w == 0));
    }
    for (measure, value) in box_values(&BTreeSet::from([bounding_box(&cells, h, w)]), h, w) {
        put(view, BOX_NAMES[measure].0, value);
    }
    if groups == 0 {
        return;
    }
    let held = groups_of(t, col, group_of, groups);
    let boxes: BTreeSet<[i32; 4]> = held.iter().map(|group| bounding_box(group, h, w)).collect();
    put(view, "C bounding box per group of its Ident, Color and key columns distinct", Value::Num(boxes.len() as i64));
    for (measure, value) in box_values(&boxes, h, w) {
        put(view, BOX_NAMES[measure].1, value);
    }
    let sizes: Vec<i64> = held.iter().map(|group| group.len() as i64).collect();
    let group_parts: Vec<i64> = held.iter().map(|group| parts_of(group, true).len() as i64).collect();
    put(view, "C cells per group of its Ident, Color and key columns min", Value::Num(sizes.iter().copied().min().unwrap_or(0)));
    put(view, "C cells per group of its Ident, Color and key columns max", Value::Num(sizes.iter().copied().max().unwrap_or(0)));
    put(view, "C components per group of its Ident, Color and key columns max", Value::Num(group_parts.iter().copied().max().unwrap_or(0)));
    put(view, "C components per group of its Ident, Color and key columns total", Value::Num(group_parts.iter().sum()));
    put(view, "C fills its bounding box per group of its Ident, Color and key columns", Value::Bool(held.iter().all(|group| fills_box(group))));
    put(view, "C symmetry count per group of its Ident, Color and key columns min", Value::Num(held.iter().map(|group| symmetric_images(group)).min().unwrap_or(0)));
    put(view, "C enclosed regions per group of its Ident, Color and key columns max", Value::Num(held.iter().map(|group| enclosed_regions(group)).max().unwrap_or(0)));
    put(view, "C full lines per group of its Ident, Color and key columns max", Value::Num(held.iter().map(|group| full_lines(group, h, w)).max().unwrap_or(0)));
    if held.len() >= 2 {
        let most = sizes.iter().copied().max().unwrap_or(0);
        let least = sizes.iter().copied().min().unwrap_or(0);
        put(view, "C largest group of its Ident, Color and key columns is unique", Value::Bool(sizes.iter().filter(|size| **size == most).count() == 1));
        put(view, "C smallest group of its Ident, Color and key columns is unique", Value::Bool(sizes.iter().filter(|size| **size == least).count() == 1));
    }
    put(view, "C distinct shapes per group of its Ident, Color and key columns", Value::Num(held.iter().map(|group| normalized(group)).collect::<BTreeSet<_>>().len() as i64));
    put(view, "C distinct shapes per group of its Ident, Color and key columns up to rotation and reflection", Value::Num(held.iter().map(|group| canonical(group)).collect::<BTreeSet<_>>().len() as i64));
    let total: usize = held.iter().map(Vec::len).sum();
    if held.len() >= 2 && total <= 900 {
        let (least, near) = group_distances(&held);
        if least <= 60 {
            put(view, "C least distance between groups of its Ident, Color and key columns", Value::Num(i64::from(least)));
        }
        if held.len() <= 30 && total <= 300 {
            put(view, "C distance to the nearest other group of its Ident, Color and key columns, max", Value::Num(i64::from(near.iter().copied().max().unwrap_or(0))));
        }
        let mut owner: HashMap<At, Vec<usize>> = HashMap::new();
        for (at, group) in held.iter().enumerate() {
            for cell in group {
                owner.entry(*cell).or_default().push(at);
            }
        }
        let adjoins = [(1, 0), (-1, 0), (0, 1), (0, -1)].iter().any(|(a, b): &At| {
            held.iter().enumerate().all(|(at, group)| {
                group.iter().any(|(r, c)| {
                    let next = (r + a, c + b);
                    !(0 <= next.0 && next.0 < h && 0 <= next.1 && next.1 < w) || owner.get(&next).is_some_and(|holders| holders.iter().any(|holder| *holder != at))
                })
            })
        });
        put(view, "C every group of its Ident, Color and key columns adjoins another group or the grid edge in one direction", Value::Bool(adjoins));
    }
}

/// `graph_shape`: the connected parts and the greatest degree of the graph whose edges are pairs of dense ids.
fn graph_shape(a: &[u32], b: &[u32], counts: (u32, u32), same_ids: bool) -> (i64, i64) {
    let offset = if same_ids { 0 } else { counts.0 };
    let total = (offset + counts.1).max(counts.0) as usize;
    let mut parent: Vec<usize> = (0..total).collect();
    fn root(parent: &mut [usize], mut x: usize) -> usize {
        while parent[x] != x {
            parent[x] = parent[parent[x]];
            x = parent[x];
        }
        x
    }
    let mut neighbors: Vec<BTreeSet<usize>> = vec![BTreeSet::new(); total];
    let mut used = vec![false; total];
    for (x, y) in a.iter().zip(b) {
        let (x, y) = (*x as usize, (*y + offset) as usize);
        used[x] = true;
        used[y] = true;
        if x != y {
            neighbors[x].insert(y);
            neighbors[y].insert(x);
        }
        let (rx, ry) = (root(&mut parent, x), root(&mut parent, y));
        parent[rx] = ry;
    }
    let mut roots = BTreeSet::new();
    for x in 0..total {
        if used[x] {
            roots.insert(root(&mut parent, x));
        }
    }
    (roots.len() as i64, neighbors.iter().map(|held| held.len() as i64).max().unwrap_or(0))
}

/// A dense id over two columns' values, so an equal value of the two has one id.
fn shared_ids(t: &TableAt<'_>, a: usize, b: usize) -> (Vec<u32>, Vec<u32>, u32) {
    let mut seen: HashMap<Cell, u32> = HashMap::new();
    let mut ids = |column: usize| -> Vec<u32> {
        (0..t.rows).map(|row| {
            let next = seen.len() as u32;
            *seen.entry(t.at(row, column)).or_insert(next)
        }).collect()
    };
    let (first, second) = (ids(a), ids(b));
    let count = seen.len() as u32;
    (first, second, count)
}

fn order_word(signs: (bool, bool, bool)) -> &'static str {
    match signs {
        (true, false, false) => "<",
        (true, true, false) => "<=",
        (false, true, false) => "=",
        (false, true, true) => ">=",
        (false, false, true) => ">",
        _ => "mixed",
    }
}

/// What two columns of one row state together.
pub(crate) fn pair_kinds(view: &mut View<'_>) {
    let t = view.t;
    let f = view.f;
    let columns = t.kinds.len();
    for a in 0..columns {
        for b in 0..columns {
            if a == b {
                continue;
            }
            let (ka, kb) = (t.kinds[a], t.kinds[b]);
            if ka.is_number() && kb.is_number() {
                let (mut below, mut same, mut above) = (false, false, false);
                let mut pairs = BTreeSet::new();
                let (mut first, mut second) = (BTreeSet::new(), BTreeSet::new());
                for row in 0..t.rows {
                    let (x, y) = (t.at(row, a)[0], t.at(row, b)[0]);
                    below |= x < y;
                    same |= x == y;
                    above |= x > y;
                    pairs.insert((x, y));
                    first.insert(x);
                    second.insert(y);
                }
                view.put("C vs C in every row", &[a, b], Value::Word(order_word((below, same, above))));
                if first.len() >= 2 && second.len() >= 2 {
                    let held: Vec<At> = pairs.into_iter().collect();
                    let tied = held.windows(2).all(|pair| pair[0].0 != pair[1].0 || pair[0].1 == pair[1].1);
                    let up = tied && held.windows(2).all(|pair| pair[0].0 == pair[1].0 || pair[0].1 <= pair[1].1);
                    let down = tied && held.windows(2).all(|pair| pair[0].0 == pair[1].0 || pair[0].1 >= pair[1].1);
                    // The word states how the second hole goes as the first rises.
                    view.put("C as C rises", &[b, a], Value::Word(if up { "rises" } else if down { "falls" } else { "neither" }));
                }
            }
            if b > a && ka == kb {
                if matches!(ka, Kind::Dir | Kind::DiagDir | Kind::Dir8 | Kind::Axis | Kind::DiagAxis | Kind::Axis4 | Kind::D4 | Kind::C4 | Kind::Sym | Kind::Sense | Kind::Ident | Kind::Color) {
                    let equal = (0..t.rows).filter(|row| t.at(*row, a) == t.at(*row, b)).count();
                    view.put("C equals C", &[a, b], Value::Word(if equal == t.rows { "in every row" } else if equal == 0 { "in no row" } else { "in some rows" }));
                }
                if matches!(ka, Kind::Ident | Kind::Position | Kind::Color | Kind::Nat | Kind::Int) {
                    let (first, second, count) = shared_ids(t, a, b);
                    let (parts, degree) = graph_shape(&first, &second, (count, count), true);
                    view.put("C-C graph components", &[a, b], Value::Num(parts));
                    view.put("C-C graph greatest degree", &[a, b], Value::Num(degree));
                }
            }
        }
    }
    let places: Vec<usize> = (0..columns).filter(|column| t.kinds[*column] == Kind::Position).collect();
    let positions: Vec<Pos> = places.iter().map(|column| pos_of(t, f, *column)).collect();
    let frames: Vec<Option<(i32, i32)>> = positions.iter().map(|pos| frame_of(t, f, pos)).collect();
    for (at, a) in places.iter().enumerate() {
        let Some(frame_a) = frames[at] else { continue };
        for (other, b) in places.iter().enumerate().skip(at + 1) {
            let Some(frame_b) = frames[other] else { continue };
            let moves: BTreeSet<At> = (0..t.rows).map(|row| {
                let (x, y) = (t.at(row, *a), t.at(row, *b));
                (y[0] - x[0], y[2] - x[2])
            }).collect();
            let one_frame = (positions[at].frame_input && positions[other].frame_input) || (positions[at].frame_output && positions[other].frame_output) || (!positions[at].frame_input && !positions[at].frame_output && !positions[other].frame_input && !positions[other].frame_output && frame_a == frame_b);
            if one_frame {
                let lengths: Vec<i32> = moves.iter().map(|(p, q)| p.abs().max(q.abs())).collect();
                view.put("C to C displacements distinct", &[*a, *b], Value::Num(moves.len() as i64));
                view.put("C to C distance max", &[*a, *b], Value::Num(i64::from(lengths.iter().copied().max().unwrap_or(0))));
                view.put("C to C distance min", &[*a, *b], Value::Num(i64::from(lengths.iter().copied().min().unwrap_or(0))));
                view.put("C to C along rows or columns", &[*a, *b], Value::Bool(moves.iter().all(|(p, q)| *p == 0 || *q == 0)));
                view.put("C to C along diagonals", &[*a, *b], Value::Bool(moves.iter().all(|(p, q)| p.abs() == q.abs())));
            } else {
                view.put("C to C offsets distinct, across frames", &[*a, *b], Value::Num(moves.len() as i64));
            }
        }
        if positions[at].frame_input {
            for b in 0..columns {
                if t.kinds[b] == Kind::Box {
                    let holds = (0..t.rows).all(|row| {
                        let (cell, held) = (t.at(row, *a), t.at(row, b));
                        (0..4).all(|side| cell[side] >= held[side])
                    });
                    view.put("C inside C in every row", &[*a, b], Value::Bool(holds));
                }
            }
        }
    }
}

/// `least_period`: the least move along a row or a column, at most half its box's extent, that keeps a colored cell set.
fn least_period(colored: &BTreeMap<At, i32>) -> Option<i64> {
    let cells: Vec<At> = colored.keys().copied().collect();
    let (r0, r1, c0, c1) = spans(&cells);
    let mut best = None;
    for (dr, dc, n) in [(0, 1, c1 - c0 + 1), (1, 0, r1 - r0 + 1)] {
        for k in 1..=n / 2 {
            if best.is_some_and(|held| k >= held) {
                break;
            }
            if colored.iter().all(|((r, c), color)| colored.get(&(r + dr * k, c + dc * k)).is_none_or(|other| other == color)) {
                best = Some(k);
                break;
            }
        }
    }
    best.map(i64::from)
}

/// The kinds of a column of cells with a column of colors.
pub(crate) fn coloring_kinds(view: &mut View<'_>) {
    let t = view.t;
    let f = view.f;
    let columns = t.kinds.len();
    for x in 0..columns {
        if t.kinds[x] != Kind::Color {
            continue;
        }
        let counts = frequencies(&view.dense[x].0, view.dense[x].1);
        view.put("C rows per value all equal", &[x], Value::Bool(counts.iter().collect::<BTreeSet<_>>().len() == 1));
        for n in 0..columns {
            if t.kinds[n] != Kind::Position || !pos_of(t, f, n).in_frame {
                continue;
            }
            let mut colored: BTreeMap<At, i32> = BTreeMap::new();
            let mut one_color = true;
            for row in 0..t.rows {
                let cell = t.at(row, n);
                let color = t.at(row, x)[0];
                one_color &= *colored.entry((cell[0], cell[2])).or_insert(color) == color;
            }
            if one_color && !colored.is_empty() {
                let cells: Vec<At> = colored.keys().copied().collect();
                let (r0, _, c0, _) = spans(&cells);
                let form = |map: &dyn Fn(At) -> At| -> Vec<(At, i32)> {
                    let moved: Vec<(At, i32)> = colored.iter().map(|(at, color)| (map(*at), *color)).collect();
                    let (a0, b0) = moved.iter().fold((i32::MAX, i32::MAX), |(a, b), ((p, q), _)| (a.min(*p), b.min(*q)));
                    let mut out: Vec<(At, i32)> = moved.into_iter().map(|((p, q), color)| ((p - a0, q - b0), color)).collect();
                    out.sort_unstable();
                    out
                };
                let _ = (r0, c0);
                let own = form(&|(r, c)| (r, c));
                let maps: [&dyn Fn(At) -> At; 8] = [&|(r, c)| (r, c), &|(r, c)| (r, -c), &|(r, c)| (-r, c), &|(r, c)| (-r, -c), &|(r, c)| (c, r), &|(r, c)| (c, -r), &|(r, c)| (-c, r), &|(r, c)| (-c, -r)];
                let count = maps.iter().filter(|map| form(**map) == own).count() as i64;
                view.put("C,C symmetry count", &[n, x], Value::Num(count));
                let mut by: BTreeMap<i32, Vec<At>> = BTreeMap::new();
                for (at, color) in &colored {
                    by.entry(*color).or_default().push(*at);
                }
                if by.len() > 1 && by.len() <= 10 {
                    let holes: BTreeMap<i32, Vec<At>> = by.iter().map(|(color, cells)| (*color, holes_of(cells))).collect();
                    let lies = by.keys().any(|p| by.iter().any(|(q, cells)| p != q && !holes[p].is_empty() && cells.iter().all(|at| holes[p].binary_search(at).is_ok())));
                    view.put("C,C a color lies in the holes of another", &[n, x], Value::Bool(lies));
                    let mut touching = BTreeSet::new();
                    for ((r, c), color) in &colored {
                        for (p, q) in [(1, 0), (0, 1)] {
                            if let Some(other) = colored.get(&(r + p, c + q)) {
                                if other != color {
                                    touching.insert((*color.min(other), *color.max(other)));
                                }
                            }
                        }
                    }
                    view.put("C,C touching color pairs", &[n, x], Value::Num(touching.len() as i64));
                }
                if fills_box(&cells) {
                    if let Some(period) = least_period(&colored) {
                        view.put("C,C least period", &[n, x], Value::Num(period));
                    }
                }
            }
            for g in 0..columns {
                if g == n || g == x || !(t.kinds[g] == Kind::Ident || t.keys[g]) {
                    continue;
                }
                let mut cells_of: BTreeMap<u32, Vec<At>> = BTreeMap::new();
                let mut colors_of: BTreeMap<u32, BTreeSet<i32>> = BTreeMap::new();
                for row in 0..t.rows {
                    let cell = t.at(row, n);
                    let id = view.dense[g].0[row];
                    cells_of.entry(id).or_default().push((cell[0], cell[2]));
                    colors_of.entry(id).or_default().insert(t.at(row, x)[0]);
                }
                if cells_of.len() < 2 {
                    continue;
                }
                let shapes: BTreeMap<u32, Vec<At>> = cells_of.iter().map(|(id, cells)| (*id, normalized(cells))).collect();
                let (mut shape_to, mut color_to): (BTreeMap<&Vec<At>, &BTreeSet<i32>>, BTreeMap<&BTreeSet<i32>, &Vec<At>>) = (BTreeMap::new(), BTreeMap::new());
                let (mut first, mut second) = (true, true);
                for (id, shape) in &shapes {
                    let colors = &colors_of[id];
                    first &= *shape_to.entry(shape).or_insert(colors) == colors;
                    second &= *color_to.entry(colors).or_insert(shape) == shape;
                }
                view.put("C,C same shape, same colors, per C", &[n, x, g], Value::Bool(first));
                view.put("C,C same colors, same shape, per C", &[n, x, g], Value::Bool(second));
            }
        }
    }
}

/// The kinds that read the table alone.
pub(crate) fn table_kinds(view: &mut View<'_>) {
    let t = view.t;
    let f = view.f;
    column_kinds(view);
    pair_kinds(view);
    if t.rows > MAX_ROWS {
        return;
    }
    let group_columns: Vec<usize> = (0..t.kinds.len()).filter(|c| matches!(t.kinds[*c], Kind::Ident | Kind::Color) || t.keys[*c]).collect();
    let (group_of, groups) = if group_columns.is_empty() {
        (Vec::new(), 0)
    } else {
        let parts: Vec<&[u32]> = group_columns.iter().map(|c| view.dense[*c].0.as_slice()).collect();
        dense_over(&parts, t.rows)
    };
    for col in 0..t.kinds.len() {
        if t.kinds[col] == Kind::Position {
            let pos = pos_of(t, f, col);
            cell_kinds(view, &pos, &group_of, groups);
        }
    }
    coloring_kinds(view);
}
