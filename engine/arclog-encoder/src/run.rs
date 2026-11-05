//! The check and the evaluation of a feature's forms, through the engine's
//! reader, checker and evaluator as they are.
//!
//! A state is a program's text. A feature's forms stand after the state's
//! queries and before its `OUT` form, and are not added to the state. Each
//! expression is read, checked and evaluated on its own, with the task
//! session's result cache and the check cache shared across expressions.

use std::cell::RefCell;
use std::ops::ControlFlow;
use std::path::Path;

use arclog::check::CheckCache;
use arclog::decode::corpus::corpus_session;
use arclog::decode::{relation_dets, Decoder};
use arclog::eval::examples::scope_of;
use arclog::eval::instance::Constructions;
use arclog::eval::join::each_row;
use arclog::eval::{Evaluation, ModelsEnd, RelationValue};
use arclog::judge::determination::{Assignment, End};
use arclog::registry::Registry;
use arclog::session::TaskSession;
use arclog::stream::corpus::case_files;
use arclog::stream::DecodeSettings;
use arclog::study::StudyProgram;
use arclog::task::{read_task, Task};
use arclog::terms::{Constant, Example, Term, TermId};
use arclog::types::{GraphRelation, ValueType};

use crate::expand::{expand, expand_at, expand_rel, Expanded};
use crate::expression::{Feature, Reader, Rel};
use crate::library::library;
use crate::expand::Rows;
use crate::schema::{graph_relation, table_schema, ColumnFacts, TableSchema, Tables};

/// The text of an `OUT` form, for a state that has none: it reads nothing that
/// a feature reads, and the checker refuses a program with no `OUT` form.
const NO_OUT: &str = "(OUT (input ^P ^Col))";

/// The rows of a relation at one model on one example.
#[derive(Clone, Debug, PartialEq, Eq)]
pub enum ModelValue {
    Rows(Vec<Vec<TermId>>),
    Undefined,
    Stopped(String),
}

/// The value of a relation at one assignment.
#[derive(Clone, Debug)]
pub struct AtAssignment {
    /// The assignment's values, as text, sorted by relation.
    pub assignment: Vec<(String, Vec<Vec<u32>>)>,
    /// Each example's value at each model; one entry with no example for a
    /// task-wide relation.
    pub examples: Vec<(Option<Example>, Vec<ModelValue>)>,
}

/// What an expression gives on a state.
#[derive(Clone, Debug)]
pub enum Evaluated {
    /// No expansion, or the checker refuses it: the expression is no feature.
    Refused(String),
    /// A fault at a form when it runs.
    Fault(String),
    Value(Value),
}

/// The value of an expression, at each assignment of the `DET`s it reads.
#[derive(Clone, Debug)]
pub struct Value {
    pub expanded: Expanded,
    /// The name of each row position of the relation that gives the value.
    pub row_names: Vec<String>,
    /// The type of each row position of that relation.
    pub types: Vec<ValueType>,
    pub at: Vec<AtAssignment>,
    /// The walk's stop, where a cap stopped it.
    pub stop: Option<String>,
}

/// A state on a task, and what its expressions share.
pub struct Host {
    pub task: Task,
    session: TaskSession,
    constructions: &'static Constructions,
    settings: DecodeSettings,
    /// The state's forms.
    before: String,
    /// The `OUT` form.
    out: String,
    base: StudyProgram,
    cache: RefCell<CheckCache>,
}

impl Tables for Host {
    fn table(&self, name: &str) -> Option<TableSchema> {
        table_schema(self.base.checked(), name)
    }

    fn accepts(&self, forms: &[String]) -> Result<(), String> {
        self.checked_with(forms).map(|_| ())
    }

    fn columns_of(&self, forms: &[String], rows: &Rows) -> Result<Vec<ColumnFacts>, String> {
        let registry = Registry::get();
        let program = self.checked_with(forms)?;
        crate::schema::column_facts(program.checked(), registry, rows)
    }
}

/// `program`'s text, split at its `OUT` form.
fn split_program(program: &str) -> (String, String) {
    match program.rfind("(OUT") {
        Some(at) => (program[..at].to_string(), program[at..].to_string()),
        None => (program.to_string(), NO_OUT.to_string()),
    }
}

