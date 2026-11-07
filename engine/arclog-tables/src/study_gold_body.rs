//! Original checked BODY evidence under the cached gold FITS interventions.
use super::*;

pub struct GoldBody {
    pub limits:arclog::eval::Limits,
    pub report:Value,
    pub tables:Vec<(usize,Table)>,
}

/// No assignment search or setter: the only interventions come from the exact
/// evaluator/gold handle's immutable GoldMemo. The optional JSON is an assertion.
pub fn evaluate_cached(gold:&StudyProgram,body:&NodePath,task:&Task,session:&TaskSession,
    constructions:&Constructions,settings:&DecodeSettings,cache:&mut PairCache,expected_kept:Option<&Value>)->Result<GoldBody,String> {
    evaluate_query(gold,body,task,session,constructions,settings,cache,expected_kept,None)
}

/// Native completed-conjunct frontier query at the same cached full choices.
pub fn evaluate_prefix_cached(gold:&StudyProgram,body:&NodePath,prefix:usize,task:&Task,session:&TaskSession,
    constructions:&Constructions,settings:&DecodeSettings,cache:&mut PairCache,expected_kept:Option<&Value>)->Result<GoldBody,String> {
    evaluate_query(gold,body,task,session,constructions,settings,cache,expected_kept,Some(prefix))
}

fn evaluate_query(gold:&StudyProgram,body:&NodePath,task:&Task,session:&TaskSession,
    constructions:&Constructions,settings:&DecodeSettings,cache:&mut PairCache,expected_kept:Option<&Value>,prefix:Option<usize>)->Result<GoldBody,String> {
    let limits=settings.operation_limits();
    let key=Arc::as_ptr(gold.checked()) as usize;
    let memo=Arc::clone(cache.gold.get(&key).ok_or("call gold_kept or evaluate_pair on this evaluator/program handle first; gold_body performs no FITS search")?);
    let (fixed,records)=memo.kept_values();
    if expected_kept.is_some_and(|expected|expected!=&json!(records)) {
        return Err("expected kept assignments differ from cached gold observation; refusing alternate assignments".into());
    }
    let mut report=gold_observation_report(gold,session,settings);
    if !report["program_provenance"]["stream"].is_null() {describe_gold_observation(&mut report,gold,&memo,true);}
    report["schema"]=json!("arclog-study-gold-body-v1");
    report["body_path"]=arclog::mutation::path_json(body);
    if let Some(count)=prefix {
        report["body_query"]=json!({"kind":"completed_conjunct_prefix","conjuncts":count,
            "branch_context":"preceding outer conjuncts and the selected OR branch; sibling branches excluded",
            "scope":"original checked owner; native INIT key and input context retained"});
    }
    report["body_table"]=Value::Null;
    report["body_assignment_map"]=Value::Null;
    report["body_status"]=json!({"status":"unavailable","reason":"BODY acquisition has not completed"});
    report["body_coverage"]=json!({"complete":false,"examples":[]});
    report["bound_scope"]=json!("one current operation request work cap and session across prefix, held BODY, extents and packing; canonical per-table work caps retained; cached FITS retains its original completion/stop");
    let mut result=GoldBody {limits:limits.clone(),report,tables:Vec::new()};
    if result.report["status"]=="fault" {return Ok(result);}
    if fixed.is_empty() || result.report["assignment_coverage_complete"]!=true {
        result.report["body_status"]=json!({"status":"unavailable","reason":"no kept assignments or a kept assignment lacks a native DET value"});
        return Ok(result);
    }
    let decoder=Decoder::new(task,session,Registry::get(),constructions,settings).with_operation_limits(limits);
    let acquired=(||->Outcome<()> {
        let view=match prefix {
            Some(count)=>arclog::eval::body_view::BodyView::prefix_at(gold.checked(),body,count)?,
            None=>arclog::eval::body_view::BodyView::keyed_at(gold.checked(),body)?,
        };
        if prefix.is_some() {
            result.report["body_query"]["columns"]=json!(view.clause.columns.iter().enumerate().map(|(i,v)| {
                json!({"physical_column":i,"label_id":view.paths.labels[v.0 as usize].0,
                    "scope_path":arclog::mutation::path_json(&view.form)})
            }).collect::<Vec<_>>());
        }
        result.report["owner_path"]=arclog::mutation::path_json(&view.form);
        result.report["body_scope"]=json!(format!("{:?}",view.scope));
        let written=source_stream(gold,&decoder,cache)?;
        let (prefix,_)=original_relations(gold,&written,Some(&view.form),&decoder,cache)?;
        result.tables=prefix;
        result.report["prefix_status"]=table_status(&result.tables);
        let dets=super::super::body_tables::dets(gold.checked(),&view);
        let index=written.forms.iter().find(|f|f.path==view.form)
            .ok_or_else(||fault("body owner is absent from the written stream",body))?.tokens.end.saturating_sub(1);
        let seen=result.tables.iter().map(|(_,t)|t).collect::<Vec<_>>();
        let contents=held_body_contents(gold,gold.checked(),&view,written.relations.len() as u32,&dets,&decoder,&fixed,&seen,None);
        let number=result.tables.len();
        result.tables.push((index,Table {form:view.form,point:Point::Body {conjuncts:view.clause.nodes.len() as u32,sites:0},contents}));
        let tables=&result.tables[number..];
        result.report["body_table"]=json!(2+number);
        result.report["body_assignment_map"]=component_tables::assignment_map(tables,2+number,task.train.len())[0].clone();
        result.report["body_status"]=table_status(tables);
        if let Ok(contents)=&tables[0].1.contents {
            let mut complete=true;
            let examples=contents.examples.iter().map(|example| {
                let (kind,index)=component_tables::example_axis(example.example,task.train.len());
                let status=match &example.rows {Err(f)=>faulted(f),Ok(rows)=>rows.stop.as_ref().map(stopped).unwrap_or_else(super::complete)};
                let counts=example.rows.as_ref().ok().map(|rows|rows.at.iter().map(|(_,models)|models.len()).collect::<Vec<_>>());
                complete &= status["status"]=="complete" && counts.as_ref().is_some_and(|c|c.len()==fixed.len());
                json!({"example_kind":kind,"example_index":index,"status":status,"model_counts":counts})
            }).collect::<Vec<_>>();
            result.report["body_coverage"]=json!({"complete":complete,"examples":examples});
        }
        let status=table_status(&result.tables);
        if status["status"]!="complete" {result.report["status"]=status["status"].clone();result.report["reason"]=status["reason"].clone();result.report["collection_status"]=status;}
        Ok(())
    })();
    if let Err(f)=acquired {
        result.report["status"]=json!("fault");result.report["reason"]=json!(f.message);
        result.report["body_status"]=faulted(&f);
    }
    Ok(result)
}
