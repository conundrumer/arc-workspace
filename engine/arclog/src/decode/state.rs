//! The state of a decode and its step by one token, by the grammar of the
//! stream that `crate::stream::write` writes: the finished forms, the form in
//! progress as a stack of open nodes, the relations declared by slot, and the
//! count of the labels of the form in progress.
//!
//! A decoded program names by slot each name that the stream holds as an id,
//! as `docs/arclog/arclog.md#names` gives: a relation it declares, by its
//! slot; an instance, a `CHOOSE` form and a `RIGID_DET` form, by the slot of
//! the first relation it declares; a column of a relation it declares, by the
//! column's position among the relation's columns; a field of a record, by
//! its position in the record; and the name of a bare label at a column of a
//! type parameter, by the label's id.
//!
//! The step refuses `DEMONSTRATED`, `DEMO_RULE`, `PREDICT` and `ALT_FORM`
//! at every state ([`State::step`]): the grammar has no form for them, though
//! the vocabulary holds their tokens.

use std::sync::Arc;

use super::Context;
use crate::check::{CheckCache, CheckedProgram, SolverClauses};
use crate::eval::{Hit, Outcome};
use crate::program::path::{NodePath, PathStep};
use crate::program::{
    written_inputs, Atom, Body, Choose, Clause, ClauseKeyword, ColumnName, Conjunct, Constraint, ConstraintLabel, ConstraintOp, DeclaredName,
    Form, Instance, InstanceInput, InstanceName, KeyBody, KeyClause, LabelId, LabelUse, Negated, Node, OneMark, Operand, OutputName, OutputOwner,
    OutputStep, PortName, Out, Program, ProgramRelation, RelationName, RelationRef, RigidDet, RigidDetName, Site, SiteArg, SiteValue,
};
use crate::read::columns::{key_labels, made_labels, slot_columns};
use crate::read::is_type_parameter_column;
use crate::registry::{Component, LibEntry, LibName, Need};
use crate::registry::Registry;
use crate::resolver::columns::example;
use crate::resolver::{resolve, resolve_in_progress, resolve_last, ResolvedProgram, SolverScope, MAX_LAYERS};
use crate::safety::body_labels;
use crate::resolver::form_columns::{part_steps, rigid_outputs};
use crate::resolver::registry_columns::{component, proposer_columns, typed_columns};
use crate::stream::{Control, Token};
use crate::types::{Meet, ValueType};

/// Why the grammar refuses a token at a state.
pub(super) type Unexpected = &'static str;

/// A relation the program has declared: what a read of it names, the
/// names of its columns in order, and whether a read of it resolves: an
/// instance's relation of an input resolves where the instance writes the
/// input, as `crate::registry::Component::relation_ports` gives.
#[derive(Clone, Debug)]
struct Declared {
    relation: ProgramRelation,
    columns: Arc<[ColumnName]>,
    readable: bool,
}

/// The state of a decode. A clone copies the stack's frames, each of which
/// holds its children as shared nodes, and shares the finished forms and the
/// declarations. Outside the crate it is read through [`super::Decoder::state`] and
/// [`super::Decoder::before`], by its finished forms ([`State::program`]), the form
/// in progress ([`State::partial`]) and its relation slots.
#[derive(Clone, Debug)]
pub struct State {
    program: Node<Program>,
    /// The relations declared, by slot.
    declared: Arc<[Arc<Declared>]>,
    /// The count of the relations declared at the last finished form, which
    /// are those of the finished forms.
    finished_slots: u32,
    /// The count of the labels of the form in progress, the next label's id.
    labels: u32,
    stack: Vec<Frame>,
    /// The resolution of the finished forms, made on its first read, which
    /// every clone of the state shares until a form finishes.
    resolved: Arc<FinishedResolution>,
    /// The resolutions of the form in progress that candidates opening an
    /// atom share, among the checks of the states and forks with the same
    /// finished forms.
    held_resolutions: Arc<crate::check::prefix::HeldResolutions>,
    /// The clauses of the finished forms, which every clone of the state
    /// shares until a form finishes. A clause set memoizes in cells that
    /// one thread reads at a time, so the pool lends each to one reader,
    /// and a reader finding the pool empty makes one.
    clauses: Arc<std::sync::Mutex<Vec<SolverClauses>>>,
    /// The fixed scalar type of each column read, which the finished forms
    /// and the registry give, shared by the states and forks with those
    /// finished forms.
    fixed_columns: Arc<std::sync::Mutex<crate::hash::StableHashMap<(RelationRef, ColumnName), Option<ValueType>>>>,
    /// The verdicts of [`State::cached_prefix`], shared by the states and
    /// forks with the same finished forms.
    prefixes: Arc<std::sync::Mutex<PrefixMemo>>,
    /// The verdicts of the atoms of the relations that the finished forms
    /// declare, shared by the states and forks with the same finished forms.
    atom_verdicts: Arc<std::sync::Mutex<crate::hash::StableHashMap<u128, super::atoms::HeldVerdict>>>,
    /// The checked program of the finished forms, resolved from the
    /// resolution of the state before the last form finished, made on its
    /// first read and shared by every clone of the state until a form
    /// finishes.
    checked_last: Arc<std::sync::OnceLock<Outcome<CheckedProgram>>>,
    /// The check cache of the whole-program checks of programs that hold
    /// the finished forms, shared by the states and forks with the same
    /// finished forms.
    checks: Arc<SharedChecks>,
    /// What the checks of the programs that start with the finished forms
    /// read of each of those forms, shared by the states and forks with
    /// those finished forms.
    earlier_forms: Arc<crate::check::EarlierForms>,
    /// The atom that the step in progress opened, as [`State::step`] takes
    /// it: none in every state a step gives.
    opened: Option<Opened>,
}

/// Where a state stands within an open atom.
#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub(super) enum AtomPlace {
    /// A column of a further site or a token that closes the atom may come.
    Sites,
    /// A site is open, and a value of it or of a field of its record is due.
    Value,
}

/// The resolution of the finished forms of a state, which every clone of
/// the state shares until a form finishes.
///
/// It is made on its first read, from the resolution of the finished forms
/// before the last one ([`resolve_last`]), which a read makes first where
/// none was read yet; the first state's is [`resolve`]'s. A resolution built
/// by [`resolve_last`] holds what [`resolve`] gives for the same forms, and
/// is [`resolve`]'s itself where [`resolve_last`] does not layer, so what
/// the finished forms are is all that fixes it.
///
/// The chain stands on fewer than [`MAX_LAYERS`] layers: the resolution of a
/// prefix is a layer over this one, and [`resolve_prefix`] and its kin
/// resolve the whole prefix program, with no layer, over a resolution that
/// already stands on [`MAX_LAYERS`], which costs as much as the program for
/// each prefix. So the link after the last layer that fits is a full
/// [`resolve`].
#[derive(Debug)]
struct FinishedResolution {
    resolved: std::sync::OnceLock<Arc<ResolvedProgram>>,
    /// The resolution of the forms before the last, until this one is made.
    before: std::sync::Mutex<Option<Arc<FinishedResolution>>>,
}

impl FinishedResolution {
    /// The resolution of no form.
    fn first() -> FinishedResolution {
        FinishedResolution { resolved: std::sync::OnceLock::new(), before: std::sync::Mutex::new(None) }
    }

    /// The resolution of the forms after those that `before` resolves, one
    /// form more.
    fn after(before: Arc<FinishedResolution>) -> FinishedResolution {
        FinishedResolution { resolved: std::sync::OnceLock::new(), before: std::sync::Mutex::new(Some(before)) }
    }

    /// The resolution of `program`, the finished forms this resolution is of.
    /// A resolution that `before` holds is of `program` less its last form.
    fn get(&self, program: &Node<Program>, registry: &Registry) -> Arc<ResolvedProgram> {
        let resolved = self.resolved.get_or_init(|| {
            let before = self.before.lock().expect("the resolution chain is not poisoned").take();
            let resolution = match (before, program.value().forms.split_last()) {
                (Some(before), Some((_, complete))) => {
                    let complete = Node::new(Program { forms: complete.into() });
                    let before = before.get(&complete, registry);
                    if before.layers() + 1 < MAX_LAYERS {
                        resolve_last(&before, program, registry)
                    } else {
                        resolve(program, None, &SolverScope::default(), registry).value
                    }
                }
                _ => resolve(program, None, &SolverScope::default(), registry).value,
            };
            Arc::new(resolution)
        });
        Arc::clone(resolved)
    }
}

/// The most bytes of a prefix key that [`State::cached_prefix`] keeps.
const PREFIX_KEY_BYTES: usize = 64 * 1024;
/// The most entries, and the most bytes of keys, that a generation of a
/// state's prefix verdicts holds before the generation before it is dropped.
const PREFIX_ENTRIES: usize = 16384;
const PREFIX_BYTES: usize = 16 * 1024 * 1024;

/// The check verdicts of the prefixes at an open node, by the key of
/// `prefix_key`, for one set of finished forms. A key holds the complete
/// source of its prefix.
#[derive(Clone, Copy, PartialEq, Eq, Hash, Debug)]
enum PrefixKind { Check, SingleCheck, DetAdmission, StaticReplacement }

/// A verdict, and the cost of the computation that gave it ([`crate::eval::Cost`]), which a hit charges again where the verdict is of the written `DET`s' admission.
type Verdict = (Result<(), super::Refusal>, crate::eval::Cost);

type PrefixEntries = crate::hash::StableHashMap<(PrefixKind, Vec<u8>), Verdict>;

/// The verdicts in two generations: a verdict that a lookup finds in the
/// older generation moves to the current one, so the verdicts in use stay
/// while the others age out.
#[derive(Debug, Default)]
struct PrefixMemo {
    entries: PrefixEntries,
    older: PrefixEntries,
    /// The bytes of the keys of `entries`.
    bytes: usize,
}

impl PrefixMemo {
    fn get(&mut self, key: &(PrefixKind, Vec<u8>)) -> Option<Hit<Result<(), super::Refusal>>> {
        if let Some((verdict, cost)) = self.entries.get(key) {
            return Some(Hit::new(verdict.clone(), *cost));
        }
        let held = self.older.remove(key)?;
        self.insert(key.clone(), held.clone());
        Some(Hit::new(held.0, held.1))
    }

    fn insert(&mut self, key: (PrefixKind, Vec<u8>), verdict: Verdict) {
        if self.entries.len() >= PREFIX_ENTRIES || self.bytes + key.1.len() > PREFIX_BYTES {
            crate::stats::tick(crate::stats::Phase::DecodePrefixClear);
            self.older = std::mem::take(&mut self.entries);
            self.bytes = 0;
        }
        self.bytes += key.1.len();
        self.entries.insert(key, verdict);
    }
}

/// The check cache of the whole-program checks of programs that hold one
/// set of finished forms. On its first use it starts as a copy of the cache
/// of the finished forms before the last one finished, so that a check
/// takes the results of each form that an earlier check along the decode
/// checked under the same [`crate::check::CheckCacheKey`]. A key holds what
/// its check's result reads, so a result taken from it is the result a
/// check from an empty cache gives.
#[derive(Debug, Default)]
pub(super) struct SharedChecks {
    cache: std::sync::Mutex<Option<CheckCache>>,
    /// The cache of the finished forms before the last one finished, until
    /// the first use copies it.
    from: std::sync::Mutex<Option<Arc<SharedChecks>>>,
}

impl SharedChecks {
    fn after(from: &Arc<SharedChecks>) -> SharedChecks {
        SharedChecks { cache: std::sync::Mutex::default(), from: std::sync::Mutex::new(Some(Arc::clone(from))) }
    }

    /// Runs `body` with the cache, or with an empty cache where another
    /// check holds it.
    pub(super) fn with<R>(&self, body: impl FnOnce(&mut CheckCache) -> R) -> R {
        let Ok(mut held) = self.cache.try_lock() else { return body(&mut CheckCache::default()) };
        let cache = held.get_or_insert_with(|| {
            let from = self.from.lock().ok().and_then(|mut from| from.take());
            from.map(|from| from.copy()).unwrap_or_default()
        });
        body(cache)
    }

    /// A copy of the cache, or of the cache it starts from where no check
    /// has used it; an empty cache where a check holds it.
    fn copy(&self) -> CheckCache {
        let Ok(mut held) = self.cache.try_lock() else { return CheckCache::default() };
        match &mut *held {
            Some(cache) => cache.fork(),
            None => {
                let from = self.from.lock().ok().and_then(|from| from.clone());
                drop(held);
                from.map(|from| from.copy()).unwrap_or_default()
            }
        }
    }
}

/// An atom that a step opened as its last change, which the form in
/// progress then ends with: its relation alone, and no site.
#[derive(Clone, Debug)]
pub(super) struct Opened;

/// Whether the atom of `relation` that a step opened, at the path in the
/// program, the second argument, of the program with the form in progress
/// as its last form, the first, reads an Example column.
pub(super) type ReadsExample<'a> = &'a dyn Fn(&Node<Program>, &NodePath, &RelationRef) -> bool;

/// An open node of the form in progress, with its children so far.
#[derive(Clone, Debug)]
enum Frame {
    Clause(ClauseFrame),
    /// A `ONE` mark of a clause, with its key labels so far.
    One(Vec<LabelId>),
    Body(BodyFrame),
    Atom(AtomFrame),
    Site(SiteFrame),
    Constraint(ConstraintFrame),
    Or(Vec<Node<Body>>),
    Lists(ListsFrame),
    Instance(InstanceFrame),
    KeyClause(KeyClauseFrame),
    Input(InputFrame),
    HeadSite(HeadSiteFrame),
    Choose(ChooseFrame),
    Rigid(RigidFrame),
    /// An `OUT` form, whose body stands open above it.
    Out,
}

/// The frame of `$variant` on top of `$state`'s stack.
macro_rules! top {
    ($state:expr, $variant:path) => {
        match $state.stack.last_mut() {
            Some($variant(frame)) => frame,
            _ => unreachable!("the frame stands on top"),
        }
    };
}

#[derive(Clone, Debug)]
struct ClauseFrame {
    keyword: ClauseKeyword,
    proposers: Vec<LibName>,
    stage: ClauseStage,
}

#[derive(Clone, Debug)]
enum ClauseStage {
    /// After the keyword and each proposer, before the body opens.
    Proposers,
    /// The body stands open above the clause.
    Body,
    /// The body is complete: the `SET` mark, then the `ONE` marks, then the
    /// clause's `END`.
    Marks { body: Node<Body>, ones: Vec<OneMark>, set: bool },
}

/// What closes a body, by the node that holds it.
#[derive(Clone, Copy, PartialEq, Eq, Debug)]
enum Close {
    /// A clause's body: `ONE` or `END`.
    Clause,
    /// A branch of an `OR`: `ALSO`, which opens the next branch, or `END`.
    Branch,
    /// Each other list: `END`.
    List,
    /// The form of a `NOT` over a form: its one conjunct.
    Not,
}

#[derive(Clone, Debug)]
struct BodyFrame {
    conjuncts: Vec<Conjunct>,
    close: Close,
    /// Whether the body is a key's body or stands within one, where `^`
    /// marks a key column.
    key: bool,
    /// Whether a `NOT` stands before the next conjunct.
    negate: bool,
}

#[derive(Clone, Debug)]
struct AtomFrame {
    relation: RelationRef,
    /// The names of the relation's columns, by the position of a column
    /// token.
    columns: Arc<[ColumnName]>,
    sites: Vec<Site>,
    negated: bool,
}

#[derive(Clone, Debug)]
struct SiteFrame {
    column: ColumnName,
    args: Vec<SiteArg>,
    /// The count of the fields of the record the site's column holds, where
    /// it holds one.
    record: Option<u16>,
    /// The field whose column token stands, which its label follows.
    field: Option<u32>,
    /// Whether the site's column is of a type parameter that the `INIT`
    /// form in progress, whose output the site's atom reads, binds at no
    /// head site yet. The first projection onto the parameter binds it
    /// (`docs/arclog/arclog.md#instance`), and in a keyed instance that
    /// projection can be the head of the input that holds the site, which
    /// the stream writes after the input's body. So the site's first token
    /// tells a label, the column's one label, from a field's column token,
    /// a field of the record.
    unbound: bool,
}

