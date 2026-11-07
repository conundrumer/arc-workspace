//! Native relation tables at fixed interventions, independent of OUT evidence.
use super::*;
use arclog::eval::join::{Budget,Materializer};

pub struct ComponentTables {
    pub limits:arclog::eval::Limits,
    pub report:Value,
    pub gold:Vec<(usize,Table)>,
    pub mutant:Vec<(usize,Table)>,
    _allocations:Vec<Arc<arclog::session::SessionAllocation>>,
}

/// A bounded collection retains every table already materialized. A stop
/// between relations is not a fault and cannot erase the prefix or its maps.
pub struct RelationTables {
    pub tables:Vec<(usize,Table)>,
    pub terminal:Option<End>,
}
impl RelationTables {
    pub fn status(&self)->Value {
        let status=table_status(&self.tables);
        if status["status"]!="complete" {return status;}
        match &self.terminal {None=>status,Some(End::Stop(s))=>stopped(s),Some(End::Fault(f))=>faulted(f)}
    }
    pub fn collection(&self)->Value {
        let terminal=match &self.terminal {None=>None,Some(End::Stop(s))=>Some(stopped(s)),Some(End::Fault(f))=>Some(faulted(f))};
        json!({"materialization_complete":self.terminal.is_none(),"returned_relation_tables":self.tables.len(),"terminal":terminal})
    }
}

/// Tables of the exact cached observation; no OUT evaluation or DET search.
pub fn evaluate_cached(gold:&StudyProgram,mutant:&ValidMutant,task:&Task,session:&TaskSession,
    constructions:&Constructions,settings:&DecodeSettings,cache:&PairCache,expected_kept:Option<&Value>)->Result<ComponentTables,String> {
    if !Arc::ptr_eq(gold.checked(),mutant.gold()) {return Err("mutant belongs to another gold handle".into());}
    gold.checked().check_held_det_interfaces(mutant.program().checked()).map_err(|e| e.to_string())?;
    let key=Arc::as_ptr(gold.checked()) as usize;
    let memo=cache.gold.get(&key).ok_or("call gold_kept or evaluate_pair on this evaluator/gold handle first; no FITS search is performed")?;
    let walked=memo.walked.as_ref().map_err(|f|f.message.to_string())?;
    let (fixed,records)=memo.kept_values();
    if expected_kept.is_some_and(|expected|expected!=&json!(records)) {
        return Err("stored kept assignments differ from cached gold observation (possibly Ident namespace); refusing alternate assignments".into());
    }
    let operation=settings.operation_limits();
    let decoder=Decoder::new(task,session,Registry::get(),constructions,settings).with_operation_limits(operation);
    let work=decoder.query_work();let limits=decoder.limits().counted_in(work.clone());
    let mut budget=Budget::new(&limits,session);
    let g=relation_tables(gold,gold.checked(),&decoder,&fixed,&limits,&work,&mut budget);
    let m=relation_tables(mutant.program(),gold.checked(),&decoder,&fixed,&limits,&work,&mut budget);
    let (choice_extents,choice_allocations)=full_choice_extents(&Materializer::new(session,&limits),&g.tables,&fixed,task.train.len());
    let report=json!({"schema":"arclog-study-component-tables-v1","gold_observation_ref":memo.sequence,
        "full_choice_extents":choice_extents,
        "kept_assignments":records,"gold_observation_stop":walked.stop.as_ref().map(stopped),
        "gold_status":g.status(),"mutant_status":m.status(),
        "gold_collection":g.collection(),"mutant_collection":m.collection(),
        "gold_assignment_map":assignment_map(&g.tables,2,task.train.len()),
        "mutant_assignment_map":assignment_map(&m.tables,2,task.train.len()),
        "scope":"native materialized relations including computed INIT outputs under exact cached gold DET interventions; no new FITS or OUT search",
        "assignment_contract":"table_entry is the zero-based position among native entries for its table; kept_assignment indexes the full kept_assignments list even when DET subsets repeat",
        "bound_scope":"one operation request work cap; per-evaluation binding and row caps"});
    Ok(ComponentTables {limits:limits.clone(),report,gold:g.tables,mutant:m.tables,_allocations:choice_allocations})
}

/// Native example coordinates shared by table maps and held evidence reports.
pub(crate) fn example_axis(example:Option<Example>,train_count:usize)->(&'static str,usize) {
    let (kind,index)=super::super::example_axis(example,train_count);
    (match kind {0=>"task",1=>"train",_=>"test"},index)
}

/// Mapping uses the exact native entries order, including repeated equal
/// assignments when a table reads only a subset. Never join choices by values.
pub fn assignment_map(tables:&[(usize,Table)],table_offset:usize,train_count:usize)->Value {
    assignment_map_with_axis(tables,table_offset,train_count,false)
}

