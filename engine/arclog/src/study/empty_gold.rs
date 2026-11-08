//! Gold without empty clauses, and the singleton double-read lint.
//!
//! For each case of a task, the case program is the program that the case
//! stream reads back as. A `RULE` or `DET` clause is empty where its
//! relation has no row on each train example and each test input, at each
//! joint assignment of the `DET`s it reads and at each model. Only a
//! complete enumeration proves it: a stop at any bound, a fault, an
//! undefined value, a walk with no assignment or a model enumeration with no
//! model leaves the relation unproved.
//!
//! The edit deletes each proved-empty clause, each `NOT` atom on a relation
//! that has become empty, each `OR` branch with a positive atom on such a
//! relation, and each clause whose body then has a positive atom on such a
//! relation, until nothing changes. A relation becomes empty when each form
//! that derives it is deleted. An `OR` with a branch the edit leaves with no
//! conjunct is true, and the edit drops it where it exports no label. An `IF`
//! whose test becomes false is its else, which then makes each label the
//! `IF` exported; one whose else becomes false is the conjunction of its test
//! and its then. An `ALL` whose domain or body becomes false is false. A
//! clause whose `OR` loses branches takes as its columns the labels its body
//! then keeps, and each read of its relation names its columns by their new
//! slots. An `INIT` form whose key body becomes false is deleted, and so is
//! one with an input body that becomes false where each of its outputs is
//! proved empty; otherwise that input's clause is removed where the input
//! then has no row, and stands as it is where the component would fill an
//! input with no clause, with each deleted form that it reads through the
//! relations that have become empty, and so on, which the edit then keeps
//! as it is. A `DEMONSTRATED` form takes the edit of an `INIT` form in its
//! key clause and inputs: one whose key body becomes false is deleted, and
//! so is one with an input body that becomes false where its relation is
//! proved empty; otherwise that input's clause stands as it is. A
//! `DEMO_RULE` form that reads a relation that has become empty stands as
//! it is, with each deleted form that it reads through such relations, and
//! so on. A relation that a deleted `DEMONSTRATED` form declares becomes
//! empty. Any other read of such a relation, an `OUT` form that
//! reads one, a clause with proposers whose body becomes empty, and a
//! filtered program that the checker refuses, keep the original gold of the
//! case, with the reason. So does an `OUT` relation of the filtered program
//! that differs from the original's on an example, an assignment or a model,
//! or whose enumeration is not complete. A case whose stream does not read
//! back, or whose program has no text in the source's names, keeps the
//! original gold of the whole task, since the result has no text of that
//! case's gold.
//!
//! The lint reports, on the original program, two positive atoms of one
//! conjunction that read the same relation, bind the same columns to the same
//! labels or constants, and put different labels at some other column, where
//! the relation has exactly one row on each train example and test input, at
//! each assignment and each model. It never changes the edit.

use std::collections::{BTreeMap, BTreeSet};
use std::ops::ControlFlow;
use std::path::Path;
use std::sync::Arc;
use std::time::Duration;

use serde_json::{json, Value};

use super::StudyProgram;
use crate::check::CheckedProgram;
use crate::decode::corpus::{corpus_session, read_task_files};
use crate::decode::program_read::ProgramReader;
use crate::decode::{derived_at, relation_dets};
use crate::eval::examples::{scope_of, ExampleScope};
use crate::eval::instance::Constructions;
use crate::eval::{output_relation, relation_of, Evaluation, ModelsEnd, RelationValue};
use crate::judge::determination::{descend_assignments, Assignment, End, EvaluationInputs};
use crate::program::path::{Handle, NodePath, NodeRef};
use crate::program::{column_spelled, Atom, Body, ClauseKeyword, ColumnName, Conjunct, Constraint, ConstraintLabel, ConstraintOp, DemoRule, Demonstrated, DemonstratedPart, Form, InstanceInput, InstanceInputPart, KeyBody, KeyClause, KeyClausePart, LabelId, LabelUse, Negated, Node, OutputName, OutputOwner, OutputStep, PortName, Program, ProgramRelation, RelationName, RelationRef, RuleForms, Site, SiteArg, SiteValue};
use crate::read::columns::{made_labels, slot_columns};
use crate::registry::LibEntry;
use crate::registry::Registry;
use crate::hash::StableHashMap;
use crate::relations::Relation;
use crate::resolver::DependencyKind;
use crate::safety::body_labels;
use crate::session::{same_rows, TaskSession};
use crate::stream::corpus::{solver_streams, token_ids, WantedCases};
use crate::stream::{DecodeSettings, Emitter, Vocabulary, WrittenStream};
use crate::task::Task;
use crate::terms::Example;
use crate::types::GraphRelation;

/// The schema of the result of [`empty_gold`].
pub const SCHEMA: &str = "arclog-empty-gold-v1";

/// The result of the task `id`: the filtered gold of each case, or its
/// original gold with the reason, or the original gold of the whole task
/// with the reason, and the lint. `Err` only where the task file does not
/// read. A panic keeps the original gold of the whole task, with the panic's
/// message as the reason, and gives no case.
pub fn empty_gold(corpus: &Path, tasks: &Path, id: &str, deadline: Option<Duration>, constructions: &Constructions) -> Result<Value, String> {
    std::panic::catch_unwind(std::panic::AssertUnwindSafe(|| task_gold(corpus, tasks, id, deadline, constructions))).unwrap_or_else(|payload| {
        let reason = format!("the filter panicked: {}", crate::harness::panic_message(&*payload).unwrap_or("a payload that is not a message"));
        Ok(json!({"schema": SCHEMA, "task": id, "selection": "original", "reason": reason,
            "cases": [], "skipped_cases": [], "singleton_double_read_lint": {"status": "unavailable", "reason": reason, "findings": []}}))
    })
}

fn task_gold(corpus: &Path, tasks: &Path, id: &str, deadline: Option<Duration>, constructions: &Constructions) -> Result<Value, String> {
    let (task, _) = read_task_files(tasks, id)?;
    let registry = Registry::get();
    let program_settings = DecodeSettings::default();
    let vocabulary = Vocabulary::new(registry, &program_settings);
    let session = corpus_session();
    let evaluator = Evaluator { task: &task, session: &session, registry, constructions, settings: DecodeSettings { deadline, ..program_settings } };
    let streams = match solver_streams(corpus, id, WantedCases::Cases, &vocabulary, false) {
        Ok(streams) => streams,
        Err(fault) => {
            return Ok(json!({"schema": SCHEMA, "task": id, "selection": "original", "reason": format!("the solver gives no streams: {fault}"),
                "cases": [], "skipped_cases": [], "singleton_double_read_lint": {"status": "unavailable", "reason": "the solver gives no streams", "findings": []}}));
        }
    };
    let mut cases = Vec::new();
    let mut skipped = Vec::new();
    let mut fallback: Option<String> = None;
    let mut lint_findings = Vec::new();
    let mut lint_gap: Option<String> = None;
    for case in streams {
        let stream = match case.stream {
            Ok(stream) => stream,
            Err(fault) => {
                skipped.push(json!({"case": case.case, "reason": fault}));
                continue;
            }
        };
        let original = match read_case(&stream, &vocabulary, registry, &program_settings) {
            Ok(original) => original,
            Err(reason) => {
                fallback.get_or_insert(format!("{}: {reason}", case.case));
                lint_gap.get_or_insert(format!("{}: {reason}", case.case));
                cases.push(CaseResult::unread(&case.case, case.concept));
                continue;
            }
        };
        let names = Names::of(&stream, &original, &program_settings);
        let mut tables = Tables::default();
        match lint(&evaluator, &original, &names, &mut tables, registry) {
            Ok(found) => lint_findings.extend(found.into_iter().map(|finding| json!({"task": id, "case": case.case, "clause_index": finding.0, "relation": finding.1, "labels": [finding.2, finding.3]}))),
            Err(reason) => {
                lint_gap.get_or_insert(format!("{}: {reason}", case.case));
            }
        }
        // Once the whole task keeps its original gold, later cases skip the
        // edit.
        if fallback.is_some() {
            cases.push(CaseResult::original(&case.case, case.concept, &original, names.as_ref().ok(), registry));
            continue;
        }
        let names = match names {
            Ok(names) => names,
            Err(reason) => {
                fallback.get_or_insert(format!("{}: {reason}", case.case));
                cases.push(CaseResult::original(&case.case, case.concept, &original, None, registry));
                continue;
            }
        };
        let result = filter(&evaluator, &original, &mut tables, registry, &program_settings).and_then(|filtered| CaseResult::filtered(&case.case, case.concept, &original, filtered, &names, registry));
        match result {
            Ok(result) => cases.push(result),
            Err(reason) => match CaseResult::kept(&case.case, case.concept, &original, &names, registry, &reason) {
                Ok(result) => cases.push(result),
                Err(fault) => {
                    fallback.get_or_insert(format!("{}: {reason}; {fault}", case.case));
                    cases.push(CaseResult::original(&case.case, case.concept, &original, Some(&names), registry));
                }
            },
        }
    }
    if cases.is_empty() && fallback.is_none() {
        fallback = Some("the task has no case with a stream".into());
    }
    let selection = if fallback.is_some() { "original" } else { "filtered" };
    let cases: Vec<Value> = cases.into_iter().map(|case| if fallback.is_some() { case.as_original() } else { case.value }).collect();
    let lint = match lint_gap {
        None => json!({"status": "complete", "reason": null, "findings": lint_findings}),
        Some(reason) => json!({"status": "unavailable", "reason": reason, "findings": []}),
    };
    Ok(json!({"schema": SCHEMA, "task": id, "selection": selection, "reason": fallback, "cases": cases, "skipped_cases": skipped, "singleton_double_read_lint": lint}))
}

