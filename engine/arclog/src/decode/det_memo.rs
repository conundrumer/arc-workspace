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
//! each relation it gave an id; each store; and its [`Cost`], the work it
//! charged and the largest counts it noted.
//! A later walk that needs the domain of a `DET` of the same key ([`Key`])
//! takes the kept domain where each kept lookup would find in its own cache
//! a value of the same rows, held in parts of the same columns, where it
//! found one, and nothing where it found nothing, and where its request work
//! and table work stay within their caps after its cost. The computation
//! reads nothing else that differs between the walks, so it would make those
//! lookups, ids and stores, and charge that cost, in the later walk too. The
//! later walk then makes them and charges that cost, so its cache and its
//! counts stand as the computation would leave them. Otherwise it computes
//! the domain.
//!
//! A walk asks for only the count of a `DET`'s values where no later step
//! reads the values ([`crate::judge::determination::descend_unread`]). The
//! memo keeps the computation of such a count as a computation that gave the
//! count, with the same lookups, ids, stores and table work that the
//! computation of the domain has. A walk that asks for the count takes a kept
//! domain too, and a walk that asks for the values takes no kept count.
//!
//! The memo holds its domains in two tiers, each with at most half of the
//! share of the byte bound that [`KEPT_SHARE`] gives, counting each relation
//! of a tier once, by its rows, however many events and values hold it. A
//! domain is kept in the young tier. Where the young tier has no room for
//! it, the young tier becomes the old one, and the old one is dropped. A walk
//! that asks for a key that the old tier holds moves its domains into the
//! young tier, so a domain that walks ask for at least once between two
//! such turns stays, and the domains that one walk keeps and none asks for
//! again, such as those of a form that the decode does not write, leave
//! with the turns. A walk that takes a kept domain makes the lookups, ids
//! and stores, and charges the cost, that its computation would, so the
//! domains that stay change the time of a walk and no verdict nor count.
//!
//! The shared intern table counts toward the byte bound of each walk's
//! session, and a value kept from another walk can hold its rows apart from
//! a value that a computation would build on them, so a walk's session
//! holds at least the bytes that a session of its own would hold. A walk
//! whose cache evicts, runs again in a
//! session of its own with no kept domain ([`super::det_admission`]).
//!
//! A walk that computes a domain that no kept domain stands for evaluates the
//! entries of its forms, each a part of a body or a clause. The memo also keeps
//! the computation of each such entry, in a store of its own that stands as long
//! as the intern table that the walks share ([`CarryStore`], [`Probe::carry`]),
//! and a walk takes a kept computation of an entry in place of computing it. The
//! domains of two candidate bodies then share the computations of the parts that
//! the candidates leave unchanged. The module [`crate::eval::carry`] gives what
//! each key holds, and why it decides its computation.
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
use crate::eval::cache::{relation_estimate, replay, replay_recorded, Recorded, RecordedKey};
use crate::eval::carry::{kept_relation, Carry, CarryStore};
use crate::eval::determinations::det_relation;
use crate::eval::{Charged, Cost, Domain, DomainSize, Evaluation, Hit, Outcome, Stop};
use crate::hash::{StableHash, StableHashMap, StableHasher};
use crate::judge::determination::{Assignment, Det, Domains};
use crate::program::canonical::{CanonicalOrder, SearchBudget};
use crate::program::ProgramRelation;
use crate::relations::Relation;
use crate::resolver::GraphNodeIndex;
use crate::session::{same_rows, ResultKey, TaskSession};
use crate::types::ValueType;
use crate::types::GraphRelation;

/// The fraction of the session's byte bound that the kept domains may hold,
/// by [`Tier::bytes_of`]: the bytes of the relations of both tiers, and the
/// bytes of the events.
const KEPT_SHARE: usize = 16;

/// The count of tiers of the kept domains, each of which may hold an equal
/// share of [`KEPT_SHARE`].
const TIERS: usize = 2;

/// The bytes that the memo counts for an event, beside its relations.
const EVENT_BYTES: usize = 256;

/// The fraction of the session's byte bound that the shared intern table may
/// hold; past it, the next walk starts a new intern table, and no domain kept
/// with the old one is taken.
const TERM_SHARE: usize = 16;

