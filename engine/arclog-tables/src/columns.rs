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
//! encoding, which [`orientation_names`] names. An Ident is the first 32 bits
//! of its member digest ([`arclog::terms::InternTable::digest`]), so it is
//! equal for equal sets in every run. A run is an offset in `values` and a
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

use arclog::decode::{Assigned, Projection, Projections};
use arclog::eval::copies::CopyViolation;
use arclog::eval::determinations::relation_spelled;
use arclog::eval::join::Materializer;
use arclog::eval::{RelationValue, RunFault, Stop};
use arclog::hash::{StableHash, StableHashMap, StableHashSet, StableHasher};
use arclog::program::path::NodePath;
use arclog::program::{column_spelled, ColumnName, FactRelation, LabelId, ProgramRelation, RelationRef};
use arclog::read::spelling::{spelling, FACT_RELATIONS};
use arclog::registry::{has_frame, Registry};
use arclog::relations::{ColumnIndex, Relation, RelationPart};
use arclog::stream::corpus::StreamLabels;
use arclog::terms::{Constant, Ident, OrientationConstant, Term, TermId, ORIENTATION_TYPES};
use arclog::types::ValueType;
use arclog::types::{IdentSource, SourceId};

use crate::extents::{EntryExtents, Extent, ExtentRows, Merged};
use crate::flows::{ColumnSource, SourceColumn, SourceFrame, SourceKind};
use crate::split::{self, Part};
use crate::summary::{bound_name, evidence_key, summarize_cached, summarize_hashes_cached, Assemblies, DetFulls, SummaryCache, SummaryKey, TableSummary};
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
    /// The count of rows alone, with the row payload omitted by export policy.
    Count = 1,
    Undefined = 2,
    /// The bound that stopped the enumeration of models, in `value_stop`.
    Stopped = 3,
    /// The example's fault: the example has no other entry.
    Fault = 4,
    /// The example has no entry, and its stop stands in `stop`.
    NoEntries = 5,
    /// The export by assignment, called without rows: the count of rows in
    /// `rows` and the hash of the Rows in `hash`, with no row cells. This
    /// export has no [`ValueKind::Count`] entry.
    NotExported = 6,
}

/// A bound that stopped a walk, and the form that reached it, as the
/// bound's name and the form's path.
#[derive(Clone, Debug, Default)]
pub struct StopColumns {
    pub bound: Vec<Option<String>>,
    pub form: Vec<Option<String>>,
    /// Whether the bound rejects one assignment alone
    /// ([`arclog::eval::ReachedBound::is_assignment`]); false where there is
    /// no bound.
    pub assignment: Vec<bool>,
}

