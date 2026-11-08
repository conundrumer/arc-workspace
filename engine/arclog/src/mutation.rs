//! Constructive, exact-K mutation of clauses in a checked gold AST.
//!
//! A draw uses only certified choices in its current context. Certification
//! has no task evaluation: it shares the resolver, binder, checker and writer.
//! Diagnostics from unavailable choices are counted, never silently repaired.
pub mod edit;
mod identity;
mod body_replacement;
pub use identity::RecordedIdentityFailure;
mod typed;
mod blocks;
mod stored_prune;
#[path = "study_replay.rs"] mod study_replay;

use std::collections::{BTreeMap, BTreeSet, VecDeque};
use std::sync::Arc;

use crate::check::safety::form_bodies;
use crate::check::{CheckCache, CheckedProgram};
use crate::eval::ir::atom_modes;
use crate::hash::StableHashSet;
use crate::program::path::{NodePath, NodeRef, node_at};
use crate::program::*;
use crate::registry::Registry;
use crate::resolver::registry_columns::typed_columns;
use crate::safety::{bound_labels, conjunct_label_set};
use crate::stream::DecodeSettings;
use crate::study::{StudyError, StudyProgram, StudyStream};
use crate::types::{FormTypes, ValueType, use_label};
use edit::AtomEdit;
use serde_json::{Value, json};

/// An immutable reference to the gold input, supplied by the study manifest.
#[derive(Clone, Debug)]
pub struct Source {
    pub revision: String,
    pub task: String,
    pub case: String,
}

/// One clause body, including the key/input clauses of compound forms.
/// The enclosing form and original body path are the address; no token offset.
#[derive(Clone, Debug)]
pub struct MutationPoint {
    source: Arc<CheckedProgram>,
    pub body: NodePath,
    pub clause: NodePath,
    pub atoms: Vec<NodePath>,
    pub kind: String,
}

/// A spec carries the certificate for its exact simultaneous edits. There is
/// deliberately no public unchecked constructor or mutable replacement field.
#[derive(Clone, Debug)]
pub struct MutationSpec {
    source: Arc<CheckedProgram>,
    point: MutationPoint,
    origin: Source,
    edits: Vec<AtomEdit>,
    certified: StudyProgram,
    body_replacement: Option<Node<Body>>,
}

#[derive(Clone, Debug)]
pub struct ValidMutant {
    spec: MutationSpec,
}

#[derive(Default, Debug)]
pub struct DrawStats {
    pub counts: BTreeMap<String, u64>,
    pub examples: BTreeMap<String, Vec<String>>,
}

impl DrawStats {
    fn count(&mut self, reason: &str) {
        *self.counts.entry(reason.into()).or_default() += 1;
    }

    /// Counts a refusal that is no check's, by the text of `message` before
    /// its first colon.
    fn refusal(&mut self, stage: &str, message: &str) {
        let reason = message
            .lines()
            .next()
            .unwrap_or("unknown")
            .split(':')
            .next()
            .unwrap_or("unknown")
            .to_string();
        self.refused(stage, &reason, message);
    }

    /// Counts a refusal by the engine check that gave it, rather than
    /// collapsing all invalid choices.
    fn check_refusal(&mut self, stage: &str, error: &StudyError) {
        match error.first_check_error() {
            Some((check, _)) => self.refused(stage, &format!("{check:?}"), &error.to_string()),
            None => self.refusal(stage, &error.to_string()),
        }
    }

    fn refused(&mut self, stage: &str, reason: &str, message: &str) {
        let key = format!("{stage}:{reason}");
        self.count(&key);
        let examples = self.examples.entry(key).or_default();
        if examples.len() < 3 {
            examples.push(message.into());
        }
    }

    pub fn json(&self) -> Value {
        json!({"counts": self.counts, "examples": self.examples})
    }
}

pub fn path_json(path: &NodePath) -> Value {
    json!(path.0.iter().map(|s| s.0).collect::<Vec<_>>())
}

impl StudyProgram {
    pub fn mutation_points(&self) -> Vec<MutationPoint> {
        let mut points = Vec::new();
        for (index, form) in self.program().value().forms.iter().enumerate() {
            if matches!(form, Form::Out(_)) {
                continue;
            }
            let top = NodePath::top(index as u32);
            for body in form_bodies(form) {
                let at = top.join(&body.at);
                let mut atoms = Vec::new();
                leaves(NodeRef::Body(body.body.value()), &at, &mut atoms);
                let clause = match body.head() {
                    Some((_, path)) => top.join(path),
                    None if matches!(form, Form::Clause(_)) => top.clone(),
                    None => at.clone(),
                };
                let kind = match form {
                    Form::Clause(c) => format!("{:?}", c.value().keyword),
                    Form::Instance(_) => if body.head().is_some() {
                        "INIT input"
                    } else {
                        "INIT key"
                    }
                    .into(),
                    Form::Choose(_) => "CHOOSE clause".into(),
                    Form::RigidDet(_) => "RIGID_DET clause".into(),
                    _ => "clause".into(),
                };
                points.push(MutationPoint {
                    source: Arc::clone(self.checked()),
                    body: at,
                    clause,
                    atoms,
                    kind,
                });
            }
        }
        points
    }

    /// Select complete valid K-edit assignments without replacement. The
    /// completion domain is a finite constraint search, not a chain of draws:
    /// branch-local uses may disappear together even when an intermediate
    /// deletion alone would be invalid. No partial assignment is a mutant.
    pub fn draw_specs(
        &self,
        point: &MutationPoint,
        k: usize,
        count: usize,
        seed: u64,
        operation: &str,
        origin: Source,
        settings: &DecodeSettings,
        registry: &Registry,
    ) -> Result<(Vec<MutationSpec>, DrawStats), String> {
        self.draw_order(
            point, k, count, seed, operation, origin, settings, registry, true,
        )
    }

    /// The new population samples source occurrences, independently of each
    /// site's number of argument variants. Include unsupported blocks in the
    /// inventory so a zero is a visible grammar shortfall, never a missing row.
    pub fn substitution_occurrences(&self, point: &MutationPoint) -> Result<Value, String> {
        if !Arc::ptr_eq(self.checked(), &point.source) {
            return Err("point_belongs_to_another_program".into());
        }
        let Some(NodeRef::Body(body)) = node_at(NodeRef::Program(self.program().value()), &point.body) else {
            return Err("point_is_not_a_body".into());
        };
        let occurrences = body.conjuncts.iter().enumerate().map(|(index, conjunct)| {
            let at = point.body.child(index as u32);
            let source = if conjunct.atom().is_some() || matches!(conjunct, Conjunct::Constraint(_)) {
                conjunct_json(conjunct)
            } else {
                json!({"node":match conjunct {
                    Conjunct::Or(_) => "or", Conjunct::If { .. } => "if",
                    Conjunct::All { .. } => "all", Conjunct::Not(_) => "not_form",
                    _ => "unsupported",
                }})
            };
            json!({"at":path_json(&at), "source":source,
                "supported":point.atoms.contains(&at)})
        }).collect::<Vec<_>>();
        Ok(json!({"schema":"substitution-occurrences-v1", "occurrences":occurrences}))
    }

