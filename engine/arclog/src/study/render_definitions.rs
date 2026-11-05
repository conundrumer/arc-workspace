//! Resolved program readers and the entire embedded library definition closure.
use super::StudyProgram;
use super::render::{column, name, program_relation};
use crate::mutation::{path_json, relation_json};
use crate::program::path::{NodePath, NodeRef};
use crate::program::*;
use crate::read::SExpr;
use crate::registry::{LibEntry, Macro, ProposerKind, Registry};
use crate::resolver::{DependencyKind, GraphNodeIndex, Resolution};
use serde_json::{Value, json};

pub fn column_witnesses(checked: &crate::check::CheckedProgram, registry: &Registry, relation: &ProgramRelation, form: &NodePath) -> (String, Vec<Value>, Value) {
    use crate::resolver::given::BindingProof;
    let reference=match relation {ProgramRelation::Declared(n)=>RelationRef::Declared(n.clone()),ProgramRelation::Output(n)=>RelationRef::Output(n.clone())};
    let Some(node)=checked.program.program_read(&reference) else {return ("unsupported_relation".into(),Vec::new(),Value::Null)};
    let output=match (&checked.program.graph.nodes[node.0 as usize].kind,relation) {
        (DependencyKind::RigidAssembly(_) | DependencyKind::RecursiveInstance(_),ProgramRelation::Output(n))=>Some(n.path.clone()),
        _=>None,
    };
    let graph=crate::types::GraphRelation {node,output};
    let Some(types)=checked.types.columns(&graph) else {return ("unsupported_schema".into(),Vec::new(),Value::Null)};
    let columns=checked.program.column_bindings(node,graph.output.as_deref(),form,types.len(),registry);
    let native_names=checked.program.column_names(node);
    let proof=|p|match p {
        BindingProof::ResolverLabelPosition=>"resolver_label_position",
        BindingProof::DeclaredLayout=>"declared_layout",
        BindingProof::ResolvedRowPath=>"resolved_row_path",
    };
    let columns=columns.iter().zip(types).enumerate().map(|(physical,(c,ty))| {
        let bindings=c.bindings.iter().map(|b| {
            let scope=crate::eval::ir::scope_of(checked,&b.form.join(&b.body));
            let field_type=checked.types.form(&scope).and_then(|f|f.label(b.label));
            json!({"definition_path":path_json(&b.form),"scope_path":path_json(&scope),"body_path":path_json(&b.form.join(&b.body)),
                "output_identity":program_relation(relation),"label_id":b.label.0,"logical_slot":b.slot,
                "source_column_path":b.source_path.iter().map(column).collect::<Vec<_>>(),
                "field_type":field_type.map(|t|format!("{t:?}")),"field_type_identity":field_type.map(super::render_correspondence::type_json),"proof":proof(b.proof),
                "status":if field_type.is_some(){"resolved"}else{"unsupported_label_type"}})
        }).collect::<Vec<_>>();
        let selected=c.selected_header_binding.and_then(|i|bindings.get(i)).cloned();
        let status=if c.placement.is_none() {"unsupported"} else if c.declared_without_local_label {"declared_without_local_label"}
            else if selected.as_ref().is_some_and(|s|s["status"]=="resolved") {"resolved"} else {"unsupported"};
        json!({"physical_column":physical,"type":format!("{ty:?}"),"physical_type":super::render_correspondence::type_json(ty),
            "row_path":c.row_path.as_ref().map(|p|p.iter().map(column).collect::<Vec<_>>()),
            "native_name":native_names.as_ref().and_then(|n|n.get(physical)),
            "definition_path":path_json(form),"relation":program_relation(relation),"status":status,
            "logical_slot":c.placement.map(|p|p.slot),"proof":c.proof.map(proof),
            "bindings":bindings,"selected_header_binding":selected})
    }).collect();
    ("complete".into(),columns,json!({"graph_node":node.0,"output":graph.output.as_ref().map(|p|format!("{p:?}")),"kind":format!("{:?}",checked.program.graph.nodes[node.0 as usize].kind)}))
}