/// The fraction of the session's byte bound that the kept computations of
/// entries ([`crate::eval::carry`]) may hold, in both their tiers.
///
/// A kept computation holds the relations its entry reads and gives, so it
/// takes megabytes, and a tier turns, and drops what it holds that no walk has
/// asked for since, each time the walks have kept a tier's share of bytes. A
/// walk that asks for a computation after more bytes of later computations than
/// the two tiers hold computes it again. These bytes stand outside the walks'
/// ledger, so beside the session's bound the process holds the share of
/// [`KEPT_SHARE`] and this one.
const CARRY_SHARE: usize = 4;

/// The most computations kept for one key, each with its own lookups.
const PER_KEY: usize = 4;

/// The most walks of parts kept; past it, the walks keep none of those kept
/// so far.
const PARTS_KEPT: usize = 1 << 16;

/// What the computation of a domain reads beside its key, the same for
/// each walk of the task session: the task, the registry, the
/// constructions, by their addresses, the table work cap and the prefix
/// content cap. The caps and the byte bound are the session's.
#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub(crate) struct Scope {
    pub(crate) task: usize,
    pub(crate) registry: usize,
    pub(crate) constructions: usize,
    pub(crate) table_work_cap: u64,
    pub(crate) prefix_content_cap: u64,
}

