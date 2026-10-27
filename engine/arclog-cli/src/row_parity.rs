//! `row-parity <corpus-dir> <tasks-dir> <rows-dir> <task_id> ...`: compares,
//! for each selected solver, each relation of the cases its rows file gives,
//! at their stored parameters, with Souffle's rows of it, from
//! `<rows-dir>/<task_id>.json` (`scripts/souffle_parity.py case-rows`). It
//! reads a file as a stream, one relation at a time, so that the file's rows
//! of a relation, and the sides it is compared on, are dropped once its
//! verdict is merged: `orientation_constants` and `check_relations` come
//! before `cases`, a case's `case` before its `failure`, `pairs` and
//! `determination`, and a pair's `pair` before its `relations`, as
//! `parity.rerun.case_rows` writes them.
//!
//! It prints a line `<task>\t<relation>\t<verdict>\t<detail>` for each task
//! and relation, in the rows file's order, ordered by task id: `equal`;
//! `differ`, with the first case and pair, both counts of rows and one row
//! that only one side holds; `fault`, with the engine's text; `skip`, with
//! the reason the file gives (`parity.rerun`), for a relation that holds no
//! row the solver derives, and "several forms of the program derive the
//! name" for a name that more than one node of the program holds, one per
//! `DEMO_RULE`; or `uncompared`, with the reason the file gives, "no case's
//! program has a relation of that name", or "no case the check runs reads it
//! from `&output`", for any other relation the check does not compare.
//! In a case, a relation is compared only where the node of the case
//! program's dependency graph that holds it is `&output`'s node or is read
//! by it at any depth, or is a check relation (`check_relations` of the
//! file), which nothing reads and the converter writes to compare the
//! clauses of a folded relation; a relation of the file that the case's
//! program has and its `&output` does not read takes no verdict from that
//! case, since the rows of a relation that the output does not read say
//! nothing of the case. A relation that more than one case reads has one
//! line, the first `differ`, `fault` or `uncompared` of the cases and
//! pairs, else the first `equal`. A column of the file that the engine's
//! relation lacks is a `fault` of the relation, which names each such column.
//! A column that a pair's rows lack, a leaf of the file that is
//! `unresolved`, an Ident with no one source, and a column of the engine's
//! relation whose type is a `Pose`, are left out of both sides, and the line
//! names each, an unresolved leaf with its reason. A `fault` is also
//! the line of a relation whose Souffle rows hold a minted id that the
//! minting relation's rows on the pair do not hold at the row's key, and of
//! one whose engine Ident at a minted leaf is a value read from a file. A
//! fault of a whole task, or of a case whose run gives no rows or whose setup
//! fails, has the relation `*`. It exits 1 where a line is `differ`, `fault`
//! or `uncompared`.
//!
//! While it runs, each task that has run 10 s, and then each further 10 s,
//! gets one line on stderr, `row-parity: <task> case <case>: <n> s`, with the
//! case its rows file's stream has reached (empty before the first case) and
//! the seconds it has run.
//!
//! The entry of a case in the file's `cases` has a `determination` where the
//! check compares a relation of the `Determine` component. It holds Souffle's
//! rows of those relations at their run over the task's examples, the run
//! `solver.determine.determine` makes, on the determination program from which
//! each clause of a branch that case does not take is dropped: for a relation
//! with an Example leaf in the column map the rows of each train example under
//! the pair `train <i>`, and for any other relation the rows of the run under
//! the pair `task`. A relation of the entry is compared at the first case of
//! the file whose program has a relation of that name, with the entry of that
//! case, as a case's relation is, with the engine's rows of the relation at
//! that case's program, at the train example for a relation per input and
//! once for a relation of the task, and its lines are the relation's lines. A
//! relation that no case's program has is `uncompared`. An engine relation
//! that is of the task where Souffle's has an Example leaf in the column map,
//! or the reverse, shows as a `differ`. A run that gives no rows is a fault of
//! the whole task where a relation that no earlier case compared is in that
//! case's program, or where no entry before has given the relations.
//!
//! An `equal` line proves: for each case that derives the relation and whose
//! `&output` reads it, or is it, or that is a check relation, at the stored
//! parameters, on each train and test input of the task, the arclog
//! rows of the relation, projected onto the leaves the converter maps from
//! Souffle's columns, are Souffle's rows projected onto the same leaves, as a
//! set, and, for a relation of `Determine`, the same over the train examples
//! at the stored parameters of the first case whose program has it; where the map gives no column to compare, the relation is present in
//! both or absent in both. Where the relation's rows differ between the
//! case's models, and Souffle's relation holds the open value in a column,
//! each model's rows are Souffle's rows of that model's open value, the
//! values that the model's picks give the open parameters, and each open
//! value of Souffle's rows is some model's. A parameter whose pick a model
//! does not hold, as the relation does not read it, does not tell open
//! values apart, and Souffle's rows of open values that only it tells apart
//! are equal.
//! Elsewhere the union of the models' rows is Souffle's rows, since Souffle's
//! run states every open value at once. An Ident that a lib relation mints is
//! compared by its members: each side writes it as the text of the set of
//! its members, and the texts are compared as written values. An Ident that a
//! fact of the solver writes is a number that denotes one object only within
//! its pair, so those are compared up to one renaming per pair, over all the
//! relations of the pair. It does not prove anything about a leaf that the
//! line names as left out, the cases that the file does not give, the cases
//! whose `&output` does not read the relation (a check relation excepted), other
//! inputs (witness inputs among them), the relations that the file leaves out
//! as `skip` or `uncompared`, or the multiplicity of rows.

use std::borrow::Cow;
use std::collections::{BTreeMap, BTreeSet};
use std::fmt;
use std::fs::File;
use std::io::BufReader;
use std::path::Path;
use std::process::ExitCode;
use std::sync::mpsc::{self, RecvTimeoutError};
use std::sync::{Arc, Mutex};
use std::time::{Duration, Instant};

use arclog::eval::{output_relation, Evaluation};
use arclog::harness::{require_optimized_build, run_over_corpus, SolverResult};
use arclog::hash::StableHashSet;
use arclog::terms::Example;
use serde::de::{DeserializeSeed, Error as _, IgnoredAny, MapAccess, SeqAccess, Visitor};
use serde::{Deserialize, Deserializer};

use crate::concept_case::{with_case, ConceptCase};
use crate::renaming::{renaming_exists, same_without_idents, EngineLeaf, Leaf};
use crate::souffle_rows::{engine_columns, engine_models, named_relation, pair_name, same_rows, Column, EngineModel, EngineModels, PickRequest, Projection};

/// The seconds between the progress lines of a task that is still running.
const PROGRESS_SECS: u64 = 10;

const USAGE: &str = "usage: arclog-cli row-parity <corpus-dir> <tasks-dir> <rows-dir> <task_id> [<task_id> ...]";

/// The relation of the line of a fault of a whole task.
const WHOLE_TASK: &str = "*";

/// The reason of the `uncompared` line of a relation that the file sends and
/// that no case's program has.
const NO_CASE_HAS_IT: &str = "no case's program has a relation of that name";

/// The reason of the `uncompared` line of a relation that the file sends, that
/// some case's program has, and that no case the check runs reads from its
/// `&output`.
const NO_CASE_READS_IT: &str = "no case the check runs reads it from `&output`";

/// The pair of the `determination` entry that holds the relations of the
/// task, which Souffle's rows give once.
const TASK_PAIR: &str = "task";

/// What the comparison of one relation gives.
#[derive(Clone, Debug, PartialEq)]
pub(crate) enum Verdict {
    Equal(String),
    Differ(String),
    Fault(String),
    Skip(String),
    Uncompared(String),
}

impl Verdict {
    fn word(&self) -> &'static str {
        match self {
            Verdict::Equal(_) => "equal",
            Verdict::Differ(_) => "differ",
            Verdict::Fault(_) => "fault",
            Verdict::Skip(_) => "skip",
            Verdict::Uncompared(_) => "uncompared",
        }
    }

    fn detail(&self) -> &str {
        match self {
            Verdict::Equal(text) | Verdict::Differ(text) | Verdict::Fault(text) | Verdict::Skip(text) | Verdict::Uncompared(text) => text,
        }
    }

    /// Whether the verdict fails the run.
    fn fails(&self) -> bool {
        matches!(self, Verdict::Differ(_) | Verdict::Fault(_) | Verdict::Uncompared(_))
    }
}

