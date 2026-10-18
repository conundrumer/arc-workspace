//! The grid of `&output`, read by its grid columns, as
//! `docs/arclog/constraints.md#the-output-set` gives.

use crate::relations::{ColumnIndex, ColumnOrder, Relation};
use crate::task::Grid;
use crate::terms::{Color, Constant, Term};
use crate::types::ValueType;

/// The grid columns of `&output`: one column of type Position and one of
/// type Color.
#[derive(Clone, Copy, PartialEq, Eq, Hash, Debug)]
pub struct GridColumns {
    pub position: ColumnIndex,
    pub color: ColumnIndex,
}

/// The pairs of a Position column and a Color column of a relation whose
/// columns take `types`, each a candidate for its grid columns.
pub fn candidate_columns(types: &[ValueType]) -> Vec<GridColumns> {
    let of = |ty: ValueType| types.iter().enumerate().filter(move |(_, t)| **t == ty).map(|(i, _)| ColumnIndex(i as u16));
    of(ValueType::Box).flat_map(|position| of(ValueType::Color).map(move |color| GridColumns { position, color })).collect()
}

/// The grid that `relation` gives by `columns`, or `None` where a cell of
/// the grid's frame has no color or two, or where the positions fill no
/// frame of at least one row and one column.
pub fn read_grid(relation: &Relation, columns: GridColumns) -> Option<Grid> {
    let index = relation.index(&ColumnOrder(Box::new([columns.position, columns.color])));
    let mut frame: Option<(usize, usize)> = None;
    let mut cells: Vec<Option<Color>> = Vec::new();
    for (position, colors) in index.entries() {
        let Term::Box(margins) = Term::decode(position, &ValueType::Box) else { unreachable!("a Box decodes to a Box") };
        let (row, column) = (usize::try_from(margins.top).ok()?, usize::try_from(margins.left).ok()?);
        let extent = (row + usize::try_from(margins.bottom).ok()? + 1, column + usize::try_from(margins.right).ok()? + 1);
        if *frame.get_or_insert(extent) != extent {
            return None;
        }
        let mut found = colors.entries();
        let (Some((color, _)), None) = (found.next(), found.next()) else { return None };
        let Term::Constant(Constant::Color(color)) = Term::decode(color, &ValueType::Color) else {
            unreachable!("a Color decodes to a Color")
        };
        cells.resize(extent.0 * extent.1, None);
        cells[row * extent.1 + column] = Some(color);
    }
    let (height, width) = frame?;
    let rows: Option<Box<[Box<[Color]>]>> = cells.chunks(width).map(|row| row.iter().copied().collect()).collect();
    debug_assert_eq!(cells.len(), height * width);
    Grid::from_rows(rows?)
}
