//! The encoder at a size: the value of every ground expression of at most that
//! many operators, for tables of a state, at every binding the checker accepts
//! (`work/feature-spec/feature-spec.md#size-and-the-encoder`). Small sizes come
//! first, and a record is written as soon as it exists.

use std::collections::HashMap;
use std::ops::ControlFlow;

use arclog::registry::Registry;
use arclog::types::ValueType;

use crate::enumerate::{value_kinds, Space, Typed};
use crate::expression::{Feature, Leaf, Rel};
use crate::run::{cell_text, Checked, Host, ModelValue, Value};

/// A feature's law under the group, which the type of each exported column
/// gives.
#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub enum Law {
    Invariant,
    Equivariant,
}

/// The law of a feature whose exported columns have `types`.
pub fn law_of(types: &[ValueType]) -> Law {
    let fixed = |ty: &ValueType| matches!(ty, ValueType::Int | ValueType::Nat | ValueType::Unit | ValueType::Example | ValueType::LibName);
    if types.iter().all(fixed) { Law::Invariant } else { Law::Equivariant }
}

/// What the encoder runs.
#[derive(Clone, Debug)]
pub struct Options {
    /// The most operators of an expression.
    pub size: usize,
    /// The tables that a leaf can name.
    pub tables: Vec<String>,
    /// Whether a leaf can name a program relation.
    pub program_relations: bool,
    /// The bindings that one expression's evaluation may try.
    pub work_cap: u64,
    /// The most expressions to visit, for a run that stops early.
    pub limit: Option<u64>,
    /// The most inputs that a component's binding writes.
    pub max_inputs: Option<usize>,
}

/// What one ground expression gives.
pub enum Outcome {
    /// The expansion or the checker refuses it: it is no feature.
    Refused,
    /// It has the same expansion as the feature of this name.
    Alias(String),
    /// A fault when it runs: it has no value.
    Fault(String),
    Value(Box<Value>, Law),
}

/// One visited expression.
pub struct Record {
    pub expression: String,
    pub size: usize,
    pub task_wide: bool,
    pub outcome: Outcome,
}

/// Counts of a run, for its progress.
#[derive(Clone, Debug, Default)]
pub struct Counts {
    pub visited: u64,
    pub refused: u64,
    pub aliases: u64,
    pub faults: u64,
    pub values: u64,
}

/// Whether `feature` has a task-wide leaf, which a term of the task-wide space
/// needs to be task-wide.
fn has_task_wide_leaf(feature: &Feature, host: &Host) -> bool {
    use crate::schema::Tables;
    let mut found = false;
    if let Some(rel) = feature.relation() {
        rel.each_leaf(&mut |leaf| {
            found |= match leaf {
                Leaf::ExInput | Leaf::ExOutput | Leaf::Proposer(_) => true,
                Leaf::Table(name) => host.table(name).is_some_and(|schema| schema.has_example),
                Leaf::Input | Leaf::Output | Leaf::Lib(_) | Leaf::Program(_) => false,
            };
        });
    }
    found
}

/// The walk of the encoder over `host`: `visit` runs on each expression, small
/// sizes first, until it stops the walk or the sizes end.
pub fn encode(host: &Host, options: &Options, visit: &mut dyn FnMut(Record) -> ControlFlow<()>) {
    let registry = Registry::get();
    let spaces: Vec<Space<'_>> = [false, true]
        .into_iter()
        .map(|task_wide| Space {
            registry,
            tables: host,
            task_wide,
            table_names: options.tables.clone(),
            program_relations: options.program_relations,
            kinds: value_kinds(),
            max_inputs: options.max_inputs,
            frames: Vec::new(),
        })
        .collect();
    let mut lower: Vec<Vec<Vec<Typed>>> = vec![Vec::new(), Vec::new()];
    let mut seen: HashMap<u128, String> = HashMap::new();
    host.set_work_cap(options.work_cap);
    for size in 0..=options.size {
        for (index, space) in spaces.iter().enumerate() {
            let keep = size < options.size;
            let mut terms: Vec<Typed> = Vec::new();
            let ended = space.generate(&lower[index], size, &mut |term| {
                let flow = root_walk(host, space, &term, size, &mut seen, visit);
                if keep && flow.is_continue() {
                    // A term the checker refuses gives no term over it.
                    if host.accepts_rel(&term.rel, space.task_wide) {
                        terms.push(term);
                    }
                }
                flow
            });
            if ended.is_break() {
                return;
            }
            lower[index].push(terms);
        }
    }
}

