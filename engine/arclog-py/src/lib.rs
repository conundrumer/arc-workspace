//! The Python bindings of the arclog engine: the pyo3 extension, built by
//! maturin as an abi3 wheel.
//!
//! Each class wraps a value of the core crate and restates no rule of it. A
//! task session owns the data that its decoders borrow, so a `PyDecoder`
//! holds the session's data beside the decode.

use std::collections::HashMap;
use std::num::NonZeroUsize;
use std::panic::{catch_unwind, AssertUnwindSafe};
use std::path::Path;
use std::sync::{Arc, Mutex, OnceLock};
use std::time::Duration;

use arclog::decode::columns::{case_columns, CaseColumns, StopColumns, TableColumns};
use arclog::decode::corpus::{read_task_files, replay_units, ReplayProgress, UnitSolver};
use arclog::decode::replay::Stepped;
use arclog::decode::{evidence_tables, step_batch, Consistency, Decoder, Points, Table, TokenMask, Projections};
use arclog::eval::determinations::relation_spelled;
use arclog::eval::instance::Constructions;
use arclog::eval::pool::Pool;
use arclog::harness::{corpus_threads, panic_message, run_over_corpus, SolverResult};
use arclog::eval::{Outcome, RelationValue};
use arclog::judge::attempts::Attempts;
use arclog::judge::candidates::{PairCandidates, Section, World};
use arclog::registry::Registry;
use arclog::session::{SessionBound, TaskSession, SESSION_BYTES};
use arclog::stream::corpus::{fault_line, solver_streams, token_ids, WantedCases};
use arclog::stream::{DecodeSettings, Emitter, Token, Vocabulary, VocabularyCaps};
use arclog::task::{read_judged_train_text, read_task_text, Grid, JudgedTask, Task, TaskError};
use arclog::terms::Example;
use arclog::trace::render::{trace_form, TraceFormOptions};
use arclog::trace::{Stop, TopK};
use pyo3::create_exception;
use pyo3::exceptions::{PyIndexError, PyRuntimeError, PyValueError};
use pyo3::prelude::*;
use pyo3::types::{PyBytes, PyDict, PyList};

create_exception!(arclog, Refusal, PyValueError, "A decode refuses a token outside its mask.");
create_exception!(arclog, Fault, PyRuntimeError, "A run of the engine faults.");

/// The table of the lib's constructions, built once.
fn constructions() -> PyResult<&'static Constructions> {
    arclog_constructions::shared().map_err(PyRuntimeError::new_err)
}

/// The thread pool of the batch step, built once.
fn pool() -> &'static Pool {
    static POOL: OnceLock<Pool> = OnceLock::new();
    POOL.get_or_init(|| Pool::new(None))
}

fn fault(fault: arclog::eval::RunFault) -> PyErr {
    Fault::new_err(fault.message.to_string())
}

fn settled<T>(outcome: Outcome<T>) -> PyResult<T> {
    outcome.map_err(fault)
}

// ---------------------------------------------------------------- the task

/// The world of a run: how the candidates of a pair are read.
#[pyclass(name = "World", eq, eq_int, frozen, module = "arclog")]
#[derive(Clone, Copy, PartialEq, Eq)]
enum PyWorld {
    /// The task data of this repository, whose pairs the judge reads in full.
    Closed,
    /// Kaggle's task data.
    Open,
}

impl From<PyWorld> for World {
    fn from(world: PyWorld) -> World {
        match world {
            PyWorld::Closed => World::Closed,
            PyWorld::Open => World::Open,
        }
    }
}

/// The task of one ARC JSON file and the judge's view of its train pairs.
struct TaskData {
    task: Task,
    judged: JudgedTask,
    world: World,
}

/// The train pairs and test inputs of one task, and its world.
#[pyclass(name = "Task", frozen, module = "arclog")]
struct PyTask {
    data: Arc<TaskData>,
}

fn read_task(text: &str, world: World) -> Result<TaskData, TaskError> {
    // A test output is the judge's, and Kaggle's files hold none.
    Ok(TaskData { task: read_task_text(text)?, judged: JudgedTask { train: read_judged_train_text(text)?, test: Box::new([]) }, world })
}

fn task_error(error: TaskError) -> PyErr {
    match error {
        TaskError::Malformed { message, .. } => PyValueError::new_err(format!("no ARC task: {message}")),
        TaskError::Unreadable { error, .. } => PyValueError::new_err(format!("no ARC task: {error}")),
    }
}

#[pymethods]
impl PyTask {
    /// The task of ARC's JSON `text`, under `world`.
    #[staticmethod]
    fn from_json(text: &str, world: PyWorld) -> PyResult<PyTask> {
        let data = read_task(text, world.into()).map_err(task_error)?;
        Ok(PyTask { data: Arc::new(data) })
    }

    #[getter]
    fn world(&self) -> PyWorld {
        match self.data.world {
            World::Closed => PyWorld::Closed,
            World::Open => PyWorld::Open,
        }
    }

    #[getter]
    fn train_count(&self) -> usize {
        self.data.task.train.len()
    }

    #[getter]
    fn test_count(&self) -> usize {
        self.data.task.test.len()
    }
}

// ----------------------------------------------------------------- settings

/// What a decode reads: the settings of `docs/engine/synthesis.md#decode-settings`.
/// A setting left out takes the engine's default.
#[pyclass(name = "DecodeSettings", frozen, get_all, module = "arclog")]
#[derive(Clone, Copy)]
struct PyDecodeSettings {
    proposer_tokens: bool,
    type_domain_proposers: bool,
    relations: u32,
    columns: u32,
    labels: u32,
    deadline_seconds: Option<f64>,
    projection_cap: u64,
    table_work_cap: u64,
}

impl PyDecodeSettings {
    fn of(settings: &DecodeSettings) -> PyDecodeSettings {
        PyDecodeSettings {
            proposer_tokens: settings.proposer_tokens,
            type_domain_proposers: settings.type_domain_proposers,
            relations: settings.vocabulary.relations,
            columns: settings.vocabulary.columns,
            labels: settings.vocabulary.labels,
            deadline_seconds: settings.deadline.map(|deadline| deadline.as_secs_f64()),
            projection_cap: settings.projection_cap,
            table_work_cap: settings.table_work_cap,
        }
    }

    fn engine(&self) -> PyResult<DecodeSettings> {
        let deadline = self.deadline_seconds.map(|seconds| Duration::try_from_secs_f64(seconds).map_err(|error| PyValueError::new_err(format!("deadline_seconds: {error}")))).transpose()?;
        Ok(DecodeSettings {
            proposer_tokens: self.proposer_tokens,
            type_domain_proposers: self.type_domain_proposers,
            vocabulary: VocabularyCaps { relations: self.relations, columns: self.columns, labels: self.labels },
            deadline,
            projection_cap: self.projection_cap,
            table_work_cap: self.table_work_cap,
            ..DecodeSettings::default()
        })
    }
}

#[pymethods]
impl PyDecodeSettings {
    #[new]
    #[pyo3(signature = (*, proposer_tokens=None, type_domain_proposers=None, relations=None, columns=None, labels=None, deadline_seconds=None, projection_cap=None, table_work_cap=None))]
    fn new(
        proposer_tokens: Option<bool>,
        type_domain_proposers: Option<bool>,
        relations: Option<u32>,
        columns: Option<u32>,
        labels: Option<u32>,
        deadline_seconds: Option<f64>,
        projection_cap: Option<u64>,
        table_work_cap: Option<u64>,
    ) -> PyResult<PyDecodeSettings> {
        let base = PyDecodeSettings::of(&DecodeSettings::default());
        let settings = PyDecodeSettings {
            proposer_tokens: proposer_tokens.unwrap_or(base.proposer_tokens),
            type_domain_proposers: type_domain_proposers.unwrap_or(base.type_domain_proposers),
            relations: relations.unwrap_or(base.relations),
            columns: columns.unwrap_or(base.columns),
            labels: labels.unwrap_or(base.labels),
            deadline_seconds: deadline_seconds.or(base.deadline_seconds),
            projection_cap: projection_cap.unwrap_or(base.projection_cap),
            table_work_cap: table_work_cap.unwrap_or(base.table_work_cap),
        };
        settings.engine()?;
        Ok(settings)
    }
}

