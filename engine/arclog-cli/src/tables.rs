//! `tables <corpus-dir> <tasks-dir> <out-dir> [--cases concept|all]
//! [<task_id> ...]`: replays the token stream of each case program of the
//! corpus that the decoder admits, and writes, for each, the tables that
//! [`arclog::decode::Decoder::tables`] gives, each at the index in the stream
//! of the token whose step gives it.
//!
//! The file `<out-dir>/<task_id>/<case>.jsonl` holds one JSON object for each
//! table, in the order of the stream. A table's object gives `token` (the
//! index), `form` (the form's `NodePath` as dot-separated indices), `point`
//! (`{"kind": "body", "conjuncts", "sites"}` for the body of the clause in
//! progress, `{"kind": "relation"}` for a relation of a finished form), and
//! either `fault`, or `relation` (its slot), `columns` (each `{"name",
//! "type"}`), `dets` (the `DET`s of its assignments, each `{"relation",
//! "types"}`), `examples` and `views`. Each of `examples` gives `example`
//! (`train/<i>`, `test/<i>` or `task`), and either `fault`, or `stop` (the
//! bound that ended the walk of the assignments, or `null`) and `entries`:
//! one for each model at each assignment, each `{"assigned", "model",
//! "value"}`, where `assigned` gives each `DET`'s `relation` and `rows`, and
//! `value` is `{"rows": [...]}`, `"undefined"` or `{"stopped": ...}`; rows
//! are arrays of values as `value_json` gives them. Where a relation holds
//! more rows on an example than the view cap, `views` is `{"stopped": ...}`
//! or `{"found": [...]}` of views `{"columns": [...], "examples": [...]}`, whose
//! `examples` give, for each example, the view's rows at each entry, and
//! `null` at an entry that holds no rows, and the entries' values give only
//! their row counts `{"count": n}`; otherwise `views` is `null`.
//!
//! A case program that holds a `DEMONSTRATED` form, that the writer gives no
//! stream, or whose stream the decoder refuses gets no file and prints as
//! `decode` prints a refusal. Each other prints one line with its count of
//! tables and its file's bytes.

use std::fmt::Write as _;
use std::ops::ControlFlow;
use std::path::{Path, PathBuf};
use std::process::ExitCode;
use std::sync::Arc;

use arclog::check::{CheckCache, CheckedProgram, SolverClauses};
use arclog::decode::{Contents, Decoder, Table, Views};
use arclog::eval::determinations::relation_spelled;
use arclog::eval::join::each_row;
use arclog::eval::{RelationValue, Stop};
use arclog::harness::{print_ended, require_optimized_build, run_over_corpus, SolverResult};
use arclog::judge::candidates::{PairCandidates, Section, World};
use arclog::program::path::NodePath;
use arclog::registry::Registry;
use arclog::relations::Relation;
use arclog::resolver::resolve_cases;
use arclog::stream::{token_stream, DecodeSettings};
use arclog::task::Task;
use arclog::terms::Example;
use arclog::types::ValueType;
use arclog_constructions::shared as constructions;
use serde_json::{json, Value};

use crate::concept_case::{case_spelled, check_cases, corpus_session, read_corpus_task, CorpusTask};
use crate::lib_compare::evaluation::value_json;
use crate::replay::{decoded_cases, holds_demonstrated, replay};
use crate::select::selected;

const USAGE: &str = "usage: arclog-cli tables <corpus-dir> <tasks-dir> <out-dir> [--cases concept|all] [<task_id> ...]";

/// The subcommand on `args`, the arguments after its name.
pub fn run(args: &[String]) -> ExitCode {
    if let Err(code) = require_optimized_build() {
        return code;
    }
    let Some((corpus, tasks, out, all, task_ids)) = parse(args) else {
        eprintln!("{USAGE}");
        return ExitCode::from(2);
    };
    let selected = selected(&task_ids, &[], Path::new("")).expect("a selection by task id alone reads no file");
    let report = run_over_corpus(&corpus, |solver| match &selected {
        Some(ids) if !ids.contains(&solver.task_id) => SolverResult::Pass,
        _ => tables_solver(&corpus, &tasks, &out, &solver.task_id, all),
    }, print_ended);
    match report {
        Ok(report) if report.failures.is_empty() => ExitCode::SUCCESS,
        Ok(_) => ExitCode::FAILURE,
        Err(error) => {
            eprintln!("the corpus does not read: {error:?}");
            ExitCode::from(2)
        }
    }
}

