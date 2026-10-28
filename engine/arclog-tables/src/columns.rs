//! The tables of one case program as flat columns, for a reader that slices
//! arrays and parses no text: the layout of [`CaseColumns`].
//!
//! Each of its parts holds one row for each item, in a column of its own:
//!
//! - [`TableColumns`]: a table, in the order of the stream, after the
//!   evidence tables;
//! - [`EntryColumns`]: a table, an example and an entry of its rows, which
//!   is a model at an assignment of the `DET`s;
//! - [`AssignedColumns`]: a `DET` at an entry's assignment;
//! - [`ProjectionColumns`] and [`ProjectionRowColumns`]: a projection of a table, and the
//!   projection's rows at an entry;
//! - [`FlowColumns`]: a source of a column of a table;
//! - [`CopyColumns`]: a declared row of a component's output that the
//!   output's rows break, which a replay under
//!   [`DecodeSettings::check_copies`](arclog::stream::DecodeSettings::check_copies)
//!   finds.
//!
//! The first tables of a case are the evidence tables of its task, `ex_input`
//! then `ex_output`, with point 2, token 0, the relation's name in `fact`,
//! and one entry for each example whose grid the relation holds.
//!
//! A part that names a table (a row of [`EntryColumns::table`], a flow's table
//! and source table, a projection's table) names it by its number in the
//! case's whole list of tables, which [`TableColumns`] numbers in its order. The
//! columns of a stream that shares a prefix with a base stream can hold the
//! tables from the first after the prefix alone ([`cut_case_columns`]): the
//! first row of [`TableColumns`] is then the table numbered `k`, the count of the
//! tables before it, and a table number below `k` names the base's table of
//! that number. A part's other row numbers (an entry, a projection) count its
//! rows in the columns.
//!
//! Every row of every table is a run of cells in `values`, each cell an
//! `i32` by the type of its column: a Box its four margins (top, bottom,
//! left, right), a Color its digit, a Number itself, an Example its index, a
//! Unit 0, and an orientation constant, a `Pose` by its D4 constant, its
//! encoding, which [`orientation_names`] names. An Ident is its number, which
//! depends on the order of interning in the session of the unit of streams
//! that interned it, so on the cut of the solver's streams into units, which
//! the solver's unit count sets, and it is equal to another Ident of the
//! same run and to no Ident of another. A run is an offset in `values` and a
//! count of rows, and its width in cells is the table's, or the `DET`'s, or
//! the projection's. The rows of a run are in the order of their cells. Two
//! runs of a case with the same cells, the same rows of the same width, share
//! one offset, and the cells stand once in `values`. A run without a cell has
//! offset 0.
//!
//! A table that has a column of type `Box` whose frame is a made frame
//! (`<maker>@<path>`, with or without ` in <frame>`) lists the indexes of those
//! columns in [`TableColumns::extent_columns`], and each of its entries and of its
//! projection rows holds one more run, the extents of the made frames, at
//! [`EntryColumns::extent_offset`] and [`ProjectionRowColumns::extent_offset`]:
//! for each row of the entry's run, in its order, two cells for each extent
//! column, in their order, the frame's count of rows V and then of columns H at
//! that row, or `-1 -1` for a row with no extent. A row has no extent where its
//! derivations give two extents, or where the engine cannot compute one, and every
//! extent is at least 1 in each cell, so `-1 -1` tells the two apart. A Box `v` in a
//! frame of extent (V, H) covers a box of own size (V - top - bottom, H - left -
//! right), so a reader tells from `v`'s margins and the extent which cells of its
//! frame `v` covers. An extent run stands in `values` beside the others, and
//! equal runs of a case share one offset. An entry of kind `Rows`, of a table
//! with extent columns, that has rows and no extent run has a stop in
//! [`EntryColumns::extent_stop`] or a reason in [`EntryColumns::extent_fault`].

use std::hash::Hash;
use std::sync::Arc;

use arclog::decode::Projections;
use arclog::eval::copies::CopyViolation;
use arclog::eval::determinations::relation_spelled;
use arclog::eval::join::each_row;
use arclog::eval::{RelationValue, RunFault, Stop};
use arclog::hash::{StableHash, StableHashMap, StableHasher};
use arclog::program::path::NodePath;
use arclog::program::{column_spelled, ColumnName, FactRelation, LabelId, ProgramRelation, RelationRef};
use arclog::read::spelling::{spelling, FACT_RELATIONS};
use arclog::registry::{has_frame, Registry};
use arclog::relations::Relation;
use arclog::stream::corpus::StreamLabels;
use arclog::terms::{Constant, OrientationConstant, Term, TermId, ORIENTATION_TYPES};
use arclog::types::ValueType;

use crate::extents::{EntryExtents, Extent, Merged};
use crate::flows::{ColumnSource, SourceColumn, SourceFrame, SourceKind};
use crate::tables::{evidence_shells, Contents, Point, Table, TableColumn, TableRelation};

/// The point of a table, as the code in [`TableColumns::point`].
#[derive(Clone, Copy, PartialEq, Eq, Debug)]
#[repr(u8)]
pub enum PointKind {
    Relation = 0,
    Body = 1,
    Evidence = 2,
}

/// What the projections of a table are, as the code in [`TableColumns::projections`].
#[derive(Clone, Copy, PartialEq, Eq, Debug)]
#[repr(u8)]
pub enum ProjectionsKind {
    /// The table gives its rows, and no projections.
    None = 0,
    /// The search stopped at a bound.
    Stopped = 1,
    /// The projections, possibly none.
    Found = 2,
}

/// What an entry holds, as the code in [`EntryColumns::kind`].
#[derive(Clone, Copy, PartialEq, Eq, Debug)]
#[repr(u8)]
pub enum ValueKind {
    /// Rows, in the run of the entry.
    Rows = 0,
    /// The count of rows alone, since the table gives projections.
    Count = 1,
    Undefined = 2,
    /// The bound that stopped the enumeration of models, in `value_stop`.
    Stopped = 3,
    /// The example's fault: the example has no other entry.
    Fault = 4,
    /// The example has no entry, and its stop stands in `stop`.
    NoEntries = 5,
}

/// A bound that stopped a walk, and the form that reached it, as the
/// bound's name and the form's path.
#[derive(Clone, Debug, Default)]
pub struct StopColumns {
    pub bound: Vec<Option<String>>,
    pub form: Vec<Option<String>>,
}

impl StopColumns {
    fn push(&mut self, stop: Option<&Stop>) {
        self.bound.push(stop.map(|stop| format!("{:?}", stop.bound)));
        self.form.push(stop.map(|stop| form_path(&stop.form)));
    }
}

