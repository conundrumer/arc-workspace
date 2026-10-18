//! Agreement, Periods, Occurrences and Wallpaper: comparisons of valued
//! families under correspondences.

#![allow(unused_variables, dead_code)]

use arclog::eval::ReachedBound;
use arclog::eval::instance::{Construction, ConstructionContext, GroupInputs, GroupOutputs};

/// The mismatches and conflicts of two valued families under each
/// correspondence of their indices.
#[derive(Clone, Copy, Debug, Default)]
pub struct Agreement;

impl Construction for Agreement {
    fn name(&self) -> &'static str {
        "Agreement"
    }

    fn evaluate(
        &self,
        group: &GroupInputs<'_>,
        context: &mut ConstructionContext<'_, '_>,
    ) -> Result<GroupOutputs, ReachedBound> {
        todo!()
    }
}

/// The translations that fix the group's valued set, the least per axis,
/// and those read through sparse damage.
#[derive(Clone, Copy, Debug, Default)]
pub struct Periods;

impl Construction for Periods {
    fn name(&self) -> &'static str {
        "Periods"
    }

    fn evaluate(
        &self,
        group: &GroupInputs<'_>,
        context: &mut ConstructionContext<'_, '_>,
    ) -> Result<GroupOutputs, ReachedBound> {
        todo!()
    }
}

/// The placements of each shape under each admitted D4 element, as
/// candidates and as occurrences.
#[derive(Clone, Copy, Debug, Default)]
pub struct Occurrences;

impl Construction for Occurrences {
    fn name(&self) -> &'static str {
        "Occurrences"
    }

    fn evaluate(
        &self,
        group: &GroupInputs<'_>,
        context: &mut ConstructionContext<'_, '_>,
    ) -> Result<GroupOutputs, ReachedBound> {
        todo!()
    }
}

/// The isometries that fix a periodic valued set, each with every shift
/// of its coset under the lattice.
#[derive(Clone, Copy, Debug, Default)]
pub struct Wallpaper;

impl Construction for Wallpaper {
    fn name(&self) -> &'static str {
        "Wallpaper"
    }

    fn evaluate(
        &self,
        group: &GroupInputs<'_>,
        context: &mut ConstructionContext<'_, '_>,
    ) -> Result<GroupOutputs, ReachedBound> {
        todo!()
    }
}
