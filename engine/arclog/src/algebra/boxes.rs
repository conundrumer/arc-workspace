//! The box algebra's relations over Box, Position, Offset and number: each
//! computes in 32-bit integers, and packs only the Boxes it binds, as
//! [`crate::terms::Margins`] gives.

#![allow(unused_variables, dead_code)]

use super::Algebra;
use crate::registry::Registry;
use crate::terms::{ReachedMarginBound, TermId};

/// A relation of the box algebra, by its registry name.
#[derive(Clone, Copy, PartialEq, Eq, Hash, Debug)]
pub enum BoxRelation {
    Compose,
    Relative,
    EdgeInset,
    Margin,
    Apply,
    CornerDist,
    FrameExtent,
    StepOffset,
    SubExtent,
    Gap,
    Divide,
}

impl BoxRelation {
    /// Each relation of the box algebra.
    pub const ALL: [BoxRelation; 11] = [
        BoxRelation::Compose,
        BoxRelation::Relative,
        BoxRelation::EdgeInset,
        BoxRelation::Margin,
        BoxRelation::Apply,
        BoxRelation::CornerDist,
        BoxRelation::FrameExtent,
        BoxRelation::StepOffset,
        BoxRelation::SubExtent,
        BoxRelation::Gap,
        BoxRelation::Divide,
    ];
}

impl Algebra for BoxRelation {
    fn name(&self) -> &'static str {
        match self {
            BoxRelation::Compose => "compose",
            BoxRelation::Relative => "relative",
            BoxRelation::EdgeInset => "edge_inset",
            BoxRelation::Margin => "margin",
            BoxRelation::Apply => "apply",
            BoxRelation::CornerDist => "corner_dist",
            BoxRelation::FrameExtent => "frame_extent",
            BoxRelation::StepOffset => "step_offset",
            BoxRelation::SubExtent => "sub_extent",
            BoxRelation::Gap => "gap",
            BoxRelation::Divide => "divide",
        }
    }

    fn evaluate(
        &self,
        bound: &[Option<TermId>],
        registry: &Registry,
        emit: &mut dyn FnMut(&[TermId]),
    ) -> Result<(), ReachedMarginBound> {
        todo!()
    }
}
