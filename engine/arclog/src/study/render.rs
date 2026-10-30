//! Structured renderer evidence from original checked AST nodes. No text is
//! parsed to discover facts; sexp is produced by the ordinary engine writer.
use super::StudyProgram;
use crate::mutation::{conjunct_json, path_json, relation_json, site_json};
use crate::program::path::{NodePath, NodeRef};
use crate::program::*;
use crate::registry::Registry;
use serde_json::{Value, json};

impl StudyProgram {
    pub fn render_json(&self, registry: &Registry) -> Result<Value, String> {
        let key = registry as *const Registry as usize;
        let cached = self
            .render_cache
            .get_or_init(|| (key, self.render_uncached(registry)));
        if cached.0 == key {
            cached.1.clone()
        } else {
            self.render_uncached(registry)
        }
    }

    fn render_uncached(&self, registry: &Registry) -> Result<Value, String> {
        let text = self.node_texts(registry)?;
        fn walk(
            node: NodeRef<'_>,
            at: &NodePath,
            text: &std::collections::BTreeMap<NodePath, String>,
            out: &mut Vec<Value>,
        ) -> Result<(), String> {
            let (kind, data) = match node {
                NodeRef::Program(_) => ("program", json!({})),
                NodeRef::Clause(c) => (
                    "clause",
                    json!({"keyword":format!("{:?}",c.keyword),
                    "defines":program_relation(&c.derives),"columns":c.columns.iter().map(|c|json!({"name":column(&c.name),"label_id":c.label.0})).collect::<Vec<_>>(),
                    "proposers":c.proposers.iter().map(|p|format!("{p:?}")).collect::<Vec<_>>()}),
                ),
                NodeRef::Instance(i) => (
                    "init",
                    json!({"name":name(&i.name.0),"component":i.component.0,"has_key":i.key.is_some()}),
                ),
                NodeRef::KeyClause(k) => (
                    "init_key",
                    json!({"columns":k.key.columns.iter().map(|c|json!({"name":column(&c.name),"label_id":c.label.0})).collect::<Vec<_>>()}),
                ),
                NodeRef::InstanceInput(i) => (
                    "init_input",
                    json!({"port":i.name.0,"head_site_count":i.head.len()}),
                ),
                NodeRef::Choose(c) => (
                    "choose",
                    json!({"name":name(&c.name.0),"from_inside_for":c.from_inside_for}),
                ),
                NodeRef::RigidDet(c) => ("rigid_det", json!({"name":name(&c.name.0)})),
                NodeRef::Out(_) => ("out", json!({})),
                NodeRef::Body(_) => ("body", json!({})),
                NodeRef::Conjunct(c) => (
                    match c {
                        Conjunct::Atom(_) => "atom",
                        Conjunct::Constraint(_) => "comparison",
                        Conjunct::Not(_) => "not",
                        Conjunct::Or(_) => "or",
                        Conjunct::If { .. } => "if",
                        Conjunct::All { .. } => "all",
                    },
                    if c.atom().is_some() || matches!(c, Conjunct::Constraint(_)) {
                        conjunct_json(c)
                    } else {
                        json!({"branch_count":node.children().len()})
                    },
                ),
                NodeRef::Atom(a) => (
                    "atom",
                    json!({"relation":relation_json(&a.relation),"sites":a.sites.iter().map(site_json).collect::<Vec<_>>()}),
                ),
                NodeRef::Site(s) => ("site", site_json(s)),
                NodeRef::Label(l) => (
                    "label",
                    match l {
                        LabelUse::Fresh(l) => json!({"use":"fresh","label_id":l.0}),
                        LabelUse::Join(l) => json!({"use":"join","label_id":l.0}),
                        LabelUse::Key(l) => json!({"use":"key","label_id":l.0}),
                        LabelUse::Zero => json!({"use":"reserved_zero"}),
                    },
                ),
                _ => {
                    return Err(format!(
                        "unsupported checked render node at {at:?}: {node:?}"
                    ));
                }
            };
            let children = node.children();
            out.push(json!({"path":path_json(at),"kind":kind,"data":data,
                "sexp":text.get(at).ok_or_else(||format!("missing engine node text at {at:?}"))?,
                "children":(0..children.len()).map(|i|path_json(&at.child(i as u32))).collect::<Vec<_>>()}));
            for (i, child) in children.into_iter().enumerate() {
                walk(child, &at.child(i as u32), text, out)?;
            }
            Ok(())
        }
        let mut nodes = Vec::new();
        walk(
            NodeRef::Program(self.program().value()),
            &NodePath::default(),
            &text,
            &mut nodes,
        )?;
        let definitions = super::render_definitions::export(self, registry)?;
        let native_semantics = if definitions["semantic_coverage"]["complete"] == true {
            "complete"
        } else {
            "pending"
        };
        Ok(
            json!({"schema":"arclog-study-render-v1","parts":{"nodes":"complete",
            "definitions_readers":"complete","native_semantics":native_semantics,"types_frames":"pending","literal_meanings":"complete","argument_types":"complete","body_views":"complete"},
            "orientation_domains":super::render_terms::program_orientation_domains(self,registry),
            "orientation_domains_contract":"native scalar encoding domains including every resolved nominal Pose type; proposal admissibility is separate",
            "typed_sites":self.typed_sites(registry)?.json.clone(),"definitions":definitions,"program_sexp":self.sexp(registry),"nodes":nodes,"body_views":super::render_bodies::export(self,registry)?,
            "source_path_correspondence":"identity; use ValidMutant.render_json for mutation correspondence"}),
        )
    }
}

pub(crate) fn column(c: &ColumnName) -> Value {
    match c {
        ColumnName::Written(n) => json!({"kind":"written","name":n}),
        ColumnName::Slot(n) => json!({"kind":"slot","slot":n}),
    }
}
pub(crate) fn name(n: &DeclaredName) -> Value {
    match n {
        DeclaredName::Written(n) => json!({"kind":"written","name":n}),
        DeclaredName::Slot(n) => json!({"kind":"slot","slot":n}),
    }
}
pub fn program_relation(r: &ProgramRelation) -> Value {
    match r {
        ProgramRelation::Declared(n) => json!({"kind":"declared","name":name(&n.0)}),
        ProgramRelation::Output(n) => relation_json(&RelationRef::Output(n.clone())),
    }
}

/// Parse external structured evidence through the engine's JSON dependency.
pub fn parse_json(text: &str) -> Result<Value, String> {
    serde_json::from_str(text).map_err(|e| e.to_string())
}

pub fn decoded_rows_json(rows: Vec<Vec<Value>>) -> String {
    json!(rows).to_string()
}

/// Includes the actual rehydrated source AST used to verify a stored decode
/// identity (which can differ from a sexp reader's presentation wrappers).
pub fn render_pair(
    gold: &StudyProgram,
    mutant: &crate::mutation::ValidMutant,
    registry: &Registry,
) -> Result<Value, String> {
    if !std::sync::Arc::ptr_eq(gold.checked(), mutant.gold()) {
        return Err("render source handle differs from rehydrated mutation source".into());
    }
    let mut changed = mutant.program().render_json(registry)?;
    changed["mutation_identity"] = mutant.identity();
    changed["source_path_correspondence"] = mutant.source_paths();
    Ok(
        json!({"schema":"arclog-study-render-pair-v1","gold":gold.render_json(registry)?,"mutant":changed}),
    )
}
