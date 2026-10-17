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
//! [`PrefixVerdict::Undecided`].
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
use crate::types::ValueType;

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
    Labels,
    /// Grounding.
    Grounding,
    /// The rule of an `Unfold` instance's reads of its outputs.
    UnfoldReads,
    /// Cycles of the dependency graph.
    Cycles,
    /// An instance's input order and defaults.
    InstanceInputs,
    /// The pooled and lifted reads of `docs/arclog.md`, Program.
    ExampleReads,
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

/// A check's result on a whole node.
///
/// Implements `work/engine/reader.md`, Checker: "The checker is a set of checks."
#[derive(Clone, PartialEq, Eq, Debug)]
pub enum CheckResult {
    Pass,
    Refuse(Vec<Diagnostic>),
}

/// A check's result on a prefix: a refusal only where no completion passes.
///
/// Implements `work/engine/reader.md`, Checker: "which refuses a prefix only where no completion passes the check".
#[derive(Clone, PartialEq, Eq, Debug)]
pub enum PrefixVerdict {
    /// Some completion may pass.
    Undecided,
    /// No completion passes, as a viable prefix of a parser is decided.
    Refuse(Vec<Diagnostic>),
}

/// A program prefix: the forms given so far, the last of them incomplete,
/// as a decode gives it.
///
/// Implements `work/engine/reader.md`, Checker: "Each check has a form on a prefix".
#[derive(Clone, Copy, Debug)]
pub struct Prefix<'a> {
    pub complete: &'a [Form],
    pub partial: &'a Form,
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
    fn check_prefix(&self, prefix: &Prefix<'_>) -> PrefixVerdict;
}

/// The cycle check, which reads the dependency graph and no node.
///
/// Implements `work/engine/reader.md`, Checker: "The cycle check reads the dependency graph instead."
pub fn check_cycles(graph: &DependencyGraph, program: &ResolvedProgram) -> CheckResult {
    todo!()
}

/// The key of the check cache: the form's canonical hash and the signatures
/// of the names it reads.
///
/// Implements "A form's check result is cached on the form's canonical hash
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

/// The checks of this step, each once.
///
/// Implements `work/engine/reader.md`, Checker: "This step builds the checks that evaluation needs".
pub fn checks() -> &'static [&'static dyn Check] {
    todo!()
}