    /// One occurrence gets its own quota and canonical finite search. This is
    /// additive: historical draw_specs scheduling and identities are unchanged.
    pub fn draw_substitutes_at(&self, point: &MutationPoint, at: &NodePath,
        count: usize, seed: u64, origin: Source, settings: &DecodeSettings,
        registry: &Registry) -> Result<(Vec<MutationSpec>, DrawStats), String> {
        if !Arc::ptr_eq(self.checked(), &point.source) {
            return Err("point_belongs_to_another_program".into());
        }
        if !point.atoms.contains(at) {
            let mut stats = DrawStats::default();
            stats.count("occurrence_unsupported_block");
            return Ok((Vec::new(), stats));
        }
        let mut scoped = point.clone();
        scoped.atoms = vec![at.clone()];
        let (specs, mut stats) = self.draw_specs(&scoped, 1, count, seed,
            "substitute", origin, settings, registry)?;
        if stats.counts.get("domain_primitive_values").copied().unwrap_or(0) == 0 {
            stats.count("occurrence_no_primitive_alternative");
        }
        Ok((specs, stats))
    }

    /// Added-only typed-interface population. Baseline primitives are removed
    /// before certification so old draws and old failures need no replay.
    pub fn draw_added_substitutes_at(&self, point:&MutationPoint, at:&NodePath,
        count:usize, seed:u64, origin:Source, settings:&DecodeSettings, registry:&Registry)
        -> Result<(Vec<MutationSpec>,DrawStats),String> {
        if !Arc::ptr_eq(self.checked(),&point.source) {return Err("point_belongs_to_another_program".into())}
        if !point.atoms.contains(at) {let mut s=DrawStats::default();s.count("occurrence_unsupported_block");return Ok((vec![],s))}
        let mut scoped=point.clone();scoped.atoms=vec![at.clone()];
        self.draw_profile(&scoped,1,count,seed,"substitute",origin,settings,registry,true,1)
    }

    /// Added-only whole-block substitutions, never historical or typed atoms.
    pub fn draw_block_substitutes_at(&self,point:&MutationPoint,at:&NodePath,
        count:usize,seed:u64,origin:Source,settings:&DecodeSettings,registry:&Registry)
        ->Result<(Vec<MutationSpec>,DrawStats),String> {
        if !Arc::ptr_eq(self.checked(),&point.source) {return Err("point_belongs_to_another_program".into())}
        if !blocks::is_site(self,point,at) {let mut s=DrawStats::default();s.count("occurrence_unsupported_block");return Ok((vec![],s))}
        let mut scoped=point.clone();scoped.atoms=vec![at.clone()];
        self.draw_profile(&scoped,1,count,seed,"substitute",origin,settings,registry,true,2)
    }

    /// Runtime audit on real programs: v5 and v6 use the same fair traversal
    /// and validity certificates. The reference retains v5's argument domain
    /// and separate zero bucket; only v6 returns production specs to callers.
    pub fn audit_draw_order(
        &self,
        point: &MutationPoint,
        k: usize,
        count: usize,
        seed: u64,
        operation: &str,
        origin: Source,
        settings: &DecodeSettings,
        registry: &Registry,
    ) -> Result<Value, String> {
        let (_, before) = self.draw_order(
            point,
            k,
            count,
            seed,
            operation,
            origin.clone(),
            settings,
            registry,
            false,
        )?;
        let (_, after) = self.draw_order(
            point, k, count, seed, operation, origin, settings, registry, true,
        )?;
        Ok(json!({"before_policy":"complete-domain-without-replacement-v5",
            "after_policy":"complete-domain-unique-text-gold-names-v7",
            "before":before.json(), "after":after.json()}))
    }

    fn draw_order(
        &self,
        point: &MutationPoint,
        k: usize,
        count: usize,
        seed: u64,
        operation: &str,
        origin: Source,
        settings: &DecodeSettings,
        registry: &Registry,
        expanded: bool,
    ) -> Result<(Vec<MutationSpec>, DrawStats), String> {
        self.draw_profile(point,k,count,seed,operation,origin,settings,registry,expanded,0)
    }

    fn draw_profile(&self, point:&MutationPoint, k:usize, count:usize, seed:u64,
        operation:&str, origin:Source, settings:&DecodeSettings, registry:&Registry,
        expanded:bool, added_profile:u8) -> Result<(Vec<MutationSpec>,DrawStats),String> {
        if !Arc::ptr_eq(self.checked(), &point.source) {
            return Err("point_belongs_to_another_program".into());
        }
        if k == 0 {
            return Err("K must be positive".into());
        }
        if !matches!(operation, "substitute" | "delete" | "mixed") {
            return Err("operation must be substitute, delete or mixed".into());
        }
        let mut rng = Rng(seed);
        {
            // Independent deterministic order per source clause, instead of
            // replaying the same short permutation at every clause.
            for byte in origin.task.bytes().chain(origin.case.bytes()) {
                rng.0 = rng
                    .0
                    .wrapping_mul(0x100000001b3)
                    .wrapping_add(u64::from(byte));
            }
            for step in &point.body.0 {
                rng.0 = rng.0.rotate_left(13) ^ u64::from(step.0);
            }
            rng.0 ^= k as u64;
        }
        let mut sites = Vec::new();
        let mut stats = DrawStats::default();
        for at in &point.atoms {
            let mut unique = BTreeSet::new();
            let mut values = Vec::new();
            let proposals = match added_profile {
                1=>typed::additions(self,at,registry,&mut stats)?,
                2=>blocks::alternatives(self,at,registry,&mut stats)?,
                _=>alternatives(self, at, operation, registry, expanded)?,
            };
            for (replacement, kind) in proposals {
                let key = replacement
                    .as_ref()
                    .map(conjunct_json)
                    .unwrap_or(Value::Null)
                    .to_string();
                if unique.insert(key) {
                    stats.count(&format!("domain_primitive_kind:{kind}"));
                    values.push(AtomEdit {
                        at: at.clone(),
                        replacement,
                        kind: if kind.starts_with("argument_") {
                            "argument"
                        } else if kind.starts_with("block_") { "block" } else {
                            kind
                        },
                        choice_kind: kind,
                    });
                } else {
                    stats.count("domain_duplicate_values_removed");
                }
            }
            rng.shuffle(&mut values);
            if !values.is_empty() {
                sites.push(values);
            }
        }
        rng.shuffle(&mut sites);
        stats
            .counts
            .insert("domain_sites".into(), sites.len() as u64);
        stats.counts.insert(
            "domain_primitive_values".into(),
            sites.iter().map(|v| v.len() as u64).sum(),
        );
        let mut domain = CompletionDomain {
            gold: self,
            point,
            origin,
            settings,
            registry,
            sites,
            cache: CheckCache::over(self.mutation_check_base(registry)?),
            stats,
            output: Vec::new(),
            texts: StableHashSet::default(),
            requested: count,
            deletion_only: operation == "delete",
            expanded,
            nodes: 0,
            stopped: false,
        };
        domain.fair_visit(k, &mut rng)?;
        if domain.stopped {
            domain.stats.count("domain_search_stopped:NodeCap");
        } else if domain.output.len() < count {
            domain.stats.count("domain_exhausted");
        }
        Ok((domain.output, domain.stats))
    }

