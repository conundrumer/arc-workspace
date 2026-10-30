//! Point-local common input universes. No OUT/FITS or caller assignments.
use super::*;
use arclog::eval::join::{Budget, Materializer};
use arclog::study::features;

pub enum OpenError {
    Unavailable(String),
    Stopped(arclog::eval::ReachedBound),
}
impl From<String> for OpenError {fn from(s:String)->Self {Self::Unavailable(s)}}
impl From<&str> for OpenError {fn from(s:&str)->Self {Self::Unavailable(s.into())}}
impl OpenError {
    pub fn report(&self)->Value {
        let (status,reason)=match self {Self::Unavailable(s)=>("unavailable",s.clone()),
            Self::Stopped(bound)=>("stopped",format!("{bound:?}"))};
        json!({"schema":"arclog-study-prefix-universe-v1","status":status,"reason":reason,
            "coverage":{"enumeration_complete":false,"assignment_values_complete":false,"parent_count":0,"zero":false}})
    }
}

pub struct Universe {
    pub source: StudyProgram,
    pub point: NodePath,
    pub frontier: Arc<CheckedProgram>,
    receipt: Arc<HeldAssignments>,
    pub report: Value,
    available: Option<component_tables::RelationTables>,
    _allocation: Arc<arclog::session::SessionAllocation>,
}

pub struct Acquisition {
    pub report: Value,
    pub tables: Vec<(usize,Table)>,
    pub limits: arclog::eval::Limits,
}

fn checked_identity(checked:&CheckedProgram,decoder:&Decoder<'_>)->Value {
    let stream=arclog::stream::written_stream(checked,decoder.vocabulary());
    match stream {
        Ok(stream)=>json!({"status":"complete","program_sexp":arclog::write::write_synthesized(&checked.program.program,decoder.registry()),
            "ids":stream.tokens.iter().map(|(token,_)|decoder.vocabulary().id(token)).collect::<Vec<_>>(),
            "model":stream.tokens.iter().map(|(_,emitter)|u8::from(*emitter==arclog::stream::Emitter::Model)).collect::<Vec<_>>(),
            "paths":stream.paths.iter().map(arclog::mutation::path_json).collect::<Vec<_>>()}),
        Err(reason)=>json!({"status":"unsupported","reason":reason.message}),
    }
}

