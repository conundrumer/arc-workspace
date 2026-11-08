//! The tables of one case program as the Python class `CaseTables`: the
//! flat columns of [`arclog_tables::columns`], each part a dict of columns.

use std::cell::RefCell;
use std::sync::Arc;

use arclog_tables::columns::{CaseColumns, StopColumns, StreamTables, TableColumns};
use arclog_tables::shape_rows::ShapeRows;

use crate::shapes::{PyTableShapes, ShapeRuntime};
use crate::spill::Spilled;
use pyo3::prelude::*;
use pyo3::types::{PyBool, PyBytes, PyDict, PyCapsule, PyInt, PyList, PyModule, PyTuple};
use pyo3::sync::PyOnceLock;

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
/// `tables` gives `column_ident_sources`, one string per column in the order of `column_names`: the
/// source of each Ident of the column's type, the form that makes its values, as 32 hexadecimal digits,
/// joined by `,` for a Record, and the empty string for a type with no Ident of a source. Two columns
/// hold values of one type where their `column_types` and their `column_ident_sources` are equal.
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
/// `tables` gives `column_widths`, one entry per column in the order of `column_names`: the column's width in cells, 4 for a column of
/// type `Box`, `Position` or `Offset` and 1 for any other, which add up to the table's `width`. In the result of `step_tables` and
/// `successor_tables` (by assignment), with summaries, `tables` also gives, for each row, one entry per column in the order of
/// `column_names`, each an empty list where the row's assignment has no `hash`:
///
/// - `column_value_hashes`: the column's value hash, a Python int of 128 bits. It depends on the column's content alone: its type, and, for
///   each example, the Set of the column's cells over the example's rows, so it holds no row order, label name, authored name or order of
///   a map or a set, and it is the same under any `ARCLOG_MAP_SEED`. Two tables of equal content up to a permutation of their columns
///   give each column the same hash, so ordering columns by (`column_type_keys`, `column_value_hashes`) gives one order for equal contents
///   where no column has a `column_ties` of 2. Columns that tie in their type and base hash are told apart by how they relate to the
///   other columns before the hash is given (the module doc of `arclog_tables::summary::column_hash` has the definition and the argument);
/// - `column_type_keys`: the column's type name as the TableHash writes it, which equals `column_types` for each type but two kinds. An
///   Ident type's name holds its source, as the type check gives it: `Ident(Open)`, or `Ident(Form(<32 hexadecimal digits>))`. A Pose type's
///   name holds the QueryHash of its `RIGID_DET` in place of its slots. A Record's name holds the names of these kinds in its fields. Order
///   by this, not by `column_types`;
/// - `column_ties`: 0 where no other column has the column's type key and value hash, 1 where another does and every exchange of those columns
///   leaves the table as it is, so that any order among them gives the same table, and 2 where another does and that was not shown (the order
///   among them is open).
///
/// `tables` also gives `column_order` in each result of `step_tables` and `successor_tables` (by assignment), with or without summaries: for
/// each row, the order of the table's columns under which the row's `hash` was computed, as a list with one entry for each canonical place,
/// the column at that place, as an index into `column_names`. It is an empty list where the row's assignment has no `hash`. Take two rows with
/// equal `hash`es, and map each column of one to the column at the same place of the other. Each such pair of columns has equal
/// `column_type_keys` and `column_value_hashes` (where the result gives them), and under the map each example's Set of TableRows is equal.
/// This holds for a column with a `column_ties` of 2 whose tie the search ordered, as for a column with a `column_ties` of 0 or 1. Where a
/// class of columns is exchangeable (`column_ties` 1), the order of its columns in the list is one of the orders that give the table.
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
/// A query that `gold_tables` stops at the binding cap or the row cap ends its assignment: each later query
/// at values that hold that assignment, at any example, takes the same stop and does not run.
///
/// `gold_tables` also gives identities, which depend on no name and no order that the program's author
/// chose (a rename of the declared relations, instances and labels, a reorder of the top-level forms that
/// keeps dependency order, of a body's conjuncts, of an `OR`'s branches and of the columns a clause writes
/// change none of them, apart from a swap of two things that a symmetry of the content exchanges):
///
/// - `tables.ident`, one string per table: 32 hexadecimal digits, the hash of the resolved content of the
///   table's query, so two tables of any two case programs have one `ident` where the contents of their
///   queries are equal. A port of an instance (and a part of a `RIGID_DET` form) has the hash of its form's
///   content and the port's name in the lib; a fact relation's table has the hash of the relation's name.
///   The empty string for a table with no identity: one that faulted or stands at a body in progress.
/// - `tables.column_idents`, per table one string per column in the order of `column_names`: the lib's
///   column name for a column the lib declares (the columns of a fact relation, a port's columns other than
///   a field of a record, a proposer's columns), `<lib column>.#<n>` for a field of the record of a lib
///   column (`key.#2`, `t.#4`, `a.#2`), and `#<n>` for every other column, with `n` the canonical position
///   of the column's label (the least of the positions of the labels that several heads bind to the field)
///   in the labeling of its form's label scope under the resolver's writer. No identity holds a name from
///   the program's text. The identities of the columns of one table differ.
/// - `flows.atom_form` and `flows.atom_path`, one string per flow: the identity (32 hexadecimal digits, the
///   hash of the resolved content) of the top-level form that holds the flow's atom, and the atom's
///   canonical path in that form (steps joined by `.`, the first step an index among the form's children,
///   each sorted list of the form in canonical order); both are empty where no atom reads the source. A
///   path that the form's canonical order cannot place is spelled `?` and its source path.
///
/// `gold_tables` also gives, with the identities, the structure of the bodies and the symmetries. Each is
/// a JSON text, one per table in the order of `column_names`, that depends on no name and no order that the
/// program's author chose (the edits above, and a reorder of the sites of an atom, of the head sites of an
/// instance input and of the fields of a record), apart from a swap of two things that a symmetry of the
/// content exchanges and apart from the table numbers, which follow the order of the tables. A list of the
/// texts that has no meaning in its order is sorted by the text of its members.
///
/// - `tables.body_ir`: a list of the bodies that the evaluator joins for the table, `[]` for a table with none
///   (an evidence table, a fact relation, a table that faulted). A body is
///   `{"form","scope","variables","table_columns","symmetries","clause"}`:
///   `form` is the identity of the top-level form that holds the body (as `flows.atom_form` gives it) and
///   `scope` the canonical path in it of the body's label scope, empty for the form's own; `variables` lists
///   `{"id","type"}` for each label of the scope in the order of its canonical position, with `id` `#<n>` for
///   position `n` (`<scope>/#<n>` in a scope other than the form's own), which is also the `n` of a column
///   identity `#<n>`, and differs for each variable of the form; `table_columns` lists
///   `[column identity, variable id]` for each variable that the body binds at a column of the table;
///   `symmetries` lists the permutations `p` of the positions of the scope's labels that the canonical
///   search found, under which the scope's content is the same (`p[a] = b` maps variable `#a` to `#b`),
///   without the identity; and `clause` is the clause IR `{"columns": [variable ids], "nodes": [node]}`
///   with a node one of:
///   `{"k":"atom","form","path","read","train_only","args"}`, an atom of a relation with rows, with `form`
///   and `path` the atom's identity (as `flows.atom_form` and `flows.atom_path` give it, `key` for the
///   path of the read of an `INIT` form's key clause), `read` one of `{"table": n}` (the table number that
///   the relation read is, -1 if the export holds no such table), `{"fact": name, "table": n}`,
///   `{"key": clause}` and `{"undefined": true}`, and `args` a list of `[column identity of the table read,
///   argument]` (`@example` for the example column of a lifted read, `@<n>` where the table is not in the
///   export, and, for a key read, the id of the key clause's variable at that column); an argument is
///   `{"v": variable id}` or `{"t": term}`;
///   `{"k":"lib","form","path","relation","args","mode","computes"}`, an atom of an algebra relation of the
///   lib, with `args` at the lib's column names, `mode` the lib columns that the mode the evaluator holds
///   binds first (`null` for a relation with no mode), and `computes` the ids of the variables that the atom
///   gives values to: those of its variables that no atom of a relation with rows, no `=` with `0`, no
///   union's export and no earlier round of algebra relations or `=` places, other than those of an
///   orientation type, which the evaluator binds by their domain;
///   `{"k":"cmp","op","first","second","binds_first"}`, a comparison, with `op` one of `= != < <= > >=`,
///   `first` a variable id, `second` an argument, and `binds_first` whether it makes `first`;
///   `{"k":"not","outer","body"}` and `{"k":"all","outer","body"}`, a `NOT` and the counterexample
///   relation of an `ALL`, with `outer` the ids of the enclosing clause's variables that the body reads and
///   `body` a clause (whose variables are the enclosing form's); and
///   `{"k":"or","exported","branches"}`, an `OR` or an `IF`, with the ids of the variables it exports and its
///   clauses.
/// - `tables.instance`: for a table that an output of an instance gives,
///   `{"component": lib name, "inputs": [[port name, table number]]}` with the table number of each input
///   port of the component (-1 for an input that the export holds no table of), and the empty string for
///   every other table.
/// - `tables.column_symmetries`: a list of the permutations of the table's column identities under which
///   the table's content is the same (the permutations of the form's label symmetries that permute the
///   labels of its columns), each a list of `[column identity, identity of the column it is replaced by]`
///   for each column it moves.
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
/// three are `None` for every other case. The `CaseTables` that `step_tables`
/// gives at a decode's later model step holds its step's tables alone in the
/// same way, with the step's token index as `base_tokens`.
#[pyclass(name = "CaseTables", frozen, module = "arclog")]
pub(crate) struct PyCaseTables {
    #[pyo3(get)]
    pub(crate) task: String,
    /// Largest completed query's (bindings, rows), before export packing.
    #[pyo3(get)]
    pub(crate) largest_counts: Option<(u64, u64)>,
    /// JSON diagnostics of row queries stopped during a corpus replay.
    #[pyo3(get)]
    pub(crate) query_stops: Option<String>,
    #[pyo3(get)]
    pub(crate) case: String,
    #[pyo3(get)]
    concept: bool,
    #[pyo3(get)]
    projection_cap: u64,
    #[pyo3(get)]
    base: Option<String>,
    #[pyo3(get)]
    base_tokens: Option<usize>,
    #[pyo3(get)]
    base_tables: Option<u32>,
    #[pyo3(get)]
    tables: Py<PyDict>,
    #[pyo3(get)]
    entries: Py<PyDict>,
    /// `None` in the result of `step_tables` by assignment, which has `assignments` in its place.
    #[pyo3(get)]
    assigned: Option<Py<PyDict>>,
    /// The `DET`s of each row of `tables` with their value hashes, in the result of `step_tables` by assignment, and `None` in any other.
    #[pyo3(get)]
    assignments: Option<Py<PyDict>>,
    /// The key of each example at each row of `tables`, as `assignments` is given.
    #[pyo3(get)]
    example_keys: Option<Py<PyDict>>,
    #[pyo3(get)]
    projections: Py<PyDict>,
    #[pyo3(get)]
    projection_rows: Py<PyDict>,
    #[pyo3(get)]
    flows: Py<PyDict>,
    #[pyo3(get)]
    copies: Py<PyDict>,
    /// The cells of every row. Empty where `spilled` holds them.
    values: Py<PyBytes>,
    /// Where the cells wait on disk, in a call that kept the exports of several candidates (`successor_tables`) past its resident bound; `values` then reads them from the file at each access.
    spilled: Option<Spilled>,
    #[pyo3(get)]
    dtypes: Py<PyDict>,
    /// What the next call of `step_tables` takes from this `CaseTables` as its `before`, for a `CaseTables` of `step_tables`; Python reads none of it.
    step: Option<Step>,
    /// Packing can return a bounded prefix; its unmaterialized suffix is
    /// unavailable with this exact stop, never a completed empty table.
    #[pyo3(get)]
    materialization_stop: Option<String>,
    /// The rows of each row of `tables` and its TableHash, for `shapes`; none for a row whose summary holds none, and none at all in the result of a function that gives no summary.
    shape_rows: Vec<Option<(Arc<ShapeRows>, u128)>>,
    shape_runtime: Option<Arc<ShapeRuntime>>,
}