/// One row for each table, the first the table numbered 0, or, in the columns
/// of [`cut_case_columns`], the table numbered `k`. A table whose contents
/// fault holds `fault`, and a relation slot of -1, no columns and no `DET`s.
#[derive(Clone, Debug, Default)]
pub struct TableColumns {
    /// The index in the stream of the token whose step gives the table.
    pub token: Vec<u32>,
    /// The form's `NodePath` as dot-separated indices.
    pub form: Vec<String>,
    /// The [`PointKind`] code.
    pub point: Vec<u8>,
    /// The count of conjuncts and of sites of a body, and 0 and 0 of a
    /// relation.
    pub conjuncts: Vec<u32>,
    pub sites: Vec<u32>,
    /// The relation's slot, and -1 for an evidence table.
    pub relation: Vec<i32>,
    /// The name of the fact relation of an evidence table, as the program
    /// spells it, and `None` for each other table.
    pub fact: Vec<Option<String>>,
    pub column_names: Vec<Vec<String>>,
    /// The name of each column's type, as `ValueType` spells it.
    pub column_types: Vec<Vec<String>>,
    /// The frame that the values of each column stand in, in the order of
    /// `column_names`, and the empty string for a column with no frame:
    ///
    /// - `input`: the frame of the task's input grid, `output`: of its output
    ///   grid;
    /// - `<maker>@<path>`: a frame that a lib column makes, one per row of the
    ///   atom or the instance at `<path>`, as the flows' `atom` spells a path.
    ///   `<maker>` is `<relation>.<column>` for a lib relation or a relation
    ///   macro, such as `relative.X_rel`, and `<component>.<output>.<column>`
    ///   for a component's output, such as `Division.tile.P_inner`;
    /// - `<maker>@<path> in <frame>`: such a frame, lying in `<frame>`, which
    ///   is any of these.
    ///
    /// Only a column of type `Position` or `Box` has a frame. A column whose
    /// sources give no frame, or give two different frames, has none. A
    /// source that gives a frame that no column of the case holds, or that a
    /// D4 element moves, gives an unknown frame, and a column with such a
    /// source has none.
    pub column_frames: Vec<Vec<String>>,
    /// The indexes, in increasing order, of the table's columns of type `Box`
    /// whose frame in `column_frames` is a made frame, empty for every other
    /// table: the columns that each entry's extent run holds extents for.
    pub extent_columns: Vec<Vec<u32>>,
    /// The slot of each column in the relation's own column order, in the
    /// order of `column_names`, and -1 for a column that the engine knows no
    /// slot for. The relation's own order is the order the form gives its
    /// columns, and a record's fields share the slot of their record. The
    /// order of `column_names` is the order the relation stores them in.
    pub column_slots: Vec<Vec<i32>>,
    /// The name of the label that the table's form writes at each column, in
    /// the order of `column_names`, as `arclog::write::label_names` names it
    /// in the decoded program, and the empty string where the form writes none.
    pub column_labels: Vec<Vec<String>>,
    /// The name that the case's `.arclog` text writes for the label of each
    /// column, in the order of `column_names`, and the empty string where the
    /// form writes none. Where the call of [`case_columns`] or
    /// [`cut_case_columns`] gives the label names of the case's stream, the
    /// names are those, and otherwise those of `column_labels`.
    pub column_source_labels: Vec<Vec<String>>,
    /// The width in cells of a row.
    pub width: Vec<u32>,
    /// The relation of each `DET` the table reads, its columns' types, and
    /// the width of its rows.
    pub det_relations: Vec<Vec<String>>,
    pub det_types: Vec<Vec<Vec<String>>>,
    /// The frame of each column of each `DET`, in the order of its types, as
    /// `column_frames` spells it: the frame of that column in the latest
    /// table of the `DET`'s relation, the table itself where it is the
    /// `DET`'s relation's, found by its path in `det_columns`, and empty where
    /// the case holds no such table.
    pub det_frames: Vec<Vec<Vec<String>>>,
    /// The slot and the label of each column of each `DET`, in the order of
    /// its types, as `column_slots` and `column_labels` give them: those of
    /// that column in the latest table of the `DET`'s relation, the table
    /// itself where it is the `DET`'s relation's, found by its path in
    /// `det_columns`, and -1 and the empty string where the case holds no
    /// such table.
    pub det_slots: Vec<Vec<Vec<i32>>>,
    pub det_labels: Vec<Vec<Vec<String>>>,
    /// The name that the case's `.arclog` text writes for the label of each
    /// column of each `DET`, in the order of its types: that of the column
    /// in the latest table of the `DET`'s relation, as `column_source_labels`
    /// gives it, and the empty string where the case holds no such table.
    pub det_source_labels: Vec<Vec<Vec<String>>>,
    pub det_widths: Vec<Vec<u32>>,
    /// The path of each column of each `DET`, in the order of its types: the
    /// names of the path, as `column_spelled` gives them, joined by `.`; the
    /// same for one column of one `DET` relation in every table of a case. Empty
    /// where the program names no columns of the `DET`.
    pub det_columns: Vec<Vec<Vec<String>>>,
    /// The [`ProjectionsKind`] code.
    pub projections: Vec<u8>,
    /// The bound that stopped the projections, and its form.
    pub projections_stop: StopColumns,
    pub fault: Vec<Option<String>>,
    /// The table's depth in the dependency graph: 0 for an evidence table.
    pub depth: Vec<u32>,
    /// The candidate keys the program text or the task's grids give, each a
    /// list of column indexes: the columns of a `ONE` mark, none for `(ONE)`,
    /// the row's columns of a `CHOOSE`, and `E` with `P` of an evidence table.
    /// The registry declares no key of a component's output.
    pub keys: Vec<Vec<Vec<u32>>>,
    /// The index of the Position column that the `OUT` form of the decode
    /// selects in the table of the relation of the atom that selects it, and
    /// of the Color column in the table of the relation of the atom that
    /// selects that one, which map to `P` and `Col` of `ex_output`; -1 for
    /// each other table.
    pub output_position: Vec<i32>,
    pub output_color: Vec<i32>,
}

/// One row for each entry of a table on an example, in the order of the
/// tables, the examples, the assignments and the models.
#[derive(Clone, Debug, Default)]
pub struct EntryColumns {
    /// The number of the table.
    pub table: Vec<u32>,
    /// 0 for the task, 1 for a train example, 2 for a test example.
    pub example_kind: Vec<u8>,
    /// The example's place among the train or the test examples, and 0 for
    /// the task.
    pub example_index: Vec<u32>,
    /// The model's place at its assignment.
    pub model: Vec<u32>,
    /// The [`ValueKind`] code.
    pub kind: Vec<u8>,
    /// The count of rows, and the offset in `values` of the first, of a
    /// `Rows` entry; the count alone of a `Count` entry; 0 and 0 of the rest.
    pub rows: Vec<u64>,
    pub offset: Vec<u64>,
    /// The bound that ended the example's walk of the assignments.
    pub stop: StopColumns,
    /// The bound of a `Stopped` entry.
    pub value_stop: StopColumns,
    /// The fault of the example.
    pub fault: Vec<Option<String>>,
    /// The offset in `values` of the entry's extent run, which holds two cells
    /// for each column of the table's `extent_columns` for each row of the
    /// entry's run, in its order; -1 where the table has no extent columns,
    /// the entry holds no rows, its extents stopped, or `extent_fault` says
    /// why it has none.
    pub extent_offset: Vec<i64>,
    /// The bound that stopped the evaluation of the entry's extents.
    pub extent_stop: StopColumns,
    /// Why the entry has no extent run though it holds rows, where the
    /// extents do not derive its rows: the fault of the widened evaluation at
    /// its form, as `fault` spells a fault, or the reason the extents do not
    /// derive them. `None` otherwise.
    pub extent_fault: Vec<Option<String>>,
}

/// One row for each `DET` of each entry's assignment, in the order of the
/// entries and then of the table's `DET`s. The models of an assignment give
/// one run of rows.
#[derive(Clone, Debug, Default)]
pub struct AssignedColumns {
    /// The row of the entry in [`EntryColumns`].
    pub entry: Vec<u32>,
    /// The `DET`'s place in the table's.
    pub det: Vec<u32>,
    pub rows: Vec<u64>,
    pub offset: Vec<u64>,
}

