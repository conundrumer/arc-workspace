//! `compare`: runs every case of each solver given, or of every solver of
//! the corpus, less the cases its `exclude` forms leave out, by the judged
//! run, at the values that the determination gives the case, and compares
//! each case's set of grids on each pair, or `undefined`, with the snapshot's
//! record of the case, in any order, the case's solves outcome with the
//! record's, and the run's time per solver, over the determination and every
//! case, with Souffle's time there. It also runs each case on each witness
//! input of the arcdata file, at the `param` records and the witness's `assign`
//! forms, and compares its set of grids, or `undefined`, with the record's on
//! that witness. The snapshot keys a case by its alts, as `case_name` of
//! `src/parity/__init__.py` gives them.
//!
//! It prints, for each solver, first each difference of a determined value
//! from the solver's `param` records and each fault that keeps a case from
//! its determination, then each mismatch by case and pair, naming each
//! parameter with such a difference that the case reads, with the first
//! relation whose rows differ from those of Souffle's reruns of the pairs up
//! to that pair where the case gives at most one grid on the pair, each
//! mismatch by case and witness, each case that only the engine or only the
//! snapshot holds, and each solver that runs slower.
//!
//! Its arguments: the snapshot's directory, the corpus directory, the
//! directory of the task files, then the task ids of the solvers to run,
//! and `--reads <name>` for the solvers that the snapshot's `uses.json`
//! gives for a lib name or a form keyword; every solver of the corpus where
//! it is given none. The rerun is `scripts/souffle_parity.py rerun --json`,
//! so the command runs from the root of the tree.

use std::collections::BTreeSet;
use std::time::Instant;
use std::process::ExitCode;

use arclog::eval::determinations::{det_node, relation_spelled};
use arclog::decode::corpus::corpus_session;
use arclog::eval::{output_relation, Evaluation, ParameterValues};
use arclog::judge::determination::DeterminedCase;
use arclog::harness::{print_ended, require_optimized_build, run_over_corpus, CorpusSolver, SolverResult};
use arclog::judge::candidates::World;
use arclog::judge::run::{full_output_set, judged_run, Depth, JudgedRun};
use arclog::judge::solves::OutputSet;
use arclog::program::{AltRecord, AltsName, Arcdata, DataValue, ParamValue, ProgramRelation, Witness, WitnessRecord};
use arclog::session::TaskSession;
use arclog::task::{Grid, Task};
use arclog::terms::{Color, Example};
use serde_json::Value;

use crate::arguments::Arguments;
use arclog::stream::corpus::case_spelled;
use crate::determine::{solver_determination, Finding};
use crate::renaming::same_without_idents;
use crate::select::{read_json, selected};
use crate::souffle_rows::{engine_rows, pair_name, EngineRows, Projection, Rerun};

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
    let report = run_over_corpus(&arguments.corpus, selected.as_ref(), |solver| compare_solver(&arguments, solver), print_ended);
    let report = match report {
        Ok(report) => report,
        Err(error) => {
            eprintln!("the corpus does not read: {error:?}");
            return ExitCode::from(2);
        }
    };
    let compared = selected.map_or(report.checked, |ids| ids.len());
    println!("{} of {compared} solvers differ from the snapshot", report.failures.len());
    if report.failures.is_empty() { ExitCode::SUCCESS } else { ExitCode::FAILURE }
}

/// The comparison of the cases of `solver` with its snapshot record.
fn compare_solver(arguments: &Arguments, solver: &CorpusSolver) -> SolverResult {
    match compared(arguments, solver) {
        Ok(lines) if lines.is_empty() => SolverResult::Pass,
        Ok(lines) => SolverResult::Fail(lines),
        Err(line) => SolverResult::Fail(vec![line]),
    }
}

/// The snapshot's key of the reading `<relation>=$Derived` of a line with
/// one proposer names the proposer, which the case's name does not.
const DERIVED: &str = "=$Derived";

