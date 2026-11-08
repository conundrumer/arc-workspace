//! The shape values of a table at an assignment, which the encoder computes
//! (`arclog_encoder::table_vector`), for Python.
//!
//! A `CaseTables` of `step_tables`, `successor_tables` and `base_tables` gives, with
//! `CaseTables.shapes(row)`, a `TableShapes` for the table at each row of its `tables`. The
//! summary of the row holds the table's rows by reference (`arclog_tables::shape_rows`), and the
//! walk of the table's shapes runs at the first `TableShapes.vector` call that needs it, so a draw
//! pays for the shapes of the tables that something reads alone. A vector is kept by the table's
//! TableHash for the session, so a later table with that TableHash reads it again.
//!
//! The families of shapes, one for each type signature, are the process's: a family depends on the
//! column types and the size alone, so every task and session shares them. A walk starts on a
//! `Walker` of its own, so its result is a function of the table, the task's grids and the list of
//! shapes, whatever was walked before it and in whatever order. A walk that passes the walker's
//! bound on cells stops the terms after that point (they have no value), and its `stopped` is set.

use std::hash::{Hash, Hasher};
use std::sync::atomic::{AtomicU64, Ordering};
use std::sync::{Arc, Mutex, OnceLock};

use arclog::eval::join::each_row;
use arclog::hash::StableHashMap;
use arclog::task::{Grid, Task};
use arclog_encoder::generate::{Generators, ShapeList, ShapeMask, Walker, MAX_COLUMNS};
use arclog_encoder::lookup::LookupSet;
use arclog_encoder::native::CELL_CAP;
use arclog_encoder::stored::{stored_json, Model, Placed, Stored};
use arclog_encoder::table_vector::{table_vector, table_vector_of_shapes, Grids, TableVector};
use arclog_tables::shape_rows::{ShapeExample, ShapeModel, ShapeRows};
use pyo3::prelude::*;
use pyo3::types::{PyBytes, PyDict};

/// The size of the shapes, as the candidate lists build them.
const SIZE: usize = 2;

/// The most slots that a session's cache of vectors holds, 24 bytes each. Past it the cache empties,
/// and a later read walks again.
const CACHED_SLOTS: usize = 1 << 22;

/// The most masks that the process holds.
const CACHED_MASKS: usize = 4096;

static WALKS: AtomicU64 = AtomicU64::new(0);
static HITS: AtomicU64 = AtomicU64::new(0);
static STOPPED: AtomicU64 = AtomicU64::new(0);
static TOO_WIDE: AtomicU64 = AtomicU64::new(0);

/// What the process shares: the families of shapes, and the masks of lists.
struct Shared {
    families: Generators,
    masks: Mutex<StableHashMap<(String, u64), Arc<ShapeMask>>>,
}

fn shared() -> &'static Shared {
    static SHARED: OnceLock<Shared> = OnceLock::new();
    SHARED.get_or_init(|| Shared { families: Generators::default(), masks: Mutex::new(StableHashMap::default()) })
}

/// The JSON of a task's grids, as `Grids::of` reads it.
fn task_json(task: &Task) -> serde_json::Value {
    let grid = |grid: &Grid| serde_json::Value::Array(grid.rows().iter().map(|row| serde_json::Value::Array(row.iter().map(|color| serde_json::json!(color.digit())).collect())).collect());
    serde_json::json!({
        "train": task.train.iter().map(|pair| serde_json::json!({"input": grid(&pair.input), "output": grid(&pair.output)})).collect::<Vec<_>>(),
        "test": task.test.iter().map(|input| serde_json::json!({"input": grid(input)})).collect::<Vec<_>>(),
    })
}

/// A list of shapes that `TableShapes.vector` computes alone.
#[pyclass(name = "ShapeSelection", frozen, module = "arclog")]
pub(crate) struct PySelection {
    hashes: Vec<u64>,
    list: ShapeList,
    /// A hash of the set of shapes, which keys the masks and the vectors that are kept.
    id: u64,
}

#[pymethods]
impl PySelection {
    #[new]
    fn new(hashes: Vec<u64>) -> Self {
        PySelection::of(hashes)
    }

