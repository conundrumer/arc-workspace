//! The canonical form of a node and its hash.
//!
//! A body's canonical form is the same under a reorder of its atoms, a
//! reorder of the branches of an `OR`, and a renaming of its labels. The
//! labeling comes from individualization–refinement: color refinement with
//! the column paths as edge labels, then the first largest cell that is not
//! a singleton, with a cap of [`SEARCH_NODE_CAP`] search nodes. A body that
//! reaches the cap takes the least labeling the search has found.
//!
//! A node's canonical hash names each relation it reads as the file writes
//! it, [`AsWritten`]. The resolved content of a node in one case program, in
//! which each derived relation stands for its own content, is
//! [`crate::resolver::ResolvedProgram::content`], which writes the same
//! canonical form through a [`NameWriter`] of the resolver.

#![allow(unused_variables, dead_code)]

use crate::hash::StableHash;

/// The provisional cap on the search nodes of individualization–refinement.
///
/// The cap guards synthesized bodies, whose symmetry the corpus does not
/// show. The corpus's search reaches at most 13 nodes.
pub const SEARCH_NODE_CAP: u32 = 1000;

/// A node kind that has a canonical form.
pub trait Canonical {
    /// Writes the value's canonical form into `out`, with each name the
    /// value reads written by `names`.
    ///
    /// The bytes written are equal for two values exactly where their
    /// canonical forms are equal.
    fn write_canonical(&self, out: &mut CanonicalWriter, search: &mut SearchBudget, names: &dyn NameWriter);

    /// Whether two values have equal canonical forms. Called only where
    /// their canonical hashes match.
    fn canonical_eq(&self, other: &Self) -> bool;
}

/// How a canonical form writes each relation a node reads: as the file
/// writes it, [`AsWritten`], for a node's canonical hash, or, in the
/// resolver, as the resolved content the name stands for, for
/// [`crate::resolver::ResolvedContent`], in which a derived relation's
/// content is its clause.
pub trait NameWriter {
    /// Writes `relation` into `out`.
    fn write_name(&self, relation: &super::RelationRef, out: &mut CanonicalWriter);

    /// Writes a column of `relation` into `out`: a column that a site names,
    /// or that a clause gives the relation it derives. `column` is the
    /// column's path: its name, or, for a site on a field of a record, the
    /// record's column and then the field, as `[key, P]` for `(:P P2)` in
    /// `(:key (:P P2))`. The resolver writes its canonical position, as
    /// [`crate::resolver::ColumnPosition`] gives, so that names do not enter
    /// the resolved content.
    fn write_column(&self, relation: &super::RelationRef, column: &[super::ColumnName], out: &mut CanonicalWriter);
}

/// The writer of a canonical form: it keeps the bytes written, so that two
/// forms whose hashes match are compared by their bytes.
#[derive(Clone, Debug, Default)]
pub struct CanonicalWriter {
    bytes: Vec<u8>,
}

impl CanonicalWriter {
    /// Writes `bytes` to the form.
    pub fn write(&mut self, bytes: &[u8]) {
        todo!()
    }

    /// The form written, with its hash under [`crate::hash::StableHasher`].
    pub fn finish(self) -> CanonicalForm {
        todo!()
    }
}

/// A canonical form, as its bytes and their hash.
#[derive(Clone, PartialEq, Eq, Debug)]
pub struct CanonicalForm {
    pub hash: StableHash,
    pub bytes: std::sync::Arc<[u8]>,
}

/// Each name as the file writes it.
#[derive(Clone, Copy, Debug, Default)]
pub struct AsWritten;

impl NameWriter for AsWritten {
    fn write_name(&self, relation: &super::RelationRef, out: &mut CanonicalWriter) {
        todo!()
    }

    fn write_column(&self, relation: &super::RelationRef, column: &[super::ColumnName], out: &mut CanonicalWriter) {
        todo!()
    }
}

/// The search nodes that individualization–refinement has left, and whether
/// a body reached the cap.
#[derive(Clone, Debug)]
pub struct SearchBudget {
    pub remaining: u32,
    /// Set when a body reached the cap, which is an alert.
    pub reached: bool,
}

impl SearchBudget {
    /// A budget of [`SEARCH_NODE_CAP`] nodes.
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
#[derive(Clone, Debug)]
pub struct CanonicalLabeling {
    pub positions: Box<[(super::LabelId, u32)]>,
    pub reached_cap: bool,
}

/// The canonical labeling of `body`, by individualization–refinement, with
/// the column paths as edge labels as `names` writes them: as written for a
/// node's hash, [`AsWritten`], or as the resolved positions for the
/// resolved content.
pub fn canonical_labeling(body: &super::Body, names: &dyn NameWriter, search: &mut SearchBudget) -> CanonicalLabeling {
    todo!()
}

/// The canonical order of one form: for each list of the form, the source
/// index at each canonical position, and for each label, its canonical
/// position. A result cached by canonical hash is held in canonical order
/// and served to each form of equal content through its own order, so the
/// cases that share a form share its check.
#[derive(Clone, Debug)]
pub struct CanonicalOrder {
    lists: crate::hash::StableHashMap<super::path::NodePath, Box<[u32]>>,
    labels: Box<[(super::LabelId, u32)]>,
}

impl CanonicalOrder {
    /// The canonical order of `form`.
    pub fn of(form: &super::Form, search: &mut SearchBudget) -> Self {
        todo!()
    }

    /// The source path of the node at `canonical`, a path in canonical
    /// order, relative to the form.
    pub fn source_path(&self, canonical: &super::path::NodePath) -> super::path::NodePath {
        todo!()
    }

    /// The canonical path of the node at `source`, a path in source order,
    /// relative to the form.
    pub fn canonical_path(&self, source: &super::path::NodePath) -> super::path::NodePath {
        todo!()
    }

    /// The form's label at canonical `position`.
    pub fn source_label(&self, position: u32) -> super::LabelId {
        todo!()
    }

    /// The canonical position of the form's `label`.
    pub fn canonical_label(&self, label: super::LabelId) -> u32 {
        todo!()
    }
}

/// The hash of the canonical form of `value`.
pub fn canonical_hash<T: Canonical>(value: &T) -> StableHash {
    todo!()
}

/// Declares that each node kind listed has a canonical form, with a body
/// the programs-as-values stage writes. Every kind a [`super::Node`] holds is
/// listed, so that each stage builds nodes of every kind through
/// [`super::Node::new`].
macro_rules! canonical_kinds {
    ($($kind:ident),* $(,)?) => {
        $(
            impl Canonical for super::$kind {
                fn write_canonical(&self, out: &mut CanonicalWriter, search: &mut SearchBudget, names: &dyn NameWriter) {
                    todo!()
                }

                fn canonical_eq(&self, other: &Self) -> bool {
                    todo!()
                }
            }
        )*
    };
}

canonical_kinds!(
    Program, Claim, Clause, Body, Atom, Instance, KeyClause, InstanceInput, Choose, RigidDet, Demonstrated,
    DemoRule, Alts, Alt, Param, Arcdata,
);
