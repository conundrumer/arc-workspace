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
use arclog::eval::{Evaluation, ModelsEnd, RelationValue, TableWork};
use arclog::judge::determination::{Assignment, End};
use arclog::registry::Registry;
use arclog::session::TaskSession;
use arclog::stream::corpus::case_files;
use arclog::stream::DecodeSettings;
use arclog::study::StudyProgram;
use arclog::task::{read_task, Task};
use arclog::eval::join::one_part;
use arclog::program::FactRelation;
use arclog::registry::declare_stored_table;
use arclog::relations::RowSet;
use arclog::terms::{Constant, Content, Example, LibNameId, Term, TermId, WrittenIdent};
use arclog::types::{GraphRelation, ValueType};

use crate::expand::{expand, expand_at, expand_rel, Expanded};
use crate::expression::{Feature, Reader, Rel};
use crate::library::library;
use crate::expand::Rows;
use crate::schema::{graph_relation, table_schema, ColumnFacts, StoredReads, TableColumn, TableSchema, Tables};

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

/// An expression whose forms the checker accepts, ready to run.
pub struct Checked {
    pub expanded: Expanded,
    pub program: StudyProgram,
    /// The engine's canonical hash of the expansion, down to the base tables.
    pub identity: Option<u128>,
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

/// A table's rows at one assignment and one model, as a law check reads them.
#[derive(Clone, Debug)]
pub struct StoredRows {
    /// The table's name in the program, by which an expression addresses it.
    pub table: String,
    /// A name of the stored table, the same for each session that holds it.
    pub stored_name: String,
    pub columns: Vec<TableColumn>,
    pub types: Vec<ValueType>,
    pub per_input: bool,
    pub has_example: bool,
    /// Each example's rows, or the rows of the task.
    pub rows: Vec<(Option<Example>, Vec<Vec<TermId>>)>,
}

impl StoredRows {
    /// These rows under the element `element`.
    pub fn moved(&self, element: &crate::law::Element) -> StoredRows {
        let rows = self.rows.iter().map(|(example, rows)| (*example, element.rows(rows, &self.types))).collect();
        StoredRows { rows, ..self.clone() }
    }
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
    /// Whether the session holds the rows of the program relations.
    provided: std::cell::Cell<bool>,
    /// The bindings that one expression's evaluation may try, where a cap holds.
    work_cap: std::cell::Cell<Option<u64>>,
    /// The table that the state holds as stored rows.
    stored: Option<(String, TableSchema)>,
}

impl Tables for Host {
    fn table(&self, name: &str) -> Option<TableSchema> {
        if let Some((own, schema)) = &self.stored {
            if own == name {
                return Some(schema.clone());
            }
        }
        table_schema(self.base.checked(), name)
    }

    fn accepts(&self, forms: &[String]) -> Result<(), String> {
        self.checked_with(forms).map(|_| ())
    }

