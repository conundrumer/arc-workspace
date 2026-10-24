//! The comparison of each solver of the corpus with its expanded form.

use std::collections::BTreeMap;
use std::panic::{catch_unwind, AssertUnwindSafe};
use std::path::Path;

use arclog::judge::solves::OutputSet;
use arclog::harness::{run_over_corpus, SolverResult};

use crate::concept_case::with_concept_case;

use super::last_panic;

/// The lines on the solvers of the corpus: each solver whose concept case
/// gives other output sets than in the expanded corpus, with each example where
/// they differ and the two sets, then each that is not compared, with
/// what stops it, each in the order of the task ids.
pub(super) fn compare_solvers(corpus: &Path, expanded: &Path, tasks: &Path) -> Result<(Vec<String>, Vec<String>), String> {
    let found = std::sync::Mutex::new(BTreeMap::new());
    run_over_corpus(corpus, None, |solver| {
        let id = &solver.task_id;
        let line = match (outcomes(corpus, tasks, id), outcomes(expanded, tasks, id)) {
            (Ok(a), Ok(b)) if a == b => None,
            (Ok(a), Ok(b)) => {
                let mut pairs: Vec<String> = a
                    .iter()
                    .zip(&b)
                    .filter(|(x, y)| x != y)
                    .map(|((example, given), (_, expanded))| format!("{example}: the given form gives {given}, the expanded form {expanded}"))
                    .collect();
                if a.len() != b.len() {
                    pairs.push(format!("the given form gives {} examples, the expanded form {}", a.len(), b.len()));
                }
                Some(Ok(format!("{id}: the two forms differ: {}", pairs.join("; "))))
            }
            (Err(fault), _) => Some(Err(format!("{id}: the given form: {fault}"))),
            (_, Err(fault)) => Some(Err(format!("{id}: the expanded form: {fault}"))),
        };
        if let Some(line) = line {
            found.lock().expect("no check panics holding the lock").insert(id.clone(), line);
        }
        SolverResult::Pass
    }, |_, _| ())
    .map_err(|error| format!("the corpus does not read: {error:?}"))?;
    let found = found.into_inner().expect("no check panics holding the lock");
    let (differ, not_compared): (Vec<_>, Vec<_>) = found.into_values().partition(Result::is_ok);
    Ok((differ.into_iter().filter_map(Result::ok).collect(), not_compared.into_iter().filter_map(Result::err).collect()))
}

/// The output set of the concept case of the solver `id` of `corpus` on
/// each example, in full, with the example's place in the task, or the
/// fault that stops it; a form the engine does not yet evaluate gives the
/// place of its panic.
pub(super) fn outcomes(corpus: &Path, tasks: &Path, id: &str) -> Result<Vec<(String, String)>, String> {
    let run = catch_unwind(AssertUnwindSafe(|| {
        with_concept_case(corpus, tasks, id, |case| {
            let (run, _) = case.run();
            let run = run.map_err(|fault| format!("a fault of the run at {:?}: {}", fault.form, fault.message))?;
            Ok(run.pairs.iter().enumerate().map(|(index, pair)| (format!("example {index}"), set_text(&pair.set))).collect())
        })
    }));
    run.unwrap_or_else(|_| Err(format!("the engine does not yet evaluate a form it reads: {}", last_panic())))
}

/// The text of an output set, its grids in the order of their texts, so
/// that two equal sets give one text.
fn set_text(set: &OutputSet) -> String {
    match set {
        OutputSet::Grids(grids) => {
            let mut texts: Vec<String> = grids.iter().map(|grid| format!("{:?}", grid.rows())).collect();
            texts.sort();
            texts.join(" or ")
        }
        OutputSet::Undefined => "undefined".to_owned(),
        OutputSet::Outside => "outside".to_owned(),
        OutputSet::Stopped(stop) => format!("a stop at {:?}", stop.bound),
    }
}
