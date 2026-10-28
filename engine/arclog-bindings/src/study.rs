//! Thin Python handles for the engine's study ASTs.

use arclog::registry::Registry;
use arclog::stream::DecodeSettings;
use arclog::study::StudyProgram;
use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;

use crate::decoder::PyDecoder;
use crate::mutation::{PyMutationPoint, PyMutationSpec, PyValidMutant};
use crate::session::PySession;
use crate::settings::PyDecodeSettings;
use crate::vocabulary::PyVocabulary;

/// Only the last successful replay's checkpoints are retained. Each is at
/// a model-step boundary after its engine echoes have been verified. At
/// most 64 decoder forks share the session's persistent engine structures;
/// this is not a growing corpus-wide trie or a cache of rewritten fields.
#[derive(Default)]
pub(crate) struct ProgramReplay {
    ids: Vec<u32>,
    model: Vec<u8>,
    checkpoints: Vec<(usize, PyDecoder)>,
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
        "complete-domain-without-replacement-v3"
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

    /// Replay an exact exported stream, then take its AST directly. Engine
    /// echoes must match; no token is repaired, dropped or guessed.
    #[staticmethod]
    fn from_stream(session: &PySession, ids: Vec<u32>, model: Vec<u8>) -> PyResult<Self> {
        if ids.len() != model.len() || model.iter().any(|&flag| flag > 1) {
            return Err(PyValueError::new_err(
                "expected equal-length ids/model arrays and flags 0 or 1",
            ));
        }
        let mut cached = session
            .program_replay
            .lock()
            .expect("a replay cache outside a panic");
        let common = ids
            .iter()
            .zip(&model)
            .zip(cached.ids.iter().zip(&cached.model))
            .take_while(|(a, b)| a == b)
            .count();
        let mut checkpoints: Vec<_> = cached
            .checkpoints
            .iter()
            .filter(|(index, _)| *index <= common)
            .map(|(index, decoder)| (*index, decoder.fork()))
            .collect();
        let (mut index, mut decoder) = match checkpoints.last() {
            Some((index, decoder)) => (*index, decoder.fork()),
            None => (0, session.decoder()?),
        };
        // Bound retained forks independently of program length.
        let stride = ids.len().div_ceil(63).max(32);
        let mut next_checkpoint = index + stride;
        while index < ids.len() {
            if model[index] != 1 {
                return Err(PyValueError::new_err(format!(
                    "unexpected engine token at {index}"
                )));
            }
            let forced = decoder.step_for_program(ids[index])?;
            let end = index + 1 + forced.len();
            if end > ids.len()
                || ids[index + 1..end] != forced
                || model[index + 1..end].iter().any(|&flag| flag != 0)
            {
                return Err(PyValueError::new_err(format!(
                    "engine echo mismatch after model token {index}"
                )));
            }
            index = end;
            if index >= next_checkpoint {
                checkpoints.push((index, decoder.fork()));
                next_checkpoint = index + stride;
            }
        }
        let settings = decoder.decoder().settings().clone();
        let program =
            StudyProgram::from_decoded(decoder.decoder().program().clone(), Registry::get())
                .map_err(PyValueError::new_err)?;
        program
            .decode_stream(Registry::get(), &settings)
            .map_err(PyValueError::new_err)?;
        // Commit only after the entire replay and full AST check pass.
        // A refusal leaves the previous successful prefix cache intact.
        if checkpoints.len() > 64 {
            let keep_every = checkpoints.len().div_ceil(64);
            checkpoints = checkpoints.into_iter().step_by(keep_every).collect();
        }
        *cached = ProgramReplay {
            ids,
            model,
            checkpoints,
        };
        Ok(Self { program, settings })
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
