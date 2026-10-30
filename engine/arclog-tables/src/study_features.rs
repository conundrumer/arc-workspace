//! Feature-safe native metadata. The checker sees only a fresh prefix.
use crate::flows::{self, ColumnSource, SourceFrame};
use arclog::check::CheckedProgram;
use arclog::eval::body_view::BodyView;
use arclog::mutation::path_json;
use arclog::program::LabelId;
use arclog::program::canonical::{CanonicalOrder, SearchBudget};
use arclog::program::path::{NodePath, NodeRef, PathStep};
use arclog::registry::Registry;
use arclog::study::{StudyProgram, features};
use serde_json::{Value, json};
use std::collections::BTreeMap;
use std::hash::Hasher;

fn path(value: &Value) -> Option<NodePath> {
    Some(NodePath(
        value
            .as_array()?
            .iter()
            .map(|n| n.as_u64().and_then(|n| u32::try_from(n).ok()).map(PathStep))
            .collect::<Option<Vec<_>>>()?
            .into(),
    ))
}
fn id(value: &Value) -> String {
    let mut h = arclog::hash::StableHasher::new();
    h.write(value.to_string().as_bytes());
    format!("frame:{:032x}", h.finish128().0)
}
fn frame_key(checked: &CheckedProgram, at: &NodePath) -> Value {
    let Some(first) = at.0.first() else {
        return json!({"status":"unsupported"});
    };
    let form = &checked.program.program.value().forms[first.0 as usize];
    let mut budget = SearchBudget::new();
    let (order, canonical) = CanonicalOrder::for_features(form, &mut budget);
    let local = NodePath(at.0[1..].into());
    json!({"clause":first.0,"canonical_form":format!("{:032x}",canonical.hash.0),"canonical_path":path_json(&order.canonical_path(&local))})
}
fn add_frame(frames: &mut BTreeMap<String, Value>, mut frame: Value) -> String {
    let key = id(&frame);
    frame["id"] = key.clone().into();
    frames.entry(key.clone()).or_insert(frame);
    key
}
fn source_frame(
    checked: &CheckedProgram,
    source: &ColumnSource,
    frame: &SourceFrame,
    frames: &mut BTreeMap<String, Value>,
) -> Option<String> {
    match frame {
        SourceFrame::Unknown => None,
        SourceFrame::Read => Some(add_frame(
            frames,
            json!({"kind":"relation_column","relation":source.relation.as_ref().map(|r|crate::columns::source_spelled(r)),"row_path":source.row.as_ref().map(|r|r.iter().map(arclog::program::column_spelled).collect::<Vec<_>>()),"column":format!("{:?}",source.column),"parents":[]}),
        )),
        SourceFrame::Made { maker, at, within } => {
            let parents = within
                .as_ref()
                .and_then(|f| source_frame(checked, source, f, frames))
                .into_iter()
                .collect::<Vec<_>>();
            Some(add_frame(
                frames,
                json!({"kind":"made","maker":maker.spelled(),"introduction":frame_key(checked,at),"parents":parents}),
            ))
        }
    }
}
fn label_frames(
    checked: &CheckedProgram,
    point: &NodePath,
    registry: &Registry,
) -> BTreeMap<(u32, u32), Vec<ColumnSource>> {
    let mut out = BTreeMap::new();
    fn visit(
        node: NodeRef<'_>,
        at: &NodePath,
        checked: &CheckedProgram,
        registry: &Registry,
        out: &mut BTreeMap<(u32, u32), Vec<ColumnSource>>,
    ) {
        if matches!(node, NodeRef::Body(_)) {
            if let Ok(view) = BodyView::at(checked, at) {
                let mut all = view.clause.clone();
                all.columns = (0..all.variables.len())
                    .map(|i| arclog::eval::ir::Variable(i as u16))
                    .collect();
                let found = flows::body_column_flows(checked, &all, &view.paths, registry);
                for (i, sources) in found.into_iter().enumerate() {
                    let label = view.paths.labels[i];
                    out.entry((view.form.0[0].0, label.0))
                        .or_default()
                        .extend(sources);
                }
            }
        }
        for (i, child) in node.children().into_iter().enumerate() {
            visit(child, &at.child(i as u32), checked, registry, out);
        }
    }
    let _ = point;
    visit(
        NodeRef::Program(checked.program.program.value()),
        &NodePath::default(),
        checked,
        registry,
        &mut out,
    );
    out
}
fn attach_frame(
    record: &mut Value,
    checked: &CheckedProgram,
    scope: &NodePath,
    flows: &BTreeMap<(u32, u32), Vec<ColumnSource>>,
    frames: &mut BTreeMap<String, Value>,
) {
    let ty = record["resolved_type"].as_str().unwrap_or("");
    if !matches!(ty, "Box" | "Position") {
        record["frame_id"] = Value::Null;
        record["frame_status"] =
            json!({"status":"not_applicable","reason":"native resolved type has no cell frame"});
        return;
    }
    let mut found = Vec::new();
    if let Some(grids) = record["frame"]["grids"].as_array() {
        for grid in grids {
            let mut grid = grid.clone();
            if let (Some(label), Some(form)) =
                (grid["example"]["label_id"].as_u64(), scope.0.first())
            {
                let mut budget = SearchBudget::new();
                let (order, _) = CanonicalOrder::for_features(
                    &checked.program.program.value().forms[form.0 as usize],
                    &mut budget,
                );
                let choices = order
                    .label_scopes()
                    .iter()
                    .flat_map(|(_, labels)| labels.iter())
                    .filter(|(id, _)| u64::from(id.0) == label)
                    .map(|(_, p)| *p)
                    .collect::<Vec<_>>();
                if let Some(label) = choices.first() {
                    grid["example"]["label_id"] = json!(label);
                    grid["example"]["clause"] = json!(form.0);
                } else {
                    continue;
                }
            }
            let frame = add_frame(frames, json!({"kind":"grid","grid":grid,"parents":[]}));
            found.push(frame);
        }
    }
    if let (Some(form), Some(label)) = (scope.0.first(), record["label_id"].as_u64()) {
        if let Some(sources) = flows.get(&(form.0, label as u32)) {
            for source in sources {
                for frame in &source.frames {
                    if let Some(frame) = source_frame(checked, source, frame, frames) {
                        found.push(frame);
                    }
                }
            }
        }
    }
    found.sort();
    found.dedup();
    let frame = match found.len() {
        0 => None,
        1 => found.pop(),
        _ => Some(add_frame(
            frames,
            json!({"kind":"native_frame_evidence","parents":found}),
        )),
    };
    record["frame_id"] = json!(frame);
    record["frame_status"] = if frame.is_some() {
        json!({"status":"established"})
    } else {
        json!({"status":"unresolved","reason":"native prefix analysis establishes no frame"})
    };
}

