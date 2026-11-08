//! The values of the closed roots on grids alone, for the evaluation of
//! `docs/feature-spec/evaluation-protocol.md`: each per-input root whose leaves
//! are the grids and lib relations, at each example of a task that holds the
//! grids to compare. So each grid is one example, and a root's value at it reads
//! that grid alone.

use std::ops::ControlFlow;

use arclog::hash::digest_text;
use arclog::registry::Registry;
use arclog::relations::Relation;
use arclog::task::{Grid, Task, TrainPair};
use arclog::terms::{Color, TermId};
use arclog::types::ValueType;

use crate::enumerate::{Space, Typed};
use crate::expand::{label_of, Col};
use crate::expression::{Feature, Leaf, Rel};
use crate::lookup::LookupSet;
use crate::run::{cell_text, Host, TermValues};

/// Which roots a run reads, by their `output` leaf.
#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub enum OutputLeaf {
    /// Roots with no `output` leaf, for Scene recognition.
    None,
    /// Roots with an `output` leaf, for Rule recognition.
    Required,
}

/// What a run of closed roots reads.
#[derive(Clone, Debug)]
pub struct ClosedRun {
    pub size: usize,
    pub max_inputs: Option<usize>,
    pub output_leaf: OutputLeaf,
    pub work_cap: u64,
}

/// The value at no example: a stop, a fault or an undefined relation.
pub const NO_VALUE: &str = "-";

/// The counts of a run.
#[derive(Clone, Debug, Default)]
pub struct ClosedCounts {
    pub terms: u64,
    /// Roots of a term with no grid leaf, which take one value on every grid.
    pub constant: u64,
    pub refused: u64,
    pub aliases: u64,
    pub equivariant: u64,
    pub faults: u64,
    pub written: u64,
}

fn grid_of(rows: &[Vec<u8>]) -> Result<Grid, String> {
    let colors: Option<Vec<Box<[Color]>>> = rows.iter().map(|row| row.iter().map(|digit| Color::from_digit(*digit)).collect::<Option<Vec<Color>>>().map(Vec::into_boxed_slice)).collect();
    Grid::from_rows(colors.ok_or("a digit that is no color")?.into()).ok_or_else(|| "a grid with no cells or with rows of unequal lengths".to_string())
}

/// A task whose examples are `inputs`, each a test input.
pub fn task_of_inputs(inputs: &[Vec<Vec<u8>>]) -> Result<Task, String> {
    Ok(Task { train: Box::new([]), test: inputs.iter().map(|grid| grid_of(grid)).collect::<Result<Vec<_>, _>>()?.into() })
}

/// A task whose examples are `pairs`, each a train pair.
pub fn task_of_pairs(pairs: &[(Vec<Vec<u8>>, Vec<Vec<u8>>)]) -> Result<Task, String> {
    let train: Result<Vec<TrainPair>, String> = pairs.iter().map(|(input, output)| Ok(TrainPair { input: grid_of(input)?, output: grid_of(output)? })).collect();
    Ok(Task { train: train?.into(), test: Box::new([]) })
}

/// The modulus of the hash of a set of rows.
const MODULUS: u128 = (1u128 << 61) - 1;

/// A hash of `value` at the place `at`, below [`MODULUS`] and above 0.
fn cell_hash(at: usize, id: TermId, ty: &ValueType) -> u128 {
    let text = match ty {
        ValueType::LibName => cell_text(id, ty),
        _ => id.encoding().to_string(),
    };
    let digest = digest_text(&format!("{at}/{text}"));
    u128::from_str_radix(&digest[..15], 16).unwrap_or(1) % (MODULUS - 1) + 1
}

