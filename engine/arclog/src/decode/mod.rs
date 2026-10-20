//! The decoder of `docs/engine/synthesis.md#token-mask`: the automaton that
//! reads a token stream into a program value, with the token mask at each
//! state. Its state, in `state`, steps by the grammar of the stream that
//! [`crate::stream::token_stream`] writes, and its mask, in `mask`, admits
//! a token where every check of [`crate::check::checks`] holds, by its prefix
//! form, on the program that the token gives.

mod mask;
mod state;

use std::sync::Arc;

use crate::check::CheckId;
use crate::eval::instance::Constructions;
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
}

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

    /// The ids in the mask, in order.
    pub fn ids(&self) -> impl Iterator<Item = u32> + '_ {
        let ids = 0..u32::try_from(self.words.len() * 64).expect("fewer than 2^32 ids");
        ids.filter(|id| self.contains(*id))
    }
}

impl<'a> Decoder<'a> {
    /// A decode of no token yet. The arguments are those of
    /// [`crate::eval::Evaluation`] less the program and its parameter values,
    /// which the decode builds, with `settings` in place of its limits.
    pub fn new(task: &'a Task, session: &'a TaskSession, registry: &'a Registry, constructions: &'a Constructions, settings: &DecodeSettings) -> Decoder<'a> {
        let context = Context { registry, settings: *settings, vocabulary: Vocabulary::new(registry, settings), cache: mask::Cache::default() };
        Decoder { task, session, constructions, context: Arc::new(context), state: state::State::new() }
    }

    /// The ids of the decode's tokens.
    pub fn vocabulary(&self) -> &Vocabulary<'a> {
        &self.context.vocabulary
    }

    pub fn settings(&self) -> &DecodeSettings {
        &self.context.settings
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

    /// Whether `token` is in the mask, or why it is not.
    pub fn admits(&self, token: &Token) -> Result<(), Refusal> {
        self.next(token).map(|_| ())
    }

    /// Advances the decode by `token`, and gives the tokens that the engine
    /// emits after it; or refuses a token outside the mask, and leaves the
    /// decode as it was.
    pub fn step(&mut self, token: Token) -> Result<Box<[Token]>, Refusal> {
        let (state, forced) = self.next(&token)?;
        self.state = state;
        Ok(forced.into())
    }

    /// A second decode from the same state, which shares this one's caches.
    pub fn fork(&self) -> Decoder<'a> {
        self.clone()
    }

    /// The program so far: its finished forms.
    pub fn program(&self) -> &Node<Program> {
        self.state.program()
    }

    /// The state after `token`, and the tokens the engine emits after it,
    /// where `token` is in the mask.
    fn next(&self, token: &Token) -> Result<(state::State, Vec<Token>), Refusal> {
        let vocabulary = &self.context.vocabulary;
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
