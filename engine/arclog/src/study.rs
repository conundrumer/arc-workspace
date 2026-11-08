//! Checked program values for the clause-mutation study.
//!
//! Input is a single case program, with determinations in the program.
//! Expand solver alternatives with `stream::corpus::case_files` first.
//! Paths always address the AST in source order, never stream offsets.

use std::sync::{Arc,OnceLock};

pub mod render;
pub mod features;
pub mod render_terms;
pub mod render_choices;
pub mod render_out;
pub mod render_bodies;
pub mod render_definitions;
pub mod render_meanings;
pub mod render_names;
pub mod render_correspondence;
pub mod stream_certificate;
pub mod normalization;
pub mod empty_gold;

use crate::check::{CheckCache, CheckId, CheckedProgram, SolverClauses, check_shared_program};
use crate::diagnostic::{Diagnostic, DiagnosticKind, Severity};
use crate::layout::{Layout, SourceFile};
use crate::program::path::NodePath;
use crate::program::{Form, Node, Program};
use crate::registry::Registry;
use crate::resolver::{SolverScope, resolve};
use crate::stream::{DecodeSettings, Emitter, Vocabulary, WrittenStream};

/// An AST together with the checks required to evaluate it. Source layout is
/// presentation metadata only; it never identifies a program or mutation.
#[derive(Clone, Debug)]
pub struct StudyProgram {
    checked: Arc<CheckedProgram>,
    layout: Option<Layout>,
    display_names: Option<Arc<crate::write::LabelNames>>,
    display_names_cache: Arc<OnceLock<(usize, Arc<crate::write::LabelNames>)>>,
    render_cache: Arc<OnceLock<(usize, Result<serde_json::Value,String>)>>,
    source_cache: Arc<OnceLock<(usize,DecodeSettings,Result<StudyProgram,String>)>>,
    stream_cache: Arc<OnceLock<(usize,DecodeSettings,Result<StudyStream,StudyError>)>>,
    written_cache: Arc<OnceLock<(usize,DecodeSettings,Result<Arc<WrittenStream>,Diagnostic>)>>,
    mutation_checks: Arc<OnceLock<Result<Arc<CheckCache>,String>>>,
    typed_sites_cache: Arc<OnceLock<(usize,Result<Arc<crate::check::render_sites::TypedSiteExport>,String>)>>,
}

/// An engine-written stream and its source-order AST correspondence.
#[derive(Clone, Debug)]
pub struct StudyStream {
    pub ids: Vec<u32>,
    pub model: Vec<u8>,
    pub paths: Vec<NodePath>,
}

/// Diagnostics retain their check and AST/source location in error reports.
pub fn diagnostics_text(diagnostics: &[Diagnostic]) -> String {
    diagnostics
        .iter()
        .map(|d| format!("{:?} at {:?}: {}", d.kind, d.location, d.message))
        .collect::<Vec<_>>()
        .join("\n")
}

/// Why a program or a stream is not made into a [`StudyProgram`].
#[derive(Clone, Debug)]
pub enum StudyError {
    /// The engine's checks refuse the program. Holds the diagnostics of the
    /// read, of the resolution or of the checks, at least one of them an error
    /// of a check ([`DiagnosticKind::Check`]).
    Refused(Vec<Diagnostic>),
    /// Any other reason the engine refuses the program or the stream, as
    /// text.
    Other(String),
    /// A failure inside the engine, as text: the input is no reason for it.
    Fault(String),
}

impl StudyError {
    /// The refusal that `diagnostics` make, where one of them is an error of a
    /// check, and the text of them otherwise.
    pub fn of_diagnostics(diagnostics: &[Diagnostic]) -> Self {
        if diagnostics.iter().any(is_check_error) {
            StudyError::Refused(diagnostics.to_vec())
        } else {
            StudyError::Other(diagnostics_text(diagnostics))
        }
    }

