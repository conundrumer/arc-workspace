//! `step_tables`: the tables of the last step of a decode, and
//! `output_columns`: the columns that the `OUT` form at which the decode ended
//! selects.

use std::sync::Arc;

use arclog::stream::Emitter;
use arclog_bindings::PyDecoder;
use arclog_tables::columns::step_case_columns;
use arclog_tables::tables::{evidence_tables, record_step, selected_columns, Points};
use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;

use crate::case_tables::{Base, PyCaseTables, Step};

/// The tables of the last step of `decoder`, a `Decoder` at any state, a fork
/// included, for the case `case` of the task `task`, as `stream_tables` gives
/// that step of the same stream, with the token of the step as their token.
/// They are the table of each relation that the form the step ended declares,
/// with their rows on each example at each assignment, and, where `bodies` is
/// true, the table of the body in progress, as `bodies` is in `stream_tables`.
/// The call replays no token and writes no file, and runs with the GIL
/// released, but for the build of the `CaseTables`.
///
/// `before` is the `CaseTables` that `step_tables` gave at the decode's
/// previous model step, or, for a fork, at the last model step of the decode
/// it was forked from. With `before`, the result holds the step's own tables
/// alone, numbered from `k`, the count of the stream's tables before them, as a
/// case of `stream_tables` that has a base holds its own: `base` is `case`,
/// `base_tokens` the token of the step and `base_tables` is `k`. Each part of
/// the result equals that step's in `stream_tables` of the same stream, and
/// every table number in it is a number of the stream's whole list of tables:
/// the result's own tables are numbered from `k`, and a flow whose source is a
/// table of an earlier step gives that table's number, below `k`, in
/// `source_table` and the column's index in it in `source_column`. The frames,
/// extents, `DET` slots and labels resolve through the earlier tables.
/// Without `before`, the call is at the decode's first model step, and the
/// result is the two evidence tables and the step's tables, with no base. A
/// step that gives no table, such as a decode before its first step, a `*`
/// before its echo, or a step in a form with no relation, adds none.
///
/// `ValueError` is raised, before any evaluation, where `before` is `None` and
/// the decode has a model step before its last, and where `before` is no
/// result of `step_tables`, gives another task, another case or another
/// `bodies`, or gives a step at a token not below the step's. A `before` of a
/// decode before its first step has no step, and passes.
///
/// The `CaseTables` has the `task` and the `case` that the call gives, as a
/// `Decoder` holds neither. Its `relation_name` is the relation as the program
/// spells it, with the slot of a name a decode gives no text. Where the
/// settings check copies, the `copies` part holds the violations that the
/// decode found since the last call that took them, which this call takes.
///
/// `output_position` and `output_color` are -1 in each table, since the `OUT`
/// form that selects a column ends the decode at a step after the one that
/// gives that column's table: `output_columns` gives that selection.
#[pyfunction]
#[pyo3(signature = (decoder, task, case, bodies=false, before=None))]
pub(crate) fn step_tables(py: Python<'_>, decoder: PyRef<'_, PyDecoder>, task: String, case: String, bodies: bool, before: Option<PyRef<'_, PyCaseTables>>) -> PyResult<PyCaseTables> {
    let points = if bodies { Points::All } else { Points::Relations };
    let (engine, evidence) = (decoder.decoder(), decoder.task());
    // The indexes of the tokens the model wrote, which the engine's forced tokens follow in the trace. The last is the index `stream_tables` gives the step; a decode before its first step has none, and no table.
    let written: Vec<usize> = engine.trace().records().iter().enumerate().filter(|(_, record)| record.emitter == Emitter::Model).map(|(index, _)| index).collect();
    let index = written.last().copied();
    let earlier = check_before(before.as_deref(), &task, &case, bodies, &written)?;
    let (columns, names) = py.detach(|| {
        let mut tables = Vec::new();
        if let Some(index) = index {
            record_step(&mut tables, engine, index, points);
        }
        let (columns, names) = step_case_columns(earlier.map(|step| &*step.names), &evidence_tables(evidence, engine.registry()), &tables, evidence.train.len());
        (columns.with_copies(&engine.take_copy_violations()), names)
    });
    let base = earlier.map(|step| Base { case: case.clone(), tokens: index.unwrap_or(0), tables: step.names.tables() });
    Ok(PyCaseTables::of(py, task, case, false, engine.settings().projection_cap, &columns, None, base)?.with_step(Step { names: Arc::new(names), bodies, token: index }))
}

/// The `Step` of `before`, the `before` of a call of `step_tables` for `task`
/// and `case` under `bodies`, at the step of the last of the tokens `written`
/// by the model, or a `ValueError` where `before` cannot stand before that
/// step. It is `None` for the call at the first model step, which has no
/// `before`.
fn check_before<'b>(before: Option<&'b PyCaseTables>, task: &str, case: &str, bodies: bool, written: &[usize]) -> PyResult<Option<&'b Step>> {
    let index = written.last().copied();
    let Some(before) = before else {
        return if written.len() > 1 { Err(PyValueError::new_err(format!("the decode has {} model steps, and a call after its first takes the result of the call at the previous model step as `before`", written.len()))) } else { Ok(None) };
    };
    let Some(step) = before.step() else { return Err(PyValueError::new_err("`before` is no result of `step_tables`")) };
    if before.task != task || before.case != case {
        return Err(PyValueError::new_err(format!("`before` is of the task {} and the case {}, not of {task} and {case}", before.task, before.case)));
    }
    if step.bodies != bodies {
        return Err(PyValueError::new_err(format!("`before` was made with bodies={}, not bodies={bodies}", step.bodies)));
    }
    match (step.token, index) {
        (Some(token), Some(index)) if token >= index => Err(PyValueError::new_err(format!("`before` is the step at token {token}, not below the step at token {index}"))),
        (Some(token), None) => Err(PyValueError::new_err(format!("`before` is the step at token {token}, and the decode has no model step"))),
        _ => Ok(Some(step)),
    }
}

/// The columns that the `OUT` form at which `decoder` ended selects: one
/// `(slot, position, color)` for each relation an atom of the form selects a
/// column of, with `slot` the `relation` of that relation's table in
/// `step_tables`, `position` the index of the Position column the form selects
/// there and `color` that of the Color column, and -1 for a column it does not
/// select there. They are the `output_position` and `output_color` of that
/// relation's table in `stream_tables` of the same stream. The list is empty
/// where the decode has not ended at an `OUT` form whose check holds.
#[pyfunction]
pub(crate) fn output_columns(py: Python<'_>, decoder: PyRef<'_, PyDecoder>) -> Vec<(u32, i32, i32)> {
    let engine = decoder.decoder();
    py.detach(|| selected_columns(engine).into_iter().map(|(slot, selected)| (slot, selected.position.map_or(-1, i32::from), selected.color.map_or(-1, i32::from))).collect())
}
