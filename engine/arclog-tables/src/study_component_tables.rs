//! Native relation tables at fixed interventions, independent of OUT evidence.
use super::*;
use arclog::eval::join::Budget;

pub struct ComponentTables {
    pub report:Value,
    pub gold:Vec<(usize,Table)>,
    pub mutant:Vec<(usize,Table)>,
}

/// Tables of the exact cached observation; no OUT evaluation or DET search.
pub fn evaluate_cached(gold:&StudyProgram,mutant:&ValidMutant,task:&Task,session:&TaskSession,
    constructions:&Constructions,settings:&DecodeSettings,cache:&PairCache,expected_kept:Option<&Value>)->Result<ComponentTables,String> {
    if !Arc::ptr_eq(gold.checked(),mutant.gold()) {return Err("mutant belongs to another gold handle".into());}
    let key=Arc::as_ptr(gold.checked()) as usize;
    let memo=cache.gold.get(&key).ok_or("call evaluate_pair on this evaluator/gold handle first; no FITS search is performed")?;
    let walked=memo.walked.as_ref().map_err(|f|f.message.to_string())?;
    let mut fixed=Vec::new();let mut records=Vec::new();
    for (i,(assigned,train)) in walked.at.iter().enumerate() {if fits(train) {fixed.push(assigned.clone());records.push(memo.records[i].clone());}}
    if expected_kept.is_some_and(|expected|expected!=&json!(records)) {
        return Err("stored kept assignments differ from cached gold observation (possibly Ident namespace); refusing alternate assignments".into());
    }
    let decoder=Decoder::new(task,session,Registry::get(),constructions,settings);
    let work=decoder.table_work();let limits=decoder.limits().counted_in(work.clone());
    let mut budget=Budget::new(&limits,session);
    let g=relation_tables(gold,&decoder,&fixed,&limits,&work,&mut budget);
    let m=relation_tables(mutant.program(),&decoder,&fixed,&limits,&work,&mut budget);
    let status=|tables:&Outcome<Vec<(usize,Table)>>|match tables {Ok(t)=>table_status(t),Err(f)=>faulted(f)};
    let report=json!({"schema":"arclog-study-component-tables-v1","gold_observation_ref":memo.sequence,
        "full_choice_extents":g.as_ref().ok().map(|tables|full_choice_extents(tables,&fixed,task.train.len())),
        "kept_assignments":records,"gold_observation_stop":walked.stop.as_ref().map(stopped),
        "gold_status":status(&g),"mutant_status":status(&m),
        "gold_assignment_map":g.as_ref().ok().map(|t|assignment_map(t,2,task.train.len())),
        "mutant_assignment_map":m.as_ref().ok().map(|t|assignment_map(t,2,task.train.len())),
        "scope":"native materialized relations including computed INIT outputs under exact cached gold DET interventions; no new FITS or OUT search",
        "assignment_contract":"table_entry is the zero-based position among native entries for its table; kept_assignment indexes the full kept_assignments list even when DET subsets repeat",
        "bound_scope":"one shared native deadline and table-work budget"});
    Ok(ComponentTables {report,gold:g.unwrap_or_default(),mutant:m.unwrap_or_default()})
}

