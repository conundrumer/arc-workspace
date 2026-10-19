//! The concept case of a solver of the corpus, checked and set up for its
//! run on its task at its stored `param` records, which `compare`,
//! `lib-compare`, `speed` and `determinism` run.

use std::path::Path;
use std::time::Instant;

use arclog::check::{check_shared_program, CheckCache, SolverClauses};
use arclog::eval::{output_relation, Caps, Cancellation, Evaluation, Limits, Outcome, ParameterValues};
use arclog::harness::read_corpus_solver;
use arclog::judge::candidates::World;
use arclog::judge::run::{judged_run, Depth, JudgedRun};
use arclog::registry::Registry;
use arclog::resolver::resolve_cases;
use arclog::session::{SessionBound, TaskSession};
use arclog::solver::{Case, Solver};
use arclog::task::{read_judged_task, read_task, JudgedTask};

use crate::engine_run::{constructions, SESSION_BYTES};

/// The concept case of a solver, set up for its run at its stored `param`
/// records, over the table of the lib's constructions, with the solver, the
/// case and the task's pairs as the judge reads them.
pub(crate) struct ConceptCase<'a> {
    pub(crate) evaluation: Evaluation<'a>,
    pub(crate) solver: &'a Solver,
    pub(crate) case: &'a Case,
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

/// What `body` gives on the concept case of the solver `id` of `corpus`,
/// on its task in `tasks`, or the fault that stops the case's setup.
pub(crate) fn with_concept_case<T>(corpus: &Path, tasks: &Path, id: &str, body: impl FnOnce(&ConceptCase<'_>) -> Result<T, String>) -> Result<T, String> {
    let solver = read_corpus_solver(corpus, id).ok_or("the solver's files do not read")?;
    let path = tasks.join(format!("{id}.json"));
    let task = read_task(&path).map_err(|error| format!("the task does not read: {error:?}"))?;
    let judged = read_judged_task(&path).map_err(|error| format!("the task's pairs do not read: {error:?}"))?;
    let registry = Registry::get();
    let cases = resolve_cases(&solver, registry);
    let clauses = SolverClauses::of_cases(&cases);
    let concept = cases.concept();
    let program = check_shared_program(std::sync::Arc::clone(&concept.resolved.value), &clauses, registry, &mut CheckCache::default()).map_err(|refusals| {
        let messages: Vec<&str> = refusals.iter().map(|d| &*d.message).collect();
        format!("the checker refuses the concept case: {}", messages.join("; "))
    })?;
    let parameters = ParameterValues::stored(solver.arcdata.value());
    let session = TaskSession::new(SessionBound { bytes: SESSION_BYTES }, Caps::CORPUS);
    let limits = Limits { deadline: None, cancellation: Cancellation::default() };
    let evaluation = Evaluation { program: &program, task: &task, parameters: &parameters, session: &session, registry, constructions: constructions()?, limits: &limits };
    body(&ConceptCase { evaluation, solver: &solver, case: &concept.case, judged: &judged })
}
