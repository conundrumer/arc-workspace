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
//! - the TableVector: the features of `arclog-features` on the Set of TableRows.
//!
//! The summary reads the rows in the table, so a table that the export writes
//! as Count entries (more rows than the projection cap) still has a hash.
//!
//! The TableHash has one definition, over the entries of one table at one
//! assignment:
//!
//! 1. Each row is encoded as export cells ([`sorted_rows`]). An Ident cell is
//!    the first 32 bits of its member digest under `ARCLOG_IDENT_SOURCE=value`.
//! 2. For each column of a type that another column has, hash the type and
//!    the set of its cell runs on each example. A column of a type that no other
//!    column has cannot tie, and its hash is 0.
//! 3. Sort the columns by type name and that hash. Columns equal in both form
//!    a tied group.
//! 4. For each order of the columns within the tied groups, up to
//!    [`MAX_ORDERS`] orders and while the orders times the cells stay within
//!    [`KEY_CELLS`], hash each example's Set of TableRows. The body hash is the least
//!    over the orders.
//! 5. The TableHash is the hash of the sorted type names and the body hash.
//!
//! A type name in the TableHash is the name that the export writes
//! ([`type_names`]), and, for each Ident in the type that has a source, the
//! identity of that source ([`hashed_names`]). So two tables are equal only
//! where their Types, Ident sources included, and their TableRows are equal.
//! A type with no Ident source, as every type is while `ARCLOG_IDENT_SOURCE`
//! is off, has the name that the export writes. A Pose type is the exception:
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
use std::collections::HashMap;
use std::hash::Hasher;
use std::rc::Rc;
use std::sync::{Arc, Mutex};

use arclog::eval::determinations::relation_spelled;
use arclog::eval::join::Materializer;
use arclog::eval::{ReachedBound, RelationValue};
use arclog::hash::{StableHash, StableHasher};
use arclog::judge::determination::Assignment;
use arclog::read::spelling::{spelling, FACT_RELATIONS};
use arclog::relations::Relation;
use arclog::session::SessionAllocation;
use arclog::task::{Grid, Task};
use arclog::program::RigidDetName;
use arclog::types::{AssemblyId, IdentSource, SourceId, ValueType};
use arclog_features::{Grid as FeatureGrid, Input, Pair, TableRows};

use crate::columns::{row_width, sorted_rows, type_names};
use crate::split::{self, Part};
use crate::tables::{example_axis, Contents, Table, TableDet, TableRelation};

/// The most column orders that the TableHash tries.
const MAX_ORDERS: usize = 720;

/// The most cells that the column orders of a TableHash hash in all.
const KEY_CELLS: usize = 1_400_000;

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
    /// where the table has no example, `TableFault` where the table has no contents, or the bound that stopped the summary itself.
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
}

impl TableSummary {
    /// The summary of `table` with no hash for `reason`, which holds as many assignments as
    /// the table's examples walk.
    pub fn unhashed(table: &Table, reason: &str) -> Self {
        let Ok(contents) = &table.contents else { return TableSummary::faulted() };
        let assignments = (0..assignment_count(contents)).map(|_| AssignmentSummary { dets: Vec::new(), more: Vec::new(), hash: None, reason: reason.to_owned(), examples: Arc::default(), models: Arc::default(), features: Arc::default() }).collect();
        TableSummary { assignments, capped: capped(contents), name: name_of(contents) }
    }

