//! The walks of tables that the programs of one task share, kept from one
//! program to the next.
//!
//! A table's rows on each example come from one walk of its relation over the
//! joint assignments of the `DET`s it reads
//! ([`relation_examples_skipping`]). Two programs whose form has one resolved
//! content ([`arclog::resolver::ResolvedProgram::content`]: the form's text,
//! with each read standing for the content of its maker) and whose table reads
//! the same `DET`s in the same order walk it to the same rows. The result cache
//! keys its entries by the same content, so the memo keys a walk the way the
//! cache keys the clauses that the walk evaluates.
//!
//! A walk also reads the result cache. A lookup that finds an entry makes no
//! work, so the work the walk counts, and with it a stop at the work cap of the
//! table, depends on the entries that the forms before it left. The memo
//! keeps, with the rows, the lookups, ids and stores that the walk made
//! ([`arclog::session::ResultCache::begin_capture`]). A later program takes the
//! walk where each kept lookup finds in its cache what it found
//! ([`arclog::eval::cache::replay`]), and the replay makes the ids and stores,
//! so the cache holds what the walk would have left in it. Where one lookup
//! differs, the walk runs.
//!
//! The memo takes and keeps a walk only where its result is a function of the
//! content: no stop at the deadline, a cancellation or the byte bound, no
//! fault, no eviction by the result cache during the walk, and no stop of the
//! program's [`TooLarge`] that the walk could read.
use super::*;
use arclog::eval::{ReachedBound, Stop};
use arclog::eval::cache::Recorded;
use arclog::hash::{StableHash, StableHashMap, StableHashSet, StableHasher};
use arclog::relations::Relation;
use arclog::session::same_rows;
use arclog::session::{Counts, TaskSession};
use std::cell::RefCell;
use std::collections::BTreeMap;
use std::hash::Hasher;

/// The content hash of each top-level form of one program, made on first use,
/// and the hash of the text of the forms that a form's tables read.
///
/// The content of a form is free of the order of the conjuncts of its clauses
/// and of the names of its relations, but the work of its search is not: the
/// order of the variables of a join follows the clause as written, and with it
/// the rows and bindings that the join counts. So the key of a walk holds the
/// text of each form that the walk reads, beside their content.
pub(super) struct TopHashes<'a> {
    checked:&'a CheckedProgram,
    held:RefCell<Vec<Option<Option<StableHash>>>>,
    /// The hash of the text of each top-level form, none where the text of
    /// the program does not split into its forms.
    texts:Option<Vec<StableHash>>,
    reads:RefCell<Vec<Option<Option<StableHash>>>>,
}

impl<'a> TopHashes<'a> {
    pub(super) fn new(checked:&'a CheckedProgram,texts:Option<Vec<&str>>)->Self {
        let forms=checked.program.program.value().forms.len();
        let texts=texts.filter(|texts|texts.len()==forms).map(|texts|texts.into_iter().map(|text|{
            let mut hasher=StableHasher::new();
            for word in text.split_whitespace() {
                hasher.write(word.as_bytes());
                hasher.write_u8(b' ');
            }
            hasher.finish128()
        }).collect());
        Self {checked,held:RefCell::new(vec![None;forms]),texts,reads:RefCell::new(vec![None;forms])}
    }
    /// The hash of the text of the form at `top` and of each form it reads, at any depth.
    fn text_of(&self,top:usize)->Option<StableHash> {
        let mut held=self.reads.borrow_mut();
        let slot=held.get_mut(top)?;
        *slot.get_or_insert_with(||{
            let texts=self.texts.as_ref()?;
            let keep=self.checked.program.use_closure(top)?;
            let mut hasher=StableHasher::new();
            hasher.write(b"arclog.gold.form-memo.text");
            for at in (0..keep.len()).filter(|&at|keep[at]) {
                hasher.write_u128(texts.get(at)?.0);
            }
            Some(hasher.finish128())
        })
    }
    fn of(&self,top:usize)->Option<StableHash> {
        let mut held=self.held.borrow_mut();
        let slot=held.get_mut(top)?;
        *slot.get_or_insert_with(||self.checked.program.content(&NodePath::top(top as u32)).map(|content|content.content_hash()))
    }
    fn count(&self)->usize {self.held.borrow().len()}
}

