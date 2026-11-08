//! The decoder of `docs/engine/synthesis.md#token-mask`: the automaton that
//! reads a token stream into a program value, with the token mask at each
//! state. Its state, in `state`, steps by the grammar of the stream that
//! [`crate::stream::token_stream`] writes, and its mask,
//! [`Decoder::admissible`], admits a token where every check of
//! [`crate::check::checks`] holds, by its prefix form, on the program that
//! the token gives: one
//! [`PrefixChecks`] per state resolves, and infers the
//! types of, the finished forms once, and each candidate token costs the
//! resolution and the checks of its form in progress alone. The candidates
//! whose step opens an atom are one program but for the atom's relation,
//! which holds no site yet, so they share the labels and their types, the
//! bindings of the conjuncts before the atom, and the result of each check
//! that reads nothing of that relation ([`Candidate::AtomHead`]); the candidates
//! that open an atom share as well the result of each check that reads the
//! relation, by the class of that relation (`RelationClass`), and take one
//! resolution of the form in progress, retargeted to each one's relation,
//! where a result is not shared. The mask keeps the state and
//! forced tokens of each admitted token, which the step of that token takes.
//! It admits a constraint's operator, or first label, only where some
//! completion of the constraint passes the checks (`Decoder::completes`), and a
//! token whose state stands in the projection of an instance input only where
//! some completion of the projection does (`Decoder::completes_projection`),
//! which the search of `projection_search` decides, and refuses with no
//! verdict only where it spends its cap of steps. Its interface
//! beside the mask, in `interface`, gives the rows of the body so far and the
//! consistency test at an `OUT` form's end, and its batch form, in
//! `batch`, steps many decodes at once, and its projections of the body so far,
//! in `projections`, give the largest sets of its columns under the projection
//! cap. The replay of a case program's stream through a decoder, in
//! `replay`, and the walk of a solver's cases that records what a caller
//! builds of each step, in `corpus`, serve the commands and the Python
//! packages that read the tables of a corpus. The tables of the last step and
//! their flat columns are no part of this crate: the crate `arclog-tables`
//! builds them from the read-only accessors of a decoder ([`Decoder::state`],
//! [`Decoder::before`], [`Decoder::registry`], [`Decoder::settings`],
//! [`Decoder::grid_columns`] and the rows of the sub-body in `interface`), so
//! that no code of this crate calls them. The decode keeps a
//! [`crate::trace::DecodeTrace`] of one record per accepted token.

mod atom_values;
mod atoms;
mod batch;
mod det_admission;
pub(crate) mod det_memo;
pub mod corpus;
mod interface;
pub mod replay;
pub use atom_values::{AtomRows, BaseRows, JoinedAtom};
pub use atoms::{add_atom_verdicts, atom_verdicts, CandidateAtoms};
pub mod program_read;
mod state;
pub(crate) mod prefix_key;
mod projection_search;
mod projections;

pub use batch::step_batch;
pub use det_admission::DetRefusal;
pub use interface::{BodyWidening, derived_at, open_clause, held_dets, relation_dets, walked_dets, Assigned, Consistency, LeftOut, OpenClause, Step, SubBody, SubBodyKey};
pub use projections::{projections, Projection, Projections};
pub use state::State;

use std::cell::RefCell;
use std::sync::{Arc, OnceLock};

use crate::check::prefix::{Candidate, PrefixChecks};
use crate::check::CheckId;
use crate::hash::StableHashMap;
use crate::eval::instance::Constructions;
use crate::eval::copies::{CopyViolation, CopyViolations};
use crate::eval::values::HeldStops;
use crate::eval::{Cancellation, Hit, RequestWork, TableWork};
use crate::judge::candidates::PairCandidates;
use crate::program::path::NodePath;
use crate::program::{ProgramRelation, RelationRef};
use crate::program::{ConstraintOp, Node, Program};
use crate::registry::Registry;
use crate::resolver::resolve_for_checks;
use crate::session::TaskSession;
use crate::stats::{self, Phase};
use crate::judge::run::Tested;
use crate::stream::{Control, DecodeSettings, Emitter, Token, Vocabulary};
use crate::task::Task;
use crate::trace::{DecodeRecord, DecodeTrace, TopK, Verdict};

/// A decode over a task in a task session.
#[derive(Clone)]
pub struct Decoder<'a> {
    task: &'a Task,
    session: &'a TaskSession,
    constructions: &'a Constructions,
    context: Arc<Context<'a>>,
    state: state::State,
    /// The state before the last step, none before the first.
    before: Option<state::State>,
    /// The candidates of the train pairs that the consistency test reads,
    /// where the decode judges them.
    train: Option<Arc<[PairCandidates<'a>]>>,
    cancellation: Cancellation,
    operation_limits: Option<crate::eval::Limits>,
    /// The request that a call of this decode is in, where it has no
    /// operation limits ([`Decoder::begin_request`]).
    requests: Requests,
    /// The path of the first `OUT` form that was consistent, at which the
    /// decode ended.
    output: Option<NodePath>,
    assignments: Vec<Vec<(ProgramRelation, Arc<crate::relations::Relation>)>>,
    /// One record per accepted token, shared with the forks.
    trace: DecodeTrace,
    /// The sum of `capped_sets` over the records of `trace`.
    capped_sets: u64,
    /// The count of the records of `trace` that the model's tokens made.
    model_steps: usize,
    /// The index in `trace` of the last of those records.
    last_model_step: Option<usize>,
    /// The hash of the ids of the tokens of the trace, in order, or none
    /// where the decode stands at a state that its tokens did not reach.
    path: Option<u128>,
    /// The mask of the current state with the step of each token it admits.
    held: Held,
    /// Where the evaluations report the declared rows that a construction's
    /// outputs break, where the settings check them.
    copies: Option<CopyViolations>,
    /// The stops that this decode's requests hold, which the limits of each
    /// request share ([`Decoder::limits`]).
    held_stops: Arc<HeldStops>,
    /// Whether a step evaluates: the consistency test of an `OUT` form, the
    /// rule test and the liveness walk of a written `DET`
    /// ([`Decoder::without_evaluation`]).
    evaluates: bool,
}

/// The request that a call of a decode is in: its work, and how many calls
/// that began it are open. A clone holds none, so a fork has requests of its
/// own.
#[derive(Default)]
struct Requests(Arc<std::sync::Mutex<ActiveRequest>>);

#[derive(Default)]
struct ActiveRequest {
    depth: u32,
    work: Option<RequestWork>,
}

impl Clone for Requests {
    fn clone(&self) -> Requests {
        Requests::default()
    }
}

/// The open call of a decode that began a request, or that is nested in one;
/// the request ends with the call that began it.
pub struct RequestGuard(Option<Arc<std::sync::Mutex<ActiveRequest>>>);

impl Drop for RequestGuard {
    fn drop(&mut self) {
        let Some(active) = &self.0 else { return };
        let mut active = active.lock().unwrap_or_else(std::sync::PoisonError::into_inner);
        active.depth -= 1;
        if active.depth == 0 {
            active.work = None;
        }
    }
}

