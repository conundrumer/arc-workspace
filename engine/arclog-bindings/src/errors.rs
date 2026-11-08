//! The exceptions of the module and the conversions of the engine's faults
//! to them.

use arclog::diagnostic::Location;
use arclog::eval::{take_effort_fault, EffortFault, Outcome, ReachedBound, RunFault};
use arclog::program::canonical::LabelingBound;
use arclog::study::StudyError;
use arclog::trace::Stop;
use pyo3::create_exception;
use pyo3::exceptions::{PyException, PyRuntimeError, PyValueError};
use pyo3::prelude::*;

use crate::results::PyStopKind;

create_exception!(arclog, Refusal, PyException, "The engine refuses its input: a decode refuses a token outside its mask, `CheckRefused` for a program that its checks refuse, or `LabelingBoundReached` for a query that has no hash. It is no `ValueError`: a `ValueError` from the engine is a bug of the caller.");
create_exception!(
    arclog,
    CheckRefused,
    Refusal,
    "The engine's checks refuse a program. Attributes: `check`, the name of the first check that refused it (`Picks`, `Types`, `Grammar`, ...); `at`, the path of the node it refused, as the list of the indexes from the top-level form, or None where the refusal stands at a place of the program's text; `line` and `column`, from 1, of that place, or None where it stands at a path. The message holds the text of all of the refusals."
);
create_exception!(
    arclog,
    LabelingBoundReached,
    Refusal,
    "A query has no hash: the search for the canonical labeling of a form that it reads passed its cap of search nodes, so the hash would depend on the written order. The same query is refused again. Attributes: `bound`, the name of the bound (`LabelingNodes`); `cap`, the bound's cap as an int."
);
create_exception!(arclog, EngineFault, PyRuntimeError, "The base of the faults of the engine: a call that raises one has no result, and the same call, run again, may raise it again. `Fault` and `EffortExhausted` are its subclasses.");
create_exception!(arclog, Fault, EngineFault, "A run of the engine faults.");
create_exception!(
    arclog,
    EffortExhausted,
    EngineFault,
    "A request passed its effort guard: the searches of the call tried more bindings than the guard allows (the gauge `effort` of `request_stats()`). It stops a runaway and is a fault of the call, never a result: no table, mask or count is given. Attributes: `gauge`, the name of the gauge that passed its cap (`effort`); `cap`, its cap as an int."
);
create_exception!(
    arclog,
    BudgetReached,
    PyException,
    "A call stopped at a bound of its request or of its tables (a budget), and its export left out tables. It is no fault of the engine: its result depends on the call's inputs alone, and the same call stops again. Attributes: `bound`, the `StopKind` of the bound (`RequestWork`, `RequestBytes`, `TableWork`, `Assignments`, ...); `cap`, the bound's cap as an int, or None where it has none; `tables`, the list of the tables left out, each by its relation and the path of its form."
);

create_exception!(arclog, RecordedIdentityError, PyValueError, "Native recorded identity admission failed; args=(stage,message).");

fn fault(fault: RunFault) -> PyErr {
    Fault::new_err(fault.message.to_string())
}

/// The `BudgetReached` for a call whose export stopped at `bound` and left
/// out `left_out`, the tables it names: the error carries the bound as
/// `bound`, its cap as `cap` and the tables as `tables`. A caller tells such a
/// stop from a fault of the engine by this type.
pub fn budget_reached(py: Python<'_>, bound: ReachedBound, left_out: &[String]) -> PyErr {
    let error = BudgetReached::new_err(format!("the export of the tables stopped at {bound:?} and left out the table of {}", left_out.join(", ")));
    let value = error.value(py);
    let named = Py::new(py, PyStopKind::from(Stop::from(bound))).and_then(|kind| value.setattr("bound", kind)).and_then(|()| value.setattr("cap", bound.cap())).and_then(|()| value.setattr("tables", left_out.to_vec()));
    match named {
        Ok(()) => error,
        Err(failure) => failure,
    }
}

/// The Python error for `error`, which the engine gives for a program or a
/// stream: a `CheckRefused` for a refusal of a check, with the attributes
/// `check`, `at`, `line` and `column` of the first refusal in it, a `Fault`
/// for a failure inside the engine, and a `Refusal` for any other reason.
pub fn study_error(py: Python<'_>, error: StudyError) -> PyErr {
    let message = error.to_string();
    if matches!(error, StudyError::Fault(_)) {
        return Fault::new_err(message);
    }
    let Some((check, diagnostic)) = error.first_check_error() else {
        return Refusal::new_err(message);
    };
    let (at, line, column): (Option<Vec<u32>>, Option<u32>, Option<u32>) = match &diagnostic.location {
        Location::Path(path) => (Some(path.0.iter().map(|step| step.0).collect()), None, None),
        Location::Places(places) => match places.first() {
            Some(file_place) => (None, Some(file_place.place.line), Some(file_place.place.column)),
            None => (None, None, None),
        },
    };
    let refused = CheckRefused::new_err(message);
    let value = refused.value(py);
    let named = value
        .setattr("check", format!("{check:?}"))
        .and_then(|()| value.setattr("at", at))
        .and_then(|()| value.setattr("line", line))
        .and_then(|()| value.setattr("column", column));
    match named {
        Ok(()) => refused,
        Err(failure) => failure,
    }
}

/// The `LabelingBoundReached` for a query that passed `bound`: the error
/// carries the bound's name as `bound` and its cap as `cap`. A caller tells
/// such a refusal from a missing query by this type.
pub fn labeling_bound_reached(py: Python<'_>, bound: LabelingBound) -> PyErr {
    let error = LabelingBoundReached::new_err(bound.to_string());
    let value = error.value(py);
    match value.setattr("bound", "LabelingNodes").and_then(|()| value.setattr("cap", bound.cap)) {
        Ok(()) => error,
        Err(failure) => failure,
    }
}

/// The `EffortExhausted` that raises for `fault`: the error carries the name
/// of the gauge as `gauge` and its cap as `cap`.
pub(crate) fn effort_exhausted(py: Python<'_>, fault: EffortFault) -> PyErr {
    let error = EffortExhausted::new_err(format!("the request passed its effort guard of {} bindings tried", fault.cap));
    let value = error.value(py);
    match value.setattr("gauge", fault.gauge.name()).and_then(|()| value.setattr("cap", fault.cap)) {
        Ok(()) => error,
        Err(failure) => failure,
    }
}

/// `Ok` where no request begun on this thread passed its effort guard since
/// the last check, and else the `EffortExhausted` that stands in place of the
/// result of the call that ran the request. A call that begins a request
/// asks it after the call ends, with its result in hand and unused.
pub fn check_effort(py: Python<'_>) -> PyResult<()> {
    match take_effort_fault() {
        None => Ok(()),
        Some(fault) => Err(effort_exhausted(py, fault)),
    }
}

/// The `Refusal` for the message of an engine call that refuses its input.
pub fn refused(message: impl ToString) -> PyErr {
    Refusal::new_err(message.to_string())
}

/// The `Fault` for the message of an engine call that fails inside the
/// engine.
pub fn faulted(message: impl ToString) -> PyErr {
    Fault::new_err(message.to_string())
}

/// The value of `outcome`, or the `Fault` that its fault raises.
pub(crate) fn settled<T>(outcome: Outcome<T>) -> PyResult<T> {
    outcome.map_err(fault)
}
