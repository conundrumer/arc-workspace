//! The catalog's kinds over orientation columns and offsets.

use crate::catalog::*;
use crate::catalog_facts::*;

/// The values of a column of small codes, as a mask.
fn codes(t: &TableAt<'_>, column: usize) -> u32 {
    let mut mask = 0u32;
    for row in 0..t.rows {
        mask |= 1 << (t.at(row, column)[0] & 31);
    }
    mask
}

fn each_code(mask: u32) -> impl Iterator<Item = i32> {
    (0..32).filter(move |code| mask >> code & 1 == 1)
}

/// A direction's step as (row, column).
fn step(code: i32) -> (i32, i32) {
    match code {
        DIR_T => (-1, 0),
        DIR_B => (1, 0),
        DIR_L => (0, -1),
        DIR_R => (0, 1),
        DIAG_TL => (-1, -1),
        DIAG_TR => (-1, 1),
        DIAG_BL => (1, -1),
        _ => (1, 1),
    }
}

/// The line of an orientation.
fn line(code: i32) -> i32 {
    match code {
        DIR_T | DIR_B => AXIS_V,
        DIR_L | DIR_R => AXIS_H,
        DIAG_TL | DIAG_BR => DAXIS_DG,
        DIAG_TR | DIAG_BL => DAXIS_AD,
        other => other,
    }
}

/// How far a span goes toward a step, the larger the farther, one number per axis the step has.
fn reach(span: &[u8; 4], s: (i32, i32)) -> [Option<i32>; 2] {
    [
        (s.0 != 0).then(|| if s.0 > 0 { i32::from(span[1]) } else { -i32::from(span[0]) }),
        (s.1 != 0).then(|| if s.1 > 0 { i32::from(span[3]) } else { -i32::from(span[2]) }),
    ]
}

fn goes_past(ahead: &[u8; 4], behind: &[u8; 4], s: (i32, i32)) -> bool {
    reach(ahead, s).iter().zip(reach(behind, s).iter()).all(|(a, b)| match (a, b) {
        (Some(a), Some(b)) => a > b,
        _ => true,
    })
}

/// The reflection across the line along an axis, and the one that swaps the two directions on it.
fn reflections(code: i32) -> (i32, i32) {
    match code {
        AXIS_V => (D4_LR, D4_TB),
        AXIS_H => (D4_TB, D4_LR),
        DAXIS_DG => (D4_DG, D4_AD),
        _ => (D4_AD, D4_DG),
    }
}

/// An orientation column against the input alone.
pub(crate) fn input_lines(view: &mut View<'_>, d: usize) {
    let t = view.t;
    let g = &view.f.input;
    let kind = t.kinds[d];
    let values: Vec<i32> = each_code(codes(t, d)).collect();
    if matches!(kind, Kind::Dir | Kind::Dir8) {
        let edges: Vec<i32> = values.iter().copied().filter(|code| matches!(*code, DIR_T | DIR_B | DIR_L | DIR_R)).collect();
        if !edges.is_empty() {
            let of = edges.len() as u32;
            let (h, w) = (g.h, g.w);
            let one_color = |code: i32| match code {
                DIR_T => g.line_colors[0][0],
                DIR_B => g.line_colors[0][h - 1],
                DIR_L => g.line_colors[1][0],
                _ => g.line_colors[1][w - 1],
            }.count_ones() == 1;
            view.put("C the input edge toward it is one color, proportion", &[d], Value::Share(edges.iter().filter(|code| one_color(**code)).count() as u32, of));
            if let Some(span) = g.foreground.as_ref().and_then(|cells| span_of(cells, w)) {
                let touches = |code: i32| match code {
                    DIR_T => span[0] == 0,
                    DIR_B => usize::from(span[1]) == h - 1,
                    DIR_L => span[2] == 0,
                    _ => usize::from(span[3]) == w - 1,
                };
                view.put("C the input foreground touches the edge toward it, proportion", &[d], Value::Share(edges.iter().filter(|code| touches(**code)).count() as u32, of));
            }
        }
    }
    if matches!(kind, Kind::Axis | Kind::DiagAxis | Kind::Axis4) {
        if !values.is_empty() {
            let cells = (g.h * g.w) as u32;
            let of = values.len() as u32 * cells;
            let kept = |pick: &dyn Fn((i32, i32)) -> i32| values.iter().map(|code| image_agreement(g, (pick(reflections(*code)) - D4_ID) as usize)).sum::<u32>();
            view.put("C the input agrees with itself under the reflection across it, mean", &[d], Value::Share(kept(&|pair| pair.0), of));
            view.put("C the input agrees with itself under the reflection that swaps it, mean", &[d], Value::Share(kept(&|pair| pair.1), of));
        }
        let straight: Vec<i32> = values.iter().copied().filter(|code| *code == AXIS_V || *code == AXIS_H).collect();
        if !straight.is_empty() {
            let of = straight.len() as u32;
            let longer = |height: usize, width: usize| straight.iter().filter(|code| if **code == AXIS_V { height > width } else { width > height }).count() as u32;
            view.put("C the longer side of the input lies along it, proportion", &[d], Value::Share(longer(g.h, g.w), of));
            if let Some(span) = g.foreground.as_ref().and_then(|cells| span_of(cells, g.w)) {
                view.put("C the longer side of the input foreground lies along it, proportion", &[d], Value::Share(longer(usize::from(span[1] - span[0]), usize::from(span[3] - span[2])), of));
            }
        }
    }
}

