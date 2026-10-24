//! The walk of a solver of a corpus that records the tables of its case
//! programs: the read of the solver and its task, the check of each wanted
//! case, and, for each case whose stream the decoder takes, the tables of
//! each step of its replay with the index of the step's token. The
//! `arclog-cli` commands that replay a corpus and the Python package share
//! the read of the task and the session of the run.

use std::path::Path;
use std::sync::Arc;

use super::replay::{holds_demonstrated, replay};
use super::{Decoder, Points, Table};
use crate::check::{CheckCache, SolverClauses};
use crate::eval::instance::Constructions;
use crate::eval::Caps;
use crate::harness::read_corpus_solver;
use crate::judge::candidates::{PairCandidates, Section, World};
use crate::registry::Registry;
use crate::resolver::resolve_cases;
use crate::session::{SessionBound, TaskSession, SESSION_BYTES};
use crate::solver::Solver;
use crate::stream::corpus::{case_spelled, check_cases, decoded_cases};
use crate::stream::{token_stream, DecodeSettings};
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
    let path = tasks.join(format!("{id}.json"));
    let task = read_task(&path).map_err(|error| format!("the task does not read: {error:?}"))?;
    let judged = read_judged_task(&path).map_err(|error| format!("the task's pairs do not read: {error:?}"))?;
    Ok(CorpusTask { solver, task, judged })
}

/// The task session of a run over the corpus, under the corpus's caps.
pub fn corpus_session() -> TaskSession {
    TaskSession::new(SessionBound { bytes: SESSION_BYTES }, Caps::CORPUS)
}

/// The tables of one case of a solver, each with the index in the stream of
/// the token whose step gives it, or the fault that gives none.
#[derive(Debug)]
pub struct CaseTables {
    /// The case as [`case_spelled`] writes its name.
    pub case: String,
    /// Whether the case is the solver's concept case.
    pub concept: bool,
    /// The tables in the order of the stream, or why the stream gives none:
    /// the writer gives no stream, or the decoder refuses it.
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
/// order of the cases, with the lib's constructions `constructions`; or the
/// fault that stops the solver. A case that holds a `DEMONSTRATED` form is
/// left out.
pub fn solver_tables(corpus: &Path, tasks: &Path, id: &str, all: bool, points: Points, constructions: &Constructions) -> Result<SolverTables, String> {
    let CorpusTask { solver, task, judged } = read_corpus_task(corpus, tasks, id)?;
    let registry = Registry::get();
    let cases = resolve_cases(&solver, registry);
    let clauses = SolverClauses::of_cases(&cases);
    let decoded = decoded_cases(&cases, all);
    let programs = check_cases(&cases, &clauses, &mut CheckCache::default(), &|name| decoded.contains(name))?;
    let concept = &cases.concept().case.name;
    let settings = DecodeSettings::default();
    let train: Arc<[PairCandidates<'_>]> = judged.train.iter().map(|pair| PairCandidates::of(pair, Section::Train, World::Closed)).collect();
    let mut recorded = Vec::new();
    for (name, program) in &programs {
        if holds_demonstrated(program) {
            continue;
        }
        let session = corpus_session();
        let mut decoder = Decoder::new(&task, &session, registry, constructions, &settings).judging(Arc::clone(&train));
        let tables = token_stream(program, decoder.vocabulary()).map_err(|diagnostic| format!("the writer gives no stream: {}", diagnostic.message)).and_then(|stream| {
            let mut tables = Vec::new();
            let replayed = replay(&mut decoder, &stream, &mut |decoder, stepped| {
                tables.extend(decoder.tables(points).into_iter().map(|table| (stepped.index, table)));
                std::ops::ControlFlow::Continue(())
            })?;
            replayed.unfinished().map_or(Ok(tables), Err)
        });
        recorded.push(CaseTables { case: case_spelled(name), concept: name == concept, tables });
    }
    Ok(SolverTables { train: task.train.len(), cases: recorded })
}
