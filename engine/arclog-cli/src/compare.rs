//! `compare`: runs the concept case of each solver given, or of every
//! solver of the corpus, at its stored `param` records, and compares each
//! pair's output with the snapshot of the Souffle outcomes, and the run's
//! time per solver with Souffle's time there. It prints each mismatch by
//! solver, case and pair, and each solver that runs slower.
//!
//! Its arguments: the snapshot's directory, the corpus directory, and the
//! task ids of the solvers to run, or none for every solver of the corpus.

#![allow(unused_variables, dead_code)]

use std::process::ExitCode;

/// The subcommand on `args`, the arguments after its name.
pub fn run(args: &[String]) -> ExitCode {
    todo!()
}
