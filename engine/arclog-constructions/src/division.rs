//! Division, Tiling, Frame and ExtentDivisions: arithmetic over extents.

#![allow(unused_variables, dead_code)]

use arclog::eval::ReachedBound;
use arclog::eval::instance::{Construction, ConstructionContext, GroupInputs, GroupOutputs};

/// Equal parts per axis, by count or by side, with a gap.
#[derive(Clone, Copy, Debug, Default)]
pub struct Division;

impl Construction for Division {
    fn name(&self) -> &'static str {
        "Division"
    }

    fn evaluate(
        &self,
        group: &GroupInputs<'_>,
        context: &mut ConstructionContext<'_, '_>,
    ) -> Result<GroupOutputs, ReachedBound> {
        todo!()
    }
}

/// The cells of a frame tiled by an inner frame at the outer positions,
/// with a gap per axis.
#[derive(Clone, Copy, Debug, Default)]
pub struct Tiling;

impl Construction for Tiling {
    fn name(&self) -> &'static str {
        "Tiling"
    }

    fn evaluate(
        &self,
        group: &GroupInputs<'_>,
        context: &mut ConstructionContext<'_, '_>,
    ) -> Result<GroupOutputs, ReachedBound> {
        todo!()
    }
}

/// The cells of a frame from its extent on each axis.
#[derive(Clone, Copy, Debug, Default)]
pub struct Frame;

impl Construction for Frame {
    fn name(&self) -> &'static str {
        "Frame"
    }

    fn evaluate(
        &self,
        group: &GroupInputs<'_>,
        context: &mut ConstructionContext<'_, '_>,
    ) -> Result<GroupOutputs, ReachedBound> {
        todo!()
    }
}

/// The divisions that a frame's extent admits on each axis.
#[derive(Clone, Copy, Debug, Default)]
pub struct ExtentDivisions;

impl Construction for ExtentDivisions {
    fn name(&self) -> &'static str {
        "ExtentDivisions"
    }

    fn evaluate(
        &self,
        group: &GroupInputs<'_>,
        context: &mut ConstructionContext<'_, '_>,
    ) -> Result<GroupOutputs, ReachedBound> {
        todo!()
    }
}
