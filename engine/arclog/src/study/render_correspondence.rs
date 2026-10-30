//! Export-local correspondence from the native writer, resolver and BODY compiler.
use super::StudyProgram;
use crate::check::CheckedProgram;
use crate::mutation::path_json;
use crate::program::LabelId;
use crate::program::path::{NodePath, NodeRef, node_at};
use crate::registry::Registry;
use crate::stream::{DecodeSettings, Vocabulary, WrittenStream};
use crate::types::ValueType;
use serde_json::{Value, json};
use std::collections::{BTreeMap, BTreeSet};

fn path(value: &Value) -> Option<NodePath> {
    Some(NodePath(
        value
            .as_array()?
            .iter()
            .map(|v| {
                v.as_u64()
                    .and_then(|v| u32::try_from(v).ok())
                    .map(crate::program::path::PathStep)
            })
            .collect::<Option<Vec<_>>>()?
            .into(),
    ))
}
fn top(at: &NodePath) -> NodePath {
    NodePath(at.0.iter().take(1).copied().collect())
}
fn label(node: NodeRef<'_>) -> Option<LabelId> {
    match node {
        NodeRef::Label(v) => crate::types::use_label(*v),
        _ => None,
    }
}
pub fn type_json(ty: &ValueType) -> Value {
    json!({"type":format!("{ty:?}"),"wire_type":format!("{:?}",if matches!(ty,ValueType::Pose(_)){&ValueType::D4}else{ty}),
        "cell_width":if ty.is_box(){4}else{1},"nominal":matches!(ty,ValueType::Pose(_))})
}

// A node is paired only when its own native writer-token coverage and node
// kind agree uniquely. Empty/ambiguous emissions remain explicitly unmapped.
fn trace_paths(
    source: &CheckedProgram,
    target: &CheckedProgram,
    a: &WrittenStream,
    b: &WrittenStream,
) -> BTreeMap<NodePath, NodePath> {
    let traces = |checked: &CheckedProgram, written: &WrittenStream| {
        let mut tokens: BTreeMap<NodePath, Vec<usize>> = BTreeMap::new();
        for (i, at) in written.paths.iter().enumerate() {
            for n in 0..=at.0.len() {
                tokens
                    .entry(NodePath(at.0[..n].into()))
                    .or_default()
                    .push(i);
            }
        }
        fn walk(
            node: NodeRef<'_>,
            at: &NodePath,
            tokens: &BTreeMap<NodePath, Vec<usize>>,
            out: &mut BTreeMap<(String, Vec<usize>), Vec<NodePath>>,
        ) {
            if let Some(indices) = tokens.get(at) {
                let mut kind = format!("{:?}", std::mem::discriminant(&node));
                if let NodeRef::Conjunct(c) = node {
                    kind.push_str(&format!("{:?}", std::mem::discriminant(c)));
                }
                out.entry((kind, indices.clone()))
                    .or_default()
                    .push(at.clone());
            }
            for (i, n) in node.children().into_iter().enumerate() {
                walk(n, &at.child(i as u32), tokens, out);
            }
        }
        let mut out = BTreeMap::new();
        walk(
            NodeRef::Program(checked.program.program.value()),
            &NodePath::default(),
            &tokens,
            &mut out,
        );
        out
    };
    let before = traces(source, a);
    let after = traces(target, b);
    let mut out = BTreeMap::new();
    for (key, targets) in after {
        if let (Some(sources), [target]) = (before.get(&key), targets.as_slice()) {
            if let [source] = sources.as_slice() {
                out.insert(target.clone(), source.clone());
            }
        }
    }
    out
}

