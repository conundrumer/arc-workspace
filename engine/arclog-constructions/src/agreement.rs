//! Agreement: the comparison of valued families under correspondences, and
//! the lib reads the detectors share. Agreement's comparison is `compare`,
//! and Periods of [`crate::periods`], Occurrences of [`crate::occurrences`]
//! and Wallpaper of [`crate::wallpaper`] each test their candidates by it,
//! as `docs/lib-spec.md#detectors` gives.
//!
//! It reads the box algebra and the orientation algebra through
//! [`arclog::algebra::algebra`], and reads no order of term ids, cells or
//! rows.

use arclog::algebra::geometry::{Edge, Edges, Geometry};
use arclog::algebra::{algebra, Algebra};
use arclog::eval::instance::{Construction, ConstructionContext, GroupInputs, GroupOutputs};
use arclog::eval::join::Budget;
use arclog::eval::ReachedBound;
use arclog::hash::{StableHashMap, StableHashSet};
use arclog::registry::{LibName, Registry};
use arclog::relations::{Row, RowSet};
use arclog::terms::{Term, TermId};

/// The mismatches and conflicts of two valued families under each admitted
/// D4 element, whose correspondence pairs each source point, a Position or
/// an Offset, with its image under the element.
///
/// - in `source(key, P, v)`, `target(key, P, v)`.
/// - in `transform(D)`, shared, default all eight.
/// - out `mismatch(key, D)`: D is in `transform`, and for some source cell P, the cell `apply` of D to P gives is not a target cell of P's value: no target cell is there, or one of another value.
/// - out `conflict(key, D)`: for some source cell, its image is a target cell of another value. A missing target cell is no conflict.
/// - A D in `transform` with no `mismatch` row takes the source into the target. Target cells that are no source cell's image are not tested.
#[derive(Clone, Copy, Debug, Default)]
pub struct Agreement;

impl Construction for Agreement {
    fn name(&self) -> &'static str {
        Self::NAME
    }

    fn evaluate(
        &self,
        group: &GroupInputs<'_>,
        context: &mut ConstructionContext<'_, '_>,
    ) -> Result<GroupOutputs, ReachedBound> {
        let [source, target, transform] = group.inputs else { panic!("Agreement's three inputs") };
        let lib = Lib(context.registry);
        let source = Family::of(source, 1);
        let target = Family::of(target, 1);
        let (mut mismatch, mut conflict) = (RowSet::empty(1), RowSet::empty(1));
        for d in transform.rows() {
            let d = d[0];
            let mut pairs = Vec::new();
            for p in source.indices() {
                if let Some(image) = lib.try_apply(d, p[0])? {
                    pairs.push(([p[0]], [image]));
                }
            }
            let verdict = compare(&source, &target, pairs, context.budget)?;
            if verdict.mismatch && group.wanted[0] {
                mismatch.insert([d].into());
            }
            if verdict.conflict && group.wanted[1] {
                conflict.insert([d].into());
            }
        }
        outputs(vec![mismatch, conflict], context.budget)
    }
}

/// What Agreement's comparison found under one correspondence: whether some
/// image lacks its source's value, and whether some image holds a value
/// other than it.
#[derive(Clone, Copy, Debug, Default)]
pub(crate) struct Verdict {
    pub(crate) mismatch: bool,
    pub(crate) conflict: bool,
}

/// Agreement's comparison of `source` with `target` under one
/// correspondence, given as its pairs of a source index and a target index.
pub(crate) fn compare<I: AsRef<[TermId]>, J: AsRef<[TermId]>>(
    source: &Family,
    target: &Family,
    pairs: impl IntoIterator<Item = impl std::borrow::Borrow<(I, J)>>,
    budget: &mut Budget<'_>,
) -> Result<Verdict, ReachedBound> {
    let mut verdict = Verdict::default();
    let mut count = 0u64;
    for pair in pairs {
        let (i, j) = pair.borrow();
        count += 1;
        let Some(values) = source.values(i.as_ref()) else { continue };
        let images = target.values(j.as_ref());
        for value in values {
            match images {
                None => verdict.mismatch = true,
                Some(images) => {
                    verdict.mismatch |= !images.contains(value);
                    verdict.conflict |= images.iter().any(|image| image != value);
                }
            }
        }
        if verdict.mismatch && verdict.conflict {
            break;
        }
    }
    budget.charge_work(count)?;
    Ok(verdict)
}

/// A valued family: the values at each index.
#[derive(Debug, Default)]
pub(crate) struct Family {
    by_index: StableHashMap<Row, StableHashSet<Row>>,
}

impl Family {
    /// The family of `rows`, whose first `width` columns are the index and
    /// whose other columns are the value.
    pub(crate) fn of(rows: &RowSet, width: usize) -> Family {
        let mut by_index: StableHashMap<Row, StableHashSet<Row>> = StableHashMap::default();
        for row in rows.rows() {
            let (index, value) = row.split_at(width);
            by_index.entry(index.into()).or_default().insert(value.into());
        }
        Family { by_index }
    }

