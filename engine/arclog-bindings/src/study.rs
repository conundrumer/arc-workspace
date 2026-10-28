//! Thin Python handles for the engine's study ASTs.

use arclog::registry::Registry;
use arclog::stream::DecodeSettings;
use arclog::study::StudyProgram;
use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;

use crate::mutation::{PyMutationPoint, PyMutationSpec, PyValidMutant};
use crate::session::PySession;
use crate::settings::PyDecodeSettings;
use crate::vocabulary::PyVocabulary;

/// A grammar/binder reader for this session's immutable settings. Each
/// returned AST still goes through the whole-program checks below.
#[derive(Default)]
pub(crate) struct ProgramReplay {
    reader: Option<arclog::decode::program_read::ProgramReader<'static>>,
}

/// A checked, standalone gold program through OUT. Mutations address AST
/// clauses; streams are input/output representations only.
#[pyclass(name = "StudyProgram", frozen, module = "arclog")]
#[derive(Clone)]
pub struct PyStudyProgram {
    pub program: StudyProgram,
    pub settings: DecodeSettings,
}

type Stream = (Vec<u32>, Vec<u8>, Vec<Vec<u32>>);

#[pymethods]
impl PyStudyProgram {
    #[staticmethod]
    fn mutation_policy() -> &'static str {
        "complete-domain-without-replacement-v5"
    }
    /// Read standalone case sexp, preserving source column/variable names.
    #[staticmethod]
    #[pyo3(signature = (text, settings=None))]
    fn from_sexp(py: Python<'_>, text: &str, settings: Option<PyDecodeSettings>) -> PyResult<Self> {
        let settings = settings
            .map(|s| s.engine())
            .transpose()?
            .unwrap_or_else(DecodeSettings::synthesis);
        let program = py
            .detach(|| StudyProgram::from_sexp(text, Registry::get()))
            .map_err(PyValueError::new_err)?;
        program
            .decode_stream(Registry::get(), &settings)
            .map_err(PyValueError::new_err)?;
        Ok(Self { program, settings })
    }

    /// Parse a complete stream with the engine grammar/binder and exact
    /// echoes, then check the entire AST. No prefix completion search or OUT
    /// evaluation is needed when the complete program is supplied.
    #[staticmethod]
    fn from_stream(
        py: Python<'_>,
        session: &PySession,
        ids: Vec<u32>,
        model: Vec<u8>,
    ) -> PyResult<Self> {
        let settings = session.program_settings();
        let program = py
            .detach(|| {
                let mut cached = session
                    .program_replay
                    .lock()
                    .expect("a program reader outside a panic");
                let reader = cached.reader.get_or_insert_with(|| {
                    arclog::decode::program_read::ProgramReader::new(Registry::get(), settings)
                });
                let ast = reader.read(&ids, &model)?;
                let program = StudyProgram::from_decoded(ast, Registry::get())?;
                let written = program.decode_stream(Registry::get(), &settings)?;
                if written.ids != ids || written.model != model {
                    return Err(
                        "parsed program does not reproduce its exact input stream".to_owned()
                    );
                }
                Ok(program)
            })
            .map_err(PyValueError::new_err)?;
        Ok(Self { program, settings })
    }

    /// Structured engine evidence. JSON schema/capabilities are versioned.
    fn render_json(&self, py: Python<'_>) -> PyResult<String> {
        py.detach(|| self.program.render_json(Registry::get()).map(|v|v.to_string()))
            .map_err(PyValueError::new_err)
    }

    fn sexp(&self) -> String {
        self.program.sexp(Registry::get())
    }

    fn program_form(&self) -> String {
        self.sexp()
    }

    /// Every gold clause, addressed by its AST, including INIT key/inputs.
    fn points(&self) -> Vec<PyMutationPoint> {
        self.program
            .mutation_points()
            .into_iter()
            .map(|inner| PyMutationPoint { inner })
            .collect()
    }

    /// Select unique complete K-edit assignments from the valid domain.
    /// Binding exclusions are solved before any spec can be sampled.
    #[pyo3(signature = (point, k, count, seed, *, source_revision, task, case, operation="mixed"))]
    fn draw_specs(
        &self,
        py: Python<'_>,
        point: &PyMutationPoint,
        k: usize,
        count: usize,
        seed: u64,
        source_revision: String,
        task: String,
        case: String,
        operation: &str,
    ) -> PyResult<(Vec<PyMutationSpec>, String)> {
        if source_revision.is_empty() || task.is_empty() || case.is_empty() {
            return Err(PyValueError::new_err(
                "source revision, task and case must be nonempty",
            ));
        }
        let origin = arclog::mutation::Source {
            revision: source_revision,
            task,
            case,
        };
        let (specs, stats) = py
            .detach(|| {
                self.program.draw_specs(
                    &point.inner,
                    k,
                    count,
                    seed,
                    operation,
                    origin,
                    &self.settings,
                    Registry::get(),
                )
            })
            .map_err(PyValueError::new_err)?;
        Ok((
            specs
                .into_iter()
                .map(|inner| PyMutationSpec { inner })
                .collect(),
            stats.json().to_string(),
        ))
    }

    /// Compare draw-kind counts before filters, using the legacy traversal
    /// and the production fair traversal over the same real AST/domain.
    #[pyo3(signature = (point, k, count, seed, *, source_revision, task, case, operation="mixed"))]
    fn audit_draw_order(
        &self,
        py: Python<'_>,
        point: &PyMutationPoint,
        k: usize,
        count: usize,
        seed: u64,
        source_revision: String,
        task: String,
        case: String,
        operation: &str,
    ) -> PyResult<String> {
        let origin = arclog::mutation::Source {
            revision: source_revision,
            task,
            case,
        };
        py.detach(|| {
            self.program
                .audit_draw_order(
                    &point.inner,
                    k,
                    count,
                    seed,
                    operation,
                    origin,
                    &self.settings,
                    Registry::get(),
                )
                .map(|v| v.to_string())
        })
        .map_err(PyValueError::new_err)
    }

    fn construct(&self, spec: &PyMutationSpec) -> PyResult<PyValidMutant> {
        let inner = self
            .program
            .construct(&spec.inner)
            .map_err(PyValueError::new_err)?;
        Ok(PyValidMutant {
            inner,
            settings: self.settings,
        })
    }

    /// (ids, model flags, AST path per token), under this handle's settings.
    fn decode_stream(&self) -> PyResult<Stream> {
        let stream = self
            .program
            .decode_stream(Registry::get(), &self.settings)
            .map_err(PyValueError::new_err)?;
        Ok((
            stream.ids,
            stream.model,
            stream
                .paths
                .into_iter()
                .map(|p| p.0.iter().map(|step| step.0).collect())
                .collect(),
        ))
    }

    #[getter]
    fn vocabulary(&self) -> PyVocabulary {
        PyVocabulary::of(&arclog::stream::Vocabulary::new(
            Registry::get(),
            &self.settings,
        ))
    }
}
