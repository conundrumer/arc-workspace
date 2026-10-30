//! Division, Tiling, Frame and ExtentDivisions: arithmetic over extents.
//!
//! A Position is a Box of margins, its distances to the frame's edges. On an
//! axis, a cell's two margins are its near and far margin, and their sum
//! plus 1 is the frame's extent on the axis. Each construction computes on
//! each axis apart, and composes the two axes' parts by adding their
//! margins, as `programs/lib/box.dl` gives `compose`.

use arclog::algebra::boxes::{compose, divide, margin, margins};
use arclog::algebra::geometry::{Edge, Geometry};
use arclog::eval::ReachedBound;
use arclog::eval::instance::{Construction, ConstructionContext, GroupInputs, GroupOutputs};
use arclog::hash::StableHashSet;
use arclog::relations::RowSet;
use arclog::terms::{Margins, Term, TermId};
use arclog::types::ValueType;

/// Equal parts per axis, by count or by side, with a gap.
///
/// - in `cell(key, P)`: the cells to cut.
/// - in `parts(key, A, N)`: N parts along A. Or `side(key, A, K)`: parts of K cells along A. An axis with neither is one part.
/// - in `gap(key, A, G)`: G cells between each two parts along A. An axis with no row has gap 0.
/// - out `tile(key, P, P_outer, P_inner)`: P is the cell P_inner of the part at P_outer. P_outer is a cell of the frame of parts.
/// - A cell is reported only when its distances from both ends place it in a complete part of the requested size; gap cells and inconsistent extents give no row.
#[derive(Clone, Copy, Debug, Default)]
pub struct Division;

impl Construction for Division {
    fn name(&self) -> &'static str {
        Self::NAME
    }

    fn evaluate(
        &self,
        group: &GroupInputs<'_>,
        context: &mut ConstructionContext<'_, '_>,
    ) -> Result<GroupOutputs, ReachedBound> {
        let [cell, parts, side, gap] = group.inputs else { panic!("Division's four inputs") };
        let cells: Vec<Margins> = cell.rows().map(|row| Term::decode_box(row[0])).collect();
        let axes = Axis::pair().map(|axis| AxisParts {
            parts: axis.numbers(parts),
            sides: axis.numbers(side),
            gaps: axis.gaps(gap),
            axis,
        });
        let mut tile = RowSet::empty(3);
        for &p in &cells {
            let [first, second] = [&axes[0], &axes[1]].map(|axis| axis.split(p));
            context.budget.charge_work((first.len() * second.len()) as u64 + 1)?;
            for &(outer_first, inner_first) in &first {
                for &(outer_second, inner_second) in &second {
                    let row = [p, compose(outer_first, outer_second), compose(inner_first, inner_second)];
                    if tile.insert(encode_row(&row)?) {
                        context.budget.charge_rows(1)?;
                    }
                }
            }
        }
        Ok(GroupOutputs { outputs: Box::new([tile]) })
    }
}

/// One axis of a Division's key group: its counts, sides and gaps.
struct AxisParts {
    axis: Axis,
    parts: Vec<i32>,
    sides: Vec<i32>,
    gaps: Vec<i32>,
}

impl AxisParts {
    /// Each part of `p` on the axis, as its outer and inner position, each
    /// on the axis alone. An axis given neither a count nor a side passes
    /// through: one part, the whole extent.
    fn split(&self, p: Margins) -> Vec<(Margins, Margins)> {
        let axis = self.axis;
        if self.parts.is_empty() && self.sides.is_empty() {
            return vec![(ZERO, axis.along(p))];
        }
        let mut split = Vec::new();
        for &g in &self.gaps {
            for &k in &self.sides {
                split.extend(axis.stride(p, k, g));
            }
            for &n in &self.parts {
                // The count gives the side that `n` parts fill the extent of
                // `p` alone with, as `divide` of `programs/lib/box.dl` gives
                // it. A cell that no side of `n` parts fills gets no part.
                let whole = axis.extent(p);
                if let Some(k) = side_of(whole, n, g) {
                    split.extend(axis.stride(p, k, g));
                }
                // One part spans the extent.
                split.extend(axis.stride(p, whole, g).filter(|&(outer, _)| axis.extent(outer) == n));
            }
        }
        split
    }
}

/// The side `k` of `n` parts with gap `g` between them that fill an extent
/// of `extent` with no remainder, where `n > 1`, `k >= 1` and
/// `1 - k <= g < extent`: `divide_gap` of `programs/lib/box.dl`.
fn side_of(extent: i32, n: i32, g: i32) -> Option<i32> {
    let (n, g64) = (i64::from(n), i64::from(g));
    let rest = i64::from(extent) - (n - 1) * g64;
    if n <= 1 || rest <= 0 || rest % n != 0 {
        return None;
    }
    let k = i32::try_from(rest / n).ok()?;
    (g64 >= 1 - i64::from(k) && g < extent).then_some(k)
}