/// One row for each projection of a table whose projections are found.
#[derive(Clone, Debug, Default)]
pub struct ProjectionColumns {
    pub table: Vec<u32>,
    /// The columns of the table that the projection projects, in increasing order.
    pub columns: Vec<Vec<u32>>,
    /// The width in cells of a projection row.
    pub width: Vec<u32>,
}

/// One row for each projection at each entry of its table.
#[derive(Clone, Debug, Default)]
pub struct ProjectionRowColumns {
    /// The row of the projection in [`ProjectionColumns`].
    pub projection: Vec<u32>,
    /// The row of the entry in [`EntryColumns`].
    pub entry: Vec<u32>,
    /// 0 where the entry holds no rows, and 1 where it gives its projection.
    pub defined: Vec<u8>,
    pub rows: Vec<u64>,
    pub offset: Vec<u64>,
    /// The offset of the extent run of the projection's rows, which holds two
    /// cells for each projection column that the table's `extent_columns` holds, for
    /// each row in its order, a row taking the one extent over the table's rows it
    /// projects; -1 where the row is not defined, none of the projection's
    /// columns is among them, or the entry's extents stopped.
    pub extent_offset: Vec<i64>,
}

/// One row for each source of each column of a table, in the order of the
/// tables, the columns and the sources.
#[derive(Clone, Debug, Default)]
pub struct FlowColumns {
    /// The number of the table.
    pub table: Vec<u32>,
    /// The column's index in the table.
    pub column: Vec<u32>,
    /// The [`SourceKind`] code.
    pub kind: Vec<u8>,
    /// The number of the source's table in the case, the
    /// latest table of the relation before this one; -1 where the case holds
    /// none: a lib relation, a constant, or a lib name.
    pub source_table: Vec<i32>,
    /// The relation read as `relation_spelled` spells it, a fact relation's
    /// name, or the lib name; empty for a constant.
    pub source_relation: Vec<String>,
    /// The source's column index in its relation, -1 for a constant or a lib
    /// name, and -2 for the example of the source's entry.
    pub source_column: Vec<i32>,
    /// The source's place in the table's `det_relations`, -1 where it is
    /// none of them.
    pub det: Vec<i32>,
    /// The path of the atom that reads the source as `form` spells a path,
    /// empty where no atom does.
    pub atom: Vec<String>,
    /// The row of the atom's relation that the value comes from in one
    /// derivation of the table's row ([`ColumnSource::occurrence`]), -1 where
    /// the source claims none.
    pub occurrence: Vec<i32>,
}

/// One row for each declared row of an output that the output's rows break,
/// as [`arclog::eval::copies`] checks it.
#[derive(Clone, Debug, Default)]
pub struct CopyColumns {
    /// The instance, its output, the declared row and the count of rows that
    /// break it, in a sentence.
    pub detail: Vec<String>,
}

/// The tables of one case program as columns.
#[derive(Clone, Debug, Default)]
pub struct CaseColumns {
    pub tables: TableColumns,
    pub entries: EntryColumns,
    pub assigned: AssignedColumns,
    pub projections: ProjectionColumns,
    pub projection_rows: ProjectionRowColumns,
    pub flows: FlowColumns,
    pub copies: CopyColumns,
    pub values: Vec<i32>,
}

impl CaseColumns {
    /// These columns with a row for each of `violations`, the declared rows
    /// that the replay of the case found its constructions' outputs break.
    pub fn with_copies(mut self, violations: &[CopyViolation]) -> CaseColumns {
        self.copies.detail = violations
            .iter()
            .map(|violation| {
                let CopyViolation { form, component, output, row, rows } = violation;
                format!("{}.{} of the instance at {}: {rows} output rows break the declared row {row} of its copies: at the columns it maps they hold the values of no row of its input", component.0, output.0, form_path(form))
            })
            .collect();
        self
    }
}

/// The columns of `evidence`, each at token 0, then of `tables`, each with
/// the index of its token, on a task of `train` train pairs, which names the
/// examples. `labels` are the names that the case's text writes for the
/// labels of its stream, which `column_source_labels` and `det_source_labels`
/// give; with `None` they give the decoded names.
pub fn case_columns(evidence: &[Table], tables: &[(usize, Table)], train: usize, labels: Option<&StreamLabels>) -> CaseColumns {
    fold(evidence, tables, None, train, labels).0
}

/// The exact column fold at a completed program prefix. Cloning preserves
/// row-run interning, so appending produces the same buffers as case_columns.
#[derive(Clone)]
pub struct CaseColumnPrefix {
    columns: CaseColumns,
    names: TableNames,
    runs: Runs,
    count: usize,
}
impl CaseColumnPrefix {
    pub fn new(evidence:&[Table],tables:&[(usize,Table)],train:usize)->Self {
        let mut held=Self {columns:CaseColumns::default(),names:Vec::new(),runs:Runs::default(),count:0};
        push_tables(&mut held.columns,&mut held.names,&mut held.runs,0,evidence.iter().map(|table|(0,table)),train,None);
        held.count=evidence.len();
        held.append(tables,train);
        held
    }
    fn append(&mut self,tables:&[(usize,Table)],train:usize) {
        push_tables(&mut self.columns,&mut self.names,&mut self.runs,self.count,tables.iter().map(|(token,table)|(*token,table)),train,None);
        self.count+=tables.len();
    }
    pub fn finish(&self,tables:&[(usize,Table)],train:usize)->CaseColumns {
        let mut held=self.clone();held.append(tables,train);held.columns
    }
}

/// The columns of the tables of a stream that shares its first `tokens`
/// tokens with a base stream, whose tables with a token below `tokens` are
/// the base's own, and the count `k` of those tables: `evidence` and each
/// table of `tables` whose token is below `tokens`. `tables` stand in the
/// order of their steps. The columns hold the tables from the first at or
/// after `tokens` alone, numbered from `k`, so a flow, an entry or a
/// projection of the columns gives a table by the number it has in the
/// stream's whole list, and a number below `k` names the base's table of that
/// number. The `values` hold the runs of those tables alone, and a table's
/// sources read the tables below `k` as [`case_columns`] reads them. `labels`
/// are as [`case_columns`] takes them.
pub fn cut_case_columns(evidence: &[Table], tables: &[(usize, Table)], tokens: usize, train: usize, labels: Option<&StreamLabels>) -> (CaseColumns, u32) {
    fold(evidence, tables, Some(tokens), train, labels)
}

/// The tables of a stream up to the end of a step, which the tables of the
/// steps after it read for their frames, extents and sources: the state that
/// [`step_case_columns`] takes from a step to the next. It holds the stream's
/// tables so far, each shared, evidence tables excluded, and the count of the
/// tables with the evidence tables.
#[derive(Clone)]
pub struct StreamTables {
    tables: Vec<Arc<Table>>,
    count: u32,
}

impl StreamTables {
    /// The count of the tables so far: the evidence tables and each table of
    /// the steps up to this one.
    pub fn count(&self) -> u32 {
        self.count
    }

    /// The tables of the steps so far, in order, without the evidence tables.
    pub fn tables(&self) -> Vec<&Table> {
        self.tables.iter().map(|table| &**table).collect()
    }
}