/// The domains kept for the liveness walks of one task session.
pub(crate) struct ProbeMemo {
    scope: Scope,
    kept_bytes: usize,
    term_bytes: usize,
    carry_bytes: usize,
    kept: Mutex<Kept>,
    parts: Mutex<StableHashMap<PartKey, (PartWalk, Cost)>>,
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
/// at any depth, of each relation they read, the types of its columns, and
/// the forms it reads ([`forms_read`]).
#[derive(PartialEq, Eq, Hash)]
struct PartDet {
    relation: ProgramRelation,
    open: bool,
    pick: bool,
    node: StableHash,
    columns: Box<[ValueType]>,
    forms: Option<Box<[StableHash]>>,
}

/// The key of the walk of `dets` with `picks` in `program`, a program with no
/// cycle, under the assignment cap `cap`, or `None` where one of them has no
/// content or no column types.
pub(crate) fn part_key(program: &CheckedProgram, dets: &[Det], picks: &[Det], cap: u64) -> Option<PartKey> {
    let resolved = &program.program;
    let part_det = |det: &Det| {
        let node = resolved.node_content(det.node)?.content_hash();
        let columns = program.types.columns(&GraphRelation { node: det.node, output: None })?.into();
        let forms = forms_read(program, &resolved.graph.reached(det.node));
        Some(PartDet { relation: det.relation.clone(), open: det.open, pick: det.pick, node, columns, forms })
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
    /// The computations of entries kept with the walks that began under this
    /// count ([`CarryStore`]).
    carry: Arc<CarryStore>,
    /// The domains kept since the last turn of the memo, and those it
    /// kept before that turn that a walk asked for since.
    young: Tier,
    /// The domains kept before the last turn that no walk has asked for
    /// since. The next turn drops them.
    old: Tier,
}

/// The kept domains of one span of the memo's life, with one relation for
/// each rows and columns of parts that they hold, so that the relations a
/// later walk compares share their storage, and the bytes they hold.
#[derive(Default)]
struct Tier {
    domains: StableHashMap<Key, Vec<Arc<Computed>>>,
    relations: StableHashMap<StableHash, Vec<Arc<Relation>>>,
    /// The bytes of the computations kept, by [`Tier::fresh_bytes`] at the
    /// time each was kept.
    bytes: usize,
}

/// A domain computed in a walk, and what its computation did there.
struct Computed {
    events: Box<[Recorded]>,
    /// What it charged, which a walk that takes it charges again.
    cost: Cost,
    given: Given,
    /// The keys of the entries that its lookups found, by the ids of their
    /// relations in the session where it ran, for a computation whose
    /// every lookup found its entry ([`crate::session::ResultCache::found_keys`]).
    found: Option<Box<[ResultKey]>>,
}

/// What a computation of a domain gave: the domain, or only its count of
/// values ([`Domains::size`]), which a walk asks for where no later step
/// reads the values. The computations of both do the same in the session and
/// the count of work.
#[derive(Clone)]
enum Given {
    Values(Domain),
    Size(DomainSize),
}

impl Given {
    /// The domain, where this holds it.
    fn values(&self) -> Option<&Domain> {
        match self {
            Given::Values(domain) => Some(domain),
            Given::Size(_) => None,
        }
    }

    /// The count of values, which a domain gives as the length of its rows.
    fn size(&self) -> DomainSize {
        match self {
            Given::Values(Domain::Rows(values)) => DomainSize::Count(values.len()),
            Given::Values(Domain::Undefined) => DomainSize::Undefined,
            Given::Values(Domain::Stopped(stop)) => DomainSize::Stopped(stop.clone()),
            Given::Size(size) => size.clone(),
        }
    }
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
        let bytes = session.bound.bytes;
        let kept = Kept { generation: 0, terms, carry: Arc::new(CarryStore::new(bytes / CARRY_SHARE)), young: Tier::default(), old: Tier::default() };
        ProbeMemo { scope, kept_bytes: bytes / KEPT_SHARE, term_bytes: bytes / TERM_SHARE, carry_bytes: bytes / CARRY_SHARE, kept: Mutex::new(kept), parts: Mutex::default() }
    }

    /// The bytes the memo counts, its count of relations, the bytes of their
    /// indexes, and the bytes of the shared intern table.
    pub(crate) fn stats(&self) -> (usize, usize, usize, usize) {
        let kept = self.kept.lock().expect("the kept domains are not poisoned");
        let relations = || kept.young.relations.values().chain(kept.old.relations.values()).flatten();
        let intern = kept.terms.intern.read().expect("an intern table that no panic poisoned").bytes();
        (kept.young.bytes + kept.old.bytes, relations().count(), relations().map(|relation| relation.index_bytes().1).sum(), intern)
    }

    /// What the walk of `key` gave under `scope`, where the memo keeps it.
    pub(crate) fn part(&self, scope: Scope, key: &PartKey) -> Option<Hit<PartWalk>> {
        let parts = self.parts.lock().expect("the kept walks are not poisoned");
        (scope == self.scope).then(|| parts.get(key).copied()).flatten().map(|(walk, cost)| Hit::new(walk, cost))
    }

    /// Keeps `walk`, what the walk of `key` gave under `scope`, with the `cost`
    /// of the walk.
    pub(crate) fn keep_part(&self, scope: Scope, key: PartKey, walk: PartWalk, cost: Cost) {
        if scope != self.scope {
            return;
        }
        let mut parts = self.parts.lock().expect("the kept walks are not poisoned");
        if parts.len() >= PARTS_KEPT {
            parts.clear();
        }
        parts.insert(key, (walk, cost));
    }

    /// The session of one walk of `session` under `scope`, which shares the
    /// intern table and the fact relations, or `None` where the memo serves
    /// another scope.
    pub(crate) fn probe(&self, scope: Scope, session: &TaskSession) -> Option<Probe<'_>> {
        if scope != self.scope {
            return None;
        }
        let mut kept = self.kept.lock().expect("the kept domains are not poisoned");
        if kept.terms.intern.read().expect("an intern table that no panic poisoned").bytes() > self.term_bytes {
            kept.generation += 1;
            kept.terms = TaskSession::new(session.bound, session.caps);
            kept.carry = Arc::new(CarryStore::new(self.carry_bytes));
            kept.clear();
        }
        Some(Probe { memo: self, generation: kept.generation, session: kept.terms.sharing_terms(), carry: Arc::clone(&kept.carry) })
    }

    /// The computations kept under `key`, those of the old tier moved into
    /// the young one where it holds their bytes within its share.
    fn computed(&self, generation: u64, key: &Key) -> Vec<Arc<Computed>> {
        let mut kept = self.kept.lock().expect("the kept domains are not poisoned");
        if kept.generation != generation {
            return Vec::new();
        }
        let kept = &mut *kept;
        let mut found = kept.young.domains.get(key).cloned().unwrap_or_default();
        let Some((held, aged)) = kept.old.domains.remove_entry(key) else { return found };
        let fresh = kept.young.fresh_bytes(&key.values, aged.iter().map(|computed| &**computed));
        if kept.young.bytes + fresh <= self.kept_bytes / TIERS {
            let mut one = |relation: &Arc<Relation>| kept_relation(&mut kept.young.relations, relation);
            let moved = aged.iter().map(|computed| Arc::new(computed.with_relations(&mut one))).collect::<Vec<_>>();
            let held = Key { shape: held.shape, values: held.values.iter().map(|value| value.as_ref().map(&mut one)).collect() };
            let room = PER_KEY.saturating_sub(found.len());
            kept.young.domains.entry(held).or_default().extend(moved.iter().take(room).cloned());
            kept.young.bytes += fresh;
            found.extend(moved.into_iter().take(room));
        } else {
            found.extend(aged.iter().cloned());
            kept.old.domains.insert(held, aged);
        }
        found
    }

