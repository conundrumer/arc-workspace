//! The native OUT key projection, independent of display names.
use super::StudyProgram;
use crate::eval::body_view::BodyView;
use crate::mutation::path_json;
use crate::program::path::{NodePath, NodeRef, node_at};
use crate::program::LabelUse;
use serde_json::{Value, json};

pub fn export(program: &StudyProgram) -> Result<Value, String> {
    let checked = program.checked();
    let output = crate::eval::output_relation(checked).ok_or("checked program has no OUT")?;
    let path = checked.program.form_of(output.node);
    let root = NodeRef::Program(program.program().value());
    let Some(NodeRef::Out(out)) = node_at(root, path) else { return Err("native OUT node is not an OUT form".into()); };
    let body = path.child(crate::program::Out::BODY);
    let view = BodyView::at(checked, &body).map_err(|e|e.message.to_string())?;
    let types = checked.types.columns(&output).ok_or("native OUT has no types")?;
    if out.key.columns.len() != 2 || types.len() != 2 { return Err("native OUT must have Position and Color columns".into()); }
    fn uses(node: NodeRef<'_>, at: &NodePath, label: crate::program::LabelId, result: &mut Vec<Value>) {
        if let NodeRef::Label(use_) = node {
            if crate::types::use_label(*use_) == Some(label) {
                result.push(json!({"path":path_json(at),"use":match use_ {LabelUse::Key(_)=>"key",LabelUse::Fresh(_)=>"fresh",_=>"join"}}));
            }
        }
        for (i,child) in node.children().into_iter().enumerate() { uses(child,&at.child(i as u32),label,result); }
    }
    let columns = out.key.columns.iter().zip(types).enumerate().map(|(i,(column,ty))| {
        let mut occurrences = Vec::new();
        uses(NodeRef::Body(out.key.body.value()),&body,column.label,&mut occurrences);
        let body_column = view.column_of(column.label).ok_or("OUT key label missing from native body columns")?;
        Ok(json!({"out_column":i,"role":if i==0 {"position"} else {"color"},"type":format!("{ty:?}"),
            "label_id":column.label.0,"name":super::render::column(&column.name),
            "body_column":body_column,"occurrences":occurrences}))
    }).collect::<Result<Vec<_>,String>>()?;
    Ok(json!({"schema":"arclog-study-out-bindings-v1","complete":true,"path":path_json(path),
        "body_path":path_json(&body),"graph_node":output.node.0,"columns":columns,
        "det_source_names":crate::decode::relation_dets(checked,output.node).iter().map(|d|crate::eval::determinations::relation_spelled(&d.relation)).collect::<Vec<_>>(),
        "projection":"native OUT key columns in engine order: Position then Color; remove duplicate projected rows",
        "coordinate_scope":"Position margins in the OUT reference frame; a cell grid exists only when the native read_grid succeeds"}))
}
