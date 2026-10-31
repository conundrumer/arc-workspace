//! The domains of the `DET`s that the liveness walks of a task session's
//! decodes compute ([`super::det_admission`]), kept across those walks.
//!
//! Each liveness walk runs in a session of its own, whose result cache
//! starts empty, so that its verdict, and the place where its table work
//! count passes the cap, do not depend on what the decode cached before.
//! The walks of one task session share one intern table and its fact
//! relations, so that the relations of one walk hold the term ids that any
//! other walk gives the same terms. No result of the engine depends on the
//! order of term ids, as `docs/engine/evaluator.md#parallelism-and-determinism`
//! gives.
//!
//! A domain that a walk computes is kept with what its computation did to
//! the walk's result cache, in order: each lookup, with the value it found;
//! each relation it gave an id; each store; and the table work it counted.
//! A later walk that needs the domain of a `DET` of the same key ([`Key`])
//! takes the kept domain where each kept lookup would find in its own cache
//! a value of the same rows, held in parts of the same columns, where it
//! found one, and nothing where it found nothing, and where its count stays
//! within the cap after that work. The computation reads nothing else that
//! differs between the walks, so it would make those lookups, ids and
//! stores, and count that work, in the later walk too. The later walk then
//! makes them and counts that work, so its cache and its count stand as
//! the computation would leave them. Otherwise it computes the domain.
//!
//! The shared intern table counts toward the byte bound of each walk's
//! session, and a value kept from another walk can hold its rows apart from
//! a value that a computation would build on them, so a walk's session
//! holds at least the bytes that a session of its own would hold. A walk
//! that stops at the byte bound, or whose cache evicts, runs again in a
//! session of its own with no kept domain ([`super::det_admission`]).
//!
//! What the walk of a part of a program's `DET`s gave is kept too
//! ([`PartKey`]). It reads only the forms that the key's content holds, in a
//! session that starts empty, so it stands for each program that holds that
//! part, whichever program walked it first.
//!
//! The walks of a decode's tables run in the task session itself, and keep
//! the domains they compute in a memo of that session ([`SessionMemo`]).

use std::hash::{Hash, Hasher};
use std::sync::{Arc, Mutex};

use crate::check::CheckedProgram;
use crate::eval::cache::{relation_estimate, replay, Recorded, RecordedKey};
use crate::eval::{Domain, Evaluation, Outcome};
use crate::hash::{StableHash, StableHashMap};
use crate::judge::determination::{Assignment, Det, Domains};
use crate::program::ProgramRelation;
use crate::relations::Relation;
use crate::session::{same_rows, ResultKey, TaskSession};
use crate::types::ValueType;
use crate::types::GraphRelation;

/// The most bytes that the kept domains hold, by [`Recorded::bytes`]; past
/// it, the walks keep none of those kept so far.
const KEPT_BYTES: usize = 1 << 28;

/// The most bytes of the shared intern table; past it, the next walk starts
/// a new intern table, and no domain kept with the old one is taken.
const TERM_BYTES: usize = 1 << 28;

/// The most computations kept for one key, each with its own lookups.
const PER_KEY: usize = 4;

/// The most walks of parts kept; past it, the walks keep none of those kept
/// so far.
const PARTS_KEPT: usize = 1 << 16;

/// What the computation of a domain reads beside its key, the same for
/// each walk of the task session: the task, the registry, the
/// constructions, by their addresses, and the table work cap. The caps and
/// the byte bound are the session's.
#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub(crate) struct Scope {
    pub(crate) task: usize,
    pub(crate) registry: usize,
    pub(crate) constructions: usize,
    pub(crate) table_work_cap: u64,
}

/// The domains kept for the liveness walks of one task session.
pub(crate) struct ProbeMemo {
    scope: Scope,
    kept: Mutex<Kept>,
    parts: Mutex<StableHashMap<PartKey, PartWalk>>,
}