/// What a `step_tables` call leaves for the call at the decode's next model
/// step: the tables of the stream up to its step, the `bodies` it was made
/// with, and its step's token index, or `None` for a decode before its first
/// step.
pub(crate) struct Step {
    pub(crate) stream: Arc<StreamTables>,
    pub(crate) bodies: bool,
    pub(crate) token: Option<usize>,
    /// The count of the tables that the step itself gave, the last of `stream`.
    pub(crate) own: u32,
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

// A raw consumer can retain a column after dropping CaseTables. Keep the
// reservation on each column object, not on the wrapper or on a serialized
// mapping key. The items of a list column are plain objects: a `bytes`
// subclass has a `__dict__`, which would take ten times a short row's bytes.
// Buffer contents and isinstance stay native.
fn owned_types(py:Python<'_>)->PyResult<&'static (Py<PyAny>,Py<PyAny>)> {
    static TYPES:PyOnceLock<(Py<PyAny>,Py<PyAny>)>=PyOnceLock::new();
    TYPES.get_or_try_init(py,||{
        let code=std::ffi::CString::new(r#"
class _OwnedBytes(bytes):
    pass

class _OwnedList(list):
    __slots__ = ('_owner',)
"#).expect("static Python source has no null");
        let module=PyModule::from_code(py,&code,c"_arclog_buffer_owner.py",c"_arclog_buffer_owner")?;
        Ok((module.getattr("_OwnedBytes")?.unbind(),module.getattr("_OwnedList")?.unbind()))
    })
}

/// The column objects of a case, which each hold the capsule of the columns'
/// reservations once all of them are made, and the bytes of the objects
/// that they reach.
struct Owned<'py> {
    objects: RefCell<Vec<Bound<'py, PyAny>>>,
    bytes: std::cell::Cell<usize>,
    /// `sys.getsizeof`.
    sizeof: Bound<'py, PyAny>,
}

/// The `__dict__` that `_owner` gives an `_OwnedBytes`, which `sys.getsizeof`
/// does not count: 304 bytes on CPython 3.13.
const OWNER_DICT_BYTES: usize = 320;

impl<'py> Owned<'py> {
    fn new(py: Python<'py>) -> PyResult<Self> {
        Ok(Owned { objects: RefCell::default(), bytes: std::cell::Cell::new(0), sizeof: PyModule::import(py, "sys")?.getattr("getsizeof")? })
    }

    fn add(&self, bytes: usize) {
        self.bytes.set(self.bytes.get().saturating_add(bytes));
    }

    /// The bytes of `value` and of each object that it reaches through its
    /// items, as `sys.getsizeof` gives each. None, a bool and an int from -5
    /// to 256 are shared objects and take none.
    fn reached(&self, value: &Bound<'py, PyAny>) -> PyResult<usize> {
        if value.is_none() || value.is_instance_of::<PyBool>() || (value.is_instance_of::<PyInt>() && value.extract::<i64>().is_ok_and(|int| (-5..=256).contains(&int))) {
            return Ok(0);
        }
        let mut bytes: usize = self.sizeof.call1((value,))?.extract()?;
        if let Ok(items) = value.cast::<PyList>() {
            for item in items.iter() {
                bytes = bytes.saturating_add(self.reached(&item)?);
            }
        } else if let Ok(items) = value.cast::<PyTuple>() {
            for item in items.iter() {
                bytes = bytes.saturating_add(self.reached(&item)?);
            }
        }
        Ok(bytes)
    }
}

/// `value` as a column object that `owned` makes hold the capsule: a `bytes`
/// as an instance of a subclass of `bytes` with the same bytes, a `list` as
/// an instance of a subclass of `list` with the same items, and any other
/// value as it is.
fn owned_value<'py>(py:Python<'py>,value:&Bound<'py,PyAny>,owned:&Owned<'py>)->PyResult<Bound<'py,PyAny>> {
    let (bytes,list)=owned_types(py)?;
    let made=if value.is_instance_of::<PyBytes>() {
        owned.add(OWNER_DICT_BYTES);
        bytes.bind(py).call1((value,))?
    } else if value.is_instance_of::<PyList>() {
        list.bind(py).call1((value,))?
    } else {
        return Ok(value.clone());
    };
    owned.add(owned.reached(&made)?);
    owned.objects.borrow_mut().push(made.clone());
    Ok(made)
}

