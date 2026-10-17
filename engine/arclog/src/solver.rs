//! The `Solver` tree, and `cases()`, which gives its case programs on demand.
//!
//! Implements `work/engine/reader.md`, Solvers: "The reader reads a solver's
//! `.arclog` and `.arcdata` files into one `Solver` tree: the claims, the tree
//! of alts, the arcdata records, and `cases()`." and the rules by which
//! `cases()` makes a case program, with `work/engine/cases.md`, Cases.
//!
//! The `cases()` stage writes the bodies.

#![allow(unused_variables, dead_code)]

use crate::layout::Layout;
use crate::program::path::NodePath;
use crate::program::{AltsName, Arcdata, Program};

/// A solver read from its two files.
///
/// Implements `work/engine/reader.md`, Solvers: "the claims, the tree of alts, the arcdata records, and `cases()`".
#[derive(Clone, Debug)]
pub struct Solver {
    /// The task id the files are named by.
    pub task_id: Box<str>,
    /// The arclog file: the claims, the concept program's forms and the tree
    /// of alts.
    pub program: Program,
    /// The arcdata file's records.
    pub records: Arcdata,
    pub layout: Layout,
}

/// The name of one case: the alt it takes at each `ALTS` form, the concept
/// case's name included, in the order of the forms in the file.
///
/// A `DET_OR_RULE` or `RULE_OR_DET` line is an `ALTS` form whose readings
/// are `&background=$Stored` and `&background=$Derived`, as
/// `docs/arclog.md`, The `ALTS` form, gives.
#[derive(Clone, PartialEq, Eq, Hash, Debug)]
pub struct CaseName(pub Box<[AltsName]>);

/// Whether `cases()` gives the cases the `exclude` forms leave, or every
/// case.
///
/// Implements `work/engine/reader.md`, Solvers: "It gives the cases that the arcdata file's `exclude` forms leave, and an excluded case on request".
#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub enum Exclusion {
    /// The cases the arcdata file's `exclude` forms leave.
    Leave,
    /// Every case, the excluded ones included.
    Include,
}

/// One case of a solver: its name and its program.
///
/// The program holds no claim, as "it removes the claims" gives.
///
/// Implements `work/engine/reader.md`, Solvers: "To make a case program, it removes the claims".
#[derive(Clone, Debug)]
pub struct Case {
    pub name: CaseName,
    pub program: Program,
    origins: crate::hash::StableHashMap<NodePath, NodePath>,
}

impl Case {
    /// The path in the arclog file of the node at `path` of the case
    /// program, so that a diagnostic on a case program reports its place in
    /// the file.
    ///
    /// Implements `work/engine/reader.md`, Checker: "It reports each error once per place in the file".
    pub fn file_path(&self, path: &NodePath) -> NodePath {
        todo!()
    }
}

/// A combination of alts that names no case of the solver.
///
/// Implements `work/engine/reader.md`, Solvers: "an excluded case on request".
#[derive(Clone, Debug)]
pub struct UnknownCase {
    pub name: CaseName,
}

impl Solver {
    /// The names of the solver's cases: the product of its `ALTS` forms,
    /// restricted by the nesting of the blocks, less the `exclude` forms
    /// where `exclusion` is [`Exclusion::Leave`].
    ///
    /// Where the arcdata file has a `representative` line that gives a case's
    /// name, the one name is that case's, as the arcdata Header gives.
    ///
    /// Implements `work/engine/cases.md`, Cases: "A solver's cases are the product of its `ALTS` forms, restricted by the nesting of the blocks, less the `exclude` forms of the arcdata file."
    pub fn case_names(&self, exclusion: Exclusion) -> Vec<CaseName> {
        todo!()
    }

    /// The cases of `case_names(exclusion)`, each built when the iterator
    /// reaches it, so a run builds only the cases it runs.
    ///
    /// Implements "`cases()` gives each case program as a program value, on
    /// demand".
    pub fn cases(&self, exclusion: Exclusion) -> Cases<'_> {
        todo!()
    }

    /// The case `name`, excluded or not.
    ///
    /// Implements "and an excluded case on request".
    pub fn case(&self, name: &CaseName) -> Result<Case, UnknownCase> {
        todo!()
    }
}

/// The iterator of [`Solver::cases`]: it builds each case program when it
/// reaches it.
///
/// Implements `work/engine/reader.md`, Solvers: "`cases()` gives each case program as a program value, on demand".
#[derive(Debug)]
pub struct Cases<'a> {
    solver: &'a Solver,
    names: std::vec::IntoIter<CaseName>,
}

impl Iterator for Cases<'_> {
    type Item = Case;

    fn next(&mut self) -> Option<Case> {
        todo!()
    }
}