// ------------------------------------------------------------- vocabulary

/// The token ids of a decode and their names. The name of a token is its
/// spelling in `docs/arclog/arclog.md#token-stream`: a control token's text,
/// a lib relation, relation macro, component, proposer or fact relation's
/// name, and `&r<slot>`, `:<position>` or `L<slot>` for a relation, column
/// or label slot. The kind of a token is `control`, `lib relation`,
/// `relation macro`, `component`, `proposer`, `fact relation`, `relation`,
/// `column` or `label`.
#[pyclass(name = "Vocabulary", frozen, module = "arclog")]
struct PyVocabulary {
    names: Box<[String]>,
    kinds: Box<[&'static str]>,
    ids: HashMap<String, u32>,
}

impl PyVocabulary {
    fn of(vocabulary: &Vocabulary<'_>) -> PyVocabulary {
        let names: Box<[String]> = (0..vocabulary.len() as u32).map(|id| vocabulary.token(id).expect("an id of the vocabulary").to_string()).collect();
        let ids = names.iter().enumerate().map(|(id, name)| (name.clone(), id as u32)).collect();
        let kinds = (0..vocabulary.len() as u32).map(|id| vocabulary.kind(id).expect("an id of the vocabulary").spelling()).collect();
        PyVocabulary { names, kinds, ids }
    }
}

#[pymethods]
impl PyVocabulary {
    fn __len__(&self) -> usize {
        self.names.len()
    }

    /// The name of the token with id `id`: its spelling in the token stream, as the class documents.
    fn name(&self, id: u32) -> PyResult<&str> {
        self.names.get(id as usize).map(String::as_str).ok_or_else(|| PyIndexError::new_err(format!("no token with id {id}")))
    }

    /// The kind of the token with id `id`, as the class documents.
    fn kind(&self, id: u32) -> PyResult<&'static str> {
        self.kinds.get(id as usize).copied().ok_or_else(|| PyIndexError::new_err(format!("no token with id {id}")))
    }

    /// The id of the token named `name`, or `None` where the vocabulary holds no such token.
    fn id(&self, name: &str) -> Option<u32> {
        self.ids.get(name).copied()
    }
}

// ----------------------------------------------------------------- session

/// What the decodes of one session borrow.
struct SessionData {
    task: Arc<TaskData>,
    session: TaskSession,
    settings: DecodeSettings,
}

/// The model steps of a replay that `corpus_streams` or `corpus_tables` runs:
/// `total`, which is 0 until the call has cut its streams into units and then
/// the model steps of all the units, and `done`, the model steps replayed so
/// far, which never passes `total`. Both are read at any time, from any
/// thread, while the call runs.
#[pyclass(name = "ReplayProgress", frozen, module = "arclog")]
#[derive(Default)]
struct PyReplayProgress {
    inner: ReplayProgress,
}

#[pymethods]
impl PyReplayProgress {
    #[new]
    fn new() -> PyReplayProgress {
        PyReplayProgress::default()
    }

    #[getter]
    fn total(&self) -> usize {
        self.inner.total()
    }

    #[getter]
    fn done(&self) -> usize {
        self.inner.done()
    }
}

/// A task session: the engine's state for one task, with the settings of its decodes.
#[pyclass(name = "Session", frozen, module = "arclog")]
struct PySession {
    data: Arc<SessionData>,
}

#[pymethods]
impl PySession {
    #[new]
    #[pyo3(signature = (task, settings=None, *, session_bytes=None))]
    fn new(task: &PyTask, settings: Option<PyDecodeSettings>, session_bytes: Option<usize>) -> PyResult<PySession> {
        let settings = match settings {
            Some(settings) => settings.engine()?,
            None => DecodeSettings::default(),
        };
        let session = TaskSession::new(SessionBound { bytes: session_bytes.unwrap_or(SESSION_BYTES) }, settings.caps);
        Ok(PySession { data: Arc::new(SessionData { task: Arc::clone(&task.data), session, settings }) })
    }

    #[getter]
    fn settings(&self) -> PyDecodeSettings {
        PyDecodeSettings::of(&self.data.settings)
    }

    #[getter]
    fn vocabulary(&self) -> PyVocabulary {
        PyVocabulary::of(&Vocabulary::new(Registry::get(), &self.data.settings))
    }

    /// A decode of no token yet, judging the train pairs.
    fn decoder(&self) -> PyResult<PyDecoder> {
        PyDecoder::open(&self.data)
    }
}

// ----------------------------------------------------------- result values

/// The bound a step reached.
#[pyclass(name = "StopKind", eq, eq_int, frozen, module = "arclog")]
#[derive(Clone, Copy, PartialEq, Eq)]
enum PyStopKind {
    Bindings,
    Rows,
    Models,
    Nodes,
    Assignments,
    TableWork,
    Margin,
    SessionBytes,
    Deadline,
    Cancelled,
}

impl From<Stop> for PyStopKind {
    fn from(stop: Stop) -> PyStopKind {
        match stop {
            Stop::Bindings => PyStopKind::Bindings,
            Stop::Rows => PyStopKind::Rows,
            Stop::Models => PyStopKind::Models,
            Stop::Nodes => PyStopKind::Nodes,
            Stop::Assignments => PyStopKind::Assignments,
            Stop::TableWork => PyStopKind::TableWork,
            Stop::Margin => PyStopKind::Margin,
            Stop::SessionBytes => PyStopKind::SessionBytes,
            Stop::Deadline => PyStopKind::Deadline,
            Stop::Cancelled => PyStopKind::Cancelled,
        }
    }
}

/// What the consistency test of a `RULE` clause's relation found.
#[pyclass(name = "ConsistencyKind", eq, eq_int, frozen, module = "arclog")]
#[derive(Clone, Copy, PartialEq, Eq)]
enum PyConsistencyKind {
    Consistent,
    NotConsistent,
    SeveralValues,
    Fault,
    Stopped,
}

/// The consistency of a relation, read as `&output`, with the train pairs.
#[pyclass(name = "Consistency", frozen, get_all, module = "arclog")]
struct PyConsistency {
    kind: PyConsistencyKind,
    /// The consistent joint assignments, for `Consistent`.
    assignments: Option<usize>,
    /// The bound the test reached, for `Stopped`.
    stop: Option<PyStopKind>,
    /// The fault, for `Fault`.
    message: Option<String>,
}

impl PyConsistency {
    fn of(consistency: &Consistency) -> PyConsistency {
        let (kind, assignments, stop, message) = match consistency {
            Consistency::Consistent { assignments } => (PyConsistencyKind::Consistent, Some(assignments.len()), None, None),
            Consistency::NotConsistent => (PyConsistencyKind::NotConsistent, None, None, None),
            Consistency::SeveralValues { .. } => (PyConsistencyKind::SeveralValues, None, None, None),
            Consistency::Fault(fault) => (PyConsistencyKind::Fault, None, None, Some(fault.message.to_string())),
            Consistency::Stopped(stop) => (PyConsistencyKind::Stopped, None, Some(Stop::from(stop.bound).into()), None),
        };
        PyConsistency { kind, assignments, stop, message }
    }
}

/// What a value of a body holds.
#[pyclass(name = "ValueKind", eq, eq_int, frozen, module = "arclog")]
#[derive(Clone, Copy, PartialEq, Eq)]
enum PyValueKind {
    Rows,
    Undefined,
    Stopped,
}