    /// Construct an immutable certified spec from this gold handle. Recheck
    /// its held-value interface at this public admission boundary.
    pub fn construct(&self, spec: &MutationSpec) -> Result<ValidMutant, &'static str> {
        if !Arc::ptr_eq(self.checked(), &spec.source) {
            return Err("spec_belongs_to_another_program");
        }
        self.checked().check_held_det_interfaces(spec.certified.checked())
            .map_err(|_| "mutator_held_det_interface")?;
        Ok(ValidMutant { spec: spec.clone() })
    }
}

/// A randomized ordering of the finite completion domain. Site subsets have
/// one canonical traversal and each site's values are unique; consequently a
/// returned text can never be drawn twice; distinct edits that write one text
/// are one candidate. Search exclusions are domain
/// constraints, recorded separately from construction failures (which are bugs).
struct CompletionDomain<'a> {
    gold: &'a StudyProgram,
    point: &'a MutationPoint,
    origin: Source,
    settings: &'a DecodeSettings,
    registry: &'a Registry,
    sites: Vec<Vec<AtomEdit>>,
    cache: CheckCache,
    stats: DrawStats,
    output: Vec<MutationSpec>,
    /// Exact written candidates, not hashes, edits or paths. Discarding one
    /// does not fill the requested count: traversal continues for a new text.
    texts: StableHashSet<String>,
    requested: usize,
    deletion_only: bool,
    expanded: bool,
    /// The search nodes visited, under `settings.mutation_node_cap`.
    nodes: u64,
    stopped: bool,
}

/// A resumable canonical suffix search. Each root owns disjoint assignments:
/// its first edited site is fixed and later sites have strictly larger indexes.
struct AssignmentCursor {
    edits: Vec<AtomEdit>,
    frames: Vec<ChoiceFrame>,
}

struct ChoiceFrame {
    site: usize,
    value: usize,
    remaining: usize,
}

impl CompletionDomain<'_> {
    fn fair_visit(&mut self, k: usize, rng: &mut Rng) -> Result<(), String> {
        // V6 schedules one argument bucket: every distinct variable or zero
        // replacement gets one ticket within it. Giving all variables one
        // category ticket against zero's category overweighted that literal.
        // Resume suffix searches so a prefix is not one DFS subtree. V5 is
        // retained only as the real-data audit's reference policy.
        let mut roots: BTreeMap<&str, Vec<AssignmentCursor>> = BTreeMap::new();
        for (site, values) in self.sites.iter().enumerate() {
            if self.sites.len() - site < k {
                continue;
            }
            for edit in values {
                if self.deletion_only {
                    let ast = edit::apply(self.gold.program(), std::slice::from_ref(edit))?;
                    if !crate::study::interfaces_hold(
                        &ast.value().forms[self.point.body.0[0].0 as usize],
                    ) {
                        self.stats.count("domain_pruned:required_column_binding");
                        continue;
                    }
                }
                roots
                    .entry(if self.expanded { edit.kind } else { edit.choice_kind })
                    .or_default()
                    .push(AssignmentCursor {
                        edits: vec![edit.clone()],
                        frames: vec![ChoiceFrame {
                            site: site + 1,
                            value: 0,
                            remaining: k - 1,
                        }],
                    });
            }
        }
        let mut kinds = roots
            .into_iter()
            .map(|(kind, mut roots)| {
                rng.shuffle(&mut roots);
                (kind, VecDeque::from(roots))
            })
            .collect::<Vec<_>>();
        rng.shuffle(&mut kinds);
        let mut kinds = VecDeque::from(kinds);
        while let Some((kind, mut roots)) = kinds.pop_front() {
            if self.output.len() >= self.requested || self.stopped {
                break;
            }
            let before = self.output.len();
            // Find one certified completion for this kind, or prove the
            // bucket exhausted. Failures are search constraints, not draws.
            while let Some(mut cursor) = roots.pop_front() {
                while self.output.len() == before && !cursor.frames.is_empty() {
                    if self.nodes >= self.settings.mutation_node_cap {
                        self.stopped = true;
                        return Ok(());
                    }
                    self.nodes += 1;
                    self.stats.count("domain_search_nodes");
                    let frame = cursor.frames.last_mut().unwrap();
                    if frame.remaining == 0 {
                        cursor.frames.pop();
                        self.certify(&cursor.edits)?;
                        cursor.edits.pop();
                        continue;
                    }
                    if self.sites.len().saturating_sub(frame.site) < frame.remaining {
                        cursor.frames.pop();
                        cursor.edits.pop();
                        continue;
                    }
                    if frame.value == self.sites[frame.site].len() {
                        frame.site += 1;
                        frame.value = 0;
                        continue;
                    }
                    let site = frame.site;
                    let remaining = frame.remaining;
                    let edit = self.sites[site][frame.value].clone();
                    frame.value += 1;
                    cursor.edits.push(edit);
                    if self.deletion_only {
                        let ast = edit::apply(self.gold.program(), &cursor.edits)?;
                        if !crate::study::interfaces_hold(
                            &ast.value().forms[self.point.body.0[0].0 as usize],
                        ) {
                            self.stats.count("domain_pruned:required_column_binding");
                            cursor.edits.pop();
                            continue;
                        }
                    }
                    cursor.frames.push(ChoiceFrame {
                        site: site + 1,
                        value: 0,
                        remaining: remaining - 1,
                    });
                }
                if !cursor.frames.is_empty() {
                    roots.push_back(cursor);
                }
                if self.output.len() > before {
                    break;
                }
            }
            if !roots.is_empty() {
                kinds.push_back((kind, roots));
            }
        }
        Ok(())
    }

    fn certify(&mut self, edits: &[AtomEdit]) -> Result<(), String> {
        let top = self.point.body.0[0].0 as usize;
        self.stats.count("domain_complete_assignments");
        let ast = edit::apply(self.gold.program(), edits)?;
        if !crate::study::interfaces_hold(&ast.value().forms[top]) {
            self.stats
                .count("domain_interface_excluded:exports_changed");
            return Ok(());
        }
        if !declared_in_scopes(NodeRef::from(&ast.value().forms[top])) {
            self.stats
                .count("domain_declaration_excluded:missing_maker");
            return Ok(());
        }
        if !named_bindings_hold(&ast.value().forms[top], &NodePath::top(top as u32), self.gold.layout()) {
            self.stats.count("domain_binding_excluded:shadowed_name");
            return Ok(());
        }
        // An edit can change an INIT parameter's inferred type and the
        // binding modes available in sibling/nested bodies. Gold's types
        // are not a safety certificate for this assignment. Resolve and
        // infer the complete candidate before the engine's whole-program
        // safety walk; only that certificate enters the selectable domain.
        let checked = match StudyProgram::from_program_cached(
            ast,
            edit::layout(self.gold.layout(), edits),
            self.registry,
            &mut self.cache,
        ) {
            Ok(checked) => checked,
            Err(error) => {
                self.stats.check_refusal("domain_check_excluded", &error);
                return Ok(());
            }
        };
        let checked = checked.preserve_gold_names(self.gold, self.registry);
        if let Err(error) = self.gold.checked().check_held_det_interfaces(checked.checked()) {
            self.stats.refusal("domain_held_det_excluded", &error.to_string());
            return Ok(());
        }
        if let Err(error) = checked.decode_stream(self.registry, self.settings) {
            self.stats.refusal("domain_stream_excluded", &error);
            return Ok(());
        }
        if let Err(error) = checked.check_preserved_name_binding(self.registry, self.settings, &mut self.cache) {
            self.stats.check_refusal("domain_written_binding_excluded", &error);
            return Ok(());
        }
        // Domain failures do not fill a draw or quota: the existing suffix
        // search continues exactly as for every other certification refusal.
        let pruned = match crate::check::static_prune::edited_matches(checked.checked(),self.registry,edits) {
            Ok(matches)=>matches,
            Err(error)=> {self.stats.refusal("domain_static_prune_unavailable",&error);Vec::new()}
        };
        if !pruned.is_empty() {
            self.stats.count("domain_static_prune_candidates_excluded");
            for found in pruned {
                self.stats.count(&format!("domain_static_prune_excluded:{}:{}",found.verdict.class.name(),found.verdict.rule));
            }
            return Ok(());
        }
        if !self.texts.insert(checked.sexp(self.registry)) {
            self.stats.count("domain_text_duplicate_excluded");
            return Ok(());
        }
        // Only now does an assignment belong to the selectable domain.
        let mut canonical = edits.to_vec();
        canonical.sort_by(|a, b| a.at.cmp(&b.at));
        self.output.push(MutationSpec {
            source: Arc::clone(self.gold.checked()),
            point: self.point.clone(),
            origin: self.origin.clone(),
            edits: canonical,
            certified: checked,
            body_replacement: None,
        });
        self.stats.count("specs_drawn");
        if let Some(edit) = edits.first() {
            self.stats
                .count(&format!("drawn_root_kind:{}", edit.choice_kind));
        }
        for edit in edits {
            self.stats
                .count(&format!("drawn_edit_kind:{}", edit.choice_kind));
        }
        Ok(())
    }
}

