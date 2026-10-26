//! The orientation constants, as the cells of `CaseTables.values` encode them.

use arclog::registry::Registry;
use pyo3::prelude::*;

/// The name of each orientation constant by its encoding, which is the
/// cell of an orientation value in `CaseTables.values`, in the order of the
/// encodings.
#[pyfunction]
pub(crate) fn orientation_names() -> Vec<(i32, String)> {
    arclog_tables::columns::orientation_names(Registry::get())
}

/// The cells of the constants that each orientation type without a
/// parameter admits, by the type's name.
#[pyfunction]
pub(crate) fn orientation_types() -> Vec<(String, Vec<i32>)> {
    arclog_tables::columns::orientation_types(Registry::get())
}