/// A column of symmetries against the input alone.
pub(crate) fn input_turns(view: &mut View<'_>, d: usize) {
    let t = view.t;
    let g = &view.f.input;
    let values: Vec<i32> = each_code(codes(t, d)).filter(|code| (D4_ID..=D4_AD).contains(code)).collect();
    if !values.is_empty() {
        let kept = values.iter().map(|code| image_agreement(g, (*code - D4_ID) as usize)).sum::<u32>();
        view.put("C the input agrees with itself under it, mean", &[d], Value::Share(kept, values.len() as u32 * (g.h * g.w) as u32));
    }
}

pub(crate) fn line_column(view: &mut View<'_>, d: usize) {
    let t = view.t;
    let f = view.f;
    let kind = t.kinds[d];
    let mask = codes(t, d);
    let values: Vec<i32> = each_code(mask).collect();
    let of = values.len() as u32;
    if matches!(kind, Kind::Dir | Kind::DiagDir | Kind::Dir8) {
        let input_span = f.input.foreground.as_ref().and_then(|cells| span_of(cells, f.input.w));
        let output_span = f.output.foreground.as_ref().and_then(|cells| span_of(cells, f.output.w));
        if let (Some(changed), Some(behind)) = (f.changed_span, input_span) {
            let hits = values.iter().filter(|code| goes_past(&changed, &behind, step(**code))).count() as u32;
            view.put("C the changed cells reach past the input foreground toward it, proportion", &[d], share(hits, of));
        }
        if let (true, Some(ahead), Some(behind)) = (f.same, output_span, input_span) {
            let hits = values.iter().filter(|code| goes_past(&ahead, &behind, step(**code))).count() as u32;
            view.put("C the output foreground reaches past the input foreground toward it, proportion", &[d], share(hits, of));
            let delta = (i32::from(ahead[0]) + i32::from(ahead[1]) - i32::from(behind[0]) - i32::from(behind[1]), i32::from(ahead[2]) + i32::from(ahead[3]) - i32::from(behind[2]) - i32::from(behind[3]));
            let moves = values.iter().filter(|code| {
                let s = step(**code);
                (s.0 == 0 || delta.0 * s.0 > 0) && (s.1 == 0 || delta.1 * s.1 > 0)
            }).count() as u32;
            view.put("C the output foreground moves toward it, proportion", &[d], share(moves, of));
        }
        if let Some(cells) = &f.output.foreground {
            if !cells.is_empty() {
                let straight: Vec<i32> = values.iter().copied().filter(|code| *code <= DIR_R).collect();
                if !straight.is_empty() {
                    let (h, w) = (f.output.h as i32, f.output.w as i32);
                    let hits = straight.iter().filter(|code| {
                        let s = step(**code);
                        let mut stable = true;
                        cells.each(|at| {
                            let (r, c) = ((at / f.output.w) as i32 + s.0, (at % f.output.w) as i32 + s.1);
                            if r >= 0 && c >= 0 && r < h && c < w && !cells.get((r * w + c) as usize) {
                                stable = false;
                            }
                        });
                        stable
                    }).count() as u32;
                    view.put("C the output foreground is stable under gravity toward it, proportion", &[d], share(hits, straight.len() as u32));
                }
            }
        }
    }
    let lines = values.iter().fold(0u32, |held, code| held | 1 << line(*code));
    let (vertical, horizontal) = (lines >> AXIS_V & 1 == 1, lines >> AXIS_H & 1 == 1);
    if vertical || horizontal {
        let along_v = compare(f.output.h as i64, f.input.h as i64);
        let along_h = compare(f.output.w as i64, f.input.w as i64);
        let word = match (vertical, horizontal) {
            (true, true) => if along_v == along_h { along_v } else { "mixed" },
            (true, false) => along_v,
            _ => along_h,
        };
        view.put("C the output extent along it vs the input", &[d], Value::Word(word));
    }
    let square = f.output.h == f.output.w;
    let usable: Vec<i32> = each_code(lines).filter(|code| *code == AXIS_V || *code == AXIS_H || square).collect();
    if !usable.is_empty() {
        let across = |code: i32| match code {
            AXIS_V => D4_LR,
            AXIS_H => D4_TB,
            DAXIS_DG => D4_DG,
            _ => D4_AD,
        };
        let swaps = |code: i32| match code {
            AXIS_V => D4_TB,
            AXIS_H => D4_LR,
            DAXIS_DG => D4_AD,
            _ => D4_DG,
        };
        let of = usable.len() as u32;
        let first = usable.iter().filter(|code| f.keeps[(across(**code) - D4_ID) as usize]).count() as u32;
        let second = usable.iter().filter(|code| f.keeps[(swaps(**code) - D4_ID) as usize]).count() as u32;
        view.put("C the output is unchanged by the reflection across it, proportion", &[d], Value::Share(first, of));
        view.put("C the output is unchanged by the reflection that swaps it, proportion", &[d], Value::Share(second, of));
    }
    // The pairs of an orientation and a number.
    if matches!(kind, Kind::Axis | Kind::Dir) {
        for n in 0..t.kinds.len() {
            if !matches!(t.kinds[n], Kind::Nat | Kind::Int) {
                continue;
            }
            let mut pairs: Vec<(i32, i32)> = (0..t.rows).map(|row| (t.at(row, d)[0], t.at(row, n)[0])).collect();
            pairs.sort_unstable();
            pairs.dedup();
            let of = pairs.len() as u32;
            let extent = pairs.iter().filter(|(code, value)| i64::from(*value) == if line(*code) == AXIS_V { f.output.h as i64 } else { f.output.w as i64 }).count() as u32;
            view.put("C,C is the output extent along it, proportion", &[d, n], share(extent, of));
            if kind == Kind::Dir {
                let margin = |span: &[u8; 4], code: i32| -> i32 {
                    match code {
                        DIR_T => i32::from(span[0]),
                        DIR_B => f.output.h as i32 - 1 - i32::from(span[1]),
                        DIR_L => i32::from(span[2]),
                        _ => f.output.w as i32 - 1 - i32::from(span[3]),
                    }
                };
                if let Some(span) = f.output.foreground.as_ref().and_then(|cells| span_of(cells, f.output.w)) {
                    let hits = pairs.iter().filter(|(code, value)| margin(&span, *code) == *value).count() as u32;
                    view.put("C,C is the output foreground margin toward it, proportion", &[d, n], share(hits, of));
                }
                if let Some(span) = f.changed_span {
                    let hits = pairs.iter().filter(|(code, value)| margin(&span, *code) == *value).count() as u32;
                    view.put("C,C is the changed cells margin toward it, proportion", &[d, n], share(hits, of));
                }
            }
        }
    }
}