    /// Keeps `computed` under `key`, each relation it holds replaced by the
    /// kept relation of the same rows and columns of parts, where one is
    /// kept, and gives what it gave so replaced. `None` where it keeps none.
    ///
    /// The young tier holds at most its share of the bytes. Where `computed`
    /// does not fit, the young tier becomes the old one, which drops the old
    /// tier it replaces.
    fn keep(&self, generation: u64, key: Key, computed: Computed) -> Option<Given> {
        let mut kept = self.kept.lock().expect("the kept domains are not poisoned");
        if kept.generation != generation {
            return None;
        }
        let kept = &mut *kept;
        if kept.young.domains.get(&key).is_some_and(|computations| computations.len() >= PER_KEY) {
            return None;
        }
        let share = self.kept_bytes / TIERS;
        let (alone, mut fresh) = kept.young.alone_and_fresh_bytes(&key.values, &computed);
        if alone > share {
            return None;
        }
        if kept.young.bytes + fresh > share {
            kept.old = std::mem::take(&mut kept.young);
            fresh = alone;
        }
        let young = &mut kept.young;
        let mut one = |relation: &Arc<Relation>| kept_relation(&mut young.relations, relation);
        let key = Key { values: key.values.iter().map(|value| value.as_ref().map(&mut one)).collect(), shape: key.shape };
        let kept_computed = computed.with_relations(&mut one);
        let given = kept_computed.given.clone();
        young.domains.entry(key).or_default().push(Arc::new(kept_computed));
        young.bytes += fresh;
        Some(given)
    }
}

impl Kept {
    fn clear(&mut self) {
        self.young = Tier::default();
        self.old = Tier::default();
    }
}

impl Tier {
    /// The bytes that keeping `computed`, a computation of the domain at
    /// the key values `values`, adds to this tier: its events' bytes less
    /// those of each relation that the tier holds already, each count of a
    /// relation once, by its rows' hash. Also the bytes it adds to an empty
    /// tier.
    fn alone_and_fresh_bytes(&self, values: &[Option<Arc<Relation>>], computed: &Computed) -> (usize, usize) {
        self.bytes_of(values, std::iter::once(computed))
    }

    fn fresh_bytes<'c>(&self, values: &[Option<Arc<Relation>>], computed: impl Iterator<Item = &'c Computed>) -> usize {
        self.bytes_of(values, computed).1
    }

    fn bytes_of<'c>(&self, values: &[Option<Arc<Relation>>], computed: impl Iterator<Item = &'c Computed>) -> (usize, usize) {
        let mut seen = crate::hash::StableHashSet::default();
        let mut sizes = (0, 0);
        let mut count = |relation: &Arc<Relation>| {
            let hash = relation.rows_hash();
            if !seen.insert(hash) {
                return;
            }
            let bytes = relation_estimate(relation);
            sizes.0 += bytes;
            let held = self.relations.get(&hash).is_some_and(|alike| alike.iter().any(|held| held.arity() == relation.arity() && held.len() == relation.len()));
            if !held {
                sizes.1 += bytes;
            }
        };
        let mut events = 0;
        values.iter().flatten().for_each(&mut count);
        for computed in computed {
            events += computed.events.len();
            computed.events.iter().for_each(|event| event.each_relation(&mut count));
            if let Some(Domain::Rows(rows)) = computed.given.values() {
                rows.iter().for_each(&mut count);
            }
        }
        let overhead = 1024 + EVENT_BYTES * events;
        (sizes.0 + overhead, sizes.1 + overhead)
    }
}

impl Computed {
    /// `value`, as a hit that charges the cost of this computation.
    fn hit<T>(&self, value: T) -> Hit<T> {
        Hit::new(value, self.cost)
    }

    /// This computation with each relation it holds replaced by `one` of it.
    fn with_relations(&self, one: &mut impl FnMut(&Arc<Relation>) -> Arc<Relation>) -> Computed {
        let given = match &self.given {
            Given::Values(Domain::Rows(values)) => Given::Values(Domain::Rows(values.iter().map(&mut *one).collect())),
            other => other.clone(),
        };
        Computed { events: self.events.iter().map(|event| event.with_relations(&mut *one)).collect(), cost: self.cost, given, found: None }
    }
}

