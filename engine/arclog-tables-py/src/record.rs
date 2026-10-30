//! What the replay of one stream records for `corpus_tables` and
//! `stream_tables`: the tables of each step, the declared rows that the
//! constructions' outputs broke, and the last consistency a step gave.

use arclog::decode::replay::Stepped;
use arclog::decode::Decoder;
use arclog::eval::copies::CopyViolation;
use arclog_bindings::PyConsistencyKind;
use arclog_tables::tables::{record_step, Points, Table};

/// The consistency kind that the last step of a stream gave, with the index
/// of its token.
#[derive(Clone, Copy)]
pub(crate) struct EndedAt {
    pub(crate) token: usize,
    pub(crate) kind: PyConsistencyKind,
}

impl EndedAt {
    /// The line `<task> <case>: ended <kind> at token <index>`.
    pub(crate) fn line(&self, task: &str, case: &str) -> String {
        format!("{task} {case}: ended {} at token {}", self.kind.name(), self.token)
    }
}

/// What the replay of one stream of `stream_tables` records: the tables of
/// each step, the violations the steps found, and the last consistency a step gave.
#[derive(Clone, Default)]
pub(crate) struct StreamRecord {
    pub(crate) tables: Vec<(usize, Table)>,
    /// Stable native namespace/accounting only. A packing callback binds its
    /// own current operation; no historical query deadline is cached here.
    pub(crate) session:Option<arclog::session::TaskSession>,
    /// The declared rows that the constructions' outputs broke, where the replay checks them.
    pub(crate) copies: Vec<CopyViolation>,
    pub(crate) ended: Option<EndedAt>,
}

impl StreamRecord {
    /// Records the tables of a step and, where the step judged, its consistency.
    pub(crate) fn step(&mut self, decoder: &Decoder<'_>, stepped: Stepped<'_>, points: Points) {
        if self.session.is_none() {self.session=Some(decoder.evaluation_inputs().1.clone());}
        record_step(&mut self.tables, decoder, stepped.index, points);
        for violation in decoder.take_copy_violations() {
            if !self.copies.contains(&violation) {
                self.copies.push(violation);
            }
        }
        if let Some(consistency) = &stepped.consistency {
            self.ended = Some(EndedAt { token: stepped.index, kind: PyConsistencyKind::of(consistency) });
        }
    }
}
