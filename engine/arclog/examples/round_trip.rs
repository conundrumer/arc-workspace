//! The end check of the reader and writer stage over the corpus: `cargo run
//! --example round_trip -- <dir> <report>`, with `<dir>` the corpus
//! directory, such as `work/arclog/gen/`, and `<report>` the Python lint's
//! output over `<dir>`, read by [`arclog::harness::LintReport`].
//!
//! The run reads the `.arclog` file of each solver of `<dir>` with
//! [`arclog::read::read_arclog`], through
//! [`arclog::harness::run_over_corpus`], and writes it back with
//! [`arclog::write::write_arclog`]. A solver fails where its file reads with
//! a diagnostic and the lint reports no error in it, and where its file
//! reads with no diagnostic and writes back other bytes. The run prints each
//! file that reads with a diagnostic and each failure, by task id, and exits
//! nonzero where a solver fails or the directory is a fault.

use std::path::Path;
use std::process::ExitCode;
use std::sync::Mutex;

use arclog::diagnostic::{Diagnostic, Location};
use arclog::harness::{run_over_corpus, CorpusSolver, LintReport, SolverResult};
use arclog::layout::SourceFile;

fn describe(diagnostic: &Diagnostic) -> String {
    match &diagnostic.location {
        Location::Places(places) => {
            let at: Vec<String> = places.iter().map(|p| format!("{}:{}", p.place.line, p.place.column)).collect();
            format!("{}: {}", at.join(", "), diagnostic.message)
        }
        Location::Path(path) => format!("{path:?}: {}", diagnostic.message),
    }
}

/// The first line at which `written` differs from `text`, with both lines.
fn first_difference(text: &str, written: &str) -> String {
    let mut original = text.split_inclusive('\n');
    let mut rewritten = written.split_inclusive('\n');
    for number in 1.. {
        match (original.next(), rewritten.next()) {
            (Some(a), Some(b)) if a == b => continue,
            (a, b) => {
                return format!(
                    "line {number} writes back {:?} in place of {:?}",
                    b.unwrap_or("<end of file>"),
                    a.unwrap_or("<end of file>")
                )
            }
        }
    }
    unreachable!("two texts that differ differ at a line")
}

fn round_trip(solver: &CorpusSolver, report: &LintReport, read_with_diagnostics: &Mutex<Vec<(String, Vec<String>)>>) -> SolverResult {
    let text = match std::fs::read_to_string(&solver.arclog) {
        Ok(text) => text,
        Err(error) => return SolverResult::Fail(vec![format!("{}: {error}", solver.arclog.display())]),
    };
    let diagnostics = match arclog::read::read_arclog(&text, SourceFile::Arclog) {
        Ok(read) if read.diagnostics.is_empty() => {
            let (program, layout) = read.value;
            let written = arclog::write::write_arclog(&program, &layout);
            return if written == text {
                SolverResult::Pass
            } else {
                SolverResult::Fail(vec![first_difference(&text, &written)])
            };
        }
        Ok(read) => read.diagnostics,
        Err(diagnostics) => diagnostics,
    };
    let lines: Vec<String> = diagnostics.iter().map(describe).collect();
    read_with_diagnostics.lock().expect("no check panics").push((solver.task_id.clone(), lines.clone()));
    match report.passes(&solver.arclog) {
        Ok(true) => SolverResult::Fail(lines.into_iter().map(|line| format!("the lint passes the file, which reads with: {line}")).collect()),
        Ok(false) => SolverResult::Pass,
        Err(error) => SolverResult::Fail(vec![format!("{}: {error}", solver.arclog.display())]),
    }
}

fn main() -> ExitCode {
    let args: Vec<String> = std::env::args().skip(1).collect();
    let [dir, report] = &args[..] else {
        eprintln!("usage: cargo run --example round_trip -- <dir> <report>");
        return ExitCode::FAILURE;
    };
    let report = match std::fs::read_to_string(report) {
        Ok(text) => LintReport::parse(&text),
        Err(error) => {
            eprintln!("{report}: {error}");
            return ExitCode::FAILURE;
        }
    };
    let read_with_diagnostics = Mutex::new(Vec::new());
    let result = run_over_corpus(Path::new(dir), |solver| round_trip(solver, &report, &read_with_diagnostics));
    let corpus = match result {
        Ok(corpus) => corpus,
        Err(error) => {
            eprintln!("{dir}: {error:?}");
            return ExitCode::FAILURE;
        }
    };
    let mut read_with_diagnostics = read_with_diagnostics.into_inner().expect("no check panics");
    read_with_diagnostics.sort();
    for (task_id, lines) in &read_with_diagnostics {
        for line in lines {
            println!("{task_id}: reads with a diagnostic: {line}");
        }
    }
    for (solver, lines) in &corpus.failures {
        for line in lines {
            println!("{}: fails: {line}", solver.task_id);
        }
    }
    println!(
        "{} files checked: {} fail, {} read with a diagnostic",
        corpus.checked,
        corpus.failures.len(),
        read_with_diagnostics.len()
    );
    if corpus.failures.is_empty() { ExitCode::SUCCESS } else { ExitCode::FAILURE }
}
