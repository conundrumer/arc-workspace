//! The checker: a set of checks, each over one syntax node and its scope,
//! the declarations, labels and types visible at that node. The cycle check
//! reads the dependency graph instead.
//!
//! Each check has a form on a prefix, [`Check::check_prefix`], so that a
//! decode can refuse a prefix that no completion passes. Until step 6 builds
//! the prefix forms, each check's `check_prefix` gives
//! [`PrefixResult::Undecided`].
//!
//! The checker stage writes the bodies of the checks, each in a submodule of
//! its own.

pub mod grammar;
pub mod grounding;
pub mod instance_inputs;
pub mod labels;
pub mod lint;
pub mod pose;
pub mod reads;
pub mod scope;
pub mod site_columns;
pub mod types;
pub mod unfold_reads;

use std::sync::Arc;

use crate::diagnostic::{Diagnostic, DiagnosticKind, Location, Severity};
use crate::program::canonical::{
    canonical_form, canonical_labeling, form_scope, AsWritten, CanonicalForm, CanonicalOrder, CanonicalWriter, SearchBudget,
};
use crate::program::path::{NodePath, NodeRef, PathStep};
use crate::program::{Form, LabelId, ProgramRelation};
use crate::registry::Registry;
use crate::resolver::{ConceptReads, DependencyGraph, MacroExpansion, ResolvedProgram, Signature};
use crate::solver::{Exclusion, FileOwner};
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
    ///
    /// Under [`crate::resolver::MacroExpansion::Expand`], where the meet of a
    /// label's type, from the label's sites outside a part of the expansion,
    /// and the types of its sites in that part is empty, that part holds
    /// nothing. A part is the body that takes the atom's place, a branch of
    /// an `OR`, or a list of an `IF`, wherever it stands in that body. Each
    /// macro's column types are its definition's, a relation macro's columns
    /// and modes and a cell instance's outputs, as
    /// [`crate::registry::macro_column_types`] gives them, so a program that
    /// passes the checks under `Keep` passes them under `Expand`.
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

/// One clause of a relation in [`SolverClauses`]: its file, its path there,
/// and its signature.
type ClauseEntry = (FileOwner, NodePath, Signature);

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
        let derived = solver.derived_relations();
        let concept_case = solver.concept_case();
        let concept = crate::resolver::resolve(&concept_case.program, None, &derived, registry, MacroExpansion::Keep).value;
        let mut found = ClausesFound::default();
        found.add(&concept, &|path| concept_case.file_path(path));
        for case in solver.cases(Exclusion::WithExcluded) {
            if case.name == concept_case.name {
                continue;
            }
            let reads = ConceptReads { concept: &concept, determinations: case.concept_determinations() };
            let resolved = crate::resolver::resolve(&case.program, Some(reads), &derived, registry, MacroExpansion::Keep).value;
            found.add(&resolved, &|path| case.file_path(path));
        }
        found.ordered()
    }

    /// The clauses of a synthesized program, its own.
    pub fn of_program(program: &ResolvedProgram) -> Self {
        let mut found = ClausesFound::default();
        found.add(program, &|path| (FileOwner::Solver, path.clone()));
        found.ordered()
    }

    /// Each clause of `relation` in the name scope `scope`, by its file and
    /// its path there, with its signature, in the order [`SolverClauses`]
    /// gives.
    pub fn of_relation(
        &self,
        scope: &FileScope,
        relation: &crate::program::ProgramRelation,
    ) -> &[(crate::solver::FileOwner, NodePath, Signature)] {
        self.clauses.get(&(scope.clone(), relation.clone())).map_or(&[], |entries| &entries[..])
    }
}

/// The clauses [`SolverClauses`] gathers, each once, before they are put in
/// its order.
#[derive(Default)]
struct ClausesFound {
    clauses: crate::hash::StableHashMap<(FileScope, ProgramRelation), Vec<ClauseEntry>>,
}

