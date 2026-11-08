//! The token streams of the corpus's cases, with the engine's masks.

use std::path::Path;
use std::sync::Mutex;

use arclog::decode::corpus::{read_task_files, replay_units_untested_ends, ReplayProgress, UnitSolver};
use arclog::eval::instance::Constructions;
use arclog::harness::corpus_threads;
use arclog::hash::StableHashMap;
use arclog::registry::Registry;
use arclog::stream::corpus::{fault_line, solver_streams, token_ids, WantedCases};
use arclog::stream::{DecodeSettings, Emitter, Vocabulary};
use arclog::task::{JudgedTask, Task};
use pyo3::prelude::*;
use pyo3::types::PyBytes;

use crate::constructions;
use crate::corpus::{walk_corpus, PyReplayProgress, Progress};
use crate::decoder::mask_bytes;

/// The token stream of one case of a solver of a corpus.
///
/// `ids` holds the token ids as `uint32` in native byte order, and `model`
/// one byte for each token, 1 where the model writes the token and 0 where
/// the engine does, so `numpy.frombuffer` reads each.
///
/// `masks` holds, where `corpus_streams` is given `tasks` and the case
/// replays, the mask `Decoder.admissible` gives before each token with a 1
/// in `model`, in stream order, each `(len(vocabulary) + 7) // 8` bytes, so
/// `numpy.frombuffer(masks, numpy.uint8).reshape(-1, (len(vocabulary) + 7) // 8)`
/// has one row for each token the model writes. Otherwise it is `None`, and
/// `mask_fault` is `None` where `tasks` is `None` and else the reason the
/// case gives no masks. Where the decode of the case ends at its `OUT` form
/// before the stream does, `ids` and `model` hold the tokens before the first
/// token the model writes after that end, and `masks` has one row for each
/// model token among them.
#[pyclass(name = "CaseStream", frozen, get_all, module = "arclog")]
pub(crate) struct PyCaseStream {
    task: String,
    case: String,
    concept: bool,
    ids: Py<PyBytes>,
    model: Py<PyBytes>,
    masks: Option<Py<PyBytes>>,
    mask_fault: Option<String>,
}

/// A stream of a case with the ids of its tokens, before it becomes an object.
struct IdStream {
    task: String,
    case: String,
    concept: bool,
    ids: Vec<(u32, Emitter)>,
    /// The masks of the model's tokens, or why the case gives none; `Ok`
    /// with no bytes where the walk replays nothing, or has not yet.
    masks: Result<Option<Vec<u8>>, String>,
}