fn expression(e: &SExpr) -> Value {
    match e {
        SExpr::Symbol { text, .. } => json!({"symbol":text}),
        SExpr::String { text, .. } => json!({"string":text}),
        SExpr::List { items, .. } => {
            json!({"list":items.iter().map(expression).collect::<Vec<_>>()})
        }
    }
}
fn ast_reads(node: NodeRef<'_>, out: &mut Vec<Value>) {
    if let Some(a) = node.atom() {
        let r = relation_json(&a.relation);
        if !out.contains(&r) {
            out.push(r);
        }
    }
    for child in node.children() {
        ast_reads(child, out);
    }
}
fn registry_export_uncached(registry: &Registry) -> Result<Value, String> {
    let mut forms = std::collections::BTreeMap::new();
    let mut implementations = std::collections::BTreeMap::new();
    for (source, text, into) in [
        (
            crate::layout::SourceFile::LibRegistry,
            crate::registry::REGISTRY_TEXT,
            &mut forms,
        ),
        (
            crate::layout::SourceFile::LibProposers,
            crate::registry::PROPOSERS_TEXT,
            &mut implementations,
        ),
    ] {
        let (sexps, _) =
            crate::read::read_sexprs(text, source).map_err(|d| super::diagnostics_text(&d))?;
        for e in sexps {
            if let SExpr::List { items, place, .. } = &e {
                if let Some(SExpr::Symbol { text: name, .. }) = items.get(1) {
                    into.insert(name.to_string(),json!({"definition":expression(&e),"sexp":&text[place.start as usize..place.end as usize]}));
                }
            }
        }
    }
    let mut entries = Vec::new();
    let mut names = registry.names().collect::<Vec<_>>();
    names.sort_by_key(|n| &n.0);
    for lib in names {
        let entry = registry
            .entry(lib)
            .ok_or_else(|| format!("registry entry disappeared: {}", lib.0))?;
        let mut reads = Vec::new();
        let (kind, implementation, ports) = match entry {
            LibEntry::Relation(_) => ("relation", "native_algebra", Value::Null),
            LibEntry::Macro(Macro::Relation { definition, .. }) => {
                ast_reads(NodeRef::Body(definition.value()), &mut reads);
                ("macro", "arclog", Value::Null)
            }
            LibEntry::Proposer(p) => {
                let implementation = match &p.kind {
                    ProposerKind::Native { .. } => "native_proposer",
                    ProposerKind::Arclog { body } => {
                        ast_reads(NodeRef::Body(body.value()), &mut reads);
                        "arclog"
                    }
                };
                ("proposer", implementation, Value::Null)
            }
            LibEntry::Component(c) => (
                "component",
                "native_component",
                json!({"component_kind":format!("{:?}",c.kind),
                "inputs":c.inputs.iter().map(|i|json!({"name":i.port.name.0,"reads_outputs":i.reads_outputs,"from_key":i.from_key,
                    "columns":i.port.columns.iter().map(|c|json!({"name":column(&c.name),"type_expression":format!("{:?}",c.ty)})).collect::<Vec<_>>()})).collect::<Vec<_>>(),
                "outputs":c.outputs.iter().map(|o|json!({"name":o.name.0,"columns":o.columns.iter().map(|c|json!({"name":column(&c.name),"type_expression":format!("{:?}",c.ty)})).collect::<Vec<_>>()})).collect::<Vec<_>>()}),
            ),
        };
        let declaration = forms
            .get(lib.0.as_ref())
            .ok_or_else(|| format!("no embedded definition for {}", lib.0))?;
        entries.push(json!({"id":format!("lib:{}",lib.0),"name":lib.0,"kind":kind,"implementation":implementation,
            "semantics":super::render_meanings::contract(&format!("lib:{}",lib.0),registry),
            "declaration":declaration,"arclog_implementation":implementations.get(lib.0.as_ref()),"reads":reads,"ports":ports}));
    }
    for fact in [
        FactRelation::Input,
        FactRelation::ExInput,
        FactRelation::ExOutput,
    ] {
        let key = match fact {
            FactRelation::Input => "input",
            FactRelation::ExInput => "ex_input",
            FactRelation::ExOutput => "ex_output",
            FactRelation::Output | FactRelation::Program(_) | FactRelation::Name(_) => unreachable!("the loop names the facts of a program"),
        };
        let definition = forms
            .get(key)
            .ok_or_else(|| format!("missing fact definition {key}"))?;
        entries.push(
            json!({"id":format!("fact:{key}"),"name":key,"kind":"fact","declaration":definition,
            "semantics":super::render_meanings::contract(&format!("fact:{key}"),registry),
            "reads":[],"implementation":"task_grid_evidence"}),
        );
    }
    Ok(
        json!({"completeness":"entire_embedded_registry_and_arclog_proposers","entries":entries,
        "semantic_catalogue":{"schema":super::render_meanings::catalogue()["schema"],"general_contract":super::render_meanings::catalogue()["general_contract"],"proposer_context":super::render_meanings::catalogue()["proposer_context"]}}),
    )
}