/// What the walk of a part of a program's `DET`s gave.
#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub(crate) enum PartWalk {
    /// The walk reached its last leaf, with `leaves` leaves, and `live`
    /// where one of them is live.
    Ended { leaves: u64, live: bool },
    /// The walk passed the assignment cap.
    PastCap,
    /// The walk ended at a fault or at another bound.
    Stopped,
}

/// The key of a walk of a part: the assignment cap, and each `DET` it
/// assigns and each pick it tests, in the order of the walk.
#[derive(PartialEq, Eq, Hash)]
pub(crate) struct PartKey {
    cap: u64,
    dets: Box<[PartDet]>,
    picks: Box<[PartDet]>,
}

/// A `DET` of a [`PartKey`]: its relation, whether it is open and a pick, the
/// content of its node, which holds the content of each of its forms and,
/// at any depth, of each relation they read, and the types of its columns.
#[derive(PartialEq, Eq, Hash)]
struct PartDet {
    relation: ProgramRelation,
    open: bool,
    pick: bool,
    node: StableHash,
    columns: Box<[ValueType]>,
}

/// The key of the walk of `dets` with `picks` in `program`, a program with no
/// cycle, under the assignment cap `cap`, or `None` where one of them has no
/// content or no column types.
pub(crate) fn part_key(program: &CheckedProgram, dets: &[Det], picks: &[Det], cap: u64) -> Option<PartKey> {
    let resolved = &program.program;
    let part_det = |det: &Det| {
        let node = resolved.node_content(det.node)?.content_hash();
        let columns = program.types.columns(&GraphRelation { node: det.node, output: None })?.into();
        Some(PartDet { relation: det.relation.clone(), open: det.open, pick: det.pick, node, columns })
    };
    Some(PartKey { cap, dets: dets.iter().map(part_det).collect::<Option<_>>()?, picks: picks.iter().map(part_det).collect::<Option<_>>()? })
}

struct Kept {
    /// The count of intern tables that `terms` replaced. A walk that began
    /// under another count holds the term ids of a replaced table, and takes
    /// and keeps no domain.
    generation: u64,
    /// A session that holds the shared intern table and fact relations.
    terms: TaskSession,
    domains: StableHashMap<Key, Vec<Arc<Computed>>>,
    /// One relation for each rows and columns of parts that the kept
    /// domains hold, so that the relations a later walk compares share
    /// their storage.
    relations: StableHashMap<StableHash, Vec<Arc<Relation>>>,
    bytes: usize,
}

/// A domain computed in a walk, and what its computation did there.
struct Computed {
    events: Box<[Recorded]>,
    /// The table work it counted.
    charged: u64,
    domain: Domain,
    /// The keys of the entries that its lookups found, by the ids of their
    /// relations in the session where it ran, for a computation whose
    /// every lookup found its entry ([`crate::session::ResultCache::found_keys`]).
    found: Option<Box<[ResultKey]>>,
}

impl std::fmt::Debug for ProbeMemo {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.debug_struct("ProbeMemo").field("scope", &self.scope).finish_non_exhaustive()
    }
}

impl ProbeMemo {
    /// The memo of the walks of `session` under `scope`, with nothing kept.
    pub(crate) fn new(scope: Scope, session: &TaskSession) -> Self {
        let terms = TaskSession::new(session.bound, session.caps);
        let kept = Kept { generation: 0, terms, domains: StableHashMap::default(), relations: StableHashMap::default(), bytes: 0 };
        ProbeMemo { scope, kept: Mutex::new(kept), parts: Mutex::default() }
    }

    /// What the walk of `key` gave under `scope`, where the memo keeps it.
    pub(crate) fn part(&self, scope: Scope, key: &PartKey) -> Option<PartWalk> {
        let parts = self.parts.lock().expect("the kept walks are not poisoned");
        (scope == self.scope).then(|| parts.get(key).copied()).flatten()
    }

