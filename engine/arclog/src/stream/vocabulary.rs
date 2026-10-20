//! The vocabulary: the map between each token and its id, by the fixed
//! slots of `docs/engine/synthesis.md#token-mask`.

use crate::hash::StableHashMap;
use crate::program::FactRelation;
use crate::registry::{LibEntry, LibName, Proposer, ProposerKind, Registry};

use super::{Control, DecodeSettings, Token, VocabularyCaps};

/// The tokens of one decode by id, and the id of each. The slots stand in
/// this order: the control tokens, the lib relations, relation macros and
/// components, the proposers the settings offer, the fact relations, then
/// the relation, column and label slots up to the settings' caps. Lib names
/// stand in the order of their text within each kind.
#[derive(Clone, Debug)]
pub struct Vocabulary<'r> {
    registry: &'r Registry,
    caps: VocabularyCaps,
    tokens: Box<[Token]>,
    ids: StableHashMap<Token, u32>,
}

impl<'r> Vocabulary<'r> {
    pub fn new(registry: &'r Registry, settings: &DecodeSettings) -> Vocabulary<'r> {
        let mut lib: Vec<&LibName> = Vec::new();
        let mut proposers: Vec<&LibName> = Vec::new();
        for name in registry.names() {
            match registry.entry(name).expect("a name the registry gives") {
                LibEntry::Relation(_) | LibEntry::Component(_) | LibEntry::Macro(_) => lib.push(name),
                LibEntry::Proposer(proposer) => {
                    if offers(proposer, settings) {
                        proposers.push(name);
                    }
                }
            }
        }
        lib.sort_by(|a, b| a.0.cmp(&b.0));
        proposers.sort_by(|a, b| a.0.cmp(&b.0));
        let caps = settings.vocabulary;
        let tokens: Box<[Token]> = Control::ALL
            .into_iter()
            .map(Token::Control)
            .chain(lib.into_iter().map(|name| Token::Lib(name.clone())))
            .chain(proposers.into_iter().map(|name| Token::Proposer(name.clone())))
            .chain([FactRelation::Input, FactRelation::ExInput, FactRelation::ExOutput].map(Token::Fact))
            .chain((0..caps.relations).map(Token::Relation))
            .chain((0..caps.columns).map(Token::Column))
            .chain((0..caps.labels).map(Token::Label))
            .collect();
        let ids = tokens.iter().enumerate().map(|(id, token)| (token.clone(), u32::try_from(id).expect("fewer than 2^32 tokens"))).collect();
        Vocabulary { registry, caps, tokens, ids }
    }

    /// The registry whose names the vocabulary holds.
    pub fn registry(&self) -> &'r Registry {
        self.registry
    }

    /// The caps of the relation, column and label slots.
    pub fn caps(&self) -> VocabularyCaps {
        self.caps
    }

    /// The id of `token`, where the vocabulary holds it.
    pub fn id(&self, token: &Token) -> Option<u32> {
        self.ids.get(token).copied()
    }

    /// The token of `id`, where the vocabulary holds one.
    pub fn token(&self, id: u32) -> Option<&Token> {
        self.tokens.get(id as usize)
    }

    /// The count of the tokens.
    pub fn len(&self) -> usize {
        self.tokens.len()
    }

    pub fn is_empty(&self) -> bool {
        self.tokens.is_empty()
    }
}

/// Whether `settings` offer `proposer` as a token.
fn offers(proposer: &Proposer, settings: &DecodeSettings) -> bool {
    let domain = matches!(proposer.kind, ProposerKind::Native { domain: true });
    settings.proposer_tokens && (settings.type_domain_proposers || !domain)
}
