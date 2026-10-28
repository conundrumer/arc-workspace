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
        let text = crate::write::node_texts(self.program(), self.layout(), registry)?;
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
                    conjunct_json(c),
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
        Ok(
            json!({"schema":"arclog-study-render-v1","parts":{"nodes":"complete",
            "definitions_readers":"pending","types_frames":"pending","literal_meanings":"pending"},
            "program_sexp":self.sexp(registry),"nodes":nodes,
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
pub(crate) fn program_relation(r: &ProgramRelation) -> Value {
    match r {
        ProgramRelation::Declared(n) => json!({"kind":"declared","name":name(&n.0)}),
        ProgramRelation::Output(n) => relation_json(&RelationRef::Output(n.clone())),
    }
}
