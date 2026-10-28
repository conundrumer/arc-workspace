//! A decode over a task in a session, as Python steps it: the mask, the
//! step, the requests of the form in progress, and the batch step.

use std::sync::{Arc, OnceLock};

use arclog::decode::{step_batch, Decoder, Projections, TokenMask};
use arclog::eval::pool::Pool;
use arclog::judge::attempts::Attempts;
use arclog::judge::candidates::{PairCandidates, Section};
use arclog::registry::Registry;
use arclog::stream::Token;
use arclog::task::Task;
use arclog::terms::Example;
use arclog::trace::render::{trace_form, TraceFormOptions};
use arclog::trace::{Stop, TopK};
use pyo3::exceptions::{PyIndexError, PyValueError};
use pyo3::prelude::*;
use pyo3::types::PyBytes;

use crate::constructions;
use crate::errors::{settled, Fault, Refusal};
use crate::results::{assigned, grid_rows, rows_view, PyAssigned, PyConsistency, PyProjection, PyProjections};
use crate::session::SessionData;
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
#[pyclass(name = "Decoder", module = "arclog")]
pub struct PyDecoder {
    decoder: Option<Decoder<'static>>,
    data: Arc<SessionData>,
}

impl PyDecoder {
    pub(crate) fn open(data: &Arc<SessionData>) -> PyResult<PyDecoder> {
        // SAFETY: the reference points into the `Arc`'s allocation, which the
        // returned `PyDecoder` keeps alive and never moves, and the decode
        // drops before the `Arc` does.
        let borrowed: &'static SessionData = unsafe { &*Arc::as_ptr(data) };
        let world = borrowed.task.world;
        let train: Arc<[PairCandidates<'static>]> = borrowed.task.judged.train.iter().map(|pair| PairCandidates::of(pair, Section::Train, world)).collect();
        let decoder = Decoder::new(&borrowed.task.task, &borrowed.session, Registry::get(), constructions()?, &borrowed.settings).judging(train);
        Ok(PyDecoder { decoder: Some(decoder), data: Arc::clone(data) })
    }

    /// The decode, for a crate that reads it as the engine's own value.
    pub fn decoder(&self) -> &Decoder<'static> {
        self.decoder.as_ref().expect("a decode outside a batch step")
    }

    /// The task that the decode runs on.
    pub fn task(&self) -> &Task {
        &self.data.task.task
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
            Ok(step) => Ok((self.forced_ids(&step.forced), step.consistency.as_ref().map(PyConsistency::of), step.rule_test.as_ref().map(PyConsistency::of))),
            Err(refusal) => Err(refusal_error(&refusal)),
        }
    }
}

/// The `Refusal` that Python raises for a decode's `refusal`.
fn refusal_error(refusal: &arclog::decode::Refusal) -> PyErr {
    Refusal::new_err(format!("{refusal:?}"))
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
    fn admissible<'py>(&self, py: Python<'py>) -> Bound<'py, PyBytes> {
        let decoder = self.decoder();
        PyBytes::new(py, &mask_bytes(&decoder.admissible(), decoder.vocabulary().len()))
    }

    /// Advances the decode by the token with id `id`, and gives the ids of
    /// the tokens the engine emits after it, with the consistency of the
    /// `OUT` form that the token ends, or `None`, and the consistency of the
    /// `RULE` clause that it ends under the rule tests, or `None`. Raises
    /// `Refusal` for a token outside the mask, and leaves the decode as it was.
    fn step(&mut self, id: u32) -> PyResult<StepResult> {
        let token = self.token(id)?;
        let result = self.decoder_mut().step(token);
        self.step_result(result)
    }

    /// The ids of the tokens the engine emits after the token with id `id`,
    /// as `step` gives them, with no consistency test, and leaves the decode
    /// as it was. Where `admissible` has computed the mask at this state,
    /// it reads them from the mask. Raises `Refusal` for a token outside the
    /// mask, as `step` does.
    fn forced(&self, id: u32) -> PyResult<Vec<u32>> {
        let token = self.token(id)?;
        self.decoder().forced(&token).map(|forced| self.forced_ids(&forced)).map_err(|refusal| refusal_error(&refusal))
    }

    /// A second decode from the same state, which shares this one's caches.
    pub(crate) fn fork(&self) -> PyDecoder {
        PyDecoder { decoder: Some(self.decoder().fork()), data: Arc::clone(&self.data) }
    }

    /// The rows of the sub-body of the clause in progress on `example`, or
    /// `None` where no clause is in progress. Raises `Fault` where the
    /// sub-body does not check or compile.
    #[pyo3(signature = (example=None))]
    fn rows(&mut self, py: Python<'_>, example: Option<u16>) -> PyResult<Option<PyAssigned>> {
        let observed = self.decoder_mut().observe_rows(example.map(Example::at));
        observed
            .map(|outcome| assigned(py, settled(outcome)?, |value| Ok(Py::new(py, rows_view(&value))?.into_any())))
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
                .map(|rows| Py::new(py, assigned(py, rows, |rows| Ok(rows.map(|relation| relation.len()).into_pyobject(py)?.into_any().unbind()))?))
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
            Err(panic) => Ok(Fault::new_err(panic).into_value(py).into_any()),
            Ok(result) => match decoder.step_result(result) {
                Ok(step) => Ok(step.into_pyobject(py)?.into_any().unbind()),
                Err(refusal) => Ok(refusal.into_value(py).into_any()),
            },
        })
        .collect()
}
