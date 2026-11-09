//! The end check of the `cases()` stage over the corpus: `cargo run
//! --example cases -- <dir>`, with `<dir>` the corpus directory, such as
//! `programs/arclog/`.
//!
//! The run builds each case program of each solver of `<dir>`, as a program
//! value, with [`arclog::harness::run_over_corpus`], prints each failure by
//! task id, and exits nonzero where a solver fails or the directory is a
//! fault.

//!
//! A solver fails where its files do not read, where a case's build
//! panics, or where a top-level form of a case program stands at a path
//! that [`arclog::solver::Case::file_path`] gives and the walk of
//! [`arclog::program::path::node_at`] reaches no node at in that file, or
//! where the last top-level form of a case program is no `OUT` form.

use std::path::{Path, PathBuf};
use std::process::ExitCode;

use arclog::harness::{print_ended, read_corpus_solver, require_optimized_build, run_over_corpus, CorpusSolver, SolverResult};
use arclog::program::path::{node_at, NodePath, NodeRef, PathStep};
use arclog::program::Form;
use arclog::solver::{Exclusion, FileOwner, Solver};

/// A line for each fault of the cases of `solver`.
fn faults(solver: &Solver) -> Vec<String> {
    let mut faults = Vec::new();
    for case in solver.cases(Exclusion::WithExcluded) {
        for index in 0..case.program.value().forms.len() {
            let (owner, path) = case.file_path(&NodePath(Box::new([PathStep(index as u32)])));
            let file = match owner {
                FileOwner::Solver => Some(&solver.program),
                FileOwner::Representative => solver.representative.as_ref().map(|r| &r.program),
            };
            if file.and_then(|program| node_at(NodeRef::Program(program.value()), &path)).is_none() {
                faults.push(format!("case {:?}: form {index} stands at {path:?} of the {owner:?} file, which holds no node there", case.name));
            }
        }
        if !matches!(case.program.value().forms.last(), Some(Form::Out(_))) {
            faults.push(format!("case {:?}: the last form of the case program is no `OUT` form", case.name));
        }
    }
    faults
}

fn check(dir: &Path, solver: &CorpusSolver) -> SolverResult {
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
    let Some(dir) = std::env::args().nth(1).map(PathBuf::from) else {
        eprintln!("usage: cases <dir>");
        return ExitCode::FAILURE;
    };
    match run_over_corpus(&dir, None, |solver| check(&dir, solver), print_ended) {
        Err(error) => {
            eprintln!("{error:?}");
            ExitCode::FAILURE
        }
        Ok(report) => {
            println!("{} solvers, {} fail", report.checked, report.failures.len());
            if report.failures.is_empty() { ExitCode::SUCCESS } else { ExitCode::FAILURE }
        }
    }
}