/// Prefix packets use exactly the packed wire axis; legacy map strings stay
/// unchanged. Entry traversal and placeholder semantics have one owner.
pub(crate) fn assignment_map_numeric(tables:&[(usize,Table)],table_offset:usize,train_count:usize)->Value {
    assignment_map_with_axis(tables,table_offset,train_count,true)
}

fn assignment_map_with_axis(tables:&[(usize,Table)],table_offset:usize,train_count:usize,numeric:bool)->Value {
    json!(tables.iter().enumerate().map(|(number,(_,table))| {
        let mut entries=Vec::new();
        if let Ok(contents)=&table.contents {for example in &contents.examples {
            let (wire,index)=super::super::example_axis(example.example,train_count);
            let kind=if numeric {json!(wire)}else{json!(example_axis(example.example,train_count).0)};
            match &example.rows {
                Ok(rows) if !rows.at.is_empty()=>for (assignment,(_,models)) in rows.at.iter().enumerate() {
                    for model in 0..models.len() {entries.push(json!({"table_entry":entries.len(),
                        "kept_assignment":assignment,"example_kind":kind,"example_index":index,"model":model}));}
                },
                _=>entries.push(json!({"table_entry":entries.len(),"kept_assignment":null,
                    "example_kind":kind,"example_index":index,"model":0,"meaning":"native fault/no-entries placeholder"})),
            }
        }}
        json!({"table":table_offset+number,"form_path":arclog::mutation::path_json(&table.form),
            "source_name":table.contents.as_ref().ok().map(|c|&c.name),"entries":entries})
    }).collect::<Vec<_>>())
}

/// Collect full native rows for component and continuation evidence. The
/// synthesis projection policy is applied by `contents`; evidence uses the
/// same schema adapter directly and retains bounded packing and annotations.
pub fn relation_tables(program:&StudyProgram,origin:&Arc<CheckedProgram>,decoder:&Decoder<'_>,fixed:&[Vec<Assignment>],limits:&arclog::eval::Limits,
    work:&TableWork,budget:&mut Budget<'_>)->RelationTables {
    relation_tables_checked(program.checked(), origin, decoder, fixed, limits, work, budget)
}

/// Shared original-IR collector for checked prefix and whole-program owners.
pub fn relation_tables_checked(checked:&Arc<CheckedProgram>,origin:&Arc<CheckedProgram>,decoder:&Decoder<'_>,fixed:&[Vec<Assignment>],limits:&arclog::eval::Limits,
    work:&TableWork,budget:&mut Budget<'_>)->RelationTables {
    let receipt=match HeldAssignments::new(Arc::clone(checked),Arc::clone(origin),fixed) {
        Ok(receipt)=>receipt,
        Err(error)=>return RelationTables {tables:Vec::new(),terminal:Some(End::Fault(error))},
    };
    relation_tables_with_receipt(checked,decoder,&receipt,limits,work,budget)
}

/// A common prefix owns one receipt for relation tables and BODY extents.
pub(crate) fn relation_tables_with_receipt(checked:&Arc<CheckedProgram>,decoder:&Decoder<'_>,receipt:&Arc<HeldAssignments>,
    limits:&arclog::eval::Limits,work:&TableWork,budget:&mut Budget<'_>)->RelationTables {
    relation_tables_with_receipt_where(checked,decoder,receipt,limits,work,budget,&mut |_,_|true)
}

/// Prefix collection uses the same materializer with a native source-boundary
/// inventory predicate. Whole-program collectors admit the entire inventory.
pub(crate) fn relation_tables_with_receipt_where(checked:&Arc<CheckedProgram>,decoder:&Decoder<'_>,receipt:&Arc<HeldAssignments>,
    limits:&arclog::eval::Limits,work:&TableWork,budget:&mut Budget<'_>,
    include:&mut dyn FnMut(&NodePath,&ProgramRelation)->bool)->RelationTables {
    let mut tables=Vec::new();
    let collected=(|| ->Result<(),End> {
    let written=arclog::stream::written_stream(checked,decoder.vocabulary()).map_err(|d|End::Fault(fault(d.message,&NodePath::default())))?;
    for form in &written.forms {for slot in materialized_slots(checked.program.program.value(),&written,form) {
        if !include(&form.path,&written.relations[slot]) {continue;}
        budget.charge_work(0).map_err(|bound|End::Stop(arclog::eval::Stop {bound,form:form.path.clone()}))?;
        let declared=&written.relations[slot];
        let relation=graph_relation(checked,decoder.registry(),&form.path,declared).ok_or_else(||End::Fault(fault("no native graph for continuation relation",&form.path)))?;
        let dets=relation_dets(checked,relation.node);
        let context=AssignmentContext::Held {receipt,limits,work};
        let examples=relation_examples_with_context(decoder,checked,&relation,&dets,work,context);
        let c=relation_metadata(decoder.registry(),checked,&form.path,&relation,slot as u32,&dets,examples).map(|c| {
            let c=Contents {name:relation_spelled(declared),output_name:output_name(checked.program.program.value(),&form.path,declared),keys:checked.program.column_keys(relation.node),..c};
            made_with_context(decoder,&tables.iter().map(|(_,t)|t).collect::<Vec<_>>(),checked,&relation,c,context)
        });
        tables.push((form.tokens.end.saturating_sub(1),Table {form:form.path.clone(),point:Point::Relation,contents:c}));
    }}
    Ok(())
    })();
    RelationTables {tables,terminal:collected.err()}
}