/// The query body is absent from this fresh checker. Every DET declared in
/// the retained frontier participates, even without a downstream reader.
pub fn open(source:&StudyProgram,point:&NodePath,task:&Task,session:&TaskSession,
    constructions:&Constructions,settings:&DecodeSettings,max_assignments:u64)->Result<Universe,OpenError> {
    if max_assignments==0 {return Err("max_assignments must be positive".into());}
    let start=Instant::now();
    let frontier=Arc::new(features::checked_frontier(source,point,Registry::get())?);
    let frontier_seconds=start.elapsed().as_secs_f64();
    let mut bounded=*settings;
    bounded.caps.assignments=bounded.caps.assignments.min(max_assignments);
    let limits=bounded.operation_limits();
    let decoder=Decoder::new(task,session,Registry::get(),constructions,&bounded).with_operation_limits(limits.clone());
    let dets=arclog::decode::held_dets(&frontier);
    // Pre-admit the canonical walk vector, the retained receipt copy and
    // per-query projections before their bounded capacity can be allocated.
    let bytes=(bounded.caps.assignments as usize).saturating_mul(4usize.saturating_mul(
        std::mem::size_of::<Vec<Assignment>>().saturating_add(dets.len().saturating_mul(std::mem::size_of::<Assignment>()))))
        .saturating_add(std::mem::size_of::<Universe>()+512);
    let allocation=Materializer::new(session,&limits).copy(bytes).map_err(OpenError::Stopped)?;
    let work=decoder.table_work();
    let root=dets.last().map_or(arclog::resolver::GraphNodeIndex(0),|d|d.node);
    let walk_start=Instant::now();
    let walked=decoder.assigned(&frontier,root,&dets,Some(&work),&mut |_|Ok(()));
    let walk_seconds=walk_start.elapsed().as_secs_f64();
    let (parents,terminal)=match walked {
        Ok(rows)=>(rows.at.into_iter().map(|(a,_)|a).collect::<Vec<_>>(),rows.stop.map(|s|stopped(&s))),
        Err(f)=>(Vec::new(),Some(faulted(&f))),
    };
    let missing=parents.iter().map(|a|dets.iter().filter(|d|!a.iter().any(|(name,_)|name==&d.relation))
        .map(|d|relation_spelled(&d.relation)).collect::<Vec<_>>()).collect::<Vec<_>>();
    let complete=terminal.is_none();
    let parameter_schema=dets.iter().map(|d| {
        let relation=GraphRelation {node:d.node,output:None};
        json!({"node":d.node.0,"relation":arclog::study::render::program_relation(&d.relation),
            "source_name":relation_spelled(&d.relation),"open":d.open,
            "definition_paths":frontier.program.forms_of(d.node).iter().map(arclog::mutation::path_json).collect::<Vec<_>>(),
            "types":frontier.types.columns(&relation).map(|types|types.iter().map(arclog::study::render_correspondence::type_json).collect::<Vec<_>>())})
    }).collect::<Vec<_>>();
    let report=json!({"schema":"arclog-study-prefix-universe-v1","status":terminal.as_ref().map(|t|t["status"].clone()).unwrap_or(json!("complete")),
        "reason":terminal.as_ref().map(|t|t["reason"].clone()),"universe_ref":table_transport_ref(),
        "source_program_sexp":source.sexp(Registry::get()),"body_path":arclog::mutation::path_json(point),
        "frontier":checked_identity(&frontier,&decoder),"settings":format!("{settings:?}"),
        "parameters":parameter_schema,"parent_assignments":parents.iter().enumerate().map(|(i,a)|json!({"parent":i,"values":assignment_json(a),"missing_parameters":missing[i]})).collect::<Vec<_>>(),
        "timings":{"frontier_check_seconds":frontier_seconds,"domain_walk_seconds":walk_seconds},
        "receipt_reserved_bytes":allocation.bytes(),
        "coverage":{"enumeration_complete":complete,"assignment_values_complete":missing.iter().all(Vec::is_empty),
            "parent_count":parents.len(),"zero":complete && parents.is_empty(),"terminal":terminal},
        "fanout":{"max_assignments":bounded.caps.assignments,"max_models_per_parent_example":session.caps.models,
            "max_parent_models_per_table_example":bounded.caps.assignments.saturating_mul(session.caps.models)},
        "admission":"all prior assignable DETs at independently checked frontier; no candidate domain, OUT/FITS, later forms or gold kept selection",
        "model_contract":"parents task-wide; models local to table/example; no ordinal or Ident cross-family alignment",
        "raw_reuse":{"status":"unproven","reason":"no stored snapshot authenticated; dependency membership or observed counts alone do not prove coverage","requires_fresh_row_evaluation":null}});
    let receipt=HeldAssignments::new(Arc::clone(&frontier),Arc::clone(&frontier),&parents).map_err(|f|f.message.to_string())?;
    Ok(Universe {source:source.clone(),point:point.clone(),frontier,receipt,report,available:None,_allocation:allocation})
}

fn coverage(tables:&[(usize,Table)],parent_count:usize,train_count:usize)->Value {
    json!(tables.iter().enumerate().map(|(i,(_,t))| {
        let mut complete=true;
        let examples=t.contents.as_ref().ok().map(|c|c.examples.iter().map(|e| {
            let (kind,index)=component_tables::example_axis(e.example,train_count);
            let (status,models,families)=match &e.rows {
                Ok(a)=>{
                    let stop=a.stop.as_ref().or_else(||a.at.iter().flat_map(|(_,m)|m).find_map(|v|
                        if let RelationValue::Stopped(s)=v {Some(s)} else {None}));
                    let families=a.at.iter().enumerate().map(|(parent,(_,values))| {
                        let stopped=values.iter().any(|v|matches!(v,RelationValue::Stopped(_)));
                        json!({"parent_assignment":parent,"complete":!stopped,
                            "model_count":if stopped {None}else{Some(values.len())},
                            "observed_entries":values.len(),
                            "undefined_models":values.iter().filter(|v|matches!(v,RelationValue::Undefined)).count(),
                            "empty_rows_models":values.iter().filter(|v|matches!(v,RelationValue::Rows(rows) if rows.is_empty())).count()})
                    }).collect::<Vec<_>>();
                    (stop.map(stopped).unwrap_or_else(super::complete),Some(a.at.iter().map(|(_,v)|v.len()).collect::<Vec<_>>()),Some(families))
                },
                Err(f)=>(faulted(f),None,None),
            };
            complete &= status["status"]=="complete" && models.as_ref().is_some_and(|m|m.len()==parent_count);
            json!({"example_kind":kind,"example_index":index,"status":status,"observed_entry_counts":models,"families":families})
        }).collect::<Vec<_>>());
        if t.contents.is_err() {complete=false;}
        json!({"table":i+2,"complete":complete,"examples":examples})
    }).collect::<Vec<_>>())
}

