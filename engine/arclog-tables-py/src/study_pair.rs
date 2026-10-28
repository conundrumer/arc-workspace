//! Study evaluation bindings, deliberately outside the streams bindings.
use crate::case_tables::PyCaseTables;
use arclog::decode::corpus::read_task_files;
use arclog::registry::Registry;
use arclog::session::{SessionBound, TaskSession};
use arclog_bindings::{Names, PyMutationPoint, PyStudyProgram, PyValidMutant, constructions};
use arclog_tables::columns::case_columns;
use arclog_tables::tables::{evidence_tables, study_pair};
use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;
use std::path::Path;

/// Returns (report_json, gold CaseTables, mutant CaseTables). The last
/// two native tables on each side are the completed body over its own DET
/// assignments and at gold FITS assignments. Earlier tables
/// retain the provenance and frame references used by the export format.
/// FITS keeps every gold assignment whose every model equals every train
/// output. Mutant OUT runs at those same assignments, with no re-selection.
/// Undefined OUT counts all expected cells as missing. For non-grid OUT,
/// count missing/ambiguous/wrong-frame cells and occupied extra positions.
#[pyfunction]
#[pyo3(signature = (gold, point, mutant, *, task, tasks, session_bytes=268435456))]
fn evaluate_pair(
    py: Python<'_>,
    gold: &PyStudyProgram,
    point: &PyMutationPoint,
    mutant: &PyValidMutant,
    task: &str,
    tasks: &str,
    session_bytes: usize,
) -> PyResult<(String, PyCaseTables, PyCaseTables)> {
    let constructions = constructions()?;
    let (read, _) = read_task_files(Path::new(tasks), task).map_err(PyValueError::new_err)?;
    let settings = gold.settings;
    let (result, g, m) = py.detach(|| {
        let session = TaskSession::new(
            SessionBound {
                bytes: session_bytes,
            },
            settings.caps,
        );
        let result = study_pair::evaluate_pair(
            &gold.program,
            &point.inner,
            &mutant.inner,
            &read,
            &session,
            constructions,
            &settings,
        );
        let evidence = evidence_tables(&read, Registry::get());
        let g = case_columns(&evidence, &result.gold, read.train.len(), None);
        let m = case_columns(&evidence, &result.mutant, read.train.len(), None);
        (result, g, m)
    });
    Ok((
        result.report.to_string(),
        PyCaseTables::of(
            py,
            task.into(),
            "gold".into(),
            false,
            settings.projection_cap,
            &g,
            None,
            None,
        )?,
        PyCaseTables::of(
            py,
            task.into(),
            "mutant".into(),
            false,
            settings.projection_cap,
            &m,
            None,
            None,
        )?,
    ))
}

pub(crate) fn register(names: &Names<'_, '_>) -> PyResult<()> {
    names.class::<PyStudyTaskEvaluator>()?;
    names.function(wrap_pyfunction!(evaluate_pair, names.module())?)
}

/// A task and its native evaluation state, reused across all cases/pairs.
/// The mutex is per task; different task evaluators run concurrently.
#[pyclass(name="StudyTaskEvaluator", frozen, module="arclog")]
struct PyStudyTaskEvaluator {
    task_name:String,
    task:arclog::task::Task,
    session:TaskSession,
    settings:arclog::stream::DecodeSettings,
    evidence:Vec<arclog_tables::tables::Table>,
    cache:std::sync::Mutex<study_pair::PairCache>,
}

#[pymethods]
impl PyStudyTaskEvaluator {
    #[new]
    #[pyo3(signature=(task,tasks,settings,session_bytes=67108864,compact=true))]
    fn new(py:Python<'_>,task:&str,tasks:&str,settings:arclog_bindings::PyDecodeSettings,session_bytes:usize,compact:bool)->PyResult<Self> {
        let settings=settings.engine()?;
        let read=py.detach(||read_task_files(Path::new(tasks),task)).map_err(PyValueError::new_err)?.0;
        let evidence=evidence_tables(&read,Registry::get());
        Ok(Self {task_name:task.into(),task:read,session:TaskSession::new(SessionBound {bytes:session_bytes},settings.caps),settings,evidence,cache:std::sync::Mutex::new(study_pair::PairCache::new(compact))})
    }

