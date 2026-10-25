//! Wallpaper: the isometries that fix a periodic valued set, each candidate
//! tested by Agreement's comparison of [`crate::agreement`], as
//! `docs/lib-spec.md#detectors` gives.
//!
//! It reads the box algebra and the orientation algebra through
//! [`arclog::algebra::algebra`], and reads no order of term ids, cells or
//! rows.

use arclog::algebra::geometry::{Edge, Geometry};
use arclog::eval::instance::{Construction, ConstructionContext, GroupInputs, GroupOutputs};
use arclog::eval::ReachedBound;
use arclog::hash::{StableHashMap, StableHashSet};
use arclog::relations::RowSet;
use arclog::terms::{Margins, Term, TermId};
use arclog::types::ValueType;

use crate::agreement::{compare, outputs, Family, Lib};
use crate::domain;

/// The isometries that fix a periodic valued set, each with every shift
/// of its coset of the period translations.
///
/// The period translations are the translations by a multiple of the period
/// on each axis that has a `period` row, and by none on an axis that has none. A
/// candidate is a transform with one coset, given by a shift along each
/// axis less than the period and the frame's extent; a transform that is
/// its own inverse is a candidate only where the candidate's square, a
/// translation, lies in the period translations, or lies off both axes, where the
/// cells decide. A candidate is one correspondence: each cell with each
/// cell that some shift of the coset takes it onto. It is a symmetry where
/// some cell goes onto another cell and none conflicts with its image.
///
/// A group outside its domain of [`crate::domain`], with two periods on one
/// axis or a period that is not positive, is undefined.
#[derive(Clone, Copy, Debug, Default)]
pub struct Wallpaper;

impl Construction for Wallpaper {
    fn name(&self) -> &'static str {
        Self::NAME
    }

    fn outside_domain(&self, group: &GroupInputs<'_>) -> bool {
        domain::check(Self::NAME, group.inputs).is_some()
    }

    fn evaluate(
        &self,
        group: &GroupInputs<'_>,
        context: &mut ConstructionContext<'_, '_>,
    ) -> Result<GroupOutputs, ReachedBound> {
        let [transform, cell, grid, period] = group.inputs else { panic!("Wallpaper's four inputs") };
        let lib = Lib(context.registry);
        let periods = Periods::of(period);
        let grid: StableHashSet<TermId> = grid.rows().map(|row| row[0]).collect();
        let mut cells = RowSet::empty(cell.arity());
        for row in cell.rows().filter(|row| grid.contains(&row[0])) {
            cells.insert(row.into());
        }
        let cells = Family::of(&cells, 1);
        let mut by_class: StableHashMap<Class, Vec<TermId>> = StableHashMap::default();
        for &p in &grid {
            by_class.entry(periods.class(p)).or_default().push(p);
        }

        let (mut symmetry, mut action) = (RowSet::empty(2), RowSet::empty(2));
        for members in by_class.values().filter(|_| group.wanted[1]) {
            for &p in members {
                for &q in members.iter().filter(|&&q| q != p) {
                    action.insert([p, q].into());
                }
            }
        }
        let shifts = cosets(lib, &grid, &periods)?;
        for d in transform.rows() {
            let d = d[0];
            let involution = lib.inverse(d)? == d;
            for &delta in &shifts {
                context.budget.charge_work(1)?;
                if involution && !periods.admits_square(lib.compose(delta, lib.apply(d, delta)?)?) {
                    continue;
                }
                let mut reach: Vec<(TermId, TermId, &[TermId])> = Vec::new();
                for &p in &grid {
                    let image = lib.apply(d, p)?;
                    let landed = by_class.get(&periods.class(lib.compose(image, delta)?));
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
                        if group.wanted[1] {
                            action.insert([p, q].into());
                        }
                        if group.wanted[0] {
                            symmetry.insert([d, lib.relative(image, q)?].into());
                        }
                    }
                }
            }
        }
        outputs(vec![symmetry, action], context.budget)
    }
}

/// The period class of a Box: on each axis, its margin from the top or the
/// left edge, modulo the period where the axis has one, and the sum of its
/// margins on that axis. Two Boxes are in one class where a period
/// translation takes one onto the other.
type Class = (i32, i32, i32, i32);

/// The period of each axis, where it has one.
#[derive(Clone, Copy, Debug)]
struct Periods {
    vertical: Option<i32>,
    horizontal: Option<i32>,
}

impl Periods {
    /// The periods of the `period` rows `(A, K)`, at most one positive
    /// period on each axis, as [`crate::domain`] checks.
    fn of(period: &RowSet) -> Periods {
        let mut periods = Periods { vertical: None, horizontal: None };
        for row in period.rows() {
            let axis = if is_vertical(row[0]) { &mut periods.vertical } else { &mut periods.horizontal };
            *axis = Some(Term::decode_number(row[1]));
        }
        periods
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

    /// Whether the translation `s` lies in the period translations, or lies off both
    /// axes.
    fn admits_square(&self, s: TermId) -> bool {
        let m = Term::decode_box(s);
        let is_period_translation = |shift: i32, period: Option<i32>| period.map_or(shift == 0, |k| shift % k == 0);
        (m.top != 0 && m.left != 0) || (is_period_translation(m.top, self.vertical) && is_period_translation(m.left, self.horizontal))
    }
}

/// Whether the Axis `axis` is the vertical one.
fn is_vertical(axis: TermId) -> bool {
    Geometry::get().axis_edges(axis).contains(Edge::Top)
}

/// One shift of each coset of the period translations of `periods` that the frame of `grid`
/// admits: on each axis, zero, or, on an axis with a period, a
/// magnitude that the frame admits and that is less than the period,
/// toward the bottom or right edge.
fn cosets(lib: Lib<'_>, grid: &StableHashSet<TermId>, periods: &Periods) -> Result<Vec<TermId>, ReachedBound> {
    let geometry = Geometry::get();
    let mut along: StableHashMap<TermId, StableHashSet<i32>> =
        geometry.domain(&ValueType::Axis).iter().map(|&axis| (axis, StableHashSet::from_iter([0]))).collect();
    for &p in grid {
        for (axis, k) in lib.sub_extents(p)? {
            if periods.of_axis(axis).is_some_and(|period| k < period) {
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
                next.push(lib.compose(shift, lib.translation(axis, k)?)?);
            }
        }
        shifts = next;
    }
    Ok(shifts)
}
