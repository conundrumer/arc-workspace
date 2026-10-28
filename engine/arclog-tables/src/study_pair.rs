//! Clause-pair evaluation. All rows remain native export Tables; the two
//! programs share a TaskSession so Ident values have the same namespace.
use super::*;
use arclog::eval::instance::Constructions;
use arclog::eval::output::{GridColumns, read_grid};
use arclog::eval::{ParameterValues, output_relation};
use arclog::mutation::{MutationPoint, ValidMutant};
use arclog::session::TaskSession;
use arclog::stream::DecodeSettings;
use arclog::study::StudyProgram;
use arclog::task::Grid;
use serde_json::{Value, json};
use std::collections::{HashMap, HashSet, VecDeque};
use std::time::Instant;
use arclog::check::{CheckCache,CheckedProgram};

pub struct PairEvaluation {
    /// Full native tables, including preceding relation tables needed to
    /// resolve provenance/frame references. The last two are the complete
    /// body at all assignments, then at gold FITS assignments.
    pub gold: Vec<(usize, Table)>,
    pub mutant: Vec<(usize, Table)>,
    pub report: Value,
}

/// One task's reusable observations and bounded native prefix tables.
/// The binding owns this beside the task session; native identifiers and
/// cached rows never cross session namespaces.
pub struct PairCache {
    gold: HashMap<usize,Arc<GoldMemo>>,
    gold_bodies: HashMap<(usize,NodePath),Outcome<ClauseTables>>,
    gold_relations: HashMap<usize,(Arc<CheckedProgram>,Outcome<Vec<(usize,Table)>>)>,
    gold_body_hits:u64,
    prefixes: HashMap<Vec<u32>,(Vec<(usize,Table)>,usize)>,
    order: VecDeque<Vec<u32>>,
    bytes: usize,
    checks: CheckCache,
    pub compact: bool,
    gold_hits:u64,
    prefix_hits:u64,
    sequence:u64,
}
struct GoldMemo {
    _source:Arc<CheckedProgram>,
    walked:Outcome<Assigned<Value>>,
    records:Vec<Value>,
    sequence:u64,
}
impl Default for PairCache { fn default()->Self {Self::new(false)} }
impl PairCache {
    pub fn new(compact:bool)->Self {Self {gold:HashMap::new(),gold_bodies:HashMap::new(),gold_relations:HashMap::new(),gold_body_hits:0,prefixes:HashMap::new(),order:VecDeque::new(),bytes:0,checks:CheckCache::default(),compact,gold_hits:0,prefix_hits:0,sequence:0}}
    fn prefix(&mut self,key:&[u32])->Option<Vec<(usize,Table)>> {
        let found=self.prefixes.get(key).map(|(tables,_)|tables.clone());
        if found.is_some() {self.prefix_hits+=1;}
        found
    }
    fn remember(&mut self,key:Vec<u32>,tables:Vec<(usize,Table)>) {
        const CAP:usize=64*1024*1024;
        let mut bytes=key.len().saturating_mul(4)+4096;
        for (_,table) in &tables {if let Ok(c)=&table.contents {for ex in &c.examples {if let Ok(a)=&ex.rows {for (_,models) in &a.at {for model in models {if let RelationValue::Rows(r)=model {
            bytes=bytes.saturating_add(usize::try_from(r.len()).unwrap_or(usize::MAX).saturating_mul(usize::from(r.arity()).saturating_mul(8)+16));
        }}}}}}}
        if bytes>CAP || self.prefixes.contains_key(&key) {return;}
        while self.bytes.saturating_add(bytes)>CAP || self.prefixes.len()>=128 {
            let Some(old)=self.order.pop_front() else {break;};
            if let Some((_,size))=self.prefixes.remove(&old) {self.bytes-=size;}
        }
        self.bytes+=bytes;self.order.push_back(key.clone());self.prefixes.insert(key,(tables,bytes));
    }
    pub fn stats(&self)->Value {json!({"gold_hits":self.gold_hits,"gold_body_hits":self.gold_body_hits,"gold_body_entries":self.gold_bodies.len(),"gold_relation_entries":self.gold_relations.len(),"prefix_hits":self.prefix_hits,"prefix_entries":self.prefixes.len(),"prefix_bytes_estimate":self.bytes})}
}

fn fault(message: impl Into<Box<str>>, form: &NodePath) -> RunFault {
    RunFault {
        message: message.into(),
        form: form.clone(),
    }
}

