//! The summary of a table at each assignment, for the export that groups a
//! table's entries by assignment ([`crate::columns::step_case_columns_by_assignment_in`]).
//!
//! At one assignment a table holds a Set of TableRows: the TableRows of its constraint
//! models on every example, equal TableRows once. The summary gives, for each
//! assignment of a table:
//!
//! - the value hash of each `DET` of the assignment ([`value_hash_of`]): the
//!   hash of the `DET`'s value, a TableRows of the `DET`'s Type;
//! - the TableHash of the table's Set of TableRows;
//! - the key of each example: the count of its distinct TableRows, the most rows
//!   of one of them and the hash of its Set of TableRows;
//! - the TableVector: the features of `arclog-features` on the Set of TableRows;
//! - the key of each column: its type name, its value hash and its tie, which
//!   order the columns by content ([`ColumnKey`]).
//!
//! The summary reads the rows in the table, so a table that the export writes
//! as Count entries (more rows than the projection cap) still has a hash.
//!
//! The TableHash has one definition, over the entries of one table at one
//! assignment:
//!
//! 1. Each row is encoded as export cells ([`sorted_rows`]). An Ident cell is
//!    the first 32 bits of its member digest.
//! 2. For each column of a type that another column has, hash the type and
//!    the set of its cell runs on each example. A column of a type that no other
//!    column has cannot tie, and its hash is 0.
//! 3. Sort the columns by type name and that hash. Columns equal in both form
//!    a tied group.
//! 4. Where no column is tied, hash each example's Set of TableRows with the
//!    columns in that order: that is the body hash. Where columns are tied, the
//!    body hash is the least over the orders that a search of the table's
//!    content reaches, individualization-refinement as the module
//!    `column_order` defines it. A table whose search passes
//!    [`SEARCH_WORK_CAP`] has no TableHash, and its reason is
//!    [`COLUMN_SEARCH_BOUND`].
//! 5. The TableHash is the hash of the sorted type names and the body hash.
//!
//! A type name in the TableHash is the name that the export writes
//! ([`type_names`]), which holds no Ident source ([`hashed_names`]). So two
//! tables are equal where their Types and their TableRows are equal, whichever
//! forms make their Idents. A Pose type is the exception:
//! the name that the export writes holds the slots of its `RIGID_DET` and of the
//! `DET`s that the form reads, which differ between programs of one query, so
//! its name in the TableHash names the assembly by the QueryHash of its
//! `RIGID_DET` ([`pose_name`]).
//!
//! The value hash of a TableRows has its columns in their order. The readers
//! of a `DET` read its columns by position, so two values that differ only by
//! an order of the columns that tie (rows `(a, b)` and `(b, a)` of two `Color`
//! columns) are different values to them, and their value hashes differ.
//! The positions of a relation's columns are part of its resolved content,
//! which the QueryHash hashes, so the value hash holds no name that a
//! relabelling of the program changes. The value hash of a TableRows is not its
//! TableHash.

use std::cell::RefCell;
use std::hash::Hasher;
use std::rc::Rc;
use std::sync::{Arc, Mutex};

use arclog::eval::determinations::relation_spelled;
use arclog::eval::join::Materializer;
use arclog::eval::{Gauge, ReachedBound, RelationValue};
use arclog::hash::{StableHash, StableHashMap, StableHasher};
use arclog::judge::determination::Assignment;
use arclog::read::spelling::{spelling, FACT_RELATIONS};
use arclog::relations::Relation;
use arclog::session::SessionAllocation;
use arclog::task::{Grid, Task};
use arclog::program::RigidDetName;
use arclog::types::{AssemblyId, ValueType};
use arclog_features::{Grid as FeatureGrid, Input, Pair, TableRows};

mod column_hash;
mod column_order;
use column_hash::Cells;
pub use column_hash::{ColumnKey, TIE_EXCHANGEABLE, TIE_NONE, TIE_OPEN};
pub use column_order::SEARCH_WORK_CAP;

use crate::columns::{row_width, sorted_rows, sorted_rows_at, type_names};
use crate::shape_rows::{ShapeExample, ShapeModel, ShapeRows, SharedShapeRows};
use crate::split::{self, Part};
use crate::tables::{example_axis, Contents, Point, Table, TableDet, TableRelation};

/// The reason of an assignment with no TableHash because the search for the order of its tied columns passed [`SEARCH_WORK_CAP`].
pub const COLUMN_SEARCH_BOUND: &str = "ColumnSearch";

/// An example at one assignment of a table.
#[derive(Clone, Debug)]
pub struct ExampleKey {
    /// 0 for the task, 1 for a train example, 2 for a test example.
    pub kind: u8,
    pub index: u32,
    /// The count of the example's distinct TableRows, one for each constraint
    /// model that gives rows.
    pub distinct: u32,
    /// The most rows of one of those TableRows.
    pub rows: u64,
    /// The low 64 bits of the hash of the example's Set of TableRows.
    pub hash: u64,
}

/// A table at one of its assignments.
#[derive(Clone, Debug)]
pub struct AssignmentSummary {
    /// Each `DET` of the assignment as its relation spells it, with its value
    /// hash, sorted by the spelling.
    pub dets: Vec<(String, StableHash)>,
    /// The other assignments of the full `DET`s that this assignment stands for, each as the value hashes of the `DET`s, in the order of `dets`, empty where
    /// every `DET` is read with all its columns. See [`DetFulls`].
    pub more: Vec<Vec<StableHash>>,
    /// The TableHash, none where the table has no hash for a `reason`. An Undefined model gives no TableRows to the Set. A Stopped model, or an example that
    /// the walk stopped before this assignment, at a bound that [`ReachedBound::is_stored`] holds, is a failed example: the TableHash then also hashes the
    /// kind, index and bound name of each failed example, and a TableHash without one is as it was.
    pub hash: Option<StableHash>,
    /// Why there is no TableHash, empty where there is one: the variant name of the machine-dependent bound that stopped an example (as [`bound_name`]
    /// gives it), `RunFault` where an example has no entry because it faulted, `NoEntry` where an example has no entry at the assignment, `NoExamples`
    /// where the table has no example, `TableFault` where the table has no contents, `ColumnSearch` ([`COLUMN_SEARCH_BOUND`]) where the search for the order of
    /// its tied columns passed its cap, or the bound that stopped the summary itself.
    pub reason: String,
    /// One for each example of the table. Shared, so a summary that the cache gives again copies none of it.
    pub examples: Arc<Vec<ExampleKey>>,
    /// For each example, for each constraint model in the order the table holds
    /// them: the count of rows and the value hash of its TableRows
    /// ([`value_hash_of`]), or none where the model gives no rows (Undefined or
    /// Stopped). Equal TableRows have equal hashes.
    pub models: Arc<Vec<Vec<Option<(u64, u128)>>>>,
    /// The TableVector: a value for each of `arclog_features::FEATURES`.
    pub features: Arc<Vec<f32>>,
    /// The rows of the table at this assignment, sharing the engine's rows, for the reader that walks the table's shapes. None where the summary
    /// holds none: a summary of [`summarize_hashes_cached`], or a table with no TableHash.
    pub shape_rows: SharedShapeRows,
    /// The key of each column of the table, in the order of the table's columns: its type name, its value hash and its tie ([`ColumnKey`]).
    /// Empty where the assignment has no TableHash, or the summary is not a full one.
    pub columns: Arc<Vec<ColumnKey>>,
}

