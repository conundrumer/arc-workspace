//! The checker: a set of checks, each over one syntax node and its scope,
//! the declarations visible at that node, the labels of each label scope
//! of its top-level form with their types, and the files it was read from. The cycle check reads the
//! dependency graph instead.
//!
//! Each check has a form on a prefix, [`Check::check_prefix`], so that a
//! decode can refuse a prefix that no completion passes. [`prefix`] gives
//! the prefixes of a form and runs the checks on one.
//!
//! The checker stage writes the bodies of the checks, each in a submodule of
//! its own.

mod earlier;
mod frames;
mod held_det;
pub use held_det::HeldDetInterfaceError;
pub mod grammar;
pub mod safety;
pub mod render_sites;
pub mod static_prune;
mod inference;
pub mod instance_inputs;
pub mod instance_sites;
pub mod labels;
pub mod lint;
pub mod marks;
pub mod one_clause;
pub mod out;
pub mod picks;
pub mod pose;
pub mod prefix;
pub mod reads;
pub mod rigid_proposer;
pub mod scope;
pub mod site_columns;
pub mod spelling;
pub mod types;
pub mod unfold_reads;
pub mod zero;

use std::sync::{Arc, Mutex};

use crate::eval::ir::{compile_body_in, ClauseIr, CompileFault, CompiledBody, IrPaths, NodeOrder};
use crate::diagnostic::{Diagnostic, DiagnosticKind, Location, Severity};
use crate::hash::StableHashMap;
use crate::program::canonical::{canonical_form, CanonicalForm, CanonicalOrder, CanonicalWriter, LabelingBound, SearchBudget};
use crate::layout::{NodeLayout, SourceFile};
use crate::program::path::{node_at, NodePath, NodeRef, PathStep};
use crate::program::{Form, LabelId, PortName};
use crate::solver::{Case, FileOwner, Solver};
use crate::registry::Registry;
use crate::resolver::{DependencyGraph, GraphNodeIndex, ResolvedContent, ResolvedProgram, Signature};
use crate::stats::{self, Phase};
use crate::types::{ProgramTypes, ValueType};

pub use earlier::EarlierForms;
use earlier::Kept;
mod clauses;
pub use clauses::{ClauseEntry, FileScope, HeldClauses, SolverClauses};
use clauses::{clause_signature, top_level_forms};

/// The checks of the checker: those that evaluation needs, and the checks
/// of the language that synthesis takes from the Python lint
/// (`docs/engine/synthesis.md#checks-moved-from-the-lint`).
#[derive(Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Hash, Debug)]
pub enum CheckId {
    /// The grammar: an s-expression that matches no node kind.
    Grammar,
    /// The scope: a name that resolves to nothing visible.
    Scope,
    /// The columns of each site.
    SiteColumns,
    /// The type check, the comparison typing rule included. The check gives each label of
    /// a body the type that [`crate::types::label_type`] gives it over the
    /// list of the label's scope, and refuses the label where that function
    /// gives a fault. A label that only `(= *X 0)` gives a type takes the type of the instance
    /// input it stands at, or else the join, as
    /// [`crate::types::ValueType::join`] gives it, of the types that the
    /// relation's other clauses in the case program under check give its
    /// column, each read from [`SolverClauses`] and typed in the case
    /// program it was found in. Where the relation has no such clause that
    /// gives a type, the label takes the join of the types that the
    /// relation's clauses in the solver's other case programs give the
    /// column, and no type where those clauses give none or have no join.
    /// The check's [`CheckCacheKey`] holds the signatures of the relation's
    /// clauses in all of the solver's case programs. A clause whose label at
    /// that column is itself one that only `(= *X 0)` gives a type adds no
    /// type. The check refuses the label where no type is above the types of
    /// the case program under check.
    ///
    /// A field of the first projection onto a type parameter of an `INIT`
    /// form, or its single label, whose label only `(= *X 0)` gives a type
    /// takes the join of the types that the later sites onto that parameter
    /// give the same field; the first projection still binds the parameter.
    /// A label of an input's body that a constraint makes equal to a key label
    /// of the form takes the type that the key clause's sites give that
    /// label, as it takes it from a list around the input's body. A read of
    /// `&<instance>.<input>` where the instance writes no clause for that
    /// input resolves to the instance's input, whose rows are the port's
    /// default rows, and takes the port's column types. The check's
    /// [`CheckCacheKey`] holds the form and the signatures it holds already,
    /// since the instance and its reads stand in one top-level form.
    ///
    /// A branch of an `OR`, or the else of an `IF`, that makes a label only
    /// by `(= X 0)`, with the label at no site of an atom in it, adds no
    /// type to the label; the label takes the join of the types that the
    /// other branches give it, and no type where none does.
    ///
    /// The check refuses a clause that gives a column of its relation a
    /// type with no join, as [`crate::types::ValueType::join`] gives it,
    /// with the types that the relation's other clauses in the case program
    /// under check give that column, each read from [`SolverClauses`] and
    /// typed in the case program it was found in, and its [`CheckCacheKey`]
    /// holds those clauses' signatures. A clause of the concept program that
    /// an `ALT` rederives, and the clauses of two `ALT`s that each rederive
    /// the relation, stand in no case program together, so the check joins
    /// no types of theirs.
    /// The refusal stands at the clause's label at that column, or at the
    /// clause where it holds no columns, as a `DET` that gives a proposer
    /// and has no body. A column that the clause's label takes from the
    /// rule on `(= *X 0)` above is that rule's.
    Types,
    /// The pose rule of `docs/arclog/rigid.md#the-pose`.
    PoseRule,
    /// The labels that `=` makes and that an `OR` or an `IF` exports.
    MadeAndExportedLabels,
    /// Safety. The check binds each body by
    /// [`crate::safety::bound_labels`].
    Safety,
    /// The rule of an `Unfold` instance's reads of its outputs.
    UnfoldReads,
    /// Cycles of the dependency graph.
    Cycles,
    /// An instance's input order and defaults.
    InstanceInputs,
    /// The pooled and lifted reads, as `docs/arclog/arclog.md#program`
    /// gives.
    PooledAndLiftedReads,
    /// The rules on `=` and `0` of
    /// `docs/arclog/arclog.md#negation-and-constraints`.
    EqualityAndZero,
    /// The marks a constraint's labels take: `*` only on the first label
    /// of `=`.
    ConstraintMarks,
    /// One clause per relation in a block, the blocks as [`CaseFiles`]
    /// gives them. The check reads the forms before the form under check,
    /// so its result is cached under no [`CheckCacheKey`].
    OneClause,
    /// The sites of an instance's keyed inputs: an input that reads no key
    /// label stands after the key clause.
    InstanceSites,
    /// The spelling of the program form: the names of labels and fields,
    /// and the elision of sites. The check reads the text of the files that
    /// [`CaseFiles`] gives, so a program with no files, as a synthesized
    /// one, passes it but for the names of fields, and its result is
    /// cached under no [`CheckCacheKey`].
    Spelling,
    /// The picks: the labels of a clause's `ONE` marks, and the `never`
    /// bodies of a `CHOOSE` form. The result on a form that holds a clause
    /// with a `ONE` mark that names a label twice, or the set of labels of an
    /// earlier mark of the clause, is cached under no [`CheckCacheKey`],
    /// since the canonical form writes the labels of each mark as a set, and
    /// each such set once.
    Picks,
    /// The reads of the outputs of a `RIGID_DET` form, and the names of a
    /// clause's proposers and their count, and, for a program read from a
    /// solver's files, that the case's reading of each line gives a program
    /// ([`Case::reading_fault`]). The check reads the `RIGID_DET` forms of
    /// the case program, which the form's [`CheckCacheKey`] does not hold, so
    /// its result is cached under no key.
    RigidPartsAndProposers,
    /// The `OUT` form: its atoms, its sites and the types of its columns,
    /// and, for a program read from a solver's files, its place in them and
    /// that the solver holds one. The check reads the other forms of the
    /// case program and the files, so its result is cached under no key.
    Out,
}

