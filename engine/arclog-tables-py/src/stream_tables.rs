//! `stream_tables`: the tables of the token streams of one task.

use std::num::NonZeroUsize;
use std::panic::{catch_unwind, AssertUnwindSafe};
use std::path::Path;

use arclog::decode::corpus::{common_prefix, read_task_files, replay_panic, replay_units, ReplayProgress, StreamReplay, UnitSolver};
use arclog::harness::{corpus_threads, run_on_workers};
use arclog::registry::Registry;
use arclog::stream::corpus::fault_line;
use arclog::stream::{DecodeSettings, Emitter, Vocabulary};
use arclog_bindings::{constructions, PyDecodeSettings};
use arclog_tables::columns::{case_columns_in,cut_case_columns_in};
use arclog::eval::join::Materializer;
use arclog_tables::tables::{evidence_tables, Points};
use pyo3::exceptions::{PyRuntimeError, PyValueError};
use pyo3::prelude::*;

use crate::case_tables::{Base, PyCaseTables};
use crate::record::StreamRecord;

/// The stream a stream is cut from, and the length of the prefix they share.
type Cut = (usize, usize);

/// The `bases` of a call of `streams`, one entry for each stream, or a
/// `ValueError` for a base outside the streams, a stream that is its own
/// base, and a base that has a base.
fn check_bases(bases: Option<Vec<Option<usize>>>, streams: usize) -> PyResult<Vec<Option<usize>>> {
    let Some(bases) = bases else { return Ok(vec![None; streams]) };
    if bases.len() != streams {
        return Err(PyValueError::new_err(format!("{} bases for {streams} streams", bases.len())));
    }
    for (index, base) in bases.iter().enumerate() {
        match *base {
            Some(base) if base >= streams => return Err(PyValueError::new_err(format!("stream {index}: the base {base} is no stream of the {streams}"))),
            Some(base) if base == index => return Err(PyValueError::new_err(format!("stream {index} is its own base"))),
            Some(base) if bases[base].is_some() => return Err(PyValueError::new_err(format!("stream {index}: its base {base} has a base"))),
            _ => {}
        }
    }
    Ok(bases)
}

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
///
/// `bases` is `None`, or gives one entry for each stream: `None`, or the index
/// of another stream of the call, its base. `ValueError` is raised, before any
/// replay, for a `bases` of another length than `streams`, an index outside
/// the streams, a stream that is its own base, and a base that has a base.
/// With a base given, the call replays its streams in one unit, so a stream and
/// its base share the session that numbers their Idents, and a stream is
/// *cut* where its base gives `CaseTables` and every stream of the call was
/// replayed (none lies past `step_cap`, and the unit did not panic, which
/// replays its streams one by one, in sessions of their own). The `CaseTables` of a cut stream
/// holds only the tables of the steps at or after `n`, the length of the
/// longest prefix of `(id, model flag)` pairs that it shares with its base: it
/// gives the base's case name, `n` and the count `k` of the base's tables before
/// `n` as `base`, `base_tokens` and `base_tables`, and numbers its tables from
/// `k`; a table number below `k` in its parts names the base's table of that
/// number. For each cut stream, the base's tables numbered below `k` with the
/// cut stream's own tables give, row for row and cell for cell but for the
/// numbers of Idents, the tables that the call without `bases` gives the stream,
/// and each equality of two Idents across those tables holds in both; the
/// `values` of a cut stream hold its own runs alone, and its `copies` and the
/// report lines are those of the call without `bases`.
#[pyfunction]
#[pyo3(signature = (task, tasks, streams, names=None, settings=None, bodies=false, step_cap=None, copies=false, bases=None))]
pub(crate) fn stream_tables(py: Python<'_>, task: &str, tasks: &str, streams: Vec<(Vec<u32>, Vec<u8>)>, names: Option<Vec<String>>, settings: Option<PyDecodeSettings>, bodies: bool, step_cap: Option<usize>, copies: bool, bases: Option<Vec<Option<usize>>>) -> PyResult<(Vec<PyCaseTables>, Vec<String>)> {
    let settings = match settings {
        Some(settings) => settings.engine()?,
        None => DecodeSettings::synthesis(),
    };
    let settings = DecodeSettings { check_copies: copies, ..settings };
    let vocabulary = Vocabulary::new(Registry::get(), &settings);
    let names = match names {
        Some(names) if names.len() != streams.len() => return Err(PyValueError::new_err(format!("{} names for {} streams", names.len(), streams.len()))),
        Some(names) => names,
        None => (0..streams.len()).map(|index| index.to_string()).collect(),
    };
    let bases = check_bases(bases, streams.len())?;
    let mut seen = arclog::hash::StableHashSet::default();
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
    let units = bases.iter().any(Option::is_some).then_some(NonZeroUsize::MIN);
    let solvers = [UnitSolver { task: &read, judged: &judged, streams: &ids, units }];
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
            &|_, _, replay| replay,
            &|_| {},
            step_cap,
        )
    });
    let outs = replayed.pop().expect("a result for the one solver");
    // The streams share one session where every stream gives its replay: a unit that panicked is replayed stream by stream.
    let one_session = outs.iter().all(Result::is_ok);
    let jobs: Vec<(&StreamReplay<StreamRecord>, Option<Cut>)> = outs
        .iter()
        .enumerate()
        .filter_map(|(index, out)| {
            let cut = bases[index].filter(|&base| one_session && outs[base].is_ok()).map(|base| (base, common_prefix(&ids[index], &ids[base])));
            out.as_ref().ok().map(|replay| (replay, cut))
        })
        .collect();
    let mut built = py
        .detach(|| {
            run_on_workers(&jobs, corpus_threads(), |&(replay, cut)| {
                let limits=settings.operation_limits();
                let empty_session=arclog::session::TaskSession::new(arclog::session::SessionBound {bytes:arclog::session::SESSION_BYTES},settings.caps);
                let session=replay.record.session.as_ref().unwrap_or(&empty_session);
                let materializer=Materializer::new(session,&limits);
                catch_unwind(AssertUnwindSafe(|| match cut {
                    Some((base, tokens)) => {
                        let (columns, tables) = cut_case_columns_in(&materializer,&evidence, &replay.record.tables, tokens, train, None);
                        (columns.with_copies(&replay.record.copies), Some((base, tokens, tables)))
                    }
                    None => (case_columns_in(&materializer,&evidence, &replay.record.tables, train, None).with_copies(&replay.record.copies), None),
                }))
                .map_err(|payload| replay_panic(&*payload))
            })
        })
        .into_iter();
    let (mut tables, mut ended, mut faults) = (Vec::new(), Vec::new(), Vec::new());
    for (case, out) in names.iter().zip(&outs) {
        match out {
            Ok(replay) => match built.next().expect("columns for each stream that was replayed") {
                Ok((columns, cut)) => {
                    let base = cut.map(|(base, tokens, count)| Base { case: names[base].clone(), tokens, tables: count });
                    if let Some(stop)=columns.packing_stop() {faults.push(format!("{task} {case}: native packing stopped {:?} at {:?}",stop.bound,stop.form));}
                    tables.push(PyCaseTables::of(py, task.to_string(), case.clone(), false, settings.projection_cap, columns, None, base)?);
                    ended.push(match replay.record.ended {
                        Some(at) => at.line(task, case),
                        None => format!("{task} {case}: ended none"),
                    });
                    faults.extend(replay.fault.as_ref().map(|fault| fault_line(task, Some(case), fault)));
                }
                Err(fault) => faults.push(fault_line(task, Some(case), &fault)),
            },
            Err(fault) => faults.push(fault_line(task, Some(case), fault)),
        }
    }
    ended.extend(faults);
    Ok((tables, ended))
}

#[cfg(test)]
mod tests {
    use super::check_bases;

    #[test]
    fn bases_are_refused_that_name_no_stream_the_stream_itself_or_a_base_with_a_base() {
        assert!(check_bases(None, 3).is_ok());
        assert!(check_bases(Some(vec![None, Some(0), Some(0)]), 3).is_ok());
        assert!(check_bases(Some(vec![None, Some(0)]), 3).is_err(), "another length than the streams");
        assert!(check_bases(Some(vec![None, Some(3), None]), 3).is_err(), "a base outside the streams");
        assert!(check_bases(Some(vec![None, Some(1), None]), 3).is_err(), "a stream that is its own base");
        assert!(check_bases(Some(vec![None, Some(0), Some(1)]), 3).is_err(), "a base that has a base");
    }
}