/// The columns of the tables of one step, `tables`, on a task of `train`
/// train pairs, and the [`StreamTables`] after them. With `before`, the
/// [`StreamTables`] after the previous step of the stream, the columns hold the
/// step's own tables alone, numbered from the count of the tables before them
/// as [`cut_case_columns`] numbers its tables, and a table's sources read the
/// tables before it as [`case_columns`] reads them. With `None`, the step is
/// the first of the stream and the columns hold the `evidence` tables, at
/// token 0, and then the step's tables, as [`case_columns`] holds them. The
/// names of the labels are the decoded ones, as [`case_columns`] gives with
/// `None` for its `labels`.
pub fn step_case_columns(before: Option<&StreamTables>, evidence: &[Table], tables: Vec<(usize, Table)>, train: usize) -> (CaseColumns, StreamTables) {
    let mut columns = CaseColumns::default();
    let mut runs = Runs::default();
    let mut names = Vec::new();
    let first = match before {
        Some(before) => {
            for (place, table) in evidence.iter().chain(before.tables.iter().map(|table| &**table)).enumerate() {
                note_name(&mut names, u32::try_from(place).expect("fewer than 2^32 tables"), table, None);
            }
            before.count as usize
        }
        None => {
            push_tables(&mut columns, &mut names, &mut runs, 0, evidence.iter().map(|table| (0, table)), train, None);
            evidence.len()
        }
    };
    push_tables(&mut columns, &mut names, &mut runs, first, tables.iter().map(|(token, table)| (*token, table)), train, None);
    let count = u32::try_from(first + tables.len()).expect("fewer than 2^32 tables");
    let kept = before.map_or_else(Vec::new, |before| before.tables.clone()).into_iter().chain(tables.into_iter().map(|(_, table)| Arc::new(table))).collect();
    (columns, StreamTables { tables: kept, count })
}

/// The fold of [`case_columns`] and [`cut_case_columns`]: the only state it
/// keeps across tables is the `names` of the tables so far, with the frames,
/// slots and labels of their columns, and the `Runs` written, so a table's columns depend on its
/// own step and the tables before it. With `cut`, the tables before it are
/// folded into `names` alone, and the count of them is given with the
/// columns.
/// `labels` are as [`case_columns`] takes them.
fn fold(evidence: &[Table], tables: &[(usize, Table)], cut: Option<usize>, train: usize, labels: Option<&StreamLabels>) -> (CaseColumns, u32) {
    let skipped = cut.map_or(0, |tokens| evidence.len() + tables.partition_point(|(token, _)| *token < tokens));
    let mut columns = CaseColumns::default();
    let mut names = Vec::new();
    let mut runs = Runs::default();
    let mut placed = evidence.iter().map(|table| (0, table)).chain(tables.iter().map(|(token, table)| (*token, table)));
    for (place, (_, table)) in placed.by_ref().take(skipped).enumerate() {
        note_name(&mut names, u32::try_from(place).expect("fewer than 2^32 tables"), table, labels);
    }
    push_tables(&mut columns, &mut names, &mut runs, skipped, placed, train, labels);
    (columns, u32::try_from(skipped).expect("fewer than 2^32 tables"))
}

/// The columns of `tables`, each with the index of its token, in `out`, the
/// first of them the table at `first`, after the tables in `names`.
fn push_tables<'t>(out: &mut CaseColumns, names: &mut TableNames, runs: &mut Runs, first: usize, tables: impl Iterator<Item = (usize, &'t Table)>, train: usize, labels: Option<&StreamLabels>) {
    for (place, (token, table)) in (first..).zip(tables) {
        let row = u32::try_from(place).expect("fewer than 2^32 tables");
        push_table(out, names, runs, row, token, table, train, labels);
    }
}

/// The name of each orientation constant by its encoding, the cell of its
/// value, in the order of the encodings.
pub fn orientation_names(registry: &Registry) -> Vec<(i32, String)> {
    let mut names: Vec<(i32, String)> = ORIENTATION_TYPES.iter().flat_map(|&ty| registry.constants_of(ty).each()).map(|constant| (orientation_cell(constant), registry.constant_name(constant).to_owned())).collect();
    names.sort();
    names
}

/// The cells of the constants that each orientation type without a parameter
/// admits as a value, by the type's name, as `encode_data_value` admits them:
/// C4 the registry's C4 constants, each other type the constants of its
/// orientation types.
pub fn orientation_types(registry: &Registry) -> Vec<(String, Vec<i32>)> {
    use ValueType::*;
    [Dir, DiagDir, Dir8, Axis, DiagAxis, Axis4, D4, C4, Sym, Sense]
        .into_iter()
        .map(|ty| {
            let mut cells: Vec<i32> = match ty {
                C4 => registry.c4_constants().each().map(orientation_cell).collect(),
                _ => ty.orientation_types().expect("an orientation type").iter().flat_map(|&of| registry.constants_of(of).each()).map(orientation_cell).collect(),
            };
            cells.sort();
            (format!("{ty:?}"), cells)
        })
        .collect()
}

fn orientation_cell(constant: OrientationConstant) -> i32 {
    cell_of(Term::Constant(Constant::Orientation(constant)))
}

/// The encoding of `term`, the cell of a term that has no number of its own.
fn cell_of(term: Term) -> i32 {
    term.encode().expect("a term that is no Box encodes").encoding() as i32
}

fn form_path(form: &NodePath) -> String {
    form.0.iter().map(|step| step.0.to_string()).collect::<Vec<_>>().join(".")
}

/// A fault as a table's, an entry's or an extent's `fault` spells it:
/// `<message> at <form>`.
pub(crate) fn fault_spelled(fault: &RunFault) -> String {
    format!("{} at {}", fault.message, form_path(&fault.form))
}

fn type_names(types: &[ValueType]) -> Vec<String> {
    types.iter().map(|ty| format!("{ty:?}")).collect()
}

/// The names of a column's path as a file writes them, or their slots, joined
/// by `.`.
fn path_spelled(path: &[ColumnName]) -> String {
    path.iter().map(column_spelled).collect::<Vec<_>>().join(".")
}

/// The width in cells of a row of columns of `types`.
fn row_width(types: &[ValueType]) -> u32 {
    types.iter().map(|ty| if ty.is_box() { 4 } else { 1 }).sum()
}

/// The cells of the term of `id` at a column of type `ty`.
fn push_cells(out: &mut Vec<i32>, id: TermId, ty: &ValueType) {
    match Term::decode(id, ty) {
        Term::Number(number) => out.push(number.0),
        Term::Box(margins) => out.extend([margins.top, margins.bottom, margins.left, margins.right]),
        Term::Constant(Constant::Color(color)) => out.push(i32::from(color.digit())),
        Term::Constant(Constant::Example(example)) => out.push(i32::from(example.index())),
        Term::Constant(Constant::Unit) => out.push(0),
        term @ (Term::Constant(Constant::Orientation(_)) | Term::Ident(_)) => out.push(cell_of(term)),
    }
}

/// The runs written to the `values` of a case, by their count of rows, their
/// count of cells and the hash of their cells: the offsets of the runs with
/// those.
#[derive(Clone, Default)]
struct Runs(
    StableHashMap<(u64, usize, StableHash), Vec<usize>>,
    // Retain the Arc to make allocation identity stable across prefix clones.
    StableHashMap<(usize, Vec<ValueType>), (Arc<Relation>, u64, Arc<[usize]>)>,
);

/// The cells of the rows of `rows`, of columns of `types`, in the order of
/// [`each_row`] ([`row_width`] cells for each row), and the places of the rows
/// in that order, sorted by their cells, rows of equal cells in the order of
/// [`each_row`].
fn sorted_rows(rows: &Relation, types: &[ValueType]) -> (Vec<i32>, Vec<usize>) {
    let width = row_width(types) as usize;
    let count = usize::try_from(rows.len()).expect("a count of rows within a usize");
    let mut written = Vec::with_capacity(count.saturating_mul(width));
    let mut visited = 0;
    each_row(rows, &mut |row| {
        for (&id, ty) in row.iter().zip(types) {
            push_cells(&mut written, id, ty);
        }
        visited += 1;
    });
    let row_cells = |at: usize| &written[at * width..(at + 1) * width];
    let mut order: Vec<usize> = (0..visited).collect();
    order.sort_by(|&a, &b| row_cells(a).cmp(row_cells(b)));
    (written, order)
}

