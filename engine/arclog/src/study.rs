//! Checked program values for the clause-mutation study.
//!
//! Input is a single case program, with determinations in the program.
//! Expand solver alternatives with `stream::corpus::case_files` first.
//! Paths always address the AST in source order, never stream offsets.

use std::sync::{Arc,OnceLock};

pub mod render;
pub mod render_terms;
pub mod render_bodies;
pub mod render_definitions;
pub mod render_meanings;

use crate::check::{CheckCache, CheckedProgram, SolverClauses, check_shared_program};
use crate::diagnostic::{Diagnostic, Severity};
use crate::layout::{Layout, SourceFile};
use crate::program::path::NodePath;
use crate::program::{Form, Node, Program};
use crate::registry::Registry;
use crate::resolver::{SolverScope, resolve};
use crate::stream::{DecodeSettings, Emitter, Vocabulary, token_stream_with_paths};

/// An AST together with the checks required to evaluate it. Source layout is
/// presentation metadata only; it never identifies a program or mutation.
#[derive(Clone, Debug)]
pub struct StudyProgram {
    checked: Arc<CheckedProgram>,
    layout: Option<Layout>,
    render_cache: Arc<OnceLock<(usize, Result<serde_json::Value,String>)>>,
    source_cache: Arc<OnceLock<(usize,DecodeSettings,Result<StudyProgram,String>)>>,
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

impl StudyProgram {
    /// Reads a standalone case, preserving the engine's column and label names.
    /// Malformed nodes must never disappear silently from study input.
    pub fn from_sexp(text: &str, registry: &Registry) -> Result<Self, String> {
        let read =
            crate::read::read_arclog(text, SourceFile::Arclog).map_err(|d| diagnostics_text(&d))?;
        if read
            .diagnostics
            .iter()
            .any(|d| d.severity == Severity::Error)
        {
            return Err(diagnostics_text(&read.diagnostics));
        }
        let (program, layout) = read.value;
        Self::from_program(program, Some(layout), registry)
    }

    /// Takes a decoder's completed AST directly, without printing/reparsing it.
    pub fn from_decoded(program: Node<Program>, registry: &Registry) -> Result<Self, String> {
        Self::from_program(program, None, registry)
    }

    pub(crate) fn from_program(
        program: Node<Program>,
        layout: Option<Layout>,
        registry: &Registry,
    ) -> Result<Self, String> {
        Self::from_program_cached(program, layout, registry, &mut CheckCache::default())
    }

    pub(crate) fn from_program_cached(
        program: Node<Program>,
        layout: Option<Layout>,
        registry: &Registry,
        cache: &mut CheckCache,
    ) -> Result<Self, String> {
        if program
            .value()
            .forms
            .iter()
            .any(|f| matches!(f, Form::Claim(_) | Form::Alts(_) | Form::Demonstrated(_)))
        {
            return Err("study input must be a standalone case; expand claims/alternatives with case_files first; DEMONSTRATED is not decodeable".into());
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
                ));
            }
        }
        let resolved = resolve(&program, None, &SolverScope::default(), registry);
        if resolved
            .diagnostics
            .iter()
            .any(|d| d.severity == Severity::Error)
        {
            return Err(diagnostics_text(&resolved.diagnostics));
        }
        let resolved = Arc::new(resolved.value);
        let clauses = SolverClauses::of_shared_program(Arc::clone(&resolved));
        let checked = check_shared_program(resolved, &clauses, registry, cache)
            .map_err(|d| diagnostics_text(&d))?;
        Ok(Self {
            checked: Arc::new(checked),
            layout,
            render_cache:Arc::new(OnceLock::new()),
            source_cache:Arc::new(OnceLock::new()),
        })
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
            None => crate::write::write_synthesized(self.program(), registry),
        }
    }

    /// Failure here means the AST is outside the requested decode vocabulary,
    /// not that it should be repaired. Construction will require this to pass.
    pub fn decode_stream(
        &self,
        registry: &Registry,
        settings: &DecodeSettings,
    ) -> Result<StudyStream, String> {
        let vocabulary = Vocabulary::new(registry, settings);
        let written = token_stream_with_paths(&self.checked, &vocabulary)
            .map_err(|d| diagnostics_text(&[d]))?;
        let mut stream = StudyStream {
            ids: Vec::new(),
            model: Vec::new(),
            paths: Vec::new(),
        };
        for (token, emitter, path) in written {
            stream.ids.push(vocabulary.id(&token).ok_or_else(|| {
                format!("writer emitted a token outside the vocabulary: {token}")
            })?);
            stream.model.push(u8::from(emitter == Emitter::Model));
            stream.paths.push(path);
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
        _ => false,
    }
}