/// One relation on one pair: Souffle's projected rows, its open values where
/// it holds the open value in a column, the engine's rows at each model
/// projected onto the same columns, `None` where the case's program has no
/// relation of the name, the columns of the file that a pair's rows lack and
/// its unresolved leaves with their reasons, and the text of a minted id that
/// Souffle's rows of the pair do not account for.
pub(crate) struct Checked {
    pub(crate) name: String,
    pub(crate) souffle: BTreeSet<Vec<Leaf>>,
    pub(crate) by_open: OpenValues,
    pub(crate) engine: Option<EngineModels>,
    pub(crate) left_out: Vec<String>,
    pub(crate) fault: Option<String>,
}

/// The open values of a relation of Souffle's: the arclog relations of the
/// open parameters that the open values name, in the order the picks of an
/// open value and of an engine model are given in, and the open values. None
/// where the relation holds no open value in a column.
#[derive(Default)]
pub(crate) struct OpenValues {
    pub(crate) picks: Vec<String>,
    pub(crate) values: Vec<OpenValue>,
}

/// One open value of a relation of Souffle's: the relation's rows under it
/// and, for each open parameter, the rows of the parameter's relation that
/// the value gives it, `None` where the value gives it none (`nil`), which
/// holds at every value of it.
pub(crate) struct OpenValue {
    pub(crate) rows: BTreeSet<Vec<Leaf>>,
    pub(crate) picks: Vec<Option<BTreeSet<Vec<Leaf>>>>,
}

/// A column of the rows file: a label and a field or null.
#[derive(Deserialize)]
struct FileColumn(String, Option<String>);

/// A leaf of the rows file that has no one source: a label, a field or null,
/// and the reason.
#[derive(Deserialize)]
struct FileUnresolved(String, Option<String>, String);

/// The kind of an Ident leaf of the rows file (`"idents"`): `null` is any
/// other leaf.
#[derive(Deserialize)]
#[serde(rename_all = "lowercase")]
enum FileIdent {
    Minted,
    Stored,
}

/// The rows of a relation in the rows file: for each row, the leaves of each
/// mapped column.
type FileRows = Vec<Vec<Vec<Leaf>>>;

/// One relation of the rows file on one pair.
#[derive(Deserialize)]
struct FileRelation {
    name: String,
    columns: Vec<FileColumn>,
    idents: Vec<Option<FileIdent>>,
    unread: Vec<FileColumn>,
    unresolved: Vec<FileUnresolved>,
    rows: FileRows,
    by_open: Option<FileByOpen>,
    fault: Option<String>,
}

/// The open parameters of a relation of the rows file, by arclog name, with
/// the columns of the pick that the file gives, and its open values.
#[derive(Deserialize)]
struct FileByOpen {
    picks: BTreeMap<String, Vec<FileColumn>>,
    values: Vec<FileOpenValue>,
}

/// One open value of a relation in the rows file: its rows, and the rows it
/// gives each open parameter that it does not give `nil`.
#[derive(Deserialize)]
struct FileOpenValue {
    rows: FileRows,
    picks: BTreeMap<String, FileRows>,
}

/// An open parameter of the rows file: its arclog relation and the names of
/// the columns of the pick that the file gives.
struct FilePick {
    name: String,
    columns: Vec<String>,
}

/// A pair of the rows file's `determination`. A case's pairs are read one
/// relation at a time, by [`Pairs`].
#[derive(Deserialize)]
struct FilePair {
    pair: String,
    relations: Vec<FileRelation>,
}

/// A case's `determination`: the pairs, or the failure of its Souffle run.
#[derive(Deserialize)]
struct FileDetermination {
    failure: Option<String>,
    pairs: Option<Vec<FilePair>>,
}

/// The verdicts that an entry of the rows file's `not_compared` can give.
#[derive(Deserialize)]
#[serde(rename_all = "lowercase")]
enum FileLeftOut {
    Skip,
    Uncompared,
}

/// A relation that the rows file leaves out of the comparison.
#[derive(Deserialize)]
struct FileNotCompared {
    name: String,
    verdict: FileLeftOut,
    reason: String,
}

/// The subcommand on `args`, the arguments after its name.
pub fn run(args: &[String]) -> ExitCode {
    if let Err(code) = require_optimized_build() {
        return code;
    }
    let [corpus, tasks, rows, ids @ ..] = args else {
        eprintln!("{USAGE}");
        return ExitCode::from(2);
    };
    if ids.is_empty() {
        eprintln!("{USAGE}");
        return ExitCode::from(2);
    }
    let selected: BTreeSet<String> = ids.iter().cloned().collect();
    let lines: Mutex<BTreeMap<String, Vec<(String, Verdict)>>> = Mutex::new(BTreeMap::new());
    let progress: Progress = Mutex::new(BTreeMap::new());
    let progress = &progress;
    let (done, watching) = mpsc::channel::<()>();
    let report = std::thread::scope(|scope| {
        scope.spawn(move || {
            while watching.recv_timeout(Duration::from_secs(1)) == Err(RecvTimeoutError::Timeout) {
                for line in overdue(progress, Instant::now()) {
                    eprintln!("{line}");
                }
            }
        });
        let report = run_over_corpus(Path::new(corpus), Some(&selected), |solver| {
            progress.lock().expect("the progress is not poisoned").insert(solver.task_id.clone(), Running { case: String::new(), start: Instant::now(), printed: 0 });
            match task_verdicts(Path::new(corpus), Path::new(tasks), &solver.task_id, &Path::new(rows).join(format!("{}.json", solver.task_id)), progress) {
                Ok(verdicts) => {
                    lines.lock().expect("the lines are not poisoned").insert(solver.task_id.clone(), verdicts);
                    SolverResult::Pass
                }
                Err(fault) => SolverResult::Fail(vec![fault]),
            }
        }, |solver, _| {
            progress.lock().expect("the progress is not poisoned").remove(&solver.task_id);
        });
        drop(done);
        report
    });
    let report = match report {
        Ok(report) => report,
        Err(error) => {
            eprintln!("the corpus does not read: {error:?}");
            return ExitCode::from(2);
        }
    };
    let mut lines = lines.into_inner().expect("the lines are not poisoned");
    for (solver, faults) in report.failures {
        lines.insert(solver.task_id, vec![(WHOLE_TASK.to_owned(), Verdict::Fault(faults.join("; ").replace(['\n', '\r', '\t'], " ")))]);
    }
    let mut failed = false;
    for (id, verdicts) in lines {
        for (relation, verdict) in verdicts {
            failed |= verdict.fails();
            println!("{id}\t{relation}\t{}\t{}", verdict.word(), verdict.detail().replace(['\n', '\r', '\t'], " "));
        }
    }
    if failed { ExitCode::FAILURE } else { ExitCode::SUCCESS }
}

/// A task in flight: the case its rows file's stream has reached, when it
/// started, and the count of progress lines printed for it.
struct Running {
    case: String,
    start: Instant,
    printed: u64,
}

/// The tasks in flight, by task id.
type Progress = Mutex<BTreeMap<String, Running>>;

/// The progress line of each task of `progress` whose time in flight at `now`
/// has reached `PROGRESS_SECS` times one more than its count of lines
/// printed, and counts that line as printed.
fn overdue(progress: &Progress, now: Instant) -> Vec<String> {
    let mut tasks = progress.lock().expect("the progress is not poisoned");
    let mut lines = Vec::new();
    for (task, running) in tasks.iter_mut() {
        let seconds = now.saturating_duration_since(running.start).as_secs();
        if seconds >= PROGRESS_SECS * (running.printed + 1) {
            running.printed += 1;
            lines.push(format!("row-parity: {task} case {}: {seconds} s", running.case));
        }
    }
    lines
}

/// The verdict of each relation of the rows file at `path` of the solver `id`:
/// each relation of the cases it gives, merged over the cases and their pairs,
/// in the file's order of relations, then the relations that the file leaves
/// out. A case that fails to set up, and a case whose Souffle run gave no
/// rows, give a fault of the whole task.
fn task_verdicts(corpus: &Path, tasks: &Path, id: &str, path: &Path, progress: &Progress) -> Result<Vec<(String, Verdict)>, String> {
    let file = File::open(path).map_err(|error| format!("{} does not read: {error}", path.display()))?;
    let mut deserializer = serde_json::Deserializer::from_reader(BufReader::new(file));
    let mut verdicts = Verdicts { corpus, tasks, id, progress, constants: None, checks: None, awaiting: None, cases_read: false, found: Found::default(), left_out: None, fault: None };
    let read = (&mut verdicts).deserialize(&mut deserializer).and_then(|()| deserializer.end());
    if let Some(fault) = verdicts.fault.take() {
        return Err(fault);
    }
    read.map_err(|error| format!("{} is no rows file: {error}", path.display()))?;
    verdicts.finish()
}