/// A label of a label scope within a top-level form, as [`LabelId`] gives
/// scopes, with its inferred type where the type check has given one.
#[derive(Clone, Debug)]
pub struct LabelInScope {
    /// The source path, relative to the top-level form, of the form of the
    /// label scope the label stands in, as
    /// [`crate::program::canonical::CanonicalOrder::label_scopes`] gives it.
    pub scope: NodePath,
    pub label: LabelId,
    pub ty: Option<ValueType>,
}

/// The scope of a node: the declarations visible at it, and the labels of
/// each label scope of its top-level form, as [`LabelId`] gives scopes,
/// with their types.
#[derive(Clone, Copy, Debug)]
pub struct Scope<'a> {
    /// The case program the node stands in.
    pub program: &'a ResolvedProgram,
    /// The registry the program's names resolve against.
    pub registry: &'a Registry,
    /// The labels of each label scope within the top-level form the node
    /// stands in.
    pub labels: &'a [LabelInScope],
    /// The clauses of each relation across the solver's blocks.
    pub clauses: &'a SolverClauses,
    /// The inference of the labels of `program`, over the case programs of
    /// `clauses`, that the checks of one [`check_program`] call share.
    inference: &'a inference::Inference<'a>,
    /// The files that `program` was read from, where it was read from
    /// text.
    pub files: Option<&'a CaseFiles<'a>>,
    /// The bindings of the conjuncts that the safety walk of `program`
    /// shares with the programs that differ from it in an atom of no site
    /// alone, where `program` is one of them.
    bound: Option<safety::BoundMemo<'a>>,
}

/// The files a case program was read from: the case, and the solver whose
/// files hold its forms.
#[derive(Clone, Copy, Debug)]
pub struct CaseFiles<'a> {
    pub solver: &'a Solver,
    pub case: &'a Case,
    /// Whether the files hold a prefix of a solver: whole forms that a
    /// completion may follow.
    pub prefix: bool,
}

impl<'a> CaseFiles<'a> {
    /// The file that holds the node at `path` of the case program, the
    /// solver whose arclog file it is, its own or its representative's, and
    /// the node's path in that file.
    fn file_of(&self, path: &NodePath) -> (FileOwner, &'a Solver, NodePath) {
        let (owner, file_path) = self.case.file_path(path);
        let owning = match owner {
            FileOwner::Solver => self.solver,
            FileOwner::Representative => self.solver.representative.as_deref().expect("a node of the representative's file has a representative"),
        };
        (owner, owning, file_path)
    }

    /// Whether the file writes the node at `path` of the case program as
    /// the program holds it, as [`Case::written_as_held`] gives.
    pub fn writes(&self, path: &NodePath) -> bool {
        self.case.written_as_held(path)
    }

