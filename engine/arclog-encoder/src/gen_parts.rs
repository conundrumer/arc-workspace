//! The parts with holes, as native operators over relations. Each part's rows follow from its
//! relation and its columns, so no part is written for one feature.

use std::collections::BTreeMap;
use std::sync::Arc;

use crate::columns::Columns;
use crate::cell_sets::{grid_pieces, relation, shape_hash, symmetry_count, FramePieces, Walk, STEPS};
pub use crate::cell_sets::SetRelation;
use crate::gen_constants::{box_bits, encoding, margins_of, number_bits, number_of};
use crate::grid_walks::{enclosed_regions, walk_outward};
use crate::lookup::{LookupMap, LookupSet};
use crate::native::{first_ids, hash_words, row_word, Cell, FastMap, Grouping, Table, Val};
use crate::occurrence::{distinct_patterns, each_turned_image, for_each_move, Canvas, PatternCell};

#[derive(Clone, Debug, serde::Serialize, serde::Deserialize)]
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
    /// A relation's rows whose value has the greatest count of rows of their key below the key's top count. A key with one count has none.
    SecondFrequentRows { keys: Box<[u16]>, v: u16 },
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
    /// Each key with an axis whose line holds all its cells: keys, A.
    StraightAxis { keys: Box<[u16]>, p: u16 },
    /// The distinct cells per key: keys, N.
    CellCount { keys: Box<[u16]>, p: u16 },
    /// The fewest eight-neighbor steps from each key's cells to a cell of the column that the key does not hold: keys, N.
    GroupGap { keys: Box<[u16]>, p: u16 },
    /// The cells of a column's frame inside the box of its cells, or outside it: (P).
    BoxCells { p: u16, outside: bool },
    /// The cells of a column's frame that its cells enclose: (P).
    HoleCells { p: u16 },
    /// Whether the rows are each key with each value of the other columns, with at least two of each.
    Product { keys: Box<[u16]> },
    /// Whether the rows of the two are one set on paired columns, and whether the first's paired columns are a key of it.
    SameRows { left: Box<[u16]>, right: Box<[u16]>, key: bool },
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
    /// How a column of each of two relations stand as sets: a row where they stand as `word`. Under `cells`, the first column holds the cells of one frame, and two disjoint sets are complements where the first column's cells and the second's that lie in that frame fill it. `Subset` is strict.
    SetWord { a: u16, b: u16, cells: bool, word: SetRelation },
    /// Whether the first relation has fewer rows than the second, or as many.
    CountWord { less: bool },
    /// How the greatest number of a column stands to the second relation's count of rows: a row where it is below, equal to or above it.
    GreatestCount { a: u16, word: i8 },
    /// What a Box column's boxes say together in the frame of the second relation's cell column. A row of a number, or a row where it holds.
    BoxMeasure { b: u16, f: u16, measure: BoxMeasureKind },
    /// The cells of a Box column's one box, in the frame of the second relation's cell column, where the column has one box.
    OneBoxCells { b: u16, f: u16 },
    /// Every cell of the frame of a column's cells.
    FrameCells { p: u16 },
    /// How many connected parts by four steps the rest of a column's frame has.
    ComplementParts { p: u16 },
    /// Whether every connected part of a column's cells lies on one line.
    EveryPartStraight { p: u16 },
    /// Whether a column's cells are the outline of their bounding box.
    OutlinesBox { p: u16 },
    /// On each axis, how many distinct gaps stand between the lines that a column's cells lie on.
    LineSpacings { p: u16 },
    /// A flag that a column's values give as a whole, or for `ExtentsDistinct` a row of a count.
    ColumnMeasure { a: u16, measure: ColumnMeasureKind },
    /// As many rows as the greatest number of a column over the relation's rows or, under `second`, as the next number over its rows.
    CountedByValue { a: u16, second: bool },
    /// The least distance from a column's cells to another relation's, counted in steps of eight directions.
    LeastDistance { a: u16, b: u16 },
    /// The cells of the first relation that lie on the boundary of another's: each is a cell of it and has one of its four neighbors outside it.
    OnBoundary { b: u16 },
    /// Each cell of the first relation with each of its eight neighbors that another relation holds.
    NeighborsIn { b: u16 },
    /// The cells of the first relation in a box of another relation and on its border.
    OnBorder { b: u16 },
    /// The rows of a first relation of a cell and a direction whose ray from the cell meets a cell of another relation.
    RayMeets { b: u16 },
    /// The colors a grid has most often under a column's cells. Under a tie, every tied color.
    TopColorsUnder { p: u16 },
    /// How the groups of two relations' cells stand as sets, of cell sets or, under `shapes`, of shapes: a row where they stand as `word`.
    GroupsWord { p: u16, left: Box<[u16]>, q: u16, right: Box<[u16]>, shapes: bool, word: SetRelation },
    /// Whether two relations give a cell the same colors at the cells they share: a row where they do at `word` of those cells.
    AgreeWord { p: u16, x: u16, q: u16, y: u16, word: AgreeRelation },
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
        matches!(self, PartStep::DiffCells { on: false, .. } | PartStep::CountWord { .. })
    }

    /// Whether the part's second relation is a relation hole, and no grid.
    pub fn reads_second_relation(&self) -> bool {
        matches!(self, PartStep::SetWord { .. } | PartStep::CountWord { .. } | PartStep::GreatestCount { .. } | PartStep::BoxMeasure { .. } | PartStep::OneBoxCells { .. } | PartStep::GroupsWord { .. } | PartStep::AgreeWord { .. } | PartStep::LeastDistance { .. } | PartStep::OnBoundary { .. } | PartStep::NeighborsIn { .. } | PartStep::OnBorder { .. } | PartStep::RayMeets { .. } | PartStep::DeterminesFlag { .. } | PartStep::SharedLine { .. } | PartStep::SameValues { .. } | PartStep::InsideBoxes { .. } | PartStep::BoxesHolding { .. } | PartStep::SameShape { .. })
    }

    /// The columns of its first relation that its holes name.
    pub fn hole_columns(&self) -> Vec<u16> {
        let with = |keys: &[u16], rest: &[u16]| keys.iter().chain(rest).copied().collect::<Vec<u16>>();
        match self {
            PartStep::Complement { p } | PartStep::BoxCells { p, .. } | PartStep::HoleCells { p } | PartStep::CellsOn { p } | PartStep::ColorsUnder { p } | PartStep::Around { p } | PartStep::Neighbors { p } | PartStep::Split { p } | PartStep::Margin { p } | PartStep::CornerDist { p } | PartStep::Parity { p } | PartStep::BorderDistance { p } | PartStep::NeighborhoodClass { p } | PartStep::NeighborColorClass { p } | PartStep::SameColorNeighbors { p } | PartStep::Distance { p } | PartStep::FrameExtent { p } => vec![*p],
            PartStep::Inside { b } | PartStep::BoxMargin { b } | PartStep::BoxExtent { b } | PartStep::BoxRead { b, .. } => vec![*b],
            PartStep::NumberExtreme { n, .. } => vec![*n],
            PartStep::SharedLine { a, .. } | PartStep::SameValues { a, .. } | PartStep::InsideBoxes { a, .. } | PartStep::BoxesHolding { a, .. } => vec![*a],
            PartStep::SameShape { keys, a, .. } => with(keys, &[*a]),
            PartStep::DeterminesJointly { p, v, w } => vec![*p, *v, *w],
            PartStep::Displacement { a, b } => vec![*a, *b],
            PartStep::BoxFrameRead { b, x, .. } | PartStep::BoxCellRead { b, x, .. } => vec![*b, *x],
            PartStep::BoxSides { keys, p } | PartStep::BoxMargins { keys, p } | PartStep::LineCounts { keys, p } | PartStep::Straight { keys, p } | PartStep::CellCount { keys, p } | PartStep::GroupGap { keys, p } | PartStep::StraightAxis { keys, p } | PartStep::Pieces { keys, p, .. } | PartStep::BoxOf { keys, p } | PartStep::RelBox { keys, p } | PartStep::ShapeClass { keys, p, .. } | PartStep::Holes { keys, p } | PartStep::Symmetry { keys, p } | PartStep::TouchesEdge { keys, p } | PartStep::FillsBox { keys, p } | PartStep::FullLines { keys, p } => with(keys, &[*p]),
            PartStep::Count { keys } | PartStep::ClassOf { keys } => keys.to_vec(),
            PartStep::OneValue { keys, f } | PartStep::Several { keys, f } | PartStep::Determines { keys, f } => with(keys, &[*f]),
            PartStep::Extreme { keys, t, score, .. } => with(keys, &[*t, *score]),
            PartStep::MostFrequentRows { keys, v } | PartStep::SecondFrequentRows { keys, v } => with(keys, &[*v]),
            PartStep::DeterminesFlag { keys, a, .. } => with(keys, &[*a]),
            PartStep::Occurs { keys, p, v, .. } => with(keys, &[*p, *v]),
            PartStep::DiffRows { p, .. } | PartStep::DiffCells { p, .. } => vec![*p],
            PartStep::DiffGroupsOff { keys, p, .. } => with(keys, &[*p]),
            PartStep::Same => Vec::new(),
            PartStep::SetWord { a, .. } | PartStep::LeastDistance { a, .. } | PartStep::GreatestCount { a, .. } | PartStep::ColumnMeasure { a, .. } | PartStep::CountedByValue { a, .. } => vec![*a],
            PartStep::OnBoundary { .. } | PartStep::NeighborsIn { .. } | PartStep::OnBorder { .. } => vec![0],
            PartStep::RayMeets { .. } => vec![0, 1],
            PartStep::TopColorsUnder { p } | PartStep::FrameCells { p } | PartStep::ComplementParts { p } | PartStep::EveryPartStraight { p } | PartStep::OutlinesBox { p } | PartStep::LineSpacings { p } => vec![*p],
            PartStep::BoxMeasure { b, .. } | PartStep::OneBoxCells { b, .. } => vec![*b],
            PartStep::CountWord { .. } => Vec::new(),
            PartStep::GroupsWord { p, left, .. } => with(left, &[*p]),
            PartStep::AgreeWord { p, x, .. } => vec![*p, *x],
            PartStep::Product { keys } => keys.to_vec(),
            PartStep::SameRows { left, .. } => left.to_vec(),
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
            PartStep::Same | PartStep::CommonValues { .. } | PartStep::ExampleClasses { .. } | PartStep::SameRows { .. } => return None,
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
            PartStep::SecondFrequentRows { keys, v } => format!("(second-frequent-rows &r {} {})", list(keys), c(v)),
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
            PartStep::SetWord { a, b, cells, word } => format!("({} &r &s {} {})", word.fragment(*cells), c(a), second(*b)),
            PartStep::CountWord { less } => format!("({} &r &s)", if *less { "count-less" } else { "count-equal" }),
            PartStep::GreatestCount { a, word } => format!("(greatest-{}-count &r {} &s)", ["less", "equal", "more"][(*word + 1) as usize], c(a)),
            PartStep::BoxMeasure { b, f, measure } => format!("({} &r {} &s {})", measure.fragment(), c(b), second(*f)),
            PartStep::OneBoxCells { b, f } => format!("(one-box-cells &r {} &s {})", c(b), second(*f)),
            PartStep::FrameCells { p } => format!("(frame-cells &r {})", c(p)),
            PartStep::ComplementParts { p } => format!("(complement-parts &r {})", c(p)),
            PartStep::EveryPartStraight { p } => format!("(every-part-straight &r {})", c(p)),
            PartStep::OutlinesBox { p } => format!("(outlines-box &r {})", c(p)),
            PartStep::LineSpacings { p } => format!("(line-spacings &r {})", c(p)),
            PartStep::ColumnMeasure { a, measure } => format!("({} &r {})", measure.fragment(), c(a)),
            PartStep::CountedByValue { a, second: next } => format!("({} &r {})", if *next { "second-number-rows" } else { "first-number-rows" }, c(a)),
            PartStep::LeastDistance { a, b } => format!("(least-distance &r &s {} {})", c(a), second(*b)),
            PartStep::OnBoundary { b } => format!("(on-boundary &r &s C0 {})", second(*b)),
            PartStep::NeighborsIn { b } => format!("(neighbors-in &r &s C0 {})", second(*b)),
            PartStep::OnBorder { b } => format!("(on-border &r &s C0 {})", second(*b)),
            PartStep::RayMeets { b } => format!("(ray-meets &r &s C0 C1 {})", second(*b)),
            PartStep::TopColorsUnder { p } => format!("(most-colors-under &r {} {grid})", c(p)),
            PartStep::GroupsWord { p, left, q, right, shapes, word } => format!("({}-{} &r &s {} {} ({}) {})", if *shapes { "shapes" } else { "groups" }, word.word(), list(left), c(p), right.iter().map(|at| second(*at)).collect::<Vec<_>>().join(" "), second(*q)),
            PartStep::AgreeWord { p, x, q, y, word } => format!("(colors-agree-{} &r &s {} {} {} {})", word.word(), c(p), c(x), second(*q), second(*y)),
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
            PartStep::Product { keys } => format!("(product &r {})", list(keys)),
            PartStep::CellCount { keys, p } => format!("(cell-count &r {} {})", list(keys), c(p)),
            PartStep::StraightAxis { keys, p } => format!("(straight-axis &r {} {})", list(keys), c(p)),
            PartStep::GroupGap { keys, p } => format!("(group-gap &r {} {})", list(keys), c(p)),
            PartStep::BoxCells { p, outside } => format!("({} &r {})", if *outside { "outside-box" } else { "box-cells" }, c(p)),
            PartStep::HoleCells { p } => format!("(hole-cells &r {})", c(p)),
            PartStep::BoxRead { b, kept } => format!("({} &r {})", if *kept { "box-kept" } else { "box-changed" }, c(b)),
            PartStep::BoxFrameRead { b, x, kept } => format!("({} &r {} {})", if *kept { "box-frame-kept" } else { "box-frame-changed" }, c(b), c(x)),
            PartStep::BoxCellRead { b, x, kept } => format!("({} &r {} {})", if *kept { "box-cell-kept" } else { "box-cell-changed" }, c(b), c(x)),
        })
    }
}

/// The number of distinct rows of a table over some of its columns.
fn distinct_over(t: &Table, places: &[usize]) -> usize {
    // Up to four cells of a row pack into one number.
    if places.len() <= 4 {
        t.rows().map(|row| places.iter().fold(0u128, |packed, at| packed << 32 | u128::from(row[*at]))).collect::<LookupSet<u128>>().len()
    } else {
        t.rows().map(|row| places.iter().map(|at| row[*at]).collect::<Vec<Cell>>()).collect::<LookupSet<_>>().len()
    }
}

/// The group of a column in a list of links between columns.
fn link_root(link: &mut [usize], mut at: usize) -> usize {
    while link[at] != at {
        link[at] = link[link[at]];
        at = link[at];
    }
    at
}

/// A table's finest split into groups of columns whose product it is: for each column the place of its group, and for each group the number of distinct rows of its columns. A table has one such split, and every split
/// of its columns into two sides has each group wholly on one side. A column of one value is a group of its own.
fn finest_split(t: &Table) -> crate::native::Factors {
    let arity = t.arity;
    let values: Vec<usize> = (0..arity).map(|at| t.sorted_column(at).len()).collect();
    // Two columns whose pairs of values are not all the pairs of their values depend on one another, and a split has no such pair across its sides. Columns that depend on one another, directly or through others, are linked.
    let mut link: Vec<usize> = (0..arity).collect();
    let many: Vec<usize> = (0..arity).filter(|at| values[*at] > 1).collect();
    for (place, a) in many.iter().enumerate() {
        for b in &many[place + 1..] {
            let (ra, rb) = (link_root(&mut link, *a), link_root(&mut link, *b));
            if ra == rb {
                continue;
            }
            // More pairs of values than rows: some pair is missing.
            let full = values[*a].saturating_mul(values[*b]);
            if full > t.len || distinct_over(t, &[*a, *b]) != full {
                link[ra] = rb;
            }
        }
    }
    let mut linked: Vec<Vec<usize>> = Vec::new();
    let mut roots: Vec<usize> = Vec::new();
    for at in many.iter().copied() {
        let root = link_root(&mut link, at);
        match roots.iter().position(|held| *held == root) {
            Some(place) => linked[place].push(at),
            None => {
                roots.push(root);
                linked.push(vec![at]);
            }
        }
    }
    // The linked columns are a group each, unless some union of them is a split that no pair shows.
    let mut together: Vec<Vec<usize>> = linked.clone();
    if linked.len() >= 2 {
        let full = linked.iter().fold(1usize, |product, columns| product.saturating_mul(distinct_over(t, columns)));
        if full != t.len {
            let count = linked.len();
            let columns_of = |mask: u32, inside: bool| -> Vec<usize> { (0..count).filter(|at| (mask >> at & 1 == 1) == inside).flat_map(|at| linked[at].iter().copied()).collect() };
            let splits: Vec<u32> = (1u32..(1 << count) - 1).filter(|mask| mask & 1 == 1).filter(|mask| distinct_over(t, &columns_of(*mask, true)).saturating_mul(distinct_over(t, &columns_of(*mask, false))) == t.len).collect();
            // Two linked groups are one group where every split has them on one side.
            together = Vec::new();
            let mut signatures: Vec<Vec<bool>> = Vec::new();
            for at in 0..count {
                let signature: Vec<bool> = splits.iter().map(|mask| mask >> at & 1 == 1).collect();
                match signatures.iter().position(|held| *held == signature) {
                    Some(place) => together[place].extend(linked[at].iter().copied()),
                    None => {
                        signatures.push(signature);
                        together.push(linked[at].clone());
                    }
                }
            }
        }
    }
    let mut group_of = vec![0u8; arity];
    let mut rows_of: Vec<u64> = Vec::new();
    for at in (0..arity).filter(|at| values[*at] <= 1) {
        group_of[at] = rows_of.len() as u8;
        rows_of.push(values[at] as u64);
    }
    for columns in &together {
        for at in columns {
            group_of[*at] = rows_of.len() as u8;
        }
        rows_of.push(distinct_over(t, columns) as u64);
    }
    (group_of, rows_of)
}