/// The program that `stream` reads back as, checked, whose own stream is
/// `stream`.
fn read_case(stream: &WrittenStream, vocabulary: &Vocabulary, registry: &Registry, settings: &DecodeSettings) -> Result<StudyProgram, String> {
    let (ids, model) = ids_of(stream, vocabulary);
    let program = StudyProgram::from_decoded(ProgramReader::new(registry, *settings).read(&ids, &model)?, registry)?;
    let again = program.decode_stream(registry, settings)?;
    if again.ids != ids || again.model != model {
        return Err("the case program does not write its stream back".into());
    }
    Ok(program)
}

fn ids_of(stream: &WrittenStream, vocabulary: &Vocabulary) -> (Vec<u32>, Vec<u8>) {
    token_ids(&stream.tokens, vocabulary).into_iter().map(|(id, emitter)| (id, u8::from(emitter == Emitter::Model))).unzip()
}

// ---------------------------------------------------------------- tables

/// What the complete enumeration of a relation gives.
#[derive(Clone, Debug)]
enum Coverage {
    /// Each value is rows: whether each has none, and whether each has one.
    Complete { empty: bool, singleton: bool },
    /// Why the enumeration does not prove anything.
    Incomplete(String),
}

/// The coverage of each relation of one program, by graph node and output.
#[derive(Default)]
struct Tables {
    held: StableHashMap<(u32, Option<String>), Coverage>,
}

struct Evaluator<'a> {
    task: &'a Task,
    session: &'a TaskSession,
    registry: &'a Registry,
    constructions: &'a Constructions,
    settings: DecodeSettings,
}

impl Evaluator<'_> {
    fn coverage(&self, tables: &mut Tables, program: &CheckedProgram, relation: &GraphRelation) -> Coverage {
        let key = (relation.node.0, relation.output.as_ref().map(|path| format!("{path:?}")));
        if let Some(found) = tables.held.get(&key) {
            return found.clone();
        }
        let (mut empty, mut singleton) = (true, true);
        let found = match self.walk(program, relation, &mut |_, _, rows| {
            let count = rows.len();
            empty &= count == 0;
            singleton &= count == 1;
        }) {
            Ok(()) => Coverage::Complete { empty, singleton },
            Err(reason) => Coverage::Incomplete(reason),
        };
        tables.held.insert(key, found.clone());
        found
    }

    /// Calls `visit` with the example, the assignment and the rows of each
    /// value of `relation` in `program`: on each example of its scope, at
    /// each joint assignment of the `DET`s it reads, at each model. `Err`
    /// where the enumeration is not complete.
    fn walk(&self, program: &CheckedProgram, relation: &GraphRelation, visit: &mut dyn FnMut(Option<Example>, &[Assignment], &Arc<Relation>)) -> Result<(), String> {
        let dets = relation_dets(program, relation.node);
        let examples: Vec<Option<Example>> = match scope_of(program, relation) {
            ExampleScope::PerExample => self.task.examples().map(Some).collect(),
            ExampleScope::TaskWide => vec![None],
        };
        for example in examples {
            let limits = self.settings.operation_limits();
            let inputs = EvaluationInputs { program, concept: None, task: self.task, session: self.session, registry: self.registry, constructions: self.constructions, limits: &limits };
            let mut leaves = 0usize;
            let mut problem: Option<String> = None;
            let mut leaf = |evaluation: &Evaluation<'_>, assigned: &[Assignment]| -> Result<(), End> {
                leaves += 1;
                let mut models = 0usize;
                let end = evaluation
                    .models(relation, example, &mut |value| {
                        models += 1;
                        match value {
                            RelationValue::Rows(rows) => {
                                visit(example, assigned, rows);
                                ControlFlow::Continue(())
                            }
                            RelationValue::Undefined => {
                                problem.get_or_insert_with(|| "a value is undefined".into());
                                ControlFlow::Break(())
                            }
                            RelationValue::Stopped(stop) => {
                                problem.get_or_insert_with(|| format!("a value stops at {:?}", stop.bound));
                                ControlFlow::Break(())
                            }
                        }
                    })
                    .map_err(End::Fault)?;
                if let ModelsEnd::Stopped(stop) = end {
                    return Err(End::Stop(stop));
                }
                if models == 0 {
                    problem.get_or_insert_with(|| "an assignment has no model".into());
                }
                if problem.is_some() { Err(End::Fault(crate::eval::RunFault { message: "incomplete".into(), form: NodePath::default() })) } else { Ok(()) }
            };
            let (_, end, stop) = descend_assignments(inputs, &dets, relation.node, self.settings.caps.assignments, &mut leaf);
            if let Some(problem) = problem {
                return Err(problem);
            }
            let end = end.and_then(|()| stop.map_or(Ok(()), |stop| Err(End::Stop(stop))));
            match end {
                Ok(()) => {}
                Err(End::Stop(stop)) => return Err(format!("the enumeration stops at {:?}", stop.bound)),
                Err(End::Fault(fault)) => return Err(format!("a fault: {}", fault.message)),
            }
            if leaves == 0 {
                return Err("the walk gives no DET assignment".into());
            }
        }
        Ok(())
    }

    /// Each value of `relation` in `program`, grouped by example and
    /// assignment, with the values of each assignment in model order.
    fn values(&self, program: &CheckedProgram, relation: &GraphRelation) -> Result<Vec<(Option<Example>, Vec<Assignment>, Vec<Arc<Relation>>)>, String> {
        let mut found: Vec<(Option<Example>, Vec<Assignment>, Vec<Arc<Relation>>)> = Vec::new();
        self.walk(program, relation, &mut |example, assigned, rows| {
            let same = found.last().is_some_and(|(at, values, _)| *at == example && values.len() == assigned.len() && values.iter().zip(assigned).all(|(a, b)| a.0 == b.0 && Arc::ptr_eq(&a.1, &b.1)));
            if !same {
                found.push((example, assigned.to_vec(), Vec::new()));
            }
            found.last_mut().expect("a group").2.push(Arc::clone(rows));
        })?;
        Ok(found)
    }
}

// ---------------------------------------------------------------- the edit

/// The relations that have become empty.
type Empty = crate::hash::StableHashSet<ProgramRelation>;

const EMPTY: &str = "empty";
const READS_EMPTY: &str = "reads an empty relation";

/// The filtered program of a case, with the reason of each deleted form and
/// the indexes of the edited forms.
struct Filtered {
    /// The filtered program as its stream reads back.
    program: StudyProgram,
    /// The filtered program with the relation names of the original.
    edit: StudyProgram,
    deleted: BTreeMap<usize, &'static str>,
    edited: BTreeSet<usize>,
}

