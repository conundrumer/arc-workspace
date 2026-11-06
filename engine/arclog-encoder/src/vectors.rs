//! The vector entries that name no column of their tables. A table's entries that name its columns
//! are shapes, which `table_vector` gives (`docs/feature-spec/feature-spec.md#vectors`).

use std::collections::BTreeMap;
use std::ops::ControlFlow;

use arclog::registry::Registry;
use arclog::types::ValueType;

use crate::enumerate::{Space, Typed};
use crate::expression::{Feature, Leaf};
use crate::schema::{TableSchema, Tables};

/// The hole of a TableVector's one table, which stands for every table.
pub const TABLE_HOLE: &str = "&table";

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
        Feature::Nonempty(_) | Feature::Cardinality(_) | Feature::Ratio(..) => true,
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
