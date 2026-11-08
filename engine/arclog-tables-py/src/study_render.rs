//! Native renderer provenance API, alongside the table implementation it reads.
use arclog::registry::Registry;
use arclog_bindings::{refused, Names, PyStudyProgram, PyValidMutant};
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
    .map_err(refused)
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
#[pyo3(signature=(program, relation_source_names_json=None,*,source_program=None))]
fn study_program_export_json(py:Python<'_>,program:&PyStudyProgram,relation_source_names_json:Option<&str>,source_program:Option<&PyStudyProgram>)->PyResult<String> {
    py.detach(|| {
        let mut export=complete_export(&program.program,&program.settings)?;
        let source=source_program.unwrap_or(program);
        if source.settings!=program.settings {return Err("source and target program settings differ".into());}
        if let Some(names)=relation_source_names_json {
            let names=serde_json::from_str(names).map_err(|e|format!("invalid relation source names: {e}"))?;
            arclog::study::render_names::attach(&mut export,program.program.checked(),&program.settings,&names)?;
        }
        let source_export=if std::ptr::eq(source,program){export.clone()}else{source.program.render_json(Registry::get())?};
        export["correspondence"]=arclog::study::render_correspondence::export(&program.program,&source.program,Registry::get(),&program.settings,&export,&source_export,None,None)?;
        // Exact-path callers keep their existing fast/default proof. Only a
        // cross-representation path difference needs the additive certificate.
        if !std::ptr::eq(source,program) && program.program.decode_stream(Registry::get(),&program.settings)?.paths
            != source.program.decode_stream(Registry::get(),&source.settings)?.paths {
            export["correspondence"]["stream_path_certificate"]=program.program.representation_certificate(&source.program,Registry::get(),&program.settings)?;
        }
        Ok::<_,String>(export.to_string())
    })
        .map_err(refused)
}

#[pyfunction]
#[pyo3(signature=(mutant, relation_source_names_json=None,*,source_program=None))]
fn study_mutant_export_json(py:Python<'_>,mutant:&PyValidMutant,relation_source_names_json:Option<&str>,source_program:Option<&PyStudyProgram>)->PyResult<String> {
    py.detach(|| {
        let mut export=complete_export(mutant.inner.program(),&mutant.settings)?;
        if let Some(names)=relation_source_names_json {
            let names=serde_json::from_str(names).map_err(|e|format!("invalid relation source names: {e}"))?;
            arclog::study::render_names::attach(&mut export,mutant.inner.gold(),&mutant.settings,&names)?;
        }
        if let Some(source)=source_program {
            if source.settings!=mutant.settings {return Err("source and mutant program settings differ".into());}
            let source_export=source.program.render_json(Registry::get())?;
            export["correspondence"]=arclog::study::render_correspondence::export(mutant.inner.program(),&source.program,Registry::get(),&mutant.settings,&export,&source_export,Some(mutant.inner.gold()),Some(&mutant.inner.source_paths()))?;
        } else {
            export["correspondence"]=arclog::study::render_correspondence::export(mutant.inner.program(),mutant.inner.program(),Registry::get(),&mutant.settings,&export,&export,None,None)?;
        }
        export["mutation_identity"]=mutant.inner.identity();
        export["source_path_correspondence"]=mutant.inner.source_paths();
        Ok::<_,String>(export.to_string())
    }).map_err(refused)
}

pub fn register(names: &Names<'_, '_>) -> PyResult<()> {
    names.function(wrap_pyfunction!(study_frame_sources_json, names.module())?)?;
    names.function(wrap_pyfunction!(study_program_export_json, names.module())?)?;
    names.function(wrap_pyfunction!(study_mutant_export_json, names.module())?)
}