/// A hash of the set of rows of `relation` at the row positions `positions`,
/// which depends on that set alone, and not on how the relation splits its
/// columns into parts: a part's rows, projected, hash as the sum of each
/// distinct row's product of its values' hashes, and the set as the product of
/// the sums.
fn set_hash(relation: &Relation, positions: &[usize], types: &[ValueType]) -> u64 {
    if relation.is_empty() {
        return VALUE_SET;
    }
    let mut product: u128 = 1;
    for part in relation.parts() {
        let chosen: Vec<(usize, usize)> = part
            .columns
            .iter()
            .enumerate()
            .filter_map(|(place, column)| positions.iter().position(|position| *position == usize::from(column.0)).map(|at| (place, at)))
            .collect();
        if chosen.is_empty() {
            continue;
        }
        let mut seen: LookupSet<Vec<u32>> = LookupSet::new();
        let mut sum: u128 = 0;
        for row in part.rows.rows() {
            let key: Vec<u32> = chosen.iter().map(|(place, _)| row[*place].encoding()).collect();
            if seen.insert(key) {
                let hash = chosen.iter().fold(1u128, |hash, (place, at)| hash * cell_hash(*at, row[*place], &types[positions[*at]]) % MODULUS);
                sum = (sum + hash) % MODULUS;
            }
        }
        product = product * sum % MODULUS;
    }
    VALUE_SET | (product as u64 & (VALUE_SET - 1))
}

/// The bits that say what a value is: a set of rows, a count or whether a
/// relation has a row, so no two kinds of value have one word.
const VALUE_SET: u64 = 1 << 62;
const VALUE_COUNT: u64 = 2 << 61;
const VALUE_NONEMPTY: u64 = 1 << 61;

/// Whether a column of this type can stand in an invariant root.
fn invariant_type(ty: &ValueType) -> bool {
    matches!(ty, ValueType::Int | ValueType::Nat | ValueType::Unit | ValueType::Example | ValueType::LibName)
}

/// The most terms that one program holds.
const BATCH: usize = 256;

/// Walks the closed roots of `run` on `host`, whose examples are the grids to
/// compare: `visit` takes each root's text, its size, and its value at each
/// example, and `done` lists the roots a restart skips. A root reads the rows of
/// its term once, so each term is evaluated once, and the terms of a batch stand
/// in one program.
pub fn closed_values(host: &Host, run: &ClosedRun, done: &LookupSet<String>, counts: &mut ClosedCounts, visit: &mut dyn FnMut(&str, usize, &[String]) -> ControlFlow<()>) {
    host.set_work_cap(run.work_cap);
    let space = Space {
        registry: Registry::get(),
        tables: host,
        task_wide: false,
        table_names: Vec::new(),
        program_relations: false,
        max_inputs: run.max_inputs,
        thin: None,
        no_output: run.output_leaf == OutputLeaf::None, quick: false, max_bound_columns: None,
    };
    let mut lower: Vec<Vec<Typed>> = Vec::new();
    let mut seen: LookupSet<u128> = LookupSet::new();
    for size in 0..=run.size {
        let keep = size < run.size;
        let mut terms: Vec<Typed> = Vec::new();
        let mut pending: Vec<Typed> = Vec::new();
        let walked = space.generate(&lower, size, &mut |term| {
            counts.terms += 1;
            let mut reads_grid = false;
            let mut reads_output = false;
            term.rel.each_leaf(&mut |leaf| {
                reads_grid |= matches!(leaf, Leaf::Input | Leaf::Output);
                reads_output |= matches!(leaf, Leaf::Output);
            });
            if !reads_grid {
                counts.constant += 1;
                if keep {
                    terms.push(term);
                }
                return ControlFlow::Continue(());
            }
            if run.output_leaf == OutputLeaf::Required && !reads_output && !keep {
                return ControlFlow::Continue(());
            }
            pending.push(term);
            if pending.len() < BATCH {
                return ControlFlow::Continue(());
            }
            flush(host, run, &mut pending, &mut terms, keep, done, &mut seen, counts, visit)
        });
        if walked.is_break() {
            return;
        }
        if flush(host, run, &mut pending, &mut terms, keep, done, &mut seen, counts, visit).is_break() {
            return;
        }
        lower.push(terms);
    }
}