/// The rows of a sub-body at one assignment, as their arity and their count: the
/// bindings expose no term of a row.
#[pyclass(name = "RowsView", frozen, get_all, module = "arclog")]
struct PyRowsView {
    kind: PyValueKind,
    arity: Option<u16>,
    count: Option<u64>,
    stop: Option<PyStopKind>,
}

/// What a request gives at each joint assignment of the `DET`s the body reads.
/// `values` holds a [`PyRowsView`] for `rows`, and a count or `None` for `counts`.
#[pyclass(name = "Assigned", frozen, get_all, module = "arclog")]
struct PyAssigned {
    values: Py<PyList>,
    /// The bound that ended the walk before its last assignment.
    stop: Option<PyStopKind>,
}

fn rows_view(value: &arclog::eval::BodyValue) -> PyRowsView {
    match &value.0 {
        RelationValue::Rows(relation) => PyRowsView { kind: PyValueKind::Rows, arity: Some(relation.arity()), count: Some(relation.len()), stop: None },
        RelationValue::Undefined => PyRowsView { kind: PyValueKind::Undefined, arity: None, count: None, stop: None },
        RelationValue::Stopped(stop) => PyRowsView { kind: PyValueKind::Stopped, arity: None, count: None, stop: Some(Stop::from(stop.bound).into()) },
    }
}

/// The [`PyAssigned`] of `found`, an `Assigned` of the core crate, with
/// the `Py<PyAny>` that `view` gives for each value. A macro, since the core crate does not export the
/// type.
macro_rules! assigned {
    ($py:expr, $found:expr, |$value:ident| $view:expr) => {{
        let (py, found) = ($py, $found);
        let values = PyList::empty(py);
        for (_, $value) in found.at {
            let view: Py<PyAny> = $view;
            values.append(view)?;
        }
        let stop: Option<PyStopKind> = found.stop.map(|stop| Stop::from(stop.bound).into());
        PyResult::Ok(PyAssigned { values: values.unbind(), stop })
    }};
}

/// One projection of a sub-body: the positions of its columns in the body, and the
/// count of its rows on each example, in the shape of `counts`.
#[pyclass(name = "Projection", frozen, get_all, module = "arclog")]
struct PyProjection {
    columns: Vec<u16>,
    counts: Vec<Py<PyAssigned>>,
}

/// The projections of a sub-body, or the bound that stopped them.
#[pyclass(name = "Projections", frozen, get_all, module = "arclog")]
struct PyProjections {
    projections: Vec<Py<PyProjection>>,
    stop: Option<PyStopKind>,
}

fn grid_rows(grid: &Grid) -> Vec<Vec<u32>> {
    grid.rows().iter().map(|row| row.iter().map(|color| u32::from(color.digit())).collect()).collect()
}

// ----------------------------------------------------------------- decoder

/// A decode over a task in a session.
///
/// The decode borrows the data of its session, which the struct holds in an
/// `Arc` that outlives the decode: `decoder` is declared before `data`, so
/// it drops first, and the `'static` of its type stands for the lifetime of
/// that `Arc`. `decoder` is `None` only inside [`step_batch`]'s call.
#[pyclass(name = "Decoder", module = "arclog")]
struct PyDecoder {
    decoder: Option<Decoder<'static>>,
    data: Arc<SessionData>,
}

impl PyDecoder {
    fn open(data: &Arc<SessionData>) -> PyResult<PyDecoder> {
        // SAFETY: the reference points into the `Arc`'s allocation, which the
        // returned `PyDecoder` keeps alive and never moves, and the decode
        // drops before the `Arc` does.
        let borrowed: &'static SessionData = unsafe { &*Arc::as_ptr(data) };
        let world = borrowed.task.world;
        let train: Arc<[PairCandidates<'static>]> = borrowed.task.judged.train.iter().map(|pair| PairCandidates::of(pair, Section::Train, world)).collect();
        let decoder = Decoder::new(&borrowed.task.task, &borrowed.session, Registry::get(), constructions()?, &borrowed.settings).judging(train);
        Ok(PyDecoder { decoder: Some(decoder), data: Arc::clone(data) })
    }

    fn decoder(&self) -> &Decoder<'static> {
        self.decoder.as_ref().expect("a decode outside a batch step")
    }

    fn decoder_mut(&mut self) -> &mut Decoder<'static> {
        self.decoder.as_mut().expect("a decode outside a batch step")
    }

    fn token(&self, id: u32) -> PyResult<Token> {
        self.decoder().vocabulary().token(id).cloned().ok_or_else(|| PyIndexError::new_err(format!("no token with id {id}")))
    }

    fn step_result(&self, result: arclog::decode::StepResult) -> PyResult<(Vec<u32>, Option<PyConsistency>)> {
        match result {
            Ok(step) => {
                let vocabulary = self.decoder().vocabulary();
                let forced = step.forced.iter().map(|token| vocabulary.id(token).expect("a forced token is in the vocabulary")).collect();
                Ok((forced, step.consistency.as_ref().map(PyConsistency::of)))
            }
            Err(refusal) => Err(Refusal::new_err(format!("{refusal:?}"))),
        }
    }
}

/// The bytes of `mask` over a vocabulary of `len` tokens: bit `id % 8` of
/// byte `id // 8` is set where the token with that id is admissible.
fn mask_bytes(mask: &TokenMask, len: usize) -> Vec<u8> {
    let mut bytes = vec![0u8; len.div_ceil(8)];
    for id in 0..len as u32 {
        if mask.contains(id) {
            bytes[id as usize / 8] |= 1 << (id % 8);
        }
    }
    bytes
}

#[pymethods]
impl PyDecoder {
    #[getter]
    fn vocabulary(&self) -> PyVocabulary {
        PyVocabulary::of(self.decoder().vocabulary())
    }

    /// Whether the decode has ended at a consistent relation.
    #[getter]
    fn ended(&self) -> bool {
        self.decoder().output().is_some()
    }

