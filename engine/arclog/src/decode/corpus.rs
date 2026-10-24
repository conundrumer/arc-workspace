//! The walk of a solver of a corpus that records the tables of its case
//! programs: the read of the solver and its task, the check of each wanted
//! case, and, for each case whose stream the decoder takes, the tables of
//! each step of its replay with the index of the step's token. The
//! `arclog-cli` commands that replay a corpus and the Python package share
//! the read of the task and the session of the run.

use std::panic::{catch_unwind, AssertUnwindSafe};
use std::path::Path;
use std::sync::Arc;

use super::replay::{replay_from, Stepped};
use super::{Decoder, Points, Table};
use crate::eval::instance::Constructions;
use crate::eval::Caps;
use crate::harness::{panic_message, read_corpus_solver, run_on_workers};
use crate::judge::candidates::{PairCandidates, Section, World};
use crate::registry::Registry;
use crate::session::{SessionBound, TaskSession, SESSION_BYTES};
use crate::solver::Solver;
use crate::stream::corpus::{solver_streams, token_ids, CaseStream, WantedCases};
use crate::stream::{DecodeSettings, Emitter, Token, Vocabulary};
use crate::task::{read_judged_task, read_task, JudgedTask, Task};

/// A solver of the corpus with its task, as a run reads it and as the
/// judge reads its pairs.
pub struct CorpusTask {
    pub solver: Arc<Solver>,
    pub task: Task,
    pub judged: JudgedTask,
}

/// The solver `id` of `corpus` with its task in `tasks`, or the fault that
/// stops its read.
pub fn read_corpus_task(corpus: &Path, tasks: &Path, id: &str) -> Result<CorpusTask, String> {
    let solver = read_corpus_solver(corpus, id).ok_or("the solver's files do not read")?;
    let (task, judged) = read_task_files(tasks, id)?;
    Ok(CorpusTask { solver, task, judged })
}

/// The task `id` in `tasks`, and the same task as the judge reads its
/// pairs, or the fault that stops the read.
pub fn read_task_files(tasks: &Path, id: &str) -> Result<(Task, JudgedTask), String> {
    let path = tasks.join(format!("{id}.json"));
    let task = read_task(&path).map_err(|error| format!("the task does not read: {error:?}"))?;
    let judged = read_judged_task(&path).map_err(|error| format!("the task's pairs do not read: {error:?}"))?;
    Ok((task, judged))
}

/// The task session of a run over the corpus, under the corpus's caps.
pub fn corpus_session() -> TaskSession {
    TaskSession::new(SessionBound { bytes: SESSION_BYTES }, Caps::CORPUS)
}

/// The record of one case of a solver, or the fault that gives none.
#[derive(Debug)]
pub struct CaseReplay<T> {
    /// The case as [`case_spelled`](crate::stream::corpus::case_spelled) writes its name.
    pub case: String,
    /// Whether the case is the solver's concept case.
    pub concept: bool,
    /// What the recorder built over the case's replay, or why the stream
    /// gives none: the writer gives no stream, or the decoder refuses it.
    pub outcome: Result<T, String>,
}

/// The record of each wanted case of a solver, with the count of train
/// pairs of its task, which names an example.
#[derive(Debug)]
pub struct SolverReplay<T> {
    pub train: usize,
    pub cases: Vec<CaseReplay<T>>,
}

/// Replays each wanted case of the solver `id` of `corpus` on its task in
/// `tasks`, the concept case or, with `all`, every case, in the order of the
/// cases, through a decoder that judges the train pairs under `settings`,
/// the lib's constructions `constructions`, and the corpus's
/// session. The replay computes the token mask before each step where
/// `masked` holds. `record` runs after each step of a token the model emits,
/// with the case's record, which starts as `T::default()`. A case that holds
/// a `DEMONSTRATED` form is left out. Gives the fault that stops the solver,
/// which is the panic's message where the replay panics.
pub fn replay_solver<T: Default + Clone>(
    corpus: &Path,
    tasks: &Path,
    id: &str,
    all: bool,
    constructions: &Constructions,
    settings: &DecodeSettings,
    masked: bool,
    record: &dyn Fn(&mut T, &Decoder<'_>, Stepped<'_>),
) -> Result<SolverReplay<T>, String> {
    catch_unwind(AssertUnwindSafe(|| replay_cases(corpus, tasks, id, all, constructions, settings, masked, record))).unwrap_or_else(|payload| Err(replay_panic(&*payload)))
}

/// The fault of a solver whose replay panicked with `payload`.
pub fn replay_panic(payload: &(dyn std::any::Any + Send)) -> String {
    format!("the replay panicked: {}", panic_message(payload).unwrap_or("a payload that is not a message"))
}

