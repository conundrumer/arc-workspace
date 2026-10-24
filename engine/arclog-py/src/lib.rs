//! The Python bindings of the arclog engine: the pyo3 extension, built by
//! maturin as an abi3 wheel.
//!
//! Each class wraps a value of the core crate and restates no rule of it. A
//! task session owns the data that its decoders borrow, so a `PyDecoder`
//! holds the session's data beside the decode.

use std::collections::HashMap;
use std::panic::{catch_unwind, AssertUnwindSafe};
use std::path::Path;
use std::sync::{Arc, Mutex, OnceLock};
use std::time::Duration;

use arclog::decode::columns::{case_columns, CaseColumns, StopColumns};
use arclog::decode::corpus::{mask_computations, new_mask_computations, read_task_files, replay_panic, replay_prefix_tree, solver_tables, sorted_streams};
use arclog::decode::{step_batch, Consistency, Decoder, Points, TokenMask, Views};
use arclog::eval::instance::Constructions;
use arclog::eval::pool::Pool;
use arclog::harness::{corpus_threads, run_on_workers, run_over_corpus, SolverResult};
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
    deadline_seconds: f64,
    view_cap: u64,
}

impl PyDecodeSettings {
    fn of(settings: &DecodeSettings) -> PyDecodeSettings {
        PyDecodeSettings {
            proposer_tokens: settings.proposer_tokens,
            type_domain_proposers: settings.type_domain_proposers,
            relations: settings.vocabulary.relations,
            columns: settings.vocabulary.columns,
            labels: settings.vocabulary.labels,
            deadline_seconds: settings.deadline.as_secs_f64(),
            view_cap: settings.view_cap,
        }
    }

    fn engine(&self) -> PyResult<DecodeSettings> {
        let deadline = Duration::try_from_secs_f64(self.deadline_seconds).map_err(|error| PyValueError::new_err(format!("deadline_seconds: {error}")))?;
        Ok(DecodeSettings {
            proposer_tokens: self.proposer_tokens,
            type_domain_proposers: self.type_domain_proposers,
            vocabulary: VocabularyCaps { relations: self.relations, columns: self.columns, labels: self.labels },
            deadline,
            view_cap: self.view_cap,
            ..DecodeSettings::default()
        })
    }
}