    /// The layout of the node at `path` of the case program, where its
    /// file gives it one.
    fn layout(&self, path: &NodePath) -> Option<&'a NodeLayout> {
        let (_, owning, file_path) = self.file_of(path);
        owning.layout.node(SourceFile::Arclog, &file_path)
    }

    /// The name the file writes for `label` of the label scope whose form
    /// stands at `scope` in the case program.
    fn label_name(&self, scope: &NodePath, label: LabelId) -> Option<&'a str> {
        let names = &self.layout(scope)?.label_names;
        names.iter().find(|(id, _)| *id == label).map(|(_, name)| &**name)
    }

    /// The block of the file that holds the form at `path` of the case
    /// program: the file, and the path there of the innermost `ALT` that
    /// holds the form, or the empty path for the concept program's block.
    fn block(&self, path: &NodePath) -> (FileOwner, NodePath) {
        let (owner, owning, file_path) = self.file_of(path);
        let root = NodeRef::Program(owning.program.value());
        let alt = (0..file_path.0.len()).rev().map(|depth| NodePath(file_path.0[..depth].into())).find(|at| matches!(node_at(root, at), Some(NodeRef::Alt(_))));
        (owner, alt.unwrap_or_default())
    }
}

/// A check's input: one node, its path, and its scope.
#[derive(Clone, Copy, Debug)]
pub struct CheckInput<'a> {
    pub form: &'a Form,
    pub path: &'a NodePath,
    pub scope: Scope<'a>,
}

impl CheckInput<'_> {
    /// The path that a refusal of a check on this input holds for the node
    /// at the source path `at`: its canonical path, as [`Refusal`] gives it,
    /// or in a mask, which reads a refusal's place and no more, `at` itself,
    /// with no canonical order taken.
    pub(crate) fn refusal_path(&self, at: &NodePath) -> NodePath {
        if self.scope.inference.is_mask() {
            return at.clone();
        }
        CanonicalOrder::of(self.form, &mut SearchBudget::new()).canonical_path(at)
    }
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
/// `scope` is the scope of the program whose forms are `complete`, then
/// `partial`, at `path`.
///
/// `open` is the path, relative to `partial`, of the innermost node the
/// decode still writes, or `None` once `partial` is complete. That node and
/// each node above it are open: an open
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
    pub path: &'a NodePath,
    pub open: Option<&'a NodePath>,
    pub scope: Scope<'a>,
}

impl Prefix<'_> {
    /// Whether the node at `at`, a path relative to `partial`, is open.
    pub fn is_open(&self, at: &NodePath) -> bool {
        self.open.is_some_and(|open| open.0.starts_with(&at.0))
    }
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

    /// The key that the check's result on the top-level form of `at` is
    /// cached under, or `None` where the result reads more than a key holds,
    /// so that it is cached under no key.
    fn cache_key(&self, at: &KeyInput<'_>) -> Option<CheckCacheKey>;
}

/// What a check's [`CheckCacheKey`] on a top-level form is built from: the
/// form, its canonical form and order, the signatures of its base key, and
/// the clauses of each relation across the solver's blocks.
#[derive(Clone, Copy, Debug)]
pub struct KeyInput<'a> {
    pub form: &'a Form,
    pub canonical: &'a CanonicalForm,
    pub order: &'a CanonicalOrder,
    /// The signatures of the names the form reads, in the order of each
    /// name's first read in the form's canonical order, then the signatures
    /// of the clauses that [`CheckId::Types`] reads, as
    /// [`types::type_clause_signatures`] gives them.
    pub signatures: &'a [Signature],
    pub clauses: &'a SolverClauses,
}

impl KeyInput<'_> {
    /// The base key of `check` on the form: the form's canonical form and
    /// [`KeyInput::signatures`]. A result holds a refusal's path by places in the
    /// form's lists, so where a list repeats a member, whose canonical form stands
    /// for lists of other lengths, the key holds the written order of the lists too.
    pub fn base(&self, check: CheckId) -> CheckCacheKey {
        let canonical_form = if self.order.repeats() { CanonicalOrder::with_written_lists(self.form) } else { self.canonical.clone() };
        CheckCacheKey { check, canonical_form, signatures: self.signatures.into() }
    }
}

/// The cycle check, which reads the dependency graph and no node. Each
/// refusal's path is relative to the program: the form of a node on the
/// cycle.
pub fn check_cycles(graph: &DependencyGraph, program: &ResolvedProgram) -> CheckResult {
    let Some(cycle) = graph.find_cycle() else {
        return CheckResult::Pass;
    };
    let mut forms: Vec<&NodePath> = Vec::new();
    for node in cycle {
        let form = program.form_of(node);
        if !forms.contains(&form) {
            forms.push(form);
        }
    }
    let refusal = |at: &NodePath| Refusal { message: "the form stands on a cycle of the dependency graph".into(), at: at.clone() };
    CheckResult::Refuse(forms.into_iter().map(refusal).collect())
}

/// The key of the check cache: the check, a canonical form, with each name
/// as the file writes it, and the signatures of the clauses and names the
/// check's result reads, in a fixed order, so the cases that share a form
/// share its check. It compares as a key of canonical parts does
/// ([`crate::program`]). Each check gives its key on a top-level form by
/// [`Check::cache_key`], from the base key that [`KeyInput::base`] gives,
/// and the doc of a check whose key differs from the base key gives what
/// its key adds. The key of [`CheckId::Cycles`], which reads no form, holds
/// the form of the program's dependency graph with the path of each node's
/// form, and no signature.
#[derive(Clone, PartialEq, Eq, Hash, Debug)]
pub struct CheckCacheKey {
    pub check: CheckId,
    pub canonical_form: crate::program::canonical::CanonicalForm,
    pub signatures: Box<[Signature]>,
}

/// The check results of the forms checked so far, by
/// [`CheckCacheKey`], so that the cases that share a form share its check.
#[derive(Clone, Debug, Default)]
pub struct CheckCache {
    /// An immutable gold-only base, shared by temporary mutation searches.
    /// Candidate-specific results remain in the requesting search's overlay.
    base: Option<Arc<CheckCache>>,
    entries: crate::hash::StableHashMap<CheckCacheKey, CheckResult>,
    /// The types the type check inferred for each label scope of a form, by
    /// the scope's canonical path, under the key of the form's
    /// [`CheckId::Types`] check.
    types: crate::hash::StableHashMap<CheckCacheKey, std::sync::Arc<types::ScopeTypes>>,
}