/// A value's rows in the order of its columns.
pub fn flat(value: &Val) -> Option<Arc<Table>> {
    if value.is_lazy() {
        return flat(&value.written());
    }
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
    // A product is written out once for all that read it.
    let key = value.hash();
    if let Some(found) = FLATS.with(|flats| flats.borrow().0.get(&key).cloned()) {
        return Some(found);
    }
    let built = flat_product(value, parts, arity)?;
    FLATS.with(|flats| {
        let mut flats = flats.borrow_mut();
        flats.1 += built.cell_count();
        if flats.1 > HELD_GROUP_CELLS {
            flats.0.clear();
            flats.1 = built.cell_count();
        }
        flats.0.insert(key, built.clone());
    });
    Some(built)
}

thread_local! {
    /// The products that `flat` has written, and their cells.
    static FLATS: std::cell::RefCell<(LookupMap<u128, Arc<Table>>, usize)> = std::cell::RefCell::new((LookupMap::new(), 0));
}

fn flat_product(value: &Val, parts: &[crate::native::Part], arity: usize) -> Option<Arc<Table>> {
    if parts.iter().any(|part| part.table.arity == 0) {
        let rows = value.rows(arity, usize::MAX)?;
        let mut cells = Vec::with_capacity(rows.len() * arity);
        for row in &rows {
            cells.extend_from_slice(row);
        }
        return Some(Table::new(arity, cells));
    }
    // The product, whose first part varies slowest, written straight into place.
    let total = parts.iter().try_fold(1usize, |total, part| total.checked_mul(part.table.len))?;
    total.checked_mul(arity)?;
    let mut cells: Vec<Cell> = vec![0; total * arity];
    let mut stride = 1usize;
    for part in parts.iter().rev() {
        let (width, rows) = (part.table.arity, part.table.len);
        let mut at = 0usize;
        while at < total {
            for own in part.table.cells().chunks_exact(width) {
                for _ in 0..stride {
                    for (cell, column) in own.iter().zip(part.columns.iter()) {
                        cells[at * arity + usize::from(*column)] = *cell;
                    }
                    at += 1;
                }
            }
        }
        stride *= rows;
    }
    Some(Table::new(arity, cells))
}

/// Each key's cells and its head.
type KeyCells = (Listing<(u8, u8)>, Listing<Cell>);

/// A list of items for each of a run of groups, held in one run of items: group `at` has the items from `bounds[at]` to `bounds[at + 1]`.
struct Listing<T> {
    bounds: Vec<u32>,
    items: Vec<T>,
}

impl<T> Listing<T> {
    fn len(&self) -> usize {
        self.bounds.len().saturating_sub(1)
    }

    fn get(&self, at: usize) -> &[T] {
        &self.items[self.bounds[at] as usize..self.bounds[at + 1] as usize]
    }

    fn iter(&self) -> ListingIter<'_, T> {
        ListingIter { listing: self, next: 0 }
    }
}

struct ListingIter<'a, T> {
    listing: &'a Listing<T>,
    next: usize,
}

impl<'a, T> Iterator for ListingIter<'a, T> {
    type Item = &'a [T];

    fn next(&mut self) -> Option<&'a [T]> {
        if self.next >= self.listing.len() {
            return None;
        }
        let found = self.listing.get(self.next);
        self.next += 1;
        Some(found)
    }
}

impl<'a, T> IntoIterator for &'a Listing<T> {
    type Item = &'a [T];
    type IntoIter = ListingIter<'a, T>;

    fn into_iter(self) -> ListingIter<'a, T> {
        self.iter()
    }
}

/// The first row at each key group of a table, read from the table in place.
pub struct FirstRows<'t> {
    grouping: Arc<Grouping>,
    cells: &'t [Cell],
    arity: usize,
}

impl<'t> FirstRows<'t> {
    pub fn len(&self) -> usize {
        self.grouping.1.len()
    }

    pub fn is_empty(&self) -> bool {
        self.grouping.1.is_empty()
    }

    /// The first row of group `at`.
    pub fn get(&self, at: usize) -> &'t [Cell] {
        let row = self.grouping.1[at] as usize;
        &self.cells[row * self.arity..(row + 1) * self.arity]
    }

    pub fn iter(&self) -> FirstRowsIter<'_, 't> {
        FirstRowsIter { rows: self, next: 0 }
    }

    /// The cells at `keys` of the first row of each group.
    fn heads(&self, keys: &[u16]) -> Listing<Cell> {
        let mut items = Vec::with_capacity(self.len() * keys.len());
        let mut bounds = Vec::with_capacity(self.len() + 1);
        bounds.push(0);
        for row in self {
            push_key(&mut items, row, keys);
            bounds.push(items.len() as u32);
        }
        Listing { bounds, items }
    }
}

pub struct FirstRowsIter<'a, 't> {
    rows: &'a FirstRows<'t>,
    next: usize,
}

impl<'t> Iterator for FirstRowsIter<'_, 't> {
    type Item = &'t [Cell];

    fn next(&mut self) -> Option<&'t [Cell]> {
        if self.next >= self.rows.len() {
            return None;
        }
        let found = self.rows.get(self.next);
        self.next += 1;
        Some(found)
    }
}

impl<'a, 't> IntoIterator for &'a FirstRows<'t> {
    type Item = &'t [Cell];
    type IntoIter = FirstRowsIter<'a, 't>;

    fn into_iter(self) -> FirstRowsIter<'a, 't> {
        self.iter()
    }
}

/// What the parts of one table read alike, held while its walks go on, up to [`HELD_GROUP_CELLS`] of its cells in all.
#[derive(Default)]
struct Groups {
    groupings: FastMap<(u128, u128), Arc<Grouping>>,
    cells: FastMap<(u128, u128), Arc<KeyCells>>,
    frames: FastMap<(u128, u128), bool>,
    boxes: FastMap<(u128, u128), BoxFeatures>,
    margins: FastMap<(u128, u128), Arc<[Vec<i32>; 4]>>,
    colors: FastMap<(u128, u128), Arc<BTreeMap<Cell, Vec<Cell>>>>,
    in_frames: FastMap<(u128, u128), usize>,
    fronts: FastMap<(u128, u128), Arc<Vec<[i32; 4]>>>,
    held: usize,
}

const HELD_GROUP_CELLS: usize = 8_000_000;

thread_local! {
    static GROUPS: std::cell::RefCell<Groups> = std::cell::RefCell::new(Groups::default());
}

/// The grouping of a table's rows by keys, numbered by the first appearance of each key: a key of one column is that column's own grouping, and each further column refines it.
fn grouping_of(table: &Table, keys: &[u16]) -> Arc<Grouping> {
    let Some((first, rest)) = keys.split_first() else {
        let mut ids = Vec::new();
        ids.resize(table.len, 0);
        return Arc::new((ids, if table.len > 0 { vec![0] } else { Vec::new() }));
    };
    let mut grouping = table.column_grouping(usize::from(*first));
    for key in rest {
        let column = table.column_grouping(usize::from(*key));
        let width = column.1.len() as u64;
        let pairs: Vec<u64> = grouping.0.iter().zip(&column.0).map(|(a, b)| u64::from(*a) * width + u64::from(*b)).collect();
        grouping = Arc::new(first_ids(&pairs, 0, grouping.1.len() as u64 * width));
    }
    grouping
}

/// A hash of how keys group a table's rows, which two keys that group alike share, and the count of groups.
pub fn grouping_signature(table: &Table, keys: &[u16]) -> (u128, u32) {
    let grouping = grouping_of(table, keys);
    (hash_words(grouping.0.iter().map(|id| u64::from(*id))), grouping.1.len() as u32)
}

fn places_word(keys: &[u16], p: Option<u16>) -> u128 {
    hash_words(keys.iter().map(|at| u64::from(*at)).chain([u64::MAX]).chain(p.map(u64::from)))
}

/// The dense id of each row's key, numbered by the first appearance of each key.
fn key_grouping(table: &Table, keys: &[u16]) -> Arc<Grouping> {
    let key = (table.hash(), places_word(keys, None));
    let found = GROUPS.with(|groups| groups.borrow().groupings.get(&key).cloned());
    found.unwrap_or_else(|| {
        let built = grouping_of(table, keys);
        if keys.len() < 2 {
            // A column's grouping stands in its table.
            return built;
        }
        GROUPS.with(|groups| {
            let mut groups = groups.borrow_mut();
            groups.held += table.len;
            if groups.held > HELD_GROUP_CELLS {
                *groups = Groups { held: table.len, ..Groups::default() };
            }
            groups.groupings.insert(key, built.clone());
        });
        built
    })
}

/// The dense id of each row's key, and the first row at each key.
pub fn key_ids<'t>(table: &'t Table, keys: &[u16]) -> (Arc<Grouping>, FirstRows<'t>) {
    let grouping = key_grouping(table, keys);
    let first = FirstRows { grouping: grouping.clone(), cells: table.cells(), arity: table.arity.max(1) };
    (grouping, first)
}

/// The distinct pairs of a key group's id and a cell of one of its rows at column `p`, each packed as the id above the cell, in order. `ids` is each row's group, of `groups` in all. Rows are counted into their groups first, so only the cells of a group are sorted together.
fn group_cells(t: &Table, ids: &[u32], groups: usize, p: u16) -> Vec<u64> {
    let mut start = vec![0usize; groups + 1];
    for id in ids {
        start[*id as usize + 1] += 1;
    }
    for at in 0..groups {
        start[at + 1] += start[at];
    }
    let mut next = start.clone();
    let mut cells: Vec<Cell> = vec![0; ids.len()];
    for (row, id) in t.rows().zip(ids) {
        cells[next[*id as usize]] = row[usize::from(p)];
        next[*id as usize] += 1;
    }
    let mut pairs = Vec::with_capacity(ids.len());
    for group in 0..groups {
        let held = &mut cells[start[group]..start[group + 1]];
        held.sort_unstable();
        let mut last = None;
        for cell in held.iter() {
            if last != Some(*cell) {
                pairs.push(((group as u64) << 32) | u64::from(*cell));
                last = Some(*cell);
            }
        }
    }
    pairs
}

/// The cells of each key group on each row and each column of its frame, for cells that all have a margin from 0 to 127 and stand on one frame per group. `each` takes the group's id, whether the line is a row, the line's near and far margins, how many distinct cells lie on it, and the frame's height and width.
fn lines_of(t: &Table, ids: &[u32], groups: usize, p: u16, mut each: impl FnMut(u32, bool, i32, i32, u32, (i32, i32))) {
    let pairs: Vec<u64> = if groups == 1 {
        t.sorted_column(usize::from(p)).iter().map(|cell| u64::from(*cell)).collect()
    } else {
        group_cells(t, ids, groups, p)
    };
    // The count of cells and the far margin of each line, by its near margin.
    let mut by_row = [(0u32, 0i32); 256];
    let mut by_col = [(0u32, 0i32); 256];
    let mut start = 0;
    while start < pairs.len() {
        let id = (pairs[start] >> 32) as u32;
        let mut end = start;
        while end < pairs.len() && (pairs[end] >> 32) as u32 == id {
            end += 1;
        }
        let group = &pairs[start..end];
        let first = margins_of(group[0] as u32);
        let frame = (first[0] + first[1] + 1, first[2] + first[3] + 1);
        for cell in group {
            let m = margins_of(*cell as u32);
            by_row[m[0] as usize] = (by_row[m[0] as usize].0 + 1, m[1]);
            by_col[m[2] as usize] = (by_col[m[2] as usize].0 + 1, m[3]);
        }
        // Each line is given once, and its count is cleared as it goes.
        for cell in group {
            let m = margins_of(*cell as u32);
            let (count, far) = by_row[m[0] as usize];
            if count > 0 {
                each(id, true, m[0], far, count, frame);
                by_row[m[0] as usize].0 = 0;
            }
            let (count, far) = by_col[m[2] as usize];
            if count > 0 {
                each(id, false, m[2], far, count, frame);
                by_col[m[2] as usize].0 = 0;
            }
        }
        start = end;
    }
}

/// Adds a row of the key's head, a cell and the label of the piece for each cell of a piece, whose cells stand in ascending order. An Ident labels the set of its members, as `Connectivity` interns it.
fn push_piece(out: &mut Vec<Cell>, head: &[Cell], keys: &[u16], piece: &[Cell]) {
    let label = hash_words(piece.iter().map(|cell| u64::from(*cell))) as u32;
    for cell in piece {
        push_key(out, head, keys);
        out.push(*cell);
        out.push(label);
    }
}

/// The connected pieces of each key's cells, as rows of keys, a cell and the label of its piece. Cells on one frame, none off it, find their neighbors on an array of the frame in place of a search.
fn pieces(t: &Table, keys: &[u16], p: u16, four: bool) -> Val {
    let (grouping, first) = key_ids(t, keys);
    let pairs: Vec<u64> = if first.len() == 1 {
        // One group: its cells are the column's distinct values, in order.
        t.sorted_column(usize::from(p)).iter().map(|cell| u64::from(*cell)).collect()
    } else {
        group_cells(t, &grouping.0, first.len(), p)
    };
    let steps = &STEPS[..if four { 4 } else { 8 }];
    let mut out = Vec::with_capacity(pairs.len() * (keys.len() + 2));
    let mut held: Vec<Cell> = Vec::new();
    let mut margins: Vec<[i32; 4]> = Vec::new();
    let mut walk = Walk::default();
    let mut frame_pieces = FramePieces::default();
    let mut piece: Vec<Cell> = Vec::new();
    let mut at = 0;
    while at < pairs.len() {
        let id = (pairs[at] >> 32) as u32;
        let mut end = at;
        while end < pairs.len() && (pairs[end] >> 32) as u32 == id {
            end += 1;
        }
        held.clear();
        held.extend(pairs[at..end].iter().map(|pair| *pair as u32));
        at = end;
        let head = first.get(id as usize);
        margins.clear();
        margins.extend(held.iter().map(|cell| margins_of(*cell)));
        let (h, w) = (margins[0][0] + margins[0][1] + 1, margins[0][2] + margins[0][3] + 1);
        let on_frame = h > 0 && w > 0 && h * w <= 1 << 16 && margins.iter().all(|m| is_cell(m) && m[0] + m[1] + 1 == h && m[2] + m[3] + 1 == w);
        if on_frame {
            // The cells stand in ascending order, so the cells of each piece come in ascending order with no sort.
            frame_pieces.pieces(h as usize, w as usize, margins.iter().map(|m| (m[0] as usize, m[2] as usize)), steps, |members| {
                piece.clear();
                piece.extend(members.iter().map(|number| held[*number as usize]));
                push_piece(&mut out, head, keys, &piece);
            });
        } else {
            let neighbor = |from: usize, dr: i32, dc: i32| held.binary_search(&shifted_box(margins[from], dr, dc)).ok();
            walk.pieces(held.len(), steps, |_| true, neighbor, |members| {
                piece.clear();
                piece.extend(members.iter().map(|place| held[*place]));
                piece.sort_unstable();
                push_piece(&mut out, head, keys, &piece);
            });
        }
    }
    // A cell is in one piece of its key, and two keys differ, so no row repeats.
    Val::of_table(Table::new(keys.len() + 2, out))
}