/// The offset of the run of `count` rows with the cells `cells`: where
/// `values` holds a run with the same count of rows and the same cells, that
/// run, and otherwise the run that this call appends to `values`. A run
/// without a cell has offset 0.
fn push_run(values: &mut Vec<i32>, runs: &mut Runs, count: u64, cells: Vec<i32>) -> u64 {
    if cells.is_empty() {
        return 0;
    }
    let mut hasher = StableHasher::new();
    cells.hash(&mut hasher);
    let offsets = runs.0.entry((count, cells.len(), hasher.finish128())).or_default();
    if let Some(&offset) = offsets.iter().find(|&&offset| values[offset..offset + cells.len()] == cells[..]) {
        return offset as u64;
    }
    let offset = values.len();
    offsets.push(offset);
    values.extend(cells);
    offset as u64
}

/// The count of rows, the offset of the run of the rows of `rows`, of
/// columns of `types`, in the order of their cells, as [`push_run`] places it,
/// and the places of the rows in that order, as [`sorted_rows`] gives them.
fn push_rows(values: &mut Vec<i32>, runs: &mut Runs, rows: &Arc<Relation>, types: &[ValueType]) -> (u64, u64, Arc<[usize]>) {
    let key=(Arc::as_ptr(rows) as usize,types.to_vec());
    if let Some((_,offset,order))=runs.1.get(&key) {
        return (order.len() as u64,*offset,Arc::clone(order));
    }
    let (written, order) = sorted_rows(rows, types);
    let width = row_width(types) as usize;
    let count = order.len() as u64;
    let mut cells = Vec::with_capacity(written.len());
    for &at in &order {
        cells.extend_from_slice(&written[at * width..(at + 1) * width]);
    }
    let offset=push_run(values, runs, count, cells);
    let order:Arc<[usize]>=order.into();
    runs.1.insert(key,(Arc::clone(rows),offset,Arc::clone(&order)));
    (count,offset,order)
}

/// The offset of the extent run of the rows that [`push_rows`] gave the places
/// `order` of, as [`push_run`] places it: for each row in that order, the
/// extents `per_row` holds for it (its place in the order of [`each_row`] indexes
/// `per_row`), two cells for each, the frame's count of rows and of columns, or
/// `-1 -1` for none. `order` holds a place at least.
fn push_extents(values: &mut Vec<i32>, runs: &mut Runs, order: &[usize], per_row: &[Box<[Option<Extent>]>]) -> i64 {
    let count = order.len() as u64;
    let cells = order.iter().flat_map(|&at| per_row[at].iter().flat_map(|extent| extent.map_or([-1, -1], |extent| [extent.rows, extent.columns]))).collect();
    i64::try_from(push_run(values, runs, count, cells)).expect("an offset within an i64")
}

/// A table that stands for a relation: the relation as the program spells it,
/// or the fact relation's name, the table's row, the path of each row position of
/// its columns where the relation is a program node, and the frame (empty for
/// none), the slot (-1 for none), the label (empty for none) and the label the
/// case's text writes (empty for none) of each column.
#[derive(Clone)]
pub(crate) struct Named {
    pub(crate) name: String,
    pub(crate) row: u32,
    pub(crate) paths: Option<Vec<Box<[ColumnName]>>>,
    pub(crate) frames: Vec<String>,
    slots: Vec<i32>,
    labels: Vec<String>,
    source_labels: Vec<String>,
}

/// The tables so far that stand for a relation, in the order of the rows.
pub(crate) type TableNames = Vec<Named>;

/// The tables of `earlier`, the tables of a stream before a point in it, as
/// the fold of [`case_columns`] names them after the evidence tables: the
/// evidence tables are the first, and a table of `earlier` stands at its place
/// among them, after the evidence.
pub(crate) fn names_of(registry: &Registry, earlier: &[&Table]) -> TableNames {
    let mut names = Vec::new();
    for (place, table) in evidence_shells(registry).iter().chain(earlier.iter().copied()).enumerate() {
        note_name(&mut names, u32::try_from(place).expect("fewer than 2^32 tables"), table, None);
    }
    names
}

/// The columns of `table`, the table at `row`, after the tables before it.
fn push_table(out: &mut CaseColumns, names: &mut TableNames, runs: &mut Runs, row: u32, token: usize, table: &Table, train: usize, labels: Option<&StreamLabels>) {
    let tables = &mut out.tables;
    tables.token.push(u32::try_from(token).expect("fewer than 2^32 tokens"));
    tables.form.push(form_path(&table.form));
    let (kind, conjuncts, sites) = match table.point {
        Point::Body { conjuncts, sites } => (PointKind::Body, conjuncts, sites),
        Point::Relation => (PointKind::Relation, 0, 0),
        Point::Evidence => (PointKind::Evidence, 0, 0),
    };
    tables.point.push(kind as u8);
    tables.conjuncts.push(conjuncts);
    tables.sites.push(sites);
    match &table.contents {
        Err(fault) => {
            tables.relation.push(-1);
            tables.fact.push(None);
            tables.column_names.push(Vec::new());
            tables.column_types.push(Vec::new());
            tables.column_frames.push(Vec::new());
            tables.extent_columns.push(Vec::new());
            tables.column_slots.push(Vec::new());
            tables.column_labels.push(Vec::new());
            tables.column_source_labels.push(Vec::new());
            tables.width.push(0);
            tables.det_relations.push(Vec::new());
            tables.det_types.push(Vec::new());
            tables.det_frames.push(Vec::new());
            tables.det_slots.push(Vec::new());
            tables.det_labels.push(Vec::new());
            tables.det_source_labels.push(Vec::new());
            tables.det_widths.push(Vec::new());
            tables.det_columns.push(Vec::new());
            tables.projections.push(ProjectionsKind::None as u8);
            tables.projections_stop.push(None);
            tables.fault.push(Some(fault_spelled(fault)));
            tables.depth.push(0);
            tables.keys.push(Vec::new());
            tables.output_position.push(-1);
            tables.output_color.push(-1);
        }
        Ok(contents) => {
            let types: Vec<ValueType> = contents.columns.iter().map(|column| column.ty.clone()).collect();
            let (slot, fact) = match contents.relation {
                TableRelation::Slot(slot) => (i32::try_from(slot).expect("a slot within an i32"), None),
                TableRelation::Fact(fact) => (-1, Some(spelling(FACT_RELATIONS, &fact).to_owned())),
            };
            tables.relation.push(slot);
            tables.fact.push(fact);
            tables.column_names.push(contents.columns.iter().map(|column| column.name.clone()).collect());
            tables.column_types.push(type_names(&types));
            let own = named(row, table, labels);
            let extent_columns = extent_columns(&types, &contents.frames);
            tables.column_frames.push(contents.frames.clone());
            tables.extent_columns.push(extent_columns.clone());
            tables.column_slots.push(slots_of(contents));
            tables.column_labels.push(labels_of(contents));
            tables.column_source_labels.push(source_labels_of(&table.form, contents, labels));
            tables.width.push(row_width(&types));
            tables.det_relations.push(contents.dets.iter().map(|det| relation_spelled(&det.relation)).collect());
            tables.det_types.push(contents.dets.iter().map(|det| type_names(&det.types)).collect());
            let places = det_places(names, own.as_ref(), contents);
            tables.det_frames.push(det_frames(&places, contents));
            tables.det_slots.push(places.iter().map(|det| det.iter().map(|place| place.and_then(|(table, at)| table.slots.get(at).copied()).unwrap_or(-1)).collect()).collect());
            tables.det_labels.push(places.iter().map(|det| det.iter().map(|place| place.and_then(|(table, at)| table.labels.get(at).cloned()).unwrap_or_default()).collect()).collect());
            tables.det_source_labels.push(places.iter().map(|det| det.iter().map(|place| place.and_then(|(table, at)| table.source_labels.get(at).cloned()).unwrap_or_default()).collect()).collect());
            tables.det_widths.push(contents.dets.iter().map(|det| row_width(&det.types)).collect());
            tables.det_columns.push(contents.dets.iter().map(|det| det.columns.iter().flat_map(|paths| paths.iter()).map(|path| path_spelled(path)).collect()).collect());
            let (projections, stop) = match &contents.projections {
                None => (ProjectionsKind::None, None),
                Some(Projections::Stopped(stop)) => (ProjectionsKind::Stopped, Some(stop)),
                Some(Projections::Found(_)) => (ProjectionsKind::Found, None),
            };
            tables.projections.push(projections as u8);
            tables.projections_stop.push(stop);
            tables.fault.push(None);
            tables.depth.push(contents.depth);
            tables.keys.push(contents.keys.iter().map(|key| key.iter().map(|&column| u32::from(column)).collect()).collect());
            tables.output_position.push(contents.selected.position.map_or(-1, i32::from));
            tables.output_color.push(contents.selected.color.map_or(-1, i32::from));
            push_flows(out, names, row, contents);
            names.extend(own);
            push_contents(out, runs, row, contents, &types, &extent_columns, train);
        }
    }
}

