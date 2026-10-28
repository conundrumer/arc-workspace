//! The tables of one case program as the Python class `CaseTables`: the
//! flat columns of [`arclog_tables::columns`], each part a dict of columns.

use arclog_tables::columns::{CaseColumns, StopColumns, TableColumns};
use pyo3::prelude::*;
use pyo3::types::{PyBytes, PyDict};

/// The tables of one case program of a solver of a corpus, as flat columns
/// (`arclog_tables::columns` gives the layout and the codes).
///
/// `tables`, `entries`, `assigned`, `projections`, `projection_rows`, `flows` and `copies` are dicts of
/// columns, one for each part of the layout, named as its fields. An integer
/// column is `bytes` in native byte order, which `numpy.frombuffer` reads at
/// the dtype that `dtypes` gives for `"<part>.<column>"`; any other column is
/// a list. `values` is the `int32` cells of every row, which the offsets of the
/// parts index. The first two tables are the evidence tables of the task,
/// `ex_input` and `ex_output`, at token 0, with point 2 and the relation's
/// name in `fact`. `tables` also gives each table's `relation_name`, its relation as the
/// case program writes it, `&x` for a declared relation and `&<instance>.<port>` for an
/// output or input of an instance, the fact relation's name for an evidence table, and
/// `None` for a table that faulted, and, in the `CaseTables` of `stream_tables`, for each
/// table at a slot; it also gives each table's `depth` in the dependency graph, its
/// candidate `keys` (lists of column indexes), and `output_position` and `output_color`,
/// the grid columns of the relation at which the replay's consistency test found them, -1
/// for each other table; `flows` gives one row for each source of each column of a table,
/// with its `occurrence`, the row of the source atom's relation that the value comes from, -1 where
/// it claims none; `copies` gives one row, its `detail` a sentence, for each declared row of a
/// component's output that the replay found the output's rows break, and none for a call without
/// `copies`.
/// `tables` gives, beside `column_types` and `det_types`, the frame that the values of each column
/// stand in: `column_frames`, one string per column in the order of `column_names`, and `det_frames`,
/// for each `DET` one string per column in the order of its `det_types`. A frame is
///
/// - `input`: the frame of the task's input grid, and `output`: of its output grid;
/// - `<maker>@<path>`: a frame that a lib column makes, one per row of the atom or the instance at
///   `<path>`. `<maker>` is `<relation>.<column>` for a lib relation or a relation macro, such as
///   `relative.X_rel`, and `<component>.<output>.<column>` for a component's output, such as
///   `Division.tile.P_inner`. `<path>` is the path of the atom or of the `INIT` form as the `atom` of
///   `flows` spells a path. A frame that `apply.P_out` makes is a frame of its own at each row, with
///   no ` in <frame>`: its extent is `P`'s frame's, with V and H swapped where the row's `D` moves the
///   top edge to the left or the right edge;
/// - `<maker>@<path> in <frame>`: such a frame, lying in `<frame>`, as `relative.X_rel@<path> in input`;
/// - the empty string: no frame. Only a column of type `Position` or `Box` has a frame, and a column
///   whose sources give no frame, or give two different frames, has none.
///
/// `tables` also gives `extent_columns`: the indexes, in increasing order, of the table's columns of type
/// `Box` whose frame is a made frame, empty for every other table. For such a table `entries` and
/// `projection_rows` give `extent_offset`, the offset in `values` of the run of the extents of those
/// frames: for each row of the entry's run (of the projection row's run), in its order, two `int32`
/// cells for each column of `extent_columns` (for each of the projection's columns among them), in their
/// order, the frame's count of rows V and then of columns H at that row, and `-1 -1` for a row with no
/// extent, which is a row whose derivations give two extents or whose extent the engine cannot compute;
/// -1 where the table has no extent columns, the entry holds no rows, its extents stopped, in which
/// case `extent_stop_bound` and `extent_stop_form` of `entries` give the stop, or the extents do not
/// derive its rows, in which case `extent_fault` of `entries` gives the reason: the fault of the widened
/// evaluation of a body that gives the rows, as `fault` spells it, or why the extents do not derive them.
/// A Box value in a frame of extent (V, H) has own size (V - top - bottom, H - left - right), which says
/// which cells of its frame it covers.
///
/// `tables` also gives `column_slots` and `column_labels`, one entry per column in the order of
/// `column_names`: the column's slot in the relation's own column order (-1 where the engine
/// knows none) and the name of the label that the table's form writes at it (the empty string
/// where none), and `det_slots` and `det_labels`, for each `DET` one entry per column in the order of
/// its `det_types`, those of that column in the latest table of the `DET`'s relation. The name in
/// `column_labels` is the name that the decoded program gives the label. `tables` also gives
/// `column_source_labels` and `det_source_labels`, of the shapes of `column_labels` and `det_labels`, with
/// the name that the case's `.arclog` text writes for the label: in the `CaseTables` of `corpus_tables`,
/// the text that `arclog::stream::corpus::case_files` writes for the case, or, for a case whose files the
/// corpus's `cases/` directory holds, those files; in those of `stream_tables` and `step_tables`, whose
/// program comes from a decode, the entries of `column_labels` and `det_labels`.
///
/// `projection_cap` is the cap of the projection rows that the tables ran
/// under.
///
/// A case of `stream_tables` that has a base holds the tables of the steps
/// from its token `base_tokens` on alone: `base` is the base's case name,
/// `base_tokens` the length of the prefix of tokens that the case shares with
/// it, and `base_tables` the count `k` of the base's tables before that prefix
/// (the 2 evidence tables and each table whose token is below `base_tokens`).
/// The case's tables are numbered from `k`, and each table number in its
/// parts names the base's table of that number where it is below `k`. The
/// three are `None` for every other case.
#[pyclass(name = "CaseTables", frozen, get_all, module = "arclog")]
pub(crate) struct PyCaseTables {
    task: String,
    case: String,
    concept: bool,
    projection_cap: u64,
    base: Option<String>,
    base_tokens: Option<usize>,
    base_tables: Option<u32>,
    tables: Py<PyDict>,
    entries: Py<PyDict>,
    assigned: Py<PyDict>,
    projections: Py<PyDict>,
    projection_rows: Py<PyDict>,
    flows: Py<PyDict>,
    copies: Py<PyDict>,
    values: Py<PyBytes>,
    dtypes: Py<PyDict>,
}

