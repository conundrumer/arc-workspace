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
//!
//! The rows of a TableRows at one example are a group ([`Group`]). A feature family reads a
//! summary of each group, made for one column or one pair of columns at a time
//! ([`summary`]), and combines the summaries with the train pairs (`family.rs`).

use std::cell::OnceCell;
use std::borrow::Cow;
use std::ops::Range;

mod cells;
mod family;
mod group;
mod pair;
pub mod summary;

pub use group::{DistinctRows, Group};
pub use pair::{Grid, Pair};


use family::Uniques;
use summary::CellsSummary;

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

/// The count of values that `Examples::fit` gives.
pub(crate) const FIT: usize = 18;
/// The count of values that `Examples::out` gives.
pub(crate) const OUT: usize = 19;
/// The count of Position or Box columns, and of Color columns, that `suit` reads.
pub(crate) const SUIT_COLUMNS: usize = 2;

/// The rows of each example, as the features read them. The rows of a TableRows at one example are a group; the groups
/// of an example are in the order of `Input::rows`.
pub struct Examples<'a> {
    /// The groups, in the order of their examples: the groups of the train examples first.
    pub(crate) groups: Vec<Group<'a>>,
    /// The groups of each train example, in the order of the examples, as a range of `groups`. A task-level table has all its
    /// examples here.
    pub(crate) train_ex: Vec<Range<usize>>,
    /// The groups of each test example in the table.
    pub(crate) test_ex: Vec<Range<usize>>,
    /// The rows of each train example, as the mean over its groups.
    pub(crate) train: Vec<f64>,
    /// The rows of each train example and of each test example in the table.
    inputs: Vec<f64>,
    /// The count of TableRows of each example in the table, train examples included.
    sets: Vec<f64>,
    /// The count of train examples; 0 for a task-level table.
    pub(crate) n_train: usize,
    pub(crate) task_level: bool,
    capped: bool,
    /// The type of each column, without parameters.
    pub(crate) names: Vec<&'a str>,
    /// The index of the first cell of each column in a row, and its count of cells.
    pub(crate) columns_at: Vec<(usize, usize)>,
    pub(crate) pairs: &'a [Pair],
    /// The index of the first cell of each Color column in a row.
    pub(crate) color_at: Vec<usize>,
    /// The same, of each Position column.
    pub(crate) position_at: Vec<usize>,
    /// The same, of each Position or Box column.
    pub(crate) grid_at: Vec<usize>,
    /// The count of columns of each of `TYPE_NAMES`, then of the other types.
    type_counts: Vec<f32>,
    /// The train groups that differ in their rows.
    pub(crate) uniques: OnceCell<Uniques>,
    /// For each of the unique groups and each Position column: the group's cells.
    pub(crate) cell_summaries: OnceCell<Vec<CellsSummary>>,
    columns: OnceCell<Option<[f32; 5]>>,
    fit: OnceCell<[f32; FIT]>,
    suit: OnceCell<f32>,
    out: OnceCell<[f32; OUT]>,
}

