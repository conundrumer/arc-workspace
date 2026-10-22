//! The Python bindings of the arclog engine: the pyo3 extension, built by
//! maturin as an abi3 wheel.
//!
//! Each class wraps a value of the core crate and restates no rule of it. A
//! task session owns the data that its decoders borrow, so a `PyDecoder`
//! holds the session's data beside the decode.

use std::collections::HashMap;
use std::sync::{Arc, OnceLock};
use std::time::Duration;

use arclog::decode::{step_batch, Consistency, Decoder};
use arclog::eval::instance::Constructions;
use arclog::eval::pool::Pool;
use arclog::eval::{Outcome, RelationValue};
use arclog::judge::attempts::Attempts;
use arclog::judge::candidates::{PairCandidates, Section, World};
use arclog::registry::Registry;
use arclog::session::{SessionBound, TaskSession, SESSION_BYTES};
use arclog::stream::{DecodeSettings, Token, Vocabulary, VocabularyCaps};
use arclog::task::{read_judged_train_text, read_task_text, Grid, JudgedTask, Task, TaskError};
use arclog::terms::Example;
use arclog::trace::render::{trace_form, TraceFormOptions};
use arclog::trace::{Stop, TopK};
use pyo3::create_exception;
use pyo3::exceptions::{PyIndexError, PyRuntimeError, PyValueError};
use pyo3::prelude::*;
use pyo3::types::{PyBytes, PyList};

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
        }
    }

    fn engine(&self) -> PyResult<DecodeSettings> {
        let deadline = Duration::try_from_secs_f64(self.deadline_seconds).map_err(|error| PyValueError::new_err(format!("deadline_seconds: {error}")))?;
        Ok(DecodeSettings {
            proposer_tokens: self.proposer_tokens,
            type_domain_proposers: self.type_domain_proposers,
            vocabulary: VocabularyCaps { relations: self.relations, columns: self.columns, labels: self.labels },
            deadline,
            ..DecodeSettings::default()
        })
    }
}

#[pymethods]
impl PyDecodeSettings {
    #[new]
    #[pyo3(signature = (*, proposer_tokens=None, type_domain_proposers=None, relations=None, columns=None, labels=None, deadline_seconds=None))]
    fn new(
        proposer_tokens: Option<bool>,
        type_domain_proposers: Option<bool>,
        relations: Option<u32>,
        columns: Option<u32>,
        labels: Option<u32>,
        deadline_seconds: Option<f64>,
    ) -> PyResult<PyDecodeSettings> {
        let base = PyDecodeSettings::of(&DecodeSettings::default());
        let settings = PyDecodeSettings {
            proposer_tokens: proposer_tokens.unwrap_or(base.proposer_tokens),
            type_domain_proposers: type_domain_proposers.unwrap_or(base.type_domain_proposers),
            relations: relations.unwrap_or(base.relations),
            columns: columns.unwrap_or(base.columns),
            labels: labels.unwrap_or(base.labels),
            deadline_seconds: deadline_seconds.unwrap_or(base.deadline_seconds),
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
/// or label slot.
#[pyclass(name = "Vocabulary", frozen, module = "arclog")]
struct PyVocabulary {
    names: Box<[String]>,
    ids: HashMap<String, u32>,
}

impl PyVocabulary {
    fn of(vocabulary: &Vocabulary<'_>) -> PyVocabulary {
        let names: Box<[String]> = (0..vocabulary.len() as u32).map(|id| vocabulary.token(id).expect("an id of the vocabulary").to_string()).collect();
        let ids = names.iter().enumerate().map(|(id, name)| (name.clone(), id as u32)).collect();
        PyVocabulary { names, ids }
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
        let mask = decoder.admissible();
        let mut bytes = vec![0u8; decoder.vocabulary().len().div_ceil(8)];
        for id in 0..decoder.vocabulary().len() as u32 {
            if mask.contains(id) {
                bytes[id as usize / 8] |= 1 << (id % 8);
            }
        }
        PyBytes::new(py, &bytes)
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
    module.add("Refusal", module.py().get_type::<Refusal>())?;
    module.add("Fault", module.py().get_type::<Fault>())?;
    module.add_function(wrap_pyfunction!(step_batch_py, module)?)?;
    Ok(())
}
