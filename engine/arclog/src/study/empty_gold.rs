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
//! that derives it is deleted. Any other read of such a relation, a clause
//! with proposers whose body becomes empty, and a filtered program that the
//! checker refuses, keep the original gold of the whole task. So does an
//! `OUT` relation of the filtered program that differs from the original's
//! on an example, an assignment or a model, or whose enumeration is not
//! complete.
//!
//! The lint reports, on the original program, two positive atoms of one
//! conjunction that read the same relation, bind the same columns to the same
//! labels or constants, and put different labels at some other column, where
//! the relation has exactly one row on each train example and test input, at
//! each assignment and each model. It never changes the edit.

use std::collections::{BTreeMap, BTreeSet, HashMap};
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
use crate::program::{column_spelled, Body, ClauseKeyword, Conjunct, Form, LabelId, LabelUse, Negated, Node, Program, ProgramRelation, RelationRef, Site, SiteArg};
use crate::registry::Registry;
use crate::relations::Relation;
use crate::resolver::DependencyKind;
use crate::session::{same_rows, TaskSession};
use crate::stream::corpus::{solver_streams, token_ids, WantedCases};
use crate::stream::{DecodeSettings, Emitter, Vocabulary, WrittenStream};
use crate::task::Task;
use crate::terms::Example;
use crate::types::GraphRelation;

/// The schema of the result of [`empty_gold`].
pub const SCHEMA: &str = "arclog-empty-gold-v1";

