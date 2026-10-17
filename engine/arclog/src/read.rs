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

use std::sync::Arc;

use crate::diagnostic::{Diagnostic, WithDiagnostics};
use crate::layout::{Layout, SourceFile, SourcePlace};
use crate::program::{Arcdata, Node, Program};
use crate::registry::Registry;
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
pub fn read_sexprs(text: &str, file: SourceFile) -> Result<(Vec<SExpr>, Vec<crate::layout::Comment>), Vec<Diagnostic>> {
    todo!()
}

/// The names of the labels of a node that one s-expression gives, in the
/// order they first stand, for a reader of a form that names labels outside
/// the node, as the registry's `(macro ...)` and `(output ...)` forms do.
///
/// Implements `work/engine/reader.md`, Checker: "a proposer written in arclog ... has its clause's labels as its columns".
pub type LabelNames = Box<[(Box<str>, crate::program::LabelId)]>;

/// The body that the s-expressions `exprs` write, as the atoms of a clause,
/// and the names of its labels: the one reader of a body that stands inside
/// a form of the registry file.
///
/// Implements `work/engine/reader.md`, Checker: "A lib name that lib-spec.md defines from other lib names can be expanded into its definition", and the registry file's format, which [`crate::registry`] gives.
pub fn read_body(exprs: &[SExpr], registry: &Registry) -> Result<(Node<crate::program::Body>, LabelNames), Vec<Diagnostic>> {
    todo!()
}

/// The `INIT` form that `expr` writes, and the names of its labels, for the
/// definition of a cell instance in the registry file.
///
/// Implements `work/engine/reader.md`, Checker: "can be expanded into its definition, by a config, as a macro", and the registry file's format, which [`crate::registry`] gives.
pub fn read_instance(expr: &SExpr, registry: &Registry) -> Result<(Node<crate::program::Instance>, LabelNames), Vec<Diagnostic>> {
    todo!()
}

/// The values of one row that `expr` writes, as an arcdata row is written,
/// for a default row of an input in the registry file.
///
/// Implements `docs/arcdata.md`, Params, and `work/engine/reader.md`, Checker: "with their defaults".
pub fn read_data_row(expr: &SExpr, registry: &Registry) -> Result<Box<[crate::program::DataValue]>, Vec<Diagnostic>> {
    todo!()
}

/// The program of an arclog file and its layout. `representative` is the
/// program of the solver that a `representative` line names, whose claims
/// declare names the file may read, such as the instance of a read
/// `&x.y`: the reader takes each read's owner and each binding of a type
/// parameter from the file and from it. `file` names the file in the
/// places of the layout and of each diagnostic, a solver's
/// [`SourceFile::Arclog`]. `registry`
/// declares which columns of a component are of a type parameter, which,
/// with the file's `INIT` forms and the key clauses of its `DEMONSTRATED`
/// and `RIGID_DET` forms, gives whether a site reads a record, as
/// [`crate::program::SiteValue`] gives.
///
/// Where a node matches no node kind, the program leaves out the least node
/// that holds it, a site, a conjunct or a form, with a diagnostic of the
/// grammar at it, and holds the rest. It fails only where
/// [`read_sexprs`] does.
///
/// Implements `work/engine/reader.md`, Solvers: "The reader reads a solver's `.arclog` and `.arcdata` files into one `Solver` tree".
pub fn read_arclog(
    text: &str,
    file: SourceFile,
    representative: Option<&Node<Program>>,
    registry: &Registry,
) -> Result<WithDiagnostics<(Node<Program>, Layout)>, Vec<Diagnostic>> {
    todo!()
}

/// The forms of an arcdata file, with the layout of the arclog file it
/// stands beside extended by its own. `program` is that arclog file's
/// program, and `representative` the representative's, as [`read_arclog`]
/// takes it, whose forms give what each name declares, such as whether
/// `&piece` of `&piece.member` is an `INIT` or a `RIGID_DET` form, and
/// `registry` gives the orientation constants by their names. A node that matches no node kind is left out,
/// as [`read_arclog`] gives.
///
/// Implements `docs/arcdata.md` and `work/engine/reader.md`, Solvers.
pub fn read_arcdata(
    text: &str,
    program: &Node<Program>,
    representative: Option<&Node<Program>>,
    layout: Layout,
    registry: &Registry,
) -> Result<WithDiagnostics<(Node<Arcdata>, Layout)>, Vec<Diagnostic>> {
    todo!()
}

/// The solver of `task_id` from the text of its two files.
///
/// Where the arcdata file has a `representative` line, the solver is read
/// under the representative's claims, and `representative` gives the
/// representative's solver by its task id. A line whose task id
/// `representative` gives no solver for is a diagnostic at the line. A node
/// that matches no node kind is left out, as [`read_arclog`] gives.
///
/// Implements `work/engine/reader.md`, Solvers: "The reader reads a solver's `.arclog` and `.arcdata` files into one `Solver` tree" and "The forms of a solver with a `representative` line, as the arcdata Header gives, are read under the representative's claims."
pub fn read_solver(
    task_id: &str,
    arclog: &str,
    arcdata: &str,
    representative: &dyn Fn(&str) -> Option<Arc<Solver>>,
    registry: &Registry,
) -> Result<WithDiagnostics<Solver>, Vec<Diagnostic>> {
    todo!()
}