/// The token stream of each case of each solver of `corpus`, the concept
/// case or, with `all_cases`, every case, over the solvers whose task ids
/// `task_ids` gives, or every solver where it is `None`, in the order of the
/// task ids and then of the cases, with the ids of the vocabulary under the
/// default settings. A case whose files `cases/<task id>/<file>.arclog` and
/// `<file>.arcdata` stand in `corpus`, with `<file>` as `CaseFiles.file` gives
/// it, takes the stream of the solver those two files make. The second value
/// holds a line for each case that gives no stream and each solver that gives
/// none, in the form the report of `arclog-cli stream --corpus` prints it, in
/// the order of the task ids.
/// With `prefix`, each solver's files hold a prefix of a solver, whole forms
/// that later forms may follow: each case takes every check but the refusal
/// of a case program that holds no `OUT` form, and its stream ends with the
/// last token of its last form. With `tasks`, a prefix's replay gives the
/// mask before each of its model tokens, and its decode ends at no `OUT`
/// form, as `replay` gives for a stream that ends before one.
/// Where `tasks`, the directory of the task files, is given, each stream is
/// also replayed on its task under the default settings, judging the train
/// pairs in the closed world, and the stream's `masks` are the engine's
/// masks of that replay; a stream whose replay gives none stays in the list
/// with its `mask_fault`, and the second value is as it is without `tasks`.
/// The walk runs on the threads of the corpus harness with the GIL released,
/// in phases. The first reads each solver, its streams and, with `tasks`, its
/// task. The second, with `tasks`, cuts the streams of each solver, in the
/// order of their tokens, into groups of consecutive streams of at most
/// `UNIT_STEPS` model steps but for the last stream's, and replays the groups,
/// the largest first. A group replays the mask of each prefix its streams
/// share once.
/// `started` and `ended`, each a callable or `None`, are called with a
/// solver's task id, holding the GIL, `started` as the first of the solver's
/// units starts, and `ended` once the last of its streams has ended. A solver
/// whose streams all lie past `step_cap` gets `ended` too; one whose task did
/// not read, and one whose unit panics, gives no `ended` call. An exception
/// that a callable raises is printed and dropped.
/// `step_cap`, an integer or `None`, bounds the replay of each solver: its
/// streams, in the order of their tokens, replay up to the last one at which
/// the model steps of their prefix tree so far stay within the cap. Each later
/// stream gives no masks and a `mask_fault` that names the cap and the model
/// steps of all the solver's streams.
/// `progress`, a `ReplayProgress` or `None`, gives the model steps of the
/// second phase: its `total` is set once the groups are cut and its `done`
/// grows while they replay.
#[pyfunction]
#[pyo3(signature = (corpus, all_cases=false, task_ids=None, tasks=None, started=None, ended=None, progress=None, step_cap=None, prefix=false))]
pub(crate) fn corpus_streams(py: Python<'_>, corpus: &str, all_cases: bool, task_ids: Option<Vec<String>>, tasks: Option<&str>, started: Option<Py<PyAny>>, ended: Option<Py<PyAny>>, progress: Option<Py<PyReplayProgress>>, step_cap: Option<usize>, prefix: bool) -> PyResult<(Vec<PyCaseStream>, Vec<String>)> {
    let wanted = if all_cases { WantedCases::All } else { WantedCases::Concept };
    let constructions = constructions()?;
    let vocabulary = Vocabulary::new(Registry::get(), &DecodeSettings::default());
    let reads: Mutex<StableHashMap<String, Result<(Task, JudgedTask), String>>> = Mutex::new(StableHashMap::default());
    let mut found = walk_corpus(py, corpus, &task_ids, |id| {
        let (mut streams, mut faults) = (Vec::new(), Vec::new());
        match solver_streams(Path::new(corpus), id, wanted, &vocabulary, prefix) {
            Ok(cases) => {
                for case in cases {
                    match case.stream {
                        Ok(stream) => {
                            streams.push(IdStream { task: id.to_string(), case: case.case, concept: case.concept, ids: token_ids(&stream.tokens, &vocabulary), masks: Ok(None) });
                        }
                        Err(fault) => faults.push(fault_line(id, Some(&case.case), &fault)),
                    }
                }
                if let (Some(tasks), false) = (tasks, streams.is_empty()) {
                    reads.lock().unwrap_or_else(|poisoned| poisoned.into_inner()).insert(id.to_string(), read_task_files(Path::new(tasks), id));
                }
            }
            Err(fault) => faults.push(fault_line(id, None, &fault)),
        }
        (streams, faults)
    })?;
    if tasks.is_some() {
        let reads = reads.into_inner().unwrap_or_else(|poisoned| poisoned.into_inner());
        let unread = ReplayProgress::default();
        let steps = progress.as_ref().map_or(&unread, |progress| &progress.get().inner);
        py.detach(|| replay_masks(&mut found, &reads, constructions, steps, started.as_ref(), ended.as_ref(), step_cap));
    }
    let mut streams = Vec::new();
    let mut faults = Vec::new();
    for (_, solver_streams, solver_faults) in found {
        for stream in solver_streams {
            let ids: Vec<u8> = stream.ids.iter().flat_map(|(id, _)| id.to_ne_bytes()).collect();
            let model: Vec<u8> = stream.ids.iter().map(|(_, emitter)| u8::from(*emitter == Emitter::Model)).collect();
            let (masks, mask_fault) = match stream.masks {
                Ok(masks) => (masks, None),
                Err(fault) => (None, Some(fault)),
            };
            streams.push(PyCaseStream {
                task: stream.task,
                case: stream.case,
                concept: stream.concept,
                ids: PyBytes::new(py, &ids).unbind(),
                model: PyBytes::new(py, &model).unbind(),
                masks: masks.map(|masks| PyBytes::new(py, &masks).unbind()),
                mask_fault,
            });
        }
        faults.extend(solver_faults);
    }
    Ok((streams, faults))
}