/// What [`Decoder::admissible`] computes at a state: the mask, and the
/// state and the forced tokens that each admitted token gives, by the
/// token's id, which [`Decoder::advance`] takes in place of a second check.
struct Mask {
    mask: TokenMask,
    steps: StableHashMap<u32, (state::State, Vec<Token>)>,
    /// What the mask's computation charged to the request, which a call of
    /// [`Decoder::admissible`] that takes the mask from the decode or from the
    /// session charges again.
    cost: crate::eval::Cost,
}

impl Mask {
    /// The mask with the cost that a call of [`Decoder::admissible`] charges
    /// for it.
    fn hit(&self) -> Hit<TokenMask> {
        Hit::new(self.mask.clone(), self.cost)
    }
}

/// The [`Mask`] of a decoder's state, once computed. A clone holds none, so
/// a fork, and a checkpoint of a replay, hold no states.
#[derive(Default)]
struct Held(OnceLock<Mask>);

impl Clone for Held {
    fn clone(&self) -> Held {
        Held::default()
    }
}

/// The state after a token and what the step gives, which
/// [`Decoder::apply`] makes the decode's.
struct Advanced {
    token: Token,
    state: state::State,
    step: Step,
}

/// What [`Decoder::step`] gives.
pub type StepResult = Result<Step, Refusal>;

/// What every fork of a decode shares.
pub(crate) struct Context<'a> {
    registry: &'a Registry,
    settings: DecodeSettings,
    vocabulary: Vocabulary<'a>,
    /// A hash of the settings and the registry, which the key of a mask in the
    /// session's masks holds ([`Decoder::path_key`]).
    key_base: u128,
}

/// The most masks that a generation of [`PathMasks`] holds.
const PATH_MASKS: usize = 8192;

/// The masks of the states that the decodes of one task session reached, by
/// [`Decoder::path_key`]: two decodes of the session, of one task, registry,
/// constructions and settings, that took the same tokens from their first
/// state stand at the same state, so they have the same mask. Where a
/// generation is full, it becomes the older one, and the one before it goes.
#[derive(Default, Debug)]
pub(crate) struct PathMasks {
    entries: StableHashMap<u128, (TokenMask, crate::eval::Cost)>,
    older: StableHashMap<u128, (TokenMask, crate::eval::Cost)>,
}

impl PathMasks {
    /// Drops every mask, as a session does where it evicts its caches.
    pub(crate) fn clear(&mut self) {
        self.entries.clear();
        self.older.clear();
    }

    fn get(&mut self, key: u128) -> Option<Hit<TokenMask>> {
        if let Some((mask, cost)) = self.entries.get(&key) {
            return Some(Hit::new(mask.clone(), *cost));
        }
        let held = self.older.remove(&key)?;
        self.insert(key, held.clone());
        Some(Hit::new(held.0, held.1))
    }

    fn insert(&mut self, key: u128, mask: (TokenMask, crate::eval::Cost)) {
        if self.entries.len() >= PATH_MASKS {
            self.older = std::mem::take(&mut self.entries);
        }
        self.entries.insert(key, mask);
    }
}

/// Why a decode refuses a token: the token is outside the mask.
#[derive(Clone, PartialEq, Eq, Debug)]
pub enum Refusal {
    /// The grammar of the stream gives no such token at the state, or a token
    /// that the engine would emit after it is outside the vocabulary.
    Grammar(&'static str),
    /// The written DETs have no complete live assignment, or their native walk failed.
    DetAdmission(DetRefusal),
    /// A check refuses the prefix that the token gives, at each of its
    /// refusals.
    Check { check: CheckId, refusals: Box<[crate::check::Refusal]> },
}

/// The tokens that may come next, by their ids in the decode's
/// [`Vocabulary`].
#[derive(Clone, PartialEq, Eq, Debug)]
pub struct TokenMask {
    words: Box<[u64]>,
}

impl TokenMask {
    fn new(len: usize) -> TokenMask {
        TokenMask { words: vec![0; len.div_ceil(64)].into() }
    }

    fn insert(&mut self, id: u32) {
        self.words[id as usize / 64] |= 1 << (id % 64);
    }

    pub fn contains(&self, id: u32) -> bool {
        self.words.get(id as usize / 64).is_some_and(|word| word & (1 << (id % 64)) != 0)
    }
}

impl<'a> Decoder<'a> {
    /// A decode of no token yet. The arguments are those of
    /// [`crate::eval::Evaluation`] less the program and its parameter values,
    /// which the decode builds, with `settings` in place of its limits.
    /// Every evaluation of `session` reads the session's caps, so the caps
    /// of `settings` are those of `session`, and this panics where they
    /// differ.
    pub fn new(task: &'a Task, session: &'a TaskSession, registry: &'a Registry, constructions: &'a Constructions, settings: &DecodeSettings) -> Decoder<'a> {
        assert_eq!(settings.caps, session.caps, "the caps of the decode settings are those of the session");
        let key_base = {
            use std::hash::{Hash, Hasher};
            let mut hasher = crate::hash::StableHasher::new();
            format!("{settings:?}").hash(&mut hasher);
            hasher.write_usize(registry as *const Registry as usize);
            hasher.finish128().0
        };
        let context = Context { registry, settings: *settings, vocabulary: Vocabulary::new(registry, settings), key_base };
        let state = state::State::new();
        Decoder { task, session, constructions, context: Arc::new(context), state, before: None, train: None, cancellation: Cancellation::default(), operation_limits:None, requests: Requests::default(), output: None, assignments: Vec::new(), trace: DecodeTrace::default(), capped_sets: 0, model_steps: 0, last_model_step: None, path: Some(0), held: Held::default(), copies: settings.check_copies.then(CopyViolations::default), held_stops: Arc::default(), evaluates: true }
    }