/// A table at each of its assignments, in the order of the walk, and at least
/// one.
#[derive(Clone, Debug)]
pub struct TableSummary {
    pub assignments: Vec<AssignmentSummary>,
    /// Whether the walk of some example stopped at the assignment cap.
    pub capped: bool,
    /// The table's Name: the output Name of a table of an instance or of a
    /// `RIGID_DET` form ([`crate::tables::output_name`]), the fact relation's
    /// name of an evidence table and the empty string for any other table. A
    /// `RIGID_DET` form's part is named by its position in the form's
    /// canonical form, `slot 0`, `slot 1` and so on, and not by the relation
    /// it reads, so the Name holds no name of the program.
    pub name: String,
    /// Whether the summary is of [`summarize_hashes_cached`]: each assignment
    /// holds the TableHash and the reason that it has none, and its `dets`,
    /// `more`, `examples`, `models` and `features` are empty.
    pub hashes_only: bool,
}

impl TableSummary {
    /// The summary of `table` with no hash for `reason`, which holds as many assignments as
    /// the table's examples walk.
    pub fn unhashed(table: &Table, reason: &str) -> Self {
        let Ok(contents) = &table.contents else { return TableSummary::faulted() };
        let assignments = (0..assignment_count(contents)).map(|_| AssignmentSummary { dets: Vec::new(), more: Vec::new(), hash: None, reason: reason.to_owned(), examples: Arc::default(), models: Arc::default(), features: Arc::default(), shape_rows: None, columns: Arc::default() }).collect();
        TableSummary { assignments, capped: capped(contents), name: name_of(contents), hashes_only: false }
    }

    fn faulted() -> Self {
        TableSummary { assignments: vec![AssignmentSummary { dets: Vec::new(), more: Vec::new(), hash: None, reason: "TableFault".to_owned(), examples: Arc::default(), models: Arc::default(), features: Arc::default(), shape_rows: None, columns: Arc::default() }], capped: false, name: String::new(), hashes_only: false }
    }

    /// The summary of a table that [`summarize_hashes_cached`] leaves out: one
    /// assignment with no TableHash, for the reason `NotComputed`.
    fn not_computed(contents: &Contents) -> Self {
        let held = AssignmentSummary { dets: Vec::new(), more: Vec::new(), hash: None, reason: "NotComputed".to_owned(), examples: Arc::default(), models: Arc::default(), features: Arc::default(), shape_rows: None, columns: Arc::default() };
        TableSummary { assignments: vec![held], capped: capped(contents), name: name_of(contents), hashes_only: true }
    }
}

/// The variant name of `bound`, which stands for it in a TableHash and in the reason of a missing one.
pub fn bound_name(bound: ReachedBound) -> &'static str {
    match bound {
        ReachedBound::Bindings { .. } => "Bindings",
        ReachedBound::Rows { .. } => "Rows",
        ReachedBound::Models { .. } => "Models",
        ReachedBound::Nodes { .. } => "Nodes",
        ReachedBound::Assignments { .. } => "Assignments",
        ReachedBound::TableWork { .. } => "TableWork",
        ReachedBound::Margin(_) => "Margin",
        ReachedBound::RequestWork { .. } => "RequestWork",
        ReachedBound::RequestBytes { .. } => "RequestBytes",
        ReachedBound::AssignmentBytes { .. } => "AssignmentBytes",
        ReachedBound::Cancelled => "Cancelled",
        ReachedBound::NoValues => "NoValues",
        ReachedBound::Effort { .. } => "Effort",
    }
}

fn assignment_count(contents: &Contents) -> usize {
    contents.examples.iter().map(|example| example.rows.as_ref().map_or(0, |rows| rows.at.len())).max().unwrap_or(0).max(1)
}

fn capped(contents: &Contents) -> bool {
    contents.examples.iter().any(|example| example.rows.as_ref().is_ok_and(|rows| rows.stop.as_ref().is_some_and(|stop| matches!(stop.bound, ReachedBound::Assignments { .. }))))
}

fn name_of(contents: &Contents) -> String {
    match contents.relation {
        TableRelation::Fact(fact) => spelling(FACT_RELATIONS, &fact).to_owned(),
        TableRelation::Slot(_) => contents.output_name.clone(),
    }
}

/// The train pairs of `task` as the features read them.
pub fn train_pairs(task: &Task) -> Vec<Pair> {
    let grid = |grid: &Grid| {
        let rows = grid.rows();
        FeatureGrid { height: rows.len(), width: rows.first().map_or(0, |row| row.len()), cells: rows.iter().flat_map(|row| row.iter().map(|color| color.digit())).collect() }
    };
    task.train.iter().map(|pair| Pair::new(grid(&pair.input), grid(&pair.output))).collect()
}

/// The summary of `table` at each of its assignments, on a task with the train
/// pairs `train`. The assignments are those of the in-memory table: example
/// number `at` of each example is one assignment, as every example walks the
/// same assignments.
pub fn summarize(materializer: &Materializer<'_>, table: &Table, train: &[Pair], fulls: &DetFulls<'_>) -> Result<TableSummary, ReachedBound> {
    let Ok(contents) = &table.contents else { return Ok(TableSummary::faulted()) };
    let mut summary = summarize_rows(materializer, contents, train, fulls)?;
    spell_dets(contents, &mut summary);
    Ok(summary)
}

/// The most tables whose summaries a [`SummaryCache`] holds in one of its two
/// generations.
pub const SUMMARY_CACHE_ENTRIES: usize = 4096;

/// The most assignments, over all the summaries of one generation of a
/// [`SummaryCache`]: a summary holds the TableVector and the keys of each of its
/// assignments, so the count bounds the generation's size.
const SUMMARY_CACHE_ASSIGNMENTS: usize = 1 << 17;

/// The most cells of the relations of [`ShapeRows`], over all the summaries of one generation of a [`SummaryCache`]: the relations share the engine's rows, and this keeps the rows of a generation near 4 bytes for each cell, 256 MiB, with the cache holding them past their session.
const SUMMARY_CACHE_SHAPE_CELLS: usize = 1 << 26;

/// The key of a table's summary in a [`SummaryCache`]: the hash of the
/// QueryHash of the table's query and of the `DET`s of its assignments in their
/// order ([`crate::columns`]), and the table's place among the tables of its
/// query.
pub type SummaryKey = (StableHash, u32);

/// The key of the summary of the evidence table at place `at`. An evidence table
/// has no query, and its summary is the same in every call of a session.
pub fn evidence_key(at: usize) -> SummaryKey {
    let mut hasher = StableHasher::new();
    hasher.write(b"arclog.summary.evidence");
    hasher.write_u64(at as u64);
    (hasher.finish128(), 0)
}

/// The summaries of the tables of one session, by [`SummaryKey`]. A query's
/// QueryHash fixes the content of its tables within a task, and the order of
/// its `DET`s fixes the place of each `DET`'s value in the summary, so a summary
/// holds for every later table of that query with its `DET`s in that order. A summary does not depend on whether
/// the export packs rows. A summary of [`summarize_hashes_cached`] is flagged, and serves no export that gives full summaries. The cache keeps two generations, each with at most
/// [`SUMMARY_CACHE_ENTRIES`] summaries and a bounded count of assignments:
/// when the young generation is full it becomes the old one and the old one is
/// dropped, and a summary found in the old generation moves to the young one.
/// So a full cache keeps the summaries that the last calls used, and drops none
/// of them at once. A summary owns its data alone: hashes, counts and
/// features, and no allocation of the session.
#[derive(Default)]
pub struct SummaryCache {
    held: Mutex<Generations>,
}

