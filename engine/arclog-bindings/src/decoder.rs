//! A decode over a task in a session, as Python steps it: the mask, the
//! step, the requests of the form in progress, and the batch step.

use std::sync::{Arc, OnceLock};

use arclog::decode::{step_batch, BatchFault, Decoder, Projections, TokenMask};
use arclog::eval::pool::Pool;
use arclog::judge::attempts::Attempts;
use arclog::judge::candidates::{PairCandidates, Section};
use arclog::registry::Registry;
use arclog::stats::{self, Phase};
use arclog::stream::Token;
use arclog::task::Task;
use arclog::terms::Example;
use arclog::trace::render::{trace_form, TraceFormOptions};
use arclog::trace::{Stop, TopK};
use pyo3::exceptions::{PyIndexError, PyValueError};
use pyo3::prelude::*;
use pyo3::types::PyBytes;

use crate::constructions;
use crate::errors::{check_effort, effort_exhausted, labeling_bound_reached, settled, Fault, Refusal};
use crate::results::{assigned, grid_rows, rows_view, PyAssigned, PyConsistency, PyProjection, PyProjections};
use crate::session::SessionData;
use crate::study::{written_query_hash, finished_query};
use crate::vocabulary::PyVocabulary;

/// The thread pool of the batch step, built once.
fn pool() -> &'static Pool {
    static POOL: OnceLock<Pool> = OnceLock::new();
    POOL.get_or_init(|| Pool::new(None))
}

/// What `Decoder.step` gives: the ids of the tokens the engine emits, the
/// consistency of the `OUT` form that the token ends, and the consistency of
/// the `RULE` clause that it ends, where the decode settings run the rule tests.
type StepResult = (Vec<u32>, Option<PyConsistency>, Option<PyConsistency>);

/// A decode over a task in a session.
///
/// The decode borrows the data of its session, which the struct holds in an
/// `Arc` that outlives the decode: `decoder` is declared before `data`, so
/// it drops first, and the `'static` of its type stands for the lifetime of
/// that `Arc`. `decoder` is `None` only inside [`step_batch`]'s call.
#[pyclass(name = "Decoder", module = "arclog", weakref)]
pub struct PyDecoder {
    decoder: Option<Decoder<'static>>,
    data: Arc<SessionData>,
}

impl PyDecoder {
    /// A decode of no token yet on the session of `data`, judging the train
    /// pairs, or, with `evaluates` false, a decode that evaluates nothing
    /// ([`Decoder::without_evaluation`]).
    pub(crate) fn open(data: &Arc<SessionData>, evaluates: bool) -> PyResult<PyDecoder> {
        // SAFETY: the reference points into the `Arc`'s allocation, which the
        // returned `PyDecoder` keeps alive and never moves, and the decode
        // drops before the `Arc` does.
        let borrowed: &'static SessionData = unsafe { &*Arc::as_ptr(data) };
        let world = borrowed.task.world;
        let train: Arc<[PairCandidates<'static>]> = borrowed.task.judged.train.iter().map(|pair| PairCandidates::of(pair, Section::Train, world)).collect();
        let decoder = Decoder::new(&borrowed.task.task, &borrowed.session, Registry::get(), constructions()?, &borrowed.settings).judging(train);
        let decoder = if evaluates { decoder } else { decoder.without_evaluation() };
        Ok(PyDecoder { decoder: Some(decoder), data: Arc::clone(data) })
    }

    /// The first token of `ids` with a flag of 1 in `model` that the decode
    /// refuses, stepping each such token and none of the others: its index in
    /// `ids` and the refusal; none where the decode takes each of them.
    pub(crate) fn first_refusal(&mut self, ids: &[u32], model: &[u8]) -> PyResult<Option<(usize, arclog::decode::Refusal)>> {
        if ids.len() != model.len() {
            return Err(PyValueError::new_err("one model flag per id"));
        }
        let decoder = self.decoder_mut();
        for (at, (&id, &flag)) in ids.iter().zip(model).enumerate() {
            if flag == 0 {
                continue;
            }
            let token = decoder.vocabulary().token(id).cloned().ok_or_else(|| PyIndexError::new_err(format!("no token with id {id}")))?;
            if let Err(refusal) = decoder.step(token) {
                return Ok(Some((at, refusal)));
            }
        }
        Ok(None)
    }

    /// The decode, for a crate that reads it as the engine's own value.
    pub fn decoder(&self) -> &Decoder<'static> {
        self.decoder.as_ref().expect("a decode outside a batch step")
    }

    /// The task that the decode runs on.
    pub fn task(&self) -> &Task {
        &self.data.task.task
    }