/// What identifies a table's walk in the program that asks for it.
pub(super) struct Probe<'a> {
    pub checked:&'a CheckedProgram,
    pub tops:&'a TopHashes<'a>,
    /// The path of the table's form.
    pub form:&'a NodePath,
    /// The table's Name, empty for a table of no output.
    pub output:&'a str,
    /// The place of the table among the form's tables of the same Name.
    pub ordinal:usize,
    /// The `DET`s that the walk assigns, in order.
    pub dets:&'a [Det],
}

impl Probe<'_> {
    /// The key of the walk: the content of the form, the Name and place of the
    /// table, and the content of each `DET` in the order of the assignments. `None`
    /// where the program holds a form or a `DET` that the key does not cover:
    /// a form below the top level, or an output of an instance or a `RIGID_DET`.
    fn key(&self)->Option<StableHash> {
        let [step]=&self.form.0[..] else {return None};
        let own=self.tops.of(step.0 as usize)?;
        let mut hasher=StableHasher::new();
        hasher.write(b"arclog.gold.form-memo");
        hasher.write_u128(own.0);
        hasher.write_u128(self.tops.text_of(step.0 as usize)?.0);
        hasher.write_usize(self.output.len());
        hasher.write(self.output.as_bytes());
        hasher.write_usize(self.ordinal);
        hasher.write_usize(self.dets.len());
        for det in self.dets {
            if matches!(det.relation,ProgramRelation::Output(_)) {return None;}
            hasher.write_u8(u8::from(det.open)*2+u8::from(det.pick));
            let paths=self.checked.program.forms_of(det.node);
            hasher.write_usize(paths.len());
            for path in paths {
                let [step]=&path.0[..] else {return None};
                hasher.write_u128(self.tops.of(step.0 as usize)?.0);
            }
        }
        Some(hasher.finish128())
    }
}

/// The bytes that the memo counts for one event beside its relations: the
/// event's own allocations, such as the copy of the content it names.
const EVENT_BYTES:usize=512;

/// The most events that the capture of one walk keeps. A walk with more is not
/// kept, and its capture stops at this count.
const EVENT_LIMIT:usize=1<<14;

/// The least work, in bindings, that a walk counted for the memo to keep it.
const MIN_WORK:u64=1<<14;

/// The bindings that a walk counts for each event it made, at the least, for
/// the memo to keep it: a replay costs about an event, and saves about the
/// work.
const WORK_PER_EVENT:u64=32;

/// The most keys of walks that the memo remembers not to keep, and of those it
/// kept, each. At this count the memo forgets them all.
const KEYS:usize=1<<16;

/// A replay that fails this many times drops its entry.
const FAILURES:u8=2;

/// The bytes of `relation`'s rows, an estimate.
fn relation_bytes(relation:&Relation)->usize {
    usize::try_from(relation.len()).unwrap_or(usize::MAX).saturating_mul(usize::from(relation.arity()).saturating_mul(8)+16).saturating_add(256)
}

/// The relations that the kept walks hold, each once however many walks hold
/// it: two relations of the same rows and the same columns of parts are one
/// relation, as the kept computations of [`arclog::eval::carry`] share them.
#[derive(Default)]
struct Pool {
    by_rows:StableHashMap<StableHash,Vec<Arc<Relation>>>,
    /// For each relation, by address, the count of entries that hold it and its bytes.
    held:StableHashMap<usize,(usize,usize)>,
    /// The bytes of the relations held.
    bytes:usize,
}

/// The relations that one entry holds, each once, by address.
#[derive(Default)]
struct Held {
    seen:StableHashSet<usize>,
    list:Vec<Arc<Relation>>,
}

impl Pool {
    /// The relation of the pool with the rows and columns of parts of `relation`, which the entry of `held` then holds.
    fn hold(&mut self,held:&mut Held,relation:&Arc<Relation>)->Arc<Relation> {
        let alike=self.by_rows.entry(relation.rows_hash()).or_default();
        let columns=|relation:&Relation|relation.parts().iter().map(|part|part.columns.clone()).collect::<Vec<_>>();
        let found=alike.iter().find(|kept|columns(kept)==columns(relation) && same_rows(kept,relation)).cloned();
        let kept=match found {
            Some(kept)=>kept,
            None=>{alike.push(Arc::clone(relation));Arc::clone(relation)}
        };
        let address=Arc::as_ptr(&kept) as usize;
        if held.seen.insert(address) {
            let bytes=relation_bytes(&kept);
            let slot=self.held.entry(address).or_insert((0,bytes));
            slot.0+=1;
            if slot.0==1 {self.bytes=self.bytes.saturating_add(bytes);}
            held.list.push(Arc::clone(&kept));
        }
        kept
    }