/// What the stream of a rows file has given so far, which `task_verdicts`
/// reads it into.
struct Verdicts<'a> {
    corpus: &'a Path,
    tasks: &'a Path,
    id: &'a str,
    progress: &'a Progress,
    constants: Option<BTreeMap<String, i64>>,
    /// The arclog names of the check relations.
    checks: Option<Vec<String>>,
    /// The relations of the `determination` entries that no case has compared,
    /// once an entry has given them.
    awaiting: Option<Vec<String>>,
    cases_read: bool,
    found: Found,
    left_out: Option<Vec<FileNotCompared>>,
    /// The fault that stopped the stream, as against a file that does not parse.
    fault: Option<String>,
}

impl Verdicts<'_> {
    /// The constants and the check relations, which come before the cases.
    fn before_cases(&self) -> Result<(&BTreeMap<String, i64>, &[String]), String> {
        let constants = self.constants.as_ref().ok_or("the rows file has no `orientation_constants` before its cases")?;
        let checks = self.checks.as_deref().ok_or("the rows file has no `check_relations` before its cases")?;
        Ok((constants, checks))
    }

    /// Sets the case that the progress line of this task gives.
    fn set_case(&self, case: &str) {
        if let Some(running) = self.progress.lock().expect("the progress is not poisoned").get_mut(self.id) {
            case.clone_into(&mut running.case);
        }
    }

    /// Reads the rest of the map of the case `name`, from its first `pairs` or
    /// `determination` key `first`, and merges its verdicts: of its pairs, and
    /// of its `determination`. `failed` is whether its Souffle run gave no
    /// rows.
    fn read_case<'de, A: MapAccess<'de>>(&mut self, name: &str, failed: bool, first: String, map: A) -> Result<(), A::Error> {
        let mut awaiting = self.awaiting.take();
        let (constants, checks) = match self.before_cases() {
            Ok(before) => before,
            Err(fault) => return Err(self.refuse(fault)),
        };
        let mut rest = CaseRest { map, pending: Some(first), name, failed, constants, checks, awaiting: &mut awaiting, pairs_seen: false, finished: false };
        let mut broken = None;
        let found = with_case(self.corpus, self.tasks, self.id, name, |case| match rest.read(Some(case)) {
            Ok(found) => found,
            Err(error) => {
                broken = Some(error);
                Err(String::new())
            }
        });
        if broken.is_none() && !rest.finished {
            broken = rest.read(None).err();
        }
        let pairs_seen = rest.pairs_seen;
        self.awaiting = awaiting;
        if let Some(error) = broken {
            return Err(error);
        }
        if !failed && !pairs_seen {
            return Err(self.refuse("a case of the rows file has no `pairs`"));
        }
        match found {
            Ok(of_case) => self.found.absorb(of_case),
            Err(fault) => self.found.lines.push((WHOLE_TASK.to_owned(), Verdict::Fault(format!("case {name}: {fault}")))),
        }
        Ok(())
    }

    /// The verdicts once the whole file is read: the relations that the pairs
    /// sent and no case's program has, then the relations the file leaves out.
    fn finish(self) -> Result<Vec<(String, Verdict)>, String> {
        let Verdicts { constants, cases_read, found: Found { lines: mut merged, sent, unread }, left_out, .. } = self;
        constants.ok_or("the rows file has no `orientation_constants`")?;
        if !cases_read {
            return Err("the rows file has no `cases`".to_owned());
        }
        for relation in sent {
            if !merged.iter().any(|(held, _)| *held == relation) {
                let reason = if unread.contains(&relation) { NO_CASE_READS_IT } else { NO_CASE_HAS_IT };
                merged.push((relation, Verdict::Uncompared(reason.to_owned())));
            }
        }
        for FileNotCompared { name, verdict, reason } in left_out.ok_or("the rows file has no `not_compared`")? {
            merged.push((
                name,
                match verdict {
                    FileLeftOut::Skip => Verdict::Skip(reason),
                    FileLeftOut::Uncompared => Verdict::Uncompared(reason),
                },
            ));
        }
        Ok(merged)
    }

    /// The error that stops the stream at `fault`.
    fn refuse<E: serde::de::Error>(&mut self, fault: impl Into<String>) -> E {
        self.fault = Some(fault.into());
        E::custom("the verdicts stopped")
    }
}

impl<'de> DeserializeSeed<'de> for &mut Verdicts<'_> {
    type Value = ();

    fn deserialize<D: Deserializer<'de>>(self, deserializer: D) -> Result<(), D::Error> {
        deserializer.deserialize_map(self)
    }
}

impl<'de> Visitor<'de> for &mut Verdicts<'_> {
    type Value = ();

    fn expecting(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        formatter.write_str("a rows file")
    }

    fn visit_map<A: MapAccess<'de>>(self, mut map: A) -> Result<(), A::Error> {
        while let Some(key) = map.next_key::<String>()? {
            match key.as_str() {
                "orientation_constants" => self.constants = Some(map.next_value()?),
                "check_relations" => self.checks = Some(map.next_value()?),
                "cases" => {
                    map.next_value_seed(Cases(&mut *self))?;
                    self.cases_read = true;
                }
                "not_compared" => self.left_out = Some(map.next_value()?),
                _ => {
                    map.next_value::<IgnoredAny>()?;
                }
            }
        }
        Ok(())
    }
}

/// The rows file's `cases`, read one case at a time into the verdicts.
struct Cases<'a, 'b>(&'a mut Verdicts<'b>);

impl<'de> DeserializeSeed<'de> for Cases<'_, '_> {
    type Value = ();

    fn deserialize<D: Deserializer<'de>>(self, deserializer: D) -> Result<(), D::Error> {
        deserializer.deserialize_seq(self)
    }
}

impl<'de> Visitor<'de> for Cases<'_, '_> {
    type Value = ();

    fn expecting(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        formatter.write_str("the cases of a rows file")
    }

    fn visit_seq<A: SeqAccess<'de>>(self, mut seq: A) -> Result<(), A::Error> {
        while seq.next_element_seed(Case(&mut *self.0))?.is_some() {}
        Ok(())
    }
}

/// One entry of the rows file's `cases`, read as a map into the verdicts. Its
/// `case` key comes first and sets the case; a `failure` key adds the fault
/// line of a case whose Souffle run gave no rows. At the first `pairs` or
/// `determination` key the case is set up, and the rest of the map is read
/// by [`CaseRest`].
struct Case<'a, 'b>(&'a mut Verdicts<'b>);

impl<'de> DeserializeSeed<'de> for Case<'_, '_> {
    type Value = ();

    fn deserialize<D: Deserializer<'de>>(self, deserializer: D) -> Result<(), D::Error> {
        deserializer.deserialize_map(self)
    }
}

impl<'de> Visitor<'de> for Case<'_, '_> {
    type Value = ();

    fn expecting(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        formatter.write_str("a case of a rows file")
    }

    fn visit_map<A: MapAccess<'de>>(self, mut map: A) -> Result<(), A::Error> {
        let verdicts = self.0;
        let mut name: Option<String> = None;
        let mut failure: Option<String> = None;
        while let Some(key) = map.next_key::<String>()? {
            match key.as_str() {
                "case" => {
                    let case: String = map.next_value()?;
                    verdicts.set_case(&case);
                    name = Some(case);
                }
                "failure" => {
                    failure = map.next_value()?;
                    if let Some(failure) = &failure {
                        let Some(name) = &name else { return Err(verdicts.refuse("the `case` of a case of the rows file comes before its `failure`")) };
                        verdicts.found.lines.push((WHOLE_TASK.to_owned(), Verdict::Fault(format!("case {name}: no Souffle rows: {failure}"))));
                    }
                }
                "pairs" if failure.is_some() => {
                    map.next_value::<IgnoredAny>()?;
                }
                "pairs" | "determination" => {
                    let Some(name) = &name else { return Err(verdicts.refuse("the `case` of a case of the rows file comes before its `pairs` and `determination`")) };
                    return verdicts.read_case(name, failure.is_some(), key, map);
                }
                _ => {
                    map.next_value::<IgnoredAny>()?;
                }
            }
        }
        if name.is_none() {
            return Err(A::Error::missing_field("case"));
        }
        match failure {
            Some(_) => Ok(()),
            None => Err(verdicts.refuse("a case of the rows file has no `pairs`")),
        }
    }
}

