//! `compare`: runs the concept case of each solver given, or of every
//! solver of the corpus, at its stored `param` records, and compares each
//! pair's output with the snapshot of the Souffle outcomes, and the run's
//! time per solver with Souffle's time there. It prints each mismatch by
//! solver, case and pair, with the first relation whose rows differ from
//! those of Souffle's reruns of the pairs up to that pair, and each solver
//! that runs slower.
//!
//! Its arguments: the snapshot's directory, the corpus directory, the
//! directory of the task files, then the task ids of the solvers to run,
//! and `--reads <name>` for the solvers that the snapshot's `uses.json`
//! gives for a lib name or a form keyword; every solver of the corpus where
//! it is given none. The rerun is `scripts/souffle_parity.py rerun --json`,
//! so the command runs from the root of the tree.

use std::collections::{BTreeMap, BTreeSet};
use std::path::{Path, PathBuf};
use std::process::ExitCode;
use std::sync::OnceLock;
use std::time::Instant;

use arclog::check::{check_program, CheckCache, SolverClauses};
use arclog::eval::instance::Constructions;
use arclog::eval::join::each_row;
use arclog::eval::{relation_of, Caps, Cancellation, Evaluation, GridValue, Limits, NoGridColumns, Outcome, ParameterValues, RelationValue};
use arclog::harness::{read_corpus_solver, run_over_corpus, CorpusSolver, SolverResult};
use arclog::program::{DeclaredName, ProgramRelation, RelationName};
use arclog::registry::Registry;
use arclog::resolver::{resolve, Side};
use arclog::session::{SessionBound, TaskSession};
use arclog::solver::CaseName;
use arclog::task::{read_task, Grid, Task};
use arclog::hash::StableHashMap;
use arclog::terms::{Constant, Example, Ident, Term};
use serde_json::Value;

use crate::select::{read_json, selected};

const USAGE: &str = "usage: arclog-cli compare <snapshot-dir> <corpus-dir> <tasks-dir> [<task_id> ...] [--reads <name> ...]";

/// The bound on the bytes of a task session of the engine's runs.
pub(crate) const SESSION_BYTES: usize = 1 << 32;

/// The subcommand on `args`, the arguments after its name.
pub fn run(args: &[String]) -> ExitCode {
    let Some(arguments) = Arguments::parse(args) else {
        eprintln!("{USAGE}");
        return ExitCode::from(2);
    };
    let selected = match selected(&arguments.task_ids, &arguments.reads, &arguments.snapshot.join("uses.json")) {
        Ok(selected) => selected,
        Err(message) => {
            eprintln!("{message}");
            return ExitCode::from(2);
        }
    };
    let report = run_over_corpus(&arguments.corpus, |solver| match &selected {
        Some(ids) if !ids.contains(&solver.task_id) => SolverResult::Pass,
        _ => compare_solver(&arguments, solver),
    });
    let report = match report {
        Ok(report) => report,
        Err(error) => {
            eprintln!("the corpus does not read: {error:?}");
            return ExitCode::from(2);
        }
    };
    for (solver, lines) in &report.failures {
        for line in lines {
            println!("{}: {line}", solver.task_id);
        }
    }
    let compared = selected.map_or(report.checked, |ids| ids.len());
    println!("{} of {compared} solvers differ from the snapshot", report.failures.len());
    if report.failures.is_empty() { ExitCode::SUCCESS } else { ExitCode::FAILURE }
}

/// The arguments of the subcommand.
struct Arguments {
    snapshot: PathBuf,
    corpus: PathBuf,
    tasks: PathBuf,
    task_ids: Vec<String>,
    reads: Vec<String>,
}

impl Arguments {
    fn parse(args: &[String]) -> Option<Arguments> {
        let mut positional = Vec::new();
        let mut reads = Vec::new();
        let mut args = args.iter();
        while let Some(arg) = args.next() {
            if arg == "--reads" {
                reads.push(args.next()?.clone());
            } else {
                positional.push(arg.clone());
            }
        }
        let mut positional = positional.into_iter();
        let (snapshot, corpus, tasks) = (positional.next()?, positional.next()?, positional.next()?);
        Some(Arguments { snapshot: snapshot.into(), corpus: corpus.into(), tasks: tasks.into(), task_ids: positional.collect(), reads })
    }
}

