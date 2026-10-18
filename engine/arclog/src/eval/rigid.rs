//! A `RIGID_DET` assembly at its stored records: its outputs
//! `&marker.<part>` and `&marker.pose`, as `docs/arclog/rigid.md#semantics`
//! gives.

#![allow(unused_variables, dead_code)]

use super::join::Budget;
use super::{Evaluation, FormBodies, Outcome, RelationValue};
use crate::program::OutputStep;
use crate::program::path::NodePath;
use crate::terms::Example;

/// The value of `output`, an output of the `RIGID_DET` form at `form`:
/// [`OutputStep::Part`] for `&marker.<part>`, and [`OutputStep::Pose`] for
/// `&marker.pose`, with the columns `docs/arclog/rigid.md#semantics` gives,
/// on `example`, or task-wide where it is `None`, with the form's bodies
/// evaluated through `bodies`.
pub fn evaluate_assembly(
    evaluation: &Evaluation<'_>,
    bodies: &FormBodies<'_>,
    form: &NodePath,
    output: &OutputStep,
    example: Option<Example>,
    budget: &mut Budget<'_>,
) -> Outcome<RelationValue> {
    todo!()
}
