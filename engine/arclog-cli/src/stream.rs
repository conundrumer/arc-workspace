//! `stream`: prints the token stream of one case program of a solver, for a
//! notebook to step a decoder through.
//!
//! The output is one line per token, in stream order: `<token id> model` or
//! `<token id> engine`, by the emitter of the token. The ids are those of
//! the vocabulary under `DecodeSettings::default()`, which a session of the
//! `arclog` Python package with no settings uses.
//!
//! Its arguments: the path of the solver's `.arclog` file, whose directory
//! also holds the `.arcdata` file and the files of the solvers it names,
//! then `--case <name>`, a case as `case_spelled` writes its name; the
//! concept case where it is not given.
//!
//! With `--corpus <corpus-dir>` it prints instead, for each case of each
//! solver of the corpus, or of the solvers whose task ids follow, one line
//! `<task_id> <case>: <n> tokens, <m> written by the model` or
//! `<task_id> <case>: <fault>`, then a line of the counts of cases streamed
//! and of cases whose stream faults. `--cases concept` (the default) takes
//! each solver's concept case, `--cases all` each case. A solver whose files
//! do not read or whose cases do not check prints one line
//! `<task_id>: <fault>`. The Python package `arclog` gives the streams
//! themselves, as `corpus_streams`.

use std::path::Path;
use std::process::ExitCode;
use std::sync::atomic::{AtomicUsize, Ordering};

use arclog::harness::{print_ended, require_optimized_build, run_over_corpus, SolverResult};
use arclog::registry::Registry;
use arclog::stream::corpus::{fault_line, solver_streams, token_ids, WantedCases};
use arclog::stream::{DecodeSettings, Emitter, Vocabulary};

use crate::select::selected;

const USAGE: &str = "usage: arclog-cli stream <solver path> [--case <name>]\n       arclog-cli stream --corpus <corpus-dir> [--cases concept|all] [<task_id> ...]";

/// The subcommand on `args`, the arguments after its name.
pub fn run(args: &[String]) -> ExitCode {
    if args.first().is_some_and(|arg| arg == "--corpus") {
        return run_corpus(&args[1..]);
    }
    let (path, case) = match args {
        [path] => (path, None),
        [path, flag, case] if flag == "--case" => (path, Some(case.as_str())),
        _ => {
            eprintln!("{USAGE}");
            return ExitCode::from(2);
        }
    };
    match stream_text(Path::new(path), case) {
        Ok(text) => {
            print!("{text}");
            ExitCode::SUCCESS
        }
        Err(fault) => {
            eprintln!("a fault that stops the stream: {fault}");
            ExitCode::FAILURE
        }
    }
}

/// The line of each token of the case `case` of the solver at `path`, the
/// concept case for `None`.
fn stream_text(path: &Path, case: Option<&str>) -> Result<String, String> {
    let id = path.file_stem().and_then(|stem| stem.to_str()).ok_or("the solver path names no file")?;
    let dir = path.parent().ok_or("the solver path has no directory")?;
    let vocabulary = Vocabulary::new(Registry::get(), &DecodeSettings::default());
    let wanted = case.map_or(WantedCases::Concept, WantedCases::Named);
    let streams = solver_streams(dir, id, wanted, &vocabulary)?;
    let [only] = streams.as_slice() else {
        return Err(format!("the solver gives {} streams, not one", streams.len()));
    };
    let stream = only.stream.as_ref().map_err(String::clone)?;
    let mut text = String::new();
    for (id, emitter) in token_ids(stream, &vocabulary) {
        let emitter = match emitter {
            Emitter::Model => "model",
            Emitter::Engine => "engine",
        };
        text.push_str(&format!("{id} {emitter}\n"));
    }
    Ok(text)
}

/// The subcommand's corpus form on `args`, the arguments after `--corpus`.
fn run_corpus(args: &[String]) -> ExitCode {
    if let Err(code) = require_optimized_build() {
        return code;
    }
    let Some((corpus, all, task_ids)) = parse_corpus(args) else {
        eprintln!("{USAGE}");
        return ExitCode::from(2);
    };
    let selected = selected(&task_ids, &[], Path::new("")).expect("a selection by task id alone reads no file");
    let streamed = AtomicUsize::new(0);
    let faulted = AtomicUsize::new(0);
    let report = run_over_corpus(
        Path::new(&corpus),
        |solver| {
            if selected.as_ref().is_some_and(|ids| !ids.contains(&solver.task_id)) {
                return SolverResult::Pass;
            }
            let lines = match stream_lines(Path::new(&corpus), &solver.task_id, all, &streamed, &faulted) {
                Ok(lines) => lines,
                Err(fault) => vec![fault_line(&solver.task_id, None, &fault)],
            };
            println!("{}", lines.join("\n"));
            SolverResult::Pass
        },
        print_ended,
    );
    let report = match report {
        Ok(report) => report,
        Err(error) => {
            eprintln!("the corpus does not read: {error:?}");
            return ExitCode::from(2);
        }
    };
    println!("corpus: {} cases streamed, {} cases whose stream faults", streamed.load(Ordering::Relaxed), faulted.load(Ordering::Relaxed));
    if report.failures.is_empty() { ExitCode::SUCCESS } else { ExitCode::FAILURE }
}

/// The corpus directory, whether `--cases all` is given, and the task ids,
/// or `None` for arguments of another form.
fn parse_corpus(args: &[String]) -> Option<(String, bool, Vec<String>)> {
    let mut args = args.iter();
    let corpus = args.next()?.clone();
    let mut all = false;
    let mut task_ids = Vec::new();
    while let Some(arg) = args.next() {
        if arg == "--cases" {
            all = match args.next()?.as_str() {
                "concept" => false,
                "all" => true,
                _ => return None,
            };
        } else {
            task_ids.push(arg.clone());
        }
    }
    Some((corpus, all, task_ids))
}

/// The line of each case of the solver `id` of `corpus`, the concept case or
/// every case, with the counts of streams and of faults taken into
/// `streamed` and `faulted`; or the fault that stops the solver's setup.
fn stream_lines(corpus: &Path, id: &str, all: bool, streamed: &AtomicUsize, faulted: &AtomicUsize) -> Result<Vec<String>, String> {
    let vocabulary = Vocabulary::new(Registry::get(), &DecodeSettings::default());
    let wanted = if all { WantedCases::All } else { WantedCases::Concept };
    let lines = solver_streams(corpus, id, wanted, &vocabulary)?
        .into_iter()
        .map(|case| {
            let outcome = match case.stream {
                Ok(stream) => {
                    streamed.fetch_add(1, Ordering::Relaxed);
                    let model = stream.iter().filter(|(_, emitter)| *emitter == Emitter::Model).count();
                    format!("{} tokens, {model} written by the model", stream.len())
                }
                Err(fault) => {
                    faulted.fetch_add(1, Ordering::Relaxed);
                    fault
                }
            };
            fault_line(id, Some(&case.case), &outcome)
        })
        .collect();
    Ok(lines)
}
