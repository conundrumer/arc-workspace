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
//!
//! Each of them reads the Python lint's report as [`LintReport`] gives it:
//! the output of `src/arclog_convert/lint.py --all`.

use std::any::Any;
use std::collections::BTreeSet;
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

/// The extension of a solver's file that holds `file`: `None` for a lib file.
pub fn solver_file_extension(file: crate::layout::SourceFile) -> Option<&'static str> {
    use crate::layout::SourceFile;
    match file {
        SourceFile::Arclog => Some("arclog"),
        SourceFile::Arcdata => Some("arcdata"),
        SourceFile::LibRegistry | SourceFile::LibProposers => None,
    }
}

/// The solver of `task_id` read from its two files in `dir`, each solver a
/// `representative` line names read the same way. `Err` where a file does
/// not read, as `<path>: <io error>`, or where the read is refused or has a
/// diagnostic of [`crate::diagnostic::Severity::Error`]: each such
/// diagnostic as `<task_id>.<extension>:<line>: <message>` per place, or the
/// message alone at a path, joined by `; `. A solver whose `representative`
/// line names a solver that does not read gives the scope diagnostic of
/// [`crate::read::read_solver`].
pub fn read_corpus_solver(dir: &Path, task_id: &str) -> Result<std::sync::Arc<crate::solver::Solver>, String> {
    use crate::diagnostic::{Diagnostic, Location, Severity};
    let read_file = |extension: &str| {
        let path = dir.join(format!("{task_id}.{extension}"));
        std::fs::read_to_string(&path).map_err(|e| format!("{}: {e}", path.display()))
    };
    let arclog = read_file("arclog")?;
    let arcdata = read_file("arcdata")?;
    let describe = |diagnostics: &[Diagnostic]| {
        let mut lines = Vec::new();
        for d in diagnostics.iter().filter(|d| d.severity == Severity::Error) {
            match &d.location {
                Location::Places(places) => {
                    for at in places.iter() {
                        let extension = solver_file_extension(at.place.file).unwrap_or("lib");
                        let id = at.task_id.as_deref().unwrap_or(task_id);
                        lines.push(format!("{id}.{extension}:{}: {}", at.place.line, d.message));
                    }
                }
                Location::Path(_) => lines.push(d.message.to_string()),
            }
        }
        lines.join("; ")
    };
    let read = crate::read::read_solver(task_id, &arclog, &arcdata, &|id| read_corpus_solver(dir, id).ok()).map_err(|d| describe(&d))?;
    if read.diagnostics.iter().any(|d| d.severity == Severity::Error) {
        return Err(describe(&read.diagnostics));
    }
    Ok(std::sync::Arc::new(read.value))
}

/// The outcome of a check on one solver.
#[derive(Clone, PartialEq, Eq, Debug)]
pub enum SolverResult {
    Pass,
    /// The check's report on the solver, one line per difference.
    Fail(Vec<String>),
}

/// The Python lint's report over the corpus: the output of
/// `src/arclog_convert/lint.py --all`, whose `main` prints one line
/// `<path>:<line>: <code>: <message>` per error, then a blank line, one
/// line `  <code> <n> in <k> files` per code, and one line
/// `<clean> of <n> <suffix> files clean` per file suffix. Without `--all`,
/// over more than 20 files, the lint prints at most four error lines of
/// each code, and [`LintReport::parse`] refuses that output.
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
    pub check: LintCode,
    pub message: String,
}

/// The table of [`LintCode`]: each variant with its spelling in the lint's
/// report.
macro_rules! lint_codes {
    ($($variant:ident => $spelling:literal,)*) => {
        /// A code that `src/arclog_convert/lint.py` reports: one variant per
        /// code that it passes to an `err` call.
        #[derive(Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Hash, Debug)]
        pub enum LintCode {
            $($variant,)*
        }

        impl LintCode {
            /// Every code, in the order of their spellings.
            pub const ALL: &[LintCode] = &[$(LintCode::$variant,)*];

            /// The code's spelling in the lint's report.
            pub fn spelling(self) -> &'static str {
                match self {
                    $(LintCode::$variant => $spelling,)*
                }
            }
        }
    };
}