/// The result of the task `id`: the filtered gold of each case, or the
/// original gold of the whole task with the reason, and the lint. `Err` only
/// where the task file does not read.
pub fn empty_gold(corpus: &Path, tasks: &Path, id: &str, deadline: Option<Duration>, constructions: &Constructions) -> Result<Value, String> {
    let (task, _) = read_task_files(tasks, id)?;
    let registry = Registry::get();
    let program_settings = DecodeSettings::default();
    let vocabulary = Vocabulary::new(registry, &program_settings);
    let session = corpus_session();
    let evaluator = Evaluator { task: &task, session: &session, registry, constructions, settings: DecodeSettings { deadline, ..program_settings } };
    let streams = match solver_streams(corpus, id, WantedCases::All, &vocabulary, false) {
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
        let read = if case.demonstrated { Err("the case program holds a DEMONSTRATED form".to_owned()) } else { read_case(&stream, &vocabulary, registry, &program_settings) };
        let original = match read {
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
        let filtered = filter(&evaluator, &original, &mut tables, registry, &program_settings);
        let result = match (filtered, &names) {
            (Ok(filtered), Ok(names)) => CaseResult::filtered(&case.case, case.concept, &original, filtered, names, registry),
            (Ok(_), Err(reason)) => Err(reason.clone()),
            (Err(reason), _) => Err(reason),
        };
        match result {
            Ok(result) => cases.push(result),
            Err(reason) => {
                fallback.get_or_insert(format!("{}: {reason}", case.case));
                cases.push(CaseResult::original(&case.case, case.concept, &original, names.as_ref().ok(), registry));
            }
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
    held: HashMap<(u32, Option<String>), Coverage>,
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
            let (_, end) = descend_assignments(inputs, &dets, relation.node, self.settings.caps.assignments, &mut leaf);
            if let Some(problem) = problem {
                return Err(problem);
            }
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
    let mut deleted: BTreeMap<usize, &'static str> = BTreeMap::new();
    for (index, form) in forms.iter().enumerate() {
        let Form::Clause(clause) = form else { continue };
        if !matches!(clause.value().keyword, ClauseKeyword::Rule | ClauseKeyword::Det) {
            continue;
        }
        let relation = derived_at(checked, &NodePath::top(index as u32));
        if let Coverage::Complete { empty: true, .. } = evaluator.coverage(tables, checked, &relation) {
            deleted.insert(index, EMPTY);
        }
    }
    let (replacements, edited) = loop {
        let empty = emptied(checked, &deleted);
        let mut added = false;
        let mut replacements: Vec<(NodePath, Node<Body>)> = Vec::new();
        let mut edited = BTreeSet::new();
        for (index, form) in forms.iter().enumerate() {
            if deleted.contains_key(&index) {
                continue;
            }
            let mut bodies = Vec::new();
            let mut parts = Vec::new();
            root_bodies(NodeRef::from(form), &NodePath::top(index as u32), &mut bodies, &mut parts);
            if parts.iter().any(|atom| reads(&atom.relation, &empty)) {
                return Err(format!("a RIGID_DET part of form {index} reads an empty relation"));
            }
            for (at, body) in bodies {
                match rewrite(body.value(), &empty).map_err(|reason| format!("form {index}: {reason}"))? {
                    Rewritten::Same => {}
                    Rewritten::Changed(conjuncts) => {
                        replacements.push((at, Node::new(Body { conjuncts: conjuncts.into() })));
                        edited.insert(index);
                    }
                    Rewritten::Empty => {
                        let deletable = match form {
                            Form::Clause(clause) => matches!(clause.value().keyword, ClauseKeyword::Rule | ClauseKeyword::Det) && clause.value().proposers.is_empty() && at == NodePath::top(index as u32).child(0),
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
        if !added {
            break (replacements, edited);
        }
    };
    let edited: BTreeSet<usize> = edited.into_iter().filter(|index| !deleted.contains_key(index)).collect();
    if deleted.is_empty() && edited.is_empty() {
        return Ok(Filtered { program: original.clone(), edit: original.clone(), deleted, edited });
    }
    let mut program = original.program().clone();
    for (at, body) in &replacements {
        program = crate::mutation::edit::replace_body(&program, at, body)?;
    }
    let kept: Vec<Form> = program.value().forms.iter().enumerate().filter(|(index, _)| !deleted.contains_key(index)).map(|(_, form)| form.clone()).collect();
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

/// The relations each of whose deriving forms is in `deleted`.
fn emptied(checked: &CheckedProgram, deleted: &BTreeMap<usize, &'static str>) -> Empty {
    let resolved = &checked.program;
    let mut empty = Empty::default();
    for (index, node) in resolved.graph.nodes.iter().enumerate() {
        let relation = match &node.kind {
            DependencyKind::Clause(relation) | DependencyKind::Parameter(relation) => relation.clone(),
            DependencyKind::Chosen(name) => ProgramRelation::Declared(name.clone()),
            _ => continue,
        };
        let forms = resolved.forms_of(crate::resolver::GraphNodeIndex(index as u32));
        if !forms.is_empty() && forms.iter().all(|at| at.0.len() == 1 && deleted.contains_key(&(at.0[0].0 as usize))) {
            empty.insert(relation);
        }
    }
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
    Changed(Vec<Conjunct>),
}

/// `body` with the empty relations of `empty` taken out, or why the edit
/// does not support it.
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
                        Err(inner) if inner.is_empty() => return Ok(Rewritten::Empty),
                        Err(_) => return Err("a NOT over a form whose edit gives several conjuncts".into()),
                    },
                }
            }
            Conjunct::Or(branches) if branches.iter().any(|branch| mentions(NodeRef::Body(branch.value()), empty)) => {
                let mut left: Vec<Node<Body>> = Vec::new();
                for branch in branches.iter() {
                    match rewrite(branch.value(), empty)? {
                        Rewritten::Same => left.push(branch.clone()),
                        Rewritten::Empty => {}
                        Rewritten::Changed(inner) if inner.is_empty() => return Err("an OR branch whose edit leaves no conjunct".into()),
                        Rewritten::Changed(inner) => left.push(Node::new(Body { conjuncts: inner.into() })),
                    }
                }
                changed = true;
                match left.len() {
                    0 => return Ok(Rewritten::Empty),
                    1 => kept.extend(left[0].value().conjuncts.iter().cloned()),
                    _ => kept.push(Conjunct::Or(left.into())),
                }
            }
            Conjunct::If { .. } | Conjunct::All { .. } if mentions(NodeRef::Conjunct(conjunct), empty) => {
                return Err("an IF or ALL form reads an empty relation".into());
            }
            other => kept.push(other.clone()),
        }
    }
    Ok(if changed { Rewritten::Changed(kept) } else { Rewritten::Same })
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
    let of = |program: &StudyProgram| -> Result<_, String> {
        let relation = output_relation(program.checked()).ok_or("the program has no OUT form")?;
        evaluator.values(program.checked(), &relation).map_err(|reason| format!("the OUT comparison is not complete: {reason}"))
    };
    let (before, after) = (of(original)?, of(filtered)?);
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
    relations: HashMap<String, String>,
}

impl Names {
    fn of(stream: &WrittenStream, original: &StudyProgram, settings: &DecodeSettings) -> Result<Names, String> {
        let native = original.written_stream(Registry::get(), settings).map_err(|fault| fault.message.to_string())?;
        if native.relations.len() != stream.relations.len() {
            return Err("the case stream and its program declare other counts of relations".into());
        }
        let mut relations = HashMap::new();
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
/// program's stream.
fn source_program(program: &StudyProgram, names: &Names, registry: &Registry) -> Result<String, String> {
    let text = names.source_text(&program.sexp(registry));
    let settings = DecodeSettings::default();
    let read = StudyProgram::from_sexp(&text, registry).map_err(|fault| format!("the program text does not read back: {fault}"))?;
    let (a, b) = (read.decode_stream(registry, &settings)?, program.decode_stream(registry, &settings)?);
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
        let value = json!({"case": case, "concept": concept, "original_program": null, "filtered_program": null, "old_to_new_clause_index": [], "removed_clauses": [], "edited_clauses": []});
        CaseResult { value: value.clone(), original: value }
    }

    fn original(case: &str, concept: bool, original: &StudyProgram, names: Option<&Names>, registry: &Registry) -> CaseResult {
        let text = match names.map(|names| source_program(original, names, registry)) {
            Some(Ok(text)) => text,
            _ => original.sexp(registry),
        };
        let count = original.program().value().forms.len();
        let value = json!({"case": case, "concept": concept, "original_program": text, "filtered_program": text,
            "old_to_new_clause_index": (0..count).collect::<Vec<_>>(), "removed_clauses": [], "edited_clauses": []});
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
            "old_to_new_clause_index": map, "removed_clauses": removed, "edited_clauses": edited});
        Ok(CaseResult { value, original: unchanged })
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
    let mut relations = HashMap::new();
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
