//! Agreement, Periods, Occurrences and Wallpaper: comparisons of valued
//! families under correspondences. Agreement's comparison is `compare`,
//! and Periods, Occurrences and Wallpaper each test their candidates by it,
//! as `docs/lib-spec.md#detectors` gives.
//!
//! Each reads the box algebra and the orientation algebra through
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
use arclog::terms::{Margins, Term, TermId};
use arclog::types::ValueType;

/// The mismatches and conflicts of two valued families under each
/// correspondence of their indices.
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
        let [source, target, correspondence] = group.inputs else { panic!("Agreement's three inputs") };
        let (index, corr) = agreement_widths(group.types);
        let source = Family::of(source, index);
        let target = Family::of(target, index);
        let mut pairs: StableHashMap<&[TermId], Vec<(&[TermId], &[TermId])>> = StableHashMap::default();
        for row in correspondence.rows() {
            let (m, rest) = row.split_at(corr);
            let (i, j) = rest.split_at(index);
            pairs.entry(m).or_default().push((i, j));
        }
        let mut mismatch = RowSet::empty(corr as u16);
        let mut conflict = RowSet::empty(corr as u16);
        for (m, pairs) in pairs {
            let verdict = compare(&source, &target, pairs, context.budget)?;
            if verdict.mismatch {
                mismatch.insert(m.into());
            }
            if verdict.conflict {
                conflict.insert(m.into());
            }
        }
        outputs(vec![mismatch, conflict], context.budget)
    }
}

/// The translations that fix the group's valued set, the least per axis,
/// and those read through sparse damage.
///
/// A translation is one per axis and magnitude, toward the bottom or the
/// right edge: the other direction pairs the same cells the other way, and
/// the cells of a pair compare alike both ways. Each line pair of a translation,
/// the line of a cell and the line of its image, is one correspondence, and
/// a line pair is broken where a cell of it conflicts with its image.
#[derive(Clone, Copy, Debug, Default)]
pub struct Periods;

impl Construction for Periods {
    fn name(&self) -> &'static str {
        Self::NAME
    }

    fn evaluate(
        &self,
        group: &GroupInputs<'_>,
        context: &mut ConstructionContext<'_, '_>,
    ) -> Result<GroupOutputs, ReachedBound> {
        let [cell] = group.inputs else { panic!("Periods' one input") };
        let lib = Lib(context.registry);
        let cells = Family::of(cell, 1);
        let mut translations: StableHashSet<(TermId, i32)> = StableHashSet::default();
        for p in cells.indices() {
            translations.extend(lib.sub_extents(p[0])?);
        }
        let (mut period, mut fundamental, mut approximate) = (RowSet::empty(2), RowSet::empty(2), RowSet::empty(2));
        let mut least: StableHashMap<TermId, i32> = StableHashMap::default();
        for (axis, k) in translations {
            context.budget.charge_work(1)?;
            let delta = lib.translation(axis, k)?;
            let mut lines: StableHashMap<TermId, Vec<([TermId; 1], [TermId; 1])>> = StableHashMap::default();
            for p in cells.indices() {
                let q = lib.compose(p[0], delta)?;
                if cells.values(&[q]).is_some() {
                    lines.entry(lib.line(p[0], axis)?).or_default().push(([p[0]], [q]));
                }
            }
            let witnessed = !lines.is_empty();
            let mut broken = 0usize;
            for pairs in lines.values() {
                broken += usize::from(compare(&cells, &cells, pairs.iter(), context.budget)?.conflict);
            }
            let row: Row = [axis, Term::encode_number(k)].into();
            if broken == 0 {
                period.insert(row.clone());
                if witnessed {
                    let at = least.entry(axis).or_insert(k);
                    *at = (*at).min(k);
                }
            }
            if broken <= lines.len() - broken {
                approximate.insert(row);
            }
        }
        for (axis, k) in least {
            fundamental.insert([axis, Term::encode_number(k)].into());
        }
        outputs(vec![period, fundamental, approximate], context.budget)
    }
}

/// The placements of each shape under each admitted D4 element, as
/// candidates and as occurrences.
///
/// A placement is the offset that takes the transformed shape onto the
/// cells, and it is one correspondence: each shape cell with the cell it
/// lands on.
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
                images.push((s[0], lib.apply(d, s[0])?));
            }
            let mut placements: StableHashSet<TermId> = StableHashSet::default();
            for row in shape_rows.rows() {
                let image = lib.apply(d, row[0])?;
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
                candidate.insert([d, m].into());
                if !compare(&shape, &cells, pairs, context.budget)?.mismatch {
                    occurrence.insert([d, m].into());
                }
            }
        }
        outputs(vec![candidate, occurrence], context.budget)
    }
}