lint_codes! {
    All => "all",
    AltClaim => "alt-claim",
    AltCols => "alt-cols",
    AltCombination => "alt-combination",
    AltSame => "alt-same",
    AltTail => "alt-tail",
    Alts => "alts",
    AltsEmpty => "alts-empty",
    Approximated => "approximated",
    ArcdataHead => "arcdata-head",
    ArcdataName => "arcdata-name",
    ArcdataOrder => "arcdata-order",
    Assign => "assign",
    Atom => "atom",
    BareInit => "bare-init",
    Body => "body",
    BroadcastInside => "broadcast-inside",
    Choose => "choose",
    ChooseNoNever => "choose-no-never",
    ChooseOne => "choose-one",
    Claim => "claim",
    ClaimText => "claim-text",
    Clause => "clause",
    ClauseTwice => "clause-twice",
    Column => "column",
    Component => "component",
    ConceptEmpty => "concept-empty",
    Constraint => "constraint",
    Count => "count",
    CountPlace => "count-place",
    Cycle => "cycle",
    DemoRule => "demo-rule",
    DetOrRule => "det-or-rule",
    Elide => "elide",
    EmptyGloss => "empty-gloss",
    EqMake => "eq-make",
    EqMark => "eq-mark",
    EqOrder => "eq-order",
    EqSameList => "eq-same-list",
    EqSite => "eq-site",
    EqUnexported => "eq-unexported",
    Exclude => "exclude",
    FieldCase => "field-case",
    Form => "form",
    FreshHere => "fresh-here",
    GridLayout => "grid-layout",
    HeadSite => "head-site",
    HeadZero => "head-zero",
    If => "if",
    InitOrder => "init-order",
    Input => "input",
    InputTwice => "input-twice",
    Instance => "instance",
    KeyForm => "key-form",
    KeyLocal => "key-local",
    KeySite => "key-site",
    Label => "label",
    LabelClash => "label-clash",
    Mark => "mark",
    Name => "name",
    NeverReads => "never-reads",
    NoOutput => "no-output",
    Not => "not",
    NotUndefined => "not-undefined",
    One => "one",
    OnePlace => "one-place",
    Or => "or",
    OrImplied => "or-implied",
    OrLineTwice => "or-line-twice",
    Order => "order",
    OutputTail => "output-tail",
    OwnRead => "own-read",
    Param => "param",
    ParamGrid => "param-grid",
    ParamTypes => "param-types",
    Parse => "parse",
    ParseHead => "parse-head",
    Proposer => "proposer",
    ProposerUnknown => "proposer-unknown",
    RecordField => "record-field",
    RecordPosition => "record-position",
    Recursion => "recursion",
    Relation => "relation",
    Remade => "remade",
    RemadeExport => "remade-export",
    Render => "render",
    RenderHead => "render-head",
    RenderPlace => "render-place",
    RepeatForm => "repeat-form",
    Representative => "representative",
    Rigid => "rigid",
    RigidPart => "rigid-part",
    Safety => "safety",
    SceneAlts => "scene-alts",
    SceneArclog => "scene-arclog",
    SceneBlock => "scene-block",
    SceneClaim => "scene-claim",
    SceneForm => "scene-form",
    SceneParse => "scene-parse",
    ScenePick => "scene-pick",
    SceneTaskSide => "scene-task-side",
    SharedCols => "shared-cols",
    Side => "side",
    Site => "site",
    SiteTwice => "site-twice",
    Spelling => "spelling",
    StandsUnder => "stands-under",
    Syntax => "syntax",
    TopOrder => "top-order",
    Unbound => "unbound",
    Undeclared => "undeclared",
    Wildcard => "wildcard",
    Witness => "witness",
    WitnessId => "witness-id",
    WitnessNoInput => "witness-no-input",
    WitnessNoSeparates => "witness-no-separates",
    WitnessOther => "witness-other",
    WitnessRef => "witness-ref",
    Zero => "zero",
    ZeroSite => "zero-site",
}

impl LintCode {
    /// The code whose spelling is `spelling`, where the lint has one.
    pub fn parse(spelling: &str) -> Option<LintCode> {
        LintCode::ALL.iter().copied().find(|code| code.spelling() == spelling)
    }
}

impl std::fmt::Display for LintCode {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.write_str(self.spelling())
    }
}

/// A refusal of [`LintReport::parse`].
#[derive(Clone, PartialEq, Eq, Debug)]
pub enum LintReportError {
    /// The line of number `number`, counted from 1, whose text is `text`,
    /// is no line of the report's forms, or is an error line or a summary
    /// line of a code that [`LintCode`] does not hold.
    Line { number: usize, text: String },
    /// The report holds `errors` error lines of `code`, and its summary
    /// gives `count` errors of it.
    Count { code: LintCode, errors: usize, count: usize },
}

impl std::fmt::Display for LintReportError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            LintReportError::Line { number, text } => write!(f, "line {number} is no line of the lint's report: {text}"),
            LintReportError::Count { code, errors, count } => {
                write!(f, "the report holds {errors} error lines of {code}, and its summary gives {count}")
            }
        }
    }
}

impl std::error::Error for LintReportError {}

impl LintError {
    /// The error that `line` gives, where it has the form
    /// `<path>:<line>: <code>: <message>` and [`LintCode`] holds its code.
    fn parse(line: &str) -> Option<LintError> {
        let (path, rest) = line.split_once(':')?;
        let (number, rest) = rest.split_once(": ")?;
        let (check, message) = rest.split_once(": ")?;
        Some(LintError {
            path: PathBuf::from(path),
            line: number.parse().ok()?,
            check: LintCode::parse(check)?,
            message: message.to_owned(),
        })
    }
}

