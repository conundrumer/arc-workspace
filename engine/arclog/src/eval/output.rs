//! The grid of `&output`, read by its grid columns, as
//! `docs/arclog/constraints.md#the-output-set` gives.

#![allow(unused_variables, dead_code)]

use crate::relations::{ColumnIndex, Relation};
use crate::task::Grid;

/// The grid columns of `&output`: one column of type Position and one of
/// type Color.
#[derive(Clone, Copy, PartialEq, Eq, Hash, Debug)]
pub struct GridColumns {
    pub position: ColumnIndex,
    pub color: ColumnIndex,
}

/// The pairs of a Position column and a Color column of a relation whose
/// columns take `types`, each a candidate for its grid columns.
pub fn candidate_columns(types: &[crate::types::ValueType]) -> Vec<GridColumns> {
    todo!()
}

/// The grid that `relation` gives by `columns`, or `None` where a cell of
/// the grid's frame has no color or two, or where the positions fill no
/// frame of at least one row and one column.
pub fn read_grid(relation: &Relation, columns: GridColumns) -> Option<Grid> {
    todo!()
}