    /// Release the relations of an entry; a relation that no entry holds leaves the pool.
    fn release(&mut self,list:&[Arc<Relation>]) {
        for relation in list {
            let address=Arc::as_ptr(relation) as usize;
            let Some(slot)=self.held.get_mut(&address) else {continue};
            slot.0-=1;
            if slot.0>0 {continue;}
            let bytes=slot.1;
            self.held.remove(&address);
            self.bytes=self.bytes.saturating_sub(bytes);
            let hash=relation.rows_hash();
            if let Some(alike)=self.by_rows.get_mut(&hash) {
                alike.retain(|kept|!Arc::ptr_eq(kept,relation));
                if alike.is_empty() {self.by_rows.remove(&hash);}
            }
        }
    }
}

/// A kept walk, in the names and form paths of the program that made it.
struct Entry {
    examples:Vec<ExampleRows>,
    /// What the walk added to the program's [`TooLarge`].
    delta:Vec<(Vec<Assignment>,Stop)>,
    events:Box<[Recorded]>,
    counts:Counts,
    /// The work the walk counted in the table's count.
    charged:u64,
    /// The relation of each `DET` of the walk, in order.
    names:Box<[ProgramRelation]>,
    /// The index and content hash of each top-level form that a stop of the
    /// result names.
    tops:Box<[(u32,StableHash)]>,
    /// The relations of the examples, the delta and the events, each once.
    relations:Box<[Arc<Relation>]>,
    /// The bytes that the entry counts beside its relations.
    fixed:usize,
    /// The bytes that a replay of its events may add to the result cache.
    grows:usize,
    /// The seconds that the walk ran, with its capture.
    walked:f64,
    failed:u8,
    used:u64,
}

/// What the memo has done, for a report.
#[derive(Clone,Copy,Default,Debug)]
pub struct FormMemoStats {
    pub entries:usize,
    pub bytes:usize,
    /// Walks taken from the memo.
    pub hits:u64,
    /// Walks kept.
    pub kept:u64,
    /// Walks that the key does not cover.
    pub bypassed:u64,
    /// Walks that the memo knows it does not keep, which ran with no capture.
    pub skipped:u64,
    /// Walks captured and then not kept for the little work they counted.
    pub cheap:u64,
    /// Walks whose capture passed `EVENT_LIMIT`.
    pub overflow:u64,
    /// Walks not kept for another reason: a stop, a fault or an eviction, or a size past the bound.
    pub declined:u64,
    /// Entries dropped to make room.
    pub evicted:u64,
    /// Misses of a key that the memo kept and dropped since: the hits that a larger bound would add, at most.
    pub lost:u64,
    /// Replays whose kept lookups did not all find what they found.
    pub mismatch:u64,
    /// Hits refused for a name or a form that the program does not map, or for no room.
    pub refused:u64,
    /// Seconds that the walks that ran under a capture took.
    pub walk_seconds:f64,
    /// Seconds that the replays took, and the seconds that the walks they replaced took.
    pub replay_seconds:f64,
    pub saved_seconds:f64,
    /// Seconds that the memo took to keep walks.
    pub keep_seconds:f64,
}

/// The kept walks of one task, bounded in bytes, which a case's end does not release.
pub struct FormMemo {
    on:bool,
    bound:usize,
    entries:StableHashMap<StableHash,Entry>,
    /// The bytes of the entries beside the relations of the pool.
    fixed:usize,
    pool:Pool,
    /// The key of each entry by the tick of its last use: the entry to drop
    /// first is the one used least recently.
    recency:BTreeMap<u64,StableHash>,
    clock:u64,
    /// The keys of walks that the memo does not keep.
    skip:StableHashSet<StableHash>,
    /// The keys of walks that the memo kept.
    kept_keys:StableHashSet<StableHash>,
    /// The work that a request counts across the calls it makes, where a caller sets one.
    request:Option<TableWork>,
    stats:FormMemoStats,
}