fn replay_cases<T: Default + Clone>(
    corpus: &Path,
    tasks: &Path,
    id: &str,
    all: bool,
    constructions: &Constructions,
    settings: &DecodeSettings,
    masked: bool,
    record: &dyn Fn(&mut T, &Decoder<'_>, Stepped<'_>),
) -> Result<SolverReplay<T>, String> {
    let vocabulary = Vocabulary::new(Registry::get(), &DecodeSettings::default());
    let cases = solver_streams(corpus, id, if all { WantedCases::All } else { WantedCases::Concept }, &vocabulary)?;
    let (task, judged) = read_task_files(tasks, id)?;
    let cases: Vec<CaseStream> = cases.into_iter().filter(|case| !case.demonstrated).collect();
    let ids: Vec<Vec<(u32, Emitter)>> = cases.iter().filter_map(|case| case.stream.as_ref().ok()).map(|stream| token_ids(stream, &vocabulary)).collect();
    let mut outcomes = replay_prefix_tree(&task, &judged, &ids, constructions, settings, masked, record).into_iter();
    let recorded = cases
        .into_iter()
        .map(|case| CaseReplay {
            case: case.case,
            concept: case.concept,
            outcome: match case.stream {
                Ok(_) => outcomes.next().expect("an outcome for each stream"),
                Err(fault) => Err(fault),
            },
        })
        .collect();
    Ok(SolverReplay { train: task.train.len(), cases: recorded })
}

/// The streams of `streams`, as indices, in the order of their
/// `(id, emitter)` sequences, which puts the streams that share a prefix
/// together. Equal streams keep their order.
pub fn sorted_streams(streams: &[Vec<(u32, Emitter)>]) -> Vec<usize> {
    let key = |stream: &Vec<(u32, Emitter)>| stream.iter().map(|(id, emitter)| (*id, *emitter == Emitter::Model)).collect::<Vec<_>>();
    let mut order: Vec<usize> = (0..streams.len()).collect();
    order.sort_by_cached_key(|&index| key(&streams[index]));
    order
}

/// The length of the longest prefix that `a` and `b` share.
fn common_prefix(a: &[(u32, Emitter)], b: &[(u32, Emitter)]) -> usize {
    a.iter().zip(b).take_while(|(x, y)| x == y).count()
}

/// The model's tokens that a replay of `stream` steps after the replay of
/// `previous`, which the prefix tree shares: those past the prefix the two
/// share. A replay computes one token mask for each, where it computes masks.
pub fn new_model_steps(previous: Option<&[(u32, Emitter)]>, stream: &[(u32, Emitter)]) -> usize {
    let shared = previous.map_or(0, |previous| common_prefix(previous, stream));
    stream[shared..].iter().filter(|(_, emitter)| *emitter == Emitter::Model).count()
}

/// The model's tokens that the prefix tree steps over `sorted`, streams in
/// the order of [`sorted_streams`]: for the first stream each token the
/// model writes, and for each later stream [`new_model_steps`] after the
/// stream before.
pub fn model_steps(sorted: &[&[(u32, Emitter)]]) -> usize {
    sorted.iter().enumerate().map(|(rank, stream)| new_model_steps(rank.checked_sub(1).map(|before| sorted[before]), stream)).sum()
}

/// A replay stopped at `position` of a stream: the decoder there, the
/// tokens the engine forces there, and the record so far.
struct Checkpoint<'a, T> {
    position: usize,
    decoder: Decoder<'a>,
    forced: Vec<Token>,
    record: T,
}