#[derive(Default)]
struct Generations {
    young: StableHashMap<SummaryKey, Arc<TableSummary>>,
    /// The assignments of the summaries in `young`.
    assignments: usize,
    /// The cells of the shape rows of the summaries in `young`.
    cells: usize,
    old: StableHashMap<SummaryKey, Arc<TableSummary>>,
}

impl SummaryCache {
    fn get(&self, key: &SummaryKey) -> Option<Arc<TableSummary>> {
        let mut held = self.held.lock().expect("the summaries are not poisoned");
        if let Some(found) = held.young.get(key) {
            return Some(Arc::clone(found));
        }
        let found = held.old.remove(key)?;
        held.insert(*key, Arc::clone(&found));
        Some(found)
    }

    fn put(&self, key: SummaryKey, summary: Arc<TableSummary>) {
        self.held.lock().expect("the summaries are not poisoned").insert(key, summary);
    }
}

/// The cells of the shape rows that the assignments of `summary` hold.
fn shape_cells(summary: &TableSummary) -> usize {
    summary.assignments.iter().filter_map(|at| at.shape_rows.as_ref()).map(|rows| rows.cells()).sum()
}

impl Generations {
    fn insert(&mut self, key: SummaryKey, summary: Arc<TableSummary>) {
        let size = summary.assignments.len();
        let cells = shape_cells(&summary);
        if !self.young.contains_key(&key) && (self.young.len() >= SUMMARY_CACHE_ENTRIES || self.assignments.saturating_add(size) > SUMMARY_CACHE_ASSIGNMENTS || self.cells.saturating_add(cells) > SUMMARY_CACHE_SHAPE_CELLS) {
            self.old = std::mem::take(&mut self.young);
            self.assignments = 0;
            self.cells = 0;
        }
        self.assignments += size;
        self.cells += cells;
        if let Some(replaced) = self.young.insert(key, summary) {
            self.assignments = self.assignments.saturating_sub(replaced.assignments.len());
            self.cells = self.cells.saturating_sub(shape_cells(&replaced));
        }
    }
}

/// [`summarize`], through `cache` where `key` is given. A summary from the
/// cache equals the one that [`summarize`] gives, as the spelling of the `DET`s,
/// the table's name and whether it is capped are read from `table` again.
pub fn summarize_cached(materializer: &Materializer<'_>, table: &Table, train: &[Pair], fulls: &DetFulls<'_>, cache: &SummaryCache, key: Option<SummaryKey>) -> Result<TableSummary, ReachedBound> {
    let (Ok(contents), Some(key)) = (&table.contents, key) else { return summarize(materializer, table, train, fulls) };
    {
        let _timed = split::span(Part::SummaryHit);
        if let Some(held) = cache.get(&key) {
            let fits = !held.hashes_only && held.assignments.len() == assignment_count(contents) && held.assignments.iter().enumerate().all(|(at, held)| held.dets.len() == det_count(contents, at));
            if fits {
                let mut summary = TableSummary::clone(&held);
                summary.capped = capped(contents);
                summary.name = name_of(contents);
                spell_dets(contents, &mut summary);
                return Ok(summary);
            }
        }
    }
    let _timed = split::span(Part::SummaryMiss);
    let mut summary = summarize_rows(materializer, contents, train, fulls)?;
    // The cached summary holds the value hashes of the `DET`s in the order of `contents.dets`, with no spelling.
    cache.put(key, Arc::new(summary.clone()));
    spell_dets(contents, &mut summary);
    Ok(summary)
}

/// The summary of `contents` with the `DET`s of each assignment in the order of `contents.dets`, unspelled.
/// The summary of the table that `contents` holds at each of its assignments,
/// as a reader of many tables of one body takes it: the `DET`s of an assignment,
/// which the tables share, stand out of it.
pub fn summarize_body(materializer: &Materializer<'_>, contents: &Contents, train: &[Pair], fulls: &DetFulls<'_>) -> Result<TableSummary, ReachedBound> {
    let types: Vec<ValueType> = contents.columns.iter().map(|column| column.ty.clone()).collect();
    let bodies = DetFulls::none().with_assemblies(fulls.assemblies.clone());
    let assignments = (0..assignment_count(contents)).map(|at| alone(materializer, |own| at_assignment_with(own, contents, &types, at, train, &bodies, false, false))).collect::<Result<_, _>>()?;
    Ok(TableSummary { assignments, capped: capped(contents), name: name_of(contents), hashes_only: false })
}

fn summarize_rows(materializer: &Materializer<'_>, contents: &Contents, train: &[Pair], fulls: &DetFulls<'_>) -> Result<TableSummary, ReachedBound> {
    let types: Vec<ValueType> = contents.columns.iter().map(|column| column.ty.clone()).collect();
    let assignments = (0..assignment_count(contents)).map(|at| alone(materializer, |own| at_assignment(own, contents, &types, at, train, fulls))).collect::<Result<_, _>>()?;
    Ok(TableSummary { assignments, capped: capped(contents), name: name_of(contents), hashes_only: false })
}

/// The summary of `contents` at each of its assignments with the TableHash alone: each assignment holds the TableHash and the reason that it has none, and
/// nothing that the other parts of a summary hold. The TableHash is the one that [`summarize_rows`] gives, and so is the walk of the rows that it takes,
/// but the value hashes of the `DET`s, the keys of the examples, the value hash of each model's TableRows and the TableVector are left out.
fn summarize_hash_rows(materializer: &Materializer<'_>, contents: &Contents, train: &[Pair], fulls: &DetFulls<'_>) -> Result<TableSummary, ReachedBound> {
    let types: Vec<ValueType> = contents.columns.iter().map(|column| column.ty.clone()).collect();
    let assignments = (0..assignment_count(contents)).map(|at| alone(materializer, |own| at_assignment_with(own, contents, &types, at, train, fulls, true, true))).collect::<Result<_, _>>()?;
    Ok(TableSummary { assignments, capped: capped(contents), name: name_of(contents), hashes_only: true })
}

/// The summary of `table` for the export that gives the TableHash of a table and nothing else of its summary: a table of a finished query and an evidence table
/// have the TableHash at each assignment, as [`summarize_cached`] gives it, and the rest of each assignment is empty. A body table has no TableHash
/// and one assignment, for the reason `NotComputed`, and no walk of its rows. A table that faulted has the summary that [`summarize`] gives it.
///
/// The cache holds the result under `key`, flagged [`TableSummary::hashes_only`], where `key` is given; a summary that [`summarize_cached`] put under the
/// key gives its TableHash here, with the rest dropped, and a summary of this function does not stand for the full summary there.
pub fn summarize_hashes_cached(materializer: &Materializer<'_>, table: &Table, train: &[Pair], fulls: &DetFulls<'_>, cache: &SummaryCache, key: Option<SummaryKey>) -> Result<TableSummary, ReachedBound> {
    let Ok(contents) = &table.contents else { return Ok(TableSummary::faulted()) };
    if matches!(table.point, Point::Body { .. }) {
        return Ok(TableSummary::not_computed(contents));
    }
    let Some(key) = key else { return summarize_hash_rows(materializer, contents, train, fulls) };
    {
        let _timed = split::span(Part::SummaryHit);
        if let Some(held) = cache.get(&key) {
            if held.assignments.len() == assignment_count(contents) {
                let mut summary = TableSummary::clone(&held);
                for assignment in &mut summary.assignments {
                    *assignment = AssignmentSummary { dets: Vec::new(), more: Vec::new(), hash: assignment.hash, reason: std::mem::take(&mut assignment.reason), examples: Arc::default(), models: Arc::default(), features: Arc::default(), shape_rows: None, columns: Arc::default() };
                }
                summary.capped = capped(contents);
                summary.name = name_of(contents);
                summary.hashes_only = true;
                return Ok(summary);
            }
        }
    }
    let _timed = split::span(Part::SummaryMiss);
    let summary = summarize_hash_rows(materializer, contents, train, fulls)?;
    cache.put(key, Arc::new(summary.clone()));
    Ok(summary)
}