/// The AST reader gives each fresh/key occurrence an id. Deleting its only
/// declaration must remove its remaining uses too; positive joins may bind
/// values, but do not create a new syntactic declaration.
struct MissingDeclaration {
    label: LabelId,
    scope: NodePath,
    at: NodePath,
    required_by: &'static str,
}

/// The draw and recorded-admission paths share this maker check. Keep the
/// exact failing use so a refusal identifies a label, not an unrelated read.
fn missing_declaration(root: NodeRef<'_>, at: &NodePath) -> Option<MissingDeclaration> {
    fn gather(
        node: NodeRef<'_>, at: &NodePath,
        uses: &mut Vec<(LabelUse, NodePath, &'static str)>,
        nested: &mut Option<MissingDeclaration>,
    ) {
        match node {
            NodeRef::Label(label) => uses.push((*label, at.clone(), "label use")),
            NodeRef::Clause(c) => {
                for column in c.columns.iter() {
                    uses.push((LabelUse::Join(column.label), at.clone(),
                        "retained clause column"));
                }
            }
            NodeRef::Conjunct(Conjunct::Constraint(c)) => {
                uses.push((c.first.into(), at.clone(), "constraint first operand"));
                if let Some(second) = constraint_second(c) {
                    uses.push((second.into(), at.clone(), "constraint second operand"));
                }
            }
            _ => {}
        }
        for (i, child) in node.children().into_iter().enumerate() {
            let child_at = at.child(i as u32);
            if crate::program::canonical::opens_scope(node, i, child) {
                if nested.is_none() { *nested = missing_declaration(child, &child_at); }
            } else {
                gather(child, &child_at, uses, nested);
            }
        }
    }
    let mut uses = Vec::new();
    let mut nested = None;
    gather(root, at, &mut uses, &mut nested);
    let makers: StableHashSet<_> = uses.iter().filter_map(|(used, _, _)| match used {
        LabelUse::Fresh(label) | LabelUse::Key(label) => Some(*label),
        _ => None,
    }).collect();
    nested.or_else(|| uses.into_iter().find_map(|(used, use_at, required_by)| match used {
        LabelUse::Join(label) if !makers.contains(&label) => Some(MissingDeclaration {
            label, scope: at.clone(), at: use_at, required_by,
        }),
        _ => None,
    }))
}

fn declared_in_scopes(root: NodeRef<'_>) -> bool {
    missing_declaration(root, &NodePath::default()).is_none()
}

/// A named source can shadow a key/candidate label with a local maker in
/// an input or NEVER. The numeric AST can express a join to the hidden
/// outer label, but that join is not a choice at this named source point:
/// the reader would resolve its spelling to the local maker. Check the
/// complete assignment so deleting that local maker can expose the outer
/// name again. Within a body the reader already requires unique makers.
fn named_bindings_hold(
    form: &Form,
    top: &NodePath,
    layout: Option<&crate::layout::Layout>,
) -> bool {
    let Some(names) = layout.and_then(|l| l.node(crate::layout::SourceFile::Arclog, top)) else {
        return true;
    };
    let name = |label| {
        names
            .label_names
            .iter()
            .find(|(id, _)| *id == label)
            .map(|(_, name)| name.as_ref())
    };
    for body in form_bodies(form) {
        let mut made = Vec::new();
        let mut joined = Vec::new();
        crate::safety::each_label_use_at(
            NodeRef::Body(body.body.value()),
            &body.at,
            &mut |_, use_| match use_ {
                LabelUse::Fresh(id) | LabelUse::Key(id) => made.push(id),
                LabelUse::Join(id) => joined.push(id),
                LabelUse::Zero => {}
            },
        );
        for id in joined {
            if let Some(spelling) = name(id) {
                if made
                    .iter()
                    .any(|local| *local != id && name(*local) == Some(spelling))
                {
                    return false;
                }
            }
        }
    }
    true
}

impl MutationSpec {
    pub fn identity(&self) -> Value {
        if let Some(body)=&self.body_replacement {
            return json!({"source":{"revision":self.origin.revision,"task":self.origin.task,"case":self.origin.case},
                "body":path_json(&self.point.body),"clause":path_json(&self.point.clause),
                "edits":[{"at":path_json(&self.point.body),"kind":"replace_body","replacement":body_json(body)}]})
        }
        json!({"source": {"revision": self.origin.revision, "task": self.origin.task, "case": self.origin.case},
               "clause": path_json(&self.point.clause), "body": path_json(&self.point.body),
               "edits": self.edits.iter().map(|e| json!({"at": path_json(&e.at), "kind":e.kind,
                   "replacement":e.replacement.as_ref().map(conjunct_json)})).collect::<Vec<_>>()})
    }

    pub fn k(&self) -> usize {
        if self.body_replacement.is_some() {1} else {self.edits.len()}
    }
}

impl ValidMutant {
    pub fn program(&self) -> &StudyProgram {
        &self.spec.certified
    }
    pub fn gold(&self) -> &Arc<CheckedProgram> {
        &self.spec.source
    }
    pub fn point(&self) -> &MutationPoint {
        &self.spec.point
    }
    pub fn identity(&self) -> Value {
        self.spec.identity()
    }
    pub fn k(&self) -> usize {
        self.spec.k()
    }
    /// The same changed-site conclusion that excludes a sampled candidate.
    /// Historical identities remain rehydratable so readers can omit them;
    /// this report never evaluates a relation or assigns a grade.
    pub fn static_prune_json(&self, registry: &Registry, survey: bool) -> Result<Value,String> {
        let body_edits;
        let edits=if let Some(body)=&self.spec.body_replacement {
            body_edits=body.value().conjuncts.iter().enumerate().map(|(i,c)|AtomEdit{
                at:self.point().body.child(i as u32),replacement:Some(c.clone()),kind:"replace_body",choice_kind:"replace_body"}).collect::<Vec<_>>();
            &body_edits
        } else {&self.spec.edits};
        let matches=crate::check::static_prune::edited_matches(self.program().checked(),registry,edits)?;
        let mut report=crate::check::static_prune::report(&matches);
        if let Some(rows)=report["matches"].as_array_mut() {
            for (row,found) in rows.iter_mut().zip(&matches) {
                row["original_atom_paths"]=json!(self.spec.edits.iter().filter(|e|e.replacement.is_some()).filter_map(|e| {
                    let after=edit::mapped(&e.at,&self.spec.edits)?;
                    (found.path.0.starts_with(&after.0)||after.0.starts_with(&found.path.0)).then(||path_json(&e.at))
                }).collect::<Vec<_>>());
            }
        }
        report["scope"]="surviving changed sites; native simultaneous-deletion path mapping".into();
        if self.spec.body_replacement.is_some() {
            report["edit_unit"]="body".into();
            report["original_body_path"]=path_json(&self.point().body);
        }
        if survey {
            let top=self.point().body.0[0].0 as usize;
            let path=NodePath::top(top as u32);
            report["survey"]=json!({
                "gold":crate::study::features::canonical_clause(&self.gold().program.program.value().forms[top],&path),
                "candidate":crate::study::features::canonical_clause(&self.program().program().value().forms[top],&path),
                "contract":"existing native canonical form; measurement only, no extra sampling rejection"});
        }
        Ok(report)
    }
    /// Exact, source-order evidence that only the requested original atoms
    /// changed. This compares AST values directly, without any fingerprint.
    /// Every original node is either mapped exactly, deleted, or belongs
    /// to a replaced subtree. Replacement descendants have no guessed match.
    pub fn source_paths(&self) -> Value {
        if self.spec.body_replacement.is_some() {
            return edit::body_source_paths(&self.gold().program.program,&self.point().body)
        }
        edit::source_paths(&self.gold().program.program, &self.spec.edits)
    }

    pub fn audit(&self) -> Result<Value, String> {
        if self.spec.body_replacement.is_some() {
            return Ok(json!({"edit_unit":"body","changed_bodies":1,"outside_body_unchanged":true,
                "outside_atoms_unchanged":true,"changed_paths":[path_json(&self.point().body)],
                "certificate":"native editor shell and full writer/stream equality at construction"}))
        }
        let gold = NodeRef::Program(self.spec.source.program.program.value());
        let mutant = NodeRef::Program(self.program().program().value());
        let mut gold_atoms = Vec::new();
        leaves(gold, &NodePath::default(), &mut gold_atoms);
        gold_atoms.extend(self.spec.edits.iter().map(|e|e.at.clone()));
        gold_atoms.sort();gold_atoms.dedup();
        let mut untouched = 0;
        let mut changed = 0;
        for path in gold_atoms {
            if self.spec.edits.iter().any(|e|path!=e.at && path.0.starts_with(&e.at.0)) {continue}
            let Some(NodeRef::Conjunct(before)) = node_at(gold, &path) else {
                continue;
            };
            let selected = self.spec.edits.iter().find(|e| e.at == path);
            match (edit::mapped(&path, &self.spec.edits), selected) {
                (None, Some(e)) if e.replacement.is_none() => changed += 1,
                (Some(after_path), selected) => {
                    let Some(NodeRef::Conjunct(after)) = node_at(mutant, &after_path) else {
                        return Err("audit_missing_atom".into());
                    };
                    let same = conjunct_json(before) == conjunct_json(after);
                    if selected.is_some() {
                        if same {
                            return Err("audit_selected_atom_unchanged".into());
                        }
                        changed += 1;
                    } else {
                        if !same {
                            return Err("audit_unselected_atom_changed".into());
                        }
                        untouched += 1;
                    }
                }
                _ => return Err("audit_unselected_atom_deleted".into()),
            }
        }
        if changed != self.k() {
            return Err("audit_K_mismatch".into());
        }
        Ok(
            json!({"changed_atoms":changed,"untouched_atoms":untouched,"outside_atoms_unchanged":true,
                  "changed_paths":self.spec.edits.iter().map(|e|path_json(&e.at)).collect::<Vec<_>>()}),
        )
    }
    pub fn decode_stream(
        &self,
        registry: &Registry,
        settings: &DecodeSettings,
    ) -> Result<StudyStream, String> {
        self.program().decode_stream(registry, settings)
    }
}

fn leaves(node: NodeRef<'_>, at: &NodePath, result: &mut Vec<NodePath>) {
    if node.atom().is_some() || matches!(node, NodeRef::Conjunct(Conjunct::Constraint(_))) {
        result.push(at.clone());
        return;
    }
    for (i, child) in node.children().into_iter().enumerate() {
        leaves(child, &at.child(i as u32), result);
    }
}

fn scope_types<'a>(program: &'a StudyProgram, at: &NodePath) -> Option<&'a FormTypes> {
    (1..=at.0.len())
        .rev()
        .find_map(|n| program.checked().types.form(&NodePath(at.0[..n].into())))
}

