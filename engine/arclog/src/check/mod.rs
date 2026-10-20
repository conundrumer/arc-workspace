//! The checker: a set of checks, each over one syntax node and its scope,
//! the declarations visible at that node and the labels of each label scope
//! of its top-level form with their types. The cycle check reads the
//! dependency graph instead.
//!
//! Each check has a form on a prefix, [`Check::check_prefix`], so that a
//! decode can refuse a prefix that no completion passes. [`prefix`] gives
//! the prefixes of a form and runs the checks on one.
//!
//! The checker stage writes the bodies of the checks, each in a submodule of
//! its own.

pub mod grammar;
pub mod safety;
mod inference;
pub mod instance_inputs;
pub mod labels;
pub mod lint;
pub mod pose;
pub mod prefix;
pub mod reads;
pub mod scope;
pub mod site_columns;
pub mod types;
pub mod unfold_reads;

use std::sync::Arc;

use crate::diagnostic::{Diagnostic, DiagnosticKind, Location, Severity};
use crate::hash::StableHashMap;
use crate::program::canonical::{canonical_form, CanonicalForm, CanonicalOrder, CanonicalWriter, SearchBudget};
use crate::program::path::{NodePath, NodeRef};
use crate::program::{Form, LabelId};
use crate::registry::Registry;
use crate::resolver::{DependencyGraph, ResolvedProgram, Signature};
use crate::types::{ProgramTypes, ValueType};

mod clauses;
pub use clauses::{ClauseEntry, FileScope, HeldClauses, SolverClauses};
use clauses::{clause_signature, top_level_forms};

/// The checks this step builds, those that evaluation needs.
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
    /// program it was found in, and the check's [`CheckCacheKey`] holds
    /// their signatures. A clause whose label at that column is
    /// itself one that only `(= *X 0)` gives a type adds no type. The check
    /// refuses the label where no type is above those types.
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
    /// The pose rule: a Pose label stands only at the sites that
    /// `docs/arclog/rigid.md#the-pose` gives.
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

/// The key of the check cache: the check, the form's canonical form, with
/// each name as the file writes it, and the signatures of the names it
/// reads, so the cases that share a form share its check. It compares as a
/// key of canonical parts does ([`crate::program`]).
/// The signatures stand in a fixed order: those of the names the form
/// reads, in the order of each name's first read in the form's canonical
/// order, then the signatures of the clauses that [`CheckId::Types`] reads,
/// as [`types::type_clause_signatures`] gives them. The key of [`CheckId::Cycles`], which
/// reads no form, holds the form of the program's dependency graph with the
/// path of each node's form, and no signature.
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
    /// The types the type check inferred for each label scope of a form, by
    /// the scope's canonical path, under the key of the form's
    /// [`CheckId::Types`] check.
    types: crate::hash::StableHashMap<CheckCacheKey, std::sync::Arc<types::ScopeTypes>>,
}

impl CheckCache {
    /// The result cached under `key`, if any.
    pub fn get(&self, key: &CheckCacheKey) -> Option<&CheckResult> {
        self.entries.get(key)
    }

    /// Caches `result` under `key`.
    pub fn insert(&mut self, key: CheckCacheKey, result: CheckResult) {
        self.entries.insert(key, result);
    }

