//! `decode`: steps the decoder through the token stream of each case
//! program of the corpus that holds no `DEMONSTRATED` form, as
//! `docs/engine/synthesis.md#synthesis` gives the end checks of the step: the
//! decoder admits the stream in full, closed-world; the consistency result
//! at the stream's last `END` equals the case's solves outcome at the values
//! the determination determines; and the rows of each prefix equal the rows
//! of a decode in a task session of its own. A difference prints by solver,
//! with the first of each kind.
//!
//! It prints, for each solver, one line with its counts of cases decoded,
//! refused, differing in consistency, differing in rows and stopped at a
//! bound, and, last, the corpus's counts and the median and the 99th
//! percentile of the engine's time per token: the time of the token mask
//! and of the step that the token takes.
//!
//! Its arguments: the corpus directory, the directory of the task files,
//! `--cases concept` (the default) or `--cases all`, then the task ids of
//! the solvers to run; every solver of the corpus where it is given none.

use std::collections::{BTreeMap, BTreeSet, HashSet};
use std::any::Any;
use std::panic::{catch_unwind, AssertUnwindSafe};
use std::path::{Path, PathBuf};
use std::process::ExitCode;
use std::sync::{Arc, Mutex};
use std::time::Instant;

use arclog::check::{CheckCache, CheckedProgram, SolverClauses};
use arclog::decode::{Consistency, Decoder};
use arclog::eval::determinations::{det_node, relation_spelled};
use arclog::eval::join::{each_row, union};
use arclog::eval::{output_relation, BodyValue, Outcome, ParameterValues, RelationValue, Stop};
use arclog::harness::{print_ended, require_optimized_build, run_over_corpus, SolverResult};
use arclog::judge::candidates::{PairCandidates, Section, World};
use arclog::judge::determination::{determine, CaseOutcome, DeterminedCase, Determination, Parameter};
use arclog::judge::run::{judged_run, Depth};
use arclog::registry::Registry;
use arclog::relations::Relation;
use arclog::resolver::{resolve_cases, DependencyKind};
use arclog::solver::{CaseName, Exclusion};
use arclog::stream::{token_stream, DecodeSettings, Emitter};
use arclog::task::{JudgedTask, Task};
use arclog::terms::{Example, TermId};

use crate::concept_case::{case_spelled, check_case, check_cases, corpus_limits, corpus_session, determined_cases, read_corpus_task, CorpusTask};
use arclog_constructions::shared as constructions;
use crate::select::selected;

const USAGE: &str = "usage: arclog-cli decode <corpus-dir> <tasks-dir> [--cases concept|all] [<task_id> ...]";