fn filter(evaluator: &Evaluator<'_>, original: &StudyProgram, tables: &mut Tables, registry: &Registry, settings: &DecodeSettings) -> Result<Filtered, String> {
    let checked = original.checked();
    let forms = &original.program().value().forms;
    // The forms that stand as they are, since an input clause that the edit
    // keeps reads them.
    let mut pinned: BTreeSet<usize> = BTreeSet::new();
    let (deleted, plan) = 'run: loop {
        let mut deleted: BTreeMap<usize, &'static str> = BTreeMap::new();
        for (index, form) in forms.iter().enumerate() {
            let Form::Clause(clause) = form else { continue };
            if !matches!(clause.value().keyword, ClauseKeyword::Rule | ClauseKeyword::Det) || pinned.contains(&index) {
                continue;
            }
            let relation = derived_at(checked, &NodePath::top(index as u32));
            if let Coverage::Complete { empty: true, .. } = evaluator.coverage(tables, checked, &relation) {
                deleted.insert(index, EMPTY);
            }
        }
        let plan = loop {
            let empty = emptied(checked, &deleted);
            let mut added = false;
            let mut plan = Plan::default();
            for (index, form) in forms.iter().enumerate() {
                if deleted.contains_key(&index) || !mentions(NodeRef::from(form), &empty) {
                    continue;
                }
                let at = NodePath::top(index as u32);
                match form {
                    Form::Out(_) => return Err(format!("the OUT form, form {index}, reads a relation that is empty on every input, so the case's output is empty")),
                    Form::Instance(_) | Form::Demonstrated(_) => match edit_keyed(evaluator, tables, checked, registry, form, &at, &empty).map_err(|reason| format!("form {index}: {reason}"))? {
                        InstanceEdit::Delete(reason) => {
                            deleted.insert(index, reason);
                            added = true;
                        }
                        InstanceEdit::Keep { bodies, inputs } => {
                            plan.bodies.extend(bodies);
                            if !inputs.is_empty() {
                                plan.inputs.insert(index, inputs);
                            }
                            plan.edited.insert(index);
                        }
                        InstanceEdit::Pin(relations) => {
                            let more = pins(checked, forms, relations, &empty, &deleted);
                            if more.is_subset(&pinned) {
                                return Err(format!("form {index}: an input clause that the edit keeps reads an empty relation that no deleted form derives"));
                            }
                            pinned.extend(more);
                            continue 'run;
                        }
                    },
                    _ => {
                        let mut bodies = Vec::new();
                        let mut parts = Vec::new();
                        root_bodies(NodeRef::from(form), &at, &mut bodies, &mut parts);
                        if parts.iter().any(|atom| reads(&atom.relation, &empty)) {
                            return Err(format!("a RIGID_DET part of form {index} reads an empty relation"));
                        }
                        for (path, body) in bodies {
                            match rewrite(body.value(), &empty).map_err(|reason| format!("form {index}: {reason}"))? {
                                Rewritten::Same => {}
                                Rewritten::Changed(conjuncts) => {
                                    plan.bodies.push((path, Node::new(Body { conjuncts: conjuncts.into() })));
                                    plan.edited.insert(index);
                                }
                                Rewritten::Empty => {
                                    let deletable = match form {
                                        Form::Clause(clause) => matches!(clause.value().keyword, ClauseKeyword::Rule | ClauseKeyword::Det) && clause.value().proposers.is_empty() && path == at.child(0),
                                        _ => false,
                                    };
                                    if !deletable {
                                        return Err(format!("form {index} reads an empty relation where no deletion is supported"));
                                    }
                                    deleted.insert(index, READS_EMPTY);
                                    added = true;
                                }
                            }
                        }
                    }
                }
            }
            if !added {
                break plan;
            }
        };
        break (deleted, plan);
    };
    let edited: BTreeSet<usize> = plan.edited.iter().copied().filter(|index| !deleted.contains_key(index)).collect();
    if deleted.is_empty() && edited.is_empty() {
        return Ok(Filtered { program: original.clone(), edit: original.clone(), deleted, edited });
    }
    let mut program = original.program().clone();
    for (at, body) in &plan.bodies {
        program = crate::mutation::edit::replace_body(&program, at, body)?;
    }
    let mut forms: Vec<Form> = program.value().forms.to_vec();
    for (index, inputs) in &plan.inputs {
        forms[*index] = without_inputs(&forms[*index], inputs);
    }
    let moved = take_columns(&mut forms, &edited)?;
    if !moved.is_empty() {
        for form in &mut forms {
            *form = remap_form(form, &moved)?;
        }
    }
    let kept: Vec<Form> = forms.into_iter().enumerate().filter(|(index, _)| !deleted.contains_key(index)).map(|(_, form)| form).collect();
    let edit = StudyProgram::from_decoded(Node::new(Program { forms: kept.into() }), registry).map_err(|fault| format!("the checker refuses the filtered program: {fault}"))?;
    compare_out(evaluator, original, &edit)?;
    // The program the filtered stream reads back as: the slots of its
    // relations are those of any later read of that stream.
    let stream = edit.decode_stream(registry, settings).map_err(|fault| format!("the filtered program writes no stream: {fault}"))?;
    let program = StudyProgram::from_decoded(ProgramReader::new(registry, *settings).read(&stream.ids, &stream.model)?, registry)?;
    let again = program.decode_stream(registry, settings)?;
    if again.ids != stream.ids || again.model != stream.model {
        return Err("the filtered program does not read back to its stream".into());
    }
    // The order of the forms in the stream, by their index in `edit`.
    let written = edit.written_stream(registry, settings).map_err(|fault| fault.message.to_string())?;
    let order: Vec<usize> = written.forms.iter().map(|form| form.path.0.first().map_or(usize::MAX, |step| step.0 as usize)).collect();
    if order.len() != program.program().value().forms.len() || order.iter().enumerate().any(|(at, index)| at != *index) {
        return Err("the stream writes the filtered forms in another order".into());
    }
    Ok(Filtered { program, edit, deleted, edited })
}

/// What the edit does to the forms it keeps.
#[derive(Default)]
struct Plan {
    /// Each body the edit replaces, by its path.
    bodies: Vec<(NodePath, Node<Body>)>,
    /// The inputs of an instance whose clauses the edit removes, by the
    /// index of the `INIT` form.
    inputs: BTreeMap<usize, Vec<PortName>>,
    /// The forms the edit changes.
    edited: BTreeSet<usize>,
}

