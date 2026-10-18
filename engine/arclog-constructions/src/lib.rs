//! The lib's constructions. They stand in a crate of their own, apart from
//! the core crate, so a change to a construction rebuilds this crate alone.
//!
//! Each file holds one group of constructions, by the method they share,
//! and the change of step 2 that writes its bodies: [`connectivity`]
//! 9-1044, [`order`] 9-1045, [`distance`] 9-1046, [`ray`] 9-1047,
//! [`agreement`] 9-1048, [`division`] 9-1049. A change that adds a
//! construction of no group here adds its own file and its `mod` line.

pub mod agreement;
pub mod connectivity;
pub mod distance;
pub mod division;
pub mod order;
pub mod ray;

use arclog::eval::instance::{Construction, Constructions, ConstructionsFault};
use arclog::registry::Registry;

/// The table of every construction of this crate, by registry name, which
/// the caller of an evaluation gives to [`arclog::eval::Evaluation`].
pub fn constructions(registry: &Registry) -> Result<Constructions, ConstructionsFault> {
    let all: Vec<Box<dyn Construction>> = vec![
        Box::new(connectivity::Connectivity),
        Box::new(connectivity::Quotient),
        Box::new(connectivity::Propagation),
        Box::new(connectivity::Enclosure),
        Box::new(connectivity::Flood),
        Box::new(order::Order),
        Box::new(order::BoundingBox),
        Box::new(order::Cardinality),
        Box::new(order::Excess),
        Box::new(order::Singleton),
        Box::new(order::Inclusion),
        Box::new(ray::Ray),
        Box::new(ray::Walk),
        Box::new(ray::Boundary),
        Box::new(ray::Outlines),
        Box::new(agreement::Agreement),
        Box::new(agreement::Periods),
        Box::new(agreement::Occurrences),
        Box::new(agreement::Wallpaper),
        Box::new(distance::Distance),
        Box::new(distance::CellDistance),
        Box::new(division::Division),
        Box::new(division::Tiling),
        Box::new(division::Frame),
        Box::new(division::ExtentDivisions),
    ];
    Constructions::new(all, registry)
}
