//! `lib-compare`: the comparison of the lib with the Souffle lib. It
//! compares each solver with its expanded form, so each lib name that has a
//! definition with that definition inside every solver that uses it, and
//! each lib relation and component with its Souffle version on small
//! generated inputs, each in its eight D4 images and under one color
//! permutation.

#![allow(unused_variables, dead_code)]

use std::process::ExitCode;

/// The subcommand on `args`, the arguments after its name.
pub fn run(args: &[String]) -> ExitCode {
    todo!()
}
