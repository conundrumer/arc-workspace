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
use arclog::hash::{StableHash, StableHashMap, StableHasher};
use arclog::session::{Counts, TaskSession};
use std::cell::RefCell;
use std::collections::BTreeMap;
use std::hash::Hasher;

/// The content hash of each top-level form of one program, made on first use.
pub(super) struct TopHashes<'a> {
    checked:&'a CheckedProgram,
    held:RefCell<Vec<Option<Option<StableHash>>>>,
}

impl<'a> TopHashes<'a> {
    pub(super) fn new(checked:&'a CheckedProgram)->Self {
        let forms=checked.program.program.value().forms.len();
        Self {checked,held:RefCell::new(vec![None;forms])}
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
    /// The bytes that the entry counts toward the memo.
    bytes:usize,
    /// The bytes that a replay of its events may add to the result cache.
    grows:usize,
    used:u64,
}

/// What the memo has done, for a report.
#[derive(Clone, Copy, Default, Debug)]
pub struct FormMemoStats {
    pub entries:usize,
    pub bytes:usize,
    pub hits:u64,
    pub kept:u64,
    pub bypassed:u64,
    pub declined:u64,
    pub evicted:u64,
}

/// The kept walks of one task, bounded in bytes, which a case's end does not release.
pub struct FormMemo {
    on:bool,
    bound:usize,
    bytes:usize,
    entries:StableHashMap<StableHash,Entry>,
    /// The key of each entry by the tick of its last use: the entry to drop
    /// first is the one used least recently.
    recency:BTreeMap<u64,StableHash>,
    clock:u64,
    /// The work that a request counts across the calls it makes, where a caller sets one.
    request:Option<TableWork>,
    stats:FormMemoStats,
}

impl FormMemo {
    /// A memo of at most `bound` bytes.
    pub fn new(bound:usize)->Self {
        Self {on:true,bound,bytes:0,entries:StableHashMap::default(),recency:BTreeMap::new(),clock:0,request:None,stats:FormMemoStats::default()}
    }
    pub fn set_on(&mut self,on:bool) {
        self.on=on;
        if !on {self.clear();}
    }
    /// Release every kept walk.
    pub fn clear(&mut self) {
        self.entries=StableHashMap::default();
        self.recency=BTreeMap::new();
        self.bytes=0;
    }
    /// The work count of the request that the calls after this one belong to,
    /// or `None` for a request with no cap. A kept walk is taken where that
    /// count has room for the work the walk counted, and then charges it; a
    /// walk that ends with the count past its cap is kept by no one, since its
    /// stop depends on the work before it.
    pub fn set_request_work(&mut self,work:Option<TableWork>) {self.request=work;}
    /// The most bytes the memo keeps.
    pub fn bound(&self)->usize {self.bound}
    pub fn stats(&self)->FormMemoStats {FormMemoStats {entries:self.entries.len(),bytes:self.bytes,..self.stats}}

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
        if let Some(examples)=self.replayed(key,probe,session,too_large) {return examples;}
        let before=too_large.0.borrow().len();
        let evictions=session.results.evictions();
        let counted=work.count();
        let capture=session.results.begin_capture();
        let examples=run();
        let (events,counts)=session.results.end_capture(capture);
        let delta:Vec<(Vec<Assignment>,Stop)>=too_large.0.borrow()[before..].to_vec();
        let in_room=self.request.as_ref().is_none_or(|request|!request.is_past_cap());
        if in_room && session.results.evictions()==evictions {
            let charged=work.count().saturating_sub(counted);
            self.keep(key,probe,&examples,delta,events,counts,charged);
        } else {
            self.stats.declined+=1;
        }
        examples
    }

    fn replayed(&mut self,key:StableHash,probe:&Probe<'_>,session:&TaskSession,too_large:&TooLarge)->Option<Vec<ExampleRows>> {
        let entry=self.entries.get(&key)?;
        if entry.names.len()!=probe.dets.len() {return None;}
        if session.results.bytes().saturating_add(entry.grows)>arclog::eval::cache::cache_bytes_bound(session) {return None;}
        if let Some(request)=&self.request {
            if !request.fits(entry.charged) {return None;}
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
            mapped.push((top,found?));
        }
        let top=|from:u32|mapped.iter().find(|(top,_)|*top==from).map(|(_,to)|*to);
        let examples=remap_examples(&entry.examples,&name,&top)?;
        let delta=entry.delta.iter().map(|(rows,stop)|{
            let rows=rows.iter().map(|(from,value)|Some((name(from)?,Arc::clone(value)))).collect::<Option<Vec<_>>>()?;
            Some((rows,remap_stop(stop,&top)?))
        }).collect::<Option<Vec<_>>>()?;
        if !arclog::eval::cache::replay(session,&entry.events) {return None;}
        session.record_counts(entry.counts);
        if let Some(request)=&self.request {let _=request.charge(entry.charged);}
        too_large.0.borrow_mut().extend(delta);
        self.stats.hits+=1;
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

    #[allow(clippy::too_many_arguments)]
    fn keep(&mut self,key:StableHash,probe:&Probe<'_>,examples:&[ExampleRows],delta:Vec<(Vec<Assignment>,Stop)>,events:Vec<Recorded>,counts:Counts,charged:u64) {
        let names:Box<[ProgramRelation]>=probe.dets.iter().map(|det|det.relation.clone()).collect();
        let Some(stops)=scan(examples,&delta,&names) else {
            self.stats.declined+=1;
            return;
        };
        let mut tops=Vec::new();
        for top in stops {
            let Some(hash)=probe.tops.of(top as usize) else {
                self.stats.declined+=1;
                return;
            };
            tops.push((top,hash));
        }
        let grows:usize=events.iter().map(Recorded::bytes).sum();
        let bytes=grows.saturating_add(rows_bytes(examples)).saturating_add(delta.len().saturating_mul(256));
        if bytes>self.bound/4 {
            self.stats.declined+=1;
            return;
        }
        if let Some(old)=self.entries.remove(&key) {
            self.recency.remove(&old.used);
            self.bytes=self.bytes.saturating_sub(old.bytes);
        }
        while self.bytes.saturating_add(bytes)>self.bound {
            let Some((_,oldest))=self.recency.pop_first() else {break};
            if let Some(gone)=self.entries.remove(&oldest) {
                self.bytes=self.bytes.saturating_sub(gone.bytes);
                self.stats.evicted+=1;
            }
        }
        self.clock+=1;
        self.recency.insert(self.clock,key);
        self.bytes+=bytes;
        self.stats.kept+=1;
        self.entries.insert(key,Entry {examples:examples.to_vec(),delta,events:events.into(),counts,charged,names,tops:tops.into(),bytes,grows,used:self.clock});
    }
}

/// Whether a bound depends on the machine or on the session's history, which
/// no kept walk may hold.
fn machine_bound(bound:ReachedBound)->bool {
    matches!(bound,ReachedBound::Deadline|ReachedBound::Cancelled|ReachedBound::SessionBytes(_))
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

fn rows_bytes(examples:&[ExampleRows])->usize {
    let mut bytes=0usize;
    for example in examples {
        let Ok(rows)=&example.rows else {continue};
        for (assigned,models) in &rows.at {
            bytes=bytes.saturating_add(assigned.len().saturating_mul(32));
            for model in models {
                if let RelationValue::Rows(r)=model {
                    bytes=bytes.saturating_add(usize::try_from(r.len()).unwrap_or(usize::MAX).saturating_mul(usize::from(r.arity()).saturating_mul(8)+16));
                }
            }
        }
    }
    bytes
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
