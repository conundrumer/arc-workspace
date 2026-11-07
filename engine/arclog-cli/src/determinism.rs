//! `determinism`: runs the corpus at one thread and at many, and compares
//! the rows and the stops at the caps of the two runs.
//!
//! Each run evaluates the concept case of each solver at its stored `param`
//! records, in one task session, with the entries of the case, each
//! relation that the `OUT` form reads on each example it holds rows on, on a
//! [`Pool`] of the run's threads. The rows of the two runs are compared
//! with Idents up to one renaming per solver, since the Ident a session
//! gives an entity depends on the order of its interning.
//!
//! Its arguments: the corpus directory, the directory of the task files,
//! the thread count of the run at many threads, then the task ids of the
//! solvers to run; every solver of the corpus where it is given none.

use std::collections::{BTreeSet, VecDeque};
use std::path::{Path, PathBuf};
use std::process::ExitCode;
use std::sync::Mutex;

use arclog::eval::examples::{scope_of, ExampleScope};
use arclog::eval::join::each_row;
use arclog::eval::pool::Pool;
use arclog::eval::{output_relation, Evaluation, RelationValue};
use arclog::hash::StableHashMap;
use arclog::harness::{print_ended, require_optimized_build, run_over_corpus, SolverResult};
use arclog::resolver::{DependencyKind, GraphNodeIndex};
use arclog::terms::{Example, Ident, Term};
use arclog::types::GraphRelation;

use crate::renaming::{renaming_exists, EngineLeaf, Leaf};
use crate::concept_case::with_concept_case;

const USAGE: &str = "usage: arclog-cli determinism <corpus-dir> <tasks-dir> <threads> [<task_id> ...]";

/// The subcommand on `args`, the arguments after its name.
pub fn run(args: &[String]) -> ExitCode {
    if let Err(code) = require_optimized_build() {
        return code;
    }
    let Some(arguments) = Arguments::parse(args) else {
        eprintln!("{USAGE}");
        return ExitCode::from(2);
    };
    let not_compared = Mutex::new(Vec::new());
    let report = run_over_corpus(&arguments.corpus, None, |solver| {
        if !arguments.task_ids.is_empty() && !arguments.task_ids.contains(&solver.task_id) {
            return SolverResult::Pass;
        }
        match compare_threads(&arguments, &solver.task_id) {
            Ok(None) => SolverResult::Pass,
            Ok(Some(line)) => SolverResult::Fail(vec![line]),
            Err(line) => {
                not_compared.lock().expect("a list that no panic poisoned").push(format!("{}: not compared: {line}", solver.task_id));
                SolverResult::Pass
            }
        }
    }, print_ended);
    let report = match report {
        Ok(report) => report,
        Err(error) => {
            eprintln!("the corpus does not read: {error:?}");
            return ExitCode::from(2);
        }
    };
    let mut not_compared = not_compared.into_inner().expect("a list that no panic poisoned");
    not_compared.sort();
    for line in &not_compared {
        println!("{line}");
    }
    let ran = if arguments.task_ids.is_empty() { report.checked } else { arguments.task_ids.len() };
    println!(
        "{} of {} solvers differ between 1 thread and {} threads or panic; {} not compared",
        report.failures.len(),
        ran - not_compared.len(),
        arguments.threads,
        not_compared.len()
    );
    if report.failures.is_empty() { ExitCode::SUCCESS } else { ExitCode::FAILURE }
}

/// The arguments of the subcommand.
struct Arguments {
    corpus: PathBuf,
    tasks: PathBuf,
    threads: usize,
    task_ids: BTreeSet<String>,
}

impl Arguments {
    fn parse(args: &[String]) -> Option<Arguments> {
        let [corpus, tasks, threads, task_ids @ ..] = args else { return None };
        let threads = threads.parse().ok().filter(|&n| n > 1)?;
        Some(Arguments { corpus: corpus.into(), tasks: tasks.into(), threads, task_ids: task_ids.iter().cloned().collect() })
    }
}

/// What an entry gives on one run: its rows, each row as its leaves, or the
/// text of its other value, `undefined`, a stop or a fault, which holds no
/// Ident.
#[derive(PartialEq, Debug)]
enum Observed {
    Rows(Vec<Vec<EngineLeaf>>),
    Other(String),
}

/// One entry of a case: a relation that the `OUT` form reads, or its own,
/// on an example or task-wide.
pub(crate) type Entry = (GraphRelation, Option<Example>);

/// The line of the first difference between the run of the solver `id` at
/// one thread and at many, `None` where the runs agree, or the fault that
/// stops the case's setup.
fn compare_threads(arguments: &Arguments, id: &str) -> Result<Option<String>, String> {
    let one = observe(&arguments.corpus, &arguments.tasks, id, 1)?;
    let many = observe(&arguments.corpus, &arguments.tasks, id, arguments.threads)?;
    Ok(first_difference(&one, &many, arguments.threads))
}

