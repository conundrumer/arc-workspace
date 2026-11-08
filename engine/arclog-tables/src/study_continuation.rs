//! Exact-kept interventions. Never enumerate or substitute a new FITS assignment.
use super::*;
use arclog::eval::determinations::Domain;
use arclog::eval::join::Budget;
use arclog::relations::Relation;
use arclog::terms::TermKey;
use std::collections::BTreeSet;

#[path = "study_out.rs"]
mod output;

pub struct Continuation {
    pub limits:arclog::eval::Limits,
    pub report: Value,
    pub gold: Vec<(usize, Table)>,
    pub mutant: Vec<(usize, Table)>,
}

fn charge_rows(value:&Relation,budget:&mut Budget<'_>,at:&NodePath)->Result<(),End> {
    budget.charge_work(value.len().saturating_mul(u64::from(value.arity()).max(1)))
        .map_err(|bound| End::Stop(arclog::eval::Stop {bound, form:at.clone()}))
}

fn rows(value: &Relation, budget: &mut Budget<'_>, at: &NodePath) -> Result<StableHashSet<Vec<TermKey>>, End> {
    charge_rows(value,budget,at)?;
    let mut found=StableHashSet::default();
    each_row(value,&mut |row| {found.insert(row.iter().map(|term|term.key()).collect());});
    Ok(found)
}

/// The packed rows of an `OUT` relation, whose columns are a Position and a
/// Color, so that their encodings are fixed.
fn out_rows(value: &Relation, budget: &mut Budget<'_>, at: &NodePath) -> Result<BTreeSet<Vec<u32>>, End> {
    charge_rows(value,budget,at)?;
    let mut found=BTreeSet::new();
    each_row(value,&mut |row| {found.insert(row.iter().map(|term|term.fixed_encoding()).collect());});
    Ok(found)
}

fn admissibility(e:&Evaluation<'_>, gold:&CheckedProgram, assigned:&[Assignment], budget:&mut Budget<'_>) -> Vec<Value> {
    assigned.iter().map(|(name,held)| {
        let source=relation_spelled(name);
        let det=match gold.check_held_det_interface(e.program,name) {
            Ok(det)=>det,
            Err(error)=>return json!({"source_name":source,"status":"complete","admissible":false,
                "reason":error.to_string(),"selected_value_overrides_proposal":true}),
        };
        let node=det.node;
        let at=e.program.program.form_of(node);
        // Remove only this intervention. All other gold-kept DET values stay fixed.
        let parameters=ParameterValues::determined(assigned.iter().filter(|(n,_)|n!=name).cloned());
        let reading=Evaluation {parameters:&parameters,..*e};
        let result=(|| -> Result<Value,End> {
            let target=if det.open {Some(rows(held,budget,at)?)} else {
                charge_rows(held,budget,at)?;None
            };
            let domain=reading.domain(node).map_err(End::Fault)?;
            match domain {
                Domain::Undefined=>Ok(json!({"status":"complete","admissible":false,"reason":"DET domain undefined"})),
                Domain::Stopped(stop)=>Err(End::Stop(stop)),
                Domain::Rows(values)=> {
                    let mut found=false;
                    for value in &values {
                        let matches=if det.open {
                            let candidate=rows(value,budget,at)?;
                            target.as_ref().is_some_and(|target|target.len()==1 && target.is_subset(&candidate))
                        } else {
                            charge_rows(value,budget,at)?;
                            arclog::session::same_rows(held,value)
                        };
                        if matches {found=true;}
                    }
                    Ok(json!({"status":"complete","admissible":found,"domain_values":values.len(),
                        "comparison_test":if det.open {"singleton_membership"} else {"row_set_equality"},
                        "comparison":match (det.open,found) {
                            (true,true)=>"ONE: held singleton occurs in a native domain value",
                            (true,false)=>"ONE: held value is not a singleton occurring in any native domain value",
                            (false,true)=>"held row set equals a native domain value",
                            (false,false)=>"held row set does not equal any native domain value",
                        }}))
                }
            }
        })();
        let mut report=match result {Ok(v)=>v,Err(End::Fault(f))=>faulted(&f),Err(End::Stop(s))=>stopped(&s)};
        report["source_name"]=source.into();report["selected_value_overrides_proposal"]=true.into();report
    }).collect()
}

