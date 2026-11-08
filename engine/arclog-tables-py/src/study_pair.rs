//! Study evaluation bindings, deliberately outside the streams bindings.
use crate::case_tables::PyCaseTables;
use arclog::decode::corpus::read_task_files;
use arclog::registry::Registry;
use arclog::session::{SessionBound, TaskSession};
use arclog_bindings::{Names, PyMutationPoint, PyStudyProgram, PyValidMutant, constructions};
use arclog_tables::columns::{case_columns_held_in,case_columns_in};
use arclog::eval::join::Materializer;
use arclog_tables::identity::identify;
use arclog_tables::tables::{evidence_tables, study_pair};
use study_pair::STUDY_SESSION_BYTES;
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
/// FITS compares each train's distinct model output set with the native
/// closed-world candidates, including rule and tiebreak alternatives.
/// Per-model equality/differences still compare the given output only.
/// Mutant OUT runs at those same assignments, with no re-selection.
/// Undefined OUT counts all expected cells as missing. For non-grid OUT,
/// count missing/ambiguous/wrong-frame cells and occupied extra positions.
#[pyfunction]
#[pyo3(signature = (gold, point, mutant, *, task, tasks, session_bytes=None))]
fn evaluate_pair(
    py: Python<'_>,
    gold: &PyStudyProgram,
    point: &PyMutationPoint,
    mutant: &PyValidMutant,
    task: &str,
    tasks: &str,
    session_bytes: Option<usize>,
) -> PyResult<(String, PyCaseTables, PyCaseTables)> {
    let constructions = constructions()?;
    let (read, judged) = read_task_files(Path::new(tasks), task).map_err(PyValueError::new_err)?;
    let settings = gold.settings;
    let session_bytes=session_bytes.unwrap_or(STUDY_SESSION_BYTES);
    let session=TaskSession::new(SessionBound {bytes:session_bytes},settings.caps);
    let mut result=py.detach(||study_pair::evaluate_pair(
        &gold.program,&point.inner,&mutant.inner,&read,&judged,&session,constructions,&settings));
    let evidence=evidence_tables(&read,Registry::get());
    let (g,m)=pack_pair(py,task,["gold","mutant"],settings.projection_cap,&study_pair::table_transport_ref(),[&gold.program,mutant.inner.program()],&mut result,|result,gold| {
        let materializer=Materializer::new(&session,&result.limits);
        Ok(case_columns_in(&materializer,&evidence,if gold {&result.gold} else {&result.mutant},read.train.len(),None))
    })?;
    Ok((result.report.to_string(),g,m))
}

pub(crate) fn register(names: &Names<'_, '_>) -> PyResult<()> {
    names.module().add("STUDY_SESSION_BYTES",STUDY_SESSION_BYTES)?;
    names.module().add("SESSION_BYTES",arclog::session::SESSION_BYTES)?;
    names.class::<PyStudyTaskEvaluator>()?;
    names.class::<PyStudyPrefixUniverse>()?;
    continuation::register(names)?;
    component_tables::register(names)?;
    names.function(wrap_pyfunction!(evaluate_pair, names.module())?)
}

/// A task and its native evaluation state, reused across all cases/pairs.
/// The mutex is per task; different task evaluators run concurrently.
#[pyclass(name="StudyTaskEvaluator", frozen, module="arclog")]
struct PyStudyTaskEvaluator {
    task_name:String,
    ident_namespace:String,
    task:arclog::task::Task,
    judged:arclog::task::JudgedTask,
    session:std::sync::Arc<TaskSession>,
    settings:arclog::stream::DecodeSettings,
    evidence:Vec<arclog_tables::tables::Table>,
    cache:std::sync::Mutex<study_pair::PairCache>,
}

/// Opaque common universe. Parent values and their native Ident namespace
/// retain the task session until the receipt is closed or its last owner drops.
#[pyclass(name="StudyPrefixUniverse", frozen, module="arclog")]
struct PyStudyPrefixUniverse {
    inner:std::sync::Mutex<Option<study_pair::prefix::Universe>>,
    report:serde_json::Value,
    session:std::sync::Arc<TaskSession>,
    ident_namespace:String,
}

