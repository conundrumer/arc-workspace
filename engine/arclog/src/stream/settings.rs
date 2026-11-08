//! The decode settings of `docs/engine/synthesis.md#decode-settings`, each
//! with its default. [`DecodeSettings::default`] gives the settings of a
//! replay of the corpus; [`DecodeSettings::synthesis`] gives the settings of
//! the synthesis decode. A decode always offers the proposers
//! and the type-domain proposers as tokens, always applies the static prune
//! and always gives the grids at the model cap: `docs/engine/synthesis.md#switches`.

use crate::eval::values::{ByteCaps, Caps, ASSIGNMENT_BYTES_CAP, CANDIDATE_BYTES_CAP, REQUEST_BYTES_CAP, REQUEST_WORK_CAP};

/// The mutation node cap of [`DecodeSettings::synthesis`]. Provisional: the
/// nodes that a draw's search reaches on the gold programs set it.
pub const MUTATION_NODE_CAP: u64 = 1 << 17;

/// The mutation node cap of [`DecodeSettings::default`], the settings of a
/// replay of the corpus, whose search runs to the end of its finite domain
/// where the cap allows: a cap that no feasible search reaches.
pub const MUTATION_NODE_CAP_CORPUS: u64 = 1 << 30;

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
    /// The search nodes of one mutation draw's search, as
    /// `docs/engine/synthesis.md#decode-settings` gives it. No query, mask,
    /// step, table or walk of a decode reads it: each of those stops at a work
    /// cap, so that a stop does not depend on the machine's speed. A job's
    /// outer deadline lives in the job runner.
    pub mutation_node_cap: u64,
    /// The rows a projection may hold on one example at one assignment, as
    /// `docs/engine/synthesis.md#decode-settings` gives it.
    pub projection_cap: u64,
    /// The work budget of an annotation or a mask walk, as
    /// `docs/engine/synthesis.md#decode-settings` gives it.
    pub table_work_cap: u64,
    /// The work of one request, summed over every query and walk of it, as
    /// `docs/engine/synthesis.md#decode-settings` gives it.
    pub request_work_cap: u64,
    /// The bindings that the searches of one request may try before the effort
    /// guard stops it, as `docs/engine/synthesis.md#decode-settings` gives it.
    /// No result depends on it.
    pub effort_cap: u64,
    /// The bytes one request may hold at a time, as
    /// `docs/engine/synthesis.md#decode-settings` gives it.
    pub request_byte_cap: u64,
    /// The bytes one assignment of a table walk may hold at a time, as
    /// `docs/engine/synthesis.md#decode-settings` gives it.
    pub assignment_byte_cap: u64,
    /// The bytes the request of one candidate of a call that evaluates several
    /// (`successor_tables`) may hold at a time, as
    /// `docs/engine/synthesis.md#decode-settings` gives it. It is the same for
    /// every candidate, whatever the order or the count of the candidates.
    pub candidate_byte_cap: u64,
    /// The bytes of exported rows that a call keeps in memory at once for its
    /// candidates, as `docs/engine/synthesis.md#decode-settings` gives it: the
    /// rows of a candidate past it wait on disk, compressed, until read. It
    /// changes no result.
    pub spill_resident_bytes: u64,
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
        limits.request=crate::eval::RequestWork::begin_capped(self.request_work_cap,self.byte_caps(),self.effort_cap);
        limits
    }
    /// The byte budgets of a request and of each assignment in it.
    pub fn byte_caps(&self)->ByteCaps {
        ByteCaps { request: self.request_byte_cap, assignment: self.assignment_byte_cap, candidate: self.candidate_byte_cap }
    }
    /// The default settings with the mutation node cap of the synthesis
    /// decode, which only the mutation draw's search reads.
    pub fn synthesis() -> DecodeSettings {
        DecodeSettings { mutation_node_cap: MUTATION_NODE_CAP, ..DecodeSettings::default() }
    }
}

/// The default bytes of exported rows that a call keeps in memory at once for
/// its candidates ([`DecodeSettings::spill_resident_bytes`]).
pub const SPILL_RESIDENT_BYTES: u64 = 1 << 30;

/// The settings of a replay of the corpus and of the writer: the table work cap
/// is the writer's, so a stop at it is the same in a check and in the writer.
impl Default for DecodeSettings {
    fn default() -> DecodeSettings {
        DecodeSettings {
            vocabulary: VocabularyCaps::CORPUS,
            caps: Caps::CORPUS,
            mutation_node_cap: MUTATION_NODE_CAP_CORPUS,
            projection_cap: 10_000,
            table_work_cap: 1 << 21,
            request_work_cap: REQUEST_WORK_CAP,
            effort_cap: crate::eval::EFFORT_CAP,
            request_byte_cap: REQUEST_BYTES_CAP,
            assignment_byte_cap: ASSIGNMENT_BYTES_CAP,
            candidate_byte_cap: CANDIDATE_BYTES_CAP,
            spill_resident_bytes: SPILL_RESIDENT_BYTES,
            check_copies: false,
            rule_tests: false,
        }
    }
}