/// Labels bound before this atom in its actual nested body, not every label
/// in the top-level form. Branch locals cannot leak into a sibling domain.
fn available(program: &StudyProgram, at: &NodePath, registry: &Registry) -> StableHashSet<LabelId> {
    let top = NodePath(at.0[..1].into());
    let form = &program.program().value().forms[at.0[0].0 as usize];
    let Some(types) = scope_types(program, at) else {
        return Default::default();
    };
    for root in form_bodies(form) {
        let path = top.join(&root.at);
        if at.0.starts_with(&path.0) {
            let initial = root.given.iter().copied().collect();
            return before(
                root.body.value(),
                &path,
                at,
                &initial,
                &root.outside(),
                types,
                registry,
            );
        }
    }
    Default::default()
}

fn before(
    body: &Body,
    path: &NodePath,
    target: &NodePath,
    given: &StableHashSet<LabelId>,
    outside: &StableHashSet<LabelId>,
    types: &FormTypes,
    registry: &Registry,
) -> StableHashSet<LabelId> {
    let Some(step) = target.0.get(path.0.len()) else {
        return given.clone();
    };
    let index = step.0 as usize;
    if index >= body.conjuncts.len() {
        return Default::default();
    }
    let prefix = body.conjuncts[..index].iter().collect::<Vec<_>>();
    let bound = bound_labels(
        &prefix,
        given,
        outside,
        &|a| atom_modes(registry, a),
        &|l| types.label(l).cloned(),
    );
    let at = path.child(step.0);
    if &at == target {
        return bound;
    }
    let mut around = outside.clone();
    for (i, conjunct) in body.conjuncts.iter().enumerate() {
        if i != index {
            around.extend(conjunct_label_set(conjunct));
        }
    }
    nested_before(
        &body.conjuncts[index],
        &at,
        target,
        &bound,
        &around,
        types,
        registry,
    )
}

