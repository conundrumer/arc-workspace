//! Constructive, exact-K mutation of clauses in a checked gold AST.
//!
//! A draw uses only certified choices in its current context. Certification
//! has no task evaluation: it shares the resolver, binder, checker and writer.
//! Diagnostics from unavailable choices are counted, never silently repaired.
pub mod edit;
mod identity;
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
use crate::study::{StudyProgram, StudyStream};
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

    fn refusal(&mut self, stage: &str, message: &str) {
        // Keep engine check names, rather than collapsing all invalid choices.
        let reason = if let Some(rest) = message.split("Check(").nth(1) {
            rest.split(')').next().unwrap_or("unknown").to_string()
        } else {
            message
                .lines()
                .next()
                .unwrap_or("unknown")
                .split(':')
                .next()
                .unwrap_or("unknown")
                .to_string()
        };
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

    /// Runtime audit on real programs: the old depth-first order and the fair
    /// order use identical alternatives and certificates. Only the production
    /// order returns specs to callers; this method returns classified counts.
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
        Ok(json!({"before":before.json(), "after":after.json()}))
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
        fair: bool,
    ) -> Result<(Vec<MutationSpec>, DrawStats), String> {
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
        if fair {
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
            for (replacement, kind) in alternatives(self, at, operation, registry) {
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
                        } else {
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
            cache: CheckCache::default(),
            stats,
            output: Vec::new(),
            requested: count,
            deletion_only: operation == "delete",
            started: std::time::Instant::now(),
            stopped: false,
        };
        if fair {
            domain.fair_visit(k, &mut rng)?;
        } else {
            domain.visit(0, k, &mut Vec::new())?;
        }
        if domain.stopped {
            domain.stats.count("domain_search_stopped:Deadline");
        } else if domain.output.len() < count {
            domain.stats.count("domain_exhausted");
        }
        Ok((domain.output, domain.stats))
    }

    /// Construction cannot discover a type/binding problem: its input is an
    /// immutable certified spec. Only a spec from another gold handle refuses.
    pub fn construct(&self, spec: &MutationSpec) -> Result<ValidMutant, &'static str> {
        if !Arc::ptr_eq(self.checked(), &spec.source) {
            return Err("spec_belongs_to_another_program");
        }
        Ok(ValidMutant { spec: spec.clone() })
    }
}

/// A randomized ordering of the finite completion domain. Site subsets have
/// one canonical traversal and each site's values are unique; consequently a
/// returned assignment can never be drawn twice. Search exclusions are domain
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
    requested: usize,
    deletion_only: bool,
    started: std::time::Instant,
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
        // One scheduling option per edit kind, independent of how many
        // columns/values instantiate it. In particular N zero-valued columns
        // do not give reserved zero N tickets against a variable substitution.
        // Within each kind, rotate sites/values and resume suffix searches so
        // a small requested prefix cannot be filled by one DFS subtree.
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
                    .entry(edit.choice_kind)
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
                    if self
                        .settings
                        .deadline
                        .is_some_and(|d| self.started.elapsed() >= d)
                    {
                        self.stopped = true;
                        return Ok(());
                    }
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
        if !named_bindings_hold(
            &ast.value().forms[top],
            &NodePath::top(top as u32),
            self.gold.layout(),
        ) {
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
                self.stats.refusal("domain_check_excluded", &error);
                return Ok(());
            }
        };
        if let Err(error) = checked.decode_stream(self.registry, self.settings) {
            self.stats.refusal("domain_stream_excluded", &error);
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

    fn visit(
        &mut self,
        start: usize,
        remaining: usize,
        edits: &mut Vec<AtomEdit>,
    ) -> Result<(), String> {
        if self.output.len() >= self.requested || self.stopped {
            return Ok(());
        }
        if self
            .settings
            .deadline
            .is_some_and(|limit| self.started.elapsed() >= limit)
        {
            self.stopped = true;
            return Ok(());
        }
        self.stats.count("domain_search_nodes");
        if self.sites.len().saturating_sub(start) < remaining {
            return Ok(());
        }
        let top = self.point.body.0[0].0 as usize;
        if remaining == 0 {
            return self.certify(edits);
        }
        for index in start..=self.sites.len() - remaining {
            for edit in self.sites[index].clone() {
                edits.push(edit);
                let can_complete = if self.deletion_only {
                    let ast = edit::apply(self.gold.program(), edits)?;
                    // Pure deletion cannot restore a lost exported/key
                    // label. This syntax-derived prune needs no stale types.
                    crate::study::interfaces_hold(&ast.value().forms[top])
                } else {
                    true
                };
                if can_complete {
                    self.visit(index + 1, remaining - 1, edits)?;
                } else {
                    self.stats.count("domain_pruned:required_column_binding");
                }
                edits.pop();
                if self.output.len() >= self.requested || self.stopped {
                    return Ok(());
                }
            }
        }
        Ok(())
    }
}

