//! The features of a table at one assignment, the TableVector, computed from
//! plain data: the column types as names, the cells of the rows as `i32` in the
//! export's own cell encoding (`arclog_tables::columns` gives it), the rows
//! grouped by example, and the task's train pairs.
//!
//! The crate depends on no other crate of the engine. The tables export calls
//! [`vector`] on the rows it holds, and `arclog-features-py` calls it on rows
//! that Python stored, so that each feature is written once.
//!
//! A table at an assignment holds a Set of TableRows. Each [`TableRows`] is at one
//! example, which is the value of its Example column. A quantity of an
//! example that a feature reads is computed for each of the example's TableRows
//! and averaged over them; the example's count of TableRows is a feature of its own.
//! A train example that has no TableRows has 0 rows. A test example that has no
//! TableRows is not in the table. An empty TableRows is a TableRows of 0 rows at its
//! example, and counts as a TableRows of that example.
//!
//! A task-level table has no train example in it. Its examples are all read where
//! a feature says so (the counts of rows, `empty_all`, `empty_inputs`, `suit`); a
//! feature that is defined on the train examples is 0 on it.

use std::cell::OnceCell;
use std::collections::{BTreeMap, BTreeSet, HashMap, HashSet};

/// The code of a column of type `Example`.
pub const EXAMPLE: u8 = 1;
/// The code of a column of type `Box`, which has four cells.
pub const BOX: u8 = 2;
/// The code of a column of type `Color`.
pub const COLOR: u8 = 3;
/// The code of a column of type `Position`, which has four cells.
pub const POSITION: u8 = 4;
/// The code of a column of type `Offset`, which has four cells.
pub const OFFSET: u8 = 5;
/// The code of any other column type, which has one cell.
pub const OTHER: u8 = 0;

/// The names of the column types that have a feature `t_<name>` of their own. Any other type counts toward `t_other`.
pub const TYPE_NAMES: &[&str] = &["Int", "Nat", "Color", "Example", "Unit", "Box", "Position", "Offset", "Ident", "C4", "D4", "Dir", "DiagDir", "Dir8", "Axis", "DiagAxis", "Axis4", "Sym", "Sense", "Pose", "Record"];

/// The name of a type without its parameters: `Ident(Value)` is `Ident`.
fn base_name(name: &str) -> &str {
    name.split('(').next().unwrap_or(name)
}

/// The code of the column type named `name`, as `ValueType`'s `Debug` spells it.
pub fn type_code(name: &str) -> u8 {
    match base_name(name) {
        "Example" => EXAMPLE,
        "Color" => COLOR,
        "Box" => BOX,
        "Position" => POSITION,
        "Offset" => OFFSET,
        _ => OTHER,
    }
}

/// The count of cells of a column of type code `code`.
pub const fn cell_width(code: u8) -> usize {
    if code == BOX || code == POSITION || code == OFFSET { 4 } else { 1 }
}

/// A grid: `height` rows of `width` colors, row by row, each color its digit.
#[derive(Clone, Debug)]
pub struct Grid {
    pub height: usize,
    pub width: usize,
    pub cells: Vec<u8>,
}

/// A train pair of the task.
#[derive(Clone, Debug)]
pub struct Pair {
    pub input: Grid,
    pub output: Grid,
}

/// One TableRows: the rows of one example under one constraint model.
#[derive(Clone, Copy, Debug)]
pub struct TableRows<'a> {
    /// The example's index among the train examples and then the test examples.
    /// Where [`Input::example_column`] gives the Example column, the rows of a
    /// TableRows are split on that column's value, and each part is the TableRows of that
    /// example; this field is then read for a TableRows with no row alone. Without
    /// the column, all the rows of a TableRows are at this example. A TableRows with no
    /// row is a TableRows of 0 rows at this example.
    pub example: u32,
    /// The count of rows.
    pub count: usize,
    /// The cells of the rows, row by row, a row being as wide as the types say.
    pub cells: &'a [i32],
}

/// A table at one assignment.
#[derive(Clone, Copy, Debug)]
pub struct Input<'a> {
    /// The type of each column: the name that `ValueType`'s `Debug` spells, without the Ident source.
    pub types: &'a [&'a str],
    /// The index of the Example column, where the rows hold one.
    pub example_column: Option<usize>,
    /// The Set of TableRows.
    pub rows: &'a [TableRows<'a>],
    /// The task's train pairs.
    pub train: &'a [Pair],
    /// Whether the table's own state sequence stopped at the 256 cap.
    pub capped: bool,
    /// Whether the table is task-level: its TableRows are at no train example, and the examples in `rows` are read together.
    pub task_level: bool,
}

type Cell = (i32, i32);

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

/// The 8-connected parts of a set of cells, each sorted.
fn components(cells: &HashSet<Cell>) -> Vec<Vec<Cell>> {
    let mut left = cells.clone();
    let mut parts = Vec::new();
    while let Some(&start) = left.iter().next() {
        left.remove(&start);
        let mut stack = vec![start];
        let mut part = vec![start];
        while let Some((r, q)) = stack.pop() {
            for a in -1..=1 {
                for b in -1..=1 {
                    let next = (r + a, q + b);
                    if left.remove(&next) {
                        part.push(next);
                        stack.push(next);
                    }
                }
            }
        }
        part.sort_unstable();
        parts.push(part);
    }
    parts
}

