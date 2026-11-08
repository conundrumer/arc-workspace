//! `corpus_tables`: the tables of each case of the corpus's solvers.

use std::num::NonZeroUsize;
use std::path::Path;
use std::sync::Mutex;

use arclog::decode::corpus::{read_task_files, replay_units, ReplayProgress, UnitSolver};
use arclog::eval::determinations::relation_spelled;
use arclog::harness::corpus_threads;
use arclog::hash::StableHashMap;
use arclog::registry::Registry;
use arclog::stream::corpus::{fault_line, solver_streams, token_ids, StreamLabels, WantedCases};
use arclog::stream::{DecodeSettings, Emitter, Vocabulary};
use arclog::task::{JudgedTask, Task};
use arclog_bindings::{constructions, walk_corpus, Progress, PyConsistencyKind, PyReplayProgress};
use arclog_tables::columns::case_columns_in;
use arclog::eval::join::Materializer;
use arclog_tables::tables::{evidence_tables, Points, Table};
use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;

use crate::case_tables::PyCaseTables;
use crate::record::StreamRecord;

/// A case of a solver whose tables `corpus_tables` builds: its stream's
/// token ids, the spelling by `relation_spelled` of the relation declared
/// at each slot, in slot order, and the names that the case's text writes for
/// the labels of the stream, or the writer's fault.
struct TableCase {
    case: String,
    concept: bool,
    stream: Result<(Vec<(u32, Emitter)>, Vec<String>, StreamLabels), String>,
}

