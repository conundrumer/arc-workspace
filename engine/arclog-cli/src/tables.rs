//! `tables <corpus-dir> <tasks-dir> [--cases concept|all] [--bodies]
//! [<task_id> ...]`: replays the token stream of each case program of the
//! corpus that the decoder admits, and prints, for each, one line with its
//! count of the tables that [`arclog::decode::Decoder::tables`] gives over the
//! steps of the replay, `<task_id>: <case>: <n> tables`. The tables of the
//! relations of finished forms are counted, and with `--bodies` those of the
//! bodies in progress as well. The command writes no file: the Python package
//! `arclog` gives the tables themselves, as arrays.
//!
//! A case program that holds a `DEMONSTRATED` form is left out. A case
//! program that the writer gives no stream, or whose stream the decoder
//! refuses, prints as `decode` prints a refusal.

use std::path::{Path, PathBuf};
use std::process::ExitCode;

use arclog::decode::corpus::solver_tables;
use arclog::decode::Points;
use arclog::harness::{print_ended, require_optimized_build, run_over_corpus, SolverResult};
use arclog::stream::DecodeSettings;
use arclog_constructions::shared as constructions;

use crate::select::selected;

const USAGE: &str = "usage: arclog-cli tables <corpus-dir> <tasks-dir> [--cases concept|all] [--bodies] [<task_id> ...]";

/// What the arguments give.
struct Arguments {
    corpus: PathBuf,
    tasks: PathBuf,
    all: bool,
    points: Points,
    task_ids: Vec<String>,
}

/// The subcommand on `args`, the arguments after its name.
pub fn run(args: &[String]) -> ExitCode {
    if let Err(code) = require_optimized_build() {
        return code;
    }
    let Some(arguments) = parse(args) else {
        eprintln!("{USAGE}");
        return ExitCode::from(2);
    };
    let selected = selected(&arguments.task_ids, &[], Path::new("")).expect("a selection by task id alone reads no file");
    let report = run_over_corpus(&arguments.corpus, selected.as_ref(), |solver| tables_solver(&arguments, &solver.task_id), print_ended);
    match report {
        Ok(report) if report.failures.is_empty() => ExitCode::SUCCESS,
        Ok(_) => ExitCode::FAILURE,
        Err(error) => {
            eprintln!("the corpus does not read: {error:?}");
            ExitCode::from(2)
        }
    }
}

/// The arguments, or `None` for arguments of another form.
fn parse(args: &[String]) -> Option<Arguments> {
    let (mut all, mut points) = (false, Points::Relations);
    let mut positional = Vec::new();
    let mut args = args.iter();
    while let Some(arg) = args.next() {
        match arg.as_str() {
            "--cases" => {
                all = match args.next()?.as_str() {
                    "concept" => false,
                    "all" => true,
                    _ => return None,
                };
            }
            "--bodies" => points = Points::All,
            _ => positional.push(arg.clone()),
        }
    }
    let mut positional = positional.into_iter();
    let (corpus, tasks) = (positional.next()?, positional.next()?);
    Some(Arguments { corpus: corpus.into(), tasks: tasks.into(), all, points, task_ids: positional.collect() })
}

/// The summary lines of the solver `id`, printed; or the lines of the
/// faults and refusals.
fn tables_solver(arguments: &Arguments, id: &str) -> SolverResult {
    let constructions = match constructions() {
        Ok(constructions) => constructions,
        Err(fault) => return SolverResult::Fail(vec![format!("a fault that stops the tables: {fault}")]),
    };
    match solver_tables(&arguments.corpus, &arguments.tasks, id, arguments.all, arguments.points, constructions, &DecodeSettings::corpus()) {
        Ok(solver) => {
            let mut failures = Vec::new();
            for case in solver.cases {
                match case.tables {
                    Ok(tables) => println!("{id}: {}: {} tables", case.case, tables.len()),
                    Err(refusal) => failures.push(format!("case {}: {refusal}", case.case)),
                }
            }
            if failures.is_empty() { SolverResult::Pass } else { SolverResult::Fail(failures) }
        }
        Err(fault) => SolverResult::Fail(vec![format!("a fault that stops the tables: {fault}")]),
    }
}
