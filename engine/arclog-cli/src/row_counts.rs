//! `row-counts [--over <n> --rows <dir>] <corpus-dir> <tasks-dir>
//! [<task_id> ...]`: relation row counts of each selected solver's concept
//! case at its stored parameters.
//!
//! Lines are `<task_id> <example> <relation> <counts>`, ordered by task id,
//! relation name, then train and test example. Task-wide relations use
//! `task`; counts are comma-separated model values, `undefined`, or
//! `stopped:<bound>`. A relation that the decode gives no table
//! ([`arclog_tables::tables::gives_no_table`]) has, after its lines for an example,
//! the line `<task_id> <example> <relation> no table`. A solver that faults
//! gets one fault line instead.
//!
//! With `--over <n> --rows <dir>`, each model of a relation and example that
//! holds more than `n` rows also has its rows written, each model's apart, to `<dir>/<task_id>/<example>/<relation>.<model>.json` (the `/` of an example written `-`), a JSON
//! object of `solver`, `input`, `relation`, `model`, `columns` (each
//! `{"name", "type"}`, the name the solver's program gives the column, a record's field `<record>.<field>`, or `c<i>` for a column of an output of a shared node) and `rows` (each row an array of values as
//! `value_json` gives them, in the order of the rows' JSON text). A relation
//! whose columns the type check gives no types gets no file. Where a
//! clause makes the relation, one line per form of the clause follows the
//! relation's line, where a model holds more than `n` rows or stopped at a
//! bound:
//! `<task_id> <example> <relation> clause <path> <body> <reads>`. `<path>`
//! is the form's `NodePath` as dot-separated indices; `<body>` is the
//! count of the rows of the body over all its conjuncts, which exceeds the
//! rows the clause gives its head where the head leaves columns out,
//! `undefined`, `fault` where the body's evaluation faults, such as a clause over a pick with several models, or `stopped:<bound>`; `<reads>` is the comma-separated
//! relations that the clause's node reads, or `-`. A relation that an
//! instance makes is attributed by its `<instance>.<port>` name.

use std::collections::{BTreeMap, BTreeSet};
use std::ops::ControlFlow;
use std::path::{Path, PathBuf};
use std::process::ExitCode;
use std::sync::{Arc, Mutex};

use arclog::eval::determinations::relation_spelled;
use arclog::eval::examples::{scope_of, ExampleScope};
use arclog::eval::join::each_row;
use arclog::eval::{Evaluation, ModelsEnd, ReachedBound, RelationValue};
use arclog::harness::{require_optimized_build, run_over_corpus, SolverResult};
use arclog::program::path::{node_at, NodePath, NodeRef};
use arclog::program::{DeclaredName, FactRelation, OutputName, OutputOwner, OutputStep, ProgramRelation, RelationRef};
use arclog::registry::LibEntry;
use arclog::resolver::{DependencyKind, GraphNodeIndex};
use arclog::terms::Example;
use arclog::types::{GraphRelation, ValueType};
use arclog_tables::tables::gives_no_table;
use serde_json::{json, Value};

use crate::concept_case::with_concept_case;
use crate::lib_compare::evaluation::value_json;

/// The fields after a relation's name on the line that says the decode gives
/// the relation no table.
const NO_TABLE: &str = "no table";

/// Where `--over` and `--rows` have the rows of the relations over a size
/// written.
struct RowDump {
    over: u64,
    dir: PathBuf,
}

