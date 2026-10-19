//! `compare`: runs the concept case of each solver given, or of every
//! solver of the corpus, at its stored `param` records, by the judged run,
//! and compares each pair's set of grids, or `undefined`, with the
//! snapshot of the Souffle outcomes, in any order, the case's solves
//! outcome with the snapshot's, and the run's time per solver with
//! Souffle's time there. It prints each mismatch by solver, case and pair,
//! with the first relation whose rows differ from those of Souffle's reruns
//! of the pairs up to that pair where the case gives at most one grid on
//! the pair,
//! each solver that runs slower, and each solver whose concept case it does
//! not compare, with the reason, since the step that builds what that case
//! reads checks it (`docs/engine/cases.md#every-case`).
//!
//! Its arguments: the snapshot's directory, the corpus directory, the
//! directory of the task files, then the task ids of the solvers to run,
//! and `--reads <name>` for the solvers that the snapshot's `uses.json`
//! gives for a lib name or a form keyword; every solver of the corpus where
//! it is given none. The rerun is `scripts/souffle_parity.py rerun --json`,
//! so the command runs from the root of the tree.

use std::collections::{BTreeMap, BTreeSet};
use std::ops::ControlFlow;
use std::process::ExitCode;
use std::sync::Mutex;

use arclog::eval::join::each_row;
use arclog::eval::models::ModelsEnd;
use arclog::eval::{relation_of, Evaluation, RelationValue};
use arclog::harness::{require_optimized_build, run_over_corpus, CorpusSolver, SolverResult};
use arclog::judge::run::{Found, JudgedRun};
use arclog::judge::solves::OutputSet;
use arclog::program::path::{node_at, NodePath, NodeRef};
use arclog::program::{ClauseKeyword, DeclaredName, Form, ProgramRelation, RelationName};
use arclog::registry::Registry;
use arclog::relations::Relation;
use arclog::resolver::Side;
use arclog::solver::FileOwner;
use arclog::task::{Grid, Task};
use arclog::terms::{Constant, Example, Term};
use arclog::types::ValueType;
use serde_json::Value;

use crate::arguments::Arguments;
use crate::concept_case::{with_concept_case, ConceptCase};
use crate::renaming::{renaming_exists, EngineLeaf, Leaf};
use crate::select::{read_json, selected};

const USAGE: &str = "usage: arclog-cli compare <snapshot-dir> <corpus-dir> <tasks-dir> [<task_id> ...] [--reads <name> ...]";