enum InstanceEdit {
    /// The instance's outputs are empty, for the reason given.
    Delete(&'static str),
    /// The bodies the edit replaces, and the inputs whose clauses it
    /// removes.
    Keep { bodies: Vec<(NodePath, Node<Body>)>, inputs: Vec<PortName> },
    /// The relations of the empty set that the parts which stand as they
    /// are read.
    Pin(Vec<ProgramRelation>),
}

/// The edit of the `INIT` form `instance` at `at`, one of whose bodies reads
/// a relation of `empty`. A key body that becomes false gives no key, and
/// each output of a keyed instance is empty at a key it does not have. An
/// input body that becomes false gives the input no row: the instance is
/// deleted where each of its outputs is proved empty in the original
/// program. Otherwise the input's clause is removed where the component
/// gives the input no default row, does not fill it from the key and does
/// not fill it from its outputs, since an input with no clause and no
/// default has no row; where the component fills it, the input's clause
/// stands as it is, which [`InstanceEdit::Pin`] gives.
fn edit_instance(evaluator: &Evaluator<'_>, tables: &mut Tables, checked: &CheckedProgram, registry: &Registry, instance: &crate::program::Instance, at: &NodePath, empty: &Empty) -> Result<InstanceEdit, String> {
    let mut bodies = Vec::new();
    let mut inputs: Vec<(NodePath, &Node<InstanceInput>)> = Vec::new();
    if let Some(key) = &instance.key {
        let clause = at.child(0);
        match rewrite(key.value().key.body.value(), empty)? {
            Rewritten::Same => {}
            Rewritten::Empty => return Ok(InstanceEdit::Delete(READS_EMPTY)),
            Rewritten::Changed(conjuncts) => bodies.push((clause.child(0), Node::new(Body { conjuncts: conjuncts.into() }))),
        }
        inputs.extend(key.value().inputs.iter().enumerate().map(|(index, input)| (clause.child(1 + index as u32), input)));
    }
    let first = u32::from(instance.key.is_some());
    inputs.extend(instance.inputs.iter().enumerate().map(|(index, input)| (at.child(first + index as u32), input)));
    let mut falsified = Vec::new();
    let mut false_bodies = Vec::new();
    for (path, input) in inputs {
        let input = input.value();
        match rewrite(input.body.value(), empty)? {
            Rewritten::Same => {}
            Rewritten::Empty => {
                falsified.push(input.name.clone());
                false_bodies.push(input.body.clone());
            }
            Rewritten::Changed(conjuncts) => bodies.push((path.child(input.head.len() as u32), Node::new(Body { conjuncts: conjuncts.into() }))),
        }
    }
    if falsified.is_empty() {
        return Ok(InstanceEdit::Keep { bodies, inputs: falsified });
    }
    if outputs_empty(evaluator, tables, checked, at) {
        return Ok(InstanceEdit::Delete(EMPTY));
    }
    let Some(LibEntry::Component(component)) = registry.entry(&instance.component) else {
        return Err("the instance's component is not in the lib".into());
    };
    let mut kept = Vec::new();
    for (name, body) in falsified.iter().zip(false_bodies) {
        let port = component.inputs.iter().find(|port| port.port.name == *name).ok_or("an input that the component does not declare")?;
        if port.default.is_some() || port.from_key || port.reads_outputs {
            empty_reads(NodeRef::Body(body.value()), empty, &mut kept);
        }
    }
    if !kept.is_empty() {
        return Ok(InstanceEdit::Pin(kept));
    }
    Ok(InstanceEdit::Keep { bodies, inputs: falsified })
}

/// The edit of `form`, an `INIT` or a `DEMONSTRATED` form at `at`.
fn edit_keyed(evaluator: &Evaluator<'_>, tables: &mut Tables, checked: &CheckedProgram, registry: &Registry, form: &Form, at: &NodePath, empty: &Empty) -> Result<InstanceEdit, String> {
    match form {
        Form::Instance(instance) => edit_instance(evaluator, tables, checked, registry, instance.value(), at, empty),
        Form::Demonstrated(demonstrated) => edit_demonstrated(evaluator, tables, checked, demonstrated.value(), at, empty),
        _ => unreachable!("an INIT or a DEMONSTRATED form"),
    }
}

/// The edit of the `DEMONSTRATED` form `demonstrated` at `at`, one of whose
/// parts reads a relation of `empty`. Its key clause and inputs take the
/// edit of an instance's: a key body that becomes false gives no key, so
/// the form's relation is empty and the form is deleted, and an input body
/// that becomes false deletes the form where its relation is proved empty
/// in the original program. Otherwise that input's clause stands as it is,
/// and so does each `DEMO_RULE` form that reads a relation of `empty`, which
/// [`InstanceEdit::Pin`] gives.
fn edit_demonstrated(evaluator: &Evaluator<'_>, tables: &mut Tables, checked: &CheckedProgram, demonstrated: &Demonstrated, at: &NodePath, empty: &Empty) -> Result<InstanceEdit, String> {
    let mut bodies = Vec::new();
    let mut inputs: Vec<(NodePath, &Node<InstanceInput>)> = Vec::new();
    if let Some(key) = &demonstrated.key {
        let clause = at.child(demonstrated.position(DemonstratedPart::Key));
        match rewrite(key.value().key.body.value(), empty)? {
            Rewritten::Same => {}
            Rewritten::Empty => return Ok(InstanceEdit::Delete(READS_EMPTY)),
            Rewritten::Changed(conjuncts) => bodies.push((clause.child(0), Node::new(Body { conjuncts: conjuncts.into() }))),
        }
        inputs.extend(key.value().inputs.iter().enumerate().map(|(index, input)| (clause.child(key.value().position(KeyClausePart::Input(index))), input)));
    }
    inputs.extend(demonstrated.inputs.iter().enumerate().map(|(index, input)| (at.child(demonstrated.position(DemonstratedPart::Input(index))), input)));
    let mut kept = Vec::new();
    for (path, input) in inputs {
        let input = input.value();
        match rewrite(input.body.value(), empty)? {
            Rewritten::Same => {}
            Rewritten::Empty if demonstrated_empty(evaluator, tables, checked, at) => return Ok(InstanceEdit::Delete(EMPTY)),
            Rewritten::Empty => empty_reads(NodeRef::Body(input.body.value()), empty, &mut kept),
            Rewritten::Changed(conjuncts) => bodies.push((path.child(input.position(InstanceInputPart::Body)), Node::new(Body { conjuncts: conjuncts.into() }))),
        }
    }
    for rule in demonstrated.rules.iter() {
        empty_reads(NodeRef::DemoRule(rule.value()), empty, &mut kept);
    }
    if !kept.is_empty() {
        return Ok(InstanceEdit::Pin(kept));
    }
    Ok(InstanceEdit::Keep { bodies, inputs: Vec::new() })
}

/// Whether the relation of the `DEMONSTRATED` form at `at` is proved empty.
fn demonstrated_empty(evaluator: &Evaluator<'_>, tables: &mut Tables, checked: &CheckedProgram, at: &NodePath) -> bool {
    let resolved = &checked.program;
    let nodes: Vec<_> = resolved.nodes_of(at).iter().copied().filter(|node| matches!(resolved.graph.nodes[node.0 as usize].kind, DependencyKind::Demonstrated(_))).collect();
    !nodes.is_empty() && nodes.into_iter().all(|node| matches!(evaluator.coverage(tables, checked, &GraphRelation { node, output: None }), Coverage::Complete { empty: true, .. }))
}

/// Whether each output of the instance at `at` that the program reads is
/// proved empty.
fn outputs_empty(evaluator: &Evaluator<'_>, tables: &mut Tables, checked: &CheckedProgram, at: &NodePath) -> bool {
    let resolved = &checked.program;
    resolved.nodes_of(at).iter().all(|&node| match &resolved.graph.nodes[node.0 as usize].kind {
        DependencyKind::InstanceOutput { .. } => matches!(evaluator.coverage(tables, checked, &GraphRelation { node, output: None }), Coverage::Complete { empty: true, .. }),
        DependencyKind::InstanceInput { .. } => true,
        _ => false,
    })
}

/// The deleted forms that derive `relations`, relations of `empty`, and so
/// on through the reads of those forms.
fn pins(checked: &CheckedProgram, forms: &[Form], mut relations: Vec<ProgramRelation>, empty: &Empty, deleted: &BTreeMap<usize, &'static str>) -> BTreeSet<usize> {
    let resolved = &checked.program;
    let mut found = BTreeSet::new();
    while let Some(relation) = relations.pop() {
        for (index, node) in resolved.graph.nodes.iter().enumerate() {
            if node_relation(&node.kind).as_ref() != Some(&relation) {
                continue;
            }
            for at in resolved.forms_of(crate::resolver::GraphNodeIndex(index as u32)) {
                let Some(step) = at.0.first() else { continue };
                let form = step.0 as usize;
                if deleted.contains_key(&form) && found.insert(form) {
                    empty_reads(NodeRef::from(&forms[form]), empty, &mut relations);
                }
            }
        }
    }
    found
}

/// Pushes onto `out` each relation of `empty` that an atom at or below
/// `node` reads.
fn empty_reads(node: NodeRef<'_>, empty: &Empty, out: &mut Vec<ProgramRelation>) {
    if let Some(atom) = node.atom() {
        let relation = match &atom.relation {
            RelationRef::Declared(name) => Some(ProgramRelation::Declared(name.clone())),
            RelationRef::Output(name) => Some(ProgramRelation::Output(name.clone())),
            _ => None,
        };
        out.extend(relation.filter(|relation| empty.contains(relation)));
    }
    for child in node.children() {
        empty_reads(child, empty, out);
    }
}

/// The relation that a graph node of kind `kind` gives, where it gives one.
fn node_relation(kind: &DependencyKind) -> Option<ProgramRelation> {
    Some(match kind {
        DependencyKind::Clause(relation) | DependencyKind::Parameter(relation) => relation.clone(),
        DependencyKind::Chosen(name) | DependencyKind::Demonstrated(name) => ProgramRelation::Declared(name.clone()),
        DependencyKind::InstanceOutput { instance, output } => ProgramRelation::Output(OutputName { of: OutputOwner::Instance(instance.clone()), path: Arc::from([OutputStep::Port(output.clone())]) }),
        _ => return None,
    })
}

/// `form`, an `INIT` form, without the clauses of the inputs `names`.
fn without_inputs(form: &Form, names: &[PortName]) -> Form {
    let Form::Instance(instance) = form else { return form.clone() };
    let instance = instance.value();
    let kept = |inputs: &[Node<InstanceInput>]| -> Arc<[Node<InstanceInput>]> { inputs.iter().filter(|input| !names.contains(&input.value().name)).cloned().collect() };
    let key = instance.key.as_ref().map(|key| Node::new(KeyClause { key: key.value().key.clone(), inputs: kept(&key.value().inputs) }));
    Form::Instance(Node::new(crate::program::Instance { key, inputs: kept(&instance.inputs), ..instance.clone() }))
}

/// The new slot of each old column of a relation whose clause takes new
/// columns.
type Moved = Vec<(RelationName, Vec<u32>)>;

/// Gives each edited clause of `forms` whose body keeps other labels than
/// its columns' the columns of its body. An `OR` that loses a branch keeps
/// each label it exported, and may export more: the labels its remaining
/// branches all name. Each such label becomes a column, which each read of
/// the relation projects away, since a read names the columns it reads. `Err`
/// where a column would be dropped, or where the clause has `ONE` marks,
/// whose models the new columns would change.
fn take_columns(forms: &mut [Form], edited: &BTreeSet<usize>) -> Result<Moved, String> {
    let mut moved = Vec::new();
    for &index in edited {
        let Form::Clause(clause) = &forms[index] else { continue };
        let clause = clause.value();
        let made = made_labels(clause.body.value());
        let old: Vec<LabelId> = clause.columns.iter().map(|column| column.label).collect();
        if made == old {
            continue;
        }
        if !clause.ones.is_empty() {
            return Err(format!("form {index}: the edit changes the columns of a clause with ONE marks"));
        }
        let ProgramRelation::Declared(name) = &clause.derives else {
            return Err(format!("form {index}: the edit changes the columns of an output's clause"));
        };
        if clause.columns.iter().enumerate().any(|(slot, column)| column.name != ColumnName::Slot(slot as u32)) {
            return Err(format!("form {index}: a column of the clause is not named by its slot"));
        }
        let slots: Option<Vec<u32>> = old.iter().map(|label| made.iter().position(|own| own == label).map(|slot| slot as u32)).collect();
        let slots = slots.ok_or_else(|| format!("form {index}: the edit drops a column of the clause"))?;
        moved.push((name.clone(), slots));
        forms[index] = Form::Clause(Node::new(crate::program::Clause { columns: slot_columns(made, 0), ..clause.clone() }));
    }
    Ok(moved)
}

/// `form` with each read of a relation of `moved` naming its columns by
/// their new slots.
fn remap_form(form: &Form, moved: &Moved) -> Result<Form, String> {
    let touched = |node: NodeRef<'_>| moved.iter().any(|(name, _)| reads_named(node, name));
    if !touched(NodeRef::from(form)) {
        return Ok(form.clone());
    }
    let atom = |atom: &Node<Atom>| remap_atom(atom, moved);
    let key = |key: &KeyBody| KeyBody { body: map_body(&key.body, &atom), columns: key.columns.clone() };
    let input = |input: &Node<InstanceInput>| {
        let input = input.value();
        Node::new(InstanceInput { name: input.name.clone(), head: input.head.clone(), body: map_body(&input.body, &atom) })
    };
    Ok(match form {
        Form::Clause(clause) => Form::Clause(Node::new(crate::program::Clause { body: map_body(&clause.value().body, &atom), ..clause.value().clone() })),
        Form::Instance(instance) => {
            let instance = instance.value();
            let clause = instance.key.as_ref().map(|clause| Node::new(KeyClause { key: key(&clause.value().key), inputs: clause.value().inputs.iter().map(input).collect() }));
            Form::Instance(Node::new(crate::program::Instance { key: clause, inputs: instance.inputs.iter().map(input).collect(), ..instance.clone() }))
        }
        Form::Out(out) => Form::Out(Node::new(crate::program::Out { key: key(&out.value().key) })),
        Form::Choose(choose) => {
            let choose = choose.value();
            Form::Choose(Node::new(crate::program::Choose {
                rows: choose.rows.as_ref().map(key),
                from: map_body(&choose.from, &atom),
                never: choose.never.iter().map(|body| map_body(body, &atom)).collect(),
                ..choose.clone()
            }))
        }
        Form::Demonstrated(demonstrated) => {
            let demonstrated = demonstrated.value();
            let clause = demonstrated.key.as_ref().map(|clause| Node::new(KeyClause { key: key(&clause.value().key), inputs: clause.value().inputs.iter().map(input).collect() }));
            let rule = |rule: &Node<DemoRule>| -> Result<Node<DemoRule>, String> {
                let rule = rule.value();
                let forms = rule.forms.iter().enumerate().map(|(index, form)| Ok((remap_form(form, moved)?, rule.forms.from_alt(index)))).collect::<Result<RuleForms, String>>()?;
                Ok(Node::new(DemoRule { forms, ..rule.clone() }))
            };
            let rules = demonstrated.rules.iter().map(rule).collect::<Result<_, String>>()?;
            Form::Demonstrated(Node::new(Demonstrated { key: clause, inputs: demonstrated.inputs.iter().map(input).collect(), rules, ..demonstrated.clone() }))
        }
        _ => return Err("a form of a kind the edit does not rewrite reads a relation whose columns change".into()),
    })
}

/// Whether an atom at or below `node` reads the relation `name`.
fn reads_named(node: NodeRef<'_>, name: &RelationName) -> bool {
    node.atom().is_some_and(|atom| matches!(&atom.relation, RelationRef::Declared(own) if own == name)) || node.children().into_iter().any(|child| reads_named(child, name))
}

fn remap_atom(atom: &Node<Atom>, moved: &Moved) -> Node<Atom> {
    let RelationRef::Declared(name) = &atom.value().relation else { return atom.clone() };
    let Some((_, slots)) = moved.iter().find(|(own, _)| own == name) else { return atom.clone() };
    let site = |site: &Site| match &site.column {
        ColumnName::Slot(slot) => Site { column: ColumnName::Slot(slots.get(*slot as usize).copied().unwrap_or(*slot)), value: site.value.clone() },
        ColumnName::Written(_) => site.clone(),
    };
    Node::new(Atom { relation: atom.value().relation.clone(), sites: atom.value().sites.iter().map(site).collect() })
}

/// `body` with `atom` applied to each atom at or below it.
fn map_body(body: &Node<Body>, atom: &dyn Fn(&Node<Atom>) -> Node<Atom>) -> Node<Body> {
    Node::new(Body { conjuncts: body.value().conjuncts.iter().map(|conjunct| map_conjunct(conjunct, atom)).collect() })
}

fn map_conjunct(conjunct: &Conjunct, atom: &dyn Fn(&Node<Atom>) -> Node<Atom>) -> Conjunct {
    match conjunct {
        Conjunct::Atom(own) => Conjunct::Atom(atom(own)),
        Conjunct::Not(Negated::Atom(own)) => Conjunct::Not(Negated::Atom(atom(own))),
        Conjunct::Not(Negated::Form(form)) => Conjunct::Not(Negated::Form(Arc::new(map_conjunct(form, atom)))),
        Conjunct::Constraint(_) => conjunct.clone(),
        Conjunct::Or(branches) => Conjunct::Or(branches.iter().map(|branch| map_body(branch, atom)).collect()),
        Conjunct::If { test, then, otherwise } => Conjunct::If { test: map_body(test, atom), then: map_body(then, atom), otherwise: map_body(otherwise, atom) },
        Conjunct::All { domain, body } => Conjunct::All { domain: map_body(domain, atom), body: map_body(body, atom) },
    }
}

/// The relations that have become empty: each relation of the graph each of
/// whose forms is in `deleted`, where no other node of the graph gives it.
fn emptied(checked: &CheckedProgram, deleted: &BTreeMap<usize, &'static str>) -> Empty {
    let resolved = &checked.program;
    let mut empty = Empty::default();
    let mut live = Empty::default();
    for (index, node) in resolved.graph.nodes.iter().enumerate() {
        let Some(relation) = node_relation(&node.kind) else { continue };
        let forms = resolved.forms_of(crate::resolver::GraphNodeIndex(index as u32));
        if !forms.is_empty() && forms.iter().all(|at| at.0.len() == 1 && deleted.contains_key(&(at.0[0].0 as usize))) {
            empty.insert(relation);
        } else {
            live.insert(relation);
        }
    }
    empty.retain(|relation| !live.contains(relation));
    empty
}

fn reads(relation: &RelationRef, empty: &Empty) -> bool {
    match relation {
        RelationRef::Declared(name) => empty.contains(&ProgramRelation::Declared(name.clone())),
        RelationRef::Output(name) => empty.contains(&ProgramRelation::Output(name.clone())),
        _ => false,
    }
}

/// Whether an atom at or below `node` reads a relation of `empty`.
fn mentions(node: NodeRef<'_>, empty: &Empty) -> bool {
    node.atom().is_some_and(|atom| reads(&atom.relation, empty)) || node.children().into_iter().any(|child| mentions(child, empty))
}

/// The bodies that a form holds outside any conjunct, with their paths, and
/// the parts of a `RIGID_DET` form.
fn root_bodies<'a>(node: NodeRef<'a>, at: &NodePath, bodies: &mut Vec<(NodePath, &'a Node<Body>)>, parts: &mut Vec<&'a crate::program::Atom>) {
    for (index, handle) in node.handles().into_iter().enumerate() {
        let child = at.child(index as u32);
        match handle {
            Handle::Body(body) => bodies.push((child, body)),
            Handle::Atom(atom) => parts.push(atom.value()),
            Handle::Site(_) | Handle::Arg(_) => {}
            other => root_bodies(other.node(), &child, bodies, parts),
        }
    }
}

enum Rewritten {
    Same,
    /// The body is false.
    Empty,
    /// The body's new conjuncts. None is a true body.
    Changed(Vec<Conjunct>),
}

/// `body` with the empty relations of `empty` taken out, or why the edit
/// does not support it.
///
/// A positive atom on an empty relation makes its body false, and a `NOT`
/// of it is true, so the edit drops it. An `OR` drops each false branch; it
/// is false with none left. A branch left with no conjunct is true, so the
/// `OR` is true where it exports no label, and the edit drops the `OR`; an
/// `OR` that exports a label keeps that label free in a true branch, which
/// the edit does not support. An `OR` left with one branch is that branch's
/// conjuncts. Where the first branch is dropped, the new first branch makes
/// each label the `OR` exported, at its first site in a positive atom of
/// the branch's own list or at the first label of a `=` there: every later
/// branch named it, so each remaining branch still does. An `IF` takes the
/// edit of [`rewrite_if`]. An `ALL` whose domain or body becomes false is
/// false.
fn rewrite(body: &Body, empty: &Empty) -> Result<Rewritten, String> {
    let mut kept: Vec<Conjunct> = Vec::new();
    let mut changed = false;
    for conjunct in body.conjuncts.iter() {
        match conjunct {
            Conjunct::Atom(atom) if reads(&atom.value().relation, empty) => return Ok(Rewritten::Empty),
            Conjunct::Not(Negated::Atom(atom)) if reads(&atom.value().relation, empty) => changed = true,
            Conjunct::Not(Negated::Form(form)) if mentions(NodeRef::Conjunct(form), empty) => {
                match rewrite(&Body { conjuncts: Arc::from([(**form).clone()]) }, empty)? {
                    Rewritten::Same => kept.push(conjunct.clone()),
                    // NOT over a false form is true.
                    Rewritten::Empty => changed = true,
                    Rewritten::Changed(inner) => match <[Conjunct; 1]>::try_from(inner) {
                        Ok([inner]) => {
                            kept.push(Conjunct::Not(Negated::Form(Arc::new(inner))));
                            changed = true;
                        }
                        // NOT over a true form is false.
                        Err(inner) if inner.is_empty() => return Ok(Rewritten::Empty),
                        Err(_) => return Err("a NOT over a form whose edit gives several conjuncts".into()),
                    },
                }
            }
            Conjunct::Or(branches) if branches.iter().any(|branch| mentions(NodeRef::Body(branch.value()), empty)) => {
                let exported = made_labels(&Body { conjuncts: Arc::from([conjunct.clone()]) });
                let mut left: Vec<(usize, Node<Body>)> = Vec::new();
                let mut true_branch = false;
                for (index, branch) in branches.iter().enumerate() {
                    match rewrite(branch.value(), empty)? {
                        Rewritten::Same => left.push((index, branch.clone())),
                        Rewritten::Empty => {}
                        Rewritten::Changed(inner) if inner.is_empty() => true_branch = true,
                        Rewritten::Changed(inner) => left.push((index, Node::new(Body { conjuncts: inner.into() }))),
                    }
                }
                changed = true;
                if true_branch {
                    if !exported.is_empty() {
                        return Err("an OR that exports a label has a branch whose edit leaves no conjunct".into());
                    }
                    continue;
                }
                let Some((first, _)) = left.first() else { return Ok(Rewritten::Empty) };
                if *first != 0 {
                    let mut branch = left[0].1.value().clone();
                    for &label in &exported {
                        if !made_labels(&branch).contains(&label) {
                            branch = make_label(&branch, label).ok_or("an OR whose new first branch has no site that can make a label the OR exports")?;
                        }
                    }
                    left[0].1 = Node::new(branch);
                }
                match left.len() {
                    1 => kept.extend(left[0].1.value().conjuncts.iter().cloned()),
                    _ => kept.push(Conjunct::Or(left.into_iter().map(|(_, branch)| branch).collect())),
                }
            }
            Conjunct::If { test, then, otherwise } if mentions(NodeRef::Conjunct(conjunct), empty) => {
                changed = true;
                match rewrite_if(conjunct, test, then, otherwise, empty)? {
                    Some(conjuncts) => kept.extend(conjuncts),
                    None => return Ok(Rewritten::Empty),
                }
            }
            Conjunct::All { domain, body: each } if mentions(NodeRef::Conjunct(conjunct), empty) => {
                // An ALL with a false domain has no member, and one with a
                // false body fails at each member, so it is false.
                let (Some(domain), Some(each)) = (list_left(domain, empty)?, list_left(each, empty)?) else { return Ok(Rewritten::Empty) };
                if domain.is_empty() || each.is_empty() {
                    return Err("an ALL with a list that the edit leaves with no conjunct".into());
                }
                changed = true;
                kept.push(Conjunct::All { domain: Node::new(Body { conjuncts: domain.into() }), body: Node::new(Body { conjuncts: each.into() }) });
            }
            other => kept.push(other.clone()),
        }
    }
    Ok(if changed { Rewritten::Changed(kept) } else { Rewritten::Same })
}

/// The conjuncts of the list `body` after the edit, `None` where it is
/// false.
fn list_left(body: &Node<Body>, empty: &Empty) -> Result<Option<Vec<Conjunct>>, String> {
    Ok(match rewrite(body.value(), empty)? {
        Rewritten::Same => Some(body.value().conjuncts.to_vec()),
        Rewritten::Empty => None,
        Rewritten::Changed(conjuncts) => Some(conjuncts),
    })
}

/// The conjuncts that take the place of the `IF` form `conjunct` after the
/// edit, `None` where it is false.
///
/// A false test makes the `IF` its else, whose list then makes each label
/// the `IF` exported, as a new first branch of an `OR` does. A test the edit
/// leaves with no conjunct is true, so the `IF` is its then. A false else
/// makes the `IF` the conjunction of its test and its then. A false then,
/// or a list that the edit leaves with no conjunct, is not supported.
fn rewrite_if(conjunct: &Conjunct, test: &Node<Body>, then: &Node<Body>, otherwise: &Node<Body>, empty: &Empty) -> Result<Option<Vec<Conjunct>>, String> {
    let otherwise = list_left(otherwise, empty)?;
    let Some(test) = list_left(test, empty)? else {
        let Some(otherwise) = otherwise else { return Ok(None) };
        let mut body = Body { conjuncts: otherwise.into() };
        for label in made_labels(&Body { conjuncts: Arc::from([conjunct.clone()]) }) {
            if !made_labels(&body).contains(&label) {
                body = make_label(&body, label).ok_or("an IF with a false test whose else has no site that can make a label the IF exports")?;
            }
        }
        return Ok(Some(body.conjuncts.to_vec()));
    };
    let then = list_left(then, empty)?;
    if test.is_empty() {
        return Ok(then);
    }
    match (then, otherwise) {
        (None, _) => Err("an IF whose then the edit makes false".into()),
        (Some(then), None) => Ok(Some(test.into_iter().chain(then).collect())),
        (Some(then), Some(otherwise)) if then.is_empty() || otherwise.is_empty() => Err("an IF with a list that the edit leaves with no conjunct".into()),
        (Some(then), Some(otherwise)) => Ok(Some(vec![Conjunct::If {
            test: Node::new(Body { conjuncts: test.into() }),
            then: Node::new(Body { conjuncts: then.into() }),
            otherwise: Node::new(Body { conjuncts: otherwise.into() }),
        }])),
    }
}

/// `body` with `label` made at its first site in a positive atom of the
/// body's own list, a site on a declared or a fact relation before one on a
/// lib relation, or else at the first label of a `=` of that list, or else
/// in the first branch of an `OR`, or the then of an `IF`, of that list
/// whose other branches all name it. `None` where none of these holds it.
fn make_label(body: &Body, label: LabelId) -> Option<Body> {
    let with = |index: usize, conjunct: Conjunct| {
        let mut conjuncts = body.conjuncts.to_vec();
        conjuncts[index] = conjunct;
        Body { conjuncts: conjuncts.into() }
    };
    for lib in [false, true] {
        for (index, conjunct) in body.conjuncts.iter().enumerate() {
            let Conjunct::Atom(atom) = conjunct else { continue };
            if matches!(atom.value().relation, RelationRef::Lib(_)) != lib {
                continue;
            }
            let mut done = false;
            let sites: Arc<[Site]> = atom.value().sites.iter().map(|site| made_in_site(site, label, &mut done)).collect();
            if done {
                return Some(with(index, Conjunct::Atom(Node::new(Atom { relation: atom.value().relation.clone(), sites }))));
            }
        }
    }
    let made = body.conjuncts.iter().enumerate().find_map(|(index, conjunct)| match conjunct {
        Conjunct::Constraint(constraint) if constraint.op == ConstraintOp::Eq && constraint.first.label == label && !constraint.first.fresh => {
            Some(with(index, Conjunct::Constraint(Constraint { first: ConstraintLabel { label, fresh: true }, ..*constraint })))
        }
        _ => None,
    });
    // An `OR` or an `IF` of the list exports the label where its first
    // branch, or its then, makes it and each other branch names it.
    made.or_else(|| {
        body.conjuncts.iter().enumerate().find_map(|(index, conjunct)| match conjunct {
            Conjunct::Or(branches) if branches[1..].iter().all(|branch| body_labels(branch.value()).contains(&label)) => {
                let first = make_label(branches[0].value(), label)?;
                let branches = std::iter::once(Node::new(first)).chain(branches[1..].iter().cloned()).collect();
                Some(with(index, Conjunct::Or(branches)))
            }
            Conjunct::If { test, then, otherwise } if body_labels(otherwise.value()).contains(&label) => {
                let then = Node::new(make_label(then.value(), label)?);
                Some(with(index, Conjunct::If { test: test.clone(), then, otherwise: otherwise.clone() }))
            }
            _ => None,
        })
    })
}

/// `site` with its first `X` of `label` made, `*X`, where `done` is not yet
/// set; sets `done` once it makes one.
fn made_in_site(site: &Site, label: LabelId, done: &mut bool) -> Site {
    let args = site
        .value
        .args
        .iter()
        .map(|arg| match arg {
            SiteArg::Label(LabelUse::Join(own)) if !*done && *own == label => {
                *done = true;
                SiteArg::Label(LabelUse::Fresh(label))
            }
            SiteArg::NamedLabel { name, label: LabelUse::Join(own) } if !*done && *own == label => {
                *done = true;
                SiteArg::NamedLabel { name: name.clone(), label: LabelUse::Fresh(label) }
            }
            SiteArg::Field(field) => SiteArg::Field(made_in_site(field, label, done)),
            other => other.clone(),
        })
        .collect();
    Site { column: site.column.clone(), value: SiteValue { args } }
}

/// `Err` where the `OUT` relation of `filtered` differs from that of
/// `original` on an example, or where either enumeration is not complete.
/// The two walks are compared leaf by leaf, in walk order: the joint
/// assignments of the `DET`s that `OUT` reads, each with the rows of `OUT` at
/// each model. A `DET` that `filtered` lost had one value at each assignment,
/// the empty relation, so it adds no leaf to the walk of `original`. The
/// values of a `DET` are not compared across the programs, since an
/// evaluation keeps only the columns that its program reads.
fn compare_out(evaluator: &Evaluator<'_>, original: &StudyProgram, filtered: &StudyProgram) -> Result<(), String> {
    let of = |program: &StudyProgram, which: &str| -> Result<_, String> {
        let relation = output_relation(program.checked()).ok_or("the program has no OUT form")?;
        evaluator.values(program.checked(), &relation).map_err(|reason| format!("the OUT comparison is not complete: in the {which} program, {reason}"))
    };
    let (before, after) = (of(original, "original")?, of(filtered, "filtered")?);
    if before.len() != after.len() {
        return Err(format!("OUT has {} leaves in the original and {} in the filtered program", before.len(), after.len()));
    }
    for ((example, _, models), (other, _, others)) in before.iter().zip(&after) {
        if example != other || models.len() != others.len() || models.iter().zip(others).any(|(a, b)| !same_rows(a, b)) {
            return Err(format!("OUT rows differ on {example:?}"));
        }
    }
    Ok(())
}

// ---------------------------------------------------------------- names and text

/// The relation names of a case's stream: the native text of each relation
/// of the program the stream reads back as, with the text of the same
/// relation in the case's source.
struct Names {
    relations: StableHashMap<String, String>,
}

impl Names {
    fn of(stream: &WrittenStream, original: &StudyProgram, settings: &DecodeSettings) -> Result<Names, String> {
        let native = original.written_stream(Registry::get(), settings).map_err(|fault| fault.message.to_string())?;
        if native.relations.len() != stream.relations.len() {
            return Err("the case stream and its program declare other counts of relations".into());
        }
        let mut relations = StableHashMap::default();
        for (native, source) in native.relations.iter().zip(&stream.relations) {
            relations.insert(spelled(native), spelled(source));
            if let (ProgramRelation::Output(native), ProgramRelation::Output(source)) = (native, source) {
                relations.entry(owner_spelled(&native.of)).or_insert_with(|| owner_spelled(&source.of));
            }
        }
        Ok(Names { relations })
    }

