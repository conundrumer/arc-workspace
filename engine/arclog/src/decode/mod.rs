//! The decoder of `docs/engine/synthesis.md#token-mask`: the automaton that
//! reads a token stream into a program value, with the token mask at each
//! state. Its state, in `state`, steps by the grammar of the stream that
//! [`crate::stream::token_stream`] writes, and its mask, in `mask`, admits
//! a token where every check of [`crate::check::checks`] holds, by its prefix
//! form, on the program that the token gives. Its interface beside the
//! mask, in `interface`, gives the rows of the body so far and the
//! consistency test at a `RULE` clause's end, and its batch form, in
//! `batch`, steps many decodes at once.

mod batch;
mod interface;
mod mask;
mod state;

pub use batch::step_batch;
pub use interface::{Consistency, Step};

use std::sync::Arc;

use crate::check::CheckId;
use crate::eval::instance::Constructions;
use crate::eval::Cancellation;
use crate::judge::candidates::PairCandidates;
use crate::program::path::NodePath;
use crate::program::ProgramRelation;
use crate::program::{Node, Program};
use crate::registry::Registry;
use crate::resolver::ResolvedProgram;
use crate::session::TaskSession;
use crate::stream::{DecodeSettings, Token, Vocabulary};
use crate::task::Task;

/// A decode over a task in a task session.
#[derive(Clone)]
pub struct Decoder<'a> {
    task: &'a Task,
    session: &'a TaskSession,
    constructions: &'a Constructions,
    context: Arc<Context<'a>>,
    state: state::State,
    /// The candidates of the train pairs that the consistency test reads,
    /// where the decode judges them.
    train: Option<Arc<[PairCandidates<'a>]>>,
    cancellation: Cancellation,
    /// The first relation that was consistent, at which the decode ended.
    output: Option<ProgramRelation>,
    assignments: Vec<Vec<(ProgramRelation, Arc<crate::relations::Relation>)>>,
    columns: Option<crate::eval::output::GridColumns>,
}

/// What [`Decoder::step`] gives.
pub type StepResult = Result<Step, Refusal>;

/// What every fork of a decode shares.
pub(crate) struct Context<'a> {
    registry: &'a Registry,
    settings: DecodeSettings,
    vocabulary: Vocabulary<'a>,
    cache: mask::Cache,
}

impl Context<'_> {
    fn resolved(&self, program: &Node<Program>) -> Arc<ResolvedProgram> {
        self.cache.resolved(program, self.registry)
    }
}

/// Why a decode refuses a token: the token is outside the mask.
#[derive(Clone, PartialEq, Eq, Debug)]
pub enum Refusal {
    /// The grammar of the stream gives no such token at the state, or a token
    /// that the engine would emit after it is outside the vocabulary.
    Grammar(&'static str),
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
        let context = Context { registry, settings: *settings, vocabulary: Vocabulary::new(registry, settings), cache: mask::Cache::default() };
        let state = state::State::new();
        Decoder { task, session, constructions, context: Arc::new(context), state, train: None, cancellation: Cancellation::default(), output: None, assignments: Vec::new(), columns: None }
    }

    /// The ids of the decode's tokens.
    pub fn vocabulary(&self) -> &Vocabulary<'a> {
        &self.context.vocabulary
    }

    /// The task, the session and the constructions that the decode's
    /// prefixes are evaluated on.
    pub fn evaluation_inputs(&self) -> (&'a Task, &'a TaskSession, &'a Constructions) {
        (self.task, self.session, self.constructions)
    }

    /// The tokens that may come next.
    pub fn admissible(&self) -> TokenMask {
        let vocabulary = &self.context.vocabulary;
        let mut mask = TokenMask::new(vocabulary.len());
        for id in 0..u32::try_from(vocabulary.len()).expect("fewer than 2^32 tokens") {
            let token = vocabulary.token(id).expect("an id of the vocabulary");
            if self.next(token).is_ok() {
                mask.insert(id);
            }
        }
        mask
    }

    /// Advances the decode by `token`, and gives the tokens that the engine
    /// emits after it, with the consistency of the relation of a `RULE`
    /// clause that the token ends; or refuses a token outside the mask, and
    /// leaves the decode as it was. The decode ends at the first consistent
    /// relation, and refuses every token after it.
    pub fn step(&mut self, token: Token) -> StepResult {
        let advanced = self.advance(&token);
        self.apply(advanced)
    }

    /// The state after `token`, and what the step gives, which
    /// [`Decoder::apply`] makes the decode's.
    fn advance(&self, token: &Token) -> Result<(state::State, Step), Refusal> {
        let (state, forced) = self.next(token)?;
        let judged = self.consistency(self.state.program(), state.program());
        let (consistency, columns) = judged.map_or((None, None), |(result, columns)| (Some(result), columns));
        Ok((state, Step { forced: forced.into(), consistency, columns }))
    }

    fn apply(&mut self, advanced: Result<(state::State, Step), Refusal>) -> StepResult {
        let (state, step) = advanced?;
        self.state = state;
        if let Some(Consistency::Consistent { assignments }) = &step.consistency {
            self.assignments = assignments.clone();
            self.columns = step.columns;
            let Some(crate::program::Form::Clause(clause)) = self.state.program().value().forms.last() else {
                unreachable!("a consistent relation is a clause's")
            };
            self.output = Some(clause.value().derives.clone());
        }
        Ok(step)
    }

    /// A second decode from the same state, which shares this one's caches
    /// and takes a cancellation of its own.
    pub fn fork(&self) -> Decoder<'a> {
        Decoder { cancellation: Cancellation::default(), ..self.clone() }
    }

    /// The program so far: its finished forms.
    pub fn program(&self) -> &Node<Program> {
        self.state.program()
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
    fn next(&self, token: &Token) -> Result<(state::State, Vec<Token>), Refusal> {
        let vocabulary = &self.context.vocabulary;
        if self.output.is_some() {
            return Err(Refusal::Grammar("the decode has ended at its `&output`"));
        }
        if vocabulary.id(token).is_none() {
            return Err(Refusal::Grammar("the vocabulary holds no such token"));
        }
        let (state, forced) = self.state.step(&self.context, token).map_err(Refusal::Grammar)?;
        if forced.iter().any(|token| vocabulary.id(token).is_none()) {
            return Err(Refusal::Grammar("a token the engine emits after it passes a vocabulary cap"));
        }
        if let Some((program, open)) = state.partial() {
            if !program.value().forms.is_empty() {
                if let Some(refusal) = self.context.cache.verdict(&program, open.as_ref(), self.context.registry) {
                    return Err(refusal);
                }
            }
        }
        Ok((state, forced))
    }
}
