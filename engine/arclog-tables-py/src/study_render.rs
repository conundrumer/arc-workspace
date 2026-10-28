//! Native renderer provenance API, alongside the table implementation it reads.
use arclog::registry::Registry;
use arclog_bindings::{Names, PyStudyProgram};
use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;

#[pyfunction]
fn study_frame_sources_json(py: Python<'_>, program: &PyStudyProgram) -> PyResult<String> {
    py.detach(|| {
        arclog_tables::tables::study_render::export(
            &program.program,
            Registry::get(),
            &program.settings,
        )
        .map(|v| v.to_string())
    })
    .map_err(PyValueError::new_err)
}

pub fn register(names: &Names<'_, '_>) -> PyResult<()> {
    names.function(wrap_pyfunction!(study_frame_sources_json, names.module())?)
}
