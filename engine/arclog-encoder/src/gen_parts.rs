//! The parts with holes, as native operators over relations. Each part's rows follow from its
//! relation and its columns, so no part is written for one feature.

use std::collections::HashMap;
use std::sync::Arc;

use crate::catalog_facts::{canon, normalized, symmetry_count};
use crate::gen_constants::{box_bits, encoding, margins_of, number_bits, number_of};
use crate::native::{hash_words, Cell, FastMap, Table, Val};

#[derive(Clone, Debug)]
pub enum PartStep {
    /// A relation's cells at a column that lie on a grid: (p).
    CellsOn { p: u16 },
    /// The grid's colors under those cells: (Col).
    ColorsUnder { p: u16 },
    /// The cells next to a relation's cells and not among them: (Q).
    Around { p: u16 },
    /// Each row with each neighbor of its cell: R, D, Q.
    Neighbors { p: u16 },
    /// Each row with the row and the column of its cell: R, A, Along.
    Split { p: u16 },
    /// Each row with its cell's margin on each edge: R, D, K.
    Margin { p: u16 },
    /// Each row with the sum of its cell's margins on each corner: R, Diag, K.
    CornerDist { p: u16 },
    /// Each row with the remainder of its cell's distance from each corner, over the count of axes: R, Diag, K.
    Parity { p: u16 },
    BorderDistance { p: u16 },
    /// The 8-connected pieces of a key's cells, or the 4-connected ones: keys, p, Id.
    Pieces { keys: Box<[u16]>, p: u16, four: bool },
    BoxOf { keys: Box<[u16]>, p: u16 },
    /// A key's cells relative to its box: keys, X_rel.
    RelBox { keys: Box<[u16]>, p: u16 },
    Count { keys: Box<[u16]> },
    /// A key with one value of a column: keys, f.
    OneValue { keys: Box<[u16]>, f: u16 },
    Several { keys: Box<[u16]>, f: u16 },
    /// No columns: each key has one value of the column.
    Determines { keys: Box<[u16]>, f: u16 },
    /// A key's values of a column at the greatest or the least of a number column: keys, t.
    Extreme { keys: Box<[u16]>, t: u16, score: u16, greatest: bool },
    /// The greatest or the least value of a number column: (n).
    NumberExtreme { n: u16, greatest: bool },
    /// Keys with one set of the other columns: keys, Id.
    ClassOf { keys: Box<[u16]> },
    /// A cell's class by its Moore neighborhood on a grid: p, Id.
    NeighborhoodClass { p: u16 },
    /// A cell's class by the multiset of its neighbors' colors: p, Id.
    NeighborColorClass { p: u16 },
    /// A cell's color on a grid, and how many neighbors share it: p, Col, N.
    SameColorNeighbors { p: u16 },
    /// A relation's rows whose value is the one most frequent of their key, in a key of two rows or more.
    MostFrequentRows { keys: Box<[u16]>, v: u16 },
    /// No columns: each key's rows all have a match in the second relation, or none do.
    DeterminesFlag { keys: Box<[u16]>, a: u16, b: u16 },
    /// Group properties: keys, Id or N; or the keys that hold.
    ShapeClass { keys: Box<[u16]>, p: u16, turned: bool },
    Holes { keys: Box<[u16]>, p: u16 },
    Symmetry { keys: Box<[u16]>, p: u16 },
    TouchesEdge { keys: Box<[u16]>, p: u16 },
    FillsBox { keys: Box<[u16]>, p: u16 },
    /// Each row with the grid's cells inside a box: R, P, Col.
    Inside { b: u16 },
    /// The translations that take a key's colored cells into a grid: keys, V.
    Occurs { keys: Box<[u16]>, p: u16, v: u16, turned: bool },
    /// The first relation's rows with a cell of the second on a row or a column.
    SharedLine { a: u16, b: u16 },
    /// The fewest eight-neighbor steps from a relation's cells over a grid: P, K.
    Distance { p: u16 },
    /// Each row with a box's or an offset's margin on each edge: R, D, K.
    BoxMargin { b: u16 },
    /// Each row with a box's extent on each axis, by a grid's extents: R, A, N.
    BoxExtent { b: u16 },
    /// Each row with the move from one cell to another of its frame: R, V.
    Displacement { a: u16, b: u16 },
    /// The extents of the frames of a column's cells: A, N.
    FrameExtent { p: u16 },
    /// A key's whole rows and columns, by the frame of its cells: keys, A, Along.
    FullLines { keys: Box<[u16]>, p: u16 },
    /// The extent of the box of a key's cells on each axis: keys, A, N.
    BoxSides { keys: Box<[u16]>, p: u16 },
    /// The margin of the box of a key's cells on each edge: keys, D, K.
    BoxMargins { keys: Box<[u16]>, p: u16 },
    /// A key's cells on each of its rows and columns: keys, A, Along, N.
    LineCounts { keys: Box<[u16]>, p: u16 },
    /// The cells of a column's frame that it does not hold: (P).
    Complement { p: u16 },
    /// The keys whose cells lie on one row, one column or one diagonal.
    Straight { keys: Box<[u16]>, p: u16 },
    /// A column of boxes read against the two grids. An input cell of a box of the output's
    /// extents stands for the output cell at its place in the box: B, P, X_rel, Col, and Col_2
    /// where the two colors differ.
    BoxRead { b: u16, kept: bool },
    /// As `BoxRead`, on a column of cells of a box's frame: B, X, P, Col, and Col_2.
    BoxFrameRead { b: u16, x: u16, kept: bool },
    /// As `BoxRead`, on a column of input cells: B, X, X_rel, Col, and Col_2.
    BoxCellRead { b: u16, x: u16, kept: bool },
    /// A relation's rows whose cell is, or is not, in a grid's diff: R.
    DiffRows { p: u16, output: bool, on: bool },
    /// The cells of a grid's diff at, or off, a relation's cells: P, Col.
    DiffCells { p: u16, output: bool, on: bool },
    /// The keys of a relation with no cell in a grid's diff: keys.
    DiffGroupsOff { keys: Box<[u16]>, p: u16, output: bool },
    /// Whether a column of each of two relations holds the same values.
    SameValues { a: u16, b: u16 },
    /// The first relation's rows with a cell inside a box of the second.
    InsideBoxes { a: u16, b: u16 },
    /// The first relation's rows whose box holds a cell of the second.
    BoxesHolding { a: u16, b: u16 },
    /// The keys of a relation whose cells are, up to a move, and a D4 element where `turned`, those of a key of the second.
    SameShape { keys: Box<[u16]>, a: u16, others: Box<[u16]>, b: u16, turned: bool },
    /// Whether two columns together give the output color at a relation's cells, where neither does alone.
    DeterminesJointly { p: u16, v: u16, w: u16 },
    /// The relation itself: a table's own rows as a term, for the roots of the table.
    Same,
    /// The values of a column at every example of a grid's Example column: (n).
    CommonValues { e: u16, n: u16 },
    /// Each example with a class per set of its rows over the other columns: E, Id.
    ExampleClasses { e: u16 },
}

impl PartStep {
    /// Whether the part has rows where its first relation has none.
    pub fn gives_rows_on_no_rows(&self) -> bool {
        matches!(self, PartStep::DiffCells { on: false, .. })
    }

    /// Whether the part's second relation is a relation hole, and no grid.
    pub fn reads_second_relation(&self) -> bool {
        matches!(self, PartStep::DeterminesFlag { .. } | PartStep::SharedLine { .. } | PartStep::SameValues { .. } | PartStep::InsideBoxes { .. } | PartStep::BoxesHolding { .. } | PartStep::SameShape { .. })
    }