/// Each entry of the concept case of the solver `id`, with what it gives on
/// a run at `threads` threads in a session of its own.
fn observe(corpus: &Path, tasks: &Path, id: &str, threads: usize) -> Result<Vec<(String, Observed)>, String> {
    with_concept_case(corpus, tasks, id, |case| {
        let evaluation = &case.evaluation;
        let entries = entries(evaluation);
        let observed = Pool::new(Some(threads)).map(&entries, |(relation, example)| observed(evaluation, relation, *example));
        let names = entries.iter().map(|(relation, example)| {
            format!("the relation at {:?} on {example:?}", evaluation.program.program.form_of(relation.node))
        });
        Ok(names.zip(observed).collect())
    })
}

/// The entries of `evaluation`'s case: each relation of a clause that
/// `OUT` form reads, at any depth, the `OUT` form's own too, by graph order, on each
/// example of the task for a relation per example, and task-wide for
/// another.
pub(crate) fn entries(evaluation: &Evaluation<'_>) -> Vec<Entry> {
    let program = evaluation.program;
    let Some(output) = output_relation(program) else { return Vec::new() };
    let graph = &program.program.graph;
    let mut reached = BTreeSet::from([output.node.0]);
    let mut next = VecDeque::from([output.node]);
    while let Some(node) = next.pop_front() {
        for read in graph.reads[node.0 as usize].iter() {
            if reached.insert(read.0) {
                next.push_back(*read);
            }
        }
    }
    let clauses = reached.into_iter().map(GraphNodeIndex).filter(|node| matches!(graph.nodes[node.0 as usize].kind, DependencyKind::Clause(_) | DependencyKind::Out(_)));
    clauses
        .flat_map(|node| {
            let relation = GraphRelation { node, output: None };
            let examples: Vec<Option<Example>> = match scope_of(program, &relation) {
                ExampleScope::PerExample => evaluation.task.examples().map(Some).collect(),
                ExampleScope::TaskWide => vec![None],
            };
            examples.into_iter().map(move |example| (relation.clone(), example))
        })
        .collect()
}

/// What `relation` gives on `example` in `evaluation`.
fn observed(evaluation: &Evaluation<'_>, relation: &GraphRelation, example: Option<Example>) -> Observed {
    let rows = match evaluation.relation(relation, example) {
        Ok(RelationValue::Rows(rows)) => rows,
        Ok(other) => return Observed::Other(format!("{other:?}")),
        Err(fault) => return Observed::Other(format!("a fault at {:?}: {}", fault.form, fault.message)),
    };
    let Some(types) = evaluation.program.types.columns(relation) else { return Observed::Other("rows whose columns have no types".to_owned()) };
    let mut written = Vec::new();
    each_row(&rows, &mut |row| written.push(row.iter().zip(types).map(|(&id, ty)| leaf(Term::decode(id, ty))).collect()));
    Observed::Rows(written)
}

/// The leaf of `term`: an Ident as itself, and another term by its text,
/// which reads no order of interning.
fn leaf(term: Term) -> EngineLeaf {
    match term {
        Term::Ident(ident) => EngineLeaf::Ident(ident),
        other => EngineLeaf::Written(Leaf::Other(format!("{other:?}").into())),
    }
}

/// The line of the first entry whose value differs between `one` and
/// `many`, other than by its rows, or the line that no one renaming of
/// Idents maps the rows of `many` onto those of `one`; `None` where the
/// runs agree.
fn first_difference(one: &[(String, Observed)], many: &[(String, Observed)], threads: usize) -> Option<String> {
    let mut numbers: StableHashMap<Ident, i64> = StableHashMap::default();
    let mut number = |ident: Ident| {
        let next = numbers.len() as i64;
        *numbers.entry(ident).or_insert(next)
    };
    let mut relations: Vec<(BTreeSet<Vec<Leaf>>, Vec<Vec<EngineLeaf>>)> = Vec::new();
    for ((name, at_one), (_, at_many)) in one.iter().zip(many) {
        match (at_one, at_many) {
            (Observed::Rows(at_one), Observed::Rows(at_many)) => {
                let numbered = at_one
                    .iter()
                    .map(|row| {
                        row.iter()
                            .map(|leaf| match leaf {
                                EngineLeaf::Written(leaf) => leaf.clone(),
                                EngineLeaf::Ident(ident) => Leaf::Number(number(*ident)),
                            })
                            .collect()
                    })
                    .collect();
                relations.push((numbered, at_many.clone()));
            }
            _ if at_one == at_many => {}
            _ => return Some(format!("{name} gives {at_one:?} at 1 thread and {at_many:?} at {threads} threads")),
        }
    }
    let relations: Vec<(&BTreeSet<Vec<Leaf>>, Vec<Vec<EngineLeaf>>)> = relations.iter().map(|(one, many)| (one, many.clone())).collect();
    (!renaming_exists(&relations)).then(|| format!("no one renaming of Idents maps the rows at {threads} threads onto those at 1 thread"))
}
