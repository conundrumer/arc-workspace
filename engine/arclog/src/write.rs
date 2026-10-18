//! The writer of arclog and arcdata files. Reading a file of the corpus and
//! writing it again gives the same bytes.
//!
//! [`write_solver`] and [`write_synthesized`] stay `todo!()` for later
//! stages.

#![allow(unused_variables, dead_code)]

mod arcdata;
mod arclog;

pub(crate) use arclog::relation_ref;

use crate::layout::Layout;
use crate::program::{Arcdata, Node, Program};
use crate::registry::Registry;
use crate::solver::Solver;
use crate::terms::InternTable;

/// The text of a solver's two files.
#[derive(Clone, PartialEq, Eq, Debug)]
pub struct SolverText {
    pub arclog: String,
    pub arcdata: String,
}

/// The text of the arclog file that `program` and `layout`, as
/// [`crate::read::read_arclog`] reads them, give: each token at the place
/// its node's layout gives, each comment of the layout, and each site the
/// layout elides as its bare label. A token whose node has no layout stands
/// one space after the token before it. Each name and column of `program`
/// is written as a file writes it, and each label is named in the layout of
/// its scope; a slot of a decode is a fault.
pub fn write_arclog(program: &Node<Program>, layout: &Layout) -> String {
    arclog::write(program.value(), layout)
}

/// The text of the arcdata file that `arcdata` and `layout`, as
/// [`crate::read::read_arcdata`] reads them, give, as [`write_arclog`]
/// writes the arclog file: each token at the place its node's layout gives,
/// and each comment of the layout whose place is in
/// [`crate::layout::SourceFile::Arcdata`]. A value read from the file is
/// written as the file wrote it.
pub fn write_arcdata(arcdata: &Node<Arcdata>, layout: &Layout) -> String {
    arcdata::write(arcdata.value(), layout)
}

/// The two files of `solver`, laid out as the converter lays out each form,
/// with the comments, strings and label names of its layout.
pub fn write_solver(solver: &Solver) -> SolverText {
    todo!()
}

/// A synthesized program as an arclog file, in the program form and the
/// s-expression layout, with names in place of token ids, and a relation
/// slot written by its index.
///
/// A label that a [`crate::program::SiteArg::NamedLabel`] holds takes that
/// argument's `name`, so the file reads that field at that site. Each name
/// so taken is reserved in its scope, as [`crate::program::LabelId`] gives
/// a scope, before any other label is named. Each other label takes the
/// name of the column or field of its first site, PascalCase, with the
/// least digit suffix that gives a name no other label of its scope holds
/// or has reserved: in `(:a *A) (:key *A2)`, where
/// `A2` is the label of `NamedLabel { name: A }`, `A2` is written `A` and the
/// label at `(:a ...)` is written `A1`.
///
/// Two labels take one name only where [`Node::apply`](crate::program::Node::apply)
/// gives them one, so the file reads back to the same labels:
/// `(OR ((r (:key *X))) ((s (:key *X))))` is written with `X` at each site,
/// and reads back as two labels.
pub fn write_synthesized(program: &Node<Program>, registry: &Registry) -> String {
    todo!()
}

/// The numbers a writer gives the Idents it writes, private to the crate's
/// writers, since a number is an order of encodings.
///
/// The Idents are numbered by the order of their contents' encodings, which
/// `TermId::encoding` gives, from the inside out. A value read from a file
/// is written as it was read, and the other Idents of that type in the file
/// are numbered after the largest such value.
#[derive(Clone, Debug, Default)]
pub struct IdentNumbering {
    numbers: crate::hash::StableHashMap<crate::terms::Ident, u32>,
}

impl IdentNumbering {
    /// The numbering of `idents`, the Idents one file writes.
    pub fn new(idents: &[crate::terms::Ident], table: &InternTable) -> Self {
        todo!()
    }

    /// The number written for `ident`.
    pub(crate) fn number(&self, ident: crate::terms::Ident) -> u32 {
        todo!()
    }
}