/// Replay a checked complete-body view, preserving its INIT/CHOOSE
/// binding context, then evaluate every complete conjunct through the
/// native body interface. No partial-decoder approximation is used.
#[derive(Clone)]
struct ClauseTables {
    tables: Vec<(usize, Table)>,
    names: Vec<(ProgramRelation, ProgramRelation)>,
}

fn clause_tables(
    program: &StudyProgram,
    body: &NodePath,
    decoder: &mut Decoder<'_>,
    fixed: &[Vec<Assignment>],
    cache: &mut PairCache,
) -> Outcome<ClauseTables> {
    let view =
        arclog::study_clause::checked_body_cached(program, body, decoder.settings(), decoder.registry(), &mut cache.checks)
            .map_err(|s| fault(s, body))?;
    let written = arclog::stream::written_stream(&view, decoder.vocabulary())
        .map_err(|d| fault(d.message, body))?;
    let mut tables = Vec::new();
    let mut index = 0;
    while index < written.tokens.len() {
        let (token, emitter) = &written.tokens[index];
        if *emitter != arclog::stream::Emitter::Model {
            return Err(fault("unexpected engine token", body));
        }
        let step = decoder.step_untested(token.clone()).map_err(|e| {
            fault(
                format!("complete-body replay at token {index}: {e:?}"),
                body,
            )
        })?;
        let end = index + 1 + step.forced.len();
        if end > written.tokens.len()
            || step
                .forced
                .iter()
                .zip(&written.tokens[index + 1..end])
                .any(|(a, (b, emitter))| a != b || *emitter != arclog::stream::Emitter::Engine)
        {
            return Err(fault("complete-body replay echo mismatch", body));
        }
        if end < written.tokens.len() && decoder.before().is_some_and(|before|decoder.program().value().forms.len()>before.program().value().forms.len()) {
            let key=written.tokens[..end].iter().map(|(token,_)|decoder.vocabulary().id(token).expect("a written vocabulary token")).collect::<Vec<_>>();
            match cache.prefix(&key) {
                Some(held)=>tables.extend(held),
                None=>{
                    let seen=tables.iter().map(|(_,t)|t).collect::<Vec<_>>();
                    let held=step_tables(decoder,Points::Relations,&seen).into_iter().map(|t|(index,t)).collect::<Vec<_>>();
                    cache.remember(key,held.clone());tables.extend(held);
                }
            }
        }
        index = end;
    }
    let before = decoder
        .before()
        .ok_or_else(|| fault("complete-body replay has no final step", body))?;
    let checked = decoder
        .finished_checked(before, decoder.state())
        .as_ref()
        .map_err(Clone::clone)?;
    let form = NodePath::top(decoder.program().value().forms.len() as u32 - 1);
    let relation = derived_at(checked, &form);
    let dets = walked_dets(checked, relation.node);
    let Some(NodeRef::Clause(clause)) = node_at(NodeRef::Program(decoder.program().value()), &form)
    else {
        return Err(fault("body view is not a completed clause", body));
    };
    let kept = (0..clause.body.value().conjuncts.len() as u32).collect::<Vec<_>>();
    let point = Point::Body {
        conjuncts: kept.len() as u32,
        sites: 0,
    };
    let work = decoder.table_work();
    let examples = decoder
        .examples_of(scope_of(checked, &relation))
        .into_iter()
        .map(|example| ExampleRows {
            example,
            rows: decoder.assigned(
                checked,
                relation.node,
                &dets,
                Some(&work),
                &mut |evaluation| {
                    evaluation
                        .body(&form, &kept, example)
                        .map(|v| vec![v.0])
                        .map_err(End::Fault)
                },
            ),
        })
        .collect();
    let held = contents(
        decoder,
        checked,
        &form,
        &relation,
        decoder.state().finished_slots() - 1,
        &dets,
        examples,
        &work,
    )?;
    let seen = tables.iter().map(|(_, t)| t).collect::<Vec<_>>();
    let held = made(decoder, &seen, checked, &relation, held);
    tables.push((
        index,
        Table {
            form: form.clone(),
            point,
            contents: Ok(held),
        },
    ));
    let work = decoder.table_work();
    let decoded = decoder.state().declared_from(0).collect::<Vec<_>>();
    let examples=decoder.examples_of(scope_of(checked,&relation)).into_iter().map(|example| {
        let mut at=Vec::new();
        for assigned in fixed {
            let mapped=assigned.iter().filter_map(|(name,rows)| {
                let slot=written.relations.iter().position(|r|r==name)?;
                let (_,relation)=decoded.iter().find(|(s,_)|*s==slot as u32)?;
                Some(((*relation).clone(),rows.clone()))
            }).collect::<Vec<_>>();
            let parameters=ParameterValues::determined(mapped.clone());
            let limits=decoder.limits().counted_in(work.clone());
            let (task,session,constructions)=decoder.evaluation_inputs();
            let evaluation=Evaluation {program:checked,concept:None,task,session,constructions,registry:decoder.registry(),parameters:&parameters,limits:&limits};
            let models=match evaluation.body(&form,&kept,example) {Ok(v)=>vec![v.0],Err(f)=>return ExampleRows {example,rows:Err(f)}};
            let projected=dets.iter().filter_map(|det|mapped.iter().find(|(name,_)|name==&det.relation).cloned()).collect::<Vec<_>>();
            if projected.len()!=dets.len() {
                return ExampleRows {example,rows:Err(fault("gold FITS assignment does not assign every DET required by the mutant clause view",body))};
            }
            at.push((projected,models));
        }
        ExampleRows {example,rows:Ok(Assigned {at,stop:None})}
    }).collect();
    let held = contents(
        decoder,
        checked,
        &form,
        &relation,
        decoder.state().finished_slots() - 1,
        &dets,
        examples,
        &work,
    )?;
    let seen = tables[..tables.len() - 1]
        .iter()
        .map(|(_, t)| t)
        .collect::<Vec<_>>();
    let held = made(decoder, &seen, checked, &relation, held);
    tables.push((
        index,
        Table {
            form,
            point,
            contents: Ok(held),
        },
    ));
    // Recover original label identities for comparison; presentation names
    // remain exactly the native decoded/export names.
    let written_form = written
        .forms
        .last()
        .ok_or_else(|| fault("body view has no written form", body))?;
    let count = tables.len();
    for (_, table) in &mut tables[count - 2..] {
        if let Ok(c) = &mut table.contents {
            for column in &mut c.columns {
                column.label_id = column
                    .label_id
                    .and_then(|id| written_form.labels.get(id.0 as usize))
                    .copied();
            }
        }
    }
    let names = decoder
        .state()
        .declared_from(0)
        .map(|(slot, name)| (name.clone(), written.relations[slot as usize].clone()))
        .collect();
    Ok(ClauseTables { tables, names })
}

