//! A complete synthesized BODY is one edit. The atomic editor owns the
//! enclosing program; the candidate's suffix is checked, never repaired.
use super::*;

fn body_at(program: &StudyProgram, at: &NodePath) -> Result<Node<Body>, String> {
    match node_at(NodeRef::Program(program.program().value()), at) {
        Some(NodeRef::Body(body)) => Ok(Node::new(body.clone())),
        _ => Err("body_replacement:point: no BODY at requested path".into()),
    }
}

fn same_stream(
    a: &StudyProgram,
    b: &StudyProgram,
    registry: &Registry,
    settings: &DecodeSettings,
) -> Result<bool, String> {
    let a = a.decode_stream(registry, settings)?;
    let b = b.decode_stream(registry, settings)?;
    Ok(a.ids == b.ids && a.model == b.model && a.paths == b.paths)
}

/// File layout retains byte/line positions after an edit. Compare the
/// native writer's fixed-layout text with each handle's own scoped names;
/// stale parentheses positions must not become an outside-BODY difference.
fn named_source_text(program: &StudyProgram, registry: &Registry) -> String {
    let names = program.label_names(registry);
    crate::write::write_synthesized_named(program.program(), registry, Some(names.as_ref()))
}

/// Compare the written envelope before resolving or checking the candidate.
/// Parsed clause columns are derived from its BODY, so checking a restored
/// AST here would misclassify a BODY-only interface change. Instead remove
/// the selected BODY on both sides and use the native file writer. These
/// empty shells are presentation probes, never admitted or evaluated.
fn source_shell(
    ast: &Node<Program>,
    layout: &crate::layout::Layout,
    at: &NodePath,
) -> Result<String, String> {
    let empty = Node::new(Body {
        conjuncts: Vec::new().into(),
    });
    let shell = edit::replace_body(ast, at, &empty)
        .map_err(|e| format!("body_replacement:outside_body_changed: {e}"))?;
    Ok(source_text(&shell, layout))
}

fn source_text(ast: &Node<Program>, layout: &crate::layout::Layout) -> String {
    let mut layout = layout.clone();
    layout.comments = Box::new([]);
    for node in layout.nodes.values_mut() {
        node.place = None;
        node.tokens = Box::new([]);
    }
    crate::write::write_arclog(ast, &layout)
}

impl StudyProgram {
    /// Certify a synthesized BODY without sampling the current atom domain.
    /// The origin belongs to the caller's source record, not to this handle.
    pub fn construct_body_replacement(
        &self,
        at: &NodePath,
        text: &str,
        body_stream: Option<&Value>,
        origin: Source,
        registry: &Registry,
        settings: &DecodeSettings,
    ) -> Result<ValidMutant, String> {
        let point = self
            .mutation_points()
            .into_iter()
            .find(|p| p.body == *at)
            .ok_or("body_replacement:point: not an original mutation point")?;
        // Separate parser diagnostics from failures of the complete candidate.
        let read =
            crate::read::read_arclog(text, crate::layout::SourceFile::Arclog).map_err(|d| {
                format!(
                    "body_replacement:syntax: {}",
                    crate::study::diagnostics_text(&d)
                )
            })?;
        if read
            .diagnostics
            .iter()
            .any(|d| d.severity == crate::diagnostic::Severity::Error)
        {
            return Err(format!(
                "body_replacement:syntax: {}",
                crate::study::diagnostics_text(&read.diagnostics)
            ));
        }
        let (ast, layout) = read.value;
        let (source_ast, source_layout) = if let Some(layout) = self.layout() {
            (self.program().clone(), layout.clone())
        } else {
            // The source reader uses Written names; decoded gold uses Slots.
            // Compare their written envelopes without mixing their AST nodes.
            let gold =
                crate::read::read_arclog(&self.sexp(registry), crate::layout::SourceFile::Arclog)
                    .map_err(|d| {
                    format!(
                        "body_replacement:source_representation: {}",
                        crate::study::diagnostics_text(&d)
                    )
                })?;
            if gold
                .diagnostics
                .iter()
                .any(|d| d.severity == crate::diagnostic::Severity::Error)
            {
                return Err(format!(
                    "body_replacement:source_representation: {}",
                    crate::study::diagnostics_text(&gold.diagnostics)
                ));
            }
            gold.value
        };
        // This is native parsed-source equality, including every scoped name
        // and source-order node, with positions/comments removed. It rejects a
        // no-op before importing any Written-name BODY into a Slot namespace.
        if source_text(&ast, &layout) == source_text(&source_ast, &source_layout) {
            return Err("body_replacement:unchanged: selected BODY is unchanged".into());
        }
        if source_shell(&ast, &layout, at)? != source_shell(&source_ast, &source_layout, at)? {
            return Err("body_replacement:outside_body_changed: parsed source outside the selected BODY differs from gold".into());
        }
        // Only a BODY-local candidate reaches the complete native checker.
        // A later-form failure caused by that BODY retains this distinct
        // whole-program reason; the suffix is never repaired.
        let candidate = StudyProgram::from_program(ast, Some(layout), registry)
            .map_err(|e| format!("body_replacement:whole_program_check: {e}"))?;
        let candidate = if self.layout().is_none() {
            // ProgramReader is the decoder's complete-stream grammar/binder,
            // without task/domain evaluation. It assigns the candidate's
            // declarations and reads the same native Slot namespace as gold.
            let decoded = candidate
                .decode_source(registry, settings)
                .map_err(|e| format!("body_replacement:candidate_representation: {e}"))?;
            let proof = decoded
                .representation_certificate(&candidate, registry, settings)
                .map_err(|e| format!("body_replacement:candidate_representation: {e}"))?;
            if proof["status"] != "complete" {
                return Err(format!(
                    "body_replacement:candidate_representation: {proof}"
                ));
            }
            decoded.preserve_gold_names(self, registry)
        } else {
            candidate
        };
        let replacement = body_at(&candidate, at)?;
        let valid = self.admit_body_replacement(point, replacement, origin, registry, settings)?;
        // At this boundary both BODY values use the actual gold namespace.
        // Retain the stronger whole-stream and native named-source proof.
        let restored = edit::replace_body(candidate.program(), at, &body_at(self, at)?)?;
        let restored = StudyProgram::from_program(restored, candidate.layout().cloned(), registry)
            .map_err(|e| format!("body_replacement:outside_body_changed: {e}"))?
            .preserve_gold_names(self, registry);
        if !same_stream(self, &restored, registry, settings)? {
            return Err("body_replacement:outside_body_changed: restored full ids/model/paths differ from gold".into());
        }
        if named_source_text(&restored, registry) != named_source_text(self, registry) {
            return Err("body_replacement:outside_body_changed: restored native named source differs from gold".into());
        }
        if !same_stream(valid.program(), &candidate, registry, settings)? {
            return Err("body_replacement:candidate_representation: native reconstruction differs from submitted full stream".into());
        }
        if let Some(supplied) = body_stream {
            check_body_stream(
                &candidate,
                &valid.point().body,
                supplied,
                registry,
                settings,
            )?;
        }
        Ok(valid)
    }