/// The rest of the map of a case, from its first `pairs` or `determination`
/// key, whose value is not yet read.
struct CaseRest<'a, A> {
    map: A,
    /// The key whose value is next in the map.
    pending: Option<String>,
    name: &'a str,
    /// The case's Souffle run gave no rows, so its `pairs` are not read.
    failed: bool,
    constants: &'a BTreeMap<String, i64>,
    checks: &'a [String],
    awaiting: &'a mut Option<Vec<String>>,
    pairs_seen: bool,
    /// The map is read to its end.
    finished: bool,
}

impl<'de, A: MapAccess<'de>> CaseRest<'_, A> {
    /// Reads the map to its end: `pairs` one relation at a time and
    /// `determination` whole, compared on `case`, or, where the case's setup
    /// failed (`None`), skipped. The verdicts of the case, merged, or the
    /// fault of its pairs, which drops those of the case.
    fn read(&mut self, case: Option<&ConceptCase<'_>>) -> Result<Result<Found, String>, A::Error> {
        self.finished = true;
        let mut found = Found::default();
        let mut fault = None;
        while let Some(key) = match self.pending.take() {
            Some(key) => Some(key),
            None => self.map.next_key::<String>()?,
        } {
            let live = case.filter(|_| fault.is_none());
            match (key.as_str(), live) {
                ("pairs", live) => {
                    self.pairs_seen = true;
                    match live {
                        Some(case) if !self.failed => {
                            let mut pairs = Pairs::new(case, self.name, self.constants, self.checks);
                            self.map.next_value_seed(&mut pairs)?;
                            match pairs.finish() {
                                Ok(of_pairs) => found.absorb(of_pairs),
                                Err(of_pairs) => fault = Some(of_pairs),
                            }
                        }
                        _ => {
                            self.map.next_value::<IgnoredAny>()?;
                        }
                    }
                }
                ("determination", Some(case)) => {
                    let determination: FileDetermination = self.map.next_value()?;
                    match determination_verdicts(case, self.name, self.constants, determination, self.awaiting) {
                        Ok(of_determination) => found.absorb(of_determination),
                        Err(fault) => found.lines.push((WHOLE_TASK.to_owned(), Verdict::Fault(format!("case {}, determination: {fault}", self.name)))),
                    }
                }
                _ => {
                    self.map.next_value::<IgnoredAny>()?;
                }
            }
        }
        Ok(fault.map_or(Ok(found), Err))
    }
}

/// What the entries of the rows file give: the verdict of each relation they
/// compare, merged over the entries, the name of each relation they send,
/// and the name of each relation that they send and a case's program has but
/// that case's `&output` does not read.
#[derive(Default)]
struct Found {
    lines: Vec<(String, Verdict)>,
    sent: Vec<String>,
    unread: Vec<String>,
}

impl Found {
    /// Merges what one case gave into this.
    fn absorb(&mut self, other: Found) {
        other.lines.into_iter().for_each(|(relation, verdict)| merge(&mut self.lines, relation, verdict));
        other.sent.iter().for_each(|relation| add_once(&mut self.sent, relation));
        other.unread.iter().for_each(|relation| add_once(&mut self.unread, relation));
    }
}

/// Adds `name` to `names` where it is not in them.
fn add_once(names: &mut Vec<String>, name: &str) {
    if !names.iter().any(|held| held == name) {
        names.push(name.to_owned());
    }
}

/// The `pairs` of the case `name`, read one relation at a time into the
/// verdicts of each relation `case` compares, merged over the pairs, and the
/// name of each relation the pairs send. A relation is compared where the
/// case's `&output` reads it, at any depth, or is it, or where it is one of
/// the check relations, which nothing reads. A pair of the task that the
/// pairs lack is a fault, given once the pairs end, as is the first fault of
/// a relation, after which the rest is skipped.
struct Pairs<'a, 'c> {
    case: &'a ConceptCase<'c>,
    name: &'a str,
    constants: &'a BTreeMap<String, i64>,
    /// For each node of the program, whether the case's `&output` reads it.
    reads: Vec<bool>,
    /// The name of each pair of the task and its example, in the task's order.
    examples: Vec<(String, Example)>,
    /// For each pair of `examples`, whether the rows file has given it.
    seen: Vec<bool>,
    found: Found,
    fault: Option<String>,
}

impl<'a, 'c> Pairs<'a, 'c> {
    fn new(case: &'a ConceptCase<'c>, name: &'a str, constants: &'a BTreeMap<String, i64>, checks: &[String]) -> Self {
        let evaluation = &case.evaluation;
        let program = evaluation.program;
        let output = output_relation(program).expect("a checked case program derives `&output`");
        let mut reads = program.program.graph.reached(output.node);
        for check in checks {
            if let Some(Ok(node)) = named_relation(program, check) {
                reads[node.node.0 as usize] = true;
            }
        }
        let examples: Vec<(String, Example)> = evaluation.task.examples().enumerate().map(|(index, example)| (pair_name(evaluation.task, index), example)).collect();
        Pairs { case, name, constants, reads, seen: vec![false; examples.len()], examples, found: Found::default(), fault: None }
    }

    /// What the pairs gave, or the fault that drops it.
    fn finish(self) -> Result<Found, String> {
        if let Some(fault) = self.fault {
            return Err(fault);
        }
        match self.seen.iter().position(|seen| !seen) {
            Some(missing) => Err(format!("the rows file has no pair `{}`", self.examples[missing].0)),
            None => Ok(self.found),
        }
    }
}

impl<'de> DeserializeSeed<'de> for &mut Pairs<'_, '_> {
    type Value = ();

    fn deserialize<D: Deserializer<'de>>(self, deserializer: D) -> Result<(), D::Error> {
        deserializer.deserialize_seq(self)
    }
}

impl<'de> Visitor<'de> for &mut Pairs<'_, '_> {
    type Value = ();

    fn expecting(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        formatter.write_str("the pairs of a case")
    }

    fn visit_seq<A: SeqAccess<'de>>(self, mut seq: A) -> Result<(), A::Error> {
        while seq.next_element_seed(PairEntry(&mut *self))?.is_some() {}
        Ok(())
    }
}

/// One pair of a case's `pairs`, read as a map: its `pair` key comes before
/// its `relations`.
struct PairEntry<'a, 'b, 'c>(&'a mut Pairs<'b, 'c>);

impl<'de> DeserializeSeed<'de> for PairEntry<'_, '_, '_> {
    type Value = ();

    fn deserialize<D: Deserializer<'de>>(self, deserializer: D) -> Result<(), D::Error> {
        deserializer.deserialize_map(self)
    }
}

impl<'de> Visitor<'de> for PairEntry<'_, '_, '_> {
    type Value = ();

    fn expecting(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        formatter.write_str("a pair of a case")
    }

    fn visit_map<A: MapAccess<'de>>(self, mut map: A) -> Result<(), A::Error> {
        let pairs = self.0;
        let mut pair: Option<String> = None;
        let mut relations_seen = false;
        while let Some(key) = map.next_key::<String>()? {
            match key.as_str() {
                "pair" => pair = Some(map.next_value()?),
                "relations" => {
                    let Some(pair) = &pair else { return Err(A::Error::custom("the `pair` of a pair comes before its `relations`")) };
                    relations_seen = true;
                    let at = pairs.examples.iter().position(|(held, _)| held == pair).filter(|&at| !pairs.seen[at] && pairs.fault.is_none());
                    match at {
                        Some(at) => {
                            pairs.seen[at] = true;
                            let example = pairs.examples[at].1;
                            let compare = PairCompare::new(format!("{}, {pair}", pairs.name));
                            map.next_value_seed(Relations { pairs: &mut *pairs, example, compare })?;
                        }
                        None => {
                            map.next_value::<IgnoredAny>()?;
                        }
                    }
                }
                _ => {
                    map.next_value::<IgnoredAny>()?;
                }
            }
        }
        if pair.is_none() {
            return Err(A::Error::missing_field("pair"));
        }
        if !relations_seen {
            return Err(A::Error::missing_field("relations"));
        }
        Ok(())
    }
}

/// The `relations` of one pair of a case, read one at a time: each is
/// compared and dropped before the next is read.
struct Relations<'a, 'b, 'c> {
    pairs: &'a mut Pairs<'b, 'c>,
    example: Example,
    compare: PairCompare,
}

impl<'de> DeserializeSeed<'de> for Relations<'_, '_, '_> {
    type Value = ();

    fn deserialize<D: Deserializer<'de>>(self, deserializer: D) -> Result<(), D::Error> {
        deserializer.deserialize_seq(self)
    }
}

