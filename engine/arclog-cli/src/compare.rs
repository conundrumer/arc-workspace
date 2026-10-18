//! `compare`: runs the concept case of each solver given, or of every
//! solver of the corpus, at its stored `param` records, and compares each
//! pair's output with the snapshot of the Souffle outcomes, and the run's
//! time per solver with Souffle's time there. It prints each mismatch by
//! solver, case and pair, with the first relation whose count of rows
//! differs from Souffle's rerun of that pair, and each solver that runs
//! slower.
//!
//! Its arguments: the snapshot's directory, the corpus directory, the
//! directory of the task files, then the task ids of the solvers to run,
//! and `--reads <name>` for the solvers that the snapshot's `uses.json`
//! gives for a lib name or a form keyword; every solver of the corpus where
//! it is given none. The rerun is `scripts/souffle_parity.py rerun`, so the
//! command runs from the root of the tree.

use std::collections::BTreeSet;
use std::path::{Path, PathBuf};
use std::process::ExitCode;
use std::time::Instant;

use arclog::check::{check_program, CheckCache, CheckedProgram, SolverClauses};
use arclog::eval::instance::Constructions;
use arclog::eval::{relation_of, Caps, Cancellation, Evaluation, GridValue, Limits, ParameterValues, RelationValue};
use arclog::harness::{read_corpus_solver, run_over_corpus, CorpusSolver, SolverResult};
use arclog::program::{DeclaredName, ProgramRelation, RelationName};
use arclog::registry::Registry;
use arclog::resolver::{resolve, Side};
use arclog::session::{SessionBound, TaskSession};
use arclog::solver::CaseName;
use arclog::task::{read_task, Grid, Task};
use arclog::terms::{Color, Example};
use serde_json::Value;

const USAGE: &str = "usage: arclog-cli compare <snapshot-dir> <corpus-dir> <tasks-dir> [<task_id> ...] [--reads <name> ...]";

/// The bound on the bytes of the task session of each solver's run.
const SESSION_BYTES: usize = 1 << 32;

