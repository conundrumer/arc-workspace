//! `decode`: steps the decoder through the token stream of each case
//! program of the corpus, as
//! `docs/engine/synthesis.md#synthesis` gives the end checks of the step: the
//! decoder admits the stream, closed-world; the consistency result at the
//! `END` of its `OUT` form equals the case's solves outcome at the values
//! the determination determines; and the rows of each prefix equal the rows
//! of a decode in a task session of its own. A difference prints by solver,
//! with the first of each kind. With `--no-rows` the decode builds no second
//! session and checks no rows, and the report says the rows are not checked.
//! The stream of a case is the one `arclog::stream::corpus::corpus_case_stream`
//! gives: that of the case's files under `cases/<task id>/` of the corpus
//! where they stand.
//!
//! It prints, for each solver, one line with its counts of cases decoded,
//! refused, differing in consistency, differing in rows and stopped at a
//! bound, and, last, the corpus's counts and the median and the 99th
//! percentile of the engine's time per token: the time of the token mask
//! and of the step that the token takes.
//!
//! Its arguments: the corpus directory, the directory of the task files,
//! `--cases concept` (the default) or `--cases all`, `--no-rows` for no
//! check of the prefix rows, then the task ids of the solvers to run; every solver of the corpus where it is given none.

use std::collections::{BTreeMap, BTreeSet};
use std::any::Any;
use std::ops::ControlFlow;
use std::panic::{catch_unwind, AssertUnwindSafe};
use std::path::{Path, PathBuf};
use std::process::ExitCode;
use std::sync::{Arc, Mutex};

use arclog::check::{CheckCache, CheckedProgram, SolverClauses};
use arclog::decode::{Consistency, Decoder};
use arclog::eval::examples::ExampleScope;
use arclog::eval::join::each_row;
use arclog::eval::{output_relation, BodyValue, Outcome, RelationValue, Stop};
use arclog::hash::StableHashSet;
use arclog::harness::{print_ended, require_optimized_build, run_over_corpus, SolverResult};
use arclog::judge::candidates::{PairCandidates, Section, World};
use arclog::judge::determination::{determine, DeterminedCase, Determination};
use arclog::judge::run::{judged_run, Depth};
use arclog::registry::Registry;
use arclog::relations::Relation;
use arclog::resolver::{resolve_cases, ResolvedCase, ResolvedCases};
use arclog::solver::Exclusion;
use arclog::stream::DecodeSettings;
use arclog::solver::CaseName;
use arclog::task::{JudgedTask, Task};
use arclog::terms::{Example, TermId};

use arclog::stream::corpus::{case_spelled, check_case, check_cases, corpus_case_stream, decoded_cases};
use arclog::decode::corpus::{corpus_session, read_corpus_task, CorpusTask};
use crate::concept_case::{corpus_limits, determined_cases};
use arclog_constructions::shared as constructions;
use arclog::decode::replay::{replay, Stepped};
use crate::select::selected;

/// Whether the rows of each prefix are compared with those of a second
/// session.
#[derive(Clone, Copy, PartialEq, Eq)]
enum RowsMode {
    Checked,
    NotChecked,
}

const USAGE: &str = "usage: arclog-cli decode <corpus-dir> <tasks-dir> [--cases concept|all] [--no-rows] [<task_id> ...]";

/// The subcommand on `args`, the arguments after its name.
pub fn run(args: &[String]) -> ExitCode {
    if let Err(code) = require_optimized_build() {
        return code;
    }
    let Some((corpus, tasks, all, rows, task_ids)) = parse(args) else {
        eprintln!("{USAGE}");
        return ExitCode::from(2);
    };
    let selected = selected(&task_ids, &[], Path::new("")).expect("a selection by task id alone reads no file");
    let totals: Mutex<Totals> = Mutex::default();
    let report = run_over_corpus(&corpus, selected.as_ref(), |solver| decode_solver(&corpus, &tasks, &solver.task_id, all, rows, &totals), print_ended);
    let report = match report {
        Ok(report) => report,
        Err(error) => {
            eprintln!("the corpus does not read: {error:?}");
            return ExitCode::from(2);
        }
    };
    let totals = totals.into_inner().expect("totals that no panic poisoned");
    println!("corpus: {}", totals.counts.line(rows));
    println!(
        "time per token over {} tokens: median {}, 99th percentile {}; of the token mask, median {} and 99th percentile {}; of the step, median {} and 99th percentile {}",
        totals.total.len(),
        micros(percentile(&totals.total, 0.5)),
        micros(percentile(&totals.total, 0.99)),
        micros(percentile(&totals.mask, 0.5)),
        micros(percentile(&totals.mask, 0.99)),
        micros(percentile(&totals.step, 0.5)),
        micros(percentile(&totals.step, 0.99)),
    );
    if report.failures.is_empty() { ExitCode::SUCCESS } else { ExitCode::FAILURE }
}