    fn columns_of(&self, forms: &[String], rows: &Rows) -> Result<Vec<ColumnFacts>, String> {
        let registry = Registry::get();
        let program = self.checked_with(forms)?;
        // A stored table's columns are those its reads write.
        if rows.relation.starts_with("stored_table") {
            return Ok(rows.columns.iter().map(|column| ColumnFacts {
                path: column.path.clone(),
                ty: column.ty.clone().unwrap_or(ValueType::Unit),
                identity: format!("{}/{}", rows.relation, column.path.join(".")),
                roots: vec![format!("{}.{}", rows.relation, column.path.join("."))],
            }).collect());
        }
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
            provided: std::cell::Cell::new(false),
            work_cap: std::cell::Cell::new(None),
            stored: None,
        })
    }

    /// A state that holds one table, `table`, as stored rows on `task`.
    pub fn stored(task: Task, table: &StoredRows) -> Result<Host, String> {
        let mut host = Host::of_task(NO_OUT, task)?;
        let registry_type = |ty: &ValueType| ty.clone();
        let plain_columns: Vec<(String, ValueType)> = table.columns.iter().zip(&table.types).map(|(column, ty)| (column.path[0].clone(), registry_type(ty))).collect();
        let plain = LibNameId::of(&table.stored_name);
        declare_stored_table(plain, &plain_columns, table.per_input);
        let lifted = LibNameId::of(&format!("{}@lifted", table.stored_name));
        if table.per_input {
            let mut columns = vec![("E".to_string(), ValueType::Example)];
            columns.extend(plain_columns.iter().cloned());
            declare_stored_table(lifted, &columns, false);
        }
        // An Ident holds nothing but its identity, so the session interns its
        // numbers as a file's.
        let mut idents: std::collections::BTreeMap<u32, TermId> = std::collections::BTreeMap::new();
        {
            let mut held: Vec<u32> = Vec::new();
            for (_, rows) in &table.rows {
                for row in rows {
                    for (id, ty) in row.iter().zip(&table.types) {
                        if matches!(ty, ValueType::Ident(_)) {
                            held.push(id.encoding());
                        }
                    }
                }
            }
            held.sort_unstable();
            held.dedup();
            let mut intern = host.session.intern.write().expect("an intern table that no panic poisoned");
            for (number, id) in held.into_iter().enumerate() {
                let content = Content::FromFile { ty: ValueType::OPEN_IDENT, written: WrittenIdent::new(number as u32) };
                let ident = intern.intern(content);
                idents.insert(id, Term::Ident(ident).encode().expect("an Ident's term id"));
            }
        }
        let cell = |id: TermId, ty: &ValueType| if matches!(ty, ValueType::Ident(_)) { idents[&id.encoding()] } else { id };
        let mut lifted_rows = RowSet::empty(table.types.len() as u16 + 1);
        for (example, rows) in &table.rows {
            let mut set = RowSet::empty(table.types.len() as u16);
            for row in rows {
                let row: Vec<TermId> = row.iter().zip(&table.types).map(|(id, ty)| cell(*id, ty)).collect();
                if let Some(example) = example {
                    let e = Term::Constant(Constant::Example(*example)).encode().expect("an Example's term id");
                    lifted_rows.insert(std::iter::once(e).chain(row.iter().copied()).collect());
                }
                set.insert(row.into());
            }
            host.session.provide_fact(FactRelation::Stored(plain), *example, one_part(set));
        }
        if table.per_input {
            host.session.provide_fact(FactRelation::Stored(lifted), None, one_part(lifted_rows));
        }
        let schema = TableSchema {
            columns: table.columns.clone(),
            stored: Some(StoredReads { plain: format!("stored_table {:?}", table.stored_name), lifted: table.per_input.then(|| format!("stored_table {:?}", format!("{}@lifted", table.stored_name))) }),
            per_input: table.per_input,
            has_example: table.has_example,
        };
        host.stored = Some((table.table.clone(), schema));
        Ok(host)
    }

    /// The rows of the table `name` of the state, at its first assignment and
    /// one model.
    pub fn stored_rows(&self, solver: &str, name: &str) -> Result<StoredRows, String> {
        let checked = self.base.checked();
        let schema = table_schema(checked, name).ok_or_else(|| format!("no table {name}"))?;
        let relation = graph_relation(checked, name).ok_or_else(|| format!("no table {name}"))?;
        let types: Vec<ValueType> = checked.types.columns(&relation).map(<[ValueType]>::to_vec).ok_or_else(|| format!("{name} has no types"))?;
        if types.iter().any(|ty| matches!(ty, ValueType::Pose(_))) {
            return Err(format!("{name} has a Pose column"));
        }
        let dets = relation_dets(checked, relation.node);
        let decoder = Decoder::new(&self.task, &self.session, Registry::get(), self.constructions, &self.settings);
        let mut rows = Vec::new();
        for example in decoder.examples_of(scope_of(checked, &relation)) {
            let assigned = decoder.assigned(checked, relation.node, &dets, None, &mut |evaluation| models_at(evaluation, &relation, example)).map_err(|fault| fault.message.to_string())?;
            let (_, models) = assigned.at.into_iter().next().ok_or_else(|| format!("{name} has no assignment"))?;
            match &models[..] {
                [RelationValue::Rows(held)] => rows.push((example, rows_of(held))),
                [_] => return Err(format!("{name} has no rows at {example:?}")),
                _ => return Err(format!("{name} has several models at {example:?}")),
            }
        }
        // A stored column has a PascalCase name, since a lower-case column is a
        // type parameter's.
        let mut taken: Vec<String> = Vec::new();
        let columns: Vec<TableColumn> = schema.columns.iter().take(types.len()).zip(&types).map(|(column, ty)| TableColumn {
            name: column.name.clone(),
            path: vec![crate::expand::unique(&crate::expand::label_of(&column.name), &mut taken)],
            ty: Some(ty.clone()),
        }).collect();
        Ok(StoredRows { table: name.to_string(), stored_name: format!("{solver}/{name}"), columns, types, per_input: schema.per_input, has_example: schema.has_example, rows })
    }

    /// The tables of the state, sorted by name.
    pub fn table_names(&self) -> Vec<String> {
        let resolved = &self.base.checked().program;
        let mut names: Vec<String> = resolved.graph.nodes.iter().filter_map(|node| crate::program_relations::table_name(&node.kind)).collect();
        names.sort();
        names.dedup();
        names
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

    /// Gives the session the rows of the program relations of the state.
    fn provide_program_relations(&self) {
        if !self.provided.replace(true) {
            for (fact, rows) in crate::program_relations::program_relations(self.base.checked(), Registry::get()) {
                self.session.provide_fact(fact, None, rows);
            }
        }
    }

    /// The state with `forms` after its queries, checked.
    fn checked_with(&self, forms: &[String]) -> Result<StudyProgram, String> {
        let text = format!("{}\n{}\n{}\n", self.before, forms.join("\n"), self.out);
        StudyProgram::from_feature_forms_cached(&text, Registry::get(), &mut self.cache.borrow_mut())
    }

    /// Sets the bindings that one expression's evaluation may try.
    pub fn set_work_cap(&self, cap: u64) {
        self.work_cap.set(Some(cap));
    }

    /// Whether the checker accepts the forms of `rel`.
    pub fn accepts_rel(&self, rel: &Rel, task_wide: bool) -> bool {
        match expand_rel(rel, self, Registry::get(), task_wide) {
            Ok(expanded) => self.checked_with(&expanded.forms).is_ok(),
            Err(_) => false,
        }
    }

    /// The forms of `feature`, checked, with their identity.
    pub fn check(&self, feature: &Feature) -> Result<Checked, String> {
        let expanded = expand(feature, self, Registry::get())?;
        self.check_expanded(expanded)
    }

    fn check_expanded(&self, expanded: Expanded) -> Result<Checked, String> {
        let program = self.checked_with(&expanded.forms)?;
        let top = program.program().value().forms.len().checked_sub(2);
        let identity = top
            .and_then(|top| program.checked().program.query_identity(top, Registry::get()))
            .map(|identity| identity.content.content_hash().0);
        Ok(Checked { expanded, program, identity })
    }

    /// Checks and evaluates the forms of `expanded`.
    pub fn run(&self, expanded: Expanded) -> Evaluated {
        match self.check_expanded(expanded) {
            Ok(checked) => self.evaluate_checked(checked),
            Err(message) => Evaluated::Refused(message),
        }
    }

    /// Evaluates the forms of `checked`.
    pub fn evaluate_checked(&self, checked: Checked) -> Evaluated {
        let Checked { expanded, program, .. } = checked;
        let registry = Registry::get();
        if expanded.forms.iter().any(|form| arclog::program::ProgramFact::ALL.iter().any(|fact| form.contains(fact.name()))) {
            self.provide_program_relations();
        }
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
            let work = self.work_cap.get().map(TableWork::new);
            let assigned = decoder.assigned(checked, relation.node, &dets, work.as_ref(), &mut |evaluation| models_at(evaluation, &relation, example));
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