/// The concept case's program of the solver `id`, from its files in `corpus`.
pub fn concept_program(corpus: &Path, id: &str) -> Result<String, String> {
    let read = |extension: &str| std::fs::read_to_string(corpus.join(format!("{id}.{extension}")));
    let arclog = read("arclog").map_err(|error| format!("the solver {id} does not read: {error}"))?;
    let arcdata = read("arcdata").unwrap_or_else(|_| format!(";; {id}\n"));
    let cases = case_files(id, &arclog, &arcdata, corpus)?;
    let concept = cases.into_iter().find(|case| case.concept).ok_or("the solver has no concept case")?;
    concept.texts.map(|texts| texts.arclog)
}

impl Host {
    /// The state that `program` writes, on the task read from `task`.
    pub fn new(program: &str, task: &Path) -> Result<Host, String> {
        let task = read_task(task).map_err(|error| format!("the task does not read: {error:?}"))?;
        Host::of_task(program, task)
    }

    pub fn of_task(program: &str, task: Task) -> Result<Host, String> {
        let (before, out) = split_program(program);
        let registry = Registry::get();
        let mut cache = CheckCache::default();
        let base = StudyProgram::from_sexp_cached(&format!("{before}\n{out}\n"), registry, &mut cache)?;
        Ok(Host {
            task,
            session: corpus_session(),
            constructions: arclog_constructions::shared()?,
            settings: DecodeSettings::default(),
            before,
            out,
            base,
            cache: RefCell::new(cache),
        })
    }

