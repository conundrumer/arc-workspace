//! The candidates of a pair under the world of a run, as
//! `docs/engine/cases.md#candidates` gives.

use crate::task::{AltKind, Grid, JudgedPair};

/// The world of a run: closed-world candidates on the task data of this
/// repo, open-world candidates on Kaggle task data.
#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub enum World {
    Closed,
    Open,
}

/// The section of a task a pair stands in.
#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub enum Section {
    Train,
    Test,
}

/// One candidate of a pair: its grids, one or two.
#[derive(Clone, Debug)]
pub struct Candidate<'a> {
    grids: Box<[&'a Grid]>,
}

impl<'a> Candidate<'a> {
    /// The grids of the candidate.
    pub fn grids(&self) -> &[&'a Grid] {
        &self.grids
    }

    /// Whether `grid` is one of the candidate's grids.
    pub fn holds(&self, grid: &Grid) -> bool {
        self.grids.iter().any(|&own| own == grid)
    }

    /// Whether each of `grids` is one of the candidate's grids.
    pub fn holds_all(&self, grids: &[Grid]) -> bool {
        grids.iter().all(|grid| self.holds(grid))
    }
}

/// The candidates of a pair under the world of a run.
#[derive(Clone, Debug)]
pub enum Candidates<'a> {
    /// The candidates the pair's alt gives: one, or two for a `rule` alt.
    Closed(Box<[Candidate<'a>]>),
    /// The pair's given output, one grid of a candidate the data does not
    /// show in full.
    Open { given: &'a Grid },
}

/// A pair's candidates, with the section that its comparison depends on.
#[derive(Clone, Debug)]
pub struct PairCandidates<'a> {
    pub section: Section,
    pub candidates: Candidates<'a>,
}

impl<'a> PairCandidates<'a> {
    /// The candidates of `pair`, in `section`, under `world`.
    pub fn of(pair: &'a JudgedPair, section: Section, world: World) -> PairCandidates<'a> {
        let candidates = match world {
            World::Open => Candidates::Open { given: &pair.output },
            World::Closed => {
                let given = Candidate { grids: Box::new([&pair.output]) };
                Candidates::Closed(match &pair.alt {
                    None => Box::new([given]),
                    Some(alt) => match alt.kind {
                        AltKind::Rule => Box::new([given, Candidate { grids: Box::new([&alt.grid]) }]),
                        AltKind::Tiebreak => Box::new([Candidate { grids: Box::new([&pair.output, &alt.grid]) }]),
                    },
                })
            }
        };
        PairCandidates { section, candidates }
    }
}
