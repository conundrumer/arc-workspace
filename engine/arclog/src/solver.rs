//! The `Solver` tree, and `cases()`, which gives its case programs on demand.
//!
//! The reader reads a solver's `.arclog` and `.arcdata` files into one
//! `Solver` tree: the claims, the tree of alts, the arcdata records, and
//! `cases()`.
//!
//! The `cases()` stage writes the bodies.

#![allow(unused_variables, dead_code)]

use crate::layout::Layout;
use crate::program::path::NodePath;
use std::sync::Arc;

use crate::program::{AltsName, Arcdata, Node, Program};

/// A solver read from its two files: the claims, the tree of alts, the
/// arcdata records, and `cases()`.
#[derive(Clone, Debug)]
pub struct Solver {
    /// The task id the files are named by.
    pub task_id: Box<str>,
    /// The arclog file: the claims, the concept program's forms and the tree
    /// of alts.
    pub program: Node<Program>,
    /// The arcdata file.
    pub arcdata: Node<Arcdata>,
    pub layout: Layout,
    /// The solver that the arcdata file's `representative` line names, whose
    /// claims this solver's forms are read under, as
    /// `docs/arclog/arcdata.md#header` gives.
    pub representative: Option<Arc<Solver>>,
}

/// The name of one case: the alt it takes at each `ALTS` form it reaches,
/// the concept case's name included, in the order of the forms in the file.
/// A case reaches an `ALTS` form that its branch holds, as the nesting of
/// the blocks gives, and a `DET_OR_RULE` or `RULE_OR_DET` line that its base
/// reads, as [`Solver::case_names`] gives.
///
/// A `DET_OR_RULE` or `RULE_OR_DET` line is an `ALTS` form whose readings
/// are `&background=$Stored` and `&background=$Derived`, or, on a line with
/// several proposers, the stored reading and one derived reading per
/// proposer, `&tile_size=ConstInDim`, as
/// `docs/arclog/arclog.md#the-alts-form` gives.
#[derive(Clone, PartialEq, Eq, Hash, Debug)]
pub struct CaseName(pub Box<[AltsName]>);

/// Whether `cases()` gives the cases the `exclude` forms leave, or every
/// case.
#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub enum Exclusion {
    /// The cases the arcdata file's `exclude` forms leave.
    WithoutExcluded,
    /// Every case, the excluded ones included.
    WithExcluded,
}

/// One case of a solver: its name and its program.
///
/// The program holds no claim. It holds
/// the forms each alt of the case rederives in the place of the concept
/// program's, and the forms of each claim the alt adds, and a combination
/// of alts takes the forms of its nested `ALT`,
/// [`crate::program::AltItem::Alt`]. A `DET` of the concept program is
/// evaluated in the concept program, and the case program reads its
/// parameter as one node, never its body:
/// [`crate::resolver::DependencyKind::Parameter`], or
/// [`crate::resolver::DependencyKind::Chosen`] for a `DET` that ends in
/// `(ONE)`.
#[derive(Clone, Debug)]
pub struct Case {
    pub name: CaseName,
    pub program: Node<Program>,
    origins: crate::hash::StableHashMap<NodePath, (FileOwner, NodePath)>,
    concept_determinations: Box<[NodePath]>,
}

impl Case {
    /// The paths in the case program of the `DET` forms it takes from the
    /// concept program, which resolve in the concept program, as
    /// [`crate::resolver::ConceptReads`] gives, so each reads the concept
    /// program's derivation in every case.
    pub fn concept_determinations(&self) -> &[NodePath] {
        todo!()
    }

    /// The arclog file that holds the node at `path` of the case program,
    /// and its path there, so that a diagnostic on a case program reports
    /// its place in the file. Both paths walk as
    /// [`crate::program::path::node_at`] gives.
    pub fn file_path(&self, path: &NodePath) -> (FileOwner, NodePath) {
        todo!()
    }
}

/// The solver whose arclog file holds a node of a case program: the solver
/// itself, or the solver its `representative` line names, whose claims its
/// forms are read under, and whose file holds those claims
/// (`docs/arclog/arcdata.md#header`).
#[derive(Clone, Copy, PartialEq, Eq, Hash, Debug)]
pub enum FileOwner {
    Solver,
    Representative,
}

/// A combination of alts that names no case of the solver.
#[derive(Clone, Debug)]
pub struct UnknownCase {
    pub name: CaseName,
}

impl Solver {
    /// The names of the solver's cases: the product of its `ALTS` forms,
    /// restricted by the nesting of the blocks, less the `exclude` forms of
    /// the arcdata file where `exclusion` is [`Exclusion::WithoutExcluded`].
    /// A `DET_OR_RULE` or `RULE_OR_DET` line splits only the bases that read
    /// its relation.
    ///
    /// Where the arcdata file has a `representative` line that gives a case's
    /// name, the one name is that case's (`docs/arclog/arcdata.md#header`).
    pub fn case_names(&self, exclusion: Exclusion) -> Vec<CaseName> {
        todo!()
    }

    /// The relations that some block of the solver derives at the program's
    /// name scope, which a name that no block of a case derives resolves
    /// among, as [`crate::resolver::resolve`] takes them. A name that a
    /// `DEMO_RULE` form declares is resolved within that form alone, as
    /// [`crate::program::NameScope`] gives, so the set leaves it out.
    pub fn derived_relations(&self) -> crate::hash::StableHashSet<crate::program::ProgramRelation> {
        todo!()
    }

    /// The concept case: the concept case's name at each `ALTS` form, whose
    /// resolution the other cases' [`crate::resolver::ConceptReads`] take, so
    /// a `DET` of the concept program is evaluated once, in it.
    pub fn concept_case(&self) -> Case {
        todo!()
    }

    /// The cases of `case_names(exclusion)`, each built when the iterator
    /// reaches it, so a run builds only the cases it runs.
    pub fn cases(&self, exclusion: Exclusion) -> Cases<'_> {
        todo!()
    }

    /// The case `name`, excluded or not.
    pub fn case(&self, name: &CaseName) -> Result<Case, UnknownCase> {
        todo!()
    }
}

/// The iterator of [`Solver::cases`]: it builds each case program when it
/// reaches it.
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