    /// The decode, with steps that evaluate nothing: a step runs the
    /// grammar, the checks of the prefix and the static prune as
    /// [`Decoder::step`] does, and gives the refusal that `step` gives for
    /// each of them. It runs no consistency test of an `OUT` form and no rule
    /// test, so the decode ends at no `OUT` form, and of the admission of a
    /// written `DET` it runs only the check of the finished program, with no
    /// liveness walk. So it refuses no token with
    /// [`DetRefusal::NoLiveAssignment`] or [`DetRefusal::Bound`], nor with a
    /// [`DetRefusal::Fault`] of an evaluation, nor a token after a
    /// consistent `OUT` form, which `step` refuses with
    /// [`Refusal::Grammar`]. Its forks evaluate nothing either.
    pub fn without_evaluation(mut self) -> Decoder<'a> {
        self.evaluates = false;
        self
    }

    /// The ids of the decode's tokens.
    pub fn vocabulary(&self) -> &Vocabulary<'a> {
        &self.context.vocabulary
    }

    /// The slot at which the decode declared `relation`, a declared relation
    /// or an output as the decode names it, `None` for a relation it has not
    /// declared.
    pub fn relation_slot(&self, relation: &ProgramRelation) -> Option<u32> {
        self.state.slot_of(relation)
    }

    /// The registry the decode reads.
    #[inline]
    pub fn registry(&self) -> &'a Registry {
        self.context.registry
    }

    /// The settings the decode runs under.
    #[inline]
    pub fn settings(&self) -> &DecodeSettings {
        &self.context.settings
    }

    /// The work count of a table of this decode, under the settings' table
    /// work cap.
    pub fn table_work(&self) -> TableWork {
        TableWork::new(self.context.settings.table_work_cap)
    }

    /// Begins a request, where this decode is in none and holds no operation
    /// limits: the work of every query, walk and check that a call under the
    /// returned guard makes counts in one request, under the request work cap
    /// of the settings. A call nested in another joins the request that began
    /// first, and the request ends when that call's guard drops. With
    /// operation limits ([`Decoder::with_operation_limits`]) the operation is
    /// the request, and the guard does nothing.
    pub fn begin_request(&self) -> RequestGuard {
        if self.operation_limits.is_some() {
            return RequestGuard(None);
        }
        let mut active = self.requests.0.lock().unwrap_or_else(std::sync::PoisonError::into_inner);
        if active.depth == 0 {
            active.work = Some(RequestWork::begin_with(self.context.settings.request_work_cap, self.context.settings.byte_caps()));
        }
        active.depth += 1;
        RequestGuard(Some(Arc::clone(&self.requests.0)))
    }

    /// The work of the request that this decode is in: the operation's, or
    /// that of the open call ([`Decoder::begin_request`]), or, where no call
    /// is open, a request that begins now and that nothing else shares.
    pub fn request_work(&self) -> RequestWork {
        if let Some(limits) = &self.operation_limits {
            return limits.request.clone();
        }
        let active = self.requests.0.lock().unwrap_or_else(std::sync::PoisonError::into_inner);
        match &active.work {
            Some(work) => work.clone(),
            None => RequestWork::begin_with(self.context.settings.request_work_cap, self.context.settings.byte_caps()),
        }
    }

    /// The work of a query walk, counted without an observation budget.
    pub fn query_work(&self) -> TableWork {
        TableWork::uncapped()
    }

    /// The state of the decode: its finished forms and the form in progress.
    #[inline]
    pub fn state(&self) -> &State {
        &self.state
    }

    /// The state before the last step, none before the first.
    #[inline]
    pub fn before(&self) -> Option<&State> {
        self.before.as_ref()
    }

    /// The task, the session and the constructions that the decode's
    /// prefixes are evaluated on.
    pub fn evaluation_inputs(&self) -> (&'a Task, &'a TaskSession, &'a Constructions) {
        (self.task, self.session, self.constructions)
    }

    /// The tokens that may come next. The first call at a state computes the
    /// mask, and keeps the state and forced tokens of each admitted token for
    /// [`Decoder::step`]; a later call at that state gives the same mask.
    ///
    /// A mask that a request stopped at its work cap is no mask of the state:
    /// the decode and its session keep none of it, and the checks that a stop
    /// left open admit their tokens ([`Decoder::request_work`]).
    pub fn admissible(&self) -> TokenMask {
        let _request = self.begin_request();
        if let Some(held) = self.held.0.get() {
            // The mask charges what its computation charged, so a second call at a state counts as the first did.
            let work = self.request_work();
            return match held.hit().charge(&work, None, self.session).value() {
                Some(mask) => mask,
                None => self.compute_mask().mask,
            };
        }
        let mask = self.path_mask();
        if self.request_work().is_past_cap() {
            return mask.mask;
        }
        self.held.0.get_or_init(|| mask).mask.clone()
    }

    /// Whether each token whose id `ids` gives may come next, as
    /// [`Decoder::admissible`] decides it, with the checks of the mask run
    /// over those tokens alone and none of the mask kept for a later step.
    /// Where the decode holds the mask of its state, it reads the verdicts
    /// from the mask.
    pub fn admits(&self, ids: &[u32]) -> Vec<bool> {
        let _request = self.begin_request();
        // A mask held for every token has a cost that is not the cost of the checks of these tokens alone, so these checks run whatever the decode or the session holds, and the count of the call does not depend on that.
        let mask = self.mask_over(ids.iter().copied()).mask;
        ids.iter().map(|&id| mask.contains(id)).collect()
    }

    /// The mask that [`Decoder::next`] gives over every token of the
    /// vocabulary, the oracle of [`Decoder::admissible`].
    #[cfg(feature = "admissible-reference")]
    pub fn admissible_reference(&self) -> TokenMask {
        self.compute_mask_reference().mask
    }

    /// The mask of `compute_mask_reference`, which `admissible_workload check`
    /// compares with it along a corpus's streams, and the step of each token
    /// it admits. It tries fewer tokens and shares check verdicts, each
    /// where a rule of the checks makes the verdict equal:
    ///
    /// - [`State::mask_may_take`] drops a token that the grammar refuses
    ///   with no step.
    /// - [`State::fixed_label_conflicts`] drops the labels that the type
    ///   check refuses by their first use.
    /// - [`State::awaits_component`] and [`State::grammar_only_candidate`]
    ///   take the grammar step alone.
    /// - [`State::native_classes`] shares one verdict among candidates.
    /// - [`State::cached_prefix`] shares the verdict of a repeated prefix.
    fn compute_mask(&self) -> Mask {
        self.mask_over(0..u32::try_from(self.context.vocabulary.len()).expect("fewer than 2^32 tokens"))
    }

    /// The mask of [`Decoder::compute_mask`] over the tokens whose ids `ids`
    /// gives: a token outside them is not in the mask. Each other token's
    /// verdict is the one the mask over every token gives.
    fn mask_over(&self, ids: impl Iterator<Item = u32>) -> Mask {
        self.mask_until(ids, false)
    }

    /// Whether the mask over the tokens whose ids `ids` gives admits one.
    fn mask_first(&self, ids: impl Iterator<Item = u32>) -> bool {
        !self.mask_until(ids, true).steps.is_empty()
    }

    /// [`Decoder::mask_over`], which stops at the first token it admits where
    /// `first` holds.
    fn mask_until(&self, ids: impl Iterator<Item = u32>, first: bool) -> Mask {
        let vocabulary = &self.context.vocabulary;
        let work = self.request_work();
        let mut mask = TokenMask::new(vocabulary.len());
        let mut steps = StableHashMap::default();
        if self.output.is_some() {
            return Mask { mask, steps, cost: Default::default() };
        }
        if self.state.awaits_component() {
            for id in ids {
                let token = vocabulary.token(id).expect("a vocabulary token");
                if matches!(token, Token::Lib(_)) {
                    if let Ok(step) = self.grammar_next(token) {
                        mask.insert(id);
                        steps.insert(id, step);
                    }
                }
            }
            return Mask { mask, steps, cost: Default::default() };
        }
        self.with_checks_at_state(|checks| {
            checks.prepare_mask();
            let memo = MaskMemo::default();
            let column_type = |relation: &RelationRef, column: &crate::program::ColumnName| self.fixed_column_type(checks, relation, column);
            let conflicts = self.state.fixed_label_conflicts(self.context.registry, &column_type);
            let classes = self.state.native_classes(self.context.registry, &column_type);
            let mut class_of = vec![None; vocabulary.len()];
            let mut admitted = vec![None; classes.len()];
            for (class, tokens) in classes.iter().enumerate() {
                for token in tokens {
                    if let Some(id) = vocabulary.id(token) {
                        class_of[id as usize] = Some(class);
                    }
                }
            }
            for id in ids {
                let token = vocabulary.token(id).expect("an id of the vocabulary");
                if matches!(token, Token::Label(label) if conflicts.contains(label)) {
                    continue;
                }
                if self.state.closes_an_empty_site(token) {
                    continue;
                }
                if self.state.mask_may_take(token) {
                    // One unit for each candidate token that the mask checks.
                    let _ = work.charge(1);
                    if let Some(result) = class_of[id as usize].and_then(|class| admitted[class]) {
                        if result {
                            // A member shares the class's verdict, and takes its own
                            // grammar step.
                            let step = self.grammar_next(token).expect("a class member passes the same grammar");
                            mask.insert(id);
                            steps.insert(id, step);
                            if first {
                                break;
                            }
                        }
                        continue;
                    }
                    let next = if self.state.grammar_only_candidate(token) { self.grammar_next(token) } else { self.next(token, checks, &memo) };
                    if let Some(class) = class_of[id as usize] {
                        admitted[class] = Some(next.is_ok());
                    }
                    if let Ok(step) = next {
                        mask.insert(id);
                        steps.insert(id, step);
                        if first {
                            break;
                        }
                    }
                }
            }
        });
        Mask { mask, steps, cost: Default::default() }
    }

    /// The fixed scalar type of `column` of `relation` at this decoder's state,
    /// kept in the state.
    fn fixed_column_type(&self, checks: &PrefixChecks<'_>, relation: &RelationRef, column: &crate::program::ColumnName) -> Option<crate::types::ValueType> {
        self.state.fixed_column_type(relation, column, || checks.fixed_column_type(relation, column))
    }

    /// The step of `token` and the cap on the tokens it forces, with no check
    /// of the prefix: for a candidate whose verdict is shared or known.
    fn grammar_next(&self, token: &Token) -> Result<(state::State, Vec<Token>), Refusal> {
        let (state, forced, _) = self.state.step(&self.context, token, &|_, _, _| unreachable!("grammar-only candidates open no declared atom")).map_err(Refusal::Grammar)?;
        if forced.iter().any(|token| self.context.vocabulary.id(token).is_none()) {
            return Err(Refusal::Grammar("a token the engine emits after it passes a vocabulary cap"));
        }
        Ok((state, forced))
    }

    /// The mask of [`Decoder::next`] over every token.
    #[cfg(feature = "admissible-reference")]
    fn compute_mask_reference(&self) -> Mask {
        let vocabulary = &self.context.vocabulary;
        let mut mask = TokenMask::new(vocabulary.len());
        let mut steps = StableHashMap::default();
        self.with_checks_at_state(|checks| {
            let memo = MaskMemo::default();
            for id in 0..u32::try_from(vocabulary.len()).expect("fewer than 2^32 tokens") {
                let token = vocabulary.token(id).expect("an id of the vocabulary");
                if let Ok(step) = self.next(token, checks, &memo) {
                    mask.insert(id);
                    steps.insert(id, step);
                }
            }
        });
        Mask { mask, steps, cost: Default::default() }
    }

    /// Runs `body` with the checks over the prefixes that follow the
    /// state's finished forms, which resolve, and whose clauses and types
    /// are made, once.
    fn with_checks<R>(&self, body: impl FnOnce(&PrefixChecks<'_>) -> R) -> R {
        let _timed = stats::span(Phase::DecodeWithChecks);
        let registry = self.context.registry;
        let resolved = self.state.resolved(registry);
        self.state.with_clauses(registry, |clauses| {
            PrefixChecks::with(&resolved, clauses, registry, |checks| {
                checks.share_resolutions(self.state.held_resolutions());
                body(checks)
            })
        })
    }

    /// [`Decoder::with_checks`], with the form in progress at the state held
    /// for the candidates, which the mask computes.
    fn with_checks_at_state<R>(&self, body: impl FnOnce(&PrefixChecks<'_>) -> R) -> R {
        let earlier = self.state.resolved(self.context.registry);
        self.with_checks(|checks| {
            if let Some((program, Some(_))) = self.state.partial() {
                checks.hold_state(earlier, program);
            }
            body(checks)
        })
    }

    /// Advances the decode by `token`, and gives the tokens that the engine
    /// emits after it, with the consistency of the relation of an `OUT` form
    /// that the token ends and, under the rule tests, of a `RULE` clause that
    /// it ends; or refuses a token outside the mask, and leaves the decode as
    /// it was. The decode ends at the first `OUT` form that is consistent,
    /// and at nothing else, and refuses every token after it.
    pub fn step(&mut self, token: Token) -> StepResult {
        let _request = self.begin_request();
        let advanced = self.advance(&token, true);
        self.apply(advanced)
    }

    /// A fork of this decode that [`Decoder::step`] advanced by `token`, and
    /// what that step gives: those of [`Decoder::fork`], then `step` on the
    /// fork. Where this decode holds the mask of its state and the mask admits
    /// `token`, the fork's state after `token` comes from the mask, and no
    /// check of the token runs again. The step's consistency tests run on the
    /// fork, as `step` runs them. This decode stays as it was.
    pub fn fork_step(&self, token: Token) -> (Decoder<'a>, StepResult) {
        let kept = self.held.0.get().and_then(|held| held.steps.get(&self.context.vocabulary.id(&token)?).cloned());
        let mut next = self.fork();
        // The fork's step is the request.
        let _request = next.begin_request();
        let result = match kept {
            Some((state, forced)) => {
                let advanced = next.advanced(&token, state, forced, true);
                next.apply(Ok(advanced))
            }
            None => next.step(token),
        };
        (next, result)
    }

    /// [`Decoder::step`] with no consistency test of an `OUT` form and no
    /// rule test: the step gives `None` as its `consistency` and as its
    /// `rule_test`, so the decode ends at no `OUT` form and takes no
    /// assignments from the step. A caller that steps no further token that
    /// reads the output of the step uses it.
    pub fn step_untested(&mut self, token: Token) -> StepResult {
        let _request = self.begin_request();
        let advanced = self.advance(&token, false);
        self.apply(advanced)
    }

    /// The decode after `token`: a fork of this decode that [`Decoder::step`]
    /// advanced by `token`, or the refusal that `step` gives for it. Where the
    /// decode holds the mask of its state and the mask admits `token`, the
    /// state after `token` comes from the mask, and no check runs. The step
    /// runs the consistency test of an `OUT` form that `token` finishes, as
    /// `step` does, and no rule test, so the fork's trace has no rule test
    /// at the step. This decode stays as it was.
    pub fn successor(&self, token: Token) -> Result<Decoder<'a>, Refusal> {
        let _request = self.begin_request();
        let (state, forced) = self.next_state(&token)?;
        let forms = &state.program().value().forms;
        let finishes_out = forms.len() > self.state.program().value().forms.len() && matches!(forms.last(), Some(crate::program::Form::Out(_)));
        let (consistency, capped_sets) = match finishes_out.then(|| self.consistency(&self.state, &state, Tested::Out)).flatten() {
            Some((consistency, capped)) => (Some(consistency), capped),
            None => (None, 0),
        };
        let mut next = self.fork();
        next.apply(Ok(Advanced { token, state, step: Step { forced: forced.into(), consistency, rule_test: None, capped_sets, rule_capped_sets: 0 } }))?;
        Ok(next)
    }

    /// The tokens that [`Decoder::step`] gives as `forced` after `token`, or
    /// the refusal that it gives for a token it refuses. It runs no
    /// consistency test, and leaves the decode as it was. Where the decode
    /// holds the mask of its state and the mask admits `token`, it reads the
    /// forced tokens from the mask and runs no check.
    pub fn forced(&self, token: &Token) -> Result<Vec<Token>, Refusal> {
        let _request = self.begin_request();
        self.next_state(token).map(|(_, forced)| forced)
    }

    /// The state after `token`, and the tokens the engine emits after it:
    /// those the held mask keeps for the token's id, or else those that the
    /// checks of the state give.
    fn next_state(&self, token: &Token) -> Result<(state::State, Vec<Token>), Refusal> {
        let kept = self.held.0.get().and_then(|held| held.steps.get(&self.context.vocabulary.id(token)?));
        match kept {
            Some((state, forced)) => Ok((state.clone(), forced.clone())),
            None => self.with_checks(|checks| self.next(token, checks, &MaskMemo::default())),
        }
    }

    /// The state after `token`, and what the step gives, which
    /// [`Decoder::apply`] makes the decode's. With `tested` false, the step
    /// runs no consistency test.
    fn advance(&self, token: &Token, tested: bool) -> Result<Advanced, Refusal> {
        let (state, forced) = self.next_state(token)?;
        Ok(self.advanced(token, state, forced, tested))
    }

    /// [`Decoder::advance`] to `state`, the state after `token`, with the tokens
    /// `forced` that the engine emits after it.
    fn advanced(&self, token: &Token, state: state::State, forced: Vec<Token>, tested: bool) -> Advanced {
        let consistency = if tested { self.consistency(&self.state, &state, Tested::Out) } else { None };
        let rule_test = if tested && self.context.settings.rule_tests { self.consistency(&self.state, &state, Tested::Rule) } else { None };
        let counted = |tested: Option<(Consistency, u64)>| match tested {
            Some((consistency, capped)) => (Some(consistency), capped),
            None => (None, 0),
        };
        let ((consistency, capped_sets), (rule_test, rule_capped_sets)) = (counted(consistency), counted(rule_test));
        Advanced { token: token.clone(), state, step: Step { forced: forced.into(), consistency, rule_test, capped_sets, rule_capped_sets } }
    }

    fn apply(&mut self, advanced: Result<Advanced, Refusal>) -> StepResult {
        let Advanced { token, state, step } = advanced?;
        self.before = Some(std::mem::replace(&mut self.state, state));
        self.held = Held::default();
        self.record(token, &step);
        if let Some(Consistency::Consistent { assignments, .. }) = &step.consistency {
            self.assignments = assignments.clone();
            self.output = Some(NodePath::top(self.state.program().value().forms.len() as u32 - 1));
        }
        Ok(step)
    }

    /// Appends the record of the model's `token`, with the verdicts and the
    /// stop of its consistency tests, and the record of each token the
    /// engine forced after it.
    fn record(&mut self, token: Token, step: &Step) {
        let mut record = DecodeRecord::new(token, Emitter::Model);
        let verdict = |consistency: &Consistency| match consistency {
            Consistency::Consistent { assignments, stop } => (Verdict::Consistent { assignments: assignments.len() }, stop.as_ref().map(|s| s.bound.into())),
            Consistency::NotConsistent => (Verdict::NotConsistent, None),
            Consistency::SeveralValues { .. } => (Verdict::SeveralValues, None),
            Consistency::Fault(_) => (Verdict::Fault, None),
            Consistency::Stopped(stop) => (Verdict::Stopped, Some(stop.bound.into())),
        };
        if let Some(consistency) = &step.consistency {
            let (verdict, stop) = verdict(consistency);
            record.consistency = Some(verdict);
            record.stop = stop;
        }
        if let Some(rule_test) = &step.rule_test {
            let (verdict, stop) = verdict(rule_test);
            record.rule_test = Some(verdict);
            record.stop = record.stop.or(stop);
        }
        record.capped_sets = step.capped_sets + step.rule_capped_sets;
        self.capped_sets += record.capped_sets;
        self.model_steps += 1;
        self.last_model_step = Some(self.trace.len());
        self.extend_path(&record.token);
        self.trace.push(record);
        for forced in step.forced.iter() {
            self.extend_path(forced);
            self.trace.push(DecodeRecord::new(forced.clone(), Emitter::Engine));
        }
    }

    /// Adds `token` to [`Decoder::path`].
    fn extend_path(&mut self, token: &Token) {
        use std::hash::{Hash, Hasher};
        let Some(path) = self.path else { return };
        let mut hasher = crate::hash::StableHasher::new();
        hasher.write_u128(path);
        match self.context.vocabulary.id(token) {
            Some(id) => hasher.write_u32(id),
            None => format!("{token:?}").hash(&mut hasher),
        }
        self.path = Some(hasher.finish128().0);
    }

    /// The key of the mask of this decode's state among the masks of its
    /// session: the path of its tokens, its settings, registry, task and
    /// constructions, and whether it evaluates, since the liveness walk of a
    /// written `DET` reads that.
    fn path_key(&self) -> Option<u128> {
        use std::hash::Hasher;
        let mut hasher = crate::hash::StableHasher::new();
        hasher.write_u128(self.path?);
        hasher.write_u128(self.context.key_base);
        hasher.write_usize(self.task as *const Task as usize);
        hasher.write_usize(self.constructions as *const Constructions as usize);
        hasher.write_u8(u8::from(self.evaluates));
        Some(hasher.finish128().0)
    }

    /// The mask of this decode's state, from the masks of its session where a
    /// decode of the same key computed it, and else computed and kept there.
    /// A mask from the session holds no states of its tokens' steps.
    fn path_mask(&self) -> Mask {
        let work = self.request_work();
        let measured = || {
            let (mut mask, cost) = work.measure(|| self.compute_mask());
            mask.cost = cost;
            mask
        };
        let Some(key) = self.path_key() else { return measured() };
        let kept = self.session.path_masks.lock().expect("the masks are not poisoned").get(key);
        // A mask from the session charges what its computation charged, unless that would pass the request's cap, where the mask is computed here and stops where it stops with empty caches.
        if let Some(hit) = kept {
            let cost = hit.cost();
            if let Some(mask) = hit.charge(&work, None, self.session).value() {
                return Mask { mask, steps: StableHashMap::default(), cost };
            }
        }
        let mask = measured();
        // A mask that a stop at the request cap cut short is the mask of no state.
        if !work.is_past_cap() {
            self.session.path_masks.lock().expect("the masks are not poisoned").insert(key, (mask.mask.clone(), mask.cost));
        }
        mask
    }

    /// The trace of the decode: one record per accepted token, the engine's
    /// forced tokens among them, in the order of the stream.
    pub fn trace(&self) -> &DecodeTrace {
        &self.trace
    }

    /// The output sets of the consistency tests of the decode's steps that
    /// ended at the model cap with the grids found so far, summed over the
    /// trace's records.
    pub fn capped_sets(&self) -> u64 {
        self.capped_sets
    }

    /// The count of the records of the trace that the model's tokens made,
    /// and the index in the trace of the last of them, or `None` before the
    /// first.
    pub fn model_steps(&self) -> (usize, Option<usize>) {
        (self.model_steps, self.last_model_step)
    }

    /// Attaches `top_k`, the language model's top tokens at the decision of
    /// the record at `step` of the trace, to that record in this decode's
    /// trace alone. Gives `false` where the trace has no such record.
    pub fn attach_top_k(&mut self, step: usize, top_k: TopK) -> bool {
        self.trace.update(step, |record| record.top_k = Some(top_k))
    }

    /// Uses one caller operation for every nested query and materialization:
    /// the operation is one request, which counts the work of every call of
    /// this decode and its forks under the cap of the limits.
    pub fn with_operation_limits(mut self,limits:crate::eval::Limits)->Self {
        self.cancellation=limits.cancellation.clone();
        self.operation_limits=Some(limits);self
    }

    /// A second decode from the same state, which shares this one's caches
    /// and takes a cancellation of its own, and a store of held stops of its
    /// own that holds the stops at the table work cap this decode holds now
    /// ([`HeldStops::snapshot`]), and requests of its own.
    pub fn fork(&self) -> Decoder<'a> {
        Decoder {
            cancellation: self.operation_limits.as_ref().map_or_else(Cancellation::default,|limits|limits.cancellation.clone()),
            held: Held::default(),
            copies: self.copies.as_ref().map(|_| CopyViolations::default()),
            held_stops: Arc::new(self.held_stops.snapshot()),
            ..self.clone()
        }
    }

    /// The declared rows that the constructions' outputs broke in the
    /// evaluations of this decode since the last call, each once, where the
    /// settings check them ([`DecodeSettings::check_copies`]), and none
    /// otherwise.
    pub fn take_copy_violations(&self) -> Vec<CopyViolation> {
        self.copies.as_ref().map(CopyViolations::take).unwrap_or_default()
    }

    /// The program so far: its finished forms.
    pub fn program(&self) -> &Node<Program> {
        self.state.program()
    }

    /// The hash of the resolver's content of the finished query at
    /// `index`, free of the names that its scope gives its tables; none where
    /// `index` names no finished query.
    pub fn query_hash(&self, index: usize) -> Option<crate::hash::StableHash> {
        self.query_content(index).map(|content| content.content_hash())
    }

    /// The resolver's content of the finished query at `index`.
    pub fn query_content(&self, index: usize) -> Option<crate::resolver::ResolvedContent> {
        self.state.resolved(self.registry()).query_content(index, self.registry())
    }

    /// The program so far with the form in progress as its last form, the
    /// prefix that the mask's checks read, and the path in that form of its
    /// innermost open node, or none where the last form is complete; or none
    /// where the form in progress shows no node yet.
    pub fn partial(&self) -> Option<(Node<Program>, Option<NodePath>)> {
        self.state.partial()
    }

    /// The state after `token`, and the tokens the engine emits after it,
    /// where `token` is in the mask.
    fn next(&self, token: &Token, checks: &PrefixChecks<'_>, memo: &MaskMemo) -> Result<(state::State, Vec<Token>), Refusal> {
        let _timed = stats::span(Phase::DecodeNext);
        let vocabulary = &self.context.vocabulary;
        if self.output.is_some() {
            return Err(Refusal::Grammar("the decode has ended at its `OUT` form"));
        }
        if vocabulary.id(token).is_none() {
            return Err(Refusal::Grammar("the vocabulary holds no such token"));
        }
        let earlier = || self.state.resolved(self.context.registry);
        let reads_example = |program: &Node<Program>, at: &NodePath, relation: &RelationRef| checks.reads_example_column(&earlier(), program, at, relation);
        let (state, forced, opened) = self.state.step(&self.context, token, &reads_example).map_err(Refusal::Grammar)?;
        stats::seen(Phase::DecodeNext, || state.stats_digest());
        if forced.iter().any(|token| vocabulary.id(token).is_none()) {
            return Err(Refusal::Grammar("a token the engine emits after it passes a vocabulary cap"));
        }
        // A relation token after the first that the mask steps takes the
        // static prune's verdict and the path of its atom from that first, and
        // the results of the head checks that the checks hold for its class,
        // with no partial program built.
        if let (Some((open, pruned)), true, Token::Lib(_) | Token::Relation(_)) = (memo.head.get(), opened.is_some(), token) {
            let relation = state.open_relation().expect("an atom stands open");
            let full = NodePath(std::iter::once(crate::program::path::PathStep(self.state.program().value().forms.len() as u32)).chain(open.0.iter().copied()).collect());
            if let Some(held) = checks.held_atom_head(&earlier(), &full, open, &relation) {
                pruned.clone()?;
                return match held {
                    Some((check, refusals)) => Err(Refusal::Check { check, refusals }),
                    None => Ok((state, forced)),
                };
            }
        }
        if let Some((program, open)) = state.partial() {
            if !program.value().forms.is_empty() {
                let pruned = self.check_static_prune(&program, open.as_ref(), checks, memo);
                if let (Some(open), true, Token::Lib(_) | Token::Relation(_)) = (&open, opened.is_some(), token) {
                    let _ = memo.head.set((open.clone(), pruned.clone()));
                }
                pruned?;
                if let (Some(open), true, Token::Lib(_) | Token::Relation(_)) = (&open, opened.is_some(), token) {
                    let relation = state.open_relation().expect("an atom stands open");
                    if let Some((check, refusals)) = checks.check_atom_head(&earlier(), &program, open, &relation) {
                        return Err(Refusal::Check { check, refusals });
                    }
                    return Ok((state, forced));
                }
                let candidate = if opened.is_some() { Candidate::AtomHead } else { Candidate::Any };
                self.check_partial(&program, open.as_ref(), candidate, checks)?;
            }
        }
        if state.open_constraint().is_some() {
            let _timed = stats::span(Phase::DecodeCompletes);
            self.completes(&state, checks, &reads_example, &memo.order)?;
        } else if state.head_site_completions(usize::MAX).is_some() {
            let _timed = stats::span(Phase::DecodeCompletes);
            self.completes_projection(&state, checks, &reads_example)?;
        }
        self.admit_written_dets(token, &state)?;
        Ok((state, forced))
    }

    /// Check only conjuncts that this grammar step completed. An atom can
    /// close on the next relation token; END can finish the entire form.
    /// Restrict replacement certificates to flat top-level clauses for now.
    /// The lists of every other form, an `INIT`, `CHOOSE` or `RIGID_DET` form among
    /// them, take only the verdicts of [`Decoder::check_nested_static_prune`].
    fn check_static_prune(
        &self,
        program: &Node<Program>,
        open: Option<&NodePath>,
        checks: &PrefixChecks<'_>,
        memo: &MaskMemo,
    ) -> Result<(), Refusal> {
        let _timed = stats::span(Phase::DecodeStaticPrune);
        fn completed<'a>(program: &'a Node<Program>, open: Option<&NodePath>) -> Option<(&'a crate::program::Body, usize)> {
            let crate::program::Form::Clause(clause) = program.value().forms.last()? else { return None };
            let body = clause.value().body.value();
            let count = match open.map(|p| &p.0[..]) {
                Some([crate::program::path::PathStep(0), crate::program::path::PathStep(index), ..]) => (*index as usize).min(body.conjuncts.len()),
                _ => body.conjuncts.len(),
            };
            Some((body, count))
        }
        // A last form that is no clause has no top-level body of its own, and its lists are the nested prune's.
        let Some((body, count)) = completed(program, open) else { return self.check_nested_static_prune(program, open, checks, memo) };
        let prior = memo.before.get_or_init(|| {
            let before = self.state.partial()?;
            completed(&before.0, before.1.as_ref()).map(|(_, count)| (before.0.value().forms.len(), count))
        });
        let prior = prior.filter(|(forms, _)| *forms == program.value().forms.len()).map_or(0, |(_, count)| count);
        let type_of = |relation: &RelationRef, column: &crate::program::ColumnName| self.fixed_column_type(checks, relation, column);
        for index in prior..count {
            let prefix = crate::program::Body { conjuncts: body.conjuncts[..=index].into() };
            let Some(found) = crate::program::static_prune::classify_prefix(&prefix, &type_of) else {
                let keys = |relation: &RelationRef| relation_keys(self.context.registry, relation);
                let binds = |atom: &crate::program::Atom, column: &crate::program::ColumnName| binds_column(self.context.registry, atom, column);
                let rule = crate::program::static_prune::makes_earlier_redundant(&prefix)
                    .or_else(|| crate::program::static_prune::reads_an_earlier_row(&prefix, &keys))
                    .or_else(|| crate::program::static_prune::makes_membership_redundant(&prefix, &type_of, &binds));
                if let Some(rule) = rule {
                    return Err(Refusal::Grammar(crate::program::static_prune::rule_message(rule).expect("a message of each rule")));
                }
                continue;
            };
            if let (Some(message), crate::program::static_prune::Class::Unsatisfiable | crate::program::static_prune::Class::Valid) =
                (crate::program::static_prune::rule_message(found.rule), found.class)
            {
                return Err(Refusal::Grammar(message));
            }
            match found.class {
                crate::program::static_prune::Class::Unsatisfiable => return Err(Refusal::Grammar("static prune: no row satisfies the completed atom")),
                crate::program::static_prune::Class::Valid => return Err(Refusal::Grammar("static prune: the completed atom repeats an existing test")),
                crate::program::static_prune::Class::Alias | crate::program::static_prune::Class::Constant => {
                    let Some(replacement) = found.replacement else { continue };
                    let admitted = || {
                        // Remove the next, still-open atom through the ordinary
                        // editor to recover this clause prefix's own declaration.
                        // The replacement checker then PRESERVES that interface.
                        let body_path = NodePath::default().child(0);
                        let absolute = NodePath::top((program.value().forms.len() - 1) as u32).join(&body_path);
                        let mut truncated = program.clone();
                        for later in ((index + 1)..body.conjuncts.len()).rev() {
                            match truncated.apply(&crate::program::edit::Edit::RemoveConjunct { at: absolute.child(later as u32) }) {
                                Ok(next) => truncated = next,
                                Err(_) => return Ok(()),
                            }
                        }
                        if crate::check::static_prune::replacement_admitted(
                            &self.state.resolved(self.context.registry), &truncated, &body_path, replacement, self.context.registry,
                        ) {
                            return Err(Refusal::Grammar("static prune: use the admitted equality binding"));
                        }
                        Ok(())
                    };
                    // The cut clause and the finished forms fix the replacement and its verdict, which each candidate of a mask shares.
                    match program.value().forms.last().and_then(|form| prefix_key::clause_cut_key(form, index + 1)) {
                        Some(key) => self.state.cached_replacement(key, admitted)?,
                        None => admitted()?,
                    }
                }
            }
        }
        self.check_nested_static_prune(program, open, checks, memo)
    }

    /// The static prune's verdicts on the conjuncts that this step completed
    /// in a list other than the top level of a clause's body: a branch of an
    /// `OR`, a list of an `IF` or an `ALL`, and a body of an `INIT`, `CHOOSE`
    /// or `RIGID_DET` form. Each such list is a conjunction, of whose rows
    /// the verdicts speak, with the types of the labels that the list's own
    /// atoms make: a conjunct that a verdict finds valid leaves the list's
    /// rows, and one that leaves the list no row makes its enclosing form
    /// constant. A list's alias or constant takes no replacement here.
    fn check_nested_static_prune(&self, program: &Node<Program>, open: Option<&NodePath>, checks: &PrefixChecks<'_>, memo: &MaskMemo) -> Result<(), Refusal> {
        use crate::program::path::{node_at, NodeRef};
        use crate::program::static_prune::{classify_prefix, makes_earlier_redundant, rule_message, Class};
        let before = memo.open_lists.get_or_init(|| {
            let (before, open) = self.state.partial()?;
            let form = before.value().forms.last()?;
            Some((before.value().forms.len(), open_lists(form, &open?)))
        });
        let Some((forms, lists)) = before else { return Ok(()) };
        let Some(form) = program.value().forms.last().filter(|_| *forms == program.value().forms.len()) else { return Ok(()) };
        let type_of = |relation: &RelationRef, column: &crate::program::ColumnName| self.fixed_column_type(checks, relation, column);
        for (path, prior) in lists {
            // The top level of a clause's body is `check_static_prune`'s.
            if matches!(form, crate::program::Form::Clause(_)) && path.0.len() == 1 {
                continue;
            }
            let Some(NodeRef::Body(body)) = node_at(NodeRef::from(form), path) else { continue };
            let count = match open {
                Some(open) if open.0.len() > path.0.len() && open.0.starts_with(&path.0) => open.0[path.0.len()].0 as usize,
                _ => body.conjuncts.len(),
            };
            for index in *prior..count.min(body.conjuncts.len()) {
                let prefix = crate::program::Body { conjuncts: body.conjuncts[..=index].into() };
                let message = match classify_prefix(&prefix, &type_of) {
                    Some(found) => match found.class {
                        Class::Unsatisfiable => Some(rule_message(found.rule).unwrap_or("static prune: no row satisfies the completed atom")),
                        Class::Valid => Some(rule_message(found.rule).unwrap_or("static prune: the completed atom repeats an existing test")),
                        Class::Alias | Class::Constant => None,
                    },
                    None => makes_earlier_redundant(&prefix)
                        .or_else(|| crate::program::static_prune::reads_an_earlier_row(&prefix, &|relation| relation_keys(self.context.registry, relation)))
                        .or_else(|| {
                            crate::program::static_prune::makes_membership_redundant(&prefix, &type_of, &|atom, column| binds_column(self.context.registry, atom, column))
                        })
                        .and_then(rule_message),
                };
                if let Some(message) = message {
                    return Err(Refusal::Grammar(message));
                }
            }
        }
        Ok(())
    }

    /// Where `state` shows a program with a form in progress, the refusal of
    /// `checks` on that program, with `candidate`.
    fn check_state(&self, state: &state::State, candidate: Candidate, checks: &PrefixChecks<'_>) -> Result<(), Refusal> {
        let Some((program, open)) = state.partial() else { return Ok(()) };
        if program.value().forms.is_empty() {
            return Ok(());
        }
        self.check_partial(&program, open.as_ref(), candidate, checks)
    }

    /// The refusal of `checks` on `program`, a program with a form in
    /// progress whose innermost open node is at `open`, with `candidate`.
    fn check_partial(&self, program: &Node<Program>, open: Option<&NodePath>, candidate: Candidate, checks: &PrefixChecks<'_>) -> Result<(), Refusal> {
        let check = || {
            let earlier = self.state.resolved(self.context.registry);
            let held = open.filter(|_| candidate == Candidate::AtomHead).and_then(|open| checks.check_atom_head_alone(&earlier, program, open));
            let refused = match held {
                Some(refused) => refused,
                None => checks.check(&resolve_for_checks(&earlier, program, self.context.registry), open, candidate, None),
            };
            match refused {
                Some((check, refusals)) => Err(Refusal::Check { check, refusals }),
                None => Ok(()),
            }
        };
        // A step shares only the verdict at an open node: a completed form keeps
        // the node that the step built, and its checks run on that node. A
        // single token's step shares it as well, so that the step of a token
        // that `forced` has checked at the state checks nothing again. A mask
        // reads the verdict alone, so it shares that of a completed form too.
        if candidate == Candidate::Any && (open.is_some() || checks.is_mask()) {
            if let Some(key) = prefix_key::key(program.value().forms.last().unwrap(), open) {
                return if checks.is_mask() { self.state.cached_prefix(key, check) } else { self.state.cached_single_prefix(key, check) };
            }
        }
        check()
    }

    /// Whether some completion of the constraint open in `state` passes the
    /// checks as a completed constraint does, or, where none does, the
    /// refusal of the last completion tried. The completions are the labels
    /// the grammar admits next, each stepped from `state`: after an
    /// operator, the first labels, a fresh one for `=` alone; after the first
    /// label, `0` and each label in scope but the first label, which the
    /// grammar refuses as the second under every operator, and for `=` a
    /// fresh label too.
    fn completes(&self, state: &state::State, checks: &PrefixChecks<'_>, reads_example: state::ReadsExample<'_>, order: &RefCell<Order>) -> Result<(), Refusal> {
        let Some((op, first)) = state.open_constraint() else {
            return self.check_state(state, Candidate::Any, checks);
        };

        let ordering = first.is_none() && matches!(op, ConstraintOp::Lt | ConstraintOp::Le | ConstraintOp::Gt | ConstraintOp::Ge);
        if ordering {
            match &*order.borrow() {
                Order::Refused(refusal) => return Err(refusal.clone()),
                Order::Passes => return Ok(()),
                Order::Unknown => {}
            }
        }
        let labels = (0..state.label_count()).rev().map(Token::Label);
        let tokens: Vec<Token> = match first {
            // Only `=` binds a label it makes, so a fresh first label of another operator leaves its label unbound.
            None => std::iter::once(Token::Control(Control::Fresh)).filter(|_| op == ConstraintOp::Eq).chain(labels).collect(),
            Some(first) => {
                let others = labels.filter(|token| *token != Token::Label(first.label.0));
                let fresh = (op == ConstraintOp::Eq).then_some(Token::Control(Control::Fresh));
                std::iter::once(Token::Control(Control::Zero)).chain(others).chain(fresh).collect()
            }
        };
        let mut refusal = Refusal::Grammar("a constraint has no completion");
        for token in tokens {
            match self.completes_with(state, &token, checks, reads_example, order) {
                Ok(()) => {
                    if ordering {
                        *order.borrow_mut() = Order::Passes;
                    }
                    return Ok(());
                }
                Err(next) => refusal = next,
            }
        }
        if ordering {
            *order.borrow_mut() = Order::Refused(refusal.clone());
        }
        Err(refusal)
    }

    /// [`Decoder::completes`] of the state after `token` from `state`.
    fn completes_with(&self, state: &state::State, token: &Token, checks: &PrefixChecks<'_>, reads_example: state::ReadsExample<'_>, order: &RefCell<Order>) -> Result<(), Refusal> {
        stats::units(Phase::DecodeCompletes, 1);
        match state.step(&self.context, token, reads_example) {
            Ok((next, _, _)) => self.completes(&next, checks, reads_example, order),
            Err(unexpected) => Err(Refusal::Grammar(unexpected)),
        }
    }
}