/// The cells of the rows of `t` whose value at `v` is the most frequent of their key, or the greatest count below the top where `second`, and none where the key has one count. Each row counts as `weights` says, or once.
fn frequent_rows(t: &Table, keys: &[u16], v: u16, second: bool, weights: Option<&[u64]>) -> Frequent {
    let grouping = key_grouping(t, keys);
    let ids = &grouping.0;
    let groups = grouping.1.len();
    if ids.is_empty() || t.arity == 0 {
        return Frequent::Rows(Vec::new());
    }
    // The rows at each pair of a key and a value, counted by the pair's own number.
    let values = t.column_grouping(usize::from(v));
    let width = values.1.len();
    let range = groups as u64 * width as u64;
    let rows = ids.len();
    // The top count of each key, or its greatest count below the top where `second`: none where the key has one count.
    let kept_count = |counts: &[u64], pair_group: &mut dyn FnMut(usize) -> usize| {
        let mut best = vec![0u64; groups];
        for (at, count) in counts.iter().enumerate() {
            let best = &mut best[pair_group(at)];
            *best = (*best).max(*count);
        }
        if !second {
            return best;
        }
        let mut below = vec![0u64; groups];
        for (at, count) in counts.iter().enumerate() {
            let key = pair_group(at);
            if *count < best[key] {
                below[key] = below[key].max(*count);
            }
        }
        below
    };
    let mut runs: Vec<(usize, usize)> = Vec::new();
    let mut total = 0;
    let mut mark = |keeps: &dyn Fn(usize) -> bool| {
        let mut start = 0;
        let mut inside = false;
        for at in 0..rows {
            let keep = keeps(at);
            if keep != inside {
                if inside {
                    runs.push((start, at));
                    total += at - start;
                } else {
                    start = at;
                }
                inside = keep;
            }
        }
        if inside {
            runs.push((start, rows));
            total += rows - start;
        }
    };
    if range <= 4 * rows as u64 + 64 {
        // Each pair of a key and a value has a place of its own in an array.
        let mut counts = vec![0u64; range as usize];
        let places = ids.iter().zip(&values.0).map(|(id, value)| *id as usize * width + *value as usize);
        match weights {
            Some(weights) => {
                for (place, weight) in places.zip(weights) {
                    counts[place] += *weight;
                }
            }
            None => {
                for place in places {
                    counts[place] += 1;
                }
            }
        }
        let kept = kept_count(&counts, &mut |at| at / width);
        // The pairs whose rows stay.
        let stays: Vec<bool> = counts.iter().enumerate().map(|(at, count)| *count == kept[at / width]).collect();
        mark(&|at| stays[ids[at] as usize * width + values.0[at] as usize]);
    } else {
        let pairs: Vec<u64> = ids.iter().zip(&values.0).map(|(id, value)| u64::from(*id) * width as u64 + u64::from(*value)).collect();
        let (pair_ids, pair_first) = first_ids(&pairs, 0, range);
        let mut counts = vec![0u64; pair_first.len()];
        for (at, id) in pair_ids.iter().enumerate() {
            counts[*id as usize] += weights.map_or(1, |weights| weights[at]);
        }
        let kept = kept_count(&counts, &mut |pair| ids[pair_first[pair] as usize] as usize);
        let stays: Vec<bool> = counts.iter().enumerate().map(|(pair, count)| *count == kept[ids[pair_first[pair] as usize] as usize]).collect();
        mark(&|at| stays[pair_ids[at] as usize]);
    }
    if total == rows {
        return Frequent::All;
    }
    // The rows that stay are copied a run at a time.
    let arity = t.arity;
    let cells = t.cells();
    let mut out = Vec::with_capacity(total * arity);
    for (start, end) in runs {
        if end - start == 1 {
            push_row(&mut out, &cells[start * arity..end * arity]);
        } else {
            out.extend_from_slice(&cells[start * arity..end * arity]);
        }
    }
    Frequent::Rows(out)
}

/// What `frequent_rows` keeps of a table: all of its rows, or the cells of some rows.
enum Frequent {
    All,
    Rows(Vec<Cell>),
}

/// Whether `columns` are every column of a table of `arity` columns, each once, so that two rows of the table, which differ, differ at them.
fn are_all_columns(arity: usize, columns: impl IntoIterator<Item = u16>) -> bool {
    let mut seen = 0u64;
    let mut count = 0;
    for column in columns {
        if usize::from(column) >= arity.min(64) || seen >> column & 1 == 1 {
            return false;
        }
        seen |= 1 << column;
        count += 1;
    }
    count == arity
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
    /// The cells of `at` with their colors, in the order of the table's rows.
    pub pairs: Vec<(Cell, Cell)>,
    /// The places of each color's cells, as (row, column).
    pub of_color: FastMap<Cell, Vec<(i32, i32)>>,
    /// Whether every cell of the grid lies in one frame of `h` rows and `w` columns with no margin below 0 and has a color other than `u32::MAX`, so that `colors` answers for any cell.
    dense: bool,
    /// Whether every cell of the grid lies in one frame of `h` rows and `w` columns with no margin below 0, so that `colors` holds a color at the place of each cell and `u32::MAX` at each other place.
    framed: bool,
    /// The places of each shape that `placements_on` has searched for on this grid, and the count of cells of those shapes.
    searched: std::sync::Mutex<(FastMap<Shape, Arc<Vec<(i32, i32)>>>, usize)>,
    /// The offsets of each pattern and its images, by the hash of the pattern and its frame, that `turned_moves_of` has found for this grid, and the count of those offsets.
    turned: std::sync::Mutex<(FastMap<u128, Arc<Vec<Cell>>>, usize)>,
    /// The neighborhood of each place, once something has read them, for a dense grid.
    hoods: std::sync::OnceLock<Vec<Hood>>,
}

/// The most offsets that a grid holds of the patterns it has been searched for with their images.
const TURNED_HELD: usize = 1 << 19;

thread_local! {
    static VIEWS: std::cell::RefCell<LookupMap<u128, Arc<GridView>>> = std::cell::RefCell::new(LookupMap::new());
}

thread_local! {
    static RIGHT_KEYS: std::cell::RefCell<LookupMap<(u128, Box<[u16]>), Arc<Vec<u64>>>> = std::cell::RefCell::new(LookupMap::new());
}

/// The keys of second relations that this thread holds.
pub fn keys_held() -> usize {
    RIGHT_KEYS.with(|keys| keys.borrow().sum_of(|_, held| held.len()))
}

/// The cells that the groupings of this thread hold.
pub fn groups_held() -> usize {
    GROUPS.with(|groups| groups.borrow().held)
}

pub fn clear_views() {
    VIEWS.with(|views| views.borrow_mut().clear());
    FLATS.with(|flats| *flats.borrow_mut() = (LookupMap::new(), 0));
    RIGHT_KEYS.with(|keys| keys.borrow_mut().clear());
    OCCURS.with(|held| *held.borrow_mut() = OccurHeld::default());
    GROUPS.with(|groups| *groups.borrow_mut() = Groups::default());
}

/// A relation's keys at columns, sorted, held while its table stands.
pub fn keys_of(value: &Val, at: &[u16]) -> Option<Arc<Vec<u64>>> {
    let compute = |table: &Table| {
        let mut keys: Vec<u64> = table.rows().map(|row| row_word(row, at)).collect();
        keys.sort_unstable();
        keys.dedup();
        Arc::new(keys)
    };
    if let Val::Rows(parts) = value {
        if let [one] = parts.as_slice() {
            if one.table.len >= 16 && one.columns.iter().enumerate().all(|(place, column)| usize::from(*column) == place) {
                let key = (one.table.hash(), at.to_vec().into_boxed_slice());
                return Some(RIGHT_KEYS.with(|keys| keys.borrow_mut().entry(key).or_insert_with(|| compute(&one.table)).clone()));
            }
        }
    }
    let table = flat(value)?;
    Some(compute(&table))
}

/// What a cell of color `mine` has from the colors of the cells that eight steps reach from it.
#[derive(Clone, Copy)]
struct Hood {
    /// A hash of the eight colors in the order of the steps, and `mine`.
    class: u32,
    /// A hash of the eight colors in ascending order.
    colors: u32,
    /// How many of the eight cells have the color `mine`.
    same: i64,
}

impl GridView {
    /// The neighborhood of a cell of color `mine`.
    fn hood_of(&self, cell: Cell, mine: Cell) -> Hood {
        let m = margins_of(cell);
        let mut held = [u32::MAX; 8];
        let mut same = 0i64;
        for (at, (dr, dc)) in STEPS.iter().enumerate() {
            if let Some(color) = moved(m, *dr, *dc).and_then(|next| self.color_of(next)) {
                held[at] = color;
                same += i64::from(color == mine);
            }
        }
        let class = hash_words(held.iter().map(|x| u64::from(*x)).chain([u64::from(mine)])) as u32;
        held.sort_unstable();
        Hood { class, colors: hash_words(held.iter().map(|x| u64::from(*x))) as u32, same }
    }

    /// The neighborhood of each place of a dense grid, by the place's row times the grid's width plus its column; the places without a cell have an arbitrary one. Found for all places at the first call.
    fn hoods(&self) -> &[Hood] {
        self.hoods.get_or_init(|| {
            (0..self.h * self.w).map(|at| {
                let (r, c) = (at / self.w, at % self.w);
                match self.colors[at as usize] {
                    u32::MAX => Hood { class: 0, colors: 0, same: 0 },
                    mine => self.hood_of(box_bits(r, self.h - 1 - r, c, self.w - 1 - c), mine),
                }
            }).collect()
        })
    }

    /// The color of a cell of the grid, if the grid has the cell.
    #[inline]
    fn color_of(&self, cell: Cell) -> Option<Cell> {
        if !self.dense {
            if self.framed {
                // A place without a color holds `u32::MAX`, which a cell of that color holds as well.
                let m = margins_of(cell);
                if !is_cell(&m) || m[0] + m[1] + 1 != self.h || m[2] + m[3] + 1 != self.w {
                    return None;
                }
                let color = self.colors[(m[0] * self.w + m[2]) as usize];
                return if color == u32::MAX { self.at.get(&cell).copied() } else { Some(color) };
            }
            return self.at.get(&cell).copied();
        }
        // In a dense grid a cell is held where its frame is the grid's and no margin is below 0.
        let m = margins_of(cell);
        if !is_cell(&m) || m[0] + m[1] + 1 != self.h || m[2] + m[3] + 1 != self.w {
            return None;
        }
        let color = self.colors[(m[0] * self.w + m[2]) as usize];
        (color != u32::MAX).then_some(color)
    }
}

