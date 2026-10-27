//! The judged run of a case on a task: the case's output set on each pair,
//! read from its `OUT` form's relation by that form's columns, and whether
//! it solves each pair and the task, as `docs/engine/cases.md#solves` gives.
//! The tests of a decode also run here: of the `OUT` form, and, under the
//! rule tests of `docs/engine/synthesis.md#decode-settings`, of the relation
//! of a `RULE` clause, whose grid columns are searched for as that setting
//! gives.

use std::ops::ControlFlow;

use crate::eval::output::{read_grid, GridColumns};
use crate::relations::ColumnIndex;
use crate::types::ValueType;
use crate::eval::{Evaluation, GridValue, ModelsEnd, Outcome, RelationValue, RunFault, Stop};
use crate::task::JudgedTask;
use crate::terms::Example;
use crate::types::GraphRelation;

use super::candidates::{PairCandidates, Section, World};
use super::solves::{solves, Comparison, Enumeration, Next, OutputSet};

/// How far the enumeration of a case's models on a pair goes.
#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub enum Depth {
    /// To the model at which the pair's comparison is decided.
    Decided,
    /// To the last model, for a caller that needs the full set.
    Full,
}

/// What the test of a relation against the train pairs finds: the grid
/// columns under which the relation solves every train pair, for an `OUT`
/// form's relation its own columns.
#[derive(Clone, Debug)]
pub enum Found {
    Columns(GridColumns),
    /// No pair of columns solves every train pair.
    None,
    /// The relation stopped at a bound on a train pair.
    Stopped(Stop),
}

/// The judged run of a case: its output set on each pair, train pairs then
/// test pairs, each with whether the case solves it.
#[derive(Clone, Debug)]
pub struct JudgedRun {
    pub pairs: Box<[JudgedOutput]>,
}

/// The output set of a case on one pair, and whether it solves the pair.
#[derive(Clone, Debug)]
pub struct JudgedOutput {
    pub set: OutputSet,
    pub solved: bool,
}

impl JudgedRun {
    /// Whether the case solves the task: whether it solves each pair.
    pub fn solves_task(&self) -> bool {
        self.pairs.iter().all(|pair| pair.solved)
    }
}

/// The candidates of each pair of `judged`, train pairs then test pairs,
/// under `world`.
fn pair_candidates(judged: &JudgedTask, world: World) -> Vec<PairCandidates<'_>> {
    let train = judged.train.iter().map(|pair| PairCandidates::of(pair, Section::Train, world));
    train.chain(judged.test.iter().map(|pair| PairCandidates::of(pair, Section::Test, world))).collect()
}

/// The judged run of `relation`, the relation of the `OUT` form of the case
/// that `evaluation` evaluates, against the pairs of `judged`, under
/// `world`, each pair's enumeration going as far as `depth` gives.
pub fn judged_run(evaluation: &Evaluation<'_>, relation: &GraphRelation, judged: &JudgedTask, world: World, depth: Depth) -> Outcome<JudgedRun> {
    let candidates = pair_candidates(judged, world);
    let pairs = candidates
        .iter()
        .zip(evaluation.task.examples())
        .map(|(pair, example)| {
            let comparison = match depth {
                Depth::Decided => Comparison::Pair(pair),
                Depth::Full => Comparison::Full,
            };
            let set = output_sets(evaluation, relation, example, &[GridColumns::OUT], &[comparison])?.pop().expect("one set");
            let solved = solves(&set, pair);
            Ok(JudgedOutput { set, solved })
        })
        .collect::<Outcome<_>>()?;
    Ok(JudgedRun { pairs })
}

/// What a test of a relation against the train pairs searches for: nothing,
/// for the `OUT` form's relation, whose grid columns are its own, or the pair
/// of one Position column and one Color column of the relation of a `RULE`
/// clause under which it solves every train pair.
#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub(crate) enum Tested {
    Out,
    Rule,
}

impl Tested {
    /// The grid columns that the test of `relation` tries: the `OUT` form's
    /// own, or each pair of a Position column and a Color column of the
    /// relation of a `RULE` clause.
    fn candidates(self, evaluation: &Evaluation<'_>, relation: &GraphRelation) -> Outcome<Vec<GridColumns>> {
        match self {
            Tested::Out => Ok(vec![GridColumns::OUT]),
            Tested::Rule => {
                let types = evaluation.program.types.columns(relation).ok_or_else(|| RunFault {
                    message: "the columns of the tested relation have no types".into(),
                    form: evaluation.program.program.form_of(relation.node).clone(),
                })?;
                Ok(candidate_columns(types))
            }
        }
    }

