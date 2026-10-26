//! The check of the rows that a component's outputs declare they copy: at
//! each key group of an instance, each row of an output is, at the columns a
//! declared row of the registry's `copies` maps, the values of a row of that
//! row's input in the group, or of one of its alternatives. The `key` column
//! is not checked: a group's rows share its key by the grouping.
//!
//! An evaluation checks only where its [`crate::eval::Limits`] hold a
//! [`CopyViolations`], to which it reports each declared row that an output
//! of a construction breaks.

use std::ops::Range;
use std::sync::{Arc, Mutex};

use super::instance::{width, GroupInputs, GroupOutputs};
use crate::hash::StableHashSet;
use crate::program::path::NodePath;
use crate::program::PortName;
use crate::registry::{Component, LibName};
use crate::terms::TermId;

/// A declared row of an output that the output's rows break at some group of
/// an instance: the count of output rows, over the instance's groups, whose
/// values at the columns the row maps are no row of its input.
#[derive(Clone, PartialEq, Eq, Debug)]
pub struct CopyViolation {
    /// The path of the `INIT` form of the instance.
    pub form: NodePath,
    pub component: LibName,
    pub output: PortName,
    /// The index of the declared row among the output's.
    pub row: usize,
    pub rows: usize,
}

impl CopyViolation {
    fn order(&self) -> (&NodePath, &str, usize, usize) {
        (&self.form, &self.output.0, self.row, self.rows)
    }
}

/// The violations that the evaluations sharing it report. Clones share the
/// list.
#[derive(Clone, Default, Debug)]
pub struct CopyViolations(Arc<Mutex<Vec<CopyViolation>>>);

impl CopyViolations {
    /// Adds `violation`.
    pub fn report(&self, violation: CopyViolation) {
        self.0.lock().unwrap_or_else(|poisoned| poisoned.into_inner()).push(violation);
    }

    /// The violations reported since the last call, each once, in the order
    /// of their forms, outputs and declared rows.
    pub fn take(&self) -> Vec<CopyViolation> {
        let mut found = std::mem::take(&mut *self.0.lock().unwrap_or_else(|poisoned| poisoned.into_inner()));
        found.sort_by(|a, b| a.order().cmp(&b.order()));
        found.dedup();
        found
    }
}

/// The cells of `row` at `ranges`, in order.
fn project(row: &[TermId], ranges: &[Range<usize>]) -> Box<[TermId]> {
    ranges.iter().flat_map(|range| row[range.clone()].iter().copied()).collect()
}

/// For each output of `component` that `group` wants, and each of its declared
/// rows that its rows in `outputs` break, the output's index, the row's index
/// and the count of rows that break it. `widths` are the widths of the
/// outputs' columns, `None` for a `key`, as the instance lays them out.
pub fn broken_rows(component: &Component, group: &GroupInputs<'_>, outputs: &GroupOutputs, widths: &[Vec<Option<usize>>]) -> Vec<(usize, usize, usize)> {
    let mut found = Vec::new();
    for (index, output) in component.outputs.iter().enumerate().filter(|(index, output)| group.wanted[*index] && !output.copies.is_empty()) {
        let to = output.row_ranges(false, widths[index].iter().flatten().copied());
        for (row, declared) in output.copies.iter().enumerate() {
            // Each alternative: its output positions, and the input's rows at its input positions.
            let alternatives: Vec<(Vec<Range<usize>>, StableHashSet<Box<[TermId]>>)> = declared
                .alternatives
                .iter()
                .map(|from| {
                    let input = &component.inputs[from.input].port;
                    let held = input.row_ranges(false, group.columns[from.input].iter().map(width));
                    let (own, copied): (Vec<_>, Vec<_>) = from.columns.iter().map(|&(source, target)| (held[source].clone().expect("a column other than the key"), to[target].clone().expect("a column other than the key"))).unzip();
                    let rows = group.inputs[from.input].rows().map(|row| project(row, &own)).collect();
                    (copied, rows)
                })
                .collect();
            let broken = outputs.outputs[index].rows().filter(|row| !alternatives.iter().any(|(copied, rows)| rows.contains(&project(row, copied)))).count();
            if broken > 0 {
                found.push((index, row, broken));
            }
        }
    }
    found
}