/// The snapshot's key of the case `name`: `concept` for the case of a
/// solver with no `ALTS` form, and otherwise its alts joined by ` & `.
fn case_key(name: &CaseName) -> BTreeSet<String> {
    if name.0.is_empty() {
        return BTreeSet::from(["concept".to_owned()]);
    }
    name.0.iter().map(|alt| alt.0.to_string()).collect()
}

/// The record of the case `name` in a solver's snapshot record, with its
/// key there; a key names the same alts in any order.
fn case_record<'r>(record: &'r Value, name: &CaseName) -> Option<(&'r str, &'r Value)> {
    let wanted = case_key(name);
    let cases = record.get("cases")?.as_object()?;
    cases.iter().find(|(key, _)| key.split(" & ").map(str::to_owned).collect::<BTreeSet<_>>() == wanted).map(|(k, v)| (k.as_str(), v))
}

/// The pair names of the task's examples, as the snapshot writes them.
fn pair_name(task: &Task, example: usize) -> String {
    if example < task.train.len() { format!("train {example}") } else { format!("test {}", example - task.train.len()) }
}

/// The comparison of the concept case of `solver` with its snapshot record.
fn compare_solver(arguments: &Arguments, solver: &CorpusSolver) -> SolverResult {
    match compared(arguments, solver) {
        Ok(lines) if lines.is_empty() => SolverResult::Pass,
        Ok(lines) => SolverResult::Fail(lines),
        Err(line) => SolverResult::Fail(vec![line]),
    }
}

/// Each line of the comparison of the concept case of `solver`, or the one
/// line of the fault that stops it.
fn compared(arguments: &Arguments, corpus: &CorpusSolver) -> Result<Vec<String>, String> {
    let id = &corpus.task_id;
    let record = read_json(&arguments.snapshot.join(format!("{id}.json")))?;
    with_concept_case(&arguments.corpus, &arguments.tasks, id, |case| {
        let (key, case_record) = case_record(&record, case.name).ok_or("the snapshot has no record of the concept case")?;
        let (outputs, seconds) = case.run();
        let outputs = outputs.map_err(|fault| format!("{key}: a fault of the run at {:?}: {}", fault.form, fault.message))?;
        let task = case.evaluation.task;
        let mut lines = Vec::new();
        let examples: Vec<(String, Example)> = task.examples().enumerate().map(|(index, example)| (pair_name(task, index), example)).collect();
        let mut reruns: Vec<Option<Rerun>> = Vec::new();
        for (index, (pair, _)) in examples.iter().enumerate() {
            let got = outputs.as_ref().map(|grids| &grids[index].1);
            let expected = case_record.get("pairs").and_then(|pairs| pairs.get(pair));
            if agrees(got, expected) {
                continue;
            }
            let mut line = format!("{key}, {pair}: the engine gives {}, Souffle {}", describe(got), expected.map_or("no outcome".to_owned(), Value::to_string));
            while reruns.len() <= index {
                reruns.push(rerun(id, key, &examples[reruns.len()].0));
            }
            let pairs: Option<Vec<PairRows<'_>>> = examples[..=index]
                .iter()
                .zip(&reruns)
                .map(|((pair, example), rerun)| {
                    let rerun = rerun.as_ref()?;
                    let example = *example;
                    let evaluation = &case.evaluation;
                    let engine: Box<dyn Fn(&str) -> Option<Result<Vec<Vec<EngineLeaf>>, String>> + '_> =
                        Box::new(move |name| engine_rows(evaluation, name, example, &rerun.orientation_constants));
                    Some(PairRows { pair, rerun, engine })
                })
                .collect();
            if let Some(comparison) = pairs.map(|pairs| first_difference(&pairs)) {
                for relation in &comparison.not_compared {
                    line.push_str(&format!("; {relation}"));
                }
                if let Some(difference) = comparison.difference {
                    line.push_str(&format!("; {difference}"));
                }
            }
            lines.push(line);
        }
        if let Some(souffle) = record.get("cpu_seconds").and_then(Value::as_f64) {
            if seconds > souffle {
                lines.push(format!("the engine runs {seconds:.3} s against Souffle's {souffle:.3} s"));
            }
        }
        Ok(lines)
    })
}