impl FormMemo {
    /// A memo of at most `bound` bytes.
    pub fn new(bound:usize)->Self {
        Self {on:true,bound,entries:StableHashMap::default(),fixed:0,pool:Pool::default(),recency:BTreeMap::new(),clock:0,skip:StableHashSet::default(),kept_keys:StableHashSet::default(),request:None,stats:FormMemoStats::default()}
    }
    pub fn set_on(&mut self,on:bool) {
        self.on=on;
        if !on {self.clear();}
    }
    /// Change the bound; entries past it go, the least recently used first.
    pub fn set_bound(&mut self,bound:usize) {
        self.bound=bound;
        self.make_room();
    }
    /// Release every kept walk.
    pub fn clear(&mut self) {
        self.entries=StableHashMap::default();
        self.recency=BTreeMap::new();
        self.pool=Pool::default();
        self.fixed=0;
        self.skip=StableHashSet::default();
        self.kept_keys=StableHashSet::default();
    }
    /// The work count of the request that the calls after this one belong to,
    /// or `None` for a request with no cap. A kept walk is taken where that
    /// count has room for the work the walk counted, and then charges it; a
    /// walk that ends with the count past its cap is kept by no one, since its
    /// stop depends on the work before it.
    pub fn set_request_work(&mut self,work:Option<TableWork>) {self.request=work;}
    /// The most bytes the memo keeps.
    pub fn bound(&self)->usize {self.bound}
    /// The bytes that the memo holds.
    pub fn bytes(&self)->usize {self.pool.bytes.saturating_add(self.fixed)}
    pub fn stats(&self)->FormMemoStats {FormMemoStats {entries:self.entries.len(),bytes:self.bytes(),..self.stats}}

    fn skipping(&mut self,key:StableHash) {
        if self.skip.len()>=KEYS {self.skip.clear();}
        self.skip.insert(key);
    }

    /// The rows of the table that `probe` names, from `run`, the walk, or from
    /// a kept walk that replays in `session`. `work` is the table's count and
    /// `too_large` the stops of the program so far.
    pub(super) fn examples(&mut self,probe:&Probe<'_>,session:&TaskSession,too_large:&TooLarge,work:&TableWork,run:impl FnOnce()->Vec<ExampleRows>)->Vec<ExampleRows> {
        let untouched=||too_large.0.borrow().iter().all(|(rows,_)|!rows.iter().all(|(name,_)|probe.dets.iter().any(|det|&det.relation==name)));
        let key=if self.on && untouched() {probe.key()} else {None};
        let Some(key)=key else {
            self.stats.bypassed+=1;
            return run();
        };
        if self.skip.contains(&key) {
            self.stats.skipped+=1;
            return run();
        }
        if let Some(examples)=self.replayed(key,probe,session,too_large) {return examples;}
        if self.kept_keys.contains(&key) {self.stats.lost+=1;}
        let before=too_large.0.borrow().len();
        let evictions=session.results.evictions();
        let counted=work.count();
        let started=Stopwatch::start();
        let capture=session.results.begin_capture_limited(EVENT_LIMIT);
        let examples=run();
        let captured=session.results.end_capture_limited(capture);
        let walked=started.elapsed().seconds();
        self.stats.walk_seconds+=walked;
        let Some((events,counts))=captured else {
            self.stats.overflow+=1;
            self.skipping(key);
            return examples;
        };
        let charged=work.count().saturating_sub(counted);
        if charged<MIN_WORK || charged<WORK_PER_EVENT.saturating_mul(events.len() as u64) {
            self.stats.cheap+=1;
            self.skipping(key);
            return examples;
        }
        let delta:Vec<(Vec<Assignment>,Stop)>=too_large.0.borrow()[before..].to_vec();
        let in_room=self.request.as_ref().is_none_or(|request|!request.is_past_cap());
        if in_room && session.results.evictions()==evictions {
            let began=Stopwatch::start();
            self.keep(key,probe,&examples,delta,events,counts,charged,walked);
            self.stats.keep_seconds+=began.elapsed().seconds();
        } else {
            self.stats.declined+=1;
        }
        examples
    }