    /// The value of type `T` that `make` derives from the task, made on the
    /// first call for the decode's session, and shared by its decodes.
    pub fn derived<T: std::any::Any + Send + Sync>(&self, make: impl FnOnce() -> T) -> Arc<T> {
        self.data.derived(make)
    }

    fn decoder_mut(&mut self) -> &mut Decoder<'static> {
        self.decoder.as_mut().expect("a decode outside a batch step")
    }

    fn token(&self, id: u32) -> PyResult<Token> {
        self.decoder().vocabulary().token(id).cloned().ok_or_else(|| PyIndexError::new_err(format!("no token with id {id}")))
    }

    /// The ids of the tokens `forced`, which the engine emits.
    fn forced_ids(&self, forced: &[Token]) -> Vec<u32> {
        let vocabulary = self.decoder().vocabulary();
        forced.iter().map(|token| vocabulary.id(token).expect("a forced token is in the vocabulary")).collect()
    }

    fn step_result(&self, result: arclog::decode::StepResult) -> PyResult<StepResult> {
        match result {
            Ok(step) => Ok((self.forced_ids(&step.forced), step.consistency.as_ref().map(|consistency| PyConsistency::of(consistency, step.capped_sets)), step.rule_test.as_ref().map(|rule_test| PyConsistency::of(rule_test, step.rule_capped_sets)))),
            Err(refusal) => Err(refusal_error(&refusal)),
        }
    }
}

/// The `Refusal` that Python raises for a decode's `refusal`.
fn refusal_error(refusal: &arclog::decode::Refusal) -> PyErr {
    Refusal::new_err(refusal_message(refusal))
}

/// The message of the `Refusal` that Python raises for a decode's `refusal`.
pub(crate) fn refusal_message(refusal: &arclog::decode::Refusal) -> String {
    format!("{refusal:?}")
}

/// The attempts as lists of at most two grids, one list per test input.
fn attempts_lists(attempts: &[Attempts]) -> Vec<Vec<Vec<Vec<u32>>>> {
    attempts
        .iter()
        .map(|attempt| match attempt {
            Attempts::None => Vec::new(),
            Attempts::One(one) => vec![grid_rows(one)],
            Attempts::Two(one, two) => vec![grid_rows(one), grid_rows(two)],
        })
        .collect()
}