fn canonical_export(program: &arclog::program::Program, point: &NodePath) -> Value {
    let owner = point.0[0].0;
    let mut prefix = Vec::new();
    let mut candidate = Value::Null;
    let mut missing = Vec::new();
    for (i, form) in program.forms.iter().enumerate() {
        let at = NodePath::top(i as u32);
        let canonical = features::canonical_clause(form, &at);
        if canonical["status"] != "complete" {
            missing.push(json!({"path":path_json(&at),"status":canonical["status"],"reason":canonical.get("reason")}));
        }
        if i as u32 == owner {
            candidate = canonical;
        } else {
            prefix.push(canonical);
        }
    }
    json!({"format":"native-canonical-clauses-v1","version":1,"status":if missing.is_empty(){"complete"}else{"partial"},"scope":"prefix_and_candidate",
        "algorithm_version":"arclog-canonical-feature-v2","digest_algorithm":"arclog StableHasher128","prefix":prefix,"candidate":candidate,"missing":missing,
        "rendering_format":"native canonical AST JSON; syntactic identity only",
        "preserved_order":["CHOOSE from/never whole written bodies (conservative)","OR/IF branches","positional IF/ALL/CHOOSE parts","fresh-first equality","key and OUT columns"],
        "unsupported_normalizations":["symmetric library relation interfaces","converse library relation interfaces"]})
}

