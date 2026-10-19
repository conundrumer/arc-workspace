//! The evaluation of a component by its construction, outside a case
//! program.
//!
//! A component is evaluated by its construction over each key group of its
//! inputs: the rows of each input with a `key` column at one key, with
//! that column left out, and every row of each input with none. Each
//! output's rows take the group's key back at their `key` column.

use arclog::eval::instance::{Construction, ConstructionContext, GroupInputs};
use arclog::eval::join::Budget;
use arclog::eval::{Caps, Cancellation, Limits};
use arclog::program::ColumnName;
use arclog::registry::{Column, Component, Port, Registry};
use arclog::relations::RowSet;
use arclog::session::{SessionBound, TaskSession};
use arclog::terms::TermId;
use arclog::types::ValueType;
use serde_json::Value;

use crate::compare::SESSION_BYTES;

use super::evaluation::{cell, insert, term_id, Rows};
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

/// The construction's rows of each output of the component's inputs, over
/// each key group of the inputs, or the stop of the run.
pub(super) fn constructed(construction: &dyn Construction, component: &Component, inputs: &Value) -> Result<Vec<Rows>, String> {
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
    let session = TaskSession::new(SessionBound { bytes: SESSION_BYTES }, Caps::PROVISIONAL);
    let limits = Limits { deadline: None, cancellation: Cancellation::default() };
    let mut out: Vec<Rows> = vec![Rows::new(); component.outputs.len()];
    for key in keys {
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
        let mut budget = Budget::new(&limits, &session);
        let mut context = ConstructionContext { session: &session, registry: Registry::get(), budget: &mut budget };
        let outputs = construction
            .evaluate(&GroupInputs { inputs: &group, types: &types }, &mut context)
            .map_err(|reached| format!("a stop at {reached:?}"))?;
        for ((output, rows), set) in component.outputs.iter().zip(&outputs.outputs).zip(&mut out) {
            let types: Vec<ValueType> = output.columns.iter().map(component_type).collect();
            let at = output.columns.iter().position(is_key);
            for row in rows.rows() {
                let mut row = row.to_vec();
                match (at, key) {
                    (Some(at), Some(key)) => row.insert(at, key),
                    (Some(_), None) => return Err(format!("the output {} has a key column, and no input has one", output.name.0)),
                    (None, _) => {}
                }
                insert(set, row.iter().zip(&types).map(|(&id, ty)| cell(id, ty)).collect());
            }
        }
    }
    Ok(out)
}
