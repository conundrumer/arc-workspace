//! The writer of arclog and arcdata files. Reading a file of the corpus and
//! writing it again gives the same bytes.
//!
//! The reader and writer stage writes the bodies.

#![allow(unused_variables, dead_code)]

use crate::program::{Node, Program};
use crate::registry::Registry;
use crate::solver::Solver;
use crate::terms::InternTable;

/// The text of a solver's two files.
#[derive(Clone, PartialEq, Eq, Debug)]
pub struct SolverText {
    pub arclog: String,
    pub arcdata: String,
}

/// The two files of `solver`, laid out as the converter lays out each form,
/// with the comments, strings and label names of its layout. `registry`
/// gives the name of each orientation constant.
pub fn write_solver(solver: &Solver, registry: &Registry) -> SolverText {
    todo!()
}

/// A synthesized program as an arclog file, in the program form and the
/// s-expression layout, with names in place of token ids: a label takes the
/// name of the column or field of its first site, PascalCase, with a digit
/// suffix where the clause already has that name, and a relation slot is
/// written by its index.
pub fn write_synthesized(program: &Node<Program>, registry: &Registry) -> String {
    todo!()
}

/// The numbers a writer gives the Idents it writes, private to the crate's
/// writers, since a number is an order of encodings.
///
/// The Idents are numbered by the order of their contents' encodings, from
/// the inside out. A value read from a file is written as it was read, and
/// the other Idents of that type in the file are numbered after the largest
/// such value.
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