    /// The first error of a check that the refusal holds: it names the check
    /// and the place of the refusal. `None` for an error that is no refusal.
    pub fn first_check_error(&self) -> Option<(CheckId, &Diagnostic)> {
        match self {
            StudyError::Refused(diagnostics) => diagnostics.iter().find_map(|d| match d.kind {
                DiagnosticKind::Check(check) if d.severity == Severity::Error => Some((check, d)),
                _ => None,
            }),
            StudyError::Other(_) | StudyError::Fault(_) => None,
        }
    }
}

fn is_check_error(diagnostic: &Diagnostic) -> bool {
    matches!(diagnostic.kind, DiagnosticKind::Check(_)) && diagnostic.severity == Severity::Error
}

impl std::fmt::Display for StudyError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            StudyError::Refused(diagnostics) => f.write_str(&diagnostics_text(diagnostics)),
            StudyError::Other(message) | StudyError::Fault(message) => f.write_str(message),
        }
    }
}

impl std::error::Error for StudyError {}

impl From<String> for StudyError {
    fn from(message: String) -> Self {
        StudyError::Other(message)
    }
}

impl From<&str> for StudyError {
    fn from(message: &str) -> Self {
        StudyError::Other(message.to_owned())
    }
}

impl From<StudyError> for String {
    fn from(error: StudyError) -> Self {
        error.to_string()
    }
}

impl StudyProgram {
    /// Reads a standalone case, preserving the engine's column and label names.
    /// Malformed nodes must never disappear silently from study input.
    pub fn from_sexp(text: &str, registry: &Registry) -> Result<Self, String> {
        Self::from_sexp_cached(text,registry,&mut CheckCache::default())
    }

    /// Reuse exact canonical check results within one caller-owned case.
    /// Reading, interface validation and name resolution are always performed.
    pub fn from_sexp_cached(text:&str,registry:&Registry,cache:&mut CheckCache)->Result<Self,String> {
        Self::read_sexp_cached(text,registry,cache).map_err(String::from)
    }

    /// [`StudyProgram::from_sexp_cached`], with the error typed: a program
    /// that the reader, the resolver or a check refuses is a
    /// [`StudyError::Refused`].
    pub fn read_sexp_cached(text:&str,registry:&Registry,cache:&mut CheckCache)->Result<Self,StudyError> {
        let read =
            crate::read::read_arclog(text, SourceFile::Arclog).map_err(|d| StudyError::of_diagnostics(&d))?;
        if read
            .diagnostics
            .iter()
            .any(|d| d.severity == Severity::Error)
        {
            return Err(StudyError::of_diagnostics(&read.diagnostics));
        }
        let (program, layout) = read.value;
        Self::from_program_cached(program, Some(layout), registry, cache)
    }

    /// [`StudyProgram::from_sexp_cached`], of a program that holds a feature's
    /// forms, as [`crate::read::read_feature_forms`] reads them.
    pub fn from_feature_forms_cached(text:&str,registry:&Registry,cache:&mut CheckCache)->Result<Self,String> {
        let read = crate::read::read_feature_forms(text).map_err(|d| diagnostics_text(&d))?;
        if read.diagnostics.iter().any(|d| d.severity == Severity::Error) {
            return Err(diagnostics_text(&read.diagnostics));
        }
        let (program, layout) = read.value;
        Self::from_program_cached(program, Some(layout), registry, cache).map_err(String::from)
    }

    /// Takes a decoder's completed AST directly, without printing/reparsing it.
    pub fn from_decoded(program: Node<Program>, registry: &Registry) -> Result<Self, String> {
        Self::from_program(program, None, registry).map_err(String::from)
    }

    pub fn from_decoded_cached(program:Node<Program>,registry:&Registry,cache:&mut CheckCache)->Result<Self,String> {
        Self::read_decoded_cached(program,registry,cache).map_err(String::from)
    }