impl<'de> Visitor<'de> for Relations<'_, '_, '_> {
    type Value = ();

    fn expecting(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        formatter.write_str("the relations of a pair")
    }

    fn visit_seq<A: SeqAccess<'de>>(mut self, mut seq: A) -> Result<(), A::Error> {
        loop {
            if self.pairs.fault.is_some() {
                if seq.next_element::<IgnoredAny>()?.is_none() {
                    return Ok(());
                }
                continue;
            }
            let Some(relation) = seq.next_element::<FileRelation>()? else { return Ok(()) };
            let pairs = &mut *self.pairs;
            if let Err(fault) = relation_verdict(&pairs.case.evaluation, self.example, pairs.constants, Some(&pairs.reads), relation, &mut self.compare, &mut pairs.found) {
                pairs.fault = Some(fault);
            }
        }
    }
}

/// The verdict of each relation of the `determination` of the case `name`
/// that is in `awaiting` and that the program of `case` has, merged over the
/// pairs, and the name of each relation the entry sends: the entry of a train
/// pair at that example, the entry of the task at the first. Each pair is
/// dropped once it is compared, and each relation compared leaves `awaiting`,
/// which the first entry sets to the relations it sends. A run that gave no
/// rows is a fault where `awaiting` is not set, or a relation in it is in the
/// program of `case`.
fn determination_verdicts(case: &ConceptCase<'_>, name: &str, constants: &BTreeMap<String, i64>, determination: FileDetermination, awaiting: &mut Option<Vec<String>>) -> Result<Found, String> {
    let evaluation = &case.evaluation;
    let has = |relation: &String| named_relation(evaluation.program, relation).is_some();
    let mut found = Found::default();
    let pairs = match (determination.failure, determination.pairs) {
        (Some(failure), _) => {
            return if awaiting.as_ref().is_some_and(|waiting| !waiting.iter().any(has)) { Ok(found) } else { Err(format!("no Souffle rows: {failure}")) };
        }
        (None, pairs) => pairs.ok_or("the `determination` of the rows file has no `pairs`")?,
    };
    pairs.iter().flat_map(|entry| &entry.relations).for_each(|relation| add_once(&mut found.sent, &relation.name));
    let waiting = awaiting.get_or_insert_with(|| found.sent.clone());
    let left: Vec<String> = waiting.iter().filter(|relation| has(relation)).cloned().collect();
    for mut entry in pairs {
        entry.relations.retain(|relation| left.contains(&relation.name));
        if entry.relations.is_empty() {
            continue;
        }
        let pair = entry.pair.clone();
        let mut trains = evaluation.task.train_examples().enumerate();
        let example = if pair == TASK_PAIR { trains.next().map(|(_, example)| example) } else { trains.find(|&(index, _)| pair_name(evaluation.task, index) == pair).map(|(_, example)| example) };
        let example = example.ok_or_else(|| format!("the `determination` has the pair `{pair}`, which is no train pair of the task"))?;
        let mut compare = PairCompare::new(format!("{name}, determination, {pair}"));
        for relation in entry.relations {
            relation_verdict(evaluation, example, constants, None, relation, &mut compare, &mut found)?;
        }
    }
    waiting.retain(|relation| !left.contains(relation));
    Ok(found)
}

/// The verdict of `relation`, one relation of a pair of the rows file,
/// compared with the engine's rows on `example` and merged into `found`, with
/// `compare` the compare of its pair; the relation's name is added to
/// `found.sent`. Where `reads` gives, for each node of the program, whether it
/// is read, a relation whose node is not read is not compared, and is added
/// to `found.unread`.
fn relation_verdict(
    evaluation: &Evaluation<'_>,
    example: Example,
    constants: &BTreeMap<String, i64>,
    reads: Option<&[bool]>,
    relation: FileRelation,
    compare: &mut PairCompare,
    found: &mut Found,
) -> Result<(), String> {
    add_once(&mut found.sent, &relation.name);
    let unread = reads.is_some_and(|reads| matches!(named_relation(evaluation.program, &relation.name), Some(Ok(node)) if !reads[node.node.0 as usize]));
    if unread {
        add_once(&mut found.unread, &relation.name);
        return Ok(());
    }
    if relation.idents.len() != relation.columns.len() {
        return Err(format!("the relation `{}` of the rows file has {} columns and {} `idents`", relation.name, relation.columns.len(), relation.idents.len()));
    }
    if let Some((name, verdict)) = compare.verdict(engine_side(evaluation, relation, example, constants)) {
        merge(&mut found.lines, name, verdict);
    }
    Ok(())
}

/// One relation on one pair: the engine's rows at each model, over the
/// columns of the map, with the rows of each open parameter's relation at the
/// model, Souffle's rows projected onto the columns, and each open value of
/// Souffle's relation projected onto them. A column of the map that the
/// engine's relation lacks, or that the relation of an open parameter lacks,
/// gives a fault. The file's rows are dropped, with equal texts of the
/// projected rows held once, before the engine's models are read.
fn engine_side(evaluation: &Evaluation<'_>, file: FileRelation, example: Example, constants: &BTreeMap<String, i64>) -> Checked {
    let FileRelation { name, columns, idents, unread, unresolved, rows, by_open, fault } = file;
    let checked = |engine, left_out, souffle, by_open| Checked { name: name.clone(), souffle, by_open, engine, left_out, fault: fault.clone() };
    let names = match engine_columns(evaluation, &name) {
        None => return checked(None, Vec::new(), BTreeSet::new(), OpenValues::default()),
        Some(Err(unread)) => return checked(Some(unread), Vec::new(), BTreeSet::new(), OpenValues::default()),
        Some(Ok(names)) => names,
    };
    let columns = column_names(&columns);
    let mut left_out = [column_names(&unread), unresolved.iter().map(unresolved_note).collect()].concat();
    let mut kept = Vec::new();
    let mut lacking = Vec::new();
    for (entry, column) in columns.iter().enumerate() {
        match names.iter().position(|n| n.name == *column) {
            Some(position) if names[position].pose => left_out.push(format!("{column} (a Pose, whose value depends on the frame)")),
            Some(position) => kept.push((entry, Column { position, minted: matches!(idents[entry], Some(FileIdent::Minted)) })),
            None => lacking.push(column.clone()),
        }
    }
    if !lacking.is_empty() {
        let text = if kept.is_empty() {
            format!("none of the columns of the map is a column of the engine's relation: {}", lacking.join(", "))
        } else {
            format!("the engine's relation lacks the columns of the map: {}", lacking.join(", "))
        };
        return checked(Some(EngineModels::Fault(text)), left_out, BTreeSet::new(), OpenValues::default());
    }
    let (picks, open_values) = match by_open {
        Some(FileByOpen { picks, values }) => (picks.into_iter().map(|(name, columns)| FilePick { name, columns: column_names(&columns) }).collect(), values),
        None => (Vec::new(), Vec::new()),
    };
    let pick_columns = match pick_columns(evaluation, &picks) {
        Ok(columns) => columns,
        Err(text) => return checked(Some(EngineModels::Fault(text)), left_out, BTreeSet::new(), OpenValues::default()),
    };
    let mut interner = Interner::default();
    let entries: Vec<usize> = kept.iter().map(|&(entry, _)| entry).collect();
    let souffle = interner.project(&entries, &rows);
    drop(rows);
    let values = open_values
        .iter()
        .map(|value| OpenValue {
            rows: interner.project(&entries, &value.rows),
            picks: picks.iter().map(|pick| value.picks.get(&pick.name).map(|rows| rows.iter().map(|row| interner.row(row.iter().flatten())).collect())).collect(),
        })
        .collect();
    drop(open_values);
    let columns: Vec<Column> = kept.iter().map(|&(_, column)| column).collect();
    let requests: Vec<PickRequest<'_>> = picks.iter().zip(&pick_columns).map(|(pick, columns)| PickRequest { name: &pick.name, projection: Projection::Positions(columns) }).collect();
    let engine = match engine_models(evaluation, &name, example, constants, Projection::Positions(&columns), &requests) {
        None => EngineModels::Fault("the relation has no rows to read".to_owned()),
        Some(EngineModels::Models(models)) => {
            EngineModels::Models(models.into_iter().map(|model| EngineModel { rows: distinct(model.rows), picks: model.picks.into_iter().map(|pick| pick.map(distinct)).collect() }).collect())
        }
        Some(fault) => fault,
    };
    let by_open = OpenValues { picks: picks.into_iter().map(|pick| pick.name).collect(), values };
    checked(Some(engine), left_out, souffle, by_open)
}