/// The corpus directory, the tasks directory, whether `--cases all` is
/// given, whether the rows are checked (not with `--no-rows`), and the task
/// ids, or `None` for arguments of another form.
fn parse(args: &[String]) -> Option<(PathBuf, PathBuf, bool, RowsMode, Vec<String>)> {
    let mut all = false;
    let mut rows = RowsMode::Checked;
    let mut positional = Vec::new();
    let mut args = args.iter();
    while let Some(arg) = args.next() {
        if arg == "--cases" {
            all = match args.next()?.as_str() {
                "concept" => false,
                "all" => true,
                _ => return None,
            };
        } else if arg == "--no-rows" {
            rows = RowsMode::NotChecked;
        } else {
            positional.push(arg.clone());
        }
    }
    let mut positional = positional.into_iter();
    let (corpus, tasks) = (positional.next()?, positional.next()?);
    Some((corpus.into(), tasks.into(), all, rows, positional.collect()))
}

/// The kinds of finding on a case.
#[derive(Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Debug)]
enum Kind {
    /// The decoder refuses a token of the stream, or the stream is not
    /// written.
    Refused,
    /// The consistency at the last `END` differs from the solves outcome.
    Consistency,
    /// The rows of a prefix differ.
    Rows,
    /// A consistency test or a prefix's rows stops at a bound.
    Stopped,
    /// No solves outcome stands for the case: the determination gives none.
    Unjudged,
}

impl Kind {
    fn label(self) -> &'static str {
        match self {
            Kind::Refused => "refused",
            Kind::Consistency => "differing in consistency",
            Kind::Rows => "differing in rows",
            Kind::Stopped => "stopped at a bound",
            Kind::Unjudged => "with no solves outcome",
        }
    }
}

/// The counts of cases: those decoded, and those with a finding of each
/// kind.
#[derive(Default)]
struct Counts {
    decoded: usize,
    found: BTreeMap<Kind, usize>,
}

impl Counts {
    fn add(&mut self, other: &Counts) {
        self.decoded += other.decoded;
        for (kind, count) in &other.found {
            *self.found.entry(*kind).or_default() += count;
        }
    }

    fn line(&self, rows: RowsMode) -> String {
        let found = |kind: Kind| self.found.get(&kind).copied().unwrap_or(0);
        let kinds = [Kind::Refused, Kind::Consistency, Kind::Rows, Kind::Stopped, Kind::Unjudged];
        let others: Vec<String> = kinds
            .iter()
            .map(|kind| if *kind == Kind::Rows && rows == RowsMode::NotChecked { "rows not checked".to_owned() } else { format!("{} {}", found(*kind), kind.label()) })
            .collect();
        format!("{} cases decoded, {}", self.decoded, others.join(", "))
    }
}

/// What the run gathers across solvers: the counts, and the seconds of each
/// token's mask, its step and both.
#[derive(Default)]
struct Totals {
    counts: Counts,
    mask: Vec<f64>,
    step: Vec<f64>,
    total: Vec<f64>,
}

/// The value at the fraction `at` of `seconds`, `None` for no values.
fn percentile(seconds: &[f64], at: f64) -> Option<f64> {
    let mut sorted = seconds.to_vec();
    sorted.sort_by(f64::total_cmp);
    let index = ((sorted.len() as f64 * at).ceil() as usize).saturating_sub(1);
    sorted.get(index).copied()
}

fn micros(seconds: Option<f64>) -> String {
    seconds.map_or("none".to_owned(), |seconds| format!("{:.1} us", seconds * 1e6))
}