#[derive(Clone, Debug)]
struct ConstraintFrame {
    op: ConstraintOp,
    first: Option<ConstraintLabel>,
}

/// The lists of an `IF` form, or of an `ALL` form where `all` holds.
#[derive(Clone, Debug)]
struct ListsFrame {
    all: bool,
    lists: Vec<Node<Body>>,
}

#[derive(Clone, Debug)]
struct InstanceFrame {
    /// The slot of the first relation the instance declares.
    first: u32,
    /// The component, from its token on.
    component: Option<LibName>,
    key: Option<Node<KeyClause>>,
    inputs: Vec<Node<InstanceInput>>,
    stage: Naming,
}

#[derive(Clone, Debug)]
struct KeyClauseFrame {
    body: Option<Node<Body>>,
    inputs: Vec<Node<InstanceInput>>,
    stage: Naming,
}

/// Where the clauses of an instance stand.
#[derive(Clone, Copy, Debug)]
enum Naming {
    /// The engine has named the `key`, or the input at this position of the
    /// component, and the language model answers with `SKIP` or the clause.
    Named(Option<usize>),
    /// A child stands open above, or the component is yet to come.
    Open,
}

#[derive(Clone, Debug)]
struct InputFrame {
    /// The input's position among the component's inputs.
    position: usize,
    name: PortName,
    columns: Arc<[ColumnName]>,
    body: Option<Node<Body>>,
    head: Vec<Site>,
    /// The column whose projection stands open, once the body is complete.
    column: usize,
}

#[derive(Clone, Debug)]
struct HeadSiteFrame {
    column: ColumnName,
    args: Vec<SiteArg>,
    /// The count of the fields written.
    fields: u32,
    field: Option<u32>,
    /// The label of the last bare label written, which the next bare label
    /// follows in the order of the labels.
    last_bare: Option<u32>,
    /// Whether the `END` of the site's record stands, which the `END` of the
    /// projection's column follows.
    record_ended: bool,
}

#[derive(Clone, Debug)]
struct ChooseFrame {
    rows: Option<KeyBody>,
    from: Option<Node<Body>>,
    never: Vec<Node<Body>>,
    stage: ChooseStage,
}

#[derive(Clone, Copy, PartialEq, Eq, Debug)]
enum ChooseStage {
    For,
    ForOpen,
    FromOpen,
    Never,
    NeverOpen,
    /// After a `never` body: `ALSO` and the next, or the form's `END`.
    NeverEnd,
}

#[derive(Clone, Debug)]
struct RigidFrame {
    key: Option<KeyBody>,
    instance: Option<KeyBody>,
    parts: Vec<Node<Atom>>,
    stage: RigidStage,
}

#[derive(Clone, Copy, PartialEq, Eq, Debug)]
enum RigidStage {
    Key,
    KeyOpen,
    Instance,
    InstanceOpen,
    Parts,
}

/// The node of a frame: the node a closed frame gives the frame below it,
/// or, in [`State::partial`], the partial node of an open frame.
enum Built {
    Body(Node<Body>),
    Conjunct(Conjunct),
    Atom { atom: Node<Atom>, negated: bool },
    Site(Site),
    /// A head site, or none for an empty projection.
    HeadSite(Option<Site>),
    Input { input: Node<InstanceInput>, position: usize },
    KeyClause(Node<KeyClause>),
    Form(Form),
}

/// What a frame does with a token.
enum Offer {
    /// The frame consumed the token.
    Taken,
    /// The stack changed and the token stands, for the new top.
    Again,
    /// The frame is complete: it closes, its node goes to the frame below
    /// it, and the token stands where `consumed` does not hold.
    Close { consumed: bool },
}

/// The most fields of a record that [`State::head_site_completions`] offers.
const FIELDS_TRIED: u32 = 1;

/// Where the head site of an instance input stands, as
/// [`State::open_projection`] gives it.
#[derive(Clone, Debug)]
pub(super) struct OpenProjection {
    /// The index, among the port's columns, of the column whose site stands
    /// open.
    pub(super) column: usize,
    /// The indices of the columns before it that the head closed with no site.
    pub(super) without_site: Vec<usize>,
    /// The arguments the open site holds.
    pub(super) args: usize,
    /// Whether the label of a field of the open site's record stands next.
    pub(super) field_open: bool,
    /// Whether the `END` of the open site's record is written.
    pub(super) record_ended: bool,
    /// Whether the open site's column is a type parameter's.
    pub(super) parameter: bool,
}

impl State {
    pub(super) fn new() -> State {
        State { program: Node::new(Program { forms: Arc::from([]) }), declared: Arc::from([]), finished_slots: 0, labels: 0, stack: Vec::new(), resolved: Arc::new(FinishedResolution::first()), held_resolutions: Arc::default(), clauses: Arc::default(), fixed_columns: Arc::default(), prefixes: Arc::default(), atom_verdicts: Arc::default(), checked_last: Arc::default(), checks: Arc::default(), earlier_forms: Arc::default(), opened: None }
    }

    /// The fixed scalar type of `column` of `relation` ([`ValueType::is_scalar`]),
    /// which `compute` gives and this state keeps until a form finishes. A
    /// column's type that the finished forms and the registry fix does not
    /// change while the form in progress is written.
    pub(super) fn fixed_column_type(&self, relation: &RelationRef, column: &ColumnName, compute: impl FnOnce() -> Option<ValueType>) -> Option<ValueType> {
        let key = (relation.clone(), column.clone());
        if let Some(ty) = self.fixed_columns.lock().expect("the column cache is not poisoned").get(&key) {
            return ty.clone();
        }
        let ty = compute();
        self.fixed_columns.lock().expect("the column cache is not poisoned").insert(key, ty.clone());
        ty
    }

    /// The verdict of `Decoder::check_state` with `Candidate::Any` at an open
    /// node for the prefix with source key `key`, which `compute` gives and
    /// this state keeps until a form finishes. The checks of that verdict read
    /// the prefix's source, its open path and the finished forms, which the
    /// key and the cache's lifetime fix.
    pub(super) fn cached_prefix(&self, key: Vec<u8>, compute: impl FnOnce() -> Result<(), super::Refusal>) -> Result<(), super::Refusal> {
        let single = (PrefixKind::SingleCheck, key);
        // The oracle of the mask reads each verdict apart.
        #[cfg(not(feature = "admissible-reference"))]
        if let Some(hit) = self.prefixes.lock().expect("the prefix cache is not poisoned").get(&single) {
            crate::stats::tick(crate::stats::Phase::DecodePrefixHit);
            return hit.without_request();
        }
        self.cached_verdict(PrefixKind::Check, single.1, &|| true, None, compute)
    }

    /// [`State::cached_prefix`] for a verdict that the checks give outside the
    /// mask's mode, as a single token's step does. A mask gives one verdict
    /// with a step, so a prefix that a mask passed takes that pass; a mask's
    /// refusal is kept apart, as a step gives each refusal's place and text.
    pub(super) fn cached_single_prefix(&self, key: Vec<u8>, compute: impl FnOnce() -> Result<(), super::Refusal>) -> Result<(), super::Refusal> {
        let mask = (PrefixKind::Check, key);
        // The oracle of the mask reads each verdict apart.
        #[cfg(not(feature = "admissible-reference"))]
        if let Some(Ok(())) = self.prefixes.lock().expect("the prefix cache is not poisoned").get(&mask).map(Hit::without_request) {
            crate::stats::tick(crate::stats::Phase::DecodePrefixHit);
            return Ok(());
        }
        self.cached_verdict(PrefixKind::SingleCheck, mask.1, &|| true, None, compute)
    }

    /// The verdict of the written `DET`s' admission at a prefix. The verdict is
    /// kept only where `keep` holds after it is computed: a verdict that a stop
    /// at the request work cap left open is no verdict of the prefix. The
    /// verdict is kept with the cost of its computation, and a hit charges that
    /// cost to `work`.
    pub(super) fn cached_det_prefix(&self, key: Vec<u8>, keep: &dyn Fn() -> bool, work: &crate::eval::RequestWork, session: &crate::session::TaskSession, compute: impl FnOnce() -> Result<(), super::Refusal>) -> Result<(), super::Refusal> {
        self.cached_verdict(PrefixKind::DetAdmission, key, keep, Some((work, session)), compute)
    }

    /// The verdict of the static prune's replacement check on a clause cut to
    /// the conjunct it replaces, which every candidate of a mask shares.
    pub(super) fn cached_replacement(&self, key: Vec<u8>, compute: impl FnOnce() -> Result<(), super::Refusal>) -> Result<(), super::Refusal> {
        self.cached_verdict(PrefixKind::StaticReplacement, key, &|| true, None, compute)
    }

    fn cached_verdict(&self, kind: PrefixKind, key: Vec<u8>, keep: &dyn Fn() -> bool, charged: Option<(&crate::eval::RequestWork, &crate::session::TaskSession)>, compute: impl FnOnce() -> Result<(), super::Refusal>) -> Result<(), super::Refusal> {
        let key = (kind, key);
        let held = self.prefixes.lock().expect("the prefix cache is not poisoned").get(&key);
        if let Some(hit) = held {
            match charged {
                None => {
                    crate::stats::tick(crate::stats::Phase::DecodePrefixHit);
                    return hit.without_request();
                }
                // A hit whose cost would pass the request's cap is no hit: the verdict is computed again, and the computation stops where it stops with empty caches.
                Some((work, session)) => {
                    if let Some(verdict) = hit.charge(work, None, session).value() {
                        crate::stats::tick(crate::stats::Phase::DecodePrefixHit);
                        return verdict;
                    }
                }
            }
        }
        crate::stats::tick(crate::stats::Phase::DecodePrefixMiss);
        let (verdict, cost) = match charged {
            Some((work, _)) => work.measure(compute),
            None => (compute(), crate::eval::Cost::default()),
        };
        if key.1.len() <= PREFIX_KEY_BYTES && keep() {
            self.prefixes.lock().expect("the prefix cache is not poisoned").insert(key, (verdict.clone(), cost));
        }
        verdict
    }

    /// Complete a written mark through the same grammar that closes a clause.
    /// An open model-pick key can change the model family, so it is checked
    /// when its END arrives. Proposers cannot take keys; their ONE is settled now.
    pub(super) fn det_admission_state(&self, before: &State, context: &Context<'_>) -> Option<State> {
        if self.program.value().forms.len() > before.program.value().forms.len() {
            let written = match self.program.value().forms.last() {
                Some(Form::Clause(c)) => c.value().keyword == ClauseKeyword::Det,
                Some(Form::RigidDet(_)) => true,
                _ => false,
            };
            return written.then(|| self.clone());
        }
        let ends = match self.stack.as_slice() {
            [Frame::Clause(ClauseFrame { keyword: ClauseKeyword::Det, stage: ClauseStage::Marks { .. }, .. })] => 1,
            [Frame::Clause(ClauseFrame { keyword: ClauseKeyword::Det, proposers, stage: ClauseStage::Marks { .. }, .. }), Frame::One(_)] if !proposers.is_empty() => 2,
            _ => return None,
        };
        let mut state = self.clone();
        for _ in 0..ends {
            state = state.step(context, &Token::Control(Control::End), &|_, _, _| false).ok()?.0;
        }
        Some(state)
    }

    /// The finished forms.
    #[inline]
    pub fn program(&self) -> &Node<Program> {
        &self.program
    }

    /// The resolution of the finished forms, a synthesized program whose
    /// names resolve within it.
    pub(super) fn resolved(&self, registry: &Registry) -> Arc<ResolvedProgram> {
        self.resolved.get(&self.program, registry)
    }

    /// The resolutions of the form in progress that the checks of this state
    /// share, among those of the states with the same finished forms.
    pub(super) fn held_resolutions(&self) -> &Arc<crate::check::prefix::HeldResolutions> {
        &self.held_resolutions
    }

    /// Runs `body` with the clauses of the finished forms' resolution, made
    /// for each reader that finds none lent, and lent again after.
    pub(super) fn with_clauses<R>(&self, registry: &Registry, body: impl FnOnce(&SolverClauses) -> R) -> R {
        let lent = self.clauses.lock().expect("the clause pool is not poisoned").pop();
        let clauses = lent.unwrap_or_else(|| SolverClauses::of_shared_program(self.resolved(registry)));
        let result = body(&clauses);
        self.clauses.lock().expect("the clause pool is not poisoned").push(clauses);
        result
    }

    /// The checked program of the finished forms, as [`State::checked_last`]
    /// holds it.
    pub(super) fn checked_last(&self) -> &std::sync::OnceLock<Outcome<CheckedProgram>> {
        &self.checked_last
    }

    /// The check cache of the programs that hold the finished forms.
    pub(super) fn checks(&self) -> &SharedChecks {
        &self.checks
    }

    /// What the checks of the programs that start with the finished forms
    /// read of each of those forms.
    pub(super) fn earlier_forms(&self) -> &crate::check::EarlierForms {
        &self.earlier_forms
    }

    /// The resolution of `partial`, the finished forms with the form in
    /// progress as the last form, as [`State::partial`] gives it.
    fn resolved_partial(&self, partial: &Node<Program>, registry: &Registry) -> ResolvedProgram {
        resolve_in_progress(&self.resolved(registry), partial, registry)
    }

    /// Whether `token` may pass [`State::step`] at this state: `false` only for
    /// a token that [`State::offer`] and the frames it closes into refuse, so
    /// the mask takes no clone of the state for it. A site with no record and
    /// an atom may close without taking the token, so their enclosing frame
    /// still sees it.
    pub(super) fn mask_may_take(&self, token: &Token) -> bool {
        let top = self.stack.last();
        match token {
            Token::Label(id) => {
                *id < self.labels
                    && match top {
                        Some(Frame::Site(SiteFrame { field: None, record: Some(_), .. })) => false,
                        Some(Frame::One(_) | Frame::Site(_) | Frame::Constraint(_) | Frame::HeadSite(_)) => true,
                        _ => false,
                    }
            }
            Token::Relation(id) if *id as usize >= self.declared.len() => false,
            Token::Column(position) => match top {
                Some(Frame::Atom(atom)) => (*position as usize) < atom.columns.len(),
                Some(Frame::Site(SiteFrame { field: None, record: Some(fields), .. })) => *position < u32::from(*fields),
                Some(Frame::Site(site @ SiteFrame { field: None, record: None, .. })) => {
                    (site.unbound && site.args.is_empty())
                        || matches!(self.stack.iter().rev().nth(1), Some(Frame::Atom(atom)) if (*position as usize) < atom.columns.len())
                }
                Some(Frame::HeadSite(site)) => site.field.is_none() && !site.record_ended && *position == site.fields,
                _ => false,
            },
            Token::Proposer(_) => matches!(top, Some(Frame::Clause(ClauseFrame { stage: ClauseStage::Proposers, .. }))),
            Token::Lib(_) | Token::Fact(_) | Token::Relation(_) => match top {
                None | Some(Frame::One(_) | Frame::Constraint(_) | Frame::HeadSite(_)) => false,
                Some(Frame::Site(site)) if site.field.is_some() || site.record.is_some() => false,
                Some(Frame::Clause(clause)) => matches!(clause.stage, ClauseStage::Proposers) && clause.proposers.is_empty(),
                Some(Frame::Choose(ChooseFrame { stage: ChooseStage::NeverEnd, .. })) => false,
                _ => true,
            },
            Token::Control(control) => match top {
                None => matches!(control, Control::Rule | Control::Det | Control::Init | Control::Choose | Control::RigidDet | Control::Out),
                Some(Frame::One(_)) => *control == Control::End,
                Some(Frame::Constraint(_)) => matches!(control, Control::Fresh | Control::Zero),
                Some(Frame::HeadSite(site)) if site.field.is_some() => matches!(control, Control::Fresh | Control::Zero),
                Some(Frame::HeadSite(_)) => matches!(control, Control::End | Control::Fresh | Control::Zero),
                Some(Frame::Site(site)) if site.field.is_some() => matches!(control, Control::Fresh | Control::Key | Control::Zero),
                Some(Frame::Site(site)) if site.record.is_some() => matches!(control, Control::End | Control::Zero),
                _ => true,
            },
        }
    }