/// The most bases under a [`CheckCache`] that [`CheckCache::fork`] leaves.
const CACHE_LAYERS: usize = 8;

impl CheckCache {
    pub(crate) fn over(base: Arc<Self>) -> Self {
        Self { base: Some(base), ..Self::default() }
    }

    /// A cache that holds what this one holds. Both read it from one shared
    /// base, so the call copies no entry, other than each [`CACHE_LAYERS`]
    /// forks, which put the bases of this cache together.
    pub(crate) fn fork(&mut self) -> Self {
        if self.entries.is_empty() && self.types.is_empty() {
            return Self { base: self.base.clone(), ..Self::default() };
        }
        if self.layers() >= CACHE_LAYERS {
            *self = self.flat();
        }
        let held = Arc::new(std::mem::take(self));
        *self = Self::over(Arc::clone(&held));
        Self::over(held)
    }

    /// The count of bases under this cache.
    fn layers(&self) -> usize {
        self.base.as_ref().map_or(0, |base| 1 + base.layers())
    }

    /// A cache with no base that holds what this one holds.
    fn flat(&self) -> Self {
        let mut flat = self.base.as_ref().map_or_else(Self::default, |base| base.flat());
        flat.entries.extend(self.entries.iter().map(|(key, result)| (key.clone(), result.clone())));
        flat.types.extend(self.types.iter().map(|(key, types)| (key.clone(), Arc::clone(types))));
        flat
    }

    /// The result cached under `key`, if any.
    pub fn get(&self, key: &CheckCacheKey) -> Option<&CheckResult> {
        self.entries.get(key).or_else(|| self.base.as_ref()?.get(key))
    }

    /// Caches `result` under `key`.
    pub fn insert(&mut self, key: CheckCacheKey, result: CheckResult) {
        self.entries.insert(key, result);
    }

    /// The types of each label scope of a form, by the scope's canonical
    /// path, cached under `key`, the key of the form's type check.
    pub fn types(&self, key: &CheckCacheKey) -> Option<std::sync::Arc<types::ScopeTypes>> {
        self.types.get(key).cloned().or_else(|| self.base.as_ref()?.types(key))
    }

    /// Caches `types`, the types of each label scope of a form by the
    /// scope's canonical path, under `key`, the key of the form's type check.
    pub fn insert_types(&mut self, key: CheckCacheKey, types: std::sync::Arc<types::ScopeTypes>) {
        self.types.insert(key, types);
    }
}

/// A case program that every check passes, with the types the type check
/// inferred for it. Each evaluator entry point takes one, so it runs only a
/// checked program.
#[derive(Clone, Debug)]
pub struct CheckedProgram {
    pub program: Arc<ResolvedProgram>,
    pub types: ProgramTypes,
    /// What the evaluator derives from the program alone, shared by its
    /// clones.
    derived: Arc<Derived>,
}

/// The clause of an `INIT` form's input or key, with the paths of its nodes
/// and the count of its key columns.
pub type InstanceClause = (Arc<ClauseIr>, Arc<IrPaths>, usize);

/// The clause of a `RIGID_DET` form's key and instance bodies, joined with
/// the atom of one part where it is given, with the paths of its nodes.
pub type AssemblyClause = (Arc<ClauseIr>, Arc<IrPaths>);

/// What a function of a checked program, a path and its arguments alone
/// gives, kept per argument on the first ask.
#[derive(Debug, Default)]
struct Derived {
    /// The result of [`crate::eval::ir::compile_body_in`] for each clause
    /// path, kept conjuncts and order of the nodes.
    bodies: Mutex<StableHashMap<(NodePath, Box<[u32]>, NodeOrder), Result<Arc<CompiledBody>, CompileFault>>>,
    /// The clause of an `INIT` form's input, or of its key where the name
    /// is `None`, with the paths of its nodes and the count of its key
    /// columns, as the evaluator compiles it.
    instance_clauses: Mutex<StableHashMap<(NodePath, Option<PortName>), Result<InstanceClause, CompileFault>>>,
    /// The clause of a `RIGID_DET` form's key and instance bodies, joined
    /// with the atom at the path of a part where it is given, with the
    /// paths of its nodes, as the evaluator compiles it.
    assembly_clauses: Mutex<StableHashMap<(NodePath, Option<NodePath>), Result<AssemblyClause, CompileFault>>>,
    /// The resolved content of the clause at each path.
    contents: Mutex<StableHashMap<NodePath, Option<ResolvedContent>>>,
    /// The resolved content of the part of the clause at a path that its
    /// conjuncts and columns make, with its columns in order.
    parts: Mutex<StableHashMap<(NodePath, Box<[u32]>, Box<[LabelId]>), Option<(ResolvedContent, Box<[LabelId]>)>>>,
}

impl CheckedProgram {
    /// This program over `program`, a resolution of the same forms that keeps
    /// fewer columns of the `DET` nodes `nodes` than the resolution of this
    /// one ([`ResolvedProgram::narrowed_to_closure`] gives it), which is to be
    /// evaluated and not checked: the types of the labels are those of this
    /// program, which the checks of its forms gave, and the types of the
    /// columns of `nodes` and the nodes with an Example column are those
    /// that `program` has. What the evaluator derives from the program is
    /// made again.
    pub(crate) fn over_narrowed(&self, program: Arc<ResolvedProgram>, nodes: &[GraphNodeIndex]) -> CheckedProgram {
        let _timed = stats::span(Phase::CheckNarrowed);
        let mut types = types::narrowed_types(&program, &self.types, nodes);
        types.set_example_nodes(reads::example_relations(&program));
        CheckedProgram { program, types, derived: Arc::default() }
    }

