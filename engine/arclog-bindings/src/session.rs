//! A task session and the settings of its decodes, as Python gives them.

use std::any::{Any, TypeId};
use std::sync::{Arc, Mutex};

use arclog::hash::StableHashMap;
use arclog::registry::Registry;
use arclog::session::{SessionBound, TaskSession, SESSION_BYTES};
use arclog::stream::{DecodeSettings, Vocabulary};
use pyo3::prelude::*;

use crate::decoder::PyDecoder;
use crate::settings::PyDecodeSettings;
use crate::task::{PyTask, TaskData};
use crate::vocabulary::PyVocabulary;

/// What the decodes of one session borrow.
pub(crate) struct SessionData {
    pub(crate) task: Arc<TaskData>,
    pub(crate) session: TaskSession,
    pub(crate) settings: DecodeSettings,
    /// The values derived from the task, one of each type, made on the first ask ([`SessionData::derived`]).
    derived: Mutex<StableHashMap<TypeId, Arc<dyn Any + Send + Sync>>>,
}

impl SessionData {
    /// The value of type `T` that `make` derives from the task, made on the
    /// first call for the session and shared after.
    pub(crate) fn derived<T: Any + Send + Sync>(&self, make: impl FnOnce() -> T) -> Arc<T> {
        let mut derived = self.derived.lock().expect("the derived values are not poisoned");
        let value = derived.entry(TypeId::of::<T>()).or_insert_with(|| Arc::new(make()));
        Arc::clone(value).downcast::<T>().expect("a value is kept under its own type")
    }
}

/// A task session: the engine's state for one task, with the settings of its decodes.
#[pyclass(name = "Session", frozen, module = "arclog")]
pub(crate) struct PySession {
    data: Arc<SessionData>,
    pub(crate) program_replay: Mutex<crate::study::ProgramReplay>,
}

impl PySession {
    pub(crate) fn program_settings(&self) -> DecodeSettings {
        self.data.settings
    }
}

#[pymethods]
impl PySession {
    #[new]
    #[pyo3(signature = (task, settings=None, *, session_bytes=None))]
    fn new(task: &PyTask, settings: Option<PyDecodeSettings>, session_bytes: Option<usize>) -> PyResult<PySession> {
        let settings = match settings {
            Some(settings) => settings.engine()?,
            None => DecodeSettings::synthesis(),
        };
        let session = TaskSession::new(SessionBound { bytes: session_bytes.unwrap_or(SESSION_BYTES) }, settings.caps);
        Ok(PySession { data: Arc::new(SessionData { task: Arc::clone(&task.data), session, settings, derived: Mutex::default() }), program_replay: Mutex::default() })
    }

    /// The result cache's entries, relations, counted bytes, indexes and
    /// index bytes, and the intern table's bytes.
    fn cache_stats(&self, py: Python<'_>) -> (usize, usize, usize, usize, usize, usize) {
        py.detach(|| {
            let (entries, relations, bytes, indexes, index_bytes) = self.data.session.results.stats();
            (entries, relations, bytes, indexes, index_bytes, self.data.session.intern.read().expect("an intern table outside a panic").bytes())
        })
    }

    /// What the walk memos count, as `TaskSession::memo_stats` gives it.
    fn memo_stats(&self, py: Python<'_>) -> ((usize, usize, usize, usize), (usize, usize)) {
        py.detach(|| self.data.session.memo_stats())
    }

    /// The bytes that the session's bound counts, as `TaskSession::ledger`
    /// gives them: the intern table's, the result cache's, and the reserved
    /// bytes of live buffers, such as those that a `CaseTables` holds.
    fn ledger_stats(&self, py: Python<'_>) -> (usize, usize, usize) {
        py.detach(|| self.data.session.ledger())
    }

    /// End a complete-program round-trip batch. No parsed/checkpoint state
    /// from the preceding case remains rooted by this session.
    fn reset_program_replay(&self,py:Python<'_>) {
        py.detach(|| {
            *self.program_replay.lock().expect("a program reader outside a panic")=crate::study::ProgramReplay::default();
        });
    }

    #[getter]
    fn settings(&self) -> PyDecodeSettings {
        PyDecodeSettings::of(&self.data.settings)
    }

    #[getter]
    fn vocabulary(&self) -> PyVocabulary {
        PyVocabulary::of(&Vocabulary::new(Registry::get(), &self.data.settings))
    }

    /// A decode of no token yet, judging the train pairs. With `evaluate`
    /// false, its steps evaluate nothing: they run the grammar, the checks
    /// and the static prune, and give the `Refusal` that a decode that
    /// evaluates gives for each of them, with no consistency test, so the
    /// decode never ends, and no liveness walk of a written `DET`
    /// (`arclog::decode::Decoder::without_evaluation`).
    #[pyo3(signature = (*, evaluate=true))]
    pub(crate) fn decoder(&self, evaluate: bool) -> PyResult<PyDecoder> {
        PyDecoder::open(&self.data, evaluate)
    }

    /// Steps each token of `ids` whose flag in `model` is 1, and none of the
    /// others, through a decode that evaluates nothing (`decoder` with
    /// `evaluate=False`), with the GIL released. Gives the index in `ids` of
    /// the first token that the decode refuses and the message of the
    /// `Refusal` that `Decoder.step` raises for it, or `None` where it takes
    /// each of them. Raises `ValueError` where `ids` and `model` differ in
    /// length, and `IndexError` for an id outside the vocabulary.
    fn check_stream(&self, py: Python<'_>, ids: Vec<u32>, model: Vec<u8>) -> PyResult<Option<(usize, String)>> {
        let mut decoder = PyDecoder::open(&self.data, false)?;
        let refused = py.detach(|| decoder.first_refusal(&ids, &model))?;
        Ok(refused.map(|(at, refusal)| (at, crate::decoder::refusal_message(&refusal))))
    }
}
