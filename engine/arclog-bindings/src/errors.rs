//! The exceptions of the module and the conversions of the engine's faults
//! to them.

use arclog::eval::{Outcome, RunFault};
use pyo3::create_exception;
use pyo3::exceptions::{PyRuntimeError, PyValueError};
use pyo3::prelude::*;

create_exception!(arclog, Refusal, PyValueError, "A decode refuses a token outside its mask.");
create_exception!(arclog, Fault, PyRuntimeError, "A run of the engine faults.");

fn fault(fault: RunFault) -> PyErr {
    Fault::new_err(fault.message.to_string())
}

/// The value of `outcome`, or the `Fault` that its fault raises.
pub(crate) fn settled<T>(outcome: Outcome<T>) -> PyResult<T> {
    outcome.map_err(fault)
}
