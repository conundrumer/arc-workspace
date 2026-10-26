//! A task session and the settings of its decodes, as Python gives them.

use std::sync::Arc;

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
}

/// A task session: the engine's state for one task, with the settings of its decodes.
#[pyclass(name = "Session", frozen, module = "arclog")]
pub(crate) struct PySession {
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
