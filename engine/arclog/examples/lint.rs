//! The end check of the checker stage, and of step 1, over the corpus:
//! `cargo run --example lint -- <dir> <report>`, with `<dir>` the corpus
//! directory, such as `engine/corpus/gen/`, and `<report>` the output of the
//! Python lint over `<dir>`, read by [`arclog::harness::LintReport`].
//!
//! The run lints each solver of `<dir>` with
//! [`arclog::harness::run_over_corpus`], prints each difference from the
//! Python lint by task id, and exits nonzero where a solver differs or the
//! directory is a fault, so the check passes where the engine and the
//! Python lint agree on `<dir>` for the checks the engine has.

fn main() {
    todo!()
}