    /// The values at `index`, where the family has one.
    pub(crate) fn values(&self, index: &[TermId]) -> Option<&StableHashSet<Row>> {
        self.by_index.get(index)
    }

    /// Each index of the family.
    pub(crate) fn indices(&self) -> impl Iterator<Item = &[TermId]> + '_ {
        self.by_index.keys().map(|index| &**index)
    }
}

/// The outputs `outputs`, each row of them counted against `budget`.
pub(crate) fn outputs(outputs: Vec<RowSet>, budget: &mut Budget<'_>) -> Result<GroupOutputs, ReachedBound> {
    budget.charge_rows(outputs.iter().map(|rows| rows.len() as u64).sum())?;
    Ok(GroupOutputs { outputs: outputs.into() })
}

/// The relations of the lib these detectors read, evaluated through
/// [`Algebra`] over the registry.
#[derive(Clone, Copy)]
pub(crate) struct Lib<'r>(pub(crate) &'r Registry);

impl Lib<'_> {
    /// Each row of the relation `name` that agrees with `bound`.
    fn rows(&self, name: &str, bound: &[Option<TermId>]) -> Result<Vec<Row>, ReachedBound> {
        let relation: &dyn Algebra = algebra(&LibName(name.into())).unwrap_or_else(|| panic!("the lib relation `{name}`"));
        let mut rows = Vec::new();
        relation.evaluate(bound, self.0, &mut |row| rows.push(row.into())).map_err(ReachedBound::Margin)?;
        Ok(rows)
    }

    /// The value of the last column of the row of `name` at `bound`, which
    /// binds every other column, or `None` where `name` holds no row there.
    fn partial_image(&self, name: &str, bound: &[Option<TermId>]) -> Result<Option<TermId>, ReachedBound> {
        match &self.rows(name, bound)?[..] {
            [] => Ok(None),
            [row] => Ok(Some(*row.last().expect("a row of some column"))),
            rows => panic!("`{name}` gives {} rows at a binding of each column but its last", rows.len()),
        }
    }

    /// The value of the last column of the one row of `name` at `bound`,
    /// which binds every other column.
    fn image(&self, name: &str, bound: &[Option<TermId>]) -> Result<TermId, ReachedBound> {
        let image = self.partial_image(name, bound)?;
        Ok(image.unwrap_or_else(|| panic!("`{name}` gives no row at a binding of each column but its last")))
    }

    /// The image of the Box `p` under the D4 element `d`.
    pub(crate) fn apply(&self, d: TermId, p: TermId) -> Result<TermId, ReachedBound> {
        self.image("apply", &[Some(d), Some(p), None])
    }

    /// The image of the Box `p` under `d`, or `None` where `d` is no D4
    /// element, where `apply` holds no row.
    pub(crate) fn try_apply(&self, d: TermId, p: TermId) -> Result<Option<TermId>, ReachedBound> {
        self.partial_image("apply", &[Some(d), Some(p), None])
    }

    /// The Box `a` translated by `b`.
    pub(crate) fn compose(&self, a: TermId, b: TermId) -> Result<TermId, ReachedBound> {
        self.image("compose", &[Some(a), Some(b), None])
    }

    /// The translation that takes the Box `base` onto `x`.
    pub(crate) fn relative(&self, base: TermId, x: TermId) -> Result<TermId, ReachedBound> {
        self.image("relative", &[Some(base), Some(x), None])
    }

    /// The inverse of `d`, or `None` where `d` is no D4 element, where
    /// `d4_inverse` holds no row.
    pub(crate) fn inverse(&self, d: TermId) -> Result<Option<TermId>, ReachedBound> {
        self.partial_image("d4_inverse", &[Some(d), None])
    }

    /// Each axis with each translation magnitude that the frame of the
    /// Position `p` admits on it.
    pub(crate) fn sub_extents(&self, p: TermId) -> Result<Vec<(TermId, i32)>, ReachedBound> {
        let rows = self.rows("sub_extent", &[Some(p), None, None])?;
        Ok(rows.iter().map(|row| (row[1], Term::decode_number(row[2]))).collect())
    }

    /// The translation by `k` along `axis`, toward its bottom or right
    /// edge, and toward the opposite edge where `k` is negative.
    pub(crate) fn translation(&self, axis: TermId, k: i32) -> Result<TermId, ReachedBound> {
        let geometry = Geometry::get();
        let edge = geometry.axis_edges(axis).each().find(|edge| matches!(edge, Edge::Bottom | Edge::Right)).expect("an axis with a bottom or a right edge");
        let toward = geometry.direction(Edges::of(&[edge])).expect("the Dir of an edge");
        self.image("jump_offset", &[Some(toward), Some(Term::encode_number(k)), None])
    }

    /// The line of the Position `p` across `axis`: its margins on the edges
    /// of `axis`.
    pub(crate) fn line(&self, p: TermId, axis: TermId) -> Result<TermId, ReachedBound> {
        match &self.rows("split", &[Some(p), Some(axis), None, None])?[..] {
            [row] => Ok(row[2]),
            rows => panic!("`split` gives {} rows at a Box and an axis", rows.len()),
        }
    }
}