/// Adds the relation of `table`, the table at `row`, to `names`, if it stands
/// for one.
fn note_name(names: &mut TableNames, row: u32, table: &Table, labels: Option<&StreamLabels>) {
    names.extend(named(row, table, labels));
}

/// The `Named` of `table`, the table at `row`, with the frames its contents
/// hold: none for a table that stands for no relation, a table of a body or
/// one that has faulted.
fn named(row: u32, table: &Table, labels: Option<&StreamLabels>) -> Option<Named> {
    let Ok(contents) = &table.contents else { return None };
    if matches!(table.point, Point::Body { .. }) {
        return None;
    }
    let name = match contents.relation {
        TableRelation::Slot(_) => contents.name.clone(),
        TableRelation::Fact(fact) => spelling(FACT_RELATIONS, &fact).to_owned(),
    };
    Some(Named { name, row, paths: contents.rows.clone(), frames: contents.frames.clone(), slots: slots_of(contents), labels: labels_of(contents), source_labels: source_labels_of(&table.form, contents, labels) })
}

/// The relation `relation` as the program spells it, a fact relation's name,
/// or the lib name.
pub(crate) fn source_spelled(relation: &RelationRef) -> String {
    match relation {
        RelationRef::Fact(fact) => spelling(FACT_RELATIONS, fact).to_owned(),
        RelationRef::Lib(name) => name.0.to_string(),
        RelationRef::Declared(name) => relation_spelled(&ProgramRelation::Declared(name.clone())),
        RelationRef::Output(name) => relation_spelled(&ProgramRelation::Output(name.clone())),
        RelationRef::DefinedPort(port) => port.0.to_string(),
    }
}

/// Where a source stands in the case: the relation it reads as spelled, the
/// latest table of `names` that stands for it, and its place among the reading
/// table's `DET`s, -1 where it is none of them.
pub(crate) struct Located<'n> {
    pub(crate) spelled: String,
    pub(crate) table: Option<&'n Named>,
    pub(crate) det: i32,
}

/// Where `source` stands, among the tables of `names` and the `DET`s `dets` of
/// the table that reads it. A constant and a lib name stand nowhere.
pub(crate) fn locate<'n>(names: &'n TableNames, dets: &[String], source: &ColumnSource) -> Located<'n> {
    let spelled = source.relation.as_ref().map(source_spelled).unwrap_or_default();
    let (table, det) = match source.kind {
        SourceKind::Copy | SourceKind::Computed => (names.iter().rev().find(|named| named.name == spelled), dets.iter().position(|det| *det == spelled).map_or(-1, |place| place as i32)),
        SourceKind::Constant | SourceKind::LibName => (None, -1),
    };
    Located { spelled, table, det }
}

/// The index of the column of `table` that `source` reads, by the source's path
/// among the table's row positions: `None` where the source or the table gives
/// no path, and `Some(None)` where the table has no such path.
pub(crate) fn position_in(table: &Named, source: &ColumnSource) -> Option<Option<usize>> {
    match (&table.paths, &source.row) {
        (Some(rows), Some(path)) => Some(rows.iter().position(|row| row == path)),
        _ => None,
    }
}

/// The index of the column that `source` reads, in the table `located` gives:
/// the one at the source's path among the table's row positions, or, where the
/// source or the table gives no path and the source is no `DET`'s, the source's
/// own position. `None` where the case does not hold the table or it holds no
/// such column.
pub(crate) fn read_index(located: &Located<'_>, source: &ColumnSource) -> Option<usize> {
    let table = located.table?;
    let SourceColumn::Position(position) = source.column else { return None };
    match position_in(table, source) {
        Some(found) => found,
        None if located.det < 0 => Some(usize::from(position)),
        None => None,
    }
}

/// The frame of the column that `source` reads, in the table `located` gives,
/// or `None` where that column has no frame or the case does not hold it.
fn read_frame(located: &Located<'_>, source: &ColumnSource) -> Option<String> {
    let index = read_index(located, source)?;
    located.table?.frames.get(index).filter(|frame| !frame.is_empty()).cloned()
}

/// The frame that `frame` is, where the source gives it, or `None` where it is
/// unknown. `read` is the frame of the column the source reads. A made frame
/// is spelled with no ` in` where the frame it lies in is unknown or none.
fn resolve_frame(frame: &SourceFrame, read: &Option<String>) -> Option<String> {
    match frame {
        SourceFrame::Read => read.clone(),
        SourceFrame::Unknown => None,
        SourceFrame::Made { maker, at, within } => {
            let made = format!("{}@{}", maker.spelled(), form_path(at));
            Some(match within.as_deref().and_then(|within| resolve_frame(within, read)) {
                Some(within) => format!("{made} in {within}"),
                None => made,
            })
        }
    }
}

/// The frame of each column of `contents`, empty for none: `input` and
/// `output` at `P` of the evidence tables, and, in any other table, for a
/// column of type `Position` or `Box`, the one frame that its sources give,
/// where each source that gives a frame gives one, they all give the same, and
/// none gives an unknown one. A source's frame is resolved in the latest table
/// of `names` that stands for the relation it reads.
pub(crate) fn column_frames(names: &TableNames, contents: &Contents) -> Vec<String> {
    if let TableRelation::Fact(fact) = contents.relation {
        return fact_frames(fact, &contents.columns);
    }
    let dets: Vec<String> = contents.dets.iter().map(|det| relation_spelled(&det.relation)).collect();
    contents
        .columns
        .iter()
        .enumerate()
        .map(|(column, own)| {
            if !has_frame(&own.ty) {
                return String::new();
            }
            let mut found: Vec<String> = Vec::new();
            for source in contents.flows.get(column).into_iter().flatten() {
                let located = locate(names, &dets, source);
                let read = read_frame(&located, source);
                for frame in &source.frames {
                    match resolve_frame(frame, &read) {
                        Some(frame) if found.contains(&frame) => {}
                        Some(frame) => found.push(frame),
                        None => return String::new(),
                    }
                }
            }
            if found.len() == 1 { found.remove(0) } else { String::new() }
        })
        .collect()
}