/// The dict of one part of a case's columns, and the dtype of each of its
/// integer columns in `dtypes`.
struct Part<'a, 'py> {
    dict: Bound<'py, PyDict>,
    name: &'static str,
    dtypes: &'a Bound<'py, PyDict>,
    owned: &'a Owned<'py>,
}

impl<'a, 'py> Part<'a, 'py> {
    fn new(py: Python<'py>, name: &'static str, dtypes: &'a Bound<'py, PyDict>,owned:&'a Owned<'py>) -> Self {
        Part { dict: PyDict::new(py), name, dtypes,owned }
    }

    fn ints<T: Cell>(&self, key: &str, column: &[T]) -> PyResult<()> {
        let bytes=PyBytes::new(self.dict.py(),&cell_bytes(column));
        self.dict.set_item(key,owned_value(self.dict.py(),bytes.as_any(),self.owned)?)?;
        self.dtypes.set_item(format!("{}.{key}", self.name), T::DTYPE)
    }

    /// A column of `bytes` that are not an integer column: the little-endian bytes of the hash of each row, 16 bytes a row.
    fn hashes(&self, key: &str, column: &[u128]) -> PyResult<()> {
        let bytes = PyBytes::new(self.dict.py(), &column.iter().flat_map(|hash| hash.to_le_bytes()).collect::<Vec<u8>>());
        self.dict.set_item(key, owned_value(self.dict.py(), bytes.as_any(), self.owned)?)
    }