    fn replayed(&mut self,key:StableHash,probe:&Probe<'_>,session:&TaskSession,too_large:&TooLarge)->Option<Vec<ExampleRows>> {
        let began=Stopwatch::start();
        let entry=self.entries.get(&key)?;
        if entry.names.len()!=probe.dets.len() {return None;}
        if session.results.bytes().saturating_add(entry.grows)>arclog::eval::cache::cache_bytes_bound(session) {
            self.stats.refused+=1;
            return None;
        }
        if let Some(request)=&self.request {
            if !request.fits(entry.charged) {
                self.stats.refused+=1;
                return None;
            }
        }
        let name=|from:&ProgramRelation|{
            let at=entry.names.iter().position(|name|name==from)?;
            Some(probe.dets[at].relation.clone())
        };
        let [own]=&probe.form.0[..] else {return None};
        let own_top=own.0;
        let own_hash=probe.tops.of(own_top as usize)?;
        let mut mapped:Vec<(u32,u32)>=Vec::new();
        for &(top,hash) in entry.tops.iter() {
            let found=if hash==own_hash {Some(own_top)} else {
                let mut same=(0..probe.tops.count()).filter(|&at|probe.tops.of(at)==Some(hash));
                match (same.next(),same.next()) {
                    (Some(at),None)=>Some(at as u32),
                    _=>None,
                }
            };
            let Some(found)=found else {
                self.stats.refused+=1;
                return None;
            };
            mapped.push((top,found));
        }
        let top=|from:u32|mapped.iter().find(|(top,_)|*top==from).map(|(_,to)|*to);
        let examples=remap_examples(&entry.examples,&name,&top);
        let delta=entry.delta.iter().map(|(rows,stop)|{
            let rows=rows.iter().map(|(from,value)|Some((name(from)?,Arc::clone(value)))).collect::<Option<Vec<_>>>()?;
            Some((rows,remap_stop(stop,&top)?))
        }).collect::<Option<Vec<_>>>();
        let (Some(examples),Some(delta))=(examples,delta) else {
            self.stats.refused+=1;
            return None;
        };
        if !arclog::eval::cache::replay(session,&entry.events) {
            self.stats.mismatch+=1;
            let failed={let entry=self.entries.get_mut(&key)?;entry.failed+=1;entry.failed};
            if failed>=FAILURES {
                self.remove(key);
                self.skipping(key);
            }
            return None;
        }
        let (counts,charged,walked)=(entry.counts,entry.charged,entry.walked);
        session.record_counts(counts);
        if let Some(request)=&self.request {let _=request.charge(charged);}
        too_large.0.borrow_mut().extend(delta);
        self.stats.hits+=1;
        self.stats.saved_seconds+=walked;
        self.stats.replay_seconds+=began.elapsed().seconds();
        self.touch(key);
        Some(examples)
    }

    fn touch(&mut self,key:StableHash) {
        self.clock+=1;
        if let Some(entry)=self.entries.get_mut(&key) {
            self.recency.remove(&entry.used);
            entry.used=self.clock;
            self.recency.insert(self.clock,key);
        }
    }

    /// Drop the entry of `key`.
    fn remove(&mut self,key:StableHash) {
        let Some(gone)=self.entries.remove(&key) else {return};
        self.recency.remove(&gone.used);
        self.fixed=self.fixed.saturating_sub(gone.fixed);
        self.pool.release(&gone.relations);
    }

    /// Drop the entries used least recently while the memo holds more than its bound.
    fn make_room(&mut self) {
        while self.bytes()>self.bound {
            let Some((_,oldest))=self.recency.pop_first() else {break};
            self.remove(oldest);
            self.stats.evicted+=1;
        }
    }

    #[allow(clippy::too_many_arguments)]
    fn keep(&mut self,key:StableHash,probe:&Probe<'_>,examples:&[ExampleRows],delta:Vec<(Vec<Assignment>,Stop)>,events:Vec<Recorded>,counts:Counts,charged:u64,walked:f64) {
        let names:Box<[ProgramRelation]>=probe.dets.iter().map(|det|det.relation.clone()).collect();
        let Some(stops)=scan(examples,&delta,&names) else {
            self.stats.declined+=1;
            self.skipping(key);
            return;
        };
        let mut tops=Vec::new();
        for top in stops {
            let Some(hash)=probe.tops.of(top as usize) else {
                self.stats.declined+=1;
                self.skipping(key);
                return;
            };
            tops.push((top,hash));
        }
        self.remove(key);
        let before=self.pool.bytes;
        let mut held=Held::default();
        let pool=&mut self.pool;
        let mut one=|relation:&Arc<Relation>|pool.hold(&mut held,relation);
        let events:Box<[Recorded]>=events.iter().map(|event|event.with_relations(&mut one)).collect();
        let examples=map_relations(examples,&mut one);
        let delta:Vec<(Vec<Assignment>,Stop)>=delta.into_iter().map(|(rows,stop)|(rows.into_iter().map(|(name,value)|(name,one(&value))).collect(),stop)).collect();
        let fixed=EVENT_BYTES.saturating_mul(events.len()).saturating_add(1024).saturating_add(delta.len().saturating_mul(256)).saturating_add(examples.len().saturating_mul(256));
        let fresh=self.pool.bytes.saturating_sub(before).saturating_add(fixed);
        if fresh>self.bound/4 {
            self.pool.release(&held.list);
            self.stats.declined+=1;
            self.skipping(key);
            return;
        }
        let grows:usize=held.list.iter().map(|relation|relation_bytes(relation)).sum::<usize>().saturating_add(fixed);
        self.fixed=self.fixed.saturating_add(fixed);
        self.clock+=1;
        self.recency.insert(self.clock,key);
        if self.kept_keys.len()>=KEYS {self.kept_keys.clear();}
        self.kept_keys.insert(key);
        self.stats.kept+=1;
        let used=self.clock;
        self.entries.insert(key,Entry {examples,delta,events,counts,charged,names,tops:tops.into(),relations:held.list.into(),fixed,grows,walked,failed:0,used});
        self.make_room();
    }
}