    fn __len__(&self) -> usize {
        self.hashes.len()
    }
}

impl PySelection {
    fn of(hashes: Vec<u64>) -> Self {
        let mut sorted = hashes.clone();
        sorted.sort_unstable();
        sorted.dedup();
        let mut hasher = std::collections::hash_map::DefaultHasher::new();
        sorted.hash(&mut hasher);
        // The hasher is the standard one with its fixed keys, so the id is the same in every process; it keys caches of the process alone.
        PySelection { list: ShapeList::new(sorted.iter().copied()), hashes, id: hasher.finish().max(1) }
    }
}

/// What a session keeps for the shapes of its task.
pub(crate) struct ShapeRuntime {
    task: Task,
    /// The task's grids, made at the first walk, so a session that reads no shape makes none.
    grids: OnceLock<Grids>,
    /// The count of examples of the task, train and test.
    examples: usize,
    vectors: Mutex<Vectors>,
}

#[derive(Default)]
struct Vectors {
    held: StableHashMap<(u128, u64), Arc<TableVector>>,
    slots: usize,
}

impl ShapeRuntime {
    pub(crate) fn new(task: &Task) -> ShapeRuntime {
        ShapeRuntime { task: task.clone(), grids: OnceLock::new(), examples: task.train.len() + task.test.len(), vectors: Mutex::new(Vectors::default()) }
    }

    /// For each place of the task, the example of `rows` that holds its TableRows: the last one that covers the place.
    fn owners(&self, rows: &ShapeRows) -> Vec<Option<usize>> {
        let mut owner = vec![None; self.examples];
        for (at, example) in rows.examples.iter().enumerate() {
            let places = match example.kind {
                0 => 0..self.examples,
                1 => example.index as usize..example.index as usize + 1,
                _ => rows.train + example.index as usize..rows.train + example.index as usize + 1,
            };
            for place in places.filter(|place| *place < self.examples) {
                owner[place] = Some(at);
            }
        }
        owner
    }

    /// The table that `rows` holds as the encoder reads it, with each example's TableRows in the place of the example.
    fn stored(&self, rows: &ShapeRows) -> Stored {
        // An example with a TableRows too large to write out has no value.
        let models: Vec<Vec<Model>> = rows.examples.iter().map(|example| models_of(example).unwrap_or_default()).collect();
        let per_example: Vec<&Vec<Model>> = self.owners(rows).iter().map(|owner| owner.map_or(&NO_MODELS, |at| &models[at])).collect();
        Stored::of_models(&rows.types, per_example.into_iter())
    }