/// The summary of one assignment, which `summary` makes under the byte budget of an assignment of its own
/// ([`arclog::eval::Limits::for_assignment`]): an assignment that holds more than that budget has no TableHash, for the reason
/// that names the bound, and the table's other assignments go on. A stop at a budget of the request ends the summary of the table.
fn alone(materializer: &Materializer<'_>, summary: impl FnOnce(&Materializer<'_>) -> Result<AssignmentSummary, ReachedBound>) -> Result<AssignmentSummary, ReachedBound> {
    let scope = materializer.limits().for_assignment();
    let own = Materializer::new(materializer.session(), &scope);
    match summary(&own) {
        Err(bound) if bound.is_assignment() => Ok(AssignmentSummary { dets: Vec::new(), more: Vec::new(), hash: None, reason: bound_name(bound).to_owned(), examples: Arc::default(), models: Arc::default(), features: Arc::default(), shape_rows: None, columns: Arc::default() }),
        found => found,
    }
}

/// The values of the `DET`s at assignment `at` of `contents`: those of the first example that has the assignment.
fn det_values(contents: &Contents, at: usize) -> Option<&[Assignment]> {
    contents.examples.iter().find_map(|example| example.rows.as_ref().ok().and_then(|rows| rows.at.get(at))).map(|(values, _)| &values[..])
}

/// The count of `DET`s that the summary of assignment `at` of `contents` holds.
fn det_count(contents: &Contents, at: usize) -> usize {
    det_values(contents, at).map_or(0, |values| values.len().min(contents.dets.len()))
}

/// Spells the `DET`s of each assignment of `summary` as the relations of
/// `contents` spell them, and sorts them by the spelling.
fn spell_dets(contents: &Contents, summary: &mut TableSummary) {
    for (at, assignment) in summary.assignments.iter_mut().enumerate() {
        let Some(values) = det_values(contents, at) else { continue };
        for ((relation, _), det) in values.iter().zip(assignment.dets.iter_mut()) {
            det.0 = relation_spelled(relation);
        }
        if assignment.more.is_empty() {
            assignment.dets.sort_by(|a, b| a.0.cmp(&b.0));
        } else {
            let mut order: Vec<usize> = (0..assignment.dets.len()).collect();
            order.sort_by(|&a, &b| assignment.dets[a].0.cmp(&assignment.dets[b].0));
            assignment.dets = order.iter().map(|&at| assignment.dets[at].clone()).collect();
            assignment.more = assignment.more.iter().map(|variant| order.iter().map(|&at| variant[at]).collect()).collect();
        }
    }
}

/// A TableRows as export cells: the cells of its rows in the order of their cells.
struct Encoded {
    count: u64,
    cells: Vec<i32>,
    /// The hash of the count and the cells, which tells equal TableRows.
    key: StableHash,
}

/// The cells of `rows`, of columns of `types`. `held` takes the admission of
/// the cells, which the caller drops when it is done with them.
fn encode(materializer: &Materializer<'_>, rows: &Relation, types: &[ValueType], held: &mut Vec<Arc<SessionAllocation>>) -> Result<Encoded, ReachedBound> {
    let (count, cells) = sorted_cells(materializer, rows, types, held)?;
    let mut hasher = StableHasher::new();
    hasher.write_u64(count);
    hasher.write_i32s(&cells);
    Ok(Encoded { count, cells, key: hasher.finish128() })
}

/// The rows of a part of a relation in the order of their cells, with the cells
/// of the part's columns in the order of the columns of the relation.
struct SortedPart {
    cells: Vec<i32>,
    width: usize,
    count: usize,
}

/// A run of neighbouring columns of a relation that one part holds. The product
/// of the parts is written level by level, in the order of the columns.
struct ProductLevel {
    part: usize,
    /// The place of the run's first cell among the cells of a row of the part.
    in_part: usize,
    /// The place of the run's first cell among the cells of a row of the product.
    in_row: usize,
    len: usize,
    /// Whether no later level reads the part, so that each of its rows counts as a row.
    last: bool,
}

/// The cells of the rows of a product, in the order of their cells.
struct ProductCells<'m, 'a> {
    materializer: &'m Materializer<'a>,
    parts: Vec<SortedPart>,
    levels: Vec<ProductLevel>,
    /// The first row and the end of the rows of each part that the levels above leave.
    ranges: Vec<(usize, usize)>,
    row: Vec<i32>,
    cells: Vec<i32>,
    written: usize,
}

impl ProductCells<'_, '_> {
    /// Writes the rows from `level` down. Each part's rows stand in the order of
    /// their cells, so the rows with one value at a level stand next to each other.
    fn write(&mut self, level: usize) -> Result<(), ReachedBound> {
        let ProductLevel { part, in_part, in_row, len, last } = self.levels[level];
        let (first, end) = self.ranges[part];
        let width = self.parts[part].width;
        if level + 1 == self.levels.len() {
            let cells = &self.parts[part].cells;
            let above = &self.row[..in_row];
            for at in first..end {
                if self.written % (1 << 16) == 0 {
                    self.materializer.check()?;
                }
                self.written += 1;
                self.cells.extend_from_slice(above);
                self.cells.extend_from_slice(&cells[at * width + in_part..at * width + in_part + len]);
            }
            return Ok(());
        }
        let mut at = first;
        while at < end {
            let start = at * width + in_part;
            let mut next = at + 1;
            if !last {
                while next < end && self.parts[part].cells[next * width + in_part..next * width + in_part + len] == self.parts[part].cells[start..start + len] {
                    next += 1;
                }
            }
            self.row[in_row..in_row + len].copy_from_slice(&self.parts[part].cells[start..start + len]);
            self.ranges[part] = (at, next);
            self.write(level + 1)?;
            at = next;
        }
        self.ranges[part] = (first, end);
        Ok(())
    }
}

/// The count of `rows`, of columns of `types`, and their cells in the order of
/// their cells. `held` takes the admission of the cells: the sort admits its
/// largest scratch before it runs, and keeps the bytes of the cells alone once
/// it ends. The buffers are contiguous: the cells as written, the cells in
/// the order of their cells and the cells of a product of parts, each of
/// `width` 4-byte cells for each row, and the places of the rows, one `usize`
/// for each. Each Ident cell adds an entry of the Ident's export cell, at
/// most two of 24 bytes with the growth of the vector.
fn sorted_cells(materializer: &Materializer<'_>, rows: &Relation, types: &[ValueType], held: &mut Vec<Arc<SessionAllocation>>) -> Result<(u64, Vec<i32>), ReachedBound> {
    let width = row_width(types) as usize;
    let idents = types.iter().filter(|ty| matches!(ty, ValueType::Ident(_))).count();
    let per_row = width.saturating_mul(3 * std::mem::size_of::<i32>()).saturating_add(std::mem::size_of::<usize>()).saturating_add(idents.saturating_mul(48));
    let mut allocation = materializer.admit(rows, per_row)?;
    let (count, cells) = sorted_cells_in(materializer, rows, types)?;
    if let Some(allocation) = Arc::get_mut(&mut allocation) {
        allocation.shrink_to(cells.capacity().saturating_mul(std::mem::size_of::<i32>()));
    }
    held.push(allocation);
    Ok((count, cells))
}

