//! The decode settings of `docs/engine/synthesis.md#decode-settings`, each
//! with its default. [`DecodeSettings::default`] holds no deadline, the
//! settings of a replay of the corpus; [`DecodeSettings::synthesis`] gives
//! the settings of the synthesis decode.

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
    /// The deadline per request, from the request's start, or `None` for no
    /// deadline.
    pub deadline: Option<Duration>,
    /// The rows a projection may hold on one example at one assignment, as
    /// `docs/engine/synthesis.md#decode-settings` gives it.
    pub projection_cap: u64,
    /// The work budget of an annotation or a mask walk, as
    /// `docs/engine/synthesis.md#decode-settings` gives it.
    pub table_work_cap: u64,
    /// Whether the evaluations check the rows that the outputs of a
    /// construction declare they copy ([`crate::eval::copies`]), and report
    /// the violations to [`crate::decode::Decoder::take_copy_violations`].
    pub check_copies: bool,
    /// Whether the `END` of a `RULE` clause tests the clause's relation, as
    /// `docs/engine/synthesis.md#decode-settings` gives it: an observation
    /// beside the step's other results, which ends no decode and changes no
    /// mask.
    pub rule_tests: bool,
    /// Apply proven local atom pruning while generating decoder offers.
    pub static_pruning: bool,
    /// Whether a case that reaches the model cap on an input gives the
    /// distinct grids of the models up to the cap there, or a stop with no
    /// output, as `docs/engine/synthesis.md#decode-settings` gives it. The
    /// consistency tests and the attempts read it; the admission of a `DET`
    /// and the determination read none of it.
    pub grids_at_model_cap: bool,
}

impl DecodeSettings {
    /// Begins one caller operation. All nested decoders, queries and packing
    /// borrow or clone this absolute deadline and cancellation thereafter.
    pub fn operation_limits(&self)->crate::eval::Limits {
        crate::eval::Limits::new(self.deadline.map(|duration|std::time::Instant::now()+duration),crate::eval::Cancellation::default())
    }
    /// The default settings with the deadline of the synthesis decode, 10 s per
    /// request.
    pub fn synthesis() -> DecodeSettings {
        DecodeSettings { deadline: Some(Duration::from_secs(10)), ..DecodeSettings::default() }
    }
}

/// The settings of a replay of the corpus: no deadline, so a verdict does not
/// depend on the machine's load.
impl Default for DecodeSettings {
    fn default() -> DecodeSettings {
        DecodeSettings {
            proposer_tokens: true,
            type_domain_proposers: true,
            vocabulary: VocabularyCaps::CORPUS,
            caps: Caps::CORPUS,
            deadline: None,
            projection_cap: 10_000,
            table_work_cap: 1 << 20,
            check_copies: false,
            rule_tests: false,
            static_pruning: false,
            grids_at_model_cap: true,
        }
    }
}
