//! The lib's constructions. They stand in a crate of their own, apart from
//! the core crate, so a change to a construction rebuilds this crate alone.
//!
//! Each file holds one group of constructions, by the method they share,
//! and one change of step 2 writes its bodies. A change that adds a
//! construction of no group here adds its own file and its `mod` line.

pub mod agreement;
pub mod connectivity;
pub mod distance;
pub mod division;
pub mod domain;
pub mod order;
pub mod ray;
pub mod wallpaper;

use arclog::eval::instance::{Construction, Constructions, ConstructionsFault};
use arclog::registry::Registry;

/// Declares the table of the constructions listed, [`constructions`], and
/// gives each its registry name, the name of its type, as `NAME`.
macro_rules! constructions {
    ($($module:ident::$construction:ident,)*) => {
        $(impl $module::$construction {
            /// The construction's name in the registry.
            pub const NAME: &'static str = stringify!($construction);
        })*

        /// The table of every construction of this crate, by registry name.
        pub fn constructions(registry: &Registry) -> Result<Constructions, ConstructionsFault> {
            let all: Vec<Box<dyn Construction>> = vec![$(Box::new($module::$construction),)*];
            Constructions::new(all, registry)
        }
    };
}

constructions! {
    connectivity::Connectivity,
    connectivity::Quotient,
    connectivity::Propagation,
    connectivity::Enclosure,
    connectivity::Flood,
    order::Order,
    order::BoundingBox,
    order::Cardinality,
    order::Excess,
    order::Singleton,
    order::Inclusion,
    ray::Ray,
    ray::Walk,
    ray::Boundary,
    ray::Outlines,
    agreement::Agreement,
    agreement::Periods,
    agreement::Occurrences,
    wallpaper::Wallpaper,
    distance::Distance,
    distance::CellDistance,
    division::Division,
    division::Tiling,
    division::Frame,
    division::ExtentDivisions,
}
