//! `check_one <corpus-dir> <task_id>`: the engine checker's diagnostics on
//! one solver of the corpus, one line each, `<kind:?> <message> at
//! <location:?>`, for `arclog-cli check-diff`.
//!
//! It prints each diagnostic of the read of the solver's two files, then of
//! the resolution of each case program, the concept case first, then of the
//! check of each. Where the read is refused, it prints the read's lines,
//! each line of the refusal led by `refused: `, and checks nothing.

use std::path::Path;
use std::process::ExitCode;
use std::sync::Arc;

use arclog::check::{check_program, CheckCache, SolverClauses};
use arclog::diagnostic::{Diagnostic, Severity};
use arclog::harness::read_corpus_solver;
use arclog::read::read_solver;
use arclog::registry::Registry;
use arclog::resolver::{resolve, ConceptReads};
use arclog::solver::Exclusion;

fn main() -> ExitCode {
    let args: Vec<String> = std::env::args().skip(1).collect();
    let [corpus, task_id] = &args[..] else {
        eprintln!("usage: check_one <corpus-dir> <task_id>");
        return ExitCode::from(2);
    };
    for line in check(Path::new(corpus), task_id) {
        println!("{line}");
    }
    ExitCode::SUCCESS
}

/// The line of `diagnostic`.
fn line(diagnostic: &Diagnostic) -> String {
    format!("{:?} {} at {:?}", diagnostic.kind, diagnostic.message, diagnostic.location)
}

/// Each line of the check of the solver `task_id` of `corpus`.
fn check(corpus: &Path, task_id: &str) -> Vec<String> {
    let file = |extension: &str| {
        let path = corpus.join(format!("{task_id}.{extension}"));
        std::fs::read_to_string(&path).map_err(|error| format!("refused: {} does not read: {error}", path.display()))
    };
    let (arclog, arcdata) = match (file("arclog"), file("arcdata")) {
        (Ok(arclog), Ok(arcdata)) => (arclog, arcdata),
        (Err(line), _) | (_, Err(line)) => return vec![line],
    };
    let read = match read_solver(task_id, &arclog, &arcdata, &|id| read_corpus_solver(corpus, id)) {
        Ok(read) => read,
        Err(refusal) => return refusal.iter().map(|d| format!("refused: {}", line(d))).collect(),
    };
    let mut lines: Vec<String> = read.diagnostics.iter().map(line).collect();
    if read.diagnostics.iter().any(|d| d.severity == Severity::Error) {
        return lines;
    }
    let solver = read.value;
    let registry = Registry::get();
    let derived = solver.derived_relations();
    let clauses = SolverClauses::of(&solver, registry);
    let concept_case = solver.concept_case();
    let concept = resolve(&concept_case.program, None, &derived, registry);
    lines.extend(concept.diagnostics.iter().map(line));
    let concept = Arc::new(concept.value);
    let mut programs = vec![(*concept).clone()];
    for case in solver.cases(Exclusion::WithExcluded) {
        if case.name == concept_case.name {
            continue;
        }
        let reads = ConceptReads { concept: &concept, determinations: case.concept_determinations() };
        let resolved = resolve(&case.program, Some(reads), &derived, registry);
        lines.extend(resolved.diagnostics.iter().map(line));
        programs.push(resolved.value);
    }
    let mut cache = CheckCache::default();
    for program in programs {
        if let Err(diagnostics) = check_program(program, &clauses, registry, &mut cache) {
            lines.extend(diagnostics.iter().map(line));
        }
    }
    lines
}
