//! The trace of a decode and of a run, as `docs/engine/synthesis.md#traces`
//! gives it: an append-only list of records, one per step, in the order of
//! the steps. [`Trace`] holds the records over a persistent spine, so a forked
//! decode shares its parent's records. [`render`] holds the trace form,
//! [`stop_shares`] the report of the stops, and [`label_names`] the naming of
//! the labels that the forms give. The evaluator and the decoder write
//! records, and read none.

pub mod label_names;
pub mod render;
pub mod stop_shares;

use std::sync::Arc;

use crate::eval::ReachedBound;
use crate::stream::{Emitter, Token};
use crate::terms::Example;
use crate::types::GraphRelation;

/// An append-only list of records over a persistent spine. A clone shares
/// every record, and a record changed in one clone is changed in no other.
#[derive(Debug)]
pub struct Trace<R> {
    tail: Option<Arc<Link<R>>>,
}

#[derive(Debug)]
struct Link<R> {
    record: Arc<R>,
    parent: Option<Arc<Link<R>>>,
    len: usize,
}

impl<R> Clone for Trace<R> {
    fn clone(&self) -> Self {
        Trace { tail: self.tail.clone() }
    }
}

impl<R> Default for Trace<R> {
    fn default() -> Self {
        Trace { tail: None }
    }
}

impl<R> Trace<R> {
    pub fn len(&self) -> usize {
        self.tail.as_ref().map_or(0, |link| link.len)
    }

    pub fn is_empty(&self) -> bool {
        self.tail.is_none()
    }

    /// Appends `record` after the last record.
    pub fn push(&mut self, record: R) {
        self.push_shared(Arc::new(record));
    }

    fn push_shared(&mut self, record: Arc<R>) {
        let len = self.len() + 1;
        self.tail = Some(Arc::new(Link { record, parent: self.tail.take(), len }));
    }

    /// The record at `index`, counted from the first step.
    pub fn get(&self, index: usize) -> Option<&R> {
        let mut link = self.tail.as_deref()?;
        if index >= link.len {
            return None;
        }
        while link.len - 1 > index {
            link = link.parent.as_deref().expect("a link below the tail has a parent");
        }
        Some(&link.record)
    }

    /// The records in the order of the steps.
    pub fn records(&self) -> Vec<&R> {
        let mut records = Vec::with_capacity(self.len());
        let mut link = self.tail.as_deref();
        while let Some(at) = link {
            records.push(&*at.record);
            link = at.parent.as_deref();
        }
        records.reverse();
        records
    }
}

impl<R: Clone> Trace<R> {
    /// Changes the record at `index` by `change`, as a copy: the records
    /// from `index` on are new links, and every clone of this trace keeps
    /// its own record. Gives `false` where there is no such record.
    pub fn update(&mut self, index: usize, change: impl FnOnce(&mut R)) -> bool {
        if index >= self.len() {
            return false;
        }
        let mut above = Vec::new();
        while self.len() > index + 1 {
            above.push(self.pop());
        }
        let mut record = self.pop();
        change(Arc::make_mut(&mut record));
        self.push_shared(record);
        while let Some(record) = above.pop() {
            self.push_shared(record);
        }
        true
    }

    fn pop(&mut self) -> Arc<R> {
        let link = self.tail.take().expect("a trace with a record");
        self.tail = link.parent.clone();
        Arc::clone(&link.record)
    }
}

/// The bound a step reached: a cap or a cancellation.
#[derive(Clone, Copy, PartialEq, Eq, Hash, PartialOrd, Ord, Debug)]
pub enum Stop {
    Bindings,
    Rows,
    Models,
    Nodes,
    Assignments,
    TableWork,
    Margin,
    RequestWork,
    RequestBytes,
    AssignmentBytes,
    Cancelled,
    NoValues,
}

impl From<ReachedBound> for Stop {
    fn from(bound: ReachedBound) -> Stop {
        match bound {
            ReachedBound::Bindings { .. } => Stop::Bindings,
            ReachedBound::Rows { .. } => Stop::Rows,
            ReachedBound::Models { .. } => Stop::Models,
            ReachedBound::Nodes { .. } => Stop::Nodes,
            ReachedBound::Assignments { .. } => Stop::Assignments,
            ReachedBound::TableWork { .. } => Stop::TableWork,
            ReachedBound::Margin(_) => Stop::Margin,
            ReachedBound::RequestWork { .. } => Stop::RequestWork,
            ReachedBound::RequestBytes { .. } => Stop::RequestBytes,
            ReachedBound::AssignmentBytes { .. } => Stop::AssignmentBytes,
            ReachedBound::Cancelled => Stop::Cancelled,
            ReachedBound::NoValues => Stop::NoValues,
        }
    }
}

/// The language model's top-k tokens at a decision, each with its
/// probability, in the order the caller gives them.
#[derive(Clone, PartialEq, Debug, Default)]
pub struct TopK(pub Vec<(Token, f32)>);

/// What the test of an `OUT` form's relation, or of a `RULE` clause's, found,
/// as [`crate::decode::Consistency`] gives it.
#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub enum Verdict {
    Consistent { assignments: usize },
    NotConsistent,
    SeveralValues,
    Fault,
    Stopped,
}

/// The rows of the sub-body of the clause in progress on one example, or of
/// a task-wide clause, that the caller asked for.
#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub struct RowsSeen {
    pub example: Option<Example>,
    /// `None` where the body is undefined or stopped.
    pub count: Option<u64>,
}

/// One step of a decode: one accepted token.
#[derive(Clone, PartialEq, Debug)]
pub struct DecodeRecord {
    pub token: Token,
    pub emitter: Emitter,
    /// The rows the caller asked for after this step.
    pub rows: Vec<RowsSeen>,
    /// The counts the caller asked for after this step, one per example.
    pub counts: Option<Box<[Option<u64>]>>,
    /// The consistency test of the `OUT` form, at its end.
    pub consistency: Option<Verdict>,
    /// The test of the relation of a `RULE` clause, at its end, where the
    /// decode settings run the rule tests.
    pub rule_test: Option<Verdict>,
    /// The bound the prefix reached at this step.
    pub stop: Option<Stop>,
    /// The output sets of the tests at this step that ended at the model
    /// cap with the grids found so far, as
    /// `docs/engine/cases.md#enumeration-and-its-stops` gives.
    pub capped_sets: u64,
    pub top_k: Option<TopK>,
}

impl DecodeRecord {
    pub fn new(token: Token, emitter: Emitter) -> DecodeRecord {
        DecodeRecord { token, emitter, rows: Vec::new(), counts: None, consistency: None, rule_test: None, stop: None, capped_sets: 0, top_k: None }
    }
}

/// The trace of a decode.
pub type DecodeTrace = Trace<DecodeRecord>;

/// One step of a run: the evaluation of one relation of one case on one
/// input.
#[derive(Clone, PartialEq, Debug)]
pub struct RunRecord {
    pub relation: GraphRelation,
    pub example: Option<Example>,
    /// The rows of the relation, `None` where it is undefined or stopped.
    pub rows: Option<u64>,
    /// The models of the case that this record counts: 1 for the evaluation
    /// at one model, and, for the record of an enumeration of models, the
    /// models it visited.
    pub models: u64,
    /// The `DET` relations read while this relation was evaluated, those of
    /// the relations it reads included.
    pub values_determined: u64,
    pub stop: Option<Stop>,
}

/// The trace of a run.
pub type RunTrace = Trace<RunRecord>;
