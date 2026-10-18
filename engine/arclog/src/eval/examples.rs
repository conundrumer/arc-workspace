//! Relations per example: a `RULE` relation is evaluated on each example,
//! from that example's `input`, and its lifted form is the union of the
//! per-example relations (`docs/arclog/arclog.md#program`). A `DET` relation
//! is task-wide.
//!
//! The checker decides whether a relation has an Example column, and
//! [`crate::types::ProgramTypes::has_example_column`] gives it.

use std::sync::Arc;

use super::RelationValue;
use super::join::{each_row, one_part};
use crate::check::CheckedProgram;
use crate::relations::RowSet;
use crate::resolver::Side;
use crate::terms::{Constant, Example, Term};
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
    match program.program.side(relation.node) {
        Side::PerInput => ExampleScope::PerExample,
        Side::TaskWide => ExampleScope::TaskWide,
    }
}

/// The lifted form of a relation per example: the union of its relation on
/// each example of `per_example`, each row with its Example first. Where
/// the relation is `undefined` or stopped on an example, the lifted form is
/// too, the first stop by the order of `per_example` where several stopped.
pub fn lift(per_example: &[(Example, RelationValue)]) -> RelationValue {
    if let Some(stop) = per_example.iter().find_map(|(_, value)| match value {
        RelationValue::Stopped(stop) => Some(stop.clone()),
        _ => None,
    }) {
        return RelationValue::Stopped(stop);
    }
    let mut arity = None;
    let mut rows = Vec::new();
    for (example, value) in per_example {
        let RelationValue::Rows(relation) = value else { return RelationValue::Undefined };
        arity = Some(relation.arity() + 1);
        let example = Term::Constant(Constant::Example(*example)).encode().expect("an Example's term id");
        each_row(relation, &mut |row| rows.push(std::iter::once(example).chain(row.iter().copied()).collect()));
    }
    let mut set = RowSet::empty(arity.expect("a task with at least one example"));
    for row in rows {
        set.insert(row);
    }
    RelationValue::Rows(Arc::new(one_part(set)))
}
