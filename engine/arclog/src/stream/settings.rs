//! The decode settings of `docs/engine/synthesis.md#decode-settings`, each
//! with its default. [`DecodeSettings::default`] holds no deadline, the
//! settings of a replay of the corpus; [`DecodeSettings::synthesis`] gives
//! the settings of the synthesis decode. A decode always offers the proposers
//! and the type-domain proposers as tokens, always applies the static prune
//! and always gives the grids at the model cap: `docs/engine/synthesis.md#switches`.

use std::time::Duration;

use crate::eval::values::{Caps, REQUEST_WORK_CAP};

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
    pub vocabulary: VocabularyCaps,
    /// The caps a prefix runs under.
    pub caps: Caps,
    /// The deadline of the mutation draw's search, from its start, or `None`
    /// for none. No query, mask, step, table or walk of a decode reads it: each
    /// of those stops at a work cap, so that a stop does not depend on the
    /// machine's speed (`docs/engine/synthesis.md#decode-settings`). A job's
    /// outer deadline lives in the job runner.
    pub deadline: Option<Duration>,
    /// The rows a projection may hold on one example at one assignment, as
    /// `docs/engine/synthesis.md#decode-settings` gives it.
    pub projection_cap: u64,
    /// The work budget of an annotation or a mask walk, as
    /// `docs/engine/synthesis.md#decode-settings` gives it.
    pub table_work_cap: u64,
    /// The work of one request, summed over every query and walk of it, as
    /// `docs/engine/synthesis.md#decode-settings` gives it.
    pub request_work_cap: u64,
    /// Whether the evaluations check the rows that the outputs of a
    /// construction declare they copy ([`crate::eval::copies`]), and report
    /// the violations to [`crate::decode::Decoder::take_copy_violations`].
    pub check_copies: bool,
    /// Whether the `END` of a `RULE` clause tests the clause's relation, as
    /// `docs/engine/synthesis.md#decode-settings` gives it: an observation
    /// beside the step's other results, which ends no decode and changes no
    /// mask.
    pub rule_tests: bool,
}

impl DecodeSettings {
    /// Begins one caller operation, a request: its limits count the work of
    /// every nested decoder, query and packing, under the request work cap,
    /// and [`crate::eval::RequestWork::latest`] gives that count on this
    /// thread until another request begins on it.
    pub fn operation_limits(&self)->crate::eval::Limits {
        let mut limits=crate::eval::Limits::new(Some(self.request_work_cap),crate::eval::Cancellation::default());
        limits.request=crate::eval::RequestWork::begin(self.request_work_cap);
        limits
    }
    /// The default settings with the deadline of the synthesis decode, 10 s,
    /// which only the mutation draw's search reads.
    pub fn synthesis() -> DecodeSettings {
        DecodeSettings { deadline: Some(Duration::from_secs(10)), ..DecodeSettings::default() }
    }
}

/// The settings of a replay of the corpus and of the writer: the table work cap
/// is the writer's, so a stop at it is the same in a check and in the writer.
impl Default for DecodeSettings {
    fn default() -> DecodeSettings {
        DecodeSettings {
            vocabulary: VocabularyCaps::CORPUS,
            caps: Caps::CORPUS,
            deadline: None,
            projection_cap: 10_000,
            table_work_cap: 1 << 21,
            request_work_cap: REQUEST_WORK_CAP,
            check_copies: false,
            rule_tests: false,
        }
    }
}
