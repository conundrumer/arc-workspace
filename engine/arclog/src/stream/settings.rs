//! The decode settings of `docs/engine/synthesis.md#decode-settings`, each
//! with its default.

use std::time::Duration;

use crate::eval::values::Caps;

/// The relation, column and label slots of the vocabulary.
#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub struct VocabularyCaps {
    /// The relations a program declares, the outputs of its instances and
    /// `CHOOSE` forms included.
    pub relations: u32,
    /// The positions of a relation's columns, of a component's inputs and
    /// of a form's named clauses.
    pub columns: u32,
    /// The labels of one label scope.
    pub labels: u32,
}

impl VocabularyCaps {
    /// The caps of `docs/engine/synthesis.md#decode-settings`.
    pub const CORPUS: VocabularyCaps = VocabularyCaps { relations: 512, columns: 64, labels: 64 };
}

/// What a decode reads.
#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub struct DecodeSettings {
    /// Whether the vocabulary offers the proposers as tokens.
    pub proposer_tokens: bool,
    /// Whether the proposers the vocabulary offers include the type-domain
    /// proposers.
    pub type_domain_proposers: bool,
    pub vocabulary: VocabularyCaps,
    /// The caps a prefix runs under.
    pub caps: Caps,
    /// The deadline per candidate program.
    pub deadline: Duration,
}

impl Default for DecodeSettings {
    fn default() -> DecodeSettings {
        DecodeSettings {
            proposer_tokens: true,
            type_domain_proposers: true,
            vocabulary: VocabularyCaps::CORPUS,
            caps: Caps::CORPUS,
            deadline: Duration::from_secs(10),
        }
    }
}