    /// Whether the state holds an `INIT` form that has no component yet.
    pub(super) fn awaits_component(&self) -> bool {
        matches!(&self.stack[..], [Frame::Instance(InstanceFrame { component: None, .. })])
    }

    /// Whether `token` takes the grammar step alone, with no check of the
    /// prefix: an `INIT`'s component token, and a proposer of a clause. At an
    /// `INIT` that holds its component alone, no check refuses, and at a
    /// clause that holds no body, no check refuses a proposer but the
    /// proposer's name rule of `RigidPartsAndProposersCheck`: the grammar
    /// refuses a second proposer of a `DET` or `RULE` before any check runs.
    /// A proposer that breaks the name rule takes the checks, which refuse it.
    pub(super) fn grammar_only_candidate(&self, token: &Token) -> bool {
        if self.awaits_component() {
            return matches!(token, Token::Lib(_));
        }
        match (&self.stack[..], token) {
            ([Frame::Clause(ClauseFrame { stage: ClauseStage::Proposers, .. })], Token::Proposer(name)) => crate::check::rigid_proposer::is_proposer_name(&name.0),
            _ => false,
        }
    }

    /// The labels that `TypesCheck` refuses with `EmptyMeet` at the open site
    /// of a fixed scalar column of a positive atom, in a body of atoms, `NOT`
    /// atoms and constraints, or, in an instance whose bodies are all atoms,
    /// across its key and inputs: the labels whose sites of fixed scalar
    /// columns there give a type with an empty meet with the column's type.
    /// `TypesCheck` refuses such a label at its first use, which no open node
    /// holds, as the label is not given, so a later site cannot undo it. A
    /// form with an `OR`, a list or a `NOT` body gives none.
    pub(super) fn fixed_label_conflicts(&self, registry: &Registry, column_type: &impl Fn(&RelationRef, &ColumnName) -> Option<ValueType>) -> Vec<u32> {
        self.label_conflicts(registry, column_type, None)
    }

    /// [`State::fixed_label_conflicts`] for the head site of `column`, a
    /// column of the port of the input whose head site stands on top, in
    /// place of the site on top: the labels that a site on `column` of a fixed
    /// scalar type refuses. The labels depend on the bodies of the form and
    /// the column's type alone, and the head sites written leave them as they
    /// are, so they are the same at each head site of the column, whatever
    /// sites of the input's head are written before it. None where no head
    /// site stands on top.
    pub(super) fn head_label_conflicts(&self, registry: &Registry, column_type: &impl Fn(&RelationRef, &ColumnName) -> Option<ValueType>, column: &ColumnName) -> Vec<u32> {
        match self.stack.last() {
            Some(Frame::HeadSite(_)) => self.label_conflicts(registry, column_type, Some(column)),
            _ => Vec::new(),
        }
    }

    fn label_conflicts(&self, registry: &Registry, column_type: &impl Fn(&RelationRef, &ColumnName) -> Option<ValueType>, head_column: Option<&ColumnName>) -> Vec<u32> {
        if self.stack.iter().any(|frame| matches!(frame, Frame::Or(_) | Frame::Lists(_) | Frame::Body(BodyFrame { close: Close::Not, .. }))) {
            return Vec::new();
        }
        let (expected, body, atom): (Option<ValueType>, Option<&Body>, Option<&AtomFrame>) = match self.stack.last() {
            Some(Frame::Site(site)) if site.field.is_none() => {
                let Some(Frame::Atom(atom)) = self.stack.iter().rev().nth(1) else { return Vec::new() };
                if atom.negated {
                    return Vec::new();
                }
                (column_type(&atom.relation, &site.column), None, Some(atom))
            }
            Some(Frame::HeadSite(site)) if head_column.is_some() || (site.field.is_none() && site.args.is_empty()) => {
                let Some(Frame::Input(input)) = self.stack.iter().rev().nth(1) else { return Vec::new() };
                let port = &self.component_from_input(registry).inputs[input.position].port;
                let named = head_column.unwrap_or(&site.column);
                let expected = port.columns.iter().find(|column| column.name == *named).and_then(|column| scalar_fixed(&column.ty));
                (expected, input.body.as_ref().map(Node::value), None)
            }
            _ => return Vec::new(),
        };
        let Some(expected) = expected else { return Vec::new() };
        let conjuncts = match body {
            Some(body) => &body.conjuncts[..],
            None => match self.stack.iter().rev().find_map(|frame| match frame { Frame::Body(body) => Some(body), _ => None }) {
                Some(body) => &body.conjuncts[..],
                None => return Vec::new(),
            },
        };
        if !conjuncts.iter().all(|conjunct| matches!(conjunct, Conjunct::Atom(_) | Conjunct::Not(Negated::Atom(_)) | Conjunct::Constraint(_))) {
            return Vec::new();
        }
        let mut conflicts = Vec::new();
        let mut add_sites = |relation: &RelationRef, sites: &[Site]| {
            for site in sites {
                let Some(known) = column_type(relation, &site.column) else { continue };
                if matches!(known.meet(&expected), Meet::Empty) {
                    for arg in site.value.args.iter() {
                        if let SiteArg::Label(LabelUse::Fresh(label) | LabelUse::Join(label) | LabelUse::Key(label)) = arg {
                            conflicts.push(label.0);
                        }
                    }
                }
            }
        };
        for conjunct in conjuncts {
            if let Conjunct::Atom(atom) = conjunct {
                add_sites(&atom.value().relation, &atom.value().sites);
            }
        }
        if let Some(atom) = atom {
            add_sites(&atom.relation, &atom.sites);
        }
        // An instance has one label scope across its key and inputs. A
        // fixed positive site anywhere in a flat instance constrains joins
        // in its current body, even if that site is in an earlier input.
        if matches!(self.stack.first(), Some(Frame::Instance(_))) {
            if let Some((program, _)) = self.partial() {
                if let Some(Form::Instance(instance)) = program.value().forms.last() {
                    let instance = instance.value();
                    let inputs: Vec<_> = crate::program::written_inputs(instance.key.as_ref(), &instance.inputs).collect();
                    let bodies = instance.key.iter().map(|key| key.value().key.body.value()).chain(inputs.iter().map(|input| input.body.value()));
                    let bodies: Vec<_> = bodies.collect();
                    if bodies.iter().all(|body| body.conjuncts.iter().all(|c| matches!(c, Conjunct::Atom(_)))) {
                        for body in bodies {
                            for conjunct in body.conjuncts.iter() {
                                if let Conjunct::Atom(atom) = conjunct { add_sites(&atom.value().relation, &atom.value().sites); }
                            }
                        }
                    }
                }
            }
        }
        conflicts
    }

