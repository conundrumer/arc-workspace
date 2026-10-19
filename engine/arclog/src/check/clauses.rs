//! The index of every clause of a solver across its case programs, which
//! the checks that compare a relation's clauses read.

use std::sync::Arc;

use crate::program::canonical::CanonicalWriter;
use crate::program::path::NodePath;
use crate::program::{DemonstratedPart, Form, ProgramRelation};
use crate::registry::Registry;
use crate::resolver::{ResolvedCases, ResolvedProgram, Signature};
use crate::solver::FileOwner;

/// Every clause of each relation that a solver declares, across its blocks
/// and so across its cases, with the case programs they were found in. A
/// key is a relation in the name scope it is declared in. Each entry of a
/// key is one clause of that relation. The entries of a key stand in a
/// fixed order: the clauses of the solver's own file first, then those of
/// its representative's, the order of the [`crate::solver::FileOwner`]
/// variants, and within a file in the order of their paths, the index of
/// the top-level form, then the index among the children at each step. A
/// synthesized program has one case, and its clauses are its own.
#[derive(Debug, Default)]
pub struct SolverClauses {
    /// Each case program the clauses were found in, the concept program
    /// first.
    programs: Box<[Arc<ResolvedProgram>]>,
    clauses: crate::hash::StableHashMap<(FileScope, ProgramRelation), Box<[ClauseEntry]>>,
    column_reads: super::inference::ClauseColumnReads,
}

/// One clause of a relation in [`SolverClauses`]. A clause that stands in
/// several case programs is found once, in the first of them.
#[derive(Clone, Debug)]
pub struct ClauseEntry {
    /// The arclog file that holds the clause, the solver's or its
    /// representative's.
    pub owner: FileOwner,
    /// The clause's path in that file.
    pub file_path: NodePath,
    pub signature: Signature,
    /// The case program the clause was found in, by its index in
    /// [`SolverClauses`]'s programs.
    pub(super) program: usize,
    /// The clause's path in that program.
    pub at: NodePath,
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
    /// The clauses of each relation of `solver`, found in each case
    /// program of the solver.
    pub fn of(solver: &crate::solver::Solver, registry: &Registry) -> Self {
        Self::of_cases(&crate::resolver::resolve_cases(solver, registry))
    }

    /// The clauses of each relation of a solver, found in each case program
    /// of `cases`, which the index holds by their `Arc`.
    pub fn of_cases(cases: &ResolvedCases) -> Self {
        let mut found = ClausesFound::default();
        for resolved in cases.resolved() {
            found.add(Arc::clone(&resolved.resolved.value), &|path| resolved.case.file_path(path));
        }
        found.ordered()
    }

    /// The clauses of a synthesized program, its own.
    pub fn of_program(program: ResolvedProgram) -> Self {
        let mut found = ClausesFound::default();
        found.add(Arc::new(program), &|path| (FileOwner::Solver, path.clone()));
        found.ordered()
    }

    /// Each clause of `relation` in the name scope `scope`.
    pub fn of_relation(&self, scope: &FileScope, relation: &ProgramRelation) -> &[ClauseEntry] {
        self.clauses.get(&(scope.clone(), relation.clone())).map_or(&[], |entries| &entries[..])
    }

    /// The case program `entry` was found in.
    pub fn program(&self, entry: &ClauseEntry) -> &ResolvedProgram {
        &self.programs[entry.program]
    }

    /// The column types read of these clauses so far.
    pub(super) fn column_reads(&self) -> &super::inference::ClauseColumnReads {
        &self.column_reads
    }
}

/// The clauses [`SolverClauses`] gathers, each once, before they are put in
/// its order.
#[derive(Default)]
struct ClausesFound {
    programs: Vec<Arc<ResolvedProgram>>,
    clauses: crate::hash::StableHashMap<(FileScope, ProgramRelation), Vec<ClauseEntry>>,
}

impl ClausesFound {
    /// Adds `program` and each clause of it, at the top level and in each
    /// `DEMO_RULE` form, with its file and its path there as `file_path`
    /// gives them for its path in `program`.
    fn add(&mut self, program: Arc<ResolvedProgram>, file_path: &dyn Fn(&NodePath) -> (FileOwner, NodePath)) {
        let program_index = self.programs.len();
        for (path, form) in top_level_forms(&program) {
            match form {
                Form::Clause(clause) => self.add_clause((program_index, &*program), file_path, FileScope::Program, &clause.value().derives, &path),
                Form::Demonstrated(demonstrated) => {
                    let demonstrated = demonstrated.value();
                    for (index, rule) in demonstrated.rules.iter().enumerate() {
                        let rule_path = path.child(demonstrated.position(DemonstratedPart::Rule(index)));
                        let (owner, file_rule_path) = file_path(&rule_path);
                        for (index, form) in rule.value().forms.iter().enumerate() {
                            if let Form::Clause(clause) = form {
                                let scope = FileScope::DemoRule(owner, file_rule_path.clone());
                                self.add_clause((program_index, &*program), file_path, scope, &clause.value().derives, &rule_path.child(index as u32));
                            }
                        }
                    }
                }
                _ => {}
            }
        }
        self.programs.push(program);
    }

    fn add_clause(
        &mut self,
        (index, program): (usize, &ResolvedProgram),
        file_path: &dyn Fn(&NodePath) -> (FileOwner, NodePath),
        scope: FileScope,
        relation: &ProgramRelation,
        path: &NodePath,
    ) {
        let (owner, file) = file_path(path);
        let signature = clause_signature(program, path);
        let entries = self.clauses.entry((scope, relation.clone())).or_default();
        if !entries.iter().any(|entry| entry.owner == owner && entry.file_path == file && entry.signature == signature) {
            entries.push(ClauseEntry { owner, file_path: file, signature, program: index, at: path.clone() });
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
                entries.sort_by(|a, b| (rank(&a.owner), &a.file_path).cmp(&(rank(&b.owner), &b.file_path)));
                (key, entries.into_boxed_slice())
            })
            .collect();
        SolverClauses { programs: self.programs.into(), clauses, column_reads: Default::default() }
    }
}

/// The signature of the clause at `path` of `program`: the hash of its
/// resolved content.
pub(super) fn clause_signature(program: &ResolvedProgram, path: &NodePath) -> Signature {
    let content = program.content(path).expect("a clause of the program has its resolved content");
    let mut out = CanonicalWriter::default();
    out.write(&content.content_hash().0.to_le_bytes());
    Signature(out.finish())
}

/// Each top-level form of `program`, with its path.
pub(super) fn top_level_forms(program: &ResolvedProgram) -> impl Iterator<Item = (NodePath, &Form)> {
    let forms = program.program.value().forms.iter();
    forms.zip(0u32..).map(|(form, index)| (NodePath::top(index), form))
}