/// The table of the lib's constructions, built once.
pub(crate) fn constructions() -> Result<&'static Constructions, String> {
    static TABLE: OnceLock<Result<Constructions, String>> = OnceLock::new();
    TABLE
        .get_or_init(|| arclog_constructions::constructions(Registry::get()).map_err(|fault| format!("no table of constructions: {fault:?}")))
        .as_ref()
        .map_err(Clone::clone)
}

/// The concept case of a solver, set up for its run at its stored `param`
/// records, over the table of the lib's constructions.
pub(crate) struct ConceptCase<'a> {
    pub(crate) name: &'a CaseName,
    pub(crate) evaluation: Evaluation<'a>,
}

impl ConceptCase<'_> {
    /// The grid of each example of the run, and the run's seconds.
    pub(crate) fn run(&self) -> (Outcome<Result<Box<[(Example, GridValue)]>, NoGridColumns>>, f64) {
        let start = Instant::now();
        let outputs = self.evaluation.outputs();
        (outputs, start.elapsed().as_secs_f64())
    }
}

/// What `body` gives on the concept case of the solver `id` of `corpus`,
/// on its task in `tasks`, or the fault that stops the case's setup.
pub(crate) fn with_concept_case<T>(corpus: &Path, tasks: &Path, id: &str, body: impl FnOnce(&ConceptCase<'_>) -> Result<T, String>) -> Result<T, String> {
    let solver = read_corpus_solver(corpus, id).ok_or("the solver's files do not read")?;
    let task = read_task(&tasks.join(format!("{id}.json"))).map_err(|error| format!("the task does not read: {error:?}"))?;
    let registry = Registry::get();
    let case = solver.concept_case();
    let resolved = resolve(&case.program, None, &solver.derived_relations(), registry).value;
    let clauses = SolverClauses::of(&solver, registry);
    let program = check_program(resolved, &clauses, registry, &mut CheckCache::default()).map_err(|refusals| {
        let messages: Vec<&str> = refusals.iter().map(|d| &*d.message).collect();
        format!("the checker refuses the concept case: {}", messages.join("; "))
    })?;
    let parameters = ParameterValues::stored(solver.arcdata.value());
    let session = TaskSession::new(SessionBound { bytes: SESSION_BYTES }, Caps::PROVISIONAL);
    let limits = Limits { deadline: None, cancellation: Cancellation::default() };
    let evaluation = Evaluation { program: &program, task: &task, parameters: &parameters, session: &session, registry, constructions: constructions()?, limits: &limits };
    body(&ConceptCase { name: &case.name, evaluation })
}

/// Whether the engine's grid value agrees with Souffle's outcome: one
/// grid, the same, or both `undefined`.
fn agrees(got: Result<&GridValue, &NoGridColumns>, expected: Option<&Value>) -> bool {
    match (got, expected) {
        (Ok(GridValue::Grid(grid)), Some(expected)) => {
            expected.get("grids").and_then(Value::as_array).is_some_and(|grids| grids.len() == 1 && grid_json(grid) == grids[0])
        }
        (Ok(GridValue::Undefined), Some(expected)) => expected.as_str() == Some("undefined"),
        _ => false,
    }
}

/// The grid as the snapshot writes it: a list of rows of digits.
fn grid_json(grid: &Grid) -> Value {
    Value::from(grid.rows().iter().map(|row| Value::from(row.iter().map(|&c| Value::from(c.digit())).collect::<Vec<_>>())).collect::<Vec<_>>())
}

/// What the engine gives on a pair, for a mismatch line.
fn describe(got: Result<&GridValue, &NoGridColumns>) -> String {
    let stop = |stop: &arclog::eval::Stop| format!("a stop at {:?} at the form {:?}", stop.bound, stop.form);
    match got {
        Err(NoGridColumns::NoPairSolves) => "no grid columns of `&output`".to_owned(),
        Err(NoGridColumns::Stopped(at)) => format!("no grid columns of `&output`, by {}", stop(at)),
        Ok(GridValue::Grid(grid)) => grid_json(grid).to_string(),
        Ok(GridValue::Undefined) => "undefined".to_owned(),
        Ok(GridValue::Stopped(at)) => stop(at),
    }
}

/// Souffle's rerun of the case `case` of the solver `id` on `pair`, with
/// every relation written out; `None` where the rerun fails.
fn rerun(id: &str, case: &str, pair: &str) -> Option<Rerun> {
    let rerun = std::process::Command::new("uv")
        .args(["run", "python", "scripts/souffle_parity.py", "rerun", id, case, pair, "--json"])
        .output()
        .ok()?;
    if !rerun.status.success() {
        return None;
    }
    serde_json::from_slice::<Value>(&rerun.stdout).ok().and_then(|json| Rerun::of(&json))
}

/// The rows of one pair on both sides: Souffle's rerun on the pair, and the
/// engine's rows on it of the relation of each name, `None` for a relation
/// the engine does not derive by that name, which is left out, and a text
/// for rows it cannot give.
struct PairRows<'a> {
    pair: &'a str,
    rerun: &'a Rerun,
    engine: Box<dyn Fn(&str) -> Option<Result<Vec<Vec<EngineLeaf>>, String>> + 'a>,
}