/// The subcommand on `args`, the arguments after its name.
pub fn run(args: &[String]) -> ExitCode {
    if let Err(code) = require_optimized_build() {
        return code;
    }
    let Some((corpus, tasks, all, task_ids)) = parse(args) else {
        eprintln!("{USAGE}");
        return ExitCode::from(2);
    };
    let selected = selected(&task_ids, &[], Path::new("")).expect("a selection by task id alone reads no file");
    let totals: Mutex<Totals> = Mutex::default();
    let report = run_over_corpus(&corpus, |solver| match &selected {
        Some(ids) if !ids.contains(&solver.task_id) => SolverResult::Pass,
        _ => decode_solver(&corpus, &tasks, &solver.task_id, all, &totals),
    }, print_ended);
    let report = match report {
        Ok(report) => report,
        Err(error) => {
            eprintln!("the corpus does not read: {error:?}");
            return ExitCode::from(2);
        }
    };
    let totals = totals.into_inner().expect("totals that no panic poisoned");
    println!("corpus: {}", totals.counts.line());
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
/// given, and the task ids, or `None` for arguments of another form.
fn parse(args: &[String]) -> Option<(PathBuf, PathBuf, bool, Vec<String>)> {
    let mut all = false;
    let mut positional = Vec::new();
    let mut args = args.iter();
    while let Some(arg) = args.next() {
        if arg == "--cases" {
            all = match args.next()?.as_str() {
                "concept" => false,
                "all" => true,
                _ => return None,
            };
        } else {
            positional.push(arg.clone());
        }
    }
    let mut positional = positional.into_iter();
    let (corpus, tasks) = (positional.next()?, positional.next()?);
    Some((corpus.into(), tasks.into(), all, positional.collect()))
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

/// The counts of cases: those decoded in full, those skipped for a
/// `DEMONSTRATED` form, and those with a finding of each kind.
#[derive(Default)]
struct Counts {
    decoded: usize,
    demonstrated: usize,
    found: BTreeMap<Kind, usize>,
}

impl Counts {
    fn add(&mut self, other: &Counts) {
        self.decoded += other.decoded;
        self.demonstrated += other.demonstrated;
        for (kind, count) in &other.found {
            *self.found.entry(*kind).or_default() += count;
        }
    }

    fn line(&self) -> String {
        let found = |kind: Kind| self.found.get(&kind).copied().unwrap_or(0);
        let kinds = [Kind::Refused, Kind::Consistency, Kind::Rows, Kind::Stopped, Kind::Unjudged];
        let others: Vec<String> = kinds.iter().map(|kind| format!("{} {}", found(*kind), kind.label())).collect();
        format!("{} cases decoded in full, {} skipped for a `DEMONSTRATED` form, {}", self.decoded, self.demonstrated, others.join(", "))
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
fn decode_solver(corpus: &Path, tasks: &Path, id: &str, all: bool, totals: &Mutex<Totals>) -> SolverResult {
    let mut gathered = Totals::default();
    let mut first: BTreeMap<Kind, String> = BTreeMap::new();
    let result = decode_cases(corpus, tasks, id, all, &mut gathered, &mut first);
    let line = match result {
        Ok(()) => gathered.counts.line(),
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
fn decode_cases(corpus: &Path, tasks: &Path, id: &str, all: bool, gathered: &mut Totals, first: &mut BTreeMap<Kind, String>) -> Result<(), String> {
    let CorpusTask { solver, task, judged } = read_corpus_task(corpus, tasks, id)?;
    let registry = Registry::get();
    let cases = resolve_cases(&solver, registry);
    let clauses = SolverClauses::of_cases(&cases);
    let mut cache = CheckCache::default();
    let concept = check_case(cases.concept(), &clauses, &mut cache, "the concept case")?;
    let bases = solver.base_case_names(Exclusion::WithoutExcluded);
    let decoded: Vec<CaseName> = if all { cases.cases().map(|case| case.case.name.clone()).collect() } else { vec![cases.concept().case.name.clone()] };
    let programs = check_cases(&cases, &clauses, &mut cache, &|name| bases.contains(name) || decoded.contains(name))?;
    let session = corpus_session();
    let limits = corpus_limits();
    let constructions = constructions()?;
    let determined = determined_cases(&programs, &concept, &task, &session, constructions, &limits);
    let base_cases: Vec<DeterminedCase<'_>> = determined.iter().filter(|case| bases.contains(case.name)).copied().collect();
    let determination = determine(&base_cases, &judged, World::Closed);
    for case in determined.iter().filter(|case| decoded.contains(case.name)) {
        if case.program.program.graph.nodes.iter().any(|node| matches!(node.kind, DependencyKind::Demonstrated(_))) {
            gathered.counts.demonstrated += 1;
            continue;
        }
        let expected = expected_solves(case, &determination, &judged);
        let case_run = catch_unwind(AssertUnwindSafe(|| decode_case(case.program, expected, &task, &judged, gathered)))
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
/// determines, closed-world, or why no such outcome stands. A base case
/// takes its own values; another case takes the values of the parameters it
/// runs.
fn expected_solves(case: &DeterminedCase<'_>, determination: &Determination, judged: &JudgedTask) -> Result<bool, String> {
    let values = match determination.cases.iter().find(|(name, ..)| name == case.name) {
        Some((_, outcome, _)) => {
            match outcome {
                CaseOutcome::Solved => {}
                CaseOutcome::Demonstrated => return Err("the case holds a `DEMONSTRATED` form".to_owned()),
                CaseOutcome::Stopped { stop, .. } => return Err(format!("the determination stops at {:?} at the form {:?}", stop.bound, stop.form)),
                CaseOutcome::Fault(fault) => return Err(format!("the determination faults at {:?}: {}", fault.form, fault.message)),
                CaseOutcome::Unsolved => return Err("no assignment solves every train pair".to_owned()),
            }
            determination.values(case.name)
        }
        None => {
            let mut values = Vec::new();
            for (relation, parameter) in &determination.parameters {
                if det_node(case.program, relation).is_none() {
                    continue;
                }
                match parameter {
                    Parameter::Determined(rows) => values.push((relation.clone(), rows.clone())),
                    Parameter::Open(rows) => values.push((relation.clone(), union(rows.clone()))),
                    Parameter::Underdetermined(_) => return Err(format!("the parameter {} is underdetermined", relation_spelled(relation))),
                    Parameter::Demonstrated | Parameter::Pick => {}
                }
            }
            ParameterValues::determined(values)
        }
    };
    let evaluation = case.evaluation(&values);
    let output = output_relation(case.program).expect("a checked case program derives `&output`");
    let run = judged_run(&evaluation, &output, judged, World::Closed, Depth::Full).map_err(|fault| format!("the judged run faults at {:?}: {}", fault.form, fault.message))?;
    Ok(run.pairs[..judged.train.len()].iter().all(|pair| pair.solved))
}

/// The findings of the decode of `program`'s token stream, and the time of
/// each token into `gathered`.
fn decode_case(program: &CheckedProgram, expected: Result<bool, String>, task: &Task, judged: &JudgedTask, gathered: &mut Totals) -> Vec<(Kind, String)> {
    let mut findings: Vec<(Kind, String)> = Vec::new();
    let constructions = constructions().expect("the table of constructions built for the determination");
    let registry = Registry::get();
    let settings = DecodeSettings::default();
    let (session, mirror_session) = (corpus_session(), corpus_session());
    let train: Arc<[PairCandidates<'_>]> = judged.train.iter().map(|pair| PairCandidates::of(pair, Section::Train, World::Closed)).collect();
    let mut decoder = Decoder::new(task, &session, registry, constructions, &settings).judging(train);
    let mut mirror = Decoder::new(task, &mirror_session, registry, constructions, &settings);
    let stream = match token_stream(program, decoder.vocabulary()) {
        Ok(stream) => stream,
        Err(diagnostic) => return vec![(Kind::Refused, format!("the writer gives no stream: {}", diagnostic.message))],
    };
    let mut forced: Vec<arclog::stream::Token> = Vec::new();
    let mut consistency = None;
    let mut rows_found = false;
    for (index, (token, emitter)) in stream.iter().enumerate() {
        match emitter {
            Emitter::Engine => {
                if forced.first() == Some(token) {
                    forced.remove(0);
                } else {
                    findings.push((Kind::Refused, format!("token {index} {token:?}: the engine emits it, and the step before forced {forced:?}")));
                    break;
                }
            }
            Emitter::Model => {
                if !forced.is_empty() {
                    findings.push((Kind::Refused, format!("token {index} {token:?}: the engine forces {forced:?} before it")));
                    break;
                }
                let start = Instant::now();
                let mask = decoder.admissible();
                let mask_seconds = start.elapsed().as_secs_f64();
                let admitted = decoder.vocabulary().id(token).is_some_and(|id| mask.contains(id));
                let start = Instant::now();
                let stepped = decoder.step(token.clone());
                let step_seconds = start.elapsed().as_secs_f64();
                let step = match stepped {
                    Ok(step) if admitted => step,
                    Ok(_) => {
                        findings.push((Kind::Refused, format!("token {index} {token:?}: the mask refuses it and the step takes it")));
                        break;
                    }
                    Err(refusal) => {
                        findings.push((Kind::Refused, format!("token {index} {token:?}: {refusal:?}")));
                        break;
                    }
                };
                gathered.mask.push(mask_seconds);
                gathered.step.push(step_seconds);
                gathered.total.push(mask_seconds + step_seconds);
                forced = step.forced.into();
                if let Some(result) = step.consistency {
                    consistency = Some(result);
                }
                if mirror.step(token.clone()).is_err() {
                    findings.push((Kind::Rows, format!("token {index} {token:?}: the decode in the second session refuses it")));
                    break;
                }
                if !rows_found {
                    let checked = catch_unwind(AssertUnwindSafe(|| prefix_rows(&decoder, &mirror, task))).unwrap_or_else(|payload| RowsCheck::Differ(format!("the decoder panicked: {}", panic_message(&*payload))));
                    match checked {
                        RowsCheck::Same => {}
                        RowsCheck::Stopped(note) => findings.push((Kind::Stopped, format!("token {index} {token:?}: {note}"))),
                        RowsCheck::Differ(note) => {
                            rows_found = true;
                            findings.push((Kind::Rows, format!("token {index} {token:?}: {note}")));
                        }
                    }
                }
            }
        }
    }
    if findings.iter().any(|(kind, _)| *kind == Kind::Refused) {
        return findings;
    }
    if !forced.is_empty() {
        findings.push((Kind::Refused, format!("the stream ends while the engine forces {forced:?}")));
        return findings;
    }
    let actual = match consistency {
        Some(Consistency::Consistent { .. }) => Some(true),
        Some(Consistency::NotConsistent) => Some(false),
        Some(Consistency::Stopped(stop)) => {
            findings.push((Kind::Stopped, format!("the consistency test stops at {:?} at the form {:?}", stop.bound, stop.form)));
            None
        }
        Some(other) => {
            findings.push((Kind::Consistency, format!("the consistency at the last END is {other:?}")));
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
            findings.push((Kind::Consistency, format!("the consistency at the last END is {}, and the case {} the train pairs", if actual { "consistent" } else { "not consistent" }, if solves { "solves" } else { "does not solve" })));
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
    let Some(counts) = decoder.counts() else {
        return RowsCheck::Same;
    };
    let examples: Vec<Option<Example>> =
        if counts.len() == 1 && task.examples().count() > 1 { vec![None] } else { task.examples().take(task.train.len()).map(Some).collect() };
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

fn row_set(relation: &Relation) -> HashSet<Vec<TermId>> {
    let mut rows = HashSet::new();
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
