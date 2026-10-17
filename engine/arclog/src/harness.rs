//! The corpus harness: runs a check over every solver of the corpus.
//!
//! The end check over the corpus of each stage that has one, the examples
//! `round_trip`, `resolve`, `cases` and `lint`, runs through
//! [`run_over_corpus`]. Together they pass where every file the Python lint
//! passes reads, resolves and round-trips, and where the engine reports each
//! error the Python lint reports from the engine's checks, at the same
//! place, and no other. The representations and programs-as-values stages
//! have no example of their own: the other stages' end checks run their
//! bodies.
//!
//! The harness takes the corpus directory as an argument, and no test reads
//! the corpus: each stage's end check over the corpus is a run of its own
//! example under `engine/arclog/examples/`, which takes the directory on its
//! command line, as the crate's module comment lists them.

#![allow(unused_variables, dead_code)]

use std::path::{Path, PathBuf};

/// One solver of the corpus: its task id and its two files.
#[derive(Clone, PartialEq, Eq, Debug)]
pub struct CorpusSolver {
    pub task_id: String,
    pub arclog: PathBuf,
    pub arcdata: PathBuf,
}

/// A fault of the corpus directory: it cannot be read, or an `.arclog` file
/// has no `.arcdata` file beside it, or the reverse.
#[derive(Debug)]
pub enum CorpusError {
    Unreadable { path: PathBuf, error: std::io::Error },
    MissingFile { path: PathBuf },
}

/// The solvers of `dir`, in the order of their task ids.
pub fn corpus_solvers(dir: &Path) -> Result<Vec<CorpusSolver>, CorpusError> {
    todo!()
}

/// The outcome of a check on one solver.
#[derive(Clone, PartialEq, Eq, Debug)]
pub enum SolverResult {
    Pass,
    /// The check's report on the solver, one line per difference.
    Fail(Vec<String>),
}

/// The Python lint's report over the corpus: one line
/// `<path>:<line>: <check>: <message>` per error, then a summary that the
/// parse skips. The examples that check the files the lint passes, and the
/// one that compares the two lints, read it through this one parse.
#[derive(Clone, Debug, Default)]
pub struct LintReport {
    /// Each error of the report, in the report's order.
    pub errors: Vec<LintError>,
}

/// One error of the Python lint's report.
#[derive(Clone, PartialEq, Eq, Debug)]
pub struct LintError {
    pub path: PathBuf,
    pub line: u32,
    pub check: String,
    pub message: String,
}

impl LintReport {
    /// The report that `text` gives.
    pub fn parse(text: &str) -> LintReport {
        todo!()
    }

    /// Whether the lint reports no error in the files of `solver`.
    pub fn passes(&self, solver: &CorpusSolver) -> bool {
        todo!()
    }
}

/// The solvers of the corpus on which `check` failed, with its report.
#[derive(Clone, PartialEq, Eq, Debug)]
pub struct CorpusReport {
    /// The number of solvers the check ran on.
    pub checked: usize,
    /// Each solver the check failed on, with the check's report on it, in
    /// the order of their task ids.
    pub failures: Vec<(CorpusSolver, Vec<String>)>,
}

/// Runs `check` over every solver of `dir`, on as many threads as the
/// machine has, and gives the report over them.
pub fn run_over_corpus<F>(dir: &Path, check: F) -> Result<CorpusReport, CorpusError>
where
    F: Fn(&CorpusSolver) -> SolverResult + Sync,
{
    todo!()
}
