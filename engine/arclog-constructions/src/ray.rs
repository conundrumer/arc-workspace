//! Ray, Walk, Boundary and Outlines: stepping, and tests of each cell's
//! neighbors.

#![allow(unused_variables, dead_code)]

use arclog::eval::ReachedBound;
use arclog::eval::instance::{Construction, ConstructionContext, GroupInputs, GroupOutputs};

/// The straight path from each source toward each direction, each step
/// onto a node, with its last cell.
#[derive(Clone, Copy, Debug, Default)]
pub struct Ray;

impl Construction for Ray {
    fn name(&self) -> &'static str {
        Self::NAME
    }

    fn evaluate(
        &self,
        group: &GroupInputs<'_>,
        context: &mut ConstructionContext<'_, '_>,
    ) -> Result<GroupOutputs, ReachedBound> {
        todo!()
    }
}

/// The member a given count of successors from a start.
#[derive(Clone, Copy, Debug, Default)]
pub struct Walk;

impl Construction for Walk {
    fn name(&self) -> &'static str {
        Self::NAME
    }

    fn evaluate(
        &self,
        group: &GroupInputs<'_>,
        context: &mut ConstructionContext<'_, '_>,
    ) -> Result<GroupOutputs, ReachedBound> {
        todo!()
    }
}

/// The cells of the group's set with nothing of the set one step toward a
/// direction.
#[derive(Clone, Copy, Debug, Default)]
pub struct Boundary;

impl Construction for Boundary {
    fn name(&self) -> &'static str {
        Self::NAME
    }

    fn evaluate(
        &self,
        group: &GroupInputs<'_>,
        context: &mut ConstructionContext<'_, '_>,
    ) -> Result<GroupOutputs, ReachedBound> {
        todo!()
    }
}

/// The rectangles drawn in the group's set: candidate boxes from corner
/// cells, each tested along its perimeter.
#[derive(Clone, Copy, Debug, Default)]
pub struct Outlines;

impl Construction for Outlines {
    fn name(&self) -> &'static str {
        Self::NAME
    }

    fn evaluate(
        &self,
        group: &GroupInputs<'_>,
        context: &mut ConstructionContext<'_, '_>,
    ) -> Result<GroupOutputs, ReachedBound> {
        todo!()
    }
}
