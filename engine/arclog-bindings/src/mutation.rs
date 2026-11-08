//! Opaque study mutation values. Python never rewrites an AST or its tokens.
use arclog::mutation::{MutationPoint, MutationSpec, ValidMutant};
use arclog::registry::Registry;
use arclog::stream::DecodeSettings;
use pyo3::prelude::*;

use crate::errors::{faulted, refused};
use crate::study::PyStudyProgram;

#[pyclass(name = "MutationPoint", frozen, module = "arclog")]
#[derive(Clone)]
pub struct PyMutationPoint {
    pub inner: MutationPoint,
}

#[pymethods]
impl PyMutationPoint {
    #[getter]
    fn clause_path(&self) -> Vec<u32> {
        self.inner.clause.0.iter().map(|s| s.0).collect()
    }
    #[getter]
    fn body_path(&self) -> Vec<u32> {
        self.inner.body.0.iter().map(|s| s.0).collect()
    }
    #[getter]
    fn atom_paths(&self) -> Vec<Vec<u32>> {
        self.inner
            .atoms
            .iter()
            .map(|p| p.0.iter().map(|s| s.0).collect())
            .collect()
    }
    #[getter]
    fn kind(&self) -> &str {
        &self.inner.kind
    }
}

#[pyclass(name = "MutationSpec", frozen, module = "arclog")]
#[derive(Clone)]
pub struct PyMutationSpec {
    pub inner: MutationSpec,
}

#[pymethods]
impl PyMutationSpec {
    #[getter]
    fn identity_json(&self) -> String {
        self.inner.identity().to_string()
    }
    #[getter]
    fn k(&self) -> usize {
        self.inner.k()
    }
}

#[pyclass(name = "ValidMutant", frozen, module = "arclog")]
#[derive(Clone)]
pub struct PyValidMutant {
    pub inner: ValidMutant,
    pub settings: DecodeSettings,
}

#[pymethods]
impl PyValidMutant {
    #[getter]
    fn identity_json(&self) -> String {
        self.inner.identity().to_string()
    }
    #[getter]
    fn k(&self) -> usize {
        self.inner.k()
    }
    /// Static sample-time rejection, also used by the shared historical reader.
    #[pyo3(signature = (*, survey=false))]
    fn static_prune_json(&self, py: Python<'_>, survey: bool) -> PyResult<String> {
        py.detach(||self.inner.static_prune_json(Registry::get(),survey))
            .map(|v|v.to_string()).map_err(refused)
    }

    /// Includes the original-to-mutant AST path correspondence.
    fn render_json(&self, py: Python<'_>) -> PyResult<String> {
        py.detach(|| {
            let mut value=self.inner.program().render_json(Registry::get())?;
            value["mutation_identity"]=self.inner.identity();
            value["source_path_correspondence"]=self.inner.source_paths();
            Ok(value.to_string())
        }).map_err(|error: String| faulted(error))
    }

    fn sexp(&self) -> String {
        self.inner.program().sexp(Registry::get())
    }
    fn program_form(&self) -> String {
        self.sexp()
    }
    fn decode_stream(&self) -> PyResult<(Vec<u32>, Vec<u8>, Vec<Vec<u32>>)> {
        let stream = self
            .inner
            .decode_stream(Registry::get(), &self.settings)
            .map_err(faulted)?;
        Ok((
            stream.ids,
            stream.model,
            stream
                .paths
                .iter()
                .map(|p| p.0.iter().map(|s| s.0).collect())
                .collect(),
        ))
    }
    fn as_program(&self) -> PyStudyProgram {
        PyStudyProgram {
            program: self.inner.program().clone(),
            settings: self.settings,
        }
    }
    fn audit_json(&self) -> PyResult<String> {
        self.inner
            .audit()
            .map(|v| v.to_string())
            .map_err(faulted)
    }
}
