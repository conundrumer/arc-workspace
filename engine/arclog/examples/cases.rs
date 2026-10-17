//! The end check of the `cases()` stage over the corpus: `cargo run
//! --example cases -- <dir>`, with `<dir>` the corpus directory, `gen/` of
//! the engine overview.
//!
//! Implements `work/engine/reader.md`, Solvers: "`cases()` gives each case
//! program as a program value, on demand". The run builds each case of each
//! solver of `<dir>` with [`arclog::harness::run_over_corpus`], prints each
//! failure by task id, and exits nonzero where a solver fails or the
//! directory is a fault.

fn main() {
    todo!()
}
