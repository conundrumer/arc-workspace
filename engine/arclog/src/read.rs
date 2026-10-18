//! The reader of arclog and arcdata files. It reads a solver's `.arclog`
//! and `.arcdata` files into one [`Solver`] tree. Both files are
//! s-expressions, read by one reader, and the arcdata file has a closed set
//! of head symbols (`docs/arclog/arcdata.md#arcdata`). The registry file
//! under `engine/lib/` is read by the same s-expression reader, as
//! [`crate::registry`] gives.
//!
//! Each node reader records the layout of each node it reads under the
//! node's path, as [`crate::layout::Layout`] gives, and leaves out a node
//! that matches no node kind with a diagnostic of the grammar at it.

mod arcdata;
mod arclog;
mod columns;
mod labels;
mod sexpr;
pub(crate) mod spelling;

use std::sync::Arc;

use crate::check::CheckId;
use crate::diagnostic::{Diagnostic, DiagnosticKind, Location, Severity, WithDiagnostics};
use crate::layout::{FilePlace, Layout, SourceFile, SourcePlace};
use crate::program::path::NodePath;
use crate::program::{Arcdata, Form, Node, Program};
use crate::solver::Solver;

use self::arclog::{Owners, Reader, Record};
use self::labels::LabelScope;

/// An s-expression as the fixed reader gives it, before node kinds.
#[derive(Clone, PartialEq, Eq, Debug)]
pub enum SExpr {
    /// A symbol: a keyword, a name, a label with its mark, a number.
    Symbol { text: Box<str>, place: SourcePlace },
    /// A quoted string, its content unescaped.
    String { text: Box<str>, place: SourcePlace },
    /// A list: its items, its place from its `(` to its `)`, and the place
    /// of its `)`.
    List { items: Box<[SExpr]>, place: SourcePlace, close: SourcePlace },
}

impl SExpr {
    /// Where the s-expression stands.
    pub fn place(&self) -> SourcePlace {
        match self {
            SExpr::Symbol { place, .. } | SExpr::String { place, .. } | SExpr::List { place, .. } => *place,
        }
    }
}

/// A diagnostic of the grammar at `place`, of a file the reader reads alone.
fn grammar(message: impl Into<Box<str>>, place: SourcePlace) -> Diagnostic {
    check_error(CheckId::Grammar, message, place)
}

/// An error of `check` at `place`, of a file the reader reads alone.
fn check_error(check: CheckId, message: impl Into<Box<str>>, place: SourcePlace) -> Diagnostic {
    Diagnostic {
        kind: DiagnosticKind::Check(check),
        severity: Severity::Error,
        message: message.into(),
        location: Location::Places(Box::new([FilePlace { task_id: None, place }])),
        cases: Box::new([]),
    }
}

/// The place of the end of `text`, of no width.
fn end_place(text: &str, file: SourceFile) -> SourcePlace {
    let (line, column) = line_column_after(text, 1, 1);
    SourcePlace { file, start: text.len() as u32, end: text.len() as u32, line, column }
}

/// The line and column after `text`, where `text` starts at `line` and
/// `column`, counted as the s-expression reader counts them: a newline
/// starts the next line at column 1, and each other character takes one
/// column.
pub(crate) fn line_column_after(text: &str, line: u32, column: u32) -> (u32, u32) {
    match text.rsplit_once('\n') {
        Some((_, last_line)) => (line + text.matches('\n').count() as u32, last_line.chars().count() as u32 + 1),
        None => (line, column + text.chars().count() as u32),
    }
}

/// The s-expressions of `text` and its comments.
///
/// Fails with a diagnostic of the grammar at each unbalanced list or
/// unterminated string.
pub fn read_sexprs(text: &str, file: SourceFile) -> Result<(Vec<SExpr>, Vec<crate::layout::Comment>), Vec<Diagnostic>> {
    sexpr::read(text, file)
}

/// The names of the labels of a node that one s-expression gives, in the
/// order they first stand, for a reader of a form that names labels outside
/// the node, as the registry's `(macro ...)` and `(output ...)` forms do. A
/// proposer written in arclog has its clause's labels as its columns.
pub type LabelNames = Box<[(Box<str>, crate::program::LabelId)]>;

