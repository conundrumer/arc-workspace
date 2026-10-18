//! Distance and CellDistance: breadth-first and Dijkstra search, keeping
//! every predecessor at the least cost.

#![allow(unused_variables, dead_code)]

use arclog::eval::ReachedBound;
use arclog::eval::instance::{Construction, ConstructionContext, GroupInputs, GroupOutputs};

/// The least cost from a source to each node, and every predecessor on a
/// least-cost path.
#[derive(Clone, Copy, Debug, Default)]
pub struct Distance;

impl Construction for Distance {
    fn name(&self) -> &'static str {
        "Distance"
    }

    fn evaluate(
        &self,
        group: &GroupInputs<'_>,
        context: &mut ConstructionContext<'_, '_>,
    ) -> Result<GroupOutputs, ReachedBound> {
        todo!()
    }
}

/// Distance over the steps inside the group's set, the cardinals by
/// default.
#[derive(Clone, Copy, Debug, Default)]
pub struct CellDistance;

impl Construction for CellDistance {
    fn name(&self) -> &'static str {
        "CellDistance"
    }

    fn evaluate(
        &self,
        group: &GroupInputs<'_>,
        context: &mut ConstructionContext<'_, '_>,
    ) -> Result<GroupOutputs, ReachedBound> {
        todo!()
    }
}