fn nested_before(
    conjunct: &Conjunct,
    at: &NodePath,
    target: &NodePath,
    bound: &StableHashSet<LabelId>,
    outside: &StableHashSet<LabelId>,
    types: &FormTypes,
    registry: &Registry,
) -> StableHashSet<LabelId> {
    if at == target {
        return bound.clone();
    }
    let Some(step) = target.0.get(at.0.len()) else {
        return bound.clone();
    };
    let child = at.child(step.0);
    match conjunct {
        Conjunct::Or(branches) => branches
            .get(step.0 as usize)
            .map(|b| before(b.value(), &child, target, bound, outside, types, registry))
            .unwrap_or_default(),
        Conjunct::If {
            test,
            then,
            otherwise,
        } => {
            let mut given = bound.clone();
            if step.0 == 1 {
                given = bound_labels(
                    &test.value().conjuncts.iter().collect::<Vec<_>>(),
                    bound,
                    outside,
                    &|a| atom_modes(registry, a),
                    &|l| types.label(l).cloned(),
                );
            }
            let b = match step.0 {
                0 => test,
                1 => then,
                _ => otherwise,
            };
            before(b.value(), &child, target, &given, outside, types, registry)
        }
        Conjunct::All { domain, body } => {
            let given = if step.0 == 1 {
                bound_labels(
                    &domain.value().conjuncts.iter().collect::<Vec<_>>(),
                    bound,
                    outside,
                    &|a| atom_modes(registry, a),
                    &|l| types.label(l).cloned(),
                )
            } else {
                bound.clone()
            };
            before(
                if step.0 == 0 {
                    domain.value()
                } else {
                    body.value()
                },
                &child,
                target,
                &given,
                outside,
                types,
                registry,
            )
        }
        Conjunct::Not(Negated::Form(inner)) => {
            nested_before(inner, &child, target, bound, outside, types, registry)
        }
        _ => bound.clone(),
    }
}

