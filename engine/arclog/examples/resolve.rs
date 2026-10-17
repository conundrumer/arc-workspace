//! The end check of the registry and resolver stage over the corpus: `cargo
//! run --example resolve -- <dir> <report>`, with `<dir>` the corpus
//! directory, `gen/` of the engine overview, and `<report>` the Python
//! lint's output over `<dir>`, read by [`arclog::harness::LintReport`]: the
//! run checks the files with no error in the report.
//!
//! Implements `work/engine/reader.md`: "Every file the lint passes reads,
//! resolves". The run resolves each case program of each of those solvers
//! with [`arclog::harness::run_over_corpus`], prints each failure by task
//! id, and exits nonzero where a solver fails or the directory is a fault.

fn main() {
    todo!()
}
