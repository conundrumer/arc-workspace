//! `verdicts <corpus-dir> <tasks-dir> [<task_id> ...]`: replays every case
//! of each solver on the train pairs of its task, with no token mask, and
//! prints one tab-separated line per case,
//! `<task>\t<case>\t<concept 0|1>\t<verdict>\t<token index or ->\t<detail>`.
//!
//! The verdict is the consistency of the last `RULE` clause the stream ends
//! (`Consistent`, `NotConsistent`, `SeveralValues`, `Fault`, `Stopped`),
//! `NoRule` where it ends none, `Refused` where the decoder refuses the
//! stream, `NoStream` where the writer gives the case no stream, and
//! `Unread` (case `-`) for a solver whose files or task do not read. The
//! token index is that of the last `RULE` clause's end. The detail is the
//! bound for `Stopped`, the message for `Fault`, `Refused`, `NoStream` and
//! `Unread`, the relation (`&x`) whose several values keep every train pair
//! consistent for `SeveralValues`, and empty otherwise. The cases are the
//! solver's cases, which leave out each combination of alts that an `exclude`
//! form of its arcdata file matches. A case that holds a `DEMONSTRATED` form
//! prints no line, so a solver whose every case holds one prints none.

use std::collections::BTreeSet;
use std::io::Write;
use std::path::{Path, PathBuf};
use std::process::ExitCode;

use arclog::decode::corpus::{solver_verdicts, Verdict};
use arclog::harness::{require_optimized_build, run_over_corpus, SolverResult};
use arclog::algebra::tables::OrientationTables;
use arclog_constructions::shared as constructions;

const USAGE: &str = "usage: verdicts <corpus-dir> <tasks-dir> [<task_id> ...]";

fn main() -> ExitCode {
    // Reads and checks the orientation tables: a table that is not
    // D4-invariant stops the program here.
    OrientationTables::get();
    let args: Vec<String> = std::env::args().skip(1).collect();
    if let Err(code) = require_optimized_build() {
        return code;
    }
    let [corpus, tasks, task_ids @ ..] = args.as_slice() else {
        eprintln!("{USAGE}");
        return ExitCode::from(2);
    };
    let (corpus, tasks): (PathBuf, PathBuf) = (corpus.into(), tasks.into());
    let selected: Option<BTreeSet<String>> = (!task_ids.is_empty()).then(|| task_ids.iter().cloned().collect());
    let report = run_over_corpus(&corpus, selected.as_ref(), |solver| verdicts_solver(&corpus, &tasks, &solver.task_id), |solver, _| eprintln!("{}: ended", solver.task_id));
    match report {
        Ok(_) => ExitCode::SUCCESS,
        Err(error) => {
            eprintln!("the corpus does not read: {error:?}");
            ExitCode::from(2)
        }
    }
}

/// The lines of the solver `id`, printed together.
fn verdicts_solver(corpus: &Path, tasks: &Path, id: &str) -> SolverResult {
    let lines = match constructions().map_err(|fault| format!("a fault that stops the verdicts: {fault}")).and_then(|constructions| solver_verdicts(corpus, tasks, id, constructions)) {
        Ok(cases) => cases
            .into_iter()
            .map(|case| {
                let (verdict, detail) = match case.verdict {
                    Verdict::Consistent => ("Consistent", String::new()),
                    Verdict::NotConsistent => ("NotConsistent", String::new()),
                    Verdict::SeveralValues(relation) => ("SeveralValues", relation),
                    Verdict::Fault(message) => ("Fault", message),
                    Verdict::Stopped(stop) => ("Stopped", format!("{stop:?}")),
                    Verdict::NoRule => ("NoRule", String::new()),
                    Verdict::Refused(message) => ("Refused", message),
                    Verdict::NoStream(message) => ("NoStream", message),
                };
                let token = case.token.map_or("-".to_owned(), |index| index.to_string());
                format!("{id}\t{}\t{}\t{verdict}\t{token}\t{}", case.case, u8::from(case.concept), one_line(&detail))
            })
            .collect(),
        Err(fault) => vec![format!("{id}\t-\t0\tUnread\t-\t{}", one_line(&fault))],
    };
    let mut out = std::io::stdout().lock();
    for line in lines {
        writeln!(out, "{line}").expect("stdout takes a verdict line");
    }
    out.flush().expect("stdout takes a verdict line");
    SolverResult::Pass
}

/// `text` on one line, with its tabs and line breaks as spaces.
fn one_line(text: &str) -> String {
    text.replace(['\t', '\n', '\r'], " ")
}