    /// [`StudyProgram::from_decoded_cached`], with the error typed as
    /// [`StudyProgram::read_sexp_cached`] types it.
    pub fn read_decoded_cached(program:Node<Program>,registry:&Registry,cache:&mut CheckCache)->Result<Self,StudyError> {
        Self::from_program_cached(program,None,registry,cache)
    }

    pub(crate) fn from_program(
        program: Node<Program>,
        layout: Option<Layout>,
        registry: &Registry,
    ) -> Result<Self, StudyError> {
        Self::from_program_cached(program, layout, registry, &mut CheckCache::default())
    }

    pub(crate) fn from_program_cached(
        program: Node<Program>,
        layout: Option<Layout>,
        registry: &Registry,
        cache: &mut CheckCache,
    ) -> Result<Self, StudyError> {
        if program
            .value()
            .forms
            .iter()
            .any(|f| matches!(f, Form::Claim(_) | Form::Alts(_)))
        {
            return Err("study input must be a standalone case; expand claims/alternatives with case_files first".into());
        }
        if !program
            .value()
            .forms
            .iter()
            .any(|f| matches!(f, Form::Out(_)))
        {
            return Err("study input must include the rest of the gold program through OUT".into());
        }
        for (index, form) in program.value().forms.iter().enumerate() {
            if !interfaces_hold(form) {
                return Err(format!(
                    "derived_interface_mismatch at form {index}: body exports must equal the preserved clause/key/candidate columns"
                ).into());
            }
        }
        let resolved = resolve(&program, None, &SolverScope::default(), registry);
        if resolved
            .diagnostics
            .iter()
            .any(|d| d.severity == Severity::Error)
        {
            return Err(StudyError::of_diagnostics(&resolved.diagnostics));
        }
        let resolved = Arc::new(resolved.value);
        let clauses = SolverClauses::of_shared_program(Arc::clone(&resolved));
        let checked = check_shared_program(resolved, &clauses, registry, cache)
            .map_err(|d| StudyError::of_diagnostics(&d))?;
        Ok(Self {
            checked: Arc::new(checked),
            layout,
            display_names: None,
            display_names_cache: Arc::new(OnceLock::new()),
            render_cache:Arc::new(OnceLock::new()),
            source_cache:Arc::new(OnceLock::new()),
            stream_cache:Arc::new(OnceLock::new()),
            written_cache:Arc::new(OnceLock::new()),
            mutation_checks:Arc::new(OnceLock::new()),
            typed_sites_cache:Arc::new(OnceLock::new()),
        })
    }

    /// The single display namespace for text, body schemas and typed metadata.
    /// Authored programs retain their layout; decoded mutants inherit gold's
    /// native LabelId names without changing the checked AST or its streams.
    pub fn label_names(&self, registry: &Registry) -> Arc<crate::write::LabelNames> {
        let key = registry as *const Registry as usize;
        let names = || Arc::new(match &self.layout {
            Some(layout) => self.program().value().forms.iter().enumerate().map(|(index, _)| {
                layout.node(SourceFile::Arclog, &NodePath::top(index as u32))
                    .map(|node| node.label_names.to_vec()).unwrap_or_default()
            }).collect(),
            None => crate::write::label_names_named(self.program(), registry, self.display_names.as_deref()),
        });
        let cached = self.display_names_cache.get_or_init(|| (key, names()));
        if cached.0 == key { Arc::clone(&cached.1) } else { names() }
    }

    pub(crate) fn preserve_gold_names(mut self, gold: &Self, registry: &Registry) -> Self {
        if self.layout.is_none() {
            self.display_names = Some(gold.label_names(registry));
        }
        self
    }