pub(crate) fn turn_column(view: &mut View<'_>, d: usize) {
    let t = view.t;
    let f = view.f;
    let values: Vec<i32> = each_code(codes(t, d)).filter(|code| (D4_ID..=D4_AD).contains(code)).collect();
    let of = values.len() as u32;
    let maps = values.iter().filter(|code| f.maps[(**code - D4_ID) as usize]).count() as u32;
    let keeps = values.iter().filter(|code| f.keeps[(**code - D4_ID) as usize]).count() as u32;
    view.put("C maps the input to the output, proportion", &[d], share(maps, of));
    view.put("C keeps the output, proportion", &[d], share(keeps, of));
    // The input's foreground under each element, against the output's, up to a move.
    if let (Some(input), Some(output)) = (&f.input.foreground, &f.output.foreground) {
        if !input.is_empty() && !output.is_empty() {
            let list = |cells: &Bits, w: usize| {
                let mut out = Vec::with_capacity(cells.count() as usize);
                cells.each(|at| out.push(((at / w) as u8, (at % w) as u8)));
                out
            };
            let want = normalized(&list(output, f.output.w));
            let held = list(input, f.input.w);
            let (hi, wi) = (f.input.h as i32, f.input.w as i32);
            let hits = values.iter().filter(|code| {
                let image: Vec<(u8, u8)> = held.iter().map(|cell| {
                    let (r, c) = (i32::from(cell.0), i32::from(cell.1));
                    let (y, z) = match **code {
                        D4_ID => (r, c),
                        D4_LR => (r, wi - 1 - c),
                        D4_TB => (hi - 1 - r, c),
                        D4_HT => (hi - 1 - r, wi - 1 - c),
                        D4_CW => (c, hi - 1 - r),
                        D4_CC => (wi - 1 - c, r),
                        D4_DG => (c, r),
                        _ => (wi - 1 - c, hi - 1 - r),
                    };
                    (y as u8, z as u8)
                }).collect();
                normalized(&image) == want
            }).count() as u32;
            view.put("C maps the input foreground shape to the output foreground shape, proportion", &[d], share(hits, of));
        }
    }
}