    /// The table that `rows` holds in the stored form of the encoder (`arclog_encoder::stored::stored_json`), none where a type or a cell has no spelling there.
    fn stored_text(&self, rows: &ShapeRows) -> Option<String> {
        let models: Vec<Option<Vec<Model>>> = rows.examples.iter().map(models_of).collect();
        let owner = self.owners(rows);
        let whole = owner.first().copied().flatten().filter(|at| rows.examples[*at].kind == 0 && owner.iter().all(|other| *other == Some(*at)));
        let placed: Vec<Placed<'_>> = match whole {
            Some(at) => vec![Placed { kind: 0, index: 0, models: models[at].as_deref() }],
            None => owner
                .iter()
                .enumerate()
                .filter_map(|(place, owner)| {
                    let models = models[(*owner)?].as_deref();
                    Some(if place < rows.train { Placed { kind: 1, index: place as u32, models } } else { Placed { kind: 2, index: (place - rows.train) as u32, models } })
                })
                .collect(),
        };
        stored_json(&rows.types, &placed)
    }

    /// The vector of the table with TableHash `hash` and rows `rows`, for the shapes of `only` or all of them. None where the table has more columns than the generator's `MAX_COLUMNS`.
    fn vector(&self, hash: u128, rows: &ShapeRows, only: Option<&PySelection>) -> Option<Arc<TableVector>> {
        let key = (hash, only.map_or(0, |only| only.id));
        if let Some(found) = self.vectors.lock().expect("the vectors are not poisoned").held.get(&key) {
            HITS.fetch_add(1, Ordering::Relaxed);
            return Some(Arc::clone(found));
        }
        if rows.types.len() > MAX_COLUMNS {
            TOO_WIDE.fetch_add(1, Ordering::Relaxed);
            return None;
        }
        let grids = self.grids.get_or_init(|| Grids::of(&self.task, &task_json(&self.task), None));
        let stored = self.stored(rows);
        let family = shared().families.get(&stored, SIZE);
        let mut walker = Walker::new(&family);
        let vector = match only {
            None => table_vector(&mut walker, &stored, grids, self.examples, false),
            Some(only) => {
                let mask = {
                    let mask_key = (stored.key.clone(), only.id);
                    let mut masks = shared().masks.lock().expect("the masks are not poisoned");
                    if masks.len() >= CACHED_MASKS {
                        masks.clear();
                    }
                    Arc::clone(masks.entry(mask_key).or_insert_with(|| Arc::new(family.shape_mask(&only.list))))
                };
                table_vector_of_shapes(&mut walker, &stored, grids, self.examples, false, &mask)
            }
        };
        WALKS.fetch_add(1, Ordering::Relaxed);
        if vector.over_budget {
            STOPPED.fetch_add(1, Ordering::Relaxed);
        }
        let vector = Arc::new(vector);
        let mut held = self.vectors.lock().expect("the vectors are not poisoned");
        if held.slots.saturating_add(vector.slots.len()) > CACHED_SLOTS {
            held.held.clear();
            held.slots = 0;
        }
        held.slots += vector.slots.len();
        held.held.insert(key, Arc::clone(&vector));
        Some(vector)
    }
}

/// The models of an example with no TableRows.
static NO_MODELS: Vec<Model> = Vec::new();

/// An example's TableRows as the encoder takes them, none where one of them passes `CELL_CAP` cells.
fn models_of(example: &ShapeExample) -> Option<Vec<Model>> {
    example.models.iter().map(model_of).collect()
}

/// A TableRows as the encoder takes it, none where its rows pass `CELL_CAP` cells.
fn model_of(model: &ShapeModel) -> Option<Model> {
    let arity = usize::from(model.relation.arity());
    let rows = usize::try_from(model.rows).ok()?;
    if rows.saturating_mul(arity.max(1)) > CELL_CAP {
        return None;
    }
    let mut columns: Vec<Vec<u32>> = vec![Vec::with_capacity(rows); arity];
    each_row(&model.relation, &mut |row| {
        for (column, cell) in columns.iter_mut().zip(row) {
            column.push(cell.encoding());
        }
    });
    Some(Model { rows, columns })
}

/// The shapes of one table at one assignment.
///
/// `vector(only=None)` walks the table's shapes where no earlier read of a table with its
/// TableHash did, and gives a `ShapeVector`. With `only` a `ShapeSelection` or a sequence of shape
/// hashes, it gives those shapes alone, in that order, and walks only the terms they need; their
/// values equal the full walk's.
#[pyclass(name = "TableShapes", frozen, module = "arclog")]
pub(crate) struct PyTableShapes {
    rows: Arc<ShapeRows>,
    hash: u128,
    runtime: Arc<ShapeRuntime>,
}

impl PyTableShapes {
    pub(crate) fn new(rows: Arc<ShapeRows>, hash: u128, runtime: Arc<ShapeRuntime>) -> Self {
        PyTableShapes { rows, hash, runtime }
    }
}

#[pymethods]
impl PyTableShapes {
    /// The count of columns of the table.
    #[getter]
    fn columns(&self) -> usize {
        self.rows.types.len()
    }