    /// A gold namespace can contain distinct branch-local IDs with one spelling.
    /// If the edit exposes such a spelling, only the ordinary reader/binder can
    /// decide it. Never approximate OR/IF/key scopes by a global name collision.
    pub(crate) fn check_preserved_name_binding(&self, registry: &Registry,
        settings: &DecodeSettings, cache: &mut CheckCache) -> Result<(), StudyError> {
        let Some(names) = &self.display_names else { return Ok(()); };
        let ambiguous = self.program().value().forms.iter().enumerate().any(|(i, form)| {
            let mut present = crate::hash::StableHashSet::default();
            crate::safety::each_label_use_at(crate::program::path::NodeRef::from(form),
                &NodePath::top(i as u32), &mut |_, used| {
                    if let Some(id) = crate::types::use_label(used) { present.insert(id); }
                });
            let mut held: crate::hash::StableHashMap<&str, crate::program::LabelId> = crate::hash::StableHashMap::default();
            names[i].iter().filter(|(id, _)| present.contains(id)).any(|(id, name)| {
                held.insert(name.as_ref(), *id).is_some_and(|other| other != *id)
            })
        });
        if !ambiguous { return Ok(()); }
        let read = Self::read_sexp_cached(&self.sexp(registry), registry, cache)?;
        // The text writes the sites of a read in slot order, which the AST
        // need not hold, so the stream of the AST is not the one to compare.
        // The same writer's text with generated names, which no two labels
        // of a scope share, gives the bindings of the AST.
        let plain = crate::write::write_synthesized_named(self.program(), registry, None);
        let before = Self::read_sexp_cached(&plain, registry, cache)?.decode_stream(registry, settings)?;
        let after = read.decode_source(registry, settings)?.decode_stream(registry, settings)?;
        if before.ids != after.ids || before.model != after.model {
            return Err("gold display names would change native bindings after the edit".into());
        }
        Ok(())
    }

    pub(crate) fn node_texts(&self, registry: &Registry)
        -> Result<std::collections::BTreeMap<NodePath, String>, String> {
        crate::write::node_texts(self.program(), self.layout(), registry, self.display_names.as_deref())
    }

    /// Renderer and mutation share one native inference traversal on this
    /// exact checked handle. New checked programs get fresh caches.
    pub(crate) fn typed_sites(&self, registry: &Registry) -> Result<Arc<crate::check::render_sites::TypedSiteExport>, String> {
        let key = registry as *const Registry as usize;
        let read = || crate::check::render_sites::export_typed_named(self.checked(), registry, &self.label_names(registry)).map(Arc::new);
        let cached = self.typed_sites_cache.get_or_init(|| (key, read()));
        if cached.0 == key { cached.1.clone() } else { read() }
    }

    /// Gold checks shared by independent domain searches on this handle.
    /// The permanent base contains no candidate results. Each search drops
    /// its own overlay, so trying more points never retains all mutants.
    pub(crate) fn mutation_check_base(&self, registry:&Registry)->Result<Arc<CheckCache>,String> {
        self.mutation_checks.get_or_init(|| {
            let mut cache=CheckCache::default();
            let clauses=SolverClauses::of_shared_program(Arc::clone(&self.checked.program));
            check_shared_program(Arc::clone(&self.checked.program),&clauses,registry,&mut cache)
                .map_err(|diagnostics|diagnostics_text(&diagnostics))?;
            Ok(Arc::new(cache))
        }).clone()
    }

    /// Reusable native decode AST for stored anonymous-slot identities.
    pub fn decode_source(&self, registry:&Registry, settings:&DecodeSettings)->Result<Self,String> {
        if self.layout.is_none() {return Ok(self.clone());}
        let key=registry as *const Registry as usize;
        let read=|| {
            let stream=self.decode_stream(registry,settings)?;
            let mut reader=crate::decode::program_read::ProgramReader::new(registry,*settings);
            Self::from_decoded(reader.read(&stream.ids,&stream.model)?,registry)
        };
        let cached=self.source_cache.get_or_init(||(key,*settings,read()));
        if cached.0==key && cached.1==*settings {cached.2.clone()} else {read()}
    }