pub fn export(program: &StudyProgram, point: &NodePath, registry: &Registry) -> Value {
    let normal_head = match program
        .program()
        .value()
        .forms
        .get(point.0.first().map_or(usize::MAX, |s| s.0 as usize))
    {
        Some(arclog::program::Form::Clause(c)) => format!("{:?}", c.value().keyword).to_uppercase(),
        Some(arclog::program::Form::Instance(_)) => "INIT".into(),
        Some(arclog::program::Form::Choose(_)) => "CHOOSE".into(),
        Some(arclog::program::Form::RigidDet(_)) => "RIGID_DET".into(),
        _ => "unsupported".into(),
    };
    let common = |format: &str, status: &str, reason: &str| json!({"format":format,"version":1,"status":status,"scope":"prefix_and_candidate","missing":[{"reason":reason}]});
    let syntax = match features::prefix(program, point) {
        Ok(p) => p,
        Err(reason) => {
            return json!({"normal_head":normal_head,"types_frames_v1":common("native-types-frames-v1","unsupported",&reason),"canonical_clauses_v1":common("native-canonical-clauses-v1","unsupported",&reason)});
        }
    };
    let canonical = canonical_export(syntax.value(), point);
    let checked = match features::checked_prefix(program, point, registry) {
        Ok(c) => c,
        Err(reason) => {
            return json!({"normal_head":normal_head,"types_frames_v1":common("native-types-frames-v1","unsupported",&reason),"canonical_clauses_v1":canonical});
        }
    };
    let mut typed = match features::prefix_label_names(program, &checked, registry)
        .and_then(|names| arclog::check::render_sites::export_with_names(&checked, registry, &names))
    {
        Ok(t) => t,
        Err(reason) => {
            return json!({"normal_head":normal_head,"types_frames_v1":common("native-types-frames-v1","unsupported",&reason),"canonical_clauses_v1":canonical});
        }
    };
    let found = label_frames(&checked, point, registry);
    let mut frames = BTreeMap::new();
    for key in ["variables", "arguments"] {
        if let Some(records) = typed[key].as_array_mut() {
            for record in records {
                if let Some(scope) = path(&record["scope_path"]) {
                    if let Some(id) = record["label_id"].as_u64() {
                        if let Some(ty) = checked
                            .types
                            .form(&scope)
                            .and_then(|f| f.label(LabelId(id as u32)))
                        {
                            record["resolved_type_identity"] = features::type_json(ty);
                        }
                    } else if let Some(ty) = record["resolved_type"]
                        .as_str()
                        .and_then(|name| arclog::study::render_terms::scalar_type(name).ok())
                    {
                        record["resolved_type_identity"] = features::type_json(&ty);
                    }
                    attach_frame(record, &checked, &scope, &found, &mut frames);
                    record["id"] = record["label_id"].clone();
                    if record.get("label_spelling").is_some() {
                        record["name"] = record["label_spelling"].clone();
                    }
                    record["status"] = json!(if record.get("resolved_type_identity").is_none()
                        || record["frame_status"]["status"] == "unresolved"
                    {
                        "partial"
                    } else {
                        "complete"
                    });
                }
            }
        }
    }
    let owner = point.0[0].0;
    let mut prefix = Vec::new();
    let mut candidate = Value::Null;
    let mut missing = Vec::new();
    for i in 0..checked.program.program.value().forms.len() {
        let at = NodePath::top(i as u32);
        let select = |key: &str| {
            typed[key]
                .as_array()
                .into_iter()
                .flatten()
                .filter(|v| {
                    path(&v["scope_path"])
                        .is_some_and(|p| p.0.first().is_some_and(|s| s.0 == i as u32))
                })
                .cloned()
                .collect::<Vec<_>>()
        };
        let labels = select("variables");
        let sites = select("arguments");
        let complete = labels
            .iter()
            .chain(&sites)
            .all(|r| r["status"] == "complete");
        for record in labels
            .iter()
            .chain(&sites)
            .filter(|r| r["status"] != "complete")
        {
            missing.push(json!({"clause_path":path_json(&at),"path":record.get("path"),"label_id":record["label_id"],"frame_status":record["frame_status"],"reason":"native type or frame is unresolved"}));
        }
        let clause = json!({"clause_id":format!("clause:{i}"),"path":path_json(&at),"labels":labels,"sites":sites,"status":if complete {"complete"} else {"partial"}});
        if i as u32 == owner {
            candidate = clause;
        } else {
            prefix.push(clause);
        }
    }
    json!({"normal_head":normal_head,"types_frames_v1":{"format":"native-types-frames-v1","version":1,"status":if missing.is_empty(){"complete"}else{"partial"},"scope":"prefix_and_candidate","prefix":prefix,"candidate":candidate,"frames":frames.into_values().collect::<Vec<_>>(),"missing":missing,"frame_identity_scope":"native prefix canonical form; source paths are locators only; unresolved evidence stays null"},
        "canonical_clauses_v1":canonical})
}
