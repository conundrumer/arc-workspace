//! A check run over every solver of the corpus on worker threads, and the report of the run.

use super::solvers::{corpus_solvers, CorpusError, CorpusSolver};
use std::any::Any;
use std::collections::BTreeSet;
use std::io::Write;
use std::panic::{catch_unwind, AssertUnwindSafe};
use std::path::Path;
use std::process::ExitCode;
use std::sync::atomic::{AtomicUsize, Ordering};

/// The outcome of a check on one solver.
#[derive(Clone, PartialEq, Eq, Debug)]
pub enum SolverResult {
    Pass,
    /// The check's report on the solver, one line per difference.
    Fail(Vec<String>),
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

/// The number of worker threads of a corpus run: the value of the
/// environment variable `ARCLOG_THREADS` where it is set, and otherwise the
/// number of threads the machine has. A set value that is not a positive
/// integer stops the process with exit code 2, after a message to stderr
/// that names the variable and the value, so a run never starts on a thread
/// count no one asked for.
pub fn corpus_threads() -> usize {
    match std::env::var("ARCLOG_THREADS") {
        Ok(value) => match value.parse::<usize>() {
            Ok(threads) if threads > 0 => threads,
            _ => refuse_threads(&value),
        },
        Err(std::env::VarError::NotUnicode(value)) => refuse_threads(&value.to_string_lossy()),
        Err(std::env::VarError::NotPresent) => std::thread::available_parallelism().map_or(1, |n| n.get()),
    }
}

fn refuse_threads(value: &str) -> ! {
    eprintln!("ARCLOG_THREADS must be a positive integer, and it holds {value:?}");
    std::process::exit(2)
}

/// Runs `work` over every item of `items`, on `threads` threads, each thread
/// taking the next item that none has taken, and gives the results in the
/// order of `items`. `work` does not panic.
pub fn run_on_workers<I: Sync, R: Send>(items: &[I], threads: usize, work: impl Fn(&I) -> R + Sync) -> Vec<R> {
    let next = AtomicUsize::new(0);
    // The requests that the workers begin leave their effort fault with the thread that calls this, which raises it.
    let sink = crate::eval::fault_sink();
    let mut results: Vec<(usize, R)> = std::thread::scope(|scope| {
        let workers: Vec<_> = (0..threads)
            .map(|_| {
                scope.spawn(|| {
                    crate::eval::adopt_fault_sink(&sink);
                    let mut done = Vec::new();
                    loop {
                        let index = next.fetch_add(1, Ordering::Relaxed);
                        let Some(item) = items.get(index) else { break done };
                        done.push((index, work(item)));
                    }
                })
            })
            .collect();
        workers.into_iter().flat_map(|w| w.join().expect("a worker over the items does not panic")).collect()
    });
    results.sort_by_key(|(index, _)| *index);
    results.into_iter().map(|(_, result)| result).collect()
}

/// Runs `check` over every solver of `dir` whose task id `selected` gives
/// (every solver where it is `None`), on the threads of
/// [`corpus_threads`] (`ARCLOG_THREADS`, or as many as the machine has), and
/// gives the report over them. The solvers start in the order of their
/// `.arclog` file size, largest first and ties in the order of their task
/// ids, so that no long solver starts last. A panic of `check` on a
/// solver is a failure of that solver, whose report is the panic's message.
/// As the check of a solver ends, the worker that ran it calls `ended` with
/// that solver and its result, so a run that stops before its last solver
/// ends has passed `ended` the result of each solver that ended.
/// `CorpusReport.checked` counts the solvers run.
pub fn run_over_corpus<F, E>(dir: &Path, selected: Option<&BTreeSet<String>>, check: F, ended: E) -> Result<CorpusReport, CorpusError>
where
    F: Fn(&CorpusSolver) -> SolverResult + Sync,
    E: Fn(&CorpusSolver, &SolverResult) + Sync,
{
    let mut solvers = corpus_solvers(dir)?;
    if let Some(ids) = selected {
        solvers.retain(|solver| ids.contains(&solver.task_id));
    }
    let sizes = solvers
        .iter()
        .map(|solver| std::fs::metadata(&solver.arclog).map(|meta| meta.len()).map_err(|error| CorpusError::Unreadable { path: solver.arclog.clone(), error }))
        .collect::<Result<Vec<u64>, _>>()?;
    let mut order: Vec<usize> = (0..solvers.len()).collect();
    order.sort_by_key(|&index| std::cmp::Reverse(sizes[index]));
    let by_size: Vec<&CorpusSolver> = order.iter().map(|&index| &solvers[index]).collect();
    let results = run_on_workers(&by_size, corpus_threads(), |solver| {
        let result = catch_unwind(AssertUnwindSafe(|| check(solver))).unwrap_or_else(|payload| SolverResult::Fail(vec![panic_line(&*payload)]));
        ended(solver, &result);
        result
    });
    let mut failed: Vec<(usize, Vec<String>)> = order
        .into_iter()
        .zip(results)
        .filter_map(|(index, result)| match result {
            SolverResult::Pass => None,
            SolverResult::Fail(report) => Some((index, report)),
        })
        .collect();
    failed.sort_by_key(|(index, _)| *index);
    let failures = failed.into_iter().map(|(index, report)| (solvers[index].clone(), report)).collect();
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

/// The message of a panic whose payload is `payload`, where the payload is a
/// `&str` or a `String`.
pub fn panic_message(payload: &(dyn Any + Send)) -> Option<&str> {
    payload.downcast_ref::<&str>().copied().or_else(|| payload.downcast_ref::<String>().map(String::as_str))
}

/// The line that reports a panic whose payload is `payload`: its message,
/// where the payload has one.
fn panic_line(payload: &(dyn Any + Send)) -> String {
    match panic_message(payload) {
        Some(message) => format!("the check panicked: {message}"),
        None => "the check panicked, with a payload that is not a message".to_owned(),
    }
}