/// The cells of a frame tiled by an inner frame at the outer positions,
/// with a gap per axis.
///
/// - in `outer(key, P)`: the frame of copies.
/// - in `inner(key, P)`: the frame of one copy.
/// - in `gap(key, A, G)`: G cells between each two copies along A. An axis with no row has gap 0.
/// - out `cell(key, P_outer, P_inner, P)`: P is the cell P_inner of the copy at P_outer.
#[derive(Clone, Copy, Debug, Default)]
pub struct Tiling;

impl Construction for Tiling {
    fn name(&self) -> &'static str {
        Self::NAME
    }

    fn evaluate(
        &self,
        group: &GroupInputs<'_>,
        context: &mut ConstructionContext<'_, '_>,
    ) -> Result<GroupOutputs, ReachedBound> {
        let [outer, inner, gap] = group.inputs else { panic!("Tiling's three inputs") };
        let [first, second] = Axis::pair();
        let (gaps_first, gaps_second) = (first.gaps(gap), second.gaps(gap));
        let mut cell = RowSet::empty(3);
        for outer_row in outer.rows() {
            let o = Term::decode_box(outer_row[0]);
            context.budget.charge_work((inner.len() * gaps_first.len() * gaps_second.len()) as u64 + 1)?;
            for inner_row in inner.rows() {
                let i = Term::decode_box(inner_row[0]);
                for &g_first in &gaps_first {
                    for &g_second in &gaps_second {
                        let p = compose(first.concat(o, i, g_first), second.concat(o, i, g_second));
                        if cell.insert(encode_row(&[o, i, p])?) {
                            context.budget.charge_rows(1)?;
                        }
                    }
                }
            }
        }
        Ok(GroupOutputs { outputs: Box::new([cell]) })
    }
}

/// The cells of a frame from its extent on each axis.
///
/// - in `extent(key, A, N)`, from the key: N cells along A. An axis with no row has extent 1.
/// - out `cell(key, P)`.
#[derive(Clone, Copy, Debug, Default)]
pub struct Frame;

impl Construction for Frame {
    fn name(&self) -> &'static str {
        Self::NAME
    }

    fn evaluate(
        &self,
        group: &GroupInputs<'_>,
        context: &mut ConstructionContext<'_, '_>,
    ) -> Result<GroupOutputs, ReachedBound> {
        let [extent] = group.inputs else { panic!("Frame's one input") };
        let [first, second] = Axis::pair().map(|axis| {
            let extents = axis.numbers(extent);
            // An axis with no `extent` row has extent 1.
            let extents = if extents.is_empty() { vec![1] } else { extents };
            extents.into_iter().flat_map(move |n| axis.frame(n)).collect::<Vec<_>>()
        });
        let mut cell = RowSet::empty(1);
        context.budget.charge_work((first.len() * second.len()) as u64 + 1)?;
        for &p_first in &first {
            for &p_second in &second {
                if cell.insert(encode_row(&[compose(p_first, p_second)])?) {
                    context.budget.charge_rows(1)?;
                }
            }
        }
        Ok(GroupOutputs { outputs: Box::new([cell]) })
    }
}

/// The divisions that a frame's extent admits on each axis.
///
/// - in `frame(key, P)`: the frame's cells.
/// - out `division(key, A, N, K, G)`: along A, N parts of K cells with G cells between each two fill the extent exactly. N is 2 or more and K is 1 or more. G can be less than 0, down to 1 less K: then two neighboring parts share that many lines.
#[derive(Clone, Copy, Debug, Default)]
pub struct ExtentDivisions;

impl Construction for ExtentDivisions {
    fn name(&self) -> &'static str {
        Self::NAME
    }

    fn evaluate(
        &self,
        group: &GroupInputs<'_>,
        context: &mut ConstructionContext<'_, '_>,
    ) -> Result<GroupOutputs, ReachedBound> {
        let [frame] = group.inputs else { panic!("ExtentDivisions' one input") };
        let mut division = RowSet::empty(4);
        for axis in Axis::each() {
            let extents: StableHashSet<i32> = frame.rows().map(|row| axis.extent(Term::decode_box(row[0]))).collect();
            for &extent in &extents {
                // The least gap, 1 - k, gives extent >= n + k - 1, so n is
                // at most the extent, and the gap is at least 1 - extent.
                context.budget.charge_work(2 * u64::from(extent.unsigned_abs()).pow(2) + 1)?;
                for n in 2..=extent {
                    for g in (1 - extent)..extent {
                        let Some(k) = side_of(extent, n, g) else { continue };
                        let row = [axis.id, Term::encode_number(n), Term::encode_number(k), Term::encode_number(g)];
                        if division.insert(row.into()) {
                            context.budget.charge_rows(1)?;
                        }
                    }
                }
            }
        }
        Ok(GroupOutputs { outputs: Box::new([division]) })
    }
}

