//! The engine's lint over a solver. It reads each file once, resolves each
//! case program, and then runs every check over what the reader and the
//! resolver could make of their input, as the Python lint does. It reports
//! each error the engine's checks find once per place in the file, at the
//! place the Python lint reports it, with the cases it holds in. Each form's
//! check runs once per [`super::CheckCacheKey`], so the cases that share a
//! form share its check.
//!
//! The lint maps each [`super::Refusal`] to the places of its node: the
//! refusal's path mapped from the form's canonical order to its source order
//! through [`crate::program::canonical::CanonicalOrder`], joined to the
//! form's path in the case program, then [`crate::solver::Case::file_path`],
//! then each place that the [`crate::layout::Layout`] of the solver that
//! owns the file gives that path, the solver's own or its representative's.
//! Each diagnostic's location is [`crate::diagnostic::Location::Places`].
//!
//! A second spelling, such as `NOT` before a form or `(= Y *X)`, is a
//! suggestion and no rule of the language
//! (`docs/arclog/arclog.md#second-spellings`), so no check of the lint
//! refuses one.

#![allow(unused_variables, dead_code)]

use crate::diagnostic::Diagnostic;
use crate::registry::Registry;
use crate::solver::Solver;

/// The diagnostics of every check over every case of `solver`, the excluded
/// cases included, each once per place in the files.
pub fn lint(solver: &Solver, registry: &Registry) -> Vec<Diagnostic> {
    todo!()
}