impl StopColumns {
    fn push(&mut self, stop: Option<&Stop>) {
        self.bound.push(stop.map(|stop| format!("{:?}", stop.bound)));
        self.form.push(stop.map(|stop| form_path(&stop.form)));
        self.assignment.push(stop.is_some_and(|stop| stop.bound.is_assignment()));
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
    /// The source of each Ident in each column's type, in the order of
    /// `column_names`: the form that makes the Ident values
    /// ([`arclog::types::IdentSource`]), as the 32 hexadecimal digits of its
    /// identity, which is a hash of the maker form's resolved content and its
    /// output port. The TableHash holds no source. A Record type gives the sources of its fields in
    /// their order, joined by `,`. The empty string for a type with no Ident
    /// of a source, such as an Ident that an input names. Two columns hold
    /// Idents of one source where `column_types` and this are equal.
    pub column_ident_sources: Vec<Vec<String>>,
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
    /// The identity of each table, as 32 hexadecimal digits, and the empty
    /// string for a table that has none. Given only where the call that makes
    /// the columns gives identities ([`CaseColumns::with_identities`]); empty
    /// otherwise. Two tables of any two case programs have one identity where
    /// the resolved contents of their queries are equal, whatever names the
    /// programs declare and in whatever order they write their forms,
    /// conjuncts, branches and columns ([`crate::identity`]).
    pub ident: Vec<String>,
    /// The identity of each column of each table, in the order of
    /// `column_names`: the lib's column name for a column the lib declares;
    /// `<lib column>.#<n>` for a field of the record of a lib column, with `n`
    /// the canonical position of the field's label (the least position of the
    /// labels that several heads bind to it); and `#<n>` for any other
    /// column, with `n` the canonical position of its label. No identity holds
    /// a name that the program's author chose. The identities of the columns
    /// of a table differ. Given as `ident` is.
    pub column_idents: Vec<Vec<String>>,
    /// The bodies that the evaluator joins for each table, as JSON
    /// ([`crate::structure`]), `[]` where a table has none. Given as `ident` is.
    pub body_ir: Vec<String>,
    /// For each table that an output of an instance gives, the instance's
    /// component and the numbers of the tables of its inputs, as JSON
    /// ([`crate::structure`]), and the empty string for every other table.
    /// Given as `ident` is.
    pub instance: Vec<String>,
    /// For each table, the permutations of its column identities under which
    /// its content is the same, as JSON ([`crate::structure`]). Given as
    /// `ident` is.
    pub column_symmetries: Vec<String>,
    /// The width in cells of a row.
    pub width: Vec<u32>,
    /// The width in cells of each column, in the order of `column_names`: 4 for a column of type `Box`, `Position` or `Offset`, and 1 for
    /// every other. The widths of a table's columns add up to its `width`.
    pub column_widths: Vec<Vec<u32>>,
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
    /// The export by assignment gives these, and a row for each table at each of
    /// its assignments, in the order of the tables and of the walk; the other
    /// export leaves them empty.
    ///
    /// The number of the table, which the other parts that name a table by its
    /// number (`flows`, `projections`) give.
    pub table: Vec<u32>,
    /// The QueryHash of the table's query: the `query_hash` of its query, for a
    /// table of a finished query, and 0 for a table that has none (a body table, whose
    /// query is not finished, and an evidence table), where `has_query` is 0.
    pub query: Vec<u128>,
    pub has_query: Vec<u8>,
    /// The table's Name: the output Name of an instance's or a `RIGID_DET` form's table, the fact
    /// relation's name of an evidence table, and the empty string for any other, as
    /// [`crate::summary::TableSummary::name`] gives it. A `RIGID_DET` form's part is `slot <n>`, by its
    /// position in the form's canonical form, and `arclog.rigid_slot_name` gives that Name for a read.
    pub name: Vec<String>,
    /// The TableHash, and whether the assignment has one (1) or not (0, with the hash 0).
    pub hash: Vec<u128>,
    pub hashed: Vec<u8>,
    /// Why the assignment has no TableHash (`hashed` 0): the name of a machine-dependent bound that stopped an example (`Models`, `Nodes`, `Assignments`, `TableWork`, `RequestWork`, `RequestBytes`, `Cancelled`), or of the bound that stopped the summary, `RunFault`, `NoEntry`, `NoExamples`, `TableFault`, or `ColumnSearch`, where the search for the order of the table's tied columns passed its cap. Empty where `hashed` is 1.
    pub unhashed_reason: Vec<String>,
    /// Whether the walk of the table stopped at the assignment cap.
    pub capped: Vec<u8>,
    /// The TableVector of each row, `arclog_features::FEATURES.len()` values.
    pub features: Vec<f32>,
    /// The rows of each row's table in the engine's cell encoding, for the reader that walks the table's shapes: one for each row of the export by assignment,
    /// and none for a row whose summary holds no rows. The columns of any other export hold none.
    pub shape_rows: Vec<Option<Arc<crate::shape_rows::ShapeRows>>>,
    /// The value hash of each column of each row, in the order of `column_names`, each a `u128`, and empty where the row's assignment has no
    /// TableHash or the export gives no full summary. The hash depends on the column's content alone ([`crate::summary::ColumnKey`]).
    pub column_value_hashes: Vec<Vec<u128>>,
    /// The type name that the TableHash writes for each column of each row, as `column_value_hashes` is given. It differs from `column_types` for an
    /// Ident type, whose name here holds the Ident's source, and for a Pose type, whose name here holds the QueryHash of its `RIGID_DET` and no slot.
    pub column_type_keys: Vec<Vec<String>>,
    /// The tie of each column of each row, as `column_value_hashes` is given: 0 where no other column has its type key and value hash, 1 where another
    /// does and the columns that have them can be exchanged without changing the table, 2 where another does and that was not shown.
    pub column_ties: Vec<Vec<u32>>,
    /// The order of the columns under which the TableHash of each row was computed: for each canonical place, the column at it, as an index into `column_names`. Empty where the
    /// row's assignment has no TableHash. Two rows with equal TableHashes have, at each place, columns of equal `column_type_keys` and `column_value_hashes`, and under the map
    /// that sends each column of one to the column at the same place of the other, each example's Set of TableRows is equal.
    pub column_order: Vec<Vec<u32>>,
}

/// One row for each entry of a table on an example, in the order of the
/// tables, the examples, the assignments and the models.
#[derive(Clone, Debug, Default)]
pub struct EntryColumns {
    /// The number of the table.
    pub table: Vec<u32>,
    /// Original top-level clause index; -1 for task evidence.
    pub clause_index: Vec<i32>,
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
    /// The place of the entry's assignment among the table's assignments. The
    /// export by assignment reads it and does not give it.
    pub assignment: Vec<u32>,
    /// The value hash of the entry's Rows (`crate::summary::value_hash_of`, which
    /// has the columns in their order), and 0 for an entry that holds no Rows. For a `DET`'s own
    /// table it is the value hash that a table reading the `DET` carries in its
    /// `assignments`. The export by assignment gives it, and the other export leaves it empty.
    pub hash: Vec<u128>,
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

/// One row for each `DET` of each row of the tables part in the export by
/// assignment, sorted by the `DET`.
#[derive(Clone, Debug, Default)]
pub struct AssignmentColumns {
    /// The row of the table in [`TableColumns`].
    pub table: Vec<u32>,
    /// The `DET`: for now its relation as the program spells it, as `det_relations` gives it. A base
    /// `DET` is keyed by this name.
    pub det: Vec<String>,
    /// The QueryHash of the `DET`'s query (`Decoder::query_hash`), 0 where `has_det_query` is 0.
    pub det_query: Vec<u128>,
    /// 0 for a base `DET`, which has no query.
    pub has_det_query: Vec<u8>,
    /// The value hash of the `DET`'s value (`crate::summary::value_hash_of`): it
    /// has the `DET`'s columns in their order, so it is not the TableHash of the value.
    pub value: Vec<u128>,
}

/// One row for each example of each row of the tables part in the export by
/// assignment.
#[derive(Clone, Debug, Default)]
pub struct ExampleKeyColumns {
    /// The row of the table in [`TableColumns`].
    pub table: Vec<u32>,
    pub kind: Vec<u8>,
    pub index: Vec<u32>,
    /// The count of the example's distinct Rows, the most rows of one of them,
    /// and the low 64 bits of the hash of its Set of Rows.
    pub distinct: Vec<u32>,
    pub rows: Vec<u64>,
    pub hash: Vec<u64>,
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
    /// The identity of the form that holds the atom ([`CaseColumns::with_identities`]):
    /// 32 hexadecimal digits, and the empty string where no atom reads the
    /// source. Given as `TableColumns::ident` is.
    pub atom_form: Vec<String>,
    /// The canonical path of the atom in its form, the steps joined by `.`,
    /// where the sorted lists of the form (the conjuncts of a body, the
    /// branches of an `OR`) stand in canonical order under the resolver's writer.
    /// With `atom_form` it is the atom's identity.
    pub atom_path: Vec<String>,
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
    /// Whether the columns are those of the export by assignment
    /// ([`step_case_columns_by_assignment_in`]), which has no `assigned` part and
    /// gives `assignments` and `example_keys`.
    pub by_assignment: bool,
    /// Whether the columns hold identities: `ident`, `column_idents`,
    /// `body_ir`, `instance` and `column_symmetries` of the tables part,
    /// `atom_form` and `atom_path` of the flows part.
    pub identified: bool,
    pub assignments: AssignmentColumns,
    pub example_keys: ExampleKeyColumns,
    pub values: Vec<i32>,
    /// Reservations follow these owned packed buffers through their last drop.
    pub(crate) allocations: Vec<Arc<arclog::session::SessionAllocation>>,
    pub(crate) packing_stop: Option<Stop>,
    /// The tables that the packing left out after its stop, each as
    /// [`table_spelled`] names it, in their order.
    pub(crate) left_out: Vec<String>,
}

impl CaseColumns {
    /// A stop reached before packing a native row buffer; no empty value was
    /// substituted. Bindings propagate it to their operation report.
    pub fn packing_stop(&self)->Option<&Stop> {self.packing_stop.as_ref()}
    /// The tables that the packing left out after [`CaseColumns::packing_stop`]:
    /// the columns hold no row of them. Empty where the columns hold a row of
    /// each table, a table whose entries stopped included.
    pub fn left_out(&self)->&[String] {&self.left_out}
    /// The reservations of these columns, taken out of them, for the owner of
    /// the copies made from the columns, such as returned Python buffers.
    /// Each that no other owner shares shrinks, in their order, so that they
    /// keep `bytes` in all: the packing allowance does not outlive the
    /// columns, and `bytes` is what the copies hold once the columns drop.
    pub fn take_allocations(&mut self,mut bytes:usize)->Vec<Arc<arclog::session::SessionAllocation>> {
        let mut allocations=std::mem::take(&mut self.allocations);
        for allocation in &mut allocations {
            let held=allocation.bytes();
            if let Some(allocation)=Arc::get_mut(allocation) {
                allocation.shrink_to(bytes);
            }
            bytes=bytes.saturating_sub(held.min(bytes));
        }
        allocations
    }
    /// The bytes that the reservations of these columns keep, as [`CaseColumns::take_allocations`] would take them.
    pub fn allocated_bytes(&self)->usize {
        self.allocations.iter().fold(0usize,|bytes,allocation|bytes.saturating_add(allocation.bytes()))
    }
    /// The cells of these columns, taken out of them for an owner that keeps them elsewhere. The reservations give back the bytes the cells took.
    pub fn take_values(&mut self)->Vec<i32> {
        let values=std::mem::take(&mut self.values);
        let mut keep=self.allocated_bytes().saturating_sub(values.capacity().saturating_mul(std::mem::size_of::<i32>()));
        for allocation in &mut self.allocations {
            let held=allocation.bytes();
            if let Some(allocation)=Arc::get_mut(allocation) {
                allocation.shrink_to(keep);
            }
            keep=keep.saturating_sub(held.min(keep));
        }
        values
    }
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
enum RowExport {
    Default,
    /// Each entry's rows as its evaluation holds them: the rows of a relation
    /// of one part, whatever their count, and of a product of parts that holds
    /// at most `cap` rows. A larger product gives its count, and its parts as
    /// the table's projections ([`held_views`]), so none of its rows is built.
    Held {cap:u64},
    /// The export that groups a table's entries by assignment: the rows of
    /// every entry with no count cap where `rows`, and no rows alone where
    /// not; no projections, and no `DET` value runs, since the assignments part
    /// holds the value hashes.
    Grouped {rows:bool},
    /// The export that groups a table's entries by assignment and holds the
    /// summaries' TableHash alone ([`step_case_columns_by_assignment_hashed`]):
    /// the columns of each table, and no entry, no projection and no `DET`
    /// value run, so no row is packed.
    Hashed,
}
impl RowExport {
    fn omit_projections(self)->bool {matches!(self,Self::Grouped {..}|Self::Hashed)}
    fn count_only(self,rows:&Relation,projected:bool)->bool {
        match self {
            Self::Default=>projected,
            Self::Held {cap}=>rows.parts().len()>1 && rows.len()>cap,
            Self::Grouped {rows}=>!rows,
            Self::Hashed=>true,
        }
    }
    fn skips_dets(self)->bool {matches!(self,Self::Grouped {..}|Self::Hashed)}
    fn skips_entries(self)->bool {matches!(self,Self::Hashed)}
}

/// Packs with the caller's CURRENT operation limits and native session.
pub fn case_columns_in(materializer:&Materializer<'_>,evidence:&[Table],tables:&[(usize,Table)],train:usize,labels:Option<&StreamLabels>)->CaseColumns {
    fold(materializer,evidence,tables,None,train,labels,RowExport::Default).0
}

/// Packs each entry's rows as its evaluation holds them, as [`RowExport::Held`]
/// gives, in place of the decode's projections.
pub fn case_columns_held_in(materializer:&Materializer<'_>,evidence:&[Table],tables:&[(usize,Table)],train:usize,labels:Option<&StreamLabels>,cap:u64)->CaseColumns {
    fold(materializer,evidence,&held_views(tables,cap),None,train,labels,RowExport::Held {cap}).0
}

/// `tables`, each with one projection for each set of columns that a part of a
/// product over `cap` rows holds, in place of its own projections. A projection
/// gives such a part's rows at its entry, and nothing at every other entry.
fn held_views(tables:&[(usize,Table)],cap:u64)->Vec<(usize,Table)> {
    let over=|value:&RelationValue|match value {RelationValue::Rows(rows) if rows.parts().len()>1 && rows.len()>cap=>Some(Arc::clone(rows)),_=>None};
    tables.iter().map(|(token,table)| {
        let mut table=table.clone();
        if let Ok(contents)=&mut table.contents {
            let entries=|contents:&Contents|contents.examples.iter().filter_map(|example|example.rows.as_ref().ok()).flat_map(|rows|rows.at.iter()).flat_map(|(_,models)|models.iter()).filter_map(over).collect::<Vec<_>>();
            let mut sets:Vec<Box<[ColumnIndex]>>=entries(contents).iter().flat_map(|rows|rows.parts().iter().map(|part|{
                let mut set=part.columns.to_vec();
                set.sort_by_key(|column|column.0);
                set.into_boxed_slice()
            }).collect::<Vec<_>>()).collect();
            sets.sort_by_key(|set|set.iter().map(|column|column.0).collect::<Vec<_>>());
            sets.dedup();
            let found=sets.into_iter().map(|set| {
                let part_of=|value:&RelationValue|over(value).and_then(|rows|rows.parts().iter().find(|part|part.columns.len()==set.len() && part.columns.iter().all(|column|set.contains(column))).map(|part|{
                    let columns=part.columns.iter().map(|column|ColumnIndex(set.iter().position(|held|held==column).expect("a column of the set") as u16)).collect();
                    Arc::new(Relation::from_parts(set.len() as u16,Box::new([RelationPart {columns,rows:part.rows.clone()}])))
                }));
                let rows=contents.examples.iter().map(|example|Assigned {
                    at:example.rows.as_ref().map_or_else(|_|Vec::new(),|rows|rows.at.iter().flat_map(|(assignment,models)|models.iter().map(|value|(assignment.clone(),part_of(value)))).collect()),
                    stop:None,
                }).collect();
                Projection {columns:set,rows}
            }).collect::<Vec<_>>();
            contents.projections=(!found.is_empty()).then_some(Projections::Found(found));
        }
        (*token,table)
    }).collect()
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
    /// The QueryHash of each of `tables` as the step that made it gave it, none where the export by assignment did not give one.
    queries: Vec<Option<StableHash>>,
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
    step_columns(materializer,before,evidence,tables,train,RowExport::Default)
}

fn step_columns(materializer:&Materializer<'_>,before:Option<&StreamTables>,evidence:&[Table],tables:Vec<(usize,Table)>,train:usize,row_export:RowExport)->(CaseColumns,StreamTables) {
    let mut columns = CaseColumns::default();
    let _timed = arclog::stats::span(arclog::stats::Phase::TablePack);
    let mut runs = Runs::default();
    let mut names = Vec::new();
    // A table of the step looks up the table of a relation by the relation's spelling, so the names of the earlier tables that no table of the step reads are not kept: the columns and the bytes of the step then depend on the relations its tables read alone, and not on the other tables of the stream.
    let read = read_names(&tables);
    let first = match before {
        Some(before) => {
            for (place, table) in evidence.iter().chain(before.tables.iter().map(|table| &**table)).enumerate() {
                if table.contents.as_ref().is_ok_and(|contents| read.contains(table_name(contents))) {
                    note_name(&mut names, u32::try_from(place).expect("fewer than 2^32 tables"), table, None);
                }
            }
            before.count as usize
        }
        None => {
            push_tables(&materializer.for_evidence(),&mut columns, &mut names, &mut runs, 0, evidence.iter().map(|table| (0, table)), train, None,row_export);
            evidence.len()
        }
    };
    push_tables(materializer,&mut columns, &mut names, &mut runs, first, tables.iter().map(|(token, table)| (*token, table)), train, None,row_export);
    let count = u32::try_from(first + tables.len()).expect("fewer than 2^32 tables");
    let mut queries = before.map_or_else(Vec::new, |before| before.queries.clone());
    queries.resize(first.saturating_sub(evidence.len()) + tables.len(), None);
    let kept = before.map_or_else(Vec::new, |before| before.tables.clone()).into_iter().chain(tables.into_iter().map(|(_, table)| Arc::new(table))).collect();
    (columns, StreamTables { tables: kept, queries, count })
}

/// The columns of the tables of one step, as [`step_case_columns_in`] gives
/// them, but with the entries of a table grouped by assignment, on a task with
/// the train pairs `train`:
///
/// - `tables` has a row for each table at each of its assignments, with the
///   table's `query` (its QueryHash, given by `queries`, one for each of
///   `tables`: none for a body table) and `name`, the TableHash (`hash` and `hashed`) and the
///   TableVector (`features`);
/// - `entries` has the Set of Rows of each row of `tables`: a row for each
///   distinct Rows, with the example it is at (`example_kind` and
///   `example_index`, the value of its Example column) and its place among the
///   example's distinct Rows (`model`), and the hash of the Rows (`hash`). Its `table` is the row of `tables`,
///   while `flows` and `projections` name a table by its number, which
///   `tables.table` gives;
/// - `assignments` has the `DET`s of each row of `tables` with their value
///   hashes, and `example_keys` the key of each example at it;
/// - `assigned` is empty, and no projection is exported.
///
/// An assignment names a `DET` by the relation's spelling, and the `DET`'s QueryHash is
/// the one that the step of the first table of the stream so far (the earlier steps'
/// tables, then this step's) at a slot with that name gave it; it is looked up when an
/// assignment names it, and once for each name. It does not change with the columns that
/// later steps read of the `DET`. A base `DET` has none. A table that reads a `DET` through
/// some of its columns has a row for each full value of the `DET` that projects to the value
/// it was evaluated at ([`crate::summary::DetFulls`]), and the `value` of its assignments is
/// the value hash of the full value.
///
/// The summaries of the tables of a query come from `cache` where it holds them.
/// The hash, the keys and the features come from the rows the table holds,
/// whatever `rows` says, and no count cap applies. With `rows`, every entry
/// is of kind [`ValueKind::Rows`] with all its rows. Without it, every entry
/// that holds Rows is of kind [`ValueKind::NotExported`]: its count of rows and
/// its hash, and the columns hold no row buffer.
///
/// A Pose type is named in the hashes by the form's spelling, which holds slots,
/// as no QueryHash of its `RIGID_DET` is given:
/// [`step_case_columns_by_assignment_with`] gives them.
pub fn step_case_columns_by_assignment_in(materializer:&Materializer<'_>,before:Option<&StreamTables>,evidence:&[Table],tables:Vec<(usize,Table)>,train:&[arclog_features::Pair],queries:Vec<Option<StableHash>>,rows:bool,cache:&SummaryCache)->(CaseColumns,StreamTables) {
    step_case_columns_by_assignment_with(materializer,before,evidence,tables,train,queries,rows,cache,Assemblies::default())
}

/// [`step_case_columns_by_assignment_in`], with `assemblies`, the QueryHash of
/// the `RIGID_DET` of each assembly of the program, by which the TableHash and
/// the value hashes name each Pose type ([`crate::summary`]).
#[allow(clippy::too_many_arguments)]
pub fn step_case_columns_by_assignment_with(materializer:&Materializer<'_>,before:Option<&StreamTables>,evidence:&[Table],tables:Vec<(usize,Table)>,train:&[arclog_features::Pair],queries:Vec<Option<StableHash>>,rows:bool,cache:&SummaryCache,assemblies:Assemblies)->(CaseColumns,StreamTables) {
    by_assignment_columns(materializer,before,evidence,tables,train,queries,RowExport::Grouped {rows},cache,assemblies)
}

/// [`step_case_columns_by_assignment_with`] for the export that computes no
/// summary of a table beyond its TableHash and packs no row. Its columns are
/// those of the other export, with these parts of them empty or left to the
/// table alone:
///
/// - `tables` has a row for each table at each of its assignments, as the other
///   export has, with no row for a full value of a `DET` that the table reads
///   through some of its columns ([`crate::summary::DetFulls`]). A table of a
///   finished query and an evidence table have the `hash`, `hashed` and
///   `unhashed_reason` that its summary gives. A body table has one row,
///   with `hashed` 0 and the reason `NotComputed`. `capped` and `name` come from
///   the table, and `features` is 0 at each feature, in every row. Every other
///   column of `tables` is the other export's;
/// - `entries`, `assignments`, `example_keys`, `assigned`, `projections` and
///   `projection_rows` have no row, and `values` no cell;
/// - `flows` has the rows that the other export gives.
///
/// The TableHash is that of the rows the table holds, so the walk of those rows
/// that it takes remains: it is the part of a summary that this export keeps.
/// What it leaves out is the value hash of each `DET`, the key of each example,
/// the value hash of each model's TableRows, the TableVector, and the entries
/// with their rows. The summaries of `cache` serve it as they serve the other
/// export, and a summary that it puts there serves no call of the other export
/// ([`crate::summary::summarize_hashes_cached`]).
#[allow(clippy::too_many_arguments)]
pub fn step_case_columns_by_assignment_hashed(materializer:&Materializer<'_>,before:Option<&StreamTables>,evidence:&[Table],tables:Vec<(usize,Table)>,train:&[arclog_features::Pair],queries:Vec<Option<StableHash>>,cache:&SummaryCache,assemblies:Assemblies)->(CaseColumns,StreamTables) {
    by_assignment_columns(materializer,before,evidence,tables,train,queries,RowExport::Hashed,cache,assemblies)
}

#[allow(clippy::too_many_arguments)]
fn by_assignment_columns(materializer:&Materializer<'_>,before:Option<&StreamTables>,evidence:&[Table],tables:Vec<(usize,Table)>,train:&[arclog_features::Pair],queries:Vec<Option<StableHash>>,row_export:RowExport,cache:&SummaryCache,assemblies:Assemblies)->(CaseColumns,StreamTables) {
    let hashed = matches!(row_export,RowExport::Hashed);
    let mut stop = None;
    let held: &[Table] = if before.is_some() {&[]} else {evidence};
    // The cache key of each table: its QueryHash with its `DET`s ([`summary_query`]), and its place among the step's tables of the same form. A body
    // table and an evidence table have none.
    let keys: Vec<Option<SummaryKey>> = {
        // The QueryHash of each `DET` table of the stream by its spelling, the first table of the spelling, as `det_query` below finds it.
        let mut det_queries: StableHashMap<&str,Option<StableHash>> = StableHashMap::default();
        let earlier = before.into_iter().flat_map(|before|before.tables.iter().map(|table|&**table).zip(before.queries.iter().copied()));
        for (table,query) in earlier.chain(tables.iter().map(|(_,table)|table).zip(queries.iter().copied())) {
            let Ok(contents) = &table.contents else {continue};
            if matches!(contents.relation,TableRelation::Slot(_)) {det_queries.entry(contents.name.as_str()).or_insert(query);}
        }
        held.iter().enumerate().map(|(at,_)|Some(evidence_key(at))).chain(tables.iter().enumerate().map(|(at,(_,table))|{
            let query = queries.get(at).copied().flatten()?;
            Some((summary_query(query,table,&det_queries),tables[..at].iter().filter(|(_,earlier)|earlier.form==table.form).count() as u32))
        })).collect()
    };
    let summaries: Vec<TableSummary> = {
        // The full `DET`s of the stream so far, which a table that reads one through some of its columns stands for each full value of.
        let fulls = DetFulls::new(before.into_iter().flat_map(|before|before.tables.iter().map(|table|&**table)).chain(tables.iter().map(|(_,table)|table)).collect()).with_assemblies(assemblies);
        // The evidence tables belong to the task: their summaries count in the request of the evidence export, where it has one, and not in the request of the step.
        let evidence_materializer = materializer.for_evidence();
        held.iter().chain(tables.iter().map(|(_,table)|table)).zip(keys).enumerate().map(|(at,(table,key))|{let materializer = if at<held.len() {&evidence_materializer} else {materializer}; (if hashed {summarize_hashes_cached(materializer,table,train,&fulls,cache,key)} else {summarize_cached(materializer,table,train,&fulls,cache,key)}).unwrap_or_else(|bound|{
            stop.get_or_insert(Stop {bound,form:table.form.clone()});
            TableSummary::unhashed(table, bound_name(bound))
        })}).collect()
    };
    let (columns, mut stream) = {
        let _timed = split::span(Part::StepColumns);
        step_columns(materializer,before,evidence,tables,train.len(),row_export)
    };
    // The QueryHash of each table of this step is the one the step gives: an assignment names a `DET` by that hash, whatever columns later steps read of it.
    let own_from = stream.queries.len()-queries.len();
    stream.queries[own_from..].copy_from_slice(&queries);
    // The QueryHash of each table of the columns, the evidence tables having none.
    let mut hashes = vec![None;held.len()];
    hashes.extend(queries);
    let mut columns = {
        let _timed = split::span(Part::Regroup);
        let found: std::cell::RefCell<StableHashMap<String,Option<StableHash>>> = Default::default();
        let det_query = |spelled:&str|->Option<StableHash> {
            if let Some(known) = found.borrow().get(spelled) {return *known;}
            let _timed = split::span(Part::DetQuery);
            let hash = stream.tables.iter().zip(&stream.queries).find_map(|(table,query)|{
                let contents = table.contents.as_ref().ok()?;
                matches!(contents.relation,TableRelation::Slot(_)).then_some(())?;
                if contents.name!=spelled {return None;}
                *query
            });
            found.borrow_mut().insert(spelled.to_owned(),hash);
            hash
        };
        by_assignment(columns,&summaries,&hashes,&det_query,before.map_or(0,|before|before.count))
    };
    if columns.packing_stop.is_none() {columns.packing_stop=stop;}
    (columns, stream)
}

/// The hash that keys the summary of `table`, whose QueryHash is `query`, in a
/// [`SummaryCache`]: `query`, and, for each `DET` of the table's assignments in
/// their order, the QueryHash of the `DET`'s table (`det_queries`, by the
/// spelling of the `DET`), or its spelling where the stream has no QueryHash of
/// it, and the columns of it that the table reads. A summary holds the value of
/// each `DET` by its place, and the walk of the assignments follows the order
/// of the `DET`s, so two programs of one query whose `DET`s stand in another
/// order take two keys.
fn summary_query(query:StableHash,table:&Table,det_queries:&StableHashMap<&str,Option<StableHash>>)->StableHash {
    let Ok(contents) = &table.contents else {return query};
    if contents.dets.is_empty() {return query;}
    use std::hash::Hasher;
    let mut hasher = StableHasher::new();
    hasher.write(b"arclog.summary.dets");
    hasher.write_u128(query.0);
    hasher.write_u64(contents.dets.len() as u64);
    for det in contents.dets.iter() {
        let spelled = relation_spelled(&det.relation);
        match det_queries.get(spelled.as_str()).copied().flatten() {
            Some(hash) => {hasher.write_u8(1);hasher.write_u128(hash.0);}
            None => {hasher.write_u8(0);hasher.write(spelled.as_bytes());hasher.write_u8(0);}
        }
        match &det.columns {
            Some(columns) => {
                hasher.write_u8(1);
                hasher.write_u64(columns.len() as u64);
                for column in columns.iter() {hasher.write(path_spelled(column).as_bytes());hasher.write_u8(0);}
            }
            None => hasher.write_u8(0),
        }
    }
    hasher.finish128()
}

impl StopColumns {
    fn picked(&self,at:&[usize])->StopColumns {
        StopColumns {bound:at.iter().map(|&entry|self.bound[entry].clone()).collect(),form:at.iter().map(|&entry|self.form[entry].clone()).collect(),assignment:at.iter().map(|&entry|self.assignment[entry]).collect()}
    }
}

/// `columns`, the columns of the tables numbered from `base`, regrouped by the
/// assignments of `summaries`, the summary of each of its tables.
fn by_assignment(mut columns:CaseColumns,summaries:&[TableSummary],queries:&[Option<StableHash>],det_query:&dyn Fn(&str)->Option<StableHash>,base:u32)->CaseColumns {
    let old = std::mem::take(&mut columns.tables);
    // The old table and the assignment of each row of the new tables part, and the first row of each old table.
    let mut source: Vec<(usize,usize,usize)> = Vec::new();
    // The first row of each assignment of each old table: an assignment stands for a row for each variant, one for each full value of the `DET`s it reads through some of their columns.
    let mut first: Vec<Vec<usize>> = Vec::with_capacity(old.token.len());
    for (table,summary) in summaries.iter().take(old.token.len()).enumerate() {
        first.push(summary.assignments.iter().enumerate().map(|(assignment,held)|{
            let place = source.len();
            source.extend((0..=held.more.len()).map(|variant|(table,assignment,variant)));
            place
        }).collect());
    }
    let at: Vec<usize> = source.iter().map(|&(table,_,_)|table).collect();
    macro_rules! pick {($($field:ident),*)=>{TableColumns {
        $($field: at.iter().map(|&table|old.$field[table].clone()).collect(),)*
        projections_stop: old.projections_stop.picked(&at),
        ..TableColumns::default()
    }}}
    let mut tables = pick!(token,form,point,conjuncts,sites,relation,fact,column_names,column_types,column_ident_sources,column_frames,extent_columns,column_slots,column_labels,column_source_labels,width,column_widths,det_relations,det_types,det_frames,det_slots,det_labels,det_source_labels,det_widths,det_columns,projections,fault,depth,keys,output_position,output_color);
    let features = arclog_features::FEATURES.len();
    for (row,&(table,assignment,variant)) in source.iter().enumerate() {
        let summary = &summaries[table];
        let held = &summary.assignments[assignment];
        let row = u32::try_from(row).expect("fewer than 2^32 table rows");
        tables.table.push(base+u32::try_from(table).expect("fewer than 2^32 tables"));
        tables.query.push(queries.get(table).copied().flatten().map_or(0,|hash|hash.0));
        tables.has_query.push(u8::from(queries.get(table).copied().flatten().is_some()));
        tables.name.push(summary.name.clone());
        tables.hash.push(held.hash.map_or(0,|hash|hash.0));
        tables.hashed.push(u8::from(held.hash.is_some()));
        tables.unhashed_reason.push(held.reason.clone());
        tables.capped.push(u8::from(summary.capped));
        if held.features.len()==features {tables.features.extend(held.features.iter());} else {tables.features.extend(std::iter::repeat_n(0.0,features));}
        tables.shape_rows.push(held.shape_rows.clone());
        tables.column_value_hashes.push(held.columns.iter().map(|key|key.hash.0).collect());
        tables.column_type_keys.push(held.columns.iter().map(|key|key.ty.clone()).collect());
        tables.column_ties.push(held.columns.iter().map(|key|key.tie).collect());
        tables.column_order.push(held.column_order.to_vec());
        for (place,(det,primary)) in held.dets.iter().enumerate() {
            let value = if variant==0 {primary} else {&held.more[variant-1][place]};
            columns.assignments.table.push(row);
            columns.assignments.det.push(det.clone());
            let query = det_query(det);
            columns.assignments.det_query.push(query.map_or(0,|hash|hash.0));
            columns.assignments.has_det_query.push(u8::from(query.is_some()));
            columns.assignments.value.push(value.0);
        }
        for key in held.examples.iter() {
            let keys = &mut columns.example_keys;
            keys.table.push(row);
            keys.kind.push(key.kind);
            keys.index.push(key.index);
            keys.distinct.push(key.distinct);
            keys.rows.push(key.rows);
            keys.hash.push(key.hash);
        }
    }
    // The entries in the order of the new rows, one for each distinct Rows of an example.
    let entries = std::mem::take(&mut columns.entries);
    // An entry stands once in each row of its assignment.
    let mut order: Vec<(usize,usize)> = Vec::with_capacity(entries.table.len());
    for entry in 0..entries.table.len() {
        let table = (entries.table[entry]-base) as usize;
        let assignment = (entries.assignment[entry] as usize).min(summaries[table].assignments.len()-1);
        order.extend((0..=summaries[table].assignments[assignment].more.len()).map(|variant|(entry,first[table][assignment]+variant)));
    }
    order.sort_by_key(|&(_,row)|row);
    // The hash of the Rows of each entry that holds Rows, from the summary of its table.
    let rows_hash: Vec<Option<u128>> = (0..entries.table.len()).map(|entry|{
        let table = (entries.table[entry]-base) as usize;
        let held = &summaries[table].assignments[(entries.assignment[entry] as usize).min(summaries[table].assignments.len()-1)];
        let example = held.examples.iter().position(|key|key.kind==entries.example_kind[entry] && key.index==entries.example_index[entry])?;
        let value = held.models.get(example)?.get(entries.model[entry] as usize)?;
        value.map(|(_,hash)|hash)
    }).collect();
    let holds_rows = |entry:usize|entries.kind[entry]==ValueKind::Rows as u8 || entries.kind[entry]==ValueKind::Count as u8;
    let mut kept: Vec<(usize,usize)> = Vec::new();
    let mut seen: StableHashMap<(usize,u8,u32,u128),()> = StableHashMap::default();
    let mut undefined: StableHashMap<(usize,u8,u32),()> = StableHashMap::default();
    for &(entry,row) in &order {
        // Equal Rows of an example stand once.
        let key = (row,entries.example_kind[entry],entries.example_index[entry]);
        let equal = match rows_hash[entry] {
            Some(hash) if holds_rows(entry) => seen.insert((key.0,key.1,key.2,hash),()).is_some(),
            _ => entries.kind[entry]==ValueKind::Undefined as u8 && undefined.insert(key,()).is_some(),
        };
        if !equal {kept.push((entry,row));}
    }
    let kept_entries: Vec<usize> = kept.iter().map(|&(entry,_)|entry).collect();
    let mut next: StableHashMap<(usize,u8,u32),u32> = StableHashMap::default();
    columns.entries = EntryColumns {
        table: kept.iter().map(|&(_,row)|row as u32).collect(),
        clause_index: kept.iter().map(|&(entry,_)|entries.clause_index[entry]).collect(),
        example_kind: kept.iter().map(|&(entry,_)|entries.example_kind[entry]).collect(),
        example_index: kept.iter().map(|&(entry,_)|entries.example_index[entry]).collect(),
        model: kept.iter().map(|&(entry,row)|{
            let place = next.entry((row,entries.example_kind[entry],entries.example_index[entry])).or_insert(0);
            *place += 1;
            *place-1
        }).collect(),
        // This export has no Count entry: without rows, an entry gives its count of rows and its hash.
        kind: kept.iter().map(|&(entry,_)|if entries.kind[entry]==ValueKind::Count as u8 {ValueKind::NotExported as u8} else {entries.kind[entry]}).collect(),
        rows: kept.iter().map(|&(entry,_)|entries.rows[entry]).collect(),
        offset: kept.iter().map(|&(entry,_)|entries.offset[entry]).collect(),
        stop: entries.stop.picked(&kept_entries),
        value_stop: entries.value_stop.picked(&kept_entries),
        fault: kept.iter().map(|&(entry,_)|entries.fault[entry].clone()).collect(),
        extent_offset: kept.iter().map(|&(entry,_)|entries.extent_offset[entry]).collect(),
        extent_stop: entries.extent_stop.picked(&kept_entries),
        extent_fault: kept.iter().map(|&(entry,_)|entries.extent_fault[entry].clone()).collect(),
        extent_status: kept.iter().map(|&(entry,_)|entries.extent_status[entry].clone()).collect(),
        assignment: Vec::new(),
        hash: kept.iter().map(|&(entry,_)|rows_hash[entry].filter(|_|holds_rows(entry)).unwrap_or(0)).collect(),
    };
    columns.tables = tables;
    columns.assigned = AssignedColumns::default();
    columns.by_assignment = true;
    columns
}

/// The spellings of the relations that `tables` read: those of the sources of their columns and of their `DET`s. [`locate`] and [`det_table`] look up
/// the earlier table of a relation by one of these.
fn read_names(tables: &[(usize, Table)]) -> StableHashSet<String> {
    let mut read = StableHashSet::default();
    for (_, table) in tables {
        let Ok(contents) = &table.contents else { continue };
        read.extend(contents.dets.iter().map(|det| relation_spelled(&det.relation)));
        read.extend(contents.flows.iter().flatten().filter_map(|source| source.relation.as_ref()).map(source_spelled));
    }
    read
}

/// The fold of [`case_columns`] and [`cut_case_columns`]: the only state it
/// keeps across tables is the `names` of the tables so far, with the frames,
/// slots and labels of their columns, and the `Runs` written, so a table's columns depend on its
/// own step and the tables before it. With `cut`, the tables before it are
/// folded into `names` alone, and the count of them is given with the
/// columns.
/// `labels` are as [`case_columns`] takes them.
fn fold(materializer:&Materializer<'_>,evidence: &[Table], tables: &[(usize, Table)], cut: Option<usize>, train: usize, labels: Option<&StreamLabels>, row_export:RowExport) -> (CaseColumns, u32) {
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
/// first of them the table at `first`, after the tables in `names`. Each
/// table after a stop goes to `out.left_out`.
fn push_tables<'t>(materializer:&Materializer<'_>,out: &mut CaseColumns, names: &mut TableNames, runs: &mut Runs, first: usize, tables: impl Iterator<Item = (usize, &'t Table)>, train: usize, labels: Option<&StreamLabels>, row_export:RowExport) {
    // A stopped fold is a prefix, including when a previous append stopped.
    // Releasing phase scratch must never admit a later table past a gap.
    for (place, (token, table)) in (first..).zip(tables) {
        if out.packing_stop.is_some() {
            out.left_out.push(table_spelled(table));
            continue;
        }
        let first_allocation=out.allocations.len();
        let before=packing_bytes(out,names,runs);
        // Headers/count-only entries allocate too, even when there is no row
        // buffer. Admit their physical metadata before any output allocation.
        let allocation=metadata_bytes(materializer,table,names,labels,row_export)
            .and_then(|bytes|materializer.copy(bytes.saturating_add(packing_growth(out,names,runs,table,row_export))));
        match allocation {
            Ok(allocation)=>out.allocations.push(allocation),
            Err(bound)=>{
                out.packing_stop=Some(Stop {bound,form:table.form.clone()});
                out.left_out.push(table_spelled(table));
                continue;
            },
        }
        let row = u32::try_from(place).expect("fewer than 2^32 tables");
        let settled=push_table(materializer,out, names, runs, row, token, table, train, labels,row_export);
        // The pointer memo is scratch for this table: release its cloned
        // types, sorted orders and relation/index owners before settlement.
        // Content run interning still spans every table and prefix copy.
        runs.1=StableHashMap::default();
        // push_table has returned: annotation matrices, projection maps and
        // conversion scratch have also dropped.
        // Only this phase's new reservations may shrink; prefix clones and
        // native Contents/matrices keep their independent shared leases.
        // The entries and projection rows have settled to the bytes they
        // keep, so the packing allowance covers only the rest of the growth.
        let growth=packing_bytes(out,names,runs).saturating_sub(before);
        let retained=packing_allowance(growth.saturating_sub(settled.heap)).saturating_add(settled.held.saturating_sub(settled.scratch));
        settle_packing(&mut out.allocations[first_allocation..],retained);
    }
}

/// How an error names `table`: the relation as the program spells it, or the
/// body in progress, or the fact relation of an evidence table, with the path
/// of its form.
pub(crate) fn table_spelled(table: &Table) -> String {
    let at = form_path(&table.form);
    match (&table.point, &table.contents) {
        (Point::Body { .. }, _) => format!("the body in progress at form {at}"),
        (_, Ok(Contents { relation: TableRelation::Fact(fact), .. })) => format!("{fact:?}"),
        (_, Ok(contents)) if !contents.name.is_empty() => format!("{} at form {at}", contents.name),
        _ => format!("the relation at form {at}"),
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
fn packing_growth(out:&CaseColumns,names:&TableNames,runs:&Runs,table:&Table,row_export:RowExport)->usize {
    let (mut entries,mut assigned,mut projections,mut projected,mut flows)=(0usize,0usize,0usize,0usize,0usize);
    let mut det_runs=0usize;
    if let Ok(contents)=&table.contents {
        flows=contents.flows.iter().map(Vec::len).sum();
        for example in contents.examples.iter().filter(|_|!row_export.skips_entries()) {match &example.rows {
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
        if let Some(Projections::Found(found))=contents.projections.as_ref().filter(|_|!row_export.omit_projections()) {
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
fn metadata_bytes(materializer:&Materializer<'_>,table:&Table,names:&TableNames,labels:Option<&StreamLabels>,row_export:RowExport)->Result<usize,arclog::eval::ReachedBound> {
    materializer.check()?;
    let mut bytes=64usize.saturating_mul(1024).saturating_add(table.form.0.len().saturating_mul(256));
    let Ok(contents)=&table.contents else {return Ok(bytes.saturating_add(table.contents.as_ref().err().map_or(0,|f|f.message.len().saturating_mul(8))));};
    let mut add=|value:usize|bytes=bytes.saturating_add(value);
    add(contents.name.len().saturating_mul(8));
    for column in &contents.columns {add(2048usize.saturating_add(column.name.len().saturating_mul(8)).saturating_add(column.label.as_ref().map_or(0,|s|s.len().saturating_mul(8))).saturating_add(type_spelling_bytes(&column.ty).saturating_mul(8)));}
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
        add(2048usize.saturating_add(det.types.iter().map(|ty|2048usize.saturating_add(type_spelling_bytes(ty).saturating_mul(8))).fold(0,usize::saturating_add)).saturating_add(det.columns.heap_bytes().saturating_mul(8)));
    }
    for key in &contents.keys {add(256usize.saturating_add(key.len().saturating_mul(32)));}
    for sources in &contents.flows {for source in sources {add(2048usize.saturating_add(source.row.heap_bytes().saturating_mul(8)).saturating_add(source.atom.0.len().saturating_mul(256)));}}
    for example in contents.examples.iter().filter(|_|!row_export.skips_entries()) {
        materializer.check()?;
        match &example.rows {
            Err(fault)=>add(4096usize.saturating_add(fault.message.len().saturating_mul(8))),
            Ok(assigned)=>for (_,models) in &assigned.at {
                materializer.check()?;
                add(models.len().max(1).saturating_mul(4096usize.saturating_add(contents.dets.len().saturating_mul(2048))));
            },
        }
    }
    if let Some(Projections::Found(projections))=contents.projections.as_ref().filter(|_|!row_export.omit_projections()) {for projection in projections {
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

/// The encoding of `term`, the cell of a term of a fixed encoding that has no number of its own: an orientation constant.
fn cell_of(term: Term) -> i32 {
    term.encode().expect("a term that is no Box encodes").fixed_encoding() as i32
}

fn form_path(form: &NodePath) -> String {
    form.0.iter().map(|step| step.0.to_string()).collect::<Vec<_>>().join(".")
}

/// A fault as a table's, an entry's or an extent's `fault` spells it:
/// `<message> at <form>`.
pub(crate) fn fault_spelled(fault: &RunFault) -> String {
    format!("{} at {}", fault.message, form_path(&fault.form))
}

pub(crate) fn type_names(types: &[ValueType]) -> Vec<String> {
    types.iter().map(|ty| format!("{:?}", ty.without_source())).collect()
}

/// The heap bytes of the spellings of `ty` in [`type_names`] and
/// [`ident_sources`], with their string headers, counted without writing them.
fn type_spelling_bytes(ty: &ValueType) -> usize {
    struct Count(usize);
    impl std::fmt::Write for Count {
        fn write_str(&mut self, s: &str) -> std::fmt::Result {
            self.0 = self.0.saturating_add(s.len());
            Ok(())
        }
    }
    fn idents(ty: &ValueType) -> usize {
        match ty {
            ValueType::Ident(IdentSource::Form(_)) => 33,
            ValueType::Record(fields) => fields.iter().map(|(_, field)| idents(field)).fold(0, usize::saturating_add),
            _ => 0,
        }
    }
    let mut spelled = Count(0);
    let _ = std::fmt::Write::write_fmt(&mut spelled, format_args!("{:?}", ty.without_source()));
    spelled.0.saturating_add(idents(ty)).saturating_add(64)
}

/// The sources of the Idents of each of `types`, as
/// [`TableColumns::column_ident_sources`] spells them.
pub(crate) fn ident_sources(types: &[ValueType]) -> Vec<String> {
    fn push(ty: &ValueType, found: &mut Vec<String>) {
        match ty {
            ValueType::Ident(IdentSource::Form(SourceId(id))) => found.push(format!("{:032x}", id.0)),
            ValueType::Record(fields) => fields.iter().for_each(|(_, field)| push(field, found)),
            _ => {}
        }
    }
    types
        .iter()
        .map(|ty| {
            let mut found = Vec::new();
            push(ty, &mut found);
            found.join(",")
        })
        .collect()
}

/// The names of a column's path as a file writes them, or their slots, joined
/// by `.`.
fn path_spelled(path: &[ColumnName]) -> String {
    path.iter().map(column_spelled).collect::<Vec<_>>().join(".")
}

/// The width in cells of a row of columns of `types`.
pub(crate) fn row_width(types: &[ValueType]) -> u32 {
    types.iter().map(|ty| if ty.is_box() { 4 } else { 1 }).sum()
}

/// The cells of the term of `id` at a column of type `ty`. An Ident's cell is
/// 0, and its place in `out` and the Ident are added to `idents`, for the
/// caller to fill with the Ident's export cell.
fn push_cells(out: &mut Vec<i32>, id: TermId, ty: &ValueType, idents: &mut Vec<(usize, Ident)>) {
    match Term::decode(id, ty) {
        Term::Ident(ident) => {
            idents.push((out.len(), ident));
            out.push(0);
        }
        Term::Number(number) => out.push(number.0),
        Term::Box(margins) => out.extend([margins.top, margins.bottom, margins.left, margins.right]),
        Term::Constant(Constant::Color(color)) => out.push(i32::from(color.digit())),
        Term::Constant(Constant::Example(example)) => out.push(i32::from(example.index())),
        Term::Constant(Constant::Unit) => out.push(0),
        Term::Constant(Constant::LibName(name)) => out.push(name.export_cell()),
        term @ Term::Constant(Constant::Orientation(_)) => out.push(cell_of(term)),
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
pub(crate) fn sorted_rows(materializer:&Materializer<'_>,rows: &Relation, types: &[ValueType]) -> Result<(Vec<i32>, Vec<usize>),arclog::eval::ReachedBound> {
    let places: Vec<usize> = (0..types.len()).collect();
    sorted_rows_at(materializer, rows, &places, types)
}

/// [`sorted_rows`] of rows whose cells are those of the values at `places`, in
/// that order, where `types` holds the type of each.
pub(crate) fn sorted_rows_at(materializer:&Materializer<'_>,rows: &Relation, places: &[usize], types: &[ValueType]) -> Result<(Vec<i32>, Vec<usize>),arclog::eval::ReachedBound> {
    assert_eq!(usize::from(rows.arity()), types.len(), "native relation arity differs from its packed schema");
    let width = row_width(types) as usize;
    let count = usize::try_from(rows.len()).expect("a count of rows within a usize");
    let mut written = Vec::with_capacity(count.saturating_mul(width));
    let mut visited = 0;
    let mut idents = Vec::new();
    materializer.walk(rows, &mut |row| {
        for (&place, ty) in places.iter().zip(types) {
            push_cells(&mut written, row[place], ty, &mut idents);
        }
        visited += 1;
    })?;
    materializer.check()?;
    if !idents.is_empty() {
        // The read lock is taken after the walk, which may read the table itself.
        let table = materializer.session().intern.read().expect("an intern table that no panic poisoned");
        for (at, ident) in idents {
            written[at] = table.export_cell(ident);
        }
    }
    let order = row_order(&written, width, visited);
    materializer.check()?;
    Ok((written, order))
}

/// The places of the `count` rows of `cells` (`width` cells each) in the order of their cells, rows of
/// equal cells in the order of their places.
///
/// A row's sort key holds its place in the low bits and, above them, the leading cells of the row that
/// differ between rows, each cell as its difference from the least cell of its column, in as many bits
/// as the column's range takes. A column that every row holds equally takes none. Columns go into the
/// key from the first on until the 128 bits are full; the last may go in by its high bits. Keys order
/// the rows by the cells in the key. Where the key holds every column that differs, the keys alone give
/// the order. Otherwise a tie of the key's cells is broken by the cells of the columns from the first
/// that the key does not hold whole, and then by the place. So the compare of two keys reads a row's
/// cells only for rows that tie in the key.
fn row_order(cells: &[i32], width: usize, count: usize) -> Vec<usize> {
    let row = |at: usize| &cells[at * width..(at + 1) * width];
    if count < 2 || width == 0 {
        return (0..count).collect();
    }
    if u32::try_from(count).is_err() {
        let mut order: Vec<usize> = (0..count).collect();
        order.sort_by(|&a, &b| row(a).cmp(row(b)));
        return order;
    }
    if width == 1 {
        // A cell in the order of its signed value, as an unsigned number.
        let mut keys: Vec<u64> = (0..count).map(|at| u64::from(cells[at] as u32 ^ 0x8000_0000) << 32 | at as u64).collect();
        keys.sort_unstable();
        return keys.into_iter().map(|key| key as u32 as usize).collect();
    }
    let mut low = row(0).to_vec();
    let mut high = low.clone();
    for at in 1..count {
        for ((low, high), &cell) in low.iter_mut().zip(high.iter_mut()).zip(row(at)) {
            *low = (*low).min(cell);
            *high = (*high).max(cell);
        }
    }
    let place_bits = usize::BITS - (count - 1).leading_zeros();
    let budget = 128 - place_bits;
    // The columns in the key: the column, its least cell, the bits of its range that the key drops, and the bits it holds.
    let mut plan: Vec<(usize, i32, u32, u32)> = Vec::new();
    let mut used = 0;
    let mut rest = width;
    for column in 0..width {
        let range = (i64::from(high[column]) - i64::from(low[column])) as u64;
        let bits = 64 - range.leading_zeros();
        if bits == 0 {
            continue;
        }
        if used + bits <= budget {
            plan.push((column, low[column], 0, bits));
            used += bits;
        } else {
            let fits = budget - used;
            if fits > 0 {
                plan.push((column, low[column], bits - fits, fits));
            }
            rest = column;
            break;
        }
    }
    if plan.is_empty() {
        return (0..count).collect();
    }
    let mut keys: Vec<u128> = (0..count)
        .map(|at| {
            let mut key = 0u128;
            for &(column, low, dropped, bits) in &plan {
                key = key << bits | u128::from(((i64::from(cells[at * width + column]) - i64::from(low)) as u64) >> dropped);
            }
            key << place_bits | at as u128
        })
        .collect();
    let place = |key: u128| key & ((1u128 << place_bits) - 1);
    if rest == width {
        keys.sort_unstable();
    } else {
        let tail = |key: u128| &cells[place(key) as usize * width + rest..(place(key) as usize + 1) * width];
        keys.sort_unstable_by(|&a, &b| (a >> place_bits).cmp(&(b >> place_bits)).then_with(|| tail(a).cmp(tail(b))).then_with(|| place(a).cmp(&place(b))));
    }
    keys.into_iter().map(|key| place(key) as usize).collect()
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
///
/// Each call admits the bytes of the rows and walks them, whether or not `runs` holds the places of the rows already. Two entries with equal rows hold
/// one `Arc` where the result cache gave both its one relation of those rows, and two where each computed its own. The bytes held and the work
/// counted must not depend on that, so a call that finds the `Arc` in `runs` makes the charges of a call that sorts, and leaves out the sort.
fn push_rows(materializer:&Materializer<'_>,allocations:&mut Vec<Arc<arclog::session::SessionAllocation>>,values: &mut Vec<i32>, runs: &mut Runs, rows: &Arc<Relation>, types: &[ValueType]) -> Result<(u64, u64, Arc<[usize]>),arclog::eval::ReachedBound> {
    let key=(Arc::as_ptr(rows) as usize,types.to_vec());
    // Flattening, sorting and export use contiguous buffers. The cells stand
    // at most four times during Python conversion; sorting keeps two index
    // buffers. Digest export can also collect one (offset, Ident) per Ident
    // cell, with capacity growth. No row has its own heap allocation.
    let ident_columns=types.iter().filter(|ty|matches!(ty,ValueType::Ident(_))).count();
    let bytes=(row_width(types) as usize).saturating_mul(4*4)
        .saturating_add(2*std::mem::size_of::<usize>())
        .saturating_add(ident_columns.saturating_mul(2*std::mem::size_of::<(usize,Ident)>()));
    let allocation=materializer.admit(rows,bytes)?;
    if let Some((_,offset,order))=runs.1.get(&key) {
        // The charges of `sorted_rows`: the walk of the rows and its two checks.
        materializer.walk(rows,&mut |_|{})?;
        materializer.check()?;
        materializer.check()?;
        allocations.push(allocation);
        return Ok((order.len() as u64,*offset,Arc::clone(order)));
    }
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

/// The columns of `table`, the table at `row`, after the tables before it,
/// and what its entries and projection rows keep once each has settled.
fn push_table(materializer:&Materializer<'_>,out: &mut CaseColumns, names: &mut TableNames, runs: &mut Runs, row: u32, token: usize, table: &Table, train: usize, labels: Option<&StreamLabels>, row_export:RowExport) -> Settled {
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
            tables.column_ident_sources.push(Vec::new());
            tables.column_frames.push(Vec::new());
            tables.extent_columns.push(Vec::new());
            tables.column_slots.push(Vec::new());
            tables.column_labels.push(Vec::new());
            tables.column_source_labels.push(Vec::new());
            tables.width.push(0);
            tables.column_widths.push(Vec::new());
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
            Settled::default()
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
            tables.column_ident_sources.push(ident_sources(&types));
            let own = named(row, table, labels);
            let extent_columns = extent_columns(&types, &contents.frames);
            tables.column_frames.push(contents.frames.clone());
            tables.extent_columns.push(extent_columns.clone());
            tables.column_slots.push(slots_of(contents));
            tables.column_labels.push(labels_of(contents));
            tables.column_source_labels.push(source_labels_of(&table.form, contents, labels));
            tables.width.push(row_width(&types));
            tables.column_widths.push(types.iter().map(|ty| row_width(std::slice::from_ref(ty))).collect());
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
            push_contents(materializer,&table.form,out, runs, row, contents, &types, &extent_columns, train,row_export)
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
        FactRelation::ExOutput | FactRelation::Output => OUTPUT_FRAME,
        FactRelation::Input | FactRelation::ExInput => INPUT_FRAME,
        FactRelation::Program(_) | FactRelation::Name(_) | FactRelation::Stored(_) => "",
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

/// The bytes that the packing of one entry or one projection's rows keeps
/// until its columns become Python objects, and the conversion makes of it:
/// `values` cells (4 bytes each) that the packing added to the case's value
/// buffer, `order` places that a new run's sorted order keeps (8 bytes each),
/// and `status`, the extent status of each row.
///
/// - The cells stand four times: in the buffer, in the conversion's byte copy
///   and in the two Python `bytes` objects that it makes of that copy, the
///   second of which stays.
/// - A row's status keeps a `Vec` slot (24 bytes) and an allocation of at
///   least 8 bytes, and becomes a Python `bytes` object, which `sys.getsizeof`
///   gives as 33 bytes and one a status, in a list slot of 8 bytes.
fn kept_bytes(values: usize, order: usize, status: &[Vec<u8>]) -> usize {
    let status = status.iter().map(|row| 24 + row.len().max(8) + 33 + row.len() + 8).fold(0usize, usize::saturating_add);
    values.saturating_mul(4 * 4).saturating_add(order.saturating_mul(8)).saturating_add(status)
}

/// What the entries and projection rows of a table keep once each has
/// settled: `heap`, the bytes that their cells and extent statuses take in
/// the columns, as [`packing_bytes`] measures them, and `held`, the bytes
/// that their reservations keep.
#[derive(Clone, Copy, Default)]
struct Settled {
    heap: usize,
    held: usize,
    /// Sorted row indexes released with the table's pointer memo.
    scratch: usize,
}

/// The bytes that a value buffer of `capacity` cells takes, as
/// [`packing_bytes`] measures them.
fn values_heap(capacity: usize) -> usize {
    capacity.saturating_mul(std::mem::size_of::<i32>()).saturating_add(usize::from(capacity > 0) * 32)
}

/// Shrinks the reservations `allocations` that no other owner shares, in
/// their order, so that they keep `bytes` in all, as the packing of an entry
/// ends: the reservations covered its scratch, and keep only what it holds.
/// Adds to `settled` the entry's `heap` and the bytes its reservations keep.
fn settle(settled: &mut Settled, allocations: &mut [Arc<arclog::session::SessionAllocation>], mut bytes: usize, heap: usize) {
    settled.heap = settled.heap.saturating_add(heap);
    for allocation in allocations {
        let held = allocation.bytes();
        if let Some(allocation) = Arc::get_mut(allocation) {
            allocation.shrink_to(bytes);
        }
        bytes = bytes.saturating_sub(held.min(bytes));
        settled.held = settled.held.saturating_add(allocation.bytes());
    }
}

// Admit the sorted extent cells, status vectors and inverse permutation
// before allocating them. The walk reuses one annotation row, so no native
// annotation matrix or second per-row extent matrix needs a reservation.
// Allow slack for the value run's growth and the Python export as well.
fn annotation_copy(materializer:&Materializer<'_>,allocations:&mut Vec<Arc<arclog::session::SessionAllocation>>,rows:&Relation,columns:usize)->Result<(),arclog::eval::ReachedBound> {
    let allocation=materializer.admit(rows,Materializer::row_bytes(columns.saturating_mul(48).saturating_add(64),3))?;
    allocations.push(allocation);
    Ok(())
}

/// The entries of `contents`, the table at `row`, and its projections;
/// `extent_columns` are the table's columns that its entries hold extents for.
/// Gives what the entries and projection rows keep once each has settled.
fn push_contents(materializer:&Materializer<'_>,form:&NodePath,out: &mut CaseColumns, runs: &mut Runs, row: u32, contents: &Contents, types: &[ValueType], extent_columns: &[u32], train: usize, row_export:RowExport) -> Settled {
    let mut settled = Settled::default();
    if row_export.skips_entries() {return settled;}
    let mut starts = Vec::with_capacity(contents.examples.len());
    for (place, example) in contents.examples.iter().enumerate() {
        starts.push(out.entries.table.len());
        let (kind, index) = crate::tables::example_axis(example.example, train);
        let index = u32::try_from(index).expect("fewer than 2^32 examples");
        let push = |materializer: &Materializer<'_>, out: &mut CaseColumns, runs: &mut Runs, settled: &mut Settled, at_assignment:usize, model: u32, value: Option<&RelationValue>, stop: Option<&Stop>, fault: Option<String>, extents: Option<&EntryExtents>| {
            let count_only=matches!(value,Some(RelationValue::Rows(rows)) if row_export.count_only(rows,contents.projections.is_some()));
            let (values_from,allocations_from)=(out.values.len(),out.allocations.len());
            let heap_from=values_heap(out.values.capacity());
            let faulted = fault.is_some();
            let entries = &mut out.entries;
            entries.table.push(row);
            entries.assignment.push(u32::try_from(at_assignment).expect("fewer than 2^32 assignments"));
            entries.clause_index.push(form.0.first().map_or(-1,|s|s.0 as i32));
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
                            if !bound.is_assignment() {out.packing_stop=packing_stop.clone();}
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
                if count_only || matches!(value_kind,ValueKind::Stopped) || matches!(extents,Some(EntryExtents::Stopped(_) | EntryExtents::Lost(_))) || relation.is_empty() || extent_columns.is_empty() {Vec::new()} else {
                    // Native annotation has each_row order; export in exactly
                    // the same sorted row order as this entry's value buffer.
                    let annotated=annotation_copy(materializer,&mut out.allocations,relation,extent_columns.len())
                        .map_err(|bound|Stop {bound,form:form.clone()})
                        .and_then(|()| {
                            let columns=extent_columns.len();
                            let mut inverse=vec![0usize;order.len()];
                            for (sorted,&native) in order.iter().enumerate() {inverse[native]=sorted;}
                            let mut cells=vec![-1i32;order.len().saturating_mul(columns).saturating_mul(2)];
                            let mut statuses=vec![Vec::new();order.len()];
                            let mut native=0usize;
                            crate::extents::visit_annotated_rows(materializer,form,contents,place,at_assignment,model as usize,relation,&mut |row| {
                                let sorted=inverse[native];native+=1;
                                statuses[sorted]=row.iter().map(|(status,_)|*status).collect();
                                for (column,(_,extent)) in row.iter().enumerate() {
                                    if let Some(extent)=extent {
                                        let at=(sorted*columns+column)*2;
                                        cells[at]=extent.rows;cells[at+1]=extent.columns;
                                    }
                                }
                            })?;
                            Ok((cells,statuses))
                        });
                    match annotated {
                        Ok((cells,statuses))=>{
                            extent_offset=i64::try_from(push_run(&mut out.values,runs,order.len() as u64,cells)).expect("an offset within an i64");
                            statuses
                        }
                        // The exact stop is already held in extent_stop above;
                        // values remain native, without an invented annotation.
                        Err(stop)=>{annotation_stop=stop;extent_stop=Some(&annotation_stop);if !annotation_stop.bound.is_annotation() {out.packing_stop=Some(annotation_stop.clone());}Vec::new()},
                    }
                }
            } else {Vec::new()};
            let order_kept=order.len();
            let kept=kept_bytes(out.values.len()-values_from,order_kept,&extent_status);
            settled.scratch=settled.scratch.saturating_add(order_kept.saturating_mul(std::mem::size_of::<usize>()));
            settle(settled,&mut out.allocations[allocations_from..],kept,values_heap(out.values.capacity())-heap_from+extent_status.heap_bytes());
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
            Err(fault) => push(materializer, out, runs, &mut settled, 0, 0, None, None, Some(fault_spelled(fault)), None),
            Ok(rows) => {
                if rows.at.is_empty() {
                    push(materializer, out, runs, &mut settled, 0, 0, None, rows.stop.as_ref(), None, None);
                }
                // A stop that ended the walk marks the entries it held. A stop
                // of one assignment stands at that assignment's own entry.
                let ended = rows.stop.as_ref().filter(|stop| !stop.bound.is_assignment());
                for (at, (assigned, models)) in rows.at.iter().enumerate() {
                    let first = out.entries.table.len();
                    // The export of an assignment holds its bytes under the byte budget of an assignment too: an assignment whose rows do not fit
                    // it has its entries stopped, and the other assignments go on.
                    let scope = materializer.limits().for_assignment();
                    let materializer = &Materializer::new(materializer.session(), &scope);
                    for (model, value) in models.iter().enumerate() {
                        let stopped = out.packing_stop.clone().map(RelationValue::Stopped);
                        push(materializer, out, runs, &mut settled, at, model as u32, Some(stopped.as_ref().unwrap_or(value)), ended, None, entry_extents(at, model));
                    }
                    let mut assigned_runs = Vec::new();
                    for (position, ((_, det_rows), det)) in assigned.iter().zip(contents.dets.iter()).enumerate().filter(|_| !row_export.skips_dets()) {
                        let (values_from,allocations_from)=(out.values.len(),out.allocations.len());
                        let heap_from=values_heap(out.values.capacity());
                        let mut order_kept=0;
                        match push_rows(materializer,&mut out.allocations,&mut out.values,runs,det_rows,&det.types) {
                            Ok((count,offset,order))=>{
                                order_kept=order.len();
                                assigned_runs.push((position as u32,count,offset));
                            },
                            Err(bound)=>{
                                let stop=Stop {bound,form:form.clone()};if !bound.is_assignment() {out.packing_stop=Some(stop.clone());}
                                for entry in first..out.entries.table.len() {
                                    out.entries.kind[entry]=ValueKind::Stopped as u8;
                                    out.entries.value_stop.bound[entry]=Some(format!("{:?}",stop.bound));
                                    out.entries.value_stop.form[entry]=Some(form_path(form));
                                    out.entries.value_stop.assignment[entry]=bound.is_assignment();
                                }
                            }
                        }
                        let kept=kept_bytes(out.values.len()-values_from,order_kept,&[]);
                        settled.scratch=settled.scratch.saturating_add(order_kept.saturating_mul(std::mem::size_of::<usize>()));
                        settle(&mut settled,&mut out.allocations[allocations_from..],kept,values_heap(out.values.capacity())-heap_from);
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
    if let Some(Projections::Found(found)) = contents.projections.as_ref().filter(|_|!row_export.omit_projections()) {
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
                    let (values_from,allocations_from)=(out.values.len(),out.allocations.len());
                    let heap_from=values_heap(out.values.capacity());
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
                            let per_row = projected_extent_rows(materializer,rows, table_rows, held, &projected_columns, &projected_extents,contents,example)?;
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
                    let order_kept=order.len();
                    let kept=kept_bytes(out.values.len()-values_from,order_kept,&extent_status);
                    settled.scratch=settled.scratch.saturating_add(order_kept.saturating_mul(std::mem::size_of::<usize>()));
                    settle(&mut settled,&mut out.allocations[allocations_from..],kept,values_heap(out.values.capacity())-heap_from+extent_status.heap_bytes());
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
    settled
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
fn projected_extent_rows(materializer:&Materializer<'_>,rows: &Relation, table_rows: &Relation, held: &ExtentRows, columns: &[usize], extents: &[usize],contents:&Contents,example:usize) -> Result<crate::extents::Materialized<Vec<Box<[Option<Extent>]>>>,arclog::eval::ReachedBound> {
    if held.by_part() {return projected_part_rows(materializer,rows,table_rows,held,columns,extents);}
    if held.is_direct() {if let Some(e)=&contents.extents {if extents.iter().all(|&k|e.no_grid[k] || e.projected_ready(e.columns[k] as usize,columns)) {
        let allocation=materializer.admit(rows,Materializer::row_bytes(extents.len().saturating_mul(std::mem::size_of::<Option<Extent>>()),1))?;
        let mut native=vec![Term::encode_number(0);contents.columns.len()];
        let mut per_row=Vec::new();
        materializer.walk(rows,&mut |row| {
            for (&column,&cell) in columns.iter().zip(row) {native[column]=cell;}
            per_row.push(extents.iter().map(|&k|if e.no_grid[k] {None} else {e.direct_at(contents,example,e.columns[k] as usize,&native)}).collect::<Box<[_]>>());
        })?;
        return Ok(crate::extents::Materialized::new(per_row,allocation));
    }}}
    // The full matrix is already admitted, but this hash map is a genuine
    // additional allocation. Its lease lasts until the projected matrix is
    // built; the returned matrix has its own retained lease.
    let payload=columns.len().saturating_mul(std::mem::size_of::<TermId>()).saturating_add(extents.len().saturating_mul(std::mem::size_of::<Merged>())).saturating_mul(4);
    let _map_allocation=materializer.admit(table_rows,Materializer::row_bytes(payload,4))?;
    let allocation=materializer.admit(rows,Materializer::row_bytes(extents.len().saturating_mul(std::mem::size_of::<Option<Extent>>()),1))?;
    let mut merged: StableHashMap<Box<[TermId]>, Vec<Merged>> = StableHashMap::default();
    let mut at = 0u64;
    materializer.walk(table_rows, &mut |row| {
        let key: Box<[TermId]> = columns.iter().map(|&column| row[column]).collect();
        let slots = merged.entry(key).or_insert_with(|| vec![Merged::Unset; extents.len()]);
        for (slot, &extent) in slots.iter_mut().zip(extents) {
            slot.merge(held.cell(at, extent).or_else(|| {
                let evidence=contents.extents.as_ref()?;
                if evidence.no_grid[extent] {None} else {evidence.direct_at(contents,example,evidence.columns[extent] as usize,row)}
            }));
        }
        at += 1;
    })?;
    let mut per_row = Vec::new();
    materializer.walk(rows, &mut |row| per_row.push(merged.get(row).map_or_else(|| vec![None; extents.len()].into(), |slots| slots.iter().map(Merged::extent).collect())))?;
    Ok(crate::extents::Materialized::new(per_row,allocation))
}

/// [`projected_extent_rows`] where `held` holds the extents per part of
/// `table_rows`. The table rows that project to a row are those that hold, in
/// each part, a row that agrees with it at the projected columns the part
/// holds; so the extent of a column at the row is merged over the rows of the
/// column's part that agree with it, and none where a part has no such row.
fn projected_part_rows(materializer:&Materializer<'_>,rows: &Relation, table_rows: &Relation, held: &ExtentRows, columns: &[usize], extents: &[usize]) -> Result<crate::extents::Materialized<Vec<Box<[Option<Extent>]>>>,arclog::eval::ReachedBound> {
    let parts = table_rows.parts();
    // For each part, the places among `columns` of the projected columns it
    // holds, with their places in the part's rows, and the places among
    // `extents` of the extent columns it gives.
    let layout: Vec<(Vec<(usize, usize)>, Vec<usize>)> = parts.iter().enumerate().map(|(p, part)| (
        columns.iter().enumerate().filter_map(|(j, &column)| part.columns.iter().position(|own| usize::from(own.0) == column).map(|local| (j, local))).collect(),
        extents.iter().enumerate().filter(|&(_, &extent)| held.part_of(extent) == Some(p)).map(|(e, _)| e).collect(),
    )).collect();
    let payload=columns.len().saturating_mul(std::mem::size_of::<TermId>()).saturating_add(extents.len().saturating_mul(std::mem::size_of::<Merged>())).saturating_mul(4);
    let count=parts.iter().map(|part|part.rows.len() as u64).fold(0u64,u64::saturating_add);
    let _map_allocation=materializer.hold(count,usize::try_from(count).unwrap_or(usize::MAX).saturating_mul(Materializer::row_bytes(payload,4)))?;
    let allocation=materializer.admit(rows,Materializer::row_bytes(extents.len().saturating_mul(std::mem::size_of::<Option<Extent>>()),1))?;
    let mut merged: Vec<StableHashMap<Box<[TermId]>, Vec<Merged>>> = Vec::with_capacity(parts.len());
    let mut visited = 0usize;
    for (part, (projected, given)) in parts.iter().zip(&layout) {
        let mut map: StableHashMap<Box<[TermId]>, Vec<Merged>> = StableHashMap::default();
        for (at, part_row) in part.rows.rows().enumerate() {
            if visited % 1024 == 0 { materializer.check()?; }
            visited += 1;
            let key: Box<[TermId]> = projected.iter().map(|&(_, local)| part_row[local]).collect();
            let slots = map.entry(key).or_insert_with(|| vec![Merged::Unset; given.len()]);
            for (slot, &e) in slots.iter_mut().zip(given) {
                slot.merge(held.part_cell(extents[e], at));
            }
        }
        merged.push(map);
    }
    let mut per_row = Vec::new();
    materializer.walk(rows, &mut |row| {
        let mut cells = vec![None; extents.len()];
        for ((projected, given), map) in layout.iter().zip(&merged) {
            let key: Box<[TermId]> = projected.iter().map(|&(j, _)| row[j]).collect();
            let Some(slots) = map.get(&key) else { return per_row.push(vec![None; extents.len()].into()) };
            for (&e, slot) in given.iter().zip(slots) {
                cells[e] = slot.extent();
            }
        }
        per_row.push(cells.into());
    })?;
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
scalar_heap!(u8,u32,i32,u64,i64,usize,bool);
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
fields_heap!(StopColumns;bound,form,assignment);
fields_heap!(TableColumns;token,form,point,conjuncts,sites,relation,fact,column_names,column_types,column_ident_sources,column_frames,extent_columns,column_slots,column_labels,column_source_labels,width,column_widths,det_relations,det_types,det_frames,det_slots,det_labels,det_source_labels,det_widths,det_columns,projections,projections_stop,fault,depth,keys,output_position,output_color);
fields_heap!(EntryColumns;table,clause_index,example_kind,example_index,model,kind,rows,offset,stop,value_stop,fault,extent_offset,extent_stop,extent_fault,extent_status,assignment);
fields_heap!(AssignedColumns;entry,det,rows,offset);
fields_heap!(ProjectionColumns;table,columns,width);
fields_heap!(ProjectionRowColumns;projection,entry,defined,rows,offset,extent_offset,extent_status);
fields_heap!(FlowColumns;table,column,kind,source_table,source_relation,source_column,det,atom,occurrence);
fields_heap!(CopyColumns;detail);
fields_heap!(CaseColumns;tables,entries,assigned,projections,projection_rows,flows,copies,values);
fields_heap!(Named;name,row,paths,frames,slots,labels,source_labels);
