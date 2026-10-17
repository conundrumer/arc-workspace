//! The corpus harness: runs a check over every solver of the corpus.
//!
//! Implements `work/engine/reader.md`, the step's end check: "each error the
//! lint reports from one of those checks, the engine reports at the same
//! place, and the engine reports no other" and "Every file the lint passes
//! reads, resolves and round-trips". Each later stage's end check runs
//! through [`run_over_corpus`].
//!
//! The harness takes the corpus directory as an argument, and no test reads
//! the corpus: the end check over the corpus is a run of the example
//! `corpus`, which takes the directory on its command line.

#![allow(unused_variables, dead_code)]

use std::path::{Path, PathBuf};

/// One solver of the corpus: its task id and its two files.
///
/// Implements `work/engine/reader.md`, the end of the step: "the engine and the Python lint agree on `gen/` for the checks this step builds".
#[derive(Clone, PartialEq, Eq, Debug)]
pub struct CorpusPair {
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
    Unpaired { path: PathBuf },
}

/// The solvers of `dir`, by task id.
///
/// Implements `work/engine/reader.md`, the end of the step: "the engine and the Python lint agree on `gen/` for the checks this step builds".
pub fn corpus_pairs(dir: &Path) -> Result<Vec<CorpusPair>, CorpusError> {
    todo!()
}

/// The outcome of a check on one solver.
///
/// Implements `work/engine/reader.md`, the end of the step: "the engine and the Python lint agree on `gen/` for the checks this step builds".
#[derive(Clone, PartialEq, Eq, Debug)]
pub enum PairOutcome {
    Pass,
    /// The check's report on the solver, one line per difference.
    Fail(Vec<String>),
}

/// The solvers of the corpus on which `check` failed, with its report.
///
/// Implements `work/engine/reader.md`, the end of the step: "the engine and the Python lint agree on `gen/` for the checks this step builds".
#[derive(Clone, PartialEq, Eq, Debug)]
pub struct CorpusReport {
    pub checked: usize,
    pub failures: Vec<(CorpusPair, Vec<String>)>,
}

/// Runs `check` over every solver of `dir`, on as many threads as the
/// machine has, and gives the failures by task id.
///
/// Implements `work/engine/reader.md`, the end of the step: "the engine and the Python lint agree on `gen/` for the checks this step builds".
pub fn run_over_corpus<F>(dir: &Path, check: F) -> Result<CorpusReport, CorpusError>
where
    F: Fn(&CorpusPair) -> PairOutcome + Sync,
{
    todo!()
}
