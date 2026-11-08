//! The decode settings, as Python gives them.

use std::time::Duration;

use arclog::stream::{DecodeSettings, VocabularyCaps};
use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;

/// What a decode reads: the settings of `docs/engine/synthesis.md#decode-settings`.
/// A setting left out takes the engine's default. `deadline_seconds` is read
/// by the search of the mutation draw alone; every other request stops at a
/// work cap, `request_work_cap` among them.
///
/// `proposer_tokens`, `type_domain_proposers`, `static_pruning` and
/// `grids_at_model_cap` are no settings: each decode has them on
/// (`docs/engine/synthesis.md#switches`). They stay as keyword arguments that
/// take `True` or `None`, and as attributes that read `True`, so a record of
/// settings that names them still reads. `False` raises `ValueError`.
#[pyclass(name = "DecodeSettings", frozen, get_all, module = "arclog")]
#[derive(Clone, Copy)]
pub struct PyDecodeSettings {
    relations: u32,
    columns: u32,
    labels: u32,
    deadline_seconds: Option<f64>,
    projection_cap: u64,
    table_work_cap: u64,
    request_work_cap: u64,
    binding_cap: u64,
    row_cap: u64,
    rule_tests: bool,
}

impl PyDecodeSettings {
    pub(crate) fn of(settings: &DecodeSettings) -> PyDecodeSettings {
        PyDecodeSettings {
            relations: settings.vocabulary.relations,
            columns: settings.vocabulary.columns,
            labels: settings.vocabulary.labels,
            deadline_seconds: settings.deadline.map(|deadline| deadline.as_secs_f64()),
            projection_cap: settings.projection_cap,
            table_work_cap: settings.table_work_cap,
            request_work_cap: settings.request_work_cap,
            binding_cap: settings.caps.bindings,
            row_cap: settings.caps.rows,
            rule_tests: settings.rule_tests,
        }
    }

    /// The engine settings these give, or `ValueError` for a deadline that is no duration.
    pub fn engine(&self) -> PyResult<DecodeSettings> {
        let deadline = self.deadline_seconds.map(|seconds| Duration::try_from_secs_f64(seconds).map_err(|error| PyValueError::new_err(format!("deadline_seconds: {error}")))).transpose()?;
        Ok(DecodeSettings {
            vocabulary: VocabularyCaps { relations: self.relations, columns: self.columns, labels: self.labels },
            deadline,
            projection_cap: self.projection_cap,
            table_work_cap: self.table_work_cap,
            request_work_cap: self.request_work_cap,
            caps: arclog::eval::Caps {bindings:self.binding_cap,rows:self.row_cap,..arclog::eval::Caps::CORPUS},
            rule_tests: self.rule_tests,
            ..DecodeSettings::default()
        })
    }
}

/// `Ok` where a caller gave a removed setting as `True` or left it out, and
/// `ValueError` where it gave `False`.
fn only_on(name: &str, given: Option<bool>) -> PyResult<()> {
    match given {
        Some(false) => Err(PyValueError::new_err(format!("{name}: a decode always has it on, so `False` is refused"))),
        Some(true) | None => Ok(()),
    }
}

#[pymethods]
impl PyDecodeSettings {
    /// Corpus verification has finite supplied programs and no wall-clock
    /// search deadline. Its verdict must not depend on competing machine load.
    #[staticmethod]
    fn corpus() -> Self {
        Self::of(&DecodeSettings::default())
    }

    #[getter]
    fn proposer_tokens(&self) -> bool {
        true
    }

    #[getter]
    fn type_domain_proposers(&self) -> bool {
        true
    }

    #[getter]
    fn static_pruning(&self) -> bool {
        true
    }

    #[getter]
    fn grids_at_model_cap(&self) -> bool {
        true
    }

    #[new]
    #[pyo3(signature = (*, proposer_tokens=None, type_domain_proposers=None, relations=None, columns=None, labels=None, deadline_seconds=None, projection_cap=None, table_work_cap=None, request_work_cap=None, binding_cap=None, row_cap=None, rule_tests=None, static_pruning=None, grids_at_model_cap=None))]
    fn new(
        proposer_tokens: Option<bool>,
        type_domain_proposers: Option<bool>,
        relations: Option<u32>,
        columns: Option<u32>,
        labels: Option<u32>,
        deadline_seconds: Option<f64>,
        projection_cap: Option<u64>,
        table_work_cap: Option<u64>,
        request_work_cap: Option<u64>,
        binding_cap: Option<u64>,
        row_cap: Option<u64>,
        rule_tests: Option<bool>,
        static_pruning: Option<bool>,
        grids_at_model_cap: Option<bool>,
    ) -> PyResult<PyDecodeSettings> {
        only_on("proposer_tokens", proposer_tokens)?;
        only_on("type_domain_proposers", type_domain_proposers)?;
        only_on("static_pruning", static_pruning)?;
        only_on("grids_at_model_cap", grids_at_model_cap)?;
        let base = PyDecodeSettings::of(&DecodeSettings::synthesis());
        let settings = PyDecodeSettings {
            relations: relations.unwrap_or(base.relations),
            columns: columns.unwrap_or(base.columns),
            labels: labels.unwrap_or(base.labels),
            deadline_seconds: deadline_seconds.or(base.deadline_seconds),
            projection_cap: projection_cap.unwrap_or(base.projection_cap),
            table_work_cap: table_work_cap.unwrap_or(base.table_work_cap),
            request_work_cap: request_work_cap.unwrap_or(base.request_work_cap),
            binding_cap: binding_cap.unwrap_or(base.binding_cap),
            row_cap: row_cap.unwrap_or(base.row_cap),
            rule_tests: rule_tests.unwrap_or(base.rule_tests),
        };
        settings.engine()?;
        Ok(settings)
    }
}