/// A part moved to the top left corner of its box.
fn normalized(part: &[Cell]) -> Vec<Cell> {
    let r0 = part.iter().map(|c| c.0).min().unwrap_or(0);
    let q0 = part.iter().map(|c| c.1).min().unwrap_or(0);
    let mut moved: Vec<Cell> = part.iter().map(|&(r, q)| (r - r0, q - q0)).collect();
    moved.sort_unstable();
    moved
}

/// The parts of at least 3 cells of each color's cells.
fn objects(by_color: &[HashSet<Cell>]) -> Vec<Vec<Cell>> {
    by_color.iter().flat_map(|cells| components(cells)).filter(|part| part.len() >= 3).collect()
}

/// The cell sets of a pair that the Position features compare with.
struct Heavy {
    changed: HashSet<Cell>,
    fg: HashSet<Cell>,
    ofg: HashSet<Cell>,
    /// The cells of each color of the input.
    incolor: HashSet<Vec<Cell>>,
    nin: HashSet<Vec<Cell>>,
    nout: HashSet<Vec<Cell>>,
    live: HashSet<Vec<Cell>>,
}

/// What a train pair gives to the features that compare rows with it.
struct PairFacts<'a> {
    pair: &'a Pair,
    area: usize,
    /// Whether the input and the output have one size.
    same: bool,
    /// The count of cells where the input and the output differ; 0 where the sizes differ.
    changed: usize,
    /// The output's most common color (the first met, on a tie), and the count of output cells off it.
    obg: u8,
    ofg: usize,
    /// The input's most common color.
    bg: u8,
    /// The colors of the output, as a bit set.
    ocolors: u16,
    /// The colors of the output that the input lacks, as a bit set.
    newcolors: u16,
    heavy: OnceCell<Heavy>,
}

impl<'a> PairFacts<'a> {
    fn of(pair: &'a Pair) -> PairFacts<'a> {
        let (input, output) = (&pair.input, &pair.output);
        let same = input.height == output.height && input.width == output.width;
        let changed = if same { input.cells.iter().zip(&output.cells).filter(|(a, b)| a != b).count() } else { 0 };
        let obg = background(&output.cells);
        let bg = background(&input.cells);
        let ofg = output.cells.iter().filter(|&&color| color.min(9) != obg).count();
        let bits = |cells: &[u8]| cells.iter().fold(0u16, |bits, &color| bits | 1 << color.min(9));
        let (ocolors, icolors) = (bits(&output.cells), bits(&input.cells));
        PairFacts { pair, area: input.height * input.width, same, changed, obg, ofg, bg, ocolors, newcolors: ocolors & !icolors, heavy: OnceCell::new() }
    }

    /// The error before any paint: the cells that differ where the sizes are one, else the output's cells off its background.
    fn base_err(&self) -> usize {
        if self.same { self.changed } else { self.ofg }
    }

    /// The color that the painted grid has at (i, j) before any paint.
    fn base_of(&self, i: usize, j: usize) -> u8 {
        if self.same { self.pair.input.cells[i * self.pair.input.width + j] } else { self.obg }
    }

    fn out_at(&self, i: usize, j: usize) -> u8 {
        self.pair.output.cells[i * self.pair.output.width + j]
    }

    fn heavy(&self) -> &Heavy {
        self.heavy.get_or_init(|| {
            let (input, output) = (&self.pair.input, &self.pair.output);
            let mut changed = HashSet::new();
            let (mut fg, mut ofg) = (HashSet::new(), HashSet::new());
            let mut in_by: Vec<HashSet<Cell>> = vec![HashSet::new(); 10];
            let mut fg_by: Vec<HashSet<Cell>> = vec![HashSet::new(); 10];
            let mut ofg_by: Vec<HashSet<Cell>> = vec![HashSet::new(); 10];
            for i in 0..input.height {
                for j in 0..input.width {
                    let a = input.cells[i * input.width + j].min(9);
                    let at = (i as i32, j as i32);
                    in_by[a as usize].insert(at);
                    if a != self.bg {
                        fg.insert(at);
                        fg_by[a as usize].insert(at);
                    }
                    if self.same && a != output.cells[i * output.width + j] {
                        changed.insert(at);
                    }
                }
            }
            for i in 0..output.height {
                for j in 0..output.width {
                    let b = output.cells[i * output.width + j].min(9);
                    if b != self.obg {
                        ofg.insert((i as i32, j as i32));
                        ofg_by[b as usize].insert((i as i32, j as i32));
                    }
                }
            }
            let incolor: HashSet<Vec<Cell>> = in_by.iter().filter(|cells| !cells.is_empty()).map(|cells| { let mut v: Vec<Cell> = cells.iter().copied().collect(); v.sort_unstable(); v }).collect();
            let iobj = objects(&fg_by);
            let oobj = objects(&ofg_by);
            let iobj_set: HashSet<&Vec<Cell>> = iobj.iter().collect();
            let nin = iobj.iter().map(|part| normalized(part)).collect();
            let nout = oobj.iter().map(|part| normalized(part)).collect();
            let live = oobj
                .iter()
                .filter(|part| !(self.same && iobj_set.contains(part) && part.iter().all(|&(i, j)| input.cells[i as usize * input.width + j as usize] == output.cells[i as usize * output.width + j as usize])))
                .map(|part| normalized(part))
                .collect();
            Heavy { changed, fg, ofg, incolor, nin, nout, live }
        })
    }
}

/// The cells that a train output wants, as `Gate`'s cell masks have them: for a mask of size 9000 the cell (y, x, color),
/// for 900 the cell, for 10 the color.
struct Masks {
    want: Vec<bool>,
    right: Vec<bool>,
    want_cell: Vec<bool>,
    want_color: Vec<bool>,
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
        Masks { want, right, want_cell, want_color }
    }

