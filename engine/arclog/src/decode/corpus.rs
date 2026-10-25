//! The walk of a solver of a corpus that records the tables of its case
//! programs: the read of the solver and its task, the check of each wanted
//! case, and, for each case whose stream the decoder takes, the tables of
//! each step of its replay with the index of the step's token. The
//! `arclog-cli` commands that replay a corpus and the Python package share
//! the read of the task and the session of the run.

use std::panic::{catch_unwind, AssertUnwindSafe};
use std::path::Path;
use std::cell::Cell;
use std::sync::atomic::{AtomicUsize, Ordering};
use std::sync::Arc;

use super::replay::{replay_from, Stepped};
use super::{Consistency, Decoder, Points, Table};
use crate::eval::determinations::relation_spelled;
use crate::eval::ReachedBound;
use crate::eval::instance::Constructions;
use crate::eval::Caps;
use crate::harness::{panic_message, read_corpus_solver, run_on_workers};
use crate::judge::candidates::{PairCandidates, Section, World};
use crate::program::ProgramRelation;
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
    let solver = read_corpus_solver(corpus, id).map_err(|e| format!("the solver's files do not read: {e}"))?;
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

/// A wanted case of a solver with what its replay gave: the replay of its
/// stream, or the writer's fault.
struct ReplayedCase<T> {
    case: String,
    concept: bool,
    /// The replay with the relation declared at each slot of the stream.
    replay: Result<(StreamReplay<T>, Vec<ProgramRelation>), String>,
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
    let wanted = if all { WantedCases::All } else { WantedCases::Concept };
    let (train, replayed) = replay_streams(corpus, tasks, id, wanted, constructions, settings, masked, record)?;
    let cases = replayed.into_iter().map(|case| CaseReplay { case: case.case, concept: case.concept, outcome: case.replay.and_then(|(replay, _)| replay.into_result()) }).collect();
    Ok(SolverReplay { train, cases })
}

/// The count of train pairs of the task `id` and, for each wanted case of the
/// solver that holds no `DEMONSTRATED` form, the replay of its stream, as
/// [`replay_prefix_tree`] gives it.
fn replay_streams<T: Default + Clone>(
    corpus: &Path,
    tasks: &Path,
    id: &str,
    wanted: WantedCases<'_>,
    constructions: &Constructions,
    settings: &DecodeSettings,
    masked: bool,
    record: &dyn Fn(&mut T, &Decoder<'_>, Stepped<'_>),
) -> Result<(usize, Vec<ReplayedCase<T>>), String> {
    let vocabulary = Vocabulary::new(Registry::get(), &DecodeSettings::default());
    let cases = solver_streams(corpus, id, wanted, &vocabulary)?;
    let (task, judged) = read_task_files(tasks, id)?;
    let cases: Vec<CaseStream> = cases.into_iter().filter(|case| !case.demonstrated).collect();
    let ids: Vec<Vec<(u32, Emitter)>> = cases.iter().filter_map(|case| case.stream.as_ref().ok()).map(|stream| token_ids(&stream.tokens, &vocabulary)).collect();
    let mut outcomes = replay_prefix_tree(&task, &judged, &ids, constructions, settings, masked, record).into_iter();
    let replayed = cases
        .into_iter()
        .map(|case| ReplayedCase {
            case: case.case,
            concept: case.concept,
            replay: match case.stream {
                Ok(stream) => Ok((outcomes.next().expect("an outcome for each stream"), stream.relations)),
                Err(fault) => Err(fault),
            },
        })
        .collect();
    Ok((task.train.len(), replayed))
}

/// What a case's replay ends on, from the consistency of the last `RULE`
/// clause its stream ends.
#[derive(Clone, Debug, PartialEq)]
pub enum Verdict {
    Consistent,
    NotConsistent,
    /// The relation whose several values keep every train pair consistent,
    /// spelled by `relation_spelled` as the case program the stream is
    /// written from names it: `&x` for a declared relation, `&owner.port` for
    /// an output.
    SeveralValues(String),
    /// The message of the run fault.
    Fault(String),
    Stopped(ReachedBound),
    /// The stream ends no `RULE` clause.
    NoRule,
    /// The decoder refuses the stream, or it ends while the engine forces tokens.
    Refused(String),
    /// The writer gives the case no stream.
    NoStream(String),
}

