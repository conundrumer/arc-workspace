//! The decode settings of `docs/engine/synthesis.md#decode-settings`, each
//! with its default. [`DecodeSettings::default`] gives the settings of a
//! replay of the corpus; [`DecodeSettings::synthesis`] gives the settings of
//! the synthesis decode; [`DecodeSettings::measurement`] gives the settings of
//! a stage that measures what the gold programs need. A decode always offers the proposers
//! and the type-domain proposers as tokens, always applies the static prune
//! and always gives the grids at the model cap: `docs/engine/synthesis.md#switches`.

use crate::eval::values::{ByteCaps, Caps, SearchCaps, ASSIGNMENT_BYTES_CAP, ATOM_STATE_CAP, CANDIDATE_BYTES_CAP, COLUMN_SEARCH_WORK_CAP, COMPARED_ROWS_CAP, LABELING_NODE_CAP, PROJECTION_STEP_CAP, REQUEST_BYTES_CAP, REQUEST_WORK_CAP, STUDY_ROW_WORK_CAP};

/// The mutation node cap of [`DecodeSettings::synthesis`]. Provisional: the
/// nodes that a draw's search reaches on the gold programs set it.
pub const MUTATION_NODE_CAP: u64 = 1 << 17;

/// The mutation node cap of [`DecodeSettings::default`], the settings of a
/// replay of the corpus, whose search runs to the end of its finite domain
/// where the cap allows: a cap that no feasible search reaches.
pub const MUTATION_NODE_CAP_CORPUS: u64 = 1 << 30;

/// The cap that [`DecodeSettings::measurement`] gives each setting that a
/// gauge measures: far above any quantity that the memory of a machine can
/// hold, and far below `u64::MAX`, which `TableWork` reads as
/// no cap.
pub const MEASURED_CAP: u64 = 1 << 48;

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
    /// The content one prefix check of the mask may count: the check of a
    /// written `DET`'s admission stops there and admits its token, as
    /// `docs/engine/synthesis.md#decode-settings` gives it.
    pub prefix_content_cap: u64,
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
    /// The steps of one completion search of a projection, as
    /// `docs/engine/synthesis.md#decode-settings` gives it: a search that
    /// spends them is refused with no verdict.
    pub projection_step_cap: u64,
    /// The bindings that the rows of one assignment of one table of a study
    /// request may count, as `docs/engine/synthesis.md#decode-settings` gives
    /// it.
    pub study_row_work_cap: u64,
    /// The rows of a relation that a comparison of successor tables reads row
    /// by row, as `docs/engine/synthesis.md#decode-settings` gives it.
    pub compared_rows_cap: u64,
    /// The states that the walk of `Decoder::candidate_atoms` checks, as
    /// `docs/engine/synthesis.md#decode-settings` gives it.
    pub atom_state_cap: u64,
    /// The work of the search for the order of the tied columns of one table
    /// at one assignment, as `docs/engine/synthesis.md#decode-settings` gives
    /// it.
    pub column_search_work_cap: u64,
    /// The search nodes of the canonical labeling of one label scope, as
    /// `docs/engine/synthesis.md#decode-settings` gives it.
    pub labeling_node_cap: u64,
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
        limits.request=crate::eval::RequestWork::begin_capped(self.request_work_cap,self.byte_caps(),self.effort_cap,self.search_caps());
        limits
    }
    /// The byte budgets of a request and of each assignment in it.
    pub fn byte_caps(&self)->ByteCaps {
        ByteCaps { request: self.request_byte_cap, assignment: self.assignment_byte_cap, candidate: self.candidate_byte_cap }
    }
    /// The caps of the searches that a request carries for the code that has
    /// no settings at hand.
    pub fn search_caps(&self)->SearchCaps {
        SearchCaps { column_search_work: self.column_search_work_cap, labeling_nodes: self.labeling_node_cap }
    }
    /// The default settings with the mutation node cap of the synthesis
    /// decode, which only the mutation draw's search reads.
    pub fn synthesis() -> DecodeSettings {
        DecodeSettings { mutation_node_cap: MUTATION_NODE_CAP, ..DecodeSettings::default() }
    }
    /// The settings of a stage that measures what the gold programs need:
    /// each setting that a gauge of a request measures
    /// ([`crate::eval::Gauge`]) is [`MEASURED_CAP`], and every other setting
    /// is its corpus default. A request under them stops at no cap that a
    /// gold program's request reaches, and no code takes one of these caps as
    /// the size of an allocation or the bound of a loop that runs to the cap,
    /// so a request that needs little uses little.
    ///
    /// A gauge whose cap is no setting keeps that cap: `box_margin` and
    /// `session_bytes`.
    pub fn measurement() -> DecodeSettings {
        DecodeSettings {
            caps: Caps { bindings: MEASURED_CAP, rows: MEASURED_CAP, models: MEASURED_CAP, nodes: MEASURED_CAP, assignments: MEASURED_CAP },
            projection_cap: MEASURED_CAP,
            table_work_cap: MEASURED_CAP,
            request_work_cap: MEASURED_CAP,
            effort_cap: MEASURED_CAP,
            prefix_content_cap: MEASURED_CAP,
            request_byte_cap: MEASURED_CAP,
            assignment_byte_cap: MEASURED_CAP,
            candidate_byte_cap: MEASURED_CAP,
            projection_step_cap: MEASURED_CAP,
            study_row_work_cap: MEASURED_CAP,
            compared_rows_cap: MEASURED_CAP,
            atom_state_cap: MEASURED_CAP,
            column_search_work_cap: MEASURED_CAP,
            labeling_node_cap: MEASURED_CAP,
            ..DecodeSettings::default()
        }
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
            prefix_content_cap: crate::eval::PREFIX_CONTENT_CAP,
            request_byte_cap: REQUEST_BYTES_CAP,
            assignment_byte_cap: ASSIGNMENT_BYTES_CAP,
            candidate_byte_cap: CANDIDATE_BYTES_CAP,
            projection_step_cap: PROJECTION_STEP_CAP,
            study_row_work_cap: STUDY_ROW_WORK_CAP,
            compared_rows_cap: COMPARED_ROWS_CAP,
            atom_state_cap: ATOM_STATE_CAP,
            column_search_work_cap: COLUMN_SEARCH_WORK_CAP,
            labeling_node_cap: LABELING_NODE_CAP,
            spill_resident_bytes: SPILL_RESIDENT_BYTES,
            check_copies: false,
            rule_tests: false,
        }
    }
}
