//! Order, BoundingBox, Cardinality, Excess, Singleton and Inclusion:
//! counts, sorts and minima.

#![allow(unused_variables, dead_code)]

use arclog::eval::ReachedBound;
use arclog::eval::instance::{Construction, ConstructionContext, GroupInputs, GroupOutputs};

/// Rank, dual rank, the minimal and maximal members and the successors of
/// the group's members under `before` or `score`, tied members sharing a
/// rank and each tied member minimal or maximal.
#[derive(Clone, Copy, Debug, Default)]
pub struct Order;

impl Construction for Order {
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

/// The least box that holds the group's cells, a minimum over margins.
#[derive(Clone, Copy, Debug, Default)]
pub struct BoundingBox;

impl Construction for BoundingBox {
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

/// The count of the group's members, 0 for a key of the domain with none.
#[derive(Clone, Copy, Debug, Default)]
pub struct Cardinality;

impl Construction for Cardinality {
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

/// The amount by which the group's plus set outnumbers its minus set.
#[derive(Clone, Copy, Debug, Default)]
pub struct Excess;

impl Construction for Excess {
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

/// The one value of the group's members, and the keys whose members
/// disagree.
#[derive(Clone, Copy, Debug, Default)]
pub struct Singleton;

impl Construction for Singleton {
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

/// Each observed set against the patterns, by counts over the pairs that
/// share a member.
#[derive(Clone, Copy, Debug, Default)]
pub struct Inclusion;

impl Construction for Inclusion {
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
