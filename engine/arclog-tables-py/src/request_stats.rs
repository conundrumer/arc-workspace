//! `RequestStats`: the work and the gauges of one request, read once, which
//! a `CaseTables` gives as its `request_stats`.

use arclog::eval::RequestWork;
use pyo3::prelude::*;
use pyo3::types::PyDict;

/// The name, the largest value, the cap and the hits of each gauge.
type Gauges = Vec<(&'static str, u64, u64, u64)>;

/// What `arclog.request_stats()` gives for a request, at the moment of the read.
/// Later work on the request, and the drop of what it held, change none of it.
/// `to_dict` gives the dict in the form of `arclog.request_stats()`
/// (`request_stats` in `arclog-bindings/src/engine_stats.rs`).
#[derive(Clone, Debug)]
pub(crate) struct RequestStats {
    work: u64,
    cap: u64,
    bytes: u64,
    byte_cap: u64,
    effort: u64,
    effort_cap: u64,
    gauges: Gauges,
    search_gauges: Gauges,
    held_gauges: Gauges,
}

fn rows(gauges: impl IntoIterator<Item = (arclog::eval::Gauge, u64, u64, u64)>) -> Gauges {
    gauges.into_iter().map(|(gauge, max, cap, hits)| (gauge.name(), max, cap, hits)).collect()
}

fn gauges_dict<'py>(py: Python<'py>, gauges: &Gauges) -> PyResult<Bound<'py, PyDict>> {
    let dict = PyDict::new(py);
    for &(name, max, cap, hits) in gauges {
        let slot = PyDict::new(py);
        slot.set_item("max", max)?;
        slot.set_item("cap", cap)?;
        slot.set_item("hits", hits)?;
        dict.set_item(name, slot)?;
    }
    Ok(dict)
}

impl RequestStats {
    /// The stats of `request` now.
    pub(crate) fn of(request: &RequestWork) -> Self {
        RequestStats {
            work: request.count(),
            cap: request.cap(),
            bytes: request.byte_count(),
            byte_cap: request.byte_cap(),
            effort: request.effort(),
            effort_cap: request.effort_cap(),
            gauges: rows(request.all_gauges()),
            search_gauges: rows(request.gauges().each()),
            held_gauges: rows(request.held_gauges().each()),
        }
    }

    /// A new dict of the stats, which the caller may change.
    pub(crate) fn to_dict<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PyDict>> {
        let stats = PyDict::new(py);
        stats.set_item("work", self.work)?;
        stats.set_item("cap", self.cap)?;
        stats.set_item("bytes", self.bytes)?;
        stats.set_item("byte_cap", self.byte_cap)?;
        stats.set_item("effort", self.effort)?;
        stats.set_item("effort_cap", self.effort_cap)?;
        stats.set_item("gauges", gauges_dict(py, &self.gauges)?)?;
        stats.set_item("search_gauges", gauges_dict(py, &self.search_gauges)?)?;
        stats.set_item("held_gauges", gauges_dict(py, &self.held_gauges)?)?;
        Ok(stats)
    }
}
