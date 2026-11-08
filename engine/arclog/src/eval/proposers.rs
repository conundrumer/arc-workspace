//! The rows of a proposer over an evidence, in the proposer's own column
//! order: a native proposer's from `native`, and a proposer written in
//! arclog's as the relation of a `DET` of its clause, evaluated over the
//! evidence's task as `docs/engine/determination.md#proposers` gives.

mod native;

use std::cell::RefCell;
use std::sync::{Arc, OnceLock};

use super::driver::Driver;
use super::join;
use super::{Evaluation, Outcome, ParameterValues, RelationValue, RunFault, Stop};
use crate::check::{check_program, CheckCache, CheckedProgram, SolverClauses};
use crate::diagnostic::{Diagnostic, Severity};
use crate::hash::StableHashMap;
use crate::layout::SourceFile;
use crate::program::path::NodePath;
use crate::read::{read_sexprs, read_solver, SExpr};
use crate::registry::{LibEntry, LibName, Proposer, ProposerKind, Registry, PROPOSERS_TEXT};
use crate::relations::RowSet;
use crate::task::Task;
use crate::terms::Example;
use crate::trace::RunTrace;

/// What a proposer runs on: the task of the evaluation, its train pairs
/// and its test inputs, or one of its inputs alone, with no output.
#[derive(Clone, Copy, Debug)]
pub enum Evidence {
    Task,
    Input(Example),
}

/// The rows of `proposer` over `evidence`, in the proposer's column order,
/// with a record appended to `trace` for each relation that a proposer
/// written in arclog evaluates.
/// A fault, or a stop of the evaluation of a proposer written in arclog,
/// stands at `form`, the clause that reads the rows.
pub fn rows(evaluation: &Evaluation<'_>, trace: Option<&RefCell<RunTrace>>, proposer: &LibName, evidence: Evidence, form: &NodePath) -> Outcome<RelationValue> {
    let fault = |message: String| RunFault { message: message.into(), form: form.clone() };
    let Some(LibEntry::Proposer(declaration)) = evaluation.registry.entry(proposer) else {
        return Err(fault(format!("`{}` is no proposer of the registry", proposer.0)));
    };
    let one_input;
    let task = match evidence {
        Evidence::Task => evaluation.task,
        Evidence::Input(example) => {
            one_input = Task { train: Box::new([]), test: Box::new([evaluation.task.input(example).clone()]) };
            &one_input
        }
    };
    match &declaration.kind {
        ProposerKind::Native { .. } => {
            let example = match evidence {
                Evidence::Task => None,
                Evidence::Input(example) => Some(example),
            };
            let rows = evaluation.session.native_proposer_rows(proposer, example, || {
                let grids = native::Grids {
                    inputs: task.train.iter().map(|pair| &pair.input).chain(task.test.iter()).collect(),
                    pairs: task.train.iter().map(|pair| (&pair.input, &pair.output)).collect(),
                };
                let context = native::Context { registry: evaluation.registry, session: evaluation.session };
                native::rows(&proposer.0, declaration, &grids, &context).map(join::one_part)
            });
            let rows = rows.ok_or_else(|| fault(format!("the native proposer `{}` has no port", proposer.0)))?;
            Ok(RelationValue::Rows(rows))
        }
        ProposerKind::Arclog { .. } => {
            let clause = arclog_proposers().get(proposer).ok_or_else(|| fault(format!("`{}` has no checked clause", proposer.0)))?;
            clause.rows(evaluation, trace, task, form)
        }
    }
}

/// A proposer written in arclog as a checked program of one `DET` clause,
/// its clause, and the position in that clause's rows of each of the
/// proposer's columns, in the proposer's column order.
struct ArclogProposer {
    program: CheckedProgram,
    form: NodePath,
    positions: Box<[usize]>,
}

