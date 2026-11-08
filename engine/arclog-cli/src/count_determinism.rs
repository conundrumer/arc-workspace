//! `count-determinism`: checks that the work count of a request, its effort,
//! and its stop at the request work cap, do not depend on what the session's
//! caches held.
//!
//! For each solver, one request evaluates the entries of the concept case
//! (the relations the `OUT` form reads, on each example they hold rows on),
//! as `determinism` lists them. The request runs in a session with cold
//! caches, and again in sessions that earlier requests filled in other ways:
//! the same entries in the reverse order, the first half of the entries, the
//! same entries once more, and, at the same time, on several threads that
//! share one session and each run a request of its own, at each thread count
//! given, so that a count that thread scheduling moves differs at some count. Each run must give the
//! same count of request work, the same largest value, cap and hits in each
//! gauge that a request keeps, and the same value or stop for each entry. The
//! runs repeat under caps that the cold count sets: at the cold count, one
//! below it, and a half and a tenth of it, so the stops are compared too.
//!
//! The report names task ids and counts, never rows.
//!
//! Its arguments: the corpus directory, the directory of the task files, the
//! thread counts of the shared-session runs, comma-separated, then the task
//! ids of the solvers to run.

use std::path::{Path, PathBuf};
use std::process::ExitCode;

use arclog::check::{CheckCache, SolverClauses};
use arclog::decode::corpus::{corpus_session, read_corpus_task};
use arclog::eval::{Cancellation, Gauge, Limits, ParameterValues, RelationValue};
use arclog::harness::require_optimized_build;
use arclog::judge::determination::DeterminedCase;
use arclog::registry::Registry;
use arclog::resolver::resolve_cases;
use arclog::session::TaskSession;
use arclog::stream::corpus::check_case;
use arclog_constructions::shared as constructions;

use crate::determinism::{entries, Entry};

const USAGE: &str = "usage: arclog-cli count-determinism <corpus-dir> <tasks-dir> <threads>[,<threads>...] <task_id> [<task_id> ...]";

/// The subcommand on `args`, the arguments after its name.
pub fn run(args: &[String]) -> ExitCode {
    if let Err(code) = require_optimized_build() {
        return code;
    }
    let [corpus, tasks, threads, ids @ ..] = args else {
        eprintln!("{USAGE}");
        return ExitCode::from(2);
    };
    let Some(threads) = threads.split(',').map(|count| count.parse::<usize>().ok().filter(|&n| n > 0)).collect::<Option<Vec<usize>>>() else {
        eprintln!("{USAGE}");
        return ExitCode::from(2);
    };
    if ids.is_empty() {
        eprintln!("{USAGE}");
        return ExitCode::from(2);
    }
    let (corpus, tasks) = (PathBuf::from(corpus), PathBuf::from(tasks));
    let mut differences = 0usize;
    for id in ids {
        match check(&corpus, &tasks, id, &threads) {
            Ok(lines) => {
                differences += lines.iter().filter(|line| line.contains("DIFFERS")).count();
                lines.iter().for_each(|line| println!("{line}"));
            }
            Err(fault) => println!("{id}: not compared: {fault}"),
        }
    }
    println!("{differences} runs differ from the run with cold caches");
    if differences == 0 { ExitCode::SUCCESS } else { ExitCode::FAILURE }
}