impl ClausesFound {
    /// Adds each clause of `program`, at the top level and in each
    /// `DEMO_RULE` form, with its file and its path there as `file_path`
    /// gives them for its path in `program`.
    fn add(&mut self, program: &ResolvedProgram, file_path: &dyn Fn(&NodePath) -> (FileOwner, NodePath)) {
        for (path, form) in top_level_forms(program) {
            match form {
                Form::Clause(clause) => self.add_clause(program, file_path, FileScope::Program, &clause.value().derives, &path),
                Form::Demonstrated(demonstrated) => {
                    let demonstrated = demonstrated.value();
                    let first_rule = demonstrated.key.iter().count() + demonstrated.inputs.len();
                    for (index, rule) in demonstrated.rules.iter().enumerate() {
                        let rule_path = path.child((first_rule + index) as u32);
                        let (owner, file_rule_path) = file_path(&rule_path);
                        for (index, form) in rule.value().forms.iter().enumerate() {
                            if let Form::Clause(clause) = form {
                                let scope = FileScope::DemoRule(owner, file_rule_path.clone());
                                self.add_clause(program, file_path, scope, &clause.value().derives, &rule_path.child(index as u32));
                            }
                        }
                    }
                }
                _ => {}
            }
        }
    }

    fn add_clause(
        &mut self,
        program: &ResolvedProgram,
        file_path: &dyn Fn(&NodePath) -> (FileOwner, NodePath),
        scope: FileScope,
        relation: &ProgramRelation,
        path: &NodePath,
    ) {
        let (owner, file) = file_path(path);
        let content = program.content(path).expect("a clause of the program has its resolved content");
        let mut out = CanonicalWriter::default();
        out.write(&content.content_hash().0.to_le_bytes());
        let entry = (owner, file, Signature(out.finish()));
        let entries = self.clauses.entry((scope, relation.clone())).or_default();
        if !entries.contains(&entry) {
            entries.push(entry);
        }
    }

    /// The clauses, each key's entries in the order [`SolverClauses`] gives.
    fn ordered(self) -> SolverClauses {
        let rank = |owner: &FileOwner| match owner {
            FileOwner::Solver => 0,
            FileOwner::Representative => 1,
        };
        let clauses = self
            .clauses
            .into_iter()
            .map(|(key, mut entries)| {
                entries.sort_by(|(a, a_path, _), (b, b_path, _)| (rank(a), a_path).cmp(&(rank(b), b_path)));
                (key, entries.into_boxed_slice())
            })
            .collect();
        SolverClauses { clauses }
    }
}

