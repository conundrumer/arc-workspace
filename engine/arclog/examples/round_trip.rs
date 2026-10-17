//! The end check of the reader and writer stage over the corpus: `cargo run
//! --example round_trip -- <dir> <report>`, with `<dir>` the corpus
//! directory, such as `work/arclog/gen/`, and `<report>` the Python lint's
//! output over `<dir>`, read by [`arclog::harness::LintReport`].
//!
//! The run reads each solver of `<dir>`, its `.arclog` and `.arcdata` files,
//! with [`arclog::read::read_solver`], through
//! [`arclog::harness::run_over_corpus`], where the solver a `representative`
//! line names is read from `<dir>` with `read_solver`, and writes back each
//! of the two files with [`arclog::write::write_arclog`] and
//! [`arclog::write::write_arcdata`]. A solver fails where its arcdata file
//! reads with a diagnostic, where its arclog file reads with a diagnostic
//! and the lint reports no error in it, and where a file that reads with no
//! diagnostic writes back other bytes. The run prints each file that reads
//! with a diagnostic and each failure, by task id, and a summary line that
//! counts the files of each kind that read with a diagnostic, and exits
//! nonzero where a solver fails or the directory is a fault.

use std::path::Path;
use std::process::ExitCode;
use std::sync::{Arc, Mutex};

use arclog::diagnostic::{Diagnostic, Location};
use arclog::harness::{run_over_corpus, CorpusSolver, LintReport, SolverResult};
use arclog::layout::SourceFile;
use arclog::read::read_solver;
use arclog::solver::Solver;
use arclog::write::{write_arcdata, write_arclog};

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

/// The solver of `task_id` read from its two files in `dir`, where both
/// read.
fn read_from(dir: &Path, task_id: &str) -> Option<Arc<Solver>> {
    let arclog = std::fs::read_to_string(dir.join(format!("{task_id}.arclog"))).ok()?;
    let arcdata = std::fs::read_to_string(dir.join(format!("{task_id}.arcdata"))).ok()?;
    let read = read_solver(task_id, &arclog, &arcdata, &|id| read_from(dir, id)).ok()?;
    Some(Arc::new(read.value))
}

/// The file `diagnostic` of a reader stands in: a reader's diagnostic stands
/// at one place.
fn file_of(diagnostic: &Diagnostic) -> SourceFile {
    match &diagnostic.location {
        Location::Places(places) => places.first().expect("a reader's diagnostic stands at a place").place.file,
        Location::Path(_) => panic!("a reader's diagnostic stands at a place of its file, not at a path"),
    }
}

/// The extension of a solver's file `file`.
fn extension(file: SourceFile) -> &'static str {
    match file {
        SourceFile::Arclog => "arclog",
        SourceFile::Arcdata => "arcdata",
        SourceFile::LibRegistry | SourceFile::LibProposers => panic!("a solver's reader reads no lib file"),
    }
}

/// The files that read with a diagnostic, each with its task id, its file
/// and its diagnostics.
type ReadWithDiagnostics = Mutex<Vec<(String, SourceFile, Vec<String>)>>;

fn round_trip(dir: &Path, solver: &CorpusSolver, report: &LintReport, read_with_diagnostics: &ReadWithDiagnostics) -> SolverResult {
    let read_text = |path: &Path| std::fs::read_to_string(path).map_err(|error| format!("{}: {error}", path.display()));
    let (arclog_text, arcdata_text) = match (read_text(&solver.arclog), read_text(&solver.arcdata)) {
        (Ok(arclog), Ok(arcdata)) => (arclog, arcdata),
        (a, b) => return SolverResult::Fail([a.err(), b.err()].into_iter().flatten().collect()),
    };
    let (read, diagnostics) = match read_solver(&solver.task_id, &arclog_text, &arcdata_text, &|id| read_from(dir, id)) {
        Ok(read) => (Some(read.value), read.diagnostics),
        Err(diagnostics) => (None, diagnostics),
    };
    let lines_of = |file: SourceFile| -> Vec<String> {
        diagnostics.iter().filter(|d| file_of(d) == file).map(describe).collect()
    };
    let (arclog_lines, arcdata_lines) = (lines_of(SourceFile::Arclog), lines_of(SourceFile::Arcdata));
    let mut failures = Vec::new();
    for (file, lines) in [(SourceFile::Arclog, &arclog_lines), (SourceFile::Arcdata, &arcdata_lines)] {
        if !lines.is_empty() {
            read_with_diagnostics.lock().expect("no check panics").push((solver.task_id.clone(), file, lines.clone()));
        }
    }
    if !arclog_lines.is_empty() {
        match report.passes(&solver.arclog) {
            Ok(true) => failures.extend(arclog_lines.iter().map(|line| format!("the lint passes the arclog file, which reads with: {line}"))),
            Ok(false) => {}
            Err(error) => failures.push(format!("{}: {error}", solver.arclog.display())),
        }
    }
    failures.extend(arcdata_lines.iter().map(|line| format!("the arcdata file reads with: {line}")));
    if let Some(read) = &read {
        if arclog_lines.is_empty() {
            let written = write_arclog(&read.program, &read.layout);
            if written != arclog_text {
                failures.push(format!("the arclog file: {}", first_difference(&arclog_text, &written)));
            }
        }
        if arcdata_lines.is_empty() {
            let written = write_arcdata(&read.arcdata, &read.layout);
            if written != arcdata_text {
                failures.push(format!("the arcdata file: {}", first_difference(&arcdata_text, &written)));
            }
        }
    }
    if failures.is_empty() { SolverResult::Pass } else { SolverResult::Fail(failures) }
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
    let result = run_over_corpus(Path::new(dir), |solver| round_trip(Path::new(dir), solver, &report, &read_with_diagnostics));
    let corpus = match result {
        Ok(corpus) => corpus,
        Err(error) => {
            eprintln!("{dir}: {error:?}");
            return ExitCode::FAILURE;
        }
    };
    let mut read_with_diagnostics = read_with_diagnostics.into_inner().expect("no check panics");
    read_with_diagnostics.sort();
    for (task_id, file, lines) in &read_with_diagnostics {
        for line in lines {
            println!("{task_id}.{}: reads with a diagnostic: {line}", extension(*file));
        }
    }
    for (solver, lines) in &corpus.failures {
        for line in lines {
            println!("{}: fails: {line}", solver.task_id);
        }
    }
    let count = |kind: SourceFile| read_with_diagnostics.iter().filter(|(_, file, _)| *file == kind).count();
    println!(
        "{} solvers checked: {} fail, {} arclog files and {} arcdata files read with a diagnostic",
        corpus.checked,
        corpus.failures.len(),
        count(SourceFile::Arclog),
        count(SourceFile::Arcdata)
    );
    if corpus.failures.is_empty() { ExitCode::SUCCESS } else { ExitCode::FAILURE }
}
