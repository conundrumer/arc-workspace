//! The rows of a table at one assignment, as the engine holds them, for the reader that
//! computes the table's shape values.
//!
//! The summary of an assignment holds a relation for each distinct TableRows of each example,
//! and the relation shares the engine's rows, so a summary copies none of them. The reader
//! writes them out as cells when it walks the table.

use arclog::relations::{Relation, RelationPart};
use arclog::types::ValueType;

/// One distinct TableRows.
#[derive(Debug)]
pub struct ShapeModel {
    /// The rows, as parts that share the engine's rows.
    pub relation: Relation,
    /// The count of rows, which is the product of the parts' counts.
    pub rows: u64,
}

impl ShapeModel {
    /// The model of `relation`: a relation of its own over the same parts, which keeps none of the indexes the engine built on `relation`.
    pub fn of(relation: &Relation) -> ShapeModel {
        let parts: Vec<RelationPart> = relation.parts().to_vec();
        ShapeModel { relation: Relation::from_parts(relation.arity(), parts.into_boxed_slice()), rows: relation.len() }
    }

    /// The cells that the parts hold, which a cache of summaries bounds.
    pub fn cells(&self) -> usize {
        self.relation.parts().iter().map(|part| part.rows.len().saturating_mul(part.columns.len())).fold(0usize, usize::saturating_add)
    }
}

/// An example's TableRows, each distinct one once.
#[derive(Debug)]
pub struct ShapeExample {
    /// 0 for the task, 1 for a train example, 2 for a test example, as [`crate::summary::ExampleKey::kind`].
    pub kind: u8,
    pub index: u32,
    /// Empty where the example has no TableRows: each model is Undefined or stopped, or the example has no entry.
    pub models: Vec<ShapeModel>,
}

/// A table at one assignment, as the reader of shape values takes it.
#[derive(Debug)]
pub struct ShapeRows {
    pub types: Vec<ValueType>,
    /// The count of train examples of the task.
    pub train: usize,
    pub examples: Vec<ShapeExample>,
}

impl ShapeRows {
    /// The cells that the relations hold, which a cache of summaries bounds.
    pub fn cells(&self) -> usize {
        self.examples.iter().flat_map(|example| &example.models).map(ShapeModel::cells).fold(0usize, usize::saturating_add)
    }
}

/// The shape rows of a summary, none where it holds none.
pub type SharedShapeRows = Option<std::sync::Arc<ShapeRows>>;
