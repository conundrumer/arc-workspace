//! The values that a decode's requests give Python: the bound a step
//! reached, the consistency of a relation, and the rows and projections of a
//! body at each assignment.

use arclog::decode::{Assigned, Consistency};
use arclog::eval::RelationValue;
use arclog::task::Grid;
use arclog::trace::Stop;
use pyo3::prelude::*;
use pyo3::types::PyList;

/// The bound a step reached.
#[pyclass(name = "StopKind", eq, eq_int, frozen, module = "arclog")]
#[derive(Clone, Copy, PartialEq, Eq)]
pub(crate) enum PyStopKind {
    Bindings,
    Rows,
    Models,
    Nodes,
    Assignments,
    TableWork,
    Margin,
    RequestWork,
    RequestBytes,
    AssignmentBytes,
    Cancelled,
    NoValues,
    Effort,
}

impl From<Stop> for PyStopKind {
    fn from(stop: Stop) -> PyStopKind {
        match stop {
            Stop::Bindings => PyStopKind::Bindings,
            Stop::Rows => PyStopKind::Rows,
            Stop::Models => PyStopKind::Models,
            Stop::Nodes => PyStopKind::Nodes,
            Stop::Assignments => PyStopKind::Assignments,
            Stop::TableWork => PyStopKind::TableWork,
            Stop::Margin => PyStopKind::Margin,
            Stop::RequestWork => PyStopKind::RequestWork,
            Stop::RequestBytes => PyStopKind::RequestBytes,
            Stop::AssignmentBytes => PyStopKind::AssignmentBytes,
            Stop::Cancelled => PyStopKind::Cancelled,
            Stop::NoValues => PyStopKind::NoValues,
            Stop::Effort => PyStopKind::Effort,
        }
    }
}

/// What the consistency test of an `OUT` form's relation, or of a `RULE` clause's, found.
#[pyclass(name = "ConsistencyKind", eq, eq_int, frozen, module = "arclog")]
#[derive(Clone, Copy, PartialEq, Eq)]
pub enum PyConsistencyKind {
    Consistent,
    NotConsistent,
    SeveralValues,
    Fault,
    Stopped,
}

/// The consistency of the relation of an `OUT` form, or of a `RULE` clause under the rule tests, with the train pairs.
#[pyclass(name = "Consistency", frozen, get_all, module = "arclog")]
pub(crate) struct PyConsistency {
    kind: PyConsistencyKind,
    /// The consistent joint assignments, for `Consistent`.
    assignments: Option<usize>,
    /// The first bound reached, including beside a consistent assignment.
    stop: Option<PyStopKind>,
    /// The fault, for `Fault`.
    message: Option<String>,
    /// The output sets of the test that ended at the model cap with the grids
    /// found so far.
    capped_sets: u64,
}

impl PyConsistency {
    pub(crate) fn of(consistency: &Consistency, capped_sets: u64) -> PyConsistency {
        let (assignments, stop, message) = match consistency {
            Consistency::Consistent { assignments, stop } => (Some(assignments.len()), stop.as_ref().map(|s|Stop::from(s.bound).into()), None),
            Consistency::Fault(fault) => (None, None, Some(fault.message.to_string())),
            Consistency::Stopped(stop) => (None, Some(Stop::from(stop.bound).into()), None),
            Consistency::NotConsistent | Consistency::SeveralValues { .. } => (None, None, None),
        };
        PyConsistency { kind: PyConsistencyKind::of(consistency), assignments, stop, message, capped_sets }
    }
}

/// What a value of a body holds.
#[pyclass(name = "ValueKind", eq, eq_int, frozen, module = "arclog")]
#[derive(Clone, Copy, PartialEq, Eq)]
pub(crate) enum PyValueKind {
    Rows,
    Undefined,
    Stopped,
}

/// The rows of a sub-body at one assignment, as their arity and their count: the
/// bindings expose no term of a row.
#[pyclass(name = "RowsView", frozen, get_all, module = "arclog")]
pub(crate) struct PyRowsView {
    kind: PyValueKind,
    arity: Option<u16>,
    count: Option<u64>,
    stop: Option<PyStopKind>,
}

/// What a request gives at each joint assignment of the `DET`s the body reads.
/// `values` holds a [`PyRowsView`] for `rows`, and a count or `None` for `counts`.
#[pyclass(name = "Assigned", frozen, get_all, module = "arclog")]
pub(crate) struct PyAssigned {
    values: Py<PyList>,
    /// The bound that ended the walk before its last assignment.
    stop: Option<PyStopKind>,
}

pub(crate) fn rows_view(value: &arclog::eval::BodyValue) -> PyRowsView {
    match &value.0 {
        RelationValue::Rows(relation) => PyRowsView { kind: PyValueKind::Rows, arity: Some(relation.arity()), count: Some(relation.len()), stop: None },
        RelationValue::Undefined => PyRowsView { kind: PyValueKind::Undefined, arity: None, count: None, stop: None },
        RelationValue::Stopped(stop) => PyRowsView { kind: PyValueKind::Stopped, arity: None, count: None, stop: Some(Stop::from(stop.bound).into()) },
    }
}

/// One projection of a sub-body: the positions of its columns in the body, and the
/// count of its rows on each example, in the shape of `counts`.
#[pyclass(name = "Projection", frozen, get_all, module = "arclog")]
pub(crate) struct PyProjection {
    pub(crate) columns: Vec<u16>,
    pub(crate) counts: Vec<Py<PyAssigned>>,
}

/// The projections of a sub-body, or the bound that stopped them.
#[pyclass(name = "Projections", frozen, get_all, module = "arclog")]
pub(crate) struct PyProjections {
    pub(crate) projections: Vec<Py<PyProjection>>,
    pub(crate) stop: Option<PyStopKind>,
}

pub(crate) fn grid_rows(grid: &Grid) -> Vec<Vec<u32>> {
    grid.rows().iter().map(|row| row.iter().map(|color| u32::from(color.digit())).collect()).collect()
}

impl PyConsistencyKind {
    /// The kind of `consistency`.
    pub fn of(consistency: &Consistency) -> PyConsistencyKind {
        match consistency {
            Consistency::Consistent { .. } => PyConsistencyKind::Consistent,
            Consistency::NotConsistent => PyConsistencyKind::NotConsistent,
            Consistency::SeveralValues { .. } => PyConsistencyKind::SeveralValues,
            Consistency::Fault(_) => PyConsistencyKind::Fault,
            Consistency::Stopped(_) => PyConsistencyKind::Stopped,
        }
    }

    /// The kind's name, as `corpus_tables` and `stream_tables` print it.
    pub fn name(self) -> &'static str {
        match self {
            PyConsistencyKind::Consistent => "Consistent",
            PyConsistencyKind::NotConsistent => "NotConsistent",
            PyConsistencyKind::SeveralValues => "SeveralValues",
            PyConsistencyKind::Fault => "Fault",
            PyConsistencyKind::Stopped => "Stopped",
        }
    }
}

/// The [`PyAssigned`] of `found`, with the `Py<PyAny>` that `view` gives for
/// each value.
pub(crate) fn assigned<T>(py: Python<'_>, found: Assigned<T>, mut view: impl FnMut(T) -> PyResult<Py<PyAny>>) -> PyResult<PyAssigned> {
    let values = PyList::empty(py);
    for (_, value) in found.at {
        values.append(view(value)?)?;
    }
    let stop: Option<PyStopKind> = found.stop.map(|stop| Stop::from(stop.bound).into());
    Ok(PyAssigned { values: values.unbind(), stop })
}
