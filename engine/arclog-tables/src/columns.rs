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

use std::hash::Hash;

use arclog::decode::Projections;
use arclog::eval::copies::CopyViolation;
use arclog::eval::determinations::relation_spelled;
use arclog::eval::join::each_row;
use arclog::eval::{RelationValue, Stop};
use arclog::hash::{StableHash, StableHashMap, StableHasher};
use arclog::program::path::NodePath;
use arclog::program::{column_spelled, ColumnName, ProgramRelation, RelationRef};
use arclog::read::spelling::{spelling, FACT_RELATIONS};
use arclog::registry::Registry;
use arclog::relations::Relation;
use arclog::terms::{Constant, OrientationConstant, Term, TermId, ORIENTATION_TYPES};
use arclog::types::ValueType;

use crate::flows::{ColumnSource, SourceColumn, SourceKind};
use crate::tables::{Contents, Point, Table, TableRelation};

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
    /// The width in cells of a row.
    pub width: Vec<u32>,
    /// The relation of each `DET` the table reads, its columns' types, and
    /// the width of its rows.
    pub det_relations: Vec<Vec<String>>,
    pub det_types: Vec<Vec<Vec<String>>>,
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
/// examples.
pub fn case_columns(evidence: &[Table], tables: &[(usize, Table)], train: usize) -> CaseColumns {
    fold(evidence, tables, None, train).0
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
/// sources read the tables below `k` as [`case_columns`] reads them.
pub fn cut_case_columns(evidence: &[Table], tables: &[(usize, Table)], tokens: usize, train: usize) -> (CaseColumns, u32) {
    fold(evidence, tables, Some(tokens), train)
}

/// The fold of [`case_columns`] and [`cut_case_columns`]: the only state it
/// keeps across tables is the `names` of the tables so far and the `Runs`
/// written, so a table's columns depend on its own step and the tables before
/// it. With `cut`, the tables before it are folded into `names` alone, and the
/// count of them is given with the columns.
fn fold(evidence: &[Table], tables: &[(usize, Table)], cut: Option<usize>, train: usize) -> (CaseColumns, u32) {
    let skipped = cut.map_or(0, |tokens| evidence.len() + tables.partition_point(|(token, _)| *token < tokens));
    let mut columns = CaseColumns::default();
    let mut names = Vec::new();
    let mut runs = Runs::default();
    for (place, (token, table)) in evidence.iter().map(|table| (0, table)).chain(tables.iter().map(|(token, table)| (*token, table))).enumerate() {
        let row = u32::try_from(place).expect("fewer than 2^32 tables");
        if place < skipped {
            note_name(&mut names, row, table);
        } else {
            push_table(&mut columns, &mut names, &mut runs, row, token, table, train);
        }
    }
    (columns, u32::try_from(skipped).expect("fewer than 2^32 tables"))
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
#[derive(Default)]
struct Runs(StableHashMap<(u64, usize, StableHash), Vec<usize>>);

/// The count of rows and the offset of the run of the rows of `rows`, of
/// columns of `types`, in the order of their cells: where `values` holds a run
/// with the same count of rows and the same cells, that run, and otherwise
/// the run that this call appends to `values`. A run without a cell has
/// offset 0.
fn push_rows(values: &mut Vec<i32>, runs: &mut Runs, rows: &Relation, types: &[ValueType]) -> (u64, u64) {
    let mut written: Vec<Vec<i32>> = Vec::new();
    each_row(rows, &mut |row| {
        let mut cells = Vec::new();
        for (&id, ty) in row.iter().zip(types) {
            push_cells(&mut cells, id, ty);
        }
        written.push(cells);
    });
    written.sort();
    let count = written.len() as u64;
    let cells: Vec<i32> = written.into_iter().flatten().collect();
    if cells.is_empty() {
        return (count, 0);
    }
    let mut hasher = StableHasher::new();
    cells.hash(&mut hasher);
    let offsets = runs.0.entry((count, cells.len(), hasher.finish128())).or_default();
    if let Some(&offset) = offsets.iter().find(|&&offset| values[offset..offset + cells.len()] == cells[..]) {
        return (count, offset as u64);
    }
    let offset = values.len();
    offsets.push(offset);
    values.extend(cells);
    (count, offset as u64)
}

/// The name of the relation that the tables of `names` stand for, each with
/// its row, in the order of the rows: the relation as the program spells it,
/// or the fact relation's name.
type TableNames = Vec<(String, u32, Option<Vec<Box<[ColumnName]>>>)>;

/// The columns of `table`, the table at `row`, after the tables before it.
fn push_table(out: &mut CaseColumns, names: &mut TableNames, runs: &mut Runs, row: u32, token: usize, table: &Table, train: usize) {
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
            tables.width.push(0);
            tables.det_relations.push(Vec::new());
            tables.det_types.push(Vec::new());
            tables.det_widths.push(Vec::new());
            tables.det_columns.push(Vec::new());
            tables.projections.push(ProjectionsKind::None as u8);
            tables.projections_stop.push(None);
            tables.fault.push(Some(format!("{} at {}", fault.message, form_path(&fault.form))));
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
            tables.width.push(row_width(&types));
            tables.det_relations.push(contents.dets.iter().map(|det| relation_spelled(&det.relation)).collect());
            tables.det_types.push(contents.dets.iter().map(|det| type_names(&det.types)).collect());
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
            note_name(names, row, table);
            push_contents(out, runs, row, contents, &types, train);
        }
    }
}

