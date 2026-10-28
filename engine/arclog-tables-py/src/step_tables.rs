//! `step_tables`: the tables of the last step of a decode.

use arclog::stream::Emitter;
use arclog_bindings::PyDecoder;
use arclog_tables::columns::case_columns;
use arclog_tables::tables::{evidence_tables, record_step, Points};
use pyo3::prelude::*;

use crate::case_tables::PyCaseTables;

/// The tables of the last step of `decoder`, a `Decoder` at any state, a fork
/// included, for the case `case` of the task `task`, as `stream_tables` gives
/// that step of the same stream: the `CaseTables` of the two evidence tables
/// and of the tables the step recorded, with the token of the step as their
/// token. They are the table of each relation that the form the step ended
/// declares, with their rows on each example at each assignment, and, where
/// `bodies` is true, the table of the body in progress, as `bodies` is in
/// `stream_tables`. Where the step gives no table, such as a decode before its
/// first step, a `*` before its echo, or a step in a form with no relation,
/// the `CaseTables` holds the evidence tables alone. The call replays no token
/// and writes no file, and runs with the GIL released, but for the build of the
/// `CaseTables`.
///
/// A flow whose source is a table of a step before the last has no table in
/// the result: its `source_table` is -1 and its `source_relation` names the
/// relation. That name is the one relation of the decode that every form
/// declares once, as a decode takes a new slot for each declaration, and a
/// relation has one table in the decode, at the step of the form that declares
/// it: a reader finds that table in the `step_tables` of that step, or in
/// `stream_tables` as the table whose `relation_name` is the name. The
/// `CaseTables` has the `task` and the `case` that the call gives, as a
/// `Decoder` holds neither, and no base. Its `relation_name` is the relation
/// as the program spells it, with the slot of a name a decode gives no text.
/// Where the settings check copies, the `copies` part holds the violations
/// that the decode found since the last call that took them, which this call
/// takes.
#[pyfunction]
#[pyo3(signature = (decoder, task, case, bodies=false))]
pub(crate) fn step_tables(py: Python<'_>, decoder: PyRef<'_, PyDecoder>, task: String, case: String, bodies: bool) -> PyResult<PyCaseTables> {
    let points = if bodies { Points::All } else { Points::Relations };
    let (engine, evidence) = (decoder.decoder(), decoder.task());
    let columns = py.detach(|| {
        let mut tables = Vec::new();
        // The index of the last token the model wrote, which the engine's forced tokens follow in the trace: the index `stream_tables` gives the step. A decode before its first step has none, and no table.
        if let Some(index) = engine.trace().records().iter().rposition(|record| record.emitter == Emitter::Model) {
            record_step(&mut tables, engine, index, points);
        }
        case_columns(&evidence_tables(evidence, engine.registry()), &tables, evidence.train.len(), None).with_copies(&engine.take_copy_violations())
    });
    PyCaseTables::of(py, task, case, false, engine.settings().projection_cap, &columns, None, None)
}