/// [`sorted_cells`], whose caller has admitted the scratch. Each part's rows are put
/// in the order of their cells, and the order of the product's rows follows from
/// them, so no row of the product takes part in a sort.
fn sorted_cells_in(materializer: &Materializer<'_>, rows: &Relation, types: &[ValueType]) -> Result<(u64, Vec<i32>), ReachedBound> {
    let width = row_width(types) as usize;
    if rows.parts().len() < 2 || rows.parts().iter().any(|part| part.columns.is_empty()) {
        let (written, order) = sorted_rows(materializer, rows, types)?;
        let mut cells = Vec::with_capacity(written.len());
        for &at in &order {
            cells.extend_from_slice(&written[at * width..(at + 1) * width]);
        }
        return Ok((order.len() as u64, cells));
    }
    let count = usize::try_from(rows.len()).expect("a count of rows within a usize");
    // The part of each column, and the place of its first cell in a row of the part.
    let mut owner = vec![(0usize, 0usize); types.len()];
    let mut parts: Vec<SortedPart> = Vec::with_capacity(rows.parts().len());
    for (index, part) in rows.parts().iter().enumerate() {
        let mut places: Vec<usize> = (0..part.columns.len()).collect();
        places.sort_unstable_by_key(|&place| part.columns[place].0);
        let part_types: Vec<ValueType> = places.iter().map(|&place| types[usize::from(part.columns[place].0)].clone()).collect();
        let (written, order) = sorted_rows_at(materializer, &arclog::eval::join::one_part(part.rows.clone()), &places, &part_types)?;
        let part_width = row_width(&part_types) as usize;
        let mut cells = Vec::with_capacity(written.len());
        for &at in &order {
            cells.extend_from_slice(&written[at * part_width..(at + 1) * part_width]);
        }
        let mut first = 0;
        for (&place, ty) in places.iter().zip(&part_types) {
            owner[usize::from(part.columns[place].0)] = (index, first);
            first += row_width(std::slice::from_ref(ty)) as usize;
        }
        parts.push(SortedPart { cells, width: part_width, count: order.len() });
    }
    let mut levels: Vec<ProductLevel> = Vec::new();
    let mut in_row = 0;
    for ((part, in_part), ty) in owner.iter().copied().zip(types) {
        let len = row_width(std::slice::from_ref(ty)) as usize;
        match levels.last_mut() {
            Some(level) if level.part == part => level.len += len,
            _ => levels.push(ProductLevel { part, in_part, in_row, len, last: false }),
        }
        in_row += len;
    }
    for index in 0..parts.len() {
        if let Some(level) = levels.iter_mut().rev().find(|level| level.part == index) {
            level.last = true;
        }
    }
    let ranges = parts.iter().map(|part| (0, part.count)).collect();
    let mut product = ProductCells { materializer, parts, levels, ranges, row: vec![0; width], cells: Vec::with_capacity(count.saturating_mul(width)), written: 0 };
    product.write(0)?;
    materializer.check()?;
    Ok((count as u64, product.cells))
}

/// The hash of the rows of `rows` that an atom's table holds in the place of a
/// TableRows's cells: it tells equal rows, and it reads each part's rows once.
fn encode_rows(materializer: &Materializer<'_>, rows: &Relation, types: &[ValueType], held: &mut Vec<Arc<SessionAllocation>>) -> Result<Encoded, ReachedBound> {
    let (count, cells) = sorted_cells(materializer, rows, types, held)?;
    Ok(Encoded { count, cells, key: rows.rows_hash() })
}

/// The value hash of `rows`, a TableRows of `types` ([`value_hash_of`]).
fn value_hash(materializer: &Materializer<'_>, types: &[ValueType], rows: &Relation, assemblies: &Assemblies) -> Result<StableHash, ReachedBound> {
    let mut held = Vec::new();
    let value = encode(materializer, rows, types, &mut held)?;
    Ok(value_hash_of(types, &value, assemblies))
}

/// The value hash of `rows`, a TableRows of columns of `types`: the hash of the
/// type names ([`hashed_names`]) in the order of the columns, and of the Set of
/// rows, each row with its cells in the order of the columns. A `DET`'s value is
/// one TableRows, and every place that gives its hash gives this one: the `value`
/// of the `assignments` of a table that reads the `DET`, and the `hash` of an entry
/// of the `DET`'s own table, whose columns are the `DET`'s in their order.
fn value_hash_of(types: &[ValueType], rows: &Encoded, assemblies: &Assemblies) -> StableHash {
    let width = row_width(types) as usize;
    let mut row_hashes: Vec<u128> = (0..rows.count as usize)
        .map(|row| {
            let mut hasher = StableHasher::new();
            hasher.write_i32s(&rows.cells[row * width..(row + 1) * width]);
            hasher.finish128().0
        })
        .collect();
    sort_hashes(&mut row_hashes);
    let mut hasher = StableHasher::new();
    hasher.write(b"arclog.value_hash");
    hasher.write_u64(types.len() as u64);
    for name in hashed_names(types, assemblies) {
        hasher.write(name.as_bytes());
        hasher.write_u8(0);
    }
    hasher.write_u128(digest(&row_hashes));
    hasher.finish128()
}

fn at_assignment(materializer: &Materializer<'_>, contents: &Contents, types: &[ValueType], at: usize, train: &[Pair], fulls: &DetFulls<'_>) -> Result<AssignmentSummary, ReachedBound> {
    at_assignment_with(materializer, contents, types, at, train, fulls, true, false)
}