    /// The table's rows as UTF-8 JSON in the stored form that `feature-encoder shapes-refresh` and `stored_of` (`atom_lists.rs`) read:
    /// `[{"types": [name, ..], "at": [{"entries": [[kind, index, model, complete, rows, cells], ..]}]}]`. The reader takes the counts of train and test
    /// examples from the task. The bytes depend on the table alone: the same table gives the same bytes in every run. `None` where a column's
    /// type has no name in that form (a Pose or a Record).
    fn rows<'py>(&self, py: Python<'py>) -> Option<Bound<'py, PyBytes>> {
        self.runtime.stored_text(&self.rows).map(|text| PyBytes::new(py, text.as_bytes()))
    }

    #[pyo3(signature = (only=None))]
    fn vector(&self, py: Python<'_>, only: Option<Bound<'_, PyAny>>) -> PyResult<PyShapeVector> {
        let selection: Option<Arc<PySelection>> = match only {
            None => None,
            Some(only) => Some(Arc::new(match only.extract::<PyRef<'_, PySelection>>() {
                Ok(held) => PySelection { hashes: held.hashes.clone(), list: held.list.clone(), id: held.id },
                Err(_) => PySelection::of(only.extract::<Vec<u64>>()?),
            })),
        };
        let found = py.detach(|| self.runtime.vector(self.hash, &self.rows, selection.as_deref()));
        Ok(match found {
            Some(vector) => ShapeValues::of(&vector, selection.as_deref()).pack(py, &vector),
            None => ShapeValues::empty(selection.as_deref()).pack_none(py),
        })
    }
}

/// A vector's values, ready to pack.
struct ShapeValues {
    hashes: Vec<u64>,
    values: Vec<f64>,
    have: Vec<u16>,
    scope: Vec<u16>,
    present: Vec<u8>,
    stopped: bool,
}

impl ShapeValues {
    fn of(vector: &TableVector, only: Option<&PySelection>) -> ShapeValues {
        let places: Vec<(u64, Option<usize>)> = match only {
            None => vector.shapes.iter().enumerate().map(|(place, shape)| (*shape, Some(place))).collect(),
            Some(only) => only.hashes.iter().map(|hash| (*hash, vector.shapes.binary_search(hash).ok())).collect(),
        };
        let mut out = ShapeValues { hashes: Vec::with_capacity(places.len()), values: Vec::with_capacity(places.len() * 6), have: Vec::with_capacity(places.len()), scope: Vec::with_capacity(places.len()), present: Vec::with_capacity(places.len()), stopped: vector.over_budget };
        for (hash, place) in places {
            out.hashes.push(hash);
            match place {
                Some(shape) => {
                    let (greatest_least, greatest_mean, greatest_most, count) = vector.over_examples(shape, false);
                    let (second_least, second_mean, second_most, _) = vector.over_examples(shape, true);
                    out.values.extend([greatest_least, greatest_mean, greatest_most, second_least, second_mean, second_most]);
                    out.have.push(count as u16);
                    out.scope.push(vector.scope(shape) as u16);
                    out.present.push(1);
                }
                // A shape that the vector lacks is at its default at every example.
                None => {
                    out.values.extend([0.0; 6]);
                    out.have.push(0);
                    out.scope.push(0);
                    out.present.push(0);
                }
            }
        }
        out
    }

    /// The values of a table whose shapes are not walked: NaN for each listed shape, and none for a full vector.
    fn empty(only: Option<&PySelection>) -> ShapeValues {
        let n = only.map_or(0, |only| only.hashes.len());
        ShapeValues { hashes: only.map_or_else(Vec::new, |only| only.hashes.clone()), values: vec![f64::NAN; n * 6], have: vec![0; n], scope: vec![0; n], present: vec![1; n], stopped: true }
    }

    fn pack(self, py: Python<'_>, vector: &TableVector) -> PyShapeVector {
        let mut packed = self.pack_none(py);
        packed.examples = vector.examples;
        packed.train = vector.train;
        packed
    }

    fn pack_none(self, py: Python<'_>) -> PyShapeVector {
        let bytes = |data: Vec<u8>| PyBytes::new(py, &data).unbind();
        PyShapeVector {
            count: self.hashes.len(),
            hashes: bytes(self.hashes.iter().flat_map(|value| value.to_ne_bytes()).collect()),
            values: bytes(self.values.iter().flat_map(|value| value.to_ne_bytes()).collect()),
            have: bytes(self.have.iter().flat_map(|value| value.to_ne_bytes()).collect()),
            scope: bytes(self.scope.iter().flat_map(|value| value.to_ne_bytes()).collect()),
            present: bytes(self.present),
            stopped: self.stopped,
            examples: 0,
            train: 0,
        }
    }
}