    /// The tokens that may come next: bit `id % 8` of byte `id // 8` is set
    /// where the token with that id is admissible.
    fn admissible<'py>(&self, py: Python<'py>) -> Bound<'py, PyBytes> {
        let decoder = self.decoder();
        PyBytes::new(py, &mask_bytes(&decoder.admissible(), decoder.vocabulary().len()))
    }

    /// Advances the decode by the token with id `id`, and gives the ids of
    /// the tokens the engine emits after it, with the consistency of a
    /// `RULE` clause that the token ends, or `None`. Raises `Refusal` for a
    /// token outside the mask, and leaves the decode as it was.
    fn step(&mut self, id: u32) -> PyResult<(Vec<u32>, Option<PyConsistency>)> {
        let token = self.token(id)?;
        let result = self.decoder_mut().step(token);
        self.step_result(result)
    }

    /// A second decode from the same state, which shares this one's caches.
    fn fork(&self) -> PyDecoder {
        PyDecoder { decoder: Some(self.decoder().fork()), data: Arc::clone(&self.data) }
    }

    /// The rows of the sub-body of the clause in progress on `example`, or
    /// `None` where no clause is in progress. Raises `Fault` where the
    /// sub-body does not check or compile.
    #[pyo3(signature = (example=None))]
    fn rows(&mut self, py: Python<'_>, example: Option<u16>) -> PyResult<Option<PyAssigned>> {
        let observed = self.decoder_mut().observe_rows(example.map(Example::at));
        observed
            .map(|outcome| assigned!(py, settled(outcome)?, |value| Py::new(py, rows_view(&value))?.into_any()))
            .transpose()
    }

    /// The count of the rows of the sub-body on each example, or once for a
    /// task-wide clause; `None` where no clause is in progress.
    fn counts(&mut self, py: Python<'_>) -> PyResult<Option<Vec<PyAssigned>>> {
        let observed = self.decoder_mut().observe_counts();
        observed
            .map(|outcomes| {
                outcomes
                    .into_vec()
                    .into_iter()
                    .map(|outcome| assigned!(py, settled(outcome)?, |count| count.into_pyobject(py)?.into_any().unbind()))
                    .collect()
            })
            .transpose()
    }

    /// The projections of the sub-body of the clause in progress, as
    /// `docs/engine/synthesis.md#decode-interface` gives them, or `None`
    /// where no clause is in progress. The projections are empty and `stop` is set
    /// where a bound ended the body or the search. The projections give no rows.
    /// Raises `Fault` where the sub-body does not check or compile.
    fn projections(&self, py: Python<'_>) -> PyResult<Option<PyProjections>> {
        let Some(outcome) = self.decoder().projections() else { return Ok(None) };
        let found = match settled(outcome)? {
            Projections::Found(found) => found,
            Projections::Stopped(stop) => return Ok(Some(PyProjections { projections: Vec::new(), stop: Some(Stop::from(stop.bound).into()) })),
        };
        let mut projections = Vec::new();
        for projection in found {
            let counts = projection
                .rows
                .into_vec()
                .into_iter()
                .map(|rows| Py::new(py, assigned!(py, rows, |rows| rows.map(|relation| relation.len()).into_pyobject(py)?.into_any().unbind())?))
                .collect::<PyResult<Vec<_>>>()?;
            projections.push(Py::new(py, PyProjection { columns: projection.columns.iter().map(|column| column.0).collect(), counts })?);
        }
        Ok(Some(PyProjections { projections, stop: None }))
    }

    /// The attempts on each test input, as lists of at most two grids, or
    /// `None` until the decode ends at a consistent relation.
    fn attempts(&self) -> PyResult<Option<Vec<Vec<Vec<Vec<u32>>>>>> {
        let Some(outcome) = self.decoder().attempts() else { return Ok(None) };
        let attempts = settled(outcome)?;
        Ok(Some(
            attempts
                .iter()
                .map(|attempt| match attempt {
                    Attempts::None => Vec::new(),
                    Attempts::One(one) => vec![grid_rows(one)],
                    Attempts::Two(one, two) => vec![grid_rows(one), grid_rows(two)],
                })
                .collect(),
        ))
    }

    /// Attaches the language model's top tokens at the record `step` of the
    /// trace, as pairs of an id and a probability. Gives `False` where the
    /// trace has no such record.
    fn attach_top_k(&mut self, step: usize, top_k: Vec<(u32, f32)>) -> PyResult<bool> {
        let tokens = top_k.into_iter().map(|(id, probability)| Ok((self.token(id)?, probability))).collect::<PyResult<Vec<_>>>()?;
        Ok(self.decoder_mut().attach_top_k(step, TopK(tokens)))
    }

    /// The trace form of the decode.
    #[pyo3(signature = (top_k=false))]
    fn trace_form(&self, top_k: bool) -> String {
        let decoder = self.decoder();
        trace_form(decoder.trace(), decoder.vocabulary(), &TraceFormOptions { top_k, ..TraceFormOptions::default() })
    }

    /// The program so far, as an arclog file.
    fn program_form(&self) -> String {
        arclog::write::write_synthesized(self.decoder().program(), Registry::get())
    }
}

// ----------------------------------------------------------------- streams

/// The cases and fault lines of each solver of `corpus` that `task_ids`
/// keeps (every solver where it is `None`), as `solver` gives them for the
/// solver's task id, in the order of the task ids. A solver whose `solver`
/// panics gives no cases and one fault line, `the walk of the solver
/// panicked: <message>`. The walk runs on the threads of the corpus harness
/// with the GIL released.
fn walk_corpus<C: Send>(
    py: Python<'_>,
    corpus: &str,
    task_ids: &Option<Vec<String>>,
    solver: impl Fn(&str) -> (Vec<C>, Vec<String>) + Sync,
) -> PyResult<Vec<(String, Vec<C>, Vec<String>)>> {
    let found: Mutex<Vec<(String, Vec<C>, Vec<String>)>> = Mutex::new(Vec::new());
    let selected: Option<std::collections::BTreeSet<String>> = task_ids.as_ref().map(|ids| ids.iter().cloned().collect());
    let walked = py.detach(|| {
        run_over_corpus(
            Path::new(corpus),
            selected.as_ref(),
            |corpus_solver| {
                let id = &corpus_solver.task_id;
                let (cases, faults) = catch_unwind(AssertUnwindSafe(|| solver(id))).unwrap_or_else(|payload| {
                    let message = panic_message(&*payload).unwrap_or("a payload that is not a message");
                    (Vec::new(), vec![fault_line(id, None, &format!("the walk of the solver panicked: {message}"))])
                });
                found.lock().unwrap_or_else(|poisoned| poisoned.into_inner()).push((corpus_solver.task_id.clone(), cases, faults));
                SolverResult::Pass
            },
            |_, _| {},
        )
    });
    walked.map_err(|error| Fault::new_err(format!("the corpus does not read: {error:?}")))?;
    let mut found = found.into_inner().unwrap_or_else(|poisoned| poisoned.into_inner());
    found.sort_by(|a, b| a.0.cmp(&b.0));
    Ok(found)
}

/// The token stream of one case of a solver of a corpus.
///
/// `ids` holds the token ids as `uint32` in native byte order, and `model`
/// one byte for each token, 1 where the model writes the token and 0 where
/// the engine does, so `numpy.frombuffer` reads each.
///
/// `masks` holds, where `corpus_streams` is given `tasks` and the case
/// replays, the mask `Decoder.admissible` gives before each token with a 1
/// in `model`, in stream order, each `(len(vocabulary) + 7) // 8` bytes, so
/// `numpy.frombuffer(masks, numpy.uint8).reshape(-1, (len(vocabulary) + 7) // 8)`
/// has one row for each token the model writes. Otherwise it is `None`, and
/// `mask_fault` is `None` where `tasks` is `None` and else the reason the
/// case gives no masks. Where the decode of the case ends at its `&output`
/// before the stream does, `ids` and `model` hold the tokens before the first
/// token the model writes after that end, and `masks` has one row for each
/// model token among them.
#[pyclass(name = "CaseStream", frozen, get_all, module = "arclog")]
struct PyCaseStream {
    task: String,
    case: String,
    concept: bool,
    ids: Py<PyBytes>,
    model: Py<PyBytes>,
    masks: Option<Py<PyBytes>>,
    mask_fault: Option<String>,
}

/// A stream of a case with the ids of its tokens, before it becomes an object.
struct IdStream {
    task: String,
    case: String,
    concept: bool,
    ids: Vec<(u32, Emitter)>,
    /// The masks of the model's tokens, or why the case gives none; `Ok`
    /// with no bytes where the walk replays nothing, or has not yet.
    masks: Result<Option<Vec<u8>>, String>,
}

