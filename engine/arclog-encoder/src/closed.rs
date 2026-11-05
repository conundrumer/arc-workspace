//! The values of the closed roots on grids alone, for the evaluation of
//! `work/feature-spec/evaluation-protocol.md`: each per-input root whose leaves
//! are the grids and lib relations, at each example of a task that holds the
//! grids to compare. So each grid is one example, and a root's value at it reads
//! that grid alone.

use std::collections::HashSet;
use std::ops::ControlFlow;

use arclog::hash::digest_text;
use arclog::registry::Registry;
use arclog::task::{Grid, Task, TrainPair};
use arclog::terms::Color;
use arclog::types::ValueType;

use crate::encoder::{law_of, Law};
use crate::enumerate::{value_kinds, Space, Typed};
use crate::expression::{Feature, Leaf};
use crate::run::{cell_text, Evaluated, Host, ModelValue, Value};

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

/// The text of a value at one example: the multiset of its values over the
/// models, by a digest, or [`NO_VALUE`].
fn value_text(value: &Value, models: &[ModelValue]) -> String {
    let mut texts: Vec<String> = Vec::with_capacity(models.len());
    for model in models {
        let ModelValue::Rows(rows) = model else { return NO_VALUE.to_string() };
        let mut cells: Vec<String> = rows.iter().map(|row| row.iter().zip(&value.types).map(|(id, ty)| cell_text(*id, ty)).collect::<Vec<_>>().join(",")).collect();
        cells.sort();
        texts.push(cells.join(";"));
    }
    texts.sort();
    digest_text(&texts.join("|"))[..16].to_string()
}

/// Whether a column of this type can stand in an invariant root.
fn invariant_type(ty: &Option<ValueType>) -> bool {
    match ty {
        None => true,
        Some(ty) => matches!(ty, ValueType::Int | ValueType::Nat | ValueType::Unit | ValueType::Example | ValueType::LibName),
    }
}

/// Walks the closed roots of `run` on `host`, whose examples are the grids to
/// compare: `visit` takes each root's text, its size, and its value at each
/// example, and `done` lists the roots a restart skips.
pub fn closed_values(host: &Host, run: &ClosedRun, done: &HashSet<String>, counts: &mut ClosedCounts, visit: &mut dyn FnMut(&str, usize, &[String]) -> ControlFlow<()>) {
    host.set_work_cap(run.work_cap);
    let space = Space {
        registry: Registry::get(),
        tables: host,
        task_wide: false,
        table_names: Vec::new(),
        program_relations: false,
        kinds: value_kinds(),
        max_inputs: run.max_inputs,
        frames: Vec::new(),
        thin: None,
        no_output: run.output_leaf == OutputLeaf::None,
    };
    let mut lower: Vec<Vec<Typed>> = Vec::new();
    let mut seen: HashSet<u128> = HashSet::new();
    for size in 0..=run.size {
        let keep = size < run.size;
        let mut terms = Vec::new();
        let walked = space.generate(&lower, size, &mut |term| {
            counts.terms += 1;
            let mut reads_grid = false;
            let mut reads_output = false;
            term.rel.each_leaf(&mut |leaf| {
                reads_grid |= matches!(leaf, Leaf::Input | Leaf::Output);
                reads_output |= matches!(leaf, Leaf::Output);
            });
            let flow = if !reads_grid {
                counts.constant += 1;
                ControlFlow::Continue(())
            } else if run.output_leaf == OutputLeaf::Required && !reads_output {
                ControlFlow::Continue(())
            } else {
                let at_size = term.size;
                space.roots(&term, &mut |feature| root(host, feature, &term, at_size, done, &mut seen, counts, visit))
            };
            if keep && flow.is_continue() && host.accepts_rel(&term.rel, false) {
                terms.push(term);
            }
            flow
        });
        if walked.is_break() {
            return;
        }
        lower.push(terms);
    }
}

#[allow(clippy::too_many_arguments)]
fn root(host: &Host, feature: Feature, term: &Typed, size: usize, done: &HashSet<String>, seen: &mut HashSet<u128>, counts: &mut ClosedCounts, visit: &mut dyn FnMut(&str, usize, &[String]) -> ControlFlow<()>) -> ControlFlow<()> {
    // All roots here are invariant, so a set of an equivariant column is left out.
    if let Feature::ValueSet(_, columns) = &feature {
        let invariant = columns.iter().all(|name| term.columns.iter().find(|column| column.name == *name).is_none_or(|column| invariant_type(&column.ty)));
        if !invariant {
            counts.equivariant += 1;
            return ControlFlow::Continue(());
        }
    }
    let expression = feature.to_string();
    if done.contains(&expression) {
        return ControlFlow::Continue(());
    }
    let checked = match host.check(&feature) {
        Ok(checked) => checked,
        Err(_) => {
            counts.refused += 1;
            return ControlFlow::Continue(());
        }
    };
    if let Some(identity) = checked.identity {
        if !seen.insert(identity) {
            counts.aliases += 1;
            return ControlFlow::Continue(());
        }
    }
    match host.evaluate_checked(checked) {
        Evaluated::Value(value) => {
            if law_of(&value.types) != Law::Invariant {
                counts.equivariant += 1;
                return ControlFlow::Continue(());
            }
            let Some(at) = value.at.first() else {
                counts.faults += 1;
                return ControlFlow::Continue(());
            };
            let values: Vec<String> = at.examples.iter().map(|(_, models)| value_text(&value, models)).collect();
            counts.written += 1;
            visit(&expression, size, &values)
        }
        Evaluated::Refused(_) => {
            counts.refused += 1;
            ControlFlow::Continue(())
        }
        Evaluated::Fault(_) => {
            counts.faults += 1;
            ControlFlow::Continue(())
        }
    }
}