fn stopped(stop: &arclog::eval::Stop) -> Value {
    json!({"status":"stopped", "reason":format!("{:?}",stop.bound), "form":format!("{:?}",stop.form)})
}
fn faulted(f: &RunFault) -> Value {
    json!({"status":"fault", "reason":f.message, "form":format!("{:?}",f.form)})
}
fn complete() -> Value {
    json!({"status":"complete"})
}

fn table_status(tables: &[(usize, Table)]) -> Value {
    for (_, table) in tables {
        let c = match &table.contents {
            Ok(c) => c,
            Err(f) => return faulted(f),
        };
        if let Some(Projections::Stopped(stop)) = &c.projections {
            return stopped(stop);
        }
        for example in &c.examples {
            let rows = match &example.rows {
                Ok(r) => r,
                Err(f) => return faulted(f),
            };
            if let Some(stop) = &rows.stop {
                return stopped(stop);
            }
            for (_, models) in &rows.at {
                for value in models {
                    if let RelationValue::Stopped(stop) = value {
                        return stopped(stop);
                    }
                }
            }
        }
        if let Some(extents) = &c.extents {
            // Extent loss/stop is part of completeness, never silently
            // collapsed to an unknown size in the pair's status.
            for (e, example) in c.examples.iter().enumerate() {
                if let Ok(rows) = &example.rows {
                    for (a, (_, models)) in rows.at.iter().enumerate() {
                        for m in 0..models.len() {
                            match extents.entry(e, a, m) {
                                Some(crate::extents::EntryExtents::Stopped(stop)) => {
                                    return stopped(stop);
                                }
                                Some(crate::extents::EntryExtents::Lost(reason)) => {
                                    return json!({"status":"fault","reason":reason});
                                }
                                _ => {}
                            }
                        }
                    }
                }
            }
        }
    }
    complete()
}

