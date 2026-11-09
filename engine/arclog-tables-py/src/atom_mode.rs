//! `atom_mode_holds`: whether an atom of a lib relation may stand where some of
//! its sites are bound, by the engine's safety check.

use arclog::check::CheckCache;
use arclog::registry::{LibName, Registry};
use arclog::stream::DecodeSettings;
use arclog::study::{StudyError, StudyProgram};
use arclog_bindings::study_error;
use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;

/// The names of the columns of `columns`, an iterable of strings, in order.
fn column_names(columns: &Bound<'_, PyAny>) -> PyResult<Vec<String>> {
    let mut names = columns.try_iter()?.map(|name| name?.extract::<String>()).collect::<PyResult<Vec<_>>>()?;
    names.sort();
    Ok(names)
}

/// Whether an atom of the lib relation `rel` may stand where its sites at the
/// columns `bound`, an iterable of column names, are bound and those at the
/// columns `unbound` are not, by the engine's safety check, which alone knows
/// a relation macro's modes. It is the check whose refusal says `no mode of the
/// atom`: the answer is the verdict of `StudyProgram.from_sexp` (with the
/// default `DecodeSettings`) on a program of one rule whose atom reads `rel`,
/// with `(= *B<j> 0)` binding the label at each column of `bound` before it and
/// a label that the atom makes at each column of `unbound`. The answer is `False`
/// where that program is refused for having no mode of the atom, and `True`
/// where it is read or refused for another reason, as a relation with no mode
/// (a fact relation, a proposer, a component) gives.
///
/// `ValueError` is raised for a relation that is none of a name of the lib, a
/// fact relation (`input`, `ex_input`, `ex_output`) and a declared relation
/// (a name that starts with `&`). `Fault` is raised where the engine faults.
#[pyfunction]
pub(crate) fn atom_mode_holds(py: Python<'_>, rel: &str, bound: &Bound<'_, PyAny>, unbound: &Bound<'_, PyAny>) -> PyResult<bool> {
    let (bound, unbound) = (column_names(bound)?, column_names(unbound)?);
    let known = rel.starts_with('&') || matches!(rel, "input" | "ex_input" | "ex_output") || Registry::get().entry(&LibName(rel.into())).is_some();
    if !known {
        return Err(PyValueError::new_err(format!("the lib has no relation named {rel:?}")));
    }
    let bounds = bound.iter().enumerate().map(|(j, _)| format!("(= *B{j} 0)")).collect::<Vec<_>>().join(" ");
    let sites = bound
        .iter()
        .enumerate()
        .map(|(j, column)| format!("(:{column} B{j})"))
        .chain(unbound.iter().enumerate().map(|(j, column)| format!("(:{column} *U{j})")))
        .collect::<Vec<_>>()
        .join(" ");
    let text = format!("(RULE &x {bounds} ({rel} {sites}))\n(RULE &y (input (:P *P) (:Col *Col)))\n(OUT (&y ^P ^Col))");
    let settings = DecodeSettings::synthesis();
    let verdict = py.detach(|| -> Result<(), StudyError> {
        let program = StudyProgram::read_sexp_cached(&text, Registry::get(), &mut CheckCache::default())?;
        program.try_decode_stream(Registry::get(), &settings).map(|_| ())
    });
    match verdict {
        Ok(()) => Ok(true),
        Err(error @ StudyError::Fault(_)) => Err(study_error(py, error)),
        Err(error) => Ok(!error.to_string().contains("no mode of the atom")),
    }
}