pub(crate) fn offset_column(view: &mut View<'_>, d: usize) {
    let t = view.t;
    let f = view.f;
    let (Some(input), Some(output)) = (&f.input.foreground, &f.output.foreground) else { return };
    if !f.same || input.is_empty() || output.is_empty() {
        return;
    }
    let mut moves: Vec<(i32, i32)> = (0..t.rows).map(|row| {
        let cell = t.at(row, d);
        (cell[0], cell[2])
    }).collect();
    moves.sort_unstable();
    moves.dedup();
    let (h, w) = (f.output.h as i32, f.output.w as i32);
    let width = f.output.w;
    let takes = |dr: i32, dc: i32| -> bool {
        if input.count() != output.count() {
            return false;
        }
        let mut holds = true;
        input.each(|at| {
            let (r, c) = ((at / width) as i32 + dr, (at % width) as i32 + dc);
            if r < 0 || c < 0 || r >= h || c >= w || !output.get((r * w + c) as usize) {
                holds = false;
            }
        });
        holds
    };
    let hits = moves.iter().filter(|(dr, dc)| takes(*dr, *dc)).count() as u32;
    view.put("C translates the input foreground onto the output foreground, proportion", &[d], share(hits, moves.len() as u32));
    let span_in = span_of(input, width);
    let span_out = span_of(output, width);
    if let (Some(a), Some(b)) = (span_in, span_out) {
        let (dr, dc) = (i32::from(b[0]) - i32::from(a[0]), i32::from(b[2]) - i32::from(a[2]));
        if input.count() == output.count() && takes(dr, dc) {
            view.put("C includes the translation of the foreground into the output", &[d], Value::Bool(moves.contains(&(dr, dc))));
        }
    }
}