    pub fn checked(&self) -> &Arc<CheckedProgram> {
        &self.checked
    }

    pub fn program(&self) -> &Node<Program> {
        &self.checked.program.program
    }

    pub(crate) fn layout(&self) -> Option<&Layout> {
        self.layout.as_ref()
    }

    /// File input keeps its original names; decoded input uses the engine's
    /// synthesized names. No independent Python printer is involved.
    pub fn sexp(&self, registry: &Registry) -> String {
        match &self.layout {
            Some(layout) => crate::write::write_arclog(self.program(), layout),
            None => crate::write::write_synthesized_named(self.program(), registry, self.display_names.as_deref()),
        }
    }

    /// Extend the existing classifier report with the case-normalization result.
    /// Only valid tests are deleted; aliases and constants are not deletions.
    /// See program/static_prune/proofs.md, "Gold case normalization".
    pub fn static_prune_report(&self, registry: &Registry, normalize: bool) -> Result<serde_json::Value, String> {
        self.static_prune_report_with_settings(registry, normalize, &DecodeSettings::default())
    }

    /// Use the caller's actual vocabulary/settings for additive provenance.
    pub fn static_prune_report_with_settings(&self, registry: &Registry, normalize: bool,
        settings: &DecodeSettings) -> Result<serde_json::Value, String> {
        self.prune_with_program(registry, normalize, settings).map(|(_, report)| report)
    }

    /// Return the actual checked editor result for fresh native acquisition.
    pub fn normalized_gold(&self, registry: &Registry, settings: &DecodeSettings)
        -> Result<(Self, serde_json::Value), String> {
        self.prune_with_program(registry, true, settings)
    }

    fn prune_with_program(&self, registry: &Registry, normalize: bool,
        settings: &DecodeSettings) -> Result<(Self, serde_json::Value), String> {
        let matches = crate::check::static_prune::matches(self.checked(), registry)?;
        let mut report = crate::check::static_prune::report(&matches);
        if !normalize { return Ok((self.clone(), report)); }
        let mut edits = Vec::new();
        for found in matches {
            if found.verdict.class != crate::program::static_prune::Class::Valid { continue; }
            let node = crate::program::path::node_at(crate::program::path::NodeRef::Program(self.program().value()), &found.path)
                .ok_or("valid atom path is absent")?;
            let mut binds = false;
            crate::safety::each_label_use_at(node, &found.path, &mut |_, use_| {
                binds |= matches!(use_, crate::program::LabelUse::Fresh(_));
            });
            if binds { return Err(format!("valid test at {:?} introduces a label; cannot delete its binder", found.path)); }
            edits.push(crate::mutation::edit::AtomEdit {
                at: found.path, replacement: None, kind: "delete", choice_kind: "static_valid",
            });
        }
        let normalized = if edits.is_empty() { self.clone() } else {
            let program = crate::mutation::edit::apply(self.program(), &edits)?;
            let layout = crate::mutation::edit::layout(self.layout(), &edits);
            // Re-resolve and check the whole edited AST with its original clause
            // interfaces. A missing binder is an error, never an inferred head.
            Self::from_program(program, layout, registry)?
        };
        report["normalized_program_sexp"] = normalized.sexp(registry).into();
        report["removed_atom_paths"] = serde_json::json!(edits.iter()
            .map(|edit| crate::mutation::path_json(&edit.at)).collect::<Vec<_>>());
        report["normalization_provenance"] = normalization::provenance(self, &normalized, &edits, registry, settings);
        Ok((normalized, report))
    }

    /// Failure here means the AST is outside the requested decode vocabulary,
    /// not that it should be repaired. Construction will require this to pass.
    pub fn decode_stream(
        &self,
        registry: &Registry,
        settings: &DecodeSettings,
    ) -> Result<StudyStream, String> {
        self.try_decode_stream(registry, settings).map_err(String::from)
    }

