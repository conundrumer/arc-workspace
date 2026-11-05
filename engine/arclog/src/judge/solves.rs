//! The output set of a case on a pair, the solves test of
//! `docs/engine/cases.md#solves`, and the enumeration of the set over the
//! case's models, with the stops of
//! `docs/engine/cases.md#enumeration-and-its-stops`.

use crate::eval::values::{GridValue, Stop};
use crate::task::Grid;

use super::candidates::{Candidates, PairCandidates, Section};

/// The output set of a case on a pair. It has no `PartialEq`, since every
/// comparison of the judge treats `outside` as different from every output,
/// itself included.
#[derive(Clone, Debug)]
pub enum OutputSet {
    /// The distinct grids of the case's models, at least one.
    Grids(Box<[Grid]>),
    Undefined,
    /// An enumeration that stopped early, as
    /// `docs/engine/cases.md#enumeration-and-its-stops` gives.
    Outside,
    /// A stop at a bound: the case has no output on the pair.
    Stopped(Stop),
}

/// Whether the output set `set` solves the pair whose candidates are `pair`.
pub fn solves(set: &OutputSet, pair: &PairCandidates) -> bool {
    let OutputSet::Grids(grids) = set else { return false };
    match (&pair.candidates, pair.section) {
        (Candidates::Closed(candidates), Section::Train) => candidates.iter().any(|candidate| {
            candidate.holds_all(grids) && candidate.grids().iter().all(|&grid| grids.contains(grid))
        }),
        (Candidates::Closed(candidates), Section::Test) => {
            grids.len() <= 2 && grids.iter().any(|grid| candidates.iter().any(|candidate| candidate.holds(grid)))
        }
        (Candidates::Open { given }, _) => grids.len() <= 2 && grids.contains(given),
    }
}

/// What an enumeration compares its grids with: a pair's candidates, which
/// stop it once its grids decide the pair's comparison, or nothing, for a
/// check that compares the whole set and takes no early stop.
#[derive(Clone, Copy, Debug)]
pub enum Comparison<'p, 'a> {
    Pair(&'p PairCandidates<'a>),
    Full,
}

/// Whether an enumeration goes on to the next model.
#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub enum Next {
    GoOn,
    Stop,
}

/// Where an enumeration ended before its last model.
#[derive(Clone, Debug)]
enum Ended {
    Outside,
    Stopped(Stop),
}

/// The enumeration of a case's output set on a pair, one model's grid at a
/// time. Whether it stops depends on the set of grids so far, and not on
/// their order.
#[derive(Clone, Debug)]
pub struct Enumeration<'p, 'a> {
    comparison: Comparison<'p, 'a>,
    grids: Vec<Grid>,
    undefined: bool,
    ended: Option<Ended>,
}

impl<'p, 'a> Enumeration<'p, 'a> {
    pub fn new(comparison: Comparison<'p, 'a>) -> Enumeration<'p, 'a> {
        Enumeration { comparison, grids: Vec::new(), undefined: false, ended: None }
    }

    /// Takes the grid of the next model, and tells whether to go on. A grid
    /// after a [`Next::Stop`] is a fault of the caller, so this panics on
    /// one.
    pub fn push(&mut self, grid: GridValue) -> Next {
        assert!(self.ended.is_none(), "no grid after an enumeration's stop");
        match grid {
            GridValue::Stopped(stop) => self.ended = Some(Ended::Stopped(stop)),
            GridValue::Undefined => match self.comparison {
                Comparison::Pair(_) => self.ended = Some(Ended::Outside),
                Comparison::Full => self.undefined = true,
            },
            GridValue::Grid(grid) => {
                if !self.grids.contains(&grid) {
                    self.grids.push(grid);
                }
                if let Comparison::Pair(pair) = self.comparison
                    && decided(&self.grids, pair)
                {
                    self.ended = Some(Ended::Outside);
                }
            }
        }
        if self.ended.is_some() { Next::Stop } else { Next::GoOn }
    }

    /// The output set the enumeration ends with. An enumeration that took no
    /// grid, since no model read one, is an undefined grid's.
    pub fn finish(self) -> OutputSet {
        match self.ended {
            Some(Ended::Stopped(stop)) => OutputSet::Stopped(stop),
            Some(Ended::Outside) => OutputSet::Outside,
            None if self.undefined => OutputSet::Undefined,
            None if self.grids.is_empty() => match self.comparison {
                Comparison::Pair(_) => OutputSet::Outside,
                Comparison::Full => OutputSet::Undefined,
            },
            None => OutputSet::Grids(self.grids.into_boxed_slice()),
        }
    }
}

impl Enumeration<'_, '_> {
    /// The output set of an enumeration that the model cap `stop` ended
    /// before its last model, and whether the set ended at the cap.
    ///
    /// An enumeration that ended before the cap gives its own set. One
    /// still going gives the distinct grids of the models up to the cap, or
    /// `undefined`, so which grids it holds depends on the order of the
    /// models. One going with no grid to give, as where the cap is zero,
    /// gives the stop.
    pub fn finish_at_cap(self, stop: Stop) -> (OutputSet, bool) {
        if self.ended.is_some() {
            return (self.finish(), false);
        }
        if self.grids.is_empty() && !self.undefined {
            return (OutputSet::Stopped(stop), false);
        }
        (self.finish(), true)
    }
}

/// Whether the distinct grids `grids` decide the comparison with `pair`, so
/// its enumeration stops.
fn decided(grids: &[Grid], pair: &PairCandidates) -> bool {
    match (pair.section, &pair.candidates) {
        (Section::Train, Candidates::Closed(candidates)) => {
            !candidates.iter().any(|candidate| candidate.holds_all(grids))
        }
        (Section::Train, Candidates::Open { given }) => grids.len() >= 3 || (grids.len() >= 2 && !grids.contains(given)),
        (Section::Test, _) => grids.len() >= 3,
    }
}