#[pymethods]
impl PyStudyPrefixUniverse {
    fn report_json(&self)->String {self.report.to_string()}
    fn close(&self) {self.inner.lock().unwrap_or_else(|p|p.into_inner()).take();}
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
    #[pyo3(signature=(task,tasks,settings,session_bytes=None,compact=true,observation_start=0,form_cache=true,form_cache_bytes=None))]
    fn new(py:Python<'_>,task:&str,tasks:&str,settings:arclog_bindings::PyDecodeSettings,session_bytes:Option<usize>,compact:bool,observation_start:u64,form_cache:bool,form_cache_bytes:Option<usize>)->PyResult<Self> {
        let settings=settings.engine()?;
        let session_bytes=session_bytes.unwrap_or(STUDY_SESSION_BYTES);
        let (read,judged)=py.detach(||read_task_files(Path::new(tasks),task)).map_err(PyValueError::new_err)?;
        let evidence=evidence_tables(&read,Registry::get());
        let mut cache=study_pair::PairCache::with_byte_bound(compact,session_bytes);
        cache.set_observation_start(observation_start);
        cache.set_form_cache(form_cache);
        if let Some(bytes)=form_cache_bytes {cache.set_form_cache_bytes(bytes);}
        Ok(Self {task_name:task.into(),ident_namespace:study_pair::table_transport_ref(),task:read,judged,session:std::sync::Arc::new(TaskSession::new(SessionBound {bytes:session_bytes},settings.caps)),settings,evidence,cache:std::sync::Mutex::new(cache)})
    }

    /// The immutable cap used by this actual task session.
    #[getter]
    fn assignment_cap(&self)->u64 {self.session.caps.assignments}

