//! Separate bounded execution evidence for structured judge renderers.
use super::*;

#[pyfunction]
#[pyo3(signature=(evaluator,gold,mutant,expected_kept_json=None))]
fn study_continuation(py:Python<'_>,evaluator:&PyStudyTaskEvaluator,gold:&PyStudyProgram,
    mutant:&PyValidMutant,expected_kept_json:Option<&str>)->PyResult<(String,PyCaseTables,PyCaseTables)> {
    if gold.settings!=evaluator.settings || mutant.settings!=evaluator.settings {
        return Err(PyValueError::new_err("task evaluator and program settings differ"));
    }
    let expected=expected_kept_json.map(serde_json::from_str::<serde_json::Value>).transpose()
        .map_err(|e|PyValueError::new_err(e.to_string()))?;
    let constructions=constructions()?;
    let mut result=py.detach(|| evaluator.with_cache("study_continuation",|cache| {
        study_pair::continuation::evaluate(&gold.program,&mutant.inner,&evaluator.task,
            &evaluator.judged,&evaluator.session,constructions,&evaluator.settings,cache,expected.as_ref())
    })).map_err(|error| study_error(py,error))?;
    let (g,m)=pack_pair(py,&evaluator.task_name,["gold-continuation","mutant-continuation"],evaluator.settings.projection_cap,&evaluator.ident_namespace,[&gold.program,mutant.inner.program()],&mut result,|result,gold| {
        let materializer=Materializer::new(&evaluator.session,&result.limits);
        Ok(case_columns_in(&materializer,&evaluator.evidence,if gold {&result.gold} else {&result.mutant},evaluator.task.train.len(),None))
    })?;
    Ok((result.report.to_string(),g,m))
}

pub(super) fn register(names:&Names<'_,'_>)->PyResult<()> {
    names.function(wrap_pyfunction!(study_continuation,names.module())?)
}
