//! The exceptions of the module and the conversions of the engine's faults
//! to them.

use arclog::eval::{Outcome, ReachedBound, RunFault};
use arclog::trace::Stop;
use pyo3::create_exception;
use pyo3::exceptions::{PyException, PyRuntimeError, PyValueError};
use pyo3::prelude::*;

use crate::results::PyStopKind;

create_exception!(arclog, Refusal, PyValueError, "A decode refuses a token outside its mask.");
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

/// The value of `outcome`, or the `Fault` that its fault raises.
pub(crate) fn settled<T>(outcome: Outcome<T>) -> PyResult<T> {
    outcome.map_err(fault)
}
