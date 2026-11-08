//! The Python bindings of the arclog engine that the streams export runs:
//! the task, the session, the decoder, the vocabulary, the replay progress,
//! the streams of a corpus, the files of a solver's cases and the counters of
//! the engine's phases. [`register`] adds their names to the module that
//! `arclog-py` builds.
//!
//! Each class wraps a value of the core crate and restates no rule of it. A
//! task session owns the data that its decoders borrow, so a `PyDecoder`
//! holds the session's data beside the decode.
//!
//! The crate depends on the core crate and the lib's constructions, and on no
//! crate of the tables export: the reuse key of the streams export covers the
//! sources of this crate and of the crates it depends on, so a call from
//! here into the tables code would not compile. `arclog-tables-py` takes
//! these items of this crate, which are `pub`: [`Names`], [`PyDecodeSettings`],
//! [`PyReplayProgress`], [`Progress`], [`walk_corpus`], [`PyConsistencyKind`],
//! [`PyDecoder`], [`study_error`] and [`constructions`].

mod case_files;
mod corpus;
mod decoder;
mod engine_stats;
mod errors;
mod names;
mod results;
mod session;
mod settings;
mod streams;
mod study;
mod mutation;
mod task;
mod vocabulary;

pub use corpus::{walk_corpus, Progress, PyReplayProgress};
pub use decoder::PyDecoder;
pub use names::Names;
pub use results::PyConsistencyKind;
pub use settings::PyDecodeSettings;
pub use study::PyStudyProgram;
pub use errors::{budget_reached, faulted, labeling_bound_reached, refused, study_error, BudgetReached, CheckRefused, LabelingBoundReached, RecordedIdentityError};
pub use mutation::{PyMutationPoint, PyMutationSpec, PyValidMutant};

use arclog::eval::instance::Constructions;
use pyo3::exceptions::PyRuntimeError;
use pyo3::prelude::*;

/// The table of the lib's constructions, built once.
pub fn constructions() -> PyResult<&'static Constructions> {
    arclog_constructions::shared().map_err(PyRuntimeError::new_err)
}

/// Registers the classes, the exceptions and the functions of this crate.
pub fn register(names: &Names<'_, '_>) -> PyResult<()> {
    let module = names.module();
    names.class::<task::PyWorld>()?;
    names.class::<task::PyTask>()?;
    names.class::<PyDecodeSettings>()?;
    names.class::<vocabulary::PyVocabulary>()?;
    names.class::<session::PySession>()?;
    names.class::<study::PyStudyProgram>()?;
    names.class::<mutation::PyMutationPoint>()?;
    names.class::<mutation::PyMutationSpec>()?;
    names.class::<mutation::PyValidMutant>()?;
    names.class::<decoder::PyDecoder>()?;
    names.class::<results::PyStopKind>()?;
    names.class::<PyConsistencyKind>()?;
    names.class::<results::PyConsistency>()?;
    names.class::<results::PyValueKind>()?;
    names.class::<results::PyRowsView>()?;
    names.class::<results::PyAssigned>()?;
    names.class::<results::PyProjection>()?;
    names.class::<results::PyProjections>()?;
    names.class::<streams::PyCaseStream>()?;
    names.class::<case_files::PyCaseFiles>()?;
    names.value("Refusal", module.py().get_type::<errors::Refusal>().into_any())?;
    names.value("CheckRefused", module.py().get_type::<errors::CheckRefused>().into_any())?;
    names.value("LabelingBoundReached", module.py().get_type::<errors::LabelingBoundReached>().into_any())?;
    names.value("RecordedIdentityError", module.py().get_type::<errors::RecordedIdentityError>().into_any())?;
    names.value("Fault", module.py().get_type::<errors::Fault>().into_any())?;
    names.value("BudgetReached", module.py().get_type::<errors::BudgetReached>().into_any())?;
    names.function(wrap_pyfunction!(decoder::step_batch_py, module)?)?;
    names.function(wrap_pyfunction!(engine_stats::engine_stats, module)?)?;
    names.function(wrap_pyfunction!(engine_stats::request_stats, module)?)?;
    names.function(wrap_pyfunction!(engine_stats::work_total, module)?)?;
    names.function(wrap_pyfunction!(engine_stats::registry_text, module)?)?;
    names.class::<PyReplayProgress>()?;
    names.function(wrap_pyfunction!(streams::corpus_streams, module)?)?;
    names.function(wrap_pyfunction!(study::empty_gold_json, module)?)?;
    names.function(wrap_pyfunction!(study::rigid_slot_name, module)?)?;
    names.function(wrap_pyfunction!(case_files::case_files, module)?)
}
