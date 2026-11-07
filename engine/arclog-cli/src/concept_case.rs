//! A case of a solver of the corpus, the concept case or the case that a
//! snapshot's key names, checked and set up for its run on its task at its
//! stored `param` records, with each `DET` by its clauses read from its
//! clause. It holds the parts of that setup that its callers share: the read
//! of the solver and its task, the check of a case, the case sets
//! (`determined_cases`) and the limits of a run (`corpus_limits`).

use std::path::Path;
use std::time::Instant;

use arclog::check::{CheckCache, CheckedProgram, SolverClauses};
use arclog::eval::{output_relation, Cancellation, Evaluation, Limits, Outcome, ParameterValues};
use arclog::decode::corpus::{corpus_session, read_corpus_task, CorpusTask};
use arclog::judge::candidates::World;
use arclog::judge::run::{judged_run, Depth, JudgedRun};
use arclog::registry::Registry;
use arclog::eval::instance::Constructions;
use arclog::judge::determination::DeterminedCase;
use arclog::resolver::resolve_cases;
use arclog::session::TaskSession;
use arclog::solver::CaseName;
use arclog::task::{JudgedTask, Task};

use arclog::stream::corpus::check_case;
use arclog_constructions::shared as constructions;

use crate::compare::names_case;

/// The snapshot's key of the concept case.
const CONCEPT: &str = "concept";

/// A case of a solver (`with_concept_case`, `with_case`), set up for its run
/// at its stored `param` records, with each `DET` by its clauses read from
/// its clause, over the table of the lib's constructions, with the task's
/// pairs as the judge reads them.
pub(crate) struct ConceptCase<'a> {
    pub(crate) evaluation: Evaluation<'a>,
    pub(crate) judged: &'a JudgedTask,
    /// The name of the alt that the case takes at each `ALTS` form it reaches
    /// (`CaseName`), as the arclog file writes it.
    pub(crate) alts: Vec<String>,
}

impl ConceptCase<'_> {
    /// The judged run of the `OUT` form's relation on the task, closed-world, with the full
    /// output set on each pair, and the run's seconds.
    pub(crate) fn run(&self) -> (Outcome<JudgedRun>, f64) {
        let start = Instant::now();
        let output = output_relation(self.evaluation.program).expect("a checked case program holds an `OUT` form");
        let run = judged_run(&self.evaluation, &output, self.judged, World::Closed, Depth::Full);
        (run, start.elapsed().as_secs_f64())
    }
}

/// The limits of a run over the corpus: the default request work cap, and a
/// cancellation that nothing cancels.
pub(crate) fn corpus_limits() -> Limits {
    Limits::new(None, Cancellation::default())
}

/// What `body` gives on the concept case of the solver `id` of `corpus`,
/// on its task in `tasks`, or the fault that stops the case's setup.
pub(crate) fn with_concept_case<T>(corpus: &Path, tasks: &Path, id: &str, body: impl FnOnce(&ConceptCase<'_>) -> Result<T, String>) -> Result<T, String> {
    with_case(corpus, tasks, id, CONCEPT, body)
}

/// What `body` gives on the case of the solver `id` of `corpus` that the
/// snapshot's key `name` names (`names_case`), on its task in `tasks`, set
/// up as the concept case is, or the fault that stops the case's setup.
pub(crate) fn with_case<T>(corpus: &Path, tasks: &Path, id: &str, name: &str, body: impl FnOnce(&ConceptCase<'_>) -> Result<T, String>) -> Result<T, String> {
    let CorpusTask { solver, task, judged } = read_corpus_task(corpus, tasks, id)?;
    let registry = Registry::get();
    let cases = resolve_cases(&solver, registry);
    let clauses = SolverClauses::of_cases(&cases);
    let chosen = if name == CONCEPT { Some(cases.concept()) } else { cases.resolved().find(|case| names_case(name, &solver.departures(&case.case.name))) };
    let chosen = chosen.ok_or_else(|| format!("the solver has no case named `{name}`"))?;
    let mut cache = CheckCache::default();
    let concept = check_case(&solver, cases.concept(), &clauses, &mut cache, "the concept case", false)?;
    let own;
    let program = if name == CONCEPT {
        &concept
    } else {
        own = check_case(&solver, chosen, &clauses, &mut cache, &format!("the case `{name}`"), false)?;
        &own
    };
    let parameters = ParameterValues::stored(solver.arcdata.value());
    let session = corpus_session();
    let limits = corpus_limits();
    let determined = DeterminedCase { name: &chosen.case.name, program, concept: &concept, task: &task, session: &session, registry, constructions: constructions()?, limits: &limits };
    body(&ConceptCase { evaluation: determined.evaluation(&parameters), judged: &judged, alts: chosen.case.name.0.iter().map(|alt| alt.0.to_string()).collect() })
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