    /// How well `rows` suit the pair: the wanted cells hit over the cells wanted plus the wrong cells. `p` is the first cell of a
    /// Position or Box column, `c` that of a Color column; either may be None.
    fn overlap(&self, rows: &[&[i32]], p: Option<usize>, c: Option<usize>) -> f64 {
        let mut seen = vec![false; if p.is_some() && c.is_some() { 9000 } else if p.is_some() { 900 } else { 10 }];
        let mut out = 0usize;
        for row in rows {
            let (mut ok, mut key) = (true, 0i64);
            if let Some(p) = p {
                let (i, j) = (row[p] as i64, row[p + 2] as i64);
                ok = (0..30).contains(&i) && (0..30).contains(&j);
                key = 30 * i + j;
            }
            if let Some(c) = c {
                let color = row[c] as i64;
                ok = ok && (0..10).contains(&color);
                key = 10 * key + color;
            }
            if ok {
                seen[key as usize] = true;
            } else {
                out += 1;
            }
        }
        let (want, right): (&[bool], &[bool]) = match seen.len() {
            9000 => (&self.want, &self.right),
            900 => (&self.want_cell, &self.want_cell),
            _ => (&self.want_color, &self.want_color),
        };
        let hit = seen.iter().zip(want).filter(|(s, w)| **s && **w).count();
        let wanted = want.iter().filter(|w| **w).count();
        let wrong = seen.iter().zip(right).filter(|(s, r)| **s && !**r).count();
        hit as f64 / (wanted + wrong + out).max(1) as f64
    }
}

/// One TableRows, as its rows of cells.
type TableRowsOf<'a> = Vec<&'a [i32]>;

/// The count of Position or Box columns, and of Color columns, that `suit` reads.
const SUIT_COLUMNS: usize = 2;

/// The count of values that `Examples::fit` gives.
const FIT: usize = 18;
/// The count of values that `Examples::out` gives.
const OUT: usize = 19;

/// The rows of each example, as the features read them.
pub struct Examples<'a> {
    /// The rows of each train example, in the order of the examples. A task-level table has all its examples here.
    train: Vec<f64>,
    /// The rows of each train example and of each test example in the table.
    inputs: Vec<f64>,
    /// The count of TableRows of each example in the table, train examples included.
    sets: Vec<f64>,
    /// The TableRows of each train example. A task-level table has all its examples here.
    train_rows: Vec<Vec<TableRowsOf<'a>>>,
    /// The TableRows of each test example in the table.
    test_rows: Vec<Vec<TableRowsOf<'a>>>,
    /// The count of train examples; 0 for a task-level table.
    n_train: usize,
    task_level: bool,
    capped: bool,
    /// The type of each column, without parameters.
    names: Vec<&'a str>,
    pairs: &'a [Pair],
    facts: Vec<PairFacts<'a>>,
    /// The index of the first cell of each Color column in a row.
    color_at: Vec<usize>,
    /// The same, of each Position column.
    position_at: Vec<usize>,
    /// The same, of each Position or Box column.
    grid_at: Vec<usize>,
    columns: OnceCell<Option<[f32; 5]>>,
    fit: OnceCell<[f32; FIT]>,
    masks: OnceCell<Vec<Masks>>,
    suit: OnceCell<f32>,
    out: OnceCell<[f32; OUT]>,
}

