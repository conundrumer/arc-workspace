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
use arclog::eval::join::Materializer;
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
    /// [entry][native sorted row][extent_columns index]: 0=no_grid,
    /// 1=resolved (positive extent pair), 2=unresolved. No renderer inference.
    pub extent_status: Vec<Vec<Vec<u8>>>,
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
    pub extent_status: Vec<Vec<Vec<u8>>>,
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
    /// Reservations follow these owned packed buffers through their last drop.
    pub(crate) allocations: Vec<Arc<arclog::session::SessionAllocation>>,
    pub(crate) packing_stop: Option<Stop>,
}

impl CaseColumns {
    /// A stop reached before packing a native row buffer; no empty value was
    /// substituted. Bindings propagate it to their operation report.
    pub fn packing_stop(&self)->Option<&Stop> {self.packing_stop.as_ref()}
    /// Stable owners for returned Python buffers and captured raw views.
    pub fn allocations(&self)->Vec<Arc<arclog::session::SessionAllocation>> {self.allocations.clone()}
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
    default_materializer(|materializer|case_columns_in(materializer,evidence,tables,train,labels))
}

#[derive(Clone,Copy)]
enum RowExport<'a> {
    Default,
    All,
    Selected(&'a [usize]),
}
impl RowExport<'_> {
    fn full_at(self,entry:usize)->bool {
        match self {Self::Default=>false,Self::All=>true,Self::Selected(entries)=>entries.binary_search(&entry).is_ok()}
    }
}

/// Packs with the caller's CURRENT operation limits and native session.
pub fn case_columns_in(materializer:&Materializer<'_>,evidence:&[Table],tables:&[(usize,Table)],train:usize,labels:Option<&StreamLabels>)->CaseColumns {
    case_columns_with_full_rows_in(materializer,evidence,tables,train,labels,false)
}

/// Packs actual native rows and their extents even when synthesis projections
/// are present. Metadata, projections and bounded admission remain unchanged.
pub fn case_columns_with_full_rows_in(materializer:&Materializer<'_>,evidence:&[Table],tables:&[(usize,Table)],train:usize,labels:Option<&StreamLabels>,full_rows:bool)->CaseColumns {
    fold(materializer,evidence,tables,None,train,labels,if full_rows {RowExport::All} else {RowExport::Default}).0
}

/// Select additional full-row payload by the canonical global entry ordinal.
/// The snapshot owner validates this sorted, unique mask before packing.
pub fn case_columns_selected_entries_in(materializer:&Materializer<'_>,evidence:&[Table],tables:&[(usize,Table)],train:usize,labels:Option<&StreamLabels>,entries:&[usize])->CaseColumns {
    fold(materializer,evidence,tables,None,train,labels,RowExport::Selected(entries)).0
}

