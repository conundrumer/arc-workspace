//! Periods: the translations that fix a valued set, each line pair tested by
//! Agreement's comparison of [`crate::agreement`], as
//! `docs/lib-spec.md#detectors` gives.
//!
//! It reads the box algebra through [`arclog::algebra::algebra`], and reads
//! no order of term ids, cells or rows.

use arclog::eval::instance::{Construction, ConstructionContext, GroupInputs, GroupOutputs};
use arclog::eval::ReachedBound;
use arclog::hash::{StableHashMap, StableHashSet};
use arclog::relations::{Row, RowSet};
use arclog::terms::{Term, TermId};

use crate::agreement::{compare, outputs, Family, Lib};

/// The translations that fix the group's valued set, the least per axis,
/// and those read through sparse damage.
///
/// A translation is one per axis and magnitude, toward the bottom or the
/// right edge: the other direction pairs the same cells the other way, and
/// the cells of a pair compare alike both ways. Each line pair of a translation,
/// the line of a cell and the line of its image, is one correspondence, and
/// a line pair is broken where a cell of it conflicts with its image.
///
/// - in `cell(key, P, v)`.
/// - out `period(key, A, K)`: a move of K along A takes every cell onto a cell of the same value, wherever both cells exist. K runs from 1 to one less than the extent. A K with no pair of cells to compare is a period.
/// - out `fundamental_period(key, A, K)`: the least period along A that compares at least one pair of cells.
/// - out `approximate_period(key, A, K)`: a period read through damage: the line pairs the move breaks do not outnumber those it keeps. Every period is one.
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
                if group.wanted[0] {
                    period.insert(row.clone());
                }
                if witnessed && group.wanted[1] {
                    let at = least.entry(axis).or_insert(k);
                    *at = (*at).min(k);
                }
            }
            if broken <= lines.len() - broken && group.wanted[2] {
                approximate.insert(row);
            }
        }
        for (axis, k) in least {
            fundamental.insert([axis, Term::encode_number(k)].into());
        }
        outputs(vec![period, fundamental, approximate], context.budget)
    }
}