    /// The result of `compile_body` for the conjuncts at `kept` of the body
    /// of the clause at `clause`, compiled on the first ask, with the nodes
    /// in the order the conjuncts are written.
    pub fn compiled_body(&self, clause: &NodePath, kept: &[u32]) -> Result<Arc<CompiledBody>, CompileFault> {
        self.compiled_body_in(clause, kept, NodeOrder::Written)
    }

    /// The body that the evaluator joins for the conjuncts at `kept` of the
    /// body of the clause at `clause`: as [`CheckedProgram::compiled_body`],
    /// with the nodes in canonical order, compiled on the first ask. Its
    /// paths and conjuncts stand in the same order.
    pub fn joined_body(&self, clause: &NodePath, kept: &[u32]) -> Result<Arc<CompiledBody>, CompileFault> {
        self.compiled_body_in(clause, kept, NodeOrder::Canonical)
    }

    fn compiled_body_in(&self, clause: &NodePath, kept: &[u32], order: NodeOrder) -> Result<Arc<CompiledBody>, CompileFault> {
        let key = (clause.clone(), Box::<[u32]>::from(kept), order);
        let mut memo = self.derived.bodies.lock().expect("a memo that no panic poisoned");
        memo.entry(key).or_insert_with(|| compile_body_in(self, clause, kept, order).map(Arc::new)).clone()
    }

    /// The clause of the input `input` of the `INIT` form at `form`, or of
    /// its key where `input` is `None`, with the paths of its nodes and the
    /// count of its key columns, from `compile` on the first ask.
    pub fn instance_clause(
        &self,
        form: &NodePath,
        input: Option<&PortName>,
        compile: impl FnOnce() -> Result<(ClauseIr, IrPaths, usize), CompileFault>,
    ) -> Result<InstanceClause, CompileFault> {
        let key = (form.clone(), input.cloned());
        let mut memo = self.derived.instance_clauses.lock().expect("a memo that no panic poisoned");
        memo.entry(key).or_insert_with(|| compile().map(|(clause, paths, key)| (Arc::new(clause), Arc::new(paths), key))).clone()
    }

    /// The clause of the `RIGID_DET` form at `form`: its key and instance
    /// bodies, joined with the atom at `part` where it is given, with the
    /// paths of its nodes, from `compile` on the first ask.
    pub fn assembly_clause(
        &self,
        form: &NodePath,
        part: Option<&NodePath>,
        compile: impl FnOnce() -> Result<(ClauseIr, IrPaths), CompileFault>,
    ) -> Result<AssemblyClause, CompileFault> {
        let key = (form.clone(), part.cloned());
        let mut memo = self.derived.assembly_clauses.lock().expect("a memo that no panic poisoned");
        memo.entry(key).or_insert_with(|| compile().map(|(clause, paths)| (Arc::new(clause), Arc::new(paths)))).clone()
    }

    /// The resolved content of the clause at `path`, as
    /// [`ResolvedProgram::content`] gives it.
    pub fn content(&self, path: &NodePath) -> Option<ResolvedContent> {
        let mut memo = self.derived.contents.lock().expect("a memo that no panic poisoned");
        memo.entry(path.clone()).or_insert_with(|| self.program.content(path)).clone()
    }

    /// The content of a part of the clause at `clause`, as
    /// [`ResolvedProgram::part_content`] gives it.
    pub fn part_content(&self, clause: &NodePath, conjuncts: &[u32], columns: &[LabelId]) -> Option<(ResolvedContent, Box<[LabelId]>)> {
        let key = (clause.clone(), Box::<[u32]>::from(conjuncts), Box::<[LabelId]>::from(columns));
        let mut memo = self.derived.parts.lock().expect("a memo that no panic poisoned");
        memo.entry(key).or_insert_with(|| self.program.part_content(clause, conjuncts, columns)).clone()
    }
}

/// Runs every check of [`checks`] over each form of `program`, and the
/// cycle check, through `cache`, and gives the checked program, or each
/// diagnostic where a check refuses. It maps each refusal's path, which a
/// [`Refusal`] holds in the form's canonical order, to the form's source
/// order through [`crate::program::canonical::CanonicalOrder`], and each
/// cached [`crate::types::FormTypes`], by its label scope's canonical path
/// and with each label its canonical position in that scope, to the scope's
/// source path and its own labels in the same way. Each diagnostic's
/// location is a [`crate::diagnostic::Location::Path`] in
/// `program`.
pub fn check_program(
    program: ResolvedProgram,
    clauses: &SolverClauses,
    registry: &Registry,
    cache: &mut CheckCache,
) -> Result<CheckedProgram, Vec<Diagnostic>> {
    check_shared_program(Arc::new(program), clauses, registry, cache)
}

/// [`check_program`] over a program that others hold as well, such as a
/// case program of [`crate::resolver::ResolvedCases`].
pub fn check_shared_program(
    program: Arc<ResolvedProgram>,
    clauses: &SolverClauses,
    registry: &Registry,
    cache: &mut CheckCache,
) -> Result<CheckedProgram, Vec<Diagnostic>> {
    check_program_of_files(program, clauses, registry, cache, None)
}

/// [`check_shared_program`] over a program read from `files`, which
/// [`CheckId::OneClause`], [`CheckId::Spelling`] and the `OUT` form checks
/// of [`CheckId::Out`] read. The refusal of a program with no `OUT` form
/// is of a program read whole, so it does not run where `files.prefix`.
pub fn check_program_of_files(
    program: Arc<ResolvedProgram>,
    clauses: &SolverClauses,
    registry: &Registry,
    cache: &mut CheckCache,
    files: Option<&CaseFiles<'_>>,
) -> Result<CheckedProgram, Vec<Diagnostic>> {
    check_program_with_open(program, clauses, registry, cache, files, None, None)
}