fn root_walk(host: &Host, space: &Space<'_>, term: &Typed, size: usize, seen: &mut HashMap<u128, String>, visit: &mut dyn FnMut(Record) -> ControlFlow<()>) -> ControlFlow<()> {
    space.roots(term, &mut |feature| {
        if space.task_wide && !has_task_wide_leaf(&feature, host) {
            return ControlFlow::Continue(());
        }
        let expression = feature.to_string();
        let outcome = outcome_of(host, &feature, &expression, seen);
        visit(Record { expression, size, task_wide: space.task_wide, outcome })
    })
}

fn outcome_of(host: &Host, feature: &Feature, expression: &str, seen: &mut HashMap<u128, String>) -> Outcome {
    let checked: Checked = match host.check(feature) {
        Ok(checked) => checked,
        Err(_) => return Outcome::Refused,
    };
    if let Some(identity) = checked.identity {
        if let Some(name) = seen.get(&identity) {
            return Outcome::Alias(name.clone());
        }
        seen.insert(identity, expression.to_string());
    }
    match host.evaluate_checked(checked) {
        crate::run::Evaluated::Value(value) => {
            let law = law_of(&value.types);
            Outcome::Value(Box::new(value), law)
        }
        crate::run::Evaluated::Fault(message) => Outcome::Fault(message),
        crate::run::Evaluated::Refused(_) => Outcome::Refused,
    }
}

/// The JSON text of a value: at each assignment, at each example, each model's
/// rows.
pub fn value_json(value: &Value) -> String {
    let mut at_texts = Vec::new();
    for at in &value.at {
        let mut examples = Vec::new();
        for (example, models) in &at.examples {
            let name = example.map_or("null".to_string(), |example| example.index().to_string());
            let models: Vec<String> = models
                .iter()
                .map(|model| match model {
                    ModelValue::Rows(rows) => {
                        let rows: Vec<String> = rows.iter().map(|row| {
                            let cells: Vec<String> = row.iter().zip(&value.types).map(|(id, ty)| json_string(&cell_text(*id, ty))).collect();
                            format!("[{}]", cells.join(","))
                        }).collect();
                        format!("[{}]", rows.join(","))
                    }
                    ModelValue::Undefined => "\"undefined\"".to_string(),
                    ModelValue::Stopped(stop) => json_string(&format!("stopped: {stop}")),
                })
                .collect();
            examples.push(format!("{{\"example\":{name},\"models\":[{}]}}", models.join(",")));
        }
        let assignment: Vec<String> = at.assignment.iter().map(|(name, rows)| format!("{}:{}", json_string(name), rows.len())).collect();
        at_texts.push(format!("{{\"assignment\":{{{}}},\"examples\":[{}]}}", assignment.join(","), examples.join(",")));
    }
    format!("[{}]", at_texts.join(","))
}

/// `text` as a JSON string.
pub fn json_string(text: &str) -> String {
    let mut out = String::with_capacity(text.len() + 2);
    out.push('"');
    for c in text.chars() {
        match c {
            '"' => out.push_str("\\\""),
            '\\' => out.push_str("\\\\"),
            '\n' => out.push_str("\\n"),
            c => out.push(c),
        }
    }
    out.push('"');
    out
}

/// The relation term with each table named by `$T` replaced by `table`.
pub fn with_table(rel: &Rel, table: &str) -> Rel {
    let swap = |rel: &Rel| Box::new(with_table(rel, table));
    match rel {
        Rel::Leaf(Leaf::Table(name)) if name == crate::vectors::TABLE_HOLE => Rel::Leaf(Leaf::Table(table.to_string())),
        Rel::Leaf(_) | Rel::Call(..) => rel.clone(),
        Rel::Project(inner, columns) => Rel::Project(swap(inner), columns.clone()),
        Rel::Select(inner, column, op, operand) => Rel::Select(swap(inner), column.clone(), *op, operand.clone()),
        Rel::Join(left, right, pairs) => Rel::Join(swap(left), swap(right), pairs.clone()),
        Rel::Antijoin(left, right, pairs) => Rel::Antijoin(swap(left), swap(right), pairs.clone()),
        Rel::Union(left, right, pairs) => Rel::Union(swap(left), swap(right), pairs.clone()),
        Rel::LibJoin(inner, name, bindings) => Rel::LibJoin(swap(inner), name.clone(), bindings.clone()),
        Rel::Component(name, bindings, port) => Rel::Component(
            name.clone(),
            bindings.iter().map(|binding| crate::expression::Binding { relation: with_table(&binding.relation, table), ..binding.clone() }).collect(),
            port.clone(),
        ),
        Rel::Pool { hole, over, kind, body } => Rel::Pool { hole: hole.clone(), over: swap(over), kind: kind.clone(), body: swap(body) },
    }
}
