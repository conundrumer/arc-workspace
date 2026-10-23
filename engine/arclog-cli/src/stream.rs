//! `stream`: prints the token stream of one case program of a solver as
//! JSON, for a notebook to step a decoder through.
//!
//! The output is an array with one object per token, in stream order:
//! `{"id": <token id>, "emitter": "model" | "engine"}`. The ids are those of
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
//! `<task_id>: <fault>`.
//!
//! With `--out <file>` as well, the corpus form writes the file one line per
//! case that streams, in no fixed order: a JSON object
//! `{"task": <task id>, "case": <case>, "tokens": <the array above>}`, where
//! `<case>` is the spelling that `--case` takes, so the array equals what the
//! one-solver form prints for that case.

use std::fs::File;
use std::io::{BufWriter, Write};
use std::path::Path;
use std::process::ExitCode;
use std::sync::atomic::{AtomicUsize, Ordering};
use std::sync::Mutex;

use arclog::check::{CheckCache, CheckedProgram, SolverClauses};
use arclog::harness::{print_ended, read_corpus_solver, require_optimized_build, run_over_corpus, SolverResult};
use arclog::registry::Registry;
use arclog::resolver::resolve_cases;
use arclog::stream::{token_stream, DecodeSettings, Emitter, Token, Vocabulary};

use crate::concept_case::{case_spelled, check_case, check_cases};
use crate::replay::decoded_cases;
use crate::select::selected;

const USAGE: &str = "usage: arclog-cli stream <solver path> [--case <name>]\n       arclog-cli stream --corpus <corpus-dir> [--cases concept|all] [--out <file>] [<task_id> ...]";

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
    match stream_json(Path::new(path), case) {
        Ok(json) => {
            println!("{json}");
            ExitCode::SUCCESS
        }
        Err(fault) => {
            eprintln!("a fault that stops the stream: {fault}");
            ExitCode::FAILURE
        }
    }
}

/// The JSON of the token stream of the case `case` of the solver at `path`,
/// the concept case for `None`.
fn stream_json(path: &Path, case: Option<&str>) -> Result<String, String> {
    let id = path.file_stem().and_then(|stem| stem.to_str()).ok_or("the solver path names no file")?;
    let dir = path.parent().ok_or("the solver path has no directory")?;
    let solver = read_corpus_solver(dir, id).ok_or("the solver's files do not read")?;
    let registry = Registry::get();
    let cases = resolve_cases(&solver, registry);
    let clauses = SolverClauses::of_cases(&cases);
    let resolved = match case {
        None => cases.concept(),
        Some(wanted) => cases.cases().find(|case| case_spelled(&case.case.name) == wanted).ok_or_else(|| format!("the solver has no case {wanted}"))?,
    };
    let program = check_case(resolved, &clauses, &mut CheckCache::default(), "the case")?;
    let vocabulary = Vocabulary::new(registry, &DecodeSettings::default());
    let stream = case_stream(&program, &vocabulary)?;
    Ok(tokens_json(&stream, &vocabulary))
}

/// The JSON array of `stream`, one object per token.
fn tokens_json(stream: &[(Token, Emitter)], vocabulary: &Vocabulary) -> String {
    let tokens: Vec<String> = stream
        .iter()
        .map(|(token, emitter)| {
            let id = vocabulary.id(token).expect("the writer gives only tokens of the vocabulary");
            let emitter = match emitter {
                Emitter::Model => "model",
                Emitter::Engine => "engine",
            };
            format!("{{\"id\":{id},\"emitter\":\"{emitter}\"}}")
        })
        .collect();
    format!("[{}]", tokens.join(","))
}

/// The token stream of `program`, or the writer's fault.
fn case_stream(program: &CheckedProgram, vocabulary: &Vocabulary) -> Result<Vec<(Token, Emitter)>, String> {
    token_stream(program, vocabulary).map_err(|diagnostic| format!("the writer gives no stream: {}", diagnostic.message))
}