    fn component_from_input<'r>(&self, registry: &'r Registry) -> &'r Component {
        let name = self.instance().component.as_ref().expect("an input's component");
        component(registry, name).expect("the instance names a component")
    }

    /// The sets of mask candidates that share one check verdict, outside an
    /// `OUT` and a `RIGID_DET` form:
    ///
    /// - the column tokens of the unwritten columns of the open atom, of a
    ///   fixed scalar type other than Example: the checks read the type of
    ///   no column that has no site.
    /// - at a site of a top-level clause body of positive atoms of fixed
    ///   scalar columns, the labels that an atom of no mode binds before the
    ///   open atom and whose type equals the column's type: the meet of such
    ///   a label with the column's type is its own type, so the checks give
    ///   the same labels and types for each.
    ///
    /// Each member still takes its own grammar step.
    pub(super) fn native_classes(&self, registry: &Registry, column_type: &impl Fn(&RelationRef, &ColumnName) -> Option<ValueType>) -> Vec<Vec<Token>> {
        let (atom, site) = match self.stack.last() {
            Some(Frame::Atom(atom)) => (atom, None),
            Some(Frame::Site(site)) if site.record.is_none() && site.field.is_none() => match self.stack.iter().rev().nth(1) {
                Some(Frame::Atom(atom)) => (atom, Some(site)),
                _ => return Vec::new(),
            },
            _ => return Vec::new(),
        };
        if self.stack.iter().any(|frame| matches!(frame, Frame::Out | Frame::Rigid(_))) {
            return Vec::new();
        }
        let mut groups = Vec::new();
        let columns: Vec<Token> = atom.columns.iter().enumerate().filter_map(|(position, name)| {
            if *name == example() || atom.sites.iter().any(|site| site.column == *name) || site.is_some_and(|site| site.column == *name) {
                return None;
            }
            let ty = column_type(&atom.relation, name)?;
            (ty != ValueType::Example).then_some(Token::Column(position as u32))
        }).collect();
        if columns.len() > 1 {
            groups.push(columns);
        }
        let body = match &self.stack[..] {
            [Frame::Clause(_), Frame::Body(body), Frame::Atom(_)] | [Frame::Clause(_), Frame::Body(body), Frame::Atom(_), Frame::Site(_)] => body,
            _ => return groups,
        };
        if atom.negated || body.negate {
            return groups;
        }
        let mut types: std::collections::BTreeMap<u32, ValueType> = std::collections::BTreeMap::new();
        let mut bound = std::collections::BTreeSet::new();
        let mut add = |relation: &RelationRef, sites: &[Site], before: bool| -> Option<()> {
            for site in sites {
                let ty = column_type(relation, &site.column)?;
                for arg in site.value.args.iter() {
                    let SiteArg::Label(LabelUse::Fresh(label) | LabelUse::Join(label)) = arg else { return None };
                    if before {
                        bound.insert(label.0);
                    }
                    match types.get(&label.0) {
                        Some(old) => match old.meet(&ty) {
                            Meet::Type(ty) => { types.insert(label.0, ty); }
                            Meet::Empty => return None,
                        },
                        None => { types.insert(label.0, ty.clone()); }
                    }
                }
            }
            Some(())
        };
        for conjunct in &body.conjuncts {
            let Conjunct::Atom(prior) = conjunct else { return groups };
            let unmoded = crate::eval::ir::atom_modes(registry, prior.value()).is_empty();
            if add(&prior.value().relation, &prior.value().sites, unmoded).is_none() {
                return groups;
            }
        }
        if add(&atom.relation, &atom.sites, false).is_none() {
            return groups;
        }
        if let Some(site) = site {
            if add(&atom.relation, std::slice::from_ref(&Site { column: site.column.clone(), value: SiteValue { args: site.args.clone().into() } }), false).is_none() {
                return groups;
            }
        }
        if let Some(site) = site {
            if let Some(expected) = column_type(&atom.relation, &site.column) {
                let labels: Vec<Token> = types.iter().filter(|(label, ty)| **ty == expected && bound.contains(label)).map(|(label, _)| Token::Label(*label)).collect();
                if labels.len() > 1 {
                    groups.push(labels);
                }
            }
        }
        groups
    }

    /// The state after `token`, and the tokens the engine emits after it.
    ///
    /// The step also gives the atom it opened as its last change, where it
    /// finished no form: the state then ends with an atom of no site.
    ///
    /// Every decode path steps through here: the mask, [`super::Decoder::step`] and
    /// its variants, the readback, the corpus replays and the projection
    /// search. The step refuses each token of [`Control::DEMONSTRATED_FORM`]
    /// at every state, so the grammar admits no `DEMONSTRATED` form.
    pub(super) fn step(&self, context: &Context<'_>, token: &Token, reads_example: ReadsExample<'_>) -> Result<(State, Vec<Token>, Option<Opened>), Unexpected> {
        if matches!(token, Token::Control(control) if Control::DEMONSTRATED_FORM.contains(control)) {
            return Err("the grammar has no `DEMONSTRATED` form: `DEMONSTRATED`, `DEMO_RULE`, `PREDICT` and `ALT_FORM` are refused");
        }
        let mut next = self.clone();
        let mut forced = Vec::new();
        loop {
            match next.offer(context, token, &mut forced)? {
                Offer::Taken => break,
                Offer::Again => {
                    next.opened = None;
                    continue;
                }
                Offer::Close { consumed } => {
                    next.opened = None;
                    let closer = consumed.then_some(token);
                    if let Some(built) = next.close(context, &mut forced)? {
                        next.deliver(context, built, closer, &mut forced)?;
                    }
                    if consumed {
                        break;
                    }
                }
            }
        }
        let opened = next.opened.take().filter(|_| next.program.value().forms.len() == self.program.value().forms.len());
        if let (Some(_), Token::Relation(_)) = (&opened, token) {
            next.add_example_column(reads_example);
        }
        Ok((next, forced, opened))
    }

    /// The operator, and the first label once it is written, of the
    /// constraint that stands open on top.
    pub(super) fn open_constraint(&self) -> Option<(ConstraintOp, Option<ConstraintLabel>)> {
        match self.stack.last() {
            Some(Frame::Constraint(constraint)) => Some((constraint.op, constraint.first)),
            _ => None,
        }
    }

    /// Where a head site of an instance input's projection stands on top,
    /// or a body atom's site stands on top after a field's column token, the
    /// tokens the grammar admits there that a completion can use, in the
    /// order a search tries them. After a body site's field token: `*` and,
    /// where the site stands in a key, `^`, each where the atom is no `NOT`
    /// atom, `0`, and the labels in scope from the last made. At a head site that holds an argument: `END`, the labels
    /// in scope from the last made, and the column token of the next field;
    /// at one that holds none, the same tokens with `END` last, as `END`
    /// there leaves the column without a site, which the check of the input
    /// can refuse once the input closes. After a field's column token only
    /// the labels, and after the record's `END` only `END`. A site that
    /// holds `limit` arguments takes `END` alone. A column of a type
    /// parameter takes the bare labels after its last bare label, so a set
    /// of them is tried once, and a record of at most `FIELDS_TRIED`
    /// fields; one of a fixed type takes one label.
    pub(super) fn head_site_completions(&self, limit: usize) -> Option<Vec<Token>> {
        let labels = |after: Option<u32>| (after.map_or(0, |last| last + 1)..self.labels).rev().map(Token::Label);
        let site = match self.stack.last() {
            Some(Frame::HeadSite(site)) => site,
            Some(Frame::Site(SiteFrame { field: Some(_), .. })) => {
                let makes = !self.in_negated_atom();
                let key = (makes && self.in_key()).then_some(Token::Control(Control::Key));
                let fresh = makes.then_some(Token::Control(Control::Fresh));
                let marks = fresh.into_iter().chain(key).chain([Token::Control(Control::Zero)]);
                return Some(marks.chain(labels(None)).collect());
            }
            _ => return None,
        };
        let end = Token::Control(Control::End);
        if site.field.is_some() {
            return Some(labels(None).collect());
        }
        if site.record_ended || site.args.len() >= limit {
            return Some(vec![end]);
        }
        let mut tokens: Vec<Token> = if !type_parameter(&site.column) {
            site.args.is_empty().then(|| labels(None)).into_iter().flatten().collect()
        } else {
            let field = (site.fields < FIELDS_TRIED).then_some(Token::Column(site.fields));
            labels(site.last_bare).chain(field).collect()
        };
        if site.args.is_empty() {
            tokens.push(end);
        } else {
            tokens.insert(0, end);
        }
        Some(tokens)
    }

    /// Whether `limit` shortens the tokens of
    /// [`State::head_site_completions`] at the head site on top: the site
    /// holds `limit` arguments or more, its column is a type parameter's, and
    /// its record is not ended, where `END` stands alone under the limit and
    /// more tokens stand without it. Some such site holds more tokens than it
    /// gives when this holds, and none holds more tokens when it does not.
    pub(super) fn limit_shortens(&self, limit: usize) -> bool {
        matches!(self.stack.last(), Some(Frame::HeadSite(site)) if site.field.is_none() && !site.record_ended && site.args.len() >= limit && type_parameter(&site.column))
    }

    /// Where the head site of an instance input stands on top: for the cuts of
    /// `Decoder::completes_projection`, which read the input's port, its
    /// columns that closed with no site, and the open site. None where no
    /// head site stands on top.
    pub(super) fn open_projection(&self) -> Option<OpenProjection> {
        let Some(Frame::HeadSite(site)) = self.stack.last() else { return None };
        let Some(Frame::Input(input)) = self.stack.iter().rev().nth(1) else { return None };
        let without_site = if input.head.len() == input.column {
            Vec::new()
        } else {
            (0..input.column).filter(|&index| !input.head.iter().any(|written| written.column == input.columns[index])).collect()
        };
        Some(OpenProjection {
            column: input.column,
            without_site,
            args: site.args.len(),
            field_open: site.field.is_some(),
            record_ended: site.record_ended,
            parameter: type_parameter(&site.column),
        })
    }

    /// The labels that the head sites of the input whose head site stands on
    /// top read, the site on top included, each as many times as it reads it.
    pub(super) fn head_labels(&self) -> Vec<u32> {
        let (Some(Frame::HeadSite(open)), Some(Frame::Input(input))) = (self.stack.last(), self.stack.iter().rev().nth(1)) else { return Vec::new() };
        let current = Site { column: open.column.clone(), value: SiteValue { args: open.args.iter().cloned().collect() } };
        let mut labels = Vec::new();
        for site in input.head.iter().chain([&current]) {
            crate::types::each_site_label(site, &mut Vec::new(), &mut |use_, _| labels.extend(crate::types::use_label(use_).map(|label| label.0)));
        }
        labels
    }

    /// The names of the columns of the port of the input whose head site
    /// stands on top, in the port's order.
    pub(super) fn head_columns(&self, registry: &Registry) -> Vec<ColumnName> {
        let Some(Frame::Input(input)) = self.stack.iter().rev().nth(1) else { return Vec::new() };
        self.component_from_input(registry).inputs[input.position].port.columns.iter().map(|column| column.name.clone()).collect()
    }

    /// The count of the labels made so far.
    pub fn label_count(&self) -> u32 {
        self.labels
    }

    /// A digest for the statistics ([`crate::stats::seen`]) of the identity
    /// of the finished forms, which the states that share their resolution
    /// share, and of the source of the form in progress, or of the last
    /// finished form where none is in progress.
    pub fn stats_digest(&self) -> u64 {
        let source = self.partial().and_then(|(program, open)| super::prefix_key::key(program.value().forms.last()?, open.as_ref()));
        crate::stats::digest(&(Arc::as_ptr(&self.resolved) as usize, source))
    }

    /// The program with the form in progress as its last form, and the path
    /// in that form of the innermost open node, or none where the last form
    /// is complete; or none where the form in progress shows no node yet.
    pub fn partial(&self) -> Option<(Node<Program>, Option<NodePath>)> {
        if self.stack.is_empty() {
            return Some((self.program.clone(), None));
        }
        let mut built = None;
        let mut shown = vec![false; self.stack.len()];
        for (index, frame) in self.stack.iter().enumerate().rev() {
            built = self.partial_node(frame, built);
            shown[index] = built.is_some();
        }
        let Some(Built::Form(form)) = built else { return None };
        let open = (0..self.stack.len() - 1).take_while(|index| shown[index + 1]).map(|index| PathStep(child_step(&self.stack[index], &self.stack[index + 1])));
        Some((self.with_form(form), Some(NodePath(open.collect()))))
    }

    fn with_form(&self, form: Form) -> Node<Program> {
        let forms = self.program.value().forms.iter().cloned().chain([form]).collect();
        Node::new(Program { forms })
    }

    fn finish_form(&mut self, form: Form) {
        self.program = self.with_form(form);
        self.finished_slots = self.next_slot();
        self.resolved = Arc::new(FinishedResolution::after(Arc::clone(&self.resolved)));
        self.held_resolutions = Arc::default();
        self.clauses = Arc::default();
        self.fixed_columns = Arc::default();
        self.prefixes = Arc::default();
        self.atom_verdicts = Arc::default();
        self.checked_last = Arc::default();
        self.checks = Arc::new(SharedChecks::after(&self.checks));
        self.earlier_forms = Arc::default();
        self.labels = 0;
    }

    fn next_slot(&self) -> u32 {
        u32::try_from(self.declared.len()).expect("fewer than 2^32 relations")
    }

    /// The slot at which `relation` is declared.
    pub(super) fn slot_of(&self, relation: &ProgramRelation) -> Option<u32> {
        self.declared.iter().position(|declared| declared.relation == *relation).map(|slot| u32::try_from(slot).expect("fewer than 2^32 relations"))
    }

    /// The readable relations of the finished forms declared from `first` on,
    /// each with its slot.
    pub fn declared_from(&self, first: u32) -> impl Iterator<Item = (u32, &ProgramRelation)> {
        (first..self.finished_slots).zip(self.declared[first as usize..].iter()).filter(|(_, declared)| declared.readable).map(|(slot, declared)| (slot, &declared.relation))
    }

    /// The count of the relations that the finished forms declare, which is
    /// the first slot of the form in progress.
    #[inline]
    pub fn finished_slots(&self) -> u32 {
        self.finished_slots
    }

    /// The slot that the clause in progress takes.
    #[inline]
    pub fn open_slot(&self) -> u32 {
        self.next_slot()
    }

    /// Takes the next slot for `relation`, with the columns `columns`, and
    /// gives it.
    fn declare(&mut self, relation: ProgramRelation, columns: Arc<[ColumnName]>, readable: bool) -> u32 {
        let slot = self.next_slot();
        self.declared = self.declared.iter().cloned().chain([Arc::new(Declared { relation, columns, readable })]).collect();
        slot
    }

    /// Whether the site on top is a site of a `NOT` atom.
    fn in_negated_atom(&self) -> bool {
        matches!(self.stack.iter().rev().nth(1), Some(Frame::Atom(AtomFrame { negated: true, .. })))
    }

    /// Whether the innermost body is a key's body or stands within one.
    fn in_key(&self) -> bool {
        self.stack.iter().rev().find_map(|frame| match frame {
            Frame::Body(body) => Some(body.key),
            _ => None,
        }) == Some(true)
    }

    fn push_body(&mut self, close: Close, key: bool) {
        self.stack.push(Frame::Body(BodyFrame { conjuncts: Vec::new(), close, key, negate: false }));
    }

    /// The label that `token` gives, where it gives one: `*` and, where
    /// `key` holds, `^` make the next label, whose echo goes to `forced`.
    fn label_token(&mut self, token: &Token, key: bool, forced: &mut Vec<Token>) -> Option<LabelUse> {
        let mut make = |state: &mut State| {
            let id = state.labels;
            state.labels += 1;
            forced.push(Token::Label(id));
            LabelId(id)
        };
        match token {
            Token::Control(Control::Fresh) => Some(LabelUse::Fresh(make(self))),
            Token::Control(Control::Key) if key => Some(LabelUse::Key(make(self))),
            Token::Control(Control::Zero) => Some(LabelUse::Zero),
            Token::Label(id) if *id < self.labels => Some(LabelUse::Join(LabelId(*id))),
            _ => None,
        }
    }

    fn offer(&mut self, context: &Context<'_>, token: &Token, forced: &mut Vec<Token>) -> Result<Offer, Unexpected> {
        match self.stack.last() {
            None => self.open_form(token, forced),
            Some(Frame::Clause(_)) => self.offer_clause(token),
            Some(Frame::One(_)) => self.offer_one(token),
            Some(Frame::Body(_)) => self.offer_body(context, token),
            Some(Frame::Atom(_)) => match token {
                Token::Column(position) => {
                    let atom = top!(self, Frame::Atom);
                    let column = atom.columns.get(*position as usize).ok_or("the relation has no column at the position")?.clone();
                    self.open_site(context, column);
                    Ok(Offer::Taken)
                }
                _ => Ok(Offer::Close { consumed: false }),
            },
            Some(Frame::Site(_)) => self.offer_site(token, forced),
            Some(Frame::Constraint(_)) => self.offer_constraint(token, forced),
            Some(Frame::Instance(_)) => self.offer_instance(context, token, forced),
            Some(Frame::KeyClause(clause)) => match (clause.stage, token) {
                (Naming::Named(Some(position)), Token::Control(Control::Skip)) => {
                    self.name_input(context, position + 1, forced);
                    Ok(Offer::Taken)
                }
                (Naming::Named(Some(position)), _) => {
                    top!(self, Frame::KeyClause).stage = Naming::Open;
                    self.open_input(context, position);
                    Ok(Offer::Again)
                }
                _ => Err("a key clause holds its body, then its inputs"),
            },
            Some(Frame::HeadSite(_)) => self.offer_head_site(token, forced),
            Some(Frame::Choose(_)) => self.offer_choose(token, forced),
            Some(Frame::Rigid(_)) => self.offer_rigid(context, token, forced),
            Some(Frame::Out) => unreachable!("an `OUT` form whose body stands open"),
            Some(Frame::Or(_) | Frame::Lists(_) | Frame::Input(_)) => unreachable!("a frame that stands below an open child"),
        }
    }

    /// The keyword of a form.
    fn open_form(&mut self, token: &Token, forced: &mut Vec<Token>) -> Result<Offer, Unexpected> {
        let frame = match token {
            Token::Control(Control::Rule) => Frame::Clause(ClauseFrame { keyword: ClauseKeyword::Rule, proposers: Vec::new(), stage: ClauseStage::Proposers }),
            Token::Control(Control::Det) => Frame::Clause(ClauseFrame { keyword: ClauseKeyword::Det, proposers: Vec::new(), stage: ClauseStage::Proposers }),
            Token::Control(Control::Init) => {
                Frame::Instance(InstanceFrame { first: self.next_slot(), component: None, key: None, inputs: Vec::new(), stage: Naming::Open })
            }
            Token::Control(Control::Choose) => {
                forced.push(Token::Column(0));
                Frame::Choose(ChooseFrame { rows: None, from: None, never: Vec::new(), stage: ChooseStage::For })
            }
            Token::Control(Control::RigidDet) => {
                forced.push(Token::Column(0));
                Frame::Rigid(RigidFrame { key: None, instance: None, parts: Vec::new(), stage: RigidStage::Key })
            }
            Token::Control(Control::Out) => {
                self.stack.push(Frame::Out);
                self.push_body(Close::List, true);
                return Ok(Offer::Taken);
            }
            _ => return Err("a form opens with its keyword"),
        };
        self.stack.push(frame);
        Ok(Offer::Taken)
    }

    /// A clause's proposers, and its marks and `END`. A clause that holds a
    /// proposer has no body, so a token other than a proposer closes its
    /// body empty and goes to its marks; a clause with no proposer opens its
    /// body.
    fn offer_clause(&mut self, token: &Token) -> Result<Offer, Unexpected> {
        let clause = top!(self, Frame::Clause);
        match (&clause.stage, token) {
            (ClauseStage::Proposers, Token::Proposer(name)) => {
                // A second naming of a proposer adds no reading to a line.
                if clause.proposers.contains(name) {
                    return Err("a clause names each proposer once");
                }
                // A line names several proposers, a reading per proposer, and each reading names its proposer alone.
                if matches!(clause.keyword, ClauseKeyword::Det | ClauseKeyword::Rule) && !clause.proposers.is_empty() {
                    return Err("a `DET` or `RULE` names one proposer");
                }
                clause.proposers.push(name.clone());
                Ok(Offer::Taken)
            }
            (ClauseStage::Proposers, _) if !clause.proposers.is_empty() => {
                clause.stage = ClauseStage::Marks { body: empty(), ones: Vec::new(), set: false };
                Ok(Offer::Again)
            }
            (ClauseStage::Proposers, _) => {
                clause.stage = ClauseStage::Body;
                self.push_body(Close::Clause, false);
                Ok(Offer::Again)
            }
            (ClauseStage::Marks { ones, set: false, .. }, Token::Control(Control::Set)) if ones.is_empty() => {
                let ClauseStage::Marks { set, .. } = &mut clause.stage else { unreachable!("a clause at its marks") };
                *set = true;
                Ok(Offer::Taken)
            }
            (ClauseStage::Marks { body, ones, .. }, Token::Control(Control::One)) => {
                if !new_key(&[], &made_labels(body.value()), ones, false) {
                    return Err(ONE_KEY_TWICE);
                }
                self.stack.push(Frame::One(Vec::new()));
                Ok(Offer::Taken)
            }
            (ClauseStage::Marks { .. }, Token::Control(Control::End)) => Ok(Offer::Close { consumed: true }),
            _ => Err("a clause's marks end with its `END`"),
        }
    }

    /// A `ONE` mark's key labels, then its `END`. A mark names key columns
    /// of its relation (`docs/arclog/constraints.md#one`): the labels that
    /// the clause's body keeps, which the body, complete before its marks,
    /// fixes. A label that the mark names already adds nothing to its key,
    /// and a mark whose labels, as a set, an earlier mark of the clause
    /// names keeps the rows that the earlier mark keeps, so the mark is
    /// refused at its first token after which every completion of it names
    /// a label twice or the labels of an earlier mark, as [`new_key`] gives.
    fn offer_one(&mut self, token: &Token) -> Result<Offer, Unexpected> {
        let marks = match self.stack.iter().rev().nth(1) {
            Some(Frame::Clause(ClauseFrame { stage: ClauseStage::Marks { body, ones, .. }, .. })) => Some((made_labels(body.value()), ones)),
            _ => None,
        };
        let Some(Frame::One(held)) = self.stack.last() else { unreachable!("a `ONE` mark stands on top") };
        match token {
            Token::Label(id) if *id < self.labels => {
                let label = LabelId(*id);
                if let Some((columns, ones)) = marks {
                    if !columns.contains(&label) {
                        return Err("a `ONE` mark names only columns of its clause, the labels that its body keeps");
                    }
                    if held.contains(&label) {
                        return Err("a `ONE` mark names each label once, since a label named twice adds nothing to its key");
                    }
                    let held: Vec<LabelId> = held.iter().copied().chain([label]).collect();
                    if !new_key(&held, &columns, ones, false) {
                        return Err(ONE_KEY_TWICE);
                    }
                }
                top!(self, Frame::One).push(label);
                Ok(Offer::Taken)
            }
            Token::Control(Control::End) => match marks {
                Some((columns, ones)) if !new_key(held, &columns, ones, true) => Err(ONE_KEY_TWICE),
                _ => Ok(Offer::Close { consumed: true }),
            },
            _ => Err("a `ONE` mark holds labels seen, then its `END`"),
        }
    }

    /// A body's conjuncts, then its closing token. `OR` opens an `OR` form
    /// wherever it stands, and `ALSO` closes a branch of one.
    fn offer_body(&mut self, context: &Context<'_>, token: &Token) -> Result<Offer, Unexpected> {
        let in_key = self.in_key();
        let in_out = matches!(self.stack.iter().rev().nth(1), Some(Frame::Out));
        // A `DET` whose body opens names no proposer, so a body of no conjunct gives it no value.
        let empty_det = matches!(&self.stack[..], [.., Frame::Clause(ClauseFrame { keyword: ClauseKeyword::Det, .. }), Frame::Body(BodyFrame { close: Close::Clause, conjuncts, .. })] if conjuncts.is_empty());
        // An `ALL` whose second list holds no conjunct holds wherever its domain has a member
        // (`docs/arclog/arclog.md#universal`), a second spelling.
        let empty_all = matches!(&self.stack[..], [.., Frame::Lists(ListsFrame { all: true, lists }), Frame::Body(BodyFrame { conjuncts, .. })] if lists.len() == 1 && conjuncts.is_empty());
        let body = top!(self, Frame::Body);
        if let Token::Control(control @ (Control::Not | Control::Op(_) | Control::Or | Control::If | Control::All)) = token {
            if in_out {
                return Err("an `OUT` form holds atoms alone");
            }
            if std::mem::take(&mut body.negate) {
                self.push_body(Close::Not, in_key);
                if *control == Control::Not {
                    top!(self, Frame::Body).negate = true;
                    return Ok(Offer::Taken);
                }
                return Ok(Offer::Again);
            }
            match control {
                Control::Not => body.negate = true,
                Control::Op(op) => self.stack.push(Frame::Constraint(ConstraintFrame { op: *op, first: None })),
                Control::Or => {
                    self.stack.push(Frame::Or(Vec::new()));
                    self.push_body(Close::Branch, in_key);
                }
                control => {
                    self.stack.push(Frame::Lists(ListsFrame { all: *control == Control::All, lists: Vec::new() }));
                    self.push_body(Close::List, in_key);
                }
            }
            return Ok(Offer::Taken);
        }
        if is_relation(token) {
            self.open_atom(context, token)?;
            return Ok(Offer::Taken);
        }
        let closes = match (body.close, token) {
            (Close::Not, _) => false,
            (_, Token::Control(Control::End)) => true,
            (Close::Clause, Token::Control(Control::One | Control::Set)) | (Close::Branch, Token::Control(Control::Also)) => true,
            _ => false,
        };
        match closes && !body.negate {
            true if empty_det => Err("a `DET` holds a body or names a proposer"),
            true if empty_all => Err("an `ALL` form's second list holds a conjunct, since an `ALL` with an empty second list holds wherever its domain has a member"),
            true => Ok(Offer::Close { consumed: true }),
            false => Err("a body holds its conjuncts, then its closing token"),
        }
    }

    /// Opens the atom of the relation token `token`.
    fn open_atom(&mut self, context: &Context<'_>, token: &Token) -> Result<(), Unexpected> {
        let registry = context.registry;
        let lib = |name: &LibName| match registry.entry(name) {
            Some(LibEntry::Relation(_) | LibEntry::Macro(_)) if component(registry, name).is_none() => Ok(RelationRef::Lib(name.clone())),
            _ => Err("the lib name is no relation"),
        };
        let (relation, columns): (RelationRef, Arc<[ColumnName]>) = match token {
            Token::Relation(slot) => {
                if self.stack.iter().any(|frame| matches!(frame, Frame::Instance(instance) if *slot >= instance.first)) && !self.reads_outputs(context) {
                    return Err("an instance's relations are read within it only by an input that reads its outputs");
                }
                let declared = self.declared.get(*slot as usize).filter(|declared| declared.readable).ok_or("the slot holds no relation that a read resolves")?;
                let relation = match &declared.relation {
                    ProgramRelation::Declared(name) => RelationRef::Declared(name.clone()),
                    ProgramRelation::Output(output) => RelationRef::Output(output.clone()),
                };
                (relation, declared.columns.clone())
            }
            Token::Fact(fact) => (RelationRef::Fact(*fact), Arc::from([])),
            Token::Lib(name) => (lib(name)?, Arc::from([])),
            _ => return Err("an atom opens with its relation"),
        };
        let columns = match token {
            Token::Relation(_) => columns,
            _ => typed_columns(registry, &relation).ok_or("the lib declares no columns of the relation")?.iter().map(|column| column.name.clone()).collect(),
        };
        let negated = match self.stack.last_mut() {
            Some(Frame::Body(body)) => std::mem::take(&mut body.negate),
            _ => false,
        };
        self.stack.push(Frame::Atom(AtomFrame { relation, columns, sites: Vec::new(), negated }));
        self.opened = Some(Opened);
        Ok(())
    }

    /// The relation of the atom on top, where one is open.
    /// The verdict at the key `key` of an atom of a relation that the finished forms declare.
    pub(super) fn atom_verdict(&self, key: u128) -> Option<super::atoms::HeldVerdict> {
        self.atom_verdicts.lock().expect("the atom verdicts are not poisoned").get(&key).cloned()
    }

    /// Keeps the verdict at the key `key`.
    pub(super) fn keep_atom_verdict(&self, key: u128, verdict: super::atoms::HeldVerdict) {
        self.atom_verdicts.lock().expect("the atom verdicts are not poisoned").insert(key, verdict);
    }

    /// Adds to `hasher` what the verdicts of the atom just opened read of the
    /// stack: its frames, and of its body whether a key stands, whether a `NOT`
    /// stands, how the body closes and whether it holds a conjunct. With
    /// `whole_form`, the component and the other bodies of an `INIT` form too,
    /// which the verdicts of an atom of a program's relation read.
    pub(super) fn atom_context(&self, whole_form: bool, hasher: &mut impl std::hash::Hasher) {
        use std::hash::Hash;
        for frame in &self.stack {
            std::mem::discriminant(frame).hash(hasher);
            match frame {
                Frame::Body(body) => {
                    body.key.hash(hasher);
                    body.negate.hash(hasher);
                    std::mem::discriminant(&body.close).hash(hasher);
                    body.conjuncts.is_empty().hash(hasher);
                }
                Frame::Atom(atom) => atom.negated.hash(hasher),
                Frame::Instance(instance) => {
                    instance.key.is_some().hash(hasher);
                    if whole_form {
                        instance.component.as_ref().map(|name| &*name.0).hash(hasher);
                        format!("{:?}", instance.key).hash(hasher);
                        format!("{:?}", instance.inputs).hash(hasher);
                    }
                }
                Frame::KeyClause(clause) => {
                    clause.body.is_some().hash(hasher);
                    if whole_form {
                        format!("{:?} {:?}", clause.body, clause.inputs).hash(hasher);
                    }
                }
                Frame::Input(input) if whole_form => input.position.hash(hasher),
                Frame::Or(branches) => {
                    branches.len().hash(hasher);
                    if whole_form {
                        format!("{branches:?}").hash(hasher);
                    }
                }
                _ => {}
            }
        }
        if self.labels >= 48 {
            self.labels.hash(hasher);
        }
    }

    /// The shape of each label at this state, where an atom just opened: its
    /// type, whether the body binds it, whether a key marks it and whether a
    /// `NOT` holds it, and whether each label has that shape. A label that stands in anything but an atom
    /// or a `NOT` of an atom of fixed scalar columns, or a head site of a fixed
    /// scalar column, in a top-level clause body or a body of an `INIT` form or
    /// a branch of an `OR` in one, has its id for its shape in place of them.
    pub(super) fn label_shapes(&self, registry: &Registry, column_type: &impl Fn(&RelationRef, &ColumnName) -> Option<ValueType>) -> (Vec<u64>, bool) {
        use std::hash::{Hash, Hasher};
        let by_id = |label: u32| (1u64 << 60) | u64::from(label);
        let mut shapes: Vec<u64> = (0..self.labels).map(by_id).collect();
        // The conjuncts in scope of the atom, with the conjuncts of the form's other bodies and its inputs, which give their labels types.
        let Some((Frame::Atom(_), frames)) = self.stack.split_last() else { return (shapes, false) };
        let Some(first_body) = frames.iter().position(|frame| matches!(frame, Frame::Body(_))) else { return (shapes, false) };
        let (around, bodies) = frames.split_at(first_body);
        let (before, instance, clause): (&[Conjunct], Option<&InstanceFrame>, Option<&KeyClauseFrame>) = match around {
            [Frame::Clause(_)] => (&[], None, None),
            [Frame::Instance(instance), Frame::KeyClause(clause)] => (&[], Some(instance), Some(clause)),
            [Frame::Instance(instance), Frame::Input(_)] => (&[], Some(instance), None),
            [Frame::Instance(instance), Frame::KeyClause(clause @ KeyClauseFrame { body: Some(key), .. }), Frame::Input(_)] => (&key.value().conjuncts[..], Some(instance), Some(clause)),
            _ => return (shapes, false),
        };
        let mut in_scope: Vec<&[Conjunct]> = vec![before];
        let mut other_bodies: Vec<&[Conjunct]> = Vec::new();
        let mut frames_left = bodies.iter();
        loop {
            let Some(Frame::Body(body)) = frames_left.next() else { return (shapes, false) };
            in_scope.push(&body.conjuncts);
            match frames_left.next() {
                None => break,
                Some(Frame::Or(branches)) => other_bodies.extend(branches.iter().map(|branch| &branch.value().conjuncts[..])),
                Some(_) => return (shapes, false),
            }
        }
        let mut inputs: Vec<&Node<InstanceInput>> = Vec::new();
        if let Some(instance) = instance {
            if let Some(key) = instance.key.as_ref().filter(|_| clause.is_none()) {
                other_bodies.push(&key.value().key.body.value().conjuncts);
                inputs.extend(key.value().inputs.iter());
            }
            inputs.extend(instance.inputs.iter());
        }
        if let Some(clause) = clause {
            inputs.extend(clause.inputs.iter());
        }
        other_bodies.extend(inputs.iter().map(|input| &input.value().body.value().conjuncts[..]));
        // The atoms of a conjunct: a form of a body other than an `OR` gives no shape.
        fn atoms_of<'c>(conjunct: &'c Conjunct, found: &mut Vec<&'c Node<Atom>>) -> bool {
            match conjunct {
                Conjunct::Atom(atom) | Conjunct::Not(Negated::Atom(atom)) => {
                    found.push(atom);
                    true
                }
                Conjunct::Or(branches) => branches.iter().all(|branch| branch.value().conjuncts.iter().all(|conjunct| atoms_of(conjunct, found))),
                _ => false,
            }
        }
        let mut atoms: Vec<&Node<Atom>> = Vec::new();
        for conjunct in in_scope.iter().chain(other_bodies.iter()).flat_map(|body| body.iter()) {
            if !atoms_of(conjunct, &mut atoms) {
                return (shapes, false);
            }
        }
        let mut types: std::collections::BTreeMap<u32, ValueType> = std::collections::BTreeMap::new();
        let mut keys: Vec<u32> = Vec::new();
        let meet = |types: &mut std::collections::BTreeMap<u32, ValueType>, label: u32, ty: &ValueType| -> bool {
            match types.get(&label) {
                Some(old) => match old.meet(ty) {
                    Meet::Type(ty) => {
                        types.insert(label, ty);
                        true
                    }
                    Meet::Empty => false,
                },
                None => {
                    types.insert(label, ty.clone());
                    true
                }
            }
        };
        for prior in atoms.iter() {
            for site in prior.value().sites.iter() {
                let Some(ty) = column_type(&prior.value().relation, &site.column) else { return (shapes, false) };
                for arg in site.value.args.iter() {
                    let SiteArg::Label(use_) = arg else { return (shapes, false) };
                    let label = match use_ {
                        LabelUse::Fresh(label) | LabelUse::Join(label) => label,
                        LabelUse::Key(label) => {
                            keys.push(label.0);
                            label
                        }
                        LabelUse::Zero => continue,
                    };
                    if !meet(&mut types, label.0, &ty) {
                        return (shapes, false);
                    }
                }
            }
        }
        for input in &inputs {
            for site in input.value().head.iter() {
                let port = self.component_from_input(registry).inputs.iter().find(|declared| declared.port.name == input.value().name).map(|declared| &declared.port);
                let ty = port.and_then(|port| port.columns.iter().find(|column| column.name == site.column)).and_then(|column| scalar_fixed(&column.ty));
                let Some(ty) = ty else { return (shapes, false) };
                for arg in site.value.args.iter() {
                    let SiteArg::Label(LabelUse::Fresh(label) | LabelUse::Join(label) | LabelUse::Key(label)) = arg else { return (shapes, false) };
                    if !meet(&mut types, label.0, &ty) {
                        return (shapes, false);
                    }
                }
            }
        }
        let list: Vec<&Conjunct> = in_scope.iter().flat_map(|body| body.iter()).collect();
        // A check refuses a label that a `NOT` holds before a conjunct binds it, where no other label of that type and binding is refused.
        let negated: Vec<u32> = list.iter().flat_map(|conjunct| match conjunct {
            Conjunct::Not(Negated::Atom(atom)) => atom.value().sites.iter().flat_map(|site| site.value.args.iter()).filter_map(|arg| match arg {
                SiteArg::Label(LabelUse::Fresh(label) | LabelUse::Join(label) | LabelUse::Key(label)) => Some(label.0),
                _ => None,
            }).collect::<Vec<u32>>(),
            _ => Vec::new(),
        }).collect();
        let bound = crate::safety::bound_labels(&list, &Default::default(), &Default::default(), &|atom| crate::eval::ir::atom_modes(registry, atom), &|label| types.get(&label.0).cloned());
        // The labels in the atom's scope: those of the conjuncts of its bodies
        // outside an `OR`, and of a keyed input's key body those that the key
        // marks. A label of a branch of an `OR`, of another body alone, or of a
        // key body that the key does not mark, stands in another scope, and a
        // check can tell it from a label in scope of its type and binding, so
        // it has its id for its shape.
        let mut scoped: std::collections::BTreeSet<u32> = std::collections::BTreeSet::new();
        for (at, body) in in_scope.iter().enumerate() {
            for conjunct in body.iter() {
                let (Conjunct::Atom(atom) | Conjunct::Not(Negated::Atom(atom))) = conjunct else { continue };
                for arg in atom.value().sites.iter().flat_map(|site| site.value.args.iter()) {
                    match arg {
                        SiteArg::Label(LabelUse::Key(label)) => {
                            scoped.insert(label.0);
                        }
                        SiteArg::Label(LabelUse::Fresh(label) | LabelUse::Join(label)) if at > 0 || instance.is_none() => {
                            scoped.insert(label.0);
                        }
                        _ => {}
                    }
                }
            }
        }
        let mut each = true;
        for (at, shape) in shapes.iter_mut().enumerate() {
            match types.get(&(at as u32)).filter(|_| scoped.contains(&(at as u32))) {
                Some(ty) => {
                    let mut hasher = crate::hash::StableHasher::new();
                    ty.hash(&mut hasher);
                    bound.contains(&LabelId(at as u32)).hash(&mut hasher);
                    keys.contains(&(at as u32)).hash(&mut hasher);
                    negated.contains(&(at as u32)).hash(&mut hasher);
                    *shape = (1u64 << 59) | (hasher.finish() >> 8);
                }
                None => each = false,
            }
        }
        (shapes, each)
    }

    /// The conjuncts of the body that are atoms of the relation of the atom just
    /// opened, a `NOT` of one included: for each, whether it is negated, and the
    /// column position and the label of each value of its sites, in order, with
    /// `u32::MAX` for a value that is no label.
    pub(super) fn prior_atoms(&self) -> Vec<(bool, Vec<(u32, u32)>)> {
        fn values(column: u32, args: &[SiteArg], found: &mut Vec<(u32, u32)>) {
            for arg in args {
                let label = match arg {
                    SiteArg::Label(label) | SiteArg::NamedLabel { label, .. } => label,
                    SiteArg::Field(site) => {
                        values(column, &site.value.args, found);
                        continue;
                    }
                };
                found.push((column, match label {
                    LabelUse::Fresh(label) | LabelUse::Join(label) | LabelUse::Key(label) => label.0,
                    LabelUse::Zero => u32::MAX,
                }));
            }
        }
        let Some(Frame::Atom(open)) = self.stack.last() else { return Vec::new() };
        let Some(Frame::Body(body)) = self.stack.iter().rev().nth(1) else { return Vec::new() };
        let mut found = Vec::new();
        for conjunct in &body.conjuncts {
            let (negated, atom) = match conjunct {
                Conjunct::Atom(atom) => (false, atom),
                Conjunct::Not(Negated::Atom(atom)) => (true, atom),
                _ => continue,
            };
            if atom.value().relation != open.relation {
                continue;
            }
            let mut sites = Vec::new();
            for site in atom.value().sites.iter() {
                let column = open.columns.iter().position(|name| *name == site.column).map_or(u32::MAX, |at| at as u32);
                values(column, &site.value.args, &mut sites);
            }
            found.push((negated, sites));
        }
        found
    }

    /// Whether the form in progress is one whose closing token reads the rows of
    /// the task: a `DET` or a `RIGID_DET`.
    pub(super) fn closes_a_det(&self) -> bool {
        matches!(self.stack.first(), Some(Frame::Clause(ClauseFrame { keyword: ClauseKeyword::Det | ClauseKeyword::DetOrRule, .. }) | Frame::Rigid(_)))
    }

    /// The conjuncts of the key body where the next token may open a body of
    /// an `INIT` form, as the engine named it: none for the key body and for an
    /// input that holds for every key. `None` at any other state.
    pub(super) fn named_body_before(&self) -> Option<&[Conjunct]> {
        match &self.stack[..] {
            [Frame::Instance(InstanceFrame { stage: Naming::Named(_), .. })] => Some(&[]),
            [Frame::Instance(_), Frame::KeyClause(KeyClauseFrame { stage: Naming::Named(_), body: Some(key), .. })] => Some(&key.value().conjuncts),
            _ => None,
        }
    }

    /// Whether the body on top stands in a form of a body other than a branch of an `OR`.
    pub(super) fn in_other_form(&self) -> bool {
        self.stack.iter().any(|frame| matches!(frame, Frame::Lists(_) | Frame::Body(BodyFrame { close: Close::Not, .. })))
    }

    /// Whether `token` would close the site open on top while the site holds
    /// no value: a token that is no label, no label mark and no column token
    /// that makes the site a record's. The checks refuse a complete site of no
    /// value, so no completion of the program the token gives passes them.
    pub(super) fn closes_an_empty_site(&self, token: &Token) -> bool {
        let Some(Frame::Site(site)) = self.stack.last() else { return false };
        if site.field.is_some() || site.record.is_some() || !site.args.is_empty() {
            return false;
        }
        let value = matches!(token, Token::Label(_) | Token::Control(Control::Fresh | Control::Key | Control::Zero));
        !value && !(site.unbound && matches!(token, Token::Column(_)))
    }

    /// Whether a `NOT` stands before the next conjunct of the body on top.
    pub(super) fn negation_pending(&self) -> bool {
        self.stack.iter().rev().find_map(|frame| match frame {
            Frame::Body(body) => Some(body.negate),
            _ => None,
        }).unwrap_or(false)
    }

    /// Whether the form in progress is a clause that stands once for the task:
    /// a clause's keyword alone sets that.
    pub(super) fn clause_is_task_wide(&self) -> bool {
        matches!(self.stack.first(), Some(Frame::Clause(ClauseFrame { keyword: ClauseKeyword::Det | ClauseKeyword::DetOrRule, .. })))
    }

    /// The names of the columns of the atom just opened, and whether it holds no site.
    pub(super) fn open_atom_columns(&self) -> Option<(Arc<[ColumnName]>, bool)> {
        match self.stack.last() {
            Some(Frame::Atom(atom)) => Some((Arc::clone(&atom.columns), atom.sites.is_empty())),
            _ => None,
        }
    }

    /// Where the state stands within an open atom, none outside one.
    pub(super) fn atom_place(&self) -> Option<AtomPlace> {
        match self.stack.last()? {
            Frame::Atom(_) => Some(AtomPlace::Sites),
            Frame::Site(site) => Some(if site.record.is_none() && !site.args.is_empty() { AtomPlace::Sites } else { AtomPlace::Value }),
            _ => None,
        }
    }

    pub(super) fn open_relation(&self) -> Option<RelationRef> {
        match self.stack.last() {
            Some(Frame::Atom(atom)) => Some(atom.relation.clone()),
            _ => None,
        }
    }

    /// Adds the Example column to the columns of the atom on top, which a
    /// step opened as its last change, where `reads_example` says that the
    /// read of its relation reads one.
    fn add_example_column(&mut self, reads_example: ReadsExample<'_>) {
        let (program, open) = self.partial().expect("a form that shows its atom");
        let at = self.absolute(&open.expect("an open atom"));
        let atom = top!(self, Frame::Atom);
        if reads_example(&program, &at, &atom.relation) {
            atom.columns = std::iter::once(example()).chain(atom.columns.iter().cloned()).collect();
        }
    }

    /// Opens the site on `column` of the atom on top. A site on a column of
    /// a type parameter holds a record where the resolver places one there.
    /// The resolver places a record of no field on a parameter that no site
    /// binds, and no site reads such a record, so a site there is on a
    /// parameter that the `INIT` form in progress binds later
    /// ([`SiteFrame::unbound`]).
    fn open_site(&mut self, context: &Context<'_>, column: ColumnName) {
        let typed = type_parameter(&column);
        let own = self.reads_own_output();
        self.stack.push(Frame::Site(SiteFrame { column, args: Vec::new(), record: None, field: None, unbound: false }));
        if typed {
            let (program, open) = self.partial().expect("a form that shows its site");
            let at = self.absolute(&open.expect("an open site"));
            let record = self.resolved_partial(&program, context.registry).column_group(&at).map(|group| group.len);
            let site = top!(self, Frame::Site);
            match record {
                Some(0) if own => site.unbound = true,
                record => site.record = record,
            }
        }
    }

    /// Whether the atom on top reads an output of the `INIT` form in
    /// progress.
    fn reads_own_output(&self) -> bool {
        let Some(Frame::Atom(atom)) = self.stack.last() else { return false };
        let Some(first) = self.stack.iter().find_map(|frame| match frame {
            Frame::Instance(instance) => Some(instance.first),
            _ => None,
        }) else {
            return false;
        };
        matches!(&atom.relation, RelationRef::Output(output) if output.of == OutputOwner::Instance(InstanceName(DeclaredName::Slot(first))))
    }

    /// The path in the program of the node at `open` in the form in
    /// progress.
    fn absolute(&self, open: &NodePath) -> NodePath {
        NodePath::top(self.program.value().forms.len() as u32).join(open)
    }

    /// A site's labels; on a record, each field's column token and label,
    /// then `END`.
    fn offer_site(&mut self, token: &Token, forced: &mut Vec<Token>) -> Result<Offer, Unexpected> {
        let in_key = self.in_key();
        // Every site of a `NOT` atom joins (`docs/arclog/arclog.md#negation-and-constraints`).
        if self.in_negated_atom() && matches!(token, Token::Control(Control::Fresh | Control::Key)) {
            return Err("a site of a `NOT` atom makes no label: every site of the atom joins");
        }
        let site = top!(self, Frame::Site);
        let (field, record) = (site.field, site.record);
        // A field's column token as the first token of a site on a parameter not yet bound makes the site a record's,
        // whose fields the projection that binds the parameter gives later.
        if let (true, true, None, Token::Column(first)) = (site.unbound, site.args.is_empty(), record, token) {
            site.record = Some(u16::MAX);
            site.field = Some(*first);
            return Ok(Offer::Taken);
        }
        match (field, record, token) {
            (Some(field), _, _) => {
                let label = self.label_token(token, in_key, forced).ok_or("a field's column token is followed by its label")?;
                let site = top!(self, Frame::Site);
                let name = ColumnName::Slot(field);
                site.args.push(field_arg(&site.column, name, label));
                site.field = None;
                return Ok(Offer::Taken);
            }
            (None, Some(fields), Token::Column(field)) if *field < u32::from(fields) => {
                // The site rule applies at every level (`docs/arclog/arclog.md#sites`): a field takes one site, as a column does.
                let name = ColumnName::Slot(*field);
                if site.args.iter().any(|arg| matches!(arg, SiteArg::NamedLabel { name: held, .. } | SiteArg::Field(Site { column: held, .. }) if *held == name)) {
                    return Err("a site on a record holds one field site on each field");
                }
                site.field = Some(*field);
                return Ok(Offer::Taken);
            }
            (None, Some(_), Token::Control(Control::End)) => return Ok(Offer::Close { consumed: true }),
            // A site on a record names its fields by their column tokens. A bare label there would take the
            // number of its label as the name of its field, so the mask would read the label's number.
            (None, Some(_), Token::Label(_) | Token::Control(Control::Fresh | Control::Key)) => return Err("a site on a record holds field columns, then `END`"),
            _ => {}
        }
        match self.label_token(token, in_key, forced) {
            Some(label) => {
                let site = top!(self, Frame::Site);
                // A column of a fixed type takes one label (`docs/arclog/arclog.md#sites`), as at a head site.
                if !type_parameter(&site.column) && !site.args.is_empty() {
                    return Err("a column of a fixed type takes one label");
                }
                // So does a column of a type parameter that one label binds, where the resolver gives the site no
                // record (`docs/arclog/arclog.md#instance`). A parameter that no site binds yet waits for its binding.
                if type_parameter(&site.column) && site.record.is_none() && !site.unbound && !site.args.is_empty() {
                    return Err("a column of a type parameter that one label binds takes one label");
                }
                site.args.push(bare_arg(&site.column, label));
                Ok(Offer::Taken)
            }
            None if record.is_some() => Err("a site on a record ends with `END`"),
            None => Ok(Offer::Close { consumed: false }),
        }
    }

    fn offer_constraint(&mut self, token: &Token, forced: &mut Vec<Token>) -> Result<Offer, Unexpected> {
        let under_not = matches!(self.stack.iter().rev().nth(1), Some(Frame::Body(BodyFrame { close: Close::Not, .. })));
        let label = self.label_token(token, false, forced).ok_or("a constraint holds a label, then a label or `0`")?;
        let constraint = top!(self, Frame::Constraint);
        let Some(first) = constraint.first else {
            let first = ConstraintLabel::try_from(label).map_err(|_| "a constraint's first operand is a label")?;
            // `(NOT (= *X Y))` holds nowhere, so a `=` under a `NOT` makes no label
            // (`docs/arclog/arclog.md#negation-and-constraints`).
            if under_not && first.fresh && constraint.op == ConstraintOp::Eq {
                return Err("`=` under a `NOT` makes no label, since the `NOT` of it holds nowhere");
            }
            constraint.first = Some(first);
            return Ok(Offer::Taken);
        };
        let second = match label {
            LabelUse::Zero => Operand::Zero,
            label => Operand::Label(ConstraintLabel::try_from(label).expect("a label")),
        };
        // `=`, `<=` and `>=` of a label with itself hold wherever the label is bound, and `!=`, `<` and `>` of a
        // label with itself hold nowhere, so the second label of a constraint is not its first.
        if matches!(second, Operand::Label(second) if second.label == first.label) {
            return Err(crate::program::self_comparison_refusal(constraint.op));
        }
        let conjunct = Conjunct::Constraint(Constraint { op: constraint.op, first, second });
        self.stack.pop();
        let body = top!(self, Frame::Body);
        body.conjuncts.push(conjunct);
        self.close_not();
        Ok(Offer::Taken)
    }

    fn offer_instance(&mut self, context: &Context<'_>, token: &Token, forced: &mut Vec<Token>) -> Result<Offer, Unexpected> {
        let instance = top!(self, Frame::Instance);
        match (instance.component.is_some(), instance.stage, token) {
            (false, _, Token::Lib(name)) => {
                let declared = component(context.registry, name).ok_or("an `INIT` names a component")?;
                instance.component = Some(name.clone());
                instance.stage = Naming::Named(None);
                let first = instance.first;
                let owner = OutputOwner::Instance(InstanceName(DeclaredName::Slot(first)));
                let every: Vec<&PortName> = declared.inputs.iter().map(|input| &input.port.name).collect();
                for port in declared.relation_ports(&every) {
                    let output = OutputName { of: owner.clone(), path: [OutputStep::Port(port.name.clone())].into() };
                    let readable = declared.outputs.iter().any(|output| output.name == port.name);
                    self.declare(ProgramRelation::Output(output), port.columns.iter().map(|column| column.name.clone()).collect(), readable);
                }
                forced.extend((first..self.next_slot()).map(Token::Relation));
                forced.push(Token::Column(0));
                Ok(Offer::Taken)
            }
            (true, Naming::Named(None), Token::Control(Control::Skip)) => {
                self.name_input(context, 0, forced);
                Ok(Offer::Taken)
            }
            (true, Naming::Named(None), _) => {
                instance.stage = Naming::Open;
                self.stack.push(Frame::KeyClause(KeyClauseFrame { body: None, inputs: Vec::new(), stage: Naming::Open }));
                self.push_body(Close::List, true);
                Ok(Offer::Again)
            }
            (true, Naming::Named(Some(position)), Token::Control(Control::Skip)) => {
                if let Some(refusal) = self.declines_a_need(context, position) {
                    return Err(refusal);
                }
                self.name_input(context, position + 1, forced);
                Ok(Offer::Taken)
            }
            (true, Naming::Named(Some(position)), _) => {
                instance.stage = Naming::Open;
                self.open_input(context, position);
                Ok(Offer::Again)
            }
            _ => Err("an `INIT` names its component"),
        }
    }

    /// The refusal of a `SKIP` after the engine's name of the input at
    /// `position` of the `INIT` form on top, after its key clause, where the
    /// `SKIP` leaves the component with no output for certain
    /// (`docs/engine/arclog-stream.md#token-stream`): the input is marked
    /// `required`, or it is the last input of a `one-of` group that the form
    /// writes no input of, and the `SKIP`s leave each input of the group with
    /// no row. A `SKIP` leaves an input with no row for certain
    /// where the input has no default rows, and it is not marked `from-key`
    /// or the form's key has no column. The registry gives the marks to no
    /// input with default rows, and to no input marked `from-key` whose one
    /// column is `key`, which the instance fills where its key has no column
    /// too.
    fn declines_a_need(&self, context: &Context<'_>, position: usize) -> Option<Unexpected> {
        let instance = self.instance();
        let component = self.component(context);
        let key = instance.key.as_ref();
        let key_columns = key.is_some_and(|key| !key.value().key.columns.is_empty());
        let input = &component.inputs[position];
        match &input.need {
            Some(Need::Required) if input.holds_no_row_unwritten(key_columns) => {
                Some("an `INIT` form writes each input that its component requires, where no key column fills the input: `SKIP` leaves it with no row, and the component then gives no output")
            }
            Some(Need::OneOf(groups)) => {
                let written: Vec<&PortName> = written_inputs(key, &instance.inputs).map(|input| &input.name).collect();
                let leaves_a_group_empty = groups.iter().any(|group| component.last_of_group(group) == Some(position) && component.group_is_empty(group, &written, key_columns));
                leaves_a_group_empty.then_some("an `INIT` form writes an input of each `one-of` group of its component, where no key column fills one: `SKIP` at a group's last input leaves the group with no row, and the component then gives no output")
            }
            _ => None,
        }
    }

    /// A projection's column: its labels, or its fields, each a column
    /// token and a label, then the record's `END`; then the column's `END`.
    fn offer_head_site(&mut self, token: &Token, forced: &mut Vec<Token>) -> Result<Offer, Unexpected> {
        let counted = self.last_of_a_counted_head();
        let site = top!(self, Frame::HeadSite);
        if let Some(field) = site.field {
            let label = self.label_token(token, false, forced).ok_or("a field's column token is followed by its label")?;
            let site = top!(self, Frame::HeadSite);
            let name = ColumnName::Slot(field);
            site.args.push(field_arg(&site.column, name, label));
            site.field = None;
            site.fields += 1;
            return Ok(Offer::Taken);
        }
        let parameter = type_parameter(&site.column);
        match token {
            Token::Control(Control::End) => {
                let record = site.fields > 0 || site.args.len() > 1;
                if record && !site.record_ended {
                    site.record_ended = true;
                    return Ok(Offer::Taken);
                }
                if counted && site.args.is_empty() {
                    return Err("the head of a `Cardinality` instance's `member` input, or of an `Excess` instance's `plus` or `minus` input, holds a site, since such an input of no column holds at most one row at each key, so the count of its rows is 0 or 1");
                }
                Ok(Offer::Close { consumed: true })
            }
            _ if site.record_ended => Err("a projection's column ends with `END`"),
            Token::Column(_) if !parameter => Err("a column of a fixed type takes one label"),
            _ if !parameter && !site.args.is_empty() => Err("a column of a fixed type takes one label"),
            Token::Column(field) if *field == site.fields => {
                site.field = Some(*field);
                Ok(Offer::Taken)
            }
            _ => {
                let label = self.label_token(token, false, forced).ok_or("a projection holds labels, then `END`")?;
                let site = top!(self, Frame::HeadSite);
                if let LabelUse::Fresh(id) | LabelUse::Join(id) | LabelUse::Key(id) = label {
                    site.last_bare = Some(id.0);
                }
                site.args.push(bare_arg(&site.column, label));
                Ok(Offer::Taken)
            }
        }
    }

    /// Whether the projection on top is the last of an input of
    /// [`COUNTED_INPUTS`] whose head holds no site yet, so that the `END` of
    /// an empty projection leaves the head with no site.
    fn last_of_a_counted_head(&self) -> bool {
        let Some(Frame::Input(input)) = self.stack.iter().rev().nth(1) else { return false };
        if input.column + 1 != input.columns.len() || !input.head.is_empty() {
            return false;
        }
        let instance = self.instance();
        let counted = |component: &LibName| COUNTED_INPUTS.iter().any(|(name, port)| *name == &*component.0 && *port == &*input.name.0);
        instance.component.as_ref().is_some_and(counted)
    }

    fn offer_choose(&mut self, token: &Token, forced: &mut Vec<Token>) -> Result<Offer, Unexpected> {
        let choose = top!(self, Frame::Choose);
        let skip = *token == Token::Control(Control::Skip);
        match (choose.stage, skip) {
            (ChooseStage::For, true) => {
                choose.stage = ChooseStage::FromOpen;
                forced.push(Token::Column(1));
                self.push_body(Close::List, false);
                Ok(Offer::Taken)
            }
            (ChooseStage::For, false) => {
                choose.stage = ChooseStage::ForOpen;
                self.push_body(Close::List, true);
                Ok(Offer::Again)
            }
            (ChooseStage::Never, true) => {
                self.finish_choose(forced);
                Ok(Offer::Taken)
            }
            (ChooseStage::Never, false) => {
                choose.stage = ChooseStage::NeverOpen;
                self.push_body(Close::List, false);
                Ok(Offer::Again)
            }
            (ChooseStage::NeverEnd, _) => match token {
                Token::Control(Control::Also) => {
                    choose.stage = ChooseStage::NeverOpen;
                    self.push_body(Close::List, false);
                    Ok(Offer::Taken)
                }
                Token::Control(Control::End) => {
                    self.finish_choose(forced);
                    Ok(Offer::Taken)
                }
                _ => Err("a `never` body is followed by `ALSO` and the next, or by the form's `END`"),
            },
            _ => unreachable!("a `CHOOSE` form whose body stands open"),
        }
    }

    fn offer_rigid(&mut self, context: &Context<'_>, token: &Token, forced: &mut Vec<Token>) -> Result<Offer, Unexpected> {
        let rigid = top!(self, Frame::Rigid);
        let skip = *token == Token::Control(Control::Skip);
        match (rigid.stage, skip) {
            (RigidStage::Key, true) => {
                rigid.stage = RigidStage::Instance;
                forced.push(Token::Column(1));
                Ok(Offer::Taken)
            }
            (RigidStage::Instance, true) => {
                rigid.stage = RigidStage::Parts;
                Ok(Offer::Taken)
            }
            (RigidStage::Key, false) | (RigidStage::Instance, false) => {
                rigid.stage = if rigid.stage == RigidStage::Key { RigidStage::KeyOpen } else { RigidStage::InstanceOpen };
                self.push_body(Close::List, true);
                Ok(Offer::Again)
            }
            (RigidStage::Parts, _) if *token == Token::Control(Control::End) => Ok(Offer::Close { consumed: true }),
            (RigidStage::Parts, _) if is_relation(token) => {
                let taken: Vec<OutputStep> = rigid.parts.iter().filter_map(|part| part_steps(&part.value().relation)?.into_iter().next()).collect();
                self.open_atom(context, token)?;
                let begins = self.open_relation().and_then(|relation| part_steps(&relation)?.into_iter().next());
                if begins.is_some_and(|step| taken.contains(&step)) {
                    return Err("the output of a part of a `RIGID_DET` form begins with a step that the output of an earlier part begins with");
                }
                Ok(Offer::Taken)
            }
            _ => Err("a `RIGID_DET` form's parts are atoms, then its `END`"),
        }
    }

    /// Pops the top frame and gives its node, or none where the frame
    /// below has taken it.
    fn close(&mut self, context: &Context<'_>, forced: &mut Vec<Token>) -> Result<Option<Built>, Unexpected> {
        let frame = self.stack.pop().expect("an open frame");
        let built = match frame {
            Frame::Clause(clause) => {
                let ClauseStage::Marks { body, ones, set } = clause.stage else { unreachable!("a clause closes at its marks' `END`") };
                let slot = self.next_slot();
                let columns = slot_columns(made_labels(body.value()), 0);
                let names: Arc<[ColumnName]> = match (columns.is_empty(), clause.proposers.first()) {
                    (true, Some(proposer)) => proposer_columns(context.registry, proposer).ok_or("a clause's proposer is one the lib names")?.into(),
                    _ => columns.iter().map(|column| column.name.clone()).collect(),
                };
                let derives = ProgramRelation::Declared(RelationName(DeclaredName::Slot(slot)));
                let value = Clause { keyword: clause.keyword, derives: derives.clone(), gloss: None, proposers: clause.proposers.into(), body, ones: ones.into(), set, columns };
                self.declare(derives, names, true);
                forced.push(Token::Relation(slot));
                Built::Form(Form::Clause(Node::new(value)))
            }
            Frame::One(key) => {
                let clause = top!(self, Frame::Clause);
                let ClauseStage::Marks { ones, .. } = &mut clause.stage else { unreachable!("a mark stands on its clause's marks") };
                ones.push(OneMark { key: key.into() });
                return Ok(None);
            }
            Frame::Body(body) => Built::Body(Node::new(Body { conjuncts: body.conjuncts.into() })),
            Frame::Atom(atom) => Built::Atom { atom: Node::new(Atom { relation: atom.relation, sites: atom.sites.into() }), negated: atom.negated },
            Frame::Site(site) => Built::Site(Site { column: site.column, value: SiteValue { args: site.args.into() } }),
            Frame::HeadSite(site) => Built::HeadSite((!site.args.is_empty()).then(|| Site { column: site.column, value: SiteValue { args: site.args.into() } })),
            Frame::Rigid(rigid) => {
                let name = RigidDetName(DeclaredName::Slot(self.next_slot()));
                let value = RigidDet { name: name.clone(), key: rigid.key, instance: rigid.instance, parts: rigid.parts.into() };
                for (steps, columns) in rigid_outputs(&value) {
                    let output = OutputName { of: OutputOwner::RigidDet(name.clone()), path: steps };
                    let slot = self.declare(ProgramRelation::Output(output), columns.names().cloned().collect(), true);
                    forced.push(Token::Relation(slot));
                }
                Built::Form(Form::RigidDet(Node::new(value)))
            }
            Frame::Constraint(_) | Frame::Or(_) | Frame::Lists(_) | Frame::Instance(_) | Frame::KeyClause(_) | Frame::Input(_) | Frame::Choose(_) | Frame::Out => {
                unreachable!("a frame that its own offer or its child's delivery closes")
            }
        };
        Ok(Some(built))
    }

    /// Gives `built`, the node of the frame that closed on `closer`, to the
    /// frame below it.
    fn deliver(&mut self, context: &Context<'_>, built: Built, closer: Option<&Token>, forced: &mut Vec<Token>) -> Result<(), Unexpected> {
        if let Built::Form(form) = built {
            self.finish_form(form);
            return Ok(());
        }
        let in_key = self.in_key();
        let ends = closer == Some(&Token::Control(Control::End));
        match (self.stack.last_mut().expect("a frame below"), built) {
            (Frame::Clause(clause), Built::Body(body)) => {
                let set = closer == Some(&Token::Control(Control::Set));
                clause.stage = ClauseStage::Marks { body, ones: Vec::new(), set };
                match (ends, set) {
                    (true, _) => {
                        if let Some(built) = self.close(context, forced)? {
                            self.deliver(context, built, closer, forced)?;
                        }
                    }
                    (false, true) => {}
                    (false, false) => self.stack.push(Frame::One(Vec::new())),
                }
            }
            (Frame::Body(body), Built::Conjunct(conjunct)) => {
                body.conjuncts.push(conjunct);
                self.close_not();
            }
            (Frame::Body(body), Built::Atom { atom, negated }) => {
                body.conjuncts.push(if negated { Conjunct::Not(Negated::Atom(atom)) } else { Conjunct::Atom(atom) });
                self.close_not();
            }
            (Frame::Rigid(rigid), Built::Atom { atom, .. }) => rigid.parts.push(atom),
            (Frame::Atom(atom), Built::Site(site)) => atom.sites.push(site),
            (Frame::Or(branches), Built::Body(body)) => {
                branches.push(body);
                match ends {
                    true => {
                        let Some(Frame::Or(branches)) = self.stack.pop() else { unreachable!("the `OR` stands on top") };
                        self.deliver(context, Built::Conjunct(Conjunct::Or(branches.into())), None, forced)?;
                    }
                    false => self.push_body(Close::Branch, in_key),
                }
            }
            (Frame::Lists(lists), Built::Body(body)) => {
                lists.lists.push(body);
                if lists.lists.len() < if lists.all { 2 } else { 3 } {
                    self.push_body(Close::List, in_key);
                } else {
                    let Some(Frame::Lists(ListsFrame { all, lists })) = self.stack.pop() else { unreachable!("the lists stand on top") };
                    let conjunct = match all {
                        false => {
                            let [test, then, otherwise] = <[Node<Body>; 3]>::try_from(lists).expect("an `IF` form's three lists");
                            Conjunct::If { test, then, otherwise }
                        }
                        true => {
                            let [domain, body] = <[Node<Body>; 2]>::try_from(lists).expect("an `ALL` form's two lists");
                            Conjunct::All { domain, body }
                        }
                    };
                    self.deliver(context, Built::Conjunct(conjunct), None, forced)?;
                }
            }
            (Frame::KeyClause(clause), Built::Body(body)) => {
                clause.body = Some(body);
                self.name_input(context, 0, forced);
            }
            (Frame::KeyClause(KeyClauseFrame { inputs, .. }) | Frame::Instance(InstanceFrame { inputs, .. }), Built::Input { input, position }) => {
                inputs.push(input);
                self.name_input(context, position + 1, forced);
            }
            (Frame::Input(input), Built::Body(body)) => {
                input.body = Some(body);
                if let Some(built) = self.next_column(forced) {
                    self.deliver(context, built, None, forced)?;
                }
            }
            (Frame::Input(input), Built::HeadSite(site)) => {
                input.head.extend(site);
                input.column += 1;
                if let Some(built) = self.next_column(forced) {
                    self.deliver(context, built, None, forced)?;
                }
            }
            (Frame::Out, Built::Body(body)) => {
                self.stack.pop();
                self.finish_form(Form::Out(Node::new(Out { key: key_body(body) })));
            }
            (Frame::Choose(choose), Built::Body(body)) => match choose.stage {
                ChooseStage::ForOpen => {
                    choose.rows = Some(key_body(body));
                    choose.stage = ChooseStage::FromOpen;
                    forced.push(Token::Column(1));
                    self.push_body(Close::List, false);
                }
                ChooseStage::FromOpen => {
                    choose.from = Some(body);
                    choose.stage = ChooseStage::Never;
                    forced.push(Token::Column(2));
                }
                _ => {
                    choose.never.push(body);
                    choose.stage = ChooseStage::NeverEnd;
                }
            },
            (Frame::Rigid(rigid), Built::Body(body)) => match rigid.stage {
                RigidStage::KeyOpen => {
                    rigid.key = Some(key_body(body));
                    rigid.stage = RigidStage::Instance;
                    forced.push(Token::Column(1));
                }
                _ => {
                    rigid.instance = Some(key_body(body));
                    rigid.stage = RigidStage::Parts;
                }
            },
            _ => unreachable!("a node that the frame below takes"),
        }
        Ok(())
    }

    /// Closes the `NOT` over a form on top, which holds its one conjunct,
    /// and each that its close completes.
    fn close_not(&mut self) {
        while let Some(Frame::Body(BodyFrame { close: Close::Not, conjuncts, .. })) = self.stack.last() {
            if conjuncts.is_empty() {
                return;
            }
            let Some(Frame::Body(body)) = self.stack.pop() else { unreachable!("the `NOT` stands on top") };
            let [form] = <[Conjunct; 1]>::try_from(body.conjuncts).expect("a `NOT` over one form");
            top!(self, Frame::Body).conjuncts.push(Conjunct::Not(Negated::Form(Arc::new(form))));
        }
    }

    /// The instance whose clauses stand open.
    fn instance(&self) -> &InstanceFrame {
        let instance = self.stack.iter().rev().find_map(|frame| match frame {
            Frame::Instance(instance) => Some(instance),
            _ => None,
        });
        instance.expect("an input stands in an instance")
    }

    fn component<'r>(&self, context: &Context<'r>) -> &'r Component {
        let name = self.instance().component.as_ref().expect("a named component");
        component(context.registry, name).expect("a component the lib names")
    }

    /// The engine's name of the next input at or after `from` that the open
    /// group of the instance names; past the last, the close of that group:
    /// of a key clause, after which the instance names each input the key
    /// clause does not write, or of the instance.
    fn name_input(&mut self, context: &Context<'_>, from: usize, forced: &mut Vec<Token>) {
        let declared = self.component(context);
        let in_key = matches!(self.stack.last(), Some(Frame::KeyClause(_)));
        let keyed = self.instance().key.iter().flat_map(|key| key.value().inputs.iter().map(|input| input.value().name.clone()));
        let keyed: Vec<PortName> = keyed.collect();
        let next = (from..declared.inputs.len()).find(|position| in_key || !keyed.contains(&declared.inputs[*position].port.name));
        if let Some(position) = next {
            match self.stack.last_mut() {
                Some(Frame::KeyClause(KeyClauseFrame { stage, .. }) | Frame::Instance(InstanceFrame { stage, .. })) => *stage = Naming::Named(Some(position)),
                _ => unreachable!("an input stands in a key clause or an instance"),
            }
            forced.push(Token::Column(1 + position as u32));
            return;
        }
        match self.stack.pop() {
            Some(Frame::KeyClause(clause)) => {
                let body = clause.body.expect("a key clause's body");
                let body = key_body(body);
                let key = KeyClause { key: body, inputs: clause.inputs.into() };
                top!(self, Frame::Instance).key = Some(Node::new(key));
                self.name_input(context, 0, forced);
            }
            Some(Frame::Instance(instance)) => {
                let name = InstanceName(DeclaredName::Slot(instance.first));
                let component = instance.component.expect("a named component");
                let value = Instance { name, component, key: instance.key, inputs: instance.inputs.into() };
                let written: Vec<&PortName> = written_inputs(value.key.as_ref(), &value.inputs).map(|input| &input.name).collect();
                let resolved = |declared: &Arc<Declared>, slot: usize| match &declared.relation {
                    ProgramRelation::Output(OutputName { path, .. }) if slot >= instance.first as usize && !declared.readable => {
                        matches!(&path[..], [OutputStep::Port(port)] if written.contains(&port))
                    }
                    _ => declared.readable,
                };
                let declared = self.declared.iter().enumerate().map(|(slot, declared)| match resolved(declared, slot) == declared.readable {
                    true => declared.clone(),
                    false => Arc::new(Declared { readable: true, ..Declared::clone(declared) }),
                });
                self.declared = declared.collect();
                self.finish_form(Form::Instance(Node::new(value)));
            }
            _ => unreachable!("an input stands in a key clause or an instance"),
        }
    }

    /// Whether the innermost input stands open and reads its instance's
    /// outputs.
    fn reads_outputs(&self, context: &Context<'_>) -> bool {
        let input = self.stack.iter().rev().find_map(|frame| match frame {
            Frame::Input(input) => Some(input.position),
            _ => None,
        });
        input.is_some_and(|position| self.component(context).inputs[position].reads_outputs)
    }

    /// Opens the input at `position` of the instance's component.
    fn open_input(&mut self, context: &Context<'_>, position: usize) {
        let port = &self.component(context).inputs[position].port;
        let columns = port.columns.iter().map(|column| column.name.clone()).collect();
        self.stack.push(Frame::Input(InputFrame { position, name: port.name.clone(), columns, body: None, head: Vec::new(), column: 0 }));
        self.push_body(Close::List, false);
    }

    /// The engine's name of the next column of the input on top, or, past
    /// the last, the input.
    fn next_column(&mut self, forced: &mut Vec<Token>) -> Option<Built> {
        let input = top!(self, Frame::Input);
        if let Some(column) = input.columns.get(input.column) {
            forced.push(Token::Column(input.column as u32));
            let column = column.clone();
            self.stack.push(Frame::HeadSite(HeadSiteFrame { column, args: Vec::new(), fields: 0, field: None, last_bare: None, record_ended: false }));
            return None;
        }
        let Some(Frame::Input(input)) = self.stack.pop() else { unreachable!("the input stands on top") };
        let value = InstanceInput { name: input.name, head: input.head.into(), body: input.body.expect("an input's body") };
        Some(Built::Input { input: Node::new(value), position: input.position })
    }

    /// Closes the `CHOOSE` form on top, which declares its relation.
    fn finish_choose(&mut self, forced: &mut Vec<Token>) {
        let Some(Frame::Choose(choose)) = self.stack.pop() else { unreachable!("the `CHOOSE` form stands on top") };
        let slot = self.next_slot();
        let from = choose.from.expect("a `CHOOSE` form's `from`");
        let rows = choose.rows.as_ref().map_or(0, |rows| rows.columns.len());
        let candidate_columns = slot_columns(made_labels(from.value()), rows);
        let name = RelationName(DeclaredName::Slot(slot));
        let row_columns = choose.rows.iter().flat_map(|rows| rows.columns.iter());
        let columns = row_columns.chain(candidate_columns.iter()).map(|column| column.name.clone()).collect();
        let from_inside_for = inside_for(choose.rows.as_ref(), from.value());
        let value = Choose { name: name.clone(), rows: choose.rows, candidate_columns, from, from_inside_for, never: choose.never.into() };
        self.declare(ProgramRelation::Declared(name), columns, true);
        forced.push(Token::Relation(slot));
        self.finish_form(Form::Choose(Node::new(value)));
    }

    /// The partial node of `frame`, with `child`, the partial node of the
    /// frame above it, as its last child.
    fn partial_node(&self, frame: &Frame, child: Option<Built>) -> Option<Built> {
        let open_body = |child: Option<Built>| match child {
            Some(Built::Body(body)) => body,
            _ => empty(),
        };
        let slot = DeclaredName::Slot(self.next_slot());
        let built = match frame {
            Frame::Clause(clause) => {
                let (body, ones, set) = match &clause.stage {
                    ClauseStage::Marks { body, ones, set } => (body.clone(), ones.clone(), *set),
                    _ => (open_body(child), Vec::new(), false),
                };
                let derives = ProgramRelation::Declared(RelationName(slot));
                let proposers = clause.proposers.iter().cloned().collect();
                let value = Clause { keyword: clause.keyword, derives, gloss: None, proposers, body, ones: ones.into(), set, columns: Arc::from([]) };
                Built::Form(Form::Clause(Node::new(value)))
            }
            Frame::One(_) | Frame::Constraint(_) => return None,
            Frame::Body(frame) => {
                let mut conjuncts = frame.conjuncts.clone();
                match child {
                    Some(Built::Conjunct(conjunct)) => conjuncts.push(conjunct),
                    Some(Built::Atom { atom, negated: true }) => conjuncts.push(Conjunct::Not(Negated::Atom(atom))),
                    Some(Built::Atom { atom, negated: false }) => conjuncts.push(Conjunct::Atom(atom)),
                    _ => {}
                }
                match frame.close {
                    Close::Not => Built::Conjunct(Conjunct::Not(Negated::Form(Arc::new(conjuncts.pop()?)))),
                    _ => Built::Body(Node::new(Body { conjuncts: conjuncts.into() })),
                }
            }
            Frame::Atom(atom) => {
                let sites = atom.sites.iter().cloned().chain(child.and_then(|child| match child {
                    Built::Site(site) => Some(site),
                    _ => None,
                }));
                Built::Atom { atom: Node::new(Atom { relation: atom.relation.clone(), sites: sites.collect() }), negated: atom.negated }
            }
            Frame::Site(site) => Built::Site(Site { column: site.column.clone(), value: SiteValue { args: site.args.iter().cloned().collect() } }),
            Frame::Or(branches) => Built::Conjunct(Conjunct::Or(branches.iter().cloned().chain([open_body(child)]).collect())),
            Frame::Lists(lists) => {
                let mut all: Vec<Node<Body>> = lists.lists.iter().cloned().chain([open_body(child)]).collect();
                all.resize_with(if lists.all { 2 } else { 3 }, empty);
                Built::Conjunct(match <[Node<Body>; 3]>::try_from(all) {
                    Ok([test, then, otherwise]) => Conjunct::If { test, then, otherwise },
                    Err(all) => {
                        let [domain, body] = <[Node<Body>; 2]>::try_from(all).expect("an `ALL` form's two lists");
                        Conjunct::All { domain, body }
                    }
                })
            }
            Frame::Instance(instance) => {
                let component = instance.component.clone()?;
                let mut key = instance.key.clone();
                let mut inputs = instance.inputs.clone();
                match child {
                    Some(Built::KeyClause(clause)) => key = Some(clause),
                    Some(Built::Input { input, .. }) => inputs.push(input),
                    _ => {}
                }
                let value = Instance { name: InstanceName(DeclaredName::Slot(instance.first)), component, key, inputs: inputs.into() };
                Built::Form(Form::Instance(Node::new(value)))
            }
            Frame::KeyClause(clause) => {
                let mut inputs = clause.inputs.clone();
                let key = match (&clause.body, child) {
                    (Some(body), child) => {
                        if let Some(Built::Input { input, .. }) = child {
                            inputs.push(input);
                        }
                        key_body(body.clone())
                    }
                    (None, child) => KeyBody { body: open_body(child), columns: Arc::from([]) },
                };
                Built::KeyClause(Node::new(KeyClause { key, inputs: inputs.into() }))
            }
            Frame::Input(input) => {
                let (head, body) = match (&input.body, child) {
                    (Some(body), Some(Built::HeadSite(Some(site)))) => (input.head.iter().cloned().chain([site]).collect(), body.clone()),
                    (Some(body), _) => (input.head.iter().cloned().collect(), body.clone()),
                    (None, child) => (Arc::from([]), open_body(child)),
                };
                Built::Input { input: Node::new(InstanceInput { name: input.name.clone(), head, body }), position: input.position }
            }
            Frame::HeadSite(site) => Built::HeadSite((!site.args.is_empty()).then(|| Site { column: site.column.clone(), value: SiteValue { args: site.args.iter().cloned().collect() } })),
            Frame::Choose(choose) => {
                let from = choose.from.clone().unwrap_or_else(empty);
                let mut value = Choose { name: RelationName(slot), rows: choose.rows.clone(), candidate_columns: Arc::from([]), from, from_inside_for: false, never: Arc::from([]) };
                let never = choose.never.iter().cloned();
                match choose.stage {
                    ChooseStage::ForOpen => value.rows = Some(KeyBody { body: open_body(child), columns: Arc::from([]) }),
                    ChooseStage::FromOpen => value.from = open_body(child),
                    ChooseStage::NeverOpen => value.never = never.chain([open_body(child)]).collect(),
                    ChooseStage::For | ChooseStage::Never | ChooseStage::NeverEnd => value.never = never.collect(),
                }
                // Once FROM is complete its columns are in scope in NEVER,
                // including while NEVER is still a prefix. The full form
                // has these columns too; omitting them here falsely refuses
                // a valid join to a candidate label.
                if choose.from.is_some() {
                    let rows = value.rows.as_ref().map_or(0, |rows| rows.columns.len());
                    value.candidate_columns = slot_columns(made_labels(value.from.value()), rows);
                }
                value.from_inside_for = inside_for(value.rows.as_ref(), value.from.value());
                Built::Form(Form::Choose(Node::new(value)))
            }
            Frame::Out => Built::Form(Form::Out(Node::new(Out { key: KeyBody { body: open_body(child), columns: Arc::from([]) } }))),
            Frame::Rigid(rigid) => {
                let mut value = RigidDet { name: RigidDetName(slot), key: rigid.key.clone(), instance: rigid.instance.clone(), parts: Arc::from([]) };
                let parts = rigid.parts.iter().cloned();
                match (rigid.stage, child) {
                    (RigidStage::KeyOpen, child) => value.key = Some(KeyBody { body: open_body(child), columns: Arc::from([]) }),
                    (RigidStage::InstanceOpen, child) => value.instance = Some(KeyBody { body: open_body(child), columns: Arc::from([]) }),
                    (_, Some(Built::Atom { atom, .. })) => value.parts = parts.chain([atom]).collect(),
                    (_, _) => value.parts = parts.collect(),
                }
                Built::Form(Form::RigidDet(Node::new(value)))
            }
        };
        Some(built)
    }
}