/// The subcommand on the arguments after its name.
pub fn run(args: &[String]) -> ExitCode {
    if let Err(code) = require_optimized_build() {
        return code;
    }
    let usage = || {
        eprintln!("usage: arclog-cli row-counts [--over <n> --rows <dir>] <corpus-dir> <tasks-dir> [<task_id> ...]");
        ExitCode::from(2)
    };
    let (dump, args) = match args {
        [flag, over, rows_flag, dir, rest @ ..] if flag == "--over" && rows_flag == "--rows" => {
            let Ok(over) = over.parse() else { return usage() };
            (Some(RowDump { over, dir: PathBuf::from(dir) }), rest)
        }
        _ => (None, args),
    };
    let [corpus, tasks, ids @ ..] = args else { return usage() };
    let selected: BTreeSet<String> = ids.iter().cloned().collect();
    let lines = Mutex::new(BTreeMap::new());
    let report = run_over_corpus(Path::new(corpus), (!selected.is_empty()).then_some(&selected), |solver| {
        match with_concept_case(Path::new(corpus), Path::new(tasks), &solver.task_id, |case| counts(&case.evaluation, &solver.task_id, dump.as_ref())) {
            Ok(report) => {
                lines.lock().expect("the report map is not poisoned").insert(solver.task_id.clone(), report);
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
    let mut lines = lines.into_inner().expect("the report map is not poisoned");
    for (solver, faults) in &report.failures {
        lines.insert(solver.task_id.clone(), vec![format!("fault {}", faults.join("; ").replace(['\n', '\r'], " "))]);
    }
    for (id, lines) in lines {
        for line in lines {
            println!("{id} {line}");
        }
    }
    if report.failures.is_empty() { ExitCode::SUCCESS } else { ExitCode::FAILURE }
}

/// The relation counts, in relation-name order and then task-file order,
/// with the dump of the rows of the relations over its size where `dump`
/// gives one.
fn counts(evaluation: &Evaluation<'_>, solver: &str, dump: Option<&RowDump>) -> Result<Vec<String>, String> {
    let mut relations = Vec::new();
    for (index, node) in evaluation.program.program.graph.nodes.iter().enumerate() {
        let node_index = GraphNodeIndex(index as u32);
        for Named { name, output, declared } in names(evaluation, node_index, &node.kind)? {
            relations.push((name, GraphRelation { node: node_index, output }, declared));
        }
    }
    relations.sort_by(|a, b| a.0.cmp(&b.0));
    let mut lines = Vec::new();
    for (name, relation, declared) in relations {
        let program = &evaluation.program.program;
        let tableless = declared.is_some_and(|declared| gives_no_table(program.program.value(), program.form_of(relation.node), &declared));
        let kind = &evaluation.program.program.graph.nodes[relation.node.0 as usize].kind;
        let per_example = match kind {
            DependencyKind::Fact(fact) => *fact == FactRelation::Input,
            _ => scope_of(evaluation.program, &relation) == ExampleScope::PerExample,
        };
        let examples: Vec<_> = if per_example { evaluation.task.examples().map(Some).collect() } else { vec![None] };
        for example in examples {
            let input = example_name(evaluation, example);
            let at = dump.map(|dump| Dump { dump, solver, input: &input, relation: &name });
            let (counts, over) = match kind {
                DependencyKind::Fact(fact) => (evaluation.task.fact_rows(*fact, example).len().to_string(), false),
                _ => model_counts(evaluation, &relation, example, at.as_ref())?,
            };
            lines.push(format!("{input} {name} {counts}"));
            if over && matches!(kind, DependencyKind::Clause(_)) {
                for form in evaluation.program.program.forms_of(relation.node) {
                    lines.push(clause_line(evaluation, &input, &name, relation.node, form, example)?);
                }
            }
            if tableless {
                lines.push(format!("{input} {name} {NO_TABLE}"));
            }
        }
    }
    Ok(lines)
}

/// The name of an example in the output: `train/<i>`, `test/<i>`, or `task`.
fn example_name(evaluation: &Evaluation<'_>, example: Option<Example>) -> String {
    match example {
        None => "task".to_owned(),
        Some(example) => {
            let index = usize::from(example.index());
            if index < evaluation.task.train.len() { format!("train/{index}") } else { format!("test/{}", index - evaluation.task.train.len()) }
        }
    }
}

/// Where the rows of one relation on one example are written.
struct Dump<'a> {
    dump: &'a RowDump,
    solver: &'a str,
    input: &'a str,
    relation: &'a str,
}

impl Dump<'_> {
    /// Writes the rows of the model `model` to its file, or nothing where the
    /// type check gives a column of the relation no type, since `value_json`
    /// reads a row's ids at the column types.
    fn write(&self, evaluation: &Evaluation<'_>, relation: &GraphRelation, model: usize, rows: &arclog::relations::Relation) -> Result<(), String> {
        let Some(types) = evaluation.program.types.columns(relation) else { return Ok(()) };
        let mut written: Vec<(String, Value)> = Vec::new();
        each_row(rows, &mut |row| {
            let value = Value::Array(row.iter().zip(types).map(|(&id, ty)| value_json(id, ty)).collect());
            written.push((value.to_string(), value));
        });
        written.sort_by(|a, b| a.0.cmp(&b.0));
        let names = column_names(evaluation, relation, types.len());
        let file = json!({
            "solver": self.solver,
            "input": self.input,
            "relation": self.relation,
            "model": model,
            "columns": types.iter().zip(&names).map(|(ty, name)| json!({"name": name, "type": type_name(ty)})).collect::<Vec<_>>(),
            "rows": written.into_iter().map(|(_, value)| value).collect::<Vec<_>>(),
        });
        let dir = self.dump.dir.join(self.solver).join(self.input.replace('/', "-"));
        std::fs::create_dir_all(&dir).map_err(|error| format!("{}: {error}", dir.display()))?;
        let path = dir.join(format!("{}.{model}.json", self.relation));
        let text = serde_json::to_string(&file).map_err(|error| error.to_string())?;
        std::fs::write(&path, text).map_err(|error| format!("{}: {error}", path.display()))
    }
}

/// The names of the `count` columns of `relation` in a rows file: the names
/// the solver's program gives them (a record's fields as `<record>.<field>`)
/// for the one relation of a node, and `c<i>` otherwise: for one of several
/// outputs of a shared node, whose columns the program records per node, and
/// where the program's count of columns differs from `count`.
pub(crate) fn column_names(evaluation: &Evaluation<'_>, relation: &GraphRelation, count: usize) -> Vec<String> {
    let declared = match relation.output {
        None => evaluation.program.program.column_names(relation.node),
        Some(_) => None,
    };
    match declared {
        Some(names) if names.len() == count => names,
        _ => (0..count).map(|index| format!("c{index}")).collect(),
    }
}

/// The name of a column type in a rows file.
fn type_name(ty: &ValueType) -> String {
    format!("{:?}", ty.without_source())
}

/// The line of the clause at `form` of `node`: the rows of its body over
/// all its conjuncts on `example`, and the relations `node` reads.
fn clause_line(evaluation: &Evaluation<'_>, input: &str, name: &str, node: GraphNodeIndex, form: &NodePath, example: Option<Example>) -> Result<String, String> {
    let program = &evaluation.program.program;
    let Some(NodeRef::Clause(written)) = node_at(NodeRef::Program(program.program.value()), form) else { return Err("a clause node has a form that is no clause".to_owned()) };
    let kept: Vec<u32> = (0..written.body.value().conjuncts.len() as u32).collect();
    let body = evaluation.body(form, &kept, example);
    let body = match body.as_ref().map(|body| (&body.0, body)) {
        Err(_) => "fault".to_owned(),
        Ok((value, body)) => match value {
            RelationValue::Rows(_) => body.count().map_or_else(|| "undefined".to_owned(), |count| count.to_string()),
            RelationValue::Undefined => "undefined".to_owned(),
            RelationValue::Stopped(stop) => stopped(stop.bound),
        },
    };
    let mut reads = Vec::new();
    for &read in &program.graph.reads[node.0 as usize] {
        for read in names(evaluation, read, &program.graph.nodes[read.0 as usize].kind)? {
            reads.push(read.name);
        }
    }
    let reads = if reads.is_empty() { "-".to_owned() } else { reads.join(",") };
    let path = form.0.iter().map(|step| step.0.to_string()).collect::<Vec<_>>().join(".");
    Ok(format!("{input} {name} clause {path} {body} {reads}"))
}

/// Each model's count or non-row value, followed by an enumeration stop,
/// and whether `at` is given and some model holds more rows than its
/// threshold, whose rows `at` then writes, or some model stopped at a bound.
fn model_counts(evaluation: &Evaluation<'_>, relation: &GraphRelation, example: Option<Example>, at: Option<&Dump<'_>>) -> Result<(String, bool), String> {
    let mut counts = Vec::new();
    let mut over = false;
    let mut written = Ok(());
    let end = evaluation.models(relation, example, &mut |value| {
        counts.push(match value {
            RelationValue::Rows(rows) => {
                if let Some(at) = at && rows.len() > at.dump.over {
                    over = true;
                    written = at.write(evaluation, relation, counts.len(), rows);
                }
                rows.len().to_string()
            }
            RelationValue::Undefined => "undefined".to_owned(),
            RelationValue::Stopped(stop) => {
                over |= at.is_some();
                stopped(stop.bound)
            }
        });
        if written.is_err() { ControlFlow::Break(()) } else { ControlFlow::Continue(()) }
    }).map_err(|fault| format!("a fault of the run at {:?}: {}", fault.form, fault.message))?;
    written?;
    if let ModelsEnd::Stopped(stop) = end {
        over |= at.is_some();
        counts.push(stopped(stop.bound));
    }
    Ok((counts.join(","), over))
}

/// The bound as one whitespace-free output field.
fn stopped(bound: ReachedBound) -> String {
    let bound = match bound {
        ReachedBound::Bindings { cap } => format!("bindings:{cap}"),
        ReachedBound::Rows { cap } => format!("rows:{cap}"),
        ReachedBound::Models { cap } => format!("models:{cap}"),
        ReachedBound::Nodes { cap } => format!("nodes:{cap}"),
        ReachedBound::Assignments { cap } => format!("assignments:{cap}"),
        ReachedBound::TableWork { cap, .. } => format!("table-work:{cap}"),
        ReachedBound::Margin(_) => "margin".to_owned(),
        ReachedBound::RequestWork { cap } => format!("request-work:{cap}"),
        ReachedBound::RequestBytes { cap } => format!("request-bytes:{cap}"),
        ReachedBound::AssignmentBytes { cap } => format!("assignment-bytes:{cap}"),
        ReachedBound::Cancelled => "cancelled".to_owned(),
        ReachedBound::NoValues => "no-values".to_owned(),
        ReachedBound::Effort { cap } => format!("effort:{cap}"),
    };
    format!("stopped:{bound}")
}

/// A relation of a node as the output names it: its name, its path where it
/// is one of several outputs of a shared node, and the relation the program
/// declares, none for a fact.
struct Named {
    name: String,
    output: Option<Arc<[OutputStep]>>,
    declared: Option<ProgramRelation>,
}

/// Each relation of a node, including each output of a shared node.
fn names(evaluation: &Evaluation<'_>, node: GraphNodeIndex, kind: &DependencyKind) -> Result<Vec<Named>, String> {
    let declared = |declared: ProgramRelation| Ok(vec![Named { name: relation_spelled(&declared), output: None, declared: Some(declared) }]);
    match kind {
        DependencyKind::Fact(fact) => Ok(vec![Named { name: fact.spelled(), output: None, declared: None }]),
        DependencyKind::Clause(name) | DependencyKind::Parameter(name) => declared(name.clone()),
        DependencyKind::Chosen(name) | DependencyKind::Demonstrated(name) => declared(ProgramRelation::Declared(name.clone())),
        DependencyKind::InstanceInput { instance, input: port } | DependencyKind::InstanceOutput { instance, output: port } => declared(ProgramRelation::Output(OutputName { of: OutputOwner::Instance(instance.clone()), path: Arc::from([OutputStep::Port(port.clone())]) })),
        DependencyKind::Out(_) => Ok(Vec::new()),
        DependencyKind::RecursiveInstance(_) | DependencyKind::RigidAssembly(_) => {
            let program = &evaluation.program.program;
            let form = node_at(NodeRef::Program(program.program.value()), program.form_of(node)).ok_or("the graph node has no form")?;
            let (owner, paths): (_, Vec<Arc<[OutputStep]>>) = match form {
                NodeRef::Instance(instance) => {
                    let Some(LibEntry::Component(component)) = evaluation.registry.entry(&instance.component) else { return Err("the instance has no component".to_owned()) };
                    (OutputOwner::Instance(instance.name.clone()), component.outputs.iter().map(|port| Arc::from([OutputStep::Port(port.name.clone())])).collect())
                }
                NodeRef::RigidDet(rigid) => {
                    let mut paths = vec![Arc::from([OutputStep::Pose])];
                    for part in &*rigid.parts {
                        let (owner, rest): (&DeclaredName, &[OutputStep]) = match &part.value().relation {
                            RelationRef::Declared(name) => (&name.0, &[]),
                            RelationRef::Output(name) => match &name.of {
                                OutputOwner::Instance(owner) => (&owner.0, &name.path),
                                OutputOwner::RigidDet(owner) => (&owner.0, &name.path),
                            },
                            _ => return Err("a rigid part has no declared relation".to_owned()),
                        };
                        paths.push(std::iter::once(OutputStep::Part(owner.clone())).chain(rest.iter().cloned()).collect());
                    }
                    (OutputOwner::RigidDet(rigid.name.clone()), paths)
                }
                _ => return Err("a shared node has no output form".to_owned()),
            };
            paths
                .into_iter()
                .map(|path| {
                    let declared = ProgramRelation::Output(OutputName { of: owner.clone(), path: path.clone() });
                    Ok(Named { name: relation_spelled(&declared), output: Some(path), declared: Some(declared) })
                })
                .collect()
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use arclog::check::{check_program, CheckCache, SolverClauses};
    use arclog::eval::{Cancellation, Caps, Limits, ParameterValues};
    use arclog::read::read_solver;
    use arclog::registry::Registry;
    use arclog::resolver::resolve;
    use arclog::session::{SessionBound, TaskSession};
    use arclog::task::{Grid, Task, TrainPair};
    use arclog::terms::Color;

    /// The lines of `counts` for the concept case of the solver `text` on a
    /// one-pair task, under `caps`, with every relation's rows dumped.
    fn lines_of(text: &str, caps: Caps) -> Vec<String> {
        let solver = read_solver("t", text, "", &|_| None).expect("a solver").value;
        let registry = Registry::get();
        let case = solver.concept_case();
        let program = resolve(&case.program, None, &solver.derived_relations(), registry).value;
        let program = check_program(program, &SolverClauses::of(&solver, registry), registry, &mut CheckCache::default()).expect("every check passes");
        let rows = [[1, 2, 0], [2, 2, 1], [0, 3, 3]].iter().map(|row| row.iter().map(|&digit| Color::from_digit(digit).expect("a color")).collect()).collect();
        let input = Grid::from_rows(rows).expect("a grid");
        let task = Task { train: Box::new([TrainPair { input: input.clone(), output: input }]), test: Box::new([]) };
        let session = TaskSession::new(SessionBound { bytes: 1 << 26 }, caps);
        let parameters = ParameterValues::default();
        let limits = Limits::new(None, Cancellation::default());
        let constructions = arclog_constructions::shared().expect("the table of constructions");
        let evaluation = Evaluation { program: &program, concept: None, task: &task, parameters: &parameters, session: &session, registry, constructions, limits: &limits };
        let dir = std::env::temp_dir().join(format!("row-counts-{}-{}", std::process::id(), text.len()));
        let lines = counts(&evaluation, "t", Some(&RowDump { over: u64::MAX, dir: dir.clone() })).expect("counts");
        let _ = std::fs::remove_dir_all(&dir);
        lines
    }

    #[test]
    fn a_relation_that_stops_at_a_bound_is_followed_by_its_clause_lines() {
        let lines = lines_of("(RULE &big (input *P) (input (:P *Q)) (input (:P *R)))\n", Caps { bindings: 3, ..Caps::CORPUS });
        assert!(lines.iter().any(|line| line.starts_with("train/0 &big stopped:bindings:3")), "{lines:?}");
        assert!(lines.iter().any(|line| line.starts_with("train/0 &big clause ") && line.contains(" stopped:bindings:3 ")), "{lines:?}");
    }
}
