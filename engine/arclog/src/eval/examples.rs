//! Relations per example: a `RULE` relation is evaluated on each example,
//! from that example's `input`, and its lifted form unions the
//! per-example relations with the Example column first, as
//! `docs/arclog/arclog.md#program` gives. A `DET` relation is task-wide,
//! and reads `ex_input` and `ex_output` where it reads the train pairs.
//!
//! The checker decides whether a relation has an Example column, and
//! [`crate::types::ProgramTypes::columns`] gives it.

#![allow(unused_variables, dead_code)]

use super::RelationValue;
use crate::check::CheckedProgram;
use crate::terms::Example;
use crate::types::GraphRelation;

/// Where a relation is evaluated: on each example, or once for the task.
#[derive(Clone, Copy, PartialEq, Eq, Hash, Debug)]
pub enum ExampleScope {
    /// A `RULE` relation, and each relation that reads one: one entry per
    /// example.
    PerExample,
    /// A `DET` relation, a parameter, a chosen relation, or a relation that
    /// reads only task-wide relations: one entry for the task.
    TaskWide,
}

/// Where `relation` of `program` is evaluated.
pub fn scope_of(program: &CheckedProgram, relation: &GraphRelation) -> ExampleScope {
    todo!()
}

/// The lifted form of a relation per example: the union of its relation on
/// each example of `per_example`, each row with its Example first. Where
/// the relation is `undefined` or stopped on an example, the lifted form is
/// too, the first stop by the order of `per_example` where several stopped.
pub fn lift(per_example: &[(Example, RelationValue)]) -> RelationValue {
    todo!()
}
