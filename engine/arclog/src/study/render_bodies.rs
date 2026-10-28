//! The exact native body-view schema, compiled in the original checked scope.
use super::StudyProgram;
use crate::mutation::path_json;
use crate::program::path::{NodePath, NodeRef, node_at};
use crate::program::{LabelId, LabelUse};
use crate::registry::Registry;
use serde_json::{Value, json};

pub fn export(program: &StudyProgram, registry: &Registry) -> Result<Value, String> {
    let text = crate::write::node_texts(program.program(), program.layout(), registry)?;
    let names = crate::write::label_names(program.program(), registry);
    let mut bodies = Vec::new();
    for point in program.mutation_points() {
        let view = crate::eval::body_view::BodyView::at(program.checked(), &point.body)
            .map_err(|e| format!("body render compile at {:?}: {}", point.body, e.message))?;
        let columns=view.clause.columns.iter().enumerate().map(|(i,v)| {
            let label=view.paths.labels[v.0 as usize];
            let spelling=names[view.form.0[0].0 as usize].iter().find(|(id,_)|*id==label).map(|(_,n)|n.as_ref());
            json!({"body_column":i,"native_column_name":format!("c{i}"),"label_id":label.0,
                "label_spelling":spelling,"type":format!("{:?}",view.clause.variables[v.0 as usize].ty)})
        }).collect::<Vec<_>>();
        let parent = NodePath(point.body.0[..point.body.0.len() - 1].into());
        let mut projection = Vec::new();
        fn labels(
            node: NodeRef<'_>,
            at: &NodePath,
            program: &StudyProgram,
            view: &crate::eval::body_view::BodyView,
            text: &std::collections::BTreeMap<NodePath, String>,
            projection: &mut Vec<Value>,
        ) -> Result<(), String> {
            if let NodeRef::Label(use_) = node {
                let label = match use_ {
                    LabelUse::Fresh(l) | LabelUse::Key(l) | LabelUse::Join(l) => *l,
                    LabelUse::Zero => return Err(format!("zero at input head {at:?}")),
                };
                let body_column = view.column_of(label).ok_or_else(|| {
                    format!("input head label {label:?} not in body columns at {at:?}")
                })?;
                let column = (1..=at.0.len())
                    .rev()
                    .find_map(|n| {
                        program
                            .checked()
                            .program
                            .column_position(&NodePath(at.0[..n].into()))
                    })
                    .ok_or_else(|| format!("input head has no resolved port column at {at:?}"))?;
                projection.push(json!({"site_path":path_json(at),"port_column":column.0,
                    "label_id":label.0,"label_spelling":text.get(at),"body_column":body_column}));
            }
            for (i, child) in node.children().into_iter().enumerate() {
                labels(child, &at.child(i as u32), program, view, text, projection)?;
            }
            Ok(())
        }
        if let Some(NodeRef::InstanceInput(input)) =
            node_at(NodeRef::Program(program.program().value()), &parent)
        {
            for i in 0..input.head.len() {
                let at = parent.child(i as u32);
                let node = node_at(NodeRef::Program(program.program().value()), &at)
                    .ok_or_else(|| format!("missing input head {at:?}"))?;
                labels(node, &at, program, &view, &text, &mut projection)?;
            }
            projection.sort_by_key(|v| v["port_column"].as_u64());
        }
        let key_labels = if view.input.is_some() {
            let in_body = view
                .clause
                .columns
                .iter()
                .map(|v| view.paths.labels[v.0 as usize])
                .collect::<Vec<LabelId>>();
            in_body
                .iter()
                .filter(|l| {
                    !projection
                        .iter()
                        .any(|p| p["label_id"].as_u64() == Some(u64::from(l.0)))
                })
                .map(|l| l.0)
                .collect::<Vec<_>>()
        } else {
            Vec::new()
        };
        bodies.push(json!({"body_path":path_json(&point.body),"owner_path":path_json(&view.form),
            "kind":point.kind,"scope":format!("{:?}",view.scope),"input_port":view.input.as_ref().map(|p|p.0.as_ref()),
            "result_kind":"body_witness_rows","columns":columns,"input_port_projection":projection,
            "unprojected_body_label_ids":key_labels,
            "native_table_selector":{"form":view.form.0.iter().map(|s|s.0.to_string()).collect::<Vec<_>>().join("."),
                "point":1,"point_kind":"Body","report_indices":["gold_all","gold_kept","mutant_all","mutant_kept"]},
            "meaning":"evaluate_pair body rows in original lexical/key scope; project input_port_projection for INIT input-port rows; these are not component output rows"}));
    }
    Ok(json!(bodies))
}
