//! The catalog's kinds over Box columns. A box's frame is the input's.

use crate::catalog::*;
use crate::catalog_facts::*;

/// A box as first row, last row, first column and last column.
type Span = [i32; 4];

pub(crate) fn crop_tests(spans: &[[i32; 4]], f: &PairFacts) -> [bool; 3] {
    let (input, output) = (&f.input, &f.output);
    let (mut exact, mut turned, mut mapped) = (false, false, false);
    for span in spans {
        if exact && turned && mapped {
            break;
        }
        let [r0, r1, c0, c1] = *span;
        if !(0 <= r0 && r0 <= r1 && (r1 as usize) < input.h && 0 <= c0 && c0 <= c1 && (c1 as usize) < input.w) {
            continue;
        }
        let (h, w) = ((r1 - r0 + 1) as usize, (c1 - c0 + 1) as usize);
        let at = |r: usize, c: usize| input.at(r0 as usize + r, c0 as usize + c);
        if (h, w) == (output.h, output.w) {
            // A test that an earlier box already met is not read again, and the read stops where neither test can hold.
            let (mut same, mut function) = (!exact, !mapped);
            let mut map = [255u8; 10];
            'cells: for r in 0..h {
                for c in 0..w {
                    let (from, to) = (at(r, c), output.at(r, c));
                    same &= from == to;
                    if function {
                        let held = &mut map[from as usize];
                        if *held == 255 {
                            *held = to;
                        } else if *held != to {
                            function = false;
                        }
                    }
                    if !same && !function {
                        break 'cells;
                    }
                }
            }
            exact |= same;
            mapped |= function;
        }
        if !turned && ((h, w) == (output.h, output.w) || (h, w) == (output.w, output.h)) {
            turned = (0..8).any(|which| {
                let (ih, iw) = if which >= 4 { (w, h) } else { (h, w) };
                (ih, iw) == (output.h, output.w) && (0..ih).all(|r| (0..iw).all(|c| {
                    let (sr, sc) = image_source(which, r, c, h, w);
                    at(sr, sc) == output.at(r, c)
                }))
            });
        }
    }
    [exact, turned, mapped]
}

/// The cell of an h by w grid that the image `which` puts at (r, c).
pub(crate) fn image_source(which: usize, r: usize, c: usize, h: usize, w: usize) -> (usize, usize) {
    match which {
        0 => (r, c),
        1 => (r, w - 1 - c),
        2 => (h - 1 - r, c),
        3 => (h - 1 - r, w - 1 - c),
        4 => (c, r),
        5 => (h - 1 - c, r),
        6 => (c, w - 1 - r),
        _ => (h - 1 - c, w - 1 - r),
    }
}

/// A column's frame against the input's size, where its values are the cells of one frame.
pub(crate) fn input_frames(view: &mut View<'_>, col: usize) {
    let t = view.t;
    let g = &view.f.input;
    let first = t.at(0, col);
    let (h, w) = (first[0] + first[1] + 1, first[2] + first[3] + 1);
    let position = t.kinds[col] == Kind::Position;
    if h <= 0 || w <= 0 || !(0..t.rows).all(|row| {
        let m = t.at(row, col);
        m[0] + m[1] + 1 == h && m[2] + m[3] + 1 == w && (position || m.iter().all(|margin| *margin >= 0))
    }) {
        return;
    }
    let (hi, wi) = (g.h as i32, g.w as i32);
    view.put("C frame proportion of the input", &[col], Value::Share((h * w) as u32, (hi * wi) as u32));
    view.put("C frame divides the input size", &[col], Value::Bool((h, w) != (hi, wi) && hi % h == 0 && wi % w == 0));
}

/// The boxes that lie wholly in the input and whose border is one of its colors.
pub(crate) fn input_borders(view: &mut View<'_>, b: usize) {
    let t = view.t;
    let g = &view.f.input;
    let (h, w) = (g.h as i32, g.w as i32);
    let mut spans: Vec<Span> = (0..t.rows).map(|row| {
        let cell = t.at(row, b);
        [cell[0], h - 1 - cell[1], cell[2], w - 1 - cell[3]]
    }).collect();
    spans.sort_unstable();
    spans.dedup();
    spans.retain(|s| 0 <= s[0] && s[0] <= s[1] && s[1] < h && 0 <= s[2] && s[2] <= s[3] && s[3] < w);
    if spans.is_empty() {
        return;
    }
    let one = spans.iter().filter(|s| {
        let [r0, r1, c0, c1] = s.map(|at| at as usize);
        (g.colors_in(r0, r0, c0, c1) | g.colors_in(r1, r1, c0, c1) | g.colors_in(r0, r1, c0, c0) | g.colors_in(r0, r1, c1, c1)).count_ones() == 1
    }).count() as u32;
    view.put("C boxes whose border is one input color, proportion", &[b], Value::Share(one, spans.len() as u32));
}