    /// Open the independently checked frontier before this candidate clause.
    /// No caller assignments, later OUT/FITS or target DET value are admitted.
    #[pyo3(signature=(program,body_path,*,max_assignments=None))]
    fn prefix_universe(&self,py:Python<'_>,program:&PyStudyProgram,body_path:Vec<u32>,max_assignments:Option<u64>)
        ->PyResult<(String,PyStudyPrefixUniverse)> {
        if program.settings!=self.settings {return Err(PyValueError::new_err("task evaluator and program settings differ"));}
        let assignment_cap=self.session.caps.assignments;
        if max_assignments.is_some_and(|requested|requested!=assignment_cap) {
            return Err(PyValueError::new_err(format!("max_assignments must equal the native session assignment cap {assignment_cap}; omit it to use the session setting")));
        }
        let point=arclog::program::path::NodePath(body_path.into_iter().map(arclog::program::path::PathStep).collect());
        let constructions=constructions()?;
        let opened=py.detach(||self.with_cache("prefix_universe",|cache| {
            if cache.activate(&program.program) {self.session.results.clear();}
            Ok(study_pair::prefix::open(&program.program,&point,&self.task,&self.session,constructions,&self.settings,assignment_cap))
        })).map_err(PyValueError::new_err)?;
        let (inner,mut report)=match opened {
            Ok(universe)=>{let report=universe.report.clone();(Some(universe),report)},
            Err(reason)=>{let mut report=reason.report();
                report["source_program_sexp"]=program.program.sexp(Registry::get()).into();
                report["body_path"]=arclog::mutation::path_json(&point);
                (None,report)},
        };
        report["task"]=self.task_name.clone().into();
        report["ident_namespace"]=self.ident_namespace.clone().into();
        Ok((report.to_string(),PyStudyPrefixUniverse {inner:std::sync::Mutex::new(inner),report,
            session:std::sync::Arc::clone(&self.session),ident_namespace:self.ident_namespace.clone()}))
    }

    /// Recorded edit admission under this opaque universe's carried prior DETs.
    /// No new domain walk, table acquisition or OUT/FITS search is performed.
    fn rehydrate_prefix_identity(&self,py:Python<'_>,universe:&PyStudyPrefixUniverse,identity_json:&str,
        stored_program:&PyStudyProgram)->PyResult<(PyValidMutant,String)> {
        if !std::sync::Arc::ptr_eq(&self.session,&universe.session) || self.ident_namespace!=universe.ident_namespace {
            return Err(arclog_bindings::RecordedIdentityError::new_err(("prefix_scope","prefix universe belongs to another task session")));
        }
        if stored_program.settings!=self.settings {
            return Err(arclog_bindings::RecordedIdentityError::new_err(("settings","prefix evaluator and stored program settings differ")));
        }
        let identity=arclog::study::render::parse_json(identity_json)
            .map_err(|e|arclog_bindings::RecordedIdentityError::new_err(("identity_admission",e)))?;
        let (inner,mut certificate)=py.detach(|| {
            let guard=universe.inner.lock().map_err(|_|arclog::mutation::RecordedIdentityFailure{
                stage:"prefix_scope",message:"prefix receipt was poisoned".into()})?;
            let inner=guard.as_ref().ok_or_else(||arclog::mutation::RecordedIdentityFailure{
                stage:"prefix_scope",message:"prefix receipt is unavailable or closed".into()})?;
            inner.rehydrate_recorded_identity(&identity,&stored_program.program,Registry::get(),&self.settings)
        }).map_err(|error|arclog_bindings::RecordedIdentityError::new_err((error.stage,error.message)))?;
        certificate["ident_namespace"]=self.ident_namespace.clone().into();
        certificate["task"]=self.task_name.clone().into();
        certificate["settings"]=format!("{:?}",self.settings).into();
        Ok((PyValidMutant{inner,settings:self.settings},certificate.to_string()))
    }

    /// Materialize canonical full native rows against this exact parent receipt.
    #[pyo3(signature=(universe,*,mutant=None,include_available=true))]
    fn prefix_tables(&self,py:Python<'_>,universe:&PyStudyPrefixUniverse,mutant:Option<&PyValidMutant>,include_available:bool)
        ->PyResult<(String,PyCaseTables)> {
        if !std::sync::Arc::ptr_eq(&self.session,&universe.session) || self.ident_namespace!=universe.ident_namespace {
            return Err(PyValueError::new_err("prefix universe belongs to another task session"));
        }
        if mutant.is_some_and(|m|m.settings!=self.settings) {return Err(PyValueError::new_err("candidate and evaluator settings differ"));}
        let constructions=constructions()?;
        let (report,columns)=py.detach(||self.with_cache("prefix_tables",|_| {
            let mut guard=universe.inner.lock().map_err(|_|"prefix receipt was poisoned")?;
            let inner=guard.as_mut().ok_or("prefix receipt unavailable or closed")?;
            let mut result=study_pair::prefix::acquire(inner,mutant.map(|m|&m.inner),&self.task,&self.session,
                constructions,&self.settings,include_available)?;
            result.report["task"]=self.task_name.clone().into();
            let materializer=Materializer::new(&self.session,&result.limits);
            let pack_start=arclog::clock::Stopwatch::start();
            let columns=case_columns_in(&materializer,&self.evidence,&result.tables,self.task.train.len(),None);
            result.report["timings"]["packing_seconds"]=pack_start.elapsed().seconds().into();
            result.report["packed_value_cells"]=columns.values.len().into();
            result.report["packed_entry_count"]=columns.entries.table.len().into();
            packing_status(&mut result.report,[&columns]);
            let maps_complete=prefix_packed_map(&mut result.report,&columns);
            let side=if mutant.is_some(){"mutant"}else{"gold"};
            result.report["packed_correspondence"]=table_binding(&columns,side,&result.report,&self.ident_namespace);
            result.report["packed_correspondence"]["query_prefix"]=result.report["query_prefix"].clone();
            result.report["packed_correspondence"]["program_sexp"]=result.report["query_prefix"]["program_sexp"].clone();
            result.report["packed_correspondence"]["universe_ref"]=result.report["universe_ref"].clone();
            let body=result.report["body_table"].as_u64();
            if let Some(tables)=result.report["packed_correspondence"]["tables"].as_array_mut() {for table in tables {
                table["report_roles"]=serde_json::json!(if table["table"].as_u64()==body {vec!["prefix_body"]}
                    else if table["table"].as_u64().is_some_and(|i|i>=2) {vec!["prefix_available"]}else{Vec::<&str>::new()});
            }}
            result.report["packed_table_count"]=columns.tables.form.len().into();
            let packing_complete=columns.packing_stop().is_none() && columns.tables.form.len()==result.tables.len()+2;
            result.report["packing_complete"]=packing_complete.into();
            result.report["complete"]=(packing_complete && maps_complete && result.report["status"]=="complete"
                && result.report["table_coverage"].as_array().is_some_and(|rows|rows.iter().all(|r|r["complete"]==true))).into();
            Ok((result.report,columns))
        })).map_err(PyValueError::new_err)?;
        let side=if mutant.is_some(){"mutant"}else{"gold"};
        Ok((report.to_string(),PyCaseTables::of(py,self.task_name.clone(),side.into(),false,self.settings.projection_cap,columns,None,None)?))
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

    /// Release the walks of tables that `gold_tables` keeps from one program
    /// to the next. A case's end does not release them; the evaluator's end does.
    fn clear_form_cache(&self,py:Python<'_>) {
        py.detach(|| self.cache.lock().unwrap_or_else(|poisoned|poisoned.into_inner()).clear_form_cache());
    }

    /// All export relation tables (plus evidence), in this evaluator's Ident
    /// namespace, as the decode gives them: a table over the projection cap gives
    /// its entries' counts and its projections in place of its rows. With
    /// held_rows, each entry gives its rows as its evaluation holds them: a
    /// product of parts over the projection cap gives its count and its parts,
    /// and every other entry its rows. Native evaluation is cached once per gold
    /// handle. Returns (status_json, CaseTables); stops and faults retain their
    /// native reason. The rows do not depend on machine load: no clock applies,
    /// and a table stops at caps that its program alone decides. The session's
    /// byte bound (`study_pair::TABLE_BYTES` for the evaluation) only makes the
    /// session evict its caches: no table is cut at it.
    ///
    /// With `form`, the index of a top-level form of the program, the result
    /// holds the tables of that form alone, with no evidence, and the rows that
    /// the full result gives them. The call takes no part in the active case:
    /// it evaluates from the first form that differs from the program of the
    /// last call without `form` through `form` (`study_pair::form_tables`), so
    /// a caller evaluates a program in full first, and then each program made
    /// from it by a change to one form.
    #[pyo3(signature=(gold,*,held_rows=false,form=None))]
    fn gold_tables(&self,py:Python<'_>,gold:&PyStudyProgram,held_rows:bool,form:Option<usize>)->PyResult<(String,PyCaseTables)> {
        if gold.settings!=self.settings {return Err(PyValueError::new_err("task evaluator and program settings differ"));}
        let constructions=constructions()?;
        let (report,columns)=py.detach(|| self.with_cache("gold_tables",|cache| {
            let limits=study_pair::table_limits(&self.settings);
            let (mut report,tables,evidence)=match form {
                None=>{
                    if cache.activate(&gold.program) {self.session.results.clear();}
                    let (report,tables)=study_pair::gold_tables_cached_in(&gold.program,&self.task,&self.session,constructions,&self.settings,cache,&limits);
                    (report,tables,&self.evidence[..])
                }
                Some(form)=>{
                    let (report,tables)=study_pair::form_tables(&gold.program,form,&self.task,&self.session,constructions,&self.settings,cache,&limits);
                    (report,tables,&[][..])
                }
            };
            report["form_cache"]=cache.form_cache_stats();
            let started=arclog::clock::Stopwatch::start();
            let materializer=Materializer::new(&self.session,&limits);
            let columns=if held_rows {
                case_columns_held_in(&materializer,evidence,&tables,self.task.train.len(),None,self.settings.projection_cap)
            } else {
                case_columns_in(&materializer,evidence,&tables,self.task.train.len(),None)
            };
            let written=gold.program.written_stream(Registry::get(),&self.settings).map_err(|d|d.message.to_string())?;
            let columns=columns.with_identities(identify(gold.program.checked(),Registry::get(),&written.relations,evidence,&tables));
            report["entry_count"]=columns.entries.table.len().into();
            let counts = self.session.largest_counts();
            report["largest_counts"] = serde_json::json!({"bindings":counts.bindings,"rows":counts.rows});
            packing_status(&mut report,[&columns]);
            report["packed_correspondence"]=table_binding(&columns,"gold",&report,&self.ident_namespace);
            report["packed_correspondence"]["program_sexp"]=gold.program.sexp(Registry::get()).into();
            report["program_sexp"]=gold.program.sexp(Registry::get()).into();
            report["native_columns_seconds"]=started.elapsed().seconds().into();
            Ok((report,columns))
        })).map_err(PyValueError::new_err)?;
        Ok((report.to_string(),PyCaseTables::of(py,self.task_name.clone(),"gold".into(),false,self.settings.projection_cap,columns,None,None)?))
    }

    /// Native gold-only TRAIN FITS and ordered kept DET choices, without a mutant.
    /// Returns self-contained arclog-study-gold-kept-v1 JSON, including on cache
    /// hits. status/observation_complete describe the walk; callers must also
    /// check assignment_coverage_complete before requiring every DET's value.
    /// Cached bounded observations remain bounded. This gives no TEST Fit verdict
    /// and does not materialize relation tables or change their search policy.
    fn gold_kept(&self,py:Python<'_>,program:&PyStudyProgram)->PyResult<String> {
        if program.settings!=self.settings {return Err(PyValueError::new_err("task evaluator and program settings differ"));}
        let constructions=constructions()?;
        py.detach(||self.with_cache("gold_kept",|cache| {
            if cache.activate(&program.program) {self.session.results.clear();}
            let mut report=study_pair::gold_kept_cached(&program.program,&self.task,&self.judged,
                &self.session,constructions,&self.settings,cache);
            report["task"]=self.task_name.clone().into();
            Ok(report.to_string())
        })).map_err(PyValueError::new_err)
    }

    /// Fresh original-scope BODY evidence at the cached full gold choices.
    /// expected_kept_json asserts the same-session ordered choices; it cannot
    /// supply assignments. Call gold_kept first with this exact program handle.
    /// prefix_conjuncts selects completed conjuncts, including an empty
    /// prefix. A nested OR branch BODY path selects only that branch with
    /// its preceding outer context. Omitting it preserves the full BODY API.
    #[pyo3(signature=(program,body_path,expected_kept_json=None,*,prefix_conjuncts=None))]
    fn gold_body(&self,py:Python<'_>,program:&PyStudyProgram,body_path:Vec<u32>,expected_kept_json:Option<&str>,prefix_conjuncts:Option<usize>)->PyResult<(String,PyCaseTables)> {
        if program.settings!=self.settings {return Err(PyValueError::new_err("task evaluator and program settings differ"));}
        let expected=expected_kept_json.map(serde_json::from_str::<serde_json::Value>).transpose().map_err(|e|PyValueError::new_err(e.to_string()))?;
        let body=arclog::program::path::NodePath(body_path.into_iter().map(arclog::program::path::PathStep).collect());
        let constructions=constructions()?;
        let (report,columns)=py.detach(||self.with_cache("gold_body",|cache| {
            let mut result=match prefix_conjuncts {
                Some(count)=>study_pair::gold_body::evaluate_prefix_cached(&program.program,&body,count,&self.task,&self.session,
                    constructions,&self.settings,cache,expected.as_ref())?,
                None=>study_pair::gold_body::evaluate_cached(&program.program,&body,&self.task,&self.session,
                    constructions,&self.settings,cache,expected.as_ref())?,
            };
            result.report["task"]=self.task_name.clone().into();
            let materializer=Materializer::new(&self.session,&result.limits);
            let columns=case_columns_in(&materializer,&self.evidence,&result.tables,self.task.train.len(),None);
            packing_status(&mut result.report,[&columns]);
            result.report["packed_correspondence"]=table_binding(&columns,"gold",&result.report,&self.ident_namespace);
            result.report["packed_correspondence"]["program_sexp"]=program.program.sexp(Registry::get()).into();
            result.report["packed_table_count"]=columns.tables.form.len().into();
            result.report["body_table_packed"]=result.report["body_table"].as_u64().is_some_and(|i|(i as usize)<columns.tables.form.len()).into();
            Ok((result.report,columns))
        })).map_err(PyValueError::new_err)?;
        Ok((report.to_string(),PyCaseTables::of(py,self.task_name.clone(),"gold".into(),false,self.settings.projection_cap,columns,None,None)?))
    }

    fn evaluate_pair(&self,py:Python<'_>,gold:&PyStudyProgram,point:&PyMutationPoint,mutant:&PyValidMutant)->PyResult<(String,PyCaseTables,PyCaseTables)> {
        if gold.settings!=self.settings || mutant.settings!=self.settings {return Err(PyValueError::new_err("task evaluator and program settings differ"));}
        let constructions=constructions()?;
        let mut result=py.detach(|| self.with_cache("evaluate_pair",|cache| {
            if cache.activate(&gold.program) {self.session.results.clear();}
            Ok(study_pair::evaluate_pair_cached(&gold.program,&point.inner,&mutant.inner,&self.task,&self.judged,&self.session,constructions,&self.settings,cache))
        })).map_err(PyValueError::new_err)?;
        let (g,m)=pack_pair(py,&self.task_name,["gold","mutant"],self.settings.projection_cap,&self.ident_namespace,[&gold.program,mutant.inner.program()],&mut result,|result,gold| {
            self.with_cache("pack_pair_side",|cache| {
                let materializer=Materializer::new(&self.session,&result.limits);
                Ok(study_pair::pair_side_columns_cached(&materializer,&self.evidence,result,gold,self.task.train.len(),cache))
            })
        })?;
        result.report["cache"]=self.with_cache("cache_stats",|cache|Ok(cache.stats())).map_err(PyValueError::new_err)?;
        result.report["cache"]["session_result_bytes"]=self.session.results.bytes().into();
        Ok((result.report.to_string(),g,m))
    }
}


// One report adapter for every native study packing entry. Execution evidence
// remains unchanged: an output-buffer stop is separate collection evidence.
// Actual packed indices identify a view; selector/form alone does not. This
// references the compiler correspondence without reparsing names or types.
/// Validate the shared materializer map against actual packed entry axes.
/// Missing packed tables keep an explicit unavailable map, never a guessed
/// ordinal into a separately persisted payload.
fn prefix_packed_map(report:&mut serde_json::Value,columns:&arclog_tables::columns::CaseColumns)->bool {
    let source=report["entry_parent_map"].take();
    let mut complete=source.is_array();let mut maps=Vec::new();
    for table in source.as_array().into_iter().flatten() {
        let index=table["table"].as_u64().unwrap_or(u64::MAX) as usize;
        let packed=columns.entries.table.iter().enumerate().filter_map(|(i,t)|((*t as usize)==index).then_some(i)).collect::<Vec<_>>();
        let rows=table["entries"].as_array();
        let valid=index<columns.tables.form.len() && rows.is_some_and(|rows|rows.len()==packed.len() &&
            rows.iter().zip(&packed).all(|(row,&i)|row["example_kind"].as_u64()==Some(columns.entries.example_kind[i] as u64)
                && row["example_index"].as_u64()==Some(columns.entries.example_index[i] as u64)
                && row["model"].as_u64()==Some(columns.entries.model[i] as u64)));
        let mut map=table.clone();
        map["status"]=if valid {"complete"}else{"unavailable"}.into();
        if valid {
            if let Some(entries)=map["entries"].as_array_mut() {for (row,index) in entries.iter_mut().zip(packed) {row["entry"]=index.into();}}
        } else {
            complete=false;map["entries"]=serde_json::json!([]);
            map["reason"]="materialized entry map not present with exact axes in packed payload".into();
        }
        maps.push(map);
    }
    report["materialized_entry_parent_map"]=source;
    report["entry_parent_map"]=maps.into();
    report["entry_parent_map_complete"]=complete.into();
    complete
}

fn table_binding(columns:&arclog_tables::columns::CaseColumns,side:&str,report:&serde_json::Value,ident_namespace:&str)->serde_json::Value {
    let tables=&columns.tables;
    let roles=report["table_indices"].as_object();
    serde_json::json!({"schema":"arclog-study-packed-correspondence-v1","packing_ref":study_pair::table_transport_ref(),"side":side,
        "binding_contract":"atomic native returned report/CaseTables tuple; persisted use requires one acquisition receipt binding report and exact payload digests/runtime/source; packing_ref is not a payload digest",
        "ident_namespace":ident_namespace,"ident_namespace_contract":"one native TaskSession intern table; comparison across namespaces requires native transport, never numeric equality",
        "ident_columns":(0..tables.form.len()).flat_map(|table|tables.column_types[table].iter().enumerate().filter(|(_,ty)|ty.as_str()=="Ident").map(move|(column,_)|serde_json::json!({"table":table,"physical_column":column}))).collect::<Vec<_>>(),
        "tables_ref":report["tables_ref"],"tables":(0..tables.form.len()).map(|i| {
            let mut roles=roles.into_iter().flat_map(|r|r.iter()).filter(|(role,value)|role.starts_with(side) && value.as_u64()==Some(i as u64)).map(|(role,_)|role.clone()).collect::<Vec<_>>();
            if report["body_table"].as_u64()==Some(i as u64) {roles.push("gold_body_kept".into());}
            if !report["tables_ref"].is_null() {roles.push("gold_relation_search".into());}
            serde_json::json!({"table":i,"selector":{"form":tables.form[i],"point":tables.point[i],"relation":tables.relation[i],"fact":tables.fact[i]},
                "clause_index":tables.form[i].split('.').next().and_then(|n|n.parse::<usize>().ok()),
                "report_roles":roles,"physical_types":tables.column_types[i],"physical_labels":tables.column_labels[i],"physical_slots":tables.column_slots[i],
                "physical_names":tables.column_names[i],"cell_width":tables.width[i]})
        }).collect::<Vec<_>>()})
}

fn packing_status<'a>(report:&mut serde_json::Value,columns:impl IntoIterator<Item=&'a arclog_tables::columns::CaseColumns>) {
    let columns: Vec<_> = columns.into_iter().collect();
    packing_stops(report,columns.iter().filter_map(|c|c.packing_stop()));
    let mut entry_stops = report["entry_stops"].as_array().cloned().unwrap_or_default();
    let mut assignment_stops = report["assignment_stops"].as_array().cloned().unwrap_or_default();
    let mut extent_stops = report["extent_stops"].as_array().cloned().unwrap_or_default();
    for columns in columns {
        for (entry, bound) in columns.entries.extent_stop.bound.iter().enumerate() {
            if let Some(bound) = bound {
                extent_stops.push(serde_json::json!({"entry":entry,"table":columns.entries.table[entry],"reason":bound,"form":columns.entries.extent_stop.form[entry],"source":"packing"}));
            }
        }
        for (entry, bound) in columns.entries.value_stop.bound.iter().enumerate() {
            if let Some(bound) = bound {
                if columns.entries.value_stop.assignment[entry] {
                    // A stop that rejects one assignment alone leaves the status as the other assignments give it.
                    assignment_stops.push(serde_json::json!({"entry":entry,"table":columns.entries.table[entry],"example_kind":columns.entries.example_kind[entry],"example":columns.entries.example_index[entry],"assignment":columns.entries.assignment[entry],"model":columns.entries.model[entry],"reason":bound,"form":columns.entries.value_stop.form[entry],"source":"packing"}));
                } else {
                    entry_stops.push(serde_json::json!({"entry":entry,"table":columns.entries.table[entry],"bound":bound,"form":columns.entries.value_stop.form[entry]}));
                }
            }
        }
    }
    report["extent_stops"] = extent_stops.into();
    if !assignment_stops.is_empty() {
        report["assignment_stops"] = assignment_stops.into();
    }
    if !entry_stops.is_empty() {
        if report["status"]!="fault" {report["status"]="stopped".into();}
        report["entry_stops"] = entry_stops.into();
    }
}

fn packing_stops<'a>(report:&mut serde_json::Value,stops:impl IntoIterator<Item=&'a arclog::eval::Stop>) {
    let stops:Vec<_>=stops.into_iter().map(|stop|serde_json::json!({"bound":format!("{:?}",stop.bound),"form":stop.form.0.iter().map(|s|s.0).collect::<Vec<_>>()})).collect();
    if !stops.is_empty() {
        report["packing"] = serde_json::json!({"status":"stopped","stops":stops});
        if report["status"]!="fault" {report["status"]="stopped".into();report["reason"]=report["packing"]["stops"][0]["bound"].clone();}
    }
}

trait PackingReport {fn packing_report(&mut self)->&mut serde_json::Value;}
macro_rules! packing_report {($($ty:ty),*)=>{$(
    impl PackingReport for $ty {fn packing_report(&mut self)->&mut serde_json::Value {&mut self.report}}
)*};}
packing_report!(study_pair::PairEvaluation,study_pair::component_tables::ComponentTables,study_pair::continuation::Continuation);

// Each side keeps its admitted conversion peak until conversion consumes its
// Rust payload. Both sides use the native evaluation's original limits and
// session; the completed first output remains charged while packing the next.
fn pack_pair<R:PackingReport+Send+Sync>(
    py:Python<'_>,task:&str,sides:[&str;2],projection_cap:u64,ident_namespace:&str,programs:[&arclog::study::StudyProgram;2],result:&mut R,
    mut pack:impl FnMut(&R,bool)->Result<arclog_tables::columns::CaseColumns,String>+Send,
)->PyResult<(PyCaseTables,PyCaseTables)> {
    let mut stops=Vec::new();
    let mut seconds=0.;
    let mut bindings=Vec::new();
    let mut side=|index:usize|->PyResult<PyCaseTables> {
        let (columns,elapsed)=py.detach(|| {
            let started=arclog::clock::Stopwatch::start();
            pack(result,index==0).map(|columns|(columns,started.elapsed().seconds()))
        }).map_err(PyValueError::new_err)?;
        seconds+=elapsed;
        stops.extend(columns.packing_stop().cloned());
        let mut binding=table_binding(&columns,sides[index],result.packing_report(),ident_namespace);
        binding["program_sexp"]=programs[index].sexp(Registry::get()).into();
        bindings.push(binding);
        packing_status(result.packing_report(),[&columns]);
        PyCaseTables::of(py,task.into(),sides[index].into(),false,projection_cap,columns,None,None)
    };
    let gold=side(0)?;
    let mutant=side(1)?;
    let report=result.packing_report();
    packing_stops(report,&stops);
    report["packed_correspondence"]=serde_json::json!(bindings);
    report["timings"]["native_columns"]=seconds.into();
    Ok((gold,mutant))
}