/// The subcommand on `args`, the arguments after its name.
pub fn run(args: &[String]) -> ExitCode {
    let Some(arguments) = Arguments::parse(args) else {
        eprintln!("{USAGE}");
        return ExitCode::from(2);
    };
    let selected = match arguments.selected() {
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

    /// The task ids of the solvers to run, `None` for every solver.
    fn selected(&self) -> Result<Option<BTreeSet<String>>, String> {
        if self.task_ids.is_empty() && self.reads.is_empty() {
            return Ok(None);
        }
        let mut ids: BTreeSet<String> = self.task_ids.iter().cloned().collect();
        if !self.reads.is_empty() {
            let uses = read_json(&self.snapshot.join("uses.json"))?;
            for name in &self.reads {
                let stems = uses.get(name).and_then(Value::as_array).ok_or_else(|| format!("`uses.json` gives no solver for `{name}`"))?;
                ids.extend(stems.iter().filter_map(Value::as_str).map(str::to_owned));
            }
        }
        Ok(Some(ids))
    }
}

/// The JSON of the file at `path`.
fn read_json(path: &Path) -> Result<Value, String> {
    let text = std::fs::read_to_string(path).map_err(|error| format!("{} does not read: {error}", path.display()))?;
    serde_json::from_str(&text).map_err(|error| format!("{} is no JSON: {error}", path.display()))
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
    let solver = read_corpus_solver(&arguments.corpus, id).ok_or("the solver's files do not read")?;
    let task = read_task(&arguments.tasks.join(format!("{id}.json"))).map_err(|error| format!("the task does not read: {error:?}"))?;
    let registry = Registry::get();
    let case = solver.concept_case();
    let (key, case_record) = case_record(&record, &case.name).ok_or("the snapshot has no record of the concept case")?;
    let resolved = resolve(&case.program, None, &solver.derived_relations(), registry).value;
    let clauses = SolverClauses::of(&solver, registry);
    let program = check_program(resolved, &clauses, registry, &mut CheckCache::default()).map_err(|refusals| {
        let messages: Vec<&str> = refusals.iter().map(|d| &*d.message).collect();
        format!("the checker refuses the concept case: {}", messages.join("; "))
    })?;
    let parameters = ParameterValues::stored(solver.arcdata.value());
    let session = TaskSession::new(SessionBound { bytes: SESSION_BYTES });
    let constructions = Constructions::new(Vec::new(), registry).map_err(|fault| format!("no table of constructions: {fault:?}"))?;
    let limits = Limits { caps: Caps::PROVISIONAL, deadline: None, cancellation: Cancellation::default() };
    let evaluation = Evaluation { program: &program, task: &task, parameters: &parameters, session: &session, registry, constructions: &constructions, limits: &limits };
    let start = Instant::now();
    let outputs = evaluation.outputs().map_err(|fault| format!("{key}: a fault of the run at {:?}: {}", fault.form, fault.message))?;
    let seconds = start.elapsed().as_secs_f64();
    let mut lines = Vec::new();
    for (index, example) in task.examples().enumerate() {
        let pair = pair_name(&task, index);
        let got = outputs.as_ref().map(|grids| &grids[index].1);
        let expected = case_record.get("pairs").and_then(|pairs| pairs.get(&pair));
        if agrees(got, expected) {
            continue;
        }
        let mut line = format!("{key}, {pair}: the engine gives {}, Souffle {}", describe(got), expected.map_or("no outcome".to_owned(), Value::to_string));
        if let Some(difference) = first_difference(id, key, &pair, &evaluation, &program, example) {
            line.push_str(&format!("; {difference}"));
        }
        lines.push(line);
    }
    if let Some(souffle) = record.get("cpu_seconds").and_then(Value::as_f64) {
        if seconds > souffle {
            lines.push(format!("the engine runs {seconds:.3} s against Souffle's {souffle:.3} s"));
        }
    }
    Ok(lines)
}

/// Whether the engine's grid value agrees with Souffle's outcome: one
/// grid, the same, or both `undefined`.
fn agrees(got: Option<&GridValue>, expected: Option<&Value>) -> bool {
    match (got, expected) {
        (Some(GridValue::Grid(grid)), Some(expected)) => {
            expected.get("grids").and_then(Value::as_array).is_some_and(|grids| grids.len() == 1 && grid_json(grid) == grids[0])
        }
        (Some(GridValue::Undefined), Some(expected)) => expected.as_str() == Some("undefined"),
        _ => false,
    }
}

/// The grid as the snapshot writes it: a list of rows of digits.
fn grid_json(grid: &Grid) -> Value {
    let digit = |color: &Color| (0u8..=9).find(|&d| Color::from_digit(d) == Some(*color)).expect("a color has a digit");
    Value::from(grid.rows().iter().map(|row| Value::from(row.iter().map(|c| Value::from(digit(c))).collect::<Vec<_>>())).collect::<Vec<_>>())
}

/// What the engine gives on a pair, for a mismatch line.
fn describe(got: Option<&GridValue>) -> String {
    match got {
        None => "no grid columns of `&output`".to_owned(),
        Some(GridValue::Grid(grid)) => grid_json(grid).to_string(),
        Some(GridValue::Undefined) => "undefined".to_owned(),
        Some(GridValue::Stopped(stop)) => format!("a stop at {:?} at the form {:?}", stop.bound, stop.form),
    }
}

/// The first relation, in the order of Souffle's rerun of the case on the
/// pair, whose count of rows on `example` differs from the engine's, each
/// relation the engine names by the same arclog name; `None` where the
/// rerun fails or no count differs.
fn first_difference(id: &str, case: &str, pair: &str, evaluation: &Evaluation<'_>, program: &CheckedProgram, example: Example) -> Option<String> {
    let rerun = std::process::Command::new("uv")
        .args(["run", "python", "scripts/souffle_parity.py", "rerun", id, case, pair])
        .output()
        .ok()?;
    if !rerun.status.success() {
        return None;
    }
    let text = String::from_utf8_lossy(&rerun.stdout);
    for line in text.lines().filter(|line| !line.starts_with(' ')) {
        let (name, count) = line.rsplit_once(' ')?;
        let Ok(souffle) = count.parse::<u64>() else { continue };
        let declared = ProgramRelation::Declared(RelationName(DeclaredName::Written(name.into())));
        let Some(relation) = relation_of(program, &declared) else { continue };
        let on = (program.program.side(relation.node) == Side::PerInput).then_some(example);
        let engine = match evaluation.relation(&relation, on) {
            Ok(RelationValue::Rows(rows)) => rows.len().to_string(),
            Ok(other) => format!("{other:?}"),
            Err(fault) => fault.message.to_string(),
        };
        if engine != souffle.to_string() {
            return Some(format!("the first relation whose rows differ is {name}: {engine} rows against Souffle's {souffle}"));
        }
    }
    None
}

