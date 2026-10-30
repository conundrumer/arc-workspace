//! Structured native column/frame provenance; no task evaluation or decoding.
use super::*;
use crate::flows::{self, ColumnSource, Maker, SourceColumn, SourceFrame};
use arclog::eval::body_view::BodyView;
use arclog::eval::ir::Variable;
use arclog::mutation::path_json;
use arclog::study::StudyProgram;
use serde_json::{Value, json};

fn relation(reference: &RelationRef) -> Value {
    match reference {
        RelationRef::Fact(f) => json!({"kind":"fact","fact":format!("{f:?}")}),
        RelationRef::Lib(n) => json!({"kind":"library","id":format!("lib:{}",n.0)}),
        RelationRef::Declared(n) => json!({"kind":"declared","name":format!("{:?}",n.0)}),
        RelationRef::Output(n) => {
            json!({"kind":"output","owner":format!("{:?}",n.of),"path":n.path.iter().map(|s|format!("{s:?}")).collect::<Vec<_>>()})
        }
        RelationRef::DefinedPort(p) => json!({"kind":"input_port","port":p.0}),
    }
}
fn frame(f: &SourceFrame) -> Value {
    match f {
        SourceFrame::Read => json!({"kind":"read_source_column_frame"}),
        SourceFrame::Unknown => {
            json!({"kind":"native_unknown","reason":"native provenance cannot name this frame"})
        }
        SourceFrame::Made { maker, at, within } => {
            let definition = match maker {
                Maker::Relation { relation, column } => {
                    json!({"kind":"relation","registry_id":format!("lib:{}",relation.0),"column":format!("{column:?}")})
                }
                Maker::Output {
                    component,
                    output,
                    column,
                } => {
                    json!({"kind":"component_output","registry_id":format!("lib:{}",component.0),"output_port":output.0,"column":format!("{column:?}")})
                }
            };
            json!({"kind":"made","maker":definition,"maker_spelling":maker.spelled(),"path":path_json(at),"within":within.as_deref().map(frame)})
        }
    }
}
fn source(s: &ColumnSource) -> Value {
    json!({"kind":format!("{:?}",s.kind),"kind_code":s.kind as u8,
        "relation":s.relation.as_ref().map(relation),"source_relation_name":s.relation.as_ref().map(crate::columns::source_spelled),"source_column":match s.column {SourceColumn::None=>json!({"kind":"none"}),SourceColumn::Example=>json!({"kind":"entry_example"}),SourceColumn::Position(p)=>json!({"kind":"position","index":p})},
        "row_path":s.row.as_ref().map(|p|p.iter().map(|c|format!("{c:?}")).collect::<Vec<_>>()),
        "atom_path":path_json(&s.atom),"occurrence":s.occurrence,"frames":s.frames.iter().map(frame).collect::<Vec<_>>()})
}