fn row_set(rows: &arclog::relations::Relation) -> HashSet<Vec<u32>> {
    let mut set = HashSet::new();
    each_row(rows, &mut |row| {
        set.insert(row.iter().map(|t| t.encoding()).collect());
    });
    set
}
fn assigned_equal(
    a: &[Assignment],
    b: &[Assignment],
    a_names: &[(ProgramRelation, ProgramRelation)],
    b_names: &[(ProgramRelation, ProgramRelation)],
) -> bool {
    let canonical = |name: &ProgramRelation, names: &[(ProgramRelation, ProgramRelation)]| {
        names
            .iter()
            .find(|(decoded, _)| decoded == name)
            .map(|(_, original)| original.clone())
            .unwrap_or_else(|| name.clone())
    };
    a.len() == b.len()
        && a.iter().all(|(name, rows)| {
            b.iter().any(|(other, value)| {
                canonical(name, a_names) == canonical(other, b_names)
                    && row_set(rows) == row_set(value)
            })
        })
}
fn assignment_json(a: &[Assignment]) -> Value {
    json!(
        a.iter()
            .map(|(name, rows)| {
                let mut rows = row_set(rows).into_iter().collect::<Vec<_>>();
                rows.sort();
                json!({"relation":relation_spelled(name), "rows":rows})
            })
            .collect::<Vec<_>>()
    )
}

fn absent_assignment(value: &RelationValue, gold_only: bool) -> Value {
    match value {
        RelationValue::Rows(rows) => {
            json!({"status":"complete","relation":if rows.is_empty() {"equal"} else if gold_only {"subset"} else {"superset"},"kept":0,"extra":if gold_only {0} else {rows.len()},"missing":if gold_only {rows.len()} else {0},"assignment_presence":if gold_only {"gold_only"} else {"mutant_only"}})
        }
        RelationValue::Stopped(stop) => stopped(stop),
        RelationValue::Undefined => {
            json!({"status":"fault","reason":"undefined table at an assignment absent from the other domain"})
        }
    }
}

fn comparisons(
    gold: &Table,
    mutant: &Table,
    fixed: bool,
    work: &TableWork,
    gold_names: &[(ProgramRelation, ProgramRelation)],
    mutant_names: &[(ProgramRelation, ProgramRelation)],
) -> Value {
    let (Ok(g), Ok(m)) = (&gold.contents, &mutant.contents) else {
        return json!([]);
    };
    // Rows are typed label tuples. Differently shaped schemas have no
    // equal tuples; retain their counts and mark schema_equal=false.
    let order = g
        .columns
        .iter()
        .map(|a| {
            m.columns
                .iter()
                .position(|b| a.ty == b.ty && a.label_id == b.label_id)
        })
        .collect::<Option<Vec<_>>>();
    let compatible = g.columns.len() == m.columns.len() && order.is_some();
    let mut out = Vec::new();
    for ex in &g.examples {
        let Some(other) = m.examples.iter().find(|e| e.example == ex.example) else {
            out.push(json!({"example":ex.example.map(|e|e.index()),"status":"fault","reason":"mutant has no matching example scope"}));
            continue;
        };
        let (Ok(gr), Ok(mr)) = (&ex.rows, &other.rows) else {
            continue;
        };
        for (a, (assigned, models)) in gr.at.iter().enumerate() {
            let Some((_, others)) = (if fixed {
                mr.at.get(a)
            } else {
                mr.at
                    .iter()
                    .find(|(b, _)| assigned_equal(assigned, b, gold_names, mutant_names))
            }) else {
                for (model, value) in models.iter().enumerate() {
                    let mut row = absent_assignment(value, true);
                    row["example"] = json!(ex.example.map(|e| e.index()));
                    row["assignment"] = json!(a);
                    row["model"] = json!(model);
                    out.push(row);
                }
                continue;
            };
            for (model, (gv, mv)) in models.iter().zip(others).enumerate() {
                let mut row =
                    json!({"example":ex.example.map(|e|e.index()),"assignment":a,"model":model});
                match (gv, mv) {
                    (RelationValue::Rows(g), RelationValue::Rows(m)) => {
                        if let Err(bound) = work.charge(g.len().saturating_add(m.len())) {
                            row["status"] = json!("stopped");
                            row["reason"] = json!(format!("{bound:?}"));
                            out.push(row);
                            continue;
                        }
                        let g = row_set(g);
                        let raw = row_set(m);
                        let m = if let Some(order) = &order {
                            raw.into_iter()
                                .map(|row| order.iter().map(|&i| row[i]).collect::<Vec<_>>())
                                .collect::<HashSet<_>>()
                        } else {
                            raw
                        };
                        let kept = if compatible {
                            g.intersection(&m).count()
                        } else {
                            0
                        };
                        let extra = m.len() - kept;
                        let missing = g.len() - kept;
                        row["schema_equal"] = json!(compatible);
                        row["status"] = json!("complete");
                        row["relation"] = json!(if extra == 0 && missing == 0 {
                            "equal"
                        } else if extra == 0 {
                            "subset"
                        } else if missing == 0 {
                            "superset"
                        } else {
                            "overlap"
                        });
                        row["kept"] = json!(kept);
                        row["extra"] = json!(extra);
                        row["missing"] = json!(missing);
                    }
                    (RelationValue::Stopped(s), _) | (_, RelationValue::Stopped(s)) => {
                        row["result"] = stopped(s);
                        row["status"] = json!("stopped");
                    }
                    _ => {
                        row["status"] = json!("fault");
                        row["reason"] = json!(if compatible {
                            "undefined clause table"
                        } else {
                            "clause body column schemas differ"
                        });
                    }
                }
                out.push(row);
            }
            if models.len() != others.len() {
                out.push(json!({"example":ex.example.map(|e|e.index()),"assignment":a,"status":"fault","reason":"model counts differ; unmatched models are not compared"}));
            }
        }
        for (a, (assigned, models)) in mr.at.iter().enumerate() {
            if !fixed
                && !gr
                    .at
                    .iter()
                    .any(|(b, _)| assigned_equal(assigned, b, mutant_names, gold_names))
            {
                for (model, value) in models.iter().enumerate() {
                    let mut row = absent_assignment(value, false);
                    row["example"] = json!(ex.example.map(|e| e.index()));
                    row["mutant_assignment"] = json!(a);
                    row["model"] = json!(model);
                    out.push(row);
                }
            }
        }
    }
    json!(out)
}