    fn list<V: IntoPyObject<'py>>(&self, key: &str, column: V) -> PyResult<()> {
        self.dict.set_item(key,column)?;
        let value=self.dict.get_item(key)?.expect("the column just inserted");
        self.dict.set_item(key,owned_value(self.dict.py(),&value,self.owned)?)
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
    /// is the base of a case whose `columns` are cut. The reservations of
    /// `columns` pass to the returned objects, which keep on the session's
    /// ledger the estimate of their own bytes alone.
    pub(crate) fn of(py: Python<'_>, task: String, case: String, concept: bool, projection_cap: u64, mut columns: CaseColumns, relations: Option<&[String]>, base: Option<Base>) -> PyResult<Self> {
        let owned=Owned::new(py)?;
        let dtypes = PyDict::new(py);
        let t = Part::new(py, "tables", &dtypes,&owned);
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
        t.list("column_ident_sources", &c.column_ident_sources)?;
        t.list("column_frames", &c.column_frames)?;
        t.list("extent_columns", &c.extent_columns)?;
        t.list("column_slots", &c.column_slots)?;
        t.list("column_labels", &c.column_labels)?;
        t.list("column_source_labels", &c.column_source_labels)?;
        if columns.identified {
            t.list("ident", &c.ident)?;
            t.list("column_idents", &c.column_idents)?;
            t.list("body_ir", &c.body_ir)?;
            t.list("instance", &c.instance)?;
            t.list("column_symmetries", &c.column_symmetries)?;
        }
        t.ints("width", &c.width)?;
        t.list("column_widths", &c.column_widths)?;
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
        if columns.by_assignment {
            t.ints("table", &c.table)?;
            t.hashes("query", &c.query)?;
            t.ints("has_query", &c.has_query)?;
            t.list("name", &c.name)?;
            t.hashes("hash", &c.hash)?;
            t.ints("hashed", &c.hashed)?;
            t.list("unhashed_reason", &c.unhashed_reason)?;
            t.ints("capped", &c.capped)?;
            // The TableVector of each row: `table_feature_names()` values, as `float32`.
            let bytes = PyBytes::new(py, &c.features.iter().flat_map(|value| value.to_ne_bytes()).collect::<Vec<u8>>());
            t.dict.set_item("features", owned_value(py, bytes.as_any(), &owned)?)?;
            dtypes.set_item("tables.features", "float32")?;
            t.list("column_value_hashes", &c.column_value_hashes)?;
            t.list("column_type_keys", &c.column_type_keys)?;
            t.list("column_ties", &c.column_ties)?;
            t.list("column_order", &c.column_order)?;
        }
        let e = Part::new(py, "entries", &dtypes,&owned);
        let c = &columns.entries;
        e.ints("table", &c.table)?;
        e.ints("clause_index", &c.clause_index)?;
        e.ints("example_kind", &c.example_kind)?;
        e.ints("example_index", &c.example_index)?;
        e.ints("model", &c.model)?;
        e.ints("kind", &c.kind)?;
        e.ints("rows", &c.rows)?;
        e.ints("offset", &c.offset)?;
        e.stop("stop", &c.stop)?;
        e.stop("value_stop", &c.value_stop)?;
        e.list("value_stop_assignment", &c.value_stop.assignment)?;
        e.list("fault", &c.fault)?;
        e.ints("extent_offset", &c.extent_offset)?;
        e.stop("extent_stop", &c.extent_stop)?;
        e.list("extent_fault", &c.extent_fault)?;
        e.list("extent_status", &c.extent_status)?;
        if columns.by_assignment {
            e.hashes("hash", &c.hash)?;
        }
        let a = Part::new(py, "assigned", &dtypes,&owned);
        let c = &columns.assigned;
        a.ints("entry", &c.entry)?;
        a.ints("det", &c.det)?;
        a.ints("rows", &c.rows)?;
        a.ints("offset", &c.offset)?;
        let n = Part::new(py, "assignments", &dtypes,&owned);
        let c = &columns.assignments;
        n.ints("table", &c.table)?;
        n.list("det", &c.det)?;
        n.hashes("det_query", &c.det_query)?;
        n.ints("has_det_query", &c.has_det_query)?;
        n.hashes("value", &c.value)?;
        let x = Part::new(py, "example_keys", &dtypes,&owned);
        let c = &columns.example_keys;
        x.ints("table", &c.table)?;
        x.ints("kind", &c.kind)?;
        x.ints("index", &c.index)?;
        x.ints("distinct", &c.distinct)?;
        x.ints("rows", &c.rows)?;
        x.ints("hash", &c.hash)?;
        let v = Part::new(py, "projections", &dtypes,&owned);
        let c = &columns.projections;
        v.ints("table", &c.table)?;
        v.list("columns", &c.columns)?;
        v.ints("width", &c.width)?;
        let r = Part::new(py, "projection_rows", &dtypes,&owned);
        let c = &columns.projection_rows;
        r.ints("projection", &c.projection)?;
        r.ints("entry", &c.entry)?;
        r.ints("defined", &c.defined)?;
        r.ints("rows", &c.rows)?;
        r.ints("offset", &c.offset)?;
        r.ints("extent_offset", &c.extent_offset)?;
        r.list("extent_status", &c.extent_status)?;
        let f = Part::new(py, "flows", &dtypes,&owned);
        let c = &columns.flows;
        f.ints("table", &c.table)?;
        f.ints("column", &c.column)?;
        f.ints("kind", &c.kind)?;
        f.ints("source_table", &c.source_table)?;
        f.list("source_relation", &c.source_relation)?;
        f.ints("source_column", &c.source_column)?;
        f.ints("det", &c.det)?;
        f.list("atom", &c.atom)?;
        if columns.identified {
            f.list("atom_form", &c.atom_form)?;
            f.list("atom_path", &c.atom_path)?;
        }
        f.ints("occurrence", &c.occurrence)?;
        let k = Part::new(py, "copies", &dtypes,&owned);
        k.list("detail", &columns.copies.detail)?;
        let values=owned_value(py,PyBytes::new(py,&cell_bytes(&columns.values)).as_any(),&owned)?.cast_into::<PyBytes>()?.unbind();
        let materialization_stop=columns.packing_stop().map(|stop|format!("{:?} at {:?}",stop.bound,stop.form));
        // Once the columns drop, the objects made from them are all that is
        // left of them, so the capsule keeps their bytes on the session's
        // ledger, not the packing's allowance.
        let capsule=PyCapsule::new(py,columns.take_allocations(owned.bytes.get()),None)?;
        let by_assignment=columns.by_assignment;
        let shape_rows: Vec<Option<(Arc<ShapeRows>, u128)>> = std::mem::take(&mut columns.tables.shape_rows).into_iter().enumerate().map(|(row, rows)| rows.map(|rows| (rows, columns.tables.hash[row]))).collect();
        drop(columns);
        for object in owned.objects.take() {
            object.setattr("_owner",&capsule)?;
        }
        Ok(PyCaseTables {
            task,
            largest_counts: None,
            query_stops: None,
            case,
            concept,
            projection_cap,
            base_tokens: base.as_ref().map(|base| base.tokens),
            base_tables: base.as_ref().map(|base| base.tables),
            base: base.map(|base| base.case),
            tables: t.dict.unbind(),
            entries: e.dict.unbind(),
            assigned: (!by_assignment).then(|| a.dict.unbind()),
            assignments: by_assignment.then(|| n.dict.unbind()),
            example_keys: by_assignment.then(|| x.dict.unbind()),
            projections: v.dict.unbind(),
            projection_rows: r.dict.unbind(),
            flows: f.dict.unbind(),
            copies: k.dict.unbind(),
            values,
            spilled: None,
            dtypes: dtypes.unbind(),
            step: None,
            materialization_stop,
            shape_rows,
            shape_runtime: None,
        })
    }

