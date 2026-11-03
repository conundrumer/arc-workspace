//! The decoder of `docs/engine/synthesis.md#token-mask`: the automaton that
//! reads a token stream into a program value, with the token mask at each
//! state. Its state, in `state`, steps by the grammar of the stream that
//! [`crate::stream::token_stream`] writes, and its mask,
//! [`Decoder::admissible`], admits a token where every check of
//! [`crate::check::checks`] holds, by its prefix form, on the program that
//! the token gives, but within a `DEMONSTRATED` form, where it admits each
//! token the grammar takes and the checks read the form at the token that
//! ends it: one [`PrefixChecks`] per state resolves, and infers the
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
//! or where the search spends its steps. Its interface
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

mod batch;
mod det_admission;
pub(crate) mod det_memo;
pub mod corpus;
mod interface;
pub mod replay;
pub mod program_read;
mod state;
mod prefix_key;
mod projections;

pub use batch::step_batch;
pub use det_admission::DetRefusal;
pub use interface::{BodyWidening, derived_at, open_clause, held_dets, relation_dets, walked_dets, Assigned, Consistency, LeftOut, OpenClause, Step, SubBody, SubBodyKey};
pub use projections::{projections, Projection, Projections};
pub use state::State;

use std::cell::RefCell;
use std::collections::HashMap;
use std::sync::{Arc, OnceLock};

use crate::check::prefix::{Candidate, PrefixChecks};
use crate::check::CheckId;
use crate::eval::instance::Constructions;
use crate::eval::copies::{CopyViolation, CopyViolations};
use crate::eval::values::HeldStops;
use crate::eval::{Cancellation, TableWork};
use crate::judge::candidates::PairCandidates;
use crate::program::path::NodePath;
use crate::program::{ProgramRelation, RelationRef};
use crate::program::{ConstraintOp, Node, Program};
use crate::registry::Registry;
use crate::resolver::resolve_last;
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
    /// The path of the first `OUT` form that was consistent, at which the
    /// decode ended.
    output: Option<NodePath>,
    assignments: Vec<Vec<(ProgramRelation, Arc<crate::relations::Relation>)>>,
    /// One record per accepted token, shared with the forks.
    trace: DecodeTrace,
    /// The mask of the current state with the step of each token it admits.
    held: Held,
    /// Where the evaluations report the declared rows that a construction's
    /// outputs break, where the settings check them.
    copies: Option<CopyViolations>,
    /// The stops that this decode's requests hold, which the limits of each
    /// request share ([`Decoder::limits`]).
    held_stops: Arc<HeldStops>,
}

/// What [`Decoder::admissible`] computes at a state: the mask, and the
/// state and the forced tokens that each admitted token gives, by the
/// token's id, which [`Decoder::advance`] takes in place of a second check.
struct Mask {
    mask: TokenMask,
    steps: HashMap<u32, (state::State, Vec<Token>)>,
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
        let context = Context { registry, settings: *settings, vocabulary: Vocabulary::new(registry, settings) };
        let state = state::State::new();
        Decoder { task, session, constructions, context: Arc::new(context), state, before: None, train: None, cancellation: Cancellation::default(), operation_limits:None, output: None, assignments: Vec::new(), trace: DecodeTrace::default(), held: Held::default(), copies: settings.check_copies.then(CopyViolations::default), held_stops: Arc::default() }
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
    pub fn admissible(&self) -> TokenMask {
        self.held.0.get_or_init(|| self.compute_mask()).mask.clone()
    }

