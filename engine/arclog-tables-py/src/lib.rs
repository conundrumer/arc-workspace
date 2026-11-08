//! The Python bindings of the tables export: the class `CaseTables`, which
//! gives a case program's tables as flat columns
//! ([`arclog_tables::columns`] gives the layout and the codes), the functions
//! `corpus_tables`, `stream_tables`, `step_tables`, `successor_tables` and `base_tables` that build them,
//! `output_columns`, which gives the columns an `OUT` form selects, and the
//! orientation constants their cells encode. [`register`] adds their names to
//! the module that `arclog-py` builds.
//!
//! The settings, the replay progress and the walk over a corpus are those of
//! `arclog-bindings`, which depends on nothing here.

mod case_tables;
mod study_pair;
mod study_filters;
mod study_render;
mod study_features;
mod corpus_tables;
mod orientation;
mod record;
mod shapes;
mod spill;
mod step_tables;
mod stream_tables;

use arclog_bindings::Names;
use pyo3::prelude::*;

/// The names of the features in the TableVector of `step_tables`, in the order of the vector.
#[pyfunction]
fn table_feature_names() -> Vec<&'static str> {
    arclog_features::names().collect()
}

/// The hash of the feature names in their order, as 32 hexadecimal digits.
#[pyfunction]
fn table_features_version() -> String {
    arclog_features::version()
}

/// Registers the class and the functions of this crate.
pub fn register(names: &Names<'_, '_>) -> PyResult<()> {
    let module = names.module();
    study_pair::register(names)?;
    study_filters::register(names)?;
    study_render::register(names)?;
    study_features::register(names)?;
    names.class::<case_tables::PyCaseTables>()?;
    names.class::<shapes::PyTableShapes>()?;
    names.class::<shapes::PyShapeVector>()?;
    names.class::<shapes::PySelection>()?;
    names.function(wrap_pyfunction!(shapes::shape_text, module)?)?;
    names.function(wrap_pyfunction!(shapes::shape_texts, module)?)?;
    names.function(wrap_pyfunction!(shapes::shape_hash, module)?)?;
    names.function(wrap_pyfunction!(shapes::table_shape_counts, module)?)?;
    names.function(wrap_pyfunction!(corpus_tables::corpus_tables, module)?)?;
    names.function(wrap_pyfunction!(stream_tables::stream_tables, module)?)?;
    names.function(wrap_pyfunction!(step_tables::step_tables, module)?)?;
    names.function(wrap_pyfunction!(step_tables::successor_tables, module)?)?;
    names.function(wrap_pyfunction!(step_tables::atom_tables, module)?)?;
    names.function(wrap_pyfunction!(step_tables::atom_verdicts, module)?)?;
    names.function(wrap_pyfunction!(step_tables::add_atom_verdicts, module)?)?;
    names.function(wrap_pyfunction!(step_tables::base_tables, module)?)?;
    names.function(wrap_pyfunction!(step_tables::output_columns, module)?)?;
    names.function(wrap_pyfunction!(step_tables::step_tables_split, module)?)?;
    names.function(wrap_pyfunction!(table_feature_names, module)?)?;
    names.function(wrap_pyfunction!(table_features_version, module)?)?;
    names.function(wrap_pyfunction!(orientation::orientation_names, module)?)?;
    names.function(wrap_pyfunction!(orientation::orientation_types, module)?)
}