/// Shared native held materializer; the one universe receipt also owns all
/// annotation lookups. A candidate's empty result never deletes a parent.
pub fn acquire(universe:&mut Universe,candidate:Option<&ValidMutant>,task:&Task,session:&TaskSession,
    constructions:&Constructions,settings:&DecodeSettings,include_available:bool)->Result<Acquisition,String> {
    let limits=settings.operation_limits();
    let decoder=Decoder::new(task,session,Registry::get(),constructions,settings).with_operation_limits(limits.clone());
    let mut report=json!({"schema":"arclog-study-prefix-tables-v1","status":"complete","universe_ref":universe.report["universe_ref"],
        "universe_coverage":universe.report["coverage"],"body_path":arclog::mutation::path_json(&universe.point),
        "side":if candidate.is_some(){"mutant"}else{"gold"},"settings":format!("{settings:?}"),
        "assignment_contract":"entry parent ordinal belongs only to universe_ref; local models never identify a shared world",
        "raw_reuse":universe.report["raw_reuse"],"body_table":null});
    if universe.report["status"]!="complete" || universe.report["coverage"]["assignment_values_complete"]!=true {
        report["status"]="unavailable".into();report["reason"]="prefix universe incomplete or contains Undefined/missing parameter values".into();
        return Ok(Acquisition {report,tables:Vec::new(),limits});
    }
    let available_start=Instant::now();
    let cached=universe.available.is_some();
    if !cached {
        let work=decoder.table_work();let mut budget=Budget::new(&limits,session);
        let tables=component_tables::relation_tables_with_receipt(&universe.frontier,&decoder,&universe.receipt,&limits,&work,&mut budget);
        universe.available=Some(tables);
    }
    let available_seconds=available_start.elapsed().as_secs_f64();
    let available=universe.available.as_ref().unwrap();
    if !include_available && !available.tables.is_empty() {
        report["status"]="unavailable".into();
        report["reason"]="available dependency transport cannot yet be omitted; request include_available=True".into();
        return Ok(Acquisition {report,tables:Vec::new(),limits});
    }
    report["available_status"]=available.status();report["available_cached"]=json!(cached);
    let source=candidate.map(|m|m.program()).unwrap_or(&universe.source);
    if candidate.is_some_and(|m|!Arc::ptr_eq(m.gold(),universe.source.checked())) {
        return Err("candidate belongs to another original gold handle".into());
    }
    let checked=Arc::new(features::checked_prefix(source,&universe.point,Registry::get())?);
    let frontier=features::frontier(source,&universe.point)?;
    if frontier!=universe.frontier.program.program ||
        arclog::write::write_synthesized(&frontier,Registry::get())!=arclog::write::write_synthesized(&universe.frontier.program.program,Registry::get()) {
        return Err("candidate changes the common native frontier".into());
    }
    let view=arclog::eval::body_view::BodyView::at(&checked,&universe.point).map_err(|f|f.message.to_string())?;
    let dets=super::super::body_tables::dets(&checked,&view);
    let prior=arclog::decode::held_dets(&universe.frontier);
    if dets.iter().any(|d|!prior.iter().any(|p|p.relation==d.relation)) {
        return Err("BODY requires a parameter not declared at common frontier".into());
    }
    let work=decoder.table_work();
    let context=AssignmentContext::Held {receipt:&universe.receipt,limits:&limits,work:&work};
    let body_start=Instant::now();
    let examples=super::super::body_tables::examples_with_context(&decoder,&checked,&view,&dets,&work,context);
    let body_seconds=body_start.elapsed().as_secs_f64();
    let annotation_start=Instant::now();
    let seen=available.tables.iter().map(|(_,t)|t).collect::<Vec<_>>();
    let slot=arclog::stream::written_stream(&checked,decoder.vocabulary()).map_err(|d|d.message.to_string())?.relations.len() as u32;
    let body=super::super::body_tables::contents_with_context(&decoder,&checked,&view,slot,&dets,examples,&seen,context);
    report["timings"]=json!({"available_materialization_seconds":available_seconds,
        "body_models_seconds":body_seconds,"body_metadata_extents_seconds":annotation_start.elapsed().as_secs_f64()});
    let mut tables=if include_available {available.tables.clone()} else {Vec::new()};
    report["body_table"]=json!(tables.len()+2);
    report["body_scope"]=json!(format!("{:?}",view.scope));
    report["query_prefix"]=checked_identity(&checked,&decoder);
    let source_view=arclog::eval::body_view::BodyView::at(source.checked(),&universe.point).ok();
    report["source_program_sexp"]=source.sexp(Registry::get()).into();
    report["body_columns"]=json!(view.clause.columns.iter().enumerate().map(|(i,v)| {
        let label=view.paths.labels[v.0 as usize];
        let original=source_view.as_ref().and_then(|b|b.column_of(label));
        let original_type=source_view.as_ref().zip(original).map(|(b,c)|
            arclog::study::render_correspondence::type_json(&b.clause.variables[b.clause.columns[c].0 as usize].ty));
        json!({"physical_column":i,"scope_path":arclog::mutation::path_json(&view.form),"label_id":label.0,
            "physical_type":arclog::study::render_correspondence::type_json(&view.clause.variables[v.0 as usize].ty),
            "source_body_path":arclog::mutation::path_json(&universe.point),"source_body_column":original,
            "source_physical_type":original_type,"source_status":if original.is_some(){"native_retained_scoped_label"}else{"unsupported"}})
    }).collect::<Vec<_>>());
    tables.push((0,Table {form:view.form,point:Point::Body {conjuncts:view.clause.nodes.len() as u32,sites:0},contents:body}));
    let prior_written=arclog::stream::written_stream(&universe.frontier,decoder.vocabulary()).map_err(|d|d.message.to_string())?;
    report["available_schemas"]=json!(available.tables.iter().enumerate().map(|(i,(_,table))| {
        let witnesses=table.contents.as_ref().ok().and_then(|c|match c.relation {
            TableRelation::Slot(slot)=>prior_written.relations.get(slot as usize),_=>None,
        }).map(|relation|arclog::study::render_definitions::column_witnesses(&universe.frontier,Registry::get(),relation,&table.form));
        match witnesses {
            Some((status,columns,graph))=>json!({"table":i+2,"form_path":arclog::mutation::path_json(&table.form),
                "status":status,"columns":columns,"graph":graph}),
            None=>json!({"table":i+2,"status":"unsupported","reason":"native declared relation witness unavailable"}),
        }
    }).collect::<Vec<_>>());
    report["entry_parent_map"]=component_tables::assignment_map(&tables,2,task.train.len());
    if let Some(list)=report["entry_parent_map"].as_array_mut() {for table in list {if let Some(entries)=table["entries"].as_array_mut() {for entry in entries {
        if let Some(fields)=entry.as_object_mut() {
            let parent=fields.remove("kept_assignment").unwrap_or(Value::Null);
            fields.insert("parent_assignment".into(),parent);
        }
    }}}}
    report["table_coverage"]=coverage(&tables,universe.receipt.parent_count(),task.train.len());
    let status=table_status(&tables);
    if available.status()["status"]!="complete" {report["status"]=available.status()["status"].clone();report["reason"]=available.status()["reason"].clone();}
    if status["status"]!="complete" {report["status"]=status["status"].clone();report["reason"]=status["reason"].clone();}
    Ok(Acquisition {report,tables,limits})
}