/// The index, among the children of the node of `frame`, of the node of
/// `above`, the frame above it.
fn child_step(frame: &Frame, above: &Frame) -> u32 {
    let count = |count: usize| u32::try_from(count).expect("fewer than 2^32 children");
    match frame {
        Frame::Clause(_) | Frame::Out => 0,
        Frame::Body(body) => count(body.conjuncts.len()),
        Frame::Atom(atom) => count(atom.sites.len()),
        Frame::Site(site) => count(site.args.len()),
        Frame::Or(branches) => count(branches.len()),
        Frame::Lists(lists) => count(lists.lists.len()),
        Frame::Instance(instance) => match above {
            Frame::KeyClause(_) => 0,
            _ => count(usize::from(instance.key.is_some()) + instance.inputs.len()),
        },
        Frame::KeyClause(clause) => match above {
            Frame::Input(_) => count(1 + clause.inputs.len()),
            _ => 0,
        },
        Frame::Input(input) => match above {
            Frame::HeadSite(_) => count(input.head.len()),
            _ => 0,
        },
        Frame::Choose(choose) => {
            let rows = usize::from(choose.rows.is_some());
            match choose.stage {
                ChooseStage::ForOpen => 0,
                ChooseStage::FromOpen => count(rows),
                _ => count(rows + 1 + choose.never.len()),
            }
        }
        Frame::Rigid(rigid) => {
            let key = usize::from(rigid.key.is_some());
            match rigid.stage {
                RigidStage::KeyOpen => 0,
                RigidStage::InstanceOpen => count(key),
                _ => count(key + usize::from(rigid.instance.is_some()) + rigid.parts.len()),
            }
        }
        Frame::One(_) | Frame::Constraint(_) | Frame::HeadSite(_) => unreachable!("a frame that holds no open child"),
    }
}