/// The AST reader gives each fresh/key occurrence an id. Deleting its only
/// declaration must remove its remaining uses too; positive joins may bind
/// values, but do not create a new syntactic declaration.
fn declared_in_scopes(root: NodeRef<'_>) -> bool {
    fn gather(node: NodeRef<'_>, uses: &mut Vec<LabelUse>, valid: &mut bool) {
        match node {
            NodeRef::Label(label) => uses.push(*label),
            NodeRef::Clause(c) => uses.extend(c.columns.iter().map(|c| LabelUse::Join(c.label))),
            NodeRef::Conjunct(Conjunct::Constraint(c)) => {
                uses.push(c.first.into());
                uses.extend(constraint_second(c).map(LabelUse::from));
            }
            _ => {}
        }
        for (i, child) in node.children().into_iter().enumerate() {
            if crate::program::canonical::opens_scope(node, i, child) {
                *valid &= declared_in_scopes(child);
            } else {
                gather(child, uses, valid);
            }
        }
    }
    let mut uses = Vec::new();
    let mut valid = true;
    gather(root, &mut uses, &mut valid);
    let makers: StableHashSet<_> = uses
        .iter()
        .filter_map(|u| match u {
            LabelUse::Fresh(l) | LabelUse::Key(l) => Some(*l),
            _ => None,
        })
        .collect();
    valid
        && uses.iter().all(|u| match u {
            LabelUse::Join(l) => makers.contains(l),
            _ => true,
        })
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
        json!({"source": {"revision": self.origin.revision, "task": self.origin.task, "case": self.origin.case},
               "clause": path_json(&self.point.clause), "body": path_json(&self.point.body),
               "edits": self.edits.iter().map(|e| json!({"at": path_json(&e.at), "kind":e.kind,
                   "replacement":e.replacement.as_ref().map(conjunct_json)})).collect::<Vec<_>>()})
    }

    pub fn k(&self) -> usize {
        self.edits.len()
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
    /// Exact, source-order evidence that only the requested original atoms
    /// changed. This compares AST values directly, without any fingerprint.
    /// Every original node is either mapped exactly, deleted, or belongs
    /// to a replaced subtree. Replacement descendants have no guessed match.
    pub fn source_paths(&self) -> Value {
        fn walk(node: NodeRef<'_>, at: &NodePath, edits: &[AtomEdit], out: &mut Vec<Value>) {
            let replaced = edits.iter().any(|e| e.replacement.is_some() && at.0.len()>e.at.0.len() && at.0.starts_with(&e.at.0));
            let after = if replaced {None} else {edit::mapped(at,edits)};
            out.push(json!({"before_path":path_json(at),"after_path":after.as_ref().map(path_json),
                "status":if replaced {"replaced_subtree"} else if after.is_none() {"deleted"}
                    else if edits.iter().any(|e|e.at==*at) {"replaced"} else {"preserved"}}));
            for (i,child) in node.children().into_iter().enumerate() {walk(child,&at.child(i as u32),edits,out);}
        }
        let mut out=Vec::new();
        walk(NodeRef::Program(self.gold().program.program.value()),&NodePath::default(),&self.spec.edits,&mut out);
        json!(out)
    }

    pub fn audit(&self) -> Result<Value, String> {
        let gold = NodeRef::Program(self.spec.source.program.program.value());
        let mutant = NodeRef::Program(self.program().program().value());
        let mut gold_atoms = Vec::new();
        leaves(gold, &NodePath::default(), &mut gold_atoms);
        let mut untouched = 0;
        let mut changed = 0;
        for path in gold_atoms {
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
) -> Vec<(Option<Conjunct>, &'static str)> {
    let Some(NodeRef::Conjunct(old)) = node_at(NodeRef::Program(program.program().value()), at)
    else {
        return Vec::new();
    };
    let Some(types) = scope_types(program, at) else {
        return Vec::new();
    };
    let bound = available(program, at, registry);
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
        return result;
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
            site_variants(site, types, &labels, record, &mut replacements);
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
    result
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

fn site_variants(
    site: &Site,
    types: &FormTypes,
    bound: &[LabelId],
    record: bool,
    result: &mut Vec<(Site, &'static str)>,
) {
    for (index, arg) in site.value.args.iter().enumerate() {
        let mut args = Vec::new();
        match arg {
            SiteArg::Label(LabelUse::Join(old))
            | SiteArg::NamedLabel {
                label: LabelUse::Join(old),
                ..
            } => {
                let replacement = |label| match arg {
                    SiteArg::NamedLabel { name, .. } if record => SiteArg::Field(Site {
                        column: name.clone(),
                        value: SiteValue {
                            args: Arc::from([SiteArg::Label(label)]),
                        },
                    }),
                    _ => SiteArg::Label(label),
                };
                for label in bound {
                    if label != old
                        && types.label(*label).is_some()
                        && types.label(*label) == types.label(*old)
                    {
                        args.push((replacement(LabelUse::Join(*label)), "argument_variable"));
                    }
                }
                if types.label(*old).is_some_and(ValueType::has_zero) {
                    args.push((replacement(LabelUse::Zero), "argument_zero"));
                }
            }
            SiteArg::Field(field) => {
                let mut variants = Vec::new();
                site_variants(field, types, bound, false, &mut variants);
                args.extend(
                    variants
                        .into_iter()
                        .map(|(site, kind)| (SiteArg::Field(site), kind)),
                );
            }
            // Fresh/key arguments introduce the clause's interface.
            _ => {}
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
}

pub(crate) fn conjunct_json(c: &Conjunct) -> Value {
    if let Some(atom) = c.atom() {
        json!({"node":if matches!(c, Conjunct::Not(_)) {"not_atom"} else {"atom"},
               "relation":relation_json(&atom.value().relation), "sites":atom.value().sites.iter().map(site_json).collect::<Vec<_>>()})
    } else if let Conjunct::Constraint(c) = c {
        json!({"node":"comparison", "op":format!("{:?}",c.op), "first":{"label":c.first.label.0,"fresh":c.first.fresh},
               "second":match c.second { Operand::Zero => json!({"zero":true}), Operand::Label(l) => json!({"label":l.label.0,"fresh":l.fresh}) }})
    } else {
        unreachable!("a mutation replaces a leaf atom only")
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
