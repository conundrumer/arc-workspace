//! The Python bindings of the tables export: the class `CaseTables`, which
//! gives a case program's tables as flat columns
//! ([`arclog_tables::columns`] gives the layout and the codes), the functions
//! `corpus_tables` and `stream_tables` that build them, and the orientation
//! constants their cells encode. [`register`] adds their names to the module
//! that `arclog-py` builds.
//!
//! The settings, the replay progress and the walk over a corpus are those of
//! `arclog-bindings`, which depends on nothing here.

mod case_tables;
mod corpus_tables;
mod orientation;
mod record;
mod stream_tables;

use arclog_bindings::Names;
use pyo3::prelude::*;

/// Registers the class and the functions of this crate.
pub fn register(names: &Names<'_, '_>) -> PyResult<()> {
    let module = names.module();
    names.class::<case_tables::PyCaseTables>()?;
    names.function(wrap_pyfunction!(corpus_tables::corpus_tables, module)?)?;
    names.function(wrap_pyfunction!(stream_tables::stream_tables, module)?)?;
    names.function(wrap_pyfunction!(orientation::orientation_names, module)?)?;
    names.function(wrap_pyfunction!(orientation::orientation_types, module)?)
}