/// An intern pool for the texts of the leaves of one relation's rows: equal
/// texts share one allocation.
#[derive(Default)]
struct Interner(StableHashSet<Arc<str>>);

impl Interner {
    /// `leaves`, each text replaced by the pool's equal text.
    fn row<'l>(&mut self, leaves: impl Iterator<Item = &'l Leaf>) -> Vec<Leaf> {
        leaves
            .map(|leaf| match leaf {
                Leaf::Number(number) => Leaf::Number(*number),
                Leaf::Other(text) => Leaf::Other(match self.0.get(text) {
                    Some(held) => Arc::clone(held),
                    None => {
                        self.0.insert(Arc::clone(text));
                        Arc::clone(text)
                    }
                }),
            })
            .collect()
    }

    /// The set of rows that give the leaves at `entries` of each row of
    /// `rows`, a row of the file as its columns' leaves.
    fn project(&mut self, entries: &[usize], rows: &[Vec<Vec<Leaf>>]) -> BTreeSet<Vec<Leaf>> {
        rows.iter().map(|row| self.row(entries.iter().flat_map(|&entry| &row[entry]))).collect()
    }
}

/// The columns of the engine's relation of each of `picks` that the file
/// names, or a text where a pick's relation or one of its columns is not in
/// the engine's program.
fn pick_columns(evaluation: &Evaluation<'_>, picks: &[FilePick]) -> Result<Vec<Vec<Column>>, String> {
    picks
        .iter()
        .map(|pick| {
            let names = match engine_columns(evaluation, &pick.name) {
                None => return Err(format!("the open parameter {} has no relation in the engine's program", pick.name)),
                Some(Err(EngineModels::Skip(reason) | EngineModels::Fault(reason))) => return Err(format!("the open parameter {}: {reason}", pick.name)),
                Some(Err(EngineModels::Models(_))) => unreachable!("engine_columns gives no models"),
                Some(Ok(names)) => names,
            };
            pick.columns
                .iter()
                .map(|column| names.iter().position(|n| n.name == *column).map(|position| Column { position, minted: false }).ok_or_else(|| format!("the engine's relation {} lacks the column {column}, which the map gives the open parameter", pick.name)))
                .collect()
        })
        .collect()
}

/// The name of a column as the engine names a row position: the label, and,
/// for a field, `<label>.<field>`.
fn column_name(label: &str, field: Option<&str>) -> String {
    field.map_or_else(|| label.to_owned(), |field| format!("{label}.{field}"))
}

/// The name of each column in `columns`.
fn column_names(columns: &[FileColumn]) -> Vec<String> {
    columns.iter().map(|FileColumn(label, field)| column_name(label, field.as_deref())).collect()
}

/// The column's name and the reason of a leaf of the rows file that has no
/// one source.
fn unresolved_note(leaf: &FileUnresolved) -> String {
    let FileUnresolved(label, field, reason) = leaf;
    format!("{} (unresolved: {reason})", column_name(label, field.as_deref()))
}

/// For each of `rows`, whether it is the first of its equal rows.
fn first_of_each<'a>(rows: impl Iterator<Item = &'a Vec<EngineLeaf>>) -> Vec<bool> {
    let mut seen: StableHashSet<&Vec<EngineLeaf>> = StableHashSet::default();
    rows.map(|row| seen.insert(row)).collect()
}

/// `rows` with each row once, in order.
fn distinct(rows: Vec<Vec<EngineLeaf>>) -> Vec<Vec<EngineLeaf>> {
    let first = first_of_each(rows.iter());
    rows.into_iter().zip(first).filter_map(|(row, first)| first.then_some(row)).collect()
}

/// Adds `verdict`, of one pair of one case, to `merged`: a `differ`, a
/// `fault` or an `uncompared` stays as the first of its relation; otherwise
/// the first verdict stands.
fn merge(merged: &mut Vec<(String, Verdict)>, name: String, verdict: Verdict) {
    match merged.iter_mut().find(|(n, _)| *n == name) {
        None => merged.push((name, verdict)),
        Some((_, held)) if held.fails() => {}
        Some((_, held)) if verdict.fails() => *held = verdict,
        Some(_) => {}
    }
}

/// One comparison of a relation: the Souffle rows an engine model's rows
/// stand for, those rows, and, where the models give different rows, the
/// open value the model takes, written for the line's detail. The rows are
/// borrowed from the relation where the comparison takes them whole.
struct Comparison<'a> {
    souffle: Cow<'a, BTreeSet<Vec<Leaf>>>,
    engine: Cow<'a, [Vec<EngineLeaf>]>,
    open: String,
}

/// The engine's rows of a relation, each compared with the Souffle rows it
/// stands for: the one set of rows where the models give one, else, where
/// Souffle's relation holds the open value in a column, the rows of each
/// model with Souffle's rows of the open value that model takes (`taken`),
/// else the union of the models' rows with Souffle's rows. A text for what
/// does not match.
fn comparisons<'a>(models: &'a [EngineModel], souffle: &'a BTreeSet<Vec<Leaf>>, by_open: &OpenValues) -> Result<Vec<Comparison<'a>>, String> {
    let one = |engine: Cow<'a, [Vec<EngineLeaf>]>| Ok(vec![Comparison { souffle: Cow::Borrowed(souffle), engine, open: String::new() }]);
    if models.iter().skip(1).all(|model| same_rows(&model.rows, &models[0].rows)) {
        return one(Cow::Borrowed(&models[0].rows));
    }
    if by_open.values.is_empty() {
        let all: Vec<&Vec<EngineLeaf>> = models.iter().flat_map(|model| &model.rows).collect();
        let first = first_of_each(all.iter().copied());
        return one(Cow::Owned(all.into_iter().zip(first).filter(|&(_, first)| first).map(|(row, _)| row.clone()).collect()));
    }
    let mut used = vec![false; by_open.values.len()];
    let mut pairs = Vec::new();
    for (index, model) in models.iter().enumerate() {
        let (expected, taken) = taken(model, by_open).map_err(|text| format!("{} models; model {} takes {}: {text}", models.len(), index + 1, show_picks(&by_open.picks, &model.picks)))?;
        taken.into_iter().for_each(|open| used[open] = true);
        pairs.push(Comparison { souffle: Cow::Owned(expected), engine: Cow::Borrowed(&model.rows), open: show_picks(&by_open.picks, &model.picks) });
    }
    match used.iter().position(|used| !used) {
        Some(open) => Err(format!("{} models; open value {} of Souffle's {} is the open value of no model", models.len(), open + 1, by_open.values.len())),
        None => Ok(pairs),
    }
}

/// Souffle's rows under the open value that `model` takes, and the open
/// values they are of: those whose picks the model's picks hold, with the
/// open values that a pick of the model does not tell apart (they give the
/// same picks, or differ only at a pick the model holds none of) counted one
/// open value, whose rows must be equal. An open value gives no row to a pick
/// it is `nil` at, so its rows hold at every value of that pick, and its rows
/// are added to those of the open value the model's picks give.
fn taken(model: &EngineModel, by_open: &OpenValues) -> Result<(BTreeSet<Vec<Leaf>>, Vec<usize>), String> {
    let holds = |open: &OpenValue| {
        open.picks.iter().zip(&model.picks).all(|(souffle, engine)| match (souffle, engine) {
            (Some(souffle), Some(engine)) => same_without_idents(engine, souffle),
            _ => true,
        })
    };
    let held: Vec<usize> = (0..by_open.values.len()).filter(|&open| holds(&by_open.values[open])).collect();
    if held.is_empty() {
        return Err(format!("none of Souffle's {} open values is that open value", by_open.values.len()));
    }
    let mut classes: BTreeMap<Vec<bool>, &BTreeSet<Vec<Leaf>>> = BTreeMap::new();
    for &open in &held {
        let value = &by_open.values[open];
        let given: Vec<bool> = value.picks.iter().map(Option::is_some).collect();
        match classes.insert(given, &value.rows) {
            Some(other) if other != &value.rows => return Err("open values that its picks do not tell apart have different rows".to_owned()),
            _ => {}
        }
    }
    Ok((classes.into_values().flatten().cloned().collect(), held))
}