/// The body that the s-expressions `exprs` write, as the atoms of a clause,
/// and the names of its labels: the one reader of a body that stands inside
/// a form of the registry file, such as the definition of a lib name by
/// other lib names, in the format [`crate::registry`] gives.
///
/// Fails where an s-expression of `exprs` matches no node kind of its
/// format, with a diagnostic of the grammar at each such s-expression.
pub fn read_body(exprs: &[SExpr]) -> Result<(Node<crate::program::Body>, LabelNames), Vec<Diagnostic>> {
    let scope = LabelScope::new(exprs, &|_| false);
    let mut reader = Reader::new(exprs, true);
    let body = reader.body(exprs, &scope);
    if reader.diagnostics.is_empty() { Ok((body, scope.names_in_order())) } else { Err(reader.diagnostics) }
}

/// The `INIT` form that `expr` writes, and the names of its labels, for the
/// definition of a cell instance in the registry file, a lib name that a
/// config expands into its definition, in the format [`crate::registry`]
/// gives.
///
/// Fails where an s-expression of `expr` matches no node kind of its format,
/// with a diagnostic of the grammar at each such s-expression.
pub fn read_instance(expr: &SExpr) -> Result<(Node<crate::program::Instance>, LabelNames), Vec<Diagnostic>> {
    let exprs = std::slice::from_ref(expr);
    let scope = LabelScope::new(exprs, &|_| false);
    let mut reader = Reader::new(exprs, true);
    let form = reader.form(expr, &NodePath::default(), Some(&scope));
    match form {
        Ok(Form::Instance(instance)) if reader.diagnostics.is_empty() => Ok((instance, scope.names_in_order())),
        Ok(_) if reader.diagnostics.is_empty() => {
            Err(vec![grammar("the definition is an `INIT` form", expr.place())])
        }
        _ => Err(reader.diagnostics),
    }
}

/// The rows that `rows` write, as a `param` form writes them after its types
/// (`docs/arclog/arcdata.md#params`), for the default of an input in the
/// registry file.
///
/// Fails where an s-expression of `rows` matches no node kind of its format,
/// with a diagnostic of the grammar at each such s-expression.
pub fn read_param_value(rows: &[SExpr]) -> Result<crate::program::ParamValue, Vec<Diagnostic>> {
    let mut reader = Reader::with_owners(Owners::default(), false);
    match reader.param_value(rows, &mut Record::new(None)) {
        Ok(value) if reader.diagnostics.is_empty() => Ok(value),
        _ => Err(reader.diagnostics),
    }
}

/// The program of an arclog file and its layout, read from the file alone.
/// `file` names the file in the places of the layout and of each
/// diagnostic, a solver's [`SourceFile::Arclog`]. Each site holds what the
/// file writes, as [`crate::program::SiteValue`] gives, and each read
/// `&x.y` names the outputs of the file's `INIT` or `RIGID_DET` form `&x`.
///
/// Where a node matches no node kind, the program leaves out the least node
/// that holds it, a site, a conjunct or a form, with a diagnostic of the
/// grammar at it, and holds the rest. It fails only where
/// [`read_sexprs`] does.
pub fn read_arclog(text: &str, file: SourceFile) -> Result<WithDiagnostics<(Node<Program>, Layout)>, Vec<Diagnostic>> {
    let (exprs, comments) = read_sexprs(text, file)?;
    let mut reader = Reader::new(&exprs, false);
    let program = reader.program(&exprs, end_place(text, file));
    let diagnostics = std::mem::take(&mut reader.diagnostics);
    Ok(WithDiagnostics { value: (program, reader.layout(file, comments)), diagnostics })
}

/// The forms of an arcdata file, with the layout of the arclog file it
/// stands beside extended by its own. `program` is that arclog file's
/// program, and `representative` the program of the solver its
/// `representative` line names, whose forms give what each name declares, such as whether
/// `&piece` of `&piece.member` is an `INIT` or a `RIGID_DET` form. Each
/// orientation constant holds its name as the file writes it. A node that
/// matches no node kind is left out, as [`read_arclog`] gives.
pub fn read_arcdata(
    text: &str,
    program: &Node<Program>,
    representative: Option<&Node<Program>>,
    layout: Layout,
) -> Result<WithDiagnostics<(Node<Arcdata>, Layout)>, Vec<Diagnostic>> {
    let (exprs, comments) = read_sexprs(text, SourceFile::Arcdata)?;
    Ok(arcdata_of(&exprs, comments, end_place(text, SourceFile::Arcdata), program, representative, layout))
}

