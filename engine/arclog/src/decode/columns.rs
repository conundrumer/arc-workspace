//! The tables of one case program as flat columns, for a reader that slices
//! arrays and parses no text: the layout of [`CaseColumns`].
//!
//! Each of its parts holds one row for each item, in a column of its own:
//!
//! - [`TableColumns`]: a table, in the order of the stream;
//! - [`EntryColumns`]: a table, an example and an entry of its rows, which
//!   is a model at an assignment of the `DET`s;
//! - [`AssignedColumns`]: a `DET` at an entry's assignment;
//! - [`ViewColumns`] and [`ViewRowColumns`]: a view of a table, and the
//!   view's rows at an entry.
//!
//! Every row of every table is a run of cells in `values`, each cell an
//! `i32` by the type of its column: a Box its four margins (top, bottom,
//! left, right), a Color its digit, a Number itself, an Example its index, a
//! Unit 0, and an orientation constant, a `Pose` by its D4 constant, its
//! encoding, which [`orientation_names`] names. An Ident is its number, which
//! depends on the order of interning, so it is equal to another Ident of the
//! same run and to no Ident of another. A run is an offset in `values` and a
//! count of rows, and its width in cells is the table's, or the `DET`'s, or
//! the view's. The rows of a run are in the order of their cells.

use super::{Contents, Point, Table, Views};
use crate::eval::determinations::relation_spelled;
use crate::eval::join::each_row;
use crate::eval::{RelationValue, Stop};
use crate::program::path::NodePath;
use crate::registry::Registry;
use crate::relations::Relation;
use crate::terms::{Constant, OrientationConstant, Term, TermId, ORIENTATION_TYPES};
use crate::types::ValueType;

/// The point of a table, as the code in [`TableColumns::point`].
#[derive(Clone, Copy, PartialEq, Eq, Debug)]
#[repr(u8)]
pub enum PointKind {
    Relation = 0,
    Body = 1,
}

/// What the views of a table are, as the code in [`TableColumns::views`].
#[derive(Clone, Copy, PartialEq, Eq, Debug)]
#[repr(u8)]
pub enum ViewsKind {
    /// The table gives its rows, and no views.
    None = 0,
    /// The search stopped at a bound.
    Stopped = 1,
    /// The views, possibly none.
    Found = 2,
}

/// What an entry holds, as the code in [`EntryColumns::kind`].
#[derive(Clone, Copy, PartialEq, Eq, Debug)]
#[repr(u8)]
pub enum ValueKind {
    /// Rows, in the run of the entry.
    Rows = 0,
    /// The count of rows alone, since the table gives views.
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

/// One row for each table. A table whose contents fault holds `fault`, and
/// a relation slot of -1, no columns and no `DET`s.
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
    /// The relation's slot.
    pub relation: Vec<i32>,
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
    /// The [`ViewsKind`] code.
    pub views: Vec<u8>,
    /// The bound that stopped the views, and its form.
    pub views_stop: StopColumns,
    pub fault: Vec<Option<String>>,
}

