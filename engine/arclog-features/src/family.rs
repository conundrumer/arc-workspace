//! The feature families that read the rows of the table's examples in detail.
//! Each takes the summaries of the groups of rows (`summary.rs`) and combines
//! them, in the order of the examples, with the train pairs.

use crate::cells::{both, index_in};
use crate::group::{merged, RowSet};
use crate::pair::{CHANGED, FG, OFG};
use crate::summary::{CellsSummary, ColorSummary, PaintSummary, SuitSummary, ValueSet};
use crate::{Examples, FIT, OUT, SUIT_COLUMNS};

/// The train groups, without those that repeat the rows of an earlier group.
pub(crate) struct Uniques {
    /// For each train group, the place in `groups` of the first group with the same rows.
    pub place: Vec<usize>,
    /// The first group of each set of rows.
    pub groups: Vec<usize>,
}

/// The most groups of rows in order that are merged to count the distinct rows; more are counted by hash.
const MERGED_UP_TO: usize = 4;

/// A group of fewer rows than this is not compared with the others for equal rows.
const COMPARED_FROM: usize = 16;

impl<'a> Examples<'a> {
    /// The end of the groups of the train examples in `groups`.
    fn train_groups_end(&self) -> usize {
        self.train_ex.last().map_or(0, |range| range.end)
    }

    /// The train groups by their rows. A summary of a group depends on its rows alone, so it is made once for the groups that
    /// share their rows.
    pub(crate) fn uniques(&self) -> &Uniques {
        self.uniques.get_or_init(|| {
            let mut found = Uniques { place: Vec::new(), groups: Vec::new() };
            for group in 0..self.train_groups_end() {
                let same = if self.groups[group].len() >= COMPARED_FROM { found.groups.iter().position(|&held| self.groups[held].same_rows_as(&self.groups[group])) } else { None };
                match same {
                    Some(at) => {
                        self.groups[group].share_distinct(&self.groups[found.groups[at]]);
                        found.place.push(at)
                    }
                    None => {
                        found.place.push(found.groups.len());
                        found.groups.push(group);
                    }
                }
            }
            found
        })
    }

    /// The cells of each Position column over each unique train group: the cells of the unique group `u` at the Position
    /// column number `k` are the entry `u * position_at.len() + k`.
    pub(crate) fn cell_summaries(&self) -> &[CellsSummary] {
        self.cell_summaries.get_or_init(|| {
            self.uniques().groups.iter().flat_map(|&group| self.position_at.iter().map(move |&at| (group, at))).map(|(group, at)| CellsSummary::of(&self.groups[group], at)).collect()
        })
    }

    /// `const_cols`, `live_cols`, `distinct_min`, `distinct_max` and `row_distinct`, over the rows of all train examples. The
    /// group of rows that the columns are summarized over is the distinct rows of all train examples.
    pub(crate) fn columns_of(&self) -> Option<[f32; 5]> {
        if self.n_train == 0 {
            return None;
        }
        let train = &self.groups[..self.train_groups_end()];
        let count: usize = train.iter().map(|group| group.len()).sum();
        if count == 0 || self.names.is_empty() {
            return None;
        }
        let unique = &self.uniques().groups;
        let rows: Vec<&[i32]> = if let [only] = unique[..] {
            // The rows of one group are distinct already.
            let mut rows = Vec::with_capacity(self.groups[only].distinct_count());
            self.groups[only].each_distinct(|row, _| rows.push(row));
            rows
        } else if unique.len() <= MERGED_UP_TO && unique.iter().all(|&group| self.groups[group].is_sorted()) {
            // Groups with rows in order merge into one list in order.
            let list = |group: usize| {
                let mut rows = Vec::with_capacity(self.groups[group].len());
                self.groups[group].each_distinct(|row, _| rows.push(row));
                rows
            };
            unique[1..].iter().fold(list(unique[0]), |held, &group| merged(&held, &list(group)))
        } else {
            let mut set = RowSet::new(unique.iter().map(|&group| self.groups[group].distinct_count()).sum());
            for &group in unique {
                self.groups[group].each_hashed(|hash, row| set.insert(hash, row));
            }
            set.into_rows()
        };
        let distinct: Vec<usize> = self.columns_at.iter().map(|&(at, width)| ValueSet::of(&rows, at, width).len()).collect();
        let constant = distinct.iter().filter(|&&n| n <= 1).count();
        Some([constant as f32, (distinct.len() - constant) as f32, *distinct.iter().min().unwrap() as f32, *distinct.iter().max().unwrap() as f32, (rows.len() as f64 / count as f64) as f32])
    }

