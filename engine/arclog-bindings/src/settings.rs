//! The decode settings, as Python gives them.

use arclog::stream::{DecodeSettings, VocabularyCaps};
use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;

/// What a decode reads: the settings of `docs/engine/synthesis.md#decode-settings`.
/// A setting left out takes the engine's default. No setting is a clock: the
/// search of the mutation draw stops at `mutation_node_cap`, and every other
/// request at a work cap, `request_work_cap` among them, or at a byte budget,
/// `request_byte_cap`, `assignment_byte_cap` and `candidate_byte_cap`.
/// `binding_cap`, `row_cap`, `model_cap`, `node_cap` and `assignment_cap` are
/// the fields of `arclog::eval::Caps`, each at its `Caps::CORPUS` value by default.
/// `spill_resident_bytes` moves rows to disk and changes no result.
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
    mutation_node_cap: u64,
    projection_cap: u64,
    table_work_cap: u64,
    request_work_cap: u64,
    effort_cap: u64,
    prefix_content_cap: u64,
    request_byte_cap: u64,
    assignment_byte_cap: u64,
    candidate_byte_cap: u64,
    spill_resident_bytes: u64,
    binding_cap: u64,
    row_cap: u64,
    model_cap: u64,
    node_cap: u64,
    assignment_cap: u64,
    rule_tests: bool,
}

impl PyDecodeSettings {
    pub(crate) fn of(settings: &DecodeSettings) -> PyDecodeSettings {
        PyDecodeSettings {
            relations: settings.vocabulary.relations,
            columns: settings.vocabulary.columns,
            labels: settings.vocabulary.labels,
            mutation_node_cap: settings.mutation_node_cap,
            projection_cap: settings.projection_cap,
            table_work_cap: settings.table_work_cap,
            request_work_cap: settings.request_work_cap,
            effort_cap: settings.effort_cap,
            prefix_content_cap: settings.prefix_content_cap,
            request_byte_cap: settings.request_byte_cap,
            assignment_byte_cap: settings.assignment_byte_cap,
            candidate_byte_cap: settings.candidate_byte_cap,
            spill_resident_bytes: settings.spill_resident_bytes,
            binding_cap: settings.caps.bindings,
            row_cap: settings.caps.rows,
            model_cap: settings.caps.models,
            node_cap: settings.caps.nodes,
            assignment_cap: settings.caps.assignments,
            rule_tests: settings.rule_tests,
        }
    }

    /// The engine settings these give.
    pub fn engine(&self) -> PyResult<DecodeSettings> {
        Ok(DecodeSettings {
            vocabulary: VocabularyCaps { relations: self.relations, columns: self.columns, labels: self.labels },
            mutation_node_cap: self.mutation_node_cap,
            projection_cap: self.projection_cap,
            table_work_cap: self.table_work_cap,
            request_work_cap: self.request_work_cap,
            effort_cap: self.effort_cap,
            prefix_content_cap: self.prefix_content_cap,
            request_byte_cap: self.request_byte_cap,
            assignment_byte_cap: self.assignment_byte_cap,
            candidate_byte_cap: self.candidate_byte_cap,
            spill_resident_bytes: self.spill_resident_bytes,
            caps: arclog::eval::Caps { bindings: self.binding_cap, rows: self.row_cap, models: self.model_cap, nodes: self.node_cap, assignments: self.assignment_cap },
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
    /// limit. Its verdict must not depend on competing machine load.
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
    #[pyo3(signature = (*, proposer_tokens=None, type_domain_proposers=None, relations=None, columns=None, labels=None, mutation_node_cap=None, projection_cap=None, table_work_cap=None, request_work_cap=None, effort_cap=None, prefix_content_cap=None, request_byte_cap=None, assignment_byte_cap=None, candidate_byte_cap=None, spill_resident_bytes=None, binding_cap=None, row_cap=None, model_cap=None, node_cap=None, assignment_cap=None, rule_tests=None, static_pruning=None, grids_at_model_cap=None))]
    fn new(
        proposer_tokens: Option<bool>,
        type_domain_proposers: Option<bool>,
        relations: Option<u32>,
        columns: Option<u32>,
        labels: Option<u32>,
        mutation_node_cap: Option<u64>,
        projection_cap: Option<u64>,
        table_work_cap: Option<u64>,
        request_work_cap: Option<u64>,
        effort_cap: Option<u64>,
        prefix_content_cap: Option<u64>,
        request_byte_cap: Option<u64>,
        assignment_byte_cap: Option<u64>,
        candidate_byte_cap: Option<u64>,
        spill_resident_bytes: Option<u64>,
        binding_cap: Option<u64>,
        row_cap: Option<u64>,
        model_cap: Option<u64>,
        node_cap: Option<u64>,
        assignment_cap: Option<u64>,
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
            mutation_node_cap: mutation_node_cap.unwrap_or(base.mutation_node_cap),
            projection_cap: projection_cap.unwrap_or(base.projection_cap),
            table_work_cap: table_work_cap.unwrap_or(base.table_work_cap),
            request_work_cap: request_work_cap.unwrap_or(base.request_work_cap),
            effort_cap: effort_cap.unwrap_or(base.effort_cap),
            prefix_content_cap: prefix_content_cap.unwrap_or(base.prefix_content_cap),
            request_byte_cap: request_byte_cap.unwrap_or(base.request_byte_cap),
            assignment_byte_cap: assignment_byte_cap.unwrap_or(base.assignment_byte_cap),
            candidate_byte_cap: candidate_byte_cap.unwrap_or(base.candidate_byte_cap),
            spill_resident_bytes: spill_resident_bytes.unwrap_or(base.spill_resident_bytes),
            binding_cap: binding_cap.unwrap_or(base.binding_cap),
            row_cap: row_cap.unwrap_or(base.row_cap),
            model_cap: model_cap.unwrap_or(base.model_cap),
            node_cap: node_cap.unwrap_or(base.node_cap),
            assignment_cap: assignment_cap.unwrap_or(base.assignment_cap),
            rule_tests: rule_tests.unwrap_or(base.rule_tests),
        };
        settings.engine()?;
        Ok(settings)
    }
}