/// What the comparison of the rows of the pairs gives: the first relation
/// whose rows differ, with its pair and what differs, and each relation
/// before it left out, since its rows on the two sides hold different
/// counts of leaves.
#[derive(Debug, Default)]
struct Comparison {
    difference: Option<String>,
    not_compared: Vec<String>,
}

/// The first relation whose rows differ, by the order of `pairs` and then
/// the rerun's order on each pair: the first such that no one renaming of
/// Idents over every pair makes every relation up to it agree. A relation
/// whose engine rows and Souffle rows hold different counts of leaves,
/// as where the converter left a Souffle column out of the arclog
/// relation, is not compared, and the comparison gives it with the two
/// counts.
fn first_difference(pairs: &[PairRows<'_>]) -> Comparison {
    let mut comparison = Comparison::default();
    let mut compared: Vec<(&BTreeSet<Vec<Leaf>>, Vec<Vec<EngineLeaf>>)> = Vec::new();
    for PairRows { pair, rerun, engine } in pairs {
        for (name, souffle) in &rerun.relations {
            let Some(rows) = engine(name) else { continue };
            let differs = |what: String| Some(format!("the first relation whose rows differ is {name} on {pair}: {what}"));
            let rows = match rows {
                Ok(rows) => rows,
                Err(text) => {
                    comparison.difference = differs(format!("the engine gives {text}"));
                    return comparison;
                }
            };
            if let (Some(ours), Some(theirs)) = (rows.first(), souffle.first())
                && ours.len() != theirs.len()
            {
                comparison.not_compared.push(format!(
                    "{name} on {pair} is not compared: its rows hold {} leaves in the engine and {} in Souffle",
                    ours.len(),
                    theirs.len()
                ));
                continue;
            }
            if !same_without_idents(&rows, souffle) {
                comparison.difference = differs(format!("{} rows against Souffle's {}", rows.len(), souffle.len()));
                return comparison;
            }
            if !rows.iter().flatten().any(|leaf| matches!(leaf, EngineLeaf::Ident(_))) {
                continue;
            }
            compared.push((souffle, rows));
            if !renaming_exists(&compared) {
                comparison.difference = differs("no one renaming of Idents makes its rows and those before it agree".to_owned());
                return comparison;
            }
        }
    }
    comparison
}

/// One leaf of a row, as `scripts/souffle_parity.py rerun --json` writes
/// a row: an integer, or another value by its JSON text.
#[derive(Clone, PartialEq, Eq, PartialOrd, Ord, Debug)]
pub(crate) enum Leaf {
    Number(i64),
    Other(Box<str>),
}

impl Leaf {
    fn of(json: &Value) -> Option<Leaf> {
        match json {
            Value::Number(n) => Some(n.as_i64().map_or_else(|| Leaf::Other(n.to_string().into()), Leaf::Number)),
            Value::String(s) => Some(Leaf::Other(s.as_str().into())),
            _ => None,
        }
    }
}

/// One leaf of a row of the engine: a leaf as Souffle writes it, or an
/// Ident, which stands for Souffle's number of the same entity under a
/// renaming that [`renaming_exists`] looks for.
#[derive(Clone, PartialEq, Eq, Debug)]
pub(crate) enum EngineLeaf {
    Written(Leaf),
    Ident(Ident),
}

/// The rows of Souffle's rerun of a case on one pair, each relation by its
/// arclog name, in the rerun's order, and the number Souffle gives each
/// orientation constant of the lib, by its name.
struct Rerun {
    relations: Vec<(String, BTreeSet<Vec<Leaf>>)>,
    orientation_constants: BTreeMap<String, i64>,
}

impl Rerun {
    /// The rerun that `json`, the output of `rerun --json`, gives.
    fn of(json: &Value) -> Option<Rerun> {
        let relations = json.get("relations")?.as_array()?.iter().map(|relation| {
            let [name, rows] = relation.as_array()?.as_slice() else { return None };
            let rows = rows.as_array()?.iter().map(|row| row.as_array()?.iter().map(Leaf::of).collect()).collect::<Option<_>>()?;
            Some((name.as_str()?.to_owned(), rows))
        });
        let constants = json.get("orientation_constants")?.as_object()?;
        Some(Rerun {
            relations: relations.collect::<Option<_>>()?,
            orientation_constants: constants.iter().map(|(name, n)| Some((name.clone(), n.as_i64()?))).collect::<Option<_>>()?,
        })
    }
}

/// Whether `engine` and `souffle` hold rows of equal leaves at each place
/// that holds no Ident in the engine's row, each row once.
fn same_without_idents(engine: &[Vec<EngineLeaf>], souffle: &BTreeSet<Vec<Leaf>>) -> bool {
    let masked = |row: &[EngineLeaf]| row.iter().map(|leaf| match leaf {
        EngineLeaf::Written(leaf) => Some(leaf.clone()),
        EngineLeaf::Ident(_) => None,
    }).collect::<Vec<_>>();
    let mut engine_masked: Vec<Vec<Option<Leaf>>> = engine.iter().map(|row| masked(row)).collect();
    engine_masked.sort();
    let Some(first) = engine.first() else { return souffle.is_empty() };
    if souffle.iter().any(|row| row.len() != first.len()) {
        return false;
    }
    let mut souffle_masked: Vec<Vec<Option<Leaf>>> = souffle
        .iter()
        .map(|row| row.iter().zip(first).map(|(leaf, at)| matches!(at, EngineLeaf::Written(_)).then(|| leaf.clone())).collect())
        .collect();
    souffle_masked.sort();
    engine_masked == souffle_masked
}

/// One side's rows of the relations compared, for [`renaming_exists`]: each
/// row as its relation's place in the list, its leaves with each Ident's
/// place left empty, and its Idents, each by its number on that side, in
/// the order of their places.
struct IdentRows {
    rows: Vec<(usize, Vec<Option<Leaf>>, Vec<usize>)>,
    idents: usize,
}

impl IdentRows {
    /// The engine's side of `relations`.
    fn engine(relations: &[(&BTreeSet<Vec<Leaf>>, Vec<Vec<EngineLeaf>>)]) -> IdentRows {
        let mut numbers: StableHashMap<Ident, usize> = StableHashMap::default();
        let mut rows = Vec::new();
        for (relation, (_, engine)) in relations.iter().enumerate() {
            for row in engine {
                let mut idents = Vec::new();
                let leaves = row
                    .iter()
                    .map(|leaf| match leaf {
                        EngineLeaf::Written(leaf) => Some(leaf.clone()),
                        EngineLeaf::Ident(ident) => {
                            let next = numbers.len();
                            idents.push(*numbers.entry(*ident).or_insert(next));
                            None
                        }
                    })
                    .collect();
                rows.push((relation, leaves, idents));
            }
        }
        IdentRows { rows, idents: numbers.len() }
    }

    /// Souffle's side of `relations`: each leaf at the place of an Ident in
    /// the engine's rows of the relation is an Ident, `None` where one such
    /// leaf is no number.
    fn souffle(relations: &[(&BTreeSet<Vec<Leaf>>, Vec<Vec<EngineLeaf>>)]) -> Option<IdentRows> {
        let mut numbers: BTreeMap<i64, usize> = BTreeMap::new();
        let mut rows = Vec::new();
        for (relation, (souffle, engine)) in relations.iter().enumerate() {
            let places: Vec<bool> = engine.first().map_or_else(Vec::new, |row| row.iter().map(|leaf| matches!(leaf, EngineLeaf::Ident(_))).collect());
            for row in souffle.iter() {
                let mut idents = Vec::new();
                let mut leaves = Vec::new();
                for (leaf, &is_ident) in row.iter().zip(&places) {
                    if !is_ident {
                        leaves.push(Some(leaf.clone()));
                        continue;
                    }
                    let Leaf::Number(n) = leaf else { return None };
                    let next = numbers.len();
                    idents.push(*numbers.entry(*n).or_insert(next));
                    leaves.push(None);
                }
                rows.push((relation, leaves, idents));
            }
        }
        Some(IdentRows { rows, idents: numbers.len() })
    }

    /// The row sets of the side, each Ident written as its class in
    /// `classes`.
    fn by_classes(&self, classes: &[usize]) -> BTreeSet<(usize, Vec<Option<Leaf>>, Vec<usize>)> {
        self.rows.iter().map(|(relation, leaves, idents)| (*relation, leaves.clone(), idents.iter().map(|&i| classes[i]).collect())).collect()
    }
}

/// The classes of the Idents of both sides, each class a number, refined
/// round by round until no class splits: an Ident's key is its class and
/// the rows that hold it, each row by its relation, its leaves, the classes
/// of its Idents and the places this Ident stands at. Classes are numbered
/// by the order of their keys, so the numbering reads no order of Idents.
fn refine(sides: [&IdentRows; 2], mut classes: [Vec<usize>; 2]) -> [Vec<usize>; 2] {
    loop {
        type Key = (usize, Vec<(usize, Vec<Option<Leaf>>, Vec<usize>, Vec<usize>)>);
        let keys: [Vec<Key>; 2] = [0, 1].map(|s| {
            let mut keys: Vec<Key> = (0..sides[s].idents).map(|i| (classes[s][i], Vec::new())).collect();
            for (relation, leaves, idents) in &sides[s].rows {
                let row_classes: Vec<usize> = idents.iter().map(|&i| classes[s][i]).collect();
                for (place, &ident) in idents.iter().enumerate() {
                    if idents[..place].contains(&ident) {
                        continue;
                    }
                    let places = idents.iter().enumerate().filter(|(_, other)| **other == ident).map(|(p, _)| p).collect();
                    keys[ident].1.push((*relation, leaves.clone(), row_classes.clone(), places));
                }
            }
            keys.iter_mut().for_each(|key| key.1.sort());
            keys
        });
        let numbering: BTreeMap<&Key, usize> = keys.iter().flatten().collect::<BTreeSet<_>>().into_iter().enumerate().map(|(n, key)| (key, n)).collect();
        let before = classes[0].iter().chain(&classes[1]).collect::<BTreeSet<_>>().len();
        classes = [0, 1].map(|s| keys[s].iter().map(|key| numbering[key]).collect());
        if numbering.len() == before {
            return classes;
        }
    }
}

/// Whether one renaming of Idents, a bijection from the engine's Idents to
/// Souffle's numbers, maps the engine's rows of each relation of
/// `relations` one to one onto Souffle's. It refines the classes of Idents
/// of both sides, as [`refine`] gives, and, where a class holds more than
/// one Ident of a side, pairs one engine Ident of a smallest such class with
/// each Souffle Ident of that class in turn, and refines again.
pub(crate) fn renaming_exists(relations: &[(&BTreeSet<Vec<Leaf>>, Vec<Vec<EngineLeaf>>)]) -> bool {
    let engine = IdentRows::engine(relations);
    let Some(souffle) = IdentRows::souffle(relations) else { return false };
    if engine.idents != souffle.idents {
        return false;
    }
    let classes = [vec![0; engine.idents], vec![0; souffle.idents]];
    individualized(&engine, &souffle, classes)
}

/// Whether a renaming exists that keeps each Ident in its class of
/// `classes`, as [`renaming_exists`] gives.
fn individualized(engine: &IdentRows, souffle: &IdentRows, classes: [Vec<usize>; 2]) -> bool {
    let classes = refine([engine, souffle], classes);
    let mut members: BTreeMap<usize, [Vec<usize>; 2]> = BTreeMap::new();
    for (s, side) in classes.iter().enumerate() {
        for (ident, &class) in side.iter().enumerate() {
            members.entry(class).or_default()[s].push(ident);
        }
    }
    if members.values().any(|[ours, theirs]| ours.len() != theirs.len()) {
        return false;
    }
    let Some((_, [ours, theirs])) = members.iter().filter(|(_, [ours, _])| ours.len() > 1).min_by_key(|(class, [ours, _])| (ours.len(), **class)) else {
        return engine.by_classes(&classes[0]) == souffle.by_classes(&classes[1]);
    };
    let fresh = classes[0].iter().chain(&classes[1]).max().map_or(0, |&max| max + 1);
    theirs.iter().any(|&other| {
        let mut split = classes.clone();
        split[0][ours[0]] = fresh;
        split[1][other] = fresh;
        individualized(engine, souffle, split)
    })
}

/// The engine's rows of the relation that `name` declares on `example`,
/// each row the leaves Souffle's rerun writes for it, an orientation
/// constant by the number `constants` gives its name; `None` where the
/// program derives no relation of that name.
fn engine_rows(evaluation: &Evaluation<'_>, name: &str, example: Example, constants: &BTreeMap<String, i64>) -> Option<Result<Vec<Vec<EngineLeaf>>, String>> {
    let program = evaluation.program;
    let declared = ProgramRelation::Declared(RelationName(DeclaredName::Written(name.into())));
    let relation = relation_of(program, &declared)?;
    let on = (program.program.side(relation.node) == Side::PerInput).then_some(example);
    let rows = match evaluation.relation(&relation, on) {
        Ok(RelationValue::Rows(rows)) => rows,
        Ok(other) => return Some(Err(format!("{other:?}"))),
        Err(fault) => return Some(Err(fault.message.to_string())),
    };
    let Some(types) = program.types.columns(&relation) else { return Some(Err("rows whose columns have no types".to_owned())) };
    let mut written = Vec::new();
    let mut faults = BTreeSet::new();
    each_row(&rows, &mut |row| match row.iter().zip(types).map(|(&id, ty)| term_leaves(Term::decode(id, ty), evaluation.registry, constants)).collect::<Result<Vec<_>, _>>() {
        Ok(leaves) => written.push(leaves.concat()),
        Err(text) => {
            faults.insert(text);
        }
    });
    Some(faults.into_iter().next().map_or(Ok(written), Err))
}

/// The leaves Souffle's rerun writes for `term`: a number, a color's
/// digit, an example's index and a Box's margins as numbers, an
/// orientation constant as its number in `constants`, an Ident as itself,
/// and Unit as no leaf. Where the converter left a leaf of a Souffle
/// relation out of its arclog relation, the two sides' rows hold
/// different counts of leaves, and [`first_difference`] does not compare
/// them.
fn term_leaves(term: Term, registry: &Registry, constants: &BTreeMap<String, i64>) -> Result<Vec<EngineLeaf>, String> {
    let number = |n: i64| EngineLeaf::Written(Leaf::Number(n));
    Ok(match term {
        Term::Number(n) => vec![number(n.0.into())],
        Term::Box(m) => [m.top, m.bottom, m.left, m.right].into_iter().map(|n| number(n.into())).collect(),
        Term::Ident(ident) => vec![EngineLeaf::Ident(ident)],
        Term::Constant(Constant::Color(color)) => vec![number(color.digit().into())],
        Term::Constant(Constant::Example(example)) => vec![number(example.index().into())],
        Term::Constant(Constant::Unit) => vec![],
        Term::Constant(Constant::Orientation(constant)) => {
            let name = registry.constant_name(constant);
            vec![number(*constants.get(name).ok_or_else(|| format!("the orientation constant {name}, which the rerun gives no number"))?)]
        }
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    use arclog::terms::{Content, InternTable, WrittenIdent};

    fn n(value: i64) -> Leaf {
        Leaf::Number(value)
    }

    fn rerun(relations: &[(&str, &[&[i64]])]) -> Rerun {
        Rerun {
            relations: relations
                .iter()
                .map(|(name, rows)| (name.to_string(), rows.iter().map(|row| row.iter().map(|&v| n(v)).collect()).collect()))
                .collect(),
            orientation_constants: BTreeMap::new(),
        }
    }

    type Relations<'r> = [(&'r str, Vec<Vec<EngineLeaf>>)];

    fn on<'r>(pair: &'r str, rerun: &'r Rerun, relations: &'r Relations<'r>) -> PairRows<'r> {
        PairRows { pair, rerun, engine: Box::new(move |name| relations.iter().find(|(n, _)| *n == name).map(|(_, rows)| Ok(rows.clone()))) }
    }

    fn written(row: &[i64]) -> Vec<EngineLeaf> {
        row.iter().map(|&v| EngineLeaf::Written(n(v))).collect()
    }

    fn idents(count: u32) -> Vec<Ident> {
        let mut table = InternTable::default();
        (0..count).map(|i| table.intern(Content::FromFile { ty: arclog::types::ValueType::Ident, written: WrittenIdent::new(i) })).collect()
    }

    #[test]
    fn names_the_relation_whose_rows_differ_at_an_equal_count() {
        let souffle = rerun(&[("souffle:lib", &[&[0]]), ("&a", &[&[1, 2]]), ("&b", &[&[3], &[4]]), ("&c", &[&[9]])]);
        let ours = [("&a", vec![written(&[1, 2])]), ("&b", vec![written(&[3]), written(&[5])]), ("&c", vec![written(&[0])])];
        let found = first_difference(&[on("train 0", &souffle, &ours)]).difference.expect("a difference");
        assert!(found.contains("is &b on train 0:"), "{found}");
    }

    #[test]
    fn compares_idents_up_to_one_renaming_over_the_pairs() {
        let [x, y] = idents(2)[..] else { unreachable!() };
        let id = |ident, color: i64| vec![EngineLeaf::Ident(ident), EngineLeaf::Written(n(color))];
        let first = rerun(&[("&color", &[&[7, 1], &[8, 2]]), ("&big", &[&[7]])]);
        let second = rerun(&[("&big", &[&[7]])]);
        let agreeing = [("&color", vec![id(x, 1), id(y, 2)]), ("&big", vec![vec![EngineLeaf::Ident(x)]])];
        let agreeing_second = [("&big", vec![vec![EngineLeaf::Ident(x)]])];
        let pairs = [on("train 0", &first, &agreeing), on("train 1", &second, &agreeing_second)];
        assert_eq!(first_difference(&pairs).difference, None);
        let crossed_second = [("&big", vec![vec![EngineLeaf::Ident(y)]])];
        let pairs = [on("train 0", &first, &agreeing), on("train 1", &second, &crossed_second)];
        let found = first_difference(&pairs).difference.expect("a difference");
        assert!(found.contains("is &big on train 1:"), "{found}");
        assert_eq!(first_difference(&pairs[1..]).difference, None);
    }

    #[test]
    fn names_a_relation_that_no_renaming_fits_after_many_alike_rows() {
        let ours = idents(12);
        let souffle_rows: Vec<Vec<i64>> = (0..12).map(|i| vec![100 + i, 1]).collect();
        let souffle_rows: Vec<&[i64]> = souffle_rows.iter().map(Vec::as_slice).collect();
        let souffle = rerun(&[("&alike", &souffle_rows), ("&pairs", &[&[100, 101], &[102, 103], &[104, 105]])]);
        let alike: Vec<Vec<EngineLeaf>> = ours.iter().map(|&i| vec![EngineLeaf::Ident(i), EngineLeaf::Written(n(1))]).collect();
        let fits = vec![
            vec![EngineLeaf::Ident(ours[3]), EngineLeaf::Ident(ours[7])],
            vec![EngineLeaf::Ident(ours[0]), EngineLeaf::Ident(ours[11])],
            vec![EngineLeaf::Ident(ours[5]), EngineLeaf::Ident(ours[2])],
        ];
        let relations = [("&alike", alike.clone()), ("&pairs", fits)];
        assert_eq!(first_difference(&[on("train 0", &souffle, &relations)]).difference, None);
        let chain = vec![
            vec![EngineLeaf::Ident(ours[3]), EngineLeaf::Ident(ours[7])],
            vec![EngineLeaf::Ident(ours[7]), EngineLeaf::Ident(ours[11])],
            vec![EngineLeaf::Ident(ours[5]), EngineLeaf::Ident(ours[2])],
        ];
        let relations = [("&alike", alike), ("&pairs", chain)];
        let found = first_difference(&[on("train 0", &souffle, &relations)]).difference.expect("a difference");
        assert!(found.contains("is &pairs on train 0:"), "{found}");
    }

    #[test]
    fn leaves_out_a_relation_whose_rows_hold_other_counts_of_leaves() {
        let souffle = rerun(&[("&out", &[&[1, 2, 9]]), ("&b", &[&[3]])]);
        let ours = [("&out", vec![written(&[1, 2])]), ("&b", vec![written(&[4])])];
        let comparison = first_difference(&[on("train 0", &souffle, &ours)]);
        assert_eq!(comparison.not_compared.len(), 1, "{comparison:?}");
        assert!(comparison.not_compared[0].contains("&out on train 0 is not compared"), "{comparison:?}");
        assert!(comparison.difference.expect("a difference").contains("is &b on train 0:"));
    }
}