/// source is explicit for a second representation. Mutants bridge through
/// their certified original gold and its exact edit path correspondence.
pub fn export(
    program: &StudyProgram,
    source: &StudyProgram,
    registry: &Registry,
    settings: &DecodeSettings,
    current: &Value,
    _source_export: &Value,
    gold: Option<&CheckedProgram>,
    edits: Option<&Value>,
) -> Result<Value, String> {
    let checked = program.checked();
    let origin = source.checked();
    let bridge = gold.unwrap_or(checked);
    let vocabulary = Vocabulary::new(registry, settings);
    let a = source
        .written_stream(registry, settings)
        .map_err(|e| e.message.to_string())?;
    let b =
        crate::stream::written_stream(bridge, &vocabulary).map_err(|e| e.message.to_string())?;
    let actual = program
        .written_stream(registry, settings)
        .map_err(|e| e.message.to_string())?;
    let same = std::ptr::eq(origin.as_ref(), bridge);
    let equal = a.tokens == b.tokens;
    let mut mapping = BTreeMap::new();
    let mut labels: BTreeMap<(NodePath, u32), BTreeSet<(NodePath, u32)>> = BTreeMap::new();
    let bridge_paths = if same {
        let mut out = BTreeMap::new();
        fn walk(node: NodeRef<'_>, at: &NodePath, out: &mut BTreeMap<NodePath, NodePath>) {
            out.insert(at.clone(), at.clone());
            for (i, n) in node.children().into_iter().enumerate() {
                walk(n, &at.child(i as u32), out);
            }
        }
        walk(
            NodeRef::Program(bridge.program.program.value()),
            &NodePath::default(),
            &mut out,
        );
        out
    } else if equal {
        trace_paths(origin, bridge, &a, &b)
    } else {
        BTreeMap::new()
    };
    if same || equal {
        // WrittenForm.labels is the writer's explicit source LabelId at each
        // stream label slot. No correspondence is inferred from spellings.
        for bf in &b.forms {
            if let Some(af) = a.forms.iter().find(|af| af.tokens == bf.tokens) {
                if af.labels.len() == bf.labels.len() {
                    for (native, source) in bf.labels.iter().zip(&af.labels) {
                        labels
                            .entry((bf.path.clone(), native.0))
                            .or_default()
                            .insert((af.path.clone(), source.0));
                    }
                }
            }
        }
    }
    let root = NodeRef::Program(checked.program.program.value());
    let bridge_root = NodeRef::Program(bridge.program.program.value());
    if let Some(edits) = edits.and_then(Value::as_array) {
        let mut changed_labels = BTreeMap::new();
        for edit in edits {
            if edit["status"] != "preserved" {
                continue;
            }
            let (Some(before), Some(after)) =
                (path(&edit["before_path"]), path(&edit["after_path"]))
            else {
                continue;
            };
            if let Some(source) = bridge_paths.get(&before) {
                mapping.insert(after.clone(), source.clone());
            }
            if let (Some(before_label), Some(after_label)) = (
                node_at(bridge_root, &before).and_then(label),
                node_at(root, &after).and_then(label),
            ) {
                if let Some(found) = labels.get(&(top(&before), before_label.0)) {
                    changed_labels
                        .entry((top(&after), after_label.0))
                        .or_insert_with(BTreeSet::new)
                        .extend(found.iter().cloned());
                }
            }
        }
        labels = changed_labels;
    } else {
        mapping = bridge_paths;
    }
    let names = source.label_names(registry);
    let canonical = |form: &NodePath, id: LabelId| -> Value {
        let identity = BTreeSet::from([(form.clone(), id.0)]);
        let candidates = if same && gold.is_none() {
            Some(&identity)
        } else {
            labels.get(&(form.clone(), id.0))
        };
        let found = candidates.filter(|c| c.len() == 1).and_then(|c| c.first());
        match found {
            Some((form, id)) => {
                let ty = crate::eval::ir::label_types(origin, form)
                    .label(LabelId(*id))
                    .cloned();
                json!({"status":if ty.is_some(){"resolved"}else{"unsupported_type"},"scope_path":path_json(form),"label_id":id,
                "name":form.0.first().and_then(|s|names.get(s.0 as usize)).and_then(|n|n.iter().find(|(l,_)|l.0==*id)).map(|(_,s)|s.as_ref()),
                "source_type":ty.as_ref().map(type_json)})
            }
            None => {
                json!({"status":"unsupported","reason":"no unique native source-label correspondence", "candidates":candidates.into_iter().flatten().map(|(form,id)|json!({"scope_path":path_json(form),"label_id":id})).collect::<Vec<_>>()})
            }
        }
    };
    let mut bodies = Vec::new();
    for view in current["body_views"].as_array().into_iter().flatten() {
        let Some(at) = path(&view["body_path"]) else {
            continue;
        };
        let form = top(&at);
        let native = crate::eval::body_view::BodyView::at(checked, &at)
            .map_err(|e| e.message.to_string())?;
        let before = mapping.get(&at);
        let source_view =
            before.and_then(|at| crate::eval::body_view::BodyView::at(origin, at).ok());
        let fields=native.clause.columns.iter().enumerate().map(|(column,v)| {
            let id=native.paths.labels[v.0 as usize];let ty=&native.clause.variables[v.0 as usize].ty;
            let source=canonical(&form,id);
            let source_column=source["label_id"].as_u64().and_then(|l|u32::try_from(l).ok()).and_then(|l|source_view.as_ref()?.column_of(LabelId(l)));
            json!({"physical_column":column,"body_column":column,"scope_path":path_json(&form),"label_id":id.0,
                "physical_type":type_json(ty),"canonical_source":source,"source_body_column":source_column})
        }).collect::<Vec<_>>();
        let keys=view["group_key_label_ids"].as_array().into_iter().flatten().map(|id| {
            let label=id.as_u64().and_then(|n|u32::try_from(n).ok()).map(LabelId);
            let column=label.and_then(|l|native.column_of(l));
            json!({"label_id":id,"body_column":column,"status":if column.is_some(){"body_column"}else{"requires_native_key_context"},
                "canonical_source":label.map(|l|canonical(&form,l))})
        }).collect::<Vec<_>>();
        let projection = view["input_port_projection"]
            .as_array()
            .into_iter()
            .flatten()
            .map(|entry| {
                let mut entry = entry.clone();
                let source = entry["label_id"]
                    .as_u64()
                    .and_then(|l| u32::try_from(l).ok())
                    .map(|l| canonical(&form, LabelId(l)));
                let source_port_columns = before
                    .and_then(|at| {
                        _source_export["body_views"]
                            .as_array()?
                            .iter()
                            .find(|v| path(&v["body_path"]).as_ref() == Some(at))
                    })
                    .and_then(|v| v["input_port_projection"].as_array())
                    .into_iter()
                    .flatten()
                    .filter(|e| {
                        source.as_ref().is_some_and(|s| {
                            s["status"] == "resolved" && s["label_id"] == e["label_id"]
                        })
                    })
                    .map(|e| e["port_column"].clone())
                    .collect::<Vec<_>>();
                entry["canonical_source"] = json!(source);
                entry["source_port_columns"] = json!(source_port_columns);
                entry
            })
            .collect::<Vec<_>>();
        let dependency_nodes = match (&native.input, node_at(root, &form)) {
            (Some(port), Some(NodeRef::Instance(instance))) => {
                let relation = crate::program::RelationRef::Output(crate::program::OutputName {
                    of: crate::program::OutputOwner::Instance(instance.name.clone()),
                    path: vec![crate::program::OutputStep::Port(port.clone())].into(),
                });
                checked
                    .program
                    .program_read(&relation)
                    .map(|node| vec![node.0])
            }
            _ => Some(
                checked
                    .program
                    .nodes_of(&form)
                    .iter()
                    .map(|n| n.0)
                    .collect::<Vec<_>>(),
            ),
        };
        bodies.push(json!({"body_path":path_json(&at),"owner_path":view["owner_path"],"scope":view["scope"],"kind":view["kind"],
            "source_body_path":before.map(path_json),"source_status":if before.is_some(){"resolved"}else{"unsupported"},
            "graph_nodes":checked.program.nodes_of(&form).iter().map(|n|n.0).collect::<Vec<_>>(),"dependency_nodes":dependency_nodes,"columns":fields,"input_port":view["input_port"],"input_port_projection":projection,"group_key_projection":keys,
            "input_port_columns":view["input_port_columns"],"group_key_label_ids":view["group_key_label_ids"]}));
    }
    let mut relations = Vec::new();
    for relation in current["definitions"]["native_relations"]
        .as_array()
        .into_iter()
        .flatten()
    {
        let source_slot = relation["relation_slot"]
            .as_u64()
            .and_then(|slot| actual.relations.get(slot as usize))
            .and_then(|relation| b.relations.iter().position(|before| before == relation));
        let fields=relation["column_witnesses"].as_array().into_iter().flatten().map(|field| {
            let aliases=field["bindings"].as_array().into_iter().flatten().map(|binding| {
                let original=path(&binding["definition_path"]).zip(binding["label_id"].as_u64()).and_then(|(form,l)|u32::try_from(l).ok().map(|l|canonical(&form,LabelId(l))));
                json!({"native_binding":binding,"canonical_source":original})
            }).collect::<Vec<_>>();
            let mut candidates=Vec::new();
            // Native writer relation slots identify declarations across an
            // equal stream. Physical columns are matched by proven local
            // bindings, never by their header ordinal or printed type.
            if same || equal {for source_relation in _source_export["definitions"]["native_relations"].as_array().into_iter().flatten().filter(|r|source_slot.is_some_and(|slot|r["relation_slot"].as_u64()==Some(slot as u64))) {
                for source_field in source_relation["column_witnesses"].as_array().into_iter().flatten() {
                    let matches=source_field["bindings"].as_array().into_iter().flatten().any(|binding|aliases.iter().any(|a|a["canonical_source"]["status"]=="resolved" && a["canonical_source"]["scope_path"]==binding["definition_path"] && a["canonical_source"]["label_id"]==binding["label_id"]));
                    if matches || (same && gold.is_none() && source_field["physical_column"]==field["physical_column"]) {candidates.push(json!({"physical_column":source_field["physical_column"],"physical_type":source_field["physical_type"],"native_selector":source_relation["native_selector"]}));}
                }
            }}
            json!({"physical_column":field["physical_column"],"physical_type":field["physical_type"],"row_path":field["row_path"],
                "logical_slot":field["logical_slot"],"aliases":aliases,"selected_header_binding":field["selected_header_binding"],
                "source_columns":candidates,"source_status":if candidates.is_empty(){"unsupported"}else{"resolved_aliases"}})
        }).collect::<Vec<_>>();
        let mut row = relation.clone();
        row["columns"] = json!(fields);
        row["source_relation_slot"] = json!(source_slot);
        row["canonical_source_relation"]=_source_export["definitions"]["native_relations"].as_array().into_iter().flatten().find(|r|source_slot.is_some_and(|slot|r["relation_slot"].as_u64()==Some(slot as u64))).map(|r|json!({"relation":r["relation"],"source_name":r["source_name"],"display_name":r["display_name"],"native_selector":r["native_selector"]})).unwrap_or(Value::Null);
        relations.push(row);
    }
    let mut readers = Vec::new();
    for argument in current["typed_sites"]["arguments"]
        .as_array()
        .into_iter()
        .flatten()
    {
        let Some(at) = path(&argument["path"]) else {
            continue;
        };
        let mut atom = None;
        let mut negation_depth = 0usize;
        for n in 0..=at.0.len() {
            let prefix = NodePath(at.0[..n].into());
            if let Some(node) = node_at(root, &prefix) {
                if matches!(node, NodeRef::Conjunct(crate::program::Conjunct::Not(_))) {
                    negation_depth += 1;
                }
                if node.atom().is_some() {
                    atom = Some(prefix);
                }
            }
        }
        let Some(occurrence) = atom else { continue };
        let resolution = match checked.program.resolution(&occurrence) {
            Some(crate::resolver::Resolution::Node(n)) => {
                json!({"kind":"node","graph_node":n.0,"graph_kind":format!("{:?}",checked.program.graph.nodes[n.0 as usize].kind)})
            }
            Some(crate::resolver::Resolution::Lib(n)) => json!({"kind":"library","name":n.0}),
            other => json!({"kind":"unsupported","native":format!("{other:?}")}),
        };
        let scalar_column = checked
            .program
            .column_position(&at)
            .or_else(|| {
                path(&argument["site_path"]).and_then(|p| checked.program.column_position(&p))
            })
            .map(|p| p.0);
        let input = node_at(root, &occurrence)
            .and_then(|n| n.atom())
            .is_some_and(|atom| {
                matches!(
                    atom.relation,
                    crate::program::RelationRef::Fact(crate::program::FactRelation::Input)
                )
            });
        let source_column = scalar_column.and_then(|column| {
            crate::eval::read_coordinates::ReadCoordinates::new(
                input,
                checked.program.reads_lifted(&occurrence),
            )
            .source(column)
        });
        let entry_axis =
            source_column == Some(crate::eval::read_coordinates::SourceColumn::Example);
        let header_column = match source_column {
            Some(crate::eval::read_coordinates::SourceColumn::Position(column)) => Some(column),
            _ => None,
        };
        let header_relation = node_at(root, &occurrence)
            .and_then(|n| n.atom())
            .map(|atom| {
                if input {
                    crate::program::RelationRef::Fact(crate::program::FactRelation::ExInput)
                } else {
                    atom.relation.clone()
                }
            });
        let header_graph = header_relation
            .as_ref()
            .and_then(|relation| checked.program.program_read(relation))
            .map(|node| node.0);
        let body_columns=bodies.iter().filter(|body|path(&body["body_path"]).is_some_and(|body|occurrence.0.starts_with(&body.0))).map(|body| {
            let columns=body["columns"].as_array().into_iter().flatten().filter(|c|c["label_id"]==argument["label_id"]).map(|c|c["physical_column"].clone()).collect::<Vec<_>>();
            json!({"body_path":body["body_path"],"physical_columns":columns,"entry_axis_binding":false,"source_entry_axis_binding":entry_axis,
                "status":if !columns.is_empty(){"physical_columns"}else if entry_axis{"requires_source_entry_context"}else{"unsupported"}})
        }).collect::<Vec<_>>();
        let out_role = if matches!(node_at(root, &top(&at)), Some(NodeRef::Out(_))) {
            "out_definition"
        } else if node_at(root, &occurrence)
            .and_then(|n| n.atom())
            .is_some_and(|a| {
                matches!(
                    a.relation,
                    crate::program::RelationRef::Fact(crate::program::FactRelation::ExOutput)
                )
            })
        {
            "train_output_evidence"
        } else {
            "none"
        };
        readers.push(json!({"occurrence_path":path_json(&occurrence),"argument_path":path_json(&at),"scope_path":argument["scope_path"],
            "site_path":argument["site_path"],"label_id":argument["label_id"],"resolved_type":argument["resolved_type"],"column_type":argument["column_type"],
            "kind":if matches!(node_at(root,&occurrence),Some(NodeRef::Conjunct(crate::program::Conjunct::Not(_)))){"not"}else{"atom"},
            "negation_depth":negation_depth,"polarity":if negation_depth%2==0{"positive"}else{"negative"},"resolution":resolution,"scalar_column":scalar_column,"header_column":header_column,"input_alias_ex_input":input,
            "header_key":{"relation":header_relation.as_ref().map(crate::mutation::relation_json),"graph_node":header_graph,"physical_column":header_column},
            "column_path":argument["column_path"],"physical_type":argument["type_identity"],"body_columns":body_columns,"out_role":out_role,
            "lifted":checked.program.reads_lifted(&occurrence),"train_only":checked.program.reads_train_examples(&occurrence),
            "entry_axis_binding":entry_axis,"entry_axis_owner":if entry_axis{json!("read_source_relation")}else{Value::Null},"source_argument_path":mapping.get(&at).map(path_json),
            "canonical_source":argument["label_id"].as_u64().and_then(|l|u32::try_from(l).ok()).map(|l|canonical(&top(&at),LabelId(l)))}));
    }
    // Candidate syntax/layout links contain no source/gold identities or
    // later-port inventory. Feature type/frame safety is a separate export.
    let point_names = program.label_names(registry);
    let mut feature_points = Vec::new();
    for point in program.mutation_points() {
        let view = crate::eval::body_view::BodyView::at(checked, &point.body)
            .map_err(|e| e.message.to_string())?;
        let mut declarations = Vec::new();
        fn made(
            node: NodeRef<'_>,
            at: &NodePath,
            out: &mut Vec<(LabelId, NodePath, &'static str)>,
        ) {
            if let NodeRef::Label(use_) = node {
                let value = match use_ {
                    crate::program::LabelUse::Fresh(l) => Some((*l, "fresh")),
                    crate::program::LabelUse::Key(l) => Some((*l, "key")),
                    _ => None,
                };
                if let Some((l, kind)) = value {
                    out.push((l, at.clone(), kind));
                }
            }
            for (i, n) in node.children().into_iter().enumerate() {
                made(n, &at.child(i as u32), out);
            }
        }
        if let Some(node) = node_at(root, &point.body) {
            made(node, &point.body, &mut declarations);
        }
        let columns=view.clause.columns.iter().enumerate().map(|(i,v)|{
            let label=view.paths.labels[v.0 as usize];
            let occurrences=declarations.iter().enumerate().filter(|(_, (id,_,_))|*id==label).map(|(ordinal,(_,at,kind))|json!({"path":path_json(at),"creation_ordinal":ordinal,"use":kind})).collect::<Vec<_>>();
            json!({"physical_column":i,"label_id":label.0,"scope_path":path_json(&view.form),"native_label_name":point_names.get(view.form.0[0].0 as usize).and_then(|n|n.iter().find(|(id,_)|*id==label)).map(|(_,s)|s.as_ref()),"declarations":occurrences})
        }).collect::<Vec<_>>();
        let parent = NodePath(point.body.0[..point.body.0.len() - 1].into());
        let key = match node_at(root, &parent) {
            Some(NodeRef::KeyClause(key)) => {
                json!({"columns":key.key.columns.iter().enumerate().map(|(index,c)|json!({"key_column":index,"name":super::render::column(&c.name),"label_id":c.label.0,"body_column":view.column_of(c.label)})).collect::<Vec<_>>() })
            }
            _ => Value::Null,
        };
        let head = match node_at(root, &parent) {
            Some(NodeRef::InstanceInput(input)) => json!({"port":input.name.0,
            "head_sites":input.head.iter().map(crate::mutation::site_json).collect::<Vec<_>>(),"body_child_index":input.head.len(),
            "body_child_meaning":"after the head sites; the index is the head-site count, not the input-port ordinal"}),
            _ => Value::Null,
        };
        let path_steps = (1..=point.body.0.len())
            .map(|n| {
                let at = NodePath(point.body.0[..n].into());
                let parent = NodePath(point.body.0[..n - 1].into());
                let role = match node_at(root, &parent) {
                    Some(NodeRef::Program(_)) => "form",
                    Some(NodeRef::Instance(i)) => {
                        if i.key.is_some() && at.0[n - 1].0 == 0 {
                            "key_clause"
                        } else {
                            "input_port"
                        }
                    }
                    Some(NodeRef::KeyClause(_)) => {
                        if at.0[n - 1].0 == 0 {
                            "key_body"
                        } else {
                            "keyed_input_port"
                        }
                    }
                    Some(NodeRef::InstanceInput(_)) => "input_body",
                    _ => "native_child",
                };
                json!({"path":path_json(&at),"index":at.0[n-1].0,"role":role})
            })
            .collect::<Vec<_>>();
        feature_points.push(json!({"body_path":path_json(&point.body),"owner_path":path_json(&view.form),"kind":point.kind,
            "result_kind":"body_witness_rows","columns":columns,"init_input":head,"init_key":key,"path_steps":path_steps,
            "contract":"actual candidate BODY physical column mapping and native head/path syntax; no gold or later-clause identity lookup"}));
    }
    let reader_occurrences=current["definitions"]["readers"].as_array().into_iter().flatten().filter_map(|r| {
        let at=path(&r["reader_path"])?;
        node_at(root,&at).and_then(|n|n.atom())?;
        Some(json!({"occurrence_path":path_json(&at),"resolution":r["resolution"],
            "scalar_arguments":readers.iter().filter(|a|path(&a["occurrence_path"]).as_ref()==Some(&at)).map(|a|a["argument_path"].clone()).collect::<Vec<_>>() }))
    }).collect::<Vec<_>>();
    let node_gaps=current["nodes"].as_array().into_iter().flatten().filter_map(|node| {
        let at=path(&node["path"])?;
        (!mapping.contains_key(&at)).then(||json!({"path":path_json(&at),"status":"unsupported","reason":"no unique native emitter/edit-path correspondence"}))
    }).collect::<Vec<_>>();
    let mut out = match super::render_out::export(program) {
        Ok(mut out) => {
            out["status"] = "resolved".into();
            out
        }
        Err(reason) => json!({"status":"unsupported","reason":reason}),
    };
    if let Some(form) = path(&out["path"]) {
        if let Some(columns) = out["columns"].as_array_mut() {
            for column in columns {
                if let Some(id) = column["label_id"]
                    .as_u64()
                    .and_then(|l| u32::try_from(l).ok())
                {
                    column["canonical_source"] = canonical(&form, LabelId(id));
                }
            }
        }
    }
    Ok(
        json!({"schema":"arclog-study-correspondence-v1","program_sexp":program.sexp(registry),"source_program_sexp":source.sexp(registry),
        "source_bridge_status":if same {"same_checked_representation"}else if equal {"native_writer_trace"}else{"unsupported"},
        "writer_tokens_equal":equal,"representation":if gold.is_some(){"certified_mutant"}else if program.layout().is_some(){"parsed"}else{"native_ast"},
        "source_representation":if source.layout().is_some(){"parsed"}else{"native_ast"},"id_scope":"exact program_sexp/source_program_sexp pair; scoped LabelIds and graph IDs are not global",
        "body_domain":{"complete":true,"meaning":"all mutation-point BODY views; OUT has its own projection","count":bodies.len()},
        "reader_domain":{"complete":true,"meaning":"all resolved AST atom occurrences, including zero-scalar reads; INIT heads, component/proposer declarations are not reader scalar arguments","occurrences":reader_occurrences},
        "bodies":bodies,"readers":readers,"node_gaps":node_gaps,"relations":relations,"out":out,
        "feature_points":feature_points,"mutation_paths":edits,"relation_source_names":current["relation_source_names"],"table_inventory":current["frame_sources"]["table_inventory"],
        "nodes":mapping.iter().map(|(to,from)|json!({"path":path_json(to),"source_path":path_json(from)})).collect::<Vec<_>>(),
        "identity_contract":"IDs are scoped to these exact programs. Unmapped, replaced and deleted nodes have no inferred identity. Table snapshot refs, indices and all/kept roles are separate runtime identities."}),
    )
}