/// The subcommand's corpus form on `args`, the arguments after `--corpus`.
fn run_corpus(args: &[String]) -> ExitCode {
    if let Err(code) = require_optimized_build() {
        return code;
    }
    let Some((corpus, all, out, task_ids)) = parse_corpus(args) else {
        eprintln!("{USAGE}");
        return ExitCode::from(2);
    };
    let sink = match out.map(|path| File::create(&path).map(BufWriter::new).map_err(|error| format!("{path}: {error}"))).transpose() {
        Ok(file) => file.map(Mutex::new),
        Err(error) => {
            eprintln!("the stream file does not open: {error}");
            return ExitCode::from(2);
        }
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
            let lines = match stream_lines(Path::new(&corpus), &solver.task_id, all, sink.as_ref(), &streamed, &faulted) {
                Ok(lines) => lines,
                Err(fault) => vec![format!("{}: {fault}", solver.task_id)],
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
    if let Some(sink) = sink {
        if let Err(error) = sink.into_inner().unwrap_or_else(|poisoned| poisoned.into_inner()).flush() {
            eprintln!("the stream file does not write: {error}");
            return ExitCode::FAILURE;
        }
    }
    println!("corpus: {} cases streamed, {} cases whose stream faults", streamed.load(Ordering::Relaxed), faulted.load(Ordering::Relaxed));
    if report.failures.is_empty() { ExitCode::SUCCESS } else { ExitCode::FAILURE }
}

/// The corpus directory, whether `--cases all` is given, the `--out` file,
/// and the task ids, or `None` for arguments of another form.
fn parse_corpus(args: &[String]) -> Option<(String, bool, Option<String>, Vec<String>)> {
    let mut args = args.iter();
    let corpus = args.next()?.clone();
    let mut all = false;
    let mut out = None;
    let mut task_ids = Vec::new();
    while let Some(arg) = args.next() {
        if arg == "--cases" {
            all = match args.next()?.as_str() {
                "concept" => false,
                "all" => true,
                _ => return None,
            };
        } else if arg == "--out" {
            out = Some(args.next()?.clone());
        } else {
            task_ids.push(arg.clone());
        }
    }
    Some((corpus, all, out, task_ids))
}

/// The line of each case of the solver `id` of `corpus`, the concept case or
/// every case, with the counts of streams and of faults taken into
/// `streamed` and `faulted`, and each stream that succeeds written to `sink`
/// where given; or the fault that stops the solver's setup.
fn stream_lines(corpus: &Path, id: &str, all: bool, sink: Option<&Mutex<BufWriter<File>>>, streamed: &AtomicUsize, faulted: &AtomicUsize) -> Result<Vec<String>, String> {
    let solver = read_corpus_solver(corpus, id).ok_or("the solver's files do not read")?;
    let registry = Registry::get();
    let cases = resolve_cases(&solver, registry);
    let clauses = SolverClauses::of_cases(&cases);
    let wanted = decoded_cases(&cases, all);
    let programs = check_cases(&cases, &clauses, &mut CheckCache::default(), &|name| wanted.contains(name))?;
    let vocabulary = Vocabulary::new(registry, &DecodeSettings::default());
    let mut lines = Vec::new();
    for (name, program) in &programs {
        let outcome = match case_stream(program, &vocabulary) {
            Ok(stream) => {
                streamed.fetch_add(1, Ordering::Relaxed);
                if let Some(sink) = sink {
                    write_stream(sink, id, &case_spelled(name), &tokens_json(&stream, &vocabulary))?;
                }
                let model = stream.iter().filter(|(_, emitter)| *emitter == Emitter::Model).count();
                format!("{} tokens, {model} written by the model", stream.len())
            }
            Err(fault) => {
                faulted.fetch_add(1, Ordering::Relaxed);
                fault
            }
        };
        lines.push(format!("{id} {}: {outcome}", case_spelled(name)));
    }
    Ok(lines)
}

/// Writes to `sink` the line of the stream `tokens` of the case `case` of
/// the solver `task`.
fn write_stream(sink: &Mutex<BufWriter<File>>, task: &str, case: &str, tokens: &str) -> Result<(), String> {
    let line = format!("{{\"task\":{},\"case\":{},\"tokens\":{tokens}}}\n", serde_json::Value::from(task), serde_json::Value::from(case));
    let mut file = sink.lock().unwrap_or_else(|poisoned| poisoned.into_inner());
    file.write_all(line.as_bytes()).map_err(|error| format!("the stream file does not write: {error}"))
}