/// The code and the count of `line`, where it has the form
/// `  <code> <n> in <k> files` and [`LintCode`] holds its code.
fn summary_count(line: &str) -> Option<(LintCode, usize)> {
    let words: Vec<&str> = line.strip_prefix("  ")?.split_whitespace().collect();
    let [code, count, "in", files, "files"] = words[..] else { return None };
    files.parse::<usize>().ok()?;
    Some((LintCode::parse(code)?, count.parse().ok()?))
}

/// Whether `line` has the form `<clean> of <n> <suffix> files clean`.
fn is_clean_line(line: &str) -> bool {
    let words: Vec<&str> = line.split(' ').collect();
    let [clean, "of", n, suffix, "files", "clean"] = words[..] else { return false };
    clean.parse::<usize>().is_ok() && n.parse::<usize>().is_ok() && suffix.starts_with('.')
}

impl LintReport {
    /// The report that `text` gives. Refuses a line of none of the forms
    /// that [`LintReport`] gives, and a code whose error lines are not as
    /// many as its summary line gives, a code with no summary line giving
    /// none.
    pub fn parse(text: &str) -> Result<LintReport, LintReportError> {
        let mut errors = Vec::new();
        let mut counts = std::collections::BTreeMap::new();
        for (index, line) in text.lines().enumerate() {
            if let Some(error) = LintError::parse(line) {
                errors.push(error);
            } else if let Some((code, count)) = summary_count(line) {
                counts.insert(code, count);
            } else if !line.is_empty() && !is_clean_line(line) {
                return Err(LintReportError::Line { number: index + 1, text: line.to_owned() });
            }
        }
        let mut found = std::collections::BTreeMap::<LintCode, usize>::new();
        for error in &errors {
            *found.entry(error.check).or_default() += 1;
        }
        for code in LintCode::ALL {
            let errors = found.get(code).copied().unwrap_or(0);
            let count = counts.get(code).copied().unwrap_or(0);
            if errors != count {
                return Err(LintReportError::Count { code: *code, errors, count });
            }
        }
        Ok(LintReport { errors })
    }

    /// The report that the file at `path` holds, as [`LintReport::parse`]
    /// reads it. Fails where the file does not read or the parse refuses it.
    pub fn read(path: &Path) -> Result<LintReport, Box<dyn std::error::Error>> {
        Ok(LintReport::parse(&std::fs::read_to_string(path)?)?)
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

/// Runs `work` over every item of `items`, on the threads of
/// [`corpus_threads`], each thread taking the next item that none has taken,
/// and gives the results in the order of `items`. `work` does not panic.
pub fn run_on_workers<I: Sync, R: Send>(items: &[I], work: impl Fn(&I) -> R + Sync) -> Vec<R> {
    let next = AtomicUsize::new(0);
    let mut results: Vec<(usize, R)> = std::thread::scope(|scope| {
        let workers: Vec<_> = (0..corpus_threads())
            .map(|_| {
                scope.spawn(|| {
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
/// gives the report over them. A panic of `check` on a
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
    let results = run_on_workers(&solvers, |solver| {
        let result = catch_unwind(AssertUnwindSafe(|| check(solver))).unwrap_or_else(|payload| SolverResult::Fail(vec![panic_line(&*payload)]));
        ended(solver, &result);
        result
    });
    let failures = results
        .into_iter()
        .enumerate()
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

#[cfg(test)]
mod tests {
    use super::{LintCode, LintReport, LintReportError};

    const WHOLE: &str = "gen/a.arclog:3: safety: X is unbound\ngen/b.arclog:7: safety: Y is unbound\ngen/b.arcdata:2: witness-no-input: witness w has no input\n\n  safety                  2 in 2 files\n  witness-no-input        1 in 1 files\n0 of 2 .arcdata files clean\n0 of 2 .arclog files clean\n";

    #[test]
    fn reads_a_whole_report() {
        let report = LintReport::parse(WHOLE).unwrap();
        let codes: Vec<LintCode> = report.errors.iter().map(|e| e.check).collect();
        assert_eq!(codes, [LintCode::Safety, LintCode::Safety, LintCode::WitnessNoInput]);
    }

    #[test]
    fn refuses_a_report_that_leaves_errors_out() {
        let cut = WHOLE.replacen("gen/b.arclog:7: safety: Y is unbound\n", "", 1);
        assert!(matches!(LintReport::parse(&cut), Err(LintReportError::Count { code: LintCode::Safety, .. })));
    }

    #[test]
    fn refuses_a_line_of_no_form_and_a_code_the_type_does_not_hold() {
        for line in ["Traceback (most recent call last):", "gen/a.arclog:3: no-such-code: X"] {
            let text = format!("{line}\n{WHOLE}");
            assert_eq!(LintReport::parse(&text).unwrap_err(), LintReportError::Line { number: 1, text: line.to_owned() });
        }
    }
}
