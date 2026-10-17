//! The engine's lint over a solver.
//!
//! Implements `work/engine/reader.md`, Checker: "The engine's lint reads each
//! file once, resolves each case program, and then runs every check. It
//! reports each error once per place in the file, with the cases it holds
//! in." Each form's check runs once per [`super::CheckCacheKey`], so the
//! cases that share a form share its check.
//!
//! The lint maps each [`super::Refusal`] to the places of its node: the
//! form's path in the case program joined with the refusal's path, then
//! [`crate::solver::Case::file_path`], then each place that the
//! [`crate::layout::Layout`] of the solver that owns the file gives that
//! path, the solver's own or its representative's. Each diagnostic's location is
//! [`crate::diagnostic::Location::Places`].

#![allow(unused_variables, dead_code)]

use crate::diagnostic::Diagnostic;
use crate::registry::Registry;
use crate::solver::Solver;

/// The diagnostics of every check over every case of `solver`, the excluded
/// cases included, each once per place in the files.
///
/// Implements `work/engine/reader.md`, Checker: "The engine's lint reads each file once, resolves each case program, and then runs every check."
pub fn lint(solver: &Solver, registry: &Registry) -> Vec<Diagnostic> {
    todo!()
}
