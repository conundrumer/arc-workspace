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
use arclog::task::JudgedTask;
use serde_json::{Value, json};
use std::collections::{HashMap, HashSet};
use std::time::Instant;
use arclog::check::{CheckedProgram};

#[path = "study_continuation.rs"]
pub mod continuation;
#[path = "study_component_tables.rs"]
pub mod component_tables;

#[path = "study_gold_body.rs"]
pub mod gold_body;

#[path = "study_prefix.rs"]
pub mod prefix;

#[path = "study_judgement.rs"]
mod judgement;

#[path = "study_form_memo.rs"]
pub mod form_memo;


/// Per-session study budget: 16 workers share the pipeline's 8 GiB memory
/// alert allowance. Callers can explicitly choose another session bound.
pub const STUDY_SESSION_BYTES:usize=512*1024*1024;

/// The bindings that the rows of one table of [`gold_tables_cached_in`] may
/// count. The count depends on the program alone, so this cap stops a table at
/// one place at any machine load.
pub const TABLE_ROW_WORK:u64=1<<28;

/// The bytes at which [`table_limits`] stops an evaluation. No table of a
/// program is meant to reach it: it guards the machine, and a caller takes a
/// stop at it as a failure of the program ([`stopped_at_bytes`]), since the
/// heap count it reads depends on the session's history.
pub const TABLE_BYTES:usize=4<<30;

/// The limits of [`gold_tables_cached_in`]: a request that begins now, under the
/// request work cap of `settings`, with no clock, whatever deadline the
/// settings hold, so that the rows of a table do not depend on machine load.
/// The request's work sums the queries, the walks and the packing of the
/// call, so the call stops at the cap where the work of its tables passes it,
/// on whatever table that is.
pub fn table_limits(settings:&DecodeSettings)->arclog::eval::Limits {
    settings.operation_limits().bound_by(arclog::session::SessionBound {bytes:TABLE_BYTES})
}

/// A stop in `tables`, in rows, projections or extents, at a bound that `at` takes.
fn stopped_where(tables:&[(usize,Table)],at:impl Fn(arclog::eval::ReachedBound)->bool)->Option<arclog::eval::Stop> {
    let taken=|stop:&arclog::eval::Stop|at(stop.bound);
    for (_,table) in tables {
        let Ok(contents)=&table.contents else {continue};
        if let Some(Projections::Stopped(stop))=&contents.projections {
            if taken(stop) {return Some(stop.clone());}
        }
        for (e,example) in contents.examples.iter().enumerate() {
            let Ok(rows)=&example.rows else {continue};
            if let Some(stop)=rows.stop.as_ref().filter(|stop|taken(stop)) {return Some(stop.clone());}
            for (a,(_,models)) in rows.at.iter().enumerate() {
                for (m,model) in models.iter().enumerate() {
                    if let RelationValue::Stopped(stop)=model {
                        if taken(stop) {return Some(stop.clone());}
                    }
                    if let Some(crate::extents::EntryExtents::Stopped(stop))=contents.extents.as_ref().and_then(|extents|extents.entry(e,a,m)) {
                        if taken(stop) {return Some(stop.clone());}
                    }
                }
            }
        }
    }
    None
}

/// A stop at the byte bound in `tables`, in rows, projections or extents.
pub fn stopped_at_bytes(tables:&[(usize,Table)])->Option<arclog::eval::Stop> {
    stopped_where(tables,|bound|matches!(bound,arclog::eval::ReachedBound::SessionBytes(_)))
}

/// The text of each top-level form of `text`, a program's S-expression.
fn top_level_forms(text:&str)->Vec<&str> {
    let mut forms=Vec::new();
    let (mut depth,mut start)=(0usize,0usize);
    for (at,byte) in text.bytes().enumerate() {
        match byte {
            b'(' => {
                if depth==0 {start=at;}
                depth+=1;
            }
            b')' => {
                depth=depth.saturating_sub(1);
                if depth==0 {forms.push(&text[start..=at]);}
            }
            _ => {}
        }
    }
    forms
}

/// The top-level form that a written form stands in.
fn top_of(form:&arclog::stream::write::WrittenForm)->usize {
    form.path.0.first().map_or(0,|step|step.0 as usize)
}

pub struct PairEvaluation {
    /// Ephemeral current operation policy, never stored in PairCache.
    pub limits:arclog::eval::Limits,
    /// Full native tables, including preceding relation tables needed to
    /// resolve provenance/frame references. The last two are the complete
    /// body at all assignments, then at gold FITS assignments.
    pub gold: Vec<(usize, Table)>,
    pub mutant: Vec<(usize, Table)>,
    pub report: Value,
    gold_prefix: Vec<u32>,
    mutant_prefix: Vec<u32>,
}

/// One active case's observations. A task never retains a history of gold
/// handles, body tables, decoder states or packed column folds. Only the
/// current body and one rolling dependency prefix can be reused.
pub struct PairCache {
    active: Option<Arc<CheckedProgram>>,
    gold: HashMap<usize,Arc<GoldMemo>>,
    gold_bodies: HashMap<(usize,NodePath),Outcome<ClauseTables>>,
    gold_relations: HashMap<usize,GoldRelationMemo>,
    held: Option<HeldProgram>,
    prefix: Option<PrefixMemo>,
    columns: Option<(Vec<u32>,crate::columns::CaseColumnPrefix)>,
    /// The walks of tables that the programs of the task share. A case's end
    /// does not release them ([`form_memo::FormMemo`]).
    forms: form_memo::FormMemo,
    source: Option<(Arc<CheckedProgram>,Arc<arclog::stream::WrittenStream>)>,
    pub compact: bool,
    cache_bytes: usize,
    active_source:usize,
    gold_body_hits:u64,
    gold_hits:u64,
    prefix_hits:u64,
    sequence:u64,
}
/// What the full evaluation of a program leaves for a later program that
/// shares its first forms ([`form_tables`]). Its tables stand in
/// [`PairCache::gold_relations`], and its results in the session's cache.
struct HeldProgram {
    /// The key of the program in [`PairCache::gold_relations`].
    key:usize,
    checked:Arc<CheckedProgram>,
    /// The text of each top-level form.
    texts:Vec<String>,
    /// For each top-level form, the place of its first table among the
    /// program's tables, and the count of `too_large` that stood before it.
    starts:Vec<(usize,usize)>,
    /// What [`TooLarge`] held at the end of the evaluation.
    too_large:Vec<(Vec<Assignment>,arclog::eval::Stop)>,
}
struct PrefixMemo {
    key:Vec<u32>,
    tables:Vec<(usize,Table)>,
    row_bytes:usize,
}
struct GoldRelationMemo {
    tables:Outcome<Vec<(usize,Table)>>,
    snapshot_ref:String,
}
/// Export-local native identity shared by immutable snapshots and packed views.
pub fn table_transport_ref()->String {
    use std::sync::{OnceLock,atomic::{AtomicU64,Ordering}};
    static START:OnceLock<std::time::SystemTime>=OnceLock::new();
    static NEXT:AtomicU64=AtomicU64::new(0);
    format!("{}:{:?}:{}",std::process::id(),START.get_or_init(std::time::SystemTime::now),NEXT.fetch_add(1,Ordering::Relaxed))
}
impl GoldRelationMemo {
    fn new(tables:Outcome<Vec<(usize,Table)>>)->Self {
        Self {tables,snapshot_ref:table_transport_ref()}
    }
    fn view(&self,cached:bool)->(Value,Vec<(usize,Table)>) {
        let (mut report,tables)=match &self.tables {
            Ok(tables)=>{let mut report=table_status(tables);report["relation_tables"]=json!(tables.len());(report,tables.clone())},
            Err(f)=>(faulted(f),Vec::new()),
        };
        report["cached"]=json!(cached);
        report["tables_ref"]=json!(self.snapshot_ref);
        (report,tables)
    }
}

