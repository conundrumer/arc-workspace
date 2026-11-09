//! The end check of the reader and writer stage over the corpus: `cargo run
//! --example round_trip -- <dir> <report>`, with `<dir>` the corpus
//! directory, such as `programs/arclog/`, and `<report>` the Python lint's
//! `--all` output over `<dir>`, read by [`arclog::harness::LintReport`].
//!
//! The run reads each solver of `<dir>`, its `.arclog` and `.arcdata` files,
//! with [`arclog::read::read_solver`], through
//! [`arclog::harness::run_over_corpus`], where the solver a `representative`
//! line names is read from `<dir>` with `read_solver`, and writes back each
//! of the two files with [`arclog::write::write_arclog`] and
//! [`arclog::write::write_arcdata`]. A solver fails where its arcdata file
//! reads with a diagnostic, where its arclog file reads with a diagnostic
//! and the lint reports no error in it, where the layout of a file that
//! reads with no diagnostic keys its nodes at other paths than those the
//! walk of [`arclog::program::path::NodeRef::children`] or
//! [`arclog::program::path::DataNodeRef::children`] reaches from the file's
//! root, each bare-label argument of a site left out, with a failure for
//! each path that one of the two sets holds and the other does not, and
//! where a file that reads with no diagnostic writes back other bytes. The
//! writers find each node's layout at the path that walk gives it, so the
//! byte check also fails a file whose layout keys a node at a path where
//! the walk reaches another node, unless the two nodes write the same text.
//! The run prints each file that reads with a diagnostic and each failure,
//! by task id, and a summary line that counts the files of each kind that
//! read with a diagnostic, and exits nonzero where a solver fails or the
//! directory is a fault.

use std::collections::BTreeSet;
use std::path::Path;
use std::process::ExitCode;
use std::sync::Mutex;

use arclog::diagnostic::{Diagnostic, Location};
use arclog::harness::{run_over_corpus, CorpusSolver, LintReport, SolverResult};
use arclog::harness::{read_corpus_solver, require_optimized_build};
use arclog::layout::{Layout, SourceFile};
use arclog::program::path::{DataNodeRef, NodePath, NodeRef};
use arclog::read::read_solver;
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

/// The path of each node below `root` that a walk of `children` reaches,
/// the root's included, and each `kept` keeps.
fn walked<N: Copy>(root: N, children: fn(N) -> Vec<N>, kept: fn(N) -> bool) -> BTreeSet<NodePath> {
    let mut paths = BTreeSet::new();
    let mut stack = vec![(root, NodePath::default())];
    while let Some((node, path)) = stack.pop() {
        for (index, child) in children(node).into_iter().enumerate() {
            stack.push((child, path.child(index as u32)));
        }
        if kept(node) {
            paths.insert(path);
        }
    }
    paths
}

/// A line for each path of `file` that `layout` keys and `walk` does not
/// hold, and for each that `walk` holds and `layout` does not key.
fn key_mismatches(layout: &Layout, file: SourceFile, walk: &BTreeSet<NodePath>) -> Vec<String> {
    let keyed: BTreeSet<&NodePath> = layout.nodes.keys().filter(|(f, _)| *f == file).map(|(_, path)| path).collect();
    let name = extension(file);
    let unwalked = keyed.iter().filter(|path| !walk.contains(**path));
    let unkeyed = walk.iter().filter(|path| !keyed.contains(path));
    unwalked
        .map(|path| format!("the {name} file: the layout keys a node at {path:?}, which the walk of the path table does not reach"))
        .chain(unkeyed.map(|path| format!("the {name} file: the walk of the path table reaches a node at {path:?}, which the layout does not key")))
        .collect()
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
    let (read, diagnostics) = match read_solver(&solver.task_id, &arclog_text, &arcdata_text, &|id| read_corpus_solver(dir, id).ok()) {
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
            let walk = walked(NodeRef::Program(read.program.value()), NodeRef::children, |node| !matches!(node, NodeRef::Label(_)));
            failures.extend(key_mismatches(&read.layout, SourceFile::Arclog, &walk));
            let written = write_arclog(&read.program, &read.layout);
            if written != arclog_text {
                failures.push(format!("the arclog file: {}", first_difference(&arclog_text, &written)));
            }
        }
        if arcdata_lines.is_empty() {
            let walk = walked(DataNodeRef::Arcdata(read.arcdata.value()), DataNodeRef::children, |_| true);
            failures.extend(key_mismatches(&read.layout, SourceFile::Arcdata, &walk));
            let written = write_arcdata(&read.arcdata, &read.layout);
            if written != arcdata_text {
                failures.push(format!("the arcdata file: {}", first_difference(&arcdata_text, &written)));
            }
        }
    }
    if failures.is_empty() { SolverResult::Pass } else { SolverResult::Fail(failures) }
}

fn main() -> ExitCode {
    if let Err(code) = require_optimized_build() {
        return code;
    }
    let args: Vec<String> = std::env::args().skip(1).collect();
    let [dir, report] = &args[..] else {
        eprintln!("usage: cargo run --profile tool --example round_trip -- <dir> <report>");
        return ExitCode::FAILURE;
    };
    let report = match LintReport::read(Path::new(report)) {
        Ok(report) => report,
        Err(error) => {
            eprintln!("{report}: {error}");
            return ExitCode::FAILURE;
        }
    };
    let read_with_diagnostics = Mutex::new(Vec::new());
    let result = run_over_corpus(Path::new(dir), None, |solver| round_trip(Path::new(dir), solver, &report, &read_with_diagnostics), |_, _| ());
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