/// The outcome of the replay of each of `streams`, token ids with their
/// emitters, in the order of `streams`, as `replay` gives it on a decoder
/// that judges the train pairs of `judged` under `settings`, the
/// constructions `constructions`, and a corpus session of this call's own.
/// `record` runs after each step of a token the model emits, with the
/// stream's record, which starts as `T::default()`. The replay computes the
/// token mask before each step where `masked` holds. The streams are
/// replayed in the order of [`sorted_streams`] as a prefix tree: the token
/// mask and the step of a prefix that streams share run once, and each
/// stream that continues the prefix resumes from a fork of the decoder and
/// a clone of the record there. A stream equal to the one before takes a
/// clone of its outcome, and a stream that shares the prefix through the
/// token at which the one before was refused is refused at that token.
pub fn replay_prefix_tree<T: Default + Clone>(
    task: &Task,
    judged: &JudgedTask,
    streams: &[Vec<(u32, Emitter)>],
    constructions: &Constructions,
    settings: &DecodeSettings,
    masked: bool,
    record: &dyn Fn(&mut T, &Decoder<'_>, Stepped<'_>),
) -> Vec<Result<T, String>> {
    let registry = Registry::get();
    let session = corpus_session();
    let train: Arc<[PairCandidates<'_>]> = judged.train.iter().map(|pair| PairCandidates::of(pair, Section::Train, World::Closed)).collect();
    let root = Decoder::new(task, &session, registry, constructions, settings).judging(train);
    let order = sorted_streams(streams);
    let mut outcomes: Vec<Option<Result<T, String>>> = streams.iter().map(|_| None).collect();
    // The index in a stream of the token at which its replay was refused.
    let mut refused_at: Vec<Option<usize>> = vec![None; streams.len()];
    let mut stack: Vec<Checkpoint<'_, T>> = Vec::new();
    for (rank, &index) in order.iter().enumerate() {
        let stream = &streams[index];
        let before = rank.checked_sub(1).map(|before| order[before]);
        let shared = before.map_or(0, |before| common_prefix(&streams[before], stream));
        while stack.last().is_some_and(|checkpoint| checkpoint.position > shared) {
            stack.pop();
        }
        if let Some(before) = before {
            if streams[before] == *stream || refused_at[before].is_some_and(|at| shared > at) {
                outcomes[index] = outcomes[before].clone();
                refused_at[index] = refused_at[before];
                continue;
            }
        }
        // The prefix that the next stream of other tokens shares.
        let target = order[rank + 1..].iter().map(|&next| &streams[next]).find(|next| *next != stream).map_or(0, |next| common_prefix(stream, next));
        let tokens: Vec<(Token, Emitter)> =
            stream.iter().map(|(id, emitter)| (root.vocabulary().token(*id).expect("an id of the decoder's vocabulary").clone(), *emitter)).collect();
        let (mut decoder, mut position, mut forced, mut recording) = match stack.last() {
            Some(checkpoint) => (checkpoint.decoder.fork(), checkpoint.position, checkpoint.forced.clone(), checkpoint.record.clone()),
            None => (root.fork(), 0, Vec::new(), T::default()),
        };
        let run = |decoder: &mut Decoder<'_>, tokens: &[(Token, Emitter)], from: usize, forced: Vec<Token>, recording: &mut T| {
            replay_from(decoder, tokens, masked, from, forced, &mut |decoder, stepped| {
                record(recording, decoder, stepped);
                std::ops::ControlFlow::Continue(())
            })
        };
        let mut result = Ok(());
        if target > position {
            match run(&mut decoder, &tokens[..target], position, forced.clone(), &mut recording) {
                Ok(replayed) => {
                    position = target;
                    forced = replayed.forced().to_vec();
                    stack.push(Checkpoint { position, decoder: decoder.fork(), forced: forced.clone(), record: recording.clone() });
                }
                Err(refused) => result = Err(refused),
            }
        }
        let result = result.and_then(|()| run(&mut decoder, &tokens, position, forced, &mut recording));
        match result {
            Ok(replayed) => outcomes[index] = Some(replayed.unfinished().map_or(Ok(recording), Err)),
            Err(refused) => {
                refused_at[index] = Some(refused.index);
                outcomes[index] = Some(Err(refused.message));
            }
        }
    }
    outcomes.into_iter().map(|outcome| outcome.expect("each stream has an outcome")).collect()
}

/// A solver whose streams a call of [`replay_units`] replays: its task, the
/// task as the judge reads its pairs, and the token ids of its streams.
pub struct UnitSolver<'a> {
    pub task: &'a Task,
    pub judged: &'a JudgedTask,
    pub streams: &'a [Vec<(u32, Emitter)>],
}

/// A run of consecutive streams of one solver, in the order of
/// [`sorted_streams`], which one worker replays from a new decoder.
struct ReplayUnit {
    /// The index in the call's solvers of the solver.
    solver: usize,
    /// The indices in the solver's streams of the unit's streams.
    streams: Vec<usize>,
    /// The model's tokens that the unit's replay steps.
    steps: usize,
}

/// The model's steps at which [`replay_units`] ends a unit. It is a fixed
/// count, so the cut of a solver's streams into units depends on the solver
/// alone, and so does the numbering of the Idents that a unit's session
/// interns, whatever the thread count and whatever else the call holds.
pub const UNIT_STEPS: usize = 50_000;