/// [`at_assignment`], with the `DET`s of the assignment where `with_dets` holds. Where `hash_only` holds, the summary has the TableHash and its reason alone:
/// the assignment takes no `DET`s, no key of an example, no value hash of a model's TableRows and no TableVector, and the walk of the rows that the
/// TableHash takes stays.
#[allow(clippy::too_many_arguments)]
fn at_assignment_with(materializer: &Materializer<'_>, contents: &Contents, types: &[ValueType], at: usize, train: &[Pair], fulls: &DetFulls<'_>, with_dets: bool, hash_only: bool) -> Result<AssignmentSummary, ReachedBound> {
    let mut dets = Vec::new();
    let mut more: Vec<Vec<StableHash>> = Vec::new();
    if let Some(values) = det_values(contents, at).filter(|_| with_dets && !hash_only) {
        // The value hashes that each `DET` stands for: those of the full values that project to the value it is read at, or its own.
        let mut choices: Vec<Vec<StableHash>> = Vec::with_capacity(values.len());
        for ((_, rows), det) in values.iter().zip(contents.dets.iter()) {
            choices.push(match fulls.choices(materializer, det, rows, values)? {
                Some(found) => found,
                None => vec![value_hash(materializer, &det.types, rows, &fulls.assemblies)?],
            });
        }
        let mut all: Vec<Vec<StableHash>> = vec![Vec::new()];
        for found in &choices {
            if found.len() == 1 {
                all.iter_mut().for_each(|prefix| prefix.push(found[0]));
            } else {
                all = all.iter().flat_map(|prefix| found.iter().map(move |hash| prefix.iter().copied().chain([*hash]).collect())).collect();
            }
        }
        let mut all = all.into_iter();
        dets = all.next().unwrap_or_default().into_iter().map(|hash| (String::new(), hash)).collect();
        more = all.collect();
    }
    let mut held = Vec::new();
    // The reason that the table has no TableHash, and the failed examples (kind, index, bound name) that it hashes.
    let mut reason: Option<&'static str> = contents.examples.is_empty().then_some("NoExamples");
    let mut failed: Vec<(u8, u32, &'static str)> = Vec::new();
    let mut examples: Vec<(u8, u32, Vec<Encoded>)> = Vec::with_capacity(contents.examples.len());
    // The place among the example's distinct TableRows of each of its models.
    let mut places: Vec<Vec<Option<usize>>> = Vec::with_capacity(contents.examples.len());
    // The rows of each example's distinct TableRows as the reader of shape values takes them.
    let mut shapes: Vec<Vec<ShapeModel>> = Vec::with_capacity(contents.examples.len());
    for example in &contents.examples {
        let (kind, index) = example_axis(example.example, train.len());
        let mut distinct: Vec<Encoded> = Vec::new();
        let mut shape_distinct: Vec<ShapeModel> = Vec::new();
        let mut place: Vec<Option<usize>> = Vec::new();
        let index = u32::try_from(index).expect("fewer than 2^32 examples");
        // A bound that depends only on the query fails the example; any other cause leaves the table with no TableHash.
        let mut fail = |bound: Option<ReachedBound>, cause: &'static str| match bound {
            Some(bound) if bound.is_stored() => failed.push((kind, index, bound_name(bound))),
            Some(bound) => {
                reason.get_or_insert(bound_name(bound));
            }
            None => {
                reason.get_or_insert(cause);
            }
        };
        match example.rows.as_ref().map(|rows| rows.at.get(at).ok_or(rows.stop.as_ref())) {
            Err(_) => fail(None, "RunFault"),
            Ok(Err(stop)) => fail(stop.map(|stop| stop.bound), "NoEntry"),
            Ok(Ok((_, models))) => {
                for value in models {
                    match value {
                        RelationValue::Rows(rows) => {
                            let found = if with_dets { encode(materializer, rows, types, &mut held)? } else { encode_rows(materializer, rows, types, &mut held)? };
                            match distinct.iter().position(|held| held.key == found.key) {
                                Some(at) => place.push(Some(at)),
                                None => {
                                    place.push(Some(distinct.len()));
                                    if !hash_only {
                                        shape_distinct.push(ShapeModel::of(rows));
                                    }
                                    distinct.push(found);
                                }
                            }
                        }
                        // An Undefined model gives no TableRows: the example's Set holds none of it, as the Set of an example whose models are all Undefined is empty.
                        RelationValue::Undefined => place.push(None),
                        RelationValue::Stopped(stop) => {
                            fail(Some(stop.bound), "Stopped");
                            place.push(None);
                        }
                    }
                }
            }
        }
        examples.push((kind, index, distinct));
        places.push(place);
        shapes.push(shape_distinct);
    }
    let views: Vec<(u8, u32, &[Encoded])> = examples.iter().map(|(kind, index, distinct)| (*kind, *index, &distinct[..])).collect();
    // A table that no `DET` reads as a value needs a hash that tells its rows from those of its other assignments, and no other: it reads its rows once for each part.
    let (found, search_work) = if with_dets { table_hash(types, &views, &fulls.assemblies) } else { (Some((rows_hash_of_table(types, &views, &fulls.assemblies), vec![0; views.len()])), None) };
    if let Some(work) = search_work {
        let gauges = materializer.limits().request.gauges();
        if found.is_none() {
            gauges.hit(Gauge::ColumnSearch, work, SEARCH_WORK_CAP);
        } else {
            gauges.note(Gauge::ColumnSearch, work, SEARCH_WORK_CAP);
        }
    }
    // A search that passed its cap gives no TableHash, and no hash of an example.
    let (hash, hashes) = match found {
        Some(found) => found,
        None => {
            reason.get_or_insert(COLUMN_SEARCH_BOUND);
            (StableHash(0), vec![0; views.len()])
        }
    };
    // The value hash of each distinct TableRows.
    let sets: Vec<Vec<u128>> = if hash_only { Vec::new() } else { views.iter().map(|(_, _, distinct)| distinct.iter().map(|rows| if with_dets { value_hash_of(types, rows, &fulls.assemblies).0 } else { rows.key.0 }).collect()).collect() };
    failed.sort_unstable();
    failed.dedup();
    let hash = if failed.is_empty() {
        hash
    } else {
        let mut hasher = StableHasher::new();
        hasher.write_u128(hash.0);
        for (kind, index, name) in &failed {
            hasher.write_u8(*kind);
            hasher.write_u32(*index);
            hasher.write(name.as_bytes());
            hasher.write_u8(0);
        }
        hasher.finish128()
    };
    let hash = reason.is_none().then_some(hash);
    let columns = Arc::new(if with_dets && !hash_only && reason.is_none() { column_hash::column_keys(types, &views, &failed, &fulls.assemblies) } else { Vec::new() });
    if hash_only {
        return Ok(AssignmentSummary { dets, more, hash, reason: reason.unwrap_or_default().to_owned(), examples: Arc::default(), models: Arc::default(), features: Arc::default(), shape_rows: None, columns: Arc::default() });
    }
    let models: Vec<Vec<Option<(u64, u128)>>> = places
        .iter()
        .zip(&examples)
        .zip(&sets)
        .map(|((place, (_, _, distinct)), sets)| place.iter().map(|at| at.map(|at| (distinct[at].count, sets[at]))).collect())
        .collect();
    let names = type_names(types);
    let names: Vec<&str> = names.iter().map(String::as_str).collect();
    // A task-level table has no train example: the features read all its examples.
    let task_level = examples.iter().any(|(kind, _, _)| *kind == 0);
    // Where the Type has an Example column, each example's TableRows holds the rows of every example, and the features split the
    // rows on that column. So each distinct non-empty TableRows is given once.
    let example_column = names.iter().position(|&name| arclog_features::type_code(name) == arclog_features::EXAMPLE);
    let mut given: Vec<&StableHash> = Vec::new();
    let mut rows: Vec<TableRows<'_>> = Vec::new();
    for (kind, index, distinct) in &examples {
        let example = match kind { 1 => *index, 2 => train.len() as u32 + *index, _ => 0 };
        for found in distinct {
            if example_column.is_some() && found.count > 0 {
                if given.iter().any(|key| **key == found.key) {
                    continue;
                }
                given.push(&found.key);
            }
            rows.push(TableRows { example, count: found.count as usize, cells: &found.cells });
        }
    }
    let features = arclog_features::vector(&Input { types: &names, example_column, rows: &rows, train, capped: capped(contents), task_level });
    // The rows for the shape values, where the table has a TableHash, which keys what the reader computes.
    let shape_rows = hash.map(|_| {
        let held = examples.iter().zip(shapes).map(|((kind, index, _), models)| ShapeExample { kind: *kind, index: *index, models }).collect();
        Arc::new(ShapeRows { types: types.to_vec(), train: train.len(), examples: held })
    });
    let examples: Vec<ExampleKey> = examples
        .iter()
        .zip(hashes)
        .map(|((kind, index, rows), hash)| ExampleKey { kind: *kind, index: *index, distinct: rows.len() as u32, rows: rows.iter().map(|rows| rows.count).max().unwrap_or(0), hash })
        .collect();
    Ok(AssignmentSummary { dets, more, hash, reason: reason.unwrap_or_default().to_owned(), examples: Arc::new(examples), models: Arc::new(models), features: Arc::new(features), shape_rows, columns })
}

