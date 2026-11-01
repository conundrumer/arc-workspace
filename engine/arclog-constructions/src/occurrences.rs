//! Occurrences: the placements of each shape under each D4 element, each
//! tested by Agreement's comparison of [`crate::agreement`], as
//! `docs/lib-spec.md#detectors` gives.
//!
//! It reads the box algebra and the orientation algebra through
//! [`arclog::algebra::algebra`], and reads no order of term ids, cells or
//! rows.

use arclog::eval::instance::{Construction, ConstructionContext, GroupInputs, GroupOutputs};
use arclog::eval::ReachedBound;
use arclog::hash::{StableHashMap, StableHashSet};
use arclog::relations::RowSet;
use arclog::terms::TermId;

use crate::agreement::{compare, outputs, Family, Lib};

/// The placements of each shape under each admitted D4 element, as
/// candidates and as occurrences.
///
/// A placement is the offset that takes the transformed shape onto the
/// cells, and it is one correspondence: each shape cell with the cell it
/// lands on.
///
/// - in `cell(key, P, v)`: the cells and their values.
/// - in `shape(key, P, v)`: the shape's cells and their values.
/// - in `transform(D)`, shared, default the identity: the D4 images of the shape to place.
/// - out `occurrence(key, D, P)`: P is an offset, and D is in `transform`. For every shape cell S of value v, the cell that `apply` of D to S, then `compose` with P, gives is a `cell` row of value v. P moves the D-image of the shape onto the cells.
/// - out `candidate(key, D, P)`: the same, where at least one shape cell lands on a cell of its value. Every occurrence is a candidate.
/// - Only the cells `cell` holds count.
#[derive(Clone, Copy, Debug, Default)]
pub struct Occurrences;

impl Construction for Occurrences {
    fn name(&self) -> &'static str {
        Self::NAME
    }

    fn evaluate(
        &self,
        group: &GroupInputs<'_>,
        context: &mut ConstructionContext<'_, '_>,
    ) -> Result<GroupOutputs, ReachedBound> {
        let [cell, shape_rows, transform] = group.inputs else { panic!("Occurrences' three inputs") };
        let lib = Lib(context.registry);
        let cells = Family::of(cell, 1);
        let shape = Family::of(shape_rows, 1);
        let mut at_value: StableHashMap<&[TermId], Vec<TermId>> = StableHashMap::default();
        for row in cell.rows() {
            at_value.entry(&row[1..]).or_default().push(row[0]);
        }
        let (mut candidate, mut occurrence) = (RowSet::empty(2), RowSet::empty(2));
        for d in transform.rows() {
            let d = d[0];
            let mut images: Vec<(TermId, TermId)> = Vec::new();
            for s in shape.indices() {
                if let Some(image) = lib.try_apply(d, s[0])? {
                    images.push((s[0], image));
                }
            }
            let mut placements: StableHashSet<TermId> = StableHashSet::default();
            for row in shape_rows.rows() {
                let Some(image) = lib.try_apply(d, row[0])? else { continue };
                for &p in at_value.get(&row[1..]).into_iter().flatten() {
                    context.budget.charge_work(1)?;
                    placements.insert(lib.relative(image, p)?);
                }
            }
            for m in placements {
                let mut pairs = Vec::with_capacity(images.len());
                for &(s, image) in &images {
                    pairs.push(([s], [lib.compose(m, image)?]));
                }
                if group.wanted[0] {
                    candidate.insert([d, m].into());
                }
                if group.wanted[1] && !compare(&shape, &cells, pairs, context.budget)?.mismatch {
                    occurrence.insert([d, m].into());
                }
            }
        }
        outputs(vec![candidate, occurrence], context.budget)
    }
}
