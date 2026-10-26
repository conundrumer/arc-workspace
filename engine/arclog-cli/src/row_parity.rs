//! `row-parity <corpus-dir> <tasks-dir> <rows-dir> <task_id> ...`: compares,
//! for each selected solver, each relation of the cases its rows file gives,
//! at their stored parameters, with Souffle's rows of it, from
//! `<rows-dir>/<task_id>.json` (`scripts/souffle_parity.py case-rows`).
//!
//! It prints a line `<task>\t<relation>\t<verdict>\t<detail>` for each task
//! and relation, in the rows file's order, ordered by task id: `equal`;
//! `differ`, with the first case and pair, both counts of rows and one row
//! that only one side holds; `fault`, with the engine's text; `skip`, with
//! the reason the file gives (`parity.rerun`), for a relation that holds no
//! row the solver derives; or `uncompared`, with the reason the file gives or
//! "no case's program has a relation of that name", for any other relation
//! the check does not compare. A relation that more than one case derives
//! has one line, the first `differ`, `fault` or `uncompared` of the cases
//! and pairs, else the first `equal`. A column of the file that the engine's
//! relation lacks is a `fault` of the relation, which names each such column.
//! A column that a pair's rows lack, and a leaf of the file that is
//! `unresolved`, an Ident with no one source, are left out of both sides, and
//! the line names each, an unresolved leaf with its reason. A `fault` is also
//! the line of a relation whose Souffle rows hold a minted id that the
//! minting relation's rows on the pair do not hold at the row's key, and of
//! one whose engine Ident at a minted leaf is a value read from a file. A
//! fault of a whole task, or of a case whose run gives no rows or whose setup
//! fails, has the relation `*`. It exits 1 where a line is `differ`, `fault`
//! or `uncompared`.
//!
//! An `equal` line proves: for each case that derives the relation, at the
//! stored parameters, on each train and test input of the task, the arclog
//! rows of the relation, projected onto the leaves the converter maps from
//! Souffle's columns, are Souffle's rows projected onto the same leaves, as a
//! set; where the map gives no column to compare, the relation is present in
//! both or absent in both. Where the relation's rows differ between the
//! case's models, and Souffle's relation holds the open value in a column,
//! the rows of the models are the rows of the open values, as sets of sets;
//! elsewhere the union of the models' rows is Souffle's rows, since Souffle's
//! run states every open value at once. An Ident that a lib relation mints is
//! compared by its members: each side writes it as the text of the set of
//! its members, and the texts are compared as written values. An Ident that a
//! fact of the solver writes is a number that denotes one object only within
//! its pair, so those are compared up to one renaming per pair, over all the
//! relations of the pair. It does not prove anything about a leaf that the
//! line names as left out, the cases that the file does not give, other
//! inputs (witness inputs among them), the relations that the file leaves out
//! as `skip` or `uncompared`, or the multiplicity of rows.

use std::collections::{BTreeMap, BTreeSet};
use std::path::Path;
use std::process::ExitCode;
use std::sync::Mutex;

use arclog::eval::Evaluation;
use arclog::harness::{require_optimized_build, run_over_corpus, SolverResult};
use arclog::terms::Example;
use serde_json::Value;

use crate::concept_case::{with_case, ConceptCase};
use crate::renaming::{renaming_exists, same_without_idents, EngineLeaf, Leaf};
use crate::select::read_json;
use crate::souffle_rows::{engine_columns, engine_models, pair_name, Column, EngineModels, Projection};

const USAGE: &str = "usage: arclog-cli row-parity <corpus-dir> <tasks-dir> <rows-dir> <task_id> [<task_id> ...]";

/// The relation of the line of a fault of a whole task.
const WHOLE_TASK: &str = "*";

/// The reason of the `uncompared` line of a relation that the file sends and
/// that no case's program has.
const NO_CASE_HAS_IT: &str = "no case's program has a relation of that name";

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

