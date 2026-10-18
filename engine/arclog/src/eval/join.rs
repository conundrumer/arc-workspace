//! Generic join over a clause's IR: it binds one variable at a time, in the
//! clause's variable order, by intersecting the atoms that hold it, and
//! counts its work and its rows against the caps per batch of bindings.
//!
//! An algebra relation is evaluated at the point in the order where one of
//! its modes is satisfied, and its outputs are variables that later atoms
//! join on through an index. Where two algebra outputs join on a computed
//! key, the join builds a [`KeyIndex`] on the key over the smaller side.

#![allow(unused_variables, dead_code)]

use std::sync::Arc;

use super::ir::ClauseIr;
use super::plan::VariableOrder;
use super::{Caps, Limits, ReachedBound};
use crate::hash::StableHashMap;
use crate::relations::{Relation, Row};
use crate::session::TaskSession;
use crate::terms::TermId;

/// The counts of one evaluation against its caps and its other bounds: the
/// bindings tried and the rows held. A native construction counts its own
/// bindings and rows through the same counter.
#[derive(Debug)]
pub struct Budget<'a> {
    limits: &'a Limits,
    session: &'a TaskSession,
    work: u64,
    rows: u64,
}

impl<'a> Budget<'a> {
    /// A budget with no work and no rows counted, under `limits` and the
    /// byte bound of `session`.
    pub fn new(limits: &'a Limits, session: &'a TaskSession) -> Self {
        Budget { limits, session, work: 0, rows: 0 }
    }

    /// The caps the budget counts against.
    pub fn caps(&self) -> Caps {
        self.limits.caps
    }

    /// Counts a batch of `bindings` tried, and checks every bound: the
    /// caps, the session's byte bound, the deadline and the cancellation.
    pub fn charge_work(&mut self, bindings: u64) -> Result<(), ReachedBound> {
        todo!()
    }

    /// Counts `rows` more rows held, and checks the row cap.
    pub fn charge_rows(&mut self, rows: u64) -> Result<(), ReachedBound> {
        todo!()
    }
}

/// What each node of a clause reads, by the node's index in
/// [`ClauseIr::nodes`].
#[derive(Clone, Debug)]
pub struct JoinInputs(pub Box<[NodeInput]>);

/// What one node of a clause reads.
#[derive(Clone, Debug)]
pub enum NodeInput {
    /// No relation with rows: a comparison's, or an algebra relation's atom.
    Unread,
    /// The relation of an atom.
    Relation(Arc<Relation>),
    /// The inputs of the node's own clauses: a filter's body, an `IF`'s
    /// test, then and else, or an `OR`'s branches, in the node's order.
    Clauses(Box<[JoinInputs]>),
}

/// The relation of `clause`: each binding of its variables that every node
/// passes, held as its parts, one per connected set of its variables, by
/// generic join in `order`.
pub fn join(
    clause: &ClauseIr,
    order: &VariableOrder,
    inputs: &JoinInputs,
    registry: &crate::registry::Registry,
    budget: &mut Budget<'_>,
) -> Result<Relation, ReachedBound> {
    todo!()
}

/// A hash index on a key computed by an algebra relation: each key's rows
/// of one side of the join.
#[derive(Debug, Default)]
pub struct KeyIndex {
    rows: StableHashMap<Box<[TermId]>, Vec<Row>>,
}

impl KeyIndex {
    /// The index of `rows` on the key that `key` computes from each row.
    pub fn build(rows: impl Iterator<Item = Row>, key: impl Fn(&[TermId]) -> Box<[TermId]>) -> Self {
        todo!()
    }

    /// The rows whose key is `key`.
    pub fn get(&self, key: &[TermId]) -> &[Row] {
        todo!()
    }
}