/// What the candidates of one mask share, each read of the state before
/// their step.
#[derive(Default)]
struct MaskMemo {
    order: RefCell<Order>,
    /// The path in the form in progress of the atom that a relation token
    /// opens at the state, and the static prune's verdict on the conjuncts
    /// that its step completes, which every relation token of the mask
    /// shares; set by the first relation token that the mask steps.
    head: std::cell::OnceCell<(NodePath, Result<(), Refusal>)>,
    /// The forms of the state's program with the form in progress, and the
    /// conjuncts complete in that form, where it is a clause.
    before: std::cell::OnceCell<Option<(usize, usize)>>,
    /// The forms of the state's program with the form in progress, and each
    /// list on the path of the form's open node, as [`open_lists`] gives.
    open_lists: std::cell::OnceCell<Option<(usize, Vec<(NodePath, usize)>)>>,
}

/// Whether `atom` can make the label at its site on `column`: its relation
/// holds rows, as a fact, a program relation or a lib relation over a finite
/// domain does, or one of its modes leaves `column` unbound and binds each
/// column it needs by a site that joins a label or holds `0`.
fn binds_column(registry: &Registry, atom: &crate::program::Atom, column: &crate::program::ColumnName) -> bool {
    use crate::program::{LabelUse, SiteArg};
    let RelationRef::Lib(name) = &atom.relation else { return true };
    let Some(relation) = registry.algebra_relation(name) else { return true };
    relation.modes.is_empty()
        || relation.modes.iter().any(|mode| {
            !mode.bound.contains(column)
                && mode.bound.iter().all(|bound| {
                    atom.sites.iter().any(|site| site.column == *bound && matches!(&site.value.args[..], [SiteArg::Label(LabelUse::Join(_) | LabelUse::Zero)]))
                })
        })
}

