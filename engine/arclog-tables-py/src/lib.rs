//! The Python bindings of the tables export: the class `CaseTables`, which
//! gives a case program's tables as flat columns
//! ([`arclog_tables::columns`] gives the layout and the codes), the functions
//! `corpus_tables`, `stream_tables` and `step_tables` that build them,
//! `output_columns`, which gives the columns an `OUT` form selects, and the
//! orientation constants their cells encode. [`register`] adds their names to
//! the module that `arclog-py` builds.
//!
//! The settings, the replay progress and the walk over a corpus are those of
//! `arclog-bindings`, which depends on nothing here.

mod case_tables;
mod study_pair;
mod corpus_tables;
mod orientation;
mod record;
mod step_tables;
mod stream_tables;

use arclog_bindings::Names;
use pyo3::prelude::*;

/// Registers the class and the functions of this crate.
pub fn register(names: &Names<'_, '_>) -> PyResult<()> {
    let module = names.module();
    study_pair::register(names)?;
    names.class::<case_tables::PyCaseTables>()?;
    names.function(wrap_pyfunction!(corpus_tables::corpus_tables, module)?)?;
    names.function(wrap_pyfunction!(stream_tables::stream_tables, module)?)?;
    names.function(wrap_pyfunction!(step_tables::step_tables, module)?)?;
    names.function(wrap_pyfunction!(step_tables::output_columns, module)?)?;
    names.function(wrap_pyfunction!(orientation::orientation_names, module)?)?;
    names.function(wrap_pyfunction!(orientation::orientation_types, module)?)
}
