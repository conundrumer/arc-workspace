//! The checker: a set of checks, each over one syntax node and its scope,
//! the declarations, labels and types visible at that node. The cycle check
//! reads the dependency graph instead.
//!
//! Each check has a form on a prefix, [`Check::check_prefix`], so that a
//! decode can refuse a prefix that no completion passes. Until step 6 builds
//! the prefix forms, each check's `check_prefix` gives
//! [`PrefixResult::Undecided`].
//!
//! The checker stage writes the bodies.

#![allow(unused_variables, dead_code)]

pub mod lint;

use crate::diagnostic::Diagnostic;
use crate::program::path::NodePath;
use crate::program::{Form, LabelId};
use crate::registry::Registry;
use crate::resolver::{DependencyGraph, ResolvedProgram, Signature};
use crate::types::{ProgramTypes, ValueType};

/// The checks this step builds, those that evaluation needs.
#[derive(Clone, Copy, PartialEq, Eq, Hash, Debug)]
pub enum CheckId {
    /// The grammar: an s-expression that matches no node kind.
    Grammar,
    /// The scope: a name that resolves to nothing visible.
    Scope,
    /// The columns of each site.
    SiteColumns,
    /// The type check, the order rule included. The check gives each label
    /// of a body the type that [`crate::types::label_type`] gives it over
    /// the list of the label's scope, and refuses the label where that
    /// function gives a fault. That list is the clause's body for a label of
    /// the top level; a branch's list for a label local to an `OR` branch or
    /// to an `IF`'s then; for a label fresh in an `IF`'s test or in a list of
    /// an `ALL`, the list that holds that form; and for a label that an `OR`
    /// or an `IF` exports, the list that holds the outermost form that
    /// exports it. The site types the check gives that function are the
    /// declared types of the columns; at a column of a type parameter bound
    /// to one label's type, that type, at the column's path and at the path
    /// of the column followed by a bare label's name; and at a field of a
    /// column of a type parameter bound to a record, that field's type in
    /// the bound record. The parameter's first projection binds it
    /// (`docs/arclog/arclog.md#instance`). A label that only
    /// `(= *X 0)` gives a type takes the type of the instance input it
    /// stands at, or else the join, as [`crate::types::ValueType::join`]
    /// gives it, of the types that the relation's other clauses give its
    /// column, each read from [`SolverClauses`]. Those clauses may stand in
    /// other blocks, as an `ALT` that rederives the relation, and so in
    /// other case programs; the check's [`CheckCacheKey`] then holds their
    /// signatures. The check refuses the label where no type is above those
    /// types.
    Types,
    /// The pose rule: a Pose label stands only at the sites that
    /// `docs/arclog/rigid.md#the-pose` gives.
    PoseRule,
    /// The labels that `=` makes and that an `OR` or an `IF` exports.
    MadeAndExportedLabels,
    /// Grounding. The check grounds each body by
    /// [`crate::grounding::grounded_labels`].
    Grounding,
    /// The rule of an `Unfold` instance's reads of its outputs.
    UnfoldReads,
    /// Cycles of the dependency graph.
    Cycles,
    /// An instance's input order and defaults.
    InstanceInputs,
    /// The pooled and lifted reads, as `docs/arclog/arclog.md#program`
    /// gives.
    PooledAndLiftedReads,
}

/// A label visible at a node, with its inferred type where the type check
/// has given one.
#[derive(Clone, Debug)]
pub struct LabelInScope {
    pub label: LabelId,
    pub ty: Option<ValueType>,
}

/// The scope of a node: the declarations, labels and types visible at it.
#[derive(Clone, Copy, Debug)]
pub struct Scope<'a> {
    /// The case program the node stands in.
    pub program: &'a ResolvedProgram,
    /// The registry the program's names resolve against.
    pub registry: &'a Registry,
    /// The labels visible at the node.
    pub labels: &'a [LabelInScope],
    /// The clauses of each relation across the solver's blocks.
    pub clauses: &'a SolverClauses,
}

