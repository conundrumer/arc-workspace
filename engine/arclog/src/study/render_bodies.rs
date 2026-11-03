//! The exact native body-view schema, compiled in the original checked scope.
use super::StudyProgram;
use crate::mutation::path_json;
use crate::program::LabelId;
use crate::program::path::{NodePath, NodeRef, node_at};
use crate::registry::Registry;
use serde_json::{Value, json};

pub fn export(program: &StudyProgram, registry: &Registry) -> Result<Value, String> {
    let text = program.node_texts(registry)?;
    let names = program.label_names(registry);
    let mut bodies = Vec::new();
    for point in program.mutation_points() {
        let view = crate::eval::body_view::BodyView::keyed_at(program.checked(), &point.body)
            .map_err(|e| format!("body render compile at {:?}: {}", point.body, e.message))?;
        // The names of the labels are those of the top-level form's scope;
        // a body within a `DEMO_RULE` stands in the rule's scope.
        let top_scope=crate::eval::ir::scope_of(program.checked(),&point.body).0.len()==1;
        let columns=view.clause.columns.iter().enumerate().map(|(i,v)| {
            let label=view.paths.labels[v.0 as usize];
            let spelling=names[view.form.0[0].0 as usize].iter().filter(|_|top_scope).find(|(id,_)|*id==label).map(|(_,n)|n.as_ref());
            json!({"body_column":i,"native_column_name":format!("c{i}"),"label_id":label.0,
                "label_spelling":spelling,"type":format!("{:?}",view.clause.variables[v.0 as usize].ty)})
        }).collect::<Vec<_>>();
        let parent = NodePath(point.body.0[..point.body.0.len() - 1].into());
        let mut projection = Vec::new();
        let mut group_key_labels = Vec::new();
        let mut logical_columns = Vec::new();
        fn head_uses(node: NodeRef<'_>, at: &NodePath, out: &mut Vec<(LabelId, NodePath)>) {
            if let NodeRef::Label(use_) = node {
                if let Some(label) = crate::types::use_label(*use_) {
                    out.push((label, at.clone()));
                }
            }
            for (i, child) in node.children().into_iter().enumerate() {
                head_uses(child, &at.child(i as u32), out);
            }
        }
        // The form whose input the body is: an `INIT` form, at the top level
        // or within a `DEMO_RULE`. The inputs of a `DEMONSTRATED` form read
        // no component's port, so they have no port projection.
        let root = NodeRef::Program(program.program().value());
        let owner = (1..parent.0.len()).rev().map(|end| NodePath(parent.0[..end].into()))
            .find(|path| matches!(node_at(root, path), Some(NodeRef::Instance(_) | NodeRef::Demonstrated(_))))
            .unwrap_or_else(|| view.form.clone());
        if let (Some(NodeRef::InstanceInput(input)), Some(NodeRef::Instance(_))) = (node_at(root, &parent), node_at(root, &owner))
        {
            let (head, types, key, port_columns) = crate::eval::init_form::render_metadata::input_projection(
                program.checked(),
                &owner,
                input,
                registry,
            )?;
            // A port without a key column does not carry the group key in its rows.
            group_key_labels = if port_columns.iter().any(|c|c.key) {key} else {Vec::new()};
            logical_columns = port_columns.iter().map(|c|json!({
                "logical_port_column":c.ordinal,"name":super::render::column(&c.name),
                "role":if c.key {"group_key"} else {"input_value"},
                "row_columns":(c.row_start..c.row_start+c.width).collect::<Vec<_>>(),
                "row_width":c.width,"fields":c.fields.as_ref().map(|f|f.iter().map(super::render::column).collect::<Vec<_>>()),
                "zero_width":!c.key && c.width==0})).collect();
            let mut uses = Vec::new();
            for i in 0..input.head.len() {
                let at = parent.child(i as u32);
                head_uses(NodeRef::Site(&input.head[i]), &at, &mut uses);
            }
            for (i, (label, ty)) in head.iter().zip(types.iter()).enumerate() {
                let logical = port_columns.iter().find(|c|!c.key && i>=c.row_start && i<c.row_start+c.width)
                    .ok_or("native INIT scalar column has no logical port identity")?;
                if label.is_none() {return Err("native INIT projection unexpectedly contains an inserted scalar column".into());}
                let paths = label
                    .map(|l| {
                        uses.iter()
                            .filter(|(id, _)| *id == l)
                            .map(|(_, p)| path_json(p))
                            .collect::<Vec<_>>()
                    })
                    .unwrap_or_default();
                let body_column = match label {
                    Some(l) => Some(
                        view.column_of(*l)
                            .ok_or_else(|| format!("native input head {l:?} not in body output"))?,
                    ),
                    None => None,
                };
                projection.push(json!({"port_column":i,"logical_port_column":logical.ordinal,
                    "logical_port_column_name":super::render::column(&logical.name),
                    "field_index":logical.fields.as_ref().map(|_|i-logical.row_start),
                    "field":logical.fields.as_ref().and_then(|f|f.get(i-logical.row_start)).map(super::render::column),
                    "type":format!("{ty:?}"),"label_id":label.map(|l|l.0),
                    "body_column":body_column,"head_occurrence_paths":paths,"site_path":if paths.len()==1 {paths.first().cloned()} else {None},
                    "label_spelling":label.and_then(|l|uses.iter().find(|(id,_)|*id==l).and_then(|(_,p)|text.get(p))),
                    "inserted_constant":Value::Null}));
            }
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
            "result_kind":"body_witness_rows","columns":columns,"input_port_projection":projection,"input_port_columns":logical_columns,
            "unprojected_body_label_ids":key_labels,"group_key_label_ids":group_key_labels.iter().map(|l|l.0).collect::<Vec<_>>(),
            "native_table_selector":{"form":view.form.0.iter().map(|s|s.0.to_string()).collect::<Vec<_>>().join("."),
                "point":1,"point_kind":"Body","report_indices":["gold_all","gold_kept","mutant_all","mutant_kept"]},
            "meaning":"evaluate_pair body rows in original lexical/key scope; project input_port_projection for INIT input-port rows; these are not component output rows"}));
    }
    Ok(json!(bodies))
}