/// Mapping uses the exact native entries order, including repeated equal
/// assignments when a table reads only a subset. Never join choices by values.
pub fn assignment_map(tables:&[(usize,Table)],table_offset:usize,train_count:usize)->Value {
    json!(tables.iter().enumerate().map(|(number,(_,table))| {
        let mut entries=Vec::new();
        if let Ok(contents)=&table.contents {for example in &contents.examples {
            let (kind,index)=match example.example {
                None=>("task",0),
                Some(e) if usize::from(e.index())<train_count=>("train",usize::from(e.index())),
                Some(e)=>("test",usize::from(e.index())-train_count),
            };
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

pub fn relation_tables(program:&StudyProgram,decoder:&Decoder<'_>,fixed:&[Vec<Assignment>],limits:&arclog::eval::Limits,
    work:&TableWork,budget:&mut Budget<'_>)->Outcome<Vec<(usize,Table)>> {
    let checked=program.checked();
    let written=arclog::stream::written_stream(checked,decoder.vocabulary()).map_err(|d|fault(d.message,&NodePath::default()))?;
    let (task,session,constructions)=decoder.evaluation_inputs();
    let mut tables=Vec::new();
    for form in &written.forms {for &slot in &form.readable {
        budget.charge_work(0).map_err(|bound|fault(format!("continuation metadata stopped: {bound:?}"),&form.path))?;
        let declared=&written.relations[slot];
        if gives_no_table(program.program().value(),&form.path,declared) {continue;}
        let relation=graph_relation(checked,decoder.registry(),&form.path,declared).ok_or_else(||fault("no native graph for continuation relation",&form.path))?;
        let dets=relation_dets(checked,relation.node);
        let examples=decoder.examples_of(scope_of(checked,&relation)).into_iter().map(|example| {
            let mut at=Vec::new();
            for assigned in fixed {
                let projected=dets.iter().filter_map(|det|assigned.iter().find(|(name,_)|*name==det.relation).cloned()).collect::<Vec<_>>();
                if projected.len()!=dets.len() {return ExampleRows {example,rows:Err(fault("kept assignment lacks a continuation DET",&form.path))};}
                let parameters=ParameterValues::determined(assigned.clone());
                let e=Evaluation {program:checked,concept:None,task,session,constructions,registry:decoder.registry(),parameters:&parameters,limits};
                match models_at(&e,&relation,example) {
                    Ok(models)=>at.push((projected,models)),
                    Err(End::Fault(f))=>return ExampleRows {example,rows:Err(f)},
                    Err(End::Stop(stop))=>return ExampleRows {example,rows:Ok(Assigned {at,stop:Some(stop)})},
                }
            }
            ExampleRows {example,rows:Ok(Assigned {at,stop:None})}
        }).collect();
        let c=contents(decoder,checked,&form.path,&relation,slot as u32,&dets,examples,work).map(|c| {
            let c=Contents {name:relation_spelled(declared),keys:checked.program.column_keys(relation.node),..c};
            made(decoder,&tables.iter().map(|(_,t)|t).collect::<Vec<_>>(),checked,&relation,c)
        });
        tables.push((form.tokens.end.saturating_sub(1),Table {form:form.path.clone(),point:Point::Relation,contents:c}));
    }}
    Ok(tables)
}


/// Authoritative annotations of exact held gold parameter rows. Example/model
/// axes are retained; a task-wide value is not assigned an arbitrary example.
pub fn full_choice_extents(tables:&[(usize,Table)],fixed:&[Vec<Assignment>],train_count:usize)->Value {
    json!({"schema":"arclog-study-choice-extents-v1","choices":fixed.iter().enumerate().map(|(choice,assigned)| {
        let dets=assigned.iter().map(|(name,held)| {
            let source=relation_spelled(name);
            let contents=tables.iter().rev().filter_map(|(_,t)|t.contents.as_ref().ok()).find(|c|c.name==source);
            let Some(contents)=contents else {return json!({"source_name":source,"status":"unresolved","reason":"exact held relation table not materialized"});};
            let mut examples=Vec::new();
            for (place,e) in contents.examples.iter().enumerate() {
                let Some((_,models))=e.rows.as_ref().ok().and_then(|r|r.at.get(choice)) else {continue;};
                let (kind,index)=match e.example {None=>("task",0),Some(e) if usize::from(e.index())<train_count=>("train",usize::from(e.index())),Some(e)=>("test",usize::from(e.index())-train_count)};
                for (model,value) in models.iter().enumerate() {
                    let RelationValue::Rows(rows)=value else {continue;};
                    if rows.rows_hash()!=held.rows_hash() || rows.arity()!=held.arity() || rows.len()!=held.len() {continue;}
                    let annotations=crate::extents::annotated_rows(contents,place,choice,model,rows);
                    let columns=contents.columns.iter().enumerate().filter(|(_,c)|c.ty.is_box()).map(|(i,_)|i).collect::<Vec<_>>();
                    let mut at=0;let mut out=Vec::new();
                    each_row(rows,&mut |row| {
                        let cells=columns.iter().zip(&annotations[at]).map(|(column,(status,extent))|json!({
                            "column":column,"extent_status":match status {0=>"no_grid",1=>"resolved",_=>"unresolved"},
                            "extent":extent.map(|e|[e.rows,e.columns])})).collect::<Vec<_>>();
                        out.push(json!({"packed_row":row.iter().map(|t|t.encoding()).collect::<Vec<_>>(),"cells":cells}));at+=1;
                    });
                    examples.push(json!({"example_kind":kind,"example_index":index,"model":model,"rows":out}));
                }
            }
            json!({"source_name":source,"status":if examples.is_empty(){"unresolved"}else{"complete"},"examples":examples})
        }).collect::<Vec<_>>();
        json!({"assignment":choice,"dets":dets})
    }).collect::<Vec<_>>(),"identity_contract":"exact cached held gold values only; rows carry packed identity and example/model axes; no cross-example extent merge"})
}