/// The corpus directory, the tasks directory, the output directory, whether
/// `--cases all` is given, and the task ids, or `None` for arguments of
/// another form.
fn parse(args: &[String]) -> Option<(PathBuf, PathBuf, PathBuf, bool, Vec<String>)> {
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
    let (corpus, tasks, out) = (positional.next()?, positional.next()?, positional.next()?);
    Some((corpus.into(), tasks.into(), out.into(), all, positional.collect()))
}

/// The files of the solver `id`, its summary lines printed; or the lines of
/// the faults and refusals.
fn tables_solver(corpus: &Path, tasks: &Path, out: &Path, id: &str, all: bool) -> SolverResult {
    match write_cases(corpus, tasks, out, id, all) {
        Ok(lines) if lines.failures.is_empty() => {
            for line in lines.written {
                println!("{id}: {line}");
            }
            SolverResult::Pass
        }
        Ok(lines) => {
            for line in lines.written {
                println!("{id}: {line}");
            }
            SolverResult::Fail(lines.failures)
        }
        Err(fault) => SolverResult::Fail(vec![format!("a fault that stops the tables: {fault}")]),
    }
}

/// The lines of a solver's run: one for each file written, and one for each
/// case that gets none.
struct Lines {
    written: Vec<String>,
    failures: Vec<String>,
}

