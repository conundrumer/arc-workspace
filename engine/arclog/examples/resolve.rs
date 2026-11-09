//! The end check of the registry and resolver stage over the corpus: `cargo
//! run --example resolve -- <dir> <report>`, with `<dir>` the corpus
//! directory, such as `programs/arclog/`, and `<report>` the Python lint's
//! `--all` output over `<dir>`, read by [`arclog::harness::LintReport`]: the run
//! checks the files with no error in the report.
//!
//! Each file the lint passes reads and resolves. The run resolves each case
//! program of each of those solvers with
//! [`arclog::harness::run_over_corpus`], prints each failure by task id, and
//! exits nonzero where a solver fails or the directory is a fault.

use std::path::Path;
use std::process::ExitCode;

use arclog::diagnostic::{Diagnostic, Location};
use arclog::harness::{print_ended, read_corpus_solver, require_optimized_build, run_over_corpus, CorpusSolver, LintReport, SolverResult};
use arclog::registry::Registry;
use arclog::resolver::resolve_cases;
use arclog::solver::{Case, Solver};

/// A line for `diagnostic` of the resolution of `case`, at the place in the
/// files of its path in the case program.
fn describe(case: &Case, diagnostic: &Diagnostic) -> String {
    let at = match &diagnostic.location {
        Location::Path(path) => format!("{:?}", case.file_path(path)),
        Location::Places(places) => format!("{places:?}"),
    };
    format!("case {:?}: {at}: {}", case.name, diagnostic.message)
}

/// A line for each diagnostic of the resolution of each case of `solver`.
fn faults(solver: &Solver) -> Vec<String> {
    let cases = resolve_cases(solver, Registry::get());
    cases.resolved().flat_map(|resolved| resolved.resolved.diagnostics.iter().map(|d| describe(&resolved.case, d))).collect()
}

fn check(dir: &Path, solver: &CorpusSolver, report: &LintReport) -> SolverResult {
    for file in [&solver.arclog, &solver.arcdata] {
        match report.passes(file) {
            Ok(true) => {}
            Ok(false) => return SolverResult::Pass,
            Err(error) => return SolverResult::Fail(vec![format!("{}: {error}", file.display())]),
        }
    }
    let read = match read_corpus_solver(dir, &solver.task_id) {
        Ok(read) => read,
        Err(e) => return SolverResult::Fail(vec![format!("the solver's files do not read: {e}")]),
    };
    let faults = faults(&read);
    if faults.is_empty() { SolverResult::Pass } else { SolverResult::Fail(faults) }
}

fn main() -> ExitCode {
    if let Err(code) = require_optimized_build() {
        return code;
    }
    let args: Vec<String> = std::env::args().skip(1).collect();
    let [dir, report] = &args[..] else {
        eprintln!("usage: cargo run --profile tool --example resolve -- <dir> <report>");
        return ExitCode::FAILURE;
    };
    let report = match LintReport::read(Path::new(report)) {
        Ok(report) => report,
        Err(error) => {
            eprintln!("{report}: {error}");
            return ExitCode::FAILURE;
        }
    };
    let dir = Path::new(dir);
    match run_over_corpus(dir, None, |solver| check(dir, solver, &report), print_ended) {
        Err(error) => {
            eprintln!("{}: {error:?}", dir.display());
            ExitCode::FAILURE
        }
        Ok(corpus) => {
            println!("{} solvers, {} fail", corpus.checked, corpus.failures.len());
            if corpus.failures.is_empty() { ExitCode::SUCCESS } else { ExitCode::FAILURE }
        }
    }
}