/// Whether the snapshot's key `key` names the case whose departures from the
/// concept case are `departures` (`Solver::departures`; `case_name` of
/// `src/parity/__init__.py`): the key joins with ` & `, in the snapshot's
/// order, each departure, a line's stored reading
/// `<relation>=$Stored` as `<relation>=stored` and its derived reading by
/// its one proposer as `<relation>=<proposer>`, and is `concept` where
/// there is none.
pub(crate) fn names_case(key: &str, departures: &[AltsName]) -> bool {
    let mut parts: BTreeSet<&str> = if key == "concept" { BTreeSet::new() } else { key.split(" & ").collect() };
    for alt in departures {
        let found = if let Some(relation) = alt.0.strip_suffix(DERIVED) {
            parts.iter().find(|part| part.strip_prefix(relation).is_some_and(|rest| rest.starts_with('=') && rest != "=stored")).copied()
        } else {
            let stored = alt.0.replace("=$Stored", "=stored");
            parts.iter().find(|part| **part == stored).copied()
        };
        match found {
            Some(part) => {
                parts.remove(part);
            }
            None => return false,
        }
    }
    parts.is_empty()
}

/// The record of the case whose departures from the concept case are
/// `departures`, in a solver's snapshot record, with its key there
/// (`names_case`).
fn case_record<'r>(record: &'r Value, departures: &[AltsName]) -> Option<(&'r str, &'r Value)> {
    let cases = record.get("cases")?.as_object()?;
    cases.iter().find(|(key, _)| names_case(key, departures)).map(|(key, value)| (key.as_str(), value))
}

/// Each line of the comparison of the solver `corpus`: the findings of its
/// determination, then the comparison of each case, then the cases that
/// only one side holds, and the time; or the one line of the fault that
/// stops it.
fn compared(arguments: &Arguments, corpus: &CorpusSolver) -> Result<Vec<String>, String> {
    let id = &corpus.task_id;
    let record = read_json(&arguments.snapshot.join(format!("{id}.json")))?;
    let start = Instant::now();
    let setup = solver_determination(&arguments.corpus, &arguments.tasks, id)?;
    let mut lines: Vec<String> = setup.findings.iter().map(|finding| finding.line().to_owned()).collect();
    let differing: Vec<&str> = setup.findings.iter().filter_map(|finding| match finding {
        Finding::Difference { parameter, .. } => Some(parameter.as_str()),
        Finding::Fault(_) => None,
    }).collect();
    let mut keys: BTreeSet<&str> = BTreeSet::new();
    let witnesses = witness_inputs(setup.solver.arcdata.value());
    let first_witness = setup.task.train.len() + setup.task.test.len();
    let witness_task = Task {
        train: setup.task.train.clone(),
        test: setup.task.test.iter().cloned().chain(witnesses.iter().filter_map(|witness| witness.input.clone())).collect(),
    };
    let witness_session = corpus_session();
    let records: Vec<(ProgramRelation, ParamValue)> = setup.solver.arcdata.value().params.iter().map(|param| (param.value().name.clone(), param.value().value.clone())).collect();
    let stored = ParameterValues::stored(setup.solver.arcdata.value());
    for case in setup.cases() {
        let spelled = case_spelled(case.name);
        let Some((key, case_record)) = case_record(&record, &setup.solver.departures(case.name)) else {
            lines.push(format!("{spelled}: the engine has the case, and the snapshot has no record of it"));
            continue;
        };
        keys.insert(key);
        lines.extend(compare_witnesses(key, case, case_record, &witnesses, first_witness, &witness_task, &witness_session, &stored, &records));
        let values = match setup.determination.case_values(&case) {
            Ok(values) => values,
            Err(fault) => {
                // A case of the determination has its fault in the findings.
                if !setup.determination.cases.iter().any(|(name, ..)| name == case.name) {
                    lines.push(format!("{spelled}: not run: {fault}"));
                }
                continue;
            }
        };
        let evaluation = case.evaluation(&values);
        let output = output_relation(case.program).expect("a checked case program holds an `OUT` form");
        let run = judged_run(&evaluation, &output, &setup.judged, World::Closed, Depth::Full);
        let run = match run {
            Ok(run) => run,
            Err(fault) => {
                lines.push(format!("{key}: a fault of the run at {:?}: {}", fault.form, fault.message));
                continue;
            }
        };
        let named: Vec<String> = setup.determination.parameters.iter().map(|(relation, _)| relation).filter(|relation| det_node(case.program, relation).is_some()).map(relation_spelled).filter(|name| differing.contains(&name.as_str())).collect();
        let suffix = if named.is_empty() { String::new() } else { format!("; the case reads {}, whose determined value differs from its `param` record", named.join(", ")) };
        lines.extend(compare_case(id, key, case_record, &evaluation, &run).into_iter().map(|line| line + &suffix));
    }
    if let Some(cases) = record.get("cases").and_then(Value::as_object) {
        for key in cases.keys().filter(|key| !keys.contains(key.as_str())) {
            lines.push(format!("{key}: the snapshot has the case, and the engine has no case of that name"));
        }
    }
    lines.extend(crate::speed::slower(start.elapsed().as_secs_f64(), &record).ok().flatten());
    Ok(lines)
}