    /// Keeps `walk`, what the walk of `key` gave under `scope`.
    pub(crate) fn keep_part(&self, scope: Scope, key: PartKey, walk: PartWalk) {
        if scope != self.scope {
            return;
        }
        let mut parts = self.parts.lock().expect("the kept walks are not poisoned");
        if parts.len() >= PARTS_KEPT {
            parts.clear();
        }
        parts.insert(key, walk);
    }

    /// The session of one walk of `session` under `scope`, which shares the
    /// intern table and the fact relations, or `None` where the memo serves
    /// another scope.
    pub(crate) fn probe(&self, scope: Scope, session: &TaskSession) -> Option<Probe<'_>> {
        if scope != self.scope {
            return None;
        }
        let mut kept = self.kept.lock().expect("the kept domains are not poisoned");
        if kept.terms.intern.read().expect("an intern table that no panic poisoned").bytes() > TERM_BYTES {
            kept.generation += 1;
            kept.terms = TaskSession::new(session.bound, session.caps);
            kept.clear();
        }
        Some(Probe { memo: self, generation: kept.generation, session: kept.terms.sharing_terms() })
    }

    fn computed(&self, generation: u64, key: &Key) -> Vec<Arc<Computed>> {
        let kept = self.kept.lock().expect("the kept domains are not poisoned");
        if kept.generation != generation {
            return Vec::new();
        }
        kept.domains.get(key).cloned().unwrap_or_default()
    }

    /// Keeps `computed` under `key`, each relation it holds replaced by the
    /// kept relation of the same rows and columns of parts, where one is
    /// kept, and gives its domain so replaced. `None` where it keeps none.
    fn keep(&self, generation: u64, key: Key, computed: Computed) -> Option<Domain> {
        let bytes = computed.events.iter().map(Recorded::bytes).sum::<usize>() + 1024;
        let mut kept = self.kept.lock().expect("the kept domains are not poisoned");
        if kept.generation != generation || bytes > KEPT_BYTES {
            return None;
        }
        if kept.bytes + bytes > KEPT_BYTES {
            kept.clear();
        }
        let kept = &mut *kept;
        if kept.domains.get(&key).is_some_and(|computations| computations.len() >= PER_KEY) {
            return None;
        }
        let mut one = |relation: &Arc<Relation>| kept_relation(&mut kept.relations, relation);
        let key = Key { reads: key.reads.iter().map(|(name, content, value)| (name.clone(), *content, value.as_ref().map(&mut one))).collect(), ..key };
        let events = computed.events.iter().map(|event| event.with_relations(&mut one)).collect();
        let domain = match &computed.domain {
            Domain::Rows(values) => Domain::Rows(values.iter().map(&mut one).collect()),
            other => other.clone(),
        };
        kept.domains.entry(key).or_default().push(Arc::new(Computed { events, charged: computed.charged, domain: domain.clone(), found: None }));
        kept.bytes += bytes;
        Some(domain)
    }
}

impl Kept {
    fn clear(&mut self) {
        self.domains.clear();
        self.relations.clear();
        self.bytes = 0;
    }
}

/// The relation of `relations` with the rows of `relation`, held in parts of
/// the same columns, or `relation`, which `relations` then holds.
fn kept_relation(relations: &mut StableHashMap<StableHash, Vec<Arc<Relation>>>, relation: &Arc<Relation>) -> Arc<Relation> {
    let alike = relations.entry(relation.rows_hash()).or_default();
    let columns = |relation: &Relation| relation.parts().iter().map(|part| part.columns.clone()).collect::<Vec<_>>();
    if let Some(found) = alike.iter().find(|held| columns(held) == columns(relation) && same_rows(held, relation)) {
        return Arc::clone(found);
    }
    alike.push(Arc::clone(relation));
    Arc::clone(relation)
}

/// One liveness walk's session, and the memo it takes domains from.
pub(crate) struct Probe<'m> {
    memo: &'m ProbeMemo,
    generation: u64,
    pub(crate) session: TaskSession,
}