/// An integer type of a column, with its numpy dtype and its native bytes.
trait Cell: Copy {
    const DTYPE: &'static str;
    fn extend(self, bytes: &mut Vec<u8>);
}

macro_rules! cell {
    ($ty:ty, $dtype:literal) => {
        impl Cell for $ty {
            const DTYPE: &'static str = $dtype;
            fn extend(self, bytes: &mut Vec<u8>) {
                bytes.extend(self.to_ne_bytes());
            }
        }
    };
}
cell!(u8, "uint8");
cell!(u32, "uint32");
cell!(u64, "uint64");
cell!(i32, "int32");
cell!(i64, "int64");

fn cell_bytes<T: Cell>(column: &[T]) -> Vec<u8> {
    let mut bytes = Vec::with_capacity(column.len() * size_of::<T>());
    for &cell in column {
        cell.extend(&mut bytes);
    }
    bytes
}

/// The dict of one part of a case's columns, and the dtype of each of its
/// integer columns in `dtypes`.
struct Part<'a, 'py> {
    dict: Bound<'py, PyDict>,
    name: &'static str,
    dtypes: &'a Bound<'py, PyDict>,
}

impl<'a, 'py> Part<'a, 'py> {
    fn new(py: Python<'py>, name: &'static str, dtypes: &'a Bound<'py, PyDict>) -> Self {
        Part { dict: PyDict::new(py), name, dtypes }
    }

    fn ints<T: Cell>(&self, key: &str, column: &[T]) -> PyResult<()> {
        self.dict.set_item(key, PyBytes::new(self.dict.py(), &cell_bytes(column)))?;
        self.dtypes.set_item(format!("{}.{key}", self.name), T::DTYPE)
    }

    fn list<V: IntoPyObject<'py>>(&self, key: &str, column: V) -> PyResult<()> {
        self.dict.set_item(key, column)
    }

    fn stop(&self, key: &str, stop: &StopColumns) -> PyResult<()> {
        self.list(&format!("{key}_bound"), &stop.bound)?;
        self.list(&format!("{key}_form"), &stop.form)
    }
}

/// The `relation_name` of each table: the spelling at the table's slot, the
/// fact relation's name for an evidence table, and `None` for a table that
/// faulted, or, where `relations` is `None`, for a table at a slot.
fn relation_names(tables: &TableColumns, relations: Option<&[String]>) -> Vec<Option<String>> {
    tables
        .relation
        .iter()
        .zip(&tables.fact)
        .map(|(&slot, fact)| match (usize::try_from(slot), relations) {
            (Ok(slot), Some(relations)) => Some(relations.get(slot).unwrap_or_else(|| panic!("the slot {slot} of a table stands in the case program's relations")).clone()),
            (Ok(_), None) => None,
            (Err(_), _) => fact.clone(),
        })
        .collect()
}

/// The base of a case that holds the tables after a prefix alone: the base's
/// case name, the tokens of the prefix and the count of the base's tables
/// before it.
pub(crate) struct Base {
    pub(crate) case: String,
    pub(crate) tokens: usize,
    pub(crate) tables: u32,
}