fn differences(a: &Grid, b: &Grid) -> usize {
    let (a, b) = (a.rows(), b.rows());
    (0..a.len().max(b.len()))
        .map(|r| {
            let (a, b) = (a.get(r), b.get(r));
            (0..a.map_or(0, |v| v.len()).max(b.map_or(0, |v| v.len())))
                .filter(|&c| a.and_then(|v| v.get(c)) != b.and_then(|v| v.get(c)))
                .count()
        })
        .sum()
}
/// For a non-grid OUT, count expected cells that are missing, ambiguous,
/// differently colored or in the wrong frame, plus occupied extra cells.
fn invalid_differences(rows: &arclog::relations::Relation, expected: &Grid) -> usize {
    let mut cells: HashMap<(i32, i32), HashSet<(u32, i32, i32)>> = HashMap::new();
    each_row(rows, &mut |row| {
        let p = Term::decode_box(row[0]);
        cells.entry((p.top, p.left)).or_default().insert((
            row[1].encoding(),
            p.top + p.bottom + 1,
            p.left + p.right + 1,
        ));
    });
    let height = expected.rows().len() as i32;
    let width = expected.rows()[0].len() as i32;
    let mut different = 0;
    for (r, row) in expected.rows().iter().enumerate() {
        for (c, color) in row.iter().enumerate() {
            let expected = (
                Term::Constant(Constant::Color(*color))
                    .encode()
                    .unwrap()
                    .encoding(),
                height,
                width,
            );
            if cells
                .remove(&(r as i32, c as i32))
                .is_none_or(|v| v.len() != 1 || !v.contains(&expected))
            {
                different += 1;
            }
        }
    }
    different + cells.len()
}

fn train(e: &Evaluation<'_>, output: &GraphRelation) -> Result<Value, End> {
    let mut out = Vec::new();
    for (example, pair) in e.task.examples().zip(e.task.train.iter()) {
        let mut models = Vec::new();
        let mut model_stop = None;
        let end=e.models(output,Some(example),&mut |value| {
            models.push(match value {
                RelationValue::Stopped(stop)=>{model_stop=Some(stop.clone());stopped(stop)},
                RelationValue::Undefined=>json!({"status":"complete","equals":false,"differing_cells":pair.output.rows().iter().map(|r|r.len()).sum::<usize>(),"grid_defined":false,"reason":"undefined OUT"}),
                RelationValue::Rows(rows)=>match read_grid(rows,GridColumns::OUT) {
                    Some(grid)=>json!({"status":"complete","equals":grid==pair.output,"differing_cells":differences(&grid,&pair.output)}),
                    None=>json!({"status":"complete","equals":false,"differing_cells":invalid_differences(rows,&pair.output),"grid_defined":false,"reason":"OUT rows do not define a grid"}),
                }
            }); ControlFlow::Continue(())
        }).map_err(End::Fault)?;
        if let ModelsEnd::Stopped(stop) = end {
            return Err(End::Stop(stop));
        }
        if let Some(stop) = model_stop {
            return Err(End::Stop(stop));
        }
        out.push(json!({"example":example.index(),"models":models}));
    }
    Ok(json!(out))
}
fn fits(train: &Value) -> bool {
    train.as_array().is_some_and(|pairs| {
        !pairs.is_empty()
            && pairs.iter().all(|p| {
                p["models"].as_array().is_some_and(|models| {
                    !models.is_empty() && models.iter().all(|m| m["equals"] == true)
                })
            })
    })
}

