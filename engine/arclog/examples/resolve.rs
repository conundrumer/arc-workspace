//! The end check of the registry and resolver stage over the corpus: `cargo
//! run --example resolve -- <dir> <report>`, with `<dir>` the corpus
//! directory, such as `work/arclog/gen/`, and `<report>` the Python lint's
//! output over `<dir>`, read by [`arclog::harness::LintReport`]: the run
//! checks the files with no error in the report.
//!
//! Each file the lint passes reads and resolves. The run resolves each case
//! program of each of those solvers, under each [`MacroExpansion`], with
//! [`arclog::harness::run_over_corpus`], prints each failure by task id, and
//! exits nonzero where a solver fails or the directory is a fault.

use std::panic::{catch_unwind, AssertUnwindSafe};
use std::path::Path;
use std::process::ExitCode;

use arclog::diagnostic::{Diagnostic, Location};
use arclog::harness::{read_corpus_solver, run_over_corpus, CorpusSolver, LintReport, SolverResult};
use arclog::registry::Registry;
use arclog::resolver::{resolve, ConceptReads, MacroExpansion};
use arclog::solver::{Case, Exclusion, Solver};

/// A line for `diagnostic` of the resolution of `case` under `macros`. A
/// diagnostic under [`MacroExpansion::Keep`] stands at the place in the
/// files of its path in the case program, and one under
/// [`MacroExpansion::Expand`] at its path in the expanded program.
fn describe(case: &Case, macros: MacroExpansion, diagnostic: &Diagnostic) -> String {
    let at = match (&diagnostic.location, macros) {
        (Location::Path(path), MacroExpansion::Keep) => format!("{:?}", case.file_path(path)),
        (Location::Path(path), MacroExpansion::Expand) => format!("{path:?}"),
        (Location::Places(places), _) => format!("{places:?}"),
    };
    format!("{macros:?}: case {:?}: {at}: {}", case.name, diagnostic.message)
}

/// A line for each diagnostic of the resolution of each case of `solver`
/// under `macros`.
fn faults(solver: &Solver, macros: MacroExpansion) -> Vec<String> {
    let registry = Registry::get();
    let derived = solver.derived_relations();
    let concept_case = solver.concept_case();
    let concept = resolve(&concept_case.program, None, &derived, registry, macros);
    let mut faults: Vec<String> = concept.diagnostics.iter().map(|d| describe(&concept_case, macros, d)).collect();
    for case in solver.cases(Exclusion::WithExcluded) {
        if case.name == concept_case.name {
            continue;
        }
        let reads = ConceptReads { concept: &concept.value, determinations: case.concept_determinations() };
        let resolved = resolve(&case.program, Some(reads), &derived, registry, macros);
        faults.extend(resolved.diagnostics.iter().map(|d| describe(&case, macros, d)));
    }
    faults
}

fn check(dir: &Path, solver: &CorpusSolver, report: &LintReport) -> SolverResult {
    for file in [&solver.arclog, &solver.arcdata] {
        match report.passes(file) {
            Ok(true) => {}
            Ok(false) => return SolverResult::Pass,
            Err(error) => return SolverResult::Fail(vec![format!("{}: {error}", file.display())]),
        }
    }
    let Some(read) = read_corpus_solver(dir, &solver.task_id) else {
        return SolverResult::Fail(vec!["the solver's files do not read".to_owned()]);
    };
    let each = || [MacroExpansion::Keep, MacroExpansion::Expand].into_iter().flat_map(|macros| faults(&read, macros)).collect::<Vec<_>>();
    match catch_unwind(AssertUnwindSafe(each)) {
        Ok(faults) if faults.is_empty() => SolverResult::Pass,
        Ok(faults) => SolverResult::Fail(faults),
        Err(_) => SolverResult::Fail(vec!["the resolution of a case panicked".to_owned()]),
    }
}

fn main() -> ExitCode {
    let args: Vec<String> = std::env::args().skip(1).collect();
    let [dir, report] = &args[..] else {
        eprintln!("usage: cargo run --example resolve -- <dir> <report>");
        return ExitCode::FAILURE;
    };
    let report = match std::fs::read_to_string(report) {
        Ok(text) => LintReport::parse(&text),
        Err(error) => {
            eprintln!("{report}: {error}");
            return ExitCode::FAILURE;
        }
    };
    let dir = Path::new(dir);
    match run_over_corpus(dir, |solver| check(dir, solver, &report)) {
        Err(error) => {
            eprintln!("{}: {error:?}", dir.display());
            ExitCode::FAILURE
        }
        Ok(corpus) => {
            for (solver, lines) in &corpus.failures {
                for line in lines {
                    println!("{}: {line}", solver.task_id);
                }
            }
            println!("{} solvers, {} fail", corpus.checked, corpus.failures.len());
            if corpus.failures.is_empty() { ExitCode::SUCCESS } else { ExitCode::FAILURE }
        }
    }
}