impl Probe<'_> {
    /// The domains of `dets`, the `DET`s of `program` in the order of the
    /// walk, through the memo.
    pub(crate) fn domains<'p>(&'p self, program: &CheckedProgram, dets: &'p [Det]) -> ProbeDomains<'p> {
        ProbeDomains { probe: self, dets, keys: det_keys(program, dets) }
    }
}

/// The parts of the key of each of `dets`, the `DET`s of `program` in the
/// order of a walk, that its values leave out, or `None` for a `DET` whose
/// domain is computed with no memo: a pick, and each `DET` of a program
/// whose graph has a cycle.
fn det_keys(program: &CheckedProgram, dets: &[Det]) -> Vec<Option<DetKey>> {
    let resolved = &program.program;
    let acyclic = resolved.graph.find_cycle().is_none();
    dets.iter()
        .enumerate()
        .map(|(at, det)| {
            if !acyclic || det.pick {
                return None;
            }
            let node = resolved.node_content(det.node)?.content_hash();
            let columns = program.types.columns(&GraphRelation { node: det.node, output: None })?.into();
            let reached = resolved.graph.reached(det.node);
            let reads = dets[..at]
                .iter()
                .enumerate()
                .filter(|(_, read)| reached[read.node.0 as usize])
                .map(|(index, read)| Some((index, resolved.node_content(read.node)?.content_hash())))
                .collect::<Option<Vec<_>>>()?;
            Some(DetKey { node, columns, reads })
        })
        .collect()
}

/// The key of the domain of `dets[at]`, whose key parts are `det`, at the
/// values `assigned` of the `DET`s before it.
fn key_at(dets: &[Det], det: &DetKey, assigned: &[Assignment]) -> Key {
    let reads = det.reads.iter().map(|&(index, content)| {
        let relation = &dets[index].relation;
        let value = assigned.iter().find(|(name, _)| name == relation).map(|(_, value)| Arc::clone(value));
        (relation.clone(), content, value)
    });
    Key { node: det.node, columns: det.columns.clone(), reads: reads.collect() }
}

/// The domains of the `DET`s of one walk.
pub(crate) struct ProbeDomains<'p> {
    probe: &'p Probe<'p>,
    dets: &'p [Det],
    /// The parts of each `DET`'s key that its values leave out, or `None`
    /// where its domain is computed with no memo.
    keys: Vec<Option<DetKey>>,
}

struct DetKey {
    node: StableHash,
    columns: Box<[ValueType]>,
    /// Each `DET` before it in the walk that it reads at any depth, by its
    /// index in the walk, with that `DET`'s content.
    reads: Vec<(usize, StableHash)>,
}

/// The key of a domain: the content of the `DET`'s node, which holds the
/// content of each of its forms and, at any depth, of each relation they
/// read; the types of its columns, by which the domain orders its values;
/// and each `DET` it reads at any depth that the walk assigns before it,
/// by its relation and its content, with its value, or none where the walk
/// left it unassigned.
struct Key {
    node: StableHash,
    columns: Box<[ValueType]>,
    reads: Box<[(ProgramRelation, StableHash, Option<Arc<Relation>>)]>,
}

impl Hash for Key {
    fn hash<H: Hasher>(&self, state: &mut H) {
        self.node.hash(state);
        self.columns.hash(state);
        for (relation, content, value) in self.reads.iter() {
            relation.hash(state);
            content.hash(state);
            value.as_ref().map(|value| value.rows_hash()).hash(state);
        }
    }
}

