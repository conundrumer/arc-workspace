//! Thin Python handles for the engine's study ASTs.

use arclog::hash::StableHash;
use arclog::program::canonical::{CanonicalOrder, SearchBudget};
use arclog::program::{Form, Node, Program};
use arclog::registry::Registry;
use arclog::resolver::{resolve, ResolvedContent, SolverScope};
use arclog::stream::DecodeSettings;
use arclog::study::StudyProgram;
use pyo3::exceptions::PyValueError;
use pyo3::exceptions::PyIndexError;
use pyo3::prelude::*;
use pyo3::types::{PyBytes, PyDict, PyTuple};

use crate::mutation::{PyMutationPoint, PyMutationSpec, PyValidMutant};
use crate::session::PySession;
use crate::settings::PyDecodeSettings;
use crate::vocabulary::PyVocabulary;

/// The finished query at `index` of `program`, counted from the end where
/// `index` is negative, with its position.
pub(crate) fn finished_query(program: &Node<Program>, index: isize) -> PyResult<(usize, &Form)> {
    let forms = &program.value().forms;
    let position = if index < 0 { index.checked_add(forms.len() as isize) } else { Some(index) };
    match position.and_then(|position| usize::try_from(position).ok()).and_then(|position| forms.get(position).map(|form| (position, form))) {
        Some(found) => Ok(found),
        None => Err(PyIndexError::new_err(format!("no finished query at index {index}: the program has {} finished queries", forms.len()))),
    }
}

/// The hash of the canonical form of `query`, with the names as written.
pub(crate) fn written_query_hash(query: &Form) -> StableHash {
    CanonicalOrder::with_form(query, &mut SearchBudget::new()).1.hash
}

/// A grammar/binder reader for this session's immutable settings. Each
/// returned AST still goes through the whole-program checks below.
#[derive(Default)]
pub(crate) struct ProgramReplay {
    reader: Option<arclog::decode::program_read::ProgramReader<'static>>,
    checks: arclog::check::CheckCache,
}

/// A checked, standalone gold program through OUT. Mutations address AST
/// clauses; streams are input/output representations only.
#[pyclass(name = "StudyProgram", frozen, module = "arclog")]
#[derive(Clone)]
pub struct PyStudyProgram {
    pub program: StudyProgram,
    pub settings: DecodeSettings,
}

type Stream = (Vec<u32>, Vec<u8>, Vec<Vec<u32>>);

impl PyStudyProgram {
    /// The resolver's content of the query at `index`, in the program of
    /// its use closure, as a decode that has finished it holds, with the
    /// query's position.
    fn query_content(&self, index: isize) -> PyResult<(ResolvedContent, usize)> {
        let (position, _) = finished_query(self.program.program(), index)?;
        let prefix = Node::new(Program { forms: self.program.program().value().forms[..=position].into() });
        let resolved = resolve(&prefix, None, &SolverScope::default(), Registry::get()).value;
        let content = resolved.query_content(position, Registry::get());
        content.map(|content| (content, position)).ok_or_else(|| PyIndexError::new_err(format!("no content for the query at index {index}")))
    }
}