/// The type of a column that the registry fixes, where it is a scalar
/// ([`ValueType::is_scalar`]).
fn scalar_fixed(ty: &crate::registry::ColumnType) -> Option<ValueType> {
    match ty {
        crate::registry::ColumnType::Fixed(ty) if ty.is_scalar() => Some(ty.clone()),
        _ => None,
    }
}

/// Whether `token` opens an atom.
fn is_relation(token: &Token) -> bool {
    matches!(token, Token::Lib(_) | Token::Fact(_) | Token::Relation(_))
}

/// Whether `column` is a column of a type parameter, whose bare labels
/// carry a name.
fn type_parameter(column: &ColumnName) -> bool {
    matches!(column, ColumnName::Written(name) if is_type_parameter_column(name))
}

/// A bare label at a site on `column`.
fn bare_arg(column: &ColumnName, label: LabelUse) -> SiteArg {
    match (type_parameter(column), label) {
        (true, LabelUse::Fresh(id) | LabelUse::Join(id) | LabelUse::Key(id)) => SiteArg::NamedLabel { name: ColumnName::Slot(id.0), label },
        _ => SiteArg::Label(label),
    }
}

/// The label at the field named `name` of a record at a site on `column`.
fn field_arg(column: &ColumnName, name: ColumnName, label: LabelUse) -> SiteArg {
    match type_parameter(column) {
        true => SiteArg::NamedLabel { name, label },
        false => SiteArg::Field(Site { column: name, value: SiteValue { args: Arc::from([SiteArg::Label(label)]) } }),
    }
}