    fn faulted() -> Self {
        TableSummary { assignments: vec![AssignmentSummary { dets: Vec::new(), more: Vec::new(), hash: None, reason: "TableFault".to_owned(), examples: Arc::default(), models: Arc::default(), features: Arc::default() }], capped: false, name: String::new() }
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
        ReachedBound::SessionBytes(_) => "SessionBytes",
        ReachedBound::Deadline => "Deadline",
        ReachedBound::Cancelled => "Cancelled",
        ReachedBound::NoValues => "NoValues",
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
/// the export packs rows. The cache keeps two generations, each with at most
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
    young: HashMap<SummaryKey, Arc<TableSummary>>,
    /// The assignments of the summaries in `young`.
    assignments: usize,
    old: HashMap<SummaryKey, Arc<TableSummary>>,
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

impl Generations {
    fn insert(&mut self, key: SummaryKey, summary: Arc<TableSummary>) {
        let size = summary.assignments.len();
        if !self.young.contains_key(&key) && (self.young.len() >= SUMMARY_CACHE_ENTRIES || self.assignments.saturating_add(size) > SUMMARY_CACHE_ASSIGNMENTS) {
            self.old = std::mem::take(&mut self.young);
            self.assignments = 0;
        }
        self.assignments += size;
        if let Some(replaced) = self.young.insert(key, summary) {
            self.assignments = self.assignments.saturating_sub(replaced.assignments.len());
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
            let fits = held.assignments.len() == assignment_count(contents) && held.assignments.iter().enumerate().all(|(at, held)| held.dets.len() == det_count(contents, at));
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
    let assignments = (0..assignment_count(contents)).map(|at| at_assignment_with(materializer, contents, &types, at, train, &bodies, false)).collect::<Result<_, _>>()?;
    Ok(TableSummary { assignments, capped: capped(contents), name: name_of(contents) })
}

fn summarize_rows(materializer: &Materializer<'_>, contents: &Contents, train: &[Pair], fulls: &DetFulls<'_>) -> Result<TableSummary, ReachedBound> {
    let types: Vec<ValueType> = contents.columns.iter().map(|column| column.ty.clone()).collect();
    let assignments = (0..assignment_count(contents)).map(|at| at_assignment(materializer, contents, &types, at, train, fulls)).collect::<Result<_, _>>()?;
    Ok(TableSummary { assignments, capped: capped(contents), name: name_of(contents) })
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
    for &cell in &cells {
        hasher.write_i32(cell);
    }
    Ok(Encoded { count, cells, key: hasher.finish128() })
}

/// The count of `rows`, of columns of `types`, and their cells in the order of
/// their cells. `held` takes the admission of the cells. Where each part of
/// `rows` holds a run of the columns in order, the rows of the product of the
/// parts, each part's rows in the order of their cells, stand in the order of
/// their cells, so no row of the product takes part in a sort.
fn sorted_cells(materializer: &Materializer<'_>, rows: &Relation, types: &[ValueType], held: &mut Vec<Arc<SessionAllocation>>) -> Result<(u64, Vec<i32>), ReachedBound> {
    let width = row_width(types) as usize;
    held.push(materializer.admit(rows, Materializer::row_bytes(width.saturating_mul(32).saturating_add(32), 4))?);
    let mut parts: Vec<&arclog::relations::RelationPart> = rows.parts().iter().collect();
    parts.sort_by_key(|part| part.columns.first().map(|column| column.0));
    let mut next = 0u16;
    let in_order = parts.iter().all(|part| part.columns.iter().all(|column| {
        let holds = column.0 == next;
        next += 1;
        holds
    }));
    if parts.len() < 2 || !in_order {
        let (written, order) = sorted_rows(materializer, rows, types)?;
        let mut cells = Vec::with_capacity(written.len());
        for &at in &order {
            cells.extend_from_slice(&written[at * width..(at + 1) * width]);
        }
        return Ok((order.len() as u64, cells));
    }
    let count = usize::try_from(rows.len()).expect("a count of rows within a usize");
    let mut sorted: Vec<Vec<i32>> = Vec::with_capacity(parts.len());
    let mut first = 0usize;
    for part in &parts {
        let part_types = &types[first..first + part.columns.len()];
        first += part.columns.len();
        let (written, order) = sorted_rows(materializer, &arclog::eval::join::one_part(part.rows.clone()), part_types)?;
        let part_width = row_width(part_types) as usize;
        let mut cells = Vec::with_capacity(written.len());
        for &at in &order {
            cells.extend_from_slice(&written[at * part_width..(at + 1) * part_width]);
        }
        sorted.push(cells);
    }
    let widths: Vec<usize> = parts.iter().scan(0usize, |first, part| {
        let part_types = &types[*first..*first + part.columns.len()];
        *first += part.columns.len();
        Some(row_width(part_types) as usize)
    }).collect();
    let mut cells: Vec<i32> = Vec::with_capacity(count.saturating_mul(width));
    let mut places = vec![0usize; parts.len()];
    for at in 0..count {
        if at % (1 << 16) == 0 {
            materializer.check()?;
        }
        for ((part, place), part_width) in sorted.iter().zip(&places).zip(&widths) {
            cells.extend_from_slice(&part[place * part_width..(place + 1) * part_width]);
        }
        // The last part's rows turn fastest, as the next column of a row in order does.
        for (index, place) in places.iter_mut().enumerate().rev() {
            *place += 1;
            if *place * widths[index] < sorted[index].len() || widths[index] == 0 && *place < parts[index].rows.len() {
                break;
            }
            *place = 0;
        }
    }
    materializer.check()?;
    Ok((count as u64, cells))
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
            for &cell in &rows.cells[row * width..(row + 1) * width] {
                hasher.write_i32(cell);
            }
            hasher.finish128().0
        })
        .collect();
    row_hashes.sort_unstable();
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
    at_assignment_with(materializer, contents, types, at, train, fulls, true)
}

/// [`at_assignment`], with the `DET`s of the assignment where `with_dets` holds.
fn at_assignment_with(materializer: &Materializer<'_>, contents: &Contents, types: &[ValueType], at: usize, train: &[Pair], fulls: &DetFulls<'_>, with_dets: bool) -> Result<AssignmentSummary, ReachedBound> {
    let mut dets = Vec::new();
    let mut more: Vec<Vec<StableHash>> = Vec::new();
    if let Some(values) = det_values(contents, at).filter(|_| with_dets) {
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
    for example in &contents.examples {
        let (kind, index) = example_axis(example.example, train.len());
        let mut distinct: Vec<Encoded> = Vec::new();
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
    }
    let views: Vec<(u8, u32, &[Encoded])> = examples.iter().map(|(kind, index, distinct)| (*kind, *index, &distinct[..])).collect();
    // A table that no `DET` reads as a value needs a hash that tells its rows from those of its other assignments, and no other: it reads its rows once for each part.
    let (hash, hashes) = if with_dets { table_hash(types, &views, &fulls.assemblies) } else { (rows_hash_of_table(types, &views, &fulls.assemblies), vec![0; views.len()]) };
    // The value hash of each distinct TableRows.
    let sets: Vec<Vec<u128>> = views.iter().map(|(_, _, distinct)| distinct.iter().map(|rows| if with_dets { value_hash_of(types, rows, &fulls.assemblies).0 } else { rows.key.0 }).collect()).collect();
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
    let examples: Vec<ExampleKey> = examples
        .iter()
        .zip(hashes)
        .map(|((kind, index, rows), hash)| ExampleKey { kind: *kind, index: *index, distinct: rows.len() as u32, rows: rows.iter().map(|rows| rows.count).max().unwrap_or(0), hash })
        .collect();
    Ok(AssignmentSummary { dets, more, hash, reason: reason.unwrap_or_default().to_owned(), examples: Arc::new(examples), models: Arc::new(models), features: Arc::new(features) })
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
/// writes, with [`pose_name`] for each Pose type in it, and `@` and the 32
/// hexadecimal digits of the identity of the source after it for each Ident of
/// a source in the type, in the order of the type.
fn hashed_names(types: &[ValueType], assemblies: &Assemblies) -> Vec<String> {
    fn push_sources(ty: &ValueType, name: &mut String) {
        match ty {
            ValueType::Ident(IdentSource::Form(SourceId(id))) => name.push_str(&format!("@{:032x}", id.0)),
            ValueType::Record(fields) => fields.iter().for_each(|(_, field)| push_sources(field, name)),
            _ => {}
        }
    }
    types
        .iter()
        .map(|ty| {
            let mut name = hashed_type_name(ty, assemblies);
            push_sources(ty, &mut name);
            name
        })
        .collect()
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
pub type Assemblies = HashMap<RigidDetName, StableHash>;

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

/// The next order of `items` in the lexicographic order, or, where `items`
/// is the last, the first, and false.
fn next_permutation(items: &mut [usize]) -> bool {
    let Some(pivot) = (1..items.len()).rev().find(|&at| items[at - 1] < items[at]).map(|at| at - 1) else {
        items.reverse();
        return false;
    };
    let swap = (pivot + 1..items.len()).rev().find(|&at| items[at] > items[pivot]).expect("an item after the pivot is greater");
    items.swap(pivot, swap);
    items[pivot + 1..].reverse();
    true
}

/// The TableHash of the Set of TableRows of each of `examples`, each as its kind,
/// index and distinct TableRows, over columns of `types`, and the low 64 bits of
/// the hash of each example's Set of TableRows under the order of the columns that
/// gives the TableHash.
fn table_hash(types: &[ValueType], examples: &[(u8, u32, &[Encoded])], assemblies: &Assemblies) -> (StableHash, Vec<u64>) {
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
                                for &cell in run_of(rows, width, starts[column], widths[column], row) {
                                    run.write_i32(cell);
                                }
                                run.finish128().0
                            })
                            .collect();
                        runs.sort_unstable();
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
    let mut tied: Vec<(usize, usize)> = Vec::new();
    let mut start = 0;
    while start < sorted.len() {
        let key = |at: usize| (&names[sorted[at]], column_hashes[sorted[at]]);
        let end = (start..sorted.len()).find(|&at| key(at) != key(start)).unwrap_or(sorted.len());
        if end - start > 1 {
            tied.push((start, end - start));
        }
        start = end;
    }
    let cells: usize = examples.iter().flat_map(|(_, _, distinct)| distinct.iter()).map(|rows| rows.cells.len()).sum::<usize>().max(1);
    let mut orders = vec![sorted.clone()];
    let mut current = sorted;
    while orders.len() < MAX_ORDERS && (orders.len() + 1).saturating_mul(cells) <= KEY_CELLS {
        let advanced = tied.iter().any(|&(start, len)| next_permutation(&mut current[start..start + len]));
        if !advanced {
            break;
        }
        orders.push(current.clone());
    }
    let mut least: Option<(u128, Vec<u64>)> = None;
    for columns in &orders {
        let mut body = StableHasher::new();
        let mut hashes = Vec::with_capacity(examples.len());
        for (kind, index, distinct) in examples {
            let mut sets: Vec<u128> = distinct
                .iter()
                .map(|rows| {
                    let mut row_hashes: Vec<u128> = (0..rows.count as usize)
                        .map(|row| {
                            let mut hasher = StableHasher::new();
                            for &column in columns {
                                for &cell in run_of(rows, width, starts[column], widths[column], row) {
                                    hasher.write_i32(cell);
                                }
                            }
                            hasher.finish128().0
                        })
                        .collect();
                    row_hashes.sort_unstable();
                    digest(&row_hashes)
                })
                .collect();
            sets.sort_unstable();
            sets.dedup();
            let set = digest(&sets);
            body.write_u8(*kind);
            body.write_u32(*index);
            body.write_u128(set);
            hashes.push(set as u64);
        }
        let body = body.finish128().0;
        if least.as_ref().map_or(true, |(held, _)| body < *held) {
            least = Some((body, hashes));
        }
    }
    let (body, hashes) = least.expect("at least one order of the columns");
    let mut hasher = StableHasher::new();
    let mut sorted_names = names;
    sorted_names.sort();
    for name in &sorted_names {
        hasher.write(name.as_bytes());
        hasher.write_u8(0);
    }
    hasher.write_u128(body);
    (hasher.finish128(), hashes)
}

/// The full values of the `DET`s of a stream, which a table that reads a `DET` through some of its columns stands for. The resolver keeps of a `DET`
/// the columns that its readers name, so such a table is evaluated at the values of the `DET` projected to those columns. The `DET` itself is
/// exported once, with all its columns, at its own step, and an assignment names it there: by its own QueryHash, and by the value hash of one of its full
/// values. So a table that reads a `DET` through some of its columns is written at each full value that projects to the value it was evaluated at (the
/// table's TableRows repeat over those assignments), and none of those expansions is capped.
pub struct DetFulls<'t> {
    tables: Vec<&'t Table>,
    built: RefCell<HashMap<String, Option<Rc<FullDet<'t>>>>>,
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