    /// Whether each token whose id `ids` gives may come next, as
    /// [`Decoder::admissible`] decides it, with the checks of the mask run
    /// over those tokens alone and none of the mask kept for a later step.
    /// Where the decode holds the mask of its state, it reads the verdicts
    /// from the mask.
    pub fn admits(&self, ids: &[u32]) -> Vec<bool> {
        let mask = match self.held.0.get() {
            Some(held) => held.mask.clone(),
            None => self.mask_over(ids.iter().copied()).mask,
        };
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
        let vocabulary = &self.context.vocabulary;
        let mut mask = TokenMask::new(vocabulary.len());
        let mut steps = HashMap::new();
        if self.output.is_some() {
            return Mask { mask, steps };
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
            return Mask { mask, steps };
        }
        self.with_checks_at_state(|checks| {
            checks.prepare_mask();
            let order = RefCell::default();
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
                if self.state.mask_may_take(token) {
                    if let Some(result) = class_of[id as usize].and_then(|class| admitted[class]) {
                        if result {
                            // A member shares the class's verdict, and takes its own
                            // grammar step.
                            let step = self.grammar_next(token).expect("a class member passes the same grammar");
                            mask.insert(id);
                            steps.insert(id, step);
                        }
                        continue;
                    }
                    let next = if self.state.grammar_only_candidate(token) { self.grammar_next(token) } else { self.next(token, checks, &order) };
                    if let Some(class) = class_of[id as usize] {
                        admitted[class] = Some(next.is_ok());
                    }
                    if let Ok(step) = next {
                        mask.insert(id);
                        steps.insert(id, step);
                    }
                }
            }
        });
        Mask { mask, steps }
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
        let mut steps = HashMap::new();
        self.with_checks_at_state(|checks| {
            let order = RefCell::default();
            for id in 0..u32::try_from(vocabulary.len()).expect("fewer than 2^32 tokens") {
                let token = vocabulary.token(id).expect("an id of the vocabulary");
                if let Ok(step) = self.next(token, checks, &order) {
                    mask.insert(id);
                    steps.insert(id, step);
                }
            }
        });
        Mask { mask, steps }
    }

    /// Runs `body` with the checks over the prefixes that follow the
    /// state's finished forms, which resolve, and whose clauses and types
    /// are made, once.
    fn with_checks<R>(&self, body: impl FnOnce(&PrefixChecks<'_>) -> R) -> R {
        let _timed = stats::span(Phase::DecodeWithChecks);
        let registry = self.context.registry;
        let resolved = self.state.resolved(registry);
        self.state.with_clauses(registry, |clauses| PrefixChecks::with(&resolved, clauses, registry, body))
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
        let advanced = self.advance(&token, true);
        self.apply(advanced)
    }

    /// [`Decoder::step`] with no consistency test of an `OUT` form and no
    /// rule test: the step gives `None` as its `consistency` and as its
    /// `rule_test`, so the decode ends at no `OUT` form and takes no
    /// assignments from the step. A caller that steps no further token that
    /// reads the output of the step uses it.
    pub fn step_untested(&mut self, token: Token) -> StepResult {
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
        self.next_state(token).map(|(_, forced)| forced)
    }

    /// The state after `token`, and the tokens the engine emits after it:
    /// those the held mask keeps for the token's id, or else those that the
    /// checks of the state give.
    fn next_state(&self, token: &Token) -> Result<(state::State, Vec<Token>), Refusal> {
        let kept = self.held.0.get().and_then(|held| held.steps.get(&self.context.vocabulary.id(token)?));
        match kept {
            Some((state, forced)) => Ok((state.clone(), forced.clone())),
            None => self.with_checks(|checks| self.next(token, checks, &RefCell::default())),
        }
    }

    /// The state after `token`, and what the step gives, which
    /// [`Decoder::apply`] makes the decode's. With `tested` false, the step
    /// runs no consistency test.
    fn advance(&self, token: &Token, tested: bool) -> Result<Advanced, Refusal> {
        let (state, forced) = self.next_state(token)?;
        let consistency = if tested { self.consistency(&self.state, &state, Tested::Out) } else { None };
        let rule_test = if tested && self.context.settings.rule_tests { self.consistency(&self.state, &state, Tested::Rule) } else { None };
        let counted = |tested: Option<(Consistency, u64)>| match tested {
            Some((consistency, capped)) => (Some(consistency), capped),
            None => (None, 0),
        };
        let ((consistency, capped_sets), (rule_test, rule_capped_sets)) = (counted(consistency), counted(rule_test));
        Ok(Advanced { token: token.clone(), state, step: Step { forced: forced.into(), consistency, rule_test, capped_sets, rule_capped_sets } })
    }

    fn apply(&mut self, advanced: Result<Advanced, Refusal>) -> StepResult {
        let Advanced { token, state, step } = advanced?;
        self.before = Some(std::mem::replace(&mut self.state, state));
        self.held = Held::default();
        self.record(token, &step);
        if let Some(Consistency::Consistent { assignments }) = &step.consistency {
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
            Consistency::Consistent { assignments } => (Verdict::Consistent { assignments: assignments.len() }, None),
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
        self.trace.push(record);
        for forced in step.forced.iter() {
            self.trace.push(DecodeRecord::new(forced.clone(), Emitter::Engine));
        }
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
        self.trace.records().iter().map(|record| record.capped_sets).sum()
    }

    /// Attaches `top_k`, the language model's top tokens at the decision of
    /// the record at `step` of the trace, to that record in this decode's
    /// trace alone. Gives `false` where the trace has no such record.
    pub fn attach_top_k(&mut self, step: usize, top_k: TopK) -> bool {
        self.trace.update(step, |record| record.top_k = Some(top_k))
    }

    /// Uses one caller operation for every nested query and materialization.
    /// Forks retain its absolute deadline; no query starts another clock.
    pub fn with_operation_limits(mut self,limits:crate::eval::Limits)->Self {
        self.cancellation=limits.cancellation.clone();
        self.operation_limits=Some(limits);self
    }

    /// A second decode from the same state, which shares this one's caches
    /// and takes a cancellation of its own, and a store of held stops of its
    /// own that holds the stops at the table work cap this decode holds now
    /// and shares the stops at the deadline ([`HeldStops::snapshot`]).
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
    fn next(&self, token: &Token, checks: &PrefixChecks<'_>, order: &RefCell<Order>) -> Result<(state::State, Vec<Token>), Refusal> {
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
        if let Some((program, open)) = state.partial() {
            if !program.value().forms.is_empty() && !in_demonstrated(&program, open.as_ref()) {
                if self.context.settings.static_pruning {
                    self.check_static_prune(&program, open.as_ref(), checks)?;
                }
                if let (Some(open), true, Token::Lib(_) | Token::Relation(_)) = (&open, opened.is_some(), token) {
                    let relation = state.open_relation().expect("an atom stands open");
                    if let Some((check, refusals)) = checks.check_atom_head(&earlier(), &program, open, &relation) {
                        return Err(Refusal::Check { check, refusals });
                    }
                    return Ok((state, forced));
                }
                let candidate = if opened.is_some() { Candidate::AtomHead } else { Candidate::Any };
                self.check_state(&state, candidate, checks)?;
            }
        }
        if state.open_constraint().is_some() {
            let _timed = stats::span(Phase::DecodeCompletes);
            self.completes(&state, checks, &reads_example, order)?;
        } else if state.head_site_completions(usize::MAX).is_some() {
            let _timed = stats::span(Phase::DecodeCompletes);
            let steps = &mut projection_steps();
            // A site of one argument first: the sets of labels it can hold are many, and one label passes where any does.
            self.completes_projection(&state, checks, &reads_example, 1, steps).or_else(|_| self.completes_projection(&state, checks, &reads_example, usize::MAX, steps))?;
        }
        self.admit_written_dets(token, &state)?;
        Ok((state, forced))
    }

    /// Check only conjuncts that this grammar step completed. An atom can
    /// close on the next relation token; END can finish the entire form.
    /// Restrict replacement certificates to flat top-level clauses for now.
    fn check_static_prune(
        &self,
        program: &Node<Program>,
        open: Option<&NodePath>,
        checks: &PrefixChecks<'_>,
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
        let Some((body, count)) = completed(program, open) else { return Ok(()) };
        let before = self.state.partial();
        let prior = before.as_ref().filter(|(p, _)| p.value().forms.len() == program.value().forms.len())
            .and_then(|(p, o)| completed(p, o.as_ref())).map_or(0, |(_, count)| count);
        let type_of = |relation: &RelationRef, column: &crate::program::ColumnName| self.fixed_column_type(checks, relation, column);
        for index in prior..count {
            let prefix = crate::program::Body { conjuncts: body.conjuncts[..=index].into() };
            let Some(found) = crate::program::static_prune::classify_prefix(&prefix, &type_of) else { continue };
            match found.class {
                crate::program::static_prune::Class::Unsatisfiable => return Err(Refusal::Grammar("static prune: no row satisfies the completed atom")),
                // A membership test that an earlier atom's column already implies has a twin that the decoder takes: the
                // membership atom first, as the binder, and the other atom joining its label. Both write one query, so
                // refusing the test only in the order where it comes second makes legality depend on the order.
                crate::program::static_prune::Class::Valid if found.rule == "membership.subtype" => {}
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
        Ok(())
    }

    /// Where `state` shows a program with a form in progress, the refusal of
    /// `checks` on that program, with `candidate`.
    fn check_state(&self, state: &state::State, candidate: Candidate, checks: &PrefixChecks<'_>) -> Result<(), Refusal> {
        let Some((program, open)) = state.partial() else { return Ok(()) };
        if program.value().forms.is_empty() || in_demonstrated(&program, open.as_ref()) {
            return Ok(());
        }
        let check = || {
            let resolved = resolve_last(&self.state.resolved(self.context.registry), &program, self.context.registry);
            match checks.check(&resolved, open.as_ref(), candidate, None) {
                Some((check, refusals)) => Err(Refusal::Check { check, refusals }),
                None => Ok(()),
            }
        };
        // Only the verdict at an open node is shared: a completed form keeps the
        // node that the step built, and its checks run on that node. A single
        // token's step shares it as well, so that the step of a token that
        // `forced` has checked at the state checks nothing again.
        if candidate == Candidate::Any && open.is_some() {
            if let Some(key) = prefix_key::key(program.value().forms.last().unwrap(), open.as_ref()) {
                return if checks.is_mask() { self.state.cached_prefix(key, check) } else { self.state.cached_single_prefix(key, check) };
            }
        }
        check()
    }

    /// Whether some completion of the constraint open in `state` passes the
    /// checks as a completed constraint does, or, where none does, the
    /// refusal of the last completion tried. The completions are the labels
    /// the grammar admits next, each stepped from `state`: after an
    /// operator, the first labels, a fresh one for `=` alone; after the first label of `=`, `0`, the
    /// labels in scope and a fresh label; after the first label of any other
    /// operator, the first label itself, which passes exactly where some
    /// second operand does.
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
            Some(first) if op != ConstraintOp::Eq => vec![Token::Label(first.label.0)],
            Some(_) => std::iter::once(Token::Control(Control::Zero)).chain(labels).chain([Token::Control(Control::Fresh)]).collect(),
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

    /// Whether some completion of the projection of an instance input, or
    /// of the field of a body site, that stands open in `state` passes the
    /// checks, or, where none does, the refusal of the last completion
    /// tried. The completions are the tokens of
    /// [`state::State::head_site_completions`] with `limit` at each head
    /// site that stands open or follows, up to the state where the input is
    /// closed or the field's label stands, which is the one the checks must
    /// pass. The search is depth-first, and where it has spent `steps` it
    /// refuses, with a refusal that says the search spent its budget.
    fn completes_projection(&self, state: &state::State, checks: &PrefixChecks<'_>, reads_example: state::ReadsExample<'_>, limit: usize, steps: &mut usize) -> Result<(), Refusal> {
        let Some(tokens) = state.head_site_completions(limit) else { return Ok(()) };
        let conflicts = if checks.is_mask() { state.fixed_label_conflicts(self.context.registry, &|relation, column| self.fixed_column_type(checks, relation, column)) } else { Vec::new() };
        let mut refusal = Refusal::Grammar("a projection has no completion");
        for token in tokens {
            if *steps == 0 {
                return Err(Refusal::Grammar("the completion search of a projection spent its budget"));
            }
            *steps -= 1;
            stats::units(Phase::DecodeCompletes, 1);
            // The refused label still spends its search step, as the original
            // refuses it at `check_state` with no deeper search.
            if matches!(&token, Token::Label(label) if conflicts.contains(label)) {
                continue;
            }
            let next = match state.step(&self.context, &token, reads_example) {
                Ok((next, _, _)) => next,
                Err(unexpected) => {
                    refusal = Refusal::Grammar(unexpected);
                    continue;
                }
            };
            match self.check_state(&next, Candidate::Any, checks).and_then(|()| self.completes_projection(&next, checks, reads_example, limit, steps)) {
                Ok(()) => return Ok(()),
                Err(next) => refusal = next,
            }
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

/// Whether the last form of `program`, whose innermost open node is at
/// `open`, is a `DEMONSTRATED` form in progress. The checks read no prefix
/// of such a form: they read the form whole, at the step that ends it.
fn in_demonstrated(program: &Node<Program>, open: Option<&NodePath>) -> bool {
    open.is_some() && matches!(program.value().forms.last(), Some(crate::program::Form::Demonstrated(_)))
}

/// The steps of the completion search of a projection, per token. A token
/// whose search spends them is refused. `ARCLOG_PROJECTION_STEPS` sets them,
/// read once; 96 where it is unset or not a number. Every gold program of the
/// ramp and training corpora decodes within 64.
fn projection_steps() -> usize {
    static STEPS: OnceLock<usize> = OnceLock::new();
    *STEPS.get_or_init(|| std::env::var("ARCLOG_PROJECTION_STEPS").ok().and_then(|v| v.parse().ok()).unwrap_or(96))
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