impl<'a> Examples<'a> {
    pub fn of(input: &Input<'a>) -> Examples<'a> {
        let codes: Vec<u8> = input.types.iter().map(|name| type_code(name)).collect();
        let width: usize = codes.iter().map(|&code| cell_width(code)).sum();
        let offset: Option<usize> = input.example_column.map(|column| codes[..column].iter().map(|&code| cell_width(code)).sum());
        // The groups. A TableRows with an Example column is split on it, so that each part is the rows of one example;
        // an empty TableRows is a TableRows of 0 rows at the example that it names.
        let mut groups: Vec<Group<'a>> = Vec::with_capacity(input.rows.len());
        for rows in input.rows {
            let example = rows.example as usize;
            let whole = rows.cells.len() / width.max(1) * width;
            if rows.count == 0 {
                groups.push(Group::new(example, Cow::Borrowed(&[]), width, 0));
            } else if width == 0 {
                groups.push(Group::new(example, Cow::Borrowed(&[]), 0, rows.count));
            } else if let Some(at) = offset {
                let cells = &rows.cells[..whole];
                let n = whole / width;
                let value = |row: usize| cells[row * width + at];
                let ordered = (1..n).all(|row| value(row - 1) <= value(row));
                let mut order: Vec<usize> = (0..n).collect();
                if !ordered {
                    order.sort_by_key(|&row| value(row));
                }
                let mut from = 0;
                while from < n {
                    let mut to = from + 1;
                    while to < n && value(order[to]) == value(order[from]) {
                        to += 1;
                    }
                    let key = usize::try_from(value(order[from])).unwrap_or(usize::MAX);
                    let part = if ordered {
                        Cow::Borrowed(&cells[from * width..to * width])
                    } else {
                        Cow::Owned(order[from..to].iter().flat_map(|&row| cells[row * width..(row + 1) * width].iter().copied()).collect())
                    };
                    groups.push(Group::new(key, part, width, to - from));
                    from = to;
                }
            } else {
                groups.push(Group::new(example, Cow::Borrowed(&rows.cells[..whole]), width, whole / width));
            }
        }
        // The groups in the order of their examples, the groups of one example keeping their order.
        groups.sort_by_key(|group| group.key);
        let n_train = if input.task_level { 0 } else { input.train.len() };
        let mut train_ex: Vec<Range<usize>> = Vec::with_capacity(n_train);
        let mut at = 0;
        for example in 0..n_train {
            let start = at;
            while at < groups.len() && groups[at].key == example {
                at += 1;
            }
            train_ex.push(start..at);
        }
        // The other examples are the test examples, or all the examples of a task-level table.
        let mut others: Vec<Range<usize>> = Vec::new();
        while at < groups.len() {
            let start = at;
            while at < groups.len() && groups[at].key == groups[start].key {
                at += 1;
            }
            others.push(start..at);
        }
        let (train_ex, test_ex) = if input.task_level { (others, Vec::new()) } else { (train_ex, others) };
        let mean_of = |of: &Range<usize>| {
            if of.is_empty() { 0.0 } else { groups[of.clone()].iter().map(Group::len).sum::<usize>() as f64 / of.len() as f64 }
        };
        let train: Vec<f64> = train_ex.iter().map(mean_of).collect();
        let inputs: Vec<f64> = train.iter().copied().chain(test_ex.iter().map(mean_of)).collect();
        let sets = train_ex.iter().chain(&test_ex).map(|of| of.len() as f64).collect();
        let mut columns_at = Vec::with_capacity(codes.len());
        let mut next = 0;
        for &code in &codes {
            columns_at.push((next, cell_width(code)));
            next += cell_width(code);
        }
        let at_of = |wanted: &[u8]| codes.iter().zip(&columns_at).filter(|(code, _)| wanted.contains(code)).map(|(_, &(start, _))| start).collect::<Vec<usize>>();
        let (color_at, position_at, grid_at) = (at_of(&[COLOR]), at_of(&[POSITION]), at_of(&[POSITION, BOX]));
        let names: Vec<&'a str> = input.types.iter().map(|name| base_name(name)).collect();
        let mut type_counts = vec![0.0f32; TYPE_NAMES.len() + 1];
        for name in &names {
            type_counts[TYPE_NAMES.iter().position(|held| held == name).unwrap_or(TYPE_NAMES.len())] += 1.0;
        }
        Examples {
            groups,
            train_ex,
            test_ex,
            train,
            inputs,
            sets,
            n_train,
            task_level: input.task_level,
            capped: input.capped,
            names,
            columns_at,
            pairs: input.train,
            color_at,
            position_at,
            grid_at,
            type_counts,
            uniques: OnceCell::new(),
            cell_summaries: OnceCell::new(),
            columns: OnceCell::new(),
            fit: OnceCell::new(),
            suit: OnceCell::new(),
            out: OnceCell::new(),
        }
    }

    fn columns(&self) -> Option<[f32; 5]> {
        *self.columns.get_or_init(|| self.columns_of())
    }

    fn fit(&self) -> [f32; FIT] {
        *self.fit.get_or_init(|| self.fit_of())
    }

    fn suit(&self) -> f32 {
        *self.suit.get_or_init(|| self.suit_of())
    }

    fn out(&self) -> [f32; OUT] {
        *self.out.get_or_init(|| self.out_of())
    }

    /// The count of columns of the type named `name`.
    fn count_of(&self, name: &str) -> f32 {
        TYPE_NAMES.iter().position(|held| *held == name).map_or(0.0, |at| self.type_counts[at])
    }

    /// The count of columns of a type that has no feature of its own.
    fn count_other(&self) -> f32 {
        self.type_counts[TYPE_NAMES.len()]
    }

    /// The signature of an example: for each of its groups, its distinct rows, sorted; then the distinct ones of those, sorted.
    /// An example with no group has the one empty signature.
    fn signature(&self, groups: &Range<usize>) -> Vec<Vec<(u64, &[i32])>> {
        let mut signatures: Vec<Vec<(u64, &[i32])>> = self.groups[groups.clone()]
            .iter()
            .map(|group| {
                let mut rows: Vec<(u64, &[i32])> = {
                    let mut rows = Vec::new();
                    group.each_hashed(|hash, row| rows.push((hash, row)));
                    rows
                };
                rows.sort_unstable();
                rows
            })
            .collect();
        signatures.sort_unstable();
        signatures.dedup();
        if signatures.is_empty() {
            signatures.push(Vec::new());
        }
        signatures
    }

    /// Whether two examples have the same signature.
    fn same_rows(&self, a: &Range<usize>, b: &Range<usize>) -> bool {
        if a.len() == 1 && b.len() == 1 {
            // One group each: the signatures are the sets of rows of the groups.
            let (a, b) = (&self.groups[a.start], &self.groups[b.start]);
            return a.same_distinct_rows(b);
        }
        self.signature(a) == self.signature(b)
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
    f32::from(e.train_ex[1..].iter().all(|groups| e.same_rows(groups, &e.train_ex[0])))
}

/// Whether some test example in the table has the Set of TableRows of some train example.
fn test_same(e: &Examples<'_>) -> f32 {
    if e.n_train == 0 {
        return 0.0;
    }
    f32::from(e.test_ex.iter().any(|groups| e.train_ex.iter().any(|train| e.same_rows(groups, train))))
}

/// Whether some test example in the table has no rows.
fn test_empty(e: &Examples<'_>) -> f32 {
    f32::from(e.n_train > 0 && e.test_ex.iter().any(|groups| e.groups[groups.clone()].iter().all(Group::is_empty)))
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