#[allow(clippy::too_many_arguments)]
fn flush(host: &Host, run: &ClosedRun, pending: &mut Vec<Typed>, terms: &mut Vec<Typed>, keep: bool, done: &LookupSet<String>, seen: &mut LookupSet<u128>, counts: &mut ClosedCounts, visit: &mut dyn FnMut(&str, usize, &[String]) -> ControlFlow<()>) -> ControlFlow<()> {
    let batch = std::mem::take(pending);
    let rels: Vec<&Rel> = batch.iter().map(|term| &term.rel).collect();
    let evaluated = host.evaluate_terms(&rels, false);
    for (term, outcome) in batch.into_iter().zip(evaluated) {
        let mut accepted = false;
        let mut flow = ControlFlow::Continue(());
        match outcome {
            Err(_) => counts.refused += 1,
            Ok(values) => {
                accepted = true;
                let mut reads_output = false;
                term.rel.each_leaf(&mut |leaf| reads_output |= matches!(leaf, Leaf::Output));
                if run.output_leaf == OutputLeaf::Required && !reads_output {
                    // A term with no `output` leaf stands only under a larger one.
                } else if values.identity.is_some_and(|identity| !seen.insert(identity)) {
                    counts.aliases += 1;
                } else {
                    flow = term_roots(&term, &values, done, counts, visit);
                }
            }
        }
        if keep && accepted {
            terms.push(term);
        }
        flow?;
    }
    ControlFlow::Continue(())
}

/// The roots over `term`, whose rows `values` holds, at each example.
fn term_roots(term: &Typed, values: &TermValues, done: &LookupSet<String>, counts: &mut ClosedCounts, visit: &mut dyn FnMut(&str, usize, &[String]) -> ControlFlow<()>) -> ControlFlow<()> {
    let rel = &term.rel;
    let size = term.size;
    let position_of = |column: &Col| values.row_names.iter().position(|name| *name == label_of(&column.name) || *name == column.name);
    // A set of an equivariant column is left out, since all roots here are invariant.
    let invariant: Vec<(String, usize)> = term
        .columns
        .iter()
        .filter_map(|column| {
            let at = position_of(column)?;
            invariant_type(values.types.get(at)?).then(|| (column.name.clone(), at))
        })
        .collect();
    counts.equivariant += term.columns.len().saturating_sub(invariant.len()) as u64;
    let nonempty = Feature::Nonempty(rel.clone()).to_string();
    let cardinality = Feature::Cardinality(rel.clone()).to_string();
    let number = |word: u64| format!("{word:016x}");
    if !done.contains(&nonempty) {
        let row: Vec<String> = values.examples.iter().map(|value| value.as_ref().map_or(NO_VALUE.to_string(), |relation| number(VALUE_NONEMPTY | u64::from(!relation.is_empty())))).collect();
        counts.written += 1;
        visit(&nonempty, size, &row)?;
    }
    if !done.contains(&cardinality) {
        let row: Vec<String> = values.examples.iter().map(|value| value.as_ref().map_or(NO_VALUE.to_string(), |relation| number(VALUE_COUNT | relation.len()))).collect();
        counts.written += 1;
        visit(&cardinality, size, &row)?;
    }
    let count = invariant.len().min(12);
    for mask in 1u32..(1 << count) {
        let chosen: Vec<&(String, usize)> = (0..count).filter(|at| mask & (1 << at) != 0).map(|at| &invariant[at]).collect();
        let columns: Vec<String> = chosen.iter().map(|(name, _)| name.clone()).collect();
        let positions: Vec<usize> = chosen.iter().map(|(_, at)| *at).collect();
        let expression = Feature::ValueSet(rel.clone(), columns).to_string();
        if done.contains(&expression) {
            continue;
        }
        let row: Vec<String> = values.examples.iter().map(|value| value.as_ref().map_or(NO_VALUE.to_string(), |relation| number(set_hash(relation, &positions, &values.types)))).collect();
        counts.written += 1;
        visit(&expression, size, &row)?;
    }
    ControlFlow::Continue(())
}
