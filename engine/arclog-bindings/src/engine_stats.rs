//! `engine_stats`: the counters of the engine's phases, which
//! [`arclog::stats`] keeps while the collection is on.

use arclog::stats;
use pyo3::prelude::*;
use pyo3::types::PyDict;

/// The counters of each phase of the engine, as a dict from the phase's name
/// to a dict of `calls`, `new`, `repeated`, `ns` and `units`, as
/// [`arclog::stats`] defines them. The collection is off at the start of the
/// process, so the counters are all 0 until a call gives `collect=True`, which
/// turns it on for the whole process; `collect=False` turns it off, and
/// `collect=None` leaves it as it is. The collection costs time: each timed
/// phase reads the clock twice and adds to counters that every thread shares,
/// and the keys it counts are held in one locked set until a reset. It changes
/// no result and no work count of the engine. With `reset` true, the counters
/// start again from zero after they are read.
#[pyfunction]
#[pyo3(signature = (reset=false, collect=None))]
pub(crate) fn engine_stats<'py>(py: Python<'py>, reset: bool, collect: Option<bool>) -> PyResult<Bound<'py, PyDict>> {
    if let Some(on) = collect {
        stats::set_enabled(on);
    }
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

/// The work and the gauges of the request that most recently began on the
/// calling thread, or `None` where none has. A request is a call into a
/// decoder or a study evaluator: a `Decoder` method, `step_tables`,
/// `successor_tables`, `gold_tables` and the like, and the read gives the
/// request of the call that returned last.
///
/// The dict holds `work` and `cap`, the units of work that the request counted
/// (its content: the rows its steps read and write) and its cap
/// (`docs/engine/synthesis.md#decode-settings`), `effort` and `effort_cap`, the
/// bindings that its searches tried and the guard on them (a request past the
/// guard raises `arclog.EffortExhausted`), `bytes` and
/// `byte_cap`, the bytes that the request holds now and its byte budget (the
/// gauge `request_bytes` gives the most it held), and `gauges`, a
/// dict from the name of each capped quantity to a dict of `max`, the largest
/// value the request reached, `cap`, the cap it ran under (0 where it never
/// gave one), and `hits`, how often it passed the cap. The gauges start empty
/// at the begin of the request and hold the work of that request alone. A
/// request that evaluates the held assignments of a gold program (`gold_body`
/// and the study pairs) counts that evaluation apart: `held_gauges` hold the
/// evaluations that ran on the held assignments and `search_gauges` the rest of
/// the request, in the same form as `gauges`, which hold the whole request.
/// `held_gauges` are all zero where the request made no such evaluation, as a
/// `gold_tables` request does not. The count is the work
/// the request did, with each entry that the result cache held charged the
/// cost its entry recorded, and the bytes held are those of a request with
/// empty caches. The read costs a few loads and changes nothing.
///
/// A call whose request passes its work cap or its byte budget, and whose
/// export leaves out tables for that reason, raises `arclog.BudgetReached`
/// (`step_tables`, `base_tables`, `successor_tables`), which names the bound:
/// `bound` is the `StopKind` (`RequestWork` or `RequestBytes`), `cap` its cap
/// as an int, and `tables` the tables left out, each by its relation and the
/// path of its form. It is no `RuntimeError`, which only a fault of the engine
/// raises. The stop depends on the call's inputs and the settings
/// (`request_work_cap`, `request_byte_cap`) alone, so the same call stops
/// again, and a caller may drop what it asked for and go on. A call that
/// evaluates several candidates (`successor_tables`, `atom_tables`) gives the request of the
/// call itself, which counts the work the candidates share and the work of no
/// candidate; its gauges are shared by the candidates. A bound of that request
/// raises `arclog.CallGuardExhausted`, a subclass of `arclog.EngineFault`. The session's byte
/// bound is no budget of the request: the session evicts its caches at it and
/// stops nothing.
#[pyfunction]
pub(crate) fn request_stats<'py>(py: Python<'py>) -> PyResult<Option<Bound<'py, PyDict>>> {
    let Some(request) = arclog::eval::RequestWork::latest() else { return Ok(None) };
    request_dict(py, &request).map(Some)
}

/// The work and the gauges of the request that exported the task's evidence
/// tables in the call that returned last, in the form of [`request_stats`], or
/// `None` where that call exported none. The first model step of a decode
/// (`step_tables`, `successor_tables` with no `before`) holds the evidence
/// tables beside its own, and that export counts in a request of its own, so
/// the request that [`request_stats`] gives holds the step's work alone. The
/// export belongs to the task, not to the query whose step comes first. The
/// read gives the latest such request on the thread, and `None` once another
/// request begins.
#[pyfunction]
pub(crate) fn evidence_request_stats<'py>(py: Python<'py>) -> PyResult<Option<Bound<'py, PyDict>>> {
    let Some(request) = arclog::eval::RequestWork::latest_side() else { return Ok(None) };
    request_dict(py, &request).map(Some)
}

fn request_dict<'py>(py: Python<'py>, request: &arclog::eval::RequestWork) -> PyResult<Bound<'py, PyDict>> {
    let stats = PyDict::new(py);
    stats.set_item("work", request.count())?;
    stats.set_item("cap", request.cap())?;
    stats.set_item("bytes", request.byte_count())?;
    stats.set_item("byte_cap", request.byte_cap())?;
    stats.set_item("effort", request.effort())?;
    stats.set_item("effort_cap", request.effort_cap())?;
    stats.set_item("gauges", gauges_dict(py, request.all_gauges())?)?;
    stats.set_item("search_gauges", gauges_dict(py, request.gauges().each())?)?;
    stats.set_item("held_gauges", gauges_dict(py, request.held_gauges().each())?)?;
    Ok(stats)
}

/// The dict from the name of each gauge to its `max`, `cap` and `hits`.
fn gauges_dict<'py>(py: Python<'py>, gauges: impl IntoIterator<Item = (arclog::eval::Gauge, u64, u64, u64)>) -> PyResult<Bound<'py, PyDict>> {
    let dict = PyDict::new(py);
    for (gauge, max, cap, hits) in gauges {
        let slot = PyDict::new(py);
        slot.set_item("max", max)?;
        slot.set_item("cap", cap)?;
        slot.set_item("hits", hits)?;
        dict.set_item(gauge.name(), slot)?;
    }
    Ok(dict)
}

/// The registry text that the engine embeds as `REGISTRY_TEXT`
/// (`engine/lib/registry.sexpr`), as it was when this build compiled.
#[pyfunction]
pub(crate) fn registry_text() -> &'static str {
    arclog::registry::REGISTRY_TEXT
}

/// Where [`work_total`] counts from: the total at its last reset.
static WORK_TOTAL_BASE: std::sync::atomic::AtomicU64 = std::sync::atomic::AtomicU64::new(0);

/// The units of work that every request of this process has charged, on
/// every thread, since the process started or since the last call with
/// `reset` true: the sum of the `work` of each request that
/// [`request_stats`] gives, a request that is still running included. With
/// `reset` true, the count starts again from zero after it is read.
#[pyfunction]
#[pyo3(signature = (reset=false))]
pub(crate) fn work_total(reset: bool) -> u64 {
    use std::sync::atomic::Ordering;
    let total = arclog::eval::RequestWork::total();
    let since = total.saturating_sub(WORK_TOTAL_BASE.load(Ordering::Relaxed));
    if reset {
        WORK_TOTAL_BASE.store(total, Ordering::Relaxed);
    }
    since
}
