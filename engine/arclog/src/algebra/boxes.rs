//! The box algebra's relations over Box, Position, Offset and number: each
//! computes in 32-bit integers, and packs only the Boxes it binds, as
//! [`crate::terms::Margins`] gives.

#![allow(unused_variables, dead_code)]

use super::Algebra;
use crate::registry::Registry;
use crate::terms::{ReachedMarginBound, TermId};

/// Declares [`BoxRelation`] from its variants, each with its registry name,
/// with [`BoxRelation::ALL`] and [`BoxRelation::registry_name`].
macro_rules! box_relations {
    ($($variant:ident => $name:literal,)*) => {
        /// A relation of the box algebra, by its registry name.
        #[derive(Clone, Copy, PartialEq, Eq, Hash, Debug)]
        pub enum BoxRelation {
            $($variant,)*
        }

        impl BoxRelation {
            /// Each relation of the box algebra.
            pub const ALL: [BoxRelation; [$($name),*].len()] = [$(BoxRelation::$variant),*];

            /// The relation's name in the registry.
            const fn registry_name(self) -> &'static str {
                match self {
                    $(BoxRelation::$variant => $name,)*
                }
            }
        }
    };
}

box_relations! {
    Compose => "compose",
    Relative => "relative",
    EdgeInset => "edge_inset",
    Margin => "margin",
    Apply => "apply",
    CornerDist => "corner_dist",
    FrameExtent => "frame_extent",
    StepOffset => "step_offset",
    SubExtent => "sub_extent",
    Gap => "gap",
    Divide => "divide",
}

impl Algebra for BoxRelation {
    fn name(&self) -> &'static str {
        self.registry_name()
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