/// The token stream of each case of each solver of `corpus`, the concept
/// case or, with `all_cases`, every case, over the solvers whose task ids
/// `task_ids` gives, or every solver where it is `None`, in the order of the
/// task ids and then of the cases, with the ids of the vocabulary under the
/// default settings. The second value holds a line for each case that gives no
/// stream and each solver that gives none, in the form the report of
/// `arclog-cli stream --corpus` prints it, in the order of the task ids.
/// Where `tasks`, the directory of the task files, is given, each stream is
/// also replayed on its task under the default settings, judging the train
/// pairs in the closed world, and the stream's `masks` are the engine's
/// masks of that replay; a stream whose replay gives none stays in the list
/// with its `mask_fault`, and the second value is as it is without `tasks`.
/// The walk runs on the threads of the corpus harness with the GIL released,
/// in phases. The first reads each solver, its streams and, with `tasks`, its
/// task. The second, with `tasks`, cuts the streams of each solver, in the
/// order of their tokens, into groups of consecutive streams of at most
/// `UNIT_STEPS` model steps but for the last stream's, and replays the groups,
/// the largest first. A group replays the mask of each prefix its streams
/// share once.
/// `started` and `ended`, each a callable or `None`, are called with a
/// solver's task id, holding the GIL, `started` as the first of the solver's
/// units starts, and `ended` once the last of its streams has ended. A solver
/// whose streams all lie past `step_cap` gets `ended` too; one whose task did
/// not read, and one whose unit panics, gives no `ended` call. An exception
/// that a callable raises is printed and dropped.
/// `step_cap`, an integer or `None`, bounds the replay of each solver: its
/// streams, in the order of their tokens, replay up to the last one at which
/// the model steps of their prefix tree so far stay within the cap. Each later
/// stream gives no masks and a `mask_fault` that names the cap and the model
/// steps of all the solver's streams.
/// `progress`, a `ReplayProgress` or `None`, gives the model steps of the
/// second phase: its `total` is set once the groups are cut and its `done`
/// grows while they replay.
#[pyfunction]
#[pyo3(signature = (corpus, all_cases=false, task_ids=None, tasks=None, started=None, ended=None, progress=None, step_cap=None))]
fn corpus_streams(py: Python<'_>, corpus: &str, all_cases: bool, task_ids: Option<Vec<String>>, tasks: Option<&str>, started: Option<Py<PyAny>>, ended: Option<Py<PyAny>>, progress: Option<Py<PyReplayProgress>>, step_cap: Option<usize>) -> PyResult<(Vec<PyCaseStream>, Vec<String>)> {
    let wanted = if all_cases { WantedCases::All } else { WantedCases::Concept };
    let constructions = constructions()?;
    let vocabulary = Vocabulary::new(Registry::get(), &DecodeSettings::default());
    let reads: Mutex<HashMap<String, Result<(Task, JudgedTask), String>>> = Mutex::new(HashMap::new());
    let mut found = walk_corpus(py, corpus, &task_ids, |id| {
        let (mut streams, mut faults) = (Vec::new(), Vec::new());
        match solver_streams(Path::new(corpus), id, wanted, &vocabulary) {
            Ok(cases) => {
                for case in cases {
                    match case.stream {
                        Ok(stream) => {
                            let masks = if tasks.is_some() && case.demonstrated { Err("the program holds a DEMONSTRATED form".to_string()) } else { Ok(None) };
                            streams.push(IdStream { task: id.to_string(), case: case.case, concept: case.concept, ids: token_ids(&stream.tokens, &vocabulary), masks });
                        }
                        Err(fault) => faults.push(fault_line(id, Some(&case.case), &fault)),
                    }
                }
                if let (Some(tasks), false) = (tasks, streams.is_empty()) {
                    reads.lock().unwrap_or_else(|poisoned| poisoned.into_inner()).insert(id.to_string(), read_task_files(Path::new(tasks), id));
                }
            }
            Err(fault) => faults.push(fault_line(id, None, &fault)),
        }
        (streams, faults)
    })?;
    if tasks.is_some() {
        let reads = reads.into_inner().unwrap_or_else(|poisoned| poisoned.into_inner());
        let unread = ReplayProgress::default();
        let steps = progress.as_ref().map_or(&unread, |progress| &progress.get().inner);
        py.detach(|| replay_masks(&mut found, &reads, constructions, steps, started.as_ref(), ended.as_ref(), step_cap));
    }
    let mut streams = Vec::new();
    let mut faults = Vec::new();
    for (_, solver_streams, solver_faults) in found {
        for stream in solver_streams {
            let ids: Vec<u8> = stream.ids.iter().flat_map(|(id, _)| id.to_ne_bytes()).collect();
            let model: Vec<u8> = stream.ids.iter().map(|(_, emitter)| u8::from(*emitter == Emitter::Model)).collect();
            let (masks, mask_fault) = match stream.masks {
                Ok(masks) => (masks, None),
                Err(fault) => (None, Some(fault)),
            };
            streams.push(PyCaseStream {
                task: stream.task,
                case: stream.case,
                concept: stream.concept,
                ids: PyBytes::new(py, &ids).unbind(),
                model: PyBytes::new(py, &model).unbind(),
                masks: masks.map(|masks| PyBytes::new(py, &masks).unbind()),
                mask_fault,
            });
        }
        faults.extend(solver_faults);
    }
    Ok((streams, faults))
}

/// The progress callbacks of a replay, `started` and `ended`, each a Python
/// callable or `None`, with, for each solver, the count of its streams left
/// and whether `started` was called.
struct Progress<'a> {
    started: Option<&'a Py<PyAny>>,
    ended: Option<&'a Py<PyAny>>,
    tasks: Vec<&'a str>,
    streams_left: Vec<std::sync::atomic::AtomicUsize>,
    begun: Vec<std::sync::atomic::AtomicBool>,
}

impl<'a> Progress<'a> {
    /// The progress of solvers with the task ids `tasks`, of whom the solver at an index has `streams[index]` streams.
    fn new(started: Option<&'a Py<PyAny>>, ended: Option<&'a Py<PyAny>>, tasks: Vec<&'a str>, streams: Vec<usize>) -> Self {
        let streams_left = streams.into_iter().map(std::sync::atomic::AtomicUsize::new).collect();
        let begun = tasks.iter().map(|_| std::sync::atomic::AtomicBool::new(false)).collect();
        Self { started, ended, tasks, streams_left, begun }
    }

    /// Calls `callback`, holding the GIL, with the task id of `solver`; an exception it raises is printed and dropped.
    fn call(&self, callback: &Py<PyAny>, solver: usize) {
        Python::attach(|py| {
            if let Err(error) = callback.call1(py, (self.tasks[solver],)) {
                error.print(py);
            }
        });
    }

    /// A unit of `solver` starts: calls `started` for the first of its units.
    fn start(&self, solver: usize) {
        if let Some(callback) = self.started {
            if !self.begun[solver].swap(true, std::sync::atomic::Ordering::SeqCst) {
                self.call(callback, solver);
            }
        }
    }

    /// A stream of `solver` has ended: calls `ended` for the last of its streams.
    fn settle(&self, solver: usize) {
        if let Some(callback) = self.ended {
            if self.streams_left[solver].fetch_sub(1, std::sync::atomic::Ordering::SeqCst) == 1 {
                self.call(callback, solver);
            }
        }
    }
}

/// Replays the streams of `found` whose masks are due, which are those with
/// `Ok(None)`, on the tasks that `reads` holds, as [`replay_units`] does, and
/// sets each stream's `masks`. A solver whose task did not read, gives each of its streams that fault.
fn replay_masks(found: &mut [(String, Vec<IdStream>, Vec<String>)], reads: &HashMap<String, Result<(Task, JudgedTask), String>>, constructions: &'static Constructions, steps: &ReplayProgress, started: Option<&Py<PyAny>>, ended: Option<&Py<PyAny>>, step_cap: Option<usize>) {
    let mut faults: HashMap<usize, String> = HashMap::new();
    // For each solver whose task read: its index in `found`, the indices in its streams of the due streams, and their ids.
    let mut due: Vec<(usize, Vec<usize>, Vec<Vec<(u32, Emitter)>>)> = Vec::new();
    for (solver, (id, streams, _)) in found.iter().enumerate() {
        match reads.get(id) {
            None => {}
            Some(Err(fault)) => {
                faults.insert(solver, fault.clone());
            }
            Some(Ok(_)) => {
                let wanted: Vec<usize> = (0..streams.len()).filter(|&stream| matches!(streams[stream].masks, Ok(None))).collect();
                let ids = wanted.iter().map(|&stream| streams[stream].ids.clone()).collect();
                due.push((solver, wanted, ids));
            }
        }
    }
    let solvers: Vec<UnitSolver<'_>> = due
        .iter()
        .map(|(solver, _, ids)| {
            let Some(Ok((task, judged))) = reads.get(&found[*solver].0) else { unreachable!("a solver of `due` has a task that read") };
            UnitSolver { task, judged, streams: ids, units: None }
        })
        .collect();
    let progress = Progress::new(started, ended, due.iter().map(|(solver, _, _)| found[*solver].0.as_str()).collect(), due.iter().map(|(_, wanted, _)| wanted.len()).collect());
    let results = replay_units(
        &solvers,
        constructions,
        &DecodeSettings::corpus(),
        true,
        corpus_threads(),
        steps,
        &|(rows, masks): &mut (usize, Vec<u8>), decoder, stepped| {
            let masked = stepped.mask.expect("the replay computes the mask");
            *rows += 1;
            masks.extend(mask_bytes(masked.mask, decoder.vocabulary().len()));
        },
        &|solver| progress.start(solver),
        &|_, replay| replay.into_result(),
        &|solver| progress.settle(solver),
        step_cap,
    );
    let mut sets = Vec::new();
    for ((solver, wanted, _), outs) in due.iter().zip(results) {
        sets.extend(wanted.iter().zip(outs).map(|(&stream, out)| (*solver, stream, out)));
    }
    for (solver, stream, out) in sets {
        let stream = &mut found[solver].1[stream];
        stream.masks = out.and_then(|out| out).map(|(rows, masks)| {
            // The tokens from the first one the model emits after the decode's end are no part of the program the decode reads.
            let end = stream.ids.iter().enumerate().filter(|(_, (_, emitter))| *emitter == Emitter::Model).nth(rows).map(|(index, _)| index);
            if let Some(end) = end {
                stream.ids.truncate(end);
            }
            Some(masks)
        });
    }
    for (solver, fault) in faults {
        for stream in &mut found[solver].1 {
            stream.masks = Err(fault.clone());
        }
    }
}

