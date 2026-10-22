//! `row-counts <corpus-dir> <tasks-dir> [<task_id> ...]`: relation row
//! counts of each selected solver's concept case at its stored parameters.
//!
//! Lines are `<task_id> <example> <relation> <counts>`, ordered by task id,
//! relation name, then train and test example. Task-wide relations use
//! `task`; counts are comma-separated model values, `undefined`, or
//! `stopped:<bound>`. A solver that faults gets one fault line instead.

use std::collections::{BTreeMap, BTreeSet};
use std::ops::ControlFlow;
use std::path::Path;
use std::process::ExitCode;
use std::sync::{Arc, Mutex};

use arclog::eval::determinations::relation_spelled;
use arclog::eval::examples::{scope_of, ExampleScope};
use arclog::eval::{Evaluation, ModelsEnd, ReachedBound, RelationValue};
use arclog::harness::{require_optimized_build, run_over_corpus, SolverResult};
use arclog::program::path::{node_at, NodeRef};
use arclog::program::{DeclaredName, FactRelation, OutputName, OutputOwner, OutputStep, ProgramRelation, RelationRef};
use arclog::registry::LibEntry;
use arclog::resolver::{DependencyKind, GraphNodeIndex};
use arclog::terms::Example;
use arclog::types::GraphRelation;

use crate::concept_case::with_concept_case;

/// The subcommand on the arguments after its name.
pub fn run(args: &[String]) -> ExitCode {
    if let Err(code) = require_optimized_build() {
        return code;
    }
    let [corpus, tasks, ids @ ..] = args else {
        eprintln!("usage: arclog-cli row-counts <corpus-dir> <tasks-dir> [<task_id> ...]");
        return ExitCode::from(2);
    };
    let selected: BTreeSet<_> = ids.iter().collect();
    let lines = Mutex::new(BTreeMap::new());
    let report = run_over_corpus(Path::new(corpus), |solver| {
        if !selected.is_empty() && !selected.contains(&solver.task_id) {
            return SolverResult::Pass;
        }
        match with_concept_case(Path::new(corpus), Path::new(tasks), &solver.task_id, |case| counts(&case.evaluation)) {
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

/// The relation counts, in relation-name order and then task-file order.
fn counts(evaluation: &Evaluation<'_>) -> Result<Vec<String>, String> {
    let mut relations = Vec::new();
    for (index, node) in evaluation.program.program.graph.nodes.iter().enumerate() {
        let node_index = GraphNodeIndex(index as u32);
        for (name, output) in names(evaluation, node_index, &node.kind)? {
            relations.push((name, GraphRelation { node: node_index, output }));
        }
    }
    relations.sort_by(|a, b| a.0.cmp(&b.0));
    let mut lines = Vec::new();
    for (name, relation) in relations {
        let kind = &evaluation.program.program.graph.nodes[relation.node.0 as usize].kind;
        let per_example = match kind {
            DependencyKind::Fact(fact) => *fact == FactRelation::Input,
            _ => scope_of(evaluation.program, &relation) == ExampleScope::PerExample,
        };
        let examples: Vec<_> = if per_example { evaluation.task.examples().map(Some).collect() } else { vec![None] };
        for example in examples {
            let counts = match kind {
                DependencyKind::Fact(fact) => evaluation.task.fact_rows(*fact, example).len().to_string(),
                _ => model_counts(evaluation, &relation, example)?,
            };
            let example = match example {
                None => "task".to_owned(),
                Some(example) => {
                    let index = usize::from(example.index());
                    if index < evaluation.task.train.len() { format!("train/{index}") } else { format!("test/{}", index - evaluation.task.train.len()) }
                }
            };
            lines.push(format!("{example} {name} {counts}"));
        }
    }
    Ok(lines)
}

/// Each model's count or non-row value, followed by an enumeration stop.
fn model_counts(evaluation: &Evaluation<'_>, relation: &GraphRelation, example: Option<Example>) -> Result<String, String> {
    let mut counts = Vec::new();
    let end = evaluation.models(relation, example, &mut |value| {
        counts.push(match value {
            RelationValue::Rows(rows) => rows.len().to_string(),
            RelationValue::Undefined => "undefined".to_owned(),
            RelationValue::Stopped(stop) => stopped(stop.bound),
        });
        ControlFlow::Continue(())
    }).map_err(|fault| format!("a fault of the run at {:?}: {}", fault.form, fault.message))?;
    if let ModelsEnd::Stopped(stop) = end {
        counts.push(stopped(stop.bound));
    }
    Ok(counts.join(","))
}

/// The bound as one whitespace-free output field.
fn stopped(bound: ReachedBound) -> String {
    let bound = match bound {
        ReachedBound::Bindings { cap } => format!("bindings:{cap}"),
        ReachedBound::Rows { cap } => format!("rows:{cap}"),
        ReachedBound::Models { cap } => format!("models:{cap}"),
        ReachedBound::Nodes { cap } => format!("nodes:{cap}"),
        ReachedBound::Assignments { cap } => format!("assignments:{cap}"),
        ReachedBound::Margin(_) => "margin".to_owned(),
        ReachedBound::SessionBytes(reached) => format!("session-bytes:{}", reached.bound.bytes),
        ReachedBound::Deadline => "deadline".to_owned(),
        ReachedBound::Cancelled => "cancelled".to_owned(),
    };
    format!("stopped:{bound}")
}

type NamedOutput = (String, Option<Arc<[OutputStep]>>);

/// Each relation of a node, including each output of a shared node.
fn names(evaluation: &Evaluation<'_>, node: GraphNodeIndex, kind: &DependencyKind) -> Result<Vec<NamedOutput>, String> {
    let single = |name| Ok(vec![(name, None)]);
    match kind {
        DependencyKind::Fact(fact) => single(match fact { FactRelation::Input => "input", FactRelation::ExInput => "ex_input", FactRelation::ExOutput => "ex_output" }.to_owned()),
        DependencyKind::Clause(name) | DependencyKind::Parameter(name) => single(relation_spelled(name)),
        DependencyKind::Chosen(name) | DependencyKind::Demonstrated(name) => single(relation_spelled(&ProgramRelation::Declared(name.clone()))),
        DependencyKind::InstanceInput { instance, input: port } | DependencyKind::InstanceOutput { instance, output: port } => single(relation_spelled(&ProgramRelation::Output(OutputName { of: OutputOwner::Instance(instance.clone()), path: Arc::from([OutputStep::Port(port.clone())]) }))),
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
            paths.into_iter().map(|path| Ok((relation_spelled(&ProgramRelation::Output(OutputName { of: owner.clone(), path: path.clone() })), Some(path)))).collect()
        }
    }
}
