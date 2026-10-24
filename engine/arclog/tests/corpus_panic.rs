//! A panic of a check on one solver of the corpus gives that solver a
//! failure with the panic's message, and the run reports each other solver.

use arclog::harness::{run_over_corpus, SolverResult};

#[test]
fn a_panic_on_one_solver_fails_that_solver_and_the_run_reports_the_others() {
    let dir = std::env::temp_dir().join(format!("arclog-corpus-panic-{}", std::process::id()));
    std::fs::create_dir_all(&dir).unwrap();
    for stem in ["a", "b", "c"] {
        for extension in ["arclog", "arcdata"] {
            std::fs::write(dir.join(format!("{stem}.{extension}")), "").unwrap();
        }
    }
    let report = run_over_corpus(&dir, None, |solver| match solver.task_id.as_str() {
        "a" => panic!("the form at a does not evaluate"),
        "b" => SolverResult::Fail(vec!["b fails".to_owned()]),
        _ => SolverResult::Pass,
    }, |_, _| ());
    std::fs::remove_dir_all(&dir).unwrap();
    let report = report.unwrap();
    assert_eq!(report.checked, 3);
    let failures: Vec<(&str, &[String])> = report.failures.iter().map(|(s, r)| (s.task_id.as_str(), r.as_slice())).collect();
    let [("a", [panic_line]), ("b", [b_line])] = failures[..] else { panic!("the failures are {failures:?}") };
    assert!(panic_line.contains("the form at a does not evaluate"), "{panic_line}");
    assert_eq!(b_line, "b fails");
}