// Sessionless public helpers retain the native default caps. Engine operation
// adapters use their explicit current session/limits through the *_in entry.
fn default_materializer<T>(run:impl FnOnce(&Materializer<'_>)->T)->T {
    let session=arclog::session::TaskSession::new(arclog::session::SessionBound {bytes:arclog::session::SESSION_BYTES},arclog::eval::Caps::CORPUS);
    let limits=arclog::eval::Limits::new(None,arclog::eval::Cancellation::default());
    run(&Materializer::new(&session,&limits))
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
    pub fn new(materializer:&Materializer<'_>,evidence:&[Table],tables:&[(usize,Table)],train:usize)->Self {
        let mut held=Self {columns:CaseColumns::default(),names:Vec::new(),runs:Runs::default(),count:0};
        push_tables(materializer,&mut held.columns,&mut held.names,&mut held.runs,0,evidence.iter().map(|table|(0,table)),train,None,RowExport::Default);
        held.count=evidence.len();
        held.append(materializer,tables,train);
        held
    }
    fn append(&mut self,materializer:&Materializer<'_>,tables:&[(usize,Table)],train:usize) {
        push_tables(materializer,&mut self.columns,&mut self.names,&mut self.runs,self.count,tables.iter().map(|(token,table)|(*token,table)),train,None,RowExport::Default);
        self.count+=tables.len();
    }
    pub fn is_complete(&self)->bool {self.columns.packing_stop.is_none()}
    pub fn finish(&self,materializer:&Materializer<'_>,tables:&[(usize,Table)],train:usize)->Option<CaseColumns> {
        if !self.is_complete() {return None;}
        let allocation=materializer.copy(packing_allowance(self.retained_bytes())).ok()?;
        let mut copied=self.clone();
        // This is a deep copy, with its own admission. It does not keep the
        // original prefix's reservations alive after that prefix is evicted.
        copied.columns.allocations=vec![allocation];
        Some(copied.into_finished(materializer,tables,train))
    }
    pub fn into_finished(mut self,materializer:&Materializer<'_>,tables:&[(usize,Table)],train:usize)->CaseColumns {
        self.append(materializer,tables,train);self.columns
    }
    /// Owned capacities, including nested strings, table names, and the
    /// run-interning hash table. The fold holds no native relation Arcs.
    pub fn retained_bytes(&self)->usize {
        std::mem::size_of::<Self>()+packing_bytes(&self.columns,&self.names,&self.runs)
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
    default_materializer(|materializer|cut_case_columns_in(materializer,evidence,tables,tokens,train,labels))
}

/// Cut packing under one current operation and the original native namespace.
pub fn cut_case_columns_in(materializer:&Materializer<'_>,evidence:&[Table],tables:&[(usize,Table)],tokens:usize,train:usize,labels:Option<&StreamLabels>)->(CaseColumns,u32) {
    fold(materializer,evidence,tables,Some(tokens),train,labels,RowExport::Default)
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
    default_materializer(|materializer|step_case_columns_in(materializer,before,evidence,tables,train))
}

/// Step packing under the current operation's native limits.
pub fn step_case_columns_in(materializer:&Materializer<'_>,before:Option<&StreamTables>,evidence:&[Table],tables:Vec<(usize,Table)>,train:usize)->(CaseColumns,StreamTables) {
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
            push_tables(materializer,&mut columns, &mut names, &mut runs, 0, evidence.iter().map(|table| (0, table)), train, None,RowExport::Default);
            evidence.len()
        }
    };
    push_tables(materializer,&mut columns, &mut names, &mut runs, first, tables.iter().map(|(token, table)| (*token, table)), train, None,RowExport::Default);
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
fn fold(materializer:&Materializer<'_>,evidence: &[Table], tables: &[(usize, Table)], cut: Option<usize>, train: usize, labels: Option<&StreamLabels>, row_export:RowExport<'_>) -> (CaseColumns, u32) {
    let skipped = cut.map_or(0, |tokens| evidence.len() + tables.partition_point(|(token, _)| *token < tokens));
    let mut columns = CaseColumns::default();
    let mut names = Vec::new();
    let mut runs = Runs::default();
    let mut placed = evidence.iter().map(|table| (0, table)).chain(tables.iter().map(|(token, table)| (*token, table)));
    for (place, (_, table)) in placed.by_ref().take(skipped).enumerate() {
        note_name(&mut names, u32::try_from(place).expect("fewer than 2^32 tables"), table, labels);
    }
    push_tables(materializer,&mut columns, &mut names, &mut runs, skipped, placed, train, labels,row_export);
    (columns, u32::try_from(skipped).expect("fewer than 2^32 tables"))
}

/// The columns of `tables`, each with the index of its token, in `out`, the
/// first of them the table at `first`, after the tables in `names`.
fn push_tables<'t>(materializer:&Materializer<'_>,out: &mut CaseColumns, names: &mut TableNames, runs: &mut Runs, first: usize, tables: impl Iterator<Item = (usize, &'t Table)>, train: usize, labels: Option<&StreamLabels>, row_export:RowExport<'_>) {
    // A stopped fold is a prefix, including when a previous append stopped.
    // Releasing phase scratch must never admit a later table past a gap.
    if out.packing_stop.is_some() {return;}
    for (place, (token, table)) in (first..).zip(tables) {
        let first_allocation=out.allocations.len();
        let before=packing_bytes(out,names,runs);
        // Headers/count-only entries allocate too, even when there is no row
        // buffer. Admit their physical metadata before any output allocation.
        let allocation=metadata_bytes(materializer,table,names,labels)
            .and_then(|bytes|materializer.copy(bytes.saturating_add(packing_growth(out,names,runs,table))));
        match allocation {
            Ok(allocation)=>out.allocations.push(allocation),
            Err(bound)=>{out.packing_stop=Some(Stop {bound,form:table.form.clone()});break;},
        }
        let row = u32::try_from(place).expect("fewer than 2^32 tables");
        push_table(materializer,out, names, runs, row, token, table, train, labels,row_export);
        // The pointer memo is scratch for this table: release its cloned
        // types, sorted orders and relation/index owners before settlement.
        // Content run interning still spans every table and prefix copy.
        runs.1=StableHashMap::default();
        // push_table has returned: annotation matrices, projection maps and
        // conversion scratch have also dropped.
        // Only this phase's new reservations may shrink; prefix clones and
        // native Contents/matrices keep their independent shared leases.
        let retained=packing_allowance(packing_bytes(out,names,runs).saturating_sub(before));
        settle_packing(&mut out.allocations[first_allocation..],retained);
        if out.packing_stop.is_some() {break;}
    }
}

// The returned Python buffers/lists, their temporary conversion owners and
// the Rust columns coexist. Keep a conservative eight times their measured
// owned capacities; borrowing a native relation adds no copied row storage.
fn packing_bytes(out:&CaseColumns,names:&TableNames,runs:&Runs)->usize {
    out.heap_bytes().saturating_add(names.heap_bytes()).saturating_add(runs.retained_bytes())
        .saturating_add(out.allocations.capacity().saturating_mul(std::mem::size_of::<Arc<arclog::session::SessionAllocation>>()))
}

fn packing_allowance(bytes:usize)->usize {bytes.saturating_mul(8).saturating_add(64*1024)}

fn settle_packing(allocations:&mut [Arc<arclog::session::SessionAllocation>],mut retained:usize) {
    let admitted=allocations.iter().fold(0usize,|bytes,allocation|bytes.saturating_add(allocation.bytes()));
    assert!(admitted>=retained,"packing preflight must cover retained ownership before settlement");
    for allocation in allocations {
        let bytes=allocation.bytes();
        if let Some(allocation)=Arc::get_mut(allocation) {
            allocation.shrink_to(retained);
        }
        retained=retained.saturating_sub(bytes.min(retained));
    }
    assert_eq!(retained,0,"packing settlement must retain its entire allowance");
}

// Forecast only metadata container growth. New nested payloads and row
// buffers keep their existing admissions; values use exact capacity growth.
// Counting model/assignment headers never traverses a factored row product.
fn packing_growth(out:&CaseColumns,names:&TableNames,runs:&Runs,table:&Table)->usize {
    let (mut entries,mut assigned,mut projections,mut projected,mut flows)=(0usize,0usize,0usize,0usize,0usize);
    let mut det_runs=0usize;
    if let Ok(contents)=&table.contents {
        flows=contents.flows.iter().map(Vec::len).sum();
        for example in &contents.examples {match &example.rows {
            Err(_)=>entries=entries.saturating_add(1),
            Ok(rows)=>{
                if rows.at.is_empty() {entries=entries.saturating_add(1);}
                for (assignment,models) in &rows.at {
                    entries=entries.saturating_add(models.len());
                    let dets=assignment.len().min(contents.dets.len());
                    assigned=assigned.saturating_add(models.len().saturating_mul(dets));
                    det_runs=det_runs.saturating_add(dets);
                }
            },
        }}
        if let Some(Projections::Found(found))=&contents.projections {
            projections=found.len();
            for projection in found {for example in &projection.rows {projected=projected.saturating_add(example.at.len());}}
        }
    }
    let new_runs=entries.saturating_mul(2).saturating_add(det_runs).saturating_add(projected.saturating_mul(2));
    let allocations=new_runs.saturating_add(1);
    let mut bytes=out.tables.growth_bytes(1).saturating_add(names.growth_bytes(1))
        .saturating_add(out.entries.growth_bytes(entries)).saturating_add(out.assigned.growth_bytes(assigned))
        .saturating_add(out.projections.growth_bytes(projections)).saturating_add(out.projection_rows.growth_bytes(projected))
        .saturating_add(out.flows.growth_bytes(flows)).saturating_add(out.allocations.growth_bytes(allocations));
    if runs.0.len().saturating_add(new_runs)>runs.0.capacity() {
        // Hash capacity is bounded by twice the requested entries; the
        // footprint estimator itself allows two bucket widths per entry.
        let buckets=runs.0.len().saturating_add(new_runs).checked_next_power_of_two().unwrap_or(usize::MAX).saturating_mul(2);
        bytes=bytes.saturating_add(buckets.saturating_mul(2*std::mem::size_of::<((u64,usize,StableHash),Vec<usize>)>()));
    }
    packing_allowance(bytes)
}

// Conservative simultaneous Rust/Python metadata ownership, independent of
// logical row cardinality. Includes output dictionaries, dtype keys, the two
// owner types/closures, vector growth and nested list/string copies. Row cells
// and extent matrices have their own admissions. No Cartesian traversal here.
fn metadata_bytes(materializer:&Materializer<'_>,table:&Table,names:&TableNames,labels:Option<&StreamLabels>)->Result<usize,arclog::eval::ReachedBound> {
    materializer.check()?;
    let mut bytes=64usize.saturating_mul(1024).saturating_add(table.form.0.len().saturating_mul(256));
    let Ok(contents)=&table.contents else {return Ok(bytes.saturating_add(table.contents.as_ref().err().map_or(0,|f|f.message.len().saturating_mul(8))));};
    let mut add=|value:usize|bytes=bytes.saturating_add(value);
    add(contents.name.len().saturating_mul(8));
    for column in &contents.columns {add(2048usize.saturating_add(column.name.len().saturating_mul(8)).saturating_add(column.label.as_ref().map_or(0,|s|s.len().saturating_mul(8))));}
    for frame in &contents.frames {add(1024usize.saturating_add(frame.len().saturating_mul(8)));}
    // A DET copies metadata from its referenced table only. Charging the
    // entire preceding name index per DET makes unrelated earlier tables
    // consume the bound again at every later table. Keep the conservative
    // source-table allowance, using the same lookup as the header writer.
    let own=if matches!(table.point,Point::Body {..}) {None} else {
        Some((table_name(contents),own_header_bytes(&table.form,contents,labels)))
    };
    for det in &contents.dets {
        if let Some(bytes)=det_table(names,own,&det.relation,HeapBytes::heap_bytes) {add(bytes.saturating_mul(8));}
        add(2048usize.saturating_add(det.types.len().saturating_mul(2048)).saturating_add(det.columns.heap_bytes().saturating_mul(8)));
    }
    for key in &contents.keys {add(256usize.saturating_add(key.len().saturating_mul(32)));}
    for sources in &contents.flows {for source in sources {add(2048usize.saturating_add(source.row.heap_bytes().saturating_mul(8)).saturating_add(source.atom.0.len().saturating_mul(256)));}}
    for example in &contents.examples {
        materializer.check()?;
        match &example.rows {
            Err(fault)=>add(4096usize.saturating_add(fault.message.len().saturating_mul(8))),
            Ok(assigned)=>for (_,models) in &assigned.at {
                materializer.check()?;
                add(models.len().max(1).saturating_mul(4096usize.saturating_add(contents.dets.len().saturating_mul(2048))));
            },
        }
    }
    if let Some(Projections::Found(projections))=&contents.projections {for projection in projections {
        materializer.check()?;
        add(4096usize.saturating_add(projection.columns.len().saturating_mul(256)));
        for example in &projection.rows {add(example.at.len().saturating_mul(4096));}
    }}
    Ok(bytes)
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

impl Runs {
    fn retained_bytes(&self)->usize {
        self.0.capacity().saturating_mul(2*std::mem::size_of::<((u64,usize,StableHash),Vec<usize>)>())
            .saturating_add(self.0.values().map(HeapBytes::heap_bytes).sum::<usize>())
    }
}

/// The cells of the rows of `rows`, of columns of `types`, in the order of
/// [`arclog::eval::join::each_row`] ([`row_width`] cells for each row), and the places of the rows
/// in that order, sorted by their cells, rows of equal cells in the order of
/// [`arclog::eval::join::each_row`].
fn sorted_rows(materializer:&Materializer<'_>,rows: &Relation, types: &[ValueType]) -> Result<(Vec<i32>, Vec<usize>),arclog::eval::ReachedBound> {
    assert_eq!(usize::from(rows.arity()), types.len(), "native relation arity differs from its packed schema");
    let width = row_width(types) as usize;
    let count = usize::try_from(rows.len()).expect("a count of rows within a usize");
    let mut written = Vec::with_capacity(count.saturating_mul(width));
    let mut visited = 0;
    materializer.walk(rows, &mut |row| {
        for (&id, ty) in row.iter().zip(types) {
            push_cells(&mut written, id, ty);
        }
        visited += 1;
    })?;
    materializer.check()?;
    let row_cells = |at: usize| &written[at * width..(at + 1) * width];
    let mut order: Vec<usize> = (0..visited).collect();
    order.sort_by(|&a, &b| row_cells(a).cmp(row_cells(b)));
    materializer.check()?;
    Ok((written, order))
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
    values.reserve_exact(cells.len());
    values.extend(cells);
    offset as u64
}

/// The count of rows, the offset of the run of the rows of `rows`, of
/// columns of `types`, in the order of their cells, as [`push_run`] places it,
/// and the places of the rows in that order, as [`sorted_rows`] gives them.
fn push_rows(materializer:&Materializer<'_>,allocations:&mut Vec<Arc<arclog::session::SessionAllocation>>,values: &mut Vec<i32>, runs: &mut Runs, rows: &Arc<Relation>, types: &[ValueType]) -> Result<(u64, u64, Arc<[usize]>),arclog::eval::ReachedBound> {
    let key=(Arc::as_ptr(rows) as usize,types.to_vec());
    if let Some((_,offset,order))=runs.1.get(&key) {
        return Ok((order.len() as u64,*offset,Arc::clone(order)));
    }
    // Admit BEFORE full product flattening, sorting, copies or Vec reserve.
    let payload=(row_width(types) as usize).saturating_mul(32).saturating_add(32);
    let allocation=materializer.admit(rows,Materializer::row_bytes(payload,4))?;
    let (written, order) = sorted_rows(materializer,rows, types)?;
    let width = row_width(types) as usize;
    let count = order.len() as u64;
    let mut cells = Vec::with_capacity(written.len());
    for &at in &order {
        cells.extend_from_slice(&written[at * width..(at + 1) * width]);
    }
    let offset=push_run(values, runs, count, cells);
    let order:Arc<[usize]>=order.into();
    runs.1.insert(key,(Arc::clone(rows),offset,Arc::clone(&order)));
    allocations.push(allocation);
    Ok((count,offset,order))
}

/// The offset of the extent run of the rows that [`push_rows`] gave the places
/// `order` of, as [`push_run`] places it: for each row in that order, the
/// extents `per_row` holds for it (its place in the order of [`arclog::eval::join::each_row`] indexes
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
fn push_table(materializer:&Materializer<'_>,out: &mut CaseColumns, names: &mut TableNames, runs: &mut Runs, row: u32, token: usize, table: &Table, train: usize, labels: Option<&StreamLabels>, row_export:RowExport<'_>) {
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
            push_contents(materializer,&table.form,out, runs, row, contents, &types, &extent_columns, train,row_export);
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
    let name = table_name(contents).to_owned();
    Some(Named { name, row, paths: contents.rows.clone(), frames: contents.frames.clone(), slots: slots_of(contents), labels: labels_of(contents), source_labels: source_labels_of(&table.form, contents, labels) })
}

fn table_name(contents:&Contents)->&str {
    match contents.relation {
        TableRelation::Slot(_)=>&contents.name,
        TableRelation::Fact(fact)=>spelling(FACT_RELATIONS,&fact),
    }
}

// Size the current Named's source metadata without building it before
// admission. Include both label spellings: file labels can differ in size.
// The caller's source allowance covers native/Python copies and Vec growth.
fn own_header_bytes(form:&NodePath,contents:&Contents,labels:Option<&StreamLabels>)->usize {
    let mut bytes=table_name(contents).len().saturating_add(contents.rows.heap_bytes()).saturating_add(contents.frames.heap_bytes());
    for column in &contents.columns {
        let label=column.label.as_deref().unwrap_or_default();
        let source=match (labels,column.label_id) {
            (Some(labels),Some(id))=>written_label(labels,form,id),
            _=>label,
        };
        bytes=bytes.saturating_add(2*std::mem::size_of::<String>()+std::mem::size_of::<i32>()+96)
            .saturating_add(label.len()).saturating_add(source.len());
    }
    bytes
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

/// Select the current table first, then the latest earlier table. Both
/// header placement and pre-admission sizing use this precedence; sizing
/// supplies the current table's byte count without allocating its Named.
fn det_table<'n,T>(names: &'n TableNames, own: Option<(&str,T)>, relation: &ProgramRelation, earlier: impl FnOnce(&'n Named)->T) -> Option<T> {
    let name=relation_spelled(relation);
    if let Some((own_name,own))=own {if own_name==name {return Some(own);}}
    names.iter().rev().find(|named|named.name==name).map(earlier)
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
            let table = det_table(names, own.map(|own|(own.name.as_str(),own)), &det.relation, |named|named);
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

// Each annotation output is genuine ownership even when its value run was
// interned earlier. Cover simultaneous per-row scratch, sorted extent/status
// copies and Python containers; retain the lease on the returned CaseColumns.
fn annotation_copy(materializer:&Materializer<'_>,allocations:&mut Vec<Arc<arclog::session::SessionAllocation>>,rows:&Relation,columns:usize)->Result<(),arclog::eval::ReachedBound> {
    let allocation=materializer.admit(rows,Materializer::row_bytes(columns.saturating_mul(128),8))?;
    allocations.push(allocation);
    Ok(())
}

/// The entries of `contents`, the table at `row`, and its projections;
/// `extent_columns` are the table's columns that its entries hold extents for.
fn push_contents(materializer:&Materializer<'_>,form:&NodePath,out: &mut CaseColumns, runs: &mut Runs, row: u32, contents: &Contents, types: &[ValueType], extent_columns: &[u32], train: usize, row_export:RowExport<'_>) {
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
        let push = |out: &mut CaseColumns, runs: &mut Runs, at_assignment:usize, model: u32, value: Option<&RelationValue>, stop: Option<&Stop>, fault: Option<String>, extents: Option<&EntryExtents>| {
            let count_only=contents.projections.is_some() && !row_export.full_at(out.entries.table.len());
            let faulted = fault.is_some();
            let entries = &mut out.entries;
            entries.table.push(row);
            entries.example_kind.push(kind);
            entries.example_index.push(index);
            entries.model.push(model);
            entries.stop.push(stop);
            entries.fault.push(fault);
            let mut order:Arc<[usize]> = Arc::from([]);
            let packing_stop;
            let (value_kind, rows, offset, value_stop) = match value {
                None if faulted => (ValueKind::Fault, 0, 0, None),
                None => (ValueKind::NoEntries, 0, 0, None),
                Some(RelationValue::Rows(rows)) if count_only => (ValueKind::Count, rows.len() as u64, 0, None),
                Some(RelationValue::Rows(rows)) => {
                    match push_rows(materializer,&mut out.allocations,&mut out.values,runs,rows,types) {
                        Ok((count,offset,sorted))=>{order=sorted;(ValueKind::Rows,count,offset,None)},
                        Err(bound)=>{
                            packing_stop=Some(Stop {bound,form:form.clone()});
                            out.packing_stop=packing_stop.clone();
                            (ValueKind::Stopped,rows.len(),0,packing_stop.as_ref())
                        }
                    }
                }
                Some(RelationValue::Undefined) => (ValueKind::Undefined, 0, 0, None),
                Some(RelationValue::Stopped(stop)) => (ValueKind::Stopped, 0, 0, Some(stop)),
            };
            let annotation_stop;
            let (mut extent_offset, mut extent_stop, extent_fault) = match (value, extents) {
                (_, Some(EntryExtents::Stopped(stop))) => (-1, Some(stop), None),
                (_, Some(EntryExtents::Lost(reason))) => (-1, None, Some(reason.clone())),
                (Some(RelationValue::Rows(rows)), Some(EntryExtents::Rows(_held))) if !count_only && !rows.is_empty() => (-1, None, None),
                _ => (-1, None, None),
            };
            let extent_status = if let Some(RelationValue::Rows(relation)) = value {
                if count_only || matches!(value_kind,ValueKind::Stopped) || relation.is_empty() || extent_columns.is_empty() {Vec::new()} else {
                    // Native annotation has each_row order; export in exactly
                    // the same sorted row order as this entry's value buffer.
                    let annotated=annotation_copy(materializer,&mut out.allocations,relation,extent_columns.len())
                        .map_err(|bound|Stop {bound,form:form.clone()})
                        .and_then(|()|crate::extents::annotated_rows(materializer,form,contents,place,at_assignment,model as usize,relation));
                    match annotated {
                        Ok(cells)=>{
                            let per_row=cells.iter().map(|r|r.iter().map(|(_,e)|*e).collect::<Box<[_]>>()).collect::<Vec<_>>();
                            extent_offset=push_extents(&mut out.values,runs,&order,&per_row);
                            order.iter().map(|i|cells[*i].iter().map(|(status,_)|*status).collect()).collect()
                        }
                        // The exact stop is already held in extent_stop above;
                        // values remain native, without an invented annotation.
                        Err(stop)=>{annotation_stop=stop;extent_stop=Some(&annotation_stop);out.packing_stop=Some(annotation_stop.clone());Vec::new()},
                    }
                }
            } else {Vec::new()};
            let entries = &mut out.entries;
            entries.extent_status.push(extent_status);
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
            Err(fault) => push(out, runs, 0, 0, None, None, Some(fault_spelled(fault)), None),
            Ok(rows) => {
                if rows.at.is_empty() {
                    push(out, runs, 0, 0, None, rows.stop.as_ref(), None, None);
                }
                for (at, (assigned, models)) in rows.at.iter().enumerate() {
                    let first = out.entries.table.len();
                    for (model, value) in models.iter().enumerate() {
                        push(out, runs, at, model as u32, Some(value), rows.stop.as_ref(), None, entry_extents(at, model));
                    }
                    let mut assigned_runs = Vec::new();
                    for (position, ((_, det_rows), det)) in assigned.iter().zip(contents.dets.iter()).enumerate() {
                        match push_rows(materializer,&mut out.allocations,&mut out.values,runs,det_rows,&det.types) {
                            Ok((count,offset,_))=>assigned_runs.push((position as u32,count,offset)),
                            Err(bound)=>{
                                let stop=Stop {bound,form:form.clone()};out.packing_stop=Some(stop.clone());
                                for entry in first..out.entries.table.len() {
                                    out.entries.kind[entry]=ValueKind::Stopped as u8;
                                    out.entries.value_stop.bound[entry]=Some(format!("{:?}",stop.bound));
                                    out.entries.value_stop.form[entry]=Some(form_path(form));
                                }
                            }
                        }
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
                            match push_rows(materializer,&mut out.allocations,&mut out.values,runs,rows,&projection_types) {
                                Ok((count,offset,sorted))=>{order=sorted;(1,count,offset)},
                                Err(bound)=>{out.packing_stop=Some(Stop {bound,form:form.clone()});(0,0,0)},
                            }
                        }
                    };
                    let annotation=(||->Result<(i64,Vec<Vec<u8>>),arclog::eval::ReachedBound> {
                    if count>0 && !projected_extents.is_empty() {if let Some(rows)=projection_rows {
                        annotation_copy(materializer,&mut out.allocations,rows,projected_extents.len())?;
                    }}
                    let result=match (projection_rows, entries.get(example).and_then(|flat| flat.get(at))) {
                        (Some(rows), Some((RelationValue::Rows(table_rows), Some(EntryExtents::Rows(held))))) if !projected_extents.is_empty() && count > 0 => {
                            let per_row = projected_extent_rows(materializer,rows, table_rows, held, &projected_columns, &projected_extents)?;
                            let status=order.iter().map(|i|per_row[*i].iter().enumerate().map(|(k,e)| {
                                let no_grid=contents.extents.as_ref().is_some_and(|x|x.no_grid[projected_extents[k]]);
                                if no_grid {0} else if e.is_some() {1} else {2}
                            }).collect()).collect();
                            (push_extents(&mut out.values, runs, &order, &per_row),status)
                        }
                        (Some(rows),_) if count>0 && !projected_extents.is_empty()=> {
                            let mut per_row=Vec::new();
                            materializer.walk(rows,&mut |row|per_row.push(projection.columns.iter().enumerate().filter_map(|(j,c)| {
                                let k=extent_columns.iter().position(|i|*i==u32::from(c.0))?;
                                let no_grid=contents.extents.as_ref().is_some_and(|x|x.no_grid[k]) || projection_types[j]==ValueType::Offset;
                                Some(if no_grid {None} else if projection_types[j]==ValueType::Position {crate::extents::position_extent(row[j],&ValueType::Position)} else {None})
                            }).collect::<Box<[_]>>()))?;
                            let status=order.iter().map(|i|per_row[*i].iter().enumerate().map(|(k,e)| {
                                if contents.extents.as_ref().is_some_and(|x|x.no_grid[projected_extents[k]]) {0} else if e.is_some(){1}else{2}
                            }).collect()).collect();
                            (push_extents(&mut out.values,runs,&order,&per_row),status)
                        }
                        _=>(-1,Vec::new()),
                    };
                    materializer.check()?;
                    Ok(result)
                    })();
                    let (extent_offset,extent_status)=match annotation {
                        Ok(value)=>value,
                        Err(bound)=>{out.packing_stop=Some(Stop {bound,form:form.clone()});(-1,Vec::new())},
                    };
                    out.projection_rows.extent_status.push(extent_status);
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
/// rows `table_rows` of a table, in the order of [`arclog::eval::join::each_row`]: for each of the
/// table's extent columns that `extents` indexes, in its order, the one extent
/// over the table rows that project to the row, as `held` gives their extents
/// in the order of `table_rows`.
fn projected_extent_rows(materializer:&Materializer<'_>,rows: &Relation, table_rows: &Relation, held: &[Box<[Option<Extent>]>], columns: &[usize], extents: &[usize]) -> Result<crate::extents::Materialized<Vec<Box<[Option<Extent>]>>>,arclog::eval::ReachedBound> {
    // The full matrix is already admitted, but this hash map is a genuine
    // additional allocation. Its lease lasts until the projected matrix is
    // built; the returned matrix has its own retained lease.
    let payload=columns.len().saturating_mul(std::mem::size_of::<TermId>()).saturating_add(extents.len().saturating_mul(std::mem::size_of::<Merged>())).saturating_mul(4);
    let _map_allocation=materializer.admit(table_rows,Materializer::row_bytes(payload,4))?;
    let allocation=materializer.admit(rows,Materializer::row_bytes(extents.len().saturating_mul(std::mem::size_of::<Option<Extent>>()),1))?;
    let mut merged: StableHashMap<Box<[TermId]>, Vec<Merged>> = StableHashMap::default();
    let mut at = 0;
    materializer.walk(table_rows, &mut |row| {
        let key: Box<[TermId]> = columns.iter().map(|&column| row[column]).collect();
        let slots = merged.entry(key).or_insert_with(|| vec![Merged::Unset; extents.len()]);
        for (slot, &extent) in slots.iter_mut().zip(extents) {
            slot.merge(held[at][extent]);
        }
        at += 1;
    })?;
    let mut per_row = Vec::new();
    materializer.walk(rows, &mut |row| per_row.push(merged.get(row).map_or_else(|| vec![None; extents.len()].into(), |slots| slots.iter().map(Merged::extent).collect())))?;
    Ok(crate::extents::Materialized::new(per_row,allocation))
}

/// Every geometric scalar column in native row order. A missing global
/// frame name is not a reason to omit per-cell extent/status evidence.
pub(crate) fn extent_columns(types: &[ValueType], frames: &[String]) -> Vec<u32> {
    let _ = frames;
    types.iter().enumerate().filter(|(_,ty)|ty.is_box()).map(|(index,_)|index as u32).collect()
}

/// The frame of the task's input grid, and of its output grid, as `column_frames`
/// spells them.
pub(crate) const INPUT_FRAME: &str = "input";
pub(crate) const OUTPUT_FRAME: &str = "output";

// Capacity accounting for the owned column fold. Scalar storage is charged by
// its enclosing vector; each nested allocation includes allocator slack.
trait HeapBytes {fn heap_bytes(&self)->usize;}
trait ColumnGrowth {fn growth_bytes(&self,additional:usize)->usize;}
macro_rules! scalar_heap {($($ty:ty),*)=>{$(
    impl HeapBytes for $ty {fn heap_bytes(&self)->usize {0}}
    impl ColumnGrowth for $ty {fn growth_bytes(&self,_additional:usize)->usize {0}}
)*};}
scalar_heap!(u8,u32,i32,u64,i64,usize);
impl HeapBytes for String {fn heap_bytes(&self)->usize {self.capacity()+usize::from(self.capacity()>0)*32}}
impl ColumnGrowth for String {fn growth_bytes(&self,_additional:usize)->usize {0}}
impl<T> ColumnGrowth for Vec<T> {
    fn growth_bytes(&self,additional:usize)->usize {
        let needed=self.len().saturating_add(additional);
        if needed<=self.capacity() {0} else {
            self.capacity().saturating_mul(2).max(needed).max(8).saturating_mul(std::mem::size_of::<T>()).saturating_add(32)
        }
    }
}
impl<T> ColumnGrowth for Option<T> {fn growth_bytes(&self,_additional:usize)->usize {0}}
impl<T:HeapBytes> HeapBytes for Vec<T> {
    fn heap_bytes(&self)->usize {self.capacity()*std::mem::size_of::<T>()+usize::from(self.capacity()>0)*32+self.iter().map(HeapBytes::heap_bytes).sum::<usize>()}
}
impl<T:HeapBytes> HeapBytes for Box<[T]> {
    fn heap_bytes(&self)->usize {std::mem::size_of_val(&**self)+32+self.iter().map(HeapBytes::heap_bytes).sum::<usize>()}
}
impl<T:HeapBytes> HeapBytes for Option<T> {fn heap_bytes(&self)->usize {self.as_ref().map_or(0,HeapBytes::heap_bytes)}}
impl HeapBytes for ColumnName {fn heap_bytes(&self)->usize {match self {ColumnName::Written(name)=>name.len()+32,ColumnName::Slot(_)=>0}}}
macro_rules! fields_heap {
    ($ty:ty;$($field:ident),*)=>{
        impl HeapBytes for $ty {fn heap_bytes(&self)->usize {0 $(+self.$field.heap_bytes())*}}
        impl ColumnGrowth for $ty {fn growth_bytes(&self,additional:usize)->usize {0usize $(.saturating_add(self.$field.growth_bytes(additional)))*}}
    };
}
fields_heap!(StopColumns;bound,form);
fields_heap!(TableColumns;token,form,point,conjuncts,sites,relation,fact,column_names,column_types,column_frames,extent_columns,column_slots,column_labels,column_source_labels,width,det_relations,det_types,det_frames,det_slots,det_labels,det_source_labels,det_widths,det_columns,projections,projections_stop,fault,depth,keys,output_position,output_color);
fields_heap!(EntryColumns;table,example_kind,example_index,model,kind,rows,offset,stop,value_stop,fault,extent_offset,extent_stop,extent_fault,extent_status);
fields_heap!(AssignedColumns;entry,det,rows,offset);
fields_heap!(ProjectionColumns;table,columns,width);
fields_heap!(ProjectionRowColumns;projection,entry,defined,rows,offset,extent_offset,extent_status);
fields_heap!(FlowColumns;table,column,kind,source_table,source_relation,source_column,det,atom,occurrence);
fields_heap!(CopyColumns;detail);
fields_heap!(CaseColumns;tables,entries,assigned,projections,projection_rows,flows,copies,values);
fields_heap!(Named;name,row,paths,frames,slots,labels,source_labels);
