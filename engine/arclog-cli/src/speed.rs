//! `speed`: the engine's time per solver over the corpus against Souffle's
//! time in the snapshot, and its stops at the caps.
//!
//! It runs the concept case of each solver given, or of every solver of the
//! corpus, at its stored `param` records, and prints each solver whose run
//! is slower than Souffle's time in the snapshot of the Souffle outcomes,
//! with both times, and each solver whose run stops at a cap, with the cap
//! and the form that reached it.
//!
//! It prints as well, for each solver run, the largest count of content
//! units (the rows an evaluation reads and writes) and of rows held of any
//! one of its evaluations that ended with no stop, and then the largest of each over the solvers run, the counts the
//! caps are set from.
//!
//! Its arguments: the snapshot's directory, the corpus directory, the
//! directory of the task files, then the task ids of the solvers to run,
//! and `--reads <name>` for the solvers that the snapshot's `uses.json`
//! gives for a lib name or a form keyword; every solver of the corpus where
//! it is given none.

use std::collections::{BTreeMap, BTreeSet};
use std::process::ExitCode;
use std::sync::Mutex;

use arclog::eval::{ReachedBound, Stop};
use arclog::harness::{print_ended, require_optimized_build, run_over_corpus, SolverResult};
use arclog::judge::solves::OutputSet;
use arclog::session::Counts;
use serde_json::Value;

use crate::arguments::Arguments;
use crate::concept_case::with_concept_case;
use crate::select::{read_json, selected};

const USAGE: &str = "usage: arclog-cli speed <snapshot-dir> <corpus-dir> <tasks-dir> [<task_id> ...] [--reads <name> ...]";

/// The subcommand on `args`, the arguments after its name.
pub fn run(args: &[String]) -> ExitCode {
    if let Err(code) = require_optimized_build() {
        return code;
    }
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
    let counts: Mutex<BTreeMap<String, Counts>> = Mutex::default();
    let report = run_over_corpus(&arguments.corpus, selected.as_ref(), |solver| match timed(&arguments, &solver.task_id, &counts) {
        Ok(lines) if lines.is_empty() => SolverResult::Pass,
        Ok(lines) => SolverResult::Fail(lines),
        Err(line) => SolverResult::Fail(vec![line]),
    }, print_ended);
    let report = match report {
        Ok(report) => report,
        Err(error) => {
            eprintln!("the corpus does not read: {error:?}");
            return ExitCode::from(2);
        }
    };
    let counts = counts.into_inner().expect("a map of counts that no panic poisoned");
    for (id, counts) in &counts {
        println!("{id}: the largest counts of one evaluation: {} content units counted, {} rows held", counts.bindings, counts.rows);
    }
    let largest = |count: fn(&Counts) -> u64| counts.iter().max_by_key(|(_, counts)| count(counts)).map(|(id, counts)| (count(counts), id));
    if let (Some((bindings, bindings_id)), Some((rows, rows_id))) = (largest(|c| c.bindings), largest(|c| c.rows)) {
        println!("the largest counts of the solvers run: {bindings} content units counted, of {bindings_id}; {rows} rows held, of {rows_id}");
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
/// each; or the one line of the fault that stops it. Its session's largest
/// counts go into `counts` under `id`, once the run ends.
fn timed(arguments: &Arguments, id: &str, counts: &Mutex<BTreeMap<String, Counts>>) -> Result<Vec<String>, String> {
    let record = read_json(&arguments.snapshot.join(format!("{id}.json")))?;
    with_concept_case(&arguments.corpus, &arguments.tasks, id, |case| {
        let (run, seconds) = case.run();
        let largest = case.evaluation.session.largest_counts();
        counts.lock().expect("a map of counts that no panic poisoned").insert(id.to_owned(), largest);
        let mut lines: Vec<String> = slower(seconds, &record)?.into_iter().collect();
        let run = run.map_err(|fault| format!("a fault of the run at {:?}: {}", fault.form, fault.message))?;
        let stops: Vec<&Stop> = run.pairs.iter().filter_map(|pair| if let OutputSet::Stopped(stop) = &pair.set { Some(stop) } else { None }).collect();
        let at_caps: BTreeSet<String> = stops
            .into_iter()
            .filter(|stop| matches!(stop.bound, ReachedBound::Bindings { .. } | ReachedBound::Rows { .. }))
            .map(|stop| format!("the run stops at {:?} at the form {:?}", stop.bound, stop.form))
            .collect();
        lines.extend(at_caps);
        Ok(lines)
    })
}