#[pymethods]
impl PyStudyProgram {
    #[staticmethod]
    fn mutation_policy() -> &'static str {
        "complete-domain-unique-text-gold-names-static-prune-v9"
    }
    /// Complete-program parsing retains grammar, binding, full checks and exact
    /// stream reproduction. It performs no online completion or OUT evaluation.
    #[staticmethod]
    fn stream_reader_policy() -> &'static str {
        "complete-program-bindings-v2"
    }

    /// Read standalone case sexp, preserving source column/variable names.
    #[staticmethod]
    #[pyo3(signature = (text, settings=None, *, session=None))]
    fn from_sexp(py: Python<'_>, text: &str, settings: Option<PyDecodeSettings>, session:Option<&PySession>) -> PyResult<Self> {
        let settings = settings
            .map(|s| s.engine())
            .transpose()?
            .unwrap_or_else(||session.map_or_else(DecodeSettings::synthesis,PySession::program_settings));
        if session.is_some_and(|session|session.program_settings()!=settings) {
            return Err(PyValueError::new_err("session and sexp settings differ"));
        }
        let program = py
            .detach(||match session {
                Some(session)=> {
                    let mut cached=session.program_replay.lock().expect("a program reader outside a panic");
                    StudyProgram::from_sexp_cached(text,Registry::get(),&mut cached.checks)
                },
                None=>StudyProgram::from_sexp(text, Registry::get()),
            })
            .map_err(PyValueError::new_err)?;
        program
            .decode_stream(Registry::get(), &settings)
            .map_err(PyValueError::new_err)?;
        Ok(Self { program, settings })
    }

    /// Parse a complete stream with the engine grammar/binder and exact
    /// echoes, then check the entire AST. No prefix completion search or OUT
    /// evaluation is needed when the complete program is supplied.
    #[staticmethod]
    fn from_stream(
        py: Python<'_>,
        session: &PySession,
        ids: Vec<u32>,
        model: Vec<u8>,
    ) -> PyResult<Self> {
        let settings = session.program_settings();
        let program = py
            .detach(|| {
                let mut cached = session
                    .program_replay
                    .lock()
                    .expect("a program reader outside a panic");
                let reader = cached.reader.get_or_insert_with(|| {
                    arclog::decode::program_read::ProgramReader::new(Registry::get(), settings)
                });
                let ast = reader.read(&ids, &model)?;
                let program = StudyProgram::from_decoded_cached(ast, Registry::get(), &mut cached.checks)?;
                let written = program.decode_stream(Registry::get(), &settings)?;
                if written.ids != ids || written.model != model {
                    return Err(
                        "parsed program does not reproduce its exact input stream".to_owned()
                    );
                }
                Ok(program)
            })
            .map_err(PyValueError::new_err)?;
        Ok(Self { program, settings })
    }

    /// Proven local static-pruning conclusions at original AST paths.
    #[pyo3(signature = (*, normalize=false))]
    fn static_prune_json(&self, py: Python<'_>, normalize: bool) -> PyResult<String> {
        py.detach(|| self.program.static_prune_report_with_settings(Registry::get(), normalize, &self.settings))
            .map(|value| value.to_string()).map_err(PyValueError::new_err)
    }

    /// The actual checked normalized gold and its source-correspondence report.
    /// This grants no evaluation equivalence or historical table reuse.
    fn normalized_gold(&self, py: Python<'_>) -> PyResult<(Self, String)> {
        let (program, report) = py.detach(|| self.program.normalized_gold(Registry::get(), &self.settings))
            .map_err(PyValueError::new_err)?;
        Ok((Self { program, settings: self.settings }, report.to_string()))
    }

    /// Structured engine evidence. JSON schema/capabilities are versioned.
    #[staticmethod]
    fn decode_term_json(type_name: &str, packed: i64) -> PyResult<String> {
        arclog::study::render_terms::decode(type_name, packed, Registry::get())
            .map(|v| v.to_string())
            .map_err(PyValueError::new_err)
    }

    /// Finite native encoding domain, including a historical nominal Pose type.
    #[staticmethod]
    fn orientation_domain_json(type_name:&str)->PyResult<String> {
        arclog::study::render_terms::orientation_domain(type_name,Registry::get())
            .map(|value|value.to_string()).map_err(PyValueError::new_err)
    }

    #[staticmethod]
    fn decode_rows_json(types: Vec<String>, rows: Vec<Vec<i64>>) -> PyResult<String> {
        let result: Result<Vec<_>, String> = rows
            .iter()
            .map(|row| {
                if row.len() != types.len() {
                    return Err("packed row width differs from supplied schema".into());
                }
                row.iter()
                    .zip(&types)
                    .map(|(value, ty)| {
                        arclog::study::render_terms::decode(ty, *value, Registry::get())
                    })
                    .collect::<Result<Vec<_>, _>>()
            })
            .collect();
        result
            .map(|rows| arclog::study::render::decoded_rows_json(rows))
            .map_err(PyValueError::new_err)
    }

    /// Full held DET choices and exact body-read subsets, decoded by Term::decode.
    fn choice_evidence_json(&self, py: Python<'_>, kept_json: &str) -> PyResult<String> {
        py.detach(|| arclog::study::render_choices::export_json(&self.program, kept_json, Registry::get()))
            .map(|v| v.to_string()).map_err(PyValueError::new_err)
    }

    /// Exact OUT key projection onto native body columns and original label paths.
    fn out_bindings_json(&self, py: Python<'_>) -> PyResult<String> {
        py.detach(|| arclog::study::render_out::export(&self.program))
            .map(|v| v.to_string()).map_err(PyValueError::new_err)
    }

    /// Relation names from the original case writer, guarded by exact stream identity.
    fn relation_source_names_json(&self, py: Python<'_>, corpus: &str, task: &str, case: &str) -> PyResult<String> {
        py.detach(|| arclog::study::render_names::from_case(self.program.checked(), &self.settings,
            std::path::Path::new(corpus), task, case).map(|v|v.to_string()))
            .map_err(PyValueError::new_err)
    }

    fn render_json(&self, py: Python<'_>) -> PyResult<String> {
        py.detach(|| {
            self.program
                .render_json(Registry::get())
                .map(|v| v.to_string())
        })
        .map_err(PyValueError::new_err)
    }

    /// The hash of the resolver's content of the query at `index`: free
    /// of the names that the scope gives its tables. The content is that of
    /// the query in the program of the queries up to it, as a decode
    /// that has just finished it holds, since a later read of a `DET`'s
    /// columns changes the columns that the resolution keeps.
    fn query_hash(&self, index: isize) -> PyResult<u128> {
        let (content, _) = self.query_content(index)?;
        Ok(content.content_hash().0)
    }

    /// The bytes that `query_hash` hashes, for the query at `index`.
    fn query_bytes<'py>(&self, py: Python<'py>, index: isize) -> PyResult<Bound<'py, PyBytes>> {
        let (content, _) = self.query_content(index)?;
        Ok(PyBytes::new(py, content.canonical_bytes()))
    }

    /// The canonical hash of the query at `index`, with the names as
    /// written.
    fn written_query_hash(&self, index: isize) -> PyResult<u128> {
        let (_, query) = finished_query(self.program.program(), index)?;
        Ok(written_query_hash(query).0)
    }

    /// For each list of the query at `index`, by its source path, the
    /// canonical position of each element.
    fn query_order<'py>(&self, py: Python<'py>, index: isize) -> PyResult<Bound<'py, PyDict>> {
        let (_, query) = finished_query(self.program.program(), index)?;
        let order = CanonicalOrder::of(query, &mut SearchBudget::new());
        let lists = PyDict::new(py);
        for (path, positions) in order.list_positions() {
            let key = PyTuple::new(py, path.0.iter().map(|step| step.0))?;
            lists.set_item(key, positions)?;
        }
        Ok(lists)
    }

    /// For each part of the `RIGID_DET` form at `index`, in the order that
    /// the form lists its parts, `(path, position)`, as `Decoder.rigid_parts`
    /// gives them. `IndexError` where the program has no form at `index`,
    /// `ValueError` where it is no `RIGID_DET` form.
    fn rigid_parts(&self, index: isize) -> PyResult<Vec<(String, u32)>> {
        let (position, _) = finished_query(self.program.program(), index)?;
        arclog::resolver::rigid_parts(self.program.program(), position, Registry::get()).map_err(PyValueError::new_err)
    }

    fn sexp(&self) -> String {
        self.program.sexp(Registry::get())
    }

    fn program_form(&self) -> String {
        self.sexp()
    }

    /// Every gold clause, addressed by its AST, including INIT key/inputs.
    fn points(&self) -> Vec<PyMutationPoint> {
        self.program
            .mutation_points()
            .into_iter()
            .map(|inner| PyMutationPoint { inner })
            .collect()
    }

    /// Select unique complete K-edit assignments from the valid domain.
    /// Binding exclusions are solved before any spec can be sampled.
    #[pyo3(signature = (point, k, count, seed, *, source_revision, task, case, operation="mixed"))]
    fn draw_specs(
        &self,
        py: Python<'_>,
        point: &PyMutationPoint,
        k: usize,
        count: usize,
        seed: u64,
        source_revision: String,
        task: String,
        case: String,
        operation: &str,
    ) -> PyResult<(Vec<PyMutationSpec>, String)> {
        if source_revision.is_empty() || task.is_empty() || case.is_empty() {
            return Err(PyValueError::new_err(
                "source revision, task and case must be nonempty",
            ));
        }
        let origin = arclog::mutation::Source {
            revision: source_revision,
            task,
            case,
        };
        let (specs, stats) = py
            .detach(|| {
                self.program.draw_specs(
                    &point.inner,
                    k,
                    count,
                    seed,
                    operation,
                    origin,
                    &self.settings,
                    Registry::get(),
                )
            })
            .map_err(PyValueError::new_err)?;
        Ok((
            specs
                .into_iter()
                .map(|inner| PyMutationSpec { inner })
                .collect(),
            stats.json().to_string(),
        ))
    }

    /// Direct source-conjunct inventory; unsupported connectives remain visible.
    fn substitution_occurrences_json(&self, point: &PyMutationPoint) -> PyResult<String> {
        self.program.substitution_occurrences(&point.inner)
            .map(|value| value.to_string()).map_err(PyValueError::new_err)
    }

    /// New occurrence-proportional population; does not change draw_specs.
    #[pyo3(signature = (point, at, count, seed, *, source_revision, task, case))]
    fn draw_substitutes_at(&self, py: Python<'_>, point: &PyMutationPoint,
        at: Vec<u32>, count: usize, seed: u64, source_revision: String,
        task: String, case: String) -> PyResult<(Vec<PyMutationSpec>, String)> {
        if source_revision.is_empty() || task.is_empty() || case.is_empty() {
            return Err(PyValueError::new_err("source revision, task and case must be nonempty"));
        }
        let at = arclog::program::path::NodePath(at.into_iter().map(arclog::program::path::PathStep).collect());
        let origin = arclog::mutation::Source { revision:source_revision, task, case };
        let (specs, stats) = py.detach(|| self.program.draw_substitutes_at(&point.inner,
            &at, count, seed, origin, &self.settings, Registry::get()))
            .map_err(PyValueError::new_err)?;
        Ok((specs.into_iter().map(|inner| PyMutationSpec { inner }).collect(), stats.json().to_string()))
    }

    /// Only new native typed-interface proposals, never baseline primitives.
    #[pyo3(signature = (point, at, count, seed, *, source_revision, task, case))]
    fn draw_added_substitutes_at(&self, py: Python<'_>, point: &PyMutationPoint,
        at: Vec<u32>, count: usize, seed: u64, source_revision: String,
        task: String, case: String) -> PyResult<(Vec<PyMutationSpec>, String)> {
        if source_revision.is_empty() || task.is_empty() || case.is_empty() {
            return Err(PyValueError::new_err("source revision, task and case must be nonempty"));
        }
        let at = arclog::program::path::NodePath(at.into_iter().map(arclog::program::path::PathStep).collect());
        let origin = arclog::mutation::Source { revision:source_revision, task, case };
        let (specs, stats) = py.detach(|| self.program.draw_added_substitutes_at(&point.inner,
            &at, count, seed, origin, &self.settings, Registry::get()))
            .map_err(PyValueError::new_err)?;
        Ok((specs.into_iter().map(|inner| PyMutationSpec { inner }).collect(), stats.json().to_string()))
    }

    /// Only whole-block proposals; previous atomic draws are not revisited.
    #[pyo3(signature = (point, at, count, seed, *, source_revision, task, case))]
    fn draw_block_substitutes_at(&self, py: Python<'_>, point: &PyMutationPoint,
        at: Vec<u32>, count: usize, seed: u64, source_revision: String,
        task: String, case: String) -> PyResult<(Vec<PyMutationSpec>, String)> {
        if source_revision.is_empty() || task.is_empty() || case.is_empty() {
            return Err(PyValueError::new_err("source revision, task and case must be nonempty"));
        }
        let at = arclog::program::path::NodePath(at.into_iter().map(arclog::program::path::PathStep).collect());
        let origin = arclog::mutation::Source { revision:source_revision, task, case };
        let (specs, stats) = py.detach(|| self.program.draw_block_substitutes_at(&point.inner,
            &at, count, seed, origin, &self.settings, Registry::get()))
            .map_err(PyValueError::new_err)?;
        Ok((specs.into_iter().map(|inner| PyMutationSpec { inner }).collect(), stats.json().to_string()))
    }

    /// Compare draw-kind counts before filters, using the legacy traversal
    /// and the production fair traversal over the same real AST/domain.
    #[pyo3(signature = (point, k, count, seed, *, source_revision, task, case, operation="mixed"))]
    fn audit_draw_order(
        &self,
        py: Python<'_>,
        point: &PyMutationPoint,
        k: usize,
        count: usize,
        seed: u64,
        source_revision: String,
        task: String,
        case: String,
        operation: &str,
    ) -> PyResult<String> {
        let origin = arclog::mutation::Source {
            revision: source_revision,
            task,
            case,
        };
        py.detach(|| {
            self.program
                .audit_draw_order(
                    &point.inner,
                    k,
                    count,
                    seed,
                    operation,
                    origin,
                    &self.settings,
                    Registry::get(),
                )
                .map(|v| v.to_string())
        })
        .map_err(PyValueError::new_err)
    }

    /// Read-only stored-form classification; recorded edits locate sites only.
    fn stored_static_prune_json(&self, py: Python<'_>, gold: &PyStudyProgram, identity_json: &str) -> PyResult<String> {
        if self.settings != gold.settings {return Err(PyValueError::new_err("stored_settings: gold and stored settings differ"));}
        let identity=arclog::study::render::parse_json(identity_json).map_err(PyValueError::new_err)?;
        py.detach(||self.program.stored_static_prune_json(&gold.program,&identity,Registry::get(),&self.settings))
            .map(|v|v.to_string()).map_err(PyValueError::new_err)
    }

    /// Rehydrate and verify a stored identity without drawing its domain.
    fn decode_source(&self, py:Python<'_>)->PyResult<Self> {
        let program=py.detach(|| self.program.decode_source(Registry::get(),&self.settings)).map_err(PyValueError::new_err)?;
        Ok(Self {program,settings:self.settings})
    }

    fn representation_certificate_json(&self,py:Python<'_>,source_program:&PyStudyProgram)->PyResult<String> {
        if self.settings!=source_program.settings {return Err(crate::errors::RecordedIdentityError::new_err(("settings","source and current settings differ")))}
        py.detach(||self.program.representation_certificate(&source_program.program,Registry::get(),&self.settings))
            .map(|v|v.to_string()).map_err(|error|crate::errors::RecordedIdentityError::new_err(("stored_representation",error)))
    }

    fn rehydrate_recorded_identity(&self,py:Python<'_>,identity_json:&str,stored_program:&PyStudyProgram)->PyResult<(PyValidMutant,String)> {
        if self.settings!=stored_program.settings {return Err(crate::errors::RecordedIdentityError::new_err(("settings","gold and stored settings differ")))}
        let identity=arclog::study::render::parse_json(identity_json)
            .map_err(|error|crate::errors::RecordedIdentityError::new_err(("identity_admission",error)))?;
        let (inner,certificate)=py.detach(||self.program.rehydrate_recorded_identity(&identity,&stored_program.program,Registry::get(),&self.settings))
            .map_err(|error|crate::errors::RecordedIdentityError::new_err((error.stage,error.message)))?;
        Ok((PyValidMutant{inner,settings:self.settings},certificate.to_string()))
    }

    /// One native BODY edit; checks the complete candidate and preserves gold's shell.
    #[pyo3(signature=(body_path, program_text, body_stream=None, *, source_revision, task, case))]
    fn construct_body_replacement(&self,py:Python<'_>,body_path:Vec<u32>,program_text:&str,body_stream:Option<&str>,
        source_revision:String,task:String,case:String)->PyResult<PyValidMutant> {
        let at=arclog::program::path::NodePath(body_path.into_iter().map(arclog::program::path::PathStep).collect());
        let stream=body_stream.map(arclog::study::render::parse_json).transpose().map_err(PyValueError::new_err)?;
        let origin=arclog::mutation::Source{revision:source_revision,task,case};
        let inner=py.detach(||self.program.construct_body_replacement(&at,program_text,stream.as_ref(),origin,Registry::get(),&self.settings))
            .map_err(PyValueError::new_err)?;
        Ok(PyValidMutant{inner,settings:self.settings})
    }

    fn construct_identity(&self, py: Python<'_>, identity_json: &str) -> PyResult<PyValidMutant> {
        let identity =
            arclog::study::render::parse_json(identity_json).map_err(PyValueError::new_err)?;
        let inner = py
            .detach(|| {
                self.program
                    .construct_identity(&identity, Registry::get(), &self.settings)
            })
            .map_err(PyValueError::new_err)?;
        Ok(PyValidMutant {
            inner,
            settings: self.settings,
        })
    }

    fn render_pair_json(&self, py: Python<'_>, identity_json: &str) -> PyResult<String> {
        let identity =
            arclog::study::render::parse_json(identity_json).map_err(PyValueError::new_err)?;
        py.detach(|| {
            let mutant =
                self.program
                    .construct_identity(&identity, Registry::get(), &self.settings)?;
            let source=if std::sync::Arc::ptr_eq(self.program.checked(),mutant.gold()) {self.program.clone()}
                else {self.program.decode_source(Registry::get(),&self.settings)?};
            arclog::study::render::render_pair(&source, &mutant, Registry::get()).map(|v| v.to_string())
        })
        .map_err(|error: String| PyValueError::new_err(error))
    }

    fn construct(&self, spec: &PyMutationSpec) -> PyResult<PyValidMutant> {
        let inner = self
            .program
            .construct(&spec.inner)
            .map_err(PyValueError::new_err)?;
        Ok(PyValidMutant {
            inner,
            settings: self.settings,
        })
    }

    /// (ids, model flags, AST path per token), under this handle's settings.
    fn decode_stream(&self) -> PyResult<Stream> {
        let stream = self
            .program
            .decode_stream(Registry::get(), &self.settings)
            .map_err(PyValueError::new_err)?;
        Ok((
            stream.ids,
            stream.model,
            stream
                .paths
                .into_iter()
                .map(|p| p.0.iter().map(|step| step.0).collect())
                .collect(),
        ))
    }

    #[getter]
    fn vocabulary(&self) -> PyVocabulary {
        PyVocabulary::of(&arclog::stream::Vocabulary::new(
            Registry::get(),
            &self.settings,
        ))
    }
}

