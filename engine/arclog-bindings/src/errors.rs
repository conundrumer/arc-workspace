//! The exceptions of the module and the conversions of the engine's faults
//! to them.

use arclog::diagnostic::Location;
use arclog::eval::{Outcome, ReachedBound, RunFault};
use arclog::study::StudyError;
use arclog::trace::Stop;
use pyo3::create_exception;
use pyo3::exceptions::{PyException, PyRuntimeError, PyValueError};
use pyo3::prelude::*;

use crate::results::PyStopKind;

create_exception!(arclog, Refusal, PyException, "The engine refuses its input: a decode refuses a token outside its mask, or `CheckRefused` for a program that its checks refuse. It is no `ValueError`: a `ValueError` from the engine is a bug of the caller.");
create_exception!(
    arclog,
    CheckRefused,
    Refusal,
    "The engine's checks refuse a program. Attributes: `check`, the name of the first check that refused it (`Picks`, `Types`, `Grammar`, ...); `at`, the path of the node it refused, as the list of the indexes from the top-level form, or None where the refusal stands at a place of the program's text; `line` and `column`, from 1, of that place, or None where it stands at a path. The message holds the text of all of the refusals."
);
create_exception!(arclog, Fault, PyRuntimeError, "A run of the engine faults.");
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

/// The `Refusal` for the message of an engine call that refuses its input.
pub fn refused(message: String) -> PyErr {
    Refusal::new_err(message)
}

/// The `Fault` for the message of an engine call that fails inside the
/// engine.
pub fn faulted(message: String) -> PyErr {
    Fault::new_err(message)
}

/// The value of `outcome`, or the `Fault` that its fault raises.
pub(crate) fn settled<T>(outcome: Outcome<T>) -> PyResult<T> {
    outcome.map_err(fault)
}