/// The report on the solver `id`: its summary line printed, and its first
/// finding of each kind as the failure lines; or the one line of the fault
/// that stops its setup.
fn decode_solver(corpus: &Path, tasks: &Path, id: &str, all: bool, rows: RowsMode, totals: &Mutex<Totals>) -> SolverResult {
    let mut gathered = Totals::default();
    let mut first: BTreeMap<Kind, String> = BTreeMap::new();
    let result = decode_cases(corpus, tasks, id, all, rows, &mut gathered, &mut first);
    let line = match result {
        Ok(()) => gathered.counts.line(rows),
        Err(fault) => return SolverResult::Fail(vec![format!("a fault that stops the decode: {fault}")]),
    };
    println!("{id}: {line}");
    let lines: Vec<String> = first.into_iter().map(|(kind, line)| format!("first case {}: {line}", kind.label())).collect();
    {
        let mut totals = totals.lock().expect("totals that no panic poisoned");
        totals.counts.add(&gathered.counts);
        totals.mask.extend(gathered.mask);
        totals.step.extend(gathered.step);
        totals.total.extend(gathered.total);
    }
    if lines.is_empty() { SolverResult::Pass } else { SolverResult::Fail(lines) }
}

/// Decodes the cases of the solver `id`, the concept case or every case,
/// into `gathered`, with the first finding of each kind in `first`.
fn decode_cases(corpus: &Path, tasks: &Path, id: &str, all: bool, rows: RowsMode, gathered: &mut Totals, first: &mut BTreeMap<Kind, String>) -> Result<(), String> {
    let CorpusTask { solver, task, judged } = read_corpus_task(corpus, tasks, id)?;
    let registry = Registry::get();
    let cases = resolve_cases(&solver, registry);
    let clauses = SolverClauses::of_cases(&cases);
    let mut cache = CheckCache::default();
    let concept = check_case(&solver, cases.concept(), &clauses, &mut cache, "the concept case", false)?;
    let bases = solver.base_case_names(Exclusion::WithoutExcluded);
    let decoded = decoded_cases(&cases, all);
    let programs = check_cases(&solver, &cases, &clauses, &mut cache, &|name| bases.contains(name) || decoded.contains(name), false)?;
    let session = corpus_session();
    let limits = corpus_limits();
    let constructions = constructions()?;
    let determined = determined_cases(&programs, &concept, &task, &session, constructions, &limits);
    let base_cases: Vec<DeterminedCase<'_>> = determined.iter().filter(|case| bases.contains(case.name)).copied().collect();
    let determination = determine(&base_cases, &judged, World::Closed);
    for case in determined.iter().filter(|case| decoded.contains(case.name)) {
        let expected = expected_solves(case, &determination, &judged);
        let case_run = catch_unwind(AssertUnwindSafe(|| decode_case(corpus, id, resolved_case(&cases, case.name), case.program, expected, &task, &judged, rows, gathered)))
            .unwrap_or_else(|payload| vec![(Kind::Refused, format!("the decoder panicked: {}", panic_message(&*payload)))]);
        let mut found = BTreeSet::new();
        for (kind, line) in case_run {
            found.insert(kind);
            first.entry(kind).or_insert_with(|| format!("{}: {line}", case_spelled(case.name)));
        }
        for kind in &found {
            *gathered.counts.found.entry(*kind).or_default() += 1;
        }
        if !found.contains(&Kind::Refused) {
            gathered.counts.decoded += 1;
        }
    }
    Ok(())
}

/// Whether `case` solves every train pair at the values `determination`
/// gives it (`Determination::case_values`), closed-world, or why no such
/// outcome stands.
fn expected_solves(case: &DeterminedCase<'_>, determination: &Determination, judged: &JudgedTask) -> Result<bool, String> {
    let values = determination.case_values(case)?;
    let evaluation = case.evaluation(&values);
    let output = output_relation(case.program).expect("a checked case program holds an `OUT` form");
    let run = judged_run(&evaluation, &output, judged, World::Closed, Depth::Full).map_err(|fault| format!("the judged run faults at {:?}: {}", fault.form, fault.message))?;
    Ok(run.pairs[..judged.train.len()].iter().all(|pair| pair.solved))
}

/// The resolved case of `cases` named `name`.
fn resolved_case<'a>(cases: &'a ResolvedCases, name: &CaseName) -> &'a ResolvedCase {
    cases.cases().find(|case| case.case.name == *name).expect("a decoded case is a case of the solver")
}

