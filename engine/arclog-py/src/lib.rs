//! The Python extension module `arclog`, built by maturin as an abi3 wheel
//! from the bindings of the streams export (`arclog-bindings`) and of the
//! tables export (`arclog-tables-py`). The init calls the `register` of each
//! and adds `streams_digest`, and holds no other code. A name that both
//! register ends the init with an `ImportError` that names it, so that no
//! tables binding stands in place of a streams binding.

use arclog_bindings::Names;
use pyo3::prelude::*;

/// The sha256, fixed when the package is built, over every input of the
/// compile of the crates that the streams bindings and this init are built
/// from, and over no file of the tables crates (`build.rs` gives the inputs).
/// Two builds with an equal digest run the same streams code.
#[pyfunction]
fn streams_digest() -> &'static str {
    env!("STREAMS_DIGEST")
}

#[pymodule]
#[pyo3(name = "arclog")]
fn arclog_module(module: &Bound<'_, PyModule>) -> PyResult<()> {
    let names = Names::new(module);
    arclog_bindings::register(&names)?;
    arclog_tables_py::register(&names)?;
    names.function(wrap_pyfunction!(streams_digest, module)?)
}