/// The tables of each case of each solver of `corpus`, on its task in
/// `tasks`, the concept case or, with `all_cases`, every case, over the
/// solvers whose task ids `task_ids` gives, or every solver where it is
/// `None`, in the order of the task ids and then of the cases. Each table
/// is at the index of the token whose step gives it, but for the first two,
/// the evidence tables `ex_input` and `ex_output` of the task, which stand at
/// token 0 with point 2. The tables are those of a decode under `projection_cap`,
/// the cap of `DecodeSettings`, the engine's default where it is `None`, and
/// each `CaseTables` gives it. `table_work_cap` budgets projections and extents,
/// with the same default and the same `None`. Row queries have only the
/// evaluation caps, whose `binding_cap` and `row_cap` overrides default to
/// `DecodeSettings::corpus()`. `largest_counts` gives their largest completed binding
/// and row counts, and `query_stops` lists stopped queries as JSON. The relations of the
/// finished forms are tabled, and with `bodies` the bodies in progress as well.
/// The second value holds a line for each case that gives no tables and each
/// solver that gives none, in the form of `corpus_streams`, in the order of
/// the task ids (a case whose program holds a `DEMONSTRATED` form gives no
/// tables, and its line is the writer's fault where its stream has one and
/// `<task> <case>: the program holds a DEMONSTRATED form` otherwise), and for
/// each case whose last `RULE` end before the stream's end gives `Stopped`
/// the line `<task> <case>: ended Stopped at token <index>` of `stream_tables`, with that case's tables kept. The replay runs under no
/// deadline and computes no token mask.
/// The call runs on the threads of the corpus harness with the GIL released,
/// but for the build of each `CaseTables`, in phases. The first reads each
/// solver, its streams and its task. The second cuts the streams of each
/// solver into units, replays the units, the
/// largest first, and turns the tables of each stream into columns as its
/// unit ends.
/// `units`, a positive integer or `None`, sets the cut and the threads of
/// the second phase. With `None`, the streams of each solver, in the order of
/// their tokens, are cut into groups of consecutive streams of at most
/// `UNIT_STEPS` model steps but for the last stream's, as `corpus_streams`
/// does, and the threads are those of the corpus harness. With an integer
/// `k`, they are cut into at most `k` units of consecutive streams with about
/// equal new model steps, each cut at the stream that passes the next
/// `k`-th of the solver's model steps, and the call replays on `k` threads,
/// whatever `ARCLOG_THREADS` holds. An Ident's number depends on the unit
/// that interned it, so the same call with another `units` gives the same
/// tables but for the numbers of its Idents, and each equality of two Idents
/// within a case holds in both. `ValueError` is raised for 0.
/// `ended`, a callable or `None`, is called with a solver's task id, holding
/// the GIL, once the last of that solver's streams has ended. A solver whose
/// streams all lie past `step_cap` gets the call; one whose task did not read,
/// and one whose unit panics, gives none. An
/// exception that `ended` raises is printed and dropped.
/// `step_cap`, an integer or `None`, bounds the replay of each solver as it
/// does in `corpus_streams`; a stream past the cap gives its line as the
/// case's fault.
/// `progress`, a `ReplayProgress` or `None`, gives the model steps of the
/// second phase: its `total` is set once the units are cut and its `done`
/// grows while they replay.
/// With `copies`, the replay checks the rows that the outputs of the constructions declare they copy
/// (`arclog::eval::copies`), and each `CaseTables.copies` gives the violations it found; a
/// construction's run that an earlier run of the call cached is not checked again.
/// With `prefix`, each solver's files hold a prefix of a solver, read as `corpus_streams` reads them.
#[pyfunction]
#[pyo3(signature = (corpus, tasks, all_cases=false, task_ids=None, bodies=false, projection_cap=None, ended=None, progress=None, step_cap=None, table_work_cap=None, units=None, copies=false, prefix=false, binding_cap=None, row_cap=None))]
pub(crate) fn corpus_tables(py: Python<'_>, corpus: &str, tasks: &str, all_cases: bool, task_ids: Option<Vec<String>>, bodies: bool, projection_cap: Option<u64>, ended: Option<Py<PyAny>>, progress: Option<Py<PyReplayProgress>>, step_cap: Option<usize>, table_work_cap: Option<u64>, units: Option<usize>, copies: bool, prefix: bool, binding_cap: Option<u64>, row_cap: Option<u64>) -> PyResult<(Vec<PyCaseTables>, Vec<String>)> {
    let units = units.map(|count| NonZeroUsize::new(count).ok_or_else(|| PyValueError::new_err("units must be a positive integer"))).transpose()?;
    let points = if bodies { Points::All } else { Points::Relations };
    let wanted = if all_cases { WantedCases::All } else { WantedCases::Concept };
    let constructions = constructions()?;
    let vocabulary = Vocabulary::new(Registry::get(), &DecodeSettings::default());
    let base = DecodeSettings::default();
    let settings = DecodeSettings { projection_cap: projection_cap.unwrap_or(base.projection_cap), table_work_cap: table_work_cap.unwrap_or(base.table_work_cap), check_copies: copies, caps: arclog::eval::Caps {bindings:binding_cap.unwrap_or(base.caps.bindings),rows:row_cap.unwrap_or(base.caps.rows),..base.caps}, ..base };
    let reads: Mutex<StableHashMap<String, (Task, JudgedTask)>> = Mutex::new(StableHashMap::default());
    let found = walk_corpus(py, corpus, &task_ids, |id| {
        let (mut cases, mut faults) = (Vec::new(), Vec::new());
        match solver_streams(Path::new(corpus), id, wanted, &vocabulary, prefix) {
            Ok(streams) => match read_task_files(Path::new(tasks), id) {
                Ok(read) => {
                    for case in streams {
                        if case.demonstrated {
                            let fault = case.stream.err().unwrap_or_else(|| "the program holds a DEMONSTRATED form".to_string());
                            faults.push(fault_line(id, Some(&case.case), &fault));
                            continue;
                        }
                        let stream = case.stream.map(|stream| (token_ids(&stream.tokens, &vocabulary), stream.relations.iter().map(relation_spelled).collect(), case.labels));
                        cases.push(TableCase { case: case.case, concept: case.concept, stream });
                    }
                    reads.lock().unwrap_or_else(|poisoned| poisoned.into_inner()).insert(id.to_string(), read);
                }
                Err(fault) => faults.push(fault_line(id, None, &fault)),
            },
            Err(fault) => faults.push(fault_line(id, None, &fault)),
        }
        (cases, faults)
    })?;
    let reads = reads.into_inner().unwrap_or_else(|poisoned| poisoned.into_inner());
    // For each solver that has cases: the ids of the streams its writer gives, and their label names.
    let streamed: Vec<(&str, Vec<Vec<(u32, Emitter)>>, Vec<&StreamLabels>)> = found
        .iter()
        .filter(|(id, cases, _)| !cases.is_empty() && reads.contains_key(id))
        .map(|(id, cases, _)| {
            let written = cases.iter().filter_map(|case| case.stream.as_ref().ok());
            (id.as_str(), written.clone().map(|(ids, _, _)| ids.clone()).collect(), written.map(|(_, _, labels)| labels).collect())
        })
        .collect();
    let solvers: Vec<UnitSolver<'_>> = streamed
        .iter()
        .map(|(id, ids, _)| {
            let (task, judged) = &reads[*id];
            UnitSolver { task, judged, streams: ids, units }
        })
        .collect();
    let trains: Vec<usize> = streamed.iter().map(|(id, _, _)| reads[*id].0.train.len()).collect();
    let evidence: Vec<Vec<Table>> = solvers.iter().map(|solver| evidence_tables(solver.task, Registry::get())).collect();
    let unread = ReplayProgress::default();
    let steps = progress.as_ref().map_or(&unread, |progress| &progress.get().inner);
    let progress = Progress::new(None, ended.as_ref(), streamed.iter().map(|(id, _, _)| *id).collect(), streamed.iter().map(|(_, ids, _)| ids.len()).collect());
    let mut replayed = py
        .detach(|| {
            replay_units(
                &solvers,
                constructions,
                &settings,
                false,
                units.map_or_else(corpus_threads, NonZeroUsize::get),
                steps,
                &|record: &mut StreamRecord, decoder, stepped| record.step(decoder, stepped, points),
                &|solver| progress.start(solver),
                &|solver, stream, replay| replay.into_result().map(|record| {
                    let limits=settings.operation_limits();
                    let empty_session=arclog::session::TaskSession::new(arclog::session::SessionBound {bytes:arclog::session::SESSION_BYTES},settings.caps);
                    let session=record.session.as_ref().unwrap_or(&empty_session);
                    let materializer=Materializer::new(session,&limits);
                    let counts = session.largest_counts();
                    (case_columns_in(&materializer,&evidence[solver],&record.tables,trains[solver],Some(streamed[solver].2[stream])).with_copies(&record.copies),record.ended,counts,record.query_stops())
                }),
                &|solver| progress.settle(solver),
                step_cap,
            )
        })
        .into_iter();
    let mut tables = Vec::new();
    let mut faults = Vec::new();
    for (task, cases, solver_faults) in &found {
        faults.extend(solver_faults.iter().cloned());
        if cases.is_empty() || !reads.contains_key(task) {
            continue;
        }
        let mut outs = replayed.next().expect("a result for each solver that has cases").into_iter();
        for case in cases {
            let outcome = match &case.stream {
                Ok((_, relations, _)) => outs.next().expect("a result for each stream").and_then(|out| out).map(|out| (out, relations)),
                Err(fault) => Err(fault.clone()),
            };
            match outcome {
                Ok(((columns, ended, counts, query_stops), relations)) => {
                    if let Some(stop)=columns.packing_stop() {faults.push(format!("{task} {}: native packing stopped {:?} at {:?}",case.case,stop.bound,stop.form));}
                    let mut table = PyCaseTables::of(py, task.clone(), case.case.clone(), case.concept, settings.projection_cap, columns, Some(relations), None)?;
                    table.largest_counts = Some((counts.bindings, counts.rows));
                    table.query_stops = Some(query_stops);
                    tables.push(table);
                    if let Some(at) = ended.filter(|at| matches!(at.kind, PyConsistencyKind::Stopped)) {
                        faults.push(at.line(task, &case.case));
                    }
                }
                Err(fault) => faults.push(fault_line(task, Some(&case.case), &fault)),
            }
        }
    }
    Ok((tables, faults))
}