/// The findings of the decode of `program`'s token stream, and the time of
/// each token into `gathered`.
fn decode_case(corpus: &Path, id: &str, case: &ResolvedCase, program: &CheckedProgram, expected: Result<bool, String>, task: &Task, judged: &JudgedTask, rows: RowsMode, gathered: &mut Totals) -> Vec<(Kind, String)> {
    let mut findings: Vec<(Kind, String)> = Vec::new();
    let constructions = constructions().expect("the table of constructions built for the determination");
    let registry = Registry::get();
    let settings = DecodeSettings::default();
    let session = corpus_session();
    let mirror_session = (rows == RowsMode::Checked).then(corpus_session);
    let train: Arc<[PairCandidates<'_>]> = judged.train.iter().map(|pair| PairCandidates::of(pair, Section::Train, World::Closed)).collect();
    let mut decoder = Decoder::new(task, &session, registry, constructions, &settings).judging(train);
    let mut mirror = mirror_session.as_ref().map(|session| Decoder::new(task, session, registry, constructions, &settings));
    let stream = match corpus_case_stream(corpus, id, case, program, decoder.vocabulary(), false) {
        Ok(stream) => stream,
        Err(fault) => return vec![(Kind::Refused, fault)],
    };
    let mut consistency = None;
    let mut rows_found = false;
    let replayed = replay(&mut decoder, &stream.tokens, true, &mut |decoder, stepped| {
        let Stepped { index, token, consistency: result, mask, step_seconds, .. } = stepped;
        let mask_seconds = mask.expect("the replay computes the mask").seconds;
        gathered.mask.push(mask_seconds);
        gathered.step.push(step_seconds);
        gathered.total.push(mask_seconds + step_seconds);
        if let Some(result) = result {
            consistency = Some(result);
        }
        let Some(mirror) = mirror.as_mut() else { return ControlFlow::Continue(()) };
        if mirror.step(token.clone()).is_err() {
            findings.push((Kind::Rows, format!("token {index} {token:?}: the decode in the second session refuses it")));
            return ControlFlow::Break(());
        }
        if !rows_found {
            let checked = catch_unwind(AssertUnwindSafe(|| prefix_rows(decoder, mirror, task))).unwrap_or_else(|payload| RowsCheck::Differ(format!("the decoder panicked: {}", panic_message(&*payload))));
            match checked {
                RowsCheck::Same => {}
                RowsCheck::Stopped(note) => findings.push((Kind::Stopped, format!("token {index} {token:?}: {note}"))),
                RowsCheck::Differ(note) => {
                    rows_found = true;
                    findings.push((Kind::Rows, format!("token {index} {token:?}: {note}")));
                }
            }
        }
        ControlFlow::Continue(())
    });
    match replayed {
        Err(refusal) => {
            findings.push((Kind::Refused, refusal));
            return findings;
        }
        Ok(replayed) => {
            if let Some(refusal) = replayed.unfinished() {
                findings.push((Kind::Refused, refusal));
                return findings;
            }
        }
    }
    let actual = match consistency {
        Some(Consistency::Consistent { .. }) => Some(true),
        Some(Consistency::NotConsistent) => Some(false),
        Some(Consistency::Stopped(stop)) => {
            findings.push((Kind::Stopped, format!("the consistency test stops at {:?} at the form {:?}", stop.bound, stop.form)));
            None
        }
        Some(other) => {
            findings.push((Kind::Consistency, format!("the consistency at the last `OUT` END is {other:?}")));
            None
        }
        None => {
            findings.push((Kind::Consistency, "no step of the stream gives a consistency".to_owned()));
            None
        }
    };
    match (actual, expected) {
        (_, Err(why)) => findings.push((Kind::Unjudged, why)),
        (Some(actual), Ok(solves)) if actual != solves => {
            findings.push((Kind::Consistency, format!("the consistency at the last `OUT` END is {}, and the case {} the train pairs", if actual { "consistent" } else { "not consistent" }, if solves { "solves" } else { "does not solve" })));
        }
        _ => {}
    }
    findings
}

/// What the comparison of a prefix's rows in two sessions gives.
enum RowsCheck {
    Same,
    Stopped(String),
    Differ(String),
}

/// The rows of a request of [`Decoder::rows`] as the comparison reads them:
/// the value at each assignment, in the walk's order, and the stop that
/// ended the walk. A macro, since the type that `rows` gives is not public.
macro_rules! flatten {
    ($rows:expr) => {
        $rows.map(|outcome| outcome.map(|assigned| (assigned.at.into_iter().map(|(_, value)| value).collect::<Vec<BodyValue>>(), assigned.stop)))
    };
}

/// The rows of the sub-body of `decoder`'s clause in progress, on each train
/// example or once for a task-wide clause, against those of `mirror`, a
/// decode of the same prefix in a task session of its own.
fn prefix_rows(decoder: &Decoder<'_>, mirror: &Decoder<'_>, task: &Task) -> RowsCheck {
    let Some(scope) = decoder.rows_scope() else {
        return RowsCheck::Same;
    };
    let examples: Vec<Option<Example>> = match scope {
        Ok(ExampleScope::TaskWide) | Err(_) => vec![None],
        Ok(ExampleScope::PerExample) => task.examples().take(task.train.len()).map(Some).collect(),
    };
    let mut stopped = None;
    for example in examples {
        match compare(&flatten!(decoder.rows(example)), &flatten!(mirror.rows(example))) {
            RowsCheck::Same => {}
            RowsCheck::Stopped(note) => stopped = Some(note),
            RowsCheck::Differ(note) => return RowsCheck::Differ(format!("{example:?}: {note}")),
        }
    }
    stopped.map_or(RowsCheck::Same, RowsCheck::Stopped)
}

/// What a request's rows give: the value at each assignment and the stop
/// that ended the walk, or a fault, or `None` for no clause in progress.
type Rows = Option<Outcome<(Vec<BodyValue>, Option<Stop>)>>;

fn compare(ours: &Rows, theirs: &Rows) -> RowsCheck {
    match (ours, theirs) {
        (None, None) => RowsCheck::Same,
        (Some(Ok((ours, our_stop))), Some(Ok((theirs, their_stop)))) => {
            if our_stop != their_stop || ours.len() != theirs.len() {
                return RowsCheck::Differ(format!("{} assignments and stop {our_stop:?} against {} and {their_stop:?} in the second session", ours.len(), theirs.len()));
            }
            let mut stopped = our_stop.as_ref().map(|stop| RowsCheck::Stopped(format!("the walk of the assignments stops at {:?} at the form {:?}", stop.bound, stop.form)));
            for (ours, theirs) in ours.iter().zip(theirs) {
                match compare_value(&ours.0, &theirs.0) {
                    RowsCheck::Same => {}
                    RowsCheck::Stopped(note) => stopped = Some(RowsCheck::Stopped(note)),
                    differ @ RowsCheck::Differ(_) => return differ,
                }
            }
            stopped.unwrap_or(RowsCheck::Same)
        }
        (Some(Err(ours)), Some(Err(theirs))) if ours.message == theirs.message => RowsCheck::Same,
        (ours, theirs) => RowsCheck::Differ(format!("{} against {} in the second session", outcome_shape(ours), outcome_shape(theirs))),
    }
}

fn compare_value(ours: &RelationValue, theirs: &RelationValue) -> RowsCheck {
    match (ours, theirs) {
        (RelationValue::Rows(ours), RelationValue::Rows(theirs)) => {
            if row_set(ours) == row_set(theirs) { RowsCheck::Same } else { RowsCheck::Differ(format!("{} rows against {} rows in the second session", ours.len(), theirs.len())) }
        }
        (RelationValue::Undefined, RelationValue::Undefined) => RowsCheck::Same,
        (RelationValue::Stopped(ours), RelationValue::Stopped(theirs)) if ours == theirs => RowsCheck::Stopped(format!("the rows stop at {:?} at the form {:?}", ours.bound, ours.form)),
        (ours, theirs) => RowsCheck::Differ(format!("{} against {} in the second session", shape(ours), shape(theirs))),
    }
}

fn row_set(relation: &Relation) -> StableHashSet<Vec<TermId>> {
    let mut rows = StableHashSet::default();
    each_row(relation, &mut |row| {
        rows.insert(row.to_vec());
    });
    rows
}

fn shape(value: &RelationValue) -> String {
    match value {
        RelationValue::Rows(rows) => format!("{} rows", rows.len()),
        RelationValue::Undefined => "undefined".to_owned(),
        RelationValue::Stopped(stop) => format!("a stop at {:?}", stop.bound),
    }
}

fn outcome_shape(outcome: &Rows) -> String {
    match outcome {
        None => "no clause in progress".to_owned(),
        Some(Ok((values, _))) => format!("{} assignments", values.len()),
        Some(Err(fault)) => format!("a fault: {}", fault.message),
    }
}

/// The message of a panic whose payload is `payload`.
fn panic_message(payload: &(dyn Any + Send)) -> &str {
    payload.downcast_ref::<&str>().copied().or_else(|| payload.downcast_ref::<String>().map(String::as_str)).unwrap_or("a payload that is not a message")
}