/// One liveness walk's session, and the memo it takes domains from.
pub(crate) struct Probe<'m> {
    memo: &'m ProbeMemo,
    generation: u64,
    pub(crate) session: TaskSession,
    /// The kept computations of entries of the intern table that `session`
    /// shares.
    carry: Arc<CarryStore>,
}

impl Probe<'_> {
    /// The kept computations of entries that this walk takes, and keeps its
    /// own in, as [`crate::eval::carry`] gives. They hold the term ids of the
    /// intern table that this walk shares, and no walk that shares another
    /// table reaches them.
    pub(crate) fn carry(&self) -> Carry {
        Carry::new(Arc::clone(&self.carry))
    }

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
            let read = dets[..at]
                .iter()
                .enumerate()
                .filter(|(_, read)| reached[read.node.0 as usize])
                .map(|(index, read)| Some((index, resolved.node_content(read.node)?.content_hash())))
                .collect::<Option<Vec<_>>>()?;
            let forms = forms_read(program, &reached);
            let reads = read.iter().map(|&(index, content)| (dets[index].relation.clone(), content)).collect();
            let shape = Arc::new(KeyShape::new(node, columns, reads, forms));
            Some(DetKey { shape, reads: read.into_iter().map(|(index, _)| index).collect() })
        })
        .collect()
}

/// The hashes of the forms as written, in no order, that give the nodes of
/// `program` that `reached` marks, a node and each node it reads at any
/// depth, where two `DET`s among those nodes have one content; `None` where
/// no two do. A node's content writes each relation it reads as that
/// relation's content, so it tells which `DET` each read reads only where no
/// two of them have one content. A form as written names each relation it
/// reads, so the forms tell it in each case.
fn forms_read(program: &CheckedProgram, reached: &[bool]) -> Option<Box<[StableHash]>> {
    let resolved = &program.program;
    let nodes = || (0..resolved.graph.nodes.len()).filter(|&node| reached[node]).map(|node| GraphNodeIndex(node as u32));
    let contents = nodes()
        .filter(|node| det_relation(&resolved.graph.nodes[node.0 as usize].kind).is_some())
        .map(|node| Some(resolved.node_content(node)?.content_hash().0))
        .collect::<Option<Vec<_>>>();
    if let Some(mut contents) = contents {
        contents.sort_unstable();
        if contents.windows(2).all(|pair| pair[0] != pair[1]) {
            return None;
        }
    }
    let mut tops: Vec<usize> = nodes().flat_map(|node| resolved.forms_of(node)).filter_map(|path| path.0.first()).map(|step| step.0 as usize).collect();
    tops.sort_unstable();
    tops.dedup();
    let forms = &resolved.program.value().forms;
    let mut written: Vec<StableHash> = tops.iter().map(|&top| CanonicalOrder::with_form(&forms[top], &mut SearchBudget::new()).1.hash).collect();
    written.sort_unstable_by_key(|hash| hash.0);
    Some(written.into())
}

/// The key of the domain of `dets[at]`, whose key parts are `det`, at the
/// values `assigned` of the `DET`s before it.
fn key_at(dets: &[Det], det: &DetKey, assigned: &[Assignment]) -> Key {
    let value = |&index: &usize| {
        let relation = &dets[index].relation;
        assigned.iter().find(|(name, _)| name == relation).map(|(_, value)| Arc::clone(value))
    };
    Key { shape: Arc::clone(&det.shape), values: det.reads.iter().map(value).collect() }
}

/// The domains of the `DET`s of one walk.
pub(crate) struct ProbeDomains<'p> {
    probe: &'p Probe<'p>,
    dets: &'p [Det],
    /// The parts of each `DET`'s key that its values leave out, or `None`
    /// where its domain is computed with no memo.
    keys: Vec<Option<DetKey>>,
}

/// The parts of the key of a `DET`'s domain that its values leave out.
struct DetKey {
    shape: Arc<KeyShape>,
    /// Each `DET` before it in the walk that it reads at any depth, by its
    /// index in the walk.
    reads: Vec<usize>,
}

