//! Edits of a program value. An edit adds, removes or replaces an atom or a
//! site; it gives a new value and leaves the old one. A partial atom, a
//! relation with the sites given so far, is a well-formed atom whose other
//! columns are projected away.

#![allow(unused_variables, dead_code)]

use super::path::NodePath;
use super::{Atom, Conjunct, Node, Program, Site};

/// An edit of a program, at the node its path names. Each node the edit
/// changes takes the columns of its new body, as [`Node::apply`] gives.
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
    /// Adds `site` to the node at `node`, at `index` of its sites in source
    /// order: an atom, a negated atom, a `RIGID_DET` part, an input, whose
    /// head takes it, or a site that reads a record, whose fields take it.
    AddSite {
        node: NodePath,
        index: u32,
        site: Site,
    },
    /// Inserts `part` into the `RIGID_DET` form at `form`, at `index` of its
    /// parts in source order.
    AddPart {
        form: NodePath,
        index: u32,
        part: Node<Atom>,
    },
    /// Removes the part at `at`.
    RemovePart { at: NodePath },
    /// Replaces the part at `at` with `part`.
    ReplacePart { at: NodePath, part: Node<Atom> },
    /// Removes the site at `at`, of any node that `AddSite` names.
    RemoveSite { at: NodePath },
    /// Replaces the site at `at` with `site`.
    ReplaceSite { at: NodePath, site: Site },
}

/// A path of an edit that names no node of the edit's kind.
#[derive(Clone, Debug)]
pub struct EditPathError {
    pub path: NodePath,
}

impl Node<Program> {
    /// The program that `edit` gives. `self` is left as it was, and the new
    /// value shares every node the edit does not change. The paths of `edit`
    /// name nodes as [`super::path::node_at`] walks them.
    ///
    /// Each node the edit changes, a clause, a key body, a `CHOOSE` form or
    /// a `DEMO_RULE` form, takes the columns of its new body: the labels the
    /// body keeps, in order of first appearance. A column whose label the
    /// edit removes is dropped. A column whose label the node keeps keeps its
    /// written name, and each other column is named by its slot, its position
    /// among the columns. The edit gives no diagnostic for a read elsewhere
    /// of a dropped column, which the resolver reports.
    pub fn apply(&self, edit: &Edit) -> Result<Node<Program>, EditPathError> {
        todo!()
    }
}

impl Node<Atom> {
    /// The atom with `site` added. Added to a positive atom, a site gives a
    /// subset of its rows.
    pub fn with_site(&self, site: Site) -> Node<Atom> {
        todo!()
    }
}