/// Adds the relation of `table`, the table at `row`, to `names`, if it stands
/// for one: a table of a relation that has not faulted.
fn note_name(names: &mut TableNames, row: u32, table: &Table) {
    let Ok(contents) = &table.contents else { return };
    if matches!(table.point, Point::Body { .. }) {
        return;
    }
    let name = match contents.relation {
        TableRelation::Slot(_) => contents.name.clone(),
        TableRelation::Fact(fact) => spelling(FACT_RELATIONS, &fact).to_owned(),
    };
    names.push((name, row, contents.rows.clone()));
}

/// The relation `relation` as the program spells it, a fact relation's name,
/// or the lib name.
fn source_spelled(relation: &RelationRef) -> String {
    match relation {
        RelationRef::Fact(fact) => spelling(FACT_RELATIONS, fact).to_owned(),
        RelationRef::Lib(name) => name.0.to_string(),
        RelationRef::Declared(name) => relation_spelled(&ProgramRelation::Declared(name.clone())),
        RelationRef::Output(name) => relation_spelled(&ProgramRelation::Output(name.clone())),
        RelationRef::DefinedPort(port) => port.0.to_string(),
    }
}

/// The sources of each column of `contents`, the table at `row`. A source's
/// table is the latest of `names` that stands for its relation.
fn push_flows(out: &mut CaseColumns, names: &TableNames, row: u32, contents: &Contents) {
    let dets: Vec<String> = contents.dets.iter().map(|det| relation_spelled(&det.relation)).collect();
    for (column, sources) in contents.flows.iter().enumerate() {
        for ColumnSource { kind, relation, column: source_column, row: source_row, atom, occurrence } in sources {
            let spelled = relation.as_ref().map(source_spelled).unwrap_or_default();
            let source = match kind {
                SourceKind::Copy | SourceKind::Computed => names.iter().rev().find(|(name, ..)| *name == spelled),
                SourceKind::Constant | SourceKind::LibName => None,
            };
            let table = source.map_or(-1, |&(_, table, _)| table as i32);
            let det = match kind {
                SourceKind::Copy | SourceKind::Computed => dets.iter().position(|det| *det == spelled).map_or(-1, |place| place as i32),
                SourceKind::Constant | SourceKind::LibName => -1,
            };
            // The source's table was exported with the order its columns had
            // then; a later form may have reordered them. A `DET` source's
            // column indexes the reading table's own `DET` columns.
            let exported = match (source.and_then(|(_, _, rows)| rows.as_ref()), source_row) {
                (Some(rows), Some(path)) if det < 0 => Some(rows.iter().position(|row| row == path)),
                _ => None,
            };
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

/// The entries of `contents`, the table at `row`, and its projections.
fn push_contents(out: &mut CaseColumns, runs: &mut Runs, row: u32, contents: &Contents, types: &[ValueType], train: usize) {
    let count_only = contents.projections.is_some();
    let mut starts = Vec::with_capacity(contents.examples.len());
    for example in contents.examples.iter() {
        starts.push(out.entries.table.len());
        let (kind, index) = match example.example {
            None => (0, 0),
            Some(example) => {
                let index = usize::from(example.index());
                if index < train { (1, index) } else { (2, index - train) }
            }
        };
        let index = u32::try_from(index).expect("fewer than 2^32 examples");
        let push = |out: &mut CaseColumns, runs: &mut Runs, model: u32, value: Option<&RelationValue>, stop: Option<&Stop>, fault: Option<String>| {
            let faulted = fault.is_some();
            let entries = &mut out.entries;
            entries.table.push(row);
            entries.example_kind.push(kind);
            entries.example_index.push(index);
            entries.model.push(model);
            entries.stop.push(stop);
            entries.fault.push(fault);
            let (value_kind, rows, offset, value_stop) = match value {
                None if faulted => (ValueKind::Fault, 0, 0, None),
                None => (ValueKind::NoEntries, 0, 0, None),
                Some(RelationValue::Rows(rows)) if count_only => (ValueKind::Count, rows.len() as u64, 0, None),
                Some(RelationValue::Rows(rows)) => {
                    let (count, offset) = push_rows(&mut out.values, runs, rows, types);
                    (ValueKind::Rows, count, offset, None)
                }
                Some(RelationValue::Undefined) => (ValueKind::Undefined, 0, 0, None),
                Some(RelationValue::Stopped(stop)) => (ValueKind::Stopped, 0, 0, Some(stop)),
            };
            let entries = &mut out.entries;
            entries.kind.push(value_kind as u8);
            entries.rows.push(rows);
            entries.offset.push(offset);
            entries.value_stop.push(value_stop);
        };
        match &example.rows {
            Err(fault) => push(out, runs, 0, None, None, Some(format!("{} at {}", fault.message, form_path(&fault.form)))),
            Ok(rows) => {
                if rows.at.is_empty() {
                    push(out, runs, 0, None, rows.stop.as_ref(), None);
                }
                for (assigned, models) in &rows.at {
                    let first = out.entries.table.len();
                    for (model, value) in models.iter().enumerate() {
                        push(out, runs, model as u32, Some(value), rows.stop.as_ref(), None);
                    }
                    let mut assigned_runs = Vec::new();
                    for (position, ((_, det_rows), det)) in assigned.iter().zip(contents.dets.iter()).enumerate() {
                        let (count, offset) = push_rows(&mut out.values, runs, det_rows, &det.types);
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
        for projection in found {
            let projection_row = out.projections.table.len() as u32;
            let projection_types: Vec<ValueType> = projection.columns.iter().map(|column| types[column.0 as usize].clone()).collect();
            out.projections.table.push(row);
            out.projections.columns.push(projection.columns.iter().map(|column| u32::from(column.0)).collect());
            out.projections.width.push(row_width(&projection_types));
            for (example, assigned) in projection.rows.iter().enumerate() {
                for (at, (_, projection)) in assigned.at.iter().enumerate() {
                    let (defined, count, offset) = match projection {
                        None => (0, 0, 0),
                        Some(rows) => {
                            let (count, offset) = push_rows(&mut out.values, runs, rows, &projection_types);
                            (1, count, offset)
                        }
                    };
                    out.projection_rows.projection.push(projection_row);
                    out.projection_rows.entry.push((starts[example] + at) as u32);
                    out.projection_rows.defined.push(defined);
                    out.projection_rows.rows.push(count);
                    out.projection_rows.offset.push(offset);
                }
            }
        }
    }
}
