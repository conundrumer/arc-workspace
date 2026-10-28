//! Native renderer provenance API, alongside the table implementation it reads.
use arclog::registry::Registry;
use arclog_bindings::{Names, PyStudyProgram, PyValidMutant};
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

fn complete_export(program:&arclog::study::StudyProgram,settings:&arclog::stream::DecodeSettings)->Result<serde_json::Value,String> {
    let mut export=program.render_json(Registry::get())?;
    export["frame_sources"]=arclog_tables::tables::study_render::export(program,Registry::get(),settings)?;
    // This higher-level binding can combine the core checker with the table
    // provenance layer. Core arclog deliberately does not depend on tables.
    export["parts"]["types_frames"]="complete".into();
    export["frame_completeness_contract"]="all resolved types and native static frame provenance exported; native_unknown is an explicit native result; per-row extents come from supplied CaseTables".into();
    Ok(export)
}

#[pyfunction]
fn study_program_export_json(py:Python<'_>,program:&PyStudyProgram)->PyResult<String> {
    py.detach(||complete_export(&program.program,&program.settings).map(|v|v.to_string()))
        .map_err(PyValueError::new_err)
}

#[pyfunction]
fn study_mutant_export_json(py:Python<'_>,mutant:&PyValidMutant)->PyResult<String> {
    py.detach(|| {
        let mut export=complete_export(mutant.inner.program(),&mutant.settings)?;
        export["mutation_identity"]=mutant.inner.identity();
        export["source_path_correspondence"]=mutant.inner.source_paths();
        Ok::<_,String>(export.to_string())
    }).map_err(PyValueError::new_err)
}

pub fn register(names: &Names<'_, '_>) -> PyResult<()> {
    names.function(wrap_pyfunction!(study_frame_sources_json, names.module())?)?;
    names.function(wrap_pyfunction!(study_program_export_json, names.module())?)?;
    names.function(wrap_pyfunction!(study_mutant_export_json, names.module())?)
}
