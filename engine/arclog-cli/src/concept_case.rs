//! The concept case of a solver of the corpus, checked and set up for its
//! run on its task at its stored `param` records, which `lib-compare`,
//! `speed` and `determinism` run, and the parts of that
//! setup that `determine` shares for each base case: the read of the solver
//! and its task, the check of a case, and the session and limits of a run.

use std::path::Path;
use std::time::Instant;

use arclog::check::{CheckCache, CheckedProgram, SolverClauses};
use arclog::eval::{output_relation, Caps, Cancellation, Evaluation, Limits, Outcome, ParameterValues};
use arclog::harness::read_corpus_solver;
use arclog::judge::candidates::World;
use arclog::judge::run::{judged_run, Depth, JudgedRun};
use arclog::registry::Registry;
use arclog::eval::instance::Constructions;
use arclog::judge::determination::DeterminedCase;
use arclog::resolver::resolve_cases;
use arclog::session::{SessionBound, TaskSession};
use arclog::solver::{CaseName, Solver};
use arclog::task::{read_judged_task, read_task, JudgedTask, Task};

use arclog::session::SESSION_BYTES;
use arclog::stream::corpus::check_case;
use arclog_constructions::shared as constructions;

/// The concept case of a solver, set up for its run at its stored `param`
/// records, over the table of the lib's constructions, with the task's pairs
/// as the judge reads them.
pub(crate) struct ConceptCase<'a> {
    pub(crate) evaluation: Evaluation<'a>,
    pub(crate) judged: &'a JudgedTask,
}

impl ConceptCase<'_> {
    /// The judged run of `&output` on the task, closed-world, with the full
    /// output set on each pair, and the run's seconds.
    pub(crate) fn run(&self) -> (Outcome<JudgedRun>, f64) {
        let start = Instant::now();
        let output = output_relation(self.evaluation.program).expect("a checked case program derives `&output`");
        let run = judged_run(&self.evaluation, &output, self.judged, World::Closed, Depth::Full);
        (run, start.elapsed().as_secs_f64())
    }
}

/// A solver of the corpus with its task, as a run reads it and as the
/// judge reads its pairs.
pub(crate) struct CorpusTask {
    pub(crate) solver: std::sync::Arc<Solver>,
    pub(crate) task: Task,
    pub(crate) judged: JudgedTask,
}

/// The solver `id` of `corpus` with its task in `tasks`, or the fault that
/// stops its read.
pub(crate) fn read_corpus_task(corpus: &Path, tasks: &Path, id: &str) -> Result<CorpusTask, String> {
    let solver = read_corpus_solver(corpus, id).ok_or("the solver's files do not read")?;
    let path = tasks.join(format!("{id}.json"));
    let task = read_task(&path).map_err(|error| format!("the task does not read: {error:?}"))?;
    let judged = read_judged_task(&path).map_err(|error| format!("the task's pairs do not read: {error:?}"))?;
    Ok(CorpusTask { solver, task, judged })
}

/// The task session of a run over the corpus, under the corpus's caps.
pub(crate) fn corpus_session() -> TaskSession {
    TaskSession::new(SessionBound { bytes: SESSION_BYTES }, Caps::CORPUS)
}

/// The limits of a run over the corpus: no deadline, and a cancellation
/// that nothing cancels.
pub(crate) fn corpus_limits() -> Limits {
    Limits { deadline: None, cancellation: Cancellation::default() }
}

/// What `body` gives on the concept case of the solver `id` of `corpus`,
/// on its task in `tasks`, or the fault that stops the case's setup.
pub(crate) fn with_concept_case<T>(corpus: &Path, tasks: &Path, id: &str, body: impl FnOnce(&ConceptCase<'_>) -> Result<T, String>) -> Result<T, String> {
    let CorpusTask { solver, task, judged } = read_corpus_task(corpus, tasks, id)?;
    let registry = Registry::get();
    let cases = resolve_cases(&solver, registry);
    let clauses = SolverClauses::of_cases(&cases);
    let concept = cases.concept();
    let program = check_case(concept, &clauses, &mut CheckCache::default(), "the concept case")?;
    let parameters = ParameterValues::stored(solver.arcdata.value());
    let session = corpus_session();
    let limits = corpus_limits();
    let evaluation = Evaluation { program: &program, concept: None, task: &task, parameters: &parameters, session: &session, registry, constructions: constructions()?, limits: &limits };
    body(&ConceptCase { evaluation, judged: &judged })
}

/// The cases of `programs` as the determination takes them, on the task
/// `task` in `session`.
pub(crate) fn determined_cases<'a>(
    programs: &'a [(CaseName, CheckedProgram)],
    concept: &'a CheckedProgram,
    task: &'a Task,
    session: &'a TaskSession,
    constructions: &'a Constructions,
    limits: &'a Limits,
) -> Vec<DeterminedCase<'a>> {
    programs
        .iter()
        .map(|(name, program)| DeterminedCase { name, program, concept, task, session, registry: Registry::get(), constructions, limits })
        .collect()
}