/// The isometries that fix a periodic valued set, each with every shift
/// of its coset under the lattice.
///
/// The lattice holds the translations by a multiple of the period on each
/// axis that has a `period` row, and by none on an axis that has none. A
/// candidate is a transform with one coset, given by a shift along each
/// axis less than the period and the frame's extent; a transform that is
/// its own inverse is a candidate only where the candidate's square, a
/// translation, lies in the lattice, or lies off both axes, where the
/// cells decide. A candidate is one correspondence: each cell with each
/// cell that some shift of the coset takes it onto. It is a symmetry where
/// some cell goes onto another cell and none conflicts with its image.
#[derive(Clone, Copy, Debug, Default)]
pub struct Wallpaper;

impl Construction for Wallpaper {
    fn name(&self) -> &'static str {
        Self::NAME
    }

    fn evaluate(
        &self,
        group: &GroupInputs<'_>,
        context: &mut ConstructionContext<'_, '_>,
    ) -> Result<GroupOutputs, ReachedBound> {
        let [transform, cell, grid, period] = group.inputs else { panic!("Wallpaper's four inputs") };
        let lib = Lib(context.registry);
        let lattice = Lattice::of(period);
        let grid: StableHashSet<TermId> = grid.rows().map(|row| row[0]).collect();
        let mut cells = RowSet::empty(cell.arity());
        for row in cell.rows().filter(|row| grid.contains(&row[0])) {
            cells.insert(row.into());
        }
        let cells = Family::of(&cells, 1);
        let mut by_class: StableHashMap<Class, Vec<TermId>> = StableHashMap::default();
        for &p in &grid {
            by_class.entry(lattice.class(p)).or_default().push(p);
        }

        let (mut symmetry, mut action) = (RowSet::empty(2), RowSet::empty(2));
        for members in by_class.values() {
            for &p in members {
                for &q in members.iter().filter(|&&q| q != p) {
                    action.insert([p, q].into());
                }
            }
        }
        let shifts = lib.cosets(&grid, &lattice)?;
        for d in transform.rows() {
            let d = d[0];
            let involution = lib.inverse(d)? == d;
            for &delta in &shifts {
                context.budget.charge_work(1)?;
                if involution && !lattice.admits_square(lib.compose(delta, lib.apply(d, delta)?)?) {
                    continue;
                }
                let mut reach: Vec<(TermId, TermId, &[TermId])> = Vec::new();
                for &p in &grid {
                    let image = lib.apply(d, p)?;
                    let landed = by_class.get(&lattice.class(lib.compose(image, delta)?));
                    reach.push((p, image, landed.map_or(&[], Vec::as_slice)));
                }
                let pairs: Vec<([TermId; 1], [TermId; 1])> = reach
                    .iter()
                    .filter(|(p, _, _)| cells.values(&[*p]).is_some())
                    .flat_map(|&(p, _, landed)| landed.iter().filter(|&&q| cells.values(&[q]).is_some()).map(move |&q| ([p], [q])))
                    .collect();
                let witnessed = pairs.iter().any(|(p, q)| p != q);
                if !witnessed || compare(&cells, &cells, pairs.iter(), context.budget)?.conflict {
                    continue;
                }
                for &(p, image, landed) in &reach {
                    for &q in landed {
                        action.insert([p, q].into());
                        symmetry.insert([d, lib.relative(image, q)?].into());
                    }
                }
            }
        }
        outputs(vec![symmetry, action], context.budget)
    }
}

/// What Agreement's comparison found under one correspondence: whether some
/// image lacks its source's value, and whether some image holds a value
/// other than it.
#[derive(Clone, Copy, Debug, Default)]
struct Verdict {
    mismatch: bool,
    conflict: bool,
}