struct GoldMemo {
    _source:Arc<CheckedProgram>,
    walked:Outcome<Assigned<Value>>,
    records:Vec<Value>,
    sequence:u64,
}
impl GoldMemo {
    /// The same FITS selection for pair execution and standalone observations.
    /// A stopped walk retains its observed prefix; no caller promotes it to full coverage.
    fn kept(&self) -> impl Iterator<Item=(usize, &[Assignment], &Value)> {
        self.walked.iter().flat_map(|walked| walked.at.iter().enumerate())
            .filter(|(_, (_, train))| fits(train))
            .map(|(index, (assigned, train))| (index, assigned.as_slice(), train))
    }

    fn assignments_json(&self) -> Value {
        json!(self.walked.iter().flat_map(|walked| walked.at.iter().enumerate()).map(|(i,(_,train))|
            json!({"assignment":self.records[i],"fits":fits(train),"train":train})).collect::<Vec<_>>())
    }

    fn kept_values(&self) -> (Vec<Vec<Assignment>>, Vec<Value>) {
        self.kept().map(|(index, assigned, _)| (assigned.to_vec(), self.records[index].clone())).unzip()
    }
}

impl Default for PairCache { fn default()->Self {Self::new(false)} }
impl PairCache {
    pub fn new(compact:bool)->Self {Self::with_byte_bound(compact,STUDY_SESSION_BYTES)}
    pub fn with_byte_bound(compact:bool,bytes:usize)->Self {
        Self {active:None,gold:HashMap::new(),gold_bodies:HashMap::new(),gold_relations:HashMap::new(),held:None,prefix:None,columns:None,forms:form_memo::FormMemo::new(bytes/4),source:None,compact,cache_bytes:bytes/2,active_source:0,gold_body_hits:0,gold_hits:0,prefix_hits:0,sequence:0}
    }
    pub fn set_observation_start(&mut self,sequence:u64) {self.sequence=sequence;}
    /// The bytes that the native prefix and the packed prefix may hold: the admission budget less the walks of tables that the form cache holds.
    fn pair_room(&self)->usize {self.cache_bytes.saturating_sub(self.forms.bytes())}
    /// Change the most bytes that the form cache holds, which is a quarter of the session bound by default.
    pub fn set_form_cache_bytes(&mut self,bytes:usize) {self.forms.set_bound(bytes);}
    /// Whether the walks of tables are kept from one program to the next.
    pub fn set_form_cache(&mut self,on:bool) {self.forms.set_on(on);}
    /// Release the kept walks of tables.
    pub fn clear_form_cache(&mut self) {self.forms.clear();}
    /// The work count of the request that the calls after this one belong to
    /// ([`form_memo::FormMemo::set_request_work`]).
    pub fn set_request_work(&mut self,work:Option<TableWork>) {self.forms.set_request_work(work);}
    pub fn form_cache_stats(&self)->Value {
        let stats=self.forms.stats();
        json!({"entries":stats.entries,"bytes":stats.bytes,"bound_bytes":self.forms.bound(),"hits":stats.hits,"kept":stats.kept,"bypassed":stats.bypassed,"skipped":stats.skipped,"cheap":stats.cheap,"overflow":stats.overflow,"declined":stats.declined,"evicted":stats.evicted,"lost":stats.lost,"mismatch":stats.mismatch,"refused":stats.refused,"walk_seconds":stats.walk_seconds,"replay_seconds":stats.replay_seconds,"saved_seconds":stats.saved_seconds,"keep_seconds":stats.keep_seconds})
    }
    /// End a case even when ingestion or a pair faults. Release allocations,
    /// including hash-map capacities, rather than leaving them at task high-water.
    /// Observation sequence numbers remain unique within the evaluator.
    pub fn finish_case(&mut self) {
        self.active=None;
        self.active_source=0;
        self.gold=HashMap::new();
        self.gold_bodies=HashMap::new();
        self.gold_relations=HashMap::new();
        self.held=None;
        self.prefix=None;
        self.columns=None;
        self.source=None;
    }
    pub fn activate(&mut self,gold:&StudyProgram)->bool {
        if self.active.as_ref().is_some_and(|active|Arc::ptr_eq(active,gold.checked())) {return false;}
        self.finish_case();
        self.active_source=Arc::as_ptr(gold.checked()) as usize;
        self.active=Some(Arc::clone(gold.checked()));
        true
    }
    fn remember(&mut self,key:Vec<u32>,tables:Vec<(usize,Table)>) {
        // Replace, never accumulate cumulative prefix tables. Checked IR
        // remains owned by the single active gold case.
        self.prefix=None;
        self.columns=None;
        let mut bytes=key.capacity().saturating_mul(4);
        let mut receipts=HashSet::new();
        for (_,table) in &tables {if let Ok(c)=&table.contents {bytes=bytes.saturating_add(c.assignment_layout.retained_bytes(&mut receipts));}}
        for (_,table) in &tables {if let Ok(c)=&table.contents {for ex in &c.examples {if let Ok(a)=&ex.rows {for (_,models) in &a.at {for model in models {if let RelationValue::Rows(r)=model {
            bytes=bytes.saturating_add(usize::try_from(r.len()).unwrap_or(usize::MAX).saturating_mul(usize::from(r.arity()).saturating_mul(8)+16));
        }}}}}}}
        if bytes<=self.pair_room() {
            self.prefix=Some(PrefixMemo {key,tables,row_bytes:bytes});
        }
    }
    fn assignment_receipt_bytes(&self)->usize {
        let mut seen=HashSet::new();
        let mut bytes=0usize;
        let bodies=self.gold_bodies.values().filter_map(|v|v.as_ref().ok()).map(|v|v.tables.as_slice());
        let relations=self.gold_relations.values().filter_map(|memo|memo.tables.as_ref().ok()).map(Vec::as_slice);
        let prefix=self.prefix.iter().map(|v|v.tables.as_slice());
        for tables in bodies.chain(relations).chain(prefix) {for (_,table) in tables {if let Ok(c)=&table.contents {
            bytes=bytes.saturating_add(c.assignment_layout.retained_bytes(&mut seen));
        }}}
        bytes
    }
    pub fn stats(&self)->Value {json!({"assignment_receipt_bytes_estimate":self.assignment_receipt_bytes(),"gold_hits":self.gold_hits,"gold_body_hits":self.gold_body_hits,"gold_body_entries":self.gold_bodies.len(),"gold_relation_entries":self.gold_relations.len(),"gold_entries":self.gold.len(),"prefix_entries":usize::from(self.prefix.is_some()),"prefix_bytes_estimate":self.prefix.as_ref().map_or(0,|memo|memo.row_bytes),"prefix_hits":self.prefix_hits,"column_prefix_entries":usize::from(self.columns.is_some()),"column_prefix_bytes":self.columns.as_ref().map_or(0,|(_,columns)|columns.retained_bytes()),"cache_byte_bound":self.cache_bytes,"form_cache":self.form_cache_stats()})}
}