/// One row for each entry of a table on an example, in the order of the
/// tables, the examples, the assignments and the models.
#[derive(Clone, Debug, Default)]
pub struct EntryColumns {
    /// The row of the table in [`TableColumns`].
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

/// One row for each view of a table whose views are found.
#[derive(Clone, Debug, Default)]
pub struct ViewColumns {
    pub table: Vec<u32>,
    /// The columns of the table that the view projects, in increasing order.
    pub columns: Vec<Vec<u32>>,
    /// The width in cells of a view row.
    pub width: Vec<u32>,
}

/// One row for each view at each entry of its table.
#[derive(Clone, Debug, Default)]
pub struct ViewRowColumns {
    /// The row of the view in [`ViewColumns`].
    pub view: Vec<u32>,
    /// The row of the entry in [`EntryColumns`].
    pub entry: Vec<u32>,
    /// 0 where the entry holds no rows, and 1 where it gives its projection.
    pub defined: Vec<u8>,
    pub rows: Vec<u64>,
    pub offset: Vec<u64>,
}

/// The tables of one case program as columns.
#[derive(Clone, Debug, Default)]
pub struct CaseColumns {
    pub tables: TableColumns,
    pub entries: EntryColumns,
    pub assigned: AssignedColumns,
    pub views: ViewColumns,
    pub view_rows: ViewRowColumns,
    pub values: Vec<i32>,
}

/// The columns of `tables`, each with the index of its token, on a task of
/// `train` train pairs, which names the examples.
pub fn case_columns(tables: &[(usize, Table)], train: usize) -> CaseColumns {
    let mut columns = CaseColumns::default();
    for (token, table) in tables {
        push_table(&mut columns, *token, table, train);
    }
    columns
}

/// The name of each orientation constant by its encoding, the cell of its
/// value, in the order of the encodings.
pub fn orientation_names(registry: &Registry) -> Vec<(i32, String)> {
    let mut names: Vec<(i32, String)> = ORIENTATION_TYPES.iter().flat_map(|&ty| registry.constants_of(ty).each()).map(|constant| (orientation_cell(constant), registry.constant_name(constant).to_owned())).collect();
    names.sort();
    names
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

/// The width in cells of a row of columns of `types`.
fn row_width(types: &[ValueType]) -> u32 {
    types.iter().map(|ty| if *ty == ValueType::Box { 4 } else { 1 }).sum()
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

/// Appends the rows of `rows`, of columns of `types`, to `values`, in the
/// order of their cells, and gives the count of rows and the offset of the
/// first.
fn push_rows(values: &mut Vec<i32>, rows: &Relation, types: &[ValueType]) -> (u64, u64) {
    let mut written: Vec<Vec<i32>> = Vec::new();
    each_row(rows, &mut |row| {
        let mut cells = Vec::new();
        for (&id, ty) in row.iter().zip(types) {
            push_cells(&mut cells, id, ty);
        }
        written.push(cells);
    });
    written.sort();
    let offset = values.len() as u64;
    let count = written.len() as u64;
    values.extend(written.into_iter().flatten());
    (count, offset)
}

fn push_table(out: &mut CaseColumns, token: usize, table: &Table, train: usize) {
    let row = u32::try_from(out.tables.token.len()).expect("fewer than 2^32 tables");
    let tables = &mut out.tables;
    tables.token.push(u32::try_from(token).expect("fewer than 2^32 tokens"));
    tables.form.push(form_path(&table.form));
    let (kind, conjuncts, sites) = match table.point {
        Point::Body { conjuncts, sites } => (PointKind::Body, conjuncts, sites),
        Point::Relation => (PointKind::Relation, 0, 0),
    };
    tables.point.push(kind as u8);
    tables.conjuncts.push(conjuncts);
    tables.sites.push(sites);
    match &table.contents {
        Err(fault) => {
            tables.relation.push(-1);
            tables.column_names.push(Vec::new());
            tables.column_types.push(Vec::new());
            tables.width.push(0);
            tables.det_relations.push(Vec::new());
            tables.det_types.push(Vec::new());
            tables.det_widths.push(Vec::new());
            tables.views.push(ViewsKind::None as u8);
            tables.views_stop.push(None);
            tables.fault.push(Some(format!("{} at {}", fault.message, form_path(&fault.form))));
        }
        Ok(contents) => {
            let types: Vec<ValueType> = contents.columns.iter().map(|column| column.ty.clone()).collect();
            tables.relation.push(i32::try_from(contents.relation).expect("a slot within an i32"));
            tables.column_names.push(contents.columns.iter().map(|column| column.name.clone()).collect());
            tables.column_types.push(type_names(&types));
            tables.width.push(row_width(&types));
            tables.det_relations.push(contents.dets.iter().map(|det| relation_spelled(&det.relation)).collect());
            tables.det_types.push(contents.dets.iter().map(|det| type_names(&det.types)).collect());
            tables.det_widths.push(contents.dets.iter().map(|det| row_width(&det.types)).collect());
            let (views, stop) = match &contents.views {
                None => (ViewsKind::None, None),
                Some(Views::Stopped(stop)) => (ViewsKind::Stopped, Some(stop)),
                Some(Views::Found(_)) => (ViewsKind::Found, None),
            };
            tables.views.push(views as u8);
            tables.views_stop.push(stop);
            tables.fault.push(None);
            push_contents(out, row, contents, &types, train);
        }
    }
}

/// The entries of `contents`, the table at `row`, and its views.
fn push_contents(out: &mut CaseColumns, row: u32, contents: &Contents, types: &[ValueType], train: usize) {
    let count_only = contents.views.is_some();
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
        let push = |out: &mut CaseColumns, model: u32, value: Option<&RelationValue>, stop: Option<&Stop>, fault: Option<String>| {
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
                    let (count, offset) = push_rows(&mut out.values, rows, types);
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
            Err(fault) => push(out, 0, None, None, Some(format!("{} at {}", fault.message, form_path(&fault.form)))),
            Ok(rows) => {
                if rows.at.is_empty() {
                    push(out, 0, None, rows.stop.as_ref(), None);
                }
                for (assigned, models) in &rows.at {
                    let first = out.entries.table.len();
                    for (model, value) in models.iter().enumerate() {
                        push(out, model as u32, Some(value), rows.stop.as_ref(), None);
                    }
                    let mut runs = Vec::new();
                    for (position, ((_, det_rows), det)) in assigned.iter().zip(contents.dets.iter()).enumerate() {
                        let (count, offset) = push_rows(&mut out.values, det_rows, &det.types);
                        runs.push((position as u32, count, offset));
                    }
                    for entry in first..out.entries.table.len() {
                        for &(position, count, offset) in &runs {
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
    if let Some(Views::Found(found)) = &contents.views {
        for view in found {
            let view_row = out.views.table.len() as u32;
            let view_types: Vec<ValueType> = view.columns.iter().map(|column| types[column.0 as usize].clone()).collect();
            out.views.table.push(row);
            out.views.columns.push(view.columns.iter().map(|column| u32::from(column.0)).collect());
            out.views.width.push(row_width(&view_types));
            for (example, assigned) in view.rows.iter().enumerate() {
                for (at, (_, projection)) in assigned.at.iter().enumerate() {
                    let (defined, count, offset) = match projection {
                        None => (0, 0, 0),
                        Some(rows) => {
                            let (count, offset) = push_rows(&mut out.values, rows, &view_types);
                            (1, count, offset)
                        }
                    };
                    out.view_rows.view.push(view_row);
                    out.view_rows.entry.push((starts[example] + at) as u32);
                    out.view_rows.defined.push(defined);
                    out.view_rows.rows.push(count);
                    out.view_rows.offset.push(offset);
                }
            }
        }
    }
}