    /// The columns of its first relation that its holes name.
    pub fn hole_columns(&self) -> Vec<u16> {
        let with = |keys: &[u16], rest: &[u16]| keys.iter().chain(rest).copied().collect::<Vec<u16>>();
        match self {
            PartStep::Complement { p } | PartStep::CellsOn { p } | PartStep::ColorsUnder { p } | PartStep::Around { p } | PartStep::Neighbors { p } | PartStep::Split { p } | PartStep::Margin { p } | PartStep::CornerDist { p } | PartStep::Parity { p } | PartStep::BorderDistance { p } | PartStep::NeighborhoodClass { p } | PartStep::NeighborColorClass { p } | PartStep::SameColorNeighbors { p } | PartStep::Distance { p } | PartStep::FrameExtent { p } => vec![*p],
            PartStep::Inside { b } | PartStep::BoxMargin { b } | PartStep::BoxExtent { b } | PartStep::BoxRead { b, .. } => vec![*b],
            PartStep::NumberExtreme { n, .. } => vec![*n],
            PartStep::SharedLine { a, .. } | PartStep::SameValues { a, .. } | PartStep::InsideBoxes { a, .. } | PartStep::BoxesHolding { a, .. } => vec![*a],
            PartStep::SameShape { keys, a, .. } => with(keys, &[*a]),
            PartStep::DeterminesJointly { p, v, w } => vec![*p, *v, *w],
            PartStep::Displacement { a, b } => vec![*a, *b],
            PartStep::BoxFrameRead { b, x, .. } | PartStep::BoxCellRead { b, x, .. } => vec![*b, *x],
            PartStep::BoxSides { keys, p } | PartStep::BoxMargins { keys, p } | PartStep::LineCounts { keys, p } | PartStep::Straight { keys, p } | PartStep::Pieces { keys, p, .. } | PartStep::BoxOf { keys, p } | PartStep::RelBox { keys, p } | PartStep::ShapeClass { keys, p, .. } | PartStep::Holes { keys, p } | PartStep::Symmetry { keys, p } | PartStep::TouchesEdge { keys, p } | PartStep::FillsBox { keys, p } | PartStep::FullLines { keys, p } => with(keys, &[*p]),
            PartStep::Count { keys } | PartStep::ClassOf { keys } => keys.to_vec(),
            PartStep::OneValue { keys, f } | PartStep::Several { keys, f } | PartStep::Determines { keys, f } => with(keys, &[*f]),
            PartStep::Extreme { keys, t, score, .. } => with(keys, &[*t, *score]),
            PartStep::MostFrequentRows { keys, v } => with(keys, &[*v]),
            PartStep::DeterminesFlag { keys, a, .. } => with(keys, &[*a]),
            PartStep::Occurs { keys, p, v, .. } => with(keys, &[*p, *v]),
            PartStep::DiffRows { p, .. } | PartStep::DiffCells { p, .. } => vec![*p],
            PartStep::DiffGroupsOff { keys, p, .. } => with(keys, &[*p]),
            PartStep::Same => Vec::new(),
            PartStep::CommonValues { e, n } => vec![*e, *n],
            PartStep::ExampleClasses { e } => vec![*e],
        }
    }

    /// The part's call over a relation `&r` of the columns `C0..`, with `grid` the grid hole and `second`
    /// the name of a column of a second relation `&s`.
    pub fn call_text(&self, grid: &str, second: &dyn Fn(u16) -> String) -> Option<String> {
        let c = |at: &u16| format!("C{at}");
        let list = |keys: &[u16]| format!("({})", keys.iter().map(|at| format!("C{at}")).collect::<Vec<_>>().join(" "));
        Some(match self {
            PartStep::Same | PartStep::CommonValues { .. } | PartStep::ExampleClasses { .. } => return None,
            PartStep::DiffRows { p, output, on } => format!("({}-{}-diff &r {})", if *on { "on" } else { "off" }, if *output { "output" } else { "input" }, c(p)),
            PartStep::DiffCells { p, output, on } => format!("({}-diff-{} &r {})", if *output { "output" } else { "input" }, if *on { "on" } else { "off" }, c(p)),
            PartStep::DiffGroupsOff { keys, p, output } => format!("(groups-off-{}-diff &r {} {})", if *output { "output" } else { "input" }, list(keys), c(p)),
            PartStep::CellsOn { p } => format!("(cells-on &r {} {grid})", c(p)),
            PartStep::ColorsUnder { p } => format!("(colors-under &r {} {grid})", c(p)),
            PartStep::Around { p } => format!("(around &r {})", c(p)),
            PartStep::Neighbors { p } => format!("(neighbors &r {})", c(p)),
            PartStep::Split { p } => format!("(split &r {})", c(p)),
            PartStep::Margin { p } => format!("(margin &r {})", c(p)),
            PartStep::CornerDist { p } => format!("(corner-dist &r {})", c(p)),
            PartStep::Parity { p } => format!("(parity &r {})", c(p)),
            PartStep::BorderDistance { p } => format!("(border-distance &r {})", c(p)),
            PartStep::Pieces { keys, p, four } => format!("({} &r {} {})", if *four { "pieces4" } else { "pieces" }, list(keys), c(p)),
            PartStep::BoxOf { keys, p } => format!("(box-of &r {} {})", list(keys), c(p)),
            PartStep::RelBox { keys, p } => format!("(cells-in-box &r {} {})", list(keys), c(p)),
            PartStep::Count { keys } => format!("(count &r {})", list(keys)),
            PartStep::OneValue { keys, f } => format!("(one-value &r {} {})", list(keys), c(f)),
            PartStep::Several { keys, f } => format!("(several &r {} {})", list(keys), c(f)),
            PartStep::Determines { keys, f } => format!("(determines &r {} {})", list(keys), c(f)),
            PartStep::Extreme { keys, t, score, greatest } => format!("({} &r {} {} {})", if *greatest { "greatest-by" } else { "least-by" }, list(keys), c(t), c(score)),
            PartStep::NumberExtreme { n, greatest } => format!("({} &r {})", if *greatest { "greatest" } else { "least" }, c(n)),
            PartStep::ClassOf { keys } => format!("(class-of &r {})", list(keys)),
            PartStep::NeighborhoodClass { p } => format!("(neighborhood-class &r {} {grid})", c(p)),
            PartStep::NeighborColorClass { p } => format!("(neighbor-color-class &r {} {grid})", c(p)),
            PartStep::SameColorNeighbors { p } => format!("(same-color-neighbors &r {} {grid})", c(p)),
            PartStep::MostFrequentRows { keys, v } => format!("(most-frequent-rows &r {} {})", list(keys), c(v)),
            PartStep::DeterminesFlag { keys, a, b } => format!("(determines-flag &r &s {} {} {})", list(keys), c(a), second(*b)),
            PartStep::ShapeClass { keys, p, turned } => format!("({} &r {} {})", if *turned { "shape-class-d4" } else { "shape-class" }, list(keys), c(p)),
            PartStep::Holes { keys, p } => format!("(holes &r {} {})", list(keys), c(p)),
            PartStep::Symmetry { keys, p } => format!("(symmetry &r {} {})", list(keys), c(p)),
            PartStep::TouchesEdge { keys, p } => format!("(touches-edge &r {} {})", list(keys), c(p)),
            PartStep::FillsBox { keys, p } => format!("(fills-box &r {} {})", list(keys), c(p)),
            PartStep::Inside { b } => format!("(inside &r {} {grid})", c(b)),
            PartStep::Occurs { keys, p, v, turned } => format!("({} &r {} {} {} {grid})", if *turned { "occurs-d4" } else { "occurs" }, list(keys), c(p), c(v)),
            PartStep::SharedLine { a, b } => format!("(shared-line &r &s {} {})", c(a), second(*b)),
            PartStep::SameValues { a, b } => format!("(same-values &r &s {} {})", c(a), second(*b)),
            PartStep::InsideBoxes { a, b } => format!("(inside-boxes &r &s {} {})", c(a), second(*b)),
            PartStep::BoxesHolding { a, b } => format!("(boxes-holding &r &s {} {})", c(a), second(*b)),
            PartStep::SameShape { keys, a, others, b, turned } => format!("({} &r &s {} {} ({}) {})", if *turned { "same-shape-d4" } else { "same-shape" }, list(keys), c(a), others.iter().map(|at| second(*at)).collect::<Vec<_>>().join(" "), second(*b)),
            PartStep::DeterminesJointly { p, v, w } => format!("(determines-jointly &r {} {} {})", c(p), c(v), c(w)),
            PartStep::Distance { p } => format!("(distance &r {} {grid})", c(p)),
            PartStep::BoxMargin { b } => format!("(box-margin &r {})", c(b)),
            PartStep::BoxExtent { b } => format!("(box-extent &r {} {grid})", c(b)),
            PartStep::Displacement { a, b } => format!("(displacement &r {} {})", c(a), c(b)),
            PartStep::FrameExtent { p } => format!("(frame-extent &r {})", c(p)),
            PartStep::FullLines { keys, p } => format!("(full-lines &r {} {})", list(keys), c(p)),
            PartStep::BoxSides { keys, p } => format!("(box-sides &r {} {})", list(keys), c(p)),
            PartStep::BoxMargins { keys, p } => format!("(box-margins &r {} {})", list(keys), c(p)),
            PartStep::LineCounts { keys, p } => format!("(line-counts &r {} {})", list(keys), c(p)),
            PartStep::Complement { p } => format!("(complement &r {})", c(p)),
            PartStep::Straight { keys, p } => format!("(straight &r {} {})", list(keys), c(p)),
            PartStep::BoxRead { b, kept } => format!("({} &r {})", if *kept { "box-kept" } else { "box-changed" }, c(b)),
            PartStep::BoxFrameRead { b, x, kept } => format!("({} &r {} {})", if *kept { "box-frame-kept" } else { "box-frame-changed" }, c(b), c(x)),
            PartStep::BoxCellRead { b, x, kept } => format!("({} &r {} {})", if *kept { "box-cell-kept" } else { "box-cell-changed" }, c(b), c(x)),
        })
    }
}