/// Requires this evaluator's cached gold observation from gold_kept or evaluate_pair. If
/// supplied, expected_kept must exactly match that observation, including the
/// session's Ident encodings. A stale/different stored assignment is an error.
pub fn evaluate(gold:&StudyProgram,mutant:&ValidMutant,task:&Task,judged:&JudgedTask,session:&TaskSession,
    constructions:&Constructions,settings:&DecodeSettings,cache:&PairCache,expected_kept:Option<&Value>)->Result<Continuation,String> {
    if !Arc::ptr_eq(gold.checked(),mutant.gold()) {return Err("mutant belongs to another gold handle".into());}
    gold.checked().check_held_det_interfaces(mutant.program().checked()).map_err(|e| e.to_string())?;
    let judge=judgement::TrainJudge::new(task,judged)?;
    let key=Arc::as_ptr(gold.checked()) as usize;
    let memo=cache.gold.get(&key).ok_or("call gold_kept or evaluate_pair on this evaluator/gold handle first; no new FITS search is performed")?;
    let walked=memo.walked.as_ref().map_err(|f|f.message.to_string())?;
    let (fixed,records)=memo.kept_values();
    if expected_kept.is_some_and(|expected|expected!=&json!(records)) {
        return Err("stored kept assignments differ from this evaluator's gold observation (possibly Ident namespace); refusing alternate FITS".into());
    }
    let operation=settings.operation_limits();
    let decoder=Decoder::new(task,session,Registry::get(),constructions,settings).with_operation_limits(operation);
    let work=decoder.query_work();let limits=decoder.limits().counted_in(work.clone());
    let mut budget=Budget::new(&limits,session);
    let mut choices=Vec::new();
    for (index,assigned) in fixed.iter().enumerate() {
        let parameters=ParameterValues::determined(assigned.clone());
        let e=Evaluation {program:mutant.program().checked(),concept:None,task,session,constructions,registry:Registry::get(),parameters:&parameters,limits:&limits};
        let checks=admissibility(&e,gold.checked(),assigned,&mut budget);
        let output=output_relation(e.program).ok_or("mutant has no OUT")?;
        let out=match output::train(&e,&output,&judge,&mut budget) {Ok(v)=>json!({"status":"complete","train":v}),Err(End::Fault(f))=>faulted(&f),Err(End::Stop(s))=>stopped(&s)};
        choices.push(json!({"assignment":index,"admissibility":checks,"out":out}));
    }
    let g=super::component_tables::relation_tables(gold,gold.checked(),&decoder,&fixed,&limits,&work,&mut budget);
    let m=super::component_tables::relation_tables(mutant.program(),gold.checked(),&decoder,&fixed,&limits,&work,&mut budget);
    let report=json!({"schema":"arclog-study-continuation-v1","gold_observation_ref":memo.sequence,
        "out_bindings":arclog::study::render_out::export(mutant.program())?,
        "kept_assignments":records,"gold_observation_stop":walked.stop.as_ref().map(stopped),"choices":choices,
        "gold_tables":g.status(),"mutant_tables":m.status(),
        "gold_collection":g.collection(),"mutant_collection":m.collection(),
        "assignment_scope":"exact cached gold FITS interventions; no alternate assignment search",
        "out_scope":"conditional OUT under held gold DET values; held values override DET proposal bodies even when inadmissible",
        "tables_scope":"all materialized native relations in written order, including INIT computed output ports; each table assignment index follows kept_assignments",
        "bound_scope":"one operation request work cap; per-evaluation binding and row caps for this operation"});
    Ok(Continuation {limits:limits.clone(),report,gold:g.tables,mutant:m.tables})
}