    /// The test of `relation` at the evaluation, against the train pairs
    /// `train`, with the output sets it evaluated.
    pub(crate) fn recorded(self, evaluation: &Evaluation<'_>, relation: &GraphRelation, train: &[PairCandidates<'_>]) -> (Outcome<Found>, Observed) {
        let mut observed = Observed::default();
        let found = self.found(evaluation, relation, train, &mut |example, columns, comparisons| {
            recorded_sets(evaluation, relation, &mut observed, example, columns, comparisons)
        });
        (found, observed)
    }

    /// The test of `relation` over the evaluations, each with the output
    /// sets that its assignment's test recorded.
    pub(crate) fn observed(self, evaluations: &[Evaluation<'_>], observations: &mut [Observed], relation: &GraphRelation, train: &[PairCandidates<'_>]) -> Outcome<Found> {
        self.found(&evaluations[0], relation, train, &mut |example, columns, comparisons| {
            output_sets_observed(evaluations, observations, relation, example, columns, comparisons)
        })
    }

    /// The grid columns of `relation` among the candidates, under which the
    /// grids it gives, read model by model, solve each train pair, whose
    /// candidates are `train`, with `sets` giving the output sets.
    ///
    /// Where two pairs of columns pass and give different output sets on an
    /// input of the task, the grid columns are underdetermined, and this
    /// gives a [`RunFault`] at the form of `relation`. Where several pass
    /// and agree on every input, this gives the first by column position. A
    /// stop at a bound on an input the search reads ends the search with
    /// that stop.
    fn found(
        self,
        evaluation: &Evaluation<'_>, relation: &GraphRelation, train: &[PairCandidates<'_>],
        sets: &mut dyn FnMut(Example, &[GridColumns], &[Comparison<'_, '_>]) -> Outcome<Vec<OutputSet>>,
    ) -> Outcome<Found> {
        let mut passing = self.candidates(evaluation, relation)?;
        for (pair, example) in train.iter().zip(evaluation.task.examples()) {
            if passing.is_empty() {
                break;
            }
            let comparisons = vec![Comparison::Pair(pair); passing.len()];
            let sets = sets(example, &passing, &comparisons)?;
            let mut kept = Vec::new();
            for (columns, set) in passing.into_iter().zip(sets) {
                match set {
                    OutputSet::Stopped(stop) => return Ok(Found::Stopped(stop)),
                    set if solves(&set, pair) => kept.push(columns),
                    _ => {}
                }
            }
            passing = kept;
        }
        let Some(&first) = passing.first() else { return Ok(Found::None) };
        if passing.len() > 1 {
            let comparisons = vec![Comparison::Full; passing.len()];
            for example in evaluation.task.examples() {
                let sets = sets(example, &passing, &comparisons)?;
                if let Some(stop) = sets.iter().find_map(|set| if let OutputSet::Stopped(stop) = set { Some(stop) } else { None }) {
                    return Ok(Found::Stopped(stop.clone()));
                }
                if sets.iter().any(|set| !same_set(set, &sets[0])) {
                    return Err(RunFault { message: "the grid columns of the tested relation are underdetermined".into(), form: evaluation.program.program.form_of(relation.node).clone() });
                }
            }
        }
        Ok(Found::Columns(first))
    }
}

/// The pairs of a Position column and a Color column of a relation whose
/// columns take `types`, each a candidate for its grid columns.
fn candidate_columns(types: &[ValueType]) -> Vec<GridColumns> {
    let of = |ty: ValueType| types.iter().enumerate().filter(move |(_, t)| **t == ty).map(|(i, _)| ColumnIndex(i as u16));
    of(ValueType::Box).flat_map(|position| of(ValueType::Color).map(move |color| GridColumns { position, color })).collect()
}

/// Output sets already evaluated during the assignment filter.
#[derive(Clone, Debug, Default)]
pub(crate) struct Observed(Vec<(Example, GridColumns, bool, OutputSet)>);

/// The output set of `relation` on `example` by each of `columns`, each
/// compared as the comparison at its index in `comparisons` gives: a set
/// that `observed` records for a pair under the rule below is served from
/// it, and every other pair's is given by one enumeration of the case's
/// models, [`output_sets`], and recorded. A recorded set serves a request
/// of the same comparison kind, and a `Full` request where it is a full
/// set of grids or `undefined`.
fn recorded_sets(evaluation: &Evaluation<'_>, relation: &GraphRelation, observed: &mut Observed, example: Example, columns: &[GridColumns], comparisons: &[Comparison<'_, '_>]) -> Outcome<Vec<OutputSet>> {
    let mut sets: Vec<Option<OutputSet>> = Vec::with_capacity(columns.len());
    let (mut missing_columns, mut missing_comparisons) = (Vec::new(), Vec::new());
    for (&columns, &comparison) in columns.iter().zip(comparisons) {
        let full = matches!(comparison, Comparison::Full);
        let found = observed.0.iter().find(|(input, cols, all, set)| *input == example && *cols == columns && (*all == full || (full && matches!(set, OutputSet::Grids(_) | OutputSet::Undefined))));
        if found.is_none() {
            missing_columns.push(columns);
            missing_comparisons.push(comparison);
        }
        sets.push(found.map(|(_, _, _, set)| set.clone()));
    }
    if missing_columns.is_empty() {
        return Ok(sets.into_iter().flatten().collect());
    }
    let mut computed = output_sets(evaluation, relation, example, &missing_columns, &missing_comparisons)?.into_iter();
    let mut recorded_at = 0;
    Ok(sets
        .into_iter()
        .map(|set| {
            set.unwrap_or_else(|| {
                let set = computed.next().expect("one set per missing pair");
                observed.0.push((example, missing_columns[recorded_at], matches!(missing_comparisons[recorded_at], Comparison::Full), set.clone()));
                recorded_at += 1;
                set
            })
        })
        .collect())
}