impl PyCaseTables {
    /// `relations` is the spelling of the relation declared at each slot of the
    /// case program, or `None` for a stream that no case program writes. `base`
    /// is the base of a case whose `columns` are cut.
    pub(crate) fn of(py: Python<'_>, task: String, case: String, concept: bool, projection_cap: u64, columns: &CaseColumns, relations: Option<&[String]>, base: Option<Base>) -> PyResult<Self> {
        let dtypes = PyDict::new(py);
        let t = Part::new(py, "tables", &dtypes);
        let c = &columns.tables;
        t.ints("token", &c.token)?;
        t.list("form", &c.form)?;
        t.ints("point", &c.point)?;
        t.ints("conjuncts", &c.conjuncts)?;
        t.ints("sites", &c.sites)?;
        t.ints("relation", &c.relation)?;
        t.list("fact", &c.fact)?;
        t.list("relation_name", relation_names(c, relations))?;
        t.list("column_names", &c.column_names)?;
        t.list("column_types", &c.column_types)?;
        t.list("column_frames", &c.column_frames)?;
        t.list("extent_columns", &c.extent_columns)?;
        t.list("column_slots", &c.column_slots)?;
        t.list("column_labels", &c.column_labels)?;
        t.list("column_source_labels", &c.column_source_labels)?;
        t.ints("width", &c.width)?;
        t.list("det_relations", &c.det_relations)?;
        t.list("det_types", &c.det_types)?;
        t.list("det_frames", &c.det_frames)?;
        t.list("det_slots", &c.det_slots)?;
        t.list("det_labels", &c.det_labels)?;
        t.list("det_source_labels", &c.det_source_labels)?;
        t.list("det_widths", &c.det_widths)?;
        t.list("det_columns", &c.det_columns)?;
        t.ints("projections", &c.projections)?;
        t.stop("projections_stop", &c.projections_stop)?;
        t.list("fault", &c.fault)?;
        t.ints("depth", &c.depth)?;
        t.list("keys", &c.keys)?;
        t.ints("output_position", &c.output_position)?;
        t.ints("output_color", &c.output_color)?;
        let e = Part::new(py, "entries", &dtypes);
        let c = &columns.entries;
        e.ints("table", &c.table)?;
        e.ints("example_kind", &c.example_kind)?;
        e.ints("example_index", &c.example_index)?;
        e.ints("model", &c.model)?;
        e.ints("kind", &c.kind)?;
        e.ints("rows", &c.rows)?;
        e.ints("offset", &c.offset)?;
        e.stop("stop", &c.stop)?;
        e.stop("value_stop", &c.value_stop)?;
        e.list("fault", &c.fault)?;
        e.ints("extent_offset", &c.extent_offset)?;
        e.stop("extent_stop", &c.extent_stop)?;
        e.list("extent_fault", &c.extent_fault)?;
        let a = Part::new(py, "assigned", &dtypes);
        let c = &columns.assigned;
        a.ints("entry", &c.entry)?;
        a.ints("det", &c.det)?;
        a.ints("rows", &c.rows)?;
        a.ints("offset", &c.offset)?;
        let v = Part::new(py, "projections", &dtypes);
        let c = &columns.projections;
        v.ints("table", &c.table)?;
        v.list("columns", &c.columns)?;
        v.ints("width", &c.width)?;
        let r = Part::new(py, "projection_rows", &dtypes);
        let c = &columns.projection_rows;
        r.ints("projection", &c.projection)?;
        r.ints("entry", &c.entry)?;
        r.ints("defined", &c.defined)?;
        r.ints("rows", &c.rows)?;
        r.ints("offset", &c.offset)?;
        r.ints("extent_offset", &c.extent_offset)?;
        let f = Part::new(py, "flows", &dtypes);
        let c = &columns.flows;
        f.ints("table", &c.table)?;
        f.ints("column", &c.column)?;
        f.ints("kind", &c.kind)?;
        f.ints("source_table", &c.source_table)?;
        f.list("source_relation", &c.source_relation)?;
        f.ints("source_column", &c.source_column)?;
        f.ints("det", &c.det)?;
        f.list("atom", &c.atom)?;
        f.ints("occurrence", &c.occurrence)?;
        let k = Part::new(py, "copies", &dtypes);
        k.list("detail", &columns.copies.detail)?;
        Ok(PyCaseTables {
            task,
            case,
            concept,
            projection_cap,
            base_tokens: base.as_ref().map(|base| base.tokens),
            base_tables: base.as_ref().map(|base| base.tables),
            base: base.map(|base| base.case),
            tables: t.dict.unbind(),
            entries: e.dict.unbind(),
            assigned: a.dict.unbind(),
            projections: v.dict.unbind(),
            projection_rows: r.dict.unbind(),
            flows: f.dict.unbind(),
            copies: k.dict.unbind(),
            values: PyBytes::new(py, &cell_bytes(&columns.values)).unbind(),
            dtypes: dtypes.unbind(),
        })
    }
}