fn view_of(table: &Arc<Table>) -> Arc<GridView> {
    let key = table.hash();
    VIEWS.with(|views| {
        views.borrow_mut().entry(key).or_insert_with(|| {
            let mut at = FastMap::default();
            let mut pairs = Vec::with_capacity(table.len);
            let (mut h, mut w) = (0, 0);
            let mut colors = Vec::new();
            let mut of_color: FastMap<Cell, Vec<(i32, i32)>> = FastMap::default();
            for row in table.rows() {
                let m = margins_of(row[0]);
                of_color.entry(row[1]).or_default().push((m[0], m[2]));
                h = m[0] + m[1] + 1;
                w = m[2] + m[3] + 1;
                at.insert(row[0], row[1]);
                pairs.push((row[0], row[1]));
            }
            if h > 0 && w > 0 {
                colors = vec![u32::MAX; (h * w) as usize];
                for row in table.rows() {
                    let m = margins_of(row[0]);
                    colors[(m[0] * w + m[2]) as usize] = row[1];
                }
            }
            let framed = !colors.is_empty() && table.rows().all(|row| {
                let m = margins_of(row[0]);
                is_cell(&m) && m[0] + m[1] + 1 == h && m[2] + m[3] + 1 == w
            });
            let dense = framed && table.rows().all(|row| row[1] != u32::MAX);
            Arc::new(GridView { h, w, colors, at, pairs, of_color, dense, framed, searched: Default::default(), turned: Default::default(), hoods: Default::default() })
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

#[inline]
fn moved(m: [i32; 4], dr: i32, dc: i32) -> Option<Cell> {
    let (t, b, l, r) = (m[0] + dr, m[1] - dr, m[2] + dc, m[3] - dc);
    (t >= 0 && b >= 0 && l >= 0 && r >= 0).then(|| box_bits(t, b, l, r))
}

/// The box that one step moves a box to, which can reach past the frame.
fn shifted_box(m: [i32; 4], dr: i32, dc: i32) -> Cell {
    box_bits(m[0] + dr, m[1] - dr, m[2] + dc, m[3] - dc)
}

/// The box one step from a box, with any margin that a signed byte holds, off the grid included.
#[inline]
fn shifted(m: [i32; 4], dr: i32, dc: i32) -> Option<Cell> {
    let bits = box_bits(m[0] + dr, m[1] - dr, m[2] + dc, m[3] - dc);
    (bits != u32::MAX).then_some(bits)
}

/// Adds the cells of a row to a list. A row of up to four cells is written in place, with no call to copy memory.
#[inline(always)]
fn push_row(out: &mut Vec<Cell>, row: &[Cell]) {
    match *row {
        [a] => out.push(a),
        [a, b] => out.extend_from_slice(&[a, b]),
        [a, b, c] => out.extend_from_slice(&[a, b, c]),
        [a, b, c, d] => out.extend_from_slice(&[a, b, c, d]),
        _ => out.extend_from_slice(row),
    }
}

/// The rows of `table`, each with `extra` more columns, and with up to `fan` rows written for each row of `table`.
fn rows_with(table: &Table, extra: usize, fan: usize, mut each: impl FnMut(&[Cell], &mut Vec<Cell>)) -> Val {
    let arity = table.arity + extra;
    let mut out: Vec<Cell> = Vec::with_capacity(table.len * fan * arity);
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
fn cells_by_key(table: &Table, keys: &[u16], p: u16) -> Arc<KeyCells> {
    let key = (table.hash(), places_word(keys, Some(p)));
    if let Some(found) = GROUPS.with(|groups| groups.borrow().cells.get(&key).cloned()) {
        return found;
    }
    let (grouping, first) = key_ids(table, keys);
    let ids = &grouping.0;
    // The places are counted into their groups first, then written into one run, sorted within each group, and kept once.
    let places = |row: &[Cell]| {
        let m = margins_of(row[usize::from(p)]);
        (is_cell(&m) && m[0] < 256 && m[2] < 256).then_some((m[0] as u8, m[2] as u8))
    };
    let mut start = vec![0u32; first.len() + 1];
    for (row, id) in table.rows().zip(ids) {
        if places(row).is_some() {
            start[*id as usize + 1] += 1;
        }
    }
    for at in 0..first.len() {
        start[at + 1] += start[at];
    }
    let mut next = start.clone();
    let mut items = vec![(0u8, 0u8); start[first.len()] as usize];
    for (row, id) in table.rows().zip(ids) {
        if let Some(place) = places(row) {
            items[next[*id as usize] as usize] = place;
            next[*id as usize] += 1;
        }
    }
    let mut bounds = Vec::with_capacity(first.len() + 1);
    bounds.push(0u32);
    let mut written = 0usize;
    for group in 0..first.len() {
        let (from, to) = (start[group] as usize, start[group + 1] as usize);
        items[from..to].sort_unstable();
        let mut last = None;
        let mut read = from;
        while read < to {
            let place = items[read];
            read += 1;
            if last != Some(place) {
                last = Some(place);
                items[written] = place;
                written += 1;
            }
        }
        bounds.push(written as u32);
    }
    items.truncate(written);
    let built = Arc::new((Listing { bounds, items }, first.heads(keys)));
    GROUPS.with(|groups| {
        let mut groups = groups.borrow_mut();
        groups.held += table.len;
        if groups.held > HELD_GROUP_CELLS {
            *groups = Groups { held: table.len, ..Groups::default() };
        }
        groups.cells.insert(key, built.clone());
    });
    built
}

/// Whether each key's cells at a column stand on one frame. The parts that read a cell as a row and
/// a column have no native value on any other column.
fn on_one_frame(table: &Table, keys: &[u16], p: u16) -> bool {
    let key = (table.hash(), places_word(keys, Some(p)));
    if let Some(found) = GROUPS.with(|groups| groups.borrow().frames.get(&key).copied()) {
        return found;
    }
    let (grouping, first) = key_ids(table, keys);
    let mut frames: Vec<Option<(i32, i32)>> = vec![None; first.len()];
    let holds = table.rows().zip(&grouping.0).all(|(row, id)| {
        let m = margins_of(row[usize::from(p)]);
        let own = (m[0] + m[1], m[2] + m[3]);
        is_cell(&m) && *frames[*id as usize].get_or_insert(own) == own
    });
    GROUPS.with(|groups| {
        groups.borrow_mut().frames.insert(key, holds);
    });
    holds
}

/// The fewest eight-neighbor steps from a set of cells to a held cell outside it.
fn nearest_other(own: &[(u8, u8)], held: &[bool], h: usize, w: usize) -> Option<i64> {
    let mut found = None;
    walk_outward(own.iter().map(|(r, c)| usize::from(*r) * w + usize::from(*c)), h, w, true, |at, steps| {
        if held[at] {
            found = Some(i64::from(steps));
        }
        held[at]
    });
    found
}


/// The rows of a key's head and its value, for each key that has one. The heads differ, so the rows do.
fn keyed_values(heads: &Listing<Cell>, values: impl Iterator<Item = Option<Cell>>, width: usize) -> Val {
    let mut out = Vec::with_capacity(heads.len() * width);
    for (head, value) in heads.iter().zip(values) {
        if let Some(value) = value {
            out.extend_from_slice(head);
            out.push(value);
        }
    }
    Val::of_table(Table::new(width, out))
}

fn keys_only(heads: &Listing<Cell>, holds: impl Iterator<Item = bool>, width: usize) -> Val {
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
    // The heads differ, so the rows do.
    Val::of_table(Table::new(width, out))
}

impl Canvas for GridView {
    fn height(&self) -> i32 {
        self.h
    }

    fn width(&self) -> i32 {
        self.w
    }

    fn color_at(&self, row: i32, column: i32) -> u32 {
        self.colors[(row * self.w + column) as usize]
    }

    fn count(&self, color: u32) -> usize {
        self.of_color.get(&color).map_or(0, Vec::len)
    }

    fn each_place(&self, color: u32, mut each: impl FnMut(i32, i32)) {
        for &(row, column) in self.of_color.get(&color).into_iter().flatten() {
            each(row, column);
        }
    }
}

/// A colored pattern with its top-left corner at (0, 0).
type Shape = Vec<PatternCell>;

/// The places of a shape on a grid, searched once for the grid.
fn placements_on(grid: &GridView, shape: Shape) -> Arc<Vec<(i32, i32)>> {
    let lock = || grid.searched.lock().unwrap_or_else(|poisoned| poisoned.into_inner());
    if let Some(found) = lock().0.get(&shape) {
        return found.clone();
    }
    let places = Arc::new(crate::occurrence::moves(grid, &shape));
    let mut held = lock();
    if held.1 + shape.len() <= 1 << 18 {
        held.1 += shape.len();
        held.0.insert(shape, places.clone());
    }
    places
}

/// The offsets that move cells of a frame with the given last row and last column onto a grid, added to `out`: each `P` where
/// `compose` of a cell and `P` is a grid cell of the cell's color, for every cell. The cells are (row, column, color) sorted.
/// Patterns that differ only by a shift share one search, which the grid keeps.
fn framed_moves(cells: &[PatternCell], frame: (i32, i32), grid: &GridView, out: &mut Vec<Cell>) {
    let offset = |dr: i32, dc: i32| box_bits(dr, grid.h - 1 - frame.0 - dr, dc, grid.w - 1 - frame.1 - dc);
    if cells.len() == 1 {
        for_each_move(grid, cells, |dr, dc| out.push(offset(dr, dc)));
        return;
    }
    let top = cells.first().map_or(0, |cell| cell.0);
    let left = cells.iter().map(|cell| cell.1).min().unwrap_or(0);
    let shape: Shape = cells.iter().map(|&(r, c, color)| (r - top, c - left, color)).collect();
    let places = placements_on(grid, shape);
    out.extend(places.iter().map(|&(r, c)| offset(r - top, c - left)));
}

/// The cells of a pattern whose cells lie in one frame, with the frame's last row and last column.
type Framed = (Vec<PatternCell>, (i32, i32));

/// The colored patterns of a relation's key groups, each pattern once.
struct OccurPatterns {
    /// Each distinct pattern, or none where its cells do not lie in one frame, which leaves no move.
    distinct: Vec<Option<Framed>>,
    /// For each distinct pattern, a hash of its cells and frame, or 0 where it has none.
    hashes: Vec<u128>,
    /// For each key group in order of first appearance, the place of its pattern in `distinct`.
    of_group: Vec<u32>,
}

/// What the occurs parts share, held while a table's walks go on, up to [`HELD_GROUP_CELLS`] of cells in all.
#[derive(Default)]
struct OccurHeld {
    patterns: FastMap<(u128, u128), Arc<OccurPatterns>>,
    moves: FastMap<(u128, u128, u128), Arc<Vec<Vec<Cell>>>>,
    held: usize,
}

thread_local! {
    static OCCURS: std::cell::RefCell<OccurHeld> = std::cell::RefCell::new(OccurHeld::default());
}

/// The patterns of the key groups of a table, whose rows give a cell at column `p` and its color at column `v`. `ids` is each row's group, and `word` hashes the keys and columns.
fn occur_patterns(table: &Table, ids: &[u32], groups: usize, (p, v): (u16, u16), word: u128) -> Arc<OccurPatterns> {
    let key = (table.hash(), word);
    if let Some(found) = OCCURS.with(|held| held.borrow().patterns.get(&key).cloned()) {
        return found;
    }
    let mut per_group: Vec<Vec<([i32; 4], Cell)>> = vec![Vec::new(); groups];
    for (row, id) in table.rows().zip(ids) {
        per_group[*id as usize].push((margins_of(row[usize::from(p)]), row[usize::from(v)]));
    }
    let (distinct, of_group) = distinct_patterns(per_group);
    // A pattern sorts by its margins, which in one frame is by row, then column.
    let distinct: Vec<Option<Framed>> = distinct.iter().map(|pattern| {
        let ((first, _), rest) = pattern.split_first()?;
        let frame = (first[0] + first[1], first[2] + first[3]);
        if rest.iter().any(|(m, _)| (m[0] + m[1], m[2] + m[3]) != frame) {
            return None;
        }
        Some((pattern.iter().map(|(m, color)| (m[0], m[2], *color)).collect(), frame))
    }).collect();
    let hashes = distinct.iter().map(|framed| framed.as_ref().map_or(0, |(cells, frame)| {
        hash_words([frame.0 as u64, frame.1 as u64].into_iter().chain(cells.iter().flat_map(|&(r, c, color)| [r as u64, c as u64, u64::from(color)])))
    })).collect();
    let built = Arc::new(OccurPatterns { distinct, hashes, of_group });
    OCCURS.with(|held| {
        let mut held = held.borrow_mut();
        held.held += table.len;
        if held.held > HELD_GROUP_CELLS {
            *held = OccurHeld { held: table.len, ..OccurHeld::default() };
        }
        held.patterns.insert(key, built.clone());
    });
    built
}

/// The offsets that move each distinct pattern onto the grid as it stands, for a table, columns and grid that `key` names.
fn occur_moves(patterns: &OccurPatterns, grid: &GridView, key: (u128, u128, u128)) -> Arc<Vec<Vec<Cell>>> {
    if let Some(found) = OCCURS.with(|held| held.borrow().moves.get(&key).cloned()) {
        return found;
    }
    let built: Arc<Vec<Vec<Cell>>> = Arc::new(patterns.distinct.iter().map(|framed| {
        let mut moves = Vec::new();
        if let Some((cells, frame)) = framed {
            framed_moves(cells, *frame, grid, &mut moves);
        }
        moves.sort_unstable();
        moves.dedup();
        moves
    }).collect());
    let size: usize = built.iter().map(Vec::len).sum::<usize>() + built.len();
    OCCURS.with(|held| {
        let mut held = held.borrow_mut();
        held.held += size;
        if held.held > HELD_GROUP_CELLS {
            *held = OccurHeld { held: size, ..OccurHeld::default() };
        }
        held.moves.insert(key, built.clone());
    });
    built
}

/// The offsets that move a pattern, or its image under some element of D4, onto the grid, sorted and without repeats. `hash` is the pattern's hash with its frame, under which the grid keeps the offsets, since patterns of other tables repeat.
fn turned_moves_of(framed: &Option<Framed>, hash: u128, grid: &GridView) -> Arc<Vec<Cell>> {
    let Some((cells, frame)) = framed else { return Arc::new(Vec::new()) };
    let lock = || grid.turned.lock().unwrap_or_else(|poisoned| poisoned.into_inner());
    if let Some(found) = lock().0.get(&hash) {
        return found.clone();
    }
    let mut out = Vec::new();
    framed_moves(cells, *frame, grid, &mut out);
    each_turned_image(cells, *frame, true, |which, image| {
        // A turn by a quarter swaps the frame's height and width.
        let turned = if which >= 4 { (frame.1, frame.0) } else { *frame };
        framed_moves(image, turned, grid, &mut out);
        false
    });
    // The offsets of the pattern and of each image come in runs that stand in order, which the merging sort reads as they are.
    out.sort();
    out.dedup();
    let built = Arc::new(out);
    let mut held = lock();
    if held.1 + built.len() <= TURNED_HELD {
        held.1 += built.len() + 1;
        held.0.insert(hash, built.clone());
    }
    built
}

impl SetRelation {
    /// The fragment that defines the word over two columns.
    pub fn fragment(self, cells: bool) -> String {
        format!("{}-{}", if cells && matches!(self, SetRelation::Disjoint | SetRelation::Complement) { "cells" } else { "set" }, self.word())
    }
}

/// At how many of the cells that two relations share they give the same colors.
#[derive(Clone, Copy, Debug, PartialEq, Eq, serde::Serialize, serde::Deserialize)]
pub enum AgreeRelation {
    EveryOne,
    None,
    Some,
}

impl AgreeRelation {
    fn word(self) -> &'static str {
        match self {
            AgreeRelation::EveryOne => "every",
            AgreeRelation::None => "none",
            AgreeRelation::Some => "some",
        }
    }
}

/// A count or a flag that a set of boxes gives in a frame.
#[derive(Clone, Copy, Debug, PartialEq, Eq, serde::Serialize, serde::Deserialize)]
pub enum BoxMeasureKind {
    LeastMargin,
    EdgesTouchedMax,
    EdgesTouchedMin,
    CenteredAxesMax,
    ShorterSideMin,
    LongerSideMax,
    Aligned,
    OneSize,
    SomeOverlap,
    Nested,
    CoverGrid,
    EvenlySpaced,
    EverySquare,
    MoreThanOneCell,
    WholeGrid,
}

impl BoxMeasureKind {
    pub const ALL: [BoxMeasureKind; 15] = [BoxMeasureKind::LeastMargin, BoxMeasureKind::EdgesTouchedMax, BoxMeasureKind::EdgesTouchedMin, BoxMeasureKind::CenteredAxesMax, BoxMeasureKind::ShorterSideMin, BoxMeasureKind::LongerSideMax, BoxMeasureKind::Aligned, BoxMeasureKind::OneSize, BoxMeasureKind::SomeOverlap, BoxMeasureKind::Nested, BoxMeasureKind::CoverGrid, BoxMeasureKind::EvenlySpaced, BoxMeasureKind::EverySquare, BoxMeasureKind::MoreThanOneCell, BoxMeasureKind::WholeGrid];

    /// Whether it gives a number, and so a row of its value.
    pub fn is_number(self) -> bool {
        (self as usize) <= (BoxMeasureKind::LongerSideMax as usize)
    }

    /// The fragment that defines it.
    pub fn fragment(self) -> &'static str {
        match self {
            BoxMeasureKind::LeastMargin => "boxes-least-margin",
            BoxMeasureKind::EdgesTouchedMax => "boxes-edges-touched-max",
            BoxMeasureKind::EdgesTouchedMin => "boxes-edges-touched-min",
            BoxMeasureKind::CenteredAxesMax => "boxes-centered-axes-max",
            BoxMeasureKind::ShorterSideMin => "boxes-shorter-side-min",
            BoxMeasureKind::LongerSideMax => "boxes-longer-side-max",
            BoxMeasureKind::Aligned => "boxes-aligned",
            BoxMeasureKind::OneSize => "boxes-one-size",
            BoxMeasureKind::SomeOverlap => "boxes-some-overlap",
            BoxMeasureKind::Nested => "boxes-nested",
            BoxMeasureKind::CoverGrid => "boxes-cover-frame",
            BoxMeasureKind::EvenlySpaced => "boxes-evenly-spaced",
            BoxMeasureKind::EverySquare => "boxes-every-square",
            BoxMeasureKind::MoreThanOneCell => "boxes-more-than-one-cell",
            BoxMeasureKind::WholeGrid => "boxes-whole-frame",
        }
    }
}

/// A flag that a column's values give as a whole, or a count of them.
#[derive(Clone, Copy, Debug, PartialEq, Eq, serde::Serialize, serde::Deserialize)]
pub enum ColumnMeasureKind {
    Consecutive,
    Arithmetic,
    OnOneAxis,
    OppositePair,
    OneLength,
    ExtentsDistinct,
}

impl ColumnMeasureKind {
    /// The fragment that defines it.
    pub fn fragment(self) -> &'static str {
        match self {
            ColumnMeasureKind::Consecutive => "values-consecutive",
            ColumnMeasureKind::Arithmetic => "values-arithmetic",
            ColumnMeasureKind::OnOneAxis => "directions-on-one-axis",
            ColumnMeasureKind::OppositePair => "directions-opposite-pair",
            ColumnMeasureKind::OneLength => "offsets-one-length",
            ColumnMeasureKind::ExtentsDistinct => "extents-distinct",
        }
    }
}

/// What a set of boxes says together, by [`BoxMeasureKind`]. A measure that a set does not reach has no value.
#[derive(Clone, Copy, Default)]
pub struct BoxFeatures {
    values: [Option<i32>; 15],
}

/// The extents of the frame of a relation's cell column, where its cells lie in one frame.
fn frame_of_rows(value: &Val, f: u16) -> Option<(i32, i32)> {
    let table = flat(value)?;
    if !on_one_frame(&table, &[], f) {
        return None;
    }
    let m = margins_of(table.rows().next()?[usize::from(f)]);
    Some((m[0] + m[1] + 1, m[2] + m[3] + 1))
}

fn box_features_of(table: &Table, b: u16, h: i32, w: i32) -> BoxFeatures {
    let key = (table.hash(), places_word(&[], Some(b)) ^ (u128::from(h as u32) << 96) ^ (u128::from(w as u32) << 64));
    if let Some(found) = GROUPS.with(|groups| groups.borrow().boxes.get(&key).copied()) {
        return found;
    }
    let mut set: Vec<[i32; 4]> = sorted_values(table, b).iter().copied().map(margins_of).collect();
    set.sort_unstable();
    let built = box_features(&set, h, w);
    GROUPS.with(|groups| {
        groups.borrow_mut().boxes.insert(key, built);
    });
    built
}

/// What a set of boxes in an H by W frame says together, each box as its margins.
fn box_features(set: &[[i32; 4]], h: i32, w: i32) -> BoxFeatures {
    use BoxMeasureKind::*;
    let mut out = BoxFeatures::default();
    let mut put = |measure: BoxMeasureKind, value: i32| out.values[measure as usize] = Some(value);
    let sides: Vec<(i32, i32)> = set.iter().map(|m| (h - m[0] - m[1], w - m[2] - m[3])).filter(|side| side.0 > 0 && side.1 > 0).collect();
    if !set.is_empty() {
        let edges = |m: &[i32; 4]| m.iter().filter(|margin| **margin == 0).count() as i32;
        put(LeastMargin, set.iter().flat_map(|m| m.iter().copied()).min().unwrap_or(0));
        put(EdgesTouchedMax, set.iter().map(edges).max().unwrap_or(0));
        put(EdgesTouchedMin, set.iter().map(edges).min().unwrap_or(0));
        put(CenteredAxesMax, set.iter().map(|m| i32::from(m[0] == m[1]) + i32::from(m[2] == m[3])).max().unwrap_or(0));
    }
    if set.len() > 1 {
        let one_of = |pick: &dyn Fn(&[i32; 4]) -> (i32, i32)| set.iter().all(|m| pick(m) == pick(&set[0]));
        put(Aligned, i32::from(one_of(&|m| (m[0], m[1])) || one_of(&|m| (m[2], m[3]))));
        put(OneSize, i32::from(!sides.is_empty() && sides.iter().all(|side| *side == sides[0])));
        let spans: Vec<[i32; 4]> = set.iter().map(|m| [m[0], h - 1 - m[1], m[2], w - 1 - m[3]]).filter(|s| s[0] <= s[1] && s[2] <= s[3]).collect();
        // Two boxes overlap where a cell of the frame lies in both.
        let held: Vec<[i32; 4]> = spans.iter().map(|s| [s[0].max(0), s[1].min(h - 1), s[2].max(0), s[3].min(w - 1)]).filter(|s| s[0] <= s[1] && s[2] <= s[3]).collect();
        let (mut overlap, mut nested) = (false, false);
        for (at, x) in held.iter().enumerate() {
            for (other, y) in held.iter().enumerate() {
                overlap = overlap || (at != other && x[0] <= y[1] && y[0] <= x[1] && x[2] <= y[3] && y[2] <= x[3]);
            }
        }
        for (at, x) in spans.iter().enumerate() {
            for (other, y) in spans.iter().enumerate() {
                nested = nested || (at != other && y[0] <= x[0] && x[1] <= y[1] && y[2] <= x[2] && x[3] <= y[3]);
            }
        }
        put(SomeOverlap, i32::from(overlap));
        put(Nested, i32::from(nested));
        if h > 0 && w > 0 {
            let mut seen = vec![false; (h * w) as usize];
            for s in &spans {
                for r in s[0].max(0)..=s[1].min(h - 1) {
                    for c in s[2].max(0)..=s[3].min(w - 1) {
                        seen[(r * w + c) as usize] = true;
                    }
                }
            }
            put(CoverGrid, i32::from(seen.iter().all(|held| *held)));
        }
        if spans.len() >= 3 {
            let mut even = false;
            for (lo, hi) in [(0, 1), (2, 3)] {
                let mut lines: Vec<(i32, i32)> = spans.iter().map(|s| (s[lo], s[hi])).collect();
                lines.sort_unstable();
                lines.dedup();
                if lines.len() >= 3 && lines.windows(2).all(|pair| pair[0].1 < pair[1].0) {
                    let gap = lines[1].0 - lines[0].1;
                    even = even || lines.windows(2).all(|pair| pair[1].0 - pair[0].1 == gap);
                }
            }
            put(EvenlySpaced, i32::from(even));
        }
    }
    if !sides.is_empty() {
        put(ShorterSideMin, sides.iter().map(|side| side.0.min(side.1)).min().unwrap_or(0));
        put(LongerSideMax, sides.iter().map(|side| side.0.max(side.1)).max().unwrap_or(0));
        put(EverySquare, i32::from(sides.iter().all(|side| side.0 == side.1)));
    }
    if let [m] = set {
        let (along, across) = (h - m[0] - m[1], w - m[2] - m[3]);
        put(MoreThanOneCell, i32::from(along > 1 && across > 1));
        put(WholeGrid, i32::from(*m == [0, 0, 0, 0]));
    }
    out
}

/// The boxes of a column that decide whether a box lies inside one of them, or holds one: the ones no other box is beyond on every margin. Past 64 of them, every box. Held with the table.
fn box_front(table: &Table, b: u16, inside: bool) -> Arc<Vec<[i32; 4]>> {
    let key = (table.hash(), places_word(&[], Some(b)) ^ u128::from(inside));
    if let Some(found) = GROUPS.with(|groups| groups.borrow().fronts.get(&key).cloned()) {
        return found;
    }
    let mut boxes: Vec<[i32; 4]> = table.sorted_column(usize::from(b)).iter().map(|cell| margins_of(*cell)).collect();
    boxes.sort_unstable();
    // A box that is beyond another on every margin stands after it in order, or before it where the boxes to hold are the greatest.
    let mut front: Vec<[i32; 4]> = Vec::new();
    let mut crowded = false;
    let order: Box<dyn Iterator<Item = &[i32; 4]>> = if inside { Box::new(boxes.iter()) } else { Box::new(boxes.iter().rev()) };
    for held in order {
        let covered = front.iter().any(|other| (0..4).all(|at| if inside { other[at] <= held[at] } else { other[at] >= held[at] }));
        if !covered {
            front.push(*held);
            if front.len() > 64 {
                crowded = true;
                break;
            }
        }
    }
    let built = Arc::new(if crowded { boxes } else { front });
    GROUPS.with(|groups| {
        let mut groups = groups.borrow_mut();
        groups.held += table.len;
        if groups.held > HELD_GROUP_CELLS {
            *groups = Groups { held: table.len, ..Groups::default() };
        }
        groups.fronts.insert(key, built.clone());
    });
    built
}

/// How many of a column's distinct cells lie in a frame of `h` rows and `w` columns, counted once for all that ask.
fn cells_in_frame(table: &Table, at: u16, h: i32, w: i32, cells: &[Cell], in_frame: &dyn Fn(&Cell) -> bool) -> usize {
    let key = (table.hash(), places_word(&[], Some(at)) ^ (u128::from(h as u32) << 96) ^ (u128::from(w as u32) << 64));
    if let Some(found) = GROUPS.with(|groups| groups.borrow().in_frames.get(&key).copied()) {
        return found;
    }
    let count = cells.iter().filter(|cell| in_frame(cell)).count();
    GROUPS.with(|groups| {
        groups.borrow_mut().in_frames.insert(key, count);
    });
    count
}

/// The distinct values of one column at each value of another, held with the table.
fn colors_by_cell(table: &Table, cell: u16, color: u16) -> Arc<BTreeMap<Cell, Vec<Cell>>> {
    let key = (table.hash(), places_word(&[cell], Some(color)));
    if let Some(found) = GROUPS.with(|groups| groups.borrow().colors.get(&key).cloned()) {
        return found;
    }
    let mut held: BTreeMap<Cell, Vec<Cell>> = BTreeMap::new();
    for row in table.rows() {
        held.entry(row[usize::from(cell)]).or_default().push(row[usize::from(color)]);
    }
    for values in held.values_mut() {
        values.sort_unstable();
        values.dedup();
    }
    let built = Arc::new(held);
    GROUPS.with(|groups| {
        let mut groups = groups.borrow_mut();
        groups.held += table.len;
        if groups.held > HELD_GROUP_CELLS {
            *groups = Groups { held: table.len, ..Groups::default() };
        }
        groups.colors.insert(key, built.clone());
    });
    built
}

/// The distinct margins of a column of boxes on each edge, in order, held with the table.
fn margin_sets(table: &Table, b: u16) -> Arc<[Vec<i32>; 4]> {
    let key = (table.hash(), places_word(&[], Some(b)));
    if let Some(found) = GROUPS.with(|groups| groups.borrow().margins.get(&key).cloned()) {
        return found;
    }
    let mut margins: [Vec<i32>; 4] = Default::default();
    for cell in table.sorted_column(usize::from(b)).iter() {
        let m = margins_of(*cell);
        for at in 0..4 {
            margins[at].push(m[at]);
        }
    }
    for held in &mut margins {
        held.sort_unstable();
        held.dedup();
    }
    let built = Arc::new(margins);
    GROUPS.with(|groups| {
        let mut groups = groups.borrow_mut();
        groups.held += table.len;
        if groups.held > HELD_GROUP_CELLS {
            *groups = Groups { held: table.len, ..Groups::default() };
        }
        groups.margins.insert(key, built.clone());
    });
    built
}

fn sorted_values(table: &Table, at: u16) -> Arc<[Cell]> {
    table.sorted_column(usize::from(at))
}

/// Whether the cells of two sets all lie in one frame: their margins give one height and one width.
fn one_frame_of(own: &[Cell], theirs: &[Cell]) -> bool {
    let mut frame = None;
    own.iter().chain(theirs).all(|cell| {
        let m = margins_of(*cell);
        let here = (m[0] + m[1], m[2] + m[3]);
        *frame.get_or_insert(here) == here
    })
}

/// The fewest steps of eight directions from a cell of `own` to a cell of `theirs`, both nonempty and in one frame. Two passes over their bounding box give each place its distance from `theirs`.
fn least_gap(own: &[Cell], theirs: &[Cell]) -> i64 {
    let places = |cells: &[Cell]| -> Vec<(i32, i32)> { cells.iter().map(|cell| { let m = margins_of(*cell); (m[0], m[2]) }).collect() };
    let (mine, others) = (places(own), places(theirs));
    let both = || mine.iter().chain(&others);
    let (r0, r1) = (both().map(|at| at.0).min().unwrap_or(0), both().map(|at| at.0).max().unwrap_or(0));
    let (c0, c1) = (both().map(|at| at.1).min().unwrap_or(0), both().map(|at| at.1).max().unwrap_or(0));
    let (h, w) = ((r1 - r0 + 1) as usize, (c1 - c0 + 1) as usize);
    let at = |r: i32, c: i32| (r - r0) as usize * w + (c - c0) as usize;
    let far = (h + w) as u32 + 1;
    let mut gap = vec![far; h * w];
    for (r, c) in &others {
        gap[at(*r, *c)] = 0;
    }
    for here in 0..h * w {
        let (r, c) = (here / w, here % w);
        let mut best = gap[here];
        if c > 0 {
            best = best.min(gap[here - 1] + 1);
        }
        if r > 0 {
            best = best.min(gap[here - w] + 1);
            if c > 0 {
                best = best.min(gap[here - w - 1] + 1);
            }
            if c + 1 < w {
                best = best.min(gap[here - w + 1] + 1);
            }
        }
        gap[here] = best;
    }
    for here in (0..h * w).rev() {
        let (r, c) = (here / w, here % w);
        let mut best = gap[here];
        if c + 1 < w {
            best = best.min(gap[here + 1] + 1);
        }
        if r + 1 < h {
            best = best.min(gap[here + w] + 1);
            if c + 1 < w {
                best = best.min(gap[here + w + 1] + 1);
            }
            if c > 0 {
                best = best.min(gap[here + w - 1] + 1);
            }
        }
        gap[here] = best;
    }
    i64::from(mine.iter().map(|(r, c)| gap[at(*r, *c)]).min().unwrap_or(0))
}

/// How two sorted sets stand to each other. With `fill`, a frame's count of cells and the count of the second set's cells in it, two disjoint sets that fill the frame are complements.
fn set_relation<K: Ord>(own: &[K], theirs: &[K], fill: Option<(usize, usize)>) -> SetRelation {
    let mut shared = 0usize;
    if own.len().min(theirs.len()) * 16 < own.len().max(theirs.len()) {
        // The smaller set is searched in the larger.
        shared = if own.len() < theirs.len() { own.iter().filter(|key| theirs.binary_search(key).is_ok()).count() } else { theirs.iter().filter(|key| own.binary_search(key).is_ok()).count() };
    } else {
        let (mut at, mut there) = (0, 0);
        while at < own.len() && there < theirs.len() {
            match own[at].cmp(&theirs[there]) {
                std::cmp::Ordering::Less => at += 1,
                std::cmp::Ordering::Greater => there += 1,
                std::cmp::Ordering::Equal => {
                    shared += 1;
                    at += 1;
                    there += 1;
                }
            }
        }
    }
    relation(shared < own.len(), shared < theirs.len(), shared > 0, fill.is_some_and(|(area, there)| area == own.len() + there))
}

/// A part with the columns that it reads of its relations, which are listed once when the part is made.
#[derive(Clone, serde::Serialize, serde::Deserialize)]
#[serde(into = "PartStep", try_from = "PartStep")]
pub struct PartTerm {
    step: PartStep,
    set: Option<Columns>,
    second: Option<Columns>,
}

impl PartTerm {
    /// The part `step`; a panic that shows it where a list of columns that it reads has one column twice.
    pub fn new(step: PartStep) -> Box<PartTerm> {
        Box::new(PartTerm::try_from(step).unwrap_or_else(|message| panic!("{message}")))
    }

    pub fn step(&self) -> &PartStep {
        &self.step
    }

    /// The columns of the first relation that the part reads, where what it gives depends on the distinct tuples of the rows at those columns alone: the other columns of a row play no part, and a row that repeats makes no difference.
    pub(crate) fn set_columns(&self) -> Option<&Columns> {
        self.set.as_ref()
    }

    /// The columns of the second relation that the part reads, where what it gives depends on the distinct tuples of the rows at those columns alone.
    pub(crate) fn second_columns(&self) -> Option<&Columns> {
        self.second.as_ref()
    }

    /// The columns, sorted and distinct, of the first relation that fix what the part adds to a row, where the part gives every row it takes with its own cells first, and then cells that the cells at those columns alone fix, for as many rows as they allow.
    pub(crate) fn row_columns(&self) -> Option<Vec<u16>> {
        let mut columns = self.step.row_list()?;
        columns.sort_unstable();
        columns.dedup();
        Some(columns)
    }

    /// Whether the part takes what it needs from the rows of `inside` as their boxes, where the relation has `width` columns.
    pub(crate) fn reads_boxes(&self, width: u16) -> bool {
        self.step.reads_boxes(width, self.set.is_some())
    }

    /// What the part gives over the rows of `inside`, where `reads_boxes` holds of it.
    pub(crate) fn read_boxes(&self, boxes: &crate::boxes::Boxes, children: &[&Val]) -> Option<Val> {
        self.step.read_boxes(boxes, children, self.set.as_ref())
    }
}

impl std::ops::Deref for PartTerm {
    type Target = PartStep;

    fn deref(&self) -> &PartStep {
        &self.step
    }
}

impl std::fmt::Debug for PartTerm {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        std::fmt::Debug::fmt(&self.step, f)
    }
}

impl From<PartTerm> for PartStep {
    fn from(part: PartTerm) -> PartStep {
        part.step
    }
}

impl TryFrom<PartStep> for PartTerm {
    type Error = String;

    fn try_from(step: PartStep) -> Result<PartTerm, String> {
        let list = |list: Option<Vec<u16>>| list.map(|list| Columns::new(list.as_slice()).map_err(|repeat| format!("{repeat} in the columns {list:?} that the part {step:?} reads"))).transpose();
        let (set, second) = (list(step.set_list())?, list(step.second_list())?);
        Ok(PartTerm { step, set, second })
    }
}

impl PartStep {
    /// The keys of a part whose count of rows reads them only through how they group the rows: its
    /// output has one distinct head per group, so two keys that group the rows alike give one count.
    pub fn grouping_keys(&self) -> Option<&[u16]> {
        match self {
            PartStep::DiffGroupsOff { keys, .. } | PartStep::Pieces { keys, .. } | PartStep::BoxOf { keys, .. } | PartStep::RelBox { keys, .. } | PartStep::Count { keys } | PartStep::OneValue { keys, .. } | PartStep::Several { keys, .. } | PartStep::Determines { keys, .. } | PartStep::Extreme { keys, .. } | PartStep::ClassOf { keys } | PartStep::MostFrequentRows { keys, .. } | PartStep::SecondFrequentRows { keys, .. } | PartStep::DeterminesFlag { keys, .. } | PartStep::ShapeClass { keys, .. } | PartStep::Holes { keys, .. } | PartStep::Symmetry { keys, .. } | PartStep::TouchesEdge { keys, .. } | PartStep::FillsBox { keys, .. } | PartStep::Occurs { keys, .. } | PartStep::SameShape { keys, .. } | PartStep::BoxSides { keys, .. } | PartStep::BoxMargins { keys, .. } | PartStep::LineCounts { keys, .. } | PartStep::CellCount { keys, .. } | PartStep::GroupGap { keys, .. } | PartStep::Straight { keys, .. } | PartStep::FullLines { keys, .. } => Some(keys),
            _ => None,
        }
    }

    /// Whether the part is empty where its first relation is.
    pub fn apply(&self, children: &[&Val]) -> Val {
        let Some(first) = flat(children[0]) else { return Val::None };
        if matches!(children[0], Val::Empty) && !self.gives_rows_on_no_rows() {
            return Val::Empty;
        }
        self.run(&first, children).unwrap_or(Val::None)
    }

    /// The columns of the part's first relation that it reads, where what it gives depends on the distinct tuples of the rows at those columns alone: the other columns of a row play no part, and a row that repeats makes no difference.
    fn set_list(&self) -> Option<Vec<u16>> {
        let with = |keys: &[u16], more: &[u16]| Some(keys.iter().chain(more).copied().collect());
        match self {
            PartStep::Pieces { keys, p, .. } | PartStep::BoxOf { keys, p } | PartStep::RelBox { keys, p } | PartStep::ShapeClass { keys, p, .. } | PartStep::Holes { keys, p } | PartStep::Symmetry { keys, p } | PartStep::TouchesEdge { keys, p } | PartStep::FillsBox { keys, p } | PartStep::BoxSides { keys, p } | PartStep::BoxMargins { keys, p } | PartStep::LineCounts { keys, p } | PartStep::CellCount { keys, p } | PartStep::GroupGap { keys, p } | PartStep::Straight { keys, p } | PartStep::StraightAxis { keys, p } | PartStep::FullLines { keys, p } | PartStep::DiffGroupsOff { keys, p, .. } => with(keys, &[*p]),
            PartStep::OneValue { keys, f } | PartStep::Several { keys, f } | PartStep::Determines { keys, f } => with(keys, &[*f]),
            PartStep::Extreme { keys, t, score, .. } => with(keys, &[*t, *score]),
            PartStep::NumberExtreme { n, .. } => Some(vec![*n]),
            PartStep::CellsOn { p } | PartStep::ColorsUnder { p } | PartStep::Around { p } | PartStep::NeighborhoodClass { p } | PartStep::NeighborColorClass { p } | PartStep::SameColorNeighbors { p } | PartStep::Distance { p } | PartStep::FrameExtent { p } | PartStep::Complement { p } | PartStep::BoxCells { p, .. } | PartStep::HoleCells { p } | PartStep::DiffCells { p, .. } | PartStep::TopColorsUnder { p } | PartStep::FrameCells { p } | PartStep::ComplementParts { p } | PartStep::EveryPartStraight { p } | PartStep::OutlinesBox { p } | PartStep::LineSpacings { p } => Some(vec![*p]),
            PartStep::DeterminesFlag { keys, a, .. } => with(keys, &[*a]),
            PartStep::Occurs { keys, p, v, .. } => with(keys, &[*p, *v]),
            _ => None,
        }
    }

    /// The columns of the part's first relation that fix what it adds to each row, for a part that gives every row it takes with its own cells first and then the cells that those columns alone fix.
    fn row_list(&self) -> Option<Vec<u16>> {
        match self {
            PartStep::DiffRows { p, .. } | PartStep::Neighbors { p } | PartStep::Split { p } | PartStep::Margin { p } | PartStep::CornerDist { p } | PartStep::Parity { p } | PartStep::BorderDistance { p } => Some(vec![*p]),
            PartStep::BoxMargin { b } | PartStep::BoxExtent { b } => Some(vec![*b]),
            PartStep::Displacement { a, b } => Some(vec![*a, *b]),
            _ => None,
        }
    }

    /// The columns of the part's second relation that it reads, where what it gives depends on the distinct tuples of the rows at those columns alone.
    fn second_list(&self) -> Option<Vec<u16>> {
        match self {
            PartStep::DeterminesFlag { b, .. } => Some(vec![*b]),
            _ => None,
        }
    }

    /// Whether the part takes what it needs from the rows of `inside` as their boxes, where the relation has `width` columns: it reads the columns of the relation alone and counts a row once for each cell of its box, or it reads a set of columns (`has_set`).
    fn reads_boxes(&self, width: u16, has_set: bool) -> bool {
        match self {
            PartStep::Count { keys } => keys.iter().all(|key| *key < width),
            PartStep::MostFrequentRows { keys, v } | PartStep::SecondFrequentRows { keys, v } => *v < width && keys.iter().all(|key| *key < width),
            _ => has_set,
        }
    }

    /// What the part gives over the rows of `inside`, where `reads_boxes` holds of it: a count of rows counts the cells of each box. `set` is the part's set of columns of the first relation.
    fn read_boxes(&self, boxes: &crate::boxes::Boxes, children: &[&Val], set: Option<&Columns>) -> Option<Val> {
        match self {
            PartStep::Count { keys } => {
                let t = boxes.support();
                let at = usize::from(boxes.at());
                let (grouping, first) = key_ids(&t, keys);
                let mut counts = vec![0u64; first.len()];
                for (row, id) in t.rows().zip(&grouping.0) {
                    counts[*id as usize] += boxes.area(row[at]);
                }
                let mut out = Vec::new();
                for (count, head) in counts.iter().zip(&first) {
                    // A count past a number's range has no value.
                    let Ok(count) = i32::try_from(*count) else { return Some(Val::None) };
                    push_key(&mut out, head, keys);
                    out.push(number_bits(i64::from(count)));
                }
                Some(Val::of_table(Table::new(keys.len() + 1, out)))
            }
            PartStep::MostFrequentRows { keys, v } | PartStep::SecondFrequentRows { keys, v } => {
                // A relation's row stands once for each cell of its box, and the rows that stay are whole relation rows.
                let t = boxes.support();
                let at = usize::from(boxes.at());
                let weights: Vec<u64> = t.rows().map(|row| boxes.area(row[at])).collect();
                Some(match frequent_rows(&t, keys, *v, matches!(self, PartStep::SecondFrequentRows { .. }), Some(&weights)) {
                    Frequent::All => boxes.with_rows(&t),
                    Frequent::Rows(out) => boxes.with_rows(&Table::new(t.arity, out)),
                })
            }
            _ => {
                let columns = set?;
                Some(match boxes.rows_at(columns) {
                    Some(t) => self.run(&t, children).unwrap_or(Val::None),
                    None => Val::None,
                })
            }
        }
    }

    pub(crate) fn run(&self, t: &Arc<Table>, children: &[&Val]) -> Option<Val> {
        let e = encoding();
        Some(match self {
            PartStep::DiffRows { p, output, on } => {
                let (input, other) = grids_of(children[1])?;
                let (one, two) = if *output { (&other, &input) } else { (&input, &other) };
                let mut out = Vec::new();
                for row in t.rows() {
                    let cell = row[usize::from(*p)];
                    let in_diff = one.color_of(cell).is_some_and(|color| two.color_of(cell) != Some(color));
                    if in_diff == *on {
                        push_row(&mut out, row);
                    }
                }
                Val::of_table(Table::new(t.arity, out))
            }
            PartStep::DiffGroupsOff { keys, p, output } => {
                let (input, other) = grids_of(children[1])?;
                let (one, two) = if *output { (&other, &input) } else { (&input, &other) };
                let (grouping, first) = key_ids(t, keys);
                let ids = &grouping.0;
                let mut touching = vec![false; first.len()];
                for (row, id) in t.rows().zip(ids) {
                    let cell = row[usize::from(*p)];
                    touching[*id as usize] |= one.color_of(cell).is_some_and(|color| two.color_of(cell) != Some(color));
                }
                keys_only(&first.heads(keys), touching.into_iter().map(|held| !held), keys.len())
            }
            PartStep::DiffCells { p, output, on } => {
                let (input, other) = grids_of(children[1])?;
                let (one, two) = if *output { (&other, &input) } else { (&input, &other) };
                let held = t.sorted_column(usize::from(*p));
                let mut out = Vec::new();
                for (cell, color) in &one.pairs {
                    if two.color_of(*cell) != Some(*color) && held.binary_search(cell).is_ok() == *on {
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
                let mut seen: LookupMap<Cell, Vec<Cell>> = LookupMap::default();
                for row in t.rows() {
                    seen.entry(row[usize::from(*n)]).or_default().push(row[usize::from(*e)]);
                }
                let mut out = Vec::new();
                for (value, mut held) in seen.into_sorted_vec() {
                    held.sort_unstable();
                    held.dedup();
                    if held == every {
                        out.push(value);
                    }
                }
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
                let held: Vec<(Cell, u128)> = sums.into_sorted_vec();
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
                let out: Vec<Cell> = t.sorted_column(usize::from(*p)).iter().copied().filter(|cell| grid.color_of(*cell).is_some()).collect();
                Val::of_table(Table::new(1, out))
            }
            PartStep::ColorsUnder { p } => {
                let grid = grid_of(children[1])?;
                let mut out: Vec<Cell> = t.sorted_column(usize::from(*p)).iter().filter_map(|cell| grid.color_of(*cell)).collect();
                out.sort_unstable();
                out.dedup();
                Val::of_table(Table::new(1, out))
            }
            PartStep::Around { p } => {
                let own = t.sorted_column(usize::from(*p));
                let mut out = Vec::new();
                for cell in own.iter() {
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
            PartStep::Neighbors { p } => rows_with(t, 2, 8, |row, out| {
                let m = margins_of(row[usize::from(*p)]);
                for (at, (dr, dc)) in STEPS.iter().enumerate() {
                    if let Some(next) = moved(m, *dr, *dc) {
                        push_row(out, row);
                        out.push(e.dirs[at]);
                        out.push(next);
                    }
                }
            }),
            PartStep::Split { p } => rows_with(t, 2, 2, |row, out| {
                let m = margins_of(row[usize::from(*p)]);
                push_row(out, row);
                out.push(e.axes[0]);
                out.push(box_bits(m[0], m[1], 0, 0));
                push_row(out, row);
                out.push(e.axes[1]);
                out.push(box_bits(0, 0, m[2], m[3]));
            }),
            PartStep::Margin { p } => rows_with(t, 2, 4, |row, out| {
                let m = margins_of(row[usize::from(*p)]);
                for at in 0..4 {
                    push_row(out, row);
                    out.push(e.dirs[at]);
                    out.push(number_bits(i64::from(m[at])));
                }
            }),
            PartStep::CornerDist { p } => rows_with(t, 2, 4, |row, out| {
                let m = margins_of(row[usize::from(*p)]);
                for (at, (a, b)) in [(0, 2), (0, 3), (1, 2), (1, 3)].iter().enumerate() {
                    push_row(out, row);
                    out.push(e.dirs[4 + at]);
                    out.push(number_bits(i64::from(m[*a] + m[*b])));
                }
            }),
            PartStep::Parity { p } => rows_with(t, 2, 4, |row, out| {
                let m = margins_of(row[usize::from(*p)]);
                for (at, (a, b)) in [(0, 2), (0, 3), (1, 2), (1, 3)].iter().enumerate() {
                    push_row(out, row);
                    out.push(e.dirs[4 + at]);
                    out.push(number_bits(i64::from((m[*a] + m[*b]).rem_euclid(2))));
                }
            }),
            PartStep::BorderDistance { p } => rows_with(t, 1, 1, |row, out| {
                let m = margins_of(row[usize::from(*p)]);
                push_row(out, row);
                out.push(number_bits(i64::from(m[0].min(m[1]).min(m[2]).min(m[3]))));
            }),
            PartStep::Pieces { keys, p, four } => pieces(t, keys, *p, *four),
            PartStep::BoxOf { keys, p } => {
                let (grouping, first) = key_ids(t, keys);
                let ids = &grouping.0;
                let mut spans = vec![[i32::MAX; 4]; first.len()];
                for (row, id) in t.rows().zip(ids) {
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
                let (grouping, first) = key_ids(t, keys);
                let ids = &grouping.0;
                let mut spans = vec![[i32::MAX; 4]; first.len()];
                for (row, id) in t.rows().zip(ids) {
                    let m = margins_of(row[usize::from(*p)]);
                    let held = &mut spans[*id as usize];
                    for at in 0..4 {
                        held[at] = held[at].min(m[at]);
                    }
                }
                let mut out = Vec::new();
                let mut every_box = true;
                for (row, id) in t.rows().zip(ids) {
                    let m = margins_of(row[usize::from(*p)]);
                    let s = &spans[*id as usize];
                    push_key(&mut out, row, keys);
                    let rel = box_bits(m[0] - s[0], m[1] - s[1], m[2] - s[2], m[3] - s[3]);
                    every_box &= rel != u32::MAX;
                    out.push(rel);
                }
                // Where the keys and the cell are all the columns, two rows differ in them, and so do their rows here, as long as each cell has a box.
                if every_box && are_all_columns(t.arity, keys.iter().copied().chain([*p])) {
                    Val::of_table(Table::new(keys.len() + 1, out))
                } else {
                    Val::of_table(Table::distinct(keys.len() + 1, out))
                }
            }
            PartStep::Count { keys } => {
                let (grouping, first) = key_ids(t, keys);
                let ids = &grouping.0;
                let mut counts = vec![0i64; first.len()];
                for id in ids {
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
                let (grouping, first) = key_ids(t, keys);
                let ids = &grouping.0;
                // The value of each key's first row, which the key's other rows are compared with.
                let held: Vec<Cell> = first.iter().map(|row| row[usize::from(*f)]).collect();
                if let PartStep::Determines { .. } = self {
                    // On no rows it is false, as an `ALL` form's empty domain is. A key with two values makes it false at once.
                    let holds = !first.is_empty() && t.rows().zip(ids).all(|(row, id)| row[usize::from(*f)] == held[*id as usize]);
                    return Some(Val::of_table(Table::unit(holds)));
                }
                let mut many = vec![false; first.len()];
                for (row, id) in t.rows().zip(ids) {
                    many[*id as usize] |= row[usize::from(*f)] != held[*id as usize];
                }
                match self {
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
                            // The keys differ, so the rows do.
                            Val::of_table(Table::new(keys.len(), out))
                        }
                    }
                    _ => {
                        let mut out = Vec::new();
                        for ((flag, value), head) in many.iter().zip(&held).zip(&first) {
                            if !*flag {
                                push_key(&mut out, head, keys);
                                out.push(*value);
                            }
                        }
                        Val::of_table(Table::new(keys.len() + 1, out))
                    }
                }
            }
            PartStep::Extreme { keys, t: column, score, greatest } => {
                let (grouping, first) = key_ids(t, keys);
                let ids = &grouping.0;
                let mut best: Vec<Option<i64>> = vec![None; first.len()];
                for (row, id) in t.rows().zip(ids) {
                    let value = number_of(row[usize::from(*score)]);
                    let held = &mut best[*id as usize];
                    *held = Some(held.map_or(value, |own| if *greatest { own.max(value) } else { own.min(value) }));
                }
                let mut out = Vec::new();
                for (row, id) in t.rows().zip(ids) {
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
                let (grouping, first) = key_ids(t, keys);
                let ids = &grouping.0;
                let mut sums = vec![0u128; first.len()];
                // The columns that are no key, in order.
                let rest: Vec<usize> = (0..t.arity).filter(|at| !keys.contains(&(*at as u16))).collect();
                for (row, id) in t.rows().zip(ids) {
                    sums[*id as usize] = sums[*id as usize].wrapping_add(hash_words(rest.iter().map(|at| u64::from(row[*at]))));
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
                let own: Vec<(Cell, Cell)> = t.sorted_column(usize::from(*p)).iter().filter_map(|cell| grid.color_of(*cell).map(|color| (*cell, color))).collect();
                let mut out = Vec::new();
                // In a dense grid the three values of every cell are found once for the grid.
                let hoods = grid.dense.then(|| grid.hoods());
                for (cell, mine) in &own {
                    let (cell, mine) = (*cell, *mine);
                    let hood = match hoods {
                        Some(hoods) => {
                            let m = margins_of(cell);
                            hoods[(m[0] * grid.w + m[2]) as usize]
                        }
                        None => grid.hood_of(cell, mine),
                    };
                    out.push(cell);
                    match self {
                        PartStep::NeighborhoodClass { .. } => out.push(hood.class),
                        PartStep::NeighborColorClass { .. } => out.push(hood.colors),
                        _ => {
                            out.push(mine);
                            out.push(number_bits(hood.same));
                        }
                    }
                }
                let width = if matches!(self, PartStep::SameColorNeighbors { .. }) { 3 } else { 2 };
                Val::of_table(Table::new(width, out))
            }
            PartStep::MostFrequentRows { keys, v } | PartStep::SecondFrequentRows { keys, v } => {
                match frequent_rows(t, keys, *v, matches!(self, PartStep::SecondFrequentRows { .. }), None) {
                    Frequent::All => Val::of_table(t.clone()),
                    Frequent::Rows(out) => Val::of_table(Table::new(t.arity, out)),
                }
            }
            PartStep::DeterminesFlag { keys, a, b } => {
                let other = flat(children[1])?;
                let held = other.sorted_column(usize::from(*b));
                let (grouping, first) = key_ids(t, keys);
                if first.is_empty() {
                    return Some(Val::of_table(Table::unit(false)));
                }
                // Whether each distinct value of the column is among the second relation's values, looked up once per value.
                let values = t.column_grouping(usize::from(*a));
                let found: Vec<bool> = values.1.iter().map(|at| held.binary_search(&t.cells()[*at as usize * t.arity + usize::from(*a)]).is_ok()).collect();
                // Each key's flag: 0 and 1 are the found flag of the key's rows so far, and 2 is that it has none yet. A key with both flags makes it false.
                let mut flag = vec![2u8; first.len()];
                for (id, value) in grouping.0.iter().zip(&values.0) {
                    let own = u8::from(found[*value as usize]);
                    let seen = &mut flag[*id as usize];
                    if *seen == 2 {
                        *seen = own;
                    } else if *seen != own {
                        return Some(Val::of_table(Table::unit(false)));
                    }
                }
                Val::of_table(Table::unit(true))
            }
            PartStep::ShapeClass { keys, p, turned } => {
                if !on_one_frame(t, keys, *p) {
                    return None;
                }
                let held = cells_by_key(t, keys, *p);
                let (cells, heads) = (&held.0, &held.1);
                keyed_values(&heads, cells.iter().map(|held| (!held.is_empty()).then(|| shape_hash(held, *turned))), keys.len() + 1)
            }
            PartStep::Holes { keys, p } => {
                if !on_one_frame(t, keys, *p) {
                    return None;
                }
                let held = cells_by_key(t, keys, *p);
                let (cells, heads) = (&held.0, &held.1);
                keyed_values(&heads, cells.iter().map(|held| (!held.is_empty()).then(|| number_bits(i64::from(enclosed_regions(held))))), keys.len() + 1)
            }
            PartStep::Symmetry { keys, p } => {
                if !on_one_frame(t, keys, *p) {
                    return None;
                }
                let held = cells_by_key(t, keys, *p);
                let (cells, heads) = (&held.0, &held.1);
                keyed_values(&heads, cells.iter().map(|held| (!held.is_empty()).then(|| number_bits(i64::from(symmetry_count(held))))), keys.len() + 1)
            }
            PartStep::TouchesEdge { keys, p } => {
                let (grouping, first) = key_ids(t, keys);
                let ids = &grouping.0;
                let mut touching = vec![false; first.len()];
                for (row, id) in t.rows().zip(ids) {
                    touching[*id as usize] |= margins_of(row[usize::from(*p)]).contains(&0);
                }
                keys_only(&first.heads(keys), touching.into_iter(), keys.len())
            }
            PartStep::FillsBox { keys, p } => {
                if !on_one_frame(t, keys, *p) {
                    return None;
                }
                let held = cells_by_key(t, keys, *p);
                let (cells, heads) = (&held.0, &held.1);
                keys_only(&heads, cells.iter().map(|held| {
                    let (rmin, rmax) = (held.iter().map(|x| x.0).min().unwrap_or(0), held.iter().map(|x| x.0).max().unwrap_or(0));
                    let (cmin, cmax) = (held.iter().map(|x| x.1).min().unwrap_or(0), held.iter().map(|x| x.1).max().unwrap_or(0));
                    !held.is_empty() && held.len() == (rmax - rmin + 1) as usize * (cmax - cmin + 1) as usize
                }), keys.len())
            }
            PartStep::Inside { b } => {
                let grid = grid_of(children[1])?;
                // The rows stand as their boxes, and are written where an operator reads a cell.
                crate::boxes::Boxes::of(t, *b, grid, children[1].hash())
            }
            PartStep::Occurs { keys, p, v, turned } => {
                let grid = grid_of(children[1])?;
                let (grouping, first) = key_ids(t, keys);
                let word = hash_words(keys.iter().map(|at| u64::from(*at)).chain([u64::MAX, u64::from(*p), u64::from(*v)]));
                let patterns = occur_patterns(t, &grouping.0, first.len(), (*p, *v), word);
                let plain;
                let turned_moves;
                let moves: Vec<&[Cell]> = if *turned {
                    turned_moves = patterns.distinct.iter().zip(&patterns.hashes).map(|(pattern, hash)| turned_moves_of(pattern, *hash, &grid)).collect::<Vec<_>>();
                    turned_moves.iter().map(|held| held.as_slice()).collect()
                } else {
                    plain = occur_moves(&patterns, &grid, (t.hash(), word, children[1].hash()));
                    plain.iter().map(Vec::as_slice).collect()
                };
                let total: usize = patterns.of_group.iter().map(|which| moves[*which as usize].len()).sum();
                let mut out = Vec::with_capacity(total * (keys.len() + 1));
                for (head, which) in first.iter().zip(&patterns.of_group) {
                    for moved in moves[*which as usize] {
                        push_key(&mut out, head, keys);
                        out.push(*moved);
                    }
                }
                // A pattern's offsets are sorted without repeats, and two keys differ, so no row repeats.
                Val::of_table(Table::new(keys.len() + 1, out))
            }
            PartStep::SetWord { a, b, cells, word } => {
                let other = flat(children[1])?;
                let (own, theirs) = (sorted_values(t, *a), sorted_values(&other, *b));
                // Under `cells`, the first column's cells are those of one frame, and the second's cells that lie in it count toward filling it.
                let fill = if *cells && matches!(word, SetRelation::Disjoint | SetRelation::Complement) {
                    let Some(first) = own.first().map(|cell| margins_of(*cell)) else { return Some(Val::Empty) };
                    let (h, w) = (first[0] + first[1] + 1, first[2] + first[3] + 1);
                    let in_frame = |cell: &Cell| { let m = margins_of(*cell); is_cell(&m) && m[0] + m[1] + 1 == h && m[2] + m[3] + 1 == w };
                    if !own.iter().all(in_frame) {
                        return None;
                    }
                    Some(((h * w) as usize, cells_in_frame(&other, *b, h, w, &theirs, &in_frame)))
                } else {
                    None
                };
                Val::of_table(Table::unit(set_relation(&own, &theirs, fill) == *word))
            }
            PartStep::CountWord { less } => {
                let other = flat(children[1])?;
                Val::of_table(Table::unit(if *less { t.len < other.len } else { t.len == other.len }))
            }
            PartStep::GreatestCount { a, word } => {
                let other = flat(children[1])?;
                let Some(most) = t.rows().map(|row| number_of(row[usize::from(*a)])).max() else { return Some(Val::Empty) };
                Val::of_table(Table::unit((most - other.len as i64).signum() as i8 == *word))
            }
            PartStep::BoxMeasure { b, f, measure } => {
                let (h, w) = frame_of_rows(children[1], *f)?;
                let value = box_features_of(t, *b, h, w).values[*measure as usize];
                let Some(value) = value else { return Some(Val::Empty) };
                if measure.is_number() {
                    Val::of_table(Table::new(1, vec![number_bits(i64::from(value))]))
                } else {
                    Val::of_table(Table::unit(value != 0))
                }
            }
            PartStep::OneBoxCells { b, f } => {
                let (h, w) = frame_of_rows(children[1], *f)?;
                let set = sorted_values(t, *b);
                let [held] = set[..] else { return Some(Val::Empty) };
                let m = margins_of(held);
                let mut out = Vec::new();
                for r in m[0].max(0)..=(h - 1 - m[1]).min(h - 1) {
                    for c in m[2].max(0)..=(w - 1 - m[3]).min(w - 1) {
                        out.push(box_bits(r, h - 1 - r, c, w - 1 - c));
                    }
                }
                Val::of_table(Table::new(1, out))
            }
            PartStep::FrameCells { p } => {
                if !on_one_frame(t, &[], *p) {
                    return None;
                }
                let m = t.rows().next().map(|row| margins_of(row[usize::from(*p)]))?;
                let (h, w) = (m[0] + m[1] + 1, m[2] + m[3] + 1);
                let mut out = Vec::with_capacity((h * w) as usize);
                for r in 0..h {
                    for c in 0..w {
                        out.push(box_bits(r, h - 1 - r, c, w - 1 - c));
                    }
                }
                Val::of_table(Table::new(1, out))
            }
            PartStep::ComplementParts { p } => {
                if !on_one_frame(t, &[], *p) {
                    return None;
                }
                let m = t.rows().next().map(|row| margins_of(row[usize::from(*p)]))?;
                let (h, w) = ((m[0] + m[1] + 1) as usize, (m[2] + m[3] + 1) as usize);
                let mut free = vec![true; h * w];
                for row in t.rows() {
                    let m = margins_of(row[usize::from(*p)]);
                    free[m[0] as usize * w + m[2] as usize] = false;
                }
                let mut count = 0;
                grid_pieces(h, w, &STEPS[..4], |at| free[at], |_| count += 1);
                Val::of_table(Table::new(1, vec![number_bits(count)]))
            }
            PartStep::EveryPartStraight { p } => {
                if !on_one_frame(t, &[], *p) {
                    return None;
                }
                let m = t.rows().next().map(|row| margins_of(row[usize::from(*p)]))?;
                let (h, w) = ((m[0] + m[1] + 1) as usize, (m[2] + m[3] + 1) as usize);
                let mut on = vec![false; h * w];
                for row in t.rows() {
                    let m = margins_of(row[usize::from(*p)]);
                    on[m[0] as usize * w + m[2] as usize] = true;
                }
                let mut straight = true;
                grid_pieces(h, w, &STEPS, |at| on[at], |part| {
                    let places: Vec<(i32, i32)> = part.iter().map(|at| ((at / w) as i32, (at % w) as i32)).collect();
                    let one = |pick: &dyn Fn(&(i32, i32)) -> i32| places.iter().all(|place| pick(place) == pick(&places[0]));
                    straight &= one(&|place| place.0) || one(&|place| place.1) || one(&|place| place.0 - place.1) || one(&|place| place.0 + place.1);
                });
                Val::of_table(Table::unit(straight))
            }
            PartStep::OutlinesBox { p } => {
                if !on_one_frame(t, &[], *p) {
                    return None;
                }
                let cells: Vec<(i32, i32)> = sorted_values(t, *p).iter().map(|cell| { let m = margins_of(*cell); (m[0], m[2]) }).collect();
                let (Some(r0), Some(r1)) = (cells.iter().map(|cell| cell.0).min(), cells.iter().map(|cell| cell.0).max()) else { return Some(Val::Empty) };
                let (c0, c1) = (cells.iter().map(|cell| cell.1).min().unwrap_or(0), cells.iter().map(|cell| cell.1).max().unwrap_or(0));
                let (bh, bw) = ((r1 - r0 + 1) as usize, (c1 - c0 + 1) as usize);
                Val::of_table(Table::unit(bh >= 2 && bw >= 2 && cells.len() == 2 * (bh + bw) - 4 && cells.iter().all(|cell| cell.0 == r0 || cell.0 == r1 || cell.1 == c0 || cell.1 == c1)))
            }
            PartStep::LineSpacings { p } => {
                if !on_one_frame(t, &[], *p) {
                    return None;
                }
                let mut out = Vec::new();
                for (axis, at) in [(e.axes[0], 0), (e.axes[1], 2)] {
                    let mut lines: Vec<i32> = t.rows().map(|row| margins_of(row[usize::from(*p)])[at]).collect();
                    lines.sort_unstable();
                    lines.dedup();
                    if lines.is_empty() {
                        continue;
                    }
                    let mut gaps: Vec<i32> = lines.windows(2).map(|pair| pair[1] - pair[0]).collect();
                    gaps.sort_unstable();
                    gaps.dedup();
                    out.push(axis);
                    out.push(number_bits(gaps.len() as i64));
                }
                Val::of_table(Table::new(2, out))
            }
            PartStep::ColumnMeasure { a, measure } => {
                let values = sorted_values(t, *a);
                if values.is_empty() {
                    return Some(Val::Empty);
                }
                match measure {
                    ColumnMeasureKind::ExtentsDistinct => {
                        let mut extents: Vec<(i32, i32)> = values.iter().map(|cell| { let m = margins_of(*cell); (m[0] + m[1], m[2] + m[3]) }).collect();
                        extents.sort_unstable();
                        extents.dedup();
                        Val::of_table(Table::new(1, vec![number_bits(extents.len() as i64)]))
                    }
                    ColumnMeasureKind::Consecutive | ColumnMeasureKind::Arithmetic => {
                        let mut numbers: Vec<i64> = values.iter().map(|cell| number_of(*cell)).collect();
                        numbers.sort_unstable();
                        if numbers.len() < 2 {
                            Val::Empty
                        } else if *measure == ColumnMeasureKind::Consecutive {
                            Val::of_table(Table::unit(numbers[numbers.len() - 1] - numbers[0] + 1 == numbers.len() as i64))
                        } else if numbers.len() < 3 {
                            Val::Empty
                        } else {
                            let gap = numbers[1] - numbers[0];
                            Val::of_table(Table::unit(numbers.windows(2).all(|pair| pair[1] - pair[0] == gap)))
                        }
                    }
                    ColumnMeasureKind::OnOneAxis | ColumnMeasureKind::OppositePair => {
                        let places: Vec<usize> = values.iter().filter_map(|cell| e.dirs.iter().position(|dir| dir == cell)).collect();
                        if places.len() != values.len() {
                            return Some(Val::Empty);
                        }
                        let holds = if *measure == ColumnMeasureKind::OnOneAxis {
                            const AXIS: [u8; 8] = [0, 0, 1, 1, 2, 3, 3, 2];
                            places.iter().all(|at| AXIS[*at] == AXIS[places[0]])
                        } else {
                            const OPPOSITE: [usize; 8] = [1, 0, 3, 2, 7, 6, 5, 4];
                            places.iter().any(|at| places.contains(&OPPOSITE[*at]))
                        };
                        Val::of_table(Table::unit(holds))
                    }
                    ColumnMeasureKind::OneLength => {
                        let mut lengths: Vec<i32> = values.iter().map(|cell| { let m = margins_of(*cell); m[0].abs().max(m[2].abs()) }).collect();
                        lengths.sort_unstable();
                        lengths.dedup();
                        Val::of_table(Table::unit(lengths.len() == 1))
                    }
                }
            }
            PartStep::CountedByValue { a, second } => {
                let mut numbers: Vec<i64> = t.rows().map(|row| number_of(row[usize::from(*a)])).collect();
                numbers.sort_unstable_by(|x, y| y.cmp(x));
                let Some(chosen) = numbers.get(usize::from(*second)).copied().filter(|chosen| *chosen > 0) else { return Some(Val::Empty) };
                Val::of_table(Table::new(1, (0..chosen).map(number_bits).collect()))
            }
            PartStep::LeastDistance { a, b } => {
                let other = flat(children[1])?;
                let (own, theirs) = (sorted_values(t, *a), sorted_values(&other, *b));
                if own.is_empty() || theirs.is_empty() || !one_frame_of(&own, &theirs) {
                    return Some(Val::Empty);
                }
                Val::of_table(Table::new(1, vec![number_bits(least_gap(&own, &theirs))]))
            }
            PartStep::OnBoundary { b } => {
                let other = flat(children[1])?;
                let (own, theirs) = (sorted_values(t, 0), sorted_values(&other, *b));
                let outside = |m: [i32; 4], step: &(i32, i32)| shifted(m, step.0, step.1).is_none_or(|next| theirs.binary_search(&next).is_err());
                Val::of_table(Table::new(1, own.iter().copied().filter(|cell| theirs.binary_search(cell).is_ok() && STEPS[..4].iter().any(|step| outside(margins_of(*cell), step))).collect()))
            }
            PartStep::NeighborsIn { b } => {
                let other = flat(children[1])?;
                let (own, theirs) = (sorted_values(t, 0), sorted_values(&other, *b));
                let mut out = Vec::new();
                for cell in own.iter() {
                    let m = margins_of(*cell);
                    for (dr, dc) in STEPS {
                        if let Some(next) = shifted(m, dr, dc).filter(|next| theirs.binary_search(next).is_ok()) {
                            out.push(*cell);
                            out.push(next);
                        }
                    }
                }
                // The cells differ, and so do the cells that the eight steps reach from one cell, so no row repeats.
                Val::of_table(Table::new(2, out))
            }
            PartStep::OnBorder { b } => {
                let other = flat(children[1])?;
                let (own, boxes) = (sorted_values(t, 0), sorted_values(&other, *b));
                let spans: Vec<[i32; 4]> = boxes.iter().map(|held| margins_of(*held)).collect();
                Val::of_table(Table::new(1, own.iter().copied().filter(|cell| {
                    let m = margins_of(*cell);
                    spans.iter().any(|span| (0..4).all(|at| m[at] >= span[at]) && (0..4).any(|at| m[at] == span[at]))
                }).collect()))
            }
            PartStep::RayMeets { b } => {
                let other = flat(children[1])?;
                let theirs = sorted_values(&other, *b);
                let mut out = Vec::new();
                for row in t.rows() {
                    let Some(at) = e.dirs.iter().position(|dir| *dir == row[1]) else { continue };
                    let (dr, dc) = STEPS[at];
                    let mut m = margins_of(row[0]);
                    while let Some(next) = moved(m, dr, dc) {
                        if theirs.binary_search(&next).is_ok() {
                            push_row(&mut out, row);
                            break;
                        }
                        m = [m[0] + dr, m[1] - dr, m[2] + dc, m[3] - dc];
                    }
                }
                Val::of_table(Table::new(2, out))
            }
            PartStep::TopColorsUnder { p } => {
                let grid = grid_of(children[1])?;
                let mut counts: BTreeMap<Cell, u32> = BTreeMap::new();
                for cell in sorted_values(t, *p).iter() {
                    if let Some(color) = grid.color_of(*cell) {
                        *counts.entry(color).or_insert(0) += 1;
                    }
                }
                let top = counts.values().copied().max().unwrap_or(0);
                Val::of_table(Table::new(1, counts.into_iter().filter(|held| held.1 == top).map(|held| held.0).collect()))
            }
            PartStep::GroupsWord { p, left, q, right, shapes, word } => {
                let other = flat(children[1])?;
                if left.is_empty() || right.is_empty() || t.len == 0 || other.len == 0 {
                    return Some(Val::Empty);
                }
                let sets = |table: &Table, keys: &[u16], cell: u16| -> Option<Vec<u128>> {
                    let mut out: Vec<u128> = if *shapes {
                        if !on_one_frame(table, keys, cell) {
                            return None;
                        }
                        let held = cells_by_key(table, keys, cell);
                        held.0.iter().filter(|cells| !cells.is_empty()).map(|cells| u128::from(shape_hash(cells, false))).collect()
                    } else {
                        // A set of cells is a set of values, whatever frame each cell is in.
                        let grouping = key_grouping(table, keys);
                        // The distinct cells of each group stand together in ascending order.
                        let pairs = group_cells(table, &grouping.0, grouping.1.len(), cell);
                        pairs.chunk_by(|a, b| a >> 32 == b >> 32).map(|group| hash_words(group.iter().map(|pair| u64::from(*pair as u32)))).collect()
                    };
                    out.sort_unstable();
                    out.dedup();
                    (!out.is_empty()).then_some(out)
                };
                let (Some(own), Some(theirs)) = (sets(t, left, *p), sets(&other, right, *q)) else { return None };
                Val::of_table(Table::unit(set_relation(&own, &theirs, None) == *word))
            }
            PartStep::AgreeWord { p, x, q, y, word } => {
                let other = flat(children[1])?;
                let colors = |table: &Table, cell: u16, color: u16| -> Arc<BTreeMap<Cell, Vec<Cell>>> { colors_by_cell(table, cell, color) };
                let (mine, theirs) = (colors(t, *p, *x), colors(&other, *q, *y));
                let (mut same, mut differ) = (false, false);
                for (cell, held) in mine.iter() {
                    if let Some(there) = theirs.get(cell) {
                        if held == there {
                            same = true;
                        } else {
                            differ = true;
                        }
                    }
                }
                let found = match (same, differ) {
                    (false, false) => return Some(Val::Empty),
                    (true, false) => AgreeRelation::EveryOne,
                    (false, true) => AgreeRelation::None,
                    (true, true) => AgreeRelation::Some,
                };
                Val::of_table(Table::unit(found == *word))
            }
            PartStep::SameValues { a, b } => {
                let other = flat(children[1])?;
                Val::of_table(Table::unit(t.len > 0 && t.sorted_column(usize::from(*a)) == other.sorted_column(usize::from(*b))))
            }
            PartStep::InsideBoxes { a, b } | PartStep::BoxesHolding { a, b } => {
                let other = flat(children[1])?;
                if other.sorted_column(usize::from(*b)).len() * t.len > 4_000_000 {
                    crate::bounds::mark(crate::bounds::Bound::BoxesGuard);
                    return None;
                }
                let inside = matches!(self, PartStep::InsideBoxes { .. });
                let others = box_front(&other, *b, inside);
                let mut out = Vec::new();
                for row in t.rows() {
                    let own = margins_of(row[usize::from(*a)]);
                    let met = others.iter().any(|held| (0..4).all(|at| if inside { own[at] >= held[at] } else { held[at] >= own[at] }));
                    if met {
                        push_row(&mut out, row);
                    }
                }
                Val::of_table(Table::new(t.arity, out))
            }
            PartStep::SameShape { keys, a, others, b, turned } => {
                let other = flat(children[1])?;
                if !on_one_frame(t, keys, *a) || !on_one_frame(&other, others, *b) {
                    return None;
                }
                let shape = |held: &[(u8, u8)]| shape_hash(held, *turned);
                let held = cells_by_key(t, keys, *a);
                let (cells, heads) = (&held.0, &held.1);
                let other_held = cells_by_key(&other, others, *b);
                let other_cells = &other_held.0;
                let seen: LookupSet<u32> = other_cells.iter().filter(|held| !held.is_empty()).map(shape).collect();
                keys_only(&heads, cells.iter().map(|held| !held.is_empty() && seen.contains(&shape(held))), keys.len())
            }
            PartStep::DeterminesJointly { p, v, w } => {
                let (_, output) = grids_of(children[1])?;
                let mut both: FastMap<(Cell, Cell), (Cell, bool)> = FastMap::default();
                let mut first: FastMap<Cell, (Cell, bool)> = FastMap::default();
                let mut second: FastMap<Cell, (Cell, bool)> = FastMap::default();
                for row in t.rows() {
                    let Some(color) = output.color_of(row[usize::from(*p)]) else { continue };
                    let color = &color;
                    let (one, other) = (row[usize::from(*v)], row[usize::from(*w)]);
                    let held = both.entry((one, other)).or_insert((*color, false));
                    held.1 |= held.0 != *color;
                    let held = first.entry(one).or_insert((*color, false));
                    held.1 |= held.0 != *color;
                    let held = second.entry(other).or_insert((*color, false));
                    held.1 |= held.0 != *color;
                }
                Val::of_table(Table::unit(first.any(|_, held| held.1) && second.any(|_, held| held.1) && !both.any(|_, held| held.1)))
            }
            PartStep::SharedLine { a, b } => {
                let other = flat(children[1])?;
                // `same_line`: the two cells have one margin on an edge of the other axis.
                let margins = margin_sets(&other, *b);
                let mut out = Vec::new();
                for row in t.rows() {
                    let m = margins_of(row[usize::from(*a)]);
                    if (0..4).any(|at| margins[at].binary_search(&m[at]).is_ok()) {
                        push_row(&mut out, row);
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
                    if grid.color_of(cell).is_some() {
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
            PartStep::BoxMargin { b } => rows_with(t, 2, 4, |row, out| {
                let m = margins_of(row[usize::from(*b)]);
                for at in 0..4 {
                    push_row(out, row);
                    out.push(e.dirs[at]);
                    out.push(number_bits(i64::from(m[at])));
                }
            }),
            PartStep::BoxExtent { b } => {
                let grid = grid_of(children[1])?;
                rows_with(t, 2, 2, |row, out| {
                    let m = margins_of(row[usize::from(*b)]);
                    let (along, across) = (grid.h - m[0] - m[1], grid.w - m[2] - m[3]);
                    if along > 0 && across > 0 {
                        push_row(out, row);
                        out.push(e.axes[0]);
                        out.push(number_bits(i64::from(along)));
                        push_row(out, row);
                        out.push(e.axes[1]);
                        out.push(number_bits(i64::from(across)));
                    }
                })
            }
            PartStep::Displacement { a, b } => rows_with(t, 1, 1, |row, out| {
                let (from, to) = (margins_of(row[usize::from(*a)]), margins_of(row[usize::from(*b)]));
                if from[0] + from[1] == to[0] + to[1] && from[2] + from[3] == to[2] + to[3] {
                    push_row(out, row);
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
                let (grouping, first) = key_ids(t, keys);
                let ids = &grouping.0;
                let mut spans: Vec<Option<[i32; 4]>> = vec![None; first.len()];
                let mut frames: Vec<(i32, i32)> = vec![(0, 0); first.len()];
                for (row, id) in t.rows().zip(ids) {
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
                            push_key(&mut out, first.get(at), keys);
                            out.push(e.axes[axis]);
                            out.push(number_bits(i64::from(long)));
                        }
                    } else {
                        let (h, w) = frames[at];
                        for (edge, margin) in [*r0, h - 1 - r1, *c0, w - 1 - c1].into_iter().enumerate() {
                            push_key(&mut out, first.get(at), keys);
                            out.push(e.dirs[edge]);
                            out.push(number_bits(i64::from(margin)));
                        }
                    }
                }
                // A key has each of its rows once, and two keys differ, so no row repeats.
                Val::of_table(Table::new(keys.len() + 2, out))
            }
            PartStep::LineCounts { keys, p } => {
                if !on_one_frame(t, keys, *p) {
                    return None;
                }
                let (grouping, first) = key_ids(t, keys);
                let mut out = Vec::new();
                lines_of(t, &grouping.0, first.len(), *p, |id, is_row, near, far, count, _| {
                    push_key(&mut out, first.get(id as usize), keys);
                    out.push(e.axes[usize::from(!is_row)]);
                    out.push(if is_row { box_bits(near, far, 0, 0) } else { box_bits(0, 0, near, far) });
                    out.push(number_bits(i64::from(count)));
                });
                // A group has each of its lines once, and two groups differ in their keys, so no row repeats.
                Val::of_table(Table::new(keys.len() + 3, out))
            }
            PartStep::Complement { p } => {
                if !on_one_frame(t, &[], *p) {
                    return None;
                }
                let first = t.rows().next().map(|row| margins_of(row[usize::from(*p)]))?;
                let (h, w) = (first[0] + first[1] + 1, first[2] + first[3] + 1);
                if h * w > 4096 {
                    crate::bounds::mark(crate::bounds::Bound::ComplementArea);
                    return None;
                }
                let held = t.sorted_column(usize::from(*p));
                let mut out = Vec::new();
                for r in 0..h {
                    for c in 0..w {
                        let cell = box_bits(r, h - 1 - r, c, w - 1 - c);
                        if held.binary_search(&cell).is_err() {
                            out.push(cell);
                        }
                    }
                }
                Val::of_table(Table::distinct(1, out))
            }
            PartStep::StraightAxis { keys, p } => {
                if !on_one_frame(t, keys, *p) {
                    return None;
                }
                let held = cells_by_key(t, keys, *p);
                let (cells, heads) = (&held.0, &held.1);
                let mut out = Vec::new();
                for (own, head) in cells.iter().zip(heads) {
                    let Some(first) = own.first() else { continue };
                    if own.iter().all(|at| at.1 == first.1) {
                        out.extend_from_slice(head);
                        out.push(e.axes[0]);
                    }
                    if own.iter().all(|at| at.0 == first.0) {
                        out.extend_from_slice(head);
                        out.push(e.axes[1]);
                    }
                }
                // A key has each axis once, and two keys differ, so no row repeats.
                Val::of_table(Table::new(keys.len() + 1, out))
            }
            PartStep::CellCount { keys, p } => {
                if !on_one_frame(t, keys, *p) {
                    return None;
                }
                let held = cells_by_key(t, keys, *p);
                let (cells, heads) = (&held.0, &held.1);
                keyed_values(&heads, cells.iter().map(|held| (!held.is_empty()).then(|| number_bits(held.len() as i64))), keys.len() + 1)
            }
            PartStep::GroupGap { keys, p } => {
                if !on_one_frame(t, &[], *p) {
                    return None;
                }
                let m = t.rows().next().map(|row| margins_of(row[usize::from(*p)]))?;
                let (h, w) = ((m[0] + m[1] + 1) as usize, (m[2] + m[3] + 1) as usize);
                let held = cells_by_key(t, keys, *p);
                let (cells, heads) = (&held.0, &held.1);
                let mut held = vec![false; h * w];
                for own in cells {
                    for (r, c) in own {
                        held[usize::from(*r) * w + usize::from(*c)] = true;
                    }
                }
                keyed_values(&heads, cells.iter().map(|own| nearest_other(own, &held, h, w).map(number_bits)), keys.len() + 1)
            }
            PartStep::BoxCells { p, outside } => {
                if !on_one_frame(t, &[], *p) {
                    return None;
                }
                let m = t.rows().next().map(|row| margins_of(row[usize::from(*p)]))?;
                let (h, w) = (m[0] + m[1] + 1, m[2] + m[3] + 1);
                let (mut r0, mut r1, mut c0, mut c1) = (i32::MAX, i32::MIN, i32::MAX, i32::MIN);
                for row in t.rows() {
                    let m = margins_of(row[usize::from(*p)]);
                    (r0, r1, c0, c1) = (r0.min(m[0]), r1.max(m[0]), c0.min(m[2]), c1.max(m[2]));
                }
                let mut out = Vec::new();
                for r in 0..h {
                    for c in 0..w {
                        if (r >= r0 && r <= r1 && c >= c0 && c <= c1) != *outside {
                            out.push(box_bits(r, h - 1 - r, c, w - 1 - c));
                        }
                    }
                }
                Val::of_table(Table::distinct(1, out))
            }
            PartStep::HoleCells { p } => {
                if !on_one_frame(t, &[], *p) {
                    return None;
                }
                let m = t.rows().next().map(|row| margins_of(row[usize::from(*p)]))?;
                let (h, w) = ((m[0] + m[1] + 1) as usize, (m[2] + m[3] + 1) as usize);
                let mut seen = vec![false; h * w];
                for row in t.rows() {
                    let m = margins_of(row[usize::from(*p)]);
                    seen[m[0] as usize * w + m[2] as usize] = true;
                }
                let held = seen.clone();
                let mut stack: Vec<usize> = (0..h * w).filter(|at| !seen[*at] && (at / w == 0 || at / w == h - 1 || at % w == 0 || at % w == w - 1)).collect();
                for at in &stack {
                    seen[*at] = true;
                }
                while let Some(at) = stack.pop() {
                    let (r, c) = (at / w, at % w);
                    for (near, inside) in [(at.wrapping_sub(w), r > 0), (at + w, r + 1 < h), (at.wrapping_sub(1), c > 0), (at + 1, c + 1 < w)] {
                        if inside && !seen[near] {
                            seen[near] = true;
                            stack.push(near);
                        }
                    }
                }
                let out: Vec<Cell> = (0..h * w).filter(|at| !seen[*at] && !held[*at]).map(|at| box_bits((at / w) as i32, (h - 1 - at / w) as i32, (at % w) as i32, (w - 1 - at % w) as i32)).collect();
                Val::of_table(Table::distinct(1, out))
            }
            PartStep::Product { keys } => {
                let factors = t.factors(|| finest_split(t));
                let (group_of, rows_of) = (&factors.0, &factors.1);
                // A split holds where each group of the finest split lies wholly on one side of it, and each side then has the product of its groups' row counts.
                let mut side_of: Vec<Option<bool>> = vec![None; rows_of.len()];
                let mut counts = [1u128, 1u128];
                let mut whole = true;
                for (at, group) in group_of.iter().enumerate() {
                    let in_keys = keys.contains(&(at as u16));
                    match side_of[usize::from(*group)] {
                        Some(side) if side != in_keys => {
                            whole = false;
                            break;
                        }
                        Some(_) => {}
                        None => {
                            side_of[usize::from(*group)] = Some(in_keys);
                            counts[usize::from(!in_keys)] *= u128::from(rows_of[usize::from(*group)]);
                        }
                    }
                }
                Val::of_table(Table::unit(whole && counts[0] >= 2 && counts[1] >= 2))
            }
            PartStep::SameRows { left, right, key } => {
                let other = flat(children[1])?;
                let rows = |table: &Table, places: &[u16]| table.rows().map(|row| places.iter().map(|at| row[usize::from(*at)]).collect::<Vec<Cell>>()).collect::<LookupSet<_>>();
                let own = rows(t, left);
                Val::of_table(Table::unit(t.len > 0 && (!key || own.len() == t.len) && own == rows(&other, right)))
            }
            PartStep::Straight { keys, p } => {
                if !on_one_frame(t, keys, *p) {
                    return None;
                }
                let held = cells_by_key(t, keys, *p);
                let (cells, heads) = (&held.0, &held.1);
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
                let (grouping, first) = key_ids(t, keys);
                let mut out = Vec::new();
                lines_of(t, &grouping.0, first.len(), *p, |id, is_row, near, far, count, (rows_long, columns_long)| {
                    if count as i32 == if is_row { columns_long } else { rows_long } {
                        push_key(&mut out, first.get(id as usize), keys);
                        out.push(e.axes[usize::from(!is_row)]);
                        out.push(if is_row { box_bits(near, far, 0, 0) } else { box_bits(0, 0, near, far) });
                    }
                });
                // A group has each of its lines once, and two groups differ in their keys, so no row repeats.
                Val::of_table(Table::new(keys.len() + 2, out))
            }
            PartStep::BoxRead { b, kept } => {
                let (input, output) = grids_of(children[1])?;
                let mut out = Vec::new();
                for held in t.sorted_column(usize::from(*b)).iter().copied() {
                    let m = margins_of(held);
                    // Only a box of the output's extents stands for the output.
                    if input.h - m[0] - m[1] != output.h || input.w - m[2] - m[3] != output.w {
                        continue;
                    }
                    // The output cells whose input cell lies in the grid.
                    let (r_first, r_last) = ((-m[0]).max(0), (input.h - m[0]).min(output.h));
                    let (c_first, c_last) = ((-m[2]).max(0), (input.w - m[2]).min(output.w));
                    for r in r_first..r_last {
                        for c in c_first..c_last {
                            let (y, z) = (r + m[0], c + m[2]);
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
                    let (Some(from), Some(to)) = (input.color_of(at_in), output.color_of(at_out)) else { continue };
                    if (from == to) == *kept {
                        out.extend_from_slice(&[held, cell, other, from]);
                        if !*kept {
                            out.push(to);
                        }
                    }
                }
                let width = if *kept { 4 } else { 5 };
                // Where the two columns are all the columns, two rows differ in them, and so do their rows here.
                if are_all_columns(t.arity, [*b, *x]) {
                    Val::of_table(Table::new(width, out))
                } else {
                    Val::of_table(Table::distinct(width, out))
                }
            }
        })
    }
}
