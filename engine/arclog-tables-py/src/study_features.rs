//! Additive, feature-safe JSON exports; no task evaluation.
use arclog_bindings::{Names, PyStudyProgram, PyValidMutant};
use pyo3::prelude::*;
#[pyfunction]
fn study_feature_metadata_json(
    py: Python<'_>,
    program: &PyStudyProgram,
    point: Vec<u32>,
) -> PyResult<String> {
    let point = arclog::program::path::NodePath(
        point
            .into_iter()
            .map(arclog::program::path::PathStep)
            .collect(),
    );
    Ok(py
        .detach(|| {
            arclog_tables::study_features::export(
                &program.program,
                &point,
                arclog::registry::Registry::get(),
            )
        })
        .to_string())
}
#[pyfunction]
fn study_mutant_feature_metadata_json(py: Python<'_>, mutant: &PyValidMutant) -> PyResult<String> {
    Ok(py
        .detach(|| {
            arclog_tables::study_features::export(
                mutant.inner.program(),
                &mutant.inner.point().body,
                arclog::registry::Registry::get(),
            )
        })
        .to_string())
}
pub fn register(names: &Names<'_, '_>) -> PyResult<()> {
    names.function(wrap_pyfunction!(
        study_feature_metadata_json,
        names.module()
    )?)?;
    names.function(wrap_pyfunction!(
        study_mutant_feature_metadata_json,
        names.module()
    )?)?;
    Ok(())
}