pub(crate) fn box_column(view: &mut View<'_>, b: usize) {
    let t = view.t;
    let f = view.f;
    let output = &f.output;
    let (hi, wi) = (f.input.h as i32, f.input.w as i32);
    let mut spans: Vec<Span> = (0..t.rows).map(|row| {
        let cell = t.at(row, b);
        [cell[0], hi - 1 - cell[1], cell[2], wi - 1 - cell[3]]
    }).collect();
    let by_row = spans.clone();
    spans.sort_unstable();
    spans.dedup();
    // `some box has the output size` reads every box.
    let sized = spans.iter().any(|span| ((span[1] - span[0] + 1) as usize, (span[3] - span[2] + 1) as usize) == (output.h, output.w));
    view.put("C some box has the output size", &[b], Value::Bool(sized));
    let crops = crop_tests(&spans, f);
    view.put("C some box crop of the input is the output", &[b], Value::Bool(crops[0]));
    view.put("C some box crop of the input is the output up to rotation and reflection", &[b], Value::Bool(crops[1]));
    view.put("C some box crop of the input maps onto the output by a color map", &[b], Value::Bool(crops[2]));
    if !f.same {
        return;
    }
    let (h, w) = (output.h as i32, output.w as i32);
    let mut piece_spans: Vec<Span> = output.pieces.iter().map(|piece| piece.span.map(i32::from)).collect();
    piece_spans.sort_unstable();
    let hits = spans.iter().filter(|span| piece_spans.binary_search(span).is_ok()).count() as u32;
    view.put("C boxes that are the box of a component in the output, proportion", &[b], share(hits, spans.len() as u32));
    // Each box cut to the grid.
    let cut = |span: &Span| -> Option<[usize; 4]> {
        let (r0, r1, c0, c1) = (span[0].max(0), span[1].min(h - 1), span[2].max(0), span[3].min(w - 1));
        (r0 <= r1 && c0 <= c1).then_some([r0 as usize, r1 as usize, c0 as usize, c1 as usize])
    };
    let real: Vec<[usize; 4]> = spans.iter().filter_map(cut).collect();
    if real.is_empty() {
        return;
    }
    let colors: Vec<u16> = real.iter().map(|s| output.colors_in(s[0], s[1], s[2], s[3])).collect();
    let one = colors.iter().filter(|mask| mask.count_ones() == 1).count() as u32;
    view.put("C boxes of one output color, proportion", &[b], Value::Share(one, real.len() as u32));
    view.put("C output colors inside its boxes distinct", &[b], Value::Num(i64::from(colors.iter().fold(0u16, |held, mask| held | mask).count_ones())));
    if !f.changed.is_empty() {
        let width = output.w;
        let columns = width + 1;
        // The changed cells over the rectangles from the top left, and the number of boxes that cover each cell, both by prefix sums.
        let mut changed_to = vec![0u32; (output.h + 1) * columns];
        let mut covered_by = vec![0i32; (output.h + 1) * columns];
        f.changed.each(|at| changed_to[(at / width + 1) * columns + at % width + 1] += 1);
        for s in &real {
            covered_by[s[0] * columns + s[2]] += 1;
            covered_by[s[0] * columns + s[3] + 1] -= 1;
            covered_by[(s[1] + 1) * columns + s[2]] -= 1;
            covered_by[(s[1] + 1) * columns + s[3] + 1] += 1;
        }
        for r in 0..=output.h {
            for c in 0..=width {
                let at = r * columns + c;
                if r > 0 {
                    changed_to[at] += changed_to[at - columns];
                    covered_by[at] += covered_by[at - columns];
                }
                if c > 0 {
                    changed_to[at] += changed_to[at - 1];
                    covered_by[at] += covered_by[at - 1];
                    if r > 0 {
                        changed_to[at] -= changed_to[at - columns - 1];
                        covered_by[at] -= covered_by[at - columns - 1];
                    }
                }
            }
        }
        let holding = real.iter().filter(|s| changed_to[(s[1] + 1) * columns + s[3] + 1] + changed_to[s[0] * columns + s[2]] > changed_to[s[0] * columns + s[3] + 1] + changed_to[(s[1] + 1) * columns + s[2]]).count() as u32;
        let mut inside = 0;
        f.changed.each(|at| inside += u32::from(covered_by[(at / width) * columns + at % width] > 0));
        view.put("C changed cells inside its boxes, proportion", &[b], Value::Share(inside, f.changed.count()));
        view.put("C boxes holding a changed cell, proportion", &[b], Value::Share(holding, real.len() as u32));
        if let Some(span) = f.changed_span {
            let whole = [span[0] as usize, span[1] as usize, span[2] as usize, span[3] as usize];
            view.put("C some box is the box of the changed cells", &[b], Value::Bool(real.contains(&whole)));
        }
    }
    let box_colors = |span: &Span| -> u16 { cut(span).map_or(0, |s| output.colors_in(s[0], s[1], s[2], s[3])) };
    let row_colors: Vec<u16> = by_row.iter().map(box_colors).collect();
    for other in 0..t.kinds.len() {
        if other == b {
            continue;
        }
        let (ids, count) = &view.dense[other];
        let mut first: Vec<Option<u16>> = vec![None; *count as usize];
        let mut function = true;
        for row in 0..t.rows {
            let held = &mut first[ids[row] as usize];
            match held {
                None => *held = Some(row_colors[row]),
                Some(mask) => function &= *mask == row_colors[row],
            }
        }
        view.put("C,C determines the output colors in the box", &[b, other], Value::Bool(function));
        if t.kinds[other] == Kind::Color {
            let hits = (0..t.rows).filter(|row| {
                let value = t.at(*row, other)[0];
                (0..10).contains(&value) && row_colors[*row] == 1 << value
            }).count() as u32;
            view.put("C,C is the output color of the box, proportion", &[b, other], Value::Share(hits, t.rows as u32));
        }
    }
}