pub fn export(
    program: &StudyProgram,
    registry: &Registry,
    settings: &arclog::stream::DecodeSettings,
) -> Result<Value, String> {
    let checked = program.checked();
    let written=program.written_stream(registry,settings).map_err(|d|d.message.to_string())?;
    let ordered=written.forms.iter().flat_map(|form|materialized_slots(program.program().value(),&written,form).map(move|slot|(form,slot))).collect::<Vec<_>>();
    let materialized=ordered.iter().map(|(_,slot)|*slot).collect::<std::collections::BTreeSet<_>>();
    let inventory=ordered.into_iter().enumerate().map(|(ordinal,(form,slot))| {
        json!({"relation_ordinal":ordinal,"table":EVIDENCE_FACTS.len()+ordinal,"form_path":path_json(&form.path),"relation_slot":slot,
            "source_name":relation_spelled(&written.relations[slot]),"native_selector":{"form":form.path.0.iter().map(|s|s.0.to_string()).collect::<Vec<_>>().join("."),"point":0,"relation":slot}})
    }).collect::<Vec<_>>();
    let names = arclog::write::label_names(program.program(), registry);
    let mut relations = Vec::new();
    for form in &written.forms {
        for slot in form.relations.clone() {
            let declared = &written.relations[slot];
            if !materialized.contains(&slot) {
                relations.push(json!({"relation_slot":slot,"source_name":relation_spelled(declared),"form_path":path_json(&form.path),
                    "materialized_table_expected":false,"schema_status":if form.readable.contains(&slot) {"native_export_omits_this_port"} else {"not_a_readable_relation_in_checked_program"},
                    "reason":if form.readable.contains(&slot) {"native alias/projection or unused specialized output; use INIT input_port_projection and its source relation schema"} else {"writer reserves this registry port slot, but this specialized checked instance defines no readable graph relation for it; registry declaration describes the port"}}));
                continue;
            }
            let graph =
                graph_relation(checked, registry, &form.path, declared).ok_or_else(|| {
                    format!(
                        "no native graph relation for slot {slot} at {:?}",
                        form.path
                    )
                })?;
            let types = checked
                .types
                .columns(&graph)
                .ok_or_else(|| format!("no native relation column types for slot {slot}"))?;
            let flows = flows::column_flows(
                checked,
                graph.node,
                graph.output.as_deref(),
                types,
                registry,
            );
            let placements = flows::column_placements(
                checked,
                graph.node,
                graph.output.as_deref(),
                &form.path,
                types.len(),
                registry,
            );
            if flows.len() != types.len() || placements.len() != types.len() {
                return Err(format!(
                    "native frame/schema width mismatch for slot {slot}"
                ));
            }
            let column_names = graph
                .output
                .is_none()
                .then(|| checked.program.column_names(graph.node))
                .flatten()
                .filter(|n| n.len() == types.len())
                .unwrap_or_else(|| (0..types.len()).map(|i| format!("c{i}")).collect());
            let columns=types.iter().enumerate().map(|(i,ty)| {
                let label=placements[i].and_then(|p|p.label);
                json!({"column":i,"name":column_names[i],"type":format!("{ty:?}"),"label_id":label.map(|l|l.0),
                    "label_spelling":label.and_then(|l|names[form.path.0[0].0 as usize].iter().find(|(id,_)|*id==l).map(|(_,n)|n.as_ref())),
                    "frame_applicable":arclog::registry::has_frame(ty),"sources":flows[i].iter().map(source).collect::<Vec<_>>()})
            }).collect::<Vec<_>>();
            relations.push(json!({"relation_slot":slot,"source_name":relation_spelled(declared),"form_path":path_json(&form.path),
                "materialized_table_expected":true,"columns":columns,
                "native_selector":{"form":form.path.0.iter().map(|s|s.0.to_string()).collect::<Vec<_>>().join("."),"point":0,"relation":slot}}));
        }
    }
    let mut bodies = Vec::new();
    for point in program.mutation_points() {
        let view = BodyView::at(checked, &point.body).map_err(|e| e.message.to_string())?;
        // Query provenance for every native lexical variable, including branch
        // locals. This does not change the evaluated body or its result schema.
        let mut all = view.clause.clone();
        all.columns = (0..all.variables.len())
            .map(|i| Variable(i as u16))
            .collect();
        let flows = flows::body_column_flows(checked, &all, &view.paths, registry);
        if flows.len() != all.variables.len() {
            return Err("native body provenance width mismatch".into());
        }
        let variables=all.variables.iter().enumerate().map(|(i,v)| {
            let label=view.paths.labels[i];
            json!({"variable":i,"label_id":label.0,"type":format!("{:?}",v.ty),"body_column":view.column_of(label),
                "frame_applicable":arclog::registry::has_frame(&v.ty),"sources":flows[i].iter().map(source).collect::<Vec<_>>()})
        }).collect::<Vec<_>>();
        bodies.push(json!({"body_path":path_json(&point.body),"owner_path":path_json(&view.form),"variables":variables}));
    }
    Ok(
        json!({"schema":"arclog-study-frame-sources-v1","complete":true,"relations":relations,"bodies":bodies,
        "table_inventory":{"complete":true,"evidence_table_count":EVIDENCE_FACTS.len(),"relation_table_count":inventory.len(),"table_count":EVIDENCE_FACTS.len()+inventory.len(),
            "evidence_facts":EVIDENCE_FACTS.iter().map(|f|format!("{f:?}")).collect::<Vec<_>>(),"relations":inventory,
            "contract":"exact original study gold_tables enumeration before bounded packing; no task evaluation; includes faults as table positions, omits native aliases"},
        "frame_contract":"native static provenance; read_source_column_frame resolves through its source relation/column; native_unknown is explicit, not an unsupported-node omission",
        "runtime_extent_contract":"resolve per-example/per-assignment frame sizes and coordinates using supplied native table frames/extents; this API evaluates no task"}),
    )
}