impl PartialEq for Key {
    fn eq(&self, other: &Key) -> bool {
        let value = |a: &Option<Arc<Relation>>, b: &Option<Arc<Relation>>| match (a, b) {
            (None, None) => true,
            (Some(a), Some(b)) => a.rows_hash() == b.rows_hash() && same_rows(a, b),
            _ => false,
        };
        self.node == other.node
            && self.columns == other.columns
            && self.reads.len() == other.reads.len()
            && self.reads.iter().zip(other.reads.iter()).all(|(a, b)| a.0 == b.0 && a.1 == b.1 && value(&a.2, &b.2))
    }
}

impl Eq for Key {}

impl Domains for ProbeDomains<'_> {
    fn domain(&self, evaluation: &Evaluation<'_>, at: usize, assigned: &[Assignment]) -> Outcome<Domain> {
        let node = self.dets[at].node;
        let (Some(det), Some(work)) = (&self.keys[at], &evaluation.limits.table_work) else {
            return evaluation.domain(node);
        };
        let key = key_at(self.dets, det, assigned);
        let session = evaluation.session;
        let memo = self.probe.memo;
        for computed in memo.computed(self.probe.generation, &key) {
            if work.fits(computed.charged) && replay(session, &computed.events) {
                work.charge(computed.charged).expect("a count that stays within the cap");
                return Ok(computed.domain.clone());
            }
        }
        session.results.start_recording();
        let before = work.count();
        let found = evaluation.domain(node);
        let events = session.results.take_recorded();
        let charged = work.count() - before;
        if let Ok(domain @ (Domain::Rows(_) | Domain::Undefined)) = &found {
            let computed = Computed { events: events.into(), charged, domain: domain.clone(), found: None };
            if let Some(domain) = memo.keep(self.probe.generation, key, computed) {
                // The kept values hold the rows of the values computed, in
                // parts of the same columns.
                return Ok(domain);
            }
        }
        found
    }
}

/// The most bytes that the domains kept for a session's table walks hold,
/// by [`Recorded::bytes`] and the estimate of each value's rows; past it,
/// the walks keep none of those kept so far.
const SESSION_KEPT_BYTES: usize = 1 << 26;

/// The domains that the table walks of one task session's decodes compute
/// in the session itself ([`super::Decoder::assigned`]), kept across those
/// walks.
///
/// A domain is kept only where its computation found in the session's
/// result cache each entry it looked up, and so stored none: it read
/// nothing that the cache did not hold, and so ran no evaluation that
/// reads a held stop or reports a copy violation. Its lookups are those
/// this thread made, so a computation on another thread adds none. A later
/// walk that needs the domain of a `DET` of the same key ([`Key`]) takes
/// the kept domain where each kept lookup would find in the cache a value
/// of the same rows, held in parts of the same columns, and where its count
/// stays within the cap after the work the computation counted. The
/// computation reads nothing else that differs between the walks, so it
/// would make those lookups and count that work in the later walk too, and
/// give a domain of the same values: each value holds its rows in the
/// content order of their terms, whatever the order of the rows it read.
/// The later walk then makes those lookups and counts that work, so the
/// cache and the count stand as the computation would leave them.
/// Otherwise it computes the domain.
pub(crate) struct SessionMemo {
    scope: Scope,
    kept: Mutex<SessionKept>,
}

#[derive(Default)]
struct SessionKept {
    domains: StableHashMap<Key, Vec<Arc<Computed>>>,
    bytes: usize,
}

impl std::fmt::Debug for SessionMemo {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.debug_struct("SessionMemo").field("scope", &self.scope).finish_non_exhaustive()
    }
}

impl SessionMemo {
    /// The memo of the table walks of a session under `scope`, with
    /// nothing kept.
    pub(crate) fn new(scope: Scope) -> Self {
        SessionMemo { scope, kept: Mutex::new(SessionKept::default()) }
    }

    /// The domains of `dets`, the `DET`s of `program` in the order of a
    /// walk under `scope`, through the memo, or `None` where the memo
    /// serves another scope.
    pub(crate) fn domains<'p>(&'p self, scope: Scope, program: &CheckedProgram, dets: &'p [Det]) -> Option<SessionDomains<'p>> {
        (scope == self.scope).then(|| SessionDomains { memo: self, dets, keys: det_keys(program, dets) })
    }

