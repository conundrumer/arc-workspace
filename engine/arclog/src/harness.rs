//! The corpus harness: runs a check over every solver of the corpus.
//!
//! The end check over the corpus of each stage that has one, the examples
//! `round_trip`, `resolve`, `cases` and `lint`, runs through
//! [`run_over_corpus`]. Together they pass where every file the Python lint
//! passes reads, resolves and round-trips, and where the engine reports each
//! error the Python lint reports from the engine's checks, at the same
//! place, and no other. The representations and programs-as-values stages
//! have no example of their own: the other stages' end checks run their
//! bodies.

use std::any::Any;
use std::io::Write;
use std::panic::{catch_unwind, AssertUnwindSafe};
use std::path::{Path, PathBuf};
use std::process::ExitCode;
use std::sync::atomic::{AtomicUsize, Ordering};

/// One solver of the corpus: its task id and its two files.
#[derive(Clone, PartialEq, Eq, Debug)]
pub struct CorpusSolver {
    pub task_id: String,
    pub arclog: PathBuf,
    pub arcdata: PathBuf,
}

/// A fault of the corpus directory: it cannot be read, or an `.arclog` file
/// has no `.arcdata` file beside it, or the reverse.
#[derive(Debug)]
pub enum CorpusError {
    Unreadable { path: PathBuf, error: std::io::Error },
    MissingFile { path: PathBuf },
}

/// The solvers of `dir`, in the order of their task ids: one for each
/// `.arclog` file, whose `.arcdata` file stands beside it. The listing
/// passes over each file of another extension.
pub fn corpus_solvers(dir: &Path) -> Result<Vec<CorpusSolver>, CorpusError> {
    let unreadable = |path: &Path, error| CorpusError::Unreadable { path: path.to_owned(), error };
    let mut arclog = std::collections::BTreeSet::new();
    let mut arcdata = std::collections::BTreeSet::new();
    for entry in std::fs::read_dir(dir).map_err(|e| unreadable(dir, e))? {
        let path = entry.map_err(|e| unreadable(dir, e))?.path();
        let (Some(stem), Some(extension)) = (path.file_stem().and_then(|s| s.to_str()), path.extension()) else {
            continue;
        };
        match extension.to_str() {
            Some("arclog") => arclog.insert(stem.to_owned()),
            Some("arcdata") => arcdata.insert(stem.to_owned()),
            _ => continue,
        };
    }
    let file = |task_id: &str, extension: &str| dir.join(format!("{task_id}.{extension}"));
    if let Some(task_id) = arclog.symmetric_difference(&arcdata).next() {
        let extension = if arclog.contains(task_id) { "arcdata" } else { "arclog" };
        return Err(CorpusError::MissingFile { path: file(task_id, extension) });
    }
    Ok(arclog
        .into_iter()
        .map(|task_id| CorpusSolver { arclog: file(&task_id, "arclog"), arcdata: file(&task_id, "arcdata"), task_id })
        .collect())
}

/// The solver of `task_id` read from its two files in `dir`, each solver a
/// `representative` line names read the same way. `None` where a file does
/// not read, or where a diagnostic of the read has
/// [`crate::diagnostic::Severity::Error`]. So a solver whose
/// `representative` line names a solver whose read is refused is `None`
/// too, by the scope diagnostic of [`crate::read::read_solver`].
pub fn read_corpus_solver(dir: &Path, task_id: &str) -> Option<std::sync::Arc<crate::solver::Solver>> {
    let arclog = std::fs::read_to_string(dir.join(format!("{task_id}.arclog"))).ok()?;
    let arcdata = std::fs::read_to_string(dir.join(format!("{task_id}.arcdata"))).ok()?;
    let read = crate::read::read_solver(task_id, &arclog, &arcdata, &|id| read_corpus_solver(dir, id)).ok()?;
    if read.diagnostics.iter().any(|d| d.severity == crate::diagnostic::Severity::Error) {
        return None;
    }
    Some(std::sync::Arc::new(read.value))
}

/// The outcome of a check on one solver.
#[derive(Clone, PartialEq, Eq, Debug)]
pub enum SolverResult {
    Pass,
    /// The check's report on the solver, one line per difference.
    Fail(Vec<String>),
}

/// The Python lint's report over the corpus: one line
/// `<path>:<line>: <check>: <message>` per error, then a summary that the
/// parse skips.
#[derive(Clone, Debug, Default)]
pub struct LintReport {
    /// Each error of the report, in the report's order.
    pub errors: Vec<LintError>,
}

/// One error of the Python lint's report.
#[derive(Clone, PartialEq, Eq, Debug)]
pub struct LintError {
    pub path: PathBuf,
    pub line: u32,
    pub check: String,
    pub message: String,
}

impl LintError {
    /// The error that `line` gives, where it has the form
    /// `<path>:<line>: <check>: <message>`.
    fn parse(line: &str) -> Option<LintError> {
        let (path, rest) = line.split_once(':')?;
        let (number, rest) = rest.split_once(": ")?;
        let (check, message) = rest.split_once(": ")?;
        Some(LintError {
            path: PathBuf::from(path),
            line: number.parse().ok()?,
            check: check.to_owned(),
            message: message.to_owned(),
        })
    }
}