/// What the keys of one `DET`'s domain hold beside the values of the `DET`s
/// that it reads: the content of its node, which holds the content of each
/// of its forms and, at any depth, of each relation they read; the types of
/// its columns, by which the domain orders its values; each `DET` it reads
/// at any depth that the walk assigns before it, by its relation and its
/// content; and the forms it reads ([`forms_read`]), which tell which of
/// those `DET`s each of its reads reads where the content does not.
///
/// The hash of these parts is taken once, where the shape is made, and not
/// at each lookup of a key.
struct KeyShape {
    node: StableHash,
    columns: Box<[ValueType]>,
    reads: Box<[(ProgramRelation, StableHash)]>,
    forms: Option<Box<[StableHash]>>,
    /// The hash of the parts above.
    digest: StableHash,
}

impl KeyShape {
    fn new(node: StableHash, columns: Box<[ValueType]>, reads: Box<[(ProgramRelation, StableHash)]>, forms: Option<Box<[StableHash]>>) -> Self {
        let mut hasher = StableHasher::new();
        node.hash(&mut hasher);
        columns.hash(&mut hasher);
        reads.hash(&mut hasher);
        forms.hash(&mut hasher);
        KeyShape { node, columns, reads, forms, digest: hasher.finish128() }
    }
}

impl PartialEq for KeyShape {
    fn eq(&self, other: &KeyShape) -> bool {
        self.digest == other.digest && self.node == other.node && self.columns == other.columns && self.reads == other.reads && self.forms == other.forms
    }
}

/// The key of a domain: its [`KeyShape`], and the value of each `DET` of
/// the shape's reads, in their order, or none where the walk left it
/// unassigned.
struct Key {
    shape: Arc<KeyShape>,
    values: Box<[Option<Arc<Relation>>]>,
}

impl Hash for Key {
    fn hash<H: Hasher>(&self, state: &mut H) {
        self.shape.digest.hash(state);
        for value in self.values.iter() {
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
        (Arc::ptr_eq(&self.shape, &other.shape) || self.shape == other.shape)
            && self.values.len() == other.values.len()
            && self.values.iter().zip(other.values.iter()).all(|(a, b)| value(a, b))
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
        let limits = evaluation.limits;
        for computed in memo.computed(self.probe.generation, &key) {
            let Some(domain) = computed.given.values() else { continue };
            match computed.hit(domain).charge_if(&limits.request, Some(work), session, || replay(session, &computed.events)) {
                Charged::Value(domain) => return Ok(domain.clone()),
                Charged::Stopped(_, bound) => return Ok(Domain::Stopped(Stop { bound, form: evaluation.program.program.form_of(node).clone() })),
                Charged::Misfit => {}
            }
        }
        let capture = session.results.begin_capture();
        let (found, cost) = limits.request.measure(|| evaluation.domain(node));
        let (events, _) = session.results.end_capture(capture);
        if let Ok(domain @ (Domain::Rows(_) | Domain::Undefined)) = &found {
            let computed = Computed { events: events.into(), cost, given: Given::Values(domain.clone()), found: None };
            if let Some(Given::Values(domain)) = memo.keep(self.probe.generation, key, computed) {
                // The kept values hold the rows of the values computed, in
                // parts of the same columns.
                return Ok(domain);
            }
        }
        found
    }

    /// The count of values that the domain would give, from a kept
    /// computation of the domain or of its count, or else from the count
    /// computed alone ([`Evaluation::domain_size`]). A computation that gave
    /// only the count is kept as that. A walk that asks for the values does
    /// not take it, and computes and keeps the domain, which a later walk
    /// that asks for the count takes. A computation of the count does in the
    /// session and the count of work what that of the domain does, so the
    /// replay of either leaves both as the other would.
    fn size(&self, evaluation: &Evaluation<'_>, at: usize, assigned: &[Assignment]) -> Outcome<DomainSize> {
        let node = self.dets[at].node;
        let (Some(det), Some(work)) = (&self.keys[at], &evaluation.limits.table_work) else {
            return evaluation.domain_size(node);
        };
        let key = key_at(self.dets, det, assigned);
        let session = evaluation.session;
        let memo = self.probe.memo;
        let limits = evaluation.limits;
        for computed in memo.computed(self.probe.generation, &key) {
            match computed.hit(&computed.given).charge_if(&limits.request, Some(work), session, || replay(session, &computed.events)) {
                Charged::Value(given) => return Ok(given.size()),
                Charged::Stopped(_, bound) => return Ok(DomainSize::Stopped(Stop { bound, form: evaluation.program.program.form_of(node).clone() })),
                Charged::Misfit => {}
            }
        }
        let capture = session.results.begin_capture();
        let (found, cost) = limits.request.measure(|| evaluation.domain_size(node));
        let (events, _) = session.results.end_capture(capture);
        if let Ok(size @ (DomainSize::Count(_) | DomainSize::Undefined)) = &found {
            memo.keep(self.probe.generation, key, Computed { events: events.into(), cost, given: Given::Size(size.clone()), found: None });
        }
        found
    }
}

/// The most bytes that the domains kept for a session's table walks hold,
/// by [`Recorded::bytes`] and the estimate of each value's rows; past it,
/// the walks keep none of those kept so far.
const SESSION_KEPT_SHARE: usize = 64;

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
/// of the same rows, held in parts of the same columns, and where its request
/// work and table work stay within their caps after the computation's cost.
/// The computation reads nothing else that differs between the walks, so it
/// would make those lookups and charge that cost in the later walk too, and
/// give a domain of the same values: each value holds its rows in the
/// content order of their terms, whatever the order of the rows it read.
/// The later walk then makes those lookups and charges that cost, so the
/// cache and the counts stand as the computation would leave them.
/// Otherwise it computes the domain.
pub(crate) struct SessionMemo {
    scope: Scope,
    kept_bytes: usize,
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
    pub(crate) fn new(scope: Scope, session: &TaskSession) -> Self {
        SessionMemo { scope, kept_bytes: session.bound.bytes / SESSION_KEPT_SHARE, kept: Mutex::new(SessionKept::default()) }
    }