fn alternatives(
    program: &StudyProgram,
    at: &NodePath,
    operation: &str,
    registry: &Registry,
    rich: bool,
) -> Result<Vec<(Option<Conjunct>, &'static str)>, String> {
    let Some(NodeRef::Conjunct(old)) = node_at(NodeRef::Program(program.program().value()), at)
    else {
        return Ok(Vec::new());
    };
    let Some(types) = scope_types(program, at) else {
        return Ok(Vec::new());
    };
    let bound = available(program, at, registry);
    let native_sites = (rich && operation != "delete" && old.atom().is_some())
        .then(|| program.typed_sites(registry)).transpose()?;
    let mut result = Vec::new();
    if operation != "substitute" {
        let parent = NodePath(at.0[..at.0.len() - 1].into());
        if matches!(
            node_at(NodeRef::Program(program.program().value()), &parent),
            Some(NodeRef::Body(_))
        ) {
            result.push((None, "delete"));
        }
    }
    if operation == "delete" {
        return Ok(result);
    }
    if let Some(atom) = old.atom() {
        let value = atom.value();
        if let Some(columns) = typed_columns(registry, &value.relation) {
            // Identical column types/names and binding modes preserve the
            // interface. Full check certification handles frame/type rules.
            let mut names = registry.names().collect::<Vec<_>>();
            names.sort_by(|a, b| a.0.cmp(&b.0));
            for name in names {
                // A proposer can have the same columns and no modes, but
                // is legal only in DET, never as a body relation.
                if registry.algebra_relation(name).is_none() {
                    continue;
                }
                let relation = RelationRef::Lib(name.clone());
                if relation == value.relation {
                    continue;
                }
                if typed_columns(registry, &relation) == Some(columns) {
                    let replacement = Atom {
                        relation,
                        sites: value.sites.clone(),
                    };
                    if atom_modes(registry, &replacement) == atom_modes(registry, value) {
                        result.push((Some(with_atom(old, replacement)), "relation"));
                    }
                }
            }
        }
        // Program relations use the checked types of an existing read with
        // the same site schema. Only earlier declarations with no dependency
        // on this form are eligible, so a replacement cannot create a cycle.
        if atom_modes(registry, value).is_empty() {
            if let Some(shape) = atom_shape(value, types) {
                let top = NodePath(at.0[..1].into());
                let target_nodes = program.checked().program.nodes_of(&top);
                let mut templates = Vec::new();
                for i in 0..at.0[0].0 {
                    let form = &program.program().value().forms[i as usize];
                    relation_templates(
                        program,
                        NodeRef::from(form),
                        &NodePath::top(i),
                        &mut templates,
                    );
                }
                let mut relations = Vec::new();
                for (relation, candidate_shape, read_at) in templates {
                    if relation == value.relation
                        || candidate_shape != shape
                        || relations.contains(&relation)
                    {
                        continue;
                    }
                    let Some(crate::resolver::Resolution::Node(node)) =
                        program.checked().program.resolution(&read_at)
                    else {
                        continue;
                    };
                    if program
                        .checked()
                        .program
                        .forms_of(*node)
                        .iter()
                        .any(|p| p.0.first().is_some_and(|s| s.0 >= at.0[0].0))
                    {
                        continue;
                    }
                    let reached = program.checked().program.graph.reached(*node);
                    if target_nodes.iter().any(|n| reached[n.0 as usize]) {
                        continue;
                    }
                    relations.push(relation.clone());
                    result.push((
                        Some(with_atom(
                            old,
                            Atom {
                                relation,
                                sites: value.sites.clone(),
                            },
                        )),
                        "relation",
                    ));
                }
            }
        }
        let mut labels = bound.iter().copied().collect::<Vec<_>>();
        labels.sort_by_key(|l| l.0);
        for (site_index, site) in value.sites.iter().enumerate() {
            let mut replacements = Vec::new();
            let record = program
                .checked()
                .program
                .column_position(&at.child(site_index as u32))
                .is_none();
            site_variants(
                site,
                types,
                &labels,
                record,
                &mut replacements,
                rich,
                &|path| {
                    let site = native_sites.as_ref().and_then(|s| s.columns.get(path))
                        .ok_or_else(|| format!("missing native argument site at {path:?}"))?;
                    site.ty.clone().ok_or_else(|| format!("missing native argument column type at {path:?} in scope {:?}", site.scope_path))
                },
                &at.child(site_index as u32),
            )?;
            for (site, choice_kind) in replacements {
                let mut sites = value.sites.to_vec();
                sites[site_index] = site;
                result.push((
                    Some(with_atom(
                        old,
                        Atom {
                            sites: sites.into(),
                            ..value.clone()
                        },
                    )),
                    choice_kind,
                ));
            }
            if rich {
                site_declarations(site, &mut labels);
            }
        }
    } else if let Conjunct::Constraint(c) = old {
        let second = constraint_second(c);
        let joins = !c.first.fresh && second.is_none_or(|l| !l.fresh);
        let all_bound =
            bound.contains(&c.first.label) && second.is_none_or(|l| bound.contains(&l.label));
        if joins && all_bound {
            for op in [
                ConstraintOp::Eq,
                ConstraintOp::Ne,
                ConstraintOp::Lt,
                ConstraintOp::Le,
                ConstraintOp::Gt,
                ConstraintOp::Ge,
            ] {
                if op == c.op {
                    continue;
                }
                if matches!(
                    op,
                    ConstraintOp::Lt | ConstraintOp::Le | ConstraintOp::Gt | ConstraintOp::Ge
                ) && !types
                    .label(c.first.label)
                    .is_some_and(ValueType::admits_order)
                {
                    continue;
                }
                result.push((
                    Some(Conjunct::Constraint(Constraint { op, ..*c })),
                    "comparison",
                ));
            }
        }
    }
    Ok(result)
}

fn with_atom(old: &Conjunct, atom: Atom) -> Conjunct {
    match old {
        Conjunct::Not(Negated::Atom(_)) => Conjunct::Not(Negated::Atom(Node::new(atom))),
        _ => Conjunct::Atom(Node::new(atom)),
    }
}

#[derive(Clone, PartialEq, Eq)]
struct SiteShape(ColumnName, Vec<ArgShape>);
#[derive(Clone, PartialEq, Eq)]
enum ArgShape {
    Label(Option<ColumnName>, ValueType),
    Field(SiteShape),
}

fn atom_shape(atom: &Atom, types: &FormTypes) -> Option<Vec<SiteShape>> {
    fn site(s: &Site, types: &FormTypes) -> Option<SiteShape> {
        let args = s
            .value
            .args
            .iter()
            .map(|a| match a {
                SiteArg::Field(s) => site(s, types).map(ArgShape::Field),
                SiteArg::Label(l) => {
                    Some(ArgShape::Label(None, types.label(use_label(*l)?)?.clone()))
                }
                SiteArg::NamedLabel { name, label } => Some(ArgShape::Label(
                    Some(name.clone()),
                    types.label(use_label(*label)?)?.clone(),
                )),
            })
            .collect::<Option<Vec<_>>>()?;
        Some(SiteShape(s.column.clone(), args))
    }
    atom.sites.iter().map(|s| site(s, types)).collect()
}

fn relation_templates(
    program: &StudyProgram,
    node: NodeRef<'_>,
    path: &NodePath,
    out: &mut Vec<(RelationRef, Vec<SiteShape>, NodePath)>,
) {
    if let Some(atom) = node.atom() {
        if matches!(
            atom.relation,
            RelationRef::Declared(_) | RelationRef::Output(_)
        ) {
            if let Some(shape) = scope_types(program, path).and_then(|ty| atom_shape(atom, ty)) {
                out.push((atom.relation.clone(), shape, path.clone()));
            }
        }
        return;
    }
    for (i, child) in node.children().into_iter().enumerate() {
        relation_templates(program, child, &path.child(i as u32), out);
    }
}

fn site_declarations(site: &Site, out: &mut Vec<LabelId>) {
    for arg in site.value.args.iter() {
        argument_declarations(arg, out);
    }
}

fn argument_declarations(arg: &SiteArg, out: &mut Vec<LabelId>) {
    match arg {
        SiteArg::Label(LabelUse::Fresh(l) | LabelUse::Key(l))
        | SiteArg::NamedLabel { label: LabelUse::Fresh(l) | LabelUse::Key(l), .. } => {
            if !out.contains(l) {
                out.push(*l);
            }
        }
        SiteArg::Field(s) => site_declarations(s, out),
        _ => {}
    }
}

