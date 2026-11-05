//! The vector entries: feature expressions whose only free holes are a
//! vector's table holes, so a `pool` binds every column hole. A version of the
//! library and the registry, and a size, fix one list of names, sorted by name,
//! for every table (`work/feature-spec/feature-spec.md#vectors`).

use std::collections::BTreeMap;
use std::ops::ControlFlow;

use arclog::registry::Registry;
use arclog::types::ValueType;

use crate::encoder::with_table;
use crate::enumerate::{value_kinds, Space, Typed};
use crate::expand::Rows;
use crate::expression::{Feature, Leaf, Reader, Rel};
use crate::library::library;
use crate::run::{Evaluated, Host, ModelValue, Value};
use crate::schema::{ColumnFacts, TableSchema, Tables};

/// The hole of a vector's table, which stands for every table.
pub const TABLE_HOLE: &str = "&table";

/// The tables of the enumeration of a vector's names: its one table has no
/// column that a name could write.
struct AbstractTable;

impl Tables for AbstractTable {
    fn table(&self, name: &str) -> Option<TableSchema> {
        (name == TABLE_HOLE).then(|| TableSchema { columns: Vec::new(), stored: None, per_input: true, has_example: false })
    }

    fn accepts(&self, _forms: &[String]) -> Result<(), String> {
        Ok(())
    }

    fn columns_of(&self, _forms: &[String], _rows: &Rows) -> Result<Vec<ColumnFacts>, String> {
        Err("no program stands behind a vector's table".to_string())
    }
}

/// One vector entry: its expression, and whether its root gives one number per
/// example and model, which the encoder combines into three entries.
#[derive(Clone, Debug)]
pub struct Entry {
    pub expression: String,
    pub feature: Feature,
    pub per_input: bool,
    /// Whether the expression has an `output` leaf, so it combines over the
    /// train examples.
    pub reads_output: bool,
}

/// Whether a root gives a number: a count, whether a relation has a row, or a
/// value-set over one number column.
fn gives_number(feature: &Feature, term: &Typed, space: &Space<'_>) -> bool {
    let _ = space;
    match feature {
        Feature::Nonempty(_) | Feature::Cardinality(_) => true,
        Feature::ValueSet(_, columns) => {
            let [one] = &columns[..] else { return false };
            let name = one.trim_start_matches('?');
            let name = crate::expand::label_of(name);
            term.columns.iter().any(|column| (column.name == *one || column.name == name) && matches!(column.ty, Some(ValueType::Int | ValueType::Nat)))
        }
        Feature::Call(..) => false,
    }
}

/// The vector entries of every size up to `size`, sorted by name.
pub fn entries(size: usize, program_relations: bool, max_inputs: Option<usize>, limit: Option<usize>) -> Vec<Entry> {
    let registry = Registry::get();
    let tables = AbstractTable;
    let mut found: BTreeMap<String, Entry> = BTreeMap::new();
    for task_wide in [false, true] {
        let space = Space {
            registry,
            tables: &tables,
            task_wide,
            table_names: vec![TABLE_HOLE.to_string()],
            program_relations,
            kinds: value_kinds(),
            max_inputs,
            frames: Vec::new(),
        };
        let mut lower: Vec<Vec<Typed>> = Vec::new();
        for at in 0..=size {
            let mut terms = Vec::new();
            let _ = space.generate(&lower, at, &mut |term| {
                let flow = space.roots(&term, &mut |feature| {
                    if gives_number(&feature, &term, &space) {
                        add_entry(&mut found, feature, task_wide);
                    }
                    if limit.is_some_and(|limit| found.len() >= limit) { ControlFlow::Break(()) } else { ControlFlow::Continue(()) }
                });
                if at < size {
                    terms.push(term);
                }
                flow
            });
            lower.push(terms);
        }
    }
    found.into_values().collect()
}

fn add_entry(found: &mut BTreeMap<String, Entry>, feature: Feature, task_wide: bool) {
    let Some(rel) = feature.relation() else { return };
    let mut wide = false;
    let mut reads_output = false;
    rel.each_leaf(&mut |leaf| {
        wide |= matches!(leaf, Leaf::ExInput | Leaf::ExOutput | Leaf::Proposer(_));
        reads_output |= matches!(leaf, Leaf::Output);
    });
    // A term of the task-wide space is task-wide only with a task-wide leaf.
    if task_wide && !wide {
        return;
    }
    let expression = feature.to_string();
    found.entry(expression.clone()).or_insert(Entry { expression, feature, per_input: !wide, reads_output });
}

