//! The catalog's kinds over a Position column and another column, and over its cells as a shape.

use crate::catalog::*;
use crate::catalog_cells::*;
use crate::catalog_facts::*;
use crate::occurrence::{distinct_patterns, each_turned_image, extent_of, PatternCell};

/// `agreeing`: the rows whose value is the one most frequent value of their key, in a key of two
/// rows or more.
fn agreeing(keys: &[u32], count: u32, values: &[u8]) -> u32 {
    let stride = 12usize;
    let mut table = vec![0u32; count as usize * stride];
    for (key, value) in keys.iter().zip(values) {
        table[*key as usize * stride + *value as usize] += 1;
    }
    let mut hits = 0;
    for held in table.chunks(stride) {
        for (at, q) in held.iter().enumerate() {
            if *q > 1 && held.iter().enumerate().all(|(other, w)| other == at || *q - 1 >= *w) {
                hits += *q;
            }
        }
    }
    hits
}

pub(crate) fn pairs_of(view: &mut View<'_>, pos: &Pos, _group_of: &[u32], _groups: u32) {
    let t = view.t;
    let f = view.f;
    let output = &f.output;
    let input = &f.input;
    let p = pos.col;
    let rows = t.rows;
    let columns = t.kinds.len();
    // Per row, the output color at its place, with 10 for a place off the grid.
    let labels: Vec<u8> = pos.at_output.iter().map(|at| if *at >= 0 { output.color[*at as usize] } else { 10 }).collect();
    let on = pos.on_output && !pos.set_output.is_empty();
    let lying: Vec<usize> = (0..rows).filter(|row| pos.cell_output[*row] >= 0).collect();
    let agreement = pos.on_output && rows >= 2;
    let changes: Vec<u8> = if f.same {
        pos.at_output.iter().map(|at| if *at >= 0 { u8::from(f.changed.get(*at as usize)) } else { 2 }).collect()
    } else {
        Vec::new()
    };
    for x in 0..columns {
        if x == p {
            continue;
        }
        let (ids, count) = (&view.dense[x].0, view.dense[x].1);
        let mut records: [Option<(&'static str, Value)>; 6] = [None; 6];
        if on && rows > 1 {
            let function = is_function(count, ids.iter().zip(&labels).map(|(id, label)| (*id, *label)));
            records[0] = Some(("C,C determines the output color", Value::Bool(function)));
            let mut first = [u32::MAX; 11];
            let mut back = true;
            for (id, label) in ids.iter().zip(&labels) {
                let held = &mut first[*label as usize];
                if *held == u32::MAX {
                    *held = *id;
                } else if *held != *id {
                    back = false;
                }
            }
            records[1] = Some(("C,C is determined by the output color", Value::Bool(back)));
        }
        if f.same && lying.len() >= 2 {
            let change = is_function(count, lying.iter().map(|row| (ids[*row], u8::from(f.changed.get(pos.cell_output[*row] as usize)))));
            records[2] = Some(("C,C determines which cells change", Value::Bool(change)));
            let pairs = count as usize * 11;
            let with_color = is_function(pairs as u32, lying.iter().map(|row| {
                let at = pos.cell_output[*row] as usize;
                (ids[*row] * 11 + u32::from(input.color[at]), output.color[at])
            }));
            records[3] = Some(("C,C with the input color determines the output color", Value::Bool(with_color)));
        }
        if agreement {
            records[4] = Some(("C,C output color agrees with the other rows of its value, proportion", Value::Share(agreeing(ids, count, &labels), rows as u32)));
            if f.same {
                records[5] = Some(("C,C whether it changes agrees with the other rows of its value, proportion", Value::Share(agreeing(ids, count, &changes), rows as u32)));
            }
        }
        for record in records.into_iter().flatten() {
            view.put(record.0, &[p, x], record.1);
        }
    }
    if agreement && columns > 2 {
        let parts: Vec<&[u32]> = (0..columns).filter(|c| *c != p).map(|c| view.dense[c].0.as_slice()).collect();
        let (keys, count) = dense_over(&parts, rows);
        view.put("C output color under its other columns agrees with the other rows of its value, proportion", &[p], Value::Share(agreeing(&keys, count, &labels), rows as u32));
        if f.same {
            view.put("C whether it changes under its other columns agrees with the other rows of its value, proportion", &[p], Value::Share(agreeing(&keys, count, &changes), rows as u32));
        }
    }
    // The pairs that read a second column's type.
    for other in 0..columns {
        if other == p {
            continue;
        }
        match t.kinds[other] {
            Kind::Color => color_pairs(view, pos, other),
            Kind::Position => two_places(view, pos, other),
            Kind::Offset => {
                if f.same {
                    let mut seen: Vec<(i32, i32, i32)> = Vec::new();
                    for row in 0..rows {
                        let at = pos.cell_input[row];
                        if at >= 0 {
                            let cell = t.at(row, other);
                            seen.push((at, cell[0], cell[2]));
                        }
                    }
                    seen.sort_unstable();
                    seen.dedup();
                    let (mut hits, mut of) = (0, 0);
                    for (at, dr, dc) in seen {
                        let (r, c) = (at / input.w as i32 + dr, at % input.w as i32 + dc);
                        if r >= 0 && c >= 0 && r < output.h as i32 && c < output.w as i32 {
                            of += 1;
                            hits += u32::from(input.color[at as usize] == output.at(r as usize, c as usize));
                        }
                    }
                    if of > 0 {
                        view.put("C,C translates the input color onto the output, proportion", &[p, other], Value::Share(hits, of));
                    }
                }
            }
            Kind::D4 | Kind::C4 => {
                let mut seen: Vec<(i32, i32)> = (0..rows).filter(|row| pos.cell_input[*row] >= 0).map(|row| (pos.cell_input[row], t.at(row, other)[0])).collect();
                seen.sort_unstable();
                seen.dedup();
                let (mut hits, mut of) = (0, 0);
                let (hi, wi) = (input.h, input.w);
                for (at, code) in seen {
                    let swaps = matches!(code, D4_CW | D4_CC | D4_DG | D4_AD);
                    if (if swaps { (wi, hi) } else { (hi, wi) }) != (output.h, output.w) {
                        continue;
                    }
                    let (r, c) = (at as usize / wi, at as usize % wi);
                    let (y, z) = match code {
                        D4_ID => (r, c),
                        D4_LR => (r, wi - 1 - c),
                        D4_TB => (hi - 1 - r, c),
                        D4_HT => (hi - 1 - r, wi - 1 - c),
                        D4_CW => (c, hi - 1 - r),
                        D4_CC => (wi - 1 - c, r),
                        D4_DG => (c, r),
                        _ => (wi - 1 - c, hi - 1 - r),
                    };
                    of += 1;
                    hits += u32::from(input.color[at as usize] == output.at(y, z));
                }
                if of > 0 {
                    view.put("C,C rotates or reflects the input color onto the output, proportion", &[p, other], Value::Share(hits, of));
                }
            }
            Kind::Dir | Kind::DiagDir | Kind::Dir8 => {
                if pos.on_output && !f.changed.is_empty() {
                    toward_changed(view, pos, other);
                }
            }
            _ => {}
        }
    }
}

/// `{n},{d}`: whether a changed cell lies toward a direction, and whether all cells do.
fn toward_changed(view: &mut View<'_>, pos: &Pos, d: usize) {
    let t = view.t;
    let f = view.f;
    let (h, w) = (f.output.h as i32, f.output.w as i32);
    let mut seen: Vec<(i32, i32, i32)> = (0..t.rows).map(|row| {
        let cell = t.at(row, pos.col);
        (cell[0], cell[2], t.at(row, d)[0])
    }).collect();
    seen.sort_unstable();
    seen.dedup();
    let (mut hit, mut whole) = (0, 0);
    let of = seen.len() as u32;
    for (r, c, code) in seen {
        if r < 0 || c < 0 || r >= h || c >= w {
            continue;
        }
        let (dr, dc) = match code {
            DIR_T => (-1, 0),
            DIR_B => (1, 0),
            DIR_L => (0, -1),
            DIR_R => (0, 1),
            DIAG_TL => (-1, -1),
            DIAG_TR => (-1, 1),
            DIAG_BL => (1, -1),
            _ => (1, 1),
        };
        let (mut y, mut z) = (r + dr, c + dc);
        let (mut any, mut every, mut some) = (false, true, false);
        while y >= 0 && z >= 0 && y < h && z < w {
            let changed = f.changed.get((y * w + z) as usize);
            any |= changed;
            every &= changed;
            some = true;
            y += dr;
            z += dc;
        }
        hit += u32::from(any);
        whole += u32::from(some && every);
    }
    view.put("C,C has a changed cell toward it, proportion", &[pos.col, d], share(hit, of));
    view.put("C,C every cell toward it is changed, proportion", &[pos.col, d], share(whole, of));
}

fn two_places(view: &mut View<'_>, pos: &Pos, q: usize) {
    let t = view.t;
    let f = view.f;
    let other = pos_of(t, f, q);
    let mut seen: Vec<(i32, i32)> = (0..t.rows).filter(|row| pos.cell_input[*row] >= 0 && other.cell_output[*row] >= 0).map(|row| (pos.cell_input[row], other.cell_output[row])).collect();
    if seen.is_empty() {
        return;
    }
    seen.sort_unstable();
    seen.dedup();
    let hits = seen.iter().filter(|(a, b)| f.input.color[*a as usize] == f.output.color[*b as usize]).count() as u32;
    view.put("C,C carries the input colors to the output, proportion", &[pos.col, q], Value::Share(hits, seen.len() as u32));
    let mut covered = Bits::EMPTY;
    for (_, b) in &seen {
        covered.set(*b as usize);
    }
    view.put("C,C covers the output cells, proportion", &[pos.col, q], Value::Share(covered.count(), (f.output.h * f.output.w) as u32));
}

/// `{n},{x}`: a Position column and a Color column.
fn color_pairs(view: &mut View<'_>, pos: &Pos, x: usize) {
    let t = view.t;
    let f = view.f;
    let output = &f.output;
    let input = &f.input;
    let p = pos.col;
    let rows = t.rows;
    let frame_aligned = pos.frame_output || (pos.frame_input && f.same);
    let colors_at = |row: usize| t.at(row, x)[0];
    if pos.frame_input && f.same {
        let usable: Vec<usize> = (0..rows).filter(|row| pos.cell_input[*row] >= 0).collect();
        if usable.len() >= 2 {
            let hits = usable.iter().filter(|row| {
                let at = pos.cell_input[**row] as usize;
                let held = i32::from(output.color[at]);
                held == i32::from(input.color[at]) || held == colors_at(**row)
            }).count() as u32;
            view.put("C,C the output color is the input color or this color, proportion", &[p, x], Value::Share(hits, usable.len() as u32));
        }
    } else if f.same {
        let usable: Vec<usize> = (0..rows).filter(|row| pos.cell_input[*row] >= 0).collect();
        if usable.len() >= 2 {
            let hits = usable.iter().filter(|row| {
                let at = pos.cell_input[**row] as usize;
                let held = i32::from(output.color[at]);
                held == i32::from(input.color[at]) || held == colors_at(**row)
            }).count() as u32;
            view.put("C,C the output color is the input color or this color, proportion", &[p, x], Value::Share(hits, usable.len() as u32));
        }
    }
    if frame_aligned {
        let (mut mask, mut agree) = (0u16, 0u32);
        let mut in_mask = Bits::EMPTY;
        for row in 0..rows {
            let value = colors_at(row);
            if (0..10).contains(&value) {
                mask |= 1 << value;
            }
            let at = pos.at_output[row];
            if at >= 0 && i32::from(output.color[at as usize]) == value {
                agree += 1;
            }
            let _ = &mut in_mask;
        }
        view.put("C,C agrees with the output colors, proportion", &[p, x], Value::Share(agree, rows as u32));
        let mut cells = Bits::EMPTY;
        for col in 0..10 {
            if mask >> col & 1 == 1 {
                cells = cells.or(&output.by_color[col]);
            }
        }
        let s = pos.set_output;
        view.put("C,C vs the output cells of its colors", &[p, x], Value::Word(set_relation_in(!s.within(&cells), !cells.within(&s), s.intersects(&cells), s.or(&cells) != output.all)));
        let mut pairs: Vec<(i32, i32, i32)> = (0..rows).map(|row| {
            let cell = t.at(row, p);
            (colors_at(row), cell[0], cell[2])
        }).collect();
        pairs.sort_unstable();
        pairs.dedup();
        let (mut held, mut hits) = (0u32, 0u32);
        let mut at = 0;
        while at < pairs.len() {
            let color = pairs[at].0;
            let start = at;
            while at < pairs.len() && pairs[at].0 == color {
                at += 1;
            }
            held += 1;
            let count = if (0..10).contains(&color) { output.counts[color as usize] } else { 0 };
            hits += u32::from((at - start) as u32 == count);
        }
        view.put("C,C color counts agree with the output, proportion", &[p, x], Value::Share(hits, held));
    }
    if pos.in_frame {
        // The colored cells against the output's.
        let mut pairs: Vec<(i32, i32, i32)> = (0..rows).map(|row| {
            let cell = t.at(row, p);
            (cell[0], cell[2], colors_at(row))
        }).collect();
        pairs.sort_unstable();
        pairs.dedup();
        let matched = |target: &[(i32, i32, i32)], set: &[(i32, i32, i32)]| -> u32 {
            target.iter().filter(|cell| set.binary_search(cell).is_ok()).count() as u32
        };
        let mut want: Vec<(i32, i32, i32)> = Vec::with_capacity(output.h * output.w);
        for r in 0..output.h {
            for c in 0..output.w {
                want.push((r as i32, c as i32, i32::from(output.at(r, c))));
            }
        }
        if pos.on_output {
            let both = matched(&pairs, &want);
            let either = (pairs.len() + want.len()) as u32 - both;
            view.put("C,C Jaccard index with the output cells in the frame", &[p, x], Value::Share(both, either));
            if pos.frame_output {
                view.put("C,C Jaccard index with the output cells", &[p, x], Value::Share(both, either));
            }
        }
        let mut mask = 0u16;
        for pair in &pairs {
            if (0..10).contains(&pair.2) {
                mask |= 1 << pair.2;
            }
        }
        let by_colors: Vec<(i32, i32, i32)> = want.iter().copied().filter(|cell| (0..10).contains(&cell.2) && mask >> cell.2 & 1 == 1).collect();
        if let Some(value) = aligned(&pairs, &want) {
            view.put("C,C Jaccard index with the output cells after bounding box scaling", &[p, x], value);
        }
        if let Some(value) = aligned(&pairs, &by_colors) {
            view.put("C,C color Jaccard index with the output cells after bounding box scaling", &[p, x], value);
        }
    }
}

/// The Jaccard index of two colored cell sets, each moved to its box, with the smaller scaled up.
fn aligned(pairs: &[(i32, i32, i32)], want: &[(i32, i32, i32)]) -> Option<Value> {
    if pairs.is_empty() || want.is_empty() {
        return None;
    }
    let anchor = |cells: &[(i32, i32, i32)]| -> (Vec<(i32, i32, i32)>, i32, i32) {
        let (r0, r1) = (cells.iter().map(|x| x.0).min().unwrap_or(0), cells.iter().map(|x| x.0).max().unwrap_or(0));
        let (c0, c1) = (cells.iter().map(|x| x.1).min().unwrap_or(0), cells.iter().map(|x| x.1).max().unwrap_or(0));
        (cells.iter().map(|x| (x.0 - r0, x.1 - c0, x.2)).collect(), r1 - r0 + 1, c1 - c0 + 1)
    };
    let expand = |cells: &[(i32, i32, i32)], h: i32, w: i32, th: i32, tw: i32| -> Option<Vec<(i32, i32, i32)>> {
        if th % h != 0 || tw % w != 0 || th / h != tw / w {
            return None;
        }
        let k = th / h;
        let mut out = Vec::with_capacity(cells.len() * (k * k) as usize);
        for cell in cells {
            for dr in 0..k {
                for dc in 0..k {
                    out.push((cell.0 * k + dr, cell.1 * k + dc, cell.2));
                }
            }
        }
        Some(out)
    };
    let (mut p, h, w) = anchor(pairs);
    let (mut q, th, tw) = anchor(want);
    if th * tw >= h * w {
        p = expand(&p, h, w, th, tw)?;
    } else {
        q = expand(&q, th, tw, h, w)?;
    }
    p.sort_unstable();
    p.dedup();
    q.sort_unstable();
    q.dedup();
    let both = p.iter().filter(|cell| q.binary_search(cell).is_ok()).count() as u32;
    Some(Value::Share(both, (p.len() + q.len()) as u32 - both))
}

/// A colored pattern moved so that its box starts at (0, 0), sorted.
fn pattern_form(cells: &[(i32, i32, u8)]) -> Vec<(i32, i32, u8)> {
    let (r0, c0) = (cells.iter().map(|x| x.0).min().unwrap_or(0), cells.iter().map(|x| x.1).min().unwrap_or(0));
    let mut out: Vec<(i32, i32, u8)> = cells.iter().map(|x| (x.0 - r0, x.1 - c0, x.2)).collect();
    out.sort_unstable();
    out
}

/// The form of a colored pattern under each element of D4.
fn d4_forms(cells: &[(i32, i32, u8)]) -> Vec<Vec<(i32, i32, u8)>> {
    let form = pattern_form(cells);
    let (r1, c1) = (form.iter().map(|x| x.0).max().unwrap_or(0), form.iter().map(|x| x.1).max().unwrap_or(0));
    (0..8).map(|which| {
        let image: Vec<(i32, i32, u8)> = form.iter().map(|x| {
            let (r, c) = (x.0, x.1);
            let (y, z) = match which {
                0 => (r, c),
                1 => (r, c1 - c),
                2 => (r1 - r, c),
                3 => (r1 - r, c1 - c),
                4 => (c, r1 - r),
                5 => (c1 - c, r),
                6 => (c, r),
                _ => (c1 - c, r1 - r),
            };
            (y, z, x.2)
        }).collect();
        pattern_form(&image)
    }).collect()
}

/// `patterns by {g}`: the column's colored cells by a label column, against the output.
fn patterns(view: &mut View<'_>, pos: &Pos) {
    let t = view.t;
    let f = view.f;
    let output = &f.output;
    let p = pos.col;
    if t.rows > MAX_ROWS {
        return;
    }
    let extents: std::collections::BTreeSet<(i32, i32)> = (0..t.rows).map(|row| {
        let cell = t.at(row, p);
        (cell[0] + cell[1] + 1, cell[2] + cell[3] + 1)
    }).collect();
    if extents.len() != 1 {
        return;
    }
    let mut target: Vec<(i32, i32, u8)> = Vec::with_capacity(output.h * output.w);
    for r in 0..output.h {
        for c in 0..output.w {
            target.push((r as i32, c as i32, output.at(r, c)));
        }
    }
    // A pattern is the output up to rotation and reflection exactly when it is one of the output's images.
    let turned_targets = d4_forms(&target);
    let colors: Vec<Option<usize>> = std::iter::once(None).chain((0..t.kinds.len()).filter(|x| *x != p && t.kinds[*x] == Kind::Color).map(Some)).collect();
    for color in colors {
        if color.is_none() && !extents.contains(&(f.input.h as i32, f.input.w as i32)) {
            continue;
        }
        for g in 0..t.kinds.len() {
            if g == p || Some(g) == color || !(matches!(t.kinds[g], Kind::Ident | Kind::Position) || t.keys[g]) {
                continue;
            }
            let count = view.dense[g].1;
            if count < 2 {
                continue;
            }
            let ids = view.dense[g].0.clone();
            let mut held: Vec<Vec<(i32, i32, u8)>> = vec![Vec::new(); count as usize];
            let mut failed = false;
            for row in 0..t.rows {
                let cell = t.at(row, p);
                let value = match color {
                    None => {
                        let at = pos.at_input[row];
                        if at < 0 {
                            failed = true;
                            break;
                        }
                        f.input.color[at as usize]
                    }
                    Some(x) => t.at(row, x)[0] as u8,
                };
                held[ids[row] as usize].push((cell[0], cell[2], value));
            }
            if failed {
                continue;
            }
            for pattern in &mut held {
                pattern.sort_unstable();
                pattern.dedup();
            }
            if held.iter().any(|pattern| pattern.windows(2).any(|pair| pair[0].0 == pair[1].0 && pair[0].1 == pair[1].1)) || held.iter().map(Vec::len).sum::<usize>() > MAX_CELLS * 3 {
                continue;
            }
            let mut counts: std::collections::HashMap<Vec<(i32, i32, u8)>, u32> = std::collections::HashMap::new();
            for pattern in &held {
                *counts.entry(pattern_form(pattern)).or_insert(0) += 1;
            }
            let here = counts.get(&target).copied();
            let most = counts.values().copied().max().unwrap_or(0);
            let least = counts.values().copied().min().unwrap_or(0);
            let some = here.is_some();
            let top = here == Some(most) && counts.len() > 1;
            let bottom = here == Some(least) && counts.len() > 1;
            let names = if color.is_some() {
                ["C,C patterns by C some pattern is the output", "C,C patterns by C the most frequent pattern is the output", "C,C patterns by C the least frequent pattern is the output", "C,C patterns by C some pattern is the output up to rotation and reflection"]
            } else {
                ["C patterns by C some pattern is the output", "C patterns by C the most frequent pattern is the output", "C patterns by C the least frequent pattern is the output", "C patterns by C some pattern is the output up to rotation and reflection"]
            };
            let holes: Vec<usize> = color.map_or(vec![p, g], |x| vec![p, x, g]);
            view.put(names[0], &holes, Value::Bool(some));
            view.put(names[1], &holes, Value::Bool(top));
            view.put(names[2], &holes, Value::Bool(bottom));
            view.put(names[3], &holes, Value::Bool(turned_targets.iter().any(|form| counts.contains_key(form))));
        }
    }
}

/// The kinds that read a column's cells as shapes.
pub(crate) fn shape_kinds(view: &mut View<'_>, pos: &Pos, group_of: &[u32], groups: u32) {
    let t = view.t;
    let f = view.f;
    let output = &f.output;
    let p = pos.col;
    let list: Vec<(u8, u8)> = pos.places.iter().filter(|x| x.0 < 256 && x.1 < 256).map(|x| (x.0 as u8, x.1 as u8)).collect();
    if let Some(cells) = &output.foreground {
        if !cells.is_empty() {
            let theirs = {
                let mut out = Vec::with_capacity(cells.count() as usize);
                cells.each(|at| out.push(((at / output.w) as u8, (at % output.w) as u8)));
                out
            };
            view.put("C same shape as the output foreground", &[p], Value::Bool(list.len() == theirs.len() && normalized(&list) == normalized(&theirs)));
            if list.len() <= MAX_CELLS {
                view.put("C same shape up to rotation and reflection as the output foreground", &[p], Value::Bool(list.len() == theirs.len() && canon(&list) == canon(&theirs)));
            }
        }
    }
    if groups > 0 {
        let mut by_group: Vec<Vec<(u8, u8)>> = vec![Vec::new(); groups as usize];
        for row in 0..t.rows {
            let cell = t.at(row, p);
            by_group[group_of[row] as usize].push((cell[0] as u8, cell[2] as u8));
        }
        for held in &mut by_group {
            held.sort_unstable();
            held.dedup();
        }
        let total: usize = by_group.iter().map(Vec::len).sum();
        if !output.foreground_parts.is_empty() && total <= MAX_CELLS && groups <= MAX_GROUPS {
            let lists: Vec<Vec<(u8, u8)>> = output.foreground_parts.iter().map(|part| {
                let mut out = Vec::with_capacity(part.count() as usize);
                part.each(|at| out.push(((at / output.w) as u8, (at % output.w) as u8)));
                out
            }).collect();
            let relation = |form: &dyn Fn(&[(u8, u8)]) -> Vec<(u8, u8)>| -> &'static str {
                let mut a: Vec<Vec<(u8, u8)>> = by_group.iter().map(|g| form(g)).collect();
                let mut b: Vec<Vec<(u8, u8)>> = lists.iter().map(|g| form(g)).collect();
                a.sort();
                a.dedup();
                b.sort();
                b.dedup();
                let left = a.iter().any(|x| b.binary_search(x).is_err());
                let right = b.iter().any(|x| a.binary_search(x).is_err());
                let both = a.iter().any(|x| b.binary_search(x).is_ok());
                set_relation(left, right, both)
            };
            let exact = relation(&|g| normalized(g));
            let turned = relation(&|g| canon(g));
            view.put("C group shapes vs the output foreground component shapes", &[p], Value::Word(exact));
            view.put("C group shapes up to rotation and reflection vs the output foreground component shapes", &[p], Value::Word(turned));
        }
    }
    if pos.frame_input && pos.places.len() <= MAX_CELLS {
        let span = |places: &[(i32, i32)]| -> [i32; 4] {
            [places.iter().map(|x| x.0).min().unwrap_or(0), places.iter().map(|x| x.0).max().unwrap_or(0), places.iter().map(|x| x.1).min().unwrap_or(0), places.iter().map(|x| x.1).max().unwrap_or(0)]
        };
        let crops = crate::catalog_boxes::crop_tests(&[span(&pos.places)], f);
        view.put("C bounding box crop of the input is the output", &[p], Value::Bool(crops[0]));
        view.put("C bounding box crop of the input is the output up to rotation and reflection", &[p], Value::Bool(crops[1]));
        view.put("C bounding box crop of the input maps onto the output by a color map", &[p], Value::Bool(crops[2]));
    }
    if pos.frame_input && groups > 1 && !pos.set_input.is_empty() {
        let mut places: Vec<Vec<(i32, i32)>> = vec![Vec::new(); groups as usize];
        for row in 0..t.rows {
            let cell = t.at(row, p);
            places[group_of[row] as usize].push((cell[0], cell[2]));
        }
        let spans: Vec<[i32; 4]> = places.iter().map(|held| [held.iter().map(|x| x.0).min().unwrap_or(0), held.iter().map(|x| x.0).max().unwrap_or(0), held.iter().map(|x| x.1).min().unwrap_or(0), held.iter().map(|x| x.1).max().unwrap_or(0)]).collect();
        let crops = crate::catalog_boxes::crop_tests(&spans, f);
        view.put("C groups of its Ident, Color and key columns some group box crop of the input is the output", &[p], Value::Bool(crops[0]));
        view.put("C groups of its Ident, Color and key columns some group box crop of the input is the output up to rotation and reflection", &[p], Value::Bool(crops[1]));
    }
    patterns(view, pos);
    occurrences(view, pos, None);
    for x in 0..t.kinds.len() {
        if x != p && t.kinds[x] == Kind::Color {
            occurrences(view, pos, Some(x));
        }
    }
}

/// `occurs ...`: the column's cells by the table's Ident and key columns, each with a color.
fn occurrences(view: &mut View<'_>, pos: &Pos, color: Option<usize>) {
    let t = view.t;
    let f = view.f;
    let output = &f.output;
    let input = &f.input;
    let p = pos.col;
    if pos.places.len() > MAX_CELLS || (color.is_none() && !pos.frame_input) {
        return;
    }
    let id_columns: Vec<usize> = (0..t.kinds.len()).filter(|c| t.kinds[*c] == Kind::Ident || t.keys[*c]).collect();
    let mut group: Vec<u32> = vec![0; t.rows];
    let mut groups = 1;
    if !id_columns.is_empty() {
        let parts: Vec<&[u32]> = id_columns.iter().map(|c| view.dense[*c].0.as_slice()).collect();
        let (ids, count) = dense_over(&parts, t.rows);
        group = ids;
        groups = count;
    } else if let Some(x) = color {
        group.clone_from(&view.dense[x].0);
        groups = view.dense[x].1;
    }
    let mut patterns: Vec<Vec<PatternCell>> = vec![Vec::new(); groups as usize];
    for row in 0..t.rows {
        let cell = t.at(row, p);
        let held = match color {
            None => {
                let at = pos.at_input[row];
                if at < 0 {
                    return;
                }
                input.color[at as usize]
            }
            Some(x) => t.at(row, x)[0] as u8,
        };
        patterns[group[row] as usize].push((cell[0], cell[2], u32::from(held)));
    }
    let of = patterns.len() as u32;
    // Equal patterns are searched once, each with the number of groups that hold it.
    let (distinct, of_group) = distinct_patterns(patterns);
    if distinct.iter().any(|pattern| pattern.windows(2).any(|pair| pair[0].0 == pair[1].0 && pair[0].1 == pair[1].1)) {
        return;
    }
    let mut weights = vec![0u32; distinct.len()];
    for which in &of_group {
        weights[*which as usize] += 1;
    }
    let (mut in_place, mut elsewhere, mut turned) = (0u32, 0u32, 0u32);
    let mut common: Option<Vec<(i32, i32)>> = None;
    for (pattern, weight) in distinct.iter().zip(&weights) {
        let mut moves = crate::occurrence::moves(output, pattern);
        moves.sort_unstable();
        if moves.binary_search(&(0, 0)).is_ok() {
            in_place += weight;
        }
        let other = if pos.on_output { moves.iter().any(|m| *m != (0, 0)) } else { !moves.is_empty() };
        if other {
            elsewhere += weight;
        }
        // A one-cell pattern is its own image under every turn and reflection.
        if !moves.is_empty() || (pattern.len() > 1 && each_turned_image(pattern, extent_of(pattern), false, |_, image| !crate::occurrence::moves(output, image).is_empty())) {
            turned += weight;
        }
        common = Some(match common {
            None => moves,
            Some(held) => held.into_iter().filter(|m| moves.binary_search(m).is_ok()).collect(),
        });
    }
    let names = if color.is_some() {
        ["C,C occurs in the output in place, proportion", "C,C occurs elsewhere in the output, proportion", "C,C one translation takes them all into the output", "C,C occurs in the output up to rotation and reflection, proportion"]
    } else {
        ["C occurs in the output in place, proportion", "C occurs elsewhere in the output, proportion", "C one translation takes them all into the output", "C occurs in the output up to rotation and reflection, proportion"]
    };
    let holes: Vec<usize> = color.map_or(vec![p], |x| vec![p, x]);
    if pos.on_output {
        view.put(names[0], &holes, Value::Share(in_place, of));
    }
    view.put(names[1], &holes, Value::Share(elsewhere, of));
    if of >= 2 {
        let common = common.unwrap_or_default();
        let found = if pos.on_output { common.iter().any(|m| *m != (0, 0)) } else { !common.is_empty() };
        view.put(names[2], &holes, Value::Bool(found));
    }
    view.put(names[3], &holes, Value::Share(turned, of));
}