/// Evaluate all gold OUT assignments, retain every FITS assignment, and
/// evaluate the complete mutant at precisely those native parameter values.
/// Independent pairs can run concurrently (no GIL in the binding).
fn evaluate_pair_inner(
    gold: &StudyProgram,
    point: &MutationPoint,
    mutant: &ValidMutant,
    task: &Task,
    session: &TaskSession,
    constructions: &Constructions,
    settings: &DecodeSettings,
    cache:&mut PairCache,
) -> PairEvaluation {
    let mut result = PairEvaluation {
        gold: Vec::new(),
        mutant: Vec::new(),
        report: json!({"status":"complete","kept_assignments":[],"outputs":[],"comparisons":[]}),
    };
    if !Arc::ptr_eq(gold.checked(), mutant.gold())
        || point.body != mutant.point().body
        || point.clause != mutant.point().clause
    {
        result.report = json!({"status":"fault","reason":"gold, point and mutant do not belong to the same certified pair"});
        return result;
    }
    let mut gd = Decoder::new(task, session, Registry::get(), constructions, settings);
    let mut md = Decoder::new(task, session, Registry::get(), constructions, settings);
    let Some(output) = output_relation(gold.checked()) else {
        result.report = faulted(&fault("gold has no OUT", &point.clause));
        return result;
    };
    let Some(mutant_output) = output_relation(mutant.program().checked()) else {
        result.report = faulted(&fault("mutant has no OUT", &point.clause));
        return result;
    };
    let work = gd.table_work();
    // An unused gold clause can read a DET that OUT does not reach. Walk
    // the program's DETs so its FITS records still assign that clause's
    // parameters explicitly; OUT remains the sole FITS criterion.
    let gold_started=Instant::now();
    let gold_key=Arc::as_ptr(gold.checked()) as usize;
    let gold_hit=cache.gold.contains_key(&gold_key);
    let memo=if gold_hit {cache.gold_hits+=1;Arc::clone(&cache.gold[&gold_key])} else {
        let dets=arclog::eval::determinations::determinations(gold.checked()).into_iter().filter_map(|node|relation_dets(gold.checked(),node).into_iter().find(|det|det.node==node)).collect::<Vec<_>>();
        let walked=gd.assigned(gold.checked(),output.node,&dets,Some(&work),&mut |e|train(e,&output));
        let records=walked.as_ref().map(|w|w.at.iter().map(|(a,_)|assignment_json(a)).collect()).unwrap_or_default();
        cache.sequence+=1;
        let memo=Arc::new(GoldMemo {_source:Arc::clone(gold.checked()),walked,records,sequence:cache.sequence});
        cache.gold.insert(gold_key,Arc::clone(&memo));memo
    };
    let gold_seconds=gold_started.elapsed().as_secs_f64();
    let include_gold=!cache.compact || !gold_hit;
    result.report["gold_observation_ref"]=json!(memo.sequence);
    result.report["gold_observation_cached"]=json!(gold_hit);
    let mut mutant_out_seconds=0.;
    let mut fixed = Vec::new();
    let mut gold_assignments = Vec::new();
    match &memo.walked {
        Err(f) => {
            result.report["status"] = json!("fault");
            result.report["reason"] = json!(f.message);
        }
        Ok(walked) => {
            let mut kept = Vec::new();
            let mut outputs = Vec::new();
            for (assignment_index,(assigned, gold_train)) in walked.at.iter().enumerate() {
                if include_gold {gold_assignments.push(json!({"assignment":memo.records[assignment_index],"fits":fits(gold_train),"train":gold_train}));}
                if !fits(&gold_train) {
                    continue;
                }
                let index = fixed.len();
                if include_gold {kept.push(memo.records[assignment_index].clone());}
                fixed.push(assigned.clone());
                let parameters = ParameterValues::determined(assigned.clone());
                let limits = md.limits().counted_in(work.clone());
                let evaluation = Evaluation {
                    program: mutant.program().checked(),
                    concept: None,
                    task,
                    parameters: &parameters,
                    session,
                    registry: Registry::get(),
                    constructions,
                    limits: &limits,
                };
                let out_started=Instant::now();
                let mutant_train = match train(&evaluation, &mutant_output) {
                    Ok(v) => json!({"status":"complete","train":v}),
                    Err(End::Stop(s)) => stopped(&s),
                    Err(End::Fault(f)) => faulted(&f),
                };
                mutant_out_seconds+=out_started.elapsed().as_secs_f64();
                let mut output=json!({"assignment":index,"mutant":mutant_train});
                if include_gold {output["gold_train"]=gold_train.clone();}
                outputs.push(output);
            }
            result.report["kept_assignments"] = json!(kept);
            result.report["outputs"] = json!(outputs);
            if let Some(stop) = &walked.stop {
                result.report["status"] = json!("stopped");
                result.report["reason"] = stopped(&stop)["reason"].clone();
            }
        }
    }
    if include_gold {result.report["gold_assignments"] = json!(gold_assignments);} else {result.report.as_object_mut().unwrap().remove("kept_assignments");}
    result.report["kept_assignment_count"]=json!(fixed.len());
    result.report["gold_fits"] = if !fixed.is_empty() {
        json!(true)
    } else if result.report["status"] == "complete" {
        json!(false)
    } else {
        Value::Null
    };
    let gold_names;
    let mutant_names;
    let clause_started=Instant::now();
    let body_key=(gold_key,point.body.clone());
    let gold_body=match cache.gold_bodies.get(&body_key) {
        Some(held)=>{cache.gold_body_hits+=1;held.clone()},
        None=>{let held=clause_tables(gold,&point.body,&mut gd,&fixed,cache);cache.gold_bodies.insert(body_key,held.clone());held}
    };
    match gold_body {
        Ok(t) => {
            result.gold = t.tables;
            gold_names = t.names;
        }
        Err(f) => {
            result.report["status"] = json!("fault");
            result.report["reason"] = json!(f.message);
            return result;
        }
    }
    let gold_clause_seconds=clause_started.elapsed().as_secs_f64();
    let clause_started=Instant::now();
    match clause_tables(mutant.program(), &point.body, &mut md, &fixed, cache) {
        Ok(t) => {
            result.mutant = t.tables;
            mutant_names = t.names;
        }
        Err(f) => {
            result.report["status"] = json!("fault");
            result.report["reason"] = json!(f.message);
            return result;
        }
    }
    let mutant_clause_seconds=clause_started.elapsed().as_secs_f64();
    let comparison_started=Instant::now();
    let (g, m) = (result.gold.len(), result.mutant.len());
    result.report["table_indices"] = json!({"gold_all":g,"gold_kept":g+1,"mutant_all":m,"mutant_kept":m+1,"note":"indices include the two evidence tables; kept entries follow kept_assignments order"});
    let comparison_work = TableWork::new(settings.table_work_cap);
    result.report["comparisons"] = comparisons(
        &result.gold[g - 2].1,
        &result.mutant[m - 2].1,
        false,
        &comparison_work,
        &gold_names,
        &mutant_names,
    );
    result.report["kept_comparisons"] = comparisons(
        &result.gold[g - 1].1,
        &result.mutant[m - 1].1,
        true,
        &comparison_work,
        &gold_names,
        &mutant_names,
    );
    result.report["gold_tables"] = table_status(&result.gold);
    result.report["mutant_tables"] = table_status(&result.mutant);
    result.report["timings"]=json!({"gold_fits":gold_seconds,"gold_clause":gold_clause_seconds,"mutant_clause":mutant_clause_seconds,"mutant_out":mutant_out_seconds,"comparison":comparison_started.elapsed().as_secs_f64()});
    result.report["cache"]=cache.stats();
    // Explicitly propagate any partial component to the pair status.
    if result.report["status"] == "complete" {
        let bad = [
            result.report["gold_tables"].clone(),
            result.report["mutant_tables"].clone(),
        ]
        .into_iter()
        .chain(
            result.report["outputs"]
                .as_array()
                .into_iter()
                .flatten()
                .map(|o| o["mutant"].clone()),
        )
        .chain(
            result.report["kept_comparisons"]
                .as_array()
                .into_iter()
                .flatten()
                .cloned(),
        )
        .chain(
            result.report["comparisons"]
                .as_array()
                .into_iter()
                .flatten()
                .cloned(),
        )
        .find(|v| v["status"] != "complete");
        if let Some(bad) = bad {
            result.report["status"] = bad["status"].clone();
            result.report["reason"] = bad["reason"].clone();
        }
    }
    result
}

