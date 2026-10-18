//! Connectivity, Quotient, Propagation, Enclosure and Flood: union-find,
//! flood fill, and forward chaining to a fixpoint.

#![allow(unused_variables, dead_code)]

use arclog::eval::ReachedBound;
use arclog::eval::instance::{Construction, ConstructionContext, GroupInputs, GroupOutputs};

/// The connected components of the group's nodes under its steps, the
/// cardinals by default.
#[derive(Clone, Copy, Debug, Default)]
pub struct Connectivity;

impl Construction for Connectivity {
    fn name(&self) -> &'static str {
        "Connectivity"
    }

    fn evaluate(
        &self,
        group: &GroupInputs<'_>,
        context: &mut ConstructionContext<'_, '_>,
    ) -> Result<GroupOutputs, ReachedBound> {
        todo!()
    }
}

/// One class id per equivalence class of the closure of `equivalent` and
/// `edge`, each id the Ident of its class, so no member is a
/// representative.
#[derive(Clone, Copy, Debug, Default)]
pub struct Quotient;

impl Construction for Quotient {
    fn name(&self) -> &'static str {
        "Quotient"
    }

    fn evaluate(
        &self,
        group: &GroupInputs<'_>,
        context: &mut ConstructionContext<'_, '_>,
    ) -> Result<GroupOutputs, ReachedBound> {
        todo!()
    }
}

/// Forward chaining from the sources over `edge` and `join` to a
/// fixpoint.
#[derive(Clone, Copy, Debug, Default)]
pub struct Propagation;

impl Construction for Propagation {
    fn name(&self) -> &'static str {
        "Propagation"
    }

    fn evaluate(
        &self,
        group: &GroupInputs<'_>,
        context: &mut ConstructionContext<'_, '_>,
    ) -> Result<GroupOutputs, ReachedBound> {
        todo!()
    }
}

/// The parts of the group's cells that the frame's edge does not reach,
/// each under its id.
#[derive(Clone, Copy, Debug, Default)]
pub struct Enclosure;

impl Construction for Enclosure {
    fn name(&self) -> &'static str {
        "Enclosure"
    }

    fn evaluate(
        &self,
        group: &GroupInputs<'_>,
        context: &mut ConstructionContext<'_, '_>,
    ) -> Result<GroupOutputs, ReachedBound> {
        todo!()
    }
}

/// The nodes a walk from a source reaches by steps inside the set, the
/// cardinals by default.
#[derive(Clone, Copy, Debug, Default)]
pub struct Flood;

impl Construction for Flood {
    fn name(&self) -> &'static str {
        "Flood"
    }

    fn evaluate(
        &self,
        group: &GroupInputs<'_>,
        context: &mut ConstructionContext<'_, '_>,
    ) -> Result<GroupOutputs, ReachedBound> {
        todo!()
    }
}
