//! `speed`: the engine's time per solver over the corpus against Souffle's
//! time in the snapshot, and its stops at the caps.
//!
//! It runs the concept case of each solver given, or of every solver of the
//! corpus, at its stored `param` records, and prints each solver whose run
//! is slower than Souffle's time in the snapshot of the Souffle outcomes,
//! with both times, and each solver whose run stops at a cap, with the cap
//! and the form that reached it.
//!
//! Its arguments: the snapshot's directory, the corpus directory, the
//! directory of the task files, then the task ids of the solvers to run,
//! and `--reads <name>` for the solvers that the snapshot's `uses.json`
//! gives for a lib name or a form keyword; every solver of the corpus where
//! it is given none.

use std::collections::BTreeSet;
use std::process::ExitCode;

use arclog::eval::{GridValue, NoGridColumns, ReachedBound, Stop};
use arclog::harness::{run_over_corpus, SolverResult};
use serde_json::Value;

use crate::compare::{with_concept_case, Arguments};
use crate::select::{read_json, selected};

const USAGE: &str = "usage: arclog-cli speed <snapshot-dir> <corpus-dir> <tasks-dir> [<task_id> ...] [--reads <name> ...]";

/// The subcommand on `args`, the arguments after its name.
pub fn run(args: &[String]) -> ExitCode {
    let Some(arguments) = Arguments::parse(args) else {
        eprintln!("{USAGE}");
        return ExitCode::from(2);
    };
    let selected = match selected(&arguments.task_ids, &arguments.reads, &arguments.snapshot.join("uses.json")) {
        Ok(selected) => selected,
        Err(message) => {
            eprintln!("{message}");
            return ExitCode::from(2);
        }
    };
    let report = run_over_corpus(&arguments.corpus, |solver| match &selected {
        Some(ids) if !ids.contains(&solver.task_id) => SolverResult::Pass,
        _ => match timed(&arguments, &solver.task_id) {
            Ok(lines) if lines.is_empty() => SolverResult::Pass,
            Ok(lines) => SolverResult::Fail(lines),
            Err(line) => SolverResult::Fail(vec![line]),
        },
    });
    let report = match report {
        Ok(report) => report,
        Err(error) => {
            eprintln!("the corpus does not read: {error:?}");
            return ExitCode::from(2);
        }
    };
    for (solver, lines) in &report.failures {
        for line in lines {
            println!("{}: {line}", solver.task_id);
        }
    }
    let ran = selected.map_or(report.checked, |ids| ids.len());
    println!("{} of {ran} solvers run slower than Souffle, stop at a cap, or do not run", report.failures.len());
    if report.failures.is_empty() { ExitCode::SUCCESS } else { ExitCode::FAILURE }
}

/// The line of a run of `seconds` that is slower than Souffle's time in
/// `record`, the solver's snapshot record, `None` where it is not slower,
/// or the fault that the record gives no time.
pub(crate) fn slower(seconds: f64, record: &Value) -> Result<Option<String>, String> {
    let souffle = record.get("cpu_seconds").and_then(Value::as_f64).ok_or("the snapshot gives no Souffle time")?;
    Ok((seconds > souffle).then(|| format!("the engine runs {seconds:.3} s against Souffle's {souffle:.3} s")))
}

/// The lines of the run of the concept case of the solver `id`: its time
/// against Souffle's, where it is slower, and each stop at a cap, once
/// each; or the one line of the fault that stops it.
fn timed(arguments: &Arguments, id: &str) -> Result<Vec<String>, String> {
    let record = read_json(&arguments.snapshot.join(format!("{id}.json")))?;
    with_concept_case(&arguments.corpus, &arguments.tasks, id, |case| {
        let (outputs, seconds) = case.run();
        let mut lines: Vec<String> = slower(seconds, &record)?.into_iter().collect();
        let outputs = outputs.map_err(|fault| format!("a fault of the run at {:?}: {}", fault.form, fault.message))?;
        let stops: Vec<&Stop> = match &outputs {
            Err(NoGridColumns::Stopped(stop)) => vec![stop],
            Err(NoGridColumns::NoPairSolves) => Vec::new(),
            Ok(grids) => grids.iter().filter_map(|(_, grid)| if let GridValue::Stopped(stop) = grid { Some(stop) } else { None }).collect(),
        };
        let at_caps: BTreeSet<String> = stops
            .into_iter()
            .filter(|stop| matches!(stop.bound, ReachedBound::Work { .. } | ReachedBound::Rows { .. }))
            .map(|stop| format!("the run stops at {:?} at the form {:?}", stop.bound, stop.form))
            .collect();
        lines.extend(at_caps);
        Ok(lines)
    })
}
