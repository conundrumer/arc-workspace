//! Edits of a program value.
//!
//! Implements `work/engine/reader.md`, Programs as values: "An edit adds,
//! removes or replaces an atom or a site. It gives a new value and leaves the
//! old one." and the partial atom: "A partial atom, a relation with the sites
//! given so far, is a well-formed atom whose other columns are projected
//! away."

#![allow(unused_variables, dead_code)]

use super::path::NodePath;
use super::{Atom, Conjunct, Node, Program, Site};

/// An edit of a program, at the node its path names.
///
/// Implements `work/engine/reader.md`, Programs as values: "An edit adds, removes or replaces an atom or a site."
#[derive(Clone, Debug)]
pub enum Edit {
    /// Inserts `conjunct` into the body at `body`, at `index` of its source
    /// order.
    AddConjunct {
        body: NodePath,
        index: u32,
        conjunct: Conjunct,
    },
    /// Removes the conjunct at `at`.
    RemoveConjunct { at: NodePath },
    /// Replaces the conjunct at `at` with `conjunct`.
    ReplaceConjunct { at: NodePath, conjunct: Conjunct },
    /// Adds `site` to the atom at `atom`, at `index` of its source order.
    AddSite {
        atom: NodePath,
        index: u32,
        site: Site,
    },
    /// Removes the site at `at`.
    RemoveSite { at: NodePath },
    /// Replaces the site at `at` with `site`.
    ReplaceSite { at: NodePath, site: Site },
}

/// A path of an edit that names no node of the edit's kind.
///
/// Implements `work/engine/reader.md`, Programs as values: "An edit adds, removes or replaces an atom or a site."
#[derive(Clone, Debug)]
pub struct EditPathError {
    pub path: NodePath,
}

impl Program {
    /// The program that `edit` gives. `self` is left as it was, and the new
    /// value shares every node the edit does not change.
    ///
    /// Implements `work/engine/reader.md`, Programs as values: "An edit adds, removes or replaces an atom or a site."
    pub fn apply(&self, edit: &Edit) -> Result<Program, EditPathError> {
        todo!()
    }
}

impl Node<Atom> {
    /// The atom with `site` added: a subset of the atom's rows, as "A site
    /// added to a positive atom gives a subset of its rows" gives.
    ///
    /// Implements `work/engine/reader.md`, Programs as values: "A site added to a positive atom gives a subset of its rows."
    pub fn with_site(&self, site: Site) -> Node<Atom> {
        todo!()
    }
}
