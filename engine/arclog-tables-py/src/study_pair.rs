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

#[path = "study_continuation.rs"]
mod continuation;
#[path = "study_component_tables.rs"]
mod component_tables;

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
    let (report, g, m) = py.detach(|| {
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
        (result.report.to_string(), g, m)
    });
    Ok((
        report,
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
    continuation::register(names)?;
    component_tables::register(names)?;
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

impl PyStudyTaskEvaluator {
    /// Catch native unwinds while the guard itself remains in scope, so a
    /// packing assertion becomes a Python exception without poisoning the
    /// task mutex. Failed case observations are discarded, never reused.
    fn with_cache<T>(&self,operation:&str,run:impl FnOnce(&mut study_pair::PairCache)->Result<T,String>)->Result<T,String> {
        let mut cache=self.cache.lock().map_err(|_|"task evaluator cache was poisoned; call finish_case to discard the failed case".to_owned())?;
        match std::panic::catch_unwind(std::panic::AssertUnwindSafe(||run(&mut cache))) {
            Ok(result)=>result,
            Err(payload)=>{
                let reason=arclog::decode::corpus::replay_panic(&*payload);
                cache.finish_case();
                self.session.results.clear();
                Err(format!("native {operation} panicked; failed case discarded: {reason}"))
            }
        }
    }
}

#[pymethods]
impl PyStudyTaskEvaluator {
    #[new]
    #[pyo3(signature=(task,tasks,settings,session_bytes=67108864,compact=true,observation_start=0))]
    fn new(py:Python<'_>,task:&str,tasks:&str,settings:arclog_bindings::PyDecodeSettings,session_bytes:usize,compact:bool,observation_start:u64)->PyResult<Self> {
        let settings=settings.engine()?;
        let read=py.detach(||read_task_files(Path::new(tasks),task)).map_err(PyValueError::new_err)?.0;
        let evidence=evidence_tables(&read,Registry::get());
        let mut cache=study_pair::PairCache::with_byte_bound(compact,session_bytes);
        cache.set_observation_start(observation_start);
        Ok(Self {task_name:task.into(),task:read,session:TaskSession::new(SessionBound {bytes:session_bytes},settings.caps),settings,evidence,cache:std::sync::Mutex::new(cache)})
    }

    /// Exact native ingestion in this task's session, with the GIL released.
    fn from_stream(&self,py:Python<'_>,ids:Vec<u32>,model:Vec<u8>)->PyResult<PyStudyProgram> {
        if ids.len()!=model.len() || model.iter().any(|f|*f>1) {return Err(PyValueError::new_err("expected equal-length ids/model and flags 0 or 1"));}
        let constructions=constructions()?;
        let program=py.detach(|| self.with_cache("from_stream",|cache| {
            // A new ingestion starts a case even if decoding subsequently faults.
            cache.finish_case();
            self.session.results.clear();
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
        })).map_err(PyValueError::new_err)?;
        Ok(PyStudyProgram {program,settings:self.settings})
    }

    /// Replay one exact logged identity; native certification and AST audit
    /// remain mandatory. No new sample can replace a historical mutant.
    fn replay(&self,py:Python<'_>,gold:&PyStudyProgram,identity_json:&str)->PyResult<(PyMutationPoint,PyValidMutant)> {
        if gold.settings!=self.settings {return Err(PyValueError::new_err("task evaluator and program settings differ"));}
        let identity:serde_json::Value=serde_json::from_str(identity_json).map_err(|e|PyValueError::new_err(e.to_string()))?;
        if identity["source"]["task"].as_str()!=Some(&self.task_name) {return Err(PyValueError::new_err("identity belongs to another task"));}
        let mutant=py.detach(|| {
            let spec=gold.program.replay_spec(&identity,Registry::get(),&self.settings)?;
            gold.program.construct(&spec).map_err(str::to_owned)
        }).map_err(PyValueError::new_err)?;
        Ok((PyMutationPoint {inner:mutant.point().clone()},PyValidMutant {inner:mutant,settings:self.settings}))
    }

    /// Release all native observations and result-cache entries at the end
    /// of a case, including a faulted case. Interned identifiers retain the
    /// task namespace; returned CaseTables own their packed buffers.
    fn finish_case(&self,py:Python<'_>) {
        py.detach(|| {
            let mut cache=self.cache.lock().unwrap_or_else(|poisoned|poisoned.into_inner());
            cache.finish_case();
            self.session.results.clear();
            self.cache.clear_poison();
        });
    }

    /// All export relation tables (plus evidence), in this evaluator's Ident
    /// namespace. Native evaluation is cached once per gold handle. Returns
    /// (status_json, CaseTables); stops and faults retain their native reason.
    fn gold_tables(&self,py:Python<'_>,gold:&PyStudyProgram)->PyResult<(String,PyCaseTables)> {
        if gold.settings!=self.settings {return Err(PyValueError::new_err("task evaluator and program settings differ"));}
        let constructions=constructions()?;
        let (report,columns)=py.detach(|| self.with_cache("gold_tables",|cache| {
            if cache.activate(&gold.program) {self.session.results.clear();}
            let (mut report,tables)=study_pair::gold_tables_cached(&gold.program,&self.task,&self.session,constructions,&self.settings,cache);
            let started=std::time::Instant::now();
            let columns=case_columns(&self.evidence,&tables,self.task.train.len(),None);
            report["native_columns_seconds"]=started.elapsed().as_secs_f64().into();
            Ok((report,columns))
        })).map_err(PyValueError::new_err)?;
        Ok((report.to_string(),PyCaseTables::of(py,self.task_name.clone(),"gold".into(),false,self.settings.projection_cap,&columns,None,None)?))
    }

    fn evaluate_pair(&self,py:Python<'_>,gold:&PyStudyProgram,point:&PyMutationPoint,mutant:&PyValidMutant)->PyResult<(String,PyCaseTables,PyCaseTables)> {
        if gold.settings!=self.settings || mutant.settings!=self.settings {return Err(PyValueError::new_err("task evaluator and program settings differ"));}
        let constructions=constructions()?;
        let (report,g,m)=py.detach(|| self.with_cache("evaluate_pair",|cache| {
            if cache.activate(&gold.program) {self.session.results.clear();}
            let mut result=study_pair::evaluate_pair_cached(&gold.program,&point.inner,&mutant.inner,&self.task,&self.session,constructions,&self.settings,cache);
            let started=std::time::Instant::now();
            let (g,m)=study_pair::pair_columns_cached(&self.evidence,&result,self.task.train.len(),cache);
            result.report["timings"]["native_columns"]=started.elapsed().as_secs_f64().into();
            result.report["cache"]=cache.stats();
            result.report["cache"]["session_result_bytes"]=self.session.results.bytes().into();
            // Drop the native pair tables before allocating their Python
            // buffers; the Python API returns only the report and columns.
            Ok((result.report.to_string(),g,m))
        })).map_err(PyValueError::new_err)?;
        Ok((report,PyCaseTables::of(py,self.task_name.clone(),"gold".into(),false,self.settings.projection_cap,&g,None,None)?,PyCaseTables::of(py,self.task_name.clone(),"mutant".into(),false,self.settings.projection_cap,&m,None,None)?))
    }
}