/// What one request gave: its work count, its gauges, and the value of each
/// of its entries, in the order the request evaluated them.
#[derive(Clone, PartialEq, Debug)]
struct Seen {
    count: u64,
    gauges: Vec<(&'static str, u64, u64, u64)>,
    outcomes: Vec<String>,
}

/// The lines for the solver `id`, one for each run and cap.
fn check(corpus: &Path, tasks: &Path, id: &str, counts: &[usize]) -> Result<Vec<String>, String> {
    let read = read_corpus_task(corpus, tasks, id)?;
    let (solver, task) = (read.solver, read.task);
    let registry = Registry::get();
    let cases = resolve_cases(&solver, registry);
    let clauses = SolverClauses::of_cases(&cases);
    let concept = check_case(&solver, cases.concept(), &clauses, &mut CheckCache::default(), "the concept case", false)?;
    let parameters = ParameterValues::stored(solver.arcdata.value());
    let constructions = constructions()?;
    let name = &cases.concept().case.name;
    let request = |session: &TaskSession, cap: Option<u64>, listed: Option<&[Entry]>| -> (Seen, Vec<Entry>) {
        let limits = Limits::new(cap, Cancellation::default());
        let case = DeterminedCase { name, program: &concept, concept: &concept, task: &task, session, registry, constructions, limits: &limits };
        let evaluation = case.evaluation(&parameters);
        let entries = listed.map_or_else(|| entries(&evaluation), <[Entry]>::to_vec);
        let outcomes = entries
            .iter()
            .map(|(relation, example)| match evaluation.relation(relation, *example) {
                Ok(RelationValue::Rows(rows)) => format!("rows {}", rows.len()),
                Ok(RelationValue::Undefined) => "undefined".to_owned(),
                Ok(RelationValue::Stopped(stop)) => format!("stopped {:?} at {:?}", stop.bound, stop.form),
                Err(fault) => format!("fault at {:?}", fault.form),
            })
            .collect();
        // The session's bytes depend on the machine's heap, and the labeling nodes are the process's.
        let gauges = limits.request.gauges().each().into_iter().filter(|(gauge, ..)| !matches!(gauge, Gauge::SessionBytes | Gauge::LabelingNodes)).map(|(gauge, max, cap, hits)| (gauge.name(), max, cap, hits)).collect();
        (Seen { count: limits.request.count(), gauges, outcomes }, entries)
    };
    let cold_session = corpus_session();
    let started = std::time::Instant::now();
    let (cold, listed) = request(&cold_session, None, None);
    let seconds = started.elapsed().as_secs_f64();
    let mut caps = vec![None, Some(cold.count), Some(cold.count.saturating_sub(1)), Some(cold.count / 2), Some((cold.count / 10).max(1))];
    caps.dedup();
    let (entries_held, _, bytes, _, _) = cold_session.results.stats();
    let cost_bytes = std::mem::size_of::<arclog::eval::Cost>();
    let mut lines = vec![format!(
        "{id}: the request with cold caches took {seconds:.2} s and counted {} units of work; the result cache holds {entries_held} entries and {bytes} bytes, of which {} bytes are the entries' costs ({cost_bytes} bytes each)",
        cold.count,
        entries_held * cost_bytes
    )];
    for cap in caps {
        let base = if cap.is_none() { cold.clone() } else { request(&corpus_session(), cap, Some(&listed)).0 };
        let reversed: Vec<Entry> = listed.iter().rev().cloned().collect();
        let half = &listed[..listed.len() / 2];
        let runs: Vec<(String, Seen)> = vec![
            ("after the entries in reverse".to_owned(), {
                let session = corpus_session();
                request(&session, None, Some(&reversed));
                request(&session, cap, Some(&listed)).0
            }),
            ("after the first half of the entries".to_owned(), {
                let session = corpus_session();
                request(&session, None, Some(half));
                request(&session, cap, Some(&listed)).0
            }),
            ("after the same entries".to_owned(), {
                let session = corpus_session();
                request(&session, None, Some(&listed));
                request(&session, cap, Some(&listed)).0
            }),
        ];
        let mut shared = Vec::new();
        for &threads in counts {
            let session = corpus_session();
            let seen: Vec<Seen> = std::thread::scope(|scope| {
                let handles: Vec<_> = (0..threads).map(|_| scope.spawn(|| request(&session, cap, Some(&listed)).0)).collect();
                handles.into_iter().map(|handle| handle.join().expect("a request that no panic ends")).collect()
            });
            shared.extend(seen.into_iter().enumerate().map(|(at, seen)| (format!("on thread {at} of {threads} sharing a session"), seen)));
        }
        for (run, seen) in runs.into_iter().chain(shared) {
            lines.push(compare(id, cap, &run, &base, &seen));
        }
    }
    Ok(lines)
}

/// The line for `seen`, a run named `run` under `cap`, against `base`, the
/// run with cold caches under the same cap.
fn compare(id: &str, cap: Option<u64>, run: &str, base: &Seen, seen: &Seen) -> String {
    let at = format!("{id} cap {cap:?} {run}");
    if seen == base {
        return format!("{at}: same, count {}", seen.count);
    }
    let mut parts = Vec::new();
    if seen.count != base.count {
        parts.push(format!("count {} against {}", seen.count, base.count));
    }
    for (a, b) in seen.gauges.iter().zip(&base.gauges) {
        if a != b {
            parts.push(format!("gauge {} (max, cap, hits) {:?} against {:?}", a.0, (a.1, a.2, a.3), (b.1, b.2, b.3)));
        }
    }
    if let Some(place) = seen.outcomes.iter().zip(&base.outcomes).position(|(a, b)| a != b) {
        parts.push(format!("entry {place}: {} against {}", seen.outcomes[place], base.outcomes[place]));
    }
    format!("{at}: DIFFERS, {}", parts.join("; "))
}