    fn computed(&self, key: &Key) -> Vec<Arc<Computed>> {
        self.kept.lock().expect("the kept domains are not poisoned").domains.get(key).cloned().unwrap_or_default()
    }

    fn keep(&self, key: Key, computed: Computed) {
        let values = match &computed.domain {
            Domain::Rows(values) => values.iter().map(|value| relation_estimate(value)).sum(),
            _ => 0,
        };
        let bytes = computed.events.iter().map(Recorded::bytes).sum::<usize>() + values + 1024;
        let mut kept = self.kept.lock().expect("the kept domains are not poisoned");
        if bytes > SESSION_KEPT_BYTES {
            return;
        }
        if kept.bytes + bytes > SESSION_KEPT_BYTES {
            *kept = SessionKept::default();
        }
        let computations = kept.domains.entry(key).or_default();
        if computations.len() >= PER_KEY {
            return;
        }
        computations.push(Arc::new(computed));
        kept.bytes += bytes;
    }
}

/// The domains of the `DET`s of one table walk.
pub(crate) struct SessionDomains<'p> {
    memo: &'p SessionMemo,
    dets: &'p [Det],
    keys: Vec<Option<DetKey>>,
}

impl Domains for SessionDomains<'_> {
    fn domain(&self, evaluation: &Evaluation<'_>, at: usize, assigned: &[Assignment]) -> Outcome<Domain> {
        let node = self.dets[at].node;
        let (Some(det), Some(work)) = (&self.keys[at], &evaluation.limits.table_work) else {
            return evaluation.domain(node);
        };
        let key = key_at(self.dets, det, assigned);
        let session = evaluation.session;
        for computed in self.memo.computed(&key) {
            let replayed = || match &computed.found {
                Some(keys) if session.results.replay_found(&computed.events, keys) => true,
                _ => replay(session, &computed.events),
            };
            if work.fits(computed.charged) && replayed() {
                work.charge(computed.charged).expect("a count that stays within the cap");
                return Ok(computed.domain.clone());
            }
        }
        let Some(recording) = session.results.record_on_thread() else {
            return evaluation.domain(node);
        };
        let before = work.count();
        let found = evaluation.domain(node);
        let events = recording.finish();
        let charged = work.count() - before;
        let pure = events.iter().all(|event| matches!(event, Recorded::Lookup { found: Some(_), .. }));
        let (true, Ok(domain @ (Domain::Rows(_) | Domain::Undefined))) = (pure, &found) else {
            return found;
        };
        // The relations that the cache holds in place of those of the same
        // rows: a key's, which a lookup reads by its rows alone, and a
        // value's that the cache holds laid out as the value is, which no
        // read tells apart from it. A later lookup then finds them by
        // their storage, with no comparison of rows.
        let results = &session.results;
        let held = |relation: &Arc<Relation>| results.held_relation(relation).unwrap_or_else(|| Arc::clone(relation));
        let events: Box<[Recorded]> = events
            .iter()
            .map(|event| match event {
                Recorded::Lookup { key, found } => Recorded::Lookup {
                    key: RecordedKey { reads: key.reads.iter().map(held).collect(), parameters: key.parameters.iter().map(held).collect(), ..key.clone() },
                    found: found.clone(),
                },
                other => other.clone(),
            })
            .collect();
        let domain = match domain {
            Domain::Rows(values) => Domain::Rows(
                values
                    .iter()
                    .map(|value| match results.held_relation(value) {
                        Some(kept) if kept.laid_out_as(value) => kept,
                        _ => Arc::clone(value),
                    })
                    .collect(),
            ),
            other => other.clone(),
        };
        let found = results.found_keys(&events);
        self.memo.keep(key, Computed { events, charged, domain: domain.clone(), found });
        Ok(domain)
    }
}