#[pymethods]
impl PyDecodeSettings {
    #[new]
    #[pyo3(signature = (*, proposer_tokens=None, type_domain_proposers=None, relations=None, columns=None, labels=None, deadline_seconds=None, view_cap=None))]
    fn new(
        proposer_tokens: Option<bool>,
        type_domain_proposers: Option<bool>,
        relations: Option<u32>,
        columns: Option<u32>,
        labels: Option<u32>,
        deadline_seconds: Option<f64>,
        view_cap: Option<u64>,
    ) -> PyResult<PyDecodeSettings> {
        let base = PyDecodeSettings::of(&DecodeSettings::default());
        let settings = PyDecodeSettings {
            proposer_tokens: proposer_tokens.unwrap_or(base.proposer_tokens),
            type_domain_proposers: type_domain_proposers.unwrap_or(base.type_domain_proposers),
            relations: relations.unwrap_or(base.relations),
            columns: columns.unwrap_or(base.columns),
            labels: labels.unwrap_or(base.labels),
            deadline_seconds: deadline_seconds.unwrap_or(base.deadline_seconds),
            view_cap: view_cap.unwrap_or(base.view_cap),
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

/// One view of a sub-body: the positions of its columns in the body, and the
/// count of its rows on each example, in the shape of `counts`.
#[pyclass(name = "View", frozen, get_all, module = "arclog")]
struct PyView {
    columns: Vec<u16>,
    counts: Vec<Py<PyAssigned>>,
}

/// The views of a sub-body, or the bound that stopped them.
#[pyclass(name = "Views", frozen, get_all, module = "arclog")]
struct PyViews {
    views: Vec<Py<PyView>>,
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

    /// The views of the sub-body of the clause in progress, as
    /// `docs/engine/synthesis.md#decode-interface` gives them, or `None`
    /// where no clause is in progress. The views are empty and `stop` is set
    /// where a bound ended the body or the search. The views give no rows.
    /// Raises `Fault` where the sub-body does not check or compile.
    fn views(&self, py: Python<'_>) -> PyResult<Option<PyViews>> {
        let Some(outcome) = self.decoder().views() else { return Ok(None) };
        let found = match settled(outcome)? {
            Views::Found(found) => found,
            Views::Stopped(stop) => return Ok(Some(PyViews { views: Vec::new(), stop: Some(Stop::from(stop.bound).into()) })),
        };
        let mut views = Vec::new();
        for view in found {
            let counts = view
                .rows
                .into_vec()
                .into_iter()
                .map(|rows| Py::new(py, assigned!(py, rows, |rows| rows.map(|relation| relation.len()).into_pyobject(py)?.into_any().unbind())?))
                .collect::<PyResult<Vec<_>>>()?;
            views.push(Py::new(py, PyView { columns: view.columns.iter().map(|column| column.0).collect(), counts })?);
        }
        Ok(Some(PyViews { views, stop: None }))
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
/// solver's task id, in the order of the task ids. The walk runs on the
/// threads of the corpus harness with the GIL released.
fn walk_corpus<C: Send>(
    py: Python<'_>,
    corpus: &str,
    task_ids: &Option<Vec<String>>,
    solver: impl Fn(&str) -> (Vec<C>, Vec<String>) + Sync,
) -> PyResult<Vec<(String, Vec<C>, Vec<String>)>> {
    let found: Mutex<Vec<(String, Vec<C>, Vec<String>)>> = Mutex::new(Vec::new());
    let walked = py.detach(|| {
        run_over_corpus(
            Path::new(corpus),
            |corpus_solver| {
                if task_ids.as_ref().is_some_and(|ids| !ids.contains(&corpus_solver.task_id)) {
                    return SolverResult::Pass;
                }
                let (cases, faults) = solver(&corpus_solver.task_id);
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
/// case gives no masks.
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
/// order of their tokens, into groups of consecutive streams, so that no
/// group's mask computations pass the share of each thread in those of the
/// call, but by the last stream's, and replays the groups, the largest
/// first. A group replays the mask of each prefix its streams share once.
#[pyfunction]
#[pyo3(signature = (corpus, all_cases=false, task_ids=None, tasks=None))]
fn corpus_streams(py: Python<'_>, corpus: &str, all_cases: bool, task_ids: Option<Vec<String>>, tasks: Option<&str>) -> PyResult<(Vec<PyCaseStream>, Vec<String>)> {
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
                            streams.push(IdStream { task: id.to_string(), case: case.case, concept: case.concept, ids: token_ids(&stream, &vocabulary), masks });
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
        py.detach(|| replay_masks(&mut found, &reads, constructions));
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

/// A run of consecutive streams of one solver, in the order of their
/// tokens, which one thread replays from a new decoder.
struct ReplayUnit {
    /// The index in `found` of the solver.
    solver: usize,
    /// The indices in the solver's streams of the unit's streams.
    streams: Vec<usize>,
    /// The mask computations of the unit's replay.
    masks: usize,
}

/// Replays the streams of `found` whose masks are due, which are those with
/// `Ok(None)`, on the tasks that `reads` holds, in units cut so that no
/// unit passes its share of the mask computations of the call but by its
/// last stream's, and sets each stream's `masks`. A solver whose task did not
/// read, or whose unit panicked, gives each of its streams that fault.
fn replay_masks(found: &mut [(String, Vec<IdStream>, Vec<String>)], reads: &HashMap<String, Result<(Task, JudgedTask), String>>, constructions: &'static Constructions) {
    let mut solvers = Vec::new();
    let mut total = 0;
    for (solver, (id, streams, _)) in found.iter().enumerate() {
        let Some(read) = reads.get(id) else { continue };
        if let Err(fault) = read {
            solvers.push((solver, Vec::new(), Some(fault.clone())));
            continue;
        }
        let due: Vec<usize> = (0..streams.len()).filter(|&stream| matches!(streams[stream].masks, Ok(None))).collect();
        let ids: Vec<Vec<(u32, Emitter)>> = due.iter().map(|&stream| streams[stream].ids.clone()).collect();
        let sorted: Vec<usize> = sorted_streams(&ids);
        total += mask_computations(&sorted.iter().map(|&stream| ids[stream].as_slice()).collect::<Vec<_>>());
        solvers.push((solver, sorted.into_iter().map(|stream| (due[stream], ids[stream].clone())).collect::<Vec<_>>(), None));
    }
    let share = (total / corpus_threads()).max(1);
    let mut units = Vec::new();
    for (solver, sorted, _) in &solvers {
        let mut unit = ReplayUnit { solver: *solver, streams: Vec::new(), masks: 0 };
        let mut last: Option<&[(u32, Emitter)]> = None;
        for (stream, ids) in sorted {
            let masks = new_mask_computations(last, ids);
            unit.streams.push(*stream);
            unit.masks += masks;
            last = Some(ids);
            if unit.masks >= share {
                units.push(std::mem::replace(&mut unit, ReplayUnit { solver: *solver, streams: Vec::new(), masks: 0 }));
                last = None;
            }
        }
        if !unit.streams.is_empty() {
            units.push(unit);
        }
    }
    units.sort_by(|a, b| b.masks.cmp(&a.masks));
    let outcomes = run_on_workers(&units, |unit| {
        let (_, streams, _) = &found[unit.solver];
        let Some(Ok((task, judged))) = reads.get(&found[unit.solver].0) else { unreachable!("a unit stands over a task that read") };
        let ids: Vec<Vec<(u32, Emitter)>> = unit.streams.iter().map(|&stream| streams[stream].ids.clone()).collect();
        catch_unwind(AssertUnwindSafe(|| {
            replay_prefix_tree(task, judged, &ids, constructions, &|masks: &mut Vec<u8>, decoder, stepped| {
                masks.extend(mask_bytes(stepped.mask, decoder.vocabulary().len()));
            })
        }))
        .map_err(|payload| replay_panic(&*payload))
    });
    let mut faults: HashMap<usize, String> = solvers.into_iter().filter_map(|(solver, _, fault)| fault.map(|fault| (solver, fault))).collect();
    for (unit, outcome) in units.iter().zip(outcomes) {
        match outcome {
            Ok(masks) => {
                for (&stream, masks) in unit.streams.iter().zip(masks) {
                    found[unit.solver].1[stream].masks = masks.map(Some);
                }
            }
            Err(fault) => {
                faults.entry(unit.solver).or_insert(fault);
            }
        }
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
/// `tables`, `entries`, `assigned`, `views` and `view_rows` are dicts of
/// columns, one for each part of the layout, named as its fields. An integer
/// column is `bytes` in native byte order, which `numpy.frombuffer` reads at
/// the dtype that `dtypes` gives for `"<part>.<column>"`; any other column is
/// a list. `values` is the `int32` cells of every row, which the offsets of the
/// parts index.
#[pyclass(name = "CaseTables", frozen, get_all, module = "arclog")]
struct PyCaseTables {
    task: String,
    case: String,
    concept: bool,
    tables: Py<PyDict>,
    entries: Py<PyDict>,
    assigned: Py<PyDict>,
    views: Py<PyDict>,
    view_rows: Py<PyDict>,
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

impl PyCaseTables {
    fn of(py: Python<'_>, task: String, case: String, concept: bool, columns: &CaseColumns) -> PyResult<Self> {
        let dtypes = PyDict::new(py);
        let t = Part::new(py, "tables", &dtypes);
        let c = &columns.tables;
        t.ints("token", &c.token)?;
        t.list("form", &c.form)?;
        t.ints("point", &c.point)?;
        t.ints("conjuncts", &c.conjuncts)?;
        t.ints("sites", &c.sites)?;
        t.ints("relation", &c.relation)?;
        t.list("column_names", &c.column_names)?;
        t.list("column_types", &c.column_types)?;
        t.ints("width", &c.width)?;
        t.list("det_relations", &c.det_relations)?;
        t.list("det_types", &c.det_types)?;
        t.list("det_widths", &c.det_widths)?;
        t.ints("views", &c.views)?;
        t.stop("views_stop", &c.views_stop)?;
        t.list("fault", &c.fault)?;
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
        let v = Part::new(py, "views", &dtypes);
        let c = &columns.views;
        v.ints("table", &c.table)?;
        v.list("columns", &c.columns)?;
        v.ints("width", &c.width)?;
        let r = Part::new(py, "view_rows", &dtypes);
        let c = &columns.view_rows;
        r.ints("view", &c.view)?;
        r.ints("entry", &c.entry)?;
        r.ints("defined", &c.defined)?;
        r.ints("rows", &c.rows)?;
        r.ints("offset", &c.offset)?;
        Ok(PyCaseTables {
            task,
            case,
            concept,
            tables: t.dict.unbind(),
            entries: e.dict.unbind(),
            assigned: a.dict.unbind(),
            views: v.dict.unbind(),
            view_rows: r.dict.unbind(),
            values: PyBytes::new(py, &cell_bytes(&columns.values)).unbind(),
            dtypes: dtypes.unbind(),
        })
    }
}

/// The tables of each case of each solver of `corpus`, on its task in
/// `tasks`, the concept case or, with `all_cases`, every case, over the
/// solvers whose task ids `task_ids` gives, or every solver where it is
/// `None`, in the order of the task ids and then of the cases. Each table
/// is at the index of the token whose step gives it. The relations of the
/// finished forms are tabled, and with `bodies` the bodies in progress as well.
/// The second value holds a line for each case that gives no tables and each
/// solver that gives none, in the form of `corpus_streams`, in the order of
/// the task ids. The walk runs on the threads of the corpus harness with the
/// GIL released.
#[pyfunction]
#[pyo3(signature = (corpus, tasks, all_cases=false, task_ids=None, bodies=false))]
fn corpus_tables(py: Python<'_>, corpus: &str, tasks: &str, all_cases: bool, task_ids: Option<Vec<String>>, bodies: bool) -> PyResult<(Vec<PyCaseTables>, Vec<String>)> {
    let points = if bodies { Points::All } else { Points::Relations };
    let constructions = constructions()?;
    let found = walk_corpus(py, corpus, &task_ids, |id| {
        let (mut cases, mut faults) = (Vec::new(), Vec::new());
        match solver_tables(Path::new(corpus), Path::new(tasks), id, all_cases, points, constructions) {
            Ok(solver) => {
                for case in solver.cases {
                    match case.tables {
                        Ok(tables) => cases.push((case.case, case.concept, case_columns(&tables, solver.train))),
                        Err(fault) => faults.push(fault_line(id, Some(&case.case), &fault)),
                    }
                }
            }
            Err(fault) => faults.push(fault_line(id, None, &fault)),
        }
        (cases, faults)
    })?;
    let mut tables = Vec::new();
    let mut faults = Vec::new();
    for (task, cases, solver_faults) in found {
        for (case, concept, columns) in cases {
            tables.push(PyCaseTables::of(py, task.clone(), case, concept, &columns)?);
        }
        faults.extend(solver_faults);
    }
    Ok((tables, faults))
}

/// The name of each orientation constant by its encoding, which is the
/// cell of an orientation value in `CaseTables.values`, in the order of the
/// encodings.
#[pyfunction]
fn orientation_names() -> Vec<(i32, String)> {
    arclog::decode::columns::orientation_names(Registry::get())
}

/// Steps each of `decoders` by the token with the id at its index in `ids`,
/// on the thread pool with the GIL released, and gives what each step
/// gives, in the order of `decoders`: the pair that `Decoder.step` gives, or,
/// for a decode that refuses its token, the `Refusal` it would raise.
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
        .map(|(decoder, result)| match decoder.step_result(result) {
            Ok(step) => Ok(step.into_pyobject(py)?.into_any().unbind()),
            Err(refusal) => Ok(refusal.into_value(py).into_any()),
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
    module.add_class::<PyView>()?;
    module.add_class::<PyViews>()?;
    module.add_class::<PyCaseStream>()?;
    module.add_class::<PyCaseTables>()?;
    module.add("Refusal", module.py().get_type::<Refusal>())?;
    module.add("Fault", module.py().get_type::<Fault>())?;
    module.add_function(wrap_pyfunction!(step_batch_py, module)?)?;
    module.add_function(wrap_pyfunction!(corpus_streams, module)?)?;
    module.add_function(wrap_pyfunction!(corpus_tables, module)?)?;
    module.add_function(wrap_pyfunction!(orientation_names, module)?)?;
    Ok(())
}
