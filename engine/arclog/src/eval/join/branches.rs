//! The rows of the branches of a union that is a clause's whole body, kept
//! across the evaluations of a session.
//!
//! Such a branch is searched alone, at no bound value
//! ([`super::union_rows`]), so its rows depend on the branch's IR and on the
//! rows of the relations its nodes read, and on nothing else of the clause
//! around it. A branch that reads none of the relations that differ between
//! two evaluations has the same rows in both, such as the branch of a rule
//! that reads no `DET` when the walk of the assignments changes only the
//! value of a `DET` that another branch reads.

use std::hash::{Hash, Hasher};
use std::sync::{Arc, Mutex};

use super::{Budget, Counted, JoinInputs, NodeInput};
use crate::eval::ir::ClauseIr;
use crate::eval::ReachedBound;
use crate::hash::{StableHashMap, StableHasher};
use crate::relations::{ColumnIndex, Relation, RowSet};
use crate::session::same_rows;

/// The share of a session's byte bound that the kept rows, and the
/// relations their keys read, may take, as a divisor. The memo is emptied
/// when a new entry would pass it, which changes the speed of an evaluation
/// and no value.
const BYTES_SHARE: usize = 16;

/// The branches of unions whose rows a session has kept, each with the
/// counts of its search.
#[derive(Debug, Default)]
pub struct BranchMemo {
    state: Mutex<State>,
}

#[derive(Debug, Default)]
struct State {
    /// The entries by the hash of their keys, each bucket in the order of
    /// insertion.
    entries: StableHashMap<u64, Vec<Stored>>,
    bytes: usize,
}

#[derive(Debug)]
struct Stored {
    clause: ClauseIr,
    columns: Box<[ColumnIndex]>,
    reads: Box<[Arc<Relation>]>,
    rows: RowSet,
    counted: Counted,
}

/// The relations that the nodes of `inputs` read, at any depth, in the order
/// of the nodes.
fn reads(inputs: &JoinInputs, found: &mut Vec<Arc<Relation>>) {
    for input in inputs.0.iter() {
        match input {
            NodeInput::Unread => {}
            NodeInput::Relation(relation) => found.push(relation.clone()),
            NodeInput::Clauses(bodies) => bodies.iter().for_each(|body| reads(body, found)),
        }
    }
}

fn key_hash(clause: &ClauseIr, columns: &[ColumnIndex], reads: &[Arc<Relation>]) -> u64 {
    let mut hasher = StableHasher::new();
    clause.hash(&mut hasher);
    columns.hash(&mut hasher);
    for relation in reads {
        relation.rows_hash().hash(&mut hasher);
    }
    hasher.finish()
}

impl BranchMemo {
    fn lock(&self) -> std::sync::MutexGuard<'_, State> {
        self.state.lock().expect("a branch memo that no panic poisoned")
    }

    fn find(&self, hash: u64, clause: &ClauseIr, columns: &[ColumnIndex], reads: &[Arc<Relation>]) -> Option<(RowSet, Counted)> {
        let state = self.lock();
        let found = state.entries.get(&hash)?.iter().find(|stored| {
            stored.columns[..] == *columns
                && stored.reads.len() == reads.len()
                && stored.clause == *clause
                && stored.reads.iter().zip(reads).all(|(held, read)| same_rows(held, read))
        })?;
        Some((found.rows.clone(), found.counted))
    }

    fn keep(&self, hash: u64, stored: Stored, bytes: usize, bound: usize) {
        let mut state = self.lock();
        if state.bytes.saturating_add(bytes) > bound {
            state.entries.clear();
            state.bytes = 0;
        }
        if bytes > bound {
            return;
        }
        state.bytes += bytes;
        state.entries.entry(hash).or_default().push(stored);
    }
}

/// The rows that `search` gives for `branch`, a branch of a union that is a
/// clause's whole body, over `inputs`, projected onto `columns`, as an
/// evaluation nested in the union ([`Budget::nested`]).
///
/// A search that gave rows is kept with the bindings it charged and the most
/// rows a nested evaluation in it held. Where the memo holds a search of an
/// equal branch over relations of the same rows and the same columns, the
/// rows are the rows that search gave: the search reads nothing else, and its
/// order depends on the rows alone. Such a hit charges the budget what the
/// search charged, as a [`super::SearchMemo`] hit does, so the counts of the
/// evaluation around it and the place where it stops at a cap are those of an
/// evaluation with no memo. A search that stopped is not kept.
pub(super) fn rows(
    budget: &mut Budget<'_>,
    branch: &ClauseIr,
    inputs: &JoinInputs,
    columns: &[ColumnIndex],
    search: impl FnOnce(&mut Budget<'_>) -> Result<RowSet, ReachedBound>,
) -> Result<RowSet, ReachedBound> {
    let session = budget.session;
    let memo = &session.branches;
    let mut read = Vec::new();
    reads(inputs, &mut read);
    let hash = key_hash(branch, columns, &read);
    let held = memo.find(hash, branch, columns, &read);
    if let Some((rows, counted)) = &held {
        // A hit whose charges would pass a cap is no hit: the search runs again, and stops where it stops with no memo.
        if budget.can_replay(counted.bindings) {
            budget.replay_nested(*counted)?;
            return Ok(rows.clone());
        }
    }
    let (rows, counted) = budget.counted(search)?;
    if held.is_some() {
        return Ok(rows);
    }
    let bytes = std::mem::size_of::<Stored>()
        + rows.bytes()
        + read.iter().map(|relation| crate::eval::cache::relation_estimate(relation)).sum::<usize>();
    memo.keep(
        hash,
        Stored { clause: branch.clone(), columns: columns.into(), reads: read.into(), rows: rows.clone(), counted },
        bytes,
        session.bound.bytes / BYTES_SHARE,
    );
    Ok(rows)
}