    /// The types of each label scope of a form, by the scope's canonical
    /// path, cached under `key`, the key of the form's type check.
    pub fn types(&self, key: &CheckCacheKey) -> Option<std::sync::Arc<types::ScopeTypes>> {
        self.types.get(key).cloned()
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
    /// The alerts on the program, such as a body whose canonical form
    /// reached the search cap, which refuse nothing.
    pub alerts: Vec<Diagnostic>,
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
    let mut refused = Vec::new();
    let cycles_key = CheckCacheKey { check: CheckId::Cycles, canonical_form: graph_form(&program), signatures: Box::new([]) };
    if let CheckResult::Refuse(refusals) = cached(cache, cycles_key, || check_cycles(&program.graph, &program)) {
        refused.extend(refusals.iter().map(|r| diagnostic(DiagnosticKind::Check(CheckId::Cycles), Severity::Error, r.message.clone(), r.at.clone())));
    }
    let mut alerts = Vec::new();
    let held = HeldClauses::of(&program);
    let forms: Vec<TopLevelForm<'_>> = top_level_forms(&program)
        .map(|(path, form)| {
            let mut search = SearchBudget::new();
            let (order, canonical) = CanonicalOrder::with_form(form, &mut search);
            if search.reached {
                let message = "the search for the form's canonical form reached its cap".into();
                alerts.push(diagnostic(DiagnosticKind::Bound, Severity::Alert, message, path.clone()));
            }
            let mut signatures = read_signatures(&program, form, &path, &order).into_vec();
            signatures.extend(types::type_clause_signatures(form, &order, clauses, &held).cloned());
            let untyped = labels_in_scopes(&order, &|_, _| None);
            TopLevelForm { path, form, order, canonical, signatures: signatures.into(), untyped }
        })
        .collect();
    let key = |check: CheckId, canonical_form: CanonicalForm, signatures: Box<[Signature]>| CheckCacheKey { check, canonical_form, signatures };
    let mut refused_by_form = vec![Vec::new(); forms.len()];
    let form_types: Vec<Arc<types::ScopeTypes>> = {
        let cases = inference::CaseInferences::new(clauses, registry);
        let inference = inference::Inference::new(&program, &cases);
        let scope = |labels| Scope { program: &program, registry, labels, clauses, inference: &inference };
        let form_types: Vec<Arc<types::ScopeTypes>> = forms
            .iter()
            .zip(&mut refused_by_form)
            .map(|(at, refused)| {
                let input = CheckInput { form: at.form, path: &at.path, scope: scope(&at.untyped) };
                let types_key = key(CheckId::Types, at.canonical.clone(), at.signatures.clone());
                let (result, types) = match (cache.get(&types_key).cloned(), cache.types(&types_key)) {
                    (Some(result), Some(types)) => (result, types),
                    _ => {
                        let (result, types) = types::infer_form(&input, &at.order);
                        let types = Arc::new(types);
                        cache.insert(types_key.clone(), result.clone());
                        cache.insert_types(types_key, Arc::clone(&types));
                        (result, types)
                    }
                };
                at.report(refused, CheckId::Types, &result);
                types
            })
            .collect();
        let labels: Vec<Vec<LabelInScope>> = forms.iter().zip(&form_types).map(|(at, types)| typed_labels(&at.order, types)).collect();
        for ((at, labels), refused) in forms.iter().zip(&labels).zip(&mut refused_by_form) {
            let input = CheckInput { form: at.form, path: &at.path, scope: scope(labels) };
            for check in checks().iter().filter(|check| check.id() != CheckId::Types) {
                let canonical_form = match check.id() {
                    CheckId::Safety => with_written_order(at.form, &at.canonical, &at.order),
                    _ => at.canonical.clone(),
                };
                let check_key = key(check.id(), canonical_form, at.signatures.clone());
                let result = cached(cache, check_key, || check.check(&input));
                at.report(refused, check.id(), &result);
            }
        }
        form_types
    };
    refused.extend(refused_by_form.into_iter().flatten());
    let form_types: Vec<(NodePath, Arc<types::ScopeTypes>, CanonicalOrder)> = forms.into_iter().zip(form_types).map(|(at, types)| (at.path, types, at.order)).collect();
    if !refused.is_empty() {
        return Err(refused);
    }
    let mut types = types::program_types(&program, registry, clauses, &form_types);
    types.set_example_nodes(reads::example_relations(&program));
    Ok(CheckedProgram { program, types, alerts })
}

/// A top-level form of a program, at its path, with its canonical order
/// and form, the signatures of the clauses its checks read, and the labels
/// of each of its label scopes with no types.
struct TopLevelForm<'p> {
    path: NodePath,
    form: &'p Form,
    order: CanonicalOrder,
    canonical: CanonicalForm,
    signatures: Box<[Signature]>,
    untyped: Vec<LabelInScope>,
}

impl TopLevelForm<'_> {
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

/// `canonical`, the canonical form of `form`, followed by the source index
/// of each child of each node of `form`, each node's children in canonical
/// order, so that two forms of one canonical form are equal under it only
/// where their lists are written in one order.
fn with_written_order(form: &Form, canonical: &CanonicalForm, order: &CanonicalOrder) -> CanonicalForm {
    fn write(node: NodeRef<'_>, at: &NodePath, order: &CanonicalOrder, out: &mut CanonicalWriter) {
        let children = node.children();
        for position in 0..children.len() as u32 {
            let child = at.child(position);
            let index = order.source_path(&child).0.last().expect("a child's path ends in its step").0;
            out.write(&index.to_le_bytes());
            write(children[index as usize], &child, order, out);
        }
    }
    let mut out = CanonicalWriter::default();
    out.write(&canonical.bytes);
    write(NodeRef::from(form), &NodePath::default(), order, &mut out);
    out.finish()
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
    static CHECKS: [&dyn Check; 10] = [
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
    ];
    &CHECKS
}
