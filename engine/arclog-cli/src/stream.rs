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

use std::path::Path;
use std::process::ExitCode;

use arclog::check::{CheckCache, SolverClauses};
use arclog::harness::read_corpus_solver;
use arclog::registry::Registry;
use arclog::resolver::resolve_cases;
use arclog::stream::{token_stream, DecodeSettings, Emitter, Vocabulary};

use crate::concept_case::{case_spelled, check_case};

const USAGE: &str = "usage: arclog-cli stream <solver path> [--case <name>]";

/// The subcommand on `args`, the arguments after its name.
pub fn run(args: &[String]) -> ExitCode {
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
    let stream = token_stream(&program, &vocabulary).map_err(|diagnostic| format!("the writer gives no stream: {}", diagnostic.message))?;
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
    Ok(format!("[{}]", tokens.join(",")))
}
