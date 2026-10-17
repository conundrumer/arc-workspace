//! The corpus harness: runs a check over every solver of the corpus.
//!
//! Implements `work/engine/reader.md`, the step's end check: "each error the
//! lint reports from one of those checks, the engine reports at the same
//! place, and the engine reports no other" and "Every file the lint passes
//! reads, resolves and round-trips". The end check over the corpus of each
//! stage that has one, the examples `round_trip`, `resolve`, `cases` and
//! `lint`, runs through [`run_over_corpus`]. The representations and
//! programs-as-values stages have no example of their own: the other
//! stages' end checks run their bodies.
//!
//! The harness takes the corpus directory as an argument, and no test reads
//! the corpus: each stage's end check over the corpus is a run of its own
//! example under `engine/arclog/examples/`, which takes the directory on its
//! command line, as the crate's module comment lists them.

#![allow(unused_variables, dead_code)]

use std::path::{Path, PathBuf};

/// One solver of the corpus: its task id and its two files.
///
/// Implements `work/engine/reader.md`, the end of the step: "the engine and the Python lint agree on `gen/` for the checks this step builds".
#[derive(Clone, PartialEq, Eq, Debug)]
pub struct CorpusSolver {
    pub task_id: String,
    pub arclog: PathBuf,
    pub arcdata: PathBuf,
}

/// A fault of the corpus directory: it cannot be read, or an `.arclog` file
/// has no `.arcdata` file beside it, or the reverse.
///
/// Implements `work/engine/reader.md`, the end of the step: "the engine and the Python lint agree on `gen/` for the checks this step builds".
#[derive(Debug)]
pub enum CorpusError {
    Unreadable { path: PathBuf, error: std::io::Error },
    MissingFile { path: PathBuf },
}

/// The solvers of `dir`, by task id.
///
/// Implements `work/engine/reader.md`, the end of the step: "the engine and the Python lint agree on `gen/` for the checks this step builds".
pub fn corpus_solvers(dir: &Path) -> Result<Vec<CorpusSolver>, CorpusError> {
    todo!()
}

/// The outcome of a check on one solver.
///
/// Implements `work/engine/reader.md`, the end of the step: "the engine and the Python lint agree on `gen/` for the checks this step builds".
#[derive(Clone, PartialEq, Eq, Debug)]
pub enum SolverResult {
    Pass,
    /// The check's report on the solver, one line per difference.
    Fail(Vec<String>),
}

/// The Python lint's report over the corpus, `work/arclog/lint.py`'s
/// output: one line `<path>:<line>: <check>: <message>` per error, then a
/// summary that the parse skips. The examples that check the files the lint
/// passes, and the one that compares the two lints, read it through this one
/// parse.
///
/// Implements `work/engine/reader.md`, the end of the step: "each error the lint reports from one of those checks, the engine reports at the same place" and "Every file the lint passes reads, resolves and round-trips".
#[derive(Clone, Debug, Default)]
pub struct LintReport {
    pub errors: Vec<LintError>,
}

/// One error of the Python lint's report.
///
/// Implements `work/engine/reader.md`, the end of the step: "each error the lint reports from one of those checks, the engine reports at the same place".
#[derive(Clone, PartialEq, Eq, Debug)]
pub struct LintError {
    pub path: PathBuf,
    pub line: u32,
    pub check: String,
    pub message: String,
}

impl LintReport {
    /// The report that `text` gives.
    ///
    /// Implements `work/engine/reader.md`, the end of the step: "the engine and the Python lint agree on `gen/`".
    pub fn parse(text: &str) -> LintReport {
        todo!()
    }

    /// Whether the lint reports no error in the files of `solver`.
    ///
    /// Implements `work/engine/reader.md`, the end of the step: "Every file the lint passes".
    pub fn passes(&self, solver: &CorpusSolver) -> bool {
        todo!()
    }
}

/// The solvers of the corpus on which `check` failed, with its report.
///
/// Implements `work/engine/reader.md`, the end of the step: "the engine and the Python lint agree on `gen/` for the checks this step builds".
#[derive(Clone, PartialEq, Eq, Debug)]
pub struct CorpusReport {
    pub checked: usize,
    pub failures: Vec<(CorpusSolver, Vec<String>)>,
}

/// Runs `check` over every solver of `dir`, on as many threads as the
/// machine has, and gives the failures by task id.
///
/// Implements `work/engine/reader.md`, the end of the step: "the engine and the Python lint agree on `gen/` for the checks this step builds".
pub fn run_over_corpus<F>(dir: &Path, check: F) -> Result<CorpusReport, CorpusError>
where
    F: Fn(&CorpusSolver) -> SolverResult + Sync,
{
    todo!()
}