/// Agreement's comparison of `source` with `target` under one
/// correspondence, given as its pairs of a source index and a target index.
fn compare<I: AsRef<[TermId]>, J: AsRef<[TermId]>>(
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
struct Family {
    by_index: StableHashMap<Row, StableHashSet<Row>>,
}

impl Family {
    /// The family of `rows`, whose first `width` columns are the index and
    /// whose other columns are the value.
    fn of(rows: &RowSet, width: usize) -> Family {
        let mut by_index: StableHashMap<Row, StableHashSet<Row>> = StableHashMap::default();
        for row in rows.rows() {
            let (index, value) = row.split_at(width);
            by_index.entry(index.into()).or_default().insert(value.into());
        }
        Family { by_index }
    }

    /// The values at `index`, where the family has one.
    fn values(&self, index: &[TermId]) -> Option<&StableHashSet<Row>> {
        self.by_index.get(index)
    }

    /// Each index of the family.
    fn indices(&self) -> impl Iterator<Item = &[TermId]> + '_ {
        self.by_index.keys().map(|index| &**index)
    }
}

/// The widths of Agreement's `Index` and `Corr` from the types of its
/// inputs, which are the source's `(i, v)`, the target's `(i, v)` and the
/// correspondence's `(m, i, j)`, each type parameter bound to one or more
/// columns. Widths that the types do not settle are a fault.
fn agreement_widths(types: &[Box<[ValueType]>]) -> (usize, usize) {
    let [source, target, correspondence] = types else { panic!("Agreement's three inputs") };
    assert_eq!(source, target, "Agreement's source and target of one type");
    let settled: Vec<(usize, usize)> = (1..source.len())
        .filter_map(|index| {
            let corr = correspondence.len().checked_sub(2 * index).filter(|&corr| corr > 0)?;
            let (i, j) = correspondence[corr..].split_at(index);
            (i == &source[..index] && j == i).then_some((index, corr))
        })
        .collect();
    match settled[..] {
        [widths] => widths,
        _ => panic!("the types of Agreement's inputs settle {} widths of its Index and Corr: {types:?}", settled.len()),
    }
}

/// The lattice class of a Box: on each axis, its margin from the top or the
/// left edge, modulo the period where the axis has one, and the sum of its
/// margins on that axis. Two Boxes are in one class where a translation of
/// the lattice takes one onto the other.
type Class = (i32, i32, i32, i32);

/// The period of each axis, where it has one.
#[derive(Clone, Copy, Debug)]
struct Lattice {
    vertical: Option<i32>,
    horizontal: Option<i32>,
}

impl Lattice {
    /// The lattice of the `period` rows `(A, K)`. An axis with more than
    /// one row, or with a period that is not positive, is a fault.
    fn of(period: &RowSet) -> Lattice {
        let mut lattice = Lattice { vertical: None, horizontal: None };
        for row in period.rows() {
            let k = Term::decode_number(row[1]);
            assert!(k > 0, "Wallpaper's period {k} is not positive");
            let axis = if is_vertical(row[0]) { &mut lattice.vertical } else { &mut lattice.horizontal };
            assert!(axis.replace(k).is_none(), "Wallpaper's two periods on one axis");
        }
        lattice
    }

    /// The period of `axis`, where it has one.
    fn of_axis(&self, axis: TermId) -> Option<i32> {
        if is_vertical(axis) { self.vertical } else { self.horizontal }
    }

    /// The class of the Box `x`.
    fn class(&self, x: TermId) -> Class {
        let m = Term::decode_box(x);
        let residue = |margin: i32, period: Option<i32>| period.map_or(margin, |k| margin.rem_euclid(k));
        (residue(m.top, self.vertical), m.top + m.bottom, residue(m.left, self.horizontal), m.left + m.right)
    }

    /// Whether the translation `s` lies in the lattice, or lies off both
    /// axes.
    fn admits_square(&self, s: TermId) -> bool {
        let m = Term::decode_box(s);
        let in_lattice = |shift: i32, period: Option<i32>| period.map_or(shift == 0, |k| shift % k == 0);
        (m.top != 0 && m.left != 0) || (in_lattice(m.top, self.vertical) && in_lattice(m.left, self.horizontal))
    }
}

/// Whether the Axis `axis` is the vertical one.
fn is_vertical(axis: TermId) -> bool {
    Geometry::get().axis_edges(axis).contains(Edge::Top)
}

/// The outputs `outputs`, each row of them counted against `budget`.
fn outputs(outputs: Vec<RowSet>, budget: &mut Budget<'_>) -> Result<GroupOutputs, ReachedBound> {
    budget.charge_rows(outputs.iter().map(|rows| rows.len() as u64).sum())?;
    Ok(GroupOutputs { outputs: outputs.into() })
}

/// The relations of the lib these detectors read, evaluated through
/// [`Algebra`] over the registry.
#[derive(Clone, Copy)]
struct Lib<'r>(&'r Registry);