pub(crate) fn output_sets_observed(evaluations: &[Evaluation<'_>], observations: &mut [Observed], relation: &GraphRelation, example: Example, columns: &[GridColumns], comparisons: &[Comparison<'_, '_>]) -> Outcome<Vec<OutputSet>> {
    let mut enumerations: Vec<(Enumeration<'_, '_>, Next)> = comparisons.iter().map(|&comparison| (Enumeration::new(comparison), Next::GoOn)).collect();
    let mut outside = vec![false; columns.len()];
    for (evaluation, observed) in evaluations.iter().zip(observations.iter_mut()) {
        let live: Vec<usize> = (0..columns.len()).filter(|&at| enumerations[at].1 == Next::GoOn && !outside[at]).collect();
        if live.is_empty() {
            break;
        }
        let live_columns: Vec<GridColumns> = live.iter().map(|&at| columns[at]).collect();
        let live_comparisons: Vec<Comparison<'_, '_>> = live.iter().map(|&at| comparisons[at]).collect();
        let sets = recorded_sets(evaluation, relation, observed, example, &live_columns, &live_comparisons)?;
        for (&at, set) in live.iter().zip(sets) {
            let (enumeration, next) = &mut enumerations[at];
            match set {
                OutputSet::Grids(grids) => for grid in grids {
                    *next = enumeration.push(GridValue::Grid(grid));
                    if *next == Next::Stop { break; }
                },
                OutputSet::Undefined => *next = enumeration.push(GridValue::Undefined),
                OutputSet::Stopped(stop) => *next = enumeration.push(GridValue::Stopped(stop)),
                OutputSet::Outside => outside[at] = true,
            }
        }
    }
    Ok(enumerations.into_iter().zip(outside).map(|((enumeration, _), outside)| if outside { OutputSet::Outside } else { enumeration.finish() }).collect())
}

/// The output set of `relation` on `example` by each of `columns`, each
/// compared as the comparison at its index in `comparisons` gives, over one
/// enumeration of the case's models, which goes on while some set's
/// enumeration does.
fn output_sets(
    evaluation: &Evaluation<'_>,
    relation: &GraphRelation,
    example: Example,
    columns: &[GridColumns],
    comparisons: &[Comparison<'_, '_>],
) -> Outcome<Vec<OutputSet>> {
    let mut enumerations: Vec<(Enumeration<'_, '_>, Next)> =
        comparisons.iter().map(|&comparison| (Enumeration::new(comparison), Next::GoOn)).collect();
    let end = evaluation.models(relation, Some(example), &mut |value| {
        for (&columns, (enumeration, next)) in columns.iter().zip(&mut enumerations) {
            if *next == Next::GoOn {
                *next = enumeration.push(grid(value, columns));
            }
        }
        if enumerations.iter().any(|(_, next)| *next == Next::GoOn) { ControlFlow::Continue(()) } else { ControlFlow::Break(()) }
    })?;
    Ok(enumerations
        .into_iter()
        .map(|(enumeration, _)| match &end {
            ModelsEnd::Stopped(stop) => OutputSet::Stopped(stop.clone()),
            ModelsEnd::Visitor | ModelsEnd::Exhausted => enumeration.finish(),
        })
        .collect())
}

/// The grid that `value`, the relation's value at one model, gives by
/// `columns`.
fn grid(value: &RelationValue, columns: GridColumns) -> GridValue {
    match value {
        RelationValue::Rows(relation) => read_grid(relation, columns).map_or(GridValue::Undefined, GridValue::Grid),
        RelationValue::Undefined => GridValue::Undefined,
        RelationValue::Stopped(stop) => GridValue::Stopped(stop.clone()),
    }
}

/// Whether two full output sets hold the same grids, in any order, or are
/// both `undefined`.
fn same_set(a: &OutputSet, b: &OutputSet) -> bool {
    match (a, b) {
        (OutputSet::Grids(a), OutputSet::Grids(b)) => a.len() == b.len() && a.iter().all(|grid| b.contains(grid)),
        (OutputSet::Undefined, OutputSet::Undefined) => true,
        _ => false,
    }
}
