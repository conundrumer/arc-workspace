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
//! No check of the lint refuses a second spelling
//! (`docs/arclog/arclog.md#second-spellings`).

use std::sync::Arc;

use super::{check_shared_program, CheckCache, SolverClauses};
use crate::diagnostic::{Diagnostic, Location, Severity};
use crate::hash::StableHashMap;
use crate::layout::{FilePlace, SourceFile};
use crate::program::path::NodePath;
use crate::registry::Registry;
use crate::resolver::{resolve_cases, ResolvedCase};
use crate::solver::{Case, CaseName, FileOwner, Solver};

/// The errors of every check over every case of `solver`, the excluded
/// cases included, each once per place in the files. The diagnostics stand
/// in the order of the first case each holds in, the concept case's first,
/// and within a case in the order the resolver and the checks give them.
pub fn lint(solver: &Solver, registry: &Registry) -> Vec<Diagnostic> {
    let cases = resolve_cases(solver, registry);
    let clauses = SolverClauses::of_cases(&cases);
    let mut cache = CheckCache::default();
    let mut found = Found::default();
    for ResolvedCase { case, resolved } in cases.cases() {
        let mut diagnostics = resolved.diagnostics.clone();
        if let Err(refused) = check_shared_program(Arc::clone(&resolved.value), &clauses, registry, &mut cache) {
            diagnostics.extend(refused);
        }
        for diagnostic in diagnostics.into_iter().filter(|d| d.severity == Severity::Error) {
            found.add(solver, case, diagnostic);
        }
    }
    found.finish()
}

/// The diagnostics found so far, one per kind, message and place, each
/// with the cases it holds in.
#[derive(Default)]
struct Found {
    diagnostics: Vec<(Diagnostic, Vec<CaseName>)>,
    /// The index in `diagnostics` of each kind, message and place.
    index: StableHashMap<(crate::diagnostic::DiagnosticKind, Box<str>, FilePlace), usize>,
}

impl Found {
    /// Adds `diagnostic`, found in `case` of `solver` at a path of the case
    /// program, at each of its places in the files.
    fn add(&mut self, solver: &Solver, case: &Case, diagnostic: Diagnostic) {
        let places = match &diagnostic.location {
            Location::Path(path) => vec![place(solver, case, path)],
            Location::Places(places) => places.to_vec(),
        };
        for place in places {
            let key = (diagnostic.kind, diagnostic.message.clone(), place.clone());
            let index = *self.index.entry(key).or_insert_with(|| {
                let at = Diagnostic { location: Location::Places(Box::new([place])), ..diagnostic.clone() };
                self.diagnostics.push((at, Vec::new()));
                self.diagnostics.len() - 1
            });
            let cases = &mut self.diagnostics[index].1;
            if !cases.contains(&case.name) {
                cases.push(case.name.clone());
            }
        }
    }

    /// Each diagnostic, with its cases.
    fn finish(self) -> Vec<Diagnostic> {
        self.diagnostics.into_iter().map(|(diagnostic, cases)| Diagnostic { cases: cases.into(), ..diagnostic }).collect()
    }
}

/// The place in the files of the node at `path` of the program of `case`:
/// the place of that node in the arclog file of the solver that owns it, or
/// of its nearest node above that has a place, as a bare-label argument of a
/// site has none of its own.
fn place(solver: &Solver, case: &Case, path: &NodePath) -> FilePlace {
    let (owner, file_path) = case.file_path(path);
    let owning = match owner {
        FileOwner::Solver => solver,
        FileOwner::Representative => solver.representative.as_deref().expect("a node of the representative's file has a representative"),
    };
    let place = (0..=file_path.0.len())
        .rev()
        .find_map(|depth| owning.layout.node(SourceFile::Arclog, &NodePath(file_path.0[..depth].into()))?.place)
        .expect("the root of a file read from text has a place");
    FilePlace { task_id: Some(owning.task_id.clone()), place }
}