impl LintReport {
    /// The report that `text` gives: each line of the error form, the
    /// summary's lines left out.
    pub fn parse(text: &str) -> LintReport {
        LintReport { errors: text.lines().filter_map(LintError::parse).collect() }
    }

    /// Whether the lint reports no error in the file at `path`: no error's
    /// path names the file that `path` names, once each resolves to its
    /// canonical path. An error whose path resolves to no file names none.
    /// Fails where `path` resolves to no file.
    pub fn passes(&self, path: &Path) -> std::io::Result<bool> {
        let file = std::fs::canonicalize(path)?;
        Ok(!self.errors.iter().any(|error| std::fs::canonicalize(&error.path).is_ok_and(|p| p == file)))
    }
}

/// The solvers of the corpus on which `check` failed, with its report.
#[derive(Clone, PartialEq, Eq, Debug)]
pub struct CorpusReport {
    /// The number of solvers the check ran on.
    pub checked: usize,
    /// Each solver the check failed on, with the check's report on it, in
    /// the order of their task ids.
    pub failures: Vec<(CorpusSolver, Vec<String>)>,
}

/// The refusal of a corpus run on a build without optimization: on such a
/// build, it prints the refusal to stderr and gives the exit code 2 of a
/// usage error. Each corpus run calls it before it reads its arguments, and
/// exits with the code it gives. [`run_over_corpus`] does not call it, as
/// the tests, which run on a debug build, call that function.
pub fn require_optimized_build() -> Result<(), ExitCode> {
    if cfg!(debug_assertions) {
        eprintln!("a corpus run needs an optimized build: run it with `cargo run --profile tool` in place of `cargo run`");
        Err(ExitCode::from(2))
    } else {
        Ok(())
    }
}

/// Runs `check` over every solver of `dir`, on as many threads as the
/// machine has, and gives the report over them. A panic of `check` on a
/// solver is a failure of that solver, whose report is the panic's message.
/// As the check of a solver ends, the worker that ran it calls `ended` with
/// that solver and its result, so a run that stops before its last solver
/// ends has passed `ended` the result of each solver that ended.
pub fn run_over_corpus<F, E>(dir: &Path, check: F, ended: E) -> Result<CorpusReport, CorpusError>
where
    F: Fn(&CorpusSolver) -> SolverResult + Sync,
    E: Fn(&CorpusSolver, &SolverResult) + Sync,
{
    let solvers = corpus_solvers(dir)?;
    let next = AtomicUsize::new(0);
    let threads = std::thread::available_parallelism().map_or(1, |n| n.get());
    let mut results: Vec<(usize, SolverResult)> = std::thread::scope(|scope| {
        let workers: Vec<_> = (0..threads)
            .map(|_| {
                scope.spawn(|| {
                    let mut done = Vec::new();
                    loop {
                        let index = next.fetch_add(1, Ordering::Relaxed);
                        let Some(solver) = solvers.get(index) else { break done };
                        let result = catch_unwind(AssertUnwindSafe(|| check(solver)))
                            .unwrap_or_else(|payload| SolverResult::Fail(vec![panic_line(&*payload)]));
                        ended(solver, &result);
                        done.push((index, result));
                    }
                })
            })
            .collect();
        workers.into_iter().flat_map(|w| w.join().expect("a check over the corpus does not panic")).collect()
    });
    results.sort_by_key(|(index, _)| *index);
    let failures = results
        .into_iter()
        .filter_map(|(index, result)| match result {
            SolverResult::Pass => None,
            SolverResult::Fail(report) => Some((solvers[index].clone(), report)),
        })
        .collect();
    Ok(CorpusReport { checked: solvers.len(), failures })
}

/// The `ended` of [`run_over_corpus`] for a corpus run that prints its
/// failures: it prints each line of a failure of `solver` to stdout as
/// `<task_id>: <line>`, then flushes stdout, so each line stands in the
/// output once the solver has ended, and then prints `<task_id>: ended` to
/// stderr, whatever the result.
pub fn print_ended(solver: &CorpusSolver, result: &SolverResult) {
    if let SolverResult::Fail(lines) = result {
        let mut out = std::io::stdout().lock();
        for line in lines {
            writeln!(out, "{}: {line}", solver.task_id).expect("stdout takes a failure line");
        }
        out.flush().expect("stdout takes a failure line");
    }
    eprintln!("{}: ended", solver.task_id);
}

/// The line that reports a panic whose payload is `payload`: its message,
/// where the payload is a `&str` or a `String`.
fn panic_line(payload: &(dyn Any + Send)) -> String {
    let message = payload.downcast_ref::<&str>().copied().or_else(|| payload.downcast_ref::<String>().map(String::as_str));
    match message {
        Some(message) => format!("the check panicked: {message}"),
        None => "the check panicked, with a payload that is not a message".to_owned(),
    }
}