/// A value's rows in the order of its columns.
pub fn flat(value: &Val) -> Option<Arc<Table>> {
    let Val::Rows(parts) = value else { return Some(Table::new(1, Vec::new())) };
    if let [one] = parts.as_slice() {
        if one.columns.iter().enumerate().all(|(at, column)| usize::from(*column) == at) {
            return Some(one.table.clone());
        }
    }
    let arity: usize = parts.iter().map(|part| part.columns.len()).sum();
    if arity == 0 {
        return Some(Table::unit(true));
    }
    let rows = value.rows(arity, 1 << 18)?;
    let mut cells = Vec::with_capacity(rows.len() * arity);
    for row in &rows {
        cells.extend_from_slice(row);
    }
    Some(Table::new(arity, cells))
}

/// The dense id of each row's key, and the first row at each key.
fn key_ids<'t>(table: &'t Table, keys: &[u16]) -> (Vec<u32>, Vec<&'t [Cell]>) {
    let mut ids = Vec::with_capacity(table.len);
    let mut first = Vec::new();
    match keys {
        [] => {
            ids.resize(table.len, 0);
            if let Some(row) = table.rows().next() {
                if table.len > 0 {
                    first.push(row);
                }
            }
        }
        [one] => {
            let at = usize::from(*one);
            let mut seen: FastMap<Cell, u32> = FastMap::default();
            for row in table.rows() {
                let next = seen.len() as u32;
                ids.push(*seen.entry(row[at]).or_insert_with(|| {
                    first.push(row);
                    next
                }));
            }
        }
        [a, b] => {
            let (a, b) = (usize::from(*a), usize::from(*b));
            let mut seen: FastMap<u64, u32> = FastMap::default();
            for row in table.rows() {
                let next = seen.len() as u32;
                ids.push(*seen.entry(u64::from(row[a]) << 32 | u64::from(row[b])).or_insert_with(|| {
                    first.push(row);
                    next
                }));
            }
        }
        _ => {
            let mut seen: FastMap<u128, u32> = FastMap::default();
            for row in table.rows() {
                let key = hash_words(keys.iter().map(|at| u64::from(row[usize::from(*at)])));
                let next = seen.len() as u32;
                ids.push(*seen.entry(key).or_insert_with(|| {
                    first.push(row);
                    next
                }));
            }
        }
    }
    (ids, first)
}

fn push_key(out: &mut Vec<Cell>, row: &[Cell], keys: &[u16]) {
    for at in keys {
        out.push(row[usize::from(*at)]);
    }
}

/// A grid's cells and colors, read from its table of `P` and `Col`.
pub struct GridView {
    pub h: i32,
    pub w: i32,
    pub colors: Vec<Cell>,
    pub at: FastMap<Cell, Cell>,
}

thread_local! {
    static VIEWS: std::cell::RefCell<HashMap<u128, Arc<GridView>>> = std::cell::RefCell::new(HashMap::new());
}

thread_local! {
    static RIGHT_KEYS: std::cell::RefCell<HashMap<(u128, Box<[u16]>), Arc<Vec<u128>>>> = std::cell::RefCell::new(HashMap::new());
}

pub fn clear_views() {
    VIEWS.with(|views| views.borrow_mut().clear());
    RIGHT_KEYS.with(|keys| keys.borrow_mut().clear());
}

/// A relation's keys at columns, sorted, held while its table stands.
pub fn keys_of(value: &Val, at: &[u16]) -> Option<Arc<Vec<u128>>> {
    let compute = |table: &Table| {
        let mut keys: Vec<u128> = table.rows().map(|row| hash_words(at.iter().map(|column| u64::from(row[usize::from(*column)])))).collect();
        keys.sort_unstable();
        keys.dedup();
        Arc::new(keys)
    };
    if let Val::Rows(parts) = value {
        if let [one] = parts.as_slice() {
            if one.table.len >= 16 && one.columns.iter().enumerate().all(|(place, column)| usize::from(*column) == place) {
                let key = (one.table.hash, at.to_vec().into_boxed_slice());
                return Some(RIGHT_KEYS.with(|keys| keys.borrow_mut().entry(key).or_insert_with(|| compute(&one.table)).clone()));
            }
        }
    }
    let table = flat(value)?;
    Some(compute(&table))
}

fn view_of(table: &Arc<Table>) -> Arc<GridView> {
    let key = table.hash;
    VIEWS.with(|views| {
        views.borrow_mut().entry(key).or_insert_with(|| {
            let mut at = FastMap::default();
            let (mut h, mut w) = (0, 0);
            let mut colors = Vec::new();
            for row in table.rows() {
                let m = margins_of(row[0]);
                h = m[0] + m[1] + 1;
                w = m[2] + m[3] + 1;
                at.insert(row[0], row[1]);
            }
            if h > 0 && w > 0 {
                colors = vec![u32::MAX; (h * w) as usize];
                for row in table.rows() {
                    let m = margins_of(row[0]);
                    colors[(m[0] * w + m[2]) as usize] = row[1];
                }
            }
            Arc::new(GridView { h, w, colors, at })
        }).clone()
    })
}

fn grid_of(value: &Val) -> Option<Arc<GridView>> {
    let Val::Rows(parts) = value else { return None };
    let [one] = parts.as_slice() else { return None };
    Some(view_of(&one.table))
}

/// The input and the output of the leaf that holds both grids.
fn grids_of(value: &Val) -> Option<(Arc<GridView>, Arc<GridView>)> {
    let Val::Rows(parts) = value else { return None };
    let [input, output] = parts.as_slice() else { return None };
    Some((view_of(&input.table), view_of(&output.table)))
}

#[inline]
fn add_cell(a: [i32; 4], b: [i32; 4]) -> Cell {
    box_bits(a[0] + b[0], a[1] + b[1], a[2] + b[2], a[3] + b[3])
}

#[inline]
fn less_cell(a: [i32; 4], b: [i32; 4]) -> Cell {
    box_bits(a[0] - b[0], a[1] - b[1], a[2] - b[2], a[3] - b[3])
}