/// A witness of a solver: its id, its input where each cell holds a color, and
/// the values its `assign` forms give.
struct WitnessInput<'a> {
    id: &'a str,
    input: Option<Grid>,
    assigns: &'a [(ProgramRelation, ParamValue)],
}

/// Each witness of `arcdata` with a body, each id once.
fn witness_inputs(arcdata: &Arcdata) -> Vec<WitnessInput<'_>> {
    fn alt<'a>(record: &'a AltRecord, found: &mut Vec<&'a Witness>) {
        found.extend(record.witnesses.iter());
        for nested in record.nested.iter() {
            alt(nested, found);
        }
    }
    let mut found: Vec<&Witness> = Vec::new();
    for record in arcdata.witness_records.iter() {
        match record {
            WitnessRecord::Alts { alts, .. } => alts.iter().for_each(|record| alt(record, &mut found)),
            WitnessRecord::Approximated { witnesses, .. } => found.extend(witnesses.iter()),
        }
    }
    let mut seen: BTreeSet<&str> = BTreeSet::new();
    found
        .into_iter()
        .filter(|witness| witness.body.is_some() && seen.insert(&witness.id))
        .map(|witness| {
            let body = witness.body.as_ref().expect("a witness with a body");
            WitnessInput { id: &witness.id, input: grid_of(&body.input), assigns: &body.assigns }
        })
        .collect()
}

/// The task grid of an arcdata grid, where each cell holds a color.
fn grid_of(grid: &arclog::program::Grid) -> Option<Grid> {
    let cell = |value: &Option<DataValue>| match value {
        Some(DataValue::Integer(digit)) => u8::try_from(*digit).ok().and_then(Color::from_digit),
        _ => None,
    };
    let rows: Option<Vec<Box<[Color]>>> = grid.rows.iter().map(|row| row.iter().map(cell).collect::<Option<Vec<Color>>>().map(Vec::into_boxed_slice)).collect();
    Grid::from_rows(rows?.into_boxed_slice())
}

/// Each line of the comparison of `case` on `witnesses`, at the stored values
/// with each witness's `assign` forms, with its snapshot record `case_record`
/// under the key `key`. `task` holds the witness inputs after its other
/// examples, from the example at the index `first`.
#[allow(clippy::too_many_arguments)]
fn compare_witnesses(key: &str, case: DeterminedCase<'_>, case_record: &Value, witnesses: &[WitnessInput<'_>], first: usize, task: &Task, session: &TaskSession, stored: &ParameterValues, records: &[(ProgramRelation, ParamValue)]) -> Vec<String> {
    let case = DeterminedCase { task, session, ..case };
    // A witness runs at the records, as Souffle's does at its facts: a `DET` by
    // its clauses would read the witness input as evidence. A relation the case
    // derives is no `DET` of the case, and keeps its clauses.
    let held: Vec<(ProgramRelation, ParamValue)> = records.iter().filter(|(relation, _)| det_node(case.program, relation).is_some()).cloned().collect();
    let stored = stored.with_assigns(&held);
    let output = output_relation(case.program).expect("a checked case program holds an `OUT` form");
    let recorded = case_record.get("witnesses").and_then(Value::as_array);
    let mut lines = Vec::new();
    let mut at = first;
    for witness in witnesses {
        let Some(expected) = recorded.and_then(|all| all.iter().find(|entry| entry.get("id").and_then(Value::as_str) == Some(witness.id))).and_then(|entry| entry.get("outcome")) else {
            lines.push(format!("{key}, witness {}: the snapshot has no outcome", witness.id));
            at += usize::from(witness.input.is_some());
            continue;
        };
        if witness.input.is_none() {
            lines.push(format!("{key}, witness {}: not run: its input is no grid of colors", witness.id));
            continue;
        }
        let values = stored.with_assigns(witness.assigns);
        let evaluation = case.evaluation(&values);
        let example = Example::at(u16::try_from(at).expect("fewer than 2^16 examples in a task"));
        at += 1;
        match full_output_set(&evaluation, &output, example) {
            Ok(set) if agrees(&set, Some(expected)) => {}
            Ok(set) => lines.push(format!("{key}, witness {}: the engine gives {}, Souffle {expected}", witness.id, describe(&set))),
            Err(fault) => lines.push(format!("{key}, witness {}: a fault of the run at {:?}: {}", witness.id, fault.form, fault.message)),
        }
    }
    lines
}

