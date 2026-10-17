//! Rows, relations and their indexes.
//!
//! Implements `work/engine/reader.md`, Relations: "A relation is a set of
//! rows of one arity. A body's relation is held as its parts, as Factorized
//! bodies gives, and each part is stored row by row with a hash set over the
//! rows. An index is a trie over the columns in one order ... built on first
//! use in the order that a clause's variable order asks for, and kept with
//! the relation."
//!
//! A relation is a set: no function here gives its rows in an order that an
//! output may read, as `work/engine/equivariance.md`, Determinism, gives.

#![allow(unused_variables, dead_code)]

use crate::hash::{StableHashMap, StableHashSet};
use crate::terms::TermId;

/// A row: a fixed-arity array of term ids, with no type tag.
///
/// Implements "A row is a fixed-arity array of term ids."
pub type Row = Box<[TermId]>;

/// The position of a column in a relation's rows.
///
/// Implements `work/engine/reader.md`, Relations: "A relation is a set of rows of one arity."
#[derive(Clone, Copy, PartialEq, Eq, Hash, Debug)]
pub struct ColumnIndex(pub u16);

/// A set of rows of one arity, stored row by row with a hash set over the
/// rows.
///
/// Implements `work/engine/reader.md`, Relations: "A relation is a set of rows of one arity."
#[derive(Clone, Debug, Default)]
pub struct RowSet {
    arity: u16,
    rows: StableHashSet<Row>,
}

impl RowSet {
    /// An empty set of rows of `arity` columns.
    ///
    /// Implements `work/engine/reader.md`, Relations: "A relation is a set of rows of one arity."
    pub fn empty(arity: u16) -> Self {
        todo!()
    }

    /// The arity of the rows.
    ///
    /// Implements `work/engine/reader.md`, Relations: "A relation is a set of rows of one arity."
    pub fn arity(&self) -> u16 {
        todo!()
    }

    /// Adds `row`. The row's length is the set's arity.
    ///
    /// Implements `work/engine/reader.md`, Relations: "A relation is a set of rows of one arity."
    pub fn insert(&mut self, row: Row) -> bool {
        todo!()
    }

    /// Whether the set holds `row`.
    ///
    /// Implements `work/engine/reader.md`, Relations: "A relation is a set of rows of one arity."
    pub fn contains(&self, row: &[TermId]) -> bool {
        todo!()
    }

    /// The count of rows.
    ///
    /// Implements `work/engine/reader.md`, Relations: "A relation is a set of rows of one arity."
    pub fn len(&self) -> usize {
        todo!()
    }

    /// Whether the set holds no row.
    ///
    /// Implements `work/engine/reader.md`, Relations: "A relation is a set of rows of one arity."
    pub fn is_empty(&self) -> bool {
        todo!()
    }
}

/// One part of a body's relation: the rows of one connected component of the
/// body's atoms, where two atoms are connected when they share a variable, as
/// `work/engine/synthesis.md`, Factorized bodies, gives.
#[derive(Clone, Debug)]
pub struct Part {
    /// The body's columns that the part holds, in the order of its rows.
    pub columns: Box<[ColumnIndex]>,
    pub rows: RowSet,
}

/// A relation: a set of rows of one arity, held as the product of its parts.
///
/// A fact relation, a lib relation's rows and an evaluated relation of one
/// part each hold one part. The count of rows is the product of the parts'
/// counts, and the relation is empty when any part is empty, as Factorized
/// bodies gives.
///
/// Implements `work/engine/synthesis.md`, Factorized bodies: "the body's rows are the product of its parts' rows".
#[derive(Clone, Debug)]
pub struct Relation {
    pub arity: u16,
    pub parts: Box<[Part]>,
    indexes: std::sync::OnceLock<StableHashMap<ColumnOrder, std::sync::Arc<Index>>>,
}

impl Relation {
    /// The relation that `parts` hold. The parts' columns are disjoint and
    /// cover `0..arity`.
    ///
    /// Implements `work/engine/synthesis.md`, Factorized bodies.
    pub fn from_parts(arity: u16, parts: Box<[Part]>) -> Self {
        todo!()
    }

    /// The count of rows, the product of the parts' counts.
    ///
    /// Implements `work/engine/reader.md`, Relations: "A relation is a set of rows of one arity."
    pub fn len(&self) -> u64 {
        todo!()
    }

    /// Whether the relation holds no row: some part is empty.
    ///
    /// Implements `work/engine/reader.md`, Relations: "A relation is a set of rows of one arity."
    pub fn is_empty(&self) -> bool {
        todo!()
    }

    /// The index of the relation in `order`, built on first use and kept
    /// with the relation.
    ///
    /// Implements `work/engine/reader.md`, Relations: "built on first use ... and kept with the relation".
    pub fn index(&self, order: &ColumnOrder) -> std::sync::Arc<Index> {
        todo!()
    }
}

/// An order of a relation's columns, in which an [`Index`] is built.
///
/// Implements `work/engine/reader.md`, Relations: "built on first use in the order that a clause's variable order asks for".
#[derive(Clone, PartialEq, Eq, Hash, Debug)]
pub struct ColumnOrder(pub Box<[ColumnIndex]>);

/// A trie over a relation's columns in one [`ColumnOrder`], as a hash trie of
/// Free Join (<https://arxiv.org/abs/2301.10841>) is: each level maps a value
/// of its column to the trie of the rows that hold it.
///
/// Implements `work/engine/reader.md`, Relations: "An index is a trie over the columns in one order".
#[derive(Debug, Default)]
pub struct Index {
    children: StableHashMap<TermId, Index>,
}

impl Index {
    /// The subtrie at `value` of the first column, or `None` where no row
    /// holds it.
    ///
    /// Implements `work/engine/reader.md`, Relations: "An index is a trie over the columns in one order".
    pub fn child(&self, value: TermId) -> Option<&Index> {
        todo!()
    }

    /// The count of values at this level.
    ///
    /// Implements `work/engine/reader.md`, Relations: "A relation is a set of rows of one arity."
    pub fn len(&self) -> usize {
        todo!()
    }

    /// Whether no value stands at this level.
    ///
    /// Implements `work/engine/reader.md`, Relations: "A relation is a set of rows of one arity."
    pub fn is_empty(&self) -> bool {
        todo!()
    }
}