/// A panic is an explicit fault of this pair; a corpus run retains its
/// context and can continue inspecting independent pairs.
pub fn evaluate_pair(
    gold: &StudyProgram,
    point: &MutationPoint,
    mutant: &ValidMutant,
    task: &Task,
    session: &TaskSession,
    constructions: &Constructions,
    settings: &DecodeSettings,
) -> PairEvaluation {
    evaluate_pair_cached(gold,point,mutant,task,session,constructions,settings,&mut PairCache::default())
}

pub fn evaluate_pair_cached(gold:&StudyProgram,point:&MutationPoint,mutant:&ValidMutant,task:&Task,session:&TaskSession,constructions:&Constructions,settings:&DecodeSettings,cache:&mut PairCache)->PairEvaluation {
    std::panic::catch_unwind(std::panic::AssertUnwindSafe(||evaluate_pair_inner(gold,point,mutant,task,session,constructions,settings,cache)))
        .unwrap_or_else(|payload|PairEvaluation {gold:Vec::new(),mutant:Vec::new(),report:json!({"status":"fault","reason":format!("pair evaluation panicked: {}",arclog::decode::corpus::replay_panic(&*payload))})})
}

/// Full native relation tables, evaluated once per gold handle in this task
/// session. Faults and work-cap stops are cached as observations too.
pub fn gold_tables_cached(gold:&StudyProgram,task:&Task,session:&TaskSession,constructions:&Constructions,settings:&DecodeSettings,cache:&mut PairCache)->(Value,Vec<(usize,Table)>) {
    let key=Arc::as_ptr(gold.checked()) as usize;
    let hit=cache.gold_relations.contains_key(&key);
    if !hit {
        let held=std::panic::catch_unwind(std::panic::AssertUnwindSafe(|| {
            let mut decoder=Decoder::new(task,session,Registry::get(),constructions,settings);
            let written=arclog::stream::written_stream(gold.checked(),decoder.vocabulary()).map_err(|d|fault(d.message,&NodePath::default()))?;
            let mut tables=Vec::new();
            let mut index=0;
            while index<written.tokens.len() {
                let (token,emitter)=&written.tokens[index];
                if *emitter!=arclog::stream::Emitter::Model {return Err(fault("unexpected engine token in gold relation replay",&NodePath::default()));}
                let step=decoder.step_untested(token.clone()).map_err(|e|fault(format!("gold relation replay at token {index}: {e:?}"),&NodePath::default()))?;
                let end=index+1+step.forced.len();
                if end>written.tokens.len() || step.forced.iter().zip(&written.tokens[index+1..end]).any(|(a,(b,emitter))|a!=b || *emitter!=arclog::stream::Emitter::Engine) {return Err(fault("gold relation replay echo mismatch",&NodePath::default()));}
                if decoder.before().is_some_and(|before|decoder.program().value().forms.len()>before.program().value().forms.len()) {
                    let prefix=written.tokens[..end].iter().map(|(token,_)|decoder.vocabulary().id(token).expect("a written vocabulary token")).collect::<Vec<_>>();
                    match cache.prefix(&prefix) {
                        Some(held)=>tables.extend(held),
                        None=>{
                            let seen=tables.iter().map(|(_,table)|table).collect::<Vec<_>>();
                            let held=step_tables(&decoder,Points::Relations,&seen).into_iter().map(|table|(index,table)).collect::<Vec<_>>();
                            cache.remember(prefix,held.clone());tables.extend(held);
                        }
                    }
                }
                index=end;
            }
            Ok(tables)
        })).unwrap_or_else(|payload|Err(fault(format!("gold relation evaluation panicked: {}",arclog::decode::corpus::replay_panic(&*payload)),&NodePath::default())));
        cache.gold_relations.insert(key,(Arc::clone(gold.checked()),held));
    }
    match &cache.gold_relations[&key].1 {
        Ok(tables)=>{let mut report=table_status(tables);report["cached"]=json!(hit);report["relation_tables"]=json!(tables.len());(report,tables.clone())},
        Err(f)=>{let mut report=faulted(f);report["cached"]=json!(hit);(report,Vec::new())}
    }
}