    /// Exact native ingestion in this task's session, with the GIL released.
    fn from_stream(&self,py:Python<'_>,ids:Vec<u32>,model:Vec<u8>)->PyResult<PyStudyProgram> {
        if ids.len()!=model.len() || model.iter().any(|f|*f>1) {return Err(PyValueError::new_err("expected equal-length ids/model and flags 0 or 1"));}
        let constructions=constructions()?;
        let program=py.detach(|| {
            let mut decoder=arclog::decode::Decoder::new(&self.task,&self.session,Registry::get(),constructions,&self.settings);
            let mut i=0;
            while i<ids.len() {
                if model[i]!=1 {return Err(format!("unexpected engine token at {i}"));}
                let token=decoder.vocabulary().token(ids[i]).ok_or_else(||format!("token outside vocabulary at {i}"))?.clone();
                let step=decoder.step_untested(token).map_err(|e|format!("replay at {i}: {e:?}"))?;
                let end=i+1+step.forced.len();
                if end>ids.len() || model[i+1..end].iter().any(|f|*f!=0) || step.forced.iter().zip(&ids[i+1..end]).any(|(t,id)|decoder.vocabulary().id(t)!=Some(*id)) {return Err(format!("engine echo mismatch at {i}"));}
                i=end;
            }
            arclog::study::StudyProgram::from_decoded(decoder.program().clone(),Registry::get())
        }).map_err(PyValueError::new_err)?;
        Ok(PyStudyProgram {program,settings:self.settings})
    }

    /// All export relation tables (plus evidence), in this evaluator's Ident
    /// namespace. Native evaluation is cached once per gold handle. Returns
    /// (status_json, CaseTables); stops and faults retain their native reason.
    fn gold_tables(&self,py:Python<'_>,gold:&PyStudyProgram)->PyResult<(String,PyCaseTables)> {
        if gold.settings!=self.settings {return Err(PyValueError::new_err("task evaluator and program settings differ"));}
        let constructions=constructions()?;
        let (report,columns)=py.detach(|| {
            let mut cache=self.cache.lock().expect("task evaluator cache is not poisoned");
            let (mut report,tables)=study_pair::gold_tables_cached(&gold.program,&self.task,&self.session,constructions,&self.settings,&mut cache);
            let started=std::time::Instant::now();
            let columns=case_columns(&self.evidence,&tables,self.task.train.len(),None);
            report["native_columns_seconds"]=started.elapsed().as_secs_f64().into();
            (report,columns)
        });
        Ok((report.to_string(),PyCaseTables::of(py,self.task_name.clone(),"gold".into(),false,self.settings.projection_cap,&columns,None,None)?))
    }

    fn evaluate_pair(&self,py:Python<'_>,gold:&PyStudyProgram,point:&PyMutationPoint,mutant:&PyValidMutant)->PyResult<(String,PyCaseTables,PyCaseTables)> {
        if gold.settings!=self.settings || mutant.settings!=self.settings {return Err(PyValueError::new_err("task evaluator and program settings differ"));}
        let constructions=constructions()?;
        let (result,g,m)=py.detach(|| {
            let mut cache=self.cache.lock().expect("task evaluator cache is not poisoned");
            let mut result=study_pair::evaluate_pair_cached(&gold.program,&point.inner,&mutant.inner,&self.task,&self.session,constructions,&self.settings,&mut cache);
            let started=std::time::Instant::now();
            let (g,m)=study_pair::pair_columns_cached(&self.evidence,&result,self.task.train.len(),&mut cache);
            result.report["timings"]["native_columns"]=started.elapsed().as_secs_f64().into();
            (result,g,m)
        });
        Ok((result.report.to_string(),PyCaseTables::of(py,self.task_name.clone(),"gold".into(),false,self.settings.projection_cap,&g,None,None)?,PyCaseTables::of(py,self.task_name.clone(),"mutant".into(),false,self.settings.projection_cap,&m,None,None)?))
    }
}
