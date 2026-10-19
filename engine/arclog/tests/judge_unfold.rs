//! The judged run refuses a case whose `Unfold` instance's tied walks give
//! grids that a train pair does not accept, as
//! `docs/engine/cases.md#one-case` gives.

use std::path::Path;

use arclog::check::{check_shared_program, CheckCache, SolverClauses};
use arclog::eval::instance::Constructions;
use arclog::eval::{output_relation, Caps, Cancellation, Evaluation, Limits, ParameterValues};
use arclog::harness::read_corpus_solver;
use arclog::judge::candidates::World;
use arclog::judge::run::{judged_run, Depth, JudgedRun};
use arclog::registry::Registry;
use arclog::resolver::resolve_cases;
use arclog::session::{SessionBound, TaskSession};
use arclog::task::{read_judged_task, read_task};

/// From the seed cell, the instance takes one of the two other cells,
/// whose scores tie, and `&output` gives the taken cell the seed's color.
/// So the walks give `2 2 1` and `1 2 2`.
const ARCLOG: &str = "\
;; tie

(DET &seed RarestColor)

(RULE &seed_cell
  (input *P *Col)
  (&seed (:C Col)))

(INIT &state Unfold
  (start ((:t P))
    (&seed_cell *P))
  (initial_untaken ((:item P))
    (input *P)
    (NOT (&seed_cell P)))
  (score ((:t P) (:item X) (:S K))
    (&seed_cell *P)
    (input (:P *X))
    (NOT (&seed_cell (:P X)))
    (= *K 0)))

(RULE &taken
  (&state.take (:item *P)))

(RULE &output
  (OR ((input *P *Col)
       (NOT (&taken P)))
      ((&taken P)
       (&seed (:C Col)))))
";

const ARCDATA: &str = "\
;; tie

(param &seed Color (2))
";

/// The judged run of the solver above on a task whose one train pair and
/// one test pair have the input `1 2 1`, the output `2 2 1`, and `alt`, a
/// JSON alt or nothing.
fn run(dir: &Path, alt: &str) -> JudgedRun {
    std::fs::create_dir_all(dir).expect("a temporary directory");
    std::fs::write(dir.join("tie.arclog"), ARCLOG).expect("the arclog file");
    std::fs::write(dir.join("tie.arcdata"), ARCDATA).expect("the arcdata file");
    let pair = format!(r#"{{"input": [[1, 2, 1]], "output": [[2, 2, 1]]{alt}}}"#);
    let task_path = dir.join("tie.json");
    std::fs::write(&task_path, format!(r#"{{"train": [{pair}], "test": [{pair}]}}"#)).expect("the task file");
    let solver = read_corpus_solver(dir, "tie").expect("the solver reads");
    let registry = Registry::get();
    let cases = resolve_cases(&solver, registry);
    let clauses = SolverClauses::of_cases(&cases);
    let program = check_shared_program(std::sync::Arc::clone(&cases.concept().resolved.value), &clauses, registry, &mut CheckCache::default())
        .expect("the checker accepts the case");
    let task = read_task(&task_path).expect("the task reads");
    let judged = read_judged_task(&task_path).expect("the task's pairs read");
    let parameters = ParameterValues::stored(solver.arcdata.value());
    let session = TaskSession::new(SessionBound { bytes: 1 << 30 }, Caps::CORPUS);
    let limits = Limits { deadline: None, cancellation: Cancellation::default() };
    let constructions = Constructions::new(Vec::new(), registry).expect("an empty table");
    let evaluation = Evaluation { program: &program, task: &task, parameters: &parameters, session: &session, registry, constructions: &constructions, limits: &limits };
    let output = output_relation(&program).expect("the case derives `&output`");
    judged_run(&evaluation, &output, &judged, World::Closed, Depth::Full).expect("the run has no fault")
}

#[test]
fn tied_walks_whose_grids_a_train_pair_does_not_accept_do_not_solve_it() {
    let dir = std::env::temp_dir().join(format!("arclog-judge-unfold-{}", std::process::id()));
    let refused = run(&dir.join("given"), "");
    let accepted = run(&dir.join("tiebreak"), r#", "alt": {"kind": "tiebreak", "grid": [[1, 2, 2]]}"#);
    std::fs::remove_dir_all(&dir).ok();
    assert!(!refused.pairs[0].solved);
    assert!(accepted.pairs[0].solved);
}
