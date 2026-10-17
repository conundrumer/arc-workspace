//! The end check of the checker stage, and of step 1, over the corpus:
//! `cargo run --example lint -- <dir> <report>`, with `<dir>` the corpus
//! directory, `gen/` of the engine overview, and `<report>` the output of
//! the Python lint, `work/arclog/lint.py`, over `<dir>`, read by
//! [`arclog::harness::LintReport`].
//!
//! Implements `work/engine/reader.md`, the end of the step: "the engine and
//! the Python lint agree on `gen/` for the checks this step builds". The run
//! lints each solver of `<dir>` with [`arclog::harness::run_over_corpus`],
//! prints each difference from the Python lint by task id, and exits
//! nonzero where a solver differs or the directory is a fault.

fn main() {
    todo!()
}