/// The verdict of one case, with the index of the token that ends the last
/// `RULE` clause the replay reached.
#[derive(Clone, Debug, PartialEq)]
pub struct CaseVerdict {
    pub case: String,
    pub concept: bool,
    pub verdict: Verdict,
    pub token: Option<usize>,
}

/// The verdict of each case of the solver `id` of `corpus` on its task in
/// `tasks`, every case of the solver that holds no `DEMONSTRATED` form (the
/// combinations its `exclude` forms leave out are no cases), replayed with the
/// default settings and no token mask; or the fault that stops the solver.
pub fn solver_verdicts(corpus: &Path, tasks: &Path, id: &str, constructions: &Constructions) -> Result<Vec<CaseVerdict>, String> {
    let record = |last: &mut Option<(usize, Recorded)>, decoder: &Decoder<'_>, stepped: Stepped<'_>| {
        let verdict = match &stepped.consistency {
            None => return,
            Some(Consistency::Consistent { .. }) => Recorded::Ended(Verdict::Consistent),
            Some(Consistency::NotConsistent) => Recorded::Ended(Verdict::NotConsistent),
            Some(Consistency::SeveralValues { relation, .. }) => Recorded::Slot(
                decoder.relation_slot(relation).expect("the writer takes the decoder's slots, so a relation the decoder tests stands at a slot of the stream's table"),
            ),
            Some(Consistency::Fault(fault)) => Recorded::Ended(Verdict::Fault(fault.message.to_string())),
            Some(Consistency::Stopped(stop)) => Recorded::Ended(Verdict::Stopped(stop.bound)),
        };
        *last = Some((stepped.index, verdict));
    };
    let settings = DecodeSettings::corpus();
    let run = || replay_streams(corpus, tasks, id, WantedCases::Cases, constructions, &settings, false, &record);
    // The spelling of a slot runs inside `catch_unwind` as well, so a slot outside the table is the solver's fault.
    let verdicts = || {
        let (_, replayed) = run()?;
        Ok(replayed
            .into_iter()
            .map(|case| {
                let (verdict, token) = match case.replay {
                    Err(fault) => (Verdict::NoStream(fault), None),
                    Ok((StreamReplay { fault: Some(message), record }, _)) => (Verdict::Refused(message), record.map(|(index, _)| index)),
                    Ok((StreamReplay { fault: None, record: None }, _)) => (Verdict::NoRule, None),
                    Ok((StreamReplay { fault: None, record: Some((index, recorded)) }, relations)) => {
                        let verdict = match recorded {
                            Recorded::Ended(verdict) => verdict,
                            Recorded::Slot(slot) => Verdict::SeveralValues(relation_spelled(relations.get(slot as usize).expect("the slot of a relation the decoder tests stands in the stream's table"))),
                        };
                        (verdict, Some(index))
                    }
                };
                CaseVerdict { case: case.case, concept: case.concept, verdict, token }
            })
            .collect())
    };
    catch_unwind(AssertUnwindSafe(verdicts)).unwrap_or_else(|payload| Err(replay_panic(&*payload)))
}

