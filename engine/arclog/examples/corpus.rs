//! The end check of step 1 over the corpus: `cargo run --example corpus --
//! <dir>`, with `<dir>` the corpus directory, `gen/` of the engine overview.
//!
//! Implements `work/engine/reader.md`, the end of the step: "the engine and
//! the Python lint agree on `gen/` for the checks this step builds". The run
//! reads the corpus pairs of `<dir>` with [`arclog::harness::run_over_corpus`],
//! prints each failure by task id, and exits nonzero where a solver fails or
//! the directory is a fault.

fn main() {
    todo!()
}