/// The arcdata file of `exprs`, as [`read_arcdata`] gives it.
fn arcdata_of(
    exprs: &[SExpr],
    comments: Vec<crate::layout::Comment>,
    end: SourcePlace,
    program: &Node<Program>,
    representative: Option<&Node<Program>>,
    layout: Layout,
) -> WithDiagnostics<(Node<Arcdata>, Layout)> {
    let programs: Vec<&Program> = std::iter::once(program).chain(representative).map(Node::value).collect();
    let mut reader = Reader::with_owners(Owners::of_programs(&programs), false);
    let arcdata = reader.arcdata(exprs, end);
    let diagnostics = std::mem::take(&mut reader.diagnostics);
    let own = reader.layout(SourceFile::Arcdata, comments);
    let mut layout = layout;
    layout.nodes.extend(own.nodes);
    layout.comments = layout.comments.iter().chain(own.comments.iter()).cloned().collect();
    WithDiagnostics { value: (arcdata, layout), diagnostics }
}

/// The task id of the `representative` line of `exprs`, and the line's
/// place, where the file has one.
fn representative_line(exprs: &[SExpr]) -> Option<(&str, SourcePlace)> {
    exprs.iter().find_map(|expr| match expr {
        SExpr::List { items, place, .. } => match &items[..] {
            [SExpr::Symbol { text: head, .. }, SExpr::Symbol { text: task_id, .. }, ..]
                if &**head == spelling::REPRESENTATIVE =>
            {
                Some((&**task_id, *place))
            }
            _ => None,
        },
        _ => None,
    })
}

/// `diagnostics`, each place of which names the file by `task_id`, where it
/// names none.
fn in_solver(mut diagnostics: Vec<Diagnostic>, task_id: &str) -> Vec<Diagnostic> {
    for diagnostic in &mut diagnostics {
        if let Location::Places(places) = &mut diagnostic.location {
            for place in places.iter_mut().filter(|p| p.task_id.is_none()) {
                place.task_id = Some(task_id.into());
            }
        }
    }
    diagnostics
}

/// The solver of `task_id` from the text of its two files.
///
/// Where the arcdata file has a `representative` line, the solver is read
/// under the representative's claims, and `representative` gives the
/// representative's solver by its task id. A line whose task id
/// `representative` gives no solver for is a diagnostic of the scope at the
/// line. A node
/// that matches no node kind is left out, as [`read_arclog`] gives. Each
/// diagnostic of the two files stands at places that name the files by
/// `task_id`.
pub fn read_solver(
    task_id: &str,
    arclog: &str,
    arcdata: &str,
    representative: &dyn Fn(&str) -> Option<Arc<Solver>>,
) -> Result<WithDiagnostics<Solver>, Vec<Diagnostic>> {
    let read = read_arclog(arclog, SourceFile::Arclog).map_err(|d| in_solver(d, task_id))?;
    let (program, layout) = read.value;
    let mut diagnostics = read.diagnostics;
    let (exprs, comments) = read_sexprs(arcdata, SourceFile::Arcdata).map_err(|d| in_solver(d, task_id))?;
    let mut solver_of_line = None;
    if let Some((line_task_id, place)) = representative_line(&exprs) {
        match representative(line_task_id) {
            Some(solver) => solver_of_line = Some(solver),
            None => diagnostics.push(check_error(CheckId::Scope, format!("`{line_task_id}` names no solver of the corpus"), place)),
        }
    }
    let end = end_place(arcdata, SourceFile::Arcdata);
    let read = arcdata_of(&exprs, comments, end, &program, solver_of_line.as_ref().map(|s| &s.program), layout);
    let (arcdata, layout) = read.value;
    diagnostics.extend(read.diagnostics);
    let solver = Solver { task_id: task_id.into(), program, arcdata, layout, representative: solver_of_line };
    Ok(WithDiagnostics { value: solver, diagnostics: in_solver(diagnostics, task_id) })
}
