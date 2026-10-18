//! A `RIGID_DET` assembly at its stored records: its outputs
//! `&marker.<part>` and `&marker.pose`, as `docs/arclog/rigid.md#semantics`
//! gives.

#![allow(unused_variables, dead_code)]

use super::join::Budget;
use super::{Evaluation, Outcome, RelationValue};
use crate::program::OutputStep;
use crate::program::path::NodePath;

/// The value of `output`, an output of the `RIGID_DET` form at `form`:
/// [`OutputStep::Part`] for `&marker.<part>`, the key's columns, `:Pose` and
/// then the part's columns; [`OutputStep::Pose`] for `&marker.pose`, the
/// key's columns, the instance's columns and then `:Pose`.
pub fn evaluate_assembly(
    evaluation: &Evaluation<'_>,
    form: &NodePath,
    output: &OutputStep,
    budget: &mut Budget<'_>,
) -> Outcome<RelationValue> {
    todo!()
}