/// The picks of a model as `name=row` for the line's detail, each row's
/// leaves separated by spaces and an Ident place written `_`; a pick the
/// model holds none of is left out.
fn show_picks(names: &[String], picks: &[Option<Vec<Vec<EngineLeaf>>>]) -> String {
    let show = |leaf: &EngineLeaf| match leaf {
        EngineLeaf::Written(Leaf::Number(n)) => n.to_string(),
        EngineLeaf::Written(Leaf::Other(text)) => text.to_string(),
        EngineLeaf::Ident(_) => "_".to_owned(),
    };
    let held: Vec<String> = names
        .iter()
        .zip(picks)
        .filter_map(|(name, rows)| {
            let rows = rows.as_ref()?;
            Some(format!("{name}={}", rows.iter().map(|row| format!("[{}]", row.iter().map(show).collect::<Vec<_>>().join(" "))).collect::<Vec<_>>().join(" ")))
        })
        .collect();
    format!("the open value {}", held.join(" "))
}

/// The compare of the relations of one pair, one relation at a time, on
/// `scope`, a case and a pair. Each relation compares as sets, with each
/// Ident that a lib relation mints written as the text of the set of its
/// members; the relations that hold an Ident of another kind, a number a fact
/// writes, then must agree under one renaming of Idents over all of them, as
/// each pair is a separate run of Souffle, whose numbers denote the objects
/// of that input alone.
struct PairCompare {
    scope: String,
    /// Souffle's rows and the engine's rows of each relation so far that holds
    /// an Ident leaf, which the renaming reads.
    compared: Vec<(BTreeSet<Vec<Leaf>>, Vec<Vec<EngineLeaf>>)>,
}

impl PairCompare {
    fn new(scope: String) -> Self {
        PairCompare { scope, compared: Vec::new() }
    }

    /// The verdict of `relation` and its name, none for a relation that the
    /// case's program lacks. The relation is dropped with it, apart from its
    /// rows that hold an Ident, which the later relations' renaming reads.
    fn verdict(&mut self, relation: Checked) -> Option<(String, Verdict)> {
        let Checked { name, souffle, by_open, engine, left_out, fault } = relation;
        let note = if left_out.is_empty() { String::new() } else { format!("; columns left out of both sides: {}", left_out.join(", ")) };
        let verdict = match engine? {
            EngineModels::Skip(reason) => Verdict::Skip(reason),
            EngineModels::Fault(text) => Verdict::Fault(format!("{}: {text}", self.scope)),
            EngineModels::Models(_) if fault.is_some() => Verdict::Fault(format!("{}: {}", self.scope, fault.unwrap_or_default())),
            EngineModels::Models(models) => self.models_verdict(&models, &souffle, &by_open, &note),
        };
        Some((name, verdict))
    }

    /// The verdict of a relation whose rows at each of `models` are compared
    /// with `souffle`, a `differ` with `note` or an `equal`.
    fn models_verdict(&mut self, models: &[EngineModel], souffle: &BTreeSet<Vec<Leaf>>, by_open: &OpenValues, note: &str) -> Verdict {
        let scope = &self.scope;
        let comparisons = match comparisons(models, souffle, by_open) {
            Ok(comparisons) => comparisons,
            Err(text) => return Verdict::Differ(format!("{scope}: {text}{note}")),
        };
        for Comparison { souffle, engine, open } in &comparisons {
            if !same_without_idents(engine, souffle) {
                let at = if open.is_empty() { String::new() } else { format!("at {open}: ") };
                return Verdict::Differ(format!("{scope}: {at}{}{note}", describe_difference(engine, souffle)));
            }
        }
        let before = self.compared.len();
        let with_idents = comparisons.into_iter().filter(|comparison| comparison.engine.iter().flatten().any(|leaf| matches!(leaf, EngineLeaf::Ident(_))));
        self.compared.extend(with_idents.map(|comparison| (comparison.souffle.into_owned(), comparison.engine.into_owned())));
        if self.compared.len() > before && !renaming_exists(&self.compared.iter().map(|(souffle, engine)| (souffle, engine.as_slice())).collect::<Vec<_>>()) {
            self.compared.truncate(before);
            return Verdict::Differ(format!("{}: no one renaming of Idents makes its rows and those of the relations before it agree{note}", self.scope));
        }
        Verdict::Equal(format!("{}{note}", self.scope))
    }
}