    /// Whether the cells are all the cells of one color of the input.
    fn is_input_color(summary: &CellsSummary, pair: &crate::Pair) -> bool {
        let heavy = pair.heavy();
        let input = &pair.input;
        let mut cells: Vec<(i32, i32)> = Vec::new();
        let first = summary.frame.iter().position(|&bits| bits != 0).map(|row| (row as i32, summary.frame[row].trailing_zeros() as i32));
        let Some((i, j)) = first.or_else(|| summary.far.first().map(|&cell| crate::cells::unpack(cell))) else { return false };
        let Some(at) = index_in(i, j, input.height, input.width) else { return false };
        let color = heavy.in_color[at];
        if heavy.color_count[color as usize] != summary.len {
            return false;
        }
        // The cells in the corner are all of that color, and none of that color is outside the cells.
        if summary.frame.iter().zip(&heavy.color_frames[color as usize]).any(|(cells, of_color)| cells & !of_color != 0) {
            return false;
        }
        cells.extend(summary.far.iter().map(|&cell| crate::cells::unpack(cell)));
        cells.iter().all(|&(i, j)| index_in(i, j, input.height, input.width).is_some_and(|at| heavy.in_color[at] == color))
    }

    /// The features against the train pairs: `rows_per_area`, `rows_eq_changed`, `rows_eq_ofg`, `color_in_out`, `color_new`,
    /// `color_one`, then `cover`, `fg_share`, `ofg_share`, `iou_changed`, `prec_changed`, `rec_changed`, `iou_ofg`,
    /// `is_input_color`, `shape_in`, `shape_out`, `shape_live`, `shape_both_live`. Each is the mean over the train
    /// examples that have rows of the mean over the example's TableRows with rows (and over the columns it reads).
    pub(crate) fn fit_of(&self) -> [f32; FIT] {
        let mut total = [(0.0f64, 0usize); FIT];
        if self.n_train == 0 {
            return [0.0; FIT];
        }
        let positions = self.position_at.len();
        let uniques = self.uniques();
        // The Color columns over each unique group.
        let colors: Vec<ColorSummary> = uniques.groups.iter().flat_map(|&group| self.color_at.iter().map(move |&at| (group, at))).map(|(group, at)| ColorSummary::of(&self.groups[group], at)).collect();
        for (groups, whole) in self.train_ex.iter().zip(self.pairs) {
            let pair = whole.facts();
            let mut own = [(0.0f64, 0usize); FIT];
            let mut add = |place: usize, value: f64| {
                own[place].0 += value;
                own[place].1 += 1;
            };
            for group in groups.clone().filter(|&group| !self.groups[group].is_empty()) {
                let rows = &self.groups[group];
                let distinct = rows.distinct_count();
                add(0, rows.len() as f64 / pair.area.max(1) as f64);
                add(1, f64::from(pair.same && distinct == pair.changed));
                add(2, f64::from(distinct == pair.ofg));
                for k in 0..self.color_at.len() {
                    let colors = &colors[uniques.place[group] * self.color_at.len() + k];
                    add(3, (colors.mask & pair.ocolors).count_ones() as f64 / colors.distinct().max(1) as f64);
                    add(4, f64::from(colors.mask & pair.newcolors != 0));
                    add(5, f64::from(colors.distinct() == 1));
                }
                for k in 0..positions {
                    let summary = &self.cell_summaries()[uniques.place[group] * positions + k];
                    let heavy = whole.heavy();
                    let size = summary.len as f64;
                    let (input, output) = (&whole.input, &whole.output);
                    let mut fg = both(&summary.frame, &heavy.fg_frame);
                    let mut changed = both(&summary.frame, &heavy.changed_frame);
                    let mut ofg = both(&summary.frame, &heavy.ofg_frame);
                    for &cell in &summary.far {
                        let (i, j) = crate::cells::unpack(cell);
                        if let Some(at) = index_in(i, j, input.height, input.width) {
                            fg += usize::from(heavy.in_flags[at] & FG != 0);
                            changed += usize::from(heavy.in_flags[at] & CHANGED != 0);
                        }
                        if let Some(at) = index_in(i, j, output.height, output.width) {
                            ofg += usize::from(heavy.out_flags[at] & OFG != 0);
                        }
                    }
                    add(6, size / pair.area.max(1) as f64);
                    add(7, fg as f64 / size);
                    add(8, ofg as f64 / size);
                    if pair.same {
                        let with_changed = changed as f64;
                        let union = summary.len + heavy.changed_len - changed;
                        add(9, if union > 0 { with_changed / union as f64 } else { 0.0 });
                        add(10, with_changed / size);
                        add(11, with_changed / heavy.changed_len.max(1) as f64);
                        let union = summary.len + heavy.ofg_len - ofg;
                        add(12, if union > 0 { ofg as f64 / union as f64 } else { 0.0 });
                    }
                    add(13, f64::from(Self::is_input_color(summary, whole)));
                    let (mut in_input, mut in_output, mut in_live, mut in_both) = (false, false, false, false);
                    if !(heavy.nin.is_empty() && heavy.nout.is_empty()) {
                        for shape in summary.shapes().iter().filter(|shape| shape.len() as f64 <= 0.6 * pair.area as f64) {
                            let (a, b, c) = (heavy.nin.contains(shape), heavy.nout.contains(shape), heavy.live.contains(shape));
                            in_input |= a;
                            in_output |= b;
                            in_live |= c;
                            in_both |= c && a;
                        }
                    }
                    add(14, f64::from(in_input));
                    add(15, f64::from(in_output));
                    add(16, f64::from(in_live));
                    add(17, f64::from(in_both));
                }
            }
            for (sum, (value, count)) in total.iter_mut().zip(own) {
                if count > 0 {
                    sum.0 += value / count as f64;
                    sum.1 += 1;
                }
            }
        }
        total.map(|(sum, count)| if count == 0 { 0.0 } else { (sum / count as f64) as f32 })
    }