/// [`check_shared_program`] over a program whose forms before its last are
/// the finished forms that `earlier` serves: its resolution is
/// [`crate::resolver::resolve_last`]'s over the resolution of those forms,
/// which gives each read of theirs the signature it has in the program, and
/// `clauses` holds those forms' clauses. The check reads from `earlier`
/// what it reads of each of those forms in every such program, and holds in
/// it what it reads there the first time.
pub fn check_shared_program_over(
    program: Arc<ResolvedProgram>,
    clauses: &SolverClauses,
    registry: &Registry,
    cache: &mut CheckCache,
    earlier: &EarlierForms,
) -> Result<CheckedProgram, Vec<Diagnostic>> {
    check_program_with_open(program, clauses, registry, cache, None, None, Some(earlier))
}

/// Check and type an unfinished contextual query with the decoder's prefix checks.
/// Earlier forms are complete; `open` is relative to the final form.
pub fn check_shared_open_program(
    program: Arc<ResolvedProgram>, clauses: &SolverClauses, registry: &Registry,
    cache: &mut CheckCache, open: &NodePath,
) -> Result<CheckedProgram, Vec<Diagnostic>> {
    check_program_with_open(program, clauses, registry, cache, None, Some(open), None)
}

fn check_program_with_open(
    program: Arc<ResolvedProgram>, clauses: &SolverClauses, registry: &Registry,
    cache: &mut CheckCache, files: Option<&CaseFiles<'_>>, open: Option<&NodePath>, earlier: Option<&EarlierForms>,
) -> Result<CheckedProgram, Vec<Diagnostic>> {
    let _timed = stats::span(Phase::CheckProgram);
    let mut refused = Vec::new();
    let cycles_key = CheckCacheKey { check: CheckId::Cycles, canonical_form: graph_form(&program), signatures: Box::new([]) };
    if let CheckResult::Refuse(refusals) = cached(cache, cycles_key, || check_cycles(&program.graph, &program)) {
        refused.extend(refusals.iter().map(|r| diagnostic(DiagnosticKind::Check(CheckId::Cycles), Severity::Error, r.message.clone(), r.at.clone())));
    }
    if let Some(files) = files {
        let missing = if files.prefix { None } else { out::missing(program.program.value()) };
        let refusals = [missing, out::several(files.case, program.program.value())];
        for refusal in refusals.into_iter().flatten() {
            refused.push(diagnostic(DiagnosticKind::Check(CheckId::Out), Severity::Error, refusal.message, refusal.at));
        }
        if let Some(refusal) = rigid_proposer::reading_fault(files.case, program.program.value()) {
            refused.push(diagnostic(DiagnosticKind::Check(CheckId::RigidPartsAndProposers), Severity::Error, refusal.message, refusal.at));
        }
    }
    let mut labeling_bounds = Vec::new();
    let held = clauses.held_of(&program).unwrap_or_else(|| Arc::new(HeldClauses::of(&program)));
    // A cycle leaves the order that forms are inferred in to the checks, which a form kept from another program was not under.
    let earlier = earlier.filter(|_| refused.is_empty() && files.is_none() && open.is_none());
    let last = program.program.value().forms.len().saturating_sub(1) as u32;
    let forms: Vec<TopLevelForm<'_>> = top_level_forms(&program)
        .zip(0u32..)
        .map(|((path, form), index)| {
            let mut search = SearchBudget::new();
            let (order, canonical) = CanonicalOrder::with_form(form, &mut search);
            // The last form of a prefix is in progress, and its labeling may pass the cap only because it is not complete.
            if search.reached && (open.is_none() || index != last) {
                labeling_bounds.push(diagnostic(DiagnosticKind::Bound, Severity::Error, LabelingBound::at_cap().to_string().into(), path.clone()));
            }
            // The signatures that the program's resolution gives the reads of a form before the last are those of the finished forms'.
            let kept = earlier.filter(|_| index < last).map(|earlier| earlier.form(index));
            let reads = || read_signatures(&program, form, &path, order);
            let mut signatures = match &kept {
                Some(kept) => kept.reads.get_or_init(reads).to_vec(),
                None => reads().into_vec(),
            };
            signatures.extend(types::type_clause_signatures(form, order, clauses, &held).cloned());
            let untyped = || -> Arc<[LabelInScope]> { labels_in_scopes(order, &|_, _| None).into() };
            let untyped = match &kept {
                Some(kept) => Arc::clone(kept.untyped.get_or_init(untyped)),
                None => untyped(),
            };
            let zero: Box<[Signature]> = if kept.is_some() { zero::zero_clause_signatures(form, clauses).cloned().collect() } else { Box::new([]) };
            let at = TopLevelForm { path, form, order, canonical, signatures: signatures.into(), untyped, zero, earlier: None, kept: None };
            match kept {
                Some(held) if *held.alone.get_or_init(|| earlier::alone(form)) => {
                    let kept = held.kept(&at.signatures, &at.zero);
                    TopLevelForm { earlier: Some(held), kept, ..at }
                }
                _ => at,
            }
        })
        .collect();
    stats::units(Phase::CheckProgram, forms.len());
    let mut refused_by_form = vec![Vec::new(); forms.len()];
    let mut kept_forms: Vec<Option<Arc<Kept>>> = vec![None; forms.len()];
    let form_types: Vec<Arc<types::ScopeTypes>> = {
        let cases = inference::CaseInferences::new(clauses, registry);
        let inference = inference::Inference::new(&program, &cases);
        let scope = |labels| Scope { program: &program, registry, labels, clauses, inference: &inference, files, bound: None };
        let form_types: Vec<Arc<types::ScopeTypes>> = forms
            .iter()
            .zip(&mut refused_by_form)
            .map(|(at, refused)| {
                if let Some(kept) = &at.kept {
                    refused.extend(kept.refused.iter().cloned());
                    return Arc::clone(&kept.types);
                }
                let input = CheckInput { form: at.form, path: &at.path, scope: scope(&at.untyped) };
                let infer = || {
                    let (result, types) = types::infer_form(&input, at.order);
                    (result, Arc::new(types))
                };
                let (result, types) = match types::TypesCheck.cache_key(&at.key_input(clauses)) {
                    None => infer(),
                    Some(types_key) => match (cache.get(&types_key).cloned(), cache.types(&types_key)) {
                        (Some(result), Some(types)) => (result, types),
                        _ => {
                            stats::tick(Phase::CheckCacheMiss);
                            let (result, types) = infer();
                            cache.insert(types_key.clone(), result.clone());
                            cache.insert_types(types_key, Arc::clone(&types));
                            (result, types)
                        }
                    },
                };
                if open.is_none() || at.path != NodePath::top(forms.len() as u32 - 1) {
                    at.report(refused, CheckId::Types, &result);
                }
                types
            })
            .collect();
        let labels: Vec<Arc<[LabelInScope]>> = forms
            .iter()
            .zip(&form_types)
            .map(|(at, types)| match &at.kept {
                Some(kept) => Arc::clone(&kept.labels),
                None => typed_labels(at.order, types).into(),
            })
            .collect();
        for ((at, labels), refused) in forms.iter().zip(&labels).zip(&mut refused_by_form) {
            if open.is_some() && at.path == NodePath::top(forms.len() as u32 - 1) { continue; }
            if at.kept.is_some() { continue; }
            let input = CheckInput { form: at.form, path: &at.path, scope: scope(labels) };
            for check in checks().iter().filter(|check| check.id() != CheckId::Types) {
                let result = match check.cache_key(&at.key_input(clauses)) {
                    None => check.check(&input),
                    Some(key) => cached(cache, key, || check.check(&input)),
                };
                at.report(refused, check.id(), &result);
            }
        }
        for (((at, types), labels), (refused, kept)) in forms.iter().zip(&form_types).zip(&labels).zip(refused_by_form.iter().zip(&mut kept_forms)) {
            *kept = match (&at.earlier, &at.kept) {
                (Some(earlier), None) => {
                    let kept = Arc::new(Kept {
                        signatures: at.signatures.clone(),
                        zero: at.zero.clone(),
                        types: Arc::clone(types),
                        labels: Arc::clone(labels),
                        refused: refused.clone(),
                        scopes: Default::default(),
                    });
                    earlier.keep(Arc::clone(&kept));
                    Some(kept)
                }
                (_, kept) => kept.clone(),
            };
        }
        form_types
    };
    refused.extend(refused_by_form.into_iter().flatten());
    refused.extend(labeling_bounds);
    if let Some(open) = open {
        let path = NodePath::top(forms.len() as u32 - 1);
        for (check, result) in prefix::check_prefix(&program, clauses, registry, Some(open)) {
            if let PrefixResult::Refuse(refusals) = result {
                refused.extend(refusals.iter().map(|r| diagnostic(
                    DiagnosticKind::Check(check), Severity::Error, r.message.clone(), path.join(&r.at))));
            }
        }
    }
    let form_types: Vec<types::FormScopes<'_>> = forms
        .into_iter()
        .zip(form_types)
        .zip(kept_forms)
        .map(|((at, types), kept)| types::FormScopes { path: at.path, scopes: types, order: at.order, kept })
        .collect();
    if !refused.is_empty() {
        return Err(refused);
    }
    let mut types = types::program_types(&program, registry, clauses, &form_types);
    types.set_example_nodes(reads::example_relations(&program));
    Ok(CheckedProgram { program, types, derived: Arc::default() })
}