/// Replays the streams of `solvers`, as [`replay_prefix_tree`] does under
/// `settings`, on the
/// workers of [`run_on_workers`]. The streams of each solver are cut, in
/// the order of [`sorted_streams`], into units of consecutive streams, so
/// that no unit passes [`UNIT_STEPS`] model steps but by its last stream's,
/// and the units run largest first, each in a session of its
/// own and under `catch_unwind`. As a unit ends, its worker calls `ended`
/// with the solver's index in `solvers` and the record of each of the unit's
/// streams that the replay takes, and the stream's result is what `ended`
/// gives. Once a stream's replay ends, whether it gives a record or a fault,
/// its worker calls `settled` with the solver's index.
///
/// Gives, for each solver, the result of each of its streams in the order of
/// `streams`, or the fault of [`replay_panic`] where one of its units
/// panicked.
pub fn replay_units<T: Default + Clone, U: Send>(
    solvers: &[UnitSolver<'_>],
    constructions: &Constructions,
    settings: &DecodeSettings,
    masked: bool,
    record: &(dyn Fn(&mut T, &Decoder<'_>, Stepped<'_>) + Sync),
    ended: &(dyn Fn(usize, T) -> U + Sync),
    settled: &(dyn Fn(usize) + Sync),
) -> Vec<Result<Vec<Result<U, String>>, String>> {
    let sorted: Vec<Vec<usize>> = solvers.iter().map(|solver| sorted_streams(solver.streams)).collect();
    let mut units = Vec::new();
    for (index, (solver, order)) in solvers.iter().zip(&sorted).enumerate() {
        let mut unit = ReplayUnit { solver: index, streams: Vec::new(), steps: 0 };
        let mut last: Option<&[(u32, Emitter)]> = None;
        for &stream in order {
            let ids = solver.streams[stream].as_slice();
            unit.streams.push(stream);
            unit.steps += new_model_steps(last, ids);
            last = Some(ids);
            if unit.steps >= UNIT_STEPS {
                units.push(std::mem::replace(&mut unit, ReplayUnit { solver: index, streams: Vec::new(), steps: 0 }));
                last = None;
            }
        }
        if !unit.streams.is_empty() {
            units.push(unit);
        }
    }
    units.sort_by(|a, b| b.steps.cmp(&a.steps));
    let outcomes = run_on_workers(&units, |unit| {
        let solver = &solvers[unit.solver];
        let ids: Vec<Vec<(u32, Emitter)>> = unit.streams.iter().map(|&stream| solver.streams[stream].clone()).collect();
        catch_unwind(AssertUnwindSafe(|| {
            replay_prefix_tree(solver.task, solver.judged, &ids, constructions, settings, masked, record)
                .into_iter()
                .map(|outcome| {
                    let out = outcome.map(|recorded| ended(unit.solver, recorded));
                    settled(unit.solver);
                    out
                })
                .collect::<Vec<_>>()
        }))
        .map_err(|payload| replay_panic(&*payload))
    });
    let mut results: Vec<Vec<Option<Result<U, String>>>> = solvers.iter().map(|solver| solver.streams.iter().map(|_| None).collect()).collect();
    let mut faults: Vec<Option<String>> = solvers.iter().map(|_| None).collect();
    for (unit, outcome) in units.iter().zip(outcomes) {
        match outcome {
            Ok(outs) => {
                for (&stream, out) in unit.streams.iter().zip(outs) {
                    results[unit.solver][stream] = Some(out);
                }
            }
            Err(fault) => {
                faults[unit.solver].get_or_insert(fault);
            }
        }
    }
    results
        .into_iter()
        .zip(faults)
        .map(|(results, fault)| match fault {
            Some(fault) => Err(fault),
            None => Ok(results.into_iter().map(|result| result.expect("a result for each stream")).collect()),
        })
        .collect()
}

/// The tables of one case of a solver, each with the index in the stream of
/// the token whose step gives it, or the fault that gives none.
#[derive(Debug)]
pub struct CaseTables {
    /// The case as [`case_spelled`](crate::stream::corpus::case_spelled) writes its name.
    pub case: String,
    /// Whether the case is the solver's concept case.
    pub concept: bool,
    /// The tables in the order of the stream, or why the stream gives none.
    pub tables: Result<Vec<(usize, Table)>, String>,
}

/// The tables of each wanted case of a solver, with the count of train
/// pairs of its task, which names an example.
#[derive(Debug)]
pub struct SolverTables {
    pub train: usize,
    pub cases: Vec<CaseTables>,
}

/// The tables, at `points`, of each case of the solver `id` of `corpus` on
/// its task in `tasks`, the concept case or, with `all`, every case, in the
/// order of the cases, with the lib's constructions `constructions`, under
/// `settings`; or the
/// fault that stops the solver. A case that holds a `DEMONSTRATED` form is
/// left out. The replay computes no token mask.
pub fn solver_tables(corpus: &Path, tasks: &Path, id: &str, all: bool, points: Points, constructions: &Constructions, settings: &DecodeSettings) -> Result<SolverTables, String> {
    let replayed = replay_solver(corpus, tasks, id, all, constructions, settings, false, &|tables: &mut Vec<(usize, Table)>, decoder, stepped| {
        tables.extend(decoder.tables(points).into_iter().map(|table| (stepped.index, table)));
    })?;
    let cases = replayed.cases.into_iter().map(|case| CaseTables { case: case.case, concept: case.concept, tables: case.outcome }).collect();
    Ok(SolverTables { train: replayed.train, cases })
}
