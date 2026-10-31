//! `engine_stats`: the counters of the engine's phases, which
//! [`arclog::stats`] keeps while the environment variable `ARCLOG_STATS` is set.

use arclog::stats;
use pyo3::prelude::*;
use pyo3::types::PyDict;

/// The counters of each phase of the engine, as a dict from the phase's name
/// to a dict of `calls`, `new`, `repeated`, `ns` and `units`, as
/// [`arclog::stats`] defines them. The counters are all 0 unless the
/// environment variable `ARCLOG_STATS` is set when the first phase runs.
/// With `reset` true, the counters start again from zero after they are read.
#[pyfunction]
#[pyo3(signature = (reset=false))]
pub(crate) fn engine_stats<'py>(py: Python<'py>, reset: bool) -> PyResult<Bound<'py, PyDict>> {
    let phases = PyDict::new(py);
    for stat in stats::snapshot(reset) {
        let counters = PyDict::new(py);
        counters.set_item("calls", stat.calls)?;
        counters.set_item("new", stat.new)?;
        counters.set_item("repeated", stat.repeated)?;
        counters.set_item("ns", stat.ns)?;
        counters.set_item("units", stat.units)?;
        phases.set_item(stat.phase.name(), counters)?;
    }
    Ok(phases)
}
