//! The attempts of a synthesized program on each test input, as
//! `docs/engine/synthesis.md#open-parameters` gives.

use crate::eval::{Evaluation, Outcome};
use crate::eval::output::GridColumns;
use crate::task::Grid;
use crate::types::GraphRelation;
use super::run::{output_sets_observed, Observed};
use super::solves::{Comparison, OutputSet};

/// At most two distinct grids on a test input. An undefined output or an
/// output of three or more grids gives no attempt.
#[derive(Clone, Debug, PartialEq, Eq)]
pub enum Attempts {
    None,
    One(Grid),
    Two(Grid, Grid),
}

pub(crate) fn attempts(evaluations: &[Evaluation<'_>], relation: &GraphRelation) -> Outcome<Box<[Attempts]>> {
    let task = evaluations[0].task;
    let mut observed = vec![Observed::default(); evaluations.len()];
    task.examples().skip(task.train.len()).map(|example| {
        let set = output_sets_observed(evaluations, &mut observed, relation, example, &[GridColumns::OUT], &[Comparison::Full])?.pop().expect("one output set");
        Ok(match set {
            OutputSet::Grids(grids) => match &*grids {
                [one] => Attempts::One(one.clone()),
                [one, two] => Attempts::Two(one.clone(), two.clone()),
                _ => Attempts::None,
            },
            _ => Attempts::None,
        })
    }).collect()
}