    /// `text` with each relation name in the source's spelling.
    fn source_text(&self, text: &str) -> String {
        let mut out = String::with_capacity(text.len());
        let mut rest = text;
        while let Some(at) = rest.find('&') {
            out.push_str(&rest[..at]);
            let tail = &rest[at..];
            let end = tail.find(|c: char| c.is_whitespace() || c == '(' || c == ')').unwrap_or(tail.len());
            let token = &tail[..end];
            match self.relations.get(token) {
                Some(name) => out.push_str(name),
                None => match token.split_once('.') {
                    Some((owner, path)) if self.relations.contains_key(owner) => {
                        out.push_str(&self.relations[owner]);
                        out.push('.');
                        out.push_str(path);
                    }
                    _ => out.push_str(token),
                },
            }
            rest = &tail[end..];
        }
        out.push_str(rest);
        out
    }
}

/// `name` as the program text writes it: a slot `n` as `&rn`.
fn declared_text(name: &crate::program::DeclaredName) -> String {
    match name {
        crate::program::DeclaredName::Written(text) => text.to_string(),
        crate::program::DeclaredName::Slot(slot) => format!("&r{slot}"),
    }
}

/// `relation` as the program text writes it.
fn spelled(relation: &ProgramRelation) -> String {
    let reference = match relation {
        ProgramRelation::Declared(name) => RelationRef::Declared(name.clone()),
        ProgramRelation::Output(name) => RelationRef::Output(name.clone()),
    };
    crate::write::relation_ref(&reference, declared_text)
}

fn owner_spelled(owner: &crate::program::OutputOwner) -> String {
    match owner {
        crate::program::OutputOwner::Instance(name) => declared_text(&name.0),
        crate::program::OutputOwner::RigidDet(name) => declared_text(&name.0),
    }
}

/// The program's text in the source's names, checked to read back to the
/// stream of the program's text in the engine's names. The text writes the
/// sites of a read in slot order, which the program need not hold, so the
/// program's own stream is not the one to compare.
fn source_program(program: &StudyProgram, names: &Names, registry: &Registry) -> Result<String, String> {
    let engine_text = program.sexp(registry);
    let text = names.source_text(&engine_text);
    let settings = DecodeSettings::default();
    let read = StudyProgram::from_sexp(&text, registry).map_err(|fault| format!("the program text does not read back: {fault}"))?;
    let engine = StudyProgram::from_sexp(&engine_text, registry).map_err(|fault| format!("the program text does not read back: {fault}"))?;
    let (a, b) = (read.decode_stream(registry, &settings)?, engine.decode_stream(registry, &settings)?);
    if a.ids != b.ids || a.model != b.model {
        return Err("the program text reads back to another stream".into());
    }
    Ok(text)
}

/// The text of each form of `program`, in the source's names.
fn form_texts(program: &StudyProgram, names: &Names, registry: &Registry) -> Result<Vec<String>, String> {
    let texts = program.node_texts(registry)?;
    (0..program.program().value().forms.len()).map(|index| texts.get(&NodePath::top(index as u32)).map(|text| names.source_text(text)).ok_or_else(|| format!("form {index} has no text"))).collect()
}

fn form_relation(form: &Form, names: &Names) -> String {
    match form {
        Form::Clause(clause) => names.source_text(&spelled(&clause.value().derives)),
        Form::Demonstrated(demonstrated) => names.source_text(&spelled(&ProgramRelation::Declared(demonstrated.value().name.clone()))),
        _ => String::new(),
    }
}

struct CaseResult {
    value: Value,
    /// The value of the case where the task keeps its original gold.
    original: Value,
}

impl CaseResult {
    fn unread(case: &str, concept: bool) -> CaseResult {
        let value = json!({"case": case, "concept": concept, "original_program": null, "filtered_program": null, "old_to_new_clause_index": [], "removed_clauses": [], "edited_clauses": [], "reason": null});
        CaseResult { value: value.clone(), original: value }
    }