    /// This `CaseTables` as one whose `shapes` read the session's `runtime`.
    pub(crate) fn with_shapes(mut self, runtime: Arc<ShapeRuntime>) -> Self {
        self.shape_runtime = Some(runtime);
        self
    }

    /// This `CaseTables` with its cells on disk, as `spilled` has them; the columns it was made of held none.
    pub(crate) fn with_spilled(mut self, spilled: Spilled) -> Self {
        self.spilled = Some(spilled);
        self
    }

    /// This `CaseTables` as the one a `step_tables` call gives, which keeps `step`.
    pub(crate) fn with_step(mut self, step: Step) -> Self {
        self.step = Some(step);
        self
    }

    /// The `step` that the call which gave this `CaseTables` kept, or `None` for a `CaseTables` of another function.
    pub(crate) fn step(&self) -> Option<&Step> {
        self.step.as_ref()
    }
}

#[pymethods]
impl PyCaseTables {
    /// The `int32` cells of every row, as native bytes. Where the cells wait on disk, each access reads them from the file and gives them as they were written.
    #[getter]
    fn values(&self, py: Python<'_>) -> PyResult<Py<PyBytes>> {
        match &self.spilled {
            None => Ok(self.values.clone_ref(py)),
            Some(spilled) => {
                let bytes = py.detach(|| spilled.read()).map_err(|error| pyo3::exceptions::PyOSError::new_err(format!("the cells of the export are lost from their spill file: {error}")))?;
                Ok(PyBytes::new(py, &bytes).unbind())
            }
        }
    }

    /// The shapes of the table at row `row` of `tables`, a `TableShapes`, or `None` where the row's summary holds no rows (a table with no TableHash, or a result of a call
    /// that gives no summary) or `row` is past the rows. The walk of the shapes runs at the first `vector` call that needs it.
    fn shapes(&self, row: usize) -> Option<PyTableShapes> {
        let runtime = self.shape_runtime.as_ref()?;
        let (rows, hash) = self.shape_rows.get(row)?.as_ref()?;
        Some(PyTableShapes::new(Arc::clone(rows), *hash, Arc::clone(runtime)))
    }
}
