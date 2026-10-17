//! The canonical form of a node and its hash.
//!
//! Implements `work/engine/reader.md`, Programs as values: "a body's content
//! is its canonical form under a reorder of its atoms, a reorder of the
//! branches of an `OR`, and a renaming of its labels, which
//! individualization–refinement gives: color refinement with the column paths
//! as edge labels, then the first largest cell that is not a singleton, with a
//! cap of 1000 search nodes." and "A body that reaches the cap takes the least
//! labeling the search has found".
//!
//! A node's canonical form names each relation it reads as the file writes
//! it. The resolved content of a node in one case program, in which each
//! derived relation stands for its own content, is
//! [`crate::resolver::ResolvedProgram::content_hash`].

#![allow(unused_variables, dead_code)]

use crate::hash::{StableHash, StableHasher};

/// The provisional cap on the search nodes of individualization–refinement.
///
/// "The cap is provisional: it guards synthesized bodies, whose symmetry the
/// corpus does not show." The corpus's search reaches at most 13 nodes.
///
/// Implements `work/engine/reader.md`, Programs as values: "a body's content is its canonical form under a reorder of its atoms, a reorder of the branches of an `OR`, and a renaming of its labels".
pub const SEARCH_NODE_CAP: u32 = 1000;

/// A node kind that has a canonical form.
///
/// Implements `work/engine/reader.md`, Programs as values: "a body's content is its canonical form under a reorder of its atoms, a reorder of the branches of an `OR`, and a renaming of its labels".
pub trait Canonical {
    /// Writes the value's canonical form into `hasher`.
    ///
    /// The bytes written are equal for two values exactly where their
    /// canonical forms are equal.
    fn write_canonical(&self, hasher: &mut StableHasher, search: &mut SearchBudget);

    /// Whether two values have equal canonical forms. Called only where
    /// their canonical hashes match.
    fn canonical_eq(&self, other: &Self) -> bool;
}

/// The search nodes that individualization–refinement has left, and whether
/// a body reached the cap.
///
/// Implements `work/engine/reader.md`, How each decision can fail: "the cap reached is an alert".
#[derive(Clone, Debug)]
pub struct SearchBudget {
    pub remaining: u32,
    /// Set when a body reached the cap. The cap reached is an alert, as the
    /// table of Reader and checker's "How each decision can fail" gives.
    pub reached: bool,
}

impl SearchBudget {
    /// A budget of [`SEARCH_NODE_CAP`] nodes.
    ///
    /// Implements `work/engine/reader.md`, Programs as values: "a body's content is its canonical form under a reorder of its atoms, a reorder of the branches of an `OR`, and a renaming of its labels".
    pub fn new() -> Self {
        todo!()
    }
}

impl Default for SearchBudget {
    fn default() -> Self {
        todo!()
    }
}

/// The canonical labeling of one body: for each label of the body, its
/// position in the canonical form.
///
/// Implements `work/engine/reader.md`, Programs as values: "a body's content is its canonical form under a reorder of its atoms, a reorder of the branches of an `OR`, and a renaming of its labels".
#[derive(Clone, Debug)]
pub struct CanonicalLabeling {
    pub positions: Box<[(super::LabelId, u32)]>,
    pub reached_cap: bool,
}

/// The canonical labeling of `body`, by individualization–refinement.
///
/// Implements `work/engine/reader.md`, Programs as values: "a body's content is its canonical form under a reorder of its atoms, a reorder of the branches of an `OR`, and a renaming of its labels".
pub fn canonical_labeling(body: &super::Body, search: &mut SearchBudget) -> CanonicalLabeling {
    todo!()
}

/// The hash of the canonical form of `value`.
///
/// Implements `work/engine/reader.md`, Programs as values: "a body's content is its canonical form under a reorder of its atoms, a reorder of the branches of an `OR`, and a renaming of its labels".
pub fn canonical_hash<T: Canonical>(value: &T) -> StableHash {
    todo!()
}

impl Canonical for super::Body {
    fn write_canonical(&self, hasher: &mut StableHasher, search: &mut SearchBudget) {
        todo!()
    }

    fn canonical_eq(&self, other: &Self) -> bool {
        todo!()
    }
}