/// The gold of the task `task` without its empty clauses, and the singleton
/// double-read lint, as JSON (`arclog::study::empty_gold`): `corpus` is the
/// converted corpus, `tasks` the directory of the task files, and
/// `deadline_seconds` is accepted and guards nothing: an evaluation request
/// stops at a work cap alone. `ValueError` where the task file does not read. The
/// call runs with the GIL released.
#[pyfunction]
#[pyo3(signature = (corpus, tasks, task, deadline_seconds=None))]
pub(crate) fn empty_gold_json(py: Python<'_>, corpus: &str, tasks: &str, task: &str, deadline_seconds: Option<f64>) -> PyResult<String> {
    let deadline = deadline_seconds.map(std::time::Duration::try_from_secs_f64).transpose().map_err(|error| PyValueError::new_err(format!("deadline_seconds: {error}")))?;
    let constructions = crate::constructions()?;
    py.detach(|| arclog::study::empty_gold::empty_gold(std::path::Path::new(corpus), std::path::Path::new(tasks), task, deadline, constructions))
        .map(|value| value.to_string())
        .map_err(PyValueError::new_err)
}

/// The Name that the tables export (`step_tables`'s `tables["name"]`) gives
/// the output of a `RIGID_DET` form that `read` reads in `text`, an arclog
/// program text: `read` is the relation of the read as `text` writes it, as
/// `&r22.r20`, `&r22.pose` or `&r22.r20.box`, and the Name is `pose` or
/// `slot <n>`, n the position of the part in the form's canonical form,
/// followed by the steps after the part's (`arclog::resolver::rigid_read_name`).
/// A part that the canonical form cannot tell from an earlier part, so that
/// two texts of one QueryHash may list the two in either order, takes the
/// Name of the earliest such part, whose table holds the same rows.
/// `ValueError` where `text` does not read, or where `read` reads no output
/// of a `RIGID_DET` form of `text`. The call runs with the GIL released.
#[pyfunction]
pub(crate) fn rigid_slot_name(py: Python<'_>, text: &str, read: &str) -> PyResult<String> {
    py.detach(|| {
        let read_text = arclog::read::read_arclog(text, arclog::layout::SourceFile::Arclog).map_err(|d| arclog::study::diagnostics_text(&d))?;
        if read_text.diagnostics.iter().any(|d| d.severity == arclog::diagnostic::Severity::Error) {
            return Err(arclog::study::diagnostics_text(&read_text.diagnostics));
        }
        arclog::resolver::rigid_read_name(&read_text.value.0, read, Registry::get())
    })
    .map_err(PyValueError::new_err)
}