/// Every clause of each relation that a solver declares, across its blocks
/// and so across its cases. A key is a relation in the name scope it is
/// declared in. Each entry of a key is one clause of that relation: the
/// arclog file that holds the clause, the solver's or its representative's,
/// the clause's path in that file, and the clause's signature. The entries
/// of a key stand in a fixed order: the clauses of the solver's own file
/// first, then those of its representative's, the order of the
/// [`crate::solver::FileOwner`] variants, and within a file in the order of
/// their paths, the index of the top-level form, then the index among the
/// children at each step. A synthesized program has one case, and its
/// clauses are its own.
#[derive(Debug, Default)]
pub struct SolverClauses {
    clauses: crate::hash::StableHashMap<(FileScope, crate::program::ProgramRelation), Box<[(crate::solver::FileOwner, NodePath, Signature)]>>,
}

/// The name scope of a relation in a solver's files: the program, or a
/// `DEMO_RULE` form (`docs/arclog/arclog.md#demonstrated`), by the file
/// that holds it and its path there.
#[derive(Clone, PartialEq, Eq, Hash, Debug)]
pub enum FileScope {
    Program,
    DemoRule(crate::solver::FileOwner, NodePath),
}

impl SolverClauses {
    /// The clauses of each relation of `solver`, by the arclog file that
    /// holds each, the solver's or its representative's, and the path there,
    /// each key's entries in the order [`SolverClauses`] gives.
    pub fn of(solver: &crate::solver::Solver, registry: &Registry) -> Self {
        todo!()
    }

    /// The clauses of a synthesized program, its own.
    pub fn of_program(program: &ResolvedProgram) -> Self {
        todo!()
    }

    /// Each clause of `relation` in the name scope `scope`, by its file and
    /// its path there, with its signature, in the order [`SolverClauses`]
    /// gives.
    pub fn of_relation(
        &self,
        scope: &FileScope,
        relation: &crate::program::ProgramRelation,
    ) -> &[(crate::solver::FileOwner, NodePath, Signature)] {
        todo!()
    }
}

/// A check's input: one node, its path, and its scope.
#[derive(Clone, Copy, Debug)]
pub struct CheckInput<'a> {
    pub form: &'a Form,
    pub path: &'a NodePath,
    pub scope: Scope<'a>,
}

/// One error a check finds: its message, at the node of the path relative to
/// the node the check read. A refusal holds no place in a file, and a cached
/// one holds its path in the form's canonical order, so that it serves each
/// form of equal content wherever it stands and however its lists and labels
/// are ordered.
#[derive(Clone, PartialEq, Eq, Debug)]
pub struct Refusal {
    pub message: Box<str>,
    pub at: NodePath,
}

/// A check's result on a whole node.
#[derive(Clone, PartialEq, Eq, Debug)]
pub enum CheckResult {
    Pass,
    Refuse(Box<[Refusal]>),
}

/// A check's result on a prefix: a refusal only where no completion passes.
/// The path of each refusal is relative to the prefix's partial form.
#[derive(Clone, PartialEq, Eq, Debug)]
pub enum PrefixResult {
    /// Some completion may pass.
    Undecided,
    /// No completion passes, as a viable prefix of a parser is decided.
    Refuse(Box<[Refusal]>),
}

/// A program prefix: the forms given so far, the last of them incomplete,
/// as a decode gives it.
///
/// `open` is the path, relative to `partial`, of the innermost node the
/// decode still writes. That node and each node above it are open: an open
/// `OR`, `IF`, `ALL` or `NOT` may still take a branch, a test atom or a
/// site, so it bounds no completion yet. Every other node of `partial` is
/// complete. A list that the decode has not reached, such as the else of an
/// `IF` whose test is open, stands empty. So a completion's rows, projected
/// onto the prefix's labels, lie among the rows of the complete positive
/// atoms at the top level of the partial form's body, each as soon as it
/// stands, which a prefix form may refuse by.
#[derive(Clone, Copy, Debug)]
pub struct Prefix<'a> {
    pub complete: &'a [Form],
    pub partial: &'a Form,
    pub open: &'a NodePath,
    pub scope: Scope<'a>,
}

/// One check of the checker.
pub trait Check: Sync {
    /// The check's id.
    fn id(&self) -> CheckId;