/// An Axis constant with its near and far edge.
#[derive(Clone, Copy)]
struct Axis {
    id: TermId,
    near: Edge,
    far: Edge,
}

impl Axis {
    /// Each Axis constant of the registry.
    fn each() -> impl Iterator<Item = Axis> {
        let geometry = Geometry::get();
        geometry.domain(&ValueType::Axis).iter().map(move |&id| {
            let mut edges = geometry.axis_edges(id).each();
            let near = edges.next().expect("an axis's two edges");
            let far = edges.next().expect("an axis's two edges");
            Axis { id, near, far }
        })
    }

    /// The registry's two axes, in their order.
    fn pair() -> [Axis; 2] {
        let mut axes = Axis::each();
        let first = axes.next().expect("two axes");
        let second = axes.next().expect("two axes");
        [first, second]
    }

    /// The Box with margins `near` and `far` on this axis, and 0 on the
    /// other.
    fn only(self, near: i32, far: i32) -> Margins {
        margins(|e| if e == self.near { near } else if e == self.far { far } else { 0 })
    }

    /// `p` on this axis alone.
    fn along(self, p: Margins) -> Margins {
        self.only(margin(p, self.near), margin(p, self.far))
    }

    /// The extent of `p`'s frame on this axis.
    fn extent(self, p: Margins) -> i32 {
        margin(p, self.near) + margin(p, self.far) + 1
    }

    /// The numbers of the rows of `rows`, an input of an Axis column and a
    /// number column, on this axis.
    fn numbers(self, rows: &RowSet) -> Vec<i32> {
        rows.rows().filter(|row| row[0] == self.id).map(|row| Term::decode_number(row[1])).collect()
    }

    /// The gaps of the rows of `rows` on this axis, or 0 where it has none.
    fn gaps(self, rows: &RowSet) -> Vec<i32> {
        let gaps = self.numbers(rows);
        if gaps.is_empty() { vec![0] } else { gaps }
    }

    /// The cells of a frame of extent `n` on this axis, each on the axis
    /// alone.
    fn frame(self, n: i32) -> impl Iterator<Item = Margins> {
        (0..n.max(0)).map(move |k| self.only(k, n - 1 - k))
    }

    /// The part of `p` on this axis among parts of side `k` with gap `g`
    /// between them, as its outer and inner position, where `p` lies in a
    /// part that no edge of the frame cuts: `stride` of `programs/lib/box.dl`
    /// on each margin.
    fn stride(self, p: Margins, k: i32, g: i32) -> Option<(Margins, Margins)> {
        let (part_near, offset_near) = divide(margin(p, self.near), k, g)?;
        let (part_far, offset_far) = divide(margin(p, self.far), k, g)?;
        let inner = self.only(offset_near, offset_far);
        (self.extent(inner) == k).then(|| (self.only(part_near, part_far), inner))
    }

    /// The cell at inner position `i` of the tile at outer position `o`, on
    /// this axis, with gap `g` between tiles: `box_concat` of
    /// `programs/lib_functors.cpp`.
    fn concat(self, o: Margins, i: Margins, g: i32) -> Margins {
        let period = self.extent(i) + g;
        let at = |edge: Edge| margin(o, edge).saturating_mul(period).saturating_add(margin(i, edge));
        self.only(at(self.near), at(self.far))
    }
}

/// The Box of margins 0, the frame itself.
const ZERO: Margins = Margins { top: 0, bottom: 0, left: 0, right: 0 };

/// The term ids of `positions`, or the margin bound where one has a margin
/// outside a byte.
fn encode_row(positions: &[Margins]) -> Result<Box<[TermId]>, ReachedBound> {
    positions.iter().map(|&p| Term::Box(p).encode().map_err(ReachedBound::Margin)).collect()
}

#[cfg(test)]
mod tests {
    use super::*;

    /// The inner extents of the parts of `p` on `axis` that a count of 3
    /// with gap 0 gives.
    fn inner_extents_of_three_parts(axis: Axis, p: Margins) -> Vec<i32> {
        let parts = AxisParts { axis, parts: vec![3], sides: vec![], gaps: vec![0] };
        parts.split(p).into_iter().map(|(_, inner)| axis.extent(inner)).collect()
    }

    /// A count cuts a cell by the side that its own extent gives, as `divide`
    /// does: a cell of extent 6 gets parts of side 2 whatever the other cells
    /// of its key are, and a cell of extent 7, which 3 parts do not fill, gets
    /// no part.
    #[test]
    fn a_count_cuts_each_cell_by_the_side_of_its_own_extent() {
        let [axis, _] = Axis::pair();
        let cell = |extent: i32| axis.only(0, extent - 1);
        assert_eq!(inner_extents_of_three_parts(axis, cell(6)), [2]);
        assert_eq!(inner_extents_of_three_parts(axis, cell(9)), [3]);
        assert!(inner_extents_of_three_parts(axis, cell(7)).is_empty());
    }
}