/// Authoritative annotations of exact held gold parameter rows. Example/model
/// axes are retained; a task-wide value is not assigned an arbitrary example.
pub fn full_choice_extents(materializer:&Materializer<'_>,tables:&[(usize,Table)],fixed:&[Vec<Assignment>],train_count:usize)->(Value,Vec<Arc<arclog::session::SessionAllocation>>) {
    let mut allocations=Vec::new();
    let value=json!({"schema":"arclog-study-choice-extents-v1","choices":fixed.iter().enumerate().map(|(choice,assigned)| {
        let dets=assigned.iter().map(|(name,held)| {
            let source=relation_spelled(name);
            let contents=tables.iter().rev().find_map(|(_,table)|table.contents.as_ref().ok().filter(|c|c.name==source).map(|c|(&table.form,c)));
            let Some((form,contents))=contents else {return json!({"source_name":source,"status":"unresolved","reason":"exact held relation table not materialized"});};
            let mut examples=Vec::new();
            for (place,e) in contents.examples.iter().enumerate() {
                let Some((_,models))=e.rows.as_ref().ok().and_then(|r|r.at.get(choice)) else {continue;};
                let (kind,index)=example_axis(e.example,train_count);
                for (model,value) in models.iter().enumerate() {
                    let RelationValue::Rows(rows)=value else {continue;};
                    if !arclog::session::same_rows(rows,held) {continue;}
                    let annotations=match crate::extents::annotated_rows(materializer,form,contents,place,choice,model,rows) {
                        Ok(rows)=>rows,
                        Err(stop)=>{
                            examples.push(json!({"example_kind":kind,"example_index":index,"model":model,"status":"stopped","reason":format!("{:?}",stop.bound),"form":format!("{:?}",stop.form)}));
                            continue;
                        }
                    };
                    let columns=contents.columns.iter().enumerate().filter(|(_,c)|c.ty.is_box()).map(|(i,_)|i).collect::<Vec<_>>();
                    let payload=usize::from(rows.arity()).saturating_mul(32).saturating_add(columns.len().saturating_mul(1024));
                    match materializer.admit(rows,Materializer::row_bytes(payload,8)) {
                        Ok(owner)=>allocations.push(owner),
                        Err(bound)=>{examples.push(json!({"example_kind":kind,"example_index":index,"model":model,"status":"stopped","reason":format!("{bound:?}")}));continue;}
                    }
                    let mut at=0;let mut out=Vec::new();
                    let walked=materializer.walk(rows,&mut |row| {
                        let cells=columns.iter().zip(&annotations[at]).map(|(column,(status,extent))|json!({
                            "column":column,"extent_status":match status {0=>"no_grid",1=>"resolved",_=>"unresolved"},
                            "extent":extent.map(|e|[e.rows,e.columns])})).collect::<Vec<_>>();
                        out.push(json!({"packed_row":row.iter().map(|t|t.encoding()).collect::<Vec<_>>(),"cells":cells}));at+=1;
                    });
                    match walked {
                        Ok(())=>examples.push(json!({"example_kind":kind,"example_index":index,"model":model,"rows":out})),
                        Err(bound)=>examples.push(json!({"example_kind":kind,"example_index":index,"model":model,"status":"stopped","reason":format!("{bound:?}")})),
                    }
                }
            }
            json!({"source_name":source,"status":if examples.iter().any(|e|e["status"]=="stopped"){"stopped"}else if examples.is_empty(){"unresolved"}else{"complete"},"examples":examples})
        }).collect::<Vec<_>>();
        json!({"assignment":choice,"dets":dets})
    }).collect::<Vec<_>>(),"identity_contract":"exact cached held gold values only; rows carry packed identity and example/model axes; no cross-example extent merge"});
    (value,allocations)
}