    /// The reader of a term, over the registry.
    pub fn with_reader<T>(&self, read: impl FnOnce(&Reader<'_>) -> T) -> T {
        read(&Reader { registry: Registry::get(), library: library(), program_relations: &crate::program_relations::is_program_relation })
    }

    /// The value of the ground expression that `text` writes.
    pub fn feature(&self, text: &str) -> Evaluated {
        match self.with_reader(|reader| reader.feature_text(text)) {
            Ok(feature) => self.evaluate(&feature),
            Err(error) => Evaluated::Refused(error),
        }
    }

    /// The rows of the relation that `text` writes, to read it apart from a
    /// root.
    pub fn relation(&self, text: &str, task_wide: bool) -> Evaluated {
        let rel = match self.with_reader(|reader| reader.rel_text(text)) {
            Ok(rel) => rel,
            Err(error) => return Evaluated::Refused(error),
        };
        self.evaluate_rel(&rel, task_wide)
    }

    pub fn evaluate_rel(&self, rel: &Rel, task_wide: bool) -> Evaluated {
        match expand_rel(rel, self, Registry::get(), task_wide) {
            Ok(expanded) => self.run(expanded),
            Err(error) => Evaluated::Refused(error),
        }
    }

    pub fn evaluate(&self, feature: &Feature) -> Evaluated {
        match expand(feature, self, Registry::get()) {
            Ok(expanded) => self.run(expanded),
            Err(error) => Evaluated::Refused(error),
        }
    }

    /// [`Host::evaluate`], with the expression read as task-wide.
    pub fn evaluate_task_wide(&self, feature: &Feature) -> Evaluated {
        match expand_at(feature, self, Registry::get(), true) {
            Ok(expanded) => self.run(expanded),
            Err(error) => Evaluated::Refused(error),
        }
    }

    /// The state with `forms` after its queries, checked.
    fn checked_with(&self, forms: &[String]) -> Result<StudyProgram, String> {
        let text = format!("{}\n{}\n{}\n", self.before, forms.join("\n"), self.out);
        StudyProgram::from_feature_forms_cached(&text, Registry::get(), &mut self.cache.borrow_mut())
    }

    /// Checks and evaluates the forms of `expanded`.
    pub fn run(&self, expanded: Expanded) -> Evaluated {
        let registry = Registry::get();
        let program = match self.checked_with(&expanded.forms) {
            Ok(program) => program,
            Err(message) => return Evaluated::Refused(message),
        };
        let checked = program.checked();
        let Some(relation) = graph_relation(checked, &expanded.export) else {
            return Evaluated::Fault(format!("the program has no relation `{}`", expanded.export));
        };
        let types: Vec<ValueType> = checked.types.columns(&relation).map(<[ValueType]>::to_vec).unwrap_or_default();
        // A `Pose` is not observable: the pose rule lets a derived column take
        // one, and a frame change moves it.
        if types.iter().any(|ty| matches!(ty, ValueType::Pose(_))) {
            return Evaluated::Refused("a `Pose` stands at an exported column".to_string());
        }
        let row_names = checked.program.column_names(relation.node).unwrap_or_default();
        let dets = relation_dets(checked, relation.node);
        let decoder = Decoder::new(&self.task, &self.session, registry, self.constructions, &self.settings);
        let mut at: Vec<AtAssignment> = Vec::new();
        let mut stop = None;
        for example in decoder.examples_of(scope_of(checked, &relation)) {
            let assigned = decoder.assigned(checked, relation.node, &dets, None, &mut |evaluation| models_at(evaluation, &relation, example));
            let assigned = match assigned {
                Ok(assigned) => assigned,
                Err(fault) => return Evaluated::Fault(format!("{} at {:?}", fault.message, fault.form)),
            };
            if let Some(stopped) = &assigned.stop {
                stop.get_or_insert_with(|| format!("{:?}", stopped.bound));
            }
            for (assignment, models) in assigned.at {
                let key = assignment_key(&assignment);
                let models: Vec<ModelValue> = models.iter().map(model_value).collect();
                match at.iter_mut().find(|held| held.assignment == key) {
                    Some(held) => held.examples.push((example, models)),
                    None => at.push(AtAssignment { assignment: key, examples: vec![(example, models)] }),
                }
            }
        }
        Evaluated::Value(Value { expanded, row_names, types, at, stop })
    }

    /// The tables of the base program.
    pub fn base_relation(&self, name: &str) -> Option<GraphRelation> {
        graph_relation(self.base.checked(), name)
    }

    pub fn base(&self) -> &StudyProgram {
        &self.base
    }
}

fn models_at(evaluation: &Evaluation<'_>, relation: &GraphRelation, example: Option<Example>) -> Result<Vec<RelationValue>, End> {
    let mut values = Vec::new();
    let end = evaluation
        .models(relation, example, &mut |value| {
            values.push(value.clone());
            ControlFlow::Continue(())
        })
        .map_err(End::Fault)?;
    if let ModelsEnd::Stopped(stop) = end {
        values.push(RelationValue::Stopped(stop));
    }
    Ok(values)
}

fn rows_of(relation: &arclog::relations::Relation) -> Vec<Vec<TermId>> {
    let mut rows: Vec<Vec<TermId>> = Vec::new();
    each_row(relation, &mut |row: &[TermId]| rows.push(row.to_vec()));
    rows.sort_by_key(|row| row.iter().map(|id| id.encoding()).collect::<Vec<u32>>());
    rows.dedup();
    rows
}

fn assignment_key(assignment: &[Assignment]) -> Vec<(String, Vec<Vec<u32>>)> {
    let mut key: Vec<(String, Vec<Vec<u32>>)> = assignment
        .iter()
        .map(|(name, rows)| (arclog::eval::determinations::relation_spelled(name), rows_of(rows).into_iter().map(|row| row.into_iter().map(|id| id.encoding()).collect()).collect()))
        .collect();
    key.sort();
    key
}

fn model_value(value: &RelationValue) -> ModelValue {
    match value {
        RelationValue::Rows(rows) => ModelValue::Rows(rows_of(rows)),
        RelationValue::Undefined => ModelValue::Undefined,
        RelationValue::Stopped(stop) => ModelValue::Stopped(format!("{:?}", stop.bound)),
    }
}

/// The text of a value at a column of type `ty`.
pub fn cell_text(id: TermId, ty: &ValueType) -> String {
    match Term::decode(id, ty) {
        Term::Number(number) => number.0.to_string(),
        Term::Constant(Constant::Color(color)) => format!("c{}", color.digit()),
        Term::Constant(Constant::Example(example)) => format!("e{}", example.index()),
        Term::Constant(Constant::Orientation(constant)) => Registry::get().constant_name(constant).to_string(),
        Term::Constant(Constant::Unit) => "unit".to_string(),
        Term::Constant(Constant::LibName(name)) => format!("{:?}", &*name.text()),
        Term::Box(margins) => format!("[{},{},{},{}]", margins.top, margins.bottom, margins.left, margins.right),
        Term::Ident(_) => format!("#{}", id.encoding()),
    }
}
