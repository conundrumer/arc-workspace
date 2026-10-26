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
//! Each of them reads the Python lint's report as [`LintReport`] gives it:
//! the output of `src/arclog_convert/lint.py --all`.
//!
//! The modules, whose items this module re-exports:
//!
//! - `solvers`: the solvers of a corpus directory and their read;
//! - `lint_report`: the Python lint's report;
//! - `run`: a check run over the solvers on worker threads, and its report.

mod lint_report;
mod run;
mod solvers;

pub use lint_report::{LintCode, LintError, LintReport, LintReportError};
pub use run::{corpus_threads, panic_message, print_ended, require_optimized_build, run_on_workers, run_over_corpus, CorpusReport, SolverResult};
pub use solvers::{corpus_solvers, read_corpus_solver, solver_file_extension, CorpusError, CorpusSolver};