/// A hash of the types of a table and of the keys of the TableRows of each of
/// its examples.
fn rows_hash_of_table(types: &[ValueType], examples: &[(u8, u32, &[Encoded])], assemblies: &Assemblies) -> StableHash {
    let mut hasher = StableHasher::new();
    for name in hashed_names(types, assemblies) {
        hasher.write(name.as_bytes());
        hasher.write_u8(0);
    }
    for (kind, index, distinct) in examples {
        hasher.write_u8(*kind);
        hasher.write_u32(*index);
        let mut keys: Vec<u128> = distinct.iter().map(|rows| rows.key.0).collect();
        keys.sort_unstable();
        hasher.write_u128(digest(&keys));
    }
    hasher.finish128()
}

/// Sorts `items` as `sort_unstable` does. Items that are hashes stand evenly over their high bits, so
/// one pass copies each item to the place of its bucket of the high 11 bits in another vector, and each bucket, which is
/// small, is sorted on its own. The copies are independent of each other.
fn sort_hashes(items: &mut [u128]) {
    const BITS: u32 = 11;
    const BUCKETS: usize = 1 << BITS;
    if items.len() < 1 << 16 {
        items.sort_unstable();
        return;
    }
    let bucket = |item: u128| (item >> (128 - BITS)) as usize;
    let mut starts = vec![0usize; BUCKETS + 1];
    for &item in items.iter() {
        starts[bucket(item) + 1] += 1;
    }
    for at in 0..BUCKETS {
        starts[at + 1] += starts[at];
    }
    let mut next = starts[..BUCKETS].to_vec();
    let mut sorted = vec![0u128; items.len()];
    for &item in items.iter() {
        let at = bucket(item);
        sorted[next[at]] = item;
        next[at] += 1;
    }
    for at in 0..BUCKETS {
        sorted[starts[at]..starts[at + 1]].sort_unstable();
    }
    items.copy_from_slice(&sorted);
}

/// The hash of `items` and their count.
fn digest(items: &[u128]) -> u128 {
    let mut hasher = StableHasher::new();
    hasher.write_u64(items.len() as u64);
    for &item in items {
        hasher.write_u128(item);
    }
    hasher.finish128().0
}

/// The `len` cells at `start` in the row `row` of `rows`, a row being `width` cells.
fn run_of(rows: &Encoded, width: usize, start: usize, len: usize, row: usize) -> &[i32] {
    &rows.cells[row * width + start..][..len]
}

/// The names of `types` as the TableHash writes them: the name that the export
/// writes, with [`pose_name`] for each Pose type in it. The name holds no Ident
/// source, so two tables whose Idents have equal contents have one TableHash
/// whichever forms make the Idents.
fn hashed_names(types: &[ValueType], assemblies: &Assemblies) -> Vec<String> {
    types.iter().map(|ty| hashed_type_name(ty, assemblies)).collect()
}

/// The name of `ty` that the export writes ([`type_names`]), with
/// [`pose_name`] in place of the name of each Pose type in it.
fn hashed_type_name(ty: &ValueType, assemblies: &Assemblies) -> String {
    fn has_pose(ty: &ValueType) -> bool {
        match ty {
            ValueType::Pose(_) => true,
            ValueType::Record(fields) => fields.iter().any(|(_, field)| has_pose(field)),
            _ => false,
        }
    }
    match ty {
        ValueType::Pose(assembly) => pose_name(assembly, assemblies),
        ValueType::Record(fields) if has_pose(ty) => {
            let fields: Vec<String> = fields.iter().map(|(name, field)| format!("({name:?}, {})", hashed_type_name(field, assemblies))).collect();
            format!("Record([{}])", fields.join(", "))
        }
        _ => type_names(std::slice::from_ref(ty)).pop().expect("a name for the type"),
    }
}

/// The QueryHash of the `RIGID_DET` of each assembly of a program, by the
/// form's name.
pub type Assemblies = StableHashMap<RigidDetName, StableHash>;

/// The name of the Pose type of `assembly` in the TableHash and the value hash:
/// `Pose(`, the 32 hexadecimal digits of the QueryHash of its `RIGID_DET` in
/// `assemblies`, and its key row, `)`. The name that the export writes holds the
/// slots of the form and of the `DET`s that the form reads, which differ
/// between two programs of one query, and the QueryHash holds no slot. Where
/// `assemblies` lacks the form, the name is the one that the export writes.
fn pose_name(assembly: &AssemblyId, assemblies: &Assemblies) -> String {
    match assemblies.get(&assembly.name) {
        Some(query) => format!("Pose({:032x}, {:?})", query.0, assembly.key),
        None => type_names(&[ValueType::Pose(assembly.clone())]).pop().expect("a name for the type"),
    }
}

/// The TableHash of the Set of TableRows of each of `examples`, each as its kind,
/// index and distinct TableRows, over columns of `types`, and the low 64 bits of
/// the hash of each example's Set of TableRows under the order of the columns that
/// gives the TableHash; none of them where the search for the order of the tied
/// columns passed its cap. The second value is the work of that search in units,
/// none where no columns tie and no search ran.
fn table_hash(types: &[ValueType], examples: &[(u8, u32, &[Encoded])], assemblies: &Assemblies) -> (Option<(StableHash, Vec<u64>)>, Option<u64>) {
    let names = hashed_names(types, assemblies);
    let widths: Vec<usize> = types.iter().map(|ty| if ty.is_box() { 4 } else { 1 }).collect();
    let starts: Vec<usize> = widths.iter().scan(0, |at, width| { let start = *at; *at += width; Some(start) }).collect();
    let width: usize = widths.iter().sum();
    let column_hashes: Vec<u128> = (0..types.len())
        .map(|column| {
            if names.iter().filter(|name| **name == names[column]).count() == 1 {
                return 0;
            }
            let mut hasher = StableHasher::new();
            for (_, _, distinct) in examples {
                let mut sets: Vec<u128> = distinct
                    .iter()
                    .map(|rows| {
                        let mut runs: Vec<u128> = (0..rows.count as usize)
                            .map(|row| {
                                let mut run = StableHasher::new();
                                run.write_i32s(run_of(rows, width, starts[column], widths[column], row));
                                run.finish128().0
                            })
                            .collect();
                        sort_hashes(&mut runs);
                        runs.dedup();
                        digest(&runs)
                    })
                    .collect();
                sets.sort_unstable();
                sets.dedup();
                hasher.write_u128(digest(&sets));
            }
            hasher.finish128().0
        })
        .collect();
    let mut sorted: Vec<usize> = (0..types.len()).collect();
    sorted.sort_by(|&a, &b| (&names[a], column_hashes[a]).cmp(&(&names[b], column_hashes[b])));
    let ties = sorted.windows(2).any(|pair| (&names[pair[0]], column_hashes[pair[0]]) == (&names[pair[1]], column_hashes[pair[1]]));
    let cells = Cells::new(types, examples);
    let (found, work) = if ties {
        let searched = column_order::least_body(&cells, &names, &column_hashes);
        (searched.found, Some(searched.work))
    } else {
        (Some(cells.body_examples(&sorted)), None)
    };
    let Some((body, hashes)) = found else { return (None, work) };
    let mut hasher = StableHasher::new();
    let mut sorted_names = names;
    sorted_names.sort();
    for name in &sorted_names {
        hasher.write(name.as_bytes());
        hasher.write_u8(0);
    }
    hasher.write_u128(body);
    (Some((hasher.finish128(), hashes)), work)
}