    fn original(case: &str, concept: bool, original: &StudyProgram, names: Option<&Names>, registry: &Registry) -> CaseResult {
        let text = match names.map(|names| source_program(original, names, registry)) {
            Some(Ok(text)) => text,
            _ => original.sexp(registry),
        };
        let count = original.program().value().forms.len();
        let value = json!({"case": case, "concept": concept, "original_program": text, "filtered_program": text,
            "old_to_new_clause_index": (0..count).collect::<Vec<_>>(), "removed_clauses": [], "edited_clauses": [], "reason": null});
        CaseResult { value: value.clone(), original: value }
    }

    fn filtered(case: &str, concept: bool, original: &StudyProgram, filtered: Filtered, names: &Names, registry: &Registry) -> Result<CaseResult, String> {
        let unchanged = CaseResult::original(case, concept, original, Some(names), registry).original;
        let text = source_program(original, names, registry)?;
        let filtered_text = if filtered.deleted.is_empty() && filtered.edited.is_empty() { text.clone() } else { source_program(&filtered.program, &names_after(&filtered, names, registry)?, registry)? };
        let forms = &original.program().value().forms;
        let texts = form_texts(original, names, registry)?;
        let mut next = 0usize;
        let map: Vec<Option<usize>> = (0..forms.len()).map(|index| if filtered.deleted.contains_key(&index) { None } else { next += 1; Some(next - 1) }).collect();
        let removed: Vec<Value> = filtered.deleted.iter().map(|(&index, &reason)| json!({"clause_index": index, "relation": form_relation(&forms[index], names), "clause": texts[index], "reason": reason})).collect();
        let edited: Vec<Value> = filtered.edited.iter().map(|&index| json!({"clause_index": index, "relation": form_relation(&forms[index], names), "clause": texts[index]})).collect();
        let value = json!({"case": case, "concept": concept, "original_program": text, "filtered_program": filtered_text,
            "old_to_new_clause_index": map, "removed_clauses": removed, "edited_clauses": edited, "reason": null});
        Ok(CaseResult { value, original: unchanged })
    }