/// One relation on one pair: Souffle's projected rows, the rows of each of
/// its open values where it holds the open value in a column, the engine's
/// rows at each model projected onto the same columns, `None` where the
/// case's program has no relation of the name, the columns of the file that
/// a pair's rows lack and its unresolved leaves with their reasons, and the
/// text of a minted id that Souffle's rows of the pair do not account for.
pub(crate) struct Checked {
    pub(crate) name: String,
    pub(crate) souffle: BTreeSet<Vec<Leaf>>,
    pub(crate) by_open: Vec<BTreeSet<Vec<Leaf>>>,
    pub(crate) engine: Option<EngineModels>,
    pub(crate) left_out: Vec<String>,
    pub(crate) fault: Option<String>,
}

/// One relation of the rows file on one pair, as `column_names_of` and
/// `souffle_rows_of` read it.
struct FileRelation {
    columns: Vec<String>,
    minted: Vec<bool>,
    left_out: Vec<String>,
    rows: Vec<Vec<Vec<Leaf>>>,
    by_open: Vec<Vec<Vec<Vec<Leaf>>>>,
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
    let report = run_over_corpus(Path::new(corpus), Some(&selected), |solver| {
        let file = read_json(&Path::new(rows).join(format!("{}.json", solver.task_id)));
        match file.and_then(|file| task_verdicts(Path::new(corpus), Path::new(tasks), &solver.task_id, &file)) {
            Ok(verdicts) => {
                lines.lock().expect("the lines are not poisoned").insert(solver.task_id.clone(), verdicts);
                SolverResult::Pass
            }
            Err(fault) => SolverResult::Fail(vec![fault]),
        }
    }, |_, _| {});
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

/// The verdict of each relation of the rows file `file` of the solver `id`:
/// the relations that the file leaves out, then each relation of the cases
/// it gives, merged over the cases and their pairs, in the file's order of
/// relations. A case that fails to set up, and a case whose Souffle run gave
/// no rows, give a fault of the whole task.
fn task_verdicts(corpus: &Path, tasks: &Path, id: &str, file: &Value) -> Result<Vec<(String, Verdict)>, String> {
    let constants = constants_of(file)?;
    let cases = file.get("cases").and_then(Value::as_array).ok_or("the rows file has no `cases`")?;
    let mut merged: Vec<(String, Verdict)> = Vec::new();
    let mut sent: Vec<String> = Vec::new();
    for case in cases {
        let name = case.get("case").and_then(Value::as_str).ok_or("a case of the rows file has no `case`")?;
        if let Some(failure) = case.get("failure").and_then(Value::as_str) {
            merged.push((WHOLE_TASK.to_owned(), Verdict::Fault(format!("case {name}: no Souffle rows: {failure}"))));
            continue;
        }
        let pairs = case.get("pairs").and_then(Value::as_array).ok_or("a case of the rows file has no `pairs`")?;
        match with_case(corpus, tasks, id, name, |case| case_verdicts(case, name, &constants, pairs)) {
            Ok((verdicts, names)) => {
                verdicts.into_iter().for_each(|(relation, verdict)| merge(&mut merged, relation, verdict));
                for relation in names {
                    if !sent.contains(&relation) {
                        sent.push(relation);
                    }
                }
            }
            Err(fault) => merged.push((WHOLE_TASK.to_owned(), Verdict::Fault(format!("case {name}: {fault}")))),
        }
    }
    for relation in sent {
        if !merged.iter().any(|(held, _)| *held == relation) {
            merged.push((relation, Verdict::Uncompared(NO_CASE_HAS_IT.to_owned())));
        }
    }
    let left_out = file.get("not_compared").and_then(Value::as_array).ok_or("the rows file has no `not_compared`")?;
    for entry in left_out {
        let text = |key: &str| entry.get(key).and_then(Value::as_str).map(str::to_owned).ok_or_else(|| format!("an entry of `not_compared` has no `{key}`"));
        let (name, reason) = (text("name")?, text("reason")?);
        let verdict = match text("verdict")?.as_str() {
            "skip" => Verdict::Skip(reason),
            "uncompared" => Verdict::Uncompared(reason),
            other => return Err(format!("an entry of `not_compared` has the verdict `{other}`")),
        };
        merged.push((name, verdict));
    }
    Ok(merged)
}

/// The verdict of each relation of the case `name`, one of the `pairs` of
/// the rows file, over the pairs of the task of `case`, merged over the
/// pairs, and the name of each relation the pairs send.
fn case_verdicts(case: &ConceptCase<'_>, name: &str, constants: &BTreeMap<String, i64>, pairs: &[Value]) -> Result<(Vec<(String, Verdict)>, Vec<String>), String> {
    let evaluation = &case.evaluation;
    let mut merged: Vec<(String, Verdict)> = Vec::new();
    let mut sent: Vec<String> = Vec::new();
    for (index, example) in evaluation.task.examples().enumerate() {
        let pair = pair_name(evaluation.task, index);
        let in_file = pairs.iter().find(|entry| entry.get("pair").and_then(Value::as_str) == Some(pair.as_str())).ok_or_else(|| format!("the rows file has no pair `{pair}`"))?;
        let relations = in_file.get("relations").and_then(Value::as_array).ok_or("a pair of the rows file has no `relations`")?;
        let mut checked = Vec::new();
        for relation in relations {
            let relation_name = relation.get("name").and_then(Value::as_str).ok_or("a relation of the rows file has no `name`")?;
            let columns = column_names_of(relation, "columns")?;
            let minted = minted_of(relation)?;
            if minted.len() != columns.len() {
                return Err(format!("the relation `{relation_name}` of the rows file has {} columns and {} `idents`", columns.len(), minted.len()));
            }
            let file_relation = FileRelation {
                columns,
                minted,
                left_out: [column_names_of(relation, "unread")?, unresolved_of(relation)?].concat(),
                rows: souffle_rows_of(relation.get("rows"))?,
                by_open: by_open_of(relation)?,
            };
            let fault = relation.get("fault").map(|text| text.as_str().map(str::to_owned).ok_or("a fault of the rows file is no text")).transpose()?;
            checked.push(engine_side(evaluation, relation_name, example, constants, file_relation, fault));
            if !sent.iter().any(|held| held == relation_name) {
                sent.push(relation_name.to_owned());
            }
        }
        for (relation, verdict) in compare_pair(&format!("{name}, {pair}"), &checked) {
            merge(&mut merged, relation, verdict);
        }
    }
    Ok((merged, sent))
}

/// One relation on one pair: the engine's rows at each model, over the
/// columns of the map, Souffle's rows projected onto them, and the rows of
/// each open value of Souffle's relation projected onto them. A column of
/// the map that the engine's relation lacks gives a fault.
fn engine_side(
    evaluation: &Evaluation<'_>,
    name: &str,
    example: Example,
    constants: &BTreeMap<String, i64>,
    file: FileRelation,
    fault: Option<String>,
) -> Checked {
    let checked = |engine, left_out, souffle, by_open| Checked { name: name.to_owned(), souffle, by_open, engine, left_out, fault: fault.clone() };
    let names = match engine_columns(evaluation, name) {
        None => return checked(None, Vec::new(), BTreeSet::new(), Vec::new()),
        Some(Err(text)) => return checked(Some(EngineModels::Fault(text)), Vec::new(), BTreeSet::new(), Vec::new()),
        Some(Ok(names)) => names,
    };
    let FileRelation { columns, minted, left_out, rows, by_open } = file;
    let mut kept = Vec::new();
    let mut lacking = Vec::new();
    for (entry, column) in columns.iter().enumerate() {
        match names.iter().position(|n| n == column) {
            Some(position) => kept.push((entry, Column { position, minted: minted[entry] })),
            None => lacking.push(column.clone()),
        }
    }
    if !lacking.is_empty() {
        let text = if kept.is_empty() {
            format!("none of the columns of the map is a column of the engine's relation: {}", lacking.join(", "))
        } else {
            format!("the engine's relation lacks the columns of the map: {}", lacking.join(", "))
        };
        return checked(Some(EngineModels::Fault(text)), left_out, BTreeSet::new(), Vec::new());
    }
    let project = |rows: &[Vec<Vec<Leaf>>]| -> BTreeSet<Vec<Leaf>> { rows.iter().map(|row| kept.iter().flat_map(|&(entry, _)| row[entry].clone()).collect()).collect() };
    let columns: Vec<Column> = kept.iter().map(|&(_, column)| column).collect();
    let engine = match engine_models(evaluation, name, example, constants, Projection::Positions(&columns)) {
        None => EngineModels::Fault("the relation has no rows to read".to_owned()),
        Some(EngineModels::Models(models)) => EngineModels::Models(models.into_iter().map(distinct).collect()),
        Some(fault) => fault,
    };
    checked(Some(engine), left_out, project(&rows), by_open.iter().map(|group| project(group)).collect())
}

/// The constants of the rows file, by name.
fn constants_of(file: &Value) -> Result<BTreeMap<String, i64>, String> {
    let object = file.get("orientation_constants").and_then(Value::as_object).ok_or("the rows file has no `orientation_constants`")?;
    object.iter().map(|(name, n)| Ok((name.clone(), n.as_i64().ok_or("an orientation constant is no number")?))).collect()
}

/// The name of each column of `relation` under `key`, as the engine names a row
/// position: the label, and, for a field, `<label>.<field>`.
fn column_names_of(relation: &Value, key: &str) -> Result<Vec<String>, String> {
    let columns = relation.get(key).and_then(Value::as_array).ok_or_else(|| format!("a relation of the rows file has no `{key}`"))?;
    columns
        .iter()
        .map(|column| {
            let [label, field] = column.as_array().map(Vec::as_slice).ok_or("a column is no pair")? else { return Err("a column is no pair".to_owned()) };
            let label = label.as_str().ok_or("a column has no label")?;
            Ok(field.as_str().map_or_else(|| label.to_owned(), |field| format!("{label}.{field}")))
        })
        .collect()
}

/// Whether each column of `relation` in the rows file is one whose leaf is
/// an id that a lib relation mints (`"minted"`), as against a number a clause
/// writes (`"stored"`) or a leaf that is no Ident (`null`).
fn minted_of(relation: &Value) -> Result<Vec<bool>, String> {
    let kinds = relation.get("idents").and_then(Value::as_array).ok_or("a relation of the rows file has no `idents`")?;
    kinds
        .iter()
        .map(|kind| match (kind.as_str(), kind.is_null()) {
            (Some("minted"), _) => Ok(true),
            (Some("stored"), _) | (None, true) => Ok(false),
            _ => Err(format!("an entry of `idents` is neither `minted`, `stored` nor null: {kind}")),
        })
        .collect()
}

/// The leaves of `relation` in the rows file that have no one source, each
/// as the column's name and the reason.
fn unresolved_of(relation: &Value) -> Result<Vec<String>, String> {
    let leaves = relation.get("unresolved").and_then(Value::as_array).ok_or("a relation of the rows file has no `unresolved`")?;
    leaves
        .iter()
        .map(|leaf| {
            let [label, field, reason] = leaf.as_array().map(Vec::as_slice).ok_or("an unresolved leaf is no triple")? else { return Err("an unresolved leaf is no triple".to_owned()) };
            let label = label.as_str().ok_or("an unresolved leaf has no label")?;
            let reason = reason.as_str().ok_or("an unresolved leaf has no reason")?;
            Ok(format!("{} (unresolved: {reason})", field.as_str().map_or_else(|| label.to_owned(), |field| format!("{label}.{field}"))))
        })
        .collect()
}

/// The rows `rows` of a relation in the rows file: for each row, the leaves
/// of each mapped column.
fn souffle_rows_of(rows: Option<&Value>) -> Result<Vec<Vec<Vec<Leaf>>>, String> {
    let rows = rows.and_then(Value::as_array).ok_or("a relation of the rows file has no `rows`")?;
    rows.iter()
        .map(|row| {
            row.as_array()
                .ok_or("a row is no array")?
                .iter()
                .map(|entry| entry.as_array().ok_or("a row's column is no array")?.iter().map(|leaf| Leaf::of(leaf).ok_or("a leaf is no number and no string")).collect::<Result<Vec<_>, _>>())
                .collect::<Result<Vec<_>, _>>()
                .map_err(str::to_owned)
        })
        .collect()
}

/// The rows of each open value of `relation` in the rows file, none where
/// the relation holds no open value in a column.
fn by_open_of(relation: &Value) -> Result<Vec<Vec<Vec<Vec<Leaf>>>>, String> {
    let Some(groups) = relation.get("by_open") else { return Ok(Vec::new()) };
    groups.as_array().ok_or("`by_open` is no array")?.iter().map(|group| souffle_rows_of(Some(group))).collect()
}

/// `rows` with each row once, in order.
fn distinct(rows: Vec<Vec<EngineLeaf>>) -> Vec<Vec<EngineLeaf>> {
    let mut seen: Vec<Vec<EngineLeaf>> = Vec::new();
    for row in rows {
        if !seen.contains(&row) {
            seen.push(row);
        }
    }
    seen
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

/// The engine's rows of a relation, each compared with the Souffle rows it
/// stands for: the one set of rows where the models give one, the rows of
/// each model with the rows of the open value it matches where Souffle's
/// relation holds the open value in a column, else the union of the models'
/// rows with Souffle's rows. A text for what does not match.
fn comparisons<'a>(models: &[Vec<Vec<EngineLeaf>>], souffle: &'a BTreeSet<Vec<Leaf>>, by_open: &'a [BTreeSet<Vec<Leaf>>]) -> Result<Vec<(&'a BTreeSet<Vec<Leaf>>, Vec<Vec<EngineLeaf>>)>, String> {
    if let [only] = models {
        return Ok(vec![(souffle, only.clone())]);
    }
    if by_open.is_empty() {
        return Ok(vec![(souffle, distinct(models.concat()))]);
    }
    let mut used = vec![false; by_open.len()];
    let mut pairs = Vec::new();
    for (index, model) in models.iter().enumerate() {
        let Some(open) = by_open.iter().position(|rows| same_without_idents(model, rows)) else {
            return Err(format!("{} models; the rows of model {} are the rows of none of Souffle's {} open values", models.len(), index + 1, by_open.len()));
        };
        used[open] = true;
        pairs.push((&by_open[open], model.clone()));
    }
    match used.iter().position(|used| !used) {
        Some(open) => Err(format!("{} models; the rows of open value {} of Souffle's {} are the rows of no model", models.len(), open + 1, by_open.len())),
        None => Ok(pairs),
    }
}

/// The verdict of each relation of `relations` on `scope`, a case and a
/// pair, in order; none for a relation that the case's program lacks. Each
/// relation compares as sets, with each Ident that a lib relation mints
/// written as the text of the set of its members; the relations that hold an
/// Ident of another kind, a number a fact writes, then must agree under one
/// renaming of Idents over all of them, as each pair is a separate run of
/// Souffle, whose numbers denote the objects of that input alone.
pub(crate) fn compare_pair(scope: &str, relations: &[Checked]) -> Vec<(String, Verdict)> {
    let mut verdicts = Vec::new();
    let mut compared: Vec<(&BTreeSet<Vec<Leaf>>, Vec<Vec<EngineLeaf>>)> = Vec::new();
    'relations: for Checked { name, souffle, by_open, engine, left_out, fault } in relations {
        let note = if left_out.is_empty() { String::new() } else { format!("; columns left out of both sides: {}", left_out.join(", ")) };
        let verdict = match engine {
            None => continue,
            Some(EngineModels::Fault(text)) => Verdict::Fault(format!("{scope}: {text}")),
            Some(EngineModels::Models(_)) if fault.is_some() => Verdict::Fault(format!("{scope}: {}", fault.as_deref().unwrap_or_default())),
            Some(EngineModels::Models(models)) => {
                let pairs = match comparisons(models, souffle, by_open) {
                    Ok(pairs) => pairs,
                    Err(text) => {
                        verdicts.push((name.clone(), Verdict::Differ(format!("{scope}: {text}{note}"))));
                        continue;
                    }
                };
                for (theirs, rows) in &pairs {
                    if !same_without_idents(rows, theirs) {
                        verdicts.push((name.clone(), Verdict::Differ(format!("{scope}: {}{note}", describe_difference(rows, theirs)))));
                        continue 'relations;
                    }
                }
                let before = compared.len();
                compared.extend(pairs.into_iter().filter(|(_, rows)| rows.iter().flatten().any(|leaf| matches!(leaf, EngineLeaf::Ident(_)))));
                if compared.len() > before && !renaming_exists(&compared) {
                    compared.truncate(before);
                    verdicts.push((name.clone(), Verdict::Differ(format!("{scope}: no one renaming of Idents makes its rows and those of the relations before it agree{note}"))));
                    continue;
                }
                Verdict::Equal(format!("{scope}{note}"))
            }
        };
        verdicts.push((name.clone(), verdict));
    }
    verdicts
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
        Checked { name: name.to_owned(), souffle, by_open: Vec::new(), engine: Some(EngineModels::Models(models)), left_out: Vec::new(), fault: None }
    }

    fn idents(count: u32) -> Vec<Ident> {
        let mut table = InternTable::default();
        (0..count).map(|i| table.intern(Content::FromFile { ty: arclog::types::ValueType::Ident, written: WrittenIdent::new(i) })).collect()
    }

    #[test]
    fn differs_where_the_engine_holds_souffles_rows_and_more() {
        let relations = [checked("&a", souffle(&[&[1, 2]]), vec![written(&[1, 2]), written(&[3, 4])])];
        let [(_, verdict)] = &compare_pair("concept, train 0", &relations)[..] else { panic!("one verdict") };
        let Verdict::Differ(text) = verdict else { panic!("{verdict:?}") };
        assert!(text.contains("2 rows in the engine and 1 in Souffle") && text.contains("only the engine holds [3 4]"), "{text}");
    }

    #[test]
    fn differs_where_a_nullary_relation_stands_on_one_side_alone() {
        let present = BTreeSet::from([Vec::new()]);
        let relations = [checked("&flag", present.clone(), Vec::new()), checked("&other", BTreeSet::new(), vec![Vec::new()]), checked("&both", present, vec![Vec::new()])];
        let verdicts = compare_pair("concept, train 0", &relations);
        assert!(matches!(verdicts[0].1, Verdict::Differ(_)), "{verdicts:?}");
        assert!(matches!(verdicts[1].1, Verdict::Differ(_)), "{verdicts:?}");
        assert!(matches!(verdicts[2].1, Verdict::Equal(_)), "{verdicts:?}");
    }

    #[test]
    fn equals_where_the_union_of_the_models_is_souffles_rows() {
        let relations = [models("&order", souffle(&[&[1, 2], &[3, 4]]), vec![vec![written(&[1, 2])], vec![written(&[3, 4])]])];
        let [(_, verdict)] = &compare_pair("concept, train 0", &relations)[..] else { panic!("one verdict") };
        assert!(matches!(verdict, Verdict::Equal(_)), "{verdict:?}");
    }

    #[test]
    fn differs_where_the_union_of_the_models_is_not_souffles_rows() {
        let relations = [models("&order", souffle(&[&[1, 2], &[3, 4]]), vec![vec![written(&[1, 2])], vec![written(&[5, 6])]])];
        let [(_, verdict)] = &compare_pair("concept, train 0", &relations)[..] else { panic!("one verdict") };
        assert!(matches!(verdict, Verdict::Differ(_)), "{verdict:?}");
    }

    #[test]
    fn differs_where_two_relations_agree_under_two_renamings() {
        let [x, y] = idents(2)[..] else { unreachable!() };
        let id = |ident, color: i64| vec![EngineLeaf::Ident(ident), EngineLeaf::Written(n(color))];
        let relations = [
            checked("&color", souffle(&[&[7, 1], &[8, 2]]), vec![id(x, 1), id(y, 2)]),
            checked("&big", souffle(&[&[7]]), vec![vec![EngineLeaf::Ident(y)]]),
        ];
        let verdicts = compare_pair("concept, train 0", &relations);
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
        let [(_, verdict)] = &compare_pair("concept, train 0", &relations)[..] else { panic!("one verdict") };
        assert!(matches!(verdict, Verdict::Differ(_)), "{verdict:?}");
    }

    #[test]
    fn faults_where_a_minted_id_has_no_row_of_the_minting_relation() {
        let mut relation = checked("&label", BTreeSet::from([vec![text("{}")]]), vec![minted("{}")]);
        relation.fault = Some("the id 5 has no row of comps4.label at the key of the row".to_owned());
        let [(_, verdict)] = &compare_pair("concept, train 0", &[relation])[..] else { panic!("one verdict") };
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
        let verdicts = compare_pair("concept, train 0", &relations);
        assert!(verdicts.iter().all(|(_, verdict)| matches!(verdict, Verdict::Equal(_))), "{verdicts:?}");
    }
}