/// Replays the streams of `found` whose masks are due, which are those with
/// `Ok(None)`, on the tasks that `reads` holds, as [`replay_units_untested_ends`] does, and
/// sets each stream's `masks`. A solver whose task did not read, gives each of its streams that fault.
fn replay_masks(found: &mut [(String, Vec<IdStream>, Vec<String>)], reads: &StableHashMap<String, Result<(Task, JudgedTask), String>>, constructions: &'static Constructions, steps: &ReplayProgress, started: Option<&Py<PyAny>>, ended: Option<&Py<PyAny>>, step_cap: Option<usize>) {
    let mut faults: StableHashMap<usize, String> = StableHashMap::default();
    // For each solver whose task read: its index in `found`, the indices in its streams of the due streams, and their ids.
    let mut due: Vec<(usize, Vec<usize>, Vec<Vec<(u32, Emitter)>>)> = Vec::new();
    for (solver, (id, streams, _)) in found.iter().enumerate() {
        match reads.get(id) {
            None => {}
            Some(Err(fault)) => {
                faults.insert(solver, fault.clone());
            }
            Some(Ok(_)) => {
                let wanted: Vec<usize> = (0..streams.len()).filter(|&stream| matches!(streams[stream].masks, Ok(None))).collect();
                let ids = wanted.iter().map(|&stream| streams[stream].ids.clone()).collect();
                due.push((solver, wanted, ids));
            }
        }
    }
    let solvers: Vec<UnitSolver<'_>> = due
        .iter()
        .map(|(solver, _, ids)| {
            let Some(Ok((task, judged))) = reads.get(&found[*solver].0) else { unreachable!("a solver of `due` has a task that read") };
            UnitSolver { task, judged, streams: ids, units: None }
        })
        .collect();
    let progress = Progress::new(started, ended, due.iter().map(|(solver, _, _)| found[*solver].0.as_str()).collect(), due.iter().map(|(_, wanted, _)| wanted.len()).collect());
    let results = replay_units_untested_ends(
        &solvers,
        constructions,
        &DecodeSettings::default(),
        true,
        corpus_threads(),
        steps,
        &|(rows, masks): &mut (usize, Vec<u8>), decoder, stepped| {
            let masked = stepped.mask.expect("the replay computes the mask");
            *rows += 1;
            masks.extend(mask_bytes(masked.mask, decoder.vocabulary().len()));
        },
        &|solver| progress.start(solver),
        &|_, _, replay| replay.into_result(),
        &|solver| progress.settle(solver),
        step_cap,
    );
    let mut sets = Vec::new();
    for ((solver, wanted, _), outs) in due.iter().zip(results) {
        sets.extend(wanted.iter().zip(outs).map(|(&stream, out)| (*solver, stream, out)));
    }
    for (solver, stream, out) in sets {
        let stream = &mut found[solver].1[stream];
        stream.masks = out.and_then(|out| out).map(|(rows, masks)| {
            // The tokens from the first one the model emits after the decode's end are no part of the program the decode reads.
            let end = stream.ids.iter().enumerate().filter(|(_, (_, emitter))| *emitter == Emitter::Model).nth(rows).map(|(index, _)| index);
            if let Some(end) = end {
                stream.ids.truncate(end);
            }
            Some(masks)
        });
    }
    for (solver, fault) in faults {
        for stream in &mut found[solver].1 {
            stream.masks = Err(fault.clone());
        }
    }
}
