//! The names a Python module registers, each once.

use pyo3::exceptions::PyImportError;
use pyo3::prelude::*;
use pyo3::pyclass::PyClass;
use pyo3::types::PyCFunction;

/// A module that crates register their names in. A name that is already
/// registered, by this crate or another, is an `ImportError` that names it, so
/// that no name of one crate stands in place of another's.
pub struct Names<'a, 'py> {
    module: &'a Bound<'py, PyModule>,
}

impl<'a, 'py> Names<'a, 'py> {
    pub fn new(module: &'a Bound<'py, PyModule>) -> Self {
        Names { module }
    }

    /// The module, for `wrap_pyfunction!`.
    pub fn module(&self) -> &'a Bound<'py, PyModule> {
        self.module
    }

    /// Registers the class `T` by its Python name.
    pub fn class<T: PyClass>(&self) -> PyResult<()> {
        self.claim(T::NAME)?;
        self.module.add_class::<T>()
    }

    /// Registers `function` by its Python name.
    pub fn function(&self, function: Bound<'py, PyCFunction>) -> PyResult<()> {
        self.claim(&function.getattr("__name__")?.extract::<String>()?)?;
        self.module.add_function(function)
    }

    /// Registers `value` as `name`.
    pub fn value(&self, name: &str, value: Bound<'py, PyAny>) -> PyResult<()> {
        self.claim(name)?;
        self.module.add(name, value)
    }

    fn claim(&self, name: &str) -> PyResult<()> {
        if self.module.hasattr(name)? {
            return Err(PyImportError::new_err(format!("the name `{name}` is registered twice")));
        }
        Ok(())
    }
}