/// A top-level form of a program, at its path, with its canonical order
/// and form, the signatures of the clauses its checks read, and the labels
/// of each of its label scopes with no types.
struct TopLevelForm<'p> {
    path: NodePath,
    form: &'p Form,
    order: &'p CanonicalOrder,
    canonical: &'p CanonicalForm,
    signatures: Box<[Signature]>,
    untyped: Arc<[LabelInScope]>,
    /// The signatures of the clauses of the form's relation that the check of
    /// [`CheckId::EqualityAndZero`] reads, for a form before the last of a
    /// program that [`EarlierForms`] serves.
    zero: Box<[Signature]>,
    /// What the check of the form keeps, where the form stands before the
    /// last of such a program and its checks read it alone.
    earlier: Option<Arc<earlier::EarlierForm>>,
    /// What the checks gave on the form, where that form kept it for keys
    /// like these.
    kept: Option<Arc<Kept>>,
}

impl TopLevelForm<'_> {
    /// What the checks' cache keys on the form are built from, with
    /// `clauses`, the clauses of each relation across the solver's blocks.
    fn key_input<'a>(&'a self, clauses: &'a SolverClauses) -> KeyInput<'a> {
        KeyInput { form: self.form, canonical: self.canonical, order: self.order, signatures: &self.signatures, clauses }
    }

    /// Pushes onto `refused` a diagnostic of `check` for each refusal of
    /// `result`, at its path in the form's source order.
    fn report(&self, refused: &mut Vec<Diagnostic>, check: CheckId, result: &CheckResult) {
        if let CheckResult::Refuse(refusals) = result {
            for refusal in refusals.iter() {
                let at = self.path.join(&self.order.source_path(&refusal.at));
                refused.push(diagnostic(DiagnosticKind::Check(check), Severity::Error, refusal.message.clone(), at));
            }
        }
    }
}