    /// The best mean overlap with the train outputs over the pairs of a Position or Box column (the first `SUIT_COLUMNS`)
    /// and a Color column (the first `SUIT_COLUMNS`). On a train example, the overlap with that example's output; on a
    /// task-level table, the mean over the train outputs. An example with no rows counts 0, and so does an empty TableRows.
    pub(crate) fn suit_of(&self) -> f32 {
        let ps: Vec<usize> = self.grid_at.iter().copied().take(SUIT_COLUMNS).collect();
        let cs: Vec<usize> = self.color_at.iter().copied().take(SUIT_COLUMNS).collect();
        if ps.is_empty() && cs.is_empty() || self.pairs.is_empty() {
            return 0.0;
        }
        let masks: Vec<_> = self.pairs.iter().map(|pair| pair.masks()).collect();
        let sites: Vec<(Option<usize>, Option<usize>)> = if ps.is_empty() {
            cs.iter().map(|&c| (None, Some(c))).collect()
        } else if cs.is_empty() {
            ps.iter().map(|&p| (Some(p), None)).collect()
        } else {
            ps.iter().flat_map(|&p| cs.iter().map(move |&c| (Some(p), Some(c)))).collect()
        };
        let mut best = 0.0f64;
        for (p, c) in sites {
            let uniques = self.uniques();
            let unique_summaries: Vec<SuitSummary> = uniques.groups.iter().map(|&group| SuitSummary::of(&self.groups[group], p, c)).collect();
            let summaries: Vec<&SuitSummary> = uniques.place.iter().map(|&at| &unique_summaries[at]).collect();
            let mut examples = 0.0f64;
            for (index, groups) in self.train_ex.iter().enumerate() {
                let mut sum = 0.0f64;
                for group in groups.clone() {
                    sum += if self.task_level {
                        masks.iter().fold(0.0f64, |sum, mask| sum + mask.overlap(summaries[group])) / masks.len() as f64
                    } else {
                        masks[index].overlap(summaries[group])
                    };
                }
                examples += if groups.is_empty() { 0.0 } else { sum / groups.len() as f64 };
            }
            best = best.max(if self.train_ex.is_empty() { 0.0 } else { examples / self.train_ex.len() as f64 });
        }
        best as f32
    }

