//! The vector entries that name no column of their tables, with their numbers
//! through the engine. A table's entries that name its columns are shapes, which
//! `tablewalk` gives (`work/feature-spec/feature-spec.md#vectors`).

use std::collections::BTreeMap;
use std::ops::ControlFlow;

use arclog::registry::Registry;
use arclog::types::ValueType;

use crate::encoder::with_tables;
use crate::enumerate::{Space, Typed};
use crate::expression::{Feature, Leaf, Rel};
use crate::run::{AtAssignment, Evaluated, Host, ModelValue, Value};
use crate::schema::{TableSchema, Tables};

/// The hole of a TableVector's one table, which stands for every table.
pub const TABLE_HOLE: &str = "&table";

/// An assignment's values, as [`AtAssignment`] holds them.
type Assignment = Vec<(String, Vec<Vec<u32>>)>;

/// The tables of the enumeration of a vector's names: its one table has no
/// column that a name could write.
struct AbstractTable<'h>(&'h [String]);

impl Tables for AbstractTable<'_> {
    fn table(&self, name: &str) -> Option<TableSchema> {
        self.0.iter().any(|hole| hole == name).then(|| TableSchema { columns: Vec::new(), stored: None, per_input: true, has_example: false })
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
fn gives_number(feature: &Feature, term: &Typed) -> bool {
    match feature {
        Feature::Nonempty(_) | Feature::Cardinality(_) => true,
        Feature::ValueSet(_, columns) => {
            let [one] = &columns[..] else { return false };
            let name = crate::expand::label_of(one);
            term.columns.iter().any(|column| (column.name == *one || column.name == name) && matches!(column.ty, Some(ValueType::Int | ValueType::Nat)))
        }
        Feature::Call(..) => false,
    }
}

/// The vector entries of every size up to `size`, over the table holes `holes`,
/// sorted by name.
pub fn entries(holes: &[String], size: usize, program_relations: bool, max_inputs: Option<usize>, limit: Option<usize>) -> Vec<Entry> {
    let registry = Registry::get();
    let tables = AbstractTable(holes);
    let mut found: BTreeMap<String, Entry> = BTreeMap::new();
    for task_wide in [false, true] {
        let space = Space {
            registry,
            tables: &tables,
            task_wide,
            table_names: holes.to_vec(),
            program_relations,
            max_inputs,
            thin: None,
            no_output: false, quick: false, max_bound_columns: None,
        };
        let mut lower: Vec<Vec<Typed>> = Vec::new();
        for at in 0..=size {
            let mut terms = Vec::new();
            let _ = space.generate(&lower, at, &mut |term| {
                // A vector entry reads its table.
                let mut reads_table = false;
                term.rel.each_leaf(&mut |leaf| reads_table |= matches!(leaf, Leaf::Table(_)));
                let flow = space.roots(&term, &mut |feature| {
                    if reads_table && gives_number(&feature, &term) {
                        // A term of the task-wide space is task-wide only with a task-wide leaf.
                        if let Some(entry) = entry_of(feature).filter(|entry| !task_wide || !entry.per_input) {
                            found.entry(entry.expression.clone()).or_insert(entry);
                        }
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

/// The vector entry of the expression `feature`.
pub fn entry_of(feature: Feature) -> Option<Entry> {
    let rel = feature.relation()?;
    let mut wide = false;
    let mut reads_output = false;
    rel.each_leaf(&mut |leaf| {
        wide |= matches!(leaf, Leaf::ExInput | Leaf::ExOutput | Leaf::Proposer(_));
        reads_output |= matches!(leaf, Leaf::Output);
    });
    Some(Entry { expression: feature.to_string(), per_input: !wide, reads_output, feature })
}

/// The ground expression that `entry` gives on `tables`, each hole's table.
fn ground(entry: &Entry, tables: &[(String, String)]) -> Feature {
    match &entry.feature {
        Feature::Nonempty(rel) => Feature::Nonempty(with_tables(rel, tables)),
        Feature::Cardinality(rel) => Feature::Cardinality(with_tables(rel, tables)),
        Feature::ValueSet(rel, columns) => Feature::ValueSet(with_tables(rel, tables), columns.clone()),
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

/// One vector at one assignment of the table: the name of each number, and its
/// value, NaN where it has none.
#[derive(Clone, Debug)]
pub struct Vector {
    pub assignment: Assignment,
    pub numbers: Vec<(String, f64)>,
}

fn mean(values: &[f64]) -> f64 {
    values.iter().sum::<f64>() / values.len() as f64
}

/// The value of `value` at `assignment`: the entry whose assignment agrees with
/// it at each `DET` that both name.
fn at_assignment<'v>(value: &'v Value, assignment: &Assignment) -> Option<&'v AtAssignment> {
    value.at.iter().find(|at| at.assignment.iter().all(|(name, rows)| assignment.iter().find(|(own, _)| own == name).is_none_or(|(_, own)| own == rows)))
}

/// The numbers that `entry` gives at one value.
fn entry_numbers(host: &Host, entry: &Entry, feature: &Feature, value: Option<(&Value, &AtAssignment)>) -> Vec<(String, f64)> {
    let mut per_example: Vec<(Option<arclog::terms::Example>, Option<f64>)> = Vec::new();
    if let Some((value, at)) = value {
        for (example, models) in &at.examples {
            // Within an example, the mean over the models.
            let numbers: Option<Vec<f64>> = models.iter().map(|model| model_number(feature, value, model)).collect();
            per_example.push((*example, numbers.filter(|numbers| !numbers.is_empty()).map(|numbers| mean(&numbers))));
        }
    }
    if !entry.per_input {
        return vec![(entry.expression.clone(), per_example.first().and_then(|(_, number)| *number).unwrap_or(f64::NAN))];
    }
    let train = host.task.train.len() as u16;
    // Over the train examples where the expression has an `output` leaf, and
    // over every example otherwise.
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
    vec![(format!("{}:min", entry.expression), min), (format!("{}:mean", entry.expression), average), (format!("{}:max", entry.expression), max)]
}

/// The vector of `entries` on the tables `tables`, one table for each hole, at
/// each assignment of the first of them.
pub fn vectors(host: &Host, entries: &[Entry], tables: &[(String, String)]) -> Vec<Vector> {
    let table = tables.first().map_or("", |(_, table)| table.as_str());
    // The assignments of the table.
    let assignments: Vec<Assignment> = match host.evaluate(&Feature::Nonempty(Rel::Leaf(Leaf::Table(table.to_string())))) {
        Evaluated::Value(value) => value.at.iter().map(|at| at.assignment.clone()).collect(),
        _ => vec![Vec::new()],
    };
    let mut out: Vec<Vector> = assignments.into_iter().map(|assignment| Vector { assignment, numbers: Vec::new() }).collect();
    for entry in entries {
        let feature = ground(entry, tables);
        let evaluated = host.evaluate(&feature);
        for vector in &mut out {
            let value = match &evaluated {
                Evaluated::Value(value) => at_assignment(value, &vector.assignment).map(|at| (value, at)),
                _ => None,
            };
            vector.numbers.extend(entry_numbers(host, entry, &feature, value));
        }
    }
    out
}