/// What a step of a case records: a verdict that needs nothing more, or the
/// slot of the relation whose several values keep every pair consistent,
/// which the case's slot table spells.
#[derive(Clone, Debug, PartialEq)]
enum Recorded {
    Ended(Verdict),
    Slot(u32),
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

/// The [`StreamReplay`] of each of `streams`, token ids with their
/// emitters, in the order of `streams`, as `replay` gives it on a decoder
/// that judges the train pairs of `judged` under `settings`, the
/// constructions `constructions`, and a corpus session of this call's own.
/// `record` runs after each step of a token the model emits, with the
/// stream's record, which starts as `T::default()`. A stream whose replay is
/// refused keeps the record of the model steps before the refused token, with
/// the refusal's message as its fault; a stream that ends while the engine
/// forces tokens keeps its whole record. The replay computes the
/// token mask before each step where `masked` holds. The streams are
/// replayed in the order of [`sorted_streams`] as a prefix tree: the token
/// mask and the step of a prefix that streams share run once: a replay
/// leaves a checkpoint at each prefix that a later stream shares with it,
/// past the position it resumed from, and each stream resumes from a fork
/// of the decoder and a clone of the record at the checkpoint of the
/// prefix it shares with the stream before it. A stream equal to the one before takes a
/// clone of its outcome; a checkpoint stands at the position the replay
/// reached, which is the end of the program the decode reads where that is
/// before the shared prefix's end ([`super::replay::Replayed::end`]); and a stream that shares the prefix through the
/// token at which the one before was refused is refused at that token.
pub fn replay_prefix_tree<T: Default + Clone>(
    task: &Task,
    judged: &JudgedTask,
    streams: &[Vec<(u32, Emitter)>],
    constructions: &Constructions,
    settings: &DecodeSettings,
    masked: bool,
    record: &dyn Fn(&mut T, &Decoder<'_>, Stepped<'_>),
) -> Vec<StreamReplay<T>> {
    let registry = Registry::get();
    let session = corpus_session();
    let train: Arc<[PairCandidates<'_>]> = judged.train.iter().map(|pair| PairCandidates::of(pair, Section::Train, World::Closed)).collect();
    let root = Decoder::new(task, &session, registry, constructions, settings).judging(train);
    let order = sorted_streams(streams);
    let mut outcomes: Vec<Option<StreamReplay<T>>> = streams.iter().map(|_| None).collect();
    // The index in a stream of the token at which its replay was refused.
    let mut refused_at: Vec<Option<usize>> = vec![None; streams.len()];
    // The prefix that each stream shares with the stream before it.
    let shared_with_before: Vec<usize> =
        order.iter().enumerate().map(|(rank, &index)| rank.checked_sub(1).map_or(0, |before| common_prefix(&streams[order[before]], &streams[index]))).collect();
    let mut stack: Vec<Checkpoint<'_, T>> = Vec::new();
    for (rank, &index) in order.iter().enumerate() {
        let stream = &streams[index];
        let before = rank.checked_sub(1).map(|before| order[before]);
        let shared = shared_with_before[rank];
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
        // The prefixes past `position` that later streams share with this one,
        // in increasing order: a later stream shares with this one the least
        // of the prefixes that the streams from this one to it share in turn.
        let mut targets = Vec::new();
        let mut least = stream.len();
        for &next in &shared_with_before[rank + 1..] {
            least = least.min(next);
            if least <= position {
                break;
            }
            if targets.last() != Some(&least) {
                targets.push(least);
            }
        }
        let mut result = Ok(());
        for &target in targets.iter().rev() {
            match run(&mut decoder, &tokens[..target], position, forced.clone(), &mut recording) {
                Ok(replayed) => {
                    position = replayed.end();
                    forced = replayed.forced().to_vec();
                    stack.push(Checkpoint { position, decoder: decoder.fork(), forced: forced.clone(), record: recording.clone() });
                    if position < target {
                        break;
                    }
                }
                Err(refused) => {
                    result = Err(refused);
                    break;
                }
            }
        }
        let result = result.and_then(|()| run(&mut decoder, &tokens, position, forced, &mut recording));
        match result {
            Ok(replayed) => outcomes[index] = Some(StreamReplay { fault: replayed.unfinished(), record: recording }),
            Err(refused) => {
                refused_at[index] = Some(refused.index);
                outcomes[index] = Some(StreamReplay { record: recording, fault: Some(refused.message) });
            }
        }
    }
    outcomes.into_iter().map(|outcome| outcome.expect("each stream has an outcome")).collect()
}

/// What the replay of one stream gives: the record it built, and the line of
/// the refusal, or of the unfinished end, that stopped it where one did.
#[derive(Clone, Debug, PartialEq)]
pub struct StreamReplay<T> {
    /// The record of each model step the replay took. Where the replay was
    /// refused at a token, it holds the steps before that token; where the
    /// stream ended while the engine forces tokens, it holds the whole stream.
    pub record: T,
    /// The refusal of a token, or [`Replayed::unfinished`](super::replay::Replayed::unfinished), that stopped the replay.
    pub fault: Option<String>,
}

impl<T> StreamReplay<T> {
    /// The record where the replay had no fault, and the fault, with its
    /// record dropped, where it had one.
    pub fn into_result(self) -> Result<T, String> {
        self.fault.map_or(Ok(self.record), Err)
    }
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

/// The model steps of a call of [`replay_units`]: how many its units hold in
/// all, and how many its workers have done. Another thread may read both while
/// the call runs.
#[derive(Debug, Default)]
pub struct ReplayProgress {
    total: AtomicUsize,
    done: AtomicUsize,
}

impl ReplayProgress {
    /// The model steps of all the call's units, 0 until the units are cut.
    pub fn total(&self) -> usize {
        self.total.load(Ordering::Relaxed)
    }

    /// The model steps done so far, at most [`total`](Self::total).
    pub fn done(&self) -> usize {
        self.done.load(Ordering::Relaxed)
    }
}

/// Replays the streams of `solvers`, as [`replay_prefix_tree`] does under
/// `settings`, on the
/// workers of [`run_on_workers`]. The streams of each solver are cut, in
/// the order of [`sorted_streams`], into units of consecutive streams, so
/// that no unit passes [`UNIT_STEPS`] model steps but by its last stream's,
/// and the units run largest first, each in a session of its
/// own and under `catch_unwind`. As a unit starts, its worker calls
/// `started` with the solver's index in `solvers`. As a unit ends, its worker calls `ended`
/// with the solver's index in `solvers` and the [`StreamReplay`] of each of the
/// unit's streams, refused or not, and the stream's result is what `ended`
/// gives. Once a stream's replay ends, whether it gives a record or a fault,
/// its worker calls `settled` with the solver's index.
///
/// `progress` is set to the model steps of all the units once they are cut,
/// and its done count grows by one at each step of a unit's replay. As a unit
/// ends, whatever way, its done count is the unit's steps, so a stream that
/// is refused early or shares a prefix leaves the count exact.
///
/// With `step_cap`, a solver's streams, in the order of [`sorted_streams`],
/// replay up to the last one at which the model steps of the prefix tree of
/// the solver's streams so far stay within the cap. Each later stream of the
/// solver replays nothing: its result is a fault that gives the cap and the
/// model steps of the solver's streams in all, and `settled` is called for it
/// before any worker starts.
///
/// Where a unit's replay panics, each of its streams replays alone, in a
/// session of its own and under `catch_unwind`: `started` is not called again,
/// `ended` is called for each stream that gives an outcome, and a stream whose
/// replay alone panics has as its result the fault of [`replay_panic`].
///
/// Gives, for each solver, the result of each of its streams in the order of
/// `streams`.
pub fn replay_units<T: Default + Clone, U: Send>(
    solvers: &[UnitSolver<'_>],
    constructions: &Constructions,
    settings: &DecodeSettings,
    masked: bool,
    progress: &ReplayProgress,
    record: &(dyn Fn(&mut T, &Decoder<'_>, Stepped<'_>) + Sync),
    started: &(dyn Fn(usize) + Sync),
    ended: &(dyn Fn(usize, StreamReplay<T>) -> U + Sync),
    settled: &(dyn Fn(usize) + Sync),
    step_cap: Option<usize>,
) -> Vec<Vec<Result<U, String>>> {
    let mut sorted: Vec<Vec<usize>> = solvers.iter().map(|solver| sorted_streams(solver.streams)).collect();
    // For each solver: the indices in its streams of the streams past the cap, and the fault each gives.
    let mut capped: Vec<(Vec<usize>, String)> = solvers.iter().map(|_| (Vec::new(), String::new())).collect();
    let mut units = Vec::new();
    for (index, (solver, order)) in solvers.iter().zip(&mut sorted).enumerate() {
        if let Some(cap) = step_cap {
            let (mut total, mut kept) = (0, None);
            let mut last: Option<&[(u32, Emitter)]> = None;
            for (rank, &stream) in order.iter().enumerate() {
                let ids = solver.streams[stream].as_slice();
                total += new_model_steps(last, ids);
                last = Some(ids);
                if total > cap && kept.is_none() {
                    kept = Some(rank);
                }
            }
            if let Some(kept) = kept {
                let line = format!("the replay's cap of {cap} model steps stops the solver's streams at this one: the solver's streams take {total} model steps");
                capped[index] = (order.split_off(kept), line);
                for _ in &capped[index].0 {
                    settled(index);
                }
            }
        }
        let mut unit = ReplayUnit { solver: index, streams: Vec::new(), steps: 0 };
        let mut last: Option<&[(u32, Emitter)]> = None;
        for &stream in order.iter() {
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
    progress.total.store(units.iter().map(|unit| unit.steps).sum(), Ordering::Relaxed);
    let outcomes = run_on_workers(&units, |unit| {
        let solver = &solvers[unit.solver];
        started(unit.solver);
        let ids: Vec<Vec<(u32, Emitter)>> = unit.streams.iter().map(|&stream| solver.streams[stream].clone()).collect();
        // The steps of this unit counted into `progress`, at most `unit.steps`.
        let counted = Cell::new(0);
        let counting = |recording: &mut T, decoder: &Decoder<'_>, stepped: Stepped<'_>| {
            record(recording, decoder, stepped);
            if counted.get() < unit.steps {
                counted.set(counted.get() + 1);
                progress.done.fetch_add(1, Ordering::Relaxed);
            }
        };
        let finish = |outcome: StreamReplay<T>| {
            let out = catch_unwind(AssertUnwindSafe(|| ended(unit.solver, outcome))).map_err(|payload| replay_panic(&*payload));
            settled(unit.solver);
            out
        };
        let replayed = catch_unwind(AssertUnwindSafe(|| replay_prefix_tree(solver.task, solver.judged, &ids, constructions, settings, masked, &counting)));
        let outs: Vec<Result<U, String>> = match replayed {
            Ok(outcomes) => outcomes.into_iter().map(finish).collect(),
            // The unit's replay panicked: each stream replays alone, so a panic faults the stream that causes it.
            Err(_) => ids
                .iter()
                .map(|stream| match catch_unwind(AssertUnwindSafe(|| replay_prefix_tree(solver.task, solver.judged, std::slice::from_ref(stream), constructions, settings, masked, &counting))) {
                    Ok(outcomes) => finish(outcomes.into_iter().next().expect("an outcome for the one stream")),
                    Err(payload) => {
                        settled(unit.solver);
                        Err(replay_panic(&*payload))
                    }
                })
                .collect(),
        };
        progress.done.fetch_add(unit.steps - counted.get(), Ordering::Relaxed);
        outs
    });
    let mut results: Vec<Vec<Option<Result<U, String>>>> = solvers.iter().map(|solver| solver.streams.iter().map(|_| None).collect()).collect();
    for (solver, (streams, line)) in capped.iter().enumerate() {
        for &stream in streams {
            results[solver][stream] = Some(Err(line.clone()));
        }
    }
    for (unit, outs) in units.iter().zip(outcomes) {
        for (&stream, out) in unit.streams.iter().zip(outs) {
            results[unit.solver][stream] = Some(out);
        }
    }
    results.into_iter().map(|results| results.into_iter().map(|result| result.expect("a result for each stream")).collect()).collect()
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
