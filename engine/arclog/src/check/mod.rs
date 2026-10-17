//! The checker: a set of checks, each over one syntax node and its scope.
//!
//! Implements `work/engine/reader.md`, Checker: "The checker is a set of
//! checks. Each check reads one syntax node and its scope: the declarations,
//! labels and types visible at that node. The cycle check reads the
//! dependency graph instead. Each check has a form on a prefix ... This step
//! gives each check an interface that admits its prefix form, and step 6
//! builds the prefix forms."
//!
//! [`Check::check_prefix`] is that form on a prefix. Until step 6 builds
//! the prefix forms, each check's `check_prefix` gives
//! [`PrefixResult::Undecided`].
//!
//! The checker stage writes the bodies.

#![allow(unused_variables, dead_code)]

pub mod lint;

use crate::diagnostic::Diagnostic;
use crate::hash::StableHash;
use crate::program::path::NodePath;
use crate::program::{Form, LabelId};
use crate::registry::Registry;
use crate::resolver::{DependencyGraph, ResolvedProgram, Signature};
use crate::types::{ProgramTypes, ValueType};

/// The checks this step builds, as Checker lists them.
///
/// Implements `work/engine/reader.md`, Checker: "This step builds the checks that evaluation needs".
#[derive(Clone, Copy, PartialEq, Eq, Hash, Debug)]
pub enum CheckId {
    /// The grammar: an s-expression that matches no node kind.
    Grammar,
    /// The scope: a name that resolves to nothing visible.
    Scope,
    /// The columns of each site.
    SiteColumns,
    /// The type check, the order rule included.
    Types,
    /// The pose rule of `work/engine/equivariance.md`, The `RIGID_DET` frame.
    PoseRule,
    /// The labels that `=` makes and that an `OR` or an `IF` exports.
    MadeAndExportedLabels,
    /// Grounding.
    Grounding,
    /// The rule of an `Unfold` instance's reads of its outputs.
    UnfoldReads,
    /// Cycles of the dependency graph.
    Cycles,
    /// An instance's input order and defaults.
    InstanceInputs,
    /// The pooled and lifted reads of `docs/arclog.md`, Program.
    PooledAndLiftedReads,
}

/// A label visible at a node, with its inferred type where the type check
/// has given one.
///
/// Implements `work/engine/reader.md`, Checker: "its scope: the declarations, labels and types visible at that node".
#[derive(Clone, Debug)]
pub struct LabelInScope {
    pub label: LabelId,
    pub ty: Option<ValueType>,
}

/// The scope of a node: the declarations, labels and types visible at it.
///
/// Implements `work/engine/reader.md`, Checker: "its scope: the declarations, labels and types visible at that node".
#[derive(Clone, Copy, Debug)]
pub struct Scope<'a> {
    pub program: &'a ResolvedProgram,
    pub registry: &'a Registry,
    pub labels: &'a [LabelInScope],
    /// The clauses of each relation across the solver's blocks.
    pub clauses: &'a SolverClauses,
}

/// Every clause of each relation that a solver declares, across its blocks
/// and so across its cases, with the signature of each. A label that only
/// `(= *X 0)` gives a type takes the type of the column that another clause
/// of the relation gives it, which may stand in another block, as an `ALT`
/// that rederives the relation, and so in another case program. A
/// synthesized program has one case, and its clauses are its own.
///
/// Implements `work/engine/reader.md`, Checker: "A label that only `(= *X 0)` gives a type takes the type of the instance input it stands at, or of the column that another clause of the relation gives it, and the check cache's key then holds that clause's signature."
#[derive(Debug, Default)]
pub struct SolverClauses {
    clauses: crate::hash::StableHashMap<(FileScope, crate::program::ProgramRelation), Box<[(crate::solver::FileOwner, NodePath, Signature)]>>,
}

/// The name scope of a relation in a solver's files: the program, or a
/// `DEMO_RULE` form, by the file that holds it and its path there.
///
/// Implements `docs/arclog.md`, Demonstrated: "Each `DEMO_RULE` is a demonstrated rule".
#[derive(Clone, PartialEq, Eq, Hash, Debug)]
pub enum FileScope {
    Program,
    DemoRule(crate::solver::FileOwner, NodePath),
}

impl SolverClauses {
    /// The clauses of each relation of `solver`, by the arclog file that
    /// holds each, the solver's or its representative's, and the path there.
    ///
    /// Implements `work/engine/reader.md`, Checker: "the column that another clause of the relation gives it".
    pub fn of(solver: &crate::solver::Solver, registry: &Registry) -> Self {
        todo!()
    }

    /// The clauses of a synthesized program, its own.
    ///
    /// Implements `work/engine/reader.md`, Checker: "the column that another clause of the relation gives it".
    pub fn of_program(program: &ResolvedProgram) -> Self {
        todo!()
    }

    /// Each clause of `relation` in the name scope `scope`, by its file and
    /// its path there, with its signature.
    ///
    /// Implements `work/engine/reader.md`, Checker: "and the check cache's key then holds that clause's signature".
    pub fn of_relation(
        &self,
        scope: &FileScope,
        relation: &crate::program::ProgramRelation,
    ) -> &[(crate::solver::FileOwner, NodePath, Signature)] {
        todo!()
    }
}

/// A check's input: one node, its path, and its scope.
///
/// Implements `work/engine/reader.md`, Checker: "Each check reads one syntax node and its scope".
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
/// are ordered: the caller maps the path to the form's source order through
/// [`crate::program::canonical::CanonicalOrder`], and the lint maps it then
/// to each place of the node, as [`crate::diagnostic::Location`] gives.
///
/// Implements `work/engine/reader.md`, Checker: "so the cases that share a form share its check" and Programs as values: "An error at a node that stands in several places is reported at each of them."
#[derive(Clone, PartialEq, Eq, Debug)]
pub struct Refusal {
    pub message: Box<str>,
    pub at: NodePath,
}

