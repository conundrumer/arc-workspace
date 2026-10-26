//! `stream_tables`: the tables of the token streams of one task.

use std::path::Path;

use arclog::decode::corpus::{read_task_files, replay_units, ReplayProgress, UnitSolver};
use arclog::harness::corpus_threads;
use arclog::registry::Registry;
use arclog::stream::corpus::fault_line;
use arclog::stream::{DecodeSettings, Emitter, Vocabulary};
use arclog_bindings::{constructions, PyDecodeSettings};
use arclog_tables::columns::case_columns;
use arclog_tables::tables::{evidence_tables, Points};
use pyo3::exceptions::{PyRuntimeError, PyValueError};
use pyo3::prelude::*;

use crate::case_tables::PyCaseTables;
use crate::record::StreamRecord;

/// The tables of the token streams of one task, for a sampler that holds the
/// streams of the programs it generates, as `corpus_tables` gives those of the
/// corpus's.
///
/// `task` is the task id and `tasks` the directory of the task files; the
/// replay judges the train pairs in the closed world, as `corpus_tables` does.
/// `streams` is a list of pairs `(ids, model)`: `ids` the token ids of a
/// stream, the engine's forced ids included, and `model` one flag for each id,
/// 1 (or `True`) where the model wrote the token and 0 where the engine did,
/// a list or `bytes`, as a sampler holds them from `Decoder.step`. The step
/// cap and the replay's units count the model's steps.
/// `settings`, a `DecodeSettings` or `None` for the default, is that of the
/// sampler's `Session`: the vocabulary that gives the ids is built from it, and
/// the replay's decodes run under it, so each `RULE` end is judged as the
/// sampler's decode judged it. Its `projection_cap` and `table_work_cap` are
/// the tables' caps. `bodies` and `step_cap` are as in `corpus_tables`; the
/// replay computes no token mask. `copies` is as in `corpus_tables`.
/// `names` gives the case of each stream, or is `None` for the index of the
/// stream as text. `ValueError` is raised, before any replay, for a `model`
/// of another length than its `ids`, a flag other than 0 and 1, an id outside
/// the vocabulary of `settings`, a `names` of another length than `streams`,
/// and a name that is empty, `.` or `..`, holds `/`, or stands twice.
/// The first value holds the `CaseTables` of the streams that were replayed, in
/// the order of the streams. A stream whose replay faults keeps the tables
/// recorded before the fault. The second value holds, in the order of the
/// streams, for each stream replayed the line
/// `<task> <case>: ended <kind> at token <index>`, the verdict at the last
/// `RULE` end before the stream's end or cut, not at the stream's end, and `<kind>` one of `Consistent`, `NotConsistent`,
/// `SeveralValues`, `Fault` and `Stopped`, or `<task> <case>: ended none`;
/// then the fault line of each stream that faults or lies past `step_cap`,
/// which gives no tables, in the form of `corpus_streams`. A unit that panics
/// gives the one line `<task> <case>: the replay panicked: <message>` and no tables. The call runs with the
/// GIL released, but for the build of each `CaseTables`.
#[pyfunction]
#[pyo3(signature = (task, tasks, streams, names=None, settings=None, bodies=false, step_cap=None, copies=false))]
pub(crate) fn stream_tables(py: Python<'_>, task: &str, tasks: &str, streams: Vec<(Vec<u32>, Vec<u8>)>, names: Option<Vec<String>>, settings: Option<PyDecodeSettings>, bodies: bool, step_cap: Option<usize>, copies: bool) -> PyResult<(Vec<PyCaseTables>, Vec<String>)> {
    let settings = match settings {
        Some(settings) => settings.engine()?,
        None => DecodeSettings::default(),
    };
    let settings = DecodeSettings { check_copies: copies, ..settings };
    let vocabulary = Vocabulary::new(Registry::get(), &settings);
    let names = match names {
        Some(names) if names.len() != streams.len() => return Err(PyValueError::new_err(format!("{} names for {} streams", names.len(), streams.len()))),
        Some(names) => names,
        None => (0..streams.len()).map(|index| index.to_string()).collect(),
    };
    let mut seen = std::collections::HashSet::new();
    for name in &names {
        if name.is_empty() || name == "." || name == ".." || name.contains('/') {
            return Err(PyValueError::new_err(format!("the name {name:?} is no file name")));
        }
        if !seen.insert(name) {
            return Err(PyValueError::new_err(format!("the name {name:?} stands twice")));
        }
    }
    let mut ids: Vec<Vec<(u32, Emitter)>> = Vec::new();
    for (index, (stream, model)) in streams.iter().enumerate() {
        if stream.len() != model.len() {
            return Err(PyValueError::new_err(format!("stream {index}: {} ids and {} model flags", stream.len(), model.len())));
        }
        let mut tokens = Vec::with_capacity(stream.len());
        for (&id, &flag) in stream.iter().zip(model) {
            if id as usize >= vocabulary.len() {
                return Err(PyValueError::new_err(format!("stream {index}: the id {id} is outside the vocabulary of {} tokens", vocabulary.len())));
            }
            tokens.push((id, match flag {
                1 => Emitter::Model,
                0 => Emitter::Engine,
                _ => return Err(PyValueError::new_err(format!("stream {index}: the model flag {flag} is neither 0 nor 1"))),
            }));
        }
        ids.push(tokens);
    }
    let constructions = constructions()?;
    let (read, judged) = read_task_files(Path::new(tasks), task).map_err(PyRuntimeError::new_err)?;
    let points = if bodies { Points::All } else { Points::Relations };
    let evidence = evidence_tables(&read, Registry::get());
    let train = read.train.len();
    let solvers = [UnitSolver { task: &read, judged: &judged, streams: &ids, units: None }];
    let steps = ReplayProgress::default();
    let mut replayed = py.detach(|| {
        replay_units(
            &solvers,
            constructions,
            &settings,
            false,
            corpus_threads(),
            &steps,
            &|record: &mut StreamRecord, decoder, stepped| record.step(decoder, stepped, points),
            &|_| {},
            &|_, replay| (case_columns(&evidence, &replay.record.tables, train).with_copies(&replay.record.copies), replay.record.ended, replay.fault),
            &|_| {},
            step_cap,
        )
    });
    let outs = replayed.pop().expect("a result for the one solver");
    let (mut tables, mut ended, mut faults) = (Vec::new(), Vec::new(), Vec::new());
    for (case, out) in names.iter().zip(outs) {
        match out {
            Ok((columns, at, fault)) => {
                tables.push(PyCaseTables::of(py, task.to_string(), case.clone(), false, settings.projection_cap, &columns, None)?);
                ended.push(match at {
                    Some(at) => at.line(task, case),
                    None => format!("{task} {case}: ended none"),
                });
                faults.extend(fault.map(|fault| fault_line(task, Some(case), &fault)));
            }
            Err(fault) => faults.push(fault_line(task, Some(case), &fault)),
        }
    }
    ended.extend(faults);
    Ok((tables, ended))
}