impl Lib<'_> {
    /// Each row of the relation `name` that agrees with `bound`.
    fn rows(&self, name: &str, bound: &[Option<TermId>]) -> Result<Vec<Row>, ReachedBound> {
        let relation: &dyn Algebra = algebra(&LibName(name.into())).unwrap_or_else(|| panic!("the lib relation `{name}`"));
        let mut rows = Vec::new();
        relation.evaluate(bound, self.0, &mut |row| rows.push(row.into())).map_err(ReachedBound::Margin)?;
        Ok(rows)
    }

    /// The value of the last column of the one row of `name` at `bound`,
    /// which binds every other column.
    fn image(&self, name: &str, bound: &[Option<TermId>]) -> Result<TermId, ReachedBound> {
        match &self.rows(name, bound)?[..] {
            [row] => Ok(*row.last().expect("a row of some column")),
            rows => panic!("`{name}` gives {} rows at a binding of each column but its last", rows.len()),
        }
    }

    /// The image of the Box `p` under the D4 element `d`.
    fn apply(&self, d: TermId, p: TermId) -> Result<TermId, ReachedBound> {
        self.image("apply", &[Some(d), Some(p), None])
    }

    /// The Box `a` translated by `b`.
    fn compose(&self, a: TermId, b: TermId) -> Result<TermId, ReachedBound> {
        self.image("compose", &[Some(a), Some(b), None])
    }

    /// The translation that takes the Box `base` onto `x`.
    fn relative(&self, base: TermId, x: TermId) -> Result<TermId, ReachedBound> {
        self.image("relative", &[Some(base), Some(x), None])
    }

    /// The inverse of the D4 element `d`.
    fn inverse(&self, d: TermId) -> Result<TermId, ReachedBound> {
        self.image("d4_inverse", &[Some(d), None])
    }

    /// Each axis with each translation magnitude that the frame of the
    /// Position `p` admits on it.
    fn sub_extents(&self, p: TermId) -> Result<Vec<(TermId, i32)>, ReachedBound> {
        let rows = self.rows("sub_extent", &[Some(p), None, None])?;
        Ok(rows.iter().map(|row| (row[1], Term::decode_number(row[2]))).collect())
    }

    /// The translation by `k` along `axis`, toward its bottom or right
    /// edge.
    fn translation(&self, axis: TermId, k: i32) -> Result<TermId, ReachedBound> {
        let geometry = Geometry::get();
        let edge = geometry.axis_edges(axis).each().find(|edge| matches!(edge, Edge::Bottom | Edge::Right)).expect("an axis with a bottom or a right edge");
        let toward = geometry.direction(Edges::of(&[edge])).expect("the Dir of an edge");
        self.image("jump_offset", &[Some(toward), Some(Term::encode_number(k)), None])
    }

    /// The line of the Position `p` across `axis`: its margins on the edges
    /// of `axis`.
    fn line(&self, p: TermId, axis: TermId) -> Result<TermId, ReachedBound> {
        match &self.rows("split", &[Some(p), Some(axis), None, None])?[..] {
            [row] => Ok(row[2]),
            rows => panic!("`split` gives {} rows at a Box and an axis", rows.len()),
        }
    }

    /// One shift of each coset of `lattice` that the frame of `grid`
    /// admits: on each axis, zero, or, on an axis with a period, a
    /// magnitude that the frame admits and that is less than the period,
    /// toward the bottom or right edge.
    fn cosets(&self, grid: &StableHashSet<TermId>, lattice: &Lattice) -> Result<Vec<TermId>, ReachedBound> {
        let geometry = Geometry::get();
        let mut along: StableHashMap<TermId, StableHashSet<i32>> =
            geometry.domain(&ValueType::Axis).iter().map(|&axis| (axis, StableHashSet::from_iter([0]))).collect();
        for &p in grid {
            for (axis, k) in self.sub_extents(p)? {
                if lattice.of_axis(axis).is_some_and(|period| k < period) {
                    along.get_mut(&axis).expect("an axis of the domain").insert(k);
                }
            }
        }
        let zero = Term::Box(Margins { top: 0, bottom: 0, left: 0, right: 0 }).encode().expect("the zero translation");
        let mut shifts = vec![zero];
        for (axis, magnitudes) in along {
            let mut next = Vec::with_capacity(shifts.len() * magnitudes.len());
            for &shift in &shifts {
                for &k in &magnitudes {
                    next.push(self.compose(shift, self.translation(axis, k)?)?);
                }
            }
            shifts = next;
        }
        Ok(shifts)
    }
}