/// A check's result on a whole node.
///
/// Implements `work/engine/reader.md`, Checker: "The checker is a set of checks."
#[derive(Clone, PartialEq, Eq, Debug)]
pub enum CheckResult {
    Pass,
    Refuse(Box<[Refusal]>),
}

/// A check's result on a prefix: a refusal only where no completion passes.
/// The path of each refusal is relative to the prefix's partial form.
///
/// Implements `work/engine/reader.md`, Checker: "which refuses a prefix only where no completion passes the check".
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
///
/// Implements `work/engine/reader.md`, Checker: "Each check has a form on a prefix", and Programs as values: "An `OR`, an `IF`, an `ALL` and a `NOT` bound the completion only once complete".
#[derive(Clone, Copy, Debug)]
pub struct Prefix<'a> {
    pub complete: &'a [Form],
    pub partial: &'a Form,
    pub open: &'a NodePath,
    pub scope: Scope<'a>,
}

/// One check of the checker.
///
/// Implements `work/engine/reader.md`, Checker: "The checker is a set of checks."
pub trait Check: Sync {
    /// The check's id.
    fn id(&self) -> CheckId;

    /// The check over one whole node.
    fn check(&self, input: &CheckInput<'_>) -> CheckResult;

    /// The check over a prefix. It refuses only where no completion of the
    /// prefix passes [`Check::check`].
    fn check_prefix(&self, prefix: &Prefix<'_>) -> PrefixResult;
}

/// The cycle check, which reads the dependency graph and no node. Each
/// refusal's path is relative to the program: the form of a node on the
/// cycle.
///
/// Implements `work/engine/reader.md`, Checker: "The cycle check reads the dependency graph instead."
pub fn check_cycles(graph: &DependencyGraph, program: &ResolvedProgram) -> CheckResult {
    todo!()
}

/// The key of the check cache: the form's canonical hash and the signatures
/// of the names it reads.
///
/// Implements `work/engine/reader.md`: "A form's check result is cached on the form's canonical hash
/// and the signatures of the names it reads, so the cases that share a form
/// share its check". Where a label's type comes from another clause of the
/// relation, as "A label that only `(= *X 0)` gives a type" gives, that
/// clause's signature is among the signatures.
#[derive(Clone, PartialEq, Eq, Hash, Debug)]
pub struct CheckCacheKey {
    pub check: CheckId,
    pub canonical_hash: StableHash,
    pub signatures: Box<[Signature]>,
}

/// The check results of the forms checked so far, by
/// [`CheckCacheKey`], so that the cases that share a form share its check.
///
/// Implements `work/engine/reader.md`, Checker: "A form's check result is cached on the form's canonical hash and the signatures of the names it reads".
#[derive(Debug, Default)]
pub struct CheckCache {
    entries: crate::hash::StableHashMap<CheckCacheKey, CheckResult>,
    /// The types the type check inferred for a form, under the key of its
    /// [`CheckId::Types`] check.
    types: crate::hash::StableHashMap<CheckCacheKey, std::sync::Arc<crate::types::FormTypes>>,
}

impl CheckCache {
    /// The result cached under `key`, if any.
    ///
    /// Implements `work/engine/reader.md`, Checker: "A form's check result is cached on the form's canonical hash and the signatures of the names it reads".
    pub fn get(&self, key: &CheckCacheKey) -> Option<&CheckResult> {
        todo!()
    }

    /// Caches `result` under `key`.
    ///
    /// Implements `work/engine/reader.md`, Checker: "A form's check result is cached on the form's canonical hash and the signatures of the names it reads".
    pub fn insert(&mut self, key: CheckCacheKey, result: CheckResult) {
        todo!()
    }

    /// The types cached under `key`, the key of a form's type check.
    ///
    /// Implements `work/engine/reader.md`, Terms: "Types are static: the checker holds them".
    pub fn types(&self, key: &CheckCacheKey) -> Option<std::sync::Arc<crate::types::FormTypes>> {
        todo!()
    }

    /// Caches `types` under `key`, the key of a form's type check.
    ///
    /// Implements `work/engine/reader.md`, Terms: "Types are static: the checker holds them".
    pub fn insert_types(&mut self, key: CheckCacheKey, types: std::sync::Arc<crate::types::FormTypes>) {
        todo!()
    }
}

/// A case program that every check passes, with the types the type check
/// inferred for it. Each evaluator entry point takes one, so it runs only a
/// checked program.
///
/// Implements `work/engine/reader.md`, Terms: "Types are static: the checker holds them", and How each decision can fail: "every evaluator entry point checks its input".
#[derive(Clone, Debug)]
pub struct CheckedProgram {
    pub program: ResolvedProgram,
    pub types: ProgramTypes,
    /// The alerts on the program, such as a body whose canonical form
    /// reached the search cap, which refuse nothing.
    pub alerts: Vec<Diagnostic>,
}

/// Runs every check of [`checks`] over each form of `program`, and the
/// cycle check, through `cache`. Each diagnostic's location is a
/// [`crate::diagnostic::Location::Path`] in `program`.
///
/// Implements `work/engine/reader.md`, Checker: "The checker is a set of checks."
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
///
/// Implements `work/engine/reader.md`, Checker: "This step builds the checks that evaluation needs".
pub fn checks() -> &'static [&'static dyn Check] {
    todo!()
}