/// The keys of `relation` that the `(key ...)` items of its lib element's
/// `refines` form give, each as its columns: those of a fact relation and of
/// a lib relation. A relation of the program has none here.
fn relation_keys(registry: &Registry, relation: &RelationRef) -> Vec<Vec<crate::program::ColumnName>> {
    use crate::program::FactRelation;
    use crate::read::SExpr;
    let name: &str = match relation {
        RelationRef::Fact(FactRelation::Input) => "input",
        RelationRef::Fact(FactRelation::ExInput) => "ex_input",
        RelationRef::Fact(FactRelation::ExOutput) => "ex_output",
        RelationRef::Lib(name) => &name.0,
        _ => return Vec::new(),
    };
    let symbol = |item: &SExpr| match item {
        SExpr::Symbol { text, .. } => Some(text.clone()),
        _ => None,
    };
    registry
        .refines(name)
        .iter()
        .filter_map(|item| match item {
            SExpr::List { items, .. } if items.first().and_then(symbol).as_deref() == Some("key") => {
                items[1..].iter().map(|column| symbol(column).map(|text| crate::program::ColumnName::Written(text))).collect()
            }
            _ => None,
        })
        .collect()
}

/// Each list on `open`, the path of the open node of `form`: its path in
/// the form, and the count of its conjuncts that stand before the open one,
/// which are complete.
fn open_lists(form: &crate::program::Form, open: &NodePath) -> Vec<(NodePath, usize)> {
    use crate::program::path::{node_at, NodeRef};
    let root = NodeRef::from(form);
    (0..open.0.len())
        .filter_map(|len| {
            let path = NodePath(open.0[..len].into());
            matches!(node_at(root, &path), Some(NodeRef::Body(_))).then(|| (path, open.0[len].0 as usize))
        })
        .collect()
}

/// What the mask has found at a state of the order operators `<`, `<=`, `>`
/// and `>=`. No check tells them apart, so the first of them that the mask
/// tries gives the verdict of all four.

#[derive(Default)]
enum Order {
    #[default]
    Unknown,
    Refused(Refusal),
    Passes,
}