impl<'a> Examples<'a> {
    pub fn of(input: &Input<'a>) -> Examples<'a> {
        let codes: Vec<u8> = input.types.iter().map(|name| type_code(name)).collect();
        let width: usize = codes.iter().map(|&code| cell_width(code)).sum();
        let offset: Option<usize> = input.example_column.map(|column| codes[..column].iter().map(|&code| cell_width(code)).sum());
        // The TableRows of each example. A TableRows with an Example column is split on it, so that each part is the rows of one example;
        // an empty TableRows is a TableRows of 0 rows at the example that it names.
        let mut by: BTreeMap<usize, Vec<TableRowsOf<'a>>> = BTreeMap::new();
        for rows in input.rows {
            if rows.count == 0 {
                by.entry(rows.example as usize).or_default().push(Vec::new());
            } else if width == 0 {
                by.entry(rows.example as usize).or_default().push(vec![&[][..]; rows.count]);
            } else if let Some(at) = offset {
                let mut parts: BTreeMap<i32, TableRowsOf<'a>> = BTreeMap::new();
                for row in rows.cells.chunks_exact(width) {
                    parts.entry(row[at]).or_default().push(row);
                }
                for (example, part) in parts {
                    by.entry(usize::try_from(example).unwrap_or(usize::MAX)).or_default().push(part);
                }
            } else {
                by.entry(rows.example as usize).or_default().push(rows.cells.chunks_exact(width).collect());
            }
        }
        let n_train = if input.task_level { 0 } else { input.train.len() };
        let train_rows: Vec<Vec<TableRowsOf<'a>>> = (0..n_train).map(|example| by.remove(&example).unwrap_or_default()).collect();
        let test_rows: Vec<Vec<TableRowsOf<'a>>> = by.into_values().collect();
        let mean_of = |of: &Vec<TableRowsOf<'a>>| if of.is_empty() { 0.0 } else { of.iter().map(Vec::len).sum::<usize>() as f64 / of.len() as f64 };
        let train_means: Vec<f64> = train_rows.iter().map(mean_of).collect();
        let test_means: Vec<f64> = test_rows.iter().map(mean_of).collect();
        let sets = train_rows.iter().chain(&test_rows).map(|of| of.len() as f64).collect();
        let starts: Vec<(usize, u8)> = codes.iter().scan(0, |at, &code| { let start = *at; *at += cell_width(code); Some((start, code)) }).collect();
        let at_of = |wanted: &[u8]| starts.iter().filter(|(_, code)| wanted.contains(code)).map(|&(start, _)| start).collect::<Vec<usize>>();
        let facts = input.train.iter().map(PairFacts::of).collect();
        let mut examples = Examples {
            train: Vec::new(),
            inputs: Vec::new(),
            sets,
            train_rows,
            test_rows,
            n_train,
            task_level: input.task_level,
            capped: input.capped,
            names: input.types.iter().map(|name| base_name(name)).collect(),
            pairs: input.train,
            facts,
            color_at: at_of(&[COLOR]),
            position_at: at_of(&[POSITION]),
            grid_at: at_of(&[POSITION, BOX]),
            columns: OnceCell::new(),
            fit: OnceCell::new(),
            masks: OnceCell::new(),
            suit: OnceCell::new(),
            out: OnceCell::new(),
        };
        // A task-level table has no train example in it: all its examples are read.
        if input.task_level {
            examples.train_rows = std::mem::take(&mut examples.test_rows);
            examples.train = test_means.clone();
            examples.inputs = test_means;
        } else {
            examples.inputs = train_means.iter().chain(&test_means).copied().collect();
            examples.train = train_means;
        }
        examples
    }

    /// The count of columns of the type named `name`.
    fn count_of(&self, name: &str) -> f32 {
        self.names.iter().filter(|&&held| held == name).count() as f32
    }

    /// The count of columns of a type that has no feature of its own.
    fn count_other(&self) -> f32 {
        self.names.iter().filter(|held| !TYPE_NAMES.contains(held)).count() as f32
    }

    /// The signature of each TableRows of an example: its distinct rows, sorted. An example with no TableRows has one empty TableRows.
    fn signature(of: &[TableRowsOf<'a>]) -> BTreeSet<Vec<&'a [i32]>> {
        let mut set: BTreeSet<Vec<&'a [i32]>> = of.iter().map(|rows| { let mut rows = rows.clone(); rows.sort_unstable(); rows.dedup(); rows }).collect();
        if set.is_empty() {
            set.insert(Vec::new());
        }
        set
    }

    /// `const_cols`, `live_cols`, `distinct_min`, `distinct_max` and `row_distinct`, over the rows of all train examples.
    fn columns(&self) -> Option<[f32; 5]> {
        *self.columns.get_or_init(|| {
            if self.n_train == 0 {
                return None;
            }
            let rows: Vec<&[i32]> = self.train_rows.iter().flatten().flatten().copied().collect();
            if rows.is_empty() || self.names.is_empty() {
                return None;
            }
            let mut start = 0;
            let mut distinct: Vec<usize> = Vec::with_capacity(self.names.len());
            for name in &self.names {
                let width = cell_width(type_code(name));
                distinct.push(rows.iter().map(|row| &row[start..start + width]).collect::<HashSet<_>>().len());
                start += width;
            }
            let constant = distinct.iter().filter(|&&n| n <= 1).count();
            let whole = rows.iter().copied().collect::<HashSet<_>>().len();
            Some([constant as f32, (distinct.len() - constant) as f32, *distinct.iter().min().unwrap() as f32, *distinct.iter().max().unwrap() as f32, (whole as f64 / rows.len() as f64) as f32])
        })
    }

    /// The features against the train pairs: `rows_per_area`, `rows_eq_changed`, `rows_eq_ofg`, `color_in_out`, `color_new`,
    /// `color_one`, then `cover`, `fg_share`, `ofg_share`, `iou_changed`, `prec_changed`, `rec_changed`, `iou_ofg`,
    /// `is_input_color`, `shape_in`, `shape_out`, `shape_live`, `shape_both_live`. Each is the mean over the train
    /// examples that have rows of the mean over the example's TableRows with rows (and over the columns it reads).
    fn fit(&self) -> [f32; FIT] {
        *self.fit.get_or_init(|| {
            let mut total = [(0.0f64, 0usize); FIT];
            if self.n_train == 0 {
                return [0.0; FIT];
            }
            for (rows_of, pair) in self.train_rows.iter().zip(&self.facts) {
                let mut own = [(0.0f64, 0usize); FIT];
                let mut add = |place: usize, value: f64| { own[place].0 += value; own[place].1 += 1; };
                for rows in rows_of.iter().filter(|rows| !rows.is_empty()) {
                    let distinct = rows.iter().copied().collect::<HashSet<_>>().len();
                    add(0, rows.len() as f64 / pair.area.max(1) as f64);
                    add(1, f64::from(pair.same && distinct == pair.changed));
                    add(2, f64::from(distinct == pair.ofg));
                    for &at in &self.color_at {
                        let colors: HashSet<i32> = rows.iter().map(|row| row[at]).collect();
                        let bit = |color: i32, bits: u16| (0..10).contains(&color) && bits >> color & 1 == 1;
                        add(3, colors.iter().filter(|&&color| bit(color, pair.ocolors)).count() as f64 / colors.len().max(1) as f64);
                        add(4, f64::from(colors.iter().any(|&color| bit(color, pair.newcolors))));
                        add(5, f64::from(colors.len() == 1));
                    }
                    for &at in &self.position_at {
                        let cells: HashSet<Cell> = rows.iter().map(|row| (row[at], row[at + 2])).collect();
                        let heavy = pair.heavy();
                        let size = cells.len() as f64;
                        add(6, size / pair.area.max(1) as f64);
                        add(7, cells.intersection(&heavy.fg).count() as f64 / size);
                        add(8, cells.intersection(&heavy.ofg).count() as f64 / size);
                        if pair.same {
                            let with_changed = cells.intersection(&heavy.changed).count() as f64;
                            let union = cells.union(&heavy.changed).count();
                            add(9, if union > 0 { with_changed / union as f64 } else { 0.0 });
                            add(10, with_changed / size);
                            add(11, with_changed / heavy.changed.len().max(1) as f64);
                            let union = cells.union(&heavy.ofg).count();
                            add(12, if union > 0 { cells.intersection(&heavy.ofg).count() as f64 / union as f64 } else { 0.0 });
                        }
                        let mut sorted: Vec<Cell> = cells.iter().copied().collect();
                        sorted.sort_unstable();
                        add(13, f64::from(heavy.incolor.contains(&sorted)));
                        let shapes: HashSet<Vec<Cell>> = components(&cells).into_iter().filter(|part| part.len() >= 3 && part.len() as f64 <= 0.6 * pair.area as f64).map(|part| normalized(&part)).collect();
                        add(14, f64::from(!shapes.is_disjoint(&heavy.nin)));
                        add(15, f64::from(!shapes.is_disjoint(&heavy.nout)));
                        add(16, f64::from(!shapes.is_disjoint(&heavy.live)));
                        add(17, f64::from(shapes.iter().any(|shape| heavy.live.contains(shape) && heavy.nin.contains(shape))));
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
        })
    }

    fn masks(&self) -> &Vec<Masks> {
        self.masks.get_or_init(|| self.pairs.iter().map(Masks::of).collect())
    }

    /// The best mean overlap with the train outputs over the pairs of a Position or Box column (the first `SUIT_COLUMNS`)
    /// and a Color column (the first `SUIT_COLUMNS`). On a train example, the overlap with that example's output; on a
    /// task-level table, the mean over the train outputs. An example with no rows counts 0, and so does an empty TableRows.
    fn suit(&self) -> f32 {
        *self.suit.get_or_init(|| {
            let ps: Vec<usize> = self.grid_at.iter().copied().take(SUIT_COLUMNS).collect();
            let cs: Vec<usize> = self.color_at.iter().copied().take(SUIT_COLUMNS).collect();
            if ps.is_empty() && cs.is_empty() || self.pairs.is_empty() {
                return 0.0;
            }
            let masks = self.masks();
            let sites: Vec<(Option<usize>, Option<usize>)> = if ps.is_empty() { cs.iter().map(|&c| (None, Some(c))).collect() } else if cs.is_empty() { ps.iter().map(|&p| (Some(p), None)).collect() } else { ps.iter().flat_map(|&p| cs.iter().map(move |&c| (Some(p), Some(c)))).collect() };
            let mean = |values: &[f64]| if values.is_empty() { 0.0 } else { values.iter().sum::<f64>() / values.len() as f64 };
            let mut best = 0.0f64;
            for (p, c) in sites {
                let per_example: Vec<f64> = self
                    .train_rows
                    .iter()
                    .enumerate()
                    .map(|(index, rows_of)| {
                        let against: Vec<&Masks> = if self.task_level { masks.iter().collect() } else { vec![&masks[index]] };
                        mean(&rows_of.iter().map(|rows| mean(&against.iter().map(|m| m.overlap(rows, p, c)).collect::<Vec<_>>())).collect::<Vec<_>>())
                    })
                    .collect();
                best = best.max(mean(&per_example));
            }
            best as f32
        })
    }

    /// The OUT distance features: `out_err`, `out_gain`, `out_exact`, `out_rec`, `out_prec`, `out_broke`, `out_oob`,
    /// `out_conflict`, `out_pair_best`, `out_pair_worst`, `out_pairs_exact`, `out_pairs_fixed`, `near_only_missing`,
    /// `near_only_extra`, `near_remap`, then `fill_gain`, `fill_rec`, `fill_one_color`, `near_fill`. Each TableRows is
    /// painted on its example's train input on its own, a Position column giving the cell and a Color column the paint.
    /// The counts of an example (cells fixed, broken, stale, out of bounds, in conflict) and its pair
    /// value are the means over its TableRows; an example with no TableRows counts as one empty TableRows. The features
    /// then combine the examples: sums of those counts, and the best, the worst and the counts over the pair values.
    /// `near_remap` reads one map from the paint color to the wanted color over the paint of all TableRows of all examples.
    fn out(&self) -> [f32; OUT] {
        *self.out.get_or_init(|| {
            let mut d = [0.0f32; OUT];
            if self.n_train == 0 || self.position_at.is_empty() {
                return d;
            }
            let base = self.facts.iter().map(PairFacts::base_err).sum::<usize>().max(1) as f64;
            let unpainted: [TableRowsOf<'a>; 1] = [Vec::new()];
            let examples: Vec<&[TableRowsOf<'a>]> = self.train_rows.iter().map(|of| if of.is_empty() { &unpainted[..] } else { &of[..] }).collect();
            // Painting. Each count is summed over the examples, each example's count being the mean over its TableRows.
            struct Paint { err: f64, fixed: f64, broke: f64, stale: f64, oob: f64, conflict: f64, per: Vec<f64>, remap_ok: bool, remap_moves: bool }
            let mut best: Option<Paint> = None;
            for &pi in &self.position_at {
                for &ci in &self.color_at {
                    let mut paint = Paint { err: 0.0, fixed: 0.0, broke: 0.0, stale: 0.0, oob: 0.0, conflict: 0.0, per: Vec::new(), remap_ok: true, remap_moves: false };
                    let mut remap: HashMap<i32, u8> = HashMap::new();
                    for (e, p) in self.facts.iter().enumerate() {
                        let be = p.base_err();
                        let (height, width) = (p.pair.output.height as i32, p.pair.output.width as i32);
                        // The sums over the example's TableRows of: fixed, broke, stale, oob, conflict, pair value.
                        let mut own = [0.0f64; 6];
                        for rows in examples[e] {
                            let mut cells: HashMap<Cell, Vec<i32>> = HashMap::new();
                            for row in rows {
                                let colors = cells.entry((row[pi], row[pi + 2])).or_default();
                                if !colors.contains(&row[ci]) {
                                    colors.push(row[ci]);
                                }
                            }
                            let (mut f, mut b, mut stale, mut oob, mut conflict) = (0usize, 0usize, 0usize, 0usize, 0usize);
                            for (&(i, j), colors) in &cells {
                                if !(0 <= i && i < height && 0 <= j && j < width) {
                                    oob += 1;
                                    continue;
                                }
                                conflict += usize::from(colors.len() > 1);
                                let value = if colors.len() == 1 { Some(colors[0]) } else { None };
                                let want = p.out_at(i as usize, j as usize);
                                let was = p.base_of(i as usize, j as usize) == want;
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
                                    if *remap.entry(v).or_insert(want) != want {
                                        paint.remap_ok = false;
                                    }
                                }
                            }
                            own[0] += f as f64;
                            own[1] += b as f64;
                            own[2] += stale as f64;
                            own[3] += oob as f64;
                            own[4] += conflict as f64;
                            own[5] += if be > 0 { (be as f64 - f as f64 + b as f64) / be as f64 } else { f64::from(b > 0) };
                        }
                        let k = examples[e].len() as f64;
                        paint.fixed += own[0] / k;
                        paint.broke += own[1] / k;
                        paint.stale += own[2] / k;
                        paint.oob += own[3] / k;
                        paint.conflict += own[4] / k;
                        paint.per.push(own[5] / k);
                    }
                    paint.remap_moves = remap.iter().any(|(&k, &v)| k != i32::from(v));
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
            for &pi in &self.position_at {
                let (mut got, mut own, mut inside, mut n) = (0.0f64, 0.0f64, 0.0f64, 0.0f64);
                for (e, p) in self.facts.iter().enumerate() {
                    let (height, width) = (p.pair.output.height as i32, p.pair.output.width as i32);
                    // The sums over the example's TableRows of: cells got, cells that held their own, cells in the fill color, cells.
                    let mut sums = [0.0f64; 4];
                    for rows in examples[e] {
                        let cells: HashSet<Cell> = rows.iter().map(|row| (row[pi], row[pi + 2])).filter(|&(i, j)| 0 <= i && i < height && 0 <= j && j < width).collect();
                        let mut counts = [0usize; 10];
                        for &(i, j) in &cells {
                            counts[p.out_at(i as usize, j as usize).min(9) as usize] += 1;
                        }
                        let Some((v, m)) = counts.iter().enumerate().fold(None, |best: Option<(usize, usize)>, (color, &count)| match best {
                            Some((_, held)) if held >= count => best,
                            _ if count > 0 => Some((color, count)),
                            _ => best,
                        }) else { continue };
                        for &(i, j) in &cells {
                            let (b, base_color) = (p.out_at(i as usize, j as usize), p.base_of(i as usize, j as usize));
                            if b as usize == v && base_color as usize != v {
                                sums[0] += 1.0;
                            }
                            if b as usize != v && base_color == b {
                                sums[1] += 1.0;
                            }
                        }
                        sums[2] += m as f64;
                        sums[3] += cells.len() as f64;
                    }
                    let k = examples[e].len() as f64;
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
        })
    }
}

/// A feature: its name and its value on a table.
pub struct Feature {
    pub name: &'static str,
    pub of: fn(&Examples<'_>) -> f32,
}

fn mean(values: &[f64]) -> f64 {
    if values.is_empty() { 0.0 } else { values.iter().sum::<f64>() / values.len() as f64 }
}

fn max(values: &[f64]) -> f64 {
    values.iter().copied().fold(0.0, f64::max)
}

fn min(values: &[f64]) -> f64 {
    values.iter().copied().reduce(f64::min).unwrap_or(0.0)
}

fn all_empty(values: &[f64]) -> f32 {
    f32::from(!values.is_empty() && values.iter().all(|&rows| rows == 0.0))
}

/// The rows of the train examples, which a task-level table has none of.
fn train_of<'e>(e: &'e Examples<'_>) -> &'e [f64] {
    if e.n_train == 0 { &[] } else { &e.train }
}

/// Whether every train example has one Set of TableRows.
fn same_hash(e: &Examples<'_>) -> f32 {
    if e.n_train == 0 {
        return 0.0;
    }
    let mut signatures = e.train_rows.iter().map(|of| Examples::signature(of));
    let first = signatures.next();
    f32::from(signatures.all(|signature| Some(&signature) == first.as_ref()))
}

/// Whether some test example in the table has the Set of TableRows of the first train example.
fn test_same(e: &Examples<'_>) -> f32 {
    let Some(first) = e.train_rows.first().filter(|_| e.n_train > 0) else { return 0.0 };
    let first = Examples::signature(first);
    f32::from(e.test_rows.iter().any(|of| Examples::signature(of) == first))
}

/// Whether some test example in the table has no rows.
fn test_empty(e: &Examples<'_>) -> f32 {
    f32::from(e.n_train > 0 && e.test_rows.iter().any(|of| of.iter().all(|rows| rows.is_empty())))
}

/// A feature `t_<name>`: the count of columns of the type `name`.
macro_rules! type_count {
    ($name:literal) => {
        Feature { name: concat!("t_", $name), of: |e| e.count_of($name) }
    };
}

/// The features, in the order of the vector. A feature that a table cannot give
/// is 0.
pub static FEATURES: &[Feature] = &[
    // The log of 1 plus the mean, and of 1 plus the most, of the rows over the train examples.
    Feature { name: "lmean", of: |e| mean(&e.train).ln_1p() as f32 },
    Feature { name: "lmax", of: |e| max(&e.train).ln_1p() as f32 },
    // The share of the train examples with rows.
    Feature { name: "share", of: |e| if e.train.is_empty() { 0.0 } else { (e.train.iter().filter(|&&rows| rows > 0.0).count() as f64 / e.train.len() as f64) as f32 } },
    Feature { name: "empty_all", of: |e| all_empty(&e.train) },
    // Empty on the train examples and on the test examples in the table.
    Feature { name: "empty_inputs", of: |e| all_empty(&e.inputs) },
    // The rows over the train examples; 0 on a task-level table.
    Feature { name: "rows_mean", of: |e| mean(train_of(e)) as f32 },
    Feature { name: "rows_min", of: |e| min(train_of(e)) as f32 },
    Feature { name: "rows_max", of: |e| max(train_of(e)) as f32 },
    Feature { name: "empty_any", of: |e| f32::from(!train_of(e).is_empty() && min(train_of(e)) == 0.0) },
    Feature { name: "one_row", of: |e| f32::from(!train_of(e).is_empty() && max(train_of(e)) == 1.0) },
    // The count of TableRows of an example, over the examples in the table.
    Feature { name: "rows_per_example_mean", of: |e| mean(&e.sets) as f32 },
    Feature { name: "rows_per_example_max", of: |e| max(&e.sets) as f32 },
    // The train examples (0 for a task-level table).
    Feature { name: "n_train", of: |e| e.n_train as f32 },
    // Whether the table's own state sequence stopped at the 256 cap.
    Feature { name: "nt", of: |e| f32::from(e.capped) },
    // The count of columns of each type, and of the types that have no feature of their own.
    type_count!("Int"),
    type_count!("Nat"),
    type_count!("Color"),
    type_count!("Example"),
    type_count!("Unit"),
    type_count!("Box"),
    type_count!("Position"),
    type_count!("Offset"),
    type_count!("Ident"),
    type_count!("C4"),
    type_count!("D4"),
    type_count!("Dir"),
    type_count!("DiagDir"),
    type_count!("Dir8"),
    type_count!("Axis"),
    type_count!("DiagAxis"),
    type_count!("Axis4"),
    type_count!("Sym"),
    type_count!("Sense"),
    type_count!("Pose"),
    type_count!("Record"),
    Feature { name: "t_other", of: |e| e.count_other() },
    // Whether the train examples all have one Set of TableRows; whether a test example has the first train example's; whether one has no rows.
    Feature { name: "same_hash", of: same_hash },
    Feature { name: "test_same", of: test_same },
    Feature { name: "test_empty", of: test_empty },
    // The columns, over the rows of all train examples: the count with at most one distinct value, the count with more,
    // the least and the most distinct values of a column, and the share of the rows that are distinct.
    Feature { name: "const_cols", of: |e| e.columns().map_or(0.0, |c| c[0]) },
    Feature { name: "live_cols", of: |e| e.columns().map_or(0.0, |c| c[1]) },
    Feature { name: "distinct_min", of: |e| e.columns().map_or(0.0, |c| c[2]) },
    Feature { name: "distinct_max", of: |e| e.columns().map_or(0.0, |c| c[3]) },
    Feature { name: "row_distinct", of: |e| e.columns().map_or(0.0, |c| c[4]) },
    // Against the train pairs, the mean over the train examples with rows. The rows over the input's area; 1 where the distinct
    // rows are as many as the cells that differ (the input and the output have one size) or as many as the output's cells off its
    // most common color.
    Feature { name: "rows_per_area", of: |e| e.fit()[0] },
    Feature { name: "rows_eq_changed", of: |e| e.fit()[1] },
    Feature { name: "rows_eq_ofg", of: |e| e.fit()[2] },
    // Over the Color columns: the share of the column's colors that the output has; 1 where one is not in the input but in the output;
    // 1 where the column has one color.
    Feature { name: "color_in_out", of: |e| e.fit()[3] },
    Feature { name: "color_new", of: |e| e.fit()[4] },
    Feature { name: "color_one", of: |e| e.fit()[5] },
    // Over the Position columns, the cells (row, column) of the rows against the input's and the output's cells off their most
    // common colors and, where the sizes are one, the cells that differ: the share of the input's area they cover; the share of
    // them in each of those sets; the overlap over the union and the precision and recall against the cells that differ; the
    // overlap over the union with the output's cells off its background.
    Feature { name: "cover", of: |e| e.fit()[6] },
    Feature { name: "fg_share", of: |e| e.fit()[7] },
    Feature { name: "ofg_share", of: |e| e.fit()[8] },
    Feature { name: "iou_changed", of: |e| e.fit()[9] },
    Feature { name: "prec_changed", of: |e| e.fit()[10] },
    Feature { name: "rec_changed", of: |e| e.fit()[11] },
    Feature { name: "iou_ofg", of: |e| e.fit()[12] },
    // 1 where the cells are all the cells of one color of the input.
    Feature { name: "is_input_color", of: |e| e.fit()[13] },
    // 1 where an 8-connected part of the cells (3 cells or more, at most 0.6 of the area), moved to the corner, is a part of the
    // input, of the output, of the output that the input does not have in place, or both of that and of the input.
    Feature { name: "shape_in", of: |e| e.fit()[14] },
    Feature { name: "shape_out", of: |e| e.fit()[15] },
    Feature { name: "shape_live", of: |e| e.fit()[16] },
    Feature { name: "shape_both_live", of: |e| e.fit()[17] },
    // The best mean overlap with the train outputs over the pairs of a Position or Box column and a Color column.
    Feature { name: "suit", of: |e| e.suit() },
    // Each TableRows painted on the train inputs against the train outputs, at the best pair of a Position and a Color column; the mean over an example's TableRows, then over the examples.
    Feature { name: "out_err", of: |e| e.out()[0] },
    Feature { name: "out_gain", of: |e| e.out()[1] },
    Feature { name: "out_exact", of: |e| e.out()[2] },
    Feature { name: "out_rec", of: |e| e.out()[3] },
    Feature { name: "out_prec", of: |e| e.out()[4] },
    Feature { name: "out_broke", of: |e| e.out()[5] },
    Feature { name: "out_oob", of: |e| e.out()[6] },
    Feature { name: "out_conflict", of: |e| e.out()[7] },
    Feature { name: "out_pair_best", of: |e| e.out()[8] },
    Feature { name: "out_pair_worst", of: |e| e.out()[9] },
    Feature { name: "out_pairs_exact", of: |e| e.out()[10] },
    Feature { name: "out_pairs_fixed", of: |e| e.out()[11] },
    Feature { name: "near_only_missing", of: |e| e.out()[12] },
    Feature { name: "near_only_extra", of: |e| e.out()[13] },
    Feature { name: "near_remap", of: |e| e.out()[14] },
    // A Position column alone, with the one fill color that fits most of its cells in each output.
    Feature { name: "fill_gain", of: |e| e.out()[15] },
    Feature { name: "fill_rec", of: |e| e.out()[16] },
    Feature { name: "fill_one_color", of: |e| e.out()[17] },
    Feature { name: "near_fill", of: |e| e.out()[18] },
];

/// The names of the features, in the order of the vector.
pub fn names() -> impl Iterator<Item = &'static str> {
    FEATURES.iter().map(|feature| feature.name)
}

/// The hash of the names of the features in their order, as 32 hexadecimal
/// digits (FNV-1a over 128 bits, each name followed by a zero byte).
pub fn version() -> String {
    let mut hash: u128 = 0x6c62272e07bb014262b821756295c58d;
    for name in names() {
        for &byte in name.as_bytes().iter().chain([&0u8]) {
            hash = (hash ^ u128::from(byte)).wrapping_mul(0x0000000001000000000000000000013b);
        }
    }
    format!("{hash:032x}")
}

/// The TableVector of `input`: one value for each of [`FEATURES`], in order.
pub fn vector(input: &Input<'_>) -> Vec<f32> {
    let examples = Examples::of(input);
    FEATURES.iter().map(|feature| (feature.of)(&examples)).collect()
}
