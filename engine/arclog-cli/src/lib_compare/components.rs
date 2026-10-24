//! The evaluation of a component outside a case program, by its
//! construction, or, for a component with an input that reads its
//! outputs, by the walks of `Unfold`.
//!
//! A component is evaluated over each key group of its inputs: the rows of
//! each input with a `key` column at one key, with that column left out,
//! and every row of each input with none. Each output's rows take the
//! group's key back at their `key` column.
//!
//! A component whose inputs read its outputs is evaluated with the rows
//! of those inputs given, and gives one set of rows of its outputs per
//! walk, at most [`WALKS`].

use arclog::eval::instance::{Construction, ConstructionContext, GroupInputs};
use arclog::eval::join::Budget;
use arclog::eval::unfold::unfold_given;
use arclog::eval::{Caps, Cancellation, Limits};
use arclog::program::ColumnName;
use arclog::registry::{Column, Component, Port, Registry};
use arclog::relations::{Row, RowSet};
use arclog::session::{SessionBound, TaskSession};
use arclog::terms::TermId;
use arclog::types::ValueType;
use serde_json::Value;

use arclog::session::SESSION_BYTES;

use super::evaluation::{cell, insert, term_id, Cell, Rows};
use super::inputs::component_type;

/// Whether `column` is its port's `key` column.
pub(super) fn is_key(column: &Column) -> bool {
    matches!(&column.name, ColumnName::Written(name) if &**name == "key")
}

/// The rows `rows` of an input of `port`, each as its terms.
pub(super) fn port_rows(port: &Port, rows: &Value) -> Result<Vec<Vec<TermId>>, String> {
    let types: Vec<ValueType> = port.columns.iter().map(component_type).collect();
    rows.as_array()
        .into_iter()
        .flatten()
        .map(|row| row.as_array().into_iter().flatten().zip(&types).map(|(value, ty)| term_id(value, ty)).collect())
        .collect()
}

/// The most walks of `Unfold` the evaluation of one inputs file gives.
pub(super) const WALKS: usize = 8;

/// The key groups of the component's inputs, each its key, or `None` where
/// no input has a `key` column, and the rows of each input at that key,
/// with the types of each input's columns other than `key`.
fn key_groups(component: &Component, inputs: &Value) -> Result<(Vec<Box<[ValueType]>>, Vec<(Option<TermId>, Vec<RowSet>)>), String> {
    let written = inputs["inputs"].as_array().map_or(&[][..], Vec::as_slice);
    let mut ports = Vec::new();
    for (port, input) in component.inputs.iter().zip(written) {
        let key = port.port.columns.iter().position(is_key);
        ports.push((key, port_rows(&port.port, &input["rows"])?));
    }
    // Each key once, in the order of the rows of the inputs file.
    let mut keys: Vec<Option<TermId>> = Vec::new();
    for (at, rows) in &ports {
        for row in rows {
            let key = at.map(|at| row[at]);
            if key.is_some() && !keys.contains(&key) {
                keys.push(key);
            }
        }
    }
    if ports.iter().all(|(key, _)| key.is_none()) {
        keys.push(None);
    }
    let types: Vec<Box<[ValueType]>> =
        component.inputs.iter().map(|port| port.port.columns.iter().filter(|c| !is_key(c)).map(component_type).collect()).collect();
    let groups = keys
        .into_iter()
        .map(|key| {
            let group: Vec<RowSet> = ports
                .iter()
                .zip(&types)
                .map(|((at, rows), types)| {
                    let mut set = RowSet::empty(types.len() as u16);
                    for row in rows {
                        match at {
                            Some(at) if Some(row[*at]) != key => {}
                            Some(at) => {
                                set.insert(row.iter().enumerate().filter(|(i, _)| i != at).map(|(_, &id)| id).collect());
                            }
                            None => {
                                set.insert(row.as_slice().into());
                            }
                        }
                    }
                    set
                })
                .collect();
            (key, group)
        })
        .collect();
    Ok((types, groups))
}

/// The session and the limits a component's evaluation runs in.
fn bounds() -> (TaskSession, Limits) {
    (TaskSession::new(SessionBound { bytes: SESSION_BYTES }, Caps::CORPUS), Limits::new(None, Cancellation::default()))
}

/// The cells of `row`, a row of `output`.
fn cells(output: &Port, row: &[TermId]) -> Vec<Cell> {
    row.iter().zip(output.columns.iter()).map(|(&id, column)| cell(id, &component_type(column))).collect()
}

/// The construction's rows of each output of the component's inputs, all
/// outputs asked for, over each key group of the inputs, or the stop of the run.
pub(super) fn constructed(construction: &dyn Construction, component: &Component, inputs: &Value) -> Result<Vec<Rows>, String> {
    let (types, groups) = key_groups(component, inputs)?;
    let (session, limits) = bounds();
    let mut out: Vec<Rows> = vec![Rows::new(); component.outputs.len()];
    let wanted = vec![true; component.outputs.len()];
    for (key, group) in groups {
        let mut budget = Budget::new(&limits, &session);
        let mut context = ConstructionContext { session: &session, registry: Registry::get(), budget: &mut budget };
        let outputs = construction
            .evaluate(&GroupInputs { inputs: &group, types: &types, columns: &types, wanted: &wanted }, &mut context)
            .map_err(|reached| format!("a stop at {reached:?}"))?;
        for ((output, rows), set) in component.outputs.iter().zip(&outputs.outputs).zip(&mut out) {
            let at = output.columns.iter().position(is_key);
            for row in rows.rows() {
                let mut row = row.to_vec();
                match (at, key) {
                    (Some(at), Some(key)) => row.insert(at, key),
                    (Some(_), None) => return Err(format!("the output {} has a key column, and no input has one", output.name.0)),
                    (None, _) => {}
                }
                insert(set, cells(output, &row));
            }
        }
    }
    Ok(out)
}

/// The rows of each output of a component whose inputs read its outputs,
/// for each walk of `Unfold` over each key group of its inputs, at most
/// [`WALKS`], or the stop of the run.
pub(super) fn unfolded(component: &Component, inputs: &Value) -> Result<Vec<Vec<Rows>>, String> {
    let (_, groups) = key_groups(component, inputs)?;
    let keys: Vec<(Row, Vec<RowSet>)> = groups.into_iter().map(|(key, group)| (key.into_iter().collect(), group)).collect();
    let (session, limits) = bounds();
    let mut budget = Budget::new(&limits, &session);
    let walks = unfold_given(component, &keys, WALKS, &mut budget).map_err(|reached| format!("a stop at {reached:?}"))?;
    let rows = |walk: Vec<RowSet>| -> Vec<Rows> {
        component
            .outputs
            .iter()
            .zip(walk)
            .map(|(output, set)| {
                let mut rows = Rows::new();
                for row in set.rows() {
                    insert(&mut rows, cells(output, row));
                }
                rows
            })
            .collect()
    };
    Ok(walks.into_iter().map(rows).collect())
}
