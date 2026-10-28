//! Typed held choices and the exact dependencies of compiled body queries.
use super::StudyProgram;
use crate::check::CheckedProgram;
use crate::decode::relation_dets;
use crate::eval::body_view::BodyView;
use crate::eval::determinations::{determinations, det_relation, relation_spelled};
use crate::eval::ir::{AtomSource, ClauseIr, IrNode};
use crate::mutation::path_json;
use crate::registry::Registry;
use crate::resolver::GraphNodeIndex;
use crate::types::GraphRelation;
use serde_json::{Value, json};
use std::collections::BTreeMap;

/// The same IR read traversal used by the native body-table exporter. This
/// includes key reads and nested/negative branches, without adding unrelated
/// DETs belonging to the enclosing form.
pub fn body_dets(checked: &CheckedProgram, view: &BodyView) -> Vec<crate::judge::determination::Det> {
    fn reads(clause: &ClauseIr, nodes: &mut Vec<GraphNodeIndex>) {
        for node in clause.nodes.iter() {
            match node {
                IrNode::Atom(atom) => match &atom.source {
                    AtomSource::Relation(r) => { if !nodes.contains(&r.node) { nodes.push(r.node); } }
                    AtomSource::Key(read) => reads(&read.clause, nodes),
                    _ => {}
                },
                IrNode::Or(union) => for branch in union.branches.iter() { reads(branch, nodes); },
                IrNode::Not(f) | IrNode::Counterexample(f) => reads(&f.body, nodes),
                _ => {}
            }
        }
    }
    let mut nodes = Vec::new();
    reads(&view.clause, &mut nodes);
    let mut held = Vec::new();
    for node in nodes {
        for det in relation_dets(checked, node) {
            if !held.iter().any(|d: &crate::judge::determination::Det| d.node == det.node) { held.push(det); }
        }
    }
    let order = determinations(checked);
    held.sort_by_key(|d| order.iter().position(|n| *n == d.node));
    held
}

/// Decode stored choices without evaluating, interning or changing assignments.
/// Types and subset membership are native checked-program facts; packed values
/// retain their original task-session identity.
pub fn export(program: &StudyProgram, kept: &Value, registry: &Registry) -> Result<Value, String> {
    let checked = program.checked();
    let mut schemas = Vec::new();
    let mut types_by_name = BTreeMap::new();
    for node in determinations(checked) {
        let (relation, one) = det_relation(&checked.program.graph.nodes[node.0 as usize].kind)
            .ok_or("determination has no native relation")?;
        // Model picks are not held parameter assignments.
        if !relation_dets(checked, node).iter().any(|d| d.node == node) { continue; }
        let types = checked.types.columns(&GraphRelation {node, output: None})
            .ok_or_else(|| format!("DET has no checked schema: {relation:?}"))?
            .iter().map(|t| format!("{t:?}")).collect::<Vec<_>>();
        let source = relation_spelled(&relation);
        if types_by_name.insert(source.clone(), types.clone()).is_some() { return Err("duplicate native DET identity".into()); }
        schemas.push(json!({"source_name":source,"relation":super::render::program_relation(&relation),
            "node":node.0,"one":one,"types":types,
            "definition_paths":checked.program.forms_of(node).iter().map(path_json).collect::<Vec<_>>(),
            "columns":checked.program.row_paths(node).map(|paths| paths.iter().map(|p|p.iter().map(super::render::column).collect::<Vec<_>>()).collect::<Vec<_>>())}));
    }
    let mut bodies = Vec::new();
    for point in program.mutation_points() {
        let view = BodyView::at(checked, &point.body).map_err(|e|e.message.to_string())?;
        bodies.push(json!({"body_path":path_json(&point.body),"source_names":body_dets(checked,&view).iter().map(|d|relation_spelled(&d.relation)).collect::<Vec<_>>()}));
    }
    let mut choices = Vec::new();
    for (index, assignment) in kept.as_array().ok_or("kept assignments must be an array")?.iter().enumerate() {
        let mut decoded = BTreeMap::new();
        for det in assignment.as_array().ok_or("each kept assignment must be an array")? {
            let source = det["relation"].as_str().ok_or("DET relation must be a source name")?;
            let types = types_by_name.get(source).ok_or_else(||format!("held relation is not a native DET: {source}"))?;
            let mut rows = Vec::new();
            for row in det["rows"].as_array().ok_or("DET rows must be an array")? {
                let row = row.as_array().ok_or("DET row must be an array")?;
                if row.len() != types.len() { return Err(format!("held DET row width differs from native schema: {source}")); }
                rows.push(row.iter().zip(types).map(|(value,ty)| {
                    super::render_terms::decode(ty, value.as_i64().ok_or("packed DET cell must be an integer")?, registry)
                }).collect::<Result<Vec<_>,String>>()?);
            }
            if decoded.insert(source.to_owned(), json!({"source_name":source,"types":types,"packed_rows":det["rows"],"rows":rows})).is_some() {return Err(format!("duplicate held DET: {source}"));}
        }
        // Full assignments must include every held parameter, even those that
        // the edited body does not read. Missing values must not look empty.
        if decoded.len() != types_by_name.len() {return Err("kept assignment is missing native DETs".into());}
        let subsets = bodies.iter().map(|body| {
            let subset = body["source_names"].as_array().unwrap().iter().map(|n| {
                decoded.get(n.as_str().unwrap()).cloned().ok_or_else(||format!("body reads a DET absent from held choice: {n}"))
            }).collect::<Result<Vec<_>,String>>()?;
            Ok(json!({"body_path":body["body_path"],"assignment":subset}))
        }).collect::<Result<Vec<_>,String>>()?;
        choices.push(json!({"assignment":index,"full_assignment":schemas.iter().map(|s|decoded[ s["source_name"].as_str().unwrap() ].clone()).collect::<Vec<_>>(),"body_read_subsets":subsets}));
    }
    Ok(json!({"schema":"arclog-study-choices-v1","complete":true,"dets":schemas,"bodies":bodies,"choices":choices,
        "identity_scope":"stored packed terms in their original task session; Ident remains opaque; no evaluation or re-interning"}))
}

/// String adapter keeps serde_json out of the streams bindings dependencies.
pub fn export_json(program: &StudyProgram, kept_json: &str, registry: &Registry) -> Result<Value, String> {
    let kept = serde_json::from_str(kept_json).map_err(|e| e.to_string())?;
    export(program, &kept, registry)
}
