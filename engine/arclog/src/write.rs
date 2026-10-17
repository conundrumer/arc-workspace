//! The writer of arclog and arcdata files.
//!
//! Implements `work/engine/reader.md`, Solvers: "The writer writes a `Solver`
//! tree as the two files." and "So reading a file of `gen/` and writing it
//! again gives the same bytes."
//!
//! The reader and writer stage writes the bodies.

#![allow(unused_variables, dead_code)]

use crate::program::{Node, Program};
use crate::registry::Registry;
use crate::solver::Solver;
use crate::terms::InternTable;

/// The text of a solver's two files.
///
/// Implements `work/engine/reader.md`, Solvers: "The writer writes a `Solver` tree as the two files."
#[derive(Clone, PartialEq, Eq, Debug)]
pub struct SolverText {
    pub arclog: String,
    pub arcdata: String,
}

/// The two files of `solver`, laid out as the converter lays out each form,
/// with the comments, strings and label names of its layout. `registry`
/// gives the name of each orientation constant.
///
/// Implements `work/engine/reader.md`, Solvers: "The writer writes a `Solver` tree as the two files."
pub fn write_solver(solver: &Solver, registry: &Registry) -> SolverText {
    todo!()
}

/// A synthesized program as an arclog file, in the program form and the
/// s-expression layout.
///
/// Implements `work/engine/reader.md`: "with names in place of token ids: a label takes the name of
/// the column or field of its first site, PascalCase, with a digit suffix
/// where the clause already has that name, and a relation slot is written by
/// its index".
pub fn write_synthesized(program: &Node<Program>, registry: &Registry) -> String {
    todo!()
}

/// The numbers a writer gives the Idents it writes, private to the crate's
/// writers, since a number is an order of encodings.
///
/// Implements `work/engine/reader.md`, Terms: "A writer ... numbers the
/// Idents it writes by the order of their contents' encodings, from the
/// inside out" and "A value read from a file ... is written as it was read,
/// and the writer numbers the other Idents of that type in the file after the
/// largest such value".
#[derive(Clone, Debug, Default)]
pub struct IdentNumbering {
    numbers: crate::hash::StableHashMap<crate::terms::Ident, u32>,
}

impl IdentNumbering {
    /// The numbering of `idents`, the Idents one file writes.
    ///
    /// Implements `work/engine/reader.md`, Terms: "A writer ... numbers the Idents it writes by the order of their contents' encodings".
    pub fn new(idents: &[crate::terms::Ident], table: &InternTable) -> Self {
        todo!()
    }

    /// The number written for `ident`.
    ///
    /// Implements `work/engine/reader.md`, Terms: "A writer ... numbers the Idents it writes by the order of their contents' encodings".
    pub(crate) fn number(&self, ident: crate::terms::Ident) -> u32 {
        todo!()
    }
}