const STEPS: [(i32, i32); 8] = [(-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (-1, 1), (1, -1), (1, 1)];

#[inline]
fn moved(m: [i32; 4], dr: i32, dc: i32) -> Option<Cell> {
    let (t, b, l, r) = (m[0] + dr, m[1] - dr, m[2] + dc, m[3] - dc);
    (t >= 0 && b >= 0 && l >= 0 && r >= 0).then(|| box_bits(t, b, l, r))
}

fn rows_with(table: &Table, extra: usize, mut each: impl FnMut(&[Cell], &mut Vec<Cell>)) -> Val {
    let arity = table.arity + extra;
    let mut out: Vec<Cell> = Vec::with_capacity(table.cells.len() * 2);
    for row in table.rows() {
        each(row, &mut out);
    }
    // Each row keeps its own cells, so two rows stay apart.
    Val::of_table(Table::new(arity, out))
}

fn is_cell(m: &[i32; 4]) -> bool {
    m.iter().all(|margin| *margin >= 0)
}

/// Each key's cells, as (row, column) places of cells with no margin below 0.
fn cells_by_key(table: &Table, keys: &[u16], p: u16) -> (Vec<Vec<(u8, u8)>>, Vec<Vec<Cell>>) {
    let (ids, first) = key_ids(table, keys);
    let mut cells = vec![Vec::new(); first.len()];
    for (row, id) in table.rows().zip(&ids) {
        let m = margins_of(row[usize::from(p)]);
        if is_cell(&m) && m[0] < 256 && m[2] < 256 {
            cells[*id as usize].push((m[0] as u8, m[2] as u8));
        }
    }
    for held in &mut cells {
        held.sort_unstable();
        held.dedup();
    }
    let heads = first.iter().map(|row| keys.iter().map(|at| row[usize::from(*at)]).collect()).collect();
    (cells, heads)
}

/// Whether each key's cells at a column stand on one frame. The parts that read a cell as a row and
/// a column have no native value on any other column.
fn on_one_frame(table: &Table, keys: &[u16], p: u16) -> bool {
    let (ids, first) = key_ids(table, keys);
    let mut frames: Vec<Option<(i32, i32)>> = vec![None; first.len()];
    table.rows().zip(&ids).all(|(row, id)| {
        let m = margins_of(row[usize::from(p)]);
        let own = (m[0] + m[1], m[2] + m[3]);
        is_cell(&m) && *frames[*id as usize].get_or_insert(own) == own
    })
}

fn hash_cells(cells: &[(u8, u8)]) -> u32 {
    hash_words(cells.iter().map(|cell| u64::from(cell.0) << 8 | u64::from(cell.1))) as u32
}

fn enclosed_regions(list: &[(u8, u8)]) -> i64 {
    let (rmin, rmax) = (list.iter().map(|x| i32::from(x.0)).min().unwrap_or(0), list.iter().map(|x| i32::from(x.0)).max().unwrap_or(0));
    let (cmin, cmax) = (list.iter().map(|x| i32::from(x.1)).min().unwrap_or(0), list.iter().map(|x| i32::from(x.1)).max().unwrap_or(0));
    let (h, w) = ((rmax - rmin + 3) as usize, (cmax - cmin + 3) as usize);
    let mut seen = vec![false; h * w];
    for (r, c) in list {
        seen[(i32::from(*r) - rmin + 1) as usize * w + (i32::from(*c) - cmin + 1) as usize] = true;
    }
    let mut regions = 0;
    let mut stack = Vec::new();
    for start in 0..h * w {
        if seen[start] {
            continue;
        }
        regions += 1;
        seen[start] = true;
        stack.push(start);
        while let Some(at) = stack.pop() {
            let (r, c) = (at / w, at % w);
            let mut go = |next: usize| {
                if !seen[next] {
                    seen[next] = true;
                    stack.push(next);
                }
            };
            if r > 0 {
                go(at - w);
            }
            if r + 1 < h {
                go(at + w);
            }
            if c > 0 {
                go(at - 1);
            }
            if c + 1 < w {
                go(at + 1);
            }
        }
    }
    regions - 1
}

fn keyed_values(heads: &[Vec<Cell>], values: impl Iterator<Item = Option<Vec<Cell>>>, width: usize) -> Val {
    let mut out = Vec::new();
    for (head, value) in heads.iter().zip(values) {
        if let Some(value) = value {
            out.extend_from_slice(head);
            out.extend_from_slice(&value);
        }
    }
    Val::of_table(Table::distinct(width, out))
}

fn keys_only(heads: &[Vec<Cell>], holds: impl Iterator<Item = bool>, width: usize) -> Val {
    let mut out = Vec::new();
    let mut any = false;
    for (head, flag) in heads.iter().zip(holds) {
        if flag {
            any = true;
            out.extend_from_slice(head);
        }
    }
    if width == 0 {
        return Val::of_table(Table::unit(any));
    }
    Val::of_table(Table::distinct(width, out))
}

/// A cell's margins under an element of D4, in the order ID, LR, TB, HT, CW, CC, DG, AD.
fn image_margins(which: usize, m: [i32; 4]) -> [i32; 4] {
    let [t, b, l, r] = m;
    match which {
        0 => [t, b, l, r],
        1 => [t, b, r, l],
        2 => [b, t, l, r],
        3 => [b, t, r, l],
        4 => [l, r, b, t],
        5 => [r, l, t, b],
        6 => [l, r, t, b],
        _ => [r, l, b, t],
    }
}

/// The offsets that move a colored pattern onto a grid's cells: each `P` where `compose` of a pattern
/// cell and `P` is a grid cell of the cell's color, for every cell of the pattern.
fn moves_of(pattern: &[([i32; 4], Cell)], grid: &GridView) -> Vec<Cell> {
    let Some((anchor, color)) = pattern.first() else { return Vec::new() };
    let mut out = Vec::new();
    for r in 0..grid.h {
        for c in 0..grid.w {
            if grid.colors[(r * grid.w + c) as usize] != *color {
                continue;
            }
            let delta = [r - anchor[0], grid.h - 1 - r - anchor[1], c - anchor[2], grid.w - 1 - c - anchor[3]];
            if pattern.iter().all(|(m, held)| {
                let (y, b, z, e) = (m[0] + delta[0], m[1] + delta[1], m[2] + delta[2], m[3] + delta[3]);
                y >= 0 && z >= 0 && b >= 0 && e >= 0 && y < grid.h && z < grid.w && y + b == grid.h - 1 && z + e == grid.w - 1 && grid.colors[(y * grid.w + z) as usize] == *held
            }) {
                out.push(box_bits(delta[0], delta[1], delta[2], delta[3]));
            }
        }
    }
    out
}

impl PartStep {
    /// Whether the part is empty where its first relation is.
    pub fn apply(&self, children: &[&Val]) -> Val {
        let Some(first) = flat(children[0]) else { return Val::None };
        if matches!(children[0], Val::Empty) && !self.gives_rows_on_no_rows() {
            return Val::Empty;
        }
        self.run(&first, children).unwrap_or(Val::None)
    }

    fn run(&self, t: &Arc<Table>, children: &[&Val]) -> Option<Val> {
        let e = encoding();
        Some(match self {
            PartStep::DiffRows { p, output, on } => {
                let (input, other) = grids_of(children[1])?;
                let (one, two) = if *output { (&other, &input) } else { (&input, &other) };
                let mut out = Vec::new();
                for row in t.rows() {
                    let cell = row[usize::from(*p)];
                    let in_diff = one.at.get(&cell).is_some_and(|color| two.at.get(&cell) != Some(color));
                    if in_diff == *on {
                        out.extend_from_slice(row);
                    }
                }
                Val::of_table(Table::new(t.arity, out))
            }
            PartStep::DiffGroupsOff { keys, p, output } => {
                let (input, other) = grids_of(children[1])?;
                let (one, two) = if *output { (&other, &input) } else { (&input, &other) };
                let (ids, first) = key_ids(t, keys);
                let mut touching = vec![false; first.len()];
                for (row, id) in t.rows().zip(&ids) {
                    let cell = row[usize::from(*p)];
                    touching[*id as usize] |= one.at.get(&cell).is_some_and(|color| two.at.get(&cell) != Some(color));
                }
                let heads: Vec<Vec<Cell>> = first.iter().map(|row| keys.iter().map(|at| row[usize::from(*at)]).collect()).collect();
                keys_only(&heads, touching.into_iter().map(|held| !held), keys.len())
            }
            PartStep::DiffCells { p, output, on } => {
                let (input, other) = grids_of(children[1])?;
                let (one, two) = if *output { (&other, &input) } else { (&input, &other) };
                let held: std::collections::HashSet<Cell> = t.rows().map(|row| row[usize::from(*p)]).collect();
                let mut out = Vec::new();
                for (cell, color) in one.at.iter() {
                    if two.at.get(cell) != Some(color) && held.contains(cell) == *on {
                        out.extend_from_slice(&[*cell, *color]);
                    }
                }
                Val::of_table(Table::distinct(2, out))
            }
            PartStep::Same => children[0].clone(),
            PartStep::CommonValues { e, n } => {
                let examples = flat(children[1])?;
                let mut every: Vec<Cell> = examples.rows().map(|row| row[0]).collect();
                every.sort_unstable();
                every.dedup();
                let mut seen: FastMap<Cell, Vec<Cell>> = FastMap::default();
                for row in t.rows() {
                    seen.entry(row[usize::from(*n)]).or_default().push(row[usize::from(*e)]);
                }
                let mut out = Vec::new();
                for (value, mut held) in seen {
                    held.sort_unstable();
                    held.dedup();
                    if held == every {
                        out.push(value);
                    }
                }
                out.sort_unstable();
                Val::of_table(Table::new(1, out))
            }
            PartStep::ExampleClasses { e } => {
                let column = usize::from(*e);
                let mut sums: FastMap<Cell, u128> = FastMap::default();
                for row in t.rows() {
                    let word = hash_words(row.iter().enumerate().filter(|(at, _)| *at != column).map(|(_, cell)| u64::from(*cell)));
                    let held = sums.entry(row[column]).or_insert(0);
                    *held = held.wrapping_add(word);
                }
                let mut held: Vec<(Cell, u128)> = sums.into_iter().collect();
                held.sort_unstable();
                let mut out = Vec::with_capacity(held.len() * 2);
                for (example, sum) in held {
                    out.push(example);
                    // A class's label holds nothing but which rows it stands for.
                    out.push(sum as u32);
                }
                Val::of_table(Table::new(2, out))
            }
            PartStep::CellsOn { p } => {
                let grid = grid_of(children[1])?;
                let mut out: Vec<Cell> = t.rows().map(|row| row[usize::from(*p)]).filter(|cell| grid.at.contains_key(cell)).collect();
                out.sort_unstable();
                out.dedup();
                Val::of_table(Table::new(1, out))
            }
            PartStep::ColorsUnder { p } => {
                let grid = grid_of(children[1])?;
                let mut out: Vec<Cell> = t.rows().filter_map(|row| grid.at.get(&row[usize::from(*p)]).copied()).collect();
                out.sort_unstable();
                out.dedup();
                Val::of_table(Table::new(1, out))
            }
            PartStep::Around { p } => {
                let mut own: Vec<Cell> = t.rows().map(|row| row[usize::from(*p)]).collect();
                own.sort_unstable();
                own.dedup();
                let mut out = Vec::new();
                for cell in &own {
                    let m = margins_of(*cell);
                    for (dr, dc) in STEPS {
                        if let Some(next) = moved(m, dr, dc) {
                            if own.binary_search(&next).is_err() {
                                out.push(next);
                            }
                        }
                    }
                }
                out.sort_unstable();
                out.dedup();
                Val::of_table(Table::new(1, out))
            }
            PartStep::Neighbors { p } => rows_with(t, 2, |row, out| {
                let m = margins_of(row[usize::from(*p)]);
                for (at, (dr, dc)) in STEPS.iter().enumerate() {
                    if let Some(next) = moved(m, *dr, *dc) {
                        out.extend_from_slice(row);
                        out.push(e.dirs[at]);
                        out.push(next);
                    }
                }
            }),
            PartStep::Split { p } => rows_with(t, 2, |row, out| {
                let m = margins_of(row[usize::from(*p)]);
                out.extend_from_slice(row);
                out.push(e.axes[0]);
                out.push(box_bits(m[0], m[1], 0, 0));
                out.extend_from_slice(row);
                out.push(e.axes[1]);
                out.push(box_bits(0, 0, m[2], m[3]));
            }),
            PartStep::Margin { p } => rows_with(t, 2, |row, out| {
                let m = margins_of(row[usize::from(*p)]);
                for at in 0..4 {
                    out.extend_from_slice(row);
                    out.push(e.dirs[at]);
                    out.push(number_bits(i64::from(m[at])));
                }
            }),
            PartStep::CornerDist { p } => rows_with(t, 2, |row, out| {
                let m = margins_of(row[usize::from(*p)]);
                for (at, (a, b)) in [(0, 2), (0, 3), (1, 2), (1, 3)].iter().enumerate() {
                    out.extend_from_slice(row);
                    out.push(e.dirs[4 + at]);
                    out.push(number_bits(i64::from(m[*a] + m[*b])));
                }
            }),
            PartStep::Parity { p } => rows_with(t, 2, |row, out| {
                let m = margins_of(row[usize::from(*p)]);
                for (at, (a, b)) in [(0, 2), (0, 3), (1, 2), (1, 3)].iter().enumerate() {
                    out.extend_from_slice(row);
                    out.push(e.dirs[4 + at]);
                    out.push(number_bits(i64::from((m[*a] + m[*b]).rem_euclid(2))));
                }
            }),
            PartStep::BorderDistance { p } => rows_with(t, 1, |row, out| {
                let m = margins_of(row[usize::from(*p)]);
                out.extend_from_slice(row);
                out.push(number_bits(i64::from(m[0].min(m[1]).min(m[2]).min(m[3]))));
            }),
            PartStep::Pieces { keys, p, four } => {
                let (ids, first) = key_ids(t, keys);
                let mut cells: Vec<Vec<Cell>> = vec![Vec::new(); first.len()];
                for (row, id) in t.rows().zip(&ids) {
                    cells[*id as usize].push(row[usize::from(*p)]);
                }
                let mut out = Vec::new();
                for (held, head) in cells.iter_mut().zip(&first) {
                    held.sort_unstable();
                    held.dedup();
                    let mut seen = vec![false; held.len()];
                    for start in 0..held.len() {
                        if seen[start] {
                            continue;
                        }
                        seen[start] = true;
                        let mut stack = vec![start];
                        let mut piece = Vec::new();
                        while let Some(at) = stack.pop() {
                            piece.push(held[at]);
                            let m = margins_of(held[at]);
                            for (dr, dc) in &STEPS[..if *four { 4 } else { 8 }] {
                                if let Some(next) = moved(m, *dr, *dc) {
                                    if let Ok(place) = held.binary_search(&next) {
                                        if !seen[place] {
                                            seen[place] = true;
                                            stack.push(place);
                                        }
                                    }
                                }
                            }
                        }
                        // An Ident labels the set of its members, as `Connectivity` interns it.
                        piece.sort_unstable();
                        let label = hash_words(piece.iter().map(|cell| u64::from(*cell))) as u32;
                        for cell in &piece {
                            push_key(&mut out, head, keys);
                            out.push(*cell);
                            out.push(label);
                        }
                    }
                }
                Val::of_table(Table::distinct(keys.len() + 2, out))
            }
            PartStep::BoxOf { keys, p } => {
                let (ids, first) = key_ids(t, keys);
                let mut spans = vec![[i32::MAX; 4]; first.len()];
                for (row, id) in t.rows().zip(&ids) {
                    let m = margins_of(row[usize::from(*p)]);
                    let held = &mut spans[*id as usize];
                    for at in 0..4 {
                        held[at] = held[at].min(m[at]);
                    }
                }
                let mut out = Vec::new();
                for (span, head) in spans.iter().zip(&first) {
                    push_key(&mut out, head, keys);
                    out.push(box_bits(span[0], span[1], span[2], span[3]));
                }
                Val::of_table(Table::new(keys.len() + 1, out))
            }
            PartStep::RelBox { keys, p } => {
                let (ids, first) = key_ids(t, keys);
                let mut spans = vec![[i32::MAX; 4]; first.len()];
                for (row, id) in t.rows().zip(&ids) {
                    let m = margins_of(row[usize::from(*p)]);
                    let held = &mut spans[*id as usize];
                    for at in 0..4 {
                        held[at] = held[at].min(m[at]);
                    }
                }
                let mut out = Vec::new();
                for (row, id) in t.rows().zip(&ids) {
                    let m = margins_of(row[usize::from(*p)]);
                    let s = &spans[*id as usize];
                    push_key(&mut out, row, keys);
                    out.push(box_bits(m[0] - s[0], m[1] - s[1], m[2] - s[2], m[3] - s[3]));
                }
                Val::of_table(Table::distinct(keys.len() + 1, out))
            }
            PartStep::Count { keys } => {
                let (ids, first) = key_ids(t, keys);
                let mut counts = vec![0i64; first.len()];
                for id in &ids {
                    counts[*id as usize] += 1;
                }
                let mut out = Vec::new();
                for (count, head) in counts.iter().zip(&first) {
                    push_key(&mut out, head, keys);
                    out.push(number_bits(*count));
                }
                Val::of_table(Table::new(keys.len() + 1, out))
            }
            PartStep::OneValue { keys, f } | PartStep::Several { keys, f } | PartStep::Determines { keys, f } => {
                let (ids, first) = key_ids(t, keys);
                let mut held: Vec<Option<Cell>> = vec![None; first.len()];
                let mut many = vec![false; first.len()];
                for (row, id) in t.rows().zip(&ids) {
                    let value = row[usize::from(*f)];
                    match held[*id as usize] {
                        None => held[*id as usize] = Some(value),
                        Some(own) if own != value => many[*id as usize] = true,
                        _ => {}
                    }
                }
                match self {
                    // On no rows it is false, as an `ALL` form's empty domain is.
                    PartStep::Determines { .. } => Val::of_table(Table::unit(!first.is_empty() && !many.iter().any(|flag| *flag))),
                    PartStep::Several { .. } => {
                        let mut out = Vec::new();
                        for (flag, head) in many.iter().zip(&first) {
                            if *flag {
                                push_key(&mut out, head, keys);
                            }
                        }
                        if keys.is_empty() {
                            Val::of_table(Table::unit(many.iter().any(|flag| *flag)))
                        } else {
                            Val::of_table(Table::distinct(keys.len(), out))
                        }
                    }
                    _ => {
                        let mut out = Vec::new();
                        for ((flag, value), head) in many.iter().zip(&held).zip(&first) {
                            if !*flag {
                                push_key(&mut out, head, keys);
                                out.push((*value)?);
                            }
                        }
                        Val::of_table(Table::new(keys.len() + 1, out))
                    }
                }
            }
            PartStep::Extreme { keys, t: column, score, greatest } => {
                let (ids, first) = key_ids(t, keys);
                let mut best: Vec<Option<i64>> = vec![None; first.len()];
                for (row, id) in t.rows().zip(&ids) {
                    let value = number_of(row[usize::from(*score)]);
                    let held = &mut best[*id as usize];
                    *held = Some(held.map_or(value, |own| if *greatest { own.max(value) } else { own.min(value) }));
                }
                let mut out = Vec::new();
                for (row, id) in t.rows().zip(&ids) {
                    if Some(number_of(row[usize::from(*score)])) == best[*id as usize] {
                        push_key(&mut out, row, keys);
                        out.push(row[usize::from(*column)]);
                    }
                }
                Val::of_table(Table::distinct(keys.len() + 1, out))
            }
            PartStep::NumberExtreme { n, greatest } => {
                let values = t.rows().map(|row| number_of(row[usize::from(*n)]));
                let held = if *greatest { values.max() } else { values.min() };
                Val::of_table(Table::new(1, held.map_or_else(Vec::new, |value| vec![number_bits(value)])))
            }
            PartStep::ClassOf { keys } => {
                let (ids, first) = key_ids(t, keys);
                let mut sums = vec![0u128; first.len()];
                for (row, id) in t.rows().zip(&ids) {
                    let rest = row.iter().enumerate().filter(|(at, _)| !keys.contains(&(*at as u16))).map(|(_, cell)| u64::from(*cell));
                    sums[*id as usize] = sums[*id as usize].wrapping_add(hash_words(rest));
                }
                let mut out = Vec::new();
                for (sum, head) in sums.iter().zip(&first) {
                    push_key(&mut out, head, keys);
                    out.push(*sum as u32);
                }
                Val::of_table(Table::new(keys.len() + 1, out))
            }
            PartStep::NeighborhoodClass { p } | PartStep::NeighborColorClass { p } | PartStep::SameColorNeighbors { p } => {
                let grid = grid_of(children[1])?;
                let mut own: Vec<Cell> = t.rows().map(|row| row[usize::from(*p)]).filter(|cell| grid.at.contains_key(cell)).collect();
                own.sort_unstable();
                own.dedup();
                let mut out = Vec::new();
                for cell in &own {
                    let m = margins_of(*cell);
                    let mine = grid.at[cell];
                    let mut held = [u32::MAX; 8];
                    let mut same = 0i64;
                    for (at, (dr, dc)) in STEPS.iter().enumerate() {
                        if let Some(color) = moved(m, *dr, *dc).and_then(|next| grid.at.get(&next)) {
                            held[at] = *color;
                            same += i64::from(*color == mine);
                        }
                    }
                    out.push(*cell);
                    match self {
                        PartStep::NeighborhoodClass { .. } => {
                            out.push(hash_words(held.iter().map(|x| u64::from(*x)).chain([u64::from(mine)])) as u32);
                        }
                        PartStep::NeighborColorClass { .. } => {
                            let mut sorted = held;
                            sorted.sort_unstable();
                            out.push(hash_words(sorted.iter().map(|x| u64::from(*x))) as u32);
                        }
                        _ => {
                            out.push(mine);
                            out.push(number_bits(same));
                        }
                    }
                }
                let width = if matches!(self, PartStep::SameColorNeighbors { .. }) { 3 } else { 2 };
                Val::of_table(Table::new(width, out))
            }
            PartStep::MostFrequentRows { keys, v } => {
                let (ids, first) = key_ids(t, keys);
                let mut counts: FastMap<(u32, Cell), u32> = FastMap::default();
                for (row, id) in t.rows().zip(&ids) {
                    *counts.entry((*id, row[usize::from(*v)])).or_insert(0) += 1;
                }
                let mut best = vec![0u32; first.len()];
                for ((id, _), count) in &counts {
                    best[*id as usize] = best[*id as usize].max(*count);
                }
                let mut out = Vec::new();
                for (row, id) in t.rows().zip(&ids) {
                    if counts[&(*id, row[usize::from(*v)])] == best[*id as usize] {
                        out.extend_from_slice(row);
                    }
                }
                Val::of_table(Table::new(t.arity, out))
            }
            PartStep::DeterminesFlag { keys, a, b } => {
                let other = flat(children[1])?;
                let mut held: Vec<Cell> = other.rows().map(|row| row[usize::from(*b)]).collect();
                held.sort_unstable();
                held.dedup();
                let (ids, first) = key_ids(t, keys);
                let mut flag: Vec<Option<bool>> = vec![None; first.len()];
                let mut holds = true;
                for (row, id) in t.rows().zip(&ids) {
                    let found = held.binary_search(&row[usize::from(*a)]).is_ok();
                    match flag[*id as usize] {
                        None => flag[*id as usize] = Some(found),
                        Some(own) if own != found => holds = false,
                        _ => {}
                    }
                }
                Val::of_table(Table::unit(holds && !first.is_empty()))
            }
            PartStep::ShapeClass { keys, p, turned } => {
                if !on_one_frame(t, keys, *p) {
                    return None;
                }
                let (cells, heads) = cells_by_key(t, keys, *p);
                keyed_values(&heads, cells.iter().map(|held| (!held.is_empty()).then(|| vec![hash_cells(&if *turned { canon(held) } else { normalized(held) })])), keys.len() + 1)
            }
            PartStep::Holes { keys, p } => {
                if !on_one_frame(t, keys, *p) {
                    return None;
                }
                let (cells, heads) = cells_by_key(t, keys, *p);
                keyed_values(&heads, cells.iter().map(|held| (!held.is_empty()).then(|| vec![number_bits(enclosed_regions(held))])), keys.len() + 1)
            }
            PartStep::Symmetry { keys, p } => {
                if !on_one_frame(t, keys, *p) {
                    return None;
                }
                let (cells, heads) = cells_by_key(t, keys, *p);
                keyed_values(&heads, cells.iter().map(|held| (!held.is_empty()).then(|| vec![number_bits(i64::from(symmetry_count(held)))])), keys.len() + 1)
            }
            PartStep::TouchesEdge { keys, p } => {
                let (ids, first) = key_ids(t, keys);
                let mut touching = vec![false; first.len()];
                for (row, id) in t.rows().zip(&ids) {
                    touching[*id as usize] |= margins_of(row[usize::from(*p)]).contains(&0);
                }
                let heads: Vec<Vec<Cell>> = first.iter().map(|row| keys.iter().map(|at| row[usize::from(*at)]).collect()).collect();
                keys_only(&heads, touching.into_iter(), keys.len())
            }
            PartStep::FillsBox { keys, p } => {
                if !on_one_frame(t, keys, *p) {
                    return None;
                }
                let (cells, heads) = cells_by_key(t, keys, *p);
                keys_only(&heads, cells.iter().map(|held| {
                    let (rmin, rmax) = (held.iter().map(|x| x.0).min().unwrap_or(0), held.iter().map(|x| x.0).max().unwrap_or(0));
                    let (cmin, cmax) = (held.iter().map(|x| x.1).min().unwrap_or(0), held.iter().map(|x| x.1).max().unwrap_or(0));
                    !held.is_empty() && held.len() == (rmax - rmin + 1) as usize * (cmax - cmin + 1) as usize
                }), keys.len())
            }
            PartStep::Inside { b } => {
                let grid = grid_of(children[1])?;
                let mut out = Vec::new();
                if t.len > 200 {
                    return None;
                }
                for row in t.rows() {
                    let m = margins_of(row[usize::from(*b)]);
                    let (r0, r1, c0, c1) = (m[0].max(0), grid.h - 1 - m[1].max(0), m[2].max(0), grid.w - 1 - m[3].max(0));
                    for r in r0..=r1 {
                        for c in c0..=c1 {
                            out.extend_from_slice(row);
                            out.push(box_bits(r, grid.h - 1 - r, c, grid.w - 1 - c));
                            out.push(grid.colors[(r * grid.w + c) as usize]);
                        }
                    }
                }
                Val::of_table(Table::distinct(t.arity + 2, out))
            }
            PartStep::Occurs { keys, p, v, turned } => {
                let grid = grid_of(children[1])?;
                let (ids, first) = key_ids(t, keys);
                if first.len() > 60 {
                    return None;
                }
                let mut patterns: Vec<Vec<([i32; 4], Cell)>> = vec![Vec::new(); first.len()];
                for (row, id) in t.rows().zip(&ids) {
                    patterns[*id as usize].push((margins_of(row[usize::from(*p)]), row[usize::from(*v)]));
                }
                let mut out = Vec::new();
                for (pattern, head) in patterns.iter_mut().zip(&first) {
                    pattern.sort_unstable();
                    pattern.dedup();
                    if pattern.len() > 900 {
                        return None;
                    }
                    for which in 0..if *turned { 8 } else { 1 } {
                        let image: Vec<([i32; 4], Cell)> = pattern.iter().map(|(m, color)| (image_margins(which, *m), *color)).collect();
                        for moved in moves_of(&image, &grid) {
                            push_key(&mut out, head, keys);
                            out.push(moved);
                        }
                    }
                }
                Val::of_table(Table::distinct(keys.len() + 1, out))
            }
            PartStep::SameValues { a, b } => {
                let other = flat(children[1])?;
                let values = |table: &Table, at: u16| -> Vec<Cell> {
                    let mut held: Vec<Cell> = table.rows().map(|row| row[usize::from(at)]).collect();
                    held.sort_unstable();
                    held.dedup();
                    held
                };
                Val::of_table(Table::unit(t.len > 0 && values(t, *a) == values(&other, *b)))
            }
            PartStep::InsideBoxes { a, b } | PartStep::BoxesHolding { a, b } => {
                let other = flat(children[1])?;
                let mut others: Vec<[i32; 4]> = other.rows().map(|row| margins_of(row[usize::from(*b)])).collect();
                others.sort_unstable();
                others.dedup();
                if others.len() * t.len > 4_000_000 {
                    return None;
                }
                let inside = matches!(self, PartStep::InsideBoxes { .. });
                let mut out = Vec::new();
                for row in t.rows() {
                    let own = margins_of(row[usize::from(*a)]);
                    let met = others.iter().any(|held| (0..4).all(|at| if inside { own[at] >= held[at] } else { held[at] >= own[at] }));
                    if met {
                        out.extend_from_slice(row);
                    }
                }
                Val::of_table(Table::new(t.arity, out))
            }
            PartStep::SameShape { keys, a, others, b, turned } => {
                let other = flat(children[1])?;
                if !on_one_frame(t, keys, *a) || !on_one_frame(&other, others, *b) {
                    return None;
                }
                let shape = |held: &Vec<(u8, u8)>| hash_cells(&if *turned { canon(held) } else { normalized(held) });
                let (cells, heads) = cells_by_key(t, keys, *a);
                let (other_cells, _) = cells_by_key(&other, others, *b);
                let seen: std::collections::HashSet<u32> = other_cells.iter().filter(|held| !held.is_empty()).map(shape).collect();
                keys_only(&heads, cells.iter().map(|held| !held.is_empty() && seen.contains(&shape(held))), keys.len())
            }
            PartStep::DeterminesJointly { p, v, w } => {
                let (_, output) = grids_of(children[1])?;
                let mut both: FastMap<(Cell, Cell), (Cell, bool)> = FastMap::default();
                let mut first: FastMap<Cell, (Cell, bool)> = FastMap::default();
                let mut second: FastMap<Cell, (Cell, bool)> = FastMap::default();
                for row in t.rows() {
                    let Some(color) = output.at.get(&row[usize::from(*p)]) else { continue };
                    let (one, other) = (row[usize::from(*v)], row[usize::from(*w)]);
                    let held = both.entry((one, other)).or_insert((*color, false));
                    held.1 |= held.0 != *color;
                    let held = first.entry(one).or_insert((*color, false));
                    held.1 |= held.0 != *color;
                    let held = second.entry(other).or_insert((*color, false));
                    held.1 |= held.0 != *color;
                }
                Val::of_table(Table::unit(first.values().any(|held| held.1) && second.values().any(|held| held.1) && !both.values().any(|held| held.1)))
            }
            PartStep::SharedLine { a, b } => {
                let other = flat(children[1])?;
                // `same_line`: the two cells have one margin on an edge of the other axis.
                let mut margins: [Vec<i32>; 4] = Default::default();
                for row in other.rows() {
                    let m = margins_of(row[usize::from(*b)]);
                    for at in 0..4 {
                        margins[at].push(m[at]);
                    }
                }
                for held in &mut margins {
                    held.sort_unstable();
                    held.dedup();
                }
                let mut out = Vec::new();
                for row in t.rows() {
                    let m = margins_of(row[usize::from(*a)]);
                    if (0..4).any(|at| margins[at].binary_search(&m[at]).is_ok()) {
                        out.extend_from_slice(row);
                    }
                }
                Val::of_table(Table::new(t.arity, out))
            }
            PartStep::Distance { p } => {
                let grid = grid_of(children[1])?;
                let (h, w) = (grid.h, grid.w);
                let mut away = vec![i64::MAX; (h * w) as usize];
                let mut layer = Vec::new();
                for row in t.rows() {
                    let cell = row[usize::from(*p)];
                    if grid.at.contains_key(&cell) {
                        let m = margins_of(cell);
                        let at = (m[0] * w + m[2]) as usize;
                        if away[at] == i64::MAX {
                            away[at] = 0;
                            layer.push(at);
                        }
                    }
                }
                let mut k = 0;
                while !layer.is_empty() {
                    k += 1;
                    let mut ahead = Vec::new();
                    for at in &layer {
                        let (r, c) = ((*at as i32) / w, (*at as i32) % w);
                        for (dr, dc) in STEPS {
                            let (y, z) = (r + dr, c + dc);
                            if y >= 0 && z >= 0 && y < h && z < w && away[(y * w + z) as usize] == i64::MAX {
                                away[(y * w + z) as usize] = k;
                                ahead.push((y * w + z) as usize);
                            }
                        }
                    }
                    layer = ahead;
                }
                let mut out = Vec::new();
                for r in 0..h {
                    for c in 0..w {
                        let held = away[(r * w + c) as usize];
                        if held != i64::MAX {
                            out.push(box_bits(r, h - 1 - r, c, w - 1 - c));
                            out.push(number_bits(held));
                        }
                    }
                }
                Val::of_table(Table::new(2, out))
            }
            PartStep::BoxMargin { b } => rows_with(t, 2, |row, out| {
                let m = margins_of(row[usize::from(*b)]);
                for at in 0..4 {
                    out.extend_from_slice(row);
                    out.push(e.dirs[at]);
                    out.push(number_bits(i64::from(m[at])));
                }
            }),
            PartStep::BoxExtent { b } => {
                let grid = grid_of(children[1])?;
                rows_with(t, 2, |row, out| {
                    let m = margins_of(row[usize::from(*b)]);
                    let (along, across) = (grid.h - m[0] - m[1], grid.w - m[2] - m[3]);
                    if along > 0 && across > 0 {
                        out.extend_from_slice(row);
                        out.push(e.axes[0]);
                        out.push(number_bits(i64::from(along)));
                        out.extend_from_slice(row);
                        out.push(e.axes[1]);
                        out.push(number_bits(i64::from(across)));
                    }
                })
            }
            PartStep::Displacement { a, b } => rows_with(t, 1, |row, out| {
                let (from, to) = (margins_of(row[usize::from(*a)]), margins_of(row[usize::from(*b)]));
                if from[0] + from[1] == to[0] + to[1] && from[2] + from[3] == to[2] + to[3] {
                    out.extend_from_slice(row);
                    out.push(less_cell(to, from));
                }
            }),
            PartStep::FrameExtent { p } => {
                let mut along: Vec<i32> = Vec::new();
                let mut across: Vec<i32> = Vec::new();
                for row in t.rows() {
                    let m = margins_of(row[usize::from(*p)]);
                    along.push(m[0] + m[1] + 1);
                    across.push(m[2] + m[3] + 1);
                }
                along.sort_unstable();
                along.dedup();
                across.sort_unstable();
                across.dedup();
                let mut out = Vec::with_capacity((along.len() + across.len()) * 2);
                for value in along {
                    out.push(e.axes[0]);
                    out.push(number_bits(i64::from(value)));
                }
                for value in across {
                    out.push(e.axes[1]);
                    out.push(number_bits(i64::from(value)));
                }
                Val::of_table(Table::new(2, out))
            }
            PartStep::BoxSides { keys, p } | PartStep::BoxMargins { keys, p } => {
                if !on_one_frame(t, keys, *p) {
                    return None;
                }
                let (ids, first) = key_ids(t, keys);
                let mut spans: Vec<Option<[i32; 4]>> = vec![None; first.len()];
                let mut frames: Vec<(i32, i32)> = vec![(0, 0); first.len()];
                for (row, id) in t.rows().zip(&ids) {
                    let m = margins_of(row[usize::from(*p)]);
                    frames[*id as usize] = (m[0] + m[1] + 1, m[2] + m[3] + 1);
                    let held = spans[*id as usize].get_or_insert([m[0], m[0], m[2], m[2]]);
                    *held = [held[0].min(m[0]), held[1].max(m[0]), held[2].min(m[2]), held[3].max(m[2])];
                }
                let mut out = Vec::new();
                for (at, span) in spans.iter().enumerate() {
                    let Some([r0, r1, c0, c1]) = span else { continue };
                    if matches!(self, PartStep::BoxSides { .. }) {
                        for (axis, long) in [(0, r1 - r0 + 1), (1, c1 - c0 + 1)] {
                            push_key(&mut out, first[at], keys);
                            out.push(e.axes[axis]);
                            out.push(number_bits(i64::from(long)));
                        }
                    } else {
                        let (h, w) = frames[at];
                        for (edge, margin) in [*r0, h - 1 - r1, *c0, w - 1 - c1].into_iter().enumerate() {
                            push_key(&mut out, first[at], keys);
                            out.push(e.dirs[edge]);
                            out.push(number_bits(i64::from(margin)));
                        }
                    }
                }
                Val::of_table(Table::distinct(keys.len() + 2, out))
            }
            PartStep::LineCounts { keys, p } => {
                if !on_one_frame(t, keys, *p) {
                    return None;
                }
                let (ids, first) = key_ids(t, keys);
                let mut lines: FastMap<(u32, bool, i32, i32), i64> = FastMap::default();
                let mut seen: std::collections::HashSet<(u32, Cell)> = std::collections::HashSet::new();
                for (row, id) in t.rows().zip(&ids) {
                    let cell = row[usize::from(*p)];
                    if seen.insert((*id, cell)) {
                        let m = margins_of(cell);
                        *lines.entry((*id, true, m[0], m[1])).or_insert(0) += 1;
                        *lines.entry((*id, false, m[2], m[3])).or_insert(0) += 1;
                    }
                }
                let mut out = Vec::new();
                for ((id, is_row, a, b), count) in &lines {
                    push_key(&mut out, first[*id as usize], keys);
                    out.push(e.axes[usize::from(!*is_row)]);
                    out.push(if *is_row { box_bits(*a, *b, 0, 0) } else { box_bits(0, 0, *a, *b) });
                    out.push(number_bits(*count));
                }
                Val::of_table(Table::distinct(keys.len() + 3, out))
            }
            PartStep::Complement { p } => {
                if !on_one_frame(t, &[], *p) {
                    return None;
                }
                let first = t.rows().next().map(|row| margins_of(row[usize::from(*p)]))?;
                let (h, w) = (first[0] + first[1] + 1, first[2] + first[3] + 1);
                if h * w > 4096 {
                    return None;
                }
                let held: std::collections::HashSet<Cell> = t.rows().map(|row| row[usize::from(*p)]).collect();
                let mut out = Vec::new();
                for r in 0..h {
                    for c in 0..w {
                        let cell = box_bits(r, h - 1 - r, c, w - 1 - c);
                        if !held.contains(&cell) {
                            out.push(cell);
                        }
                    }
                }
                Val::of_table(Table::distinct(1, out))
            }
            PartStep::Straight { keys, p } => {
                if !on_one_frame(t, keys, *p) {
                    return None;
                }
                let (cells, heads) = cells_by_key(t, keys, *p);
                keys_only(&heads, cells.iter().map(|held| {
                    let Some(first) = held.first() else { return false };
                    let (r, c) = (i32::from(first.0), i32::from(first.1));
                    held.iter().all(|at| i32::from(at.0) == r) || held.iter().all(|at| i32::from(at.1) == c) || held.iter().all(|at| i32::from(at.0) - i32::from(at.1) == r - c) || held.iter().all(|at| i32::from(at.0) + i32::from(at.1) == r + c)
                }), keys.len())
            }
            PartStep::FullLines { keys, p } => {
                if !on_one_frame(t, keys, *p) {
                    return None;
                }
                let (ids, first) = key_ids(t, keys);
                let mut lines: FastMap<(u32, bool, i32, i32), u32> = FastMap::default();
                let mut wide: Vec<(i32, i32)> = vec![(0, 0); first.len()];
                let mut seen: std::collections::HashSet<(u32, Cell)> = std::collections::HashSet::new();
                for (row, id) in t.rows().zip(&ids) {
                    let cell = row[usize::from(*p)];
                    let m = margins_of(cell);
                    if !is_cell(&m) || !seen.insert((*id, cell)) {
                        continue;
                    }
                    wide[*id as usize] = (m[0] + m[1] + 1, m[2] + m[3] + 1);
                    *lines.entry((*id, true, m[0], m[1])).or_insert(0) += 1;
                    *lines.entry((*id, false, m[2], m[3])).or_insert(0) += 1;
                }
                let mut out = Vec::new();
                for ((id, is_row, a, b), count) in &lines {
                    let (rows_long, columns_long) = wide[*id as usize];
                    let full = if *is_row { *count as i32 == columns_long } else { *count as i32 == rows_long };
                    if full {
                        push_key(&mut out, first[*id as usize], keys);
                        out.push(e.axes[usize::from(!*is_row)]);
                        out.push(if *is_row { box_bits(*a, *b, 0, 0) } else { box_bits(0, 0, *a, *b) });
                    }
                }
                Val::of_table(Table::distinct(keys.len() + 2, out))
            }
            PartStep::BoxRead { b, kept } => {
                let (input, output) = grids_of(children[1])?;
                let mut boxes: Vec<Cell> = t.rows().map(|row| row[usize::from(*b)]).collect();
                boxes.sort_unstable();
                boxes.dedup();
                boxes.retain(|held| {
                    let m = margins_of(*held);
                    input.h - m[0] - m[1] == output.h && input.w - m[2] - m[3] == output.w
                });
                if boxes.len() > 64 {
                    return None;
                }
                let mut out = Vec::new();
                for held in boxes {
                    let m = margins_of(held);
                    for r in 0..output.h {
                        for c in 0..output.w {
                            let (y, z) = (r + m[0], c + m[2]);
                            if y < 0 || z < 0 || y >= input.h || z >= input.w {
                                continue;
                            }
                            let (from, to) = (input.colors[(y * input.w + z) as usize], output.colors[(r * output.w + c) as usize]);
                            if (from == to) == *kept {
                                out.extend_from_slice(&[held, box_bits(y, input.h - 1 - y, z, input.w - 1 - z), box_bits(r, output.h - 1 - r, c, output.w - 1 - c), from]);
                                if !*kept {
                                    out.push(to);
                                }
                            }
                        }
                    }
                }
                Val::of_table(Table::new(if *kept { 4 } else { 5 }, out))
            }
            PartStep::BoxFrameRead { b, x, kept } | PartStep::BoxCellRead { b, x, kept } => {
                let (input, output) = grids_of(children[1])?;
                let in_frame = matches!(self, PartStep::BoxCellRead { .. });
                let mut out = Vec::new();
                for row in t.rows() {
                    let (held, cell) = (row[usize::from(*b)], row[usize::from(*x)]);
                    let (m, n) = (margins_of(held), margins_of(cell));
                    // The cell's two places: in the input's frame, and in the output's.
                    let (at_in, at_out, other) = if in_frame {
                        let other = less_cell(n, m);
                        (cell, other, other)
                    } else {
                        let other = add_cell(n, m);
                        (other, cell, other)
                    };
                    let (Some(from), Some(to)) = (input.at.get(&at_in), output.at.get(&at_out)) else { continue };
                    if (from == to) == *kept {
                        out.extend_from_slice(&[held, cell, other, *from]);
                        if !*kept {
                            out.push(*to);
                        }
                    }
                }
                Val::of_table(Table::distinct(if *kept { 4 } else { 5 }, out))
            }
        })
    }
}