impl ArclogProposer {
    /// The rows of the proposer over `task`, evaluated in the session of
    /// `evaluation`, each fault and stop at `form`.
    fn rows(&self, evaluation: &Evaluation<'_>, trace: Option<&RefCell<RunTrace>>, task: &Task, form: &NodePath) -> Outcome<RelationValue> {
        let parameters = ParameterValues::default();
        // The session keeps one fact relation for each fact, built from its first request, so a task other than the evaluation's reads its facts in a session of its own.
        let own;
        let session = if std::ptr::eq(task, evaluation.task) {
            evaluation.session
        } else {
            own = evaluation.session.with_own_facts();
            &own
        };
        let inner = Evaluation { program: &self.program, concept: None, task, session, parameters: &parameters, ..*evaluation };
        let value = Driver::nested(&inner, trace).clause(&self.form, None).map_err(|fault| RunFault { form: form.clone(), ..fault })?;
        Ok(match value {
            RelationValue::Rows(relation) => {
                let mut rows = RowSet::empty(self.positions.len() as u16);
                join::each_row(&relation, &mut |row| {
                    rows.insert(self.positions.iter().map(|&at| row[at]).collect());
                });
                RelationValue::Rows(Arc::new(join::one_part(rows)))
            }
            RelationValue::Stopped(stop) => RelationValue::Stopped(Stop { form: form.clone(), ..stop }),
            undefined => undefined,
        })
    }
}

/// The proposers written in arclog of [`Registry::get`], each read from its
/// clause in `engine/lib/proposers.arclog` and checked once per process.
///
/// A fault of the lib files fails the test `registry_file`, and a clause
/// that does not check is a fault of the lib, so this panics on one.
fn arclog_proposers() -> &'static StableHashMap<LibName, ArclogProposer> {
    static PROPOSERS: OnceLock<StableHashMap<LibName, ArclogProposer>> = OnceLock::new();
    PROPOSERS.get_or_init(|| {
        let registry = Registry::get();
        let (exprs, _) = read_sexprs(PROPOSERS_TEXT, SourceFile::LibProposers).expect("the proposers file reads");
        exprs.iter().map(|expr| arclog_proposer(expr, registry)).collect()
    })
}

/// The proposer of the form `expr` of the proposers file, its body the
/// body of a `DET` clause.
fn arclog_proposer(expr: &SExpr, registry: &Registry) -> (LibName, ArclogProposer) {
    let SExpr::List { items, .. } = expr else { panic!("a form of the proposers file is a list") };
    let [_, SExpr::Symbol { text: name, .. }, atoms @ ..] = &items[..] else { panic!("a proposer form names its proposer") };
    let (Some(first), Some(last)) = (atoms.first(), atoms.last()) else { panic!("the proposer `{name}` has a body") };
    let body = &PROPOSERS_TEXT[first.place().start as usize..last.place().end as usize];
    let text = format!("(DET &proposer\n  {body})\n");
    let solver = read_solver("proposers", &text, "", &|_| None).unwrap_or_else(|error| panic!("the clause of `{name}` reads: {error:?}")).value;
    let case = solver.concept_case();
    let resolved = crate::resolver::resolve(&case.program, None, &solver.derived_relations(), registry);
    let errors: Vec<&Diagnostic> = resolved.diagnostics.iter().filter(|diagnostic| diagnostic.severity == Severity::Error).collect();
    assert!(errors.is_empty(), "the resolver refuses the clause of `{name}`: {errors:?}");
    let resolved = resolved.value;
    let program = check_program(resolved, &SolverClauses::of(&solver, registry), registry, &mut CheckCache::default())
        .unwrap_or_else(|refusals| panic!("the checker refuses the clause of `{name}`: {refusals:?}"));
    let form = NodePath::top(0);
    let crate::program::Form::Clause(clause) = &program.program.program.value().forms[0] else { panic!("the program is one clause") };
    let name = LibName(name.clone());
    let Some(LibEntry::Proposer(Proposer { columns, .. })) = registry.entry(&name) else { panic!("`{}` is a proposer", name.0) };
    let positions = columns
        .iter()
        .map(|column| {
            let label = clause.value().columns.iter().find(|kept| kept.name == column.name).map(|kept| kept.label);
            let position = label.and_then(|label| program.program.label_position(&form, label));
            usize::from(position.unwrap_or_else(|| panic!("the clause of `{}` keeps its column {:?}", name.0, column.name)).0)
        })
        .collect();
    (name, ArclogProposer { program, form, positions })
}
