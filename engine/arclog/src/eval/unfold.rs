//! `Unfold`: its states, its rounds, the forks of a tied `score`, and the
//! distinct outputs of its walks.
//!
//! A state is the cursor `t` with its `taken`, `untaken` and `excluded`
//! sets. Each round evaluates the instance's `step`, `skip` and `take`
//! bodies against the current states, a `NOT` in them reading the current
//! state. A state already reached is not expanded again, and the states are
//! finite, so the rounds end. Where a `score` ties, the walk forks: each
//! walk is one tiebreak resolution, as
//! `docs/handbook/solver-file.md#alt-outputs` gives, and walks that reach
//! states of equal content share that state.

#![allow(unused_variables, dead_code)]

use super::join::Budget;
use super::{Evaluation, FormBodies, Outcome, RelationValue, Stop};
use crate::program::path::NodePath;
use crate::relations::{Row, RowSet};
use crate::terms::{Example, TermId};
use crate::types::GraphRelation;

/// A state of an `Unfold` walk, on one key: its cursor and its three sets
/// of items.
#[derive(Clone, PartialEq, Eq, Hash, Debug)]
pub struct UnfoldState {
    pub cursor: TermId,
    pub taken: Box<[TermId]>,
    pub untaken: Box<[TermId]>,
    pub excluded: Box<[TermId]>,
}

/// The index of a state in a [`StateGraph`].
#[derive(Clone, Copy, PartialEq, Eq, Hash, Debug)]
pub struct StateIndex(pub u32);

/// The states an `Unfold` instance reaches on one key, and the edges of its
/// rounds between them. The first state is the start.
#[derive(Clone, Debug, Default)]
pub struct StateGraph {
    pub states: Vec<UnfoldState>,
    /// For each state, the states one round reaches from it, more than one
    /// where a `score` ties.
    pub next: Vec<Box<[StateIndex]>>,
}

/// The state graph of the `Unfold` instance whose `INIT` form stands at
/// `form`, with each of its keys, the key's columns of the instance's rows.
pub fn unfold(
    evaluation: &Evaluation<'_>,
    form: &NodePath,
    budget: &mut Budget<'_>,
) -> Outcome<Result<Vec<(Row, StateGraph)>, Stop>> {
    todo!()
}

/// The distinct outputs of the walks of `graph`, each the facts along one
/// walk's path, collected over the graph with each state's facts once, and
/// at most `limit` of them: the collection stops at the `limit`-th
/// distinct output.
pub fn distinct_outputs(graph: &StateGraph, limit: usize) -> Vec<RowSet> {
    todo!()
}

/// The values of `output`, an output of the `Unfold` instance at `form`:
/// one per distinct output of its walks, at most `limit`, so one value
/// where no `score` ties, on `example`, or task-wide where it is `None`,
/// with the instance's bodies evaluated through `bodies`.
pub fn evaluate_unfold(
    evaluation: &Evaluation<'_>,
    bodies: &FormBodies<'_>,
    form: &NodePath,
    output: &GraphRelation,
    example: Option<Example>,
    limit: usize,
    budget: &mut Budget<'_>,
) -> Outcome<Vec<RelationValue>> {
    todo!()
}