    /// [`StudyProgram::decode_stream`], with the error typed: a program that
    /// is outside the requested decode vocabulary is a [`StudyError::Other`],
    /// and a token that the writer emits outside the vocabulary is a
    /// [`StudyError::Fault`].
    pub fn try_decode_stream(
        &self,
        registry: &Registry,
        settings: &DecodeSettings,
    ) -> Result<StudyStream, StudyError> {
        let key=registry as *const Registry as usize;
        let cached=self.stream_cache.get_or_init(||(key,*settings,self.write_stream(registry,settings)));
        if cached.0==key && cached.1==*settings {cached.2.clone()} else {self.write_stream(registry,settings)}
    }

    /// One complete writer artifact for the certificate and its native
    /// consumers. Registry/settings mismatches are written in their own
    /// context, without reading or replacing the first context's artifact.
    pub fn written_stream(&self,registry:&Registry,settings:&DecodeSettings)->Result<Arc<WrittenStream>,Diagnostic> {
        let key=registry as *const Registry as usize;
        let write=||crate::stream::written_stream(&self.checked,&Vocabulary::new(registry,settings)).map(Arc::new);
        let cached=self.written_cache.get_or_init(||(key,*settings,write()));
        if cached.0==key && cached.1==*settings {cached.2.clone()} else {write()}
    }

    fn write_stream(&self,registry:&Registry,settings:&DecodeSettings)->Result<StudyStream,StudyError> {
        let vocabulary = Vocabulary::new(registry, settings);
        let written = self.written_stream(registry,settings).map_err(|d| StudyError::of_diagnostics(&[d]))?;
        let mut stream = StudyStream {
            ids: Vec::new(),
            model: Vec::new(),
            paths: written.paths.clone(),
        };
        for (token, emitter) in &written.tokens {
            stream.ids.push(vocabulary.id(token).ok_or_else(|| {
                StudyError::Fault(format!("writer emitted a token outside the vocabulary: {token}"))
            })?);
            stream.model.push(u8::from(*emitter == Emitter::Model));
        }
        Ok(stream)
    }
}

/// Heads in this AST are materialized derived fields. A simultaneous edit
/// must preserve their derivation, not only the old field values. Otherwise
/// stale columns can make the whole-program checker treat a now-local OR
/// label as a head label, while the reader/decoder rightly exports less.
/// Use precisely the reader's export/key derivation; never repair a head.
pub(crate) fn interfaces_hold(form: &Form) -> bool {
    use crate::program::*;
    use crate::read::columns::{key_labels, made_labels};
    fn labels(columns: &[RelationColumn]) -> Vec<LabelId> {
        columns.iter().map(|c| c.label).collect()
    }
    fn key(k: &KeyBody) -> bool {
        labels(&k.columns) == key_labels(k.body.value())
    }
    match form {
        Form::Clause(c) => labels(&c.value().columns) == made_labels(c.value().body.value()),
        Form::Instance(i) => i.value().key.as_ref().is_none_or(|k| key(&k.value().key)),
        Form::Choose(c) => {
            c.value().rows.as_ref().is_none_or(key)
                && labels(&c.value().candidate_columns) == made_labels(c.value().from.value())
        }
        Form::RigidDet(r) => {
            r.value().key.as_ref().is_none_or(key) && r.value().instance.as_ref().is_none_or(key)
        }
        Form::Out(o) => key(&o.value().key),
        // A `&prediction` clause has the columns the form fills, which need
        // not be the labels its body makes.
        Form::Demonstrated(d) => {
            let prediction = |form: &Form| matches!(form, Form::Clause(c) if crate::program::canonical::relation_of(&c.value().derives) == crate::program::canonical::prediction());
            d.value().key.as_ref().is_none_or(|k| key(&k.value().key))
                && d.value().rules.iter().all(|rule| rule.value().forms.iter().all(|form| prediction(form) || interfaces_hold(form)))
        }
        _ => false,
    }
}