/// The frame of each column of the table of the fact relation `fact` with
/// `columns`, empty for none: `input` or `output` at `P`.
pub(crate) fn fact_frames(fact: FactRelation, columns: &[TableColumn]) -> Vec<String> {
    let grid = match fact {
        FactRelation::ExOutput => OUTPUT_FRAME,
        FactRelation::Input | FactRelation::ExInput => INPUT_FRAME,
    };
    columns.iter().map(|column| if column.name == "P" && has_frame(&column.ty) { grid.to_owned() } else { String::new() }).collect()
}

/// The slot of each column of `contents`, -1 for none.
fn slots_of(contents: &Contents) -> Vec<i32> {
    contents.columns.iter().map(|column| column.slot.map_or(-1, |slot| i32::try_from(slot).expect("a slot within an i32"))).collect()
}

/// The label of each column of `contents`, empty for none.
fn labels_of(contents: &Contents) -> Vec<String> {
    contents.columns.iter().map(|column| column.label.as_deref().unwrap_or_default().to_owned()).collect()
}

/// The name that the case's text writes for the label of each column of
/// `contents`, the contents of the table at `form`, empty for none. With the
/// names `labels` of the case's stream, a column's name is that of its label
/// at the table's form, and without them, the name the decoded program gives
/// the label.
fn source_labels_of(form: &NodePath, contents: &Contents, labels: Option<&StreamLabels>) -> Vec<String> {
    contents
        .columns
        .iter()
        .map(|column| match (labels, column.label_id) {
            (Some(labels), Some(id)) => written_label(labels, form, id).to_owned(),
            _ => column.label.as_deref().unwrap_or_default().to_owned(),
        })
        .collect()
}

/// The name that the stream's text writes for the decoded label `label` of the
/// table at `form`. The decoder makes the label at each label slot of a form
/// as `LabelId(slot)`, and the form of the table is the form's place in the
/// stream, so `labels` gives the name at that form and slot.
fn written_label<'a>(labels: &'a StreamLabels, form: &NodePath, label: LabelId) -> &'a str {
    let top = form.0.first().expect("a table with a label stands in a top-level form").0 as usize;
    labels.get(top).and_then(|form| form.get(label.0 as usize)).expect("the stream names each label of each form the decode reaches")
}

/// For each column of each `DET` of `contents`, the latest table that stands
/// for the `DET`'s relation, among `names` and `own`, the table of `contents`
/// itself where it stands for one, and the position in it of the column, found
/// by the column's path among the table's row positions; none where the case
/// holds no such table or the path is unknown.
fn det_places<'n>(names: &'n TableNames, own: Option<&'n Named>, contents: &Contents) -> Vec<Vec<Option<(&'n Named, usize)>>> {
    contents
        .dets
        .iter()
        .map(|det| {
            let table = own.into_iter().chain(names.iter().rev()).find(|named| named.name == relation_spelled(&det.relation));
            let place = |index: usize| -> Option<(&'n Named, usize)> {
                let path = det.columns.as_ref()?.get(index)?;
                let table = table?;
                let at = table.paths.as_ref()?.iter().position(|row| row == path)?;
                Some((table, at))
            };
            (0..det.types.len()).map(place).collect()
        })
        .collect()
}

/// The frame of each column of each `DET` of `contents`, empty for none: that
/// of the column at its place in `places` ([`det_places`]), for a type that
/// has a frame.
fn det_frames(places: &[Vec<Option<(&Named, usize)>>], contents: &Contents) -> Vec<Vec<String>> {
    let frame = |place: Option<(&Named, usize)>, ty: &ValueType| -> Option<String> {
        let (table, at) = place.filter(|_| has_frame(ty))?;
        table.frames.get(at).cloned()
    };
    places.iter().zip(&contents.dets).map(|(det, own)| det.iter().zip(own.types.iter()).map(|(place, ty)| frame(*place, ty).unwrap_or_default()).collect()).collect()
}

/// The sources of each column of `contents`, the table at `row`. A source's
/// table is the latest of `names` that stands for its relation.
fn push_flows(out: &mut CaseColumns, names: &TableNames, row: u32, contents: &Contents) {
    let dets: Vec<String> = contents.dets.iter().map(|det| relation_spelled(&det.relation)).collect();
    for (column, sources) in contents.flows.iter().enumerate() {
        for source in sources {
            let ColumnSource { kind, column: source_column, atom, occurrence, .. } = source;
            let Located { spelled, table: source_table, det } = locate(names, &dets, source);
            let table = source_table.map_or(-1, |named| named.row as i32);
            // The source's table was exported with the order its columns had
            // then; a later form may have reordered them. A `DET` source's
            // column indexes the reading table's own `DET` columns.
            let exported = if det < 0 { source_table.and_then(|named| position_in(named, source)) } else { None };
            let flows = &mut out.flows;
            flows.table.push(row);
            flows.column.push(column as u32);
            flows.kind.push(*kind as u8);
            flows.source_table.push(table);
            flows.det.push(det);
            flows.source_relation.push(spelled);
            flows.source_column.push(match source_column {
                SourceColumn::None => -1,
                SourceColumn::Position(position) => match exported {
                    Some(found) => found.map_or(-1, |index| index as i32),
                    None => i32::from(*position),
                },
                SourceColumn::Example => -2,
            });
            flows.atom.push(form_path(atom));
            flows.occurrence.push(occurrence.map_or(-1, i32::from));
        }
    }
}