/// Whether a bound depends on the machine or on the session's history, which
/// no kept walk may hold: a request cap stop depends on the work the request
/// did before the walk.
fn machine_bound(bound:ReachedBound)->bool {
    matches!(bound,ReachedBound::RequestWork{..}|ReachedBound::Cancelled|ReachedBound::SessionBytes(_))
}

/// The top-level forms that the stops of `examples` and `delta` stand at, or
/// `None` where the walk is not one a memo keeps: a fault, a stop of a
/// machine bound, a stop below the top level, or an assignment of a relation
/// that is no `DET` of the walk.
fn scan(examples:&[ExampleRows],delta:&[(Vec<Assignment>,Stop)],names:&[ProgramRelation])->Option<Vec<u32>> {
    let mut tops:Vec<u32>=Vec::new();
    let mut stop=|stop:&Stop|->Option<()> {
        let [step]=&stop.form.0[..] else {return None};
        if machine_bound(stop.bound) {return None;}
        if !tops.contains(&step.0) {tops.push(step.0);}
        Some(())
    };
    let named=|rows:&[Assignment]|rows.iter().all(|(name,_)|names.contains(name));
    for example in examples {
        let Ok(rows)=&example.rows else {return None};
        for (assigned,models) in &rows.at {
            if !named(assigned) {return None;}
            for model in models {
                if let RelationValue::Stopped(found)=model {stop(found)?;}
            }
        }
        if let Some(found)=&rows.stop {stop(found)?;}
    }
    for (rows,found) in delta {
        if !named(rows) {return None;}
        stop(found)?;
    }
    Some(tops)
}

/// `examples` with each relation of its rows and assignments replaced by `one` of it.
fn map_relations(examples:&[ExampleRows],one:&mut impl FnMut(&Arc<Relation>)->Arc<Relation>)->Vec<ExampleRows> {
    examples.iter().map(|example|ExampleRows {example:example.example,rows:example.rows.as_ref().map(|rows|Assigned {
        at:rows.at.iter().map(|(assigned,models)|(
            assigned.iter().map(|(name,value)|(name.clone(),one(value))).collect(),
            models.iter().map(|model|match model {RelationValue::Rows(rows)=>RelationValue::Rows(one(rows)),other=>other.clone()}).collect(),
        )).collect(),
        stop:rows.stop.clone(),
    }).map_err(|fault|fault.clone())}).collect()
}

fn remap_stop(stop:&Stop,top:&dyn Fn(u32)->Option<u32>)->Option<Stop> {
    let [step]=&stop.form.0[..] else {return None};
    Some(Stop {bound:stop.bound,form:NodePath::top(top(step.0)?)})
}

fn remap_examples(examples:&[ExampleRows],name:&dyn Fn(&ProgramRelation)->Option<ProgramRelation>,top:&dyn Fn(u32)->Option<u32>)->Option<Vec<ExampleRows>> {
    let mut made=Vec::with_capacity(examples.len());
    for example in examples {
        let Ok(rows)=&example.rows else {return None};
        let mut at=Vec::with_capacity(rows.at.len());
        for (assigned,models) in &rows.at {
            let assigned=assigned.iter().map(|(from,value)|Some((name(from)?,Arc::clone(value)))).collect::<Option<Vec<_>>>()?;
            let models=models.iter().map(|model|match model {
                RelationValue::Stopped(stop)=>Some(RelationValue::Stopped(remap_stop(stop,top)?)),
                other=>Some(other.clone()),
            }).collect::<Option<Vec<_>>>()?;
            at.push((assigned,models));
        }
        let stop=match &rows.stop {
            Some(stop)=>Some(remap_stop(stop,top)?),
            None=>None,
        };
        made.push(ExampleRows {example:example.example,rows:Ok(Assigned {at,stop})});
    }
    Some(made)
}
