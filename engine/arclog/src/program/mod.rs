//! Programs as values: the node kinds of an arclog file and of an arcdata
//! file, each an immutable value that holds its canonical hash. The reader,
//! the decoder and any search procedure build programs through these values
//! and their edits, and evaluation takes a program value, not a file.
//!
//! This module holds the node wrapper, [`Node`], and its canonical hash. Its
//! submodules hold the rest: the names a file writes, the nodes of an
//! arclog file and the nodes of an arcdata file, each re-exported here, and
//! the canonical form, the edits and the paths of a node.
//!
//! A key of canonical parts, such as a cache key that holds canonical forms,
//! is equal to another where each of its parts is, so two keys whose
//! hashes collide stay two keys.
//!
//! A node holds its lists in source order. Its canonical hash leaves out
//! the order of the atoms of a body and of the branches of an `OR`, and
//! keeps the order of every other list, such as a parameter's columns, a
//! row's values or an output's path. A node holds no name of a label and no place in a file:
//! those stand beside it, in a [`crate::layout::Layout`]. Two exceptions
//! hold a name, since a read names a column by it, as
//! `docs/arclog/arclog.md#sites` gives: the name of a column that a label
//! gives a relation the program declares, [`RelationColumn`], and the name
//! of a [`SiteArg::NamedLabel`], the field it reads. The resolved content
//! writes the position of each. A label is a [`LabelId`] local to its scope,
//! as [`LabelId`] gives, so a renaming of label ids gives an equal value,
//! and a renaming of the written name of a `NamedLabel`'s label does not.
//!
//! The node kinds follow the forms of `docs/arclog/arclog.md` and
//! `docs/arclog/arcdata.md`. The programs-as-values stage writes the bodies
//! of this module and of its submodules.

#![allow(unused_variables, dead_code)]

mod arcdata_nodes;
mod arclog_nodes;
pub mod canonical;
pub mod edit;
mod names;
pub mod path;
pub mod static_prune;
pub(crate) mod zero_columns;

pub use arcdata_nodes::*;
pub use arclog_nodes::*;
pub use names::*;

use std::sync::{Arc, OnceLock};

use crate::hash::StableHash;

/// A node value and the hash of its canonical form.
///
/// Two nodes whose hashes match are compared by canonical form. Cloning a
/// `Node` shares the value and its hash. The hash is computed on its first
/// use, so that a reader or a decode that builds a tree pays for no hash it
/// does not read.
///
/// A node's equality is that of its canonical form, in which each name it
/// reads stands as the file writes it. The equality of resolved content,
/// whatever file or decode it came from, is that of
/// [`crate::resolver::ResolvedContent`].
#[derive(Debug)]
pub struct Node<T> {
    shared: Arc<Shared<T>>,
}

#[derive(Debug)]
struct Shared<T> {
    value: T,
    /// The hash of the value's canonical form, and whether its search
    /// reached [`canonical::SEARCH_NODE_CAP`], set on first use.
    canonical_hash: OnceLock<((StableHash, bool), crate::eval::NoteId)>,
    /// What the canonical form of the value gives where the value is a
    /// form, [`canonical::FormCache`], made on its first use, so that a
    /// node of another kind holds none.
    cache: OnceLock<Box<canonical::FormCache>>,
}

impl<T> Clone for Node<T> {
    fn clone(&self) -> Self {
        Node { shared: Arc::clone(&self.shared) }
    }
}

impl<T: canonical::Canonical> Node<T> {
    /// The node of `value`, which is immutable.
    pub fn new(value: T) -> Self {
        Node { shared: Arc::new(Shared { value, canonical_hash: OnceLock::new(), cache: OnceLock::new() }) }
    }

    /// Whether the search for the value's canonical form reached
    /// [`canonical::SEARCH_NODE_CAP`], which is an alert on the node.
    pub fn reached_search_cap(&self) -> bool {
        self.computed().1
    }

    /// The hash of the value's canonical form, as [`canonical`] gives it.
    pub fn canonical_hash(&self) -> StableHash {
        self.computed().0
    }

    fn computed(&self) -> (StableHash, bool) {
        *crate::eval::once_noted(&self.shared.canonical_hash, || {
            let (form, reached) = canonical::form_of(&self.shared.value);
            (form.hash, reached)
        })
    }
}

impl<T> Node<T> {
    /// The value.
    pub fn value(&self) -> &T {
        &self.shared.value
    }
}

impl<T: canonical::Canonical> PartialEq for Node<T> {
    /// Equality of canonical forms: equal hashes, then equal canonical forms.
    fn eq(&self, other: &Self) -> bool {
        Arc::ptr_eq(&self.shared, &other.shared)
            || (self.canonical_hash() == other.canonical_hash() && self.value().canonical_eq(other.value()))
    }
}

impl<T: canonical::Canonical> Eq for Node<T> {}