/// The labels of each label scope that `order` gives, each with the type
/// `ty` gives at its scope's source path and its canonical position there.
fn labels_in_scopes(order: &CanonicalOrder, ty: &dyn Fn(&NodePath, u32) -> Option<ValueType>) -> Vec<LabelInScope> {
    let each = |(scope, labels): &(NodePath, &[(LabelId, u32)])| {
        labels.iter().map(|&(label, position)| LabelInScope { scope: scope.clone(), label, ty: ty(scope, position) }).collect::<Vec<_>>()
    };
    order.label_scopes().iter().flat_map(each).collect()
}

/// The labels of each label scope that `order` gives, each with the type
/// that `types`, the type check's types of the form, give it.
fn typed_labels(order: &CanonicalOrder, types: &types::ScopeTypes) -> Vec<LabelInScope> {
    let typed: StableHashMap<NodePath, &crate::types::FormTypes> = types.iter().map(|(canonical, types)| (order.source_path(canonical), types)).collect();
    labels_in_scopes(order, &|scope, position| {
        let types = typed.get(scope).expect("the type check gives the types of each label scope of the form");
        types.label(LabelId(position)).cloned()
    })
}

/// The result cached under `key`, or else the result of `run`, which it
/// caches there.
fn cached(cache: &mut CheckCache, key: CheckCacheKey, run: impl FnOnce() -> CheckResult) -> CheckResult {
    if let Some(result) = cache.get(&key) {
        return result.clone();
    }
    stats::tick(Phase::CheckCacheMiss);
    let result = run();
    cache.insert(key, result.clone());
    result
}

/// The form of the dependency graph of `program`: for each node, the path
/// of its form and the nodes it reads. Two programs of one such form give
/// one result of [`check_cycles`], whose refusals are paths of the program.
fn graph_form(program: &ResolvedProgram) -> CanonicalForm {
    let mut out = CanonicalWriter::default();
    let len = |out: &mut CanonicalWriter, len: usize| out.write(&(len as u32).to_le_bytes());
    len(&mut out, program.graph.reads.len());
    for (reads, index) in program.graph.reads.iter().zip(0u32..) {
        let form = program.form_of(crate::resolver::GraphNodeIndex(index));
        len(&mut out, form.0.len());
        for step in form.0.iter() {
            out.write(&step.0.to_le_bytes());
        }
        len(&mut out, reads.len());
        for read in reads.iter() {
            out.write(&read.0.to_le_bytes());
        }
    }
    out.finish()
}

fn diagnostic(kind: DiagnosticKind, severity: Severity, message: Box<str>, at: NodePath) -> Diagnostic {
    Diagnostic { kind, severity, message, location: Location::Path(at), cases: Box::new([]) }
}

/// The signatures of the names `form`, at `path` in `program`, reads, in
/// the order of each name's first read in the form's canonical order.
fn read_signatures(program: &ResolvedProgram, form: &Form, path: &NodePath, order: &CanonicalOrder) -> Box<[Signature]> {
    fn collect<'a>(program: &'a ResolvedProgram, node: NodeRef<'_>, form_path: &NodePath, at: NodePath, order: &CanonicalOrder, out: &mut Vec<(NodePath, &'a Signature)>) {
        if let Some(signature) = program.signature(&form_path.join(&at)) {
            out.push((order.canonical_path(&at), signature));
        }
        for (child, index) in node.children().into_iter().zip(0u32..) {
            collect(program, child, form_path, at.child(index), order, out);
        }
    }
    let mut reads = Vec::new();
    collect(program, NodeRef::from(form), path, NodePath::default(), order, &mut reads);
    reads.sort_by(|(a, _), (b, _)| a.cmp(b));
    let mut signatures: Vec<Signature> = Vec::new();
    for (_, signature) in reads {
        if !signatures.contains(signature) {
            signatures.push(signature.clone());
        }
    }
    signatures.into()
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
    static CHECKS: [&dyn Check; 18] = [
        &grammar::GrammarCheck,
        &scope::ScopeCheck,
        &site_columns::SiteColumnsCheck,
        &types::TypesCheck,
        &pose::PoseRuleCheck,
        &labels::MadeAndExportedLabelsCheck,
        &safety::SafetyCheck,
        &unfold_reads::UnfoldReadsCheck,
        &instance_inputs::InstanceInputsCheck,
        &reads::PooledAndLiftedReadsCheck,
        &zero::EqualityAndZeroCheck,
        &marks::ConstraintMarksCheck,
        &one_clause::OneClauseCheck,
        &instance_sites::InstanceSitesCheck,
        &spelling::SpellingCheck,
        &picks::PicksCheck,
        &rigid_proposer::RigidPartsAndProposersCheck,
        &out::OutCheck,
    ];
    &CHECKS
}

/// Visits `node`, at `at`, and each node below it, in source order, each
/// with its path.
fn each_node<'a>(node: NodeRef<'a>, at: &NodePath, visit: &mut dyn FnMut(NodeRef<'a>, &[PathStep])) {
    fn walk<'a>(node: NodeRef<'a>, at: &mut Vec<PathStep>, visit: &mut dyn FnMut(NodeRef<'a>, &[PathStep])) {
        visit(node, at);
        let mut index = 0;
        node.each_handle(|handle| {
            at.push(PathStep(index));
            walk(handle.node(), at, visit);
            at.pop();
            index += 1;
            std::ops::ControlFlow::Continue(())
        });
    }
    walk(node, &mut at.0.to_vec(), visit);
}