// ------------------------------------------------------------------ tables

/// The tables of one case program of a solver of a corpus, as flat columns
/// (`arclog::decode::columns` gives the layout and the codes).
///
/// `tables`, `entries`, `assigned`, `projections`, `projection_rows` and `flows` are dicts of
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
/// for each other table; `flows` gives one row for each source of each column of a table.
/// `projection_cap` is the cap of the projection rows that the tables ran
/// under.
#[pyclass(name = "CaseTables", frozen, get_all, module = "arclog")]
struct PyCaseTables {
    task: String,
    case: String,
    concept: bool,
    projection_cap: u64,
    tables: Py<PyDict>,
    entries: Py<PyDict>,
    assigned: Py<PyDict>,
    projections: Py<PyDict>,
    projection_rows: Py<PyDict>,
    flows: Py<PyDict>,
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

impl PyCaseTables {
    /// `relations` is the spelling of the relation declared at each slot of the
    /// case program, or `None` for a stream that no case program writes.
    fn of(py: Python<'_>, task: String, case: String, concept: bool, projection_cap: u64, columns: &CaseColumns, relations: Option<&[String]>) -> PyResult<Self> {
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
        t.ints("width", &c.width)?;
        t.list("det_relations", &c.det_relations)?;
        t.list("det_types", &c.det_types)?;
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
        Ok(PyCaseTables {
            task,
            case,
            concept,
            projection_cap,
            tables: t.dict.unbind(),
            entries: e.dict.unbind(),
            assigned: a.dict.unbind(),
            projections: v.dict.unbind(),
            projection_rows: r.dict.unbind(),
            flows: f.dict.unbind(),
            values: PyBytes::new(py, &cell_bytes(&columns.values)).unbind(),
            dtypes: dtypes.unbind(),
        })
    }
}

/// A case of a solver whose tables `corpus_tables` builds: its stream's
/// token ids and the spelling by `relation_spelled` of the relation declared
/// at each slot, in slot order, or the writer's fault.
struct TableCase {
    case: String,
    concept: bool,
    stream: Result<(Vec<(u32, Emitter)>, Vec<String>), String>,
}

/// The tables of each case of each solver of `corpus`, on its task in
/// `tasks`, the concept case or, with `all_cases`, every case, over the
/// solvers whose task ids `task_ids` gives, or every solver where it is
/// `None`, in the order of the task ids and then of the cases. Each table
/// is at the index of the token whose step gives it, but for the first two,
/// the evidence tables `ex_input` and `ex_output` of the task, which stand at
/// token 0 with point 2. The tables are those of a decode under `projection_cap`,
/// the cap of `DecodeSettings`, the engine's default where it is `None`, and
/// each `CaseTables` gives it. `table_work_cap` is the cap of the bindings that
/// all the evaluations of one table try, with the same default and the same
/// `None`; a table past it ends with a stop whose bound is `TableWork`. The relations of the
/// finished forms are tabled, and with `bodies` the bodies in progress as well.
/// The second value holds a line for each case that gives no tables and each
/// solver that gives none, in the form of `corpus_streams`, in the order of
/// the task ids, and for each case whose last `RULE` end before the stream's
/// end gives `Stopped` the line `<task> <case>: ended Stopped at token <index>`
/// of `stream_tables`, with that case's tables kept. The replay runs under no
/// deadline and computes no token mask.
/// The call runs on the threads of the corpus harness with the GIL released,
/// but for the build of each `CaseTables`, in phases. The first reads each
/// solver, its streams and its task. The second cuts the streams of each
/// solver into units, replays the units, the
/// largest first, and turns the tables of each stream into columns as its
/// unit ends.
/// `units`, a positive integer or `None`, sets the cut and the threads of
/// the second phase. With `None`, the streams of each solver, in the order of
/// their tokens, are cut into groups of consecutive streams of at most
/// `UNIT_STEPS` model steps but for the last stream's, as `corpus_streams`
/// does, and the threads are those of the corpus harness. With an integer
/// `k`, they are cut into at most `k` units of consecutive streams with about
/// equal new model steps, each cut at the stream that passes the next
/// `k`-th of the solver's model steps, and the call replays on `k` threads,
/// whatever `ARCLOG_THREADS` holds. An Ident's number depends on the unit
/// that interned it, so the same call with another `units` gives the same
/// tables but for the numbers of its Idents, and each equality of two Idents
/// within a case holds in both. `ValueError` is raised for 0.
/// `ended`, a callable or `None`, is called with a solver's task id, holding
/// the GIL, once the last of that solver's streams has ended. A solver whose
/// streams all lie past `step_cap` gets the call; one whose task did not read,
/// and one whose unit panics, gives none. An
/// exception that `ended` raises is printed and dropped.
/// `step_cap`, an integer or `None`, bounds the replay of each solver as it
/// does in `corpus_streams`; a stream past the cap gives its line as the
/// case's fault.
/// `progress`, a `ReplayProgress` or `None`, gives the model steps of the
/// second phase: its `total` is set once the units are cut and its `done`
/// grows while they replay.
#[pyfunction]
#[pyo3(signature = (corpus, tasks, all_cases=false, task_ids=None, bodies=false, projection_cap=None, ended=None, progress=None, step_cap=None, table_work_cap=None, units=None))]
fn corpus_tables(py: Python<'_>, corpus: &str, tasks: &str, all_cases: bool, task_ids: Option<Vec<String>>, bodies: bool, projection_cap: Option<u64>, ended: Option<Py<PyAny>>, progress: Option<Py<PyReplayProgress>>, step_cap: Option<usize>, table_work_cap: Option<u64>, units: Option<usize>) -> PyResult<(Vec<PyCaseTables>, Vec<String>)> {
    let units = units.map(|count| NonZeroUsize::new(count).ok_or_else(|| PyValueError::new_err("units must be a positive integer"))).transpose()?;
    let points = if bodies { Points::All } else { Points::Relations };
    let wanted = if all_cases { WantedCases::All } else { WantedCases::Concept };
    let constructions = constructions()?;
    let vocabulary = Vocabulary::new(Registry::get(), &DecodeSettings::default());
    let base = DecodeSettings::corpus();
    let settings = DecodeSettings { projection_cap: projection_cap.unwrap_or(base.projection_cap), table_work_cap: table_work_cap.unwrap_or(base.table_work_cap), ..base };
    let reads: Mutex<HashMap<String, (Task, JudgedTask)>> = Mutex::new(HashMap::new());
    let found = walk_corpus(py, corpus, &task_ids, |id| {
        let (mut cases, mut faults) = (Vec::new(), Vec::new());
        match solver_streams(Path::new(corpus), id, wanted, &vocabulary) {
            Ok(streams) => match read_task_files(Path::new(tasks), id) {
                Ok(read) => {
                    for case in streams.into_iter().filter(|case| !case.demonstrated) {
                        let stream = case.stream.map(|stream| (token_ids(&stream.tokens, &vocabulary), stream.relations.iter().map(relation_spelled).collect()));
                        cases.push(TableCase { case: case.case, concept: case.concept, stream });
                    }
                    reads.lock().unwrap_or_else(|poisoned| poisoned.into_inner()).insert(id.to_string(), read);
                }
                Err(fault) => faults.push(fault_line(id, None, &fault)),
            },
            Err(fault) => faults.push(fault_line(id, None, &fault)),
        }
        (cases, faults)
    })?;
    let reads = reads.into_inner().unwrap_or_else(|poisoned| poisoned.into_inner());
    // For each solver that has cases: the ids of the streams its writer gives.
    let streamed: Vec<(&str, Vec<Vec<(u32, Emitter)>>)> = found
        .iter()
        .filter(|(id, cases, _)| !cases.is_empty() && reads.contains_key(id))
        .map(|(id, cases, _)| (id.as_str(), cases.iter().filter_map(|case| case.stream.as_ref().ok().map(|(ids, _)| ids.clone())).collect()))
        .collect();
    let solvers: Vec<UnitSolver<'_>> = streamed
        .iter()
        .map(|(id, ids)| {
            let (task, judged) = &reads[*id];
            UnitSolver { task, judged, streams: ids, units }
        })
        .collect();
    let trains: Vec<usize> = streamed.iter().map(|(id, _)| reads[*id].0.train.len()).collect();
    let evidence: Vec<Vec<Table>> = solvers.iter().map(|solver| evidence_tables(solver.task, Registry::get())).collect();
    let unread = ReplayProgress::default();
    let steps = progress.as_ref().map_or(&unread, |progress| &progress.get().inner);
    let progress = Progress::new(None, ended.as_ref(), streamed.iter().map(|(id, _)| *id).collect(), streamed.iter().map(|(_, ids)| ids.len()).collect());
    let mut replayed = py
        .detach(|| {
            replay_units(
                &solvers,
                constructions,
                &settings,
                false,
                units.map_or_else(corpus_threads, NonZeroUsize::get),
                steps,
                &|record: &mut StreamRecord, decoder, stepped| record.step(decoder, stepped, points),
                &|solver| progress.start(solver),
                &|solver, replay| replay.into_result().map(|record| (case_columns(&evidence[solver], &record.tables, trains[solver]), record.ended)),
                &|solver| progress.settle(solver),
                step_cap,
            )
        })
        .into_iter();
    let mut tables = Vec::new();
    let mut faults = Vec::new();
    for (task, cases, solver_faults) in &found {
        faults.extend(solver_faults.iter().cloned());
        if cases.is_empty() || !reads.contains_key(task) {
            continue;
        }
        let mut outs = replayed.next().expect("a result for each solver that has cases").into_iter();
        for case in cases {
            let outcome = match &case.stream {
                Ok((_, relations)) => outs.next().expect("a result for each stream").and_then(|out| out).map(|out| (out, relations)),
                Err(fault) => Err(fault.clone()),
            };
            match outcome {
                Ok(((columns, ended), relations)) => {
                    tables.push(PyCaseTables::of(py, task.clone(), case.case.clone(), case.concept, settings.projection_cap, &columns, Some(relations))?);
                    if let Some(at) = ended.filter(|at| matches!(at.kind, PyConsistencyKind::Stopped)) {
                        faults.push(at.line(task, &case.case));
                    }
                }
                Err(fault) => faults.push(fault_line(task, Some(&case.case), &fault)),
            }
        }
    }
    Ok((tables, faults))
}

/// The consistency kind that the last step of a stream gave, with the index
/// of its token.
#[derive(Clone, Copy)]
struct EndedAt {
    token: usize,
    kind: PyConsistencyKind,
}

impl EndedAt {
    /// The line `<task> <case>: ended <kind> at token <index>`.
    fn line(&self, task: &str, case: &str) -> String {
        format!("{task} {case}: ended {} at token {}", self.kind.name(), self.token)
    }
}

impl PyConsistencyKind {
    fn name(self) -> &'static str {
        match self {
            PyConsistencyKind::Consistent => "Consistent",
            PyConsistencyKind::NotConsistent => "NotConsistent",
            PyConsistencyKind::SeveralValues => "SeveralValues",
            PyConsistencyKind::Fault => "Fault",
            PyConsistencyKind::Stopped => "Stopped",
        }
    }
}