/// The shape values of a table at an assignment, as columns of `n` shapes. Each of `hashes`,
/// `values`, `have`, `scope` and `present` is `bytes` in native byte order, which `numpy.frombuffer`
/// reads at the dtype given here.
///
/// - `hashes`: `uint64`. The shape's hash, the low 64 bits of the hash of its text
///   (`shape_text` gives the text). With a list, the hashes of the list in its order; otherwise
///   each shape that is not at its default at every example, in the order of their hashes.
/// - `values`: `float64`, `n` rows of 6: the greatest of the shape's values at an example, over the
///   examples of the shape's scope, as its least, its mean and its most, and the same for its second
///   number (the sum of its values, or for a ratio their least). A shape at its default has 0 at an
///   example. NaN where no example of the scope has a value.
/// - `have`: `uint16`. The count of the scope's examples where the shape has a value. The shape has
///   one at every example of its scope where `have` equals `scope`.
/// - `scope`: `uint16`. The count of examples the shape combines over: the train examples for a
///   shape that reads the output, and every example otherwise.
/// - `present`: `uint8`. 0 for a listed shape that the vector lacks, which is at its default at each
///   example (`values` 0, `have` 0, `scope` 0).
/// - `stopped`: whether the walk passed the walker's bound on cells, so that the terms after that
///   point have no value there (NaN), or the table has more columns than the generator's `MAX_COLUMNS`, so that
///   it gives no vector, and each listed shape is NaN.
/// - `examples`, `train`: the count of examples and of train examples; 0 for a table with no vector.
#[pyclass(name = "ShapeVector", frozen, module = "arclog")]
pub(crate) struct PyShapeVector {
    #[pyo3(get)]
    count: usize,
    #[pyo3(get)]
    hashes: Py<PyBytes>,
    #[pyo3(get)]
    values: Py<PyBytes>,
    #[pyo3(get)]
    have: Py<PyBytes>,
    #[pyo3(get)]
    scope: Py<PyBytes>,
    #[pyo3(get)]
    present: Py<PyBytes>,
    #[pyo3(get)]
    stopped: bool,
    #[pyo3(get)]
    examples: usize,
    #[pyo3(get)]
    train: usize,
}

/// The text of the shape with hash `hash`, or `None` where no family that this process built has it.
#[pyfunction]
pub(crate) fn shape_text(hash: u64) -> Option<String> {
    shared().families.names.texts_of(&LookupSet::from([hash])).remove(&hash)
}

/// The hash of a shape's text, as a vector names the shape.
#[pyfunction]
pub(crate) fn shape_hash(text: &str) -> u64 {
    ShapeList::hash_of_text(text)
}

/// The text of each shape of `hashes`, in their order, by one look through the names.
#[pyfunction]
pub(crate) fn shape_texts(hashes: Vec<u64>) -> Vec<Option<String>> {
    let found = shared().families.names.texts_of(&hashes.iter().copied().collect());
    hashes.iter().map(|hash| found.get(hash).cloned()).collect()
}

/// The counters of this process's shape reads: `walks` (vectors walked), `hits` (vectors a session
/// kept and gave again), `stopped` (walks that passed the bound on cells) and `too_wide` (tables with
/// more columns than the generator's `MAX_COLUMNS`).
#[pyfunction]
pub(crate) fn table_shape_counts<'py>(py: Python<'py>) -> PyResult<Bound<'py, PyDict>> {
    let counts = PyDict::new(py);
    counts.set_item("walks", WALKS.load(Ordering::Relaxed))?;
    counts.set_item("hits", HITS.load(Ordering::Relaxed))?;
    counts.set_item("stopped", STOPPED.load(Ordering::Relaxed))?;
    counts.set_item("too_wide", TOO_WIDE.load(Ordering::Relaxed))?;
    Ok(counts)
}