/// The entries of `contents`, the table at `row`, and its projections;
/// `extent_columns` are the table's columns that its entries hold extents for.
fn push_contents(out: &mut CaseColumns, runs: &mut Runs, row: u32, contents: &Contents, types: &[ValueType], extent_columns: &[u32], train: usize) {
    let count_only = contents.projections.is_some();
    let mut starts = Vec::with_capacity(contents.examples.len());
    for (place, example) in contents.examples.iter().enumerate() {
        starts.push(out.entries.table.len());
        let (kind, index) = match example.example {
            None => (0, 0),
            Some(example) => {
                let index = usize::from(example.index());
                if index < train { (1, index) } else { (2, index - train) }
            }
        };
        let index = u32::try_from(index).expect("fewer than 2^32 examples");
        let push = |out: &mut CaseColumns, runs: &mut Runs, model: u32, value: Option<&RelationValue>, stop: Option<&Stop>, fault: Option<String>, extents: Option<&EntryExtents>| {
            let faulted = fault.is_some();
            let entries = &mut out.entries;
            entries.table.push(row);
            entries.example_kind.push(kind);
            entries.example_index.push(index);
            entries.model.push(model);
            entries.stop.push(stop);
            entries.fault.push(fault);
            let mut order:Arc<[usize]> = Arc::from([]);
            let (value_kind, rows, offset, value_stop) = match value {
                None if faulted => (ValueKind::Fault, 0, 0, None),
                None => (ValueKind::NoEntries, 0, 0, None),
                Some(RelationValue::Rows(rows)) if count_only => (ValueKind::Count, rows.len() as u64, 0, None),
                Some(RelationValue::Rows(rows)) => {
                    let (count, offset, sorted) = push_rows(&mut out.values, runs, rows, types);
                    order = sorted;
                    (ValueKind::Rows, count, offset, None)
                }
                Some(RelationValue::Undefined) => (ValueKind::Undefined, 0, 0, None),
                Some(RelationValue::Stopped(stop)) => (ValueKind::Stopped, 0, 0, Some(stop)),
            };
            let (extent_offset, extent_stop, extent_fault) = match (value, extents) {
                (_, Some(EntryExtents::Stopped(stop))) => (-1, Some(stop), None),
                (_, Some(EntryExtents::Lost(reason))) => (-1, None, Some(reason.clone())),
                (Some(RelationValue::Rows(rows)), Some(EntryExtents::Rows(held))) if !count_only && !rows.is_empty() => (push_extents(&mut out.values, runs, &order, held), None, None),
                _ => (-1, None, None),
            };
            let entries = &mut out.entries;
            entries.kind.push(value_kind as u8);
            entries.rows.push(rows);
            entries.offset.push(offset);
            entries.value_stop.push(value_stop);
            entries.extent_offset.push(extent_offset);
            entries.extent_stop.push(extent_stop);
            entries.extent_fault.push(extent_fault);
        };
        let entry_extents = |at: usize, model: usize| contents.extents.as_ref().and_then(|extents| extents.entry(place, at, model));
        match &example.rows {
            Err(fault) => push(out, runs, 0, None, None, Some(fault_spelled(fault)), None),
            Ok(rows) => {
                if rows.at.is_empty() {
                    push(out, runs, 0, None, rows.stop.as_ref(), None, None);
                }
                for (at, (assigned, models)) in rows.at.iter().enumerate() {
                    let first = out.entries.table.len();
                    for (model, value) in models.iter().enumerate() {
                        push(out, runs, model as u32, Some(value), rows.stop.as_ref(), None, entry_extents(at, model));
                    }
                    let mut assigned_runs = Vec::new();
                    for (position, ((_, det_rows), det)) in assigned.iter().zip(contents.dets.iter()).enumerate() {
                        let (count, offset, _) = push_rows(&mut out.values, runs, det_rows, &det.types);
                        assigned_runs.push((position as u32, count, offset));
                    }
                    for entry in first..out.entries.table.len() {
                        for &(position, count, offset) in &assigned_runs {
                            out.assigned.entry.push(entry as u32);
                            out.assigned.det.push(position);
                            out.assigned.rows.push(count);
                            out.assigned.offset.push(offset);
                        }
                    }
                }
            }
        }
    }
    if let Some(Projections::Found(found)) = &contents.projections {
        let entries = projected_entries(contents);
        for projection in found {
            let projected_columns: Vec<usize> = projection.columns.iter().map(|column| usize::from(column.0)).collect();
            let projection_row = out.projections.table.len() as u32;
            let projection_types: Vec<ValueType> = projection.columns.iter().map(|column| types[column.0 as usize].clone()).collect();
            // The extent columns that the projection holds: each with its place among the table's extent columns.
            let projected_extents: Vec<usize> = projection.columns.iter().filter_map(|column| extent_columns.iter().position(|&held| held == u32::from(column.0))).collect();
            out.projections.table.push(row);
            out.projections.columns.push(projection.columns.iter().map(|column| u32::from(column.0)).collect());
            out.projections.width.push(row_width(&projection_types));
            for (example, assigned) in projection.rows.iter().enumerate() {
                for (at, (_, projection_rows)) in assigned.at.iter().enumerate() {
                    let mut order:Arc<[usize]> = Arc::from([]);
                    let (defined, count, offset) = match projection_rows {
                        None => (0, 0, 0),
                        Some(rows) => {
                            let (count, offset, sorted) = push_rows(&mut out.values, runs, rows, &projection_types);
                            order = sorted;
                            (1, count, offset)
                        }
                    };
                    let extent_offset = match (projection_rows, entries.get(example).and_then(|flat| flat.get(at))) {
                        (Some(rows), Some((RelationValue::Rows(table_rows), Some(EntryExtents::Rows(held))))) if !projected_extents.is_empty() && count > 0 => {
                            let per_row = projected_extent_rows(rows, table_rows, held, &projected_columns, &projected_extents);
                            push_extents(&mut out.values, runs, &order, &per_row)
                        }
                        _ => -1,
                    };
                    out.projection_rows.projection.push(projection_row);
                    out.projection_rows.entry.push((starts[example] + at) as u32);
                    out.projection_rows.defined.push(defined);
                    out.projection_rows.rows.push(count);
                    out.projection_rows.offset.push(offset);
                    out.projection_rows.extent_offset.push(extent_offset);
                }
            }
        }
    }
}

/// For each example of `contents`, its entries in the order of the models of
/// its assignments, as the projections of the example follow them: the value
/// of each and its extents.
fn projected_entries(contents: &Contents) -> Vec<Vec<(&RelationValue, Option<&EntryExtents>)>> {
    let mut entries = Vec::new();
    for (place, example) in contents.examples.iter().enumerate() {
        let mut flat = Vec::new();
        if let Ok(rows) = &example.rows {
            for (at, (_, models)) in rows.at.iter().enumerate() {
                for (model, value) in models.iter().enumerate() {
                    flat.push((value, contents.extents.as_ref().and_then(|extents| extents.entry(place, at, model))));
                }
            }
        }
        entries.push(flat);
    }
    entries
}

/// The extents of each row of `rows`, the projection onto `columns` of the
/// rows `table_rows` of a table, in the order of [`each_row`]: for each of the
/// table's extent columns that `extents` indexes, in its order, the one extent
/// over the table rows that project to the row, as `held` gives their extents
/// in the order of `table_rows`.
fn projected_extent_rows(rows: &Relation, table_rows: &Relation, held: &[Box<[Option<Extent>]>], columns: &[usize], extents: &[usize]) -> Vec<Box<[Option<Extent>]>> {
    let mut merged: StableHashMap<Box<[TermId]>, Vec<Merged>> = StableHashMap::default();
    let mut at = 0;
    each_row(table_rows, &mut |row| {
        let key: Box<[TermId]> = columns.iter().map(|&column| row[column]).collect();
        let slots = merged.entry(key).or_insert_with(|| vec![Merged::Unset; extents.len()]);
        for (slot, &extent) in slots.iter_mut().zip(extents) {
            slot.merge(held[at][extent]);
        }
        at += 1;
    });
    let mut per_row = Vec::new();
    each_row(rows, &mut |row| per_row.push(merged.get(row).map_or_else(|| vec![None; extents.len()].into(), |slots| slots.iter().map(Merged::extent).collect())));
    per_row
}

/// The indexes, in increasing order, of the columns of `types` of type `Box`
/// whose frame in `frames` is a made frame.
pub(crate) fn extent_columns(types: &[ValueType], frames: &[String]) -> Vec<u32> {
    types.iter().zip(frames).enumerate().filter(|(_, (ty, frame))| **ty == ValueType::Box && is_made(frame)).map(|(index, _)| u32::try_from(index).expect("fewer than 2^32 columns")).collect()
}

/// The frame of the task's input grid, and of its output grid, as `column_frames`
/// spells them.
pub(crate) const INPUT_FRAME: &str = "input";
pub(crate) const OUTPUT_FRAME: &str = "output";

/// Whether `frame`, a frame as `column_frames` spells it, is a made frame:
/// `<maker>@<path>`, with or without ` in <frame>`.
fn is_made(frame: &str) -> bool {
    frame.contains('@')
}
