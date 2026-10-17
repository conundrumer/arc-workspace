//! The reader of arclog and arcdata files.
//!
//! Implements `work/engine/reader.md`, Solvers: the reader reads a solver's
//! `.arclog` and `.arcdata` files into one [`Solver`] tree, and the arcdata
//! file is "s-expressions, read by the arclog reader, with a closed set of
//! head symbols", as `docs/arcdata.md` gives. The registry file under
//! `engine/lib/` is read by the same s-expression reader, as
//! [`crate::registry`] gives.
//!
//! The reader and writer stage writes the bodies.

#![allow(unused_variables, dead_code)]

use crate::diagnostic::Diagnostic;
use crate::layout::{Layout, SolverFile, SourcePlace};
use crate::program::{Arcdata, Program};
use crate::solver::Solver;

/// An s-expression as the fixed reader gives it, before node kinds.
///
/// Implements `docs/arcdata.md`: "The file is s-expressions, read by the arclog reader".
#[derive(Clone, PartialEq, Eq, Debug)]
pub enum SExpr {
    /// A symbol: a keyword, a name, a label with its mark, a number.
    Symbol { text: Box<str>, place: SourcePlace },
    /// A quoted string, its content unescaped.
    String { text: Box<str>, place: SourcePlace },
    List { items: Box<[SExpr]>, place: SourcePlace },
}

/// The s-expressions of `text` and its comments.
///
/// Fails with a diagnostic of the grammar at each unbalanced list or
/// unterminated string.
///
/// Implements `docs/arcdata.md`: "The file is s-expressions, read by the arclog reader".
pub fn read_sexprs(text: &str, file: SolverFile) -> Result<(Vec<SExpr>, Vec<crate::layout::Comment>), Vec<Diagnostic>> {
    todo!()
}

/// The program of an arclog file and its layout.
///
/// Implements `work/engine/reader.md`, Solvers: "The reader reads a solver's `.arclog` and `.arcdata` files into one `Solver` tree".
pub fn read_arclog(text: &str) -> Result<(Program, Layout), Vec<Diagnostic>> {
    todo!()
}

/// The records of an arcdata file, with the layout of the arclog file it
/// stands beside extended by its own.
///
/// Implements `docs/arcdata.md` and `work/engine/reader.md`, Solvers.
pub fn read_arcdata(text: &str, layout: Layout) -> Result<(Arcdata, Layout), Vec<Diagnostic>> {
    todo!()
}

/// The solver of `task_id` from the text of its two files.
///
/// Implements `work/engine/reader.md`, Solvers: "The reader reads a solver's `.arclog` and `.arcdata` files into one `Solver` tree".
pub fn read_solver(task_id: &str, arclog: &str, arcdata: &str) -> Result<Solver, Vec<Diagnostic>> {
    todo!()
}