    pub(super) fn admit_body_replacement(
        &self,
        point: MutationPoint,
        replacement: Node<Body>,
        origin: Source,
        registry: &Registry,
        settings: &DecodeSettings,
    ) -> Result<ValidMutant, String> {
        if origin.revision.is_empty() || origin.task.is_empty() || origin.case.is_empty() {
            return Err("body_replacement:source: revision, task and case must be nonempty".into());
        }
        if !matches!(
            point.kind.as_str(),
            "Rule" | "Det" | "INIT input" | "INIT key"
        ) {
            return Err(
                "body_replacement:point: supported points are RULE, DET and INIT bodies".into(),
            );
        }
        if body_json(&body_at(self, &point.body)?) == body_json(&replacement) {
            return Err("body_replacement:unchanged: selected BODY is unchanged".into());
        }
        let ast = edit::replace_body(self.program(), &point.body, &replacement)?;
        // The same makers, interfaces, native checker, held DET interface,
        // vocabulary and name-binding checks as recorded atom admission.
        let certified = self
            .certify_mutation_program(ast, None, &point, registry, settings, None)
            .map_err(|e| format!("body_replacement:admission: {e}"))?;
        Ok(ValidMutant {
            spec: MutationSpec {
                source: Arc::clone(self.checked()),
                point,
                origin,
                edits: Vec::new(),
                certified,
                body_replacement: Some(replacement),
            },
        })
    }
}

/// The optional stream is a clause completion: after RULE/DET and its
/// proposers, through the unchanged SET/ONE marks and final model END,
/// excluding the engine's declared relation. Its token slots are those of
/// the whole candidate in the original prefix context, not a standalone body.
fn check_body_stream(
    program: &StudyProgram,
    at: &NodePath,
    supplied: &Value,
    registry: &Registry,
    settings: &DecodeSettings,
) -> Result<(), String> {
    if at.0.len() != 2 {
        return Err(
            "body_replacement:body_stream: only top-level RULE/DET streams are supported".into(),
        );
    }
    let top = NodePath::top(at.0[0].0);
    let clause = match &program.program().value().forms[at.0[0].0 as usize] {
        Form::Clause(c)
            if matches!(c.value().keyword, ClauseKeyword::Rule | ClauseKeyword::Det) =>
        {
            c.value()
        }
        _ => return Err("body_replacement:body_stream: INIT has no body decoder stream".into()),
    };
    let written = program
        .written_stream(registry, settings)
        .map_err(|d| crate::study::diagnostics_text(&[d]))?;
    let form = written
        .forms
        .iter()
        .find(|f| f.path == top)
        .ok_or("body_replacement:body_stream: missing written clause")?;
    let start = form.tokens.start + 1 + clause.proposers.len();
    let end = form
        .tokens
        .end
        .checked_sub(1)
        .ok_or("body_replacement:body_stream: missing declaration")?;
    if start >= end {
        return Err("body_replacement:body_stream: missing clause completion".into());
    }
    let stream = program.decode_stream(registry, settings)?;
    let expected = json!({"ids":&stream.ids[start..end],"model":&stream.model[start..end]});
    if supplied != &expected {
        return Err(format!(
            "body_replacement:body_stream: expected exact native clause completion ({} tokens)",
            end - start
        ));
    }
    Ok(())
}