/// Each line of the comparison of the judged run `run` of a case, in
/// `evaluation`, with its snapshot record `case_record` under the key
/// `key`, for the solver `id`.
fn compare_case(id: &str, key: &str, case_record: &Value, evaluation: &Evaluation<'_>, run: &JudgedRun) -> Vec<String> {
    let task = evaluation.task;
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
        let mut line = format!("{key}, {pair}: the engine gives {}, Souffle {}", describe(got), expected.map_or("no outcome".to_owned(), Value::to_string));
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
                let engine: Box<dyn Fn(&str) -> Option<EngineRows> + '_> = Box::new(move |name| engine_rows(evaluation, name, example, &rerun.orientation_constants, Projection::All));
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
    lines
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

/// The grid as the snapshot writes it: a list of rows of digits.
fn grid_json(grid: &Grid) -> Value {
    Value::from(grid.rows().iter().map(|row| Value::from(row.iter().map(|&c| Value::from(c.digit())).collect::<Vec<_>>())).collect::<Vec<_>>())
}

/// What the engine gives on a pair, `got`, for a mismatch line.
fn describe(got: &OutputSet) -> String {
    match got {
        OutputSet::Grids(grids) => Value::from(grids.iter().map(grid_json).collect::<Vec<_>>()).to_string(),
        OutputSet::Undefined => "undefined".to_owned(),
        OutputSet::Outside => "outside".to_owned(),
        OutputSet::Stopped(at) => format!("a stop at {:?} at the form {:?}", at.bound, at.form),
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
/// the rerun's order on each pair. The rows of a relation compare as sets
/// with each place that holds an Ident left blank, and no renaming of Idents
/// is looked for: a Souffle number denotes one object only within its
/// instance, its key and its pair, so a number is no name for an object
/// across relations or pairs. A relation whose engine rows and Souffle rows
/// hold different counts of leaves,
/// as where the converter left a Souffle column out of the arclog
/// relation, is not compared, and the comparison gives it with the two
/// counts. A relation whose rows differ between the case's models is not
/// compared either, and the comparison gives it with that reason.
fn first_difference(pairs: &[PairRows<'_>]) -> Comparison {
    let mut comparison = Comparison::default();
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
                EngineRows::Skip(reason) => {
                    comparison.not_compared.push(format!("{name} on {pair} is not compared: {reason}"));
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
        }
    }
    comparison
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::collections::BTreeMap;
    use crate::renaming::{EngineLeaf, Leaf};

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

    #[test]
    fn names_the_relation_whose_rows_differ_at_an_equal_count() {
        let souffle = rerun(&[("souffle:lib", &[&[0]]), ("&a", &[&[1, 2]]), ("&b", &[&[3], &[4]]), ("&c", &[&[9]])]);
        let ours = [("&a", vec![written(&[1, 2])]), ("&b", vec![written(&[3]), written(&[5])]), ("&c", vec![written(&[0])])];
        let found = first_difference(&[on("train 0", &souffle, &ours)]).difference.expect("a difference");
        assert!(found.contains("is &b on train 0:"), "{found}");
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

    #[test]
    fn names_a_case_by_the_snapshots_key() {
        use arclog::program::AltsName;
        let departures = |alts: &[&str]| -> Vec<AltsName> { alts.iter().map(|alt| AltsName((*alt).into())).collect() };
        let case = departures(&["&background=$Derived", "&floor_cell=$Stored", "$LargerOnTop"]);
        assert!(names_case("$LargerOnTop & &background=DominantColor & &floor_cell=stored", &case));
        assert!(!names_case("$LargerOnTop & &background=stored & &floor_cell=stored", &case));
        assert!(!names_case("$LargerOnTop & &background=DominantColor", &case));
        assert!(names_case("concept", &[]));
        assert!(!names_case("$LargerOnTop", &[]));
    }
}
