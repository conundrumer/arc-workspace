//! Exact-kept interventions. Never enumerate or substitute a new FITS assignment.
use super::*;
use arclog::eval::determinations::{Domain, det_node};
use arclog::eval::join::Budget;
use arclog::relations::Relation;
use std::collections::BTreeSet;

#[path = "study_out.rs"]
mod output;

pub struct Continuation {
    pub report: Value,
    pub gold: Vec<(usize, Table)>,
    pub mutant: Vec<(usize, Table)>,
}

fn rows(value: &Relation, budget: &mut Budget<'_>, at: &NodePath) -> Result<BTreeSet<Vec<u32>>, End> {
    budget.charge_work(value.len().saturating_mul(u64::from(value.arity()).max(1)))
        .map_err(|bound| End::Stop(arclog::eval::Stop {bound, form:at.clone()}))?;
    let mut found=BTreeSet::new();
    each_row(value,&mut |row| {found.insert(row.iter().map(|term|term.encoding()).collect());});
    Ok(found)
}

fn admissibility(e:&Evaluation<'_>, gold:&CheckedProgram, assigned:&[Assignment], budget:&mut Budget<'_>) -> Vec<Value> {
    assigned.iter().map(|(name,held)| {
        let source=relation_spelled(name);
        let Some(node)=det_node(e.program,name) else {
            return json!({"source_name":source,"status":"complete","admissible":false,"reason":"held DET no longer exists"});
        };
        let at=e.program.program.form_of(node);
        let gold_types=det_node(gold,name).and_then(|node|gold.types.columns(&GraphRelation {node,output:None}));
        let mutant_types=e.program.types.columns(&GraphRelation {node,output:None});
        if gold_types.is_none() || gold_types!=mutant_types {
            return json!({"source_name":source,"status":"complete","admissible":false,
                "reason":"held gold DET schema differs from mutant schema","selected_value_overrides_proposal":true});
        }
        let Some(det)=relation_dets(e.program,node).into_iter().find(|det|det.node==node) else {
            return json!({"source_name":source,"status":"fault","reason":"held relation is not an assignable DET"});
        };
        // Remove only this intervention. All other gold-kept DET values stay fixed.
        let parameters=ParameterValues::determined(assigned.iter().filter(|(n,_)|n!=name).cloned());
        let reading=Evaluation {parameters:&parameters,..*e};
        let result=(|| -> Result<Value,End> {
            let target=rows(held,budget,at)?;
            let domain=reading.domain(node).map_err(End::Fault)?;
            match domain {
                Domain::Undefined=>Ok(json!({"status":"complete","admissible":false,"reason":"DET domain undefined"})),
                Domain::Stopped(stop)=>Err(End::Stop(stop)),
                Domain::Rows(values)=> {
                    let mut found=false;
                    for value in &values {
                        let candidate=rows(value,budget,at)?;
                        if (det.open && target.len()==1 && target.is_subset(&candidate)) || (!det.open && candidate==target) {found=true;}
                    }
                    Ok(json!({"status":"complete","admissible":found,"domain_values":values.len(),
                        "comparison":if det.open {"ONE: held singleton occurs in a native domain value"} else {"held row set equals a native domain value"}}))
                }
            }
        })();
        let mut report=match result {Ok(v)=>v,Err(End::Fault(f))=>faulted(&f),Err(End::Stop(s))=>stopped(&s)};
        report["source_name"]=source.into();report["selected_value_overrides_proposal"]=true.into();report
    }).collect()
}

/// Requires this evaluator's cached gold observation from evaluate_pair. If
/// supplied, expected_kept must exactly match that observation, including the
/// session's Ident encodings. A stale/different stored assignment is an error.
pub fn evaluate(gold:&StudyProgram,mutant:&ValidMutant,task:&Task,session:&TaskSession,
    constructions:&Constructions,settings:&DecodeSettings,cache:&PairCache,expected_kept:Option<&Value>)->Result<Continuation,String> {
    if !Arc::ptr_eq(gold.checked(),mutant.gold()) {return Err("mutant belongs to another gold handle".into());}
    let key=Arc::as_ptr(gold.checked()) as usize;
    let memo=cache.gold.get(&key).ok_or("call evaluate_pair on this evaluator/gold handle first; no new FITS search is performed")?;
    let walked=memo.walked.as_ref().map_err(|f|f.message.to_string())?;
    let mut fixed=Vec::new();let mut records=Vec::new();
    for (i,(assigned,train)) in walked.at.iter().enumerate() {if fits(train) {fixed.push(assigned.clone());records.push(memo.records[i].clone());}}
    if expected_kept.is_some_and(|expected|expected!=&json!(records)) {
        return Err("stored kept assignments differ from this evaluator's gold observation (possibly Ident namespace); refusing alternate FITS".into());
    }
    let decoder=Decoder::new(task,session,Registry::get(),constructions,settings);
    let work=decoder.table_work();let limits=decoder.limits().counted_in(work.clone());
    let mut budget=Budget::new(&limits,session);
    let mut choices=Vec::new();
    for (index,assigned) in fixed.iter().enumerate() {
        let parameters=ParameterValues::determined(assigned.clone());
        let e=Evaluation {program:mutant.program().checked(),concept:None,task,session,constructions,registry:Registry::get(),parameters:&parameters,limits:&limits};
        let checks=admissibility(&e,gold.checked(),assigned,&mut budget);
        let output=output_relation(e.program).ok_or("mutant has no OUT")?;
        let out=match output::train(&e,&output,&mut budget) {Ok(v)=>json!({"status":"complete","train":v}),Err(End::Fault(f))=>faulted(&f),Err(End::Stop(s))=>stopped(&s)};
        choices.push(json!({"assignment":index,"admissibility":checks,"out":out}));
    }
    let g=super::component_tables::relation_tables(gold,&decoder,&fixed,&limits,&work,&mut budget);
    let m=super::component_tables::relation_tables(mutant.program(),&decoder,&fixed,&limits,&work,&mut budget);
    let report=json!({"schema":"arclog-study-continuation-v1","gold_observation_ref":memo.sequence,
        "out_bindings":arclog::study::render_out::export(mutant.program())?,
        "kept_assignments":records,"gold_observation_stop":walked.stop.as_ref().map(stopped),"choices":choices,
        "gold_tables":g.status(),"mutant_tables":m.status(),
        "gold_collection":g.collection(),"mutant_collection":m.collection(),
        "assignment_scope":"exact cached gold FITS interventions; no alternate assignment search",
        "out_scope":"conditional OUT under held gold DET values; held values override DET proposal bodies even when inadmissible",
        "tables_scope":"all materialized native relations in written order, including INIT computed output ports; each table assignment index follows kept_assignments",
        "bound_scope":"one shared native deadline and table-work budget for this operation"});
    Ok(Continuation {report,gold:g.tables,mutant:m.tables})
}