fn fault(message: impl Into<Box<str>>, form: &NodePath) -> RunFault {
    RunFault {
        message: message.into(),
        form: form.clone(),
    }
}

/// A complete query over the original checked IR and its native prefix.
#[derive(Clone)]
struct ClauseTables {
    tables: Vec<(usize, Table)>,
    names: Vec<(ProgramRelation, ProgramRelation)>,
    prefix: Vec<u32>,
}

fn source_stream(program:&StudyProgram,decoder:&Decoder<'_>,cache:&PairCache)->Outcome<Arc<arclog::stream::WrittenStream>> {
    match &cache.source {
        Some((checked,written)) if Arc::ptr_eq(checked,program.checked())=>Ok(Arc::clone(written)),
        _=>program.written_stream(decoder.registry(),decoder.settings()).map_err(|d|fault(d.message,&NodePath::default())),
    }
}

/// The tables of `form` of `program`, after the tables `earlier`, with the
/// stops of a table's rows that `skipping` holds where it is given: then a
/// table's rows count under [`TABLE_ROW_WORK`].
fn form_relations(program:&StudyProgram,written:&arclog::stream::WrittenStream,form:&arclog::stream::write::WrittenForm,skipping:Option<&TooLarge>,decoder:&Decoder<'_>,earlier:&[&Table],mut memo:Option<(&mut form_memo::FormMemo,&form_memo::TopHashes<'_>)>)->Outcome<Vec<(usize,Table)>> {
    let checked=program.checked();
    let mut held:Vec<(usize,Table)>=Vec::new();
    let mut outputs:Vec<String>=Vec::new();
    for slot in materialized_slots(program.program().value(),written,form) {
        let declared=&written.relations[slot];
        let relation=graph_relation(checked,decoder.registry(),&form.path,declared).ok_or_else(||fault("the graph holds no node for a relation the form declares",&form.path))?;
        let dets=relation_dets(checked,relation.node);
        let work=if skipping.is_some() {TableWork::counted_as(TABLE_ROW_WORK,arclog::eval::Gauge::StudyRowWork,&decoder.request_work())} else {decoder.query_work()};
        let output=output_name(program.program().value(),&form.path,declared);
        let ordinal=outputs.iter().filter(|seen|**seen==output).count();
        outputs.push(output.clone());
        let examples=match (skipping,memo.as_mut()) {
            (Some(too_large),Some((memo,tops)))=>{
                let probe=form_memo::Probe {checked,tops:*tops,form:&form.path,output:&output,ordinal,dets:&dets};
                let (_,session,_)=decoder.evaluation_inputs();
                memo.examples(&probe,session,too_large,&work,||relation_examples_skipping(decoder,checked,&relation,&dets,&work,too_large))
            }
            (Some(too_large),None)=>relation_examples_skipping(decoder,checked,&relation,&dets,&work,too_large),
            (None,_)=>relation_examples(decoder,checked,&relation,&dets,&work),
        };
        let contents=contents(decoder,checked,&form.path,&relation,slot as u32,&dets,examples).map(|c| {
            let c=Contents {name:relation_spelled(declared),output_name:output,keys:checked.program.column_keys(relation.node),..c};
            let seen=earlier.iter().copied().chain(held.iter().map(|(_,t)|t)).collect::<Vec<_>>();
            made(decoder,&seen,checked,&relation,c)
        });
        held.push((form.tokens.end.saturating_sub(1),Table {form:form.path.clone(),point:Point::Relation,contents}));
    }
    Ok(held)
}

/// Evaluate export relation declarations against their original checked
/// graph. Prefixes are scoped to the certified gold handle, so source names
/// and AST paths are never confused across equal-looking token streams.
fn original_relations(program:&StudyProgram,written:&arclog::stream::WrittenStream,until:Option<&NodePath>,decoder:&Decoder<'_>,cache:&mut PairCache)->Outcome<(Vec<(usize,Table)>,Vec<u32>)> {
    let checked=program.checked();
    let end=until.and_then(|until|written.forms.iter().position(|form|&form.path==until)).unwrap_or(written.forms.len());
    let forms=&written.forms[..end];
    // One cumulative prefix replaces the former map of cloned table vectors.
    // Find its exact source boundary before evaluating any preceding form.
    let mut tables=Vec::new();let mut start=0;
    let source=[cache.active_source as u32,(cache.active_source>>32) as u32];
    let mut paths=Vec::new();
    for (index,form) in forms.iter().enumerate() {
        paths.push(form.path.0.len() as u32);
        paths.extend(form.path.0.iter().map(|s|s.0));
        if let Some(prefix)=&cache.prefix {
            let header=source.len()+paths.len()+1;
            // Key lengths strictly increase at form boundaries. Only the
            // possible matching boundary reads any vocabulary IDs; every
            // other boundary needs no cumulative token vector at all.
            if prefix.key.len()==header+form.tokens.end
                && source.iter().chain(&paths).copied().chain([u32::MAX]).eq(prefix.key[..header].iter().copied())
                && written.tokens[..form.tokens.end].iter().zip(&prefix.key[header..]).all(|((token,_),id)|decoder.vocabulary().id(token)==Some(*id))
            {
                tables=prefix.tables.clone();start=index+1;cache.prefix_hits+=1;
            }
        }
    }
    let too_large=TooLarge::default();
    let source_text=until.is_none().then(||program.sexp(decoder.registry()));
    let hashes=form_memo::TopHashes::new(checked,source_text.as_deref().map(top_level_forms));
    let (_,session,_)=decoder.evaluation_inputs();
    let mut starts=Vec::new();
    for form in forms.iter().skip(start) {
        let top=top_of(form);
        if starts.len()<=top {
            starts.resize(top+1,(tables.len(),too_large.0.borrow().len()));
            session.results.mark(top as u32);
        }
        let seen=tables.iter().map(|(_,t)|t).collect::<Vec<_>>();
        let held=form_relations(program,written,form,until.is_none().then_some(&too_large),decoder,&seen,until.is_none().then(||(&mut cache.forms,&hashes)))?;
        tables.extend(held);
    }
    if until.is_none() && start==0 {
        let source=source_text.unwrap_or_default();
        cache.held=Some(HeldProgram {
            key:Arc::as_ptr(checked) as usize,
            checked:Arc::clone(checked),
            texts:top_level_forms(&source).into_iter().map(str::to_owned).collect(),
            starts,
            too_large:too_large.0.into_inner(),
        });
    }
    let last=match forms.last() {
        None=>Vec::new(),
        Some(form)=>source.into_iter().chain(paths).chain([u32::MAX])
            .chain(written.tokens[..form.tokens.end].iter().map(|(token,_)|decoder.vocabulary().id(token).expect("a written vocabulary token"))).collect(),
    };
    if until.is_some() && !last.is_empty() && !cache.prefix.as_ref().is_some_and(|memo|memo.key==last) {
        cache.remember(last.clone(),tables.clone());
    }
    Ok((tables,last))
}