fn write_cases(corpus: &Path, tasks: &Path, out: &Path, id: &str, all: bool) -> Result<Lines, String> {
    let CorpusTask { solver, task, judged } = read_corpus_task(corpus, tasks, id)?;
    let registry = Registry::get();
    let cases = resolve_cases(&solver, registry);
    let clauses = SolverClauses::of_cases(&cases);
    let decoded = decoded_cases(&cases, all);
    let programs = check_cases(&cases, &clauses, &mut CheckCache::default(), &|name| decoded.contains(name))?;
    let constructions = constructions()?;
    let settings = DecodeSettings::default();
    let train: Arc<[PairCandidates<'_>]> = judged.train.iter().map(|pair| PairCandidates::of(pair, Section::Train, World::Closed)).collect();
    let mut lines = Lines { written: Vec::new(), failures: Vec::new() };
    for (name, program) in &programs {
        let case = case_spelled(name);
        if holds_demonstrated(program) {
            continue;
        }
        let session = corpus_session();
        let mut decoder = Decoder::new(&task, &session, registry, constructions, &settings).judging(Arc::clone(&train));
        match record_case(&mut decoder, program, &task) {
            Ok((count, text)) => {
                let dir = out.join(id);
                let path = dir.join(format!("{case}.jsonl"));
                std::fs::create_dir_all(&dir).and_then(|()| std::fs::write(&path, &text)).map_err(|error| format!("{}: {error}", path.display()))?;
                lines.written.push(format!("{case}: {count} tables, {} bytes", text.len()));
            }
            Err(refusal) => lines.failures.push(format!("case {case}: {refusal}")),
        }
    }
    Ok(lines)
}

/// The count of the tables of `program`'s stream and their lines, or why the
/// stream gives none.
fn record_case(decoder: &mut Decoder<'_>, program: &CheckedProgram, task: &Task) -> Result<(usize, String), String> {
    let stream = token_stream(program, decoder.vocabulary()).map_err(|diagnostic| format!("the writer gives no stream: {}", diagnostic.message))?;
    let mut text = String::new();
    let mut count = 0;
    let replayed = replay(decoder, &stream, &mut |decoder, stepped| {
        for table in decoder.tables() {
            writeln!(text, "{}", table_json(stepped.index, &table, task)).expect("a string takes a line");
            count += 1;
        }
        ControlFlow::Continue(())
    })?;
    match replayed.unfinished() {
        Some(refusal) => Err(refusal),
        None => Ok((count, text)),
    }
}

/// The object of `table`, the table of the step of the token at `index`.
fn table_json(index: usize, table: &Table, task: &Task) -> Value {
    let point = match table.point {
        arclog::decode::Point::Body { conjuncts, sites } => json!({"kind": "body", "conjuncts": conjuncts, "sites": sites}),
        arclog::decode::Point::Relation => json!({"kind": "relation"}),
    };
    let mut object = json!({"token": index, "form": form_path(&table.form), "point": point});
    match &table.contents {
        Err(fault) => object["fault"] = Value::from(format!("{} at {}", fault.message, form_path(&fault.form))),
        Ok(contents) => {
            let fields = contents_json(contents, task);
            object.as_object_mut().expect("an object").extend(fields);
        }
    }
    object
}

fn form_path(form: &NodePath) -> String {
    form.0.iter().map(|step| step.0.to_string()).collect::<Vec<_>>().join(".")
}

fn contents_json(contents: &Contents, task: &Task) -> serde_json::Map<String, Value> {
    let types: Vec<ValueType> = contents.columns.iter().map(|column| column.ty.clone()).collect();
    let in_views = contents.views.is_some();
    let examples: Vec<Value> = contents
        .examples
        .iter()
        .map(|example| {
            let mut object = json!({"example": example_name(task, example.example)});
            match &example.rows {
                Err(fault) => object["fault"] = Value::from(format!("{} at {}", fault.message, form_path(&fault.form))),
                Ok(rows) => {
                    object["stop"] = rows.stop.as_ref().map_or(Value::Null, stop_json);
                    let mut entries = Vec::new();
                    for (assigned, models) in &rows.at {
                        let assigned: Vec<Value> = assigned.iter().zip(contents.dets.iter()).map(|((relation, rows), det)| json!({"relation": relation_spelled(relation), "rows": rows_json(rows, &det.types)})).collect();
                        for (model, value) in models.iter().enumerate() {
                            entries.push(json!({"assigned": assigned, "model": model, "value": value_summary(value, &types, in_views)}));
                        }
                    }
                    object["entries"] = Value::from(entries);
                }
            }
            object
        })
        .collect();
    let views = match &contents.views {
        None => Value::Null,
        Some(Views::Stopped(stop)) => json!({"stopped": stop_json(stop)}),
        Some(Views::Found(found)) => {
            let found: Vec<Value> = found
                .iter()
                .map(|view| {
                    let view_types: Vec<ValueType> = view.columns.iter().map(|column| types[column.0 as usize].clone()).collect();
                    let per_example: Vec<Value> = view
                        .rows
                        .iter()
                        .map(|rows| Value::from(rows.at.iter().map(|(_, projection)| projection.as_ref().map_or(Value::Null, |rows| rows_json(rows, &view_types))).collect::<Vec<_>>()))
                        .collect();
                    json!({"columns": view.columns.iter().map(|column| column.0).collect::<Vec<_>>(), "examples": per_example})
                })
                .collect();
            json!({"found": found})
        }
    };
    let mut fields = serde_json::Map::new();
    fields.insert("relation".to_owned(), Value::from(contents.relation));
    fields.insert("columns".to_owned(), Value::from(contents.columns.iter().map(|column| json!({"name": column.name, "type": format!("{:?}", column.ty)})).collect::<Vec<_>>()));
    fields.insert("dets".to_owned(), Value::from(contents.dets.iter().map(|det| json!({"relation": relation_spelled(&det.relation), "types": det.types.iter().map(|ty| format!("{ty:?}")).collect::<Vec<_>>()})).collect::<Vec<_>>()));
    fields.insert("examples".to_owned(), Value::from(examples));
    fields.insert("views".to_owned(), views);
    fields
}

/// The name of an example: `train/<i>`, `test/<i>`, or `task`.
fn example_name(task: &Task, example: Option<Example>) -> String {
    match example {
        None => "task".to_owned(),
        Some(example) => {
            let index = usize::from(example.index());
            if index < task.train.len() { format!("train/{index}") } else { format!("test/{}", index - task.train.len()) }
        }
    }
}

fn stop_json(stop: &Stop) -> Value {
    json!({"bound": format!("{:?}", stop.bound), "form": form_path(&stop.form)})
}

/// A model's value: its rows, or only their count where the views stand in
/// place of the rows.
fn value_summary(value: &RelationValue, types: &[ValueType], count_only: bool) -> Value {
    match value {
        RelationValue::Rows(rows) if count_only => json!({"count": rows.len()}),
        RelationValue::Rows(rows) => json!({"rows": rows_json(rows, types)}),
        RelationValue::Undefined => Value::from("undefined"),
        RelationValue::Stopped(stop) => json!({"stopped": stop_json(stop)}),
    }
}

/// The rows of `rows` as arrays of values of `types`, in the order of their
/// JSON text.
fn rows_json(rows: &Relation, types: &[ValueType]) -> Value {
    let mut written: Vec<(String, Value)> = Vec::new();
    each_row(rows, &mut |row| {
        let value = Value::Array(row.iter().zip(types).map(|(&id, ty)| value_json(id, ty)).collect());
        written.push((value.to_string(), value));
    });
    written.sort_by(|a, b| a.0.cmp(&b.0));
    Value::from(written.into_iter().map(|(_, value)| value).collect::<Vec<_>>())
}