    /// The case's original gold in a task whose other cases may be filtered,
    /// with the reason the edit gives none. `Err` where the program has no
    /// text in the source's names.
    fn kept(case: &str, concept: bool, original: &StudyProgram, names: &Names, registry: &Registry, reason: &str) -> Result<CaseResult, String> {
        let text = source_program(original, names, registry)?;
        let count = original.program().value().forms.len();
        let value = json!({"case": case, "concept": concept, "original_program": text, "filtered_program": text,
            "old_to_new_clause_index": (0..count).collect::<Vec<_>>(), "removed_clauses": [], "edited_clauses": [], "reason": reason});
        Ok(CaseResult { value, original: CaseResult::original(case, concept, original, Some(names), registry).original })
    }

    fn as_original(self) -> Value {
        self.original
    }
}

/// The names of the filtered program's stream: the relation at each slot of
/// the filtered program's stream is the relation at that slot of the stream
/// of the edited program, which keeps the original's names.
fn names_after(filtered: &Filtered, names: &Names, registry: &Registry) -> Result<Names, String> {
    let settings = DecodeSettings::default();
    let edit = filtered.edit.written_stream(registry, &settings).map_err(|fault| fault.message.to_string())?;
    let read = filtered.program.written_stream(registry, &settings).map_err(|fault| fault.message.to_string())?;
    if edit.relations.len() != read.relations.len() {
        return Err("the filtered stream declares another count of relations".into());
    }
    let mut relations = StableHashMap::default();
    for (old, new) in edit.relations.iter().zip(&read.relations) {
        relations.insert(spelled(new), names.source_text(&spelled(old)));
        if let (ProgramRelation::Output(old), ProgramRelation::Output(new)) = (old, new) {
            relations.entry(owner_spelled(&new.of)).or_insert_with(|| names.source_text(&owner_spelled(&old.of)));
        }
    }
    Ok(Names { relations })
}

// ---------------------------------------------------------------- the lint

/// The label at each leaf of an atom's sites: the path of column names and
/// argument indexes, and the label.
fn leaves(sites: &[Site], prefix: &str, out: &mut Vec<(String, LabelUse)>) {
    for site in sites {
        let column = format!("{prefix}/{}", column_spelled(&site.column));
        for (index, arg) in site.value.args.iter().enumerate() {
            let at = format!("{column}#{index}");
            match arg {
                SiteArg::Label(label) | SiteArg::NamedLabel { label, .. } => out.push((at, *label)),
                SiteArg::Field(field) => leaves(std::slice::from_ref(field), &at, out),
            }
        }
    }
}

fn bound(label: &LabelUse) -> bool {
    matches!(label, LabelUse::Join(_) | LabelUse::Zero)
}

fn fresh_id(label: &LabelUse) -> Option<LabelId> {
    match label {
        LabelUse::Fresh(id) | LabelUse::Key(id) => Some(*id),
        _ => None,
    }
}

/// The lint's findings on `original`: (form index, relation, label, label).
fn lint(evaluator: &Evaluator<'_>, original: &StudyProgram, names: &Result<Names, String>, tables: &mut Tables, registry: &Registry) -> Result<Vec<(usize, String, String, String)>, String> {
    let names = names.as_ref().map_err(Clone::clone)?;
    let labels = original.label_names(registry);
    let checked = original.checked();
    let mut found = Vec::new();
    for (index, form) in original.program().value().forms.iter().enumerate() {
        let mut bodies = Vec::new();
        each_body(NodeRef::from(form), &mut bodies);
        let name_of = |id: LabelId| labels.get(index).and_then(|names| names.iter().find(|(own, _)| *own == id)).map_or_else(|| format!("{id:?}"), |(_, name)| name.to_string());
        for body in bodies {
            let atoms: Vec<(&RelationRef, Vec<(String, LabelUse)>)> = body
                .conjuncts
                .iter()
                .filter_map(|conjunct| match conjunct {
                    Conjunct::Atom(atom) if matches!(atom.value().relation, RelationRef::Declared(_) | RelationRef::Output(_)) => {
                        let mut out = Vec::new();
                        leaves(&atom.value().sites, "", &mut out);
                        Some((&atom.value().relation, out))
                    }
                    _ => None,
                })
                .collect();
            for (a, (relation, first)) in atoms.iter().enumerate() {
                for (other, second) in &atoms[a + 1..] {
                    if relation != other {
                        continue;
                    }
                    let key = |leaves: &[(String, LabelUse)]| leaves.iter().filter(|(_, label)| bound(label)).map(|(at, label)| format!("{at}={label:?}")).collect::<BTreeSet<_>>();
                    if key(first) != key(second) {
                        continue;
                    }
                    let pairs: Vec<(LabelId, LabelId)> = first
                        .iter()
                        .filter_map(|(at, label)| {
                            let other = second.iter().find(|(own, _)| own == at)?;
                            match (fresh_id(label), fresh_id(&other.1)) {
                                (Some(x), Some(y)) if x != y => Some((x, y)),
                                _ => None,
                            }
                        })
                        .collect();
                    if pairs.is_empty() {
                        continue;
                    }
                    let program_relation = match relation {
                        RelationRef::Declared(name) => ProgramRelation::Declared(name.clone()),
                        RelationRef::Output(name) => ProgramRelation::Output(name.clone()),
                        _ => unreachable!("a declared relation or an output"),
                    };
                    let spelled = names.source_text(&spelled(&program_relation));
                    let graph = relation_of(checked, &program_relation).ok_or_else(|| format!("form {index}: the relation {spelled} has no table"))?;
                    match evaluator.coverage(tables, checked, &graph) {
                        Coverage::Incomplete(reason) => return Err(format!("form {index}: the table of {spelled} is not complete: {reason}")),
                        Coverage::Complete { singleton: false, .. } => {}
                        Coverage::Complete { singleton: true, .. } => found.extend(pairs.into_iter().map(|(x, y)| (index, spelled.clone(), name_of(x), name_of(y)))),
                    }
                }
            }
        }
    }
    Ok(found)
}

/// Each body at or below `node`.
fn each_body<'a>(node: NodeRef<'a>, out: &mut Vec<&'a Body>) {
    if let NodeRef::Body(body) = node {
        out.push(body);
    }
    for child in node.children() {
        each_body(child, out);
    }
}