/// Whether a `CHOOSE` form's `from` stands inside its `for`, which is where
/// it reads a label of the rows, as `docs/arclog/constraints.md#choose`
/// gives.
fn inside_for(rows: Option<&KeyBody>, from: &Body) -> bool {
    let read = body_labels(from);
    rows.is_some_and(|rows| rows.columns.iter().any(|column| read.contains(&column.label)))
}

/// A key's body, whose columns are its `^` labels.
fn key_body(body: Node<Body>) -> KeyBody {
    KeyBody { columns: slot_columns(key_labels(body.value()), 0), body }
}

/// The inputs whose rows their component counts, each by its component and
/// its name. Such an input whose head holds no site has no column, so it
/// holds at most one row at each key, and the count of its rows is 0 or 1.
const COUNTED_INPUTS: [(&str, &str); 3] = [("Cardinality", "member"), ("Excess", "plus"), ("Excess", "minus")];

/// The refusal of a `ONE` mark whose key, as a set of labels, an earlier
/// mark of its clause names in every completion of the mark.
const ONE_KEY_TWICE: Unexpected = "no two `ONE` marks of a clause name the same labels, since a second mark of a key keeps the rows that the first keeps";

/// Whether a `ONE` mark that holds `held`, columns of its clause each named
/// once, has a completion whose key, as a set of labels, no mark of `ones`,
/// the clause's earlier marks, names: `held` itself where `closed` holds,
/// and otherwise `held` with any of the other labels of `columns`, the
/// clause's columns. Marks of one key keep the rows that one of them keeps
/// (`docs/arclog/constraints.md#one`).
fn new_key(held: &[LabelId], columns: &[LabelId], ones: &[OneMark], closed: bool) -> bool {
    fn key_of(labels: impl Iterator<Item = LabelId>) -> Vec<u32> {
        let mut key: Vec<u32> = labels.map(|label| label.0).collect();
        key.sort_unstable();
        key.dedup();
        key
    }
    let named: Vec<Vec<u32>> = ones.iter().map(|mark| key_of(mark.key.iter().copied())).collect();
    let rest: Vec<LabelId> = if closed { Vec::new() } else { columns.iter().filter(|label| !held.contains(label)).copied().collect() };
    // Each set of labels of `rest` added to `held` gives a key, so fewer earlier marks than such sets leave a key free.
    if rest.len() >= usize::BITS as usize || named.len() < (1usize << rest.len()) {
        return true;
    }
    (0..1usize << rest.len()).any(|chosen| {
        let added = rest.iter().enumerate().filter(|(at, _)| (chosen >> at) & 1 == 1).map(|(_, label)| *label);
        !named.contains(&key_of(held.iter().copied().chain(added)))
    })
}

fn empty() -> Node<Body> {
    Node::new(Body { conjuncts: Arc::from([]) })
}