/// The full values of the `DET`s of a stream, which a table that reads a `DET` through some of its columns stands for. The resolver keeps of a `DET`
/// the columns that its readers name, so such a table is evaluated at the values of the `DET` projected to those columns. The `DET` itself is
/// exported once, with all its columns, at its own step, and an assignment names it there: by its own QueryHash, and by the value hash of one of its full
/// values. So a table that reads a `DET` through some of its columns is written at each full value that projects to the value it was evaluated at (the
/// table's TableRows repeat over those assignments), and none of those expansions is capped.
pub struct DetFulls<'t> {
    tables: Vec<&'t Table>,
    built: RefCell<StableHashMap<String, Option<Rc<FullDet<'t>>>>>,
    /// The assemblies of the program, by which the hashes name each Pose type ([`pose_name`]).
    assemblies: Assemblies,
}

/// A `DET` of the stream with all its columns.
struct FullDet<'t> {
    contents: &'t Contents,
    /// The place of the `DET` itself among the `DET`s of its own table.
    own: usize,
    values: RefCell<Option<Rc<Vec<FullValue>>>>,
}

/// A full value of a `DET`, at one assignment of the `DET`'s own table.
struct FullValue {
    /// The other `DET`s of that assignment: their spelling, arity and the hash of their rows.
    others: Vec<(String, u16, StableHash)>,
    cells: Encoded,
    hash: StableHash,
}

impl<'t> DetFulls<'t> {
    /// The full `DET`s of `tables`, the tables of the stream, in order.
    pub fn new(tables: Vec<&'t Table>) -> Self {
        DetFulls { tables, built: RefCell::default(), assemblies: Assemblies::default() }
    }

    /// These full `DET`s, with `assemblies`, the QueryHash of the `RIGID_DET`
    /// of each assembly of the program, by which the hashes name each Pose type.
    pub fn with_assemblies(mut self, assemblies: Assemblies) -> Self {
        self.assemblies = assemblies;
        self
    }

    /// No full `DET`: every `DET` is read as the table holds it.
    pub fn none() -> Self {
        DetFulls::new(Vec::new())
    }

    fn find(&self, spelled: &str) -> Option<Rc<FullDet<'t>>> {
        if let Some(found) = self.built.borrow().get(spelled) {
            return found.clone();
        }
        let found = self.tables.iter().find_map(|table| {
            let contents = table.contents.as_ref().ok()?;
            if !matches!(contents.relation, TableRelation::Slot(_)) || contents.name != spelled {
                return None;
            }
            let own = contents.dets.iter().position(|det| relation_spelled(&det.relation) == spelled)?;
            contents.dets[own].columns.as_ref()?;
            Some(Rc::new(FullDet { contents, own, values: RefCell::new(None) }))
        });
        self.built.borrow_mut().insert(spelled.to_owned(), found.clone());
        found
    }

    fn values(&self, materializer: &Materializer<'_>, full: &FullDet<'t>) -> Result<Rc<Vec<FullValue>>, ReachedBound> {
        if let Some(held) = full.values.borrow().as_ref() {
            return Ok(Rc::clone(held));
        }
        let det = &full.contents.dets[full.own];
        let mut values: Vec<FullValue> = Vec::new();
        if let Some(assigned) = full.contents.examples.iter().find_map(|example| example.rows.as_ref().ok()) {
            for (assignment, _) in &assigned.at {
                let Some((_, rows)) = assignment.get(full.own) else { continue };
                let others: Vec<(String, u16, StableHash)> = assignment.iter().enumerate().filter(|(at, _)| *at != full.own).map(|(_, (relation, rows))| (relation_spelled(relation), rows.arity(), rows.rows_hash())).collect();
                let mut held = Vec::new();
                let cells = encode(materializer, rows, &det.types, &mut held)?;
                if values.iter().any(|value| value.cells.key == cells.key && value.others == others) {
                    continue;
                }
                let hash = value_hash_of(&det.types, &cells, &self.assemblies);
                values.push(FullValue { others, cells, hash });
            }
        }
        let values = Rc::new(values);
        *full.values.borrow_mut() = Some(Rc::clone(&values));
        Ok(values)
    }

    /// The value hashes of the full values that project to `rows`, the value that `det` is read at, among `assignment`, the `DET`s of one assignment of
    /// the table that reads it; none where `det` is read with all its columns, or the stream holds no full value that projects to `rows`.
    fn choices(&self, materializer: &Materializer<'_>, det: &TableDet, rows: &Relation, assignment: &[Assignment]) -> Result<Option<Vec<StableHash>>, ReachedBound> {
        let Some(paths) = &det.columns else { return Ok(None) };
        let spelled = relation_spelled(&det.relation);
        let Some(full) = self.find(&spelled) else { return Ok(None) };
        let own = &full.contents.dets[full.own];
        let Some(columns) = &own.columns else { return Ok(None) };
        if columns.len() == paths.len() && columns.iter().zip(paths.iter()).all(|(a, b)| a == b) {
            return Ok(None);
        }
        let Some(map) = paths.iter().map(|path| columns.iter().position(|column| column == path)).collect::<Option<Vec<usize>>>() else { return Ok(None) };
        let mut held = Vec::new();
        let read = encode(materializer, rows, &det.types, &mut held)?;
        let identity: Vec<usize> = (0..det.types.len()).collect();
        let wanted = row_cells(&read, &det.types, &identity);
        let siblings: Vec<(String, u16, StableHash)> = assignment.iter().map(|(relation, rows)| (relation_spelled(relation), rows.arity(), rows.rows_hash())).collect();
        let mut found: Vec<StableHash> = Vec::new();
        for value in self.values(materializer, &full)?.iter() {
            let agrees = value.others.iter().all(|(name, arity, hash)| siblings.iter().find(|sibling| sibling.0 == *name).is_none_or(|sibling| sibling.1 != *arity || sibling.2 == *hash));
            if agrees && !found.contains(&value.hash) && row_cells(&value.cells, &own.types, &map) == wanted {
                found.push(value.hash);
            }
        }
        Ok((!found.is_empty()).then_some(found))
    }
}

/// The rows of `rows` (of columns of `types`) at the columns `columns`, as sorted, distinct runs of cells.
fn row_cells(rows: &Encoded, types: &[ValueType], columns: &[usize]) -> Vec<Vec<i32>> {
    let widths: Vec<usize> = types.iter().map(|ty| if ty.is_box() { 4 } else { 1 }).collect();
    let starts: Vec<usize> = widths.iter().scan(0, |at, width| { let start = *at; *at += width; Some(start) }).collect();
    let width: usize = widths.iter().sum();
    let mut out: Vec<Vec<i32>> = (0..rows.count as usize)
        .map(|row| columns.iter().flat_map(|&column| rows.cells[row * width + starts[column]..][..widths[column]].iter().copied()).collect())
        .collect();
    out.sort_unstable();
    out.dedup();
    out
}