    /// The domains of `dets`, the `DET`s of `program` in the order of a
    /// walk under `scope`, through the memo, or `None` where the memo
    /// serves another scope.
    pub(crate) fn domains<'p>(&'p self, scope: Scope, program: &CheckedProgram, dets: &'p [Det]) -> Option<SessionDomains<'p>> {
        (scope == self.scope).then(|| SessionDomains { memo: self, dets, keys: det_keys(program, dets) })
    }

    /// The bytes the memo counts and its count of domains.
    pub(crate) fn stats(&self) -> (usize, usize) {
        let kept = self.kept.lock().expect("the kept domains are not poisoned");
        (kept.bytes, kept.domains.values().map(Vec::len).sum())
    }

    fn computed(&self, key: &Key) -> Vec<Arc<Computed>> {
        self.kept.lock().expect("the kept domains are not poisoned").domains.get(key).cloned().unwrap_or_default()
    }

    fn keep(&self, key: Key, computed: Computed) {
        let values = match computed.given.values() {
            Some(Domain::Rows(values)) => values.iter().map(|value| relation_estimate(value)).sum(),
            _ => 0,
        };
        let bytes = computed.events.iter().map(Recorded::bytes).sum::<usize>() + values + 1024;
        let mut kept = self.kept.lock().expect("the kept domains are not poisoned");
        if bytes > self.kept_bytes {
            return;
        }
        if kept.bytes + bytes > self.kept_bytes {
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
        let limits = evaluation.limits;
        for computed in self.memo.computed(&key) {
            let Some(domain) = computed.given.values() else { continue };
            // An open capture keeps the events of this replay, as it keeps those of a
            // computation, so that a later replay of the capture makes the same lookups.
            let replayed = || match &computed.found {
                Some(keys) if session.results.replay_found(&computed.events, keys) => {
                    for event in computed.events.iter() {
                        session.results.record(|| event.clone());
                    }
                    true
                }
                _ => replay_recorded(session, &computed.events),
            };
            match computed.hit(domain).charge_if(&limits.request, Some(work), session, replayed) {
                Charged::Value(domain) => return Ok(domain.clone()),
                Charged::Stopped(_, bound) => return Ok(Domain::Stopped(Stop { bound, form: evaluation.program.program.form_of(node).clone() })),
                Charged::Misfit => {}
            }
        }
        let Some(recording) = session.results.record_on_thread() else {
            return evaluation.domain(node);
        };
        let (found, cost) = limits.request.measure(|| evaluation.domain(node));
        let events = recording.finish();
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
        self.memo.keep(key, Computed { events, cost, given: Given::Values(domain.clone()), found });
        Ok(domain)
    }
}
