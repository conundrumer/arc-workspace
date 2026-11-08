//! Native component tables kept separate from OUT and DET decoding bindings.
use super::*;

#[pyfunction]
#[pyo3(signature=(evaluator,gold,mutant,expected_kept_json=None))]
fn study_component_tables(py:Python<'_>,evaluator:&PyStudyTaskEvaluator,gold:&PyStudyProgram,
    mutant:&PyValidMutant,expected_kept_json:Option<&str>)->PyResult<(String,PyCaseTables,PyCaseTables)> {
    if gold.settings!=evaluator.settings || mutant.settings!=evaluator.settings {
        return Err(PyValueError::new_err("task evaluator and program settings differ"));
    }
    let expected=expected_kept_json.map(serde_json::from_str::<serde_json::Value>).transpose()
        .map_err(|e|PyValueError::new_err(e.to_string()))?;
    let constructions=constructions()?;
    let mut result=py.detach(|| evaluator.with_cache("study_component_tables",|cache| {
        study_pair::component_tables::evaluate_cached(&gold.program,&mutant.inner,&evaluator.task,
            &evaluator.session,constructions,&evaluator.settings,cache,expected.as_ref())
    })).map_err(|error| study_error(py,error))?;
    arclog_bindings::check_effort(py)?;
    let (g,m)=pack_pair(py,&evaluator.task_name,["gold-components","mutant-components"],evaluator.settings.projection_cap,&evaluator.ident_namespace,[&gold.program,mutant.inner.program()],&mut result,|result,gold| {
        let materializer=Materializer::new(&evaluator.session,&result.limits);
        Ok(case_columns_in(&materializer,&evaluator.evidence,if gold {&result.gold} else {&result.mutant},evaluator.task.train.len(),None))
    })?;
    Ok((result.report.to_string(),g,m))
}

pub(super) fn register(names:&Names<'_,'_>)->PyResult<()> {
    names.function(wrap_pyfunction!(study_component_tables,names.module())?)
}