/// The subcommand on `args`, the arguments after its name.
pub fn run(args: &[String]) -> ExitCode {
    if let Err(code) = require_optimized_build() {
        return code;
    }
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
    let not_compared: Mutex<BTreeMap<String, &'static str>> = Mutex::default();
    let report = run_over_corpus(&arguments.corpus, |solver| match &selected {
        Some(ids) if !ids.contains(&solver.task_id) => SolverResult::Pass,
        _ => compare_solver(&arguments, solver, &not_compared),
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
    let not_compared = not_compared.into_inner().expect("a map that no panic poisoned");
    for (id, reason) in &not_compared {
        println!("{id}: {CONCEPT}: not compared: {reason}");
    }
    let compared = selected.map_or(report.checked, |ids| ids.len());
    println!("{} of {compared} solvers differ from the snapshot, and {} are not compared", report.failures.len(), not_compared.len());
    if report.failures.is_empty() { ExitCode::SUCCESS } else { ExitCode::FAILURE }
}

/// The snapshot's key of the concept case, whatever alts and line
/// readings its name picks (`src/parity/snapshot.py`).
const CONCEPT: &str = "concept";

/// The pair names of the task's examples, as the snapshot writes them.
fn pair_name(task: &Task, example: usize) -> String {
    if example < task.train.len() { format!("train {example}") } else { format!("test {}", example - task.train.len()) }
}

/// The comparison of the concept case of `solver` with its snapshot
/// record. A concept case that it does not compare goes into
/// `not_compared` with the reason, and passes.
fn compare_solver(arguments: &Arguments, solver: &CorpusSolver, not_compared: &Mutex<BTreeMap<String, &'static str>>) -> SolverResult {
    match compared(arguments, solver, not_compared) {
        Ok(lines) if lines.is_empty() => SolverResult::Pass,
        Ok(lines) => SolverResult::Fail(lines),
        Err(line) => SolverResult::Fail(vec![line]),
    }
}

/// Each line of the comparison of the concept case of `solver`, or the one
/// line of the fault that stops it.
fn compared(arguments: &Arguments, corpus: &CorpusSolver, not_compared: &Mutex<BTreeMap<String, &'static str>>) -> Result<Vec<String>, String> {
    let id = &corpus.task_id;
    let record = read_json(&arguments.snapshot.join(format!("{id}.json")))?;
    with_concept_case(&arguments.corpus, &arguments.tasks, id, |case| {
        let key = CONCEPT;
        if let Some(reason) = unjudged(case) {
            not_compared.lock().expect("a map that no panic poisoned").insert(id.clone(), reason);
            return Ok(Vec::new());
        }
        let case_record = record.get("cases").and_then(|cases| cases.get(key)).ok_or("the snapshot has no record of the concept case")?;
        let (run, seconds) = case.run();
        let run = run.map_err(|fault| format!("{key}: a fault of the run at {:?}: {}", fault.form, fault.message))?;
        let task = case.evaluation.task;
        let mut lines = Vec::new();
        let fits = case_record.get("fit").and_then(Value::as_str) == Some("fits");
        if run.solves_task() != fits {
            let engine = if run.solves_task() { "solves" } else { "does not solve" };
            lines.push(format!("{key}: the case {engine} the task in the engine, and Souffle's fit is {}", case_record.get("fit").map_or("absent".to_owned(), Value::to_string)));
        }
        let examples: Vec<(String, Example)> = task.examples().enumerate().map(|(index, example)| (pair_name(task, index), example)).collect();
        let mut reruns: Vec<Option<Rerun>> = Vec::new();
        for (index, (pair, _)) in examples.iter().enumerate() {
            let got = &run.pairs[index].set;
            let expected = case_record.get("pairs").and_then(|pairs| pairs.get(pair));
            if agrees(got, expected) {
                continue;
            }
            let mut line = format!("{key}, {pair}: the engine gives {}, Souffle {}", describe(&run, got), expected.map_or("no outcome".to_owned(), Value::to_string));
            if matches!(got, OutputSet::Grids(grids) if grids.len() > 1) {
                lines.push(line);
                continue;
            }
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
                    let engine: Box<dyn Fn(&str) -> Option<EngineRows> + '_> =
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
        lines.extend(crate::speed::slower(seconds, &record).ok().flatten());
        Ok(lines)
    })
}

/// Whether the engine's output set agrees with Souffle's outcome: the same
/// set of grids, in any order, or both `undefined`.
fn agrees(got: &OutputSet, expected: Option<&Value>) -> bool {
    match (got, expected) {
        (OutputSet::Grids(grids), Some(expected)) => expected.get("grids").and_then(Value::as_array).is_some_and(|expected| {
            let ours: Vec<Value> = grids.iter().map(grid_json).collect();
            ours.len() == expected.len() && ours.iter().all(|grid| expected.contains(grid))
        }),
        (OutputSet::Undefined, Some(expected)) => expected.as_str() == Some("undefined"),
        _ => false,
    }
}

/// Why the concept case of `case` is not compared, or `None` where it is:
/// it holds a `DEMONSTRATED` form, or it reads a `DET_OR_RULE` or
/// `RULE_OR_DET` line with `(ONE)` on the derived reading, an open
/// parameter there.
fn unjudged(case: &ConceptCase<'_>) -> Option<&'static str> {
    let forms = case.case.program.value().forms.iter().zip(0u32..);
    forms.into_iter().find_map(|(form, index)| match form {
        Form::Demonstrated(_) => Some("the case holds a `DEMONSTRATED` form"),
        Form::Clause(clause)
            if clause.value().keyword == ClauseKeyword::Rule
                && clause.value().ones.iter().any(|mark| mark.key.is_empty())
                && is_line(case, &NodePath::top(index)) =>
        {
            Some("the case reads a `DET_OR_RULE` or `RULE_OR_DET` line with `(ONE)` on the derived reading")
        }
        _ => None,
    })
}

/// Whether the form at `path` of the case program of `case` stands in its
/// file as a `DET_OR_RULE` or `RULE_OR_DET` line.
fn is_line(case: &ConceptCase<'_>, path: &NodePath) -> bool {
    let (owner, at) = case.case.file_path(path);
    let file = match owner {
        FileOwner::Solver => case.solver,
        FileOwner::Representative => case.solver.representative.as_deref().expect("a representative's file"),
    };
    matches!(
        node_at(NodeRef::Program(file.program.value()), &at),
        Some(NodeRef::Clause(line)) if matches!(line.keyword, ClauseKeyword::DetOrRule | ClauseKeyword::RuleOrDet)
    )
}

/// The grid as the snapshot writes it: a list of rows of digits.
fn grid_json(grid: &Grid) -> Value {
    Value::from(grid.rows().iter().map(|row| Value::from(row.iter().map(|&c| Value::from(c.digit())).collect::<Vec<_>>())).collect::<Vec<_>>())
}

/// What the engine gives on a pair, `got` of `run`, for a mismatch line.
fn describe(run: &JudgedRun, got: &OutputSet) -> String {
    let stop = |stop: &arclog::eval::Stop| format!("a stop at {:?} at the form {:?}", stop.bound, stop.form);
    match (&run.columns, got) {
        (Found::None, _) => "no grid columns of `&output`, so `undefined`".to_owned(),
        (Found::Stopped(at), _) => format!("no grid columns of `&output`, by {}", stop(at)),
        (_, OutputSet::Grids(grids)) => Value::from(grids.iter().map(grid_json).collect::<Vec<_>>()).to_string(),
        (_, OutputSet::Undefined) => "undefined".to_owned(),
        (_, OutputSet::Outside) => "outside".to_owned(),
        (_, OutputSet::Stopped(at)) => stop(at),
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
    engine: Box<dyn Fn(&str) -> Option<EngineRows> + 'a>,
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
/// counts. A relation whose rows differ between the case's models is not
/// compared either, and the comparison gives it with that reason.
fn first_difference(pairs: &[PairRows<'_>]) -> Comparison {
    let mut comparison = Comparison::default();
    let mut compared: Vec<(&BTreeSet<Vec<Leaf>>, Vec<Vec<EngineLeaf>>)> = Vec::new();
    for PairRows { pair, rerun, engine } in pairs {
        for (name, souffle) in &rerun.relations {
            let Some(rows) = engine(name) else { continue };
            let differs = |what: String| Some(format!("the first relation whose rows differ is {name} on {pair}: {what}"));
            let rows = match rows {
                EngineRows::Rows(rows) => rows,
                EngineRows::DifferBetweenModels => {
                    comparison.not_compared.push(format!("{name} on {pair} is not compared: its rows differ between the case's models"));
                    continue;
                }
                EngineRows::Fault(text) => {
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

/// What the engine gives for a relation on a pair.
enum EngineRows {
    /// The relation's rows, each the leaves Souffle's rerun writes for it,
    /// the same at every model of the case.
    Rows(Vec<Vec<EngineLeaf>>),
    /// Two models of the case give the relation different rows, so Souffle's
    /// one set of rows has nothing to compare with.
    DifferBetweenModels,
    /// A text for rows the engine cannot give.
    Fault(String),
}

/// The engine's rows of the relation that `name` declares on `example`,
/// each row the leaves Souffle's rerun writes for it, an orientation
/// constant by the number `constants` gives its name; `None` where the
/// program derives no relation of that name. The rows are read at each
/// model of the case: where two models give different rows as sets, the
/// result is [`EngineRows::DifferBetweenModels`].
fn engine_rows(evaluation: &Evaluation<'_>, name: &str, example: Example, constants: &BTreeMap<String, i64>) -> Option<EngineRows> {
    let program = evaluation.program;
    let declared = ProgramRelation::Declared(RelationName(DeclaredName::Written(name.into())));
    let relation = relation_of(program, &declared)?;
    let on = (program.program.side(relation.node) == Side::PerInput).then_some(example);
    let Some(types) = program.types.columns(&relation) else { return Some(EngineRows::Fault("rows whose columns have no types".to_owned())) };
    let mut first: Option<Vec<Vec<EngineLeaf>>> = None;
    let mut fault = None;
    let mut differ = false;
    let end = evaluation.models(&relation, on, &mut |value| {
        let RelationValue::Rows(rows) = value else {
            fault = Some(format!("{value:?}"));
            return ControlFlow::Break(());
        };
        let rows = match model_leaves(evaluation, rows, types, constants) {
            Ok(rows) => rows,
            Err(text) => {
                fault = Some(text);
                return ControlFlow::Break(());
            }
        };
        match &first {
            None => first = Some(rows),
            Some(kept) if same_rows(kept, &rows) => {}
            Some(_) => {
                differ = true;
                return ControlFlow::Break(());
            }
        }
        ControlFlow::Continue(())
    });
    match end {
        Err(error) => return Some(EngineRows::Fault(error.message.to_string())),
        Ok(ModelsEnd::Stopped(stop)) if !differ && fault.is_none() => return Some(EngineRows::Fault(format!("{stop:?}"))),
        Ok(_) => {}
    }
    Some(match (fault, differ, first) {
        (Some(text), _, _) => EngineRows::Fault(text),
        (None, true, _) => EngineRows::DifferBetweenModels,
        (None, false, Some(rows)) => EngineRows::Rows(rows),
        (None, false, None) => EngineRows::Rows(Vec::new()),
    })
}

/// The leaves of the rows of one model's value of a relation of column
/// types `types`.
fn model_leaves(
    evaluation: &Evaluation<'_>,
    rows: &Relation,
    types: &[ValueType],
    constants: &BTreeMap<String, i64>,
) -> Result<Vec<Vec<EngineLeaf>>, String> {
    let mut written = Vec::new();
    let mut faults = BTreeSet::new();
    each_row(rows, &mut |row| match row.iter().zip(types).map(|(&id, ty)| term_leaves(Term::decode(id, ty), evaluation.registry, constants)).collect::<Result<Vec<_>, _>>() {
        Ok(leaves) => written.push(leaves.concat()),
        Err(text) => {
            faults.insert(text);
        }
    });
    faults.into_iter().next().map_or(Ok(written), Err)
}

/// Whether `a` and `b` hold the same rows, each row once.
fn same_rows(a: &[Vec<EngineLeaf>], b: &[Vec<EngineLeaf>]) -> bool {
    a.iter().all(|row| b.contains(row)) && b.iter().all(|row| a.contains(row))
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
    use arclog::terms::{Content, Ident, InternTable, WrittenIdent};

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
        PairRows { pair, rerun, engine: Box::new(move |name| relations.iter().find(|(n, _)| *n == name).map(|(_, rows)| EngineRows::Rows(rows.clone()))) }
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

    #[test]
    fn leaves_out_a_relation_whose_rows_differ_between_models() {
        let souffle = rerun(&[("&out", &[&[1]]), ("&b", &[&[3]])]);
        let pair = PairRows {
            pair: "train 0",
            rerun: &souffle,
            engine: Box::new(|name| match name {
                "&out" => Some(EngineRows::DifferBetweenModels),
                _ => Some(EngineRows::Rows(vec![written(&[4])])),
            }),
        };
        let comparison = first_difference(&[pair]);
        assert_eq!(comparison.not_compared.len(), 1, "{comparison:?}");
        assert!(comparison.not_compared[0].contains("&out on train 0 is not compared: its rows differ between the case's models"), "{comparison:?}");
        assert!(comparison.difference.expect("a difference").contains("is &b on train 0:"));
    }
}