fn registry_export(registry: &Registry) -> Result<Value, String> {
    static SHARED: std::sync::OnceLock<Result<std::sync::Arc<Value>, String>> =
        std::sync::OnceLock::new();
    if std::ptr::eq(registry, Registry::get()) {
        SHARED
            .get_or_init(|| registry_export_uncached(registry).map(std::sync::Arc::new))
            .as_ref()
            .map(|value| (**value).clone())
            .map_err(Clone::clone)
    } else {
        registry_export_uncached(registry)
    }
}

pub fn export(program: &StudyProgram, registry: &Registry) -> Result<Value, String> {
    let resolved = &program.checked().program;
    let graph=resolved.graph.nodes.iter().enumerate().map(|(i,n)| {
        let kind=match &n.kind {
            DependencyKind::Fact(f)=>json!({"kind":"fact","relation":relation_json(&RelationRef::Fact(*f))}),
            DependencyKind::Clause(r)=>json!({"kind":"clause","relation":program_relation(r)}),
            DependencyKind::Parameter(r)=>json!({"kind":"parameter","relation":program_relation(r)}),
            DependencyKind::InstanceInput{instance,input}=>json!({"kind":"instance_input","instance":name(&instance.0),"port":input.0}),
            DependencyKind::InstanceOutput{instance,output}=>json!({"kind":"instance_output","instance":name(&instance.0),"port":output.0}),
            DependencyKind::Chosen(n)=>json!({"kind":"chosen","name":name(&n.0)}),
            DependencyKind::RigidAssembly(n)=>json!({"kind":"rigid_assembly","name":name(&n.0)}),
            DependencyKind::Demonstrated(n)=>json!({"kind":"demonstrated","name":name(&n.0)}),
            DependencyKind::RecursiveInstance(n)=>json!({"kind":"recursive_instance","name":name(&n.0)}),
            DependencyKind::Out(p)=>json!({"kind":"out","path":path_json(p)}),
        };
        json!({"node":i,"definition":kind,"name_scope":format!("{:?}",n.scope),"side":format!("{:?}",resolved.side(GraphNodeIndex(i as u32))),
            "forms":resolved.forms_of(GraphNodeIndex(i as u32)).iter().map(path_json).collect::<Vec<_>>(),
            "reads":resolved.graph.reads[i].iter().map(|n|n.0).collect::<Vec<_>>()})
    }).collect::<Vec<_>>();
    fn walk(
        node: NodeRef<'_>,
        at: &NodePath,
        program: &StudyProgram,
        out: &mut Vec<Value>,
    ) -> Result<(), String> {
        if let Some(atom) = node.atom() {
            let resolution = match program.checked().program.resolution(at) {
                Some(Resolution::Node(n)) => json!({"kind":"graph_node","node":n.0}),
                Some(Resolution::Lib(n)) => json!({"kind":"library","id":format!("lib:{}",n.0)}),
                Some(Resolution::Undefined(r)) => {
                    json!({"kind":"undefined_case_relation","relation":program_relation(r)})
                }
                _ => return Err(format!("atom has no resolved read at {at:?}")),
            };
            out.push(json!({"reader_path":path_json(at),"reader_owner_path":at.0.first().map(|s|vec![s.0]),
                "relation":relation_json(&atom.relation),"resolution":resolution}));
        }
        if let NodeRef::Instance(i) = node {
            out.push(json!({"reader_path":path_json(at),"relation":{"component":i.component.0},"resolution":{"kind":"library","id":format!("lib:{}",i.component.0)}}));
        }
        if let NodeRef::Clause(c) = node {
            for p in c.proposers.iter() {
                out.push(json!({"reader_path":path_json(at),"relation":{"proposer":p.0},"resolution":{"kind":"library","id":format!("lib:{}",p.0)}}));
            }
        }
        for (i, child) in node.children().into_iter().enumerate() {
            walk(child, &at.child(i as u32), program, out)?;
        }
        Ok(())
    }
    let mut readers = Vec::new();
    walk(
        NodeRef::Program(program.program().value()),
        &NodePath::default(),
        program,
        &mut readers,
    )?;
    let settings = crate::stream::DecodeSettings::synthesis();
    let vocabulary = crate::stream::Vocabulary::new(registry, &settings);
    let written = crate::stream::written_stream(program.checked(), &vocabulary)
        .map_err(|d| super::diagnostics_text(&[d]))?;
    let native_relations=written.relations.iter().enumerate().map(|(slot,r)| {
        let owner=written.forms.iter().find(|f|f.relations.contains(&slot));
        let form=owner.map(|f|&f.path);
        let reference=match r {ProgramRelation::Declared(n)=>RelationRef::Declared(n.clone()),ProgramRelation::Output(n)=>RelationRef::Output(n.clone())};
        let display_name=crate::write::relation_ref(&reference,|n|match n {DeclaredName::Written(n)=>n.to_string(),DeclaredName::Slot(n)=>format!("&r{n}")});
        let (witness_status,witnesses,graph)=form.map(|form|column_witnesses(program.checked(),registry,r,form))
            .unwrap_or_else(||("unsupported_definition".into(),Vec::new(),Value::Null));
        json!({"relation_slot":slot,"relation":program_relation(r),"source_name":crate::eval::determinations::relation_spelled(r),
            "display_name":display_name,
            "graph":graph,"column_witness_status":witness_status,"column_witnesses":witnesses,
            "readable_in_checked_program":owner.is_some_and(|f|f.readable.contains(&slot)),
            "definition_path":form.map(path_json),"native_selector":{"point":0,"relation":slot,
                "form":form.map(|p|p.0.iter().map(|s|s.0.to_string()).collect::<Vec<_>>().join("."))},
            "note":"selector identifies a present relation table; some aliased/omitted INIT ports have no table"})
    }).collect::<Vec<_>>();
    let library = registry_export(registry)?;
    let pending = library["entries"]
        .as_array()
        .unwrap()
        .iter()
        .filter(|e| e["semantics"]["status"] != "authored_contract")
        .map(|e| e["id"].clone())
        .collect::<Vec<_>>();
    Ok(
        json!({"graph_nodes":graph,"readers":readers,"native_relations":native_relations,
        "semantic_coverage":{"complete":pending.is_empty(),"pending":pending,"scope":"entire embedded registry"},
        "registry":library}),
    )
}