/// What the replay of one stream of `stream_tables` records: the tables of
/// each step, and the last consistency a step gave.
#[derive(Clone, Default)]
struct StreamRecord {
    tables: Vec<(usize, Table)>,
    ended: Option<EndedAt>,
}

impl StreamRecord {
    /// Records the tables of a step and, where the step judged, its consistency.
    fn step(&mut self, decoder: &Decoder<'_>, stepped: Stepped<'_>, points: Points) {
        self.tables.extend(decoder.tables(points).into_iter().map(|table| (stepped.index, table)));
        if let Some(consistency) = &stepped.consistency {
            self.ended = Some(EndedAt { token: stepped.index, kind: PyConsistency::of(consistency).kind });
        }
    }
}

/// The tables of the token streams of one task, for a sampler that holds the
/// streams of the programs it generates, as `corpus_tables` gives those of the
/// corpus's.
///
/// `task` is the task id and `tasks` the directory of the task files; the
/// replay judges the train pairs in the closed world, as `corpus_tables` does.
/// `streams` is a list of pairs `(ids, model)`: `ids` the token ids of a
/// stream, the engine's forced ids included, and `model` one flag for each id,
/// 1 (or `True`) where the model wrote the token and 0 where the engine did,
/// a list or `bytes`, as a sampler holds them from `Decoder.step`. The step
/// cap and the replay's units count the model's steps.
/// `settings`, a `DecodeSettings` or `None` for the default, is that of the
/// sampler's `Session`: the vocabulary that gives the ids is built from it, and
/// the replay's decodes run under it, so each `RULE` end is judged as the
/// sampler's decode judged it. Its `projection_cap` and `table_work_cap` are
/// the tables' caps. `bodies` and `step_cap` are as in `corpus_tables`; the
/// replay computes no token mask.
/// `names` gives the case of each stream, or is `None` for the index of the
/// stream as text. `ValueError` is raised, before any replay, for a `model`
/// of another length than its `ids`, a flag other than 0 and 1, an id outside
/// the vocabulary of `settings`, a `names` of another length than `streams`,
/// and a name that is empty, `.` or `..`, holds `/`, or stands twice.
/// The first value holds the `CaseTables` of the streams that were replayed, in
/// the order of the streams. A stream whose replay faults keeps the tables
/// recorded before the fault. The second value holds, in the order of the
/// streams, for each stream replayed the line
/// `<task> <case>: ended <kind> at token <index>`, the verdict at the last
/// `RULE` end before the stream's end or cut, not at the stream's end, and `<kind>` one of `Consistent`, `NotConsistent`,
/// `SeveralValues`, `Fault` and `Stopped`, or `<task> <case>: ended none`;
/// then the fault line of each stream that faults or lies past `step_cap`,
/// which gives no tables, in the form of `corpus_streams`. A unit that panics
/// gives the one line `<task> <case>: the replay panicked: <message>` and no tables. The call runs with the
/// GIL released, but for the build of each `CaseTables`.
#[pyfunction]
#[pyo3(signature = (task, tasks, streams, names=None, settings=None, bodies=false, step_cap=None))]
fn stream_tables(py: Python<'_>, task: &str, tasks: &str, streams: Vec<(Vec<u32>, Vec<u8>)>, names: Option<Vec<String>>, settings: Option<PyDecodeSettings>, bodies: bool, step_cap: Option<usize>) -> PyResult<(Vec<PyCaseTables>, Vec<String>)> {
    let settings = match settings {
        Some(settings) => settings.engine()?,
        None => DecodeSettings::default(),
    };
    let vocabulary = Vocabulary::new(Registry::get(), &settings);
    let names = match names {
        Some(names) if names.len() != streams.len() => return Err(PyValueError::new_err(format!("{} names for {} streams", names.len(), streams.len()))),
        Some(names) => names,
        None => (0..streams.len()).map(|index| index.to_string()).collect(),
    };
    let mut seen = std::collections::HashSet::new();
    for name in &names {
        if name.is_empty() || name == "." || name == ".." || name.contains('/') {
            return Err(PyValueError::new_err(format!("the name {name:?} is no file name")));
        }
        if !seen.insert(name) {
            return Err(PyValueError::new_err(format!("the name {name:?} stands twice")));
        }
    }
    let mut ids: Vec<Vec<(u32, Emitter)>> = Vec::new();
    for (index, (stream, model)) in streams.iter().enumerate() {
        if stream.len() != model.len() {
            return Err(PyValueError::new_err(format!("stream {index}: {} ids and {} model flags", stream.len(), model.len())));
        }
        let mut tokens = Vec::with_capacity(stream.len());
        for (&id, &flag) in stream.iter().zip(model) {
            if id as usize >= vocabulary.len() {
                return Err(PyValueError::new_err(format!("stream {index}: the id {id} is outside the vocabulary of {} tokens", vocabulary.len())));
            }
            tokens.push((id, match flag {
                1 => Emitter::Model,
                0 => Emitter::Engine,
                _ => return Err(PyValueError::new_err(format!("stream {index}: the model flag {flag} is neither 0 nor 1"))),
            }));
        }
        ids.push(tokens);
    }
    let constructions = constructions()?;
    let (read, judged) = read_task_files(Path::new(tasks), task).map_err(PyRuntimeError::new_err)?;
    let points = if bodies { Points::All } else { Points::Relations };
    let evidence = evidence_tables(&read, Registry::get());
    let train = read.train.len();
    let solvers = [UnitSolver { task: &read, judged: &judged, streams: &ids, units: None }];
    let steps = ReplayProgress::default();
    let mut replayed = py.detach(|| {
        replay_units(
            &solvers,
            constructions,
            &settings,
            false,
            corpus_threads(),
            &steps,
            &|record: &mut StreamRecord, decoder, stepped| record.step(decoder, stepped, points),
            &|_| {},
            &|_, replay| (case_columns(&evidence, &replay.record.tables, train), replay.record.ended, replay.fault),
            &|_| {},
            step_cap,
        )
    });
    let outs = replayed.pop().expect("a result for the one solver");
    let (mut tables, mut ended, mut faults) = (Vec::new(), Vec::new(), Vec::new());
    for (case, out) in names.iter().zip(outs) {
        match out {
            Ok((columns, at, fault)) => {
                tables.push(PyCaseTables::of(py, task.to_string(), case.clone(), false, settings.projection_cap, &columns, None)?);
                ended.push(match at {
                    Some(at) => at.line(task, case),
                    None => format!("{task} {case}: ended none"),
                });
                faults.extend(fault.map(|fault| fault_line(task, Some(case), &fault)));
            }
            Err(fault) => faults.push(fault_line(task, Some(case), &fault)),
        }
    }
    ended.extend(faults);
    Ok((tables, ended))
}