fn clause_tables(program:&StudyProgram,origin:&Arc<CheckedProgram>,body:&NodePath,decoder:&mut Decoder<'_>,fixed:&[Vec<Assignment>],cache:&mut PairCache)->Outcome<ClauseTables> {
    let view=arclog::eval::body_view::BodyView::at(program.checked(),body)?;
    let written=source_stream(program,decoder,cache)?;
    let (mut tables,prefix)=original_relations(program,&written,Some(&view.form),decoder,cache)?;
    let dets=super::body_tables::dets(program.checked(),&view);
    let work=decoder.query_work();
    let examples=super::body_tables::examples(decoder,program.checked(),&view,&dets,&work);
    let seen=tables.iter().map(|(_,t)|t).collect::<Vec<_>>();
    let slot=written.relations.len() as u32;
    let point=Point::Body {conjuncts:view.clause.nodes.len() as u32,sites:0};
    let index=written.forms.iter().find(|f|f.path==view.form).ok_or_else(||fault("body owner is absent from the written stream",body))?.tokens.end.saturating_sub(1);
    let held=super::body_tables::contents(decoder,program.checked(),&view,slot,&dets,examples,&seen)?;
    tables.push((index,Table {form:view.form.clone(),point,contents:Ok(held)}));
    let completed=&tables.last().expect("the all-assignment body table just inserted").1.contents.as_ref().expect("body contents was checked").examples;
    let seen=tables[..tables.len()-1].iter().map(|(_,t)|t).collect::<Vec<_>>();
    let held=held_body_contents(program,origin,&view,slot,&dets,decoder,fixed,&seen,Some(completed))?;
    tables.push((index,Table {form:view.form,point,contents:Ok(held)}));
    Ok(ClauseTables {tables,names:written.relations.iter().map(|n|(n.clone(),n.clone())).collect(),prefix})
}