fn site_variants(
    site: &Site,
    types: &FormTypes,
    bound: &[LabelId],
    record: bool,
    result: &mut Vec<(Site, &'static str)>,
    rich: bool,
    expected_type: &dyn Fn(&NodePath) -> Result<ValueType, String>,
    at: &NodePath,
) -> Result<(), String> {
    let mut local = bound.to_vec();
    for (index, arg) in site.value.args.iter().enumerate() {
        let mut args = Vec::new();
        match arg {
            SiteArg::Label(label @ (LabelUse::Join(_) | LabelUse::Zero))
            | SiteArg::NamedLabel {
                label: label @ (LabelUse::Join(_) | LabelUse::Zero),
                ..
            } if rich || matches!(label, LabelUse::Join(_)) => {
                let old = use_label(*label);
                // Resolve named record fields at their own scalar position,
                // not the containing record's or its old label's narrow type.
                // Whole-assignment inference certifies conditional rules.
                let expected = if rich {
                    Some(expected_type(&at.child(index as u32))?)
                } else {
                    old.and_then(|l| types.label(l).cloned())
                };
                let replacement = |label| match arg {
                    SiteArg::NamedLabel { name, .. } if record => SiteArg::Field(Site {
                        column: name.clone(),
                        value: SiteValue {
                            args: Arc::from([SiteArg::Label(label)]),
                        },
                    }),
                    _ => SiteArg::Label(label),
                };
                for label in &local {
                    let compatible = types
                        .label(*label)
                        .zip(expected.as_ref())
                        .is_some_and(|(a, b)| if rich { a.meets(b) } else { a == b });
                    if Some(*label) != old && compatible {
                        args.push((replacement(LabelUse::Join(*label)), "argument_variable"));
                    }
                }
                if old.is_some() && expected.as_ref().is_some_and(ValueType::has_zero) {
                    args.push((replacement(LabelUse::Zero), "argument_zero"));
                }
            }
            SiteArg::Field(field) => {
                let mut variants = Vec::new();
                site_variants(
                    field,
                    types,
                    &local,
                    false,
                    &mut variants,
                    rich,
                    expected_type,
                    &at.child(index as u32),
                )?;
                args.extend(
                    variants
                        .into_iter()
                        .map(|(site, kind)| (SiteArg::Field(site), kind)),
                );
            }
            // Fresh/key arguments introduce the clause's interface.
            _ => {}
        }
        if rich {
            argument_declarations(arg, &mut local);
        }
        for (arg, kind) in args {
            let mut changed = site.value.args.to_vec();
            changed[index] = arg;
            result.push((
                Site {
                    value: SiteValue {
                        args: changed.into(),
                    },
                    ..site.clone()
                },
                kind,
            ));
        }
    }
    Ok(())
}

pub(crate) fn body_json(body:&Node<Body>)->Value {
    json!(body.value().conjuncts.iter().map(conjunct_json).collect::<Vec<_>>())
}

pub(crate) fn conjunct_json(c: &Conjunct) -> Value {
    if let Some(atom) = c.atom() {
        json!({"node":if matches!(c, Conjunct::Not(_)) {"not_atom"} else {"atom"},
               "relation":relation_json(&atom.value().relation), "sites":atom.value().sites.iter().map(site_json).collect::<Vec<_>>()})
    } else if let Conjunct::Constraint(c) = c {
        json!({"node":"comparison", "op":format!("{:?}",c.op), "first":{"label":c.first.label.0,"fresh":c.first.fresh},
               "second":match c.second { Operand::Zero => json!({"zero":true}), Operand::Label(l) => json!({"label":l.label.0,"fresh":l.fresh}) }})
    } else {
        fn body(b:&Node<Body>)->Value {json!(b.value().conjuncts.iter().map(conjunct_json).collect::<Vec<_>>())}
        match c {
            Conjunct::Or(branches)=>json!({"node":"or","branches":branches.iter().map(body).collect::<Vec<_>>()}),
            Conjunct::If{test,then,otherwise}=>json!({"node":"if","test":body(test),"then":body(then),"otherwise":body(otherwise)}),
            Conjunct::All{domain,body:b}=>json!({"node":"all","domain":body(domain),"body":body(b)}),
            Conjunct::Not(Negated::Form(inner))=>json!({"node":"not_form","inner":conjunct_json(inner)}),
            _=>unreachable!("all conjunct kinds covered"),
        }
    }
}

pub(crate) fn relation_json(r: &RelationRef) -> Value {
    fn name(n: &DeclaredName) -> Value {
        match n {
            DeclaredName::Written(n) => json!({"name":n}),
            DeclaredName::Slot(n) => json!({"slot":n}),
        }
    }
    match r {
        RelationRef::Fact(f) => json!({"fact":format!("{:?}",f)}),
        RelationRef::Lib(n) => json!({"lib":n.0}),
        RelationRef::Declared(n) => json!({"declared":name(&n.0)}),
        RelationRef::DefinedPort(n) => json!({"input_port":n.0}),
        RelationRef::Output(o) => {
            let owner = match &o.of {
                OutputOwner::Instance(n) => json!({"instance":name(&n.0)}),
                OutputOwner::RigidDet(n) => json!({"rigid":name(&n.0)}),
            };
            let path = o
                .path
                .iter()
                .map(|p| match p {
                    OutputStep::Port(n) => json!({"port":n.0}),
                    OutputStep::Part(n) => json!({"part":name(n)}),
                    OutputStep::Pose => json!({"pose":true}),
                })
                .collect::<Vec<_>>();
            json!({"owner":owner,"path":path})
        }
    }
}

pub(crate) fn site_json(s: &Site) -> Value {
    fn column(c: &ColumnName) -> Value {
        match c {
            ColumnName::Written(n) => json!({"name":n}),
            ColumnName::Slot(n) => json!({"slot":n}),
        }
    }
    fn label(l: LabelUse) -> Value {
        match l {
            LabelUse::Fresh(n) => json!({"fresh":n.0}),
            LabelUse::Join(n) => json!({"join":n.0}),
            LabelUse::Key(n) => json!({"key":n.0}),
            LabelUse::Zero => json!({"zero":true}),
        }
    }
    json!({"column":column(&s.column),"args":s.value.args.iter().map(|a|match a {
        SiteArg::Label(l) => label(*l), SiteArg::NamedLabel { name, label:l } => json!({"field":column(name),"label":label(*l)}),
        SiteArg::Field(s) => json!({"site":site_json(s)}) }).collect::<Vec<_>>()})
}

struct Rng(u64);
impl Rng {
    fn index(&mut self, len: usize) -> usize {
        self.0 = self.0.wrapping_add(0x9e3779b97f4a7c15);
        let mut x = self.0;
        x = (x ^ (x >> 30)).wrapping_mul(0xbf58476d1ce4e5b9);
        x = (x ^ (x >> 27)).wrapping_mul(0x94d049bb133111eb);
        ((x ^ (x >> 31)) % len as u64) as usize
    }
    fn shuffle<T>(&mut self, values: &mut [T]) {
        for i in (1..values.len()).rev() {
            let j = self.index(i + 1);
            values.swap(i, j);
        }
    }
}
