//! `test-pairs <corpus-dir> <tasks-dir> [<task_id> ...]`: runs the concept
//! case of each solver given, or of every solver of the corpus, at its stored
//! `param` records, and prints one line for each, its fields separated by
//! tabs: the task id, the number of test pairs, the number of them that the
//! case solves, and each other test pair by its index, with the kind of what
//! the case gives on it. A line holds no grid. Where the run faults, the
//! number solved is `-`, and the last field gives the form at the fault.

use std::path::{Path, PathBuf};
use std::process::ExitCode;

use arclog::harness::{print_ended, require_optimized_build, run_over_corpus, SolverResult};
use arclog::judge::solves::OutputSet;

use crate::concept_case::{with_concept_case, ConceptCase};
use crate::select::selected;

const USAGE: &str = "usage: arclog-cli test-pairs <corpus-dir> <tasks-dir> [<task_id> ...]";

/// The subcommand on `args`, the arguments after its name.
pub fn run(args: &[String]) -> ExitCode {
    if let Err(code) = require_optimized_build() {
        return code;
    }
    let [corpus, tasks, task_ids @ ..] = args else {
        eprintln!("{USAGE}");
        return ExitCode::from(2);
    };
    let (corpus, tasks) = (PathBuf::from(corpus), PathBuf::from(tasks));
    let selected = selected(task_ids, &[], Path::new("")).expect("a selection by task id alone reads no file");
    let report = run_over_corpus(&corpus, selected.as_ref(), |solver| {
        let id = &solver.task_id;
        match with_concept_case(&corpus, &tasks, id, |case| Ok(fields(case))) {
            Ok(fields) => {
                println!("{id}\t{fields}");
                SolverResult::Pass
            }
            Err(fault) => SolverResult::Fail(vec![fault]),
        }
    }, print_ended);
    match report {
        Ok(report) if report.failures.is_empty() => ExitCode::SUCCESS,
        Ok(_) => ExitCode::FAILURE,
        Err(error) => {
            eprintln!("the corpus does not read: {error:?}");
            ExitCode::from(2)
        }
    }
}

/// The fields after the task id of the line on `case`.
fn fields(case: &ConceptCase<'_>) -> String {
    let test = case.judged.test.len();
    let (run, _) = case.run();
    match run {
        Ok(run) => {
            let pairs = &run.pairs[case.judged.train.len()..];
            let solved = pairs.iter().filter(|pair| pair.solved).count();
            let others: Vec<String> = pairs.iter().enumerate().filter(|(_, pair)| !pair.solved).map(|(at, pair)| format!("{at}:{}", kind(&pair.set))).collect();
            format!("{test}\t{solved}\t{}", others.join(","))
        }
        Err(fault) => format!("{test}\t-\tfault at {:?}", fault.form),
    }
}

/// The kind of the output set `set`.
fn kind(set: &OutputSet) -> &'static str {
    match set {
        OutputSet::Grids(_) => "grids",
        OutputSet::Undefined => "undefined",
        OutputSet::Outside => "outside",
        OutputSet::Stopped(_) => "stopped",
    }
}