/// The bytes of `mask` over a vocabulary of `len` tokens: bit `id % 8` of
/// byte `id // 8` is set where the token with that id is admissible.
pub(crate) fn mask_bytes(mask: &TokenMask, len: usize) -> Vec<u8> {
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

    /// Whether the decode has ended at a consistent `OUT` form.
    #[getter]
    fn ended(&self) -> bool {
        self.decoder().output().is_some()
    }

    /// The tokens that may come next: bit `id % 8` of byte `id // 8` is set
    /// where the token with that id is admissible.
    fn admissible<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PyBytes>> {
        let _timed = stats::span(Phase::PyAdmissible);
        let decoder = self.decoder();
        let mask = decoder.admissible();
        check_effort(py)?;
        Ok(PyBytes::new(py, &mask_bytes(&mask, decoder.vocabulary().len())))
    }

    /// The atoms that may come next at this state, each as the ids of its
    /// tokens, in a fixed order, with the count of the states that the walk
    /// read and whether it stopped at `limit` states
    /// (`arclog::decode::Decoder::candidate_atoms`).
    #[pyo3(signature = (limit=1<<20, reference=false))]
    fn atoms(&self, py: Python<'_>, limit: usize, reference: bool) -> PyResult<(Vec<Vec<u32>>, usize, bool)> {
        let decoder = self.decoder();
        let found = py.detach(|| if reference { decoder.candidate_atoms_reference(limit) } else { decoder.candidate_atoms(limit) });
        check_effort(py)?;
        Ok((found.atoms.iter().map(|atom| atom.to_vec()).collect(), found.states, found.truncated))
    }

    /// Advances the decode by the token with id `id`, and gives the ids of
    /// the tokens the engine emits after it, with the consistency of the
    /// `OUT` form that the token ends, or `None`, and the consistency of the
    /// `RULE` clause that it ends under the rule tests, or `None`. Raises
    /// `Refusal` for a token outside the mask, and leaves the decode as it was.
    fn step(&mut self, py: Python<'_>, id: u32) -> PyResult<StepResult> {
        let _timed = stats::span(Phase::PyStep);
        let token = self.token(id)?;
        let result = self.decoder_mut().step(token);
        check_effort(py)?;
        self.step_result(result)
    }

    /// A fork of the decode advanced by the token with id `id`, and what `step`
    /// gives for it: the fork and the result of `fork()`, then `step(id)` on
    /// the fork. Where `admissible` has computed the mask at this state and the
    /// mask admits the token, the fork's state comes from the mask, and no
    /// check of the token runs again. Raises `Refusal` for a token outside the
    /// mask, and leaves the decode as it was.
    fn fork_step(&self, py: Python<'_>, id: u32) -> PyResult<(PyDecoder, StepResult)> {
        let _timed = stats::span(Phase::PyStep);
        let token = self.token(id)?;
        let (decoder, result) = self.decoder().fork_step(token);
        check_effort(py)?;
        let child = PyDecoder { decoder: Some(decoder), data: Arc::clone(&self.data) };
        let result = child.step_result(result)?;
        Ok((child, result))
    }

    /// The ids of the tokens the engine emits after the token with id `id`,
    /// as `step` gives them, with no consistency test, and leaves the decode
    /// as it was. Where `admissible` has computed the mask at this state,
    /// it reads them from the mask. Raises `Refusal` for a token outside the
    /// mask, as `step` does.
    fn forced(&self, py: Python<'_>, id: u32) -> PyResult<Vec<u32>> {
        let _timed = stats::span(Phase::PyForced);
        let token = self.token(id)?;
        let forced = self.decoder().forced(&token);
        check_effort(py)?;
        forced.map(|forced| self.forced_ids(&forced)).map_err(|refusal| refusal_error(&refusal))
    }

    /// Whether each token with an id of `ids` may come next: the verdicts of
    /// `forced` for those tokens, each `True` where `forced` gives the token's
    /// forced ids and `False` where it raises `Refusal`. The checks run over
    /// those tokens together, as the checks of `admissible` run over the
    /// vocabulary, and leave the decode as it was.
    fn admits(&self, py: Python<'_>, ids: Vec<u32>) -> PyResult<Vec<bool>> {
        let _timed = stats::span(Phase::PyAdmits);
        let vocabulary = self.decoder().vocabulary();
        if let Some(&id) = ids.iter().find(|&&id| vocabulary.token(id).is_none()) {
            return Err(PyIndexError::new_err(format!("no token with id {id}")));
        }
        let admitted = self.decoder().admits(&ids);
        check_effort(py)?;
        Ok(admitted)
    }

    /// A second decode from the same state, which shares this one's caches.
    pub(crate) fn fork(&self) -> PyDecoder {
        let _timed = stats::span(Phase::PyFork);
        PyDecoder { decoder: Some(self.decoder().fork()), data: Arc::clone(&self.data) }
    }

    /// The rows of the sub-body of the clause in progress on `example`, or
    /// `None` where no clause is in progress. Raises `Fault` where the
    /// sub-body does not check or compile.
    #[pyo3(signature = (example=None))]
    fn rows(&mut self, py: Python<'_>, example: Option<u16>) -> PyResult<Option<PyAssigned>> {
        let observed = self.decoder_mut().observe_rows(example.map(Example::at));
        check_effort(py)?;
        observed
            .map(|outcome| assigned(py, settled(outcome)?, |value| Ok(Py::new(py, rows_view(&value))?.into_any())))
            .transpose()
    }

    /// The count of the rows of the sub-body on each example, or once for a
    /// task-wide clause; `None` where no clause is in progress.
    fn counts(&mut self, py: Python<'_>) -> PyResult<Option<Vec<PyAssigned>>> {
        let observed = self.decoder_mut().observe_counts();
        check_effort(py)?;
        observed
            .map(|outcomes| {
                outcomes
                    .into_vec()
                    .into_iter()
                    .map(|outcome| assigned(py, settled(outcome)?, |count| Ok(count.into_pyobject(py)?.into_any().unbind())))
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
        let projected = self.decoder().projections();
        check_effort(py)?;
        let Some(outcome) = projected else { return Ok(None) };
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
                .map(|rows| Py::new(py, assigned(py, rows, |rows| Ok(rows.map(|relation| relation.len()).into_pyobject(py)?.into_any().unbind()))?))
                .collect::<PyResult<Vec<_>>>()?;
            projections.push(Py::new(py, PyProjection { columns: projection.columns.iter().map(|column| column.0).collect(), counts })?);
        }
        Ok(Some(PyProjections { projections, stop: None }))
    }

    /// The attempts on each test input, as lists of at most two grids, or
    /// `None` until the decode ends at a consistent relation.
    fn attempts(&self, py: Python<'_>) -> PyResult<Option<Vec<Vec<Vec<Vec<u32>>>>>> {
        let attempted = self.decoder().attempts();
        check_effort(py)?;
        let Some(outcome) = attempted else { return Ok(None) };
        let attempts = settled(outcome)?;
        Ok(Some(attempts_lists(&attempts)))
    }

    /// The output sets of the consistency tests of the decode's steps that
    /// ended at the model cap with the grids found so far.
    #[getter]
    fn capped_sets(&self) -> u64 {
        self.decoder().capped_sets()
    }

    /// The attempts, as `attempts` gives them, and the count of the output
    /// sets on the test inputs that ended at the model cap with the grids
    /// found so far; `None` until the decode ends at a consistent relation.
    fn attempts_counted(&self, py: Python<'_>) -> PyResult<Option<(Vec<Vec<Vec<Vec<u32>>>>, u64)>> {
        let attempted = self.decoder().attempts_counted();
        check_effort(py)?;
        let Some(outcome) = attempted else { return Ok(None) };
        let (attempts, capped) = settled(outcome)?;
        Ok(Some((attempts_lists(&attempts), capped)))
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

    /// The hash of the resolver's content of the finished query at
    /// `index`: free of the names that the scope gives its tables. Index -1
    /// is the last finished query.
    #[pyo3(signature = (index=-1))]
    fn query_hash(&self, py: Python<'_>, index: isize) -> PyResult<u128> {
        let decoder = self.decoder();
        let (position, _) = finished_query(decoder.program(), index)?;
        let hash = decoder.query_hash_or_bound(position).ok_or_else(|| PyIndexError::new_err(format!("no content for the query at index {index}")))?;
        hash.map(|hash| hash.0).map_err(|bound| labeling_bound_reached(py, bound))
    }

    /// The bytes that `query_hash` hashes, for the finished query at `index`.
    #[pyo3(signature = (index=-1))]
    fn query_bytes<'py>(&self, py: Python<'py>, index: isize) -> PyResult<Bound<'py, PyBytes>> {
        let decoder = self.decoder();
        let (position, _) = finished_query(decoder.program(), index)?;
        let content = decoder.query_content_or_bound(position).ok_or_else(|| PyIndexError::new_err(format!("no content for the query at index {index}")))?;
        let content = content.map_err(|bound| labeling_bound_reached(py, bound))?;
        Ok(PyBytes::new(py, content.canonical_bytes()))
    }

    /// The canonical hash of the finished query at `index`, with the
    /// names as written. Index -1 is the last finished query.
    #[pyo3(signature = (index=-1))]
    fn written_query_hash(&self, py: Python<'_>, index: isize) -> PyResult<u128> {
        let (_, query) = finished_query(self.decoder().program(), index)?;
        written_query_hash(query).map(|hash| hash.0).map_err(|bound| labeling_bound_reached(py, bound))
    }

    /// For each part of the finished `RIGID_DET` form at `index`, in the
    /// order that the form lists its parts, `(path, position)`: the path of
    /// the part's output after the form's name, as the program spells it,
    /// and the position of the part in the form's canonical form. A part that
    /// ties with an earlier part has the earlier part's position. The Name
    /// that `step_tables` gives the part's output table is `slot <index of
    /// the part>`, and `arclog.rigid_slot_name` gives the Name of a read,
    /// which holds the position and the steps of the path after the part's
    /// own. Index -1 is the last finished query. `IndexError` where there is
    /// no finished query at `index`, `ValueError` where it is no `RIGID_DET`
    /// form.
    #[pyo3(signature = (index=-1))]
    fn rigid_parts(&self, index: isize) -> PyResult<Vec<(String, u32)>> {
        let decoder = self.decoder();
        let (position, _) = finished_query(decoder.program(), index)?;
        arclog::resolver::rigid_parts(decoder.program(), position, Registry::get()).map_err(PyValueError::new_err)
    }

    /// The program so far, as an arclog file.
    fn program_form(&self) -> String {
        arclog::write::write_synthesized(self.decoder().program(), Registry::get())
    }
}

/// Steps each of `decoders` by the token with the id at its index in `ids`,
/// on the thread pool with the GIL released, and gives what each step
/// gives, in the order of `decoders`: the pair that `Decoder.step` gives, or,
/// for a decode that refuses its token, the `Refusal` it would raise, or, for
/// a decode whose step panicked, a `Fault` whose message is the panic's. That
/// decode stays at its state before the step.
#[pyfunction]
#[pyo3(name = "step_batch")]
pub(crate) fn step_batch_py(py: Python<'_>, decoders: Vec<Bound<'_, PyDecoder>>, ids: Vec<u32>) -> PyResult<Vec<Py<PyAny>>> {
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
            Err(BatchFault::Panic(panic)) => Ok(Fault::new_err(panic).into_value(py).into_any()),
            Err(BatchFault::Effort(fault)) => Ok(effort_exhausted(py, fault).into_value(py).into_any()),
            Ok(result) => match decoder.step_result(result) {
                Ok(step) => Ok(step.into_pyobject(py)?.into_any().unbind()),
                Err(refusal) => Ok(refusal.into_value(py).into_any()),
            },
        })
        .collect()
}