/// The two counts of rows and one row that only one side holds, with each
/// Ident place left out.
fn describe_difference(engine: &[Vec<EngineLeaf>], record: &BTreeSet<Vec<Leaf>>) -> String {
    let counts = format!("{} rows in the engine and {} in Souffle", engine.len(), record.len());
    let places: Vec<bool> = engine.first().map_or_else(Vec::new, |row| row.iter().map(|leaf| matches!(leaf, EngineLeaf::Written(_))).collect());
    let ours: BTreeSet<Vec<Option<Leaf>>> = engine
        .iter()
        .map(|row| row.iter().map(|leaf| match leaf { EngineLeaf::Written(leaf) => Some(leaf.clone()), EngineLeaf::Ident(_) => None }).collect())
        .collect();
    if record.iter().any(|row| !places.is_empty() && row.len() != places.len()) {
        return format!("{counts}; their rows hold other counts of leaves");
    }
    let theirs: BTreeSet<Vec<Option<Leaf>>> = record
        .iter()
        .map(|row| row.iter().zip(&places).map(|(leaf, &written)| written.then(|| leaf.clone())).collect())
        .collect();
    let show = |row: &Vec<Option<Leaf>>| {
        row.iter()
            .map(|leaf| match leaf {
                Some(Leaf::Number(n)) => n.to_string(),
                Some(Leaf::Other(text)) => text.to_string(),
                None => "_".to_owned(),
            })
            .collect::<Vec<_>>()
            .join(" ")
    };
    if let Some(row) = ours.difference(&theirs).next() {
        format!("{counts}; only the engine holds [{}]", show(row))
    } else if let Some(row) = theirs.difference(&ours).next() {
        format!("{counts}; only Souffle holds [{}]", show(row))
    } else {
        format!("{counts}; the rows agree as sets, and differ in multiplicity or in the Ident places")
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use arclog::terms::{Content, Ident, InternTable, WrittenIdent};

    /// What `task_verdicts` gives on a rows file with `text` for its content,
    /// for a corpus and tasks that no case of the text reaches.
    fn verdicts_of(name: &str, text: &str) -> Result<Vec<(String, Verdict)>, String> {
        let path = std::env::temp_dir().join(format!("row_parity_{}_{name}.json", std::process::id()));
        std::fs::write(&path, text).expect("the rows file writes");
        let verdicts = task_verdicts(Path::new("corpus"), Path::new("tasks"), "aaaa0001", &path, &Mutex::new(BTreeMap::new()));
        std::fs::remove_file(&path).expect("the rows file is removed");
        verdicts
    }

    #[test]
    fn reads_the_failures_and_the_left_out_relations_of_a_rows_file() {
        let text = r#"{"orientation_constants": {}, "cases": [{"case": "concept", "failure": "no rows"}],
            "not_compared": [{"name": "&b", "verdict": "skip", "reason": "an input"}, {"name": "&c", "verdict": "uncompared", "reason": "no entry"}]}"#;
        let verdicts = verdicts_of("failures", text).expect("the file reads");
        let words: Vec<(&str, &str)> = verdicts.iter().map(|(relation, verdict)| (relation.as_str(), verdict.word())).collect();
        assert_eq!(words, [("*", "fault"), ("&b", "skip"), ("&c", "uncompared")]);
    }

    #[test]
    fn refuses_cases_that_come_before_the_constants() {
        let text = r#"{"cases": [{"case": "concept", "pairs": []}], "orientation_constants": {}, "not_compared": []}"#;
        assert!(verdicts_of("order", text).is_err());
    }

    #[test]
    fn refuses_a_rows_file_with_no_left_out_relations() {
        assert!(verdicts_of("not_compared", r#"{"orientation_constants": {}, "cases": []}"#).is_err());
    }

    /// The verdict of each relation of `relations` on `scope`, a case and a
    /// pair, in order; none for a relation that the case's program lacks.
    fn compare_pair(scope: &str, relations: impl IntoIterator<Item = Checked>) -> Vec<(String, Verdict)> {
        let mut compare = PairCompare::new(scope.to_owned());
        relations.into_iter().filter_map(|relation| compare.verdict(relation)).collect()
    }

    fn n(value: i64) -> Leaf {
        Leaf::Number(value)
    }

    fn souffle(rows: &[&[i64]]) -> BTreeSet<Vec<Leaf>> {
        rows.iter().map(|row| row.iter().map(|&v| n(v)).collect()).collect()
    }

    fn written(row: &[i64]) -> Vec<EngineLeaf> {
        row.iter().map(|&v| EngineLeaf::Written(n(v))).collect()
    }

    fn checked(name: &str, souffle: BTreeSet<Vec<Leaf>>, rows: Vec<Vec<EngineLeaf>>) -> Checked {
        models(name, souffle, vec![rows])
    }

    fn models(name: &str, souffle: BTreeSet<Vec<Leaf>>, models: Vec<Vec<Vec<EngineLeaf>>>) -> Checked {
        let models = models.into_iter().map(|rows| EngineModel { rows, picks: Vec::new() }).collect();
        Checked { name: name.to_owned(), souffle, by_open: OpenValues::default(), engine: Some(EngineModels::Models(models)), left_out: Vec::new(), fault: None }
    }

    fn idents(count: u32) -> Vec<Ident> {
        let mut table = InternTable::default();
        (0..count).map(|i| table.intern(Content::FromFile { ty: arclog::types::ValueType::Ident, written: WrittenIdent::new(i) })).collect()
    }

    #[test]
    fn differs_where_the_engine_holds_souffles_rows_and_more() {
        let relations = [checked("&a", souffle(&[&[1, 2]]), vec![written(&[1, 2]), written(&[3, 4])])];
        let [(_, verdict)] = &compare_pair("concept, train 0", relations)[..] else { panic!("one verdict") };
        let Verdict::Differ(text) = verdict else { panic!("{verdict:?}") };
        assert!(text.contains("2 rows in the engine and 1 in Souffle") && text.contains("only the engine holds [3 4]"), "{text}");
    }

    #[test]
    fn differs_where_a_nullary_relation_stands_on_one_side_alone() {
        let present = BTreeSet::from([Vec::new()]);
        let relations = [checked("&flag", present.clone(), Vec::new()), checked("&other", BTreeSet::new(), vec![Vec::new()]), checked("&both", present, vec![Vec::new()])];
        let verdicts = compare_pair("concept, train 0", relations);
        assert!(matches!(verdicts[0].1, Verdict::Differ(_)), "{verdicts:?}");
        assert!(matches!(verdicts[1].1, Verdict::Differ(_)), "{verdicts:?}");
        assert!(matches!(verdicts[2].1, Verdict::Equal(_)), "{verdicts:?}");
    }

    #[test]
    fn equals_where_the_union_of_the_models_is_souffles_rows() {
        let relations = [models("&order", souffle(&[&[1, 2], &[3, 4]]), vec![vec![written(&[1, 2])], vec![written(&[3, 4])]])];
        let [(_, verdict)] = &compare_pair("concept, train 0", relations)[..] else { panic!("one verdict") };
        assert!(matches!(verdict, Verdict::Equal(_)), "{verdict:?}");
    }

    #[test]
    fn differs_where_the_union_of_the_models_is_not_souffles_rows() {
        let relations = [models("&order", souffle(&[&[1, 2], &[3, 4]]), vec![vec![written(&[1, 2])], vec![written(&[5, 6])]])];
        let [(_, verdict)] = &compare_pair("concept, train 0", relations)[..] else { panic!("one verdict") };
        assert!(matches!(verdict, Verdict::Differ(_)), "{verdict:?}");
    }

    /// A relation of two open values of the parameter `&p`: the rows `[1 2]`
    /// at `&p` = `[1]`, the rows `[3 4]` at `&p` = `[2]`, and the rows `[9 9]`
    /// at `nil`, which hold at both. `at` gives the engine's rows and its
    /// pick at each of two models.
    fn open_relation(at: [(&[i64], i64); 2]) -> Checked {
        let open = |rows: &[&[i64]], pick: Option<i64>| OpenValue { rows: souffle(rows), picks: vec![pick.map(|p| souffle(&[&[p]]))] };
        let values = vec![open(&[&[1, 2]], Some(1)), open(&[&[3, 4]], Some(2)), open(&[&[9, 9]], None)];
        let model = |(rows, pick): (&[i64], i64)| EngineModel { rows: vec![written(rows), written(&[9, 9])], picks: vec![Some(vec![written(&[pick])])] };
        Checked {
            name: "&out".to_owned(),
            souffle: souffle(&[&[1, 2], &[3, 4], &[9, 9]]),
            by_open: OpenValues { picks: vec!["&p".to_owned()], values },
            engine: Some(EngineModels::Models(at.into_iter().map(model).collect())),
            left_out: Vec::new(),
            fault: None,
        }
    }

    #[test]
    fn equals_where_each_model_holds_the_rows_of_its_own_open_value() {
        let relations = [open_relation([(&[1, 2], 1), (&[3, 4], 2)])];
        let [(_, verdict)] = &compare_pair("concept, train 0", relations)[..] else { panic!("one verdict") };
        assert!(matches!(verdict, Verdict::Equal(_)), "{verdict:?}");
    }

    #[test]
    fn differs_where_the_models_hold_the_rows_of_the_open_values_swapped() {
        let relations = [open_relation([(&[1, 2], 2), (&[3, 4], 1)])];
        let [(_, verdict)] = &compare_pair("concept, train 0", relations)[..] else { panic!("one verdict") };
        let Verdict::Differ(text) = verdict else { panic!("{verdict:?}") };
        assert!(text.contains("&p=[2]") && text.contains("only the engine holds [1 2]"), "{text}");
    }

    #[test]
    fn differs_where_a_model_takes_no_open_value_of_souffles() {
        let relations = [open_relation([(&[1, 2], 1), (&[3, 4], 3)])];
        let [(_, verdict)] = &compare_pair("concept, train 0", relations)[..] else { panic!("one verdict") };
        let Verdict::Differ(text) = verdict else { panic!("{verdict:?}") };
        assert!(text.contains("open value 2 of Souffle's 3 is the open value of no model"), "{text}");
    }

    #[test]
    fn differs_where_two_relations_agree_under_two_renamings() {
        let [x, y] = idents(2)[..] else { unreachable!() };
        let id = |ident, color: i64| vec![EngineLeaf::Ident(ident), EngineLeaf::Written(n(color))];
        let relations = [
            checked("&color", souffle(&[&[7, 1], &[8, 2]]), vec![id(x, 1), id(y, 2)]),
            checked("&big", souffle(&[&[7]]), vec![vec![EngineLeaf::Ident(y)]]),
        ];
        let verdicts = compare_pair("concept, train 0", relations);
        assert!(matches!(verdicts[0].1, Verdict::Equal(_)), "{verdicts:?}");
        assert!(matches!(&verdicts[1].1, Verdict::Differ(text) if text.contains("no one renaming")), "{verdicts:?}");
    }

    fn text(members: &str) -> Leaf {
        Leaf::Other(members.into())
    }

    fn minted(members: &str) -> Vec<EngineLeaf> {
        vec![EngineLeaf::Written(text(members))]
    }

    #[test]
    fn differs_where_a_minted_id_has_other_members() {
        let relations = [checked("&label", BTreeSet::from([vec![text("{[1],[2]}")]]), vec![minted("{[1],[3]}")])];
        let [(_, verdict)] = &compare_pair("concept, train 0", relations)[..] else { panic!("one verdict") };
        assert!(matches!(verdict, Verdict::Differ(_)), "{verdict:?}");
    }

    #[test]
    fn faults_where_a_minted_id_has_no_row_of_the_minting_relation() {
        let mut relation = checked("&label", BTreeSet::from([vec![text("{}")]]), vec![minted("{}")]);
        relation.fault = Some("the id 5 has no row of comps4.label at the key of the row".to_owned());
        let [(_, verdict)] = &compare_pair("concept, train 0", [relation])[..] else { panic!("one verdict") };
        assert!(matches!(verdict, Verdict::Fault(text) if text.contains("the id 5 has no row")), "{verdict:?}");
    }

    #[test]
    fn equals_where_the_rows_agree_under_one_renaming() {
        let [x, y] = idents(2)[..] else { unreachable!() };
        let id = |ident, color: i64| vec![EngineLeaf::Ident(ident), EngineLeaf::Written(n(color))];
        let relations = [
            checked("&color", souffle(&[&[7, 1], &[8, 2]]), vec![id(x, 1), id(y, 2)]),
            checked("&big", souffle(&[&[7]]), vec![vec![EngineLeaf::Ident(x)]]),
        ];
        let verdicts = compare_pair("concept, train 0", relations);
        assert!(verdicts.iter().all(|(_, verdict)| matches!(verdict, Verdict::Equal(_))), "{verdicts:?}");
    }
}
