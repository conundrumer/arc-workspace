//! The end check of the `cases()` stage over the corpus: `cargo run
//! --example cases -- <dir>`, with `<dir>` the corpus directory, such as
//! `work/arclog/gen/`.
//!
//! The run builds each case program of each solver of `<dir>`, as a program
//! value, with [`arclog::harness::run_over_corpus`], prints each failure by
//! task id, and exits nonzero where a solver fails or the directory is a
//! fault.

fn main() {
    todo!()
}