    /// The OUT distance features: `out_err`, `out_gain`, `out_exact`, `out_rec`, `out_prec`, `out_broke`, `out_oob`,
    /// `out_conflict`, `out_pair_best`, `out_pair_worst`, `out_pairs_exact`, `out_pairs_fixed`, `near_only_missing`,
    /// `near_only_extra`, `near_remap`, then `fill_gain`, `fill_rec`, `fill_one_color`, `near_fill`. Each TableRows is
    /// painted on its example's train input on its own, a Position column giving the cell and a Color column the paint.
    /// The counts of an example (cells fixed, broken, stale, out of bounds, in conflict) and its pair
    /// value are the means over its TableRows; an example with no TableRows counts as one empty TableRows. The features
    /// then combine the examples: sums of those counts, and the best, the worst and the counts over the pair values.
    /// `near_remap` reads one map from the paint color to the wanted color over the paint of all TableRows of all examples.
    pub(crate) fn out_of(&self) -> [f32; OUT] {
        let mut d = [0.0f32; OUT];
        if self.n_train == 0 || self.position_at.is_empty() {
            return d;
        }
        let base = self.pairs.iter().map(|pair| pair.facts().base_err()).sum::<usize>().max(1) as f64;
        // The value of one TableRows, as its example reads it: the share of the error that is left.
        let value_of = |be: usize, fixed: usize, broke: usize| {
            if be > 0 { (be as f64 - fixed as f64 + broke as f64) / be as f64 } else { f64::from(broke > 0) }
        };
        // Painting. Each count is summed over the examples, each example's count being the mean over its TableRows.
        struct Paint {
            err: f64,
            fixed: f64,
            broke: f64,
            stale: f64,
            oob: f64,
            conflict: f64,
            per: Vec<f64>,
            remap_ok: bool,
            remap_moves: bool,
        }
        let mut best: Option<Paint> = None;
        let positions = self.position_at.len();
        for &pi in &self.position_at {
            for &ci in &self.color_at {
                let uniques = self.uniques();
                let unique_summaries: Vec<PaintSummary> = uniques.groups.iter().map(|&group| PaintSummary::of(&self.groups[group], pi, ci)).collect();
                let summaries: Vec<&PaintSummary> = uniques.place.iter().map(|&at| &unique_summaries[at]).collect();
                let mut paint = Paint { err: 0.0, fixed: 0.0, broke: 0.0, stale: 0.0, oob: 0.0, conflict: 0.0, per: Vec::new(), remap_ok: true, remap_moves: false };
                // The wanted color of each paint color: for the colors 0 to 9 in `remap`, 256 where there is none; for the others in `rest`.
                let mut remap = [256u16; 10];
                let mut rest: Vec<(i32, u8)> = Vec::new();
                for (e, p) in self.pairs.iter().enumerate() {
                    let facts = p.facts();
                    let be = facts.base_err();
                    let (height, width) = (p.output.height, p.output.width);
                    // The sums over the example's TableRows of: fixed, broke, stale, oob, conflict, pair value.
                    let mut own = [0.0f64; 6];
                    for group in self.train_ex[e].clone() {
                        let (mut f, mut b, mut stale, mut oob, mut conflict) = (0usize, 0usize, 0usize, 0usize, 0usize);
                        for cell in summaries[group].cells() {
                            let (i, j) = (cell.row, cell.column);
                            let Some(at) = index_in(i, j, height, width) else {
                                oob += 1;
                                continue;
                            };
                            conflict += usize::from(cell.conflict);
                            let value = if cell.conflict { None } else { Some(cell.color) };
                            let want = p.output.cells[at];
                            let was = (if facts.same { p.input.cells[at] } else { facts.obg }) == want;
                            if value == Some(i32::from(want)) {
                                if !was {
                                    f += 1;
                                }
                            } else if was {
                                b += 1;
                            } else {
                                stale += 1;
                            }
                            if let Some(v) = value {
                                if (0..10).contains(&v) {
                                    let held = &mut remap[v as usize];
                                    if *held == 256 {
                                        *held = u16::from(want);
                                    } else if *held != u16::from(want) {
                                        paint.remap_ok = false;
                                    }
                                } else {
                                    match rest.iter().find(|(held, _)| *held == v) {
                                        Some(&(_, wanted)) => {
                                            if wanted != want {
                                                paint.remap_ok = false;
                                            }
                                        }
                                        None => rest.push((v, want)),
                                    }
                                }
                            }
                        }
                        own[0] += f as f64;
                        own[1] += b as f64;
                        own[2] += stale as f64;
                        own[3] += oob as f64;
                        own[4] += conflict as f64;
                        own[5] += value_of(be, f, b);
                    }
                    if self.train_ex[e].is_empty() {
                        own[5] += value_of(be, 0, 0);
                    }
                    let k = self.train_ex[e].len().max(1) as f64;
                    paint.fixed += own[0] / k;
                    paint.broke += own[1] / k;
                    paint.stale += own[2] / k;
                    paint.oob += own[3] / k;
                    paint.conflict += own[4] / k;
                    paint.per.push(own[5] / k);
                }
                paint.remap_moves = remap.iter().enumerate().any(|(k, &v)| v != 256 && k as i32 != i32::from(v)) || rest.iter().any(|&(k, v)| k != i32::from(v));
                paint.err = base - paint.fixed + paint.broke;
                if best.as_ref().is_none_or(|held| paint.err < held.err) {
                    best = Some(paint);
                }
            }
        }
        if let Some(p) = best {
            let n = p.fixed + p.broke + p.stale;
            let per_len = p.per.len().max(1) as f64;
            d[0] = (p.err / base) as f32;
            d[1] = (1.0 - p.err / base) as f32;
            d[2] = f32::from(p.err == 0.0 && p.oob == 0.0);
            d[3] = (p.fixed / base) as f32;
            d[4] = if n > 0.0 { (p.fixed / n) as f32 } else { 0.0 };
            d[5] = (p.broke / base) as f32;
            d[6] = f32::from(p.oob > 0.0);
            d[7] = f32::from(p.conflict > 0.0);
            d[8] = (1.0 - p.per.iter().copied().fold(f64::INFINITY, f64::min)) as f32;
            d[9] = (1.0 - p.per.iter().copied().fold(f64::NEG_INFINITY, f64::max)) as f32;
            d[10] = (p.per.iter().filter(|&&x| x == 0.0).count() as f64 / per_len) as f32;
            d[11] = (p.per.iter().filter(|&&x| x < 1.0).count() as f64 / per_len) as f32;
            d[12] = f32::from(p.err > 0.0 && p.broke == 0.0 && p.stale == 0.0 && p.fixed > 0.0);
            d[13] = f32::from(p.fixed == base && p.err > 0.0);
            d[14] = f32::from(p.remap_ok && p.remap_moves && p.fixed == 0.0);
        }
        // One fill color for a Position column alone, chosen for each TableRows on its own.
        let mut best_fill: Option<(f64, f64, f64)> = None;
        for place in 0..positions {
            let (mut got, mut own, mut inside, mut n) = (0.0f64, 0.0f64, 0.0f64, 0.0f64);
            for (e, p) in self.pairs.iter().enumerate() {
                let facts = p.facts();
                let (height, width) = (p.output.height, p.output.width);
                // The sums over the example's TableRows of: cells got, cells that held their own, cells in the fill color, cells.
                let mut sums = [0.0f64; 4];
                for group in self.train_ex[e].clone() {
                    let cells = &self.cell_summaries()[self.uniques().place[group] * positions + place];
                    let mut counts = [0usize; 10];
                    let mut inside_cells = 0usize;
                    let frames = p.fill_frames();
                    if let Some(frames) = frames {
                        // Cells outside the corner are outside the output.
                        for (count, color) in counts.iter_mut().zip(&frames.out_color) {
                            *count = both(&cells.frame, color);
                        }
                        inside_cells = both(&cells.frame, &frames.inside);
                    } else {
                        cells.each(|i, j| {
                            if let Some(at) = index_in(i, j, height, width) {
                                counts[p.output.cells[at].min(9) as usize] += 1;
                                inside_cells += 1;
                            }
                        });
                    }
                    let Some((v, m)) = counts.iter().enumerate().fold(None, |best: Option<(usize, usize)>, (color, &count)| match best {
                        Some((_, held)) if held >= count => best,
                        _ if count > 0 => Some((color, count)),
                        _ => best,
                    }) else { continue };
                    if let Some(frames) = frames {
                        let (mut got, mut held) = (0usize, 0usize);
                        for row in 0..32 {
                            let cell = cells.frame[row];
                            got += (cell & frames.out_color[v][row] & !frames.base_color[v][row]).count_ones() as usize;
                            held += (cell & !frames.out_color[v][row] & frames.was[row]).count_ones() as usize;
                        }
                        sums[0] += got as f64;
                        sums[1] += held as f64;
                    } else {
                        cells.each(|i, j| {
                            let Some(at) = index_in(i, j, height, width) else { return };
                            let (b, base_color) = (p.output.cells[at], if facts.same { p.input.cells[at] } else { facts.obg });
                            if b as usize == v && base_color as usize != v {
                                sums[0] += 1.0;
                            }
                            if b as usize != v && base_color == b {
                                sums[1] += 1.0;
                            }
                        });
                    }
                    sums[2] += m as f64;
                    sums[3] += inside_cells as f64;
                }
                let k = self.train_ex[e].len().max(1) as f64;
                got += sums[0] / k;
                own += sums[1] / k;
                inside += sums[2] / k;
                n += sums[3] / k;
            }
            let gain = (got - own) / base;
            if best_fill.is_none_or(|held| gain > held.0) {
                best_fill = Some((gain, got / base, if n > 0.0 { inside / n } else { 0.0 }));
            }
        }
        if let Some((gain, rec, one)) = best_fill {
            d[15] = gain as f32;
            d[16] = rec as f32;
            d[17] = one as f32;
            d[18] = f32::from(one == 1.0 && rec > 0.0);
        }
        d
    }
}