/// The ground expression that `entry` gives on `table`.
fn ground(entry: &Entry, table: &str) -> Feature {
    match &entry.feature {
        Feature::Nonempty(rel) => Feature::Nonempty(with_table(rel, table)),
        Feature::Cardinality(rel) => Feature::Cardinality(with_table(rel, table)),
        Feature::ValueSet(rel, columns) => Feature::ValueSet(with_table(rel, table), columns.clone()),
        Feature::Call(name, args) => Feature::Call(name.clone(), args.clone()),
    }
}

/// The number that one model's rows give at a root.
fn model_number(feature: &Feature, value: &Value, model: &ModelValue) -> Option<f64> {
    let ModelValue::Rows(rows) = model else { return None };
    match feature {
        Feature::Nonempty(_) => Some(if rows.is_empty() { 0.0 } else { 1.0 }),
        Feature::Cardinality(_) => rows.first().and_then(|row| row.first()).map(|id| f64::from(arclog::terms::Term::decode_number(*id))),
        // A value-set over one number column gives a number where the set has one member.
        Feature::ValueSet(..) => match &rows[..] {
            [row] if value.types.len() == 1 => row.first().map(|id| f64::from(arclog::terms::Term::decode_number(*id))),
            _ => None,
        },
        Feature::Call(..) => None,
    }
}

/// One vector: the name of each number, and its value, NaN where it has none.
pub type Vector = Vec<(String, f64)>;

fn mean(values: &[f64]) -> f64 {
    values.iter().sum::<f64>() / values.len() as f64
}

/// The numbers of `entries` on `table` at the assignment of index `assignment`
/// of each expression's walk.
pub fn vector(host: &Host, entries: &[Entry], table: &str, assignment: usize) -> Vector {
    let mut out = Vec::new();
    let reader = Reader { registry: Registry::get(), library: library(), program_relations: &crate::program_relations::is_program_relation };
    let _ = reader;
    for entry in entries {
        let feature = ground(entry, table);
        let evaluated = host.evaluate(&feature);
        let Evaluated::Value(value) = evaluated else {
            if entry.per_input {
                for suffix in ["min", "mean", "max"] {
                    out.push((format!("{}:{suffix}", entry.expression), f64::NAN));
                }
            } else {
                out.push((entry.expression.clone(), f64::NAN));
            }
            continue;
        };
        let at = value.at.get(assignment).or_else(|| value.at.first());
        // Within an example, the mean over the models.
        let mut per_example: Vec<(Option<arclog::terms::Example>, Option<f64>)> = Vec::new();
        for (example, models) in at.map(|at| &at.examples[..]).unwrap_or_default() {
            let numbers: Option<Vec<f64>> = models.iter().map(|model| model_number(&feature, &value, model)).collect();
            per_example.push((*example, numbers.filter(|numbers| !numbers.is_empty()).map(|numbers| mean(&numbers))));
        }
        if entry.per_input {
            let train = host.task.train.len() as u16;
            // Over the train examples where the expression has an `output` leaf,
            // and over every example otherwise.
            let kept: Vec<Option<f64>> = per_example
                .iter()
                .filter(|(example, _)| !entry.reads_output || example.is_none_or(|example| example.index() < train))
                .map(|(_, number)| *number)
                .collect();
            let numbers: Option<Vec<f64>> = kept.iter().copied().collect();
            let (min, average, max) = match numbers.filter(|numbers| !numbers.is_empty()) {
                Some(numbers) => (numbers.iter().copied().fold(f64::INFINITY, f64::min), mean(&numbers), numbers.iter().copied().fold(f64::NEG_INFINITY, f64::max)),
                None => (f64::NAN, f64::NAN, f64::NAN),
            };
            out.push((format!("{}:min", entry.expression), min));
            out.push((format!("{}:mean", entry.expression), average));
            out.push((format!("{}:max", entry.expression), max));
        } else {
            out.push((entry.expression.clone(), per_example.first().and_then(|(_, number)| *number).unwrap_or(f64::NAN)));
        }
    }
    out
}

/// The relation under `feature`.
pub fn relation_of(feature: &Feature) -> Option<&Rel> {
    feature.relation()
}