    /// The check over one whole node: a pass, or each refusal it finds.
    fn check(&self, input: &CheckInput<'_>) -> CheckResult;

    /// The check over a prefix. It refuses only where no completion of the
    /// prefix passes [`Check::check`].
    fn check_prefix(&self, prefix: &Prefix<'_>) -> PrefixResult;
}

/// The cycle check, which reads the dependency graph and no node. Each
/// refusal's path is relative to the program: the form of a node on the
/// cycle.
pub fn check_cycles(graph: &DependencyGraph, program: &ResolvedProgram) -> CheckResult {
    todo!()
}

/// The key of the check cache: the check, the form's canonical form, with
/// each name as the file writes it, and the signatures of the names it
/// reads, so the cases that share a form share its check. Two keys are equal
/// where their checks, their canonical forms and their signatures are, so
/// two forms or two reads whose hashes collide take two checks.
/// The signatures stand in a fixed order: those of the names the form
/// reads, in the order of each name's first read in the form's canonical
/// order, then, where a label's type comes from other clauses of a
/// relation, as [`CheckId::Types`] gives, those clauses' signatures, in the
/// order [`SolverClauses`] gives.
#[derive(Clone, PartialEq, Eq, Hash, Debug)]
pub struct CheckCacheKey {
    pub check: CheckId,
    pub canonical_form: crate::program::canonical::CanonicalForm,
    pub signatures: Box<[Signature]>,
}

/// The check results of the forms checked so far, by
/// [`CheckCacheKey`], so that the cases that share a form share its check.
#[derive(Debug, Default)]
pub struct CheckCache {
    entries: crate::hash::StableHashMap<CheckCacheKey, CheckResult>,
    /// The types the type check inferred for a form, under the key of its
    /// [`CheckId::Types`] check.
    types: crate::hash::StableHashMap<CheckCacheKey, std::sync::Arc<crate::types::FormTypes>>,
}

impl CheckCache {
    /// The result cached under `key`, if any.
    pub fn get(&self, key: &CheckCacheKey) -> Option<&CheckResult> {
        todo!()
    }

    /// Caches `result` under `key`.
    pub fn insert(&mut self, key: CheckCacheKey, result: CheckResult) {
        todo!()
    }

    /// The types cached under `key`, the key of a form's type check.
    pub fn types(&self, key: &CheckCacheKey) -> Option<std::sync::Arc<crate::types::FormTypes>> {
        todo!()
    }

    /// Caches `types` under `key`, the key of a form's type check.
    pub fn insert_types(&mut self, key: CheckCacheKey, types: std::sync::Arc<crate::types::FormTypes>) {
        todo!()
    }
}

/// A case program that every check passes, with the types the type check
/// inferred for it. Each evaluator entry point takes one, so it runs only a
/// checked program.
#[derive(Clone, Debug)]
pub struct CheckedProgram {
    pub program: ResolvedProgram,
    pub types: ProgramTypes,
    /// The alerts on the program, such as a body whose canonical form
    /// reached the search cap, which refuse nothing.
    pub alerts: Vec<Diagnostic>,
}

/// Runs every check of [`checks`] over each form of `program`, and the
/// cycle check, through `cache`, and gives the checked program, or each
/// diagnostic where a check refuses. It maps each refusal's path, which a
/// [`Refusal`] holds in the form's canonical order, to the form's source
/// order through [`crate::program::canonical::CanonicalOrder`], and the
/// labels of each cached [`crate::types::FormTypes`], each its canonical
/// position, to the form's own labels in the same way. Each diagnostic's
/// location is a [`crate::diagnostic::Location::Path`] in
/// `program`.
pub fn check_program(
    program: ResolvedProgram,
    clauses: &SolverClauses,
    registry: &Registry,
    cache: &mut CheckCache,
) -> Result<CheckedProgram, Vec<Diagnostic>> {
    todo!()
}

/// The checks of this step, each once: one per [`CheckId`] but
/// [`CheckId::Cycles`], which [`check_cycles`] runs and which has no prefix
/// form, since a decode writes clauses that read only relations declared
/// before them. The grammar and scope checks are among them: over a whole
/// node, which the reader built and the resolver resolved, they pass, since
/// the reader and the resolver report those errors; on a prefix, they refuse
/// a partial form that no completion makes a node of the grammar, or a name
/// that no completion resolves.
pub fn checks() -> &'static [&'static dyn Check] {
    todo!()
}