/// Each top-level form of `program`, with its path.
fn top_level_forms(program: &ResolvedProgram) -> impl Iterator<Item = (NodePath, &Form)> {
    let forms = program.program.value().forms.iter();
    forms.zip(0u32..).map(|(form, index)| (NodePath(Box::new([PathStep(index)])), form))
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
/// order, then, where a label's type comes from other clauses of a
/// relation, as [`CheckId::Types`] gives, those clauses' signatures, in the
/// order [`SolverClauses`] gives. The key of [`CheckId::Cycles`], which
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
    /// The types the type check inferred for a form, under the key of its
    /// [`CheckId::Types`] check.
    types: crate::hash::StableHashMap<CheckCacheKey, std::sync::Arc<crate::types::FormTypes>>,
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

    /// The types cached under `key`, the key of a form's type check.
    pub fn types(&self, key: &CheckCacheKey) -> Option<std::sync::Arc<crate::types::FormTypes>> {
        self.types.get(key).cloned()
    }

    /// Caches `types` under `key`, the key of a form's type check.
    pub fn insert_types(&mut self, key: CheckCacheKey, types: std::sync::Arc<crate::types::FormTypes>) {
        self.types.insert(key, types);
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
    let mut refused = Vec::new();
    let cycles_key = CheckCacheKey { check: CheckId::Cycles, canonical_form: graph_form(&program), signatures: Box::new([]) };
    if let CheckResult::Refuse(refusals) = cached(cache, cycles_key, || check_cycles(&program.graph, &program)) {
        refused.extend(refusals.iter().map(|r| diagnostic(DiagnosticKind::Check(CheckId::Cycles), Severity::Error, r.message.clone(), r.at.clone())));
    }
    let mut alerts = Vec::new();
    let mut form_types = Vec::new();
    for (path, form) in top_level_forms(&program) {
        let mut search = SearchBudget::new();
        let order = CanonicalOrder::of(form, &mut search);
        if search.reached {
            let message = "the search for the form's canonical form reached its cap".into();
            alerts.push(diagnostic(DiagnosticKind::Bound, Severity::Alert, message, path.clone()));
        }
        let canonical = canonical_form(form);
        let mut signatures = read_signatures(&program, form, &path, &order).into_vec();
        signatures.extend(types::type_clause_signatures(form, clauses).cloned());
        let signatures: Box<[Signature]> = signatures.into();
        let positions = own_labels(form);
        let key = |check: CheckId, canonical_form: CanonicalForm, signatures: Box<[Signature]>| CheckCacheKey { check, canonical_form, signatures };
        let report = |refused: &mut Vec<Diagnostic>, check: CheckId, result: &CheckResult| {
            if let CheckResult::Refuse(refusals) = result {
                for refusal in refusals.iter() {
                    let at = path.join(&order.source_path(&refusal.at));
                    refused.push(diagnostic(DiagnosticKind::Check(check), Severity::Error, refusal.message.clone(), at));
                }
            }
        };

        let untyped: Vec<LabelInScope> = positions.iter().map(|&(label, _)| LabelInScope { label, ty: None }).collect();
        let input = CheckInput { form, path: &path, scope: Scope { program: &program, registry, labels: &untyped, clauses } };
        let types_key = key(CheckId::Types, canonical.clone(), signatures.clone());
        let (result, types) = match (cache.get(&types_key).cloned(), cache.types(&types_key)) {
            (Some(result), Some(types)) => (result, types),
            _ => {
                let (result, types) = types::infer_form(&input, &order);
                let types = Arc::new(types);
                cache.insert(types_key.clone(), result.clone());
                cache.insert_types(types_key, Arc::clone(&types));
                (result, types)
            }
        };
        report(&mut refused, CheckId::Types, &result);

        let labels: Vec<LabelInScope> =
            positions.iter().map(|&(label, position)| LabelInScope { label, ty: types.label(LabelId(position)).cloned() }).collect();
        let input = CheckInput { scope: Scope { labels: &labels, ..input.scope }, ..input };
        for check in checks().iter().filter(|check| check.id() != CheckId::Types) {
            let canonical_form = match check.id() {
                CheckId::Grounding => with_written_order(form, &canonical, &order),
                _ => canonical.clone(),
            };
            let check_key = key(check.id(), canonical_form, signatures.clone());
            let result = cached(cache, check_key, || check.check(&input));
            report(&mut refused, check.id(), &result);
        }
        form_types.push((path.clone(), types, order));
    }
    if !refused.is_empty() {
        return Err(refused);
    }
    let types = types::program_types(&program, clauses, &form_types);
    Ok(CheckedProgram { program, types, alerts })
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

/// Each label of the scope of `form` itself, with its canonical position.
/// A claim and an `ALTS` form have no such scope.
fn own_labels(form: &Form) -> Box<[(LabelId, u32)]> {
    match form_scope(form) {
        Some(scope) => canonical_labeling(scope, &AsWritten, &mut SearchBudget::new()).positions,
        None => Box::new([]),
    }
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
        &grounding::GroundingCheck,
        &unfold_reads::UnfoldReadsCheck,
        &instance_inputs::InstanceInputsCheck,
        &reads::PooledAndLiftedReadsCheck,
    ];
    &CHECKS
}
