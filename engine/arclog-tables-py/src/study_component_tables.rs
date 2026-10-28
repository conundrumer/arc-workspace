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
    let (report,g,m)=py.detach(|| {
        let cache=evaluator.cache.lock().expect("task evaluator cache is not poisoned");
        let result=study_pair::component_tables::evaluate_cached(&gold.program,&mutant.inner,&evaluator.task,
            &evaluator.session,constructions,&evaluator.settings,&cache,expected.as_ref())?;
        let g=case_columns(&evaluator.evidence,&result.gold,evaluator.task.train.len(),None);
        let m=case_columns(&evaluator.evidence,&result.mutant,evaluator.task.train.len(),None);
        Ok::<_,String>((result.report.to_string(),g,m))
    }).map_err(PyValueError::new_err)?;
    let pack=|side:&str,columns:&_|PyCaseTables::of(py,evaluator.task_name.clone(),side.into(),false,
        evaluator.settings.projection_cap,columns,None,None);
    Ok((report,pack("gold-components",&g)?,pack("mutant-components",&m)?))
}

pub(super) fn register(names:&Names<'_,'_>)->PyResult<()> {
    names.function(wrap_pyfunction!(study_component_tables,names.module())?)
}