/// The name of each orientation constant by its encoding, which is the
/// cell of an orientation value in `CaseTables.values`, in the order of the
/// encodings.
#[pyfunction]
fn orientation_names() -> Vec<(i32, String)> {
    arclog::decode::columns::orientation_names(Registry::get())
}

/// The cells of the constants that each orientation type without a
/// parameter admits, by the type's name.
#[pyfunction]
fn orientation_types() -> Vec<(String, Vec<i32>)> {
    arclog::decode::columns::orientation_types(Registry::get())
}

/// Steps each of `decoders` by the token with the id at its index in `ids`,
/// on the thread pool with the GIL released, and gives what each step
/// gives, in the order of `decoders`: the pair that `Decoder.step` gives, or,
/// for a decode that refuses its token, the `Refusal` it would raise, or, for
/// a decode whose step panicked, a `Fault` whose message is the panic's. That
/// decode stays at its state before the step.
#[pyfunction]
#[pyo3(name = "step_batch")]
fn step_batch_py(py: Python<'_>, decoders: Vec<Bound<'_, PyDecoder>>, ids: Vec<u32>) -> PyResult<Vec<Py<PyAny>>> {
    if decoders.len() != ids.len() {
        return Err(PyValueError::new_err("one id per decoder"));
    }
    let mut held = Vec::with_capacity(decoders.len());
    for decoder in &decoders {
        // A second hold of one decoder fails here, as the borrow of a `PyRefMut` does.
        held.push(decoder.try_borrow_mut()?);
    }
    let mut tokens = Vec::with_capacity(ids.len());
    for (decoder, id) in held.iter().zip(&ids) {
        tokens.push(decoder.token(*id)?);
    }
    let mut taken: Vec<Decoder<'static>> = held.iter_mut().map(|decoder| decoder.decoder.take().expect("a decode outside a batch step")).collect();
    let results = py.detach(|| step_batch(pool(), &mut taken, &tokens));
    for (decoder, stepped) in held.iter_mut().zip(taken) {
        decoder.decoder = Some(stepped);
    }
    held.iter()
        .zip(results.into_vec())
        .map(|(decoder, result)| match result {
            Err(panic) => Ok(Fault::new_err(panic).into_value(py).into_any()),
            Ok(result) => match decoder.step_result(result) {
                Ok(step) => Ok(step.into_pyobject(py)?.into_any().unbind()),
                Err(refusal) => Ok(refusal.into_value(py).into_any()),
            },
        })
        .collect()
}

#[pymodule]
#[pyo3(name = "arclog")]
fn arclog_module(module: &Bound<'_, PyModule>) -> PyResult<()> {
    module.add_class::<PyWorld>()?;
    module.add_class::<PyTask>()?;
    module.add_class::<PyDecodeSettings>()?;
    module.add_class::<PyVocabulary>()?;
    module.add_class::<PySession>()?;
    module.add_class::<PyDecoder>()?;
    module.add_class::<PyStopKind>()?;
    module.add_class::<PyConsistencyKind>()?;
    module.add_class::<PyConsistency>()?;
    module.add_class::<PyValueKind>()?;
    module.add_class::<PyRowsView>()?;
    module.add_class::<PyAssigned>()?;
    module.add_class::<PyProjection>()?;
    module.add_class::<PyProjections>()?;
    module.add_class::<PyCaseStream>()?;
    module.add_class::<PyCaseTables>()?;
    module.add("Refusal", module.py().get_type::<Refusal>())?;
    module.add("Fault", module.py().get_type::<Fault>())?;
    module.add_function(wrap_pyfunction!(step_batch_py, module)?)?;
    module.add_class::<PyReplayProgress>()?;
    module.add_function(wrap_pyfunction!(corpus_streams, module)?)?;
    module.add_function(wrap_pyfunction!(corpus_tables, module)?)?;
    module.add_function(wrap_pyfunction!(stream_tables, module)?)?;
    module.add_function(wrap_pyfunction!(orientation_names, module)?)?;
    module.add_function(wrap_pyfunction!(orientation_types, module)?)?;
    Ok(())
}