/// The original checked BODY query at full gold interventions. Both pair and
/// gold-only acquisition use this boundary, including recursive owner context.
fn held_body_contents(program:&StudyProgram,origin:&Arc<CheckedProgram>,view:&arclog::eval::body_view::BodyView,
    slot:u32,dets:&[Det],decoder:&Decoder<'_>,fixed:&[Vec<Assignment>],earlier:&[&Table],completed:Option<&[ExampleRows]>)->Outcome<Contents> {
    let work=decoder.query_work();
    let limits=decoder.limits().counted_in(work.clone());
    let receipt=HeldAssignments::new(Arc::clone(program.checked()),Arc::clone(origin),fixed)?;
    let context=AssignmentContext::Held {receipt:&receipt,limits:&limits,work:&work};
    let examples=super::body_tables::examples_reusing(decoder,program.checked(),view,dets,&work,context,completed);
    super::body_tables::contents_with_context(decoder,program.checked(),view,slot,dets,examples,earlier,context)
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

/// Row status with annotation diagnostics. Projection stops and extent stops
/// at an observation or evaluation bound leave row status intact; they are
/// listed in `projection_stops` and `extent_stops`. Extent loss is a fault,
/// and machine-dependent extent stops stop the table.
fn table_status(tables: &[(usize, Table)]) -> Value {
    let mut status = rows_status(tables);
    let projection_stops: Vec<Value> = tables.iter().filter_map(|(_, table)| match &table.contents {
        Ok(Contents { projections: Some(Projections::Stopped(stop)), .. }) =>
            Some(json!({"table_form":format!("{:?}",table.form), "reason":format!("{:?}",stop.bound), "form":format!("{:?}",stop.form)})),
        _ => None,
    }).collect();
    status["projection_stops"] = json!(projection_stops);
    let mut extent_stops = Vec::new();
    for (_, table) in tables {
        if let Ok(c) = &table.contents {
            if let Some(extents) = &c.extents {
                for (e, example) in c.examples.iter().enumerate() {
                    if let Ok(rows) = &example.rows {
                        for (a, (_, models)) in rows.at.iter().enumerate() {
                            for m in 0..models.len() {
                                if let Some(crate::extents::EntryExtents::Stopped(stop)) = extents.entry(e,a,m) {
                                    extent_stops.push(json!({"table_form":format!("{:?}",table.form),"example":e,"assignment":a,"model":m,"reason":format!("{:?}",stop.bound),"form":format!("{:?}",stop.form)}));
                                }
                            }
                        }
                    }
                }
            }
        }
    }
    status["extent_stops"] = json!(extent_stops);
    status
}

fn rows_status(tables: &[(usize, Table)]) -> Value {
    for (_, table) in tables {
        let c = match &table.contents {
            Ok(c) => c,
            Err(f) => return faulted(f),
        };
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
            // Only an annotation budget or evaluation stop leaves rows intact.
            for (e, example) in c.examples.iter().enumerate() {
                if let Ok(rows) = &example.rows {
                    for (a, (_, models)) in rows.at.iter().enumerate() {
                        for m in 0..models.len() {
                            match extents.entry(e, a, m) {
                                Some(crate::extents::EntryExtents::Stopped(stop)) if !stop.bound.is_annotation() => {
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
                    && arclog::session::same_rows(rows,value)
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

/// Undefined is a native semantic value (for example, a construction outside
/// its input domain), not an evaluator fault and not an empty row set.
fn undefined_comparison(gold: Option<&RelationValue>, mutant: Option<&RelationValue>) -> Value {
    let kind = |value: Option<&RelationValue>| match value {
        None => "absent_assignment",
        Some(RelationValue::Undefined) => "undefined",
        Some(RelationValue::Rows(_)) => "rows",
        Some(RelationValue::Stopped(_)) => "stopped",
    };
    let count = |value: Option<&RelationValue>| match value {
        Some(RelationValue::Rows(rows)) => Some(rows.len()),
        _ => None,
    };
    json!({"status":"complete","comparable":false,"comparison":"undefined",
        "gold_value":kind(gold),"mutant_value":kind(mutant),
        "gold_rows":count(gold),"mutant_rows":count(mutant),
        "relation":null,"kept":null,"extra":null,"missing":null,
        "reason":"row comparison is undefined because a native table value is undefined"})
}

fn absent_assignment(value: &RelationValue, gold_only: bool) -> Value {
    match value {
        RelationValue::Rows(rows) => {
            json!({"status":"complete","comparable":true,"relation":if rows.is_empty() {"equal"} else if gold_only {"subset"} else {"superset"},"kept":0,"extra":if gold_only {0} else {rows.len()},"missing":if gold_only {rows.len()} else {0},"assignment_presence":if gold_only {"gold_only"} else {"mutant_only"}})
        }
        RelationValue::Stopped(stop) => stopped(stop),
        RelationValue::Undefined => {
            let mut row = if gold_only {undefined_comparison(Some(value),None)} else {undefined_comparison(None,Some(value))};
            row["assignment_presence"] = json!(if gold_only {"gold_only"} else {"mutant_only"});
            row
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
    // Compare on the union of native example domains. A task-wide body is
    // constant on every example; broadcast it explicitly when a mutation
    // changes the owner's scope. Native tables retain their actual scope.
    let mut examples=g.examples.iter().chain(m.examples.iter()).filter_map(|e|e.example).collect::<Vec<_>>();
    examples.sort_by_key(|e|e.index());examples.dedup();
    let examples=if examples.is_empty() {vec![None]} else {examples.into_iter().map(Some).collect()};
    let mut out = Vec::new();
    for example in examples {
        let find=|rows:&[ExampleRows]|rows.iter().position(|e|e.example==example).or_else(||rows.iter().position(|e|e.example.is_none()));
        let (Some(gi),Some(mi))=(find(&g.examples),find(&m.examples)) else {
            out.push(json!({"example":example.map(|e|e.index()),"status":"fault","reason":"native comparison domain is missing an example"}));continue;
        };
        let (ex,other)=(&g.examples[gi],&m.examples[mi]);
        let scope_alignment=if ex.example!=other.example {"broadcast_task_wide"} else {"same"};
        let first=out.len();
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
                    row["example"] = json!(example.map(|e| e.index()));
                    row["assignment"] = json!(a);
                    row["model"] = json!(model);
                    row["gold_model"] = json!(model);
                    row["mutant_model"] = Value::Null;
                    row["model_alignment"] = json!("absent_assignment");
                    row["scope_alignment"] = json!(scope_alignment);
                    out.push(row);
                }
                continue;
            };
            // Enumeration indices belong to one program, not to a shared
            // model identity. A mutation may add/remove pick dependencies or
            // change their alternatives. Compare the full Cartesian family.
            for (gold_model, gv) in models.iter().enumerate() {
              for (mutant_model, mv) in others.iter().enumerate() {
                let mut row = json!({"example":example.map(|e|e.index()),"assignment":a,
                    "model":gold_model,"gold_model":gold_model,"mutant_model":mutant_model,
                    "model_alignment":"cartesian","scope_alignment":scope_alignment});
                // Count alternatives as work even when both are empty or
                // undefined. A product cannot bypass the comparison work cap.
                if let Err(bound) = work.charge(1) {
                    row["status"] = json!("stopped");
                    row["reason"] = json!(format!("{bound:?}"));
                    out.push(row);
                    return json!(out);
                }
                match (gv, mv) {
                    (RelationValue::Rows(g), RelationValue::Rows(m)) => {
                        if let Err(bound) = work.charge(g.len().saturating_add(m.len())) {
                            row["status"] = json!("stopped");
                            row["reason"] = json!(format!("{bound:?}"));
                            out.push(row);
                            return json!(out);
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
                        row["comparable"] = json!(true);
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
                        let value = undefined_comparison(Some(gv),Some(mv));
                        row.as_object_mut().unwrap().extend(value.as_object().unwrap().clone());
                    }
                }
                out.push(row);
              }
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
                    row["example"] = json!(example.map(|e| e.index()));
                    row["mutant_assignment"] = json!(a);
                    row["model"] = json!(model);
                    row["gold_model"] = Value::Null;
                    row["mutant_model"] = json!(model);
                    row["model_alignment"] = json!("absent_assignment");
                    row["scope_alignment"] = json!(scope_alignment);
                    out.push(row);
                }
            }
        }
        for row in &mut out[first..] {row["scope_alignment"]=json!(scope_alignment);}
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

fn train(e: &Evaluation<'_>, output: &GraphRelation, judge: &judgement::TrainJudge<'_>) -> Result<Value, End> {
    let mut out = Vec::new();
    for ((example, pair), candidates) in e.task.examples().zip(e.task.train.iter()).zip(&judge.pairs) {
        let mut models = Vec::new();
        let mut observed = judgement::ModelSet::default();
        let mut model_stop = None;
        let end=e.models(output,Some(example),&mut |value| {
            models.push(match value {
                RelationValue::Stopped(stop)=>{model_stop=Some(stop.clone());stopped(stop)},
                RelationValue::Undefined=>{observed.observe(None);json!({"status":"complete","equals":false,"differing_cells":pair.output.rows().iter().map(|r|r.len()).sum::<usize>(),"grid_defined":false,"reason":"undefined OUT"})},
                RelationValue::Rows(rows)=>match read_grid(rows,GridColumns::OUT) {
                    Some(grid)=>{
                        let detail=json!({"status":"complete","equals":grid==pair.output,"differing_cells":differences(&grid,&pair.output)});
                        observed.observe(Some(grid));detail
                    },
                    None=>{observed.observe(None);json!({"status":"complete","equals":false,"differing_cells":invalid_differences(rows,&pair.output),"grid_defined":false,"reason":"OUT rows do not define a grid"})},
                }
            }); ControlFlow::Continue(())
        }).map_err(End::Fault)?;
        if let ModelsEnd::Stopped(stop) = end {
            return Err(End::Stop(stop));
        }
        if let Some(stop) = model_stop {
            return Err(End::Stop(stop));
        }
        let mut comparison=observed.finish(candidates);
        comparison["example"]=json!(example.index());
        comparison["models"]=json!(models);
        out.push(comparison);
    }
    Ok(json!(out))
}
fn fits(train: &Value) -> bool {
    train.as_array().is_some_and(|pairs| {
        !pairs.is_empty()
            && pairs.iter().all(|p| p["fits"] == true)
    })
}

/// Acquire the native gold walk once in this active case's session. Walk all
/// assignable DETs, including those OUT does not read; OUT alone decides FITS.
fn gold_observation(gold:&StudyProgram,output:&GraphRelation,judge:&judgement::TrainJudge<'_>,
    decoder:&Decoder<'_>,work:&TableWork,cache:&mut PairCache)->Outcome<(Arc<GoldMemo>,bool)> {
    let written=source_stream(gold,decoder,cache)?;
    cache.source=Some((Arc::clone(gold.checked()),written));
    let gold_key=Arc::as_ptr(gold.checked()) as usize;
    let gold_hit=cache.gold.contains_key(&gold_key);
    let memo=if gold_hit {cache.gold_hits+=1;Arc::clone(&cache.gold[&gold_key])} else {
        let dets=arclog::decode::held_dets(gold.checked());
        let walked=decoder.assigned(gold.checked(),output.node,&dets,Some(&work),&mut |e|train(e,&output,&judge));
        let records=walked.as_ref().map(|w|w.at.iter().map(|(a,_)|assignment_json(a)).collect()).unwrap_or_default();
        cache.sequence+=1;
        let memo=Arc::new(GoldMemo {_source:Arc::clone(gold.checked()),walked,records,sequence:cache.sequence});
        cache.gold.insert(gold_key,Arc::clone(&memo));memo
    };
    Ok((memo,gold_hit))
}

/// Gold-only TRAIN FITS observation in the evaluator's existing session.
/// No mutant is constructed, no caller assignment is accepted, and no relation
/// tables or test-output verdict are acquired. Kept JSON always uses the pair
/// report's original assignment_json encoding, including on compact cache hits.
pub fn gold_kept_cached(gold:&StudyProgram,task:&Task,judged:&JudgedTask,session:&TaskSession,
    constructions:&Constructions,settings:&DecodeSettings,cache:&mut PairCache)->Value {
    cache.activate(gold);
    let limits=settings.operation_limits();
    let decoder=Decoder::new(task,session,Registry::get(),constructions,settings).with_operation_limits(limits);
    let mut report=gold_observation_report(gold,session,settings);
    if report["program_provenance"]["stream"].is_null() {return report;}
    let judge=match judgement::TrainJudge::new(task,judged) {
        Ok(judge)=>judge,
        Err(reason)=>{report["reason"]=json!(reason);return report;}
    };
    let Some(output)=output_relation(gold.checked()) else {
        report["reason"]=json!("gold has no OUT");return report;
    };
    let work=decoder.query_work();
    let (memo,hit)=match gold_observation(gold,&output,&judge,&decoder,&work,cache) {
        Ok(observation)=>observation,
        Err(fault)=>{report["reason"]=json!(fault.message);return report;}
    };
    describe_gold_observation(&mut report,gold,&memo,hit);
    report
}

/// Shared provenance and observation serialization for gold-only queries.
fn gold_observation_report(gold:&StudyProgram,session:&TaskSession,settings:&DecodeSettings)->Value {
    let mut report=json!({"schema":"arclog-study-gold-kept-v1","status":"fault","reason":null,
        "gold_observation_ref":null,"gold_observation_cached":false,"gold_observation_stop":null,
        "observation_complete":false,"gold_assignments":[],"kept_assignments":[],
        "kept_assignment_count":0,"gold_fits":null,"assignment_coverage_complete":false,
        "kept_assignment_missing_dets":[],"held_det_relations":[],
        "fits_contract":"native closed-world TRAIN candidate-set comparison; no TEST Fit verdict",
        "settings":{"deadline_seconds":settings.deadline.map(|d|d.as_secs_f64()),
            "table_work_cap":settings.table_work_cap,"projection_cap":settings.projection_cap,
            "rule_tests":settings.rule_tests,"check_copies":settings.check_copies,
            "vocabulary":{"relations":settings.vocabulary.relations,"columns":settings.vocabulary.columns,"labels":settings.vocabulary.labels},
            "caps":{"bindings":session.caps.bindings,"rows":session.caps.rows,"models":session.caps.models,
                "nodes":session.caps.nodes,"assignments":session.caps.assignments},"session_bytes":session.bound.bytes},
        "program_provenance":{"program_sexp":gold.sexp(Registry::get()),"stream":null},
        "assignment_contract":"kept_assignments are ordered native full-program DET choices; raw rows and relation names use the existing pair encoding; Undefined DETs may have no assigned value and are listed separately",
        "bound_scope":"one operation request work cap; per-evaluation binding and row caps for the native gold walk; cached observations retain their original completion/stop"});
    let stream=match gold.decode_stream(Registry::get(),settings) {
        Ok(stream)=>stream,
        Err(reason)=>{report["reason"]=json!(reason);return report;}
    };
    report["program_provenance"]["stream"]=json!({"ids":stream.ids,"model":stream.model,
        "paths":stream.paths.iter().map(arclog::mutation::path_json).collect::<Vec<_>>()});
    report
}

fn describe_gold_observation(report:&mut Value,gold:&StudyProgram,memo:&GoldMemo,hit:bool) {
    report["gold_observation_ref"]=json!(memo.sequence);
    report["gold_observation_cached"]=json!(hit);
    match &memo.walked {
        Err(f)=>{report["reason"]=json!(f.message);report["form"]=json!(format!("{:?}",f.form));}
        Ok(walked)=>{
            report["status"]=json!(if walked.stop.is_some(){"stopped"}else{"complete"});
            report["observation_complete"]=json!(walked.stop.is_none());
            if let Some(stop)=&walked.stop {
                let detail=stopped(stop);
                report["reason"]=detail["reason"].clone();
                report["gold_observation_stop"]=detail;
            }
            report["gold_assignments"]=memo.assignments_json();
            let records=memo.kept().map(|(i,_,_)|memo.records[i].clone()).collect::<Vec<_>>();
            report["kept_assignment_count"]=json!(records.len());
            report["gold_fits"]=if !records.is_empty(){json!(true)}else if walked.stop.is_none(){json!(false)}else{Value::Null};
            report["kept_assignments"]=json!(records);
            let dets=arclog::decode::held_dets(gold.checked());
            report["held_det_relations"]=json!(dets.iter().map(|d|relation_spelled(&d.relation)).collect::<Vec<_>>());
            let missing=memo.kept().map(|(_,values,_)|dets.iter().filter(|d|
                !values.iter().any(|(name,_)|*name==d.relation))
                .map(|d|relation_spelled(&d.relation)).collect::<Vec<_>>()).collect::<Vec<_>>();
            report["assignment_coverage_complete"]=json!(missing.iter().all(Vec::is_empty));
            report["kept_assignment_missing_dets"]=json!(missing);
        }
    }
}

/// Evaluate all gold OUT assignments, retain every FITS assignment, and
/// evaluate the complete mutant at precisely those native parameter values.
/// Independent pairs can run concurrently (no GIL in the binding).
fn evaluate_pair_inner(
    gold: &StudyProgram,
    point: &MutationPoint,
    mutant: &ValidMutant,
    task: &Task,
    judged: &JudgedTask,
    session: &TaskSession,
    constructions: &Constructions,
    settings: &DecodeSettings,
    cache:&mut PairCache,
    limits:&arclog::eval::Limits,
) -> PairEvaluation {
    let mut result = PairEvaluation {
        limits:limits.clone(),
        gold: Vec::new(),
        mutant: Vec::new(),
        gold_prefix:Vec::new(),
        mutant_prefix:Vec::new(),
        report: json!({"status":"complete","kept_assignments":[],"outputs":[],"comparisons":[]}),
    };
    let judge=match judgement::TrainJudge::new(task,judged) {
        Ok(judge)=>judge,
        Err(message)=>{result.report=faulted(&fault(message,&point.body));return result;}
    };
    result.report["fits_contract"]=json!("native closed-world candidate-set comparison; per-model equals/differing_cells compare the given output only");
    if !Arc::ptr_eq(gold.checked(), mutant.gold())
        || point.body != mutant.point().body
        || point.clause != mutant.point().clause
    {
        result.report = json!({"status":"fault","reason":"gold, point and mutant do not belong to the same certified pair"});
        return result;
    }
    if let Err(error) = gold.checked().check_held_det_interfaces(mutant.program().checked()) {
        result.report = faulted(&error.into());
        result.report["fault_kind"] = json!("mutator_held_det_interface");
        return result;
    }
    cache.activate(gold);
    let mut gd = Decoder::new(task, session, Registry::get(), constructions, settings).with_operation_limits(limits.clone());
    let mut md = Decoder::new(task, session, Registry::get(), constructions, settings).with_operation_limits(limits.clone());
    let Some(output) = output_relation(gold.checked()) else {
        result.report = faulted(&fault("gold has no OUT", &point.clause));
        return result;
    };
    let Some(mutant_output) = output_relation(mutant.program().checked()) else {
        result.report = faulted(&fault("mutant has no OUT", &point.clause));
        return result;
    };
    let work = gd.query_work();
    // An unused gold clause can read a DET that OUT does not reach. Walk
    // the program's DETs so its FITS records still assign that clause's
    // parameters explicitly; OUT remains the sole FITS criterion.
    let gold_started=Instant::now();
    let gold_key=Arc::as_ptr(gold.checked()) as usize;
    cache.active_source=gold_key;
    let (memo,gold_hit)=match gold_observation(gold,&output,&judge,&gd,&work,cache) {
        Ok(observation)=>observation,
        Err(error)=>{result.report=faulted(&fault(error.message,&point.body));return result;}
    };
    let gold_seconds=gold_started.elapsed().as_secs_f64();
    let include_gold=!cache.compact || !gold_hit;
    result.report["gold_observation_ref"]=json!(memo.sequence);
    result.report["gold_observation_cached"]=json!(gold_hit);
    let mut mutant_out_seconds=0.;
    let mut fixed = Vec::new();
    let mut gold_assignments = json!([]);
    match &memo.walked {
        Err(f) => {
            result.report["status"] = json!("fault");
            result.report["reason"] = json!(f.message);
        }
        Ok(walked) => {
            let mut kept = Vec::new();
            let mut outputs = Vec::new();
            if include_gold {
                gold_assignments=memo.assignments_json();
            }
            for (assignment_index,assigned,gold_train) in memo.kept() {
                let index = fixed.len();
                if include_gold {kept.push(memo.records[assignment_index].clone());}
                fixed.push(assigned.to_vec());
                let parameters = ParameterValues::determined(assigned.to_vec());
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
                let mutant_train = match train(&evaluation, &mutant_output, &judge) {
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
    if include_gold {result.report["gold_assignments"] = gold_assignments;} else {result.report.as_object_mut().unwrap().remove("kept_assignments");}
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
        None=>{cache.gold_bodies=HashMap::new();let held=clause_tables(gold,gold.checked(),&point.body,&mut gd,&fixed,cache);cache.gold_bodies.insert(body_key,held.clone());held}
    };
    match gold_body {
        Ok(t) => {
            result.gold_prefix=t.prefix;
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
    match clause_tables(mutant.program(), gold.checked(), &point.body, &mut md, &fixed, cache) {
        Ok(t) => {
            result.mutant_prefix=t.prefix;
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
    result.report["table_indices"] = json!({"gold_all":g,"gold_kept":g+1,"mutant_all":m,"mutant_kept":m+1,"note":"indices include the two evidence tables; each kept assignment can have multiple native models per example; use the kept assignment maps"});
    result.report["gold_kept_assignment_map"] = component_tables::assignment_map(&result.gold[g-1..],g+1,task.train.len());
    result.report["mutant_kept_assignment_map"] = component_tables::assignment_map(&result.mutant[m-1..],m+1,task.train.len());
    let comparison_work = TableWork::counted_as(settings.table_work_cap, arclog::eval::Gauge::PairComparisons, &limits.request);
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
    judged: &JudgedTask,
    session: &TaskSession,
    constructions: &Constructions,
    settings: &DecodeSettings,
) -> PairEvaluation {
    evaluate_pair_cached(gold,point,mutant,task,judged,session,constructions,settings,&mut PairCache::default())
}

pub fn evaluate_pair_cached(gold:&StudyProgram,point:&MutationPoint,mutant:&ValidMutant,task:&Task,judged:&JudgedTask,session:&TaskSession,constructions:&Constructions,settings:&DecodeSettings,cache:&mut PairCache)->PairEvaluation {
    let limits=settings.operation_limits();
    std::panic::catch_unwind(std::panic::AssertUnwindSafe(||evaluate_pair_inner(gold,point,mutant,task,judged,session,constructions,settings,cache,&limits)))
        .unwrap_or_else(|payload|PairEvaluation {limits:limits.clone(),gold:Vec::new(),mutant:Vec::new(),gold_prefix:Vec::new(),mutant_prefix:Vec::new(),report:json!({"status":"fault","reason":format!("pair evaluation panicked: {}",arclog::decode::corpus::replay_panic(&*payload))})})
}

/// Full native relation tables, evaluated once per gold handle in this task
/// session. Faults and work-cap stops are cached as observations too.
pub fn gold_tables_cached(gold:&StudyProgram,task:&Task,session:&TaskSession,constructions:&Constructions,settings:&DecodeSettings,cache:&mut PairCache)->(Value,Vec<(usize,Table)>) {
    let limits=table_limits(settings);
    gold_tables_cached_in(gold,task,session,constructions,settings,cache,&limits)
}

/// Full-table evaluation and packing share the caller's limits ([`table_limits`]).
pub fn gold_tables_cached_in(gold:&StudyProgram,task:&Task,session:&TaskSession,constructions:&Constructions,settings:&DecodeSettings,cache:&mut PairCache,limits:&arclog::eval::Limits)->(Value,Vec<(usize,Table)>) {
    cache.activate(gold);
    let key=Arc::as_ptr(gold.checked()) as usize;
    let hit=cache.gold_relations.contains_key(&key);
    if !hit {
        let held=std::panic::catch_unwind(std::panic::AssertUnwindSafe(|| {
            let decoder=Decoder::new(task,session,Registry::get(),constructions,settings).with_operation_limits(limits.clone());
            let written=source_stream(gold,&decoder,cache)?;
            original_relations(gold,&written,None,&decoder,cache).map(|(tables,_)|tables)
        })).unwrap_or_else(|payload|Err(fault(format!("gold relation evaluation panicked: {}",arclog::decode::corpus::replay_panic(&*payload)),&NodePath::default())));
        cache.gold_relations.insert(key,GoldRelationMemo::new(held));
    }
    cache.gold_relations[&key].view(hit)
}

/// The tables of the top-level form `form` of `program`, with the rows and
/// the stops that a full evaluation of `program` gives them.
///
/// Where the evaluator holds the full evaluation of a program that opens with
/// the same forms ([`HeldProgram`]), those forms are not evaluated again: no
/// form among them reads a later form, so their tables and the size stops they
/// found are the same here. The forms from the first that differs through
/// `form` see the session's result cache as the evaluation of the earlier forms
/// left it ([`arclog::session::ResultCache::begin_view`]). A count of work
/// depends on what the cache holds, and an entry that an eviction dropped costs
/// its work again, so the count here is no less than a full evaluation's while
/// the cache evicts nothing. So the result stands where the cache evicts
/// nothing and no table stops at a cap of work or at the byte bound. Otherwise
/// the forms through `form` are evaluated in a session of their own, from the
/// first form.
pub fn form_tables(program:&StudyProgram,form:usize,task:&Task,session:&TaskSession,constructions:&Constructions,settings:&DecodeSettings,cache:&PairCache,limits:&arclog::eval::Limits)->(Value,Vec<(usize,Table)>) {
    let registry=Registry::get();
    let of_form=|tables:Vec<(usize,Table)>|tables.into_iter().filter(|(_,table)|table.form.0.first().is_some_and(|step|step.0 as usize==form)).collect::<Vec<_>>();
    let finish=|tables:Outcome<Vec<(usize,Table)>>,kind:&str,evaluated:usize| {
        let (mut report,tables)=match tables {
            Ok(tables)=>{let mut report=table_status(&tables);report["relation_tables"]=json!(tables.len());(report,tables)},
            Err(f)=>(faulted(&f),Vec::new()),
        };
        report["form_tables"]=json!({"form":form,"kind":kind,"forms_evaluated":evaluated});
        (report,tables)
    };
    let held=cache.held.as_ref().and_then(|held| {
        let source=program.sexp(registry);
        let texts=top_level_forms(&source);
        if texts.len()!=program.program().value().forms.len() {return None;}
        let same=texts.iter().zip(&held.texts).take_while(|(a,b)|**a==b.as_str()).count();
        let tables=cache.gold_relations.get(&held.key)?.tables.as_ref().ok()?;
        (same>0 && same<=held.starts.len() && !held.checked.program.reads_from(same) && !program.checked().program.reads_from(same)).then_some((held,tables,same))
    });
    let held=held.filter(|(held,_,same)|if *same>form {form<held.starts.len()} else {*same<held.starts.len()});
    let written=match program.written_stream(registry,settings) {
        Ok(written)=>written,
        Err(d)=>return finish(Err(fault(d.message,&NodePath::default())),"fault",0),
    };
    if let Some((held,tables,same))=held {
        if same>form {
            let (start,end)=(held.starts[form].0,held.starts.get(form+1).map_or(tables.len(),|at|at.0));
            return finish(Ok(tables[start..end].to_vec()),"held",0);
        }
        let (start,stops)=held.starts[same];
        let earlier=tables[..start].iter().map(|(_,table)|table).collect::<Vec<_>>();
        let too_large=TooLarge(std::cell::RefCell::new(held.too_large[..stops].to_vec()));
        let decoder=Decoder::new(task,session,registry,constructions,settings).with_operation_limits(limits.clone());
        let evictions=session.results.evictions();
        session.results.begin_view(same as u32);
        let mut made:Vec<(usize,Table)>=Vec::new();
        let mut result:Outcome<()>=Ok(());
        for written_form in written.forms.iter().filter(|written_form|(same..=form).contains(&top_of(written_form))) {
            let seen=earlier.iter().copied().chain(made.iter().map(|(_,table)|table)).collect::<Vec<_>>();
            match form_relations(program,&written,written_form,Some(&too_large),&decoder,&seen,None) {
                Ok(tables)=>made.extend(tables),
                Err(fault)=>{result=Err(fault);break},
            }
        }
        session.results.end_view();
        let near_a_cap=stopped_where(&made,|bound|matches!(bound,arclog::eval::ReachedBound::TableWork {..}|arclog::eval::ReachedBound::SessionBytes(_))).is_some();
        if result.is_ok() && !near_a_cap && session.results.evictions()==evictions {
            return finish(Ok(of_form(made)),"reused",form+1-same);
        }
        if let Err(fault)=result {
            if session.results.evictions()==evictions {return finish(Err(fault),"reused",form+1-same);}
        }
    }
    let own=session.sharing_terms();
    let decoder=Decoder::new(task,&own,registry,constructions,settings).with_operation_limits(limits.clone());
    let too_large=TooLarge::default();
    let mut made:Vec<(usize,Table)>=Vec::new();
    for written_form in written.forms.iter().filter(|written_form|top_of(written_form)<=form) {
        let seen=made.iter().map(|(_,table)|table).collect::<Vec<_>>();
        match form_relations(program,&written,written_form,Some(&too_large),&decoder,&seen,None) {
            Ok(tables)=>made.extend(tables),
            Err(fault)=>return finish(Err(fault),"full",form+1),
        }
    }
    finish(Ok(of_form(made)),"full",form+1)
}

/// Pack the shared relation prefix once, preserving every exported offset
/// and run-interning decision. Only the two body tables are appended per side.
pub fn pair_columns_cached(materializer:&arclog::eval::join::Materializer<'_>,evidence:&[Table],result:&PairEvaluation,train:usize,cache:&mut PairCache)->(crate::columns::CaseColumns,crate::columns::CaseColumns) {
    (pair_side_columns_cached(materializer,evidence,result,true,train,cache),
     pair_side_columns_cached(materializer,evidence,result,false,train,cache))
}

/// One side of the same cached fold, allowing a caller to finish conversion
/// and release that phase's scratch before constructing the other side.
pub fn pair_side_columns_cached(materializer:&arclog::eval::join::Materializer<'_>,evidence:&[Table],result:&PairEvaluation,gold:bool,train:usize,cache:&mut PairCache)->crate::columns::CaseColumns {
    let (tables,key)=if gold {(&result.gold,&result.gold_prefix)} else {(&result.mutant,&result.mutant_prefix)};
    if tables.len()<2 {return crate::columns::case_columns_in(materializer,evidence,tables,train,None);}
    let split=tables.len()-2;
    if cache.columns.as_ref().is_some_and(|(held,_)|held==key) {
        if let Some(columns)=cache.columns.as_ref().unwrap().1.finish(materializer,&tables[split..],train) {return columns;}
        cache.columns=None;
        return crate::columns::case_columns_in(materializer,evidence,tables,train,None);
    }
    cache.columns=None;
    let prefix=crate::columns::CaseColumnPrefix::new(materializer,evidence,&tables[..split],train);
    // The packed fold includes nested string/vector capacities and its
    // run-interning metadata, not just the values buffer.
    let native_prefix_bytes=cache.prefix.as_ref().map_or(0,|memo|memo.row_bytes);
    if prefix.is_complete() && prefix.retained_bytes().saturating_add(native_prefix_bytes)<=cache.pair_room() {
        let columns=prefix.finish(materializer,&tables[split..],train);
        if let Some(columns)=columns {
            cache.columns=Some((key.clone(),prefix));columns
        } else {drop(prefix);crate::columns::case_columns_in(materializer,evidence,tables,train,None)}
    } else {
        prefix.into_finished(materializer,&tables[split..],train)
    }
}
