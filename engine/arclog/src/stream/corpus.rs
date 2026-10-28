//! The token streams of the cases of a solver of a corpus, and the helpers
//! that read, check and name those cases, which the `arclog-cli`
//! subcommands and the `arclog` Python package share. The files of a case
//! under `cases/` of a corpus are those of [`case_files`].

mod files;

use std::path::Path;

pub use files::{case_file_name, case_files, CaseFiles, CaseTexts};

use crate::check::{check_program_of_files, check_shared_program, CheckCache, CheckedProgram, SolverClauses};
use crate::decode::replay::holds_demonstrated;
use crate::harness::{read_corpus_solver, read_solver_texts};
use crate::registry::Registry;
use crate::eval::determinations::relation_spelled;
use crate::hash::StableHashSet;
use crate::program::ProgramRelation;
use crate::resolver::{resolve, resolve_cases, DependencyKind, GraphNodeIndex, ResolvedCase, ResolvedCases, ResolvedProgram, SolverScope};
use crate::solver::{Case, CaseName, Exclusion, Solver};
use crate::stream::{written_stream, Emitter, Token, Vocabulary, WrittenStream};

use files::{case_layout, label_name_at};

/// The cases of a solver whose streams are wanted.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum WantedCases<'a> {
    /// The concept case.
    Concept,
    /// Each case of the solver, the combinations that its `exclude` forms
    /// leave out not included.
    Cases,
    /// Each combination of alts, the excluded ones included.
    All,
    /// The case that [`case_spelled`] spells as given.
    Named(&'a str),
}

/// The name that the text of a case's program writes for the label at each
/// label slot of each form of its stream: for each form of
/// [`WrittenStream::forms`], in that order, the name at each slot of the form.
pub type StreamLabels = Vec<Vec<Box<str>>>;

/// The stream of one case of a solver, or the fault that gives none.
#[derive(Clone, Debug)]
pub struct CaseStream {
    /// The case as [`case_spelled`] writes its name.
    pub case: String,
    /// Whether the case is the solver's concept case.
    pub concept: bool,
    /// Whether the case program holds a `DEMONSTRATED` form, whose stream
    /// the commands that replay do not decode.
    pub demonstrated: bool,
    /// The case's token stream with the relation at each slot, or the writer's fault.
    pub stream: Result<WrittenStream, String>,
    /// The names of the stream's labels as the case's `.arclog` text writes
    /// them: those of [`case_files`], or, for a case whose files the corpus's
    /// `cases/` directory holds, those files. A form that stands as its file
    /// writes it, or as the zero-column lowering rewrote it, has the file's
    /// names, and a form that the case program builds or rewrites has the
    /// names that [`case_files`] gives it. Empty where `stream` is a fault.
    pub labels: StreamLabels,
}

/// The stream of each wanted case of the solver `id` of `corpus`, in the
/// order of the cases, as [`corpus_case_stream`] gives it, or the fault that
/// stops the solver: its files do not read, a wanted case is absent, or the
/// checker refuses a wanted case. Where `prefix`, the files of the solver,
/// and of each case under `cases/<id>/`, hold a prefix of a solver, as
/// [`crate::check::CaseFiles::prefix`] gives it, so the checker does not
/// refuse a case program for holding no `OUT` form, and a case's stream ends
/// with the last token of its last form.
pub fn solver_streams(corpus: &Path, id: &str, wanted: WantedCases<'_>, vocabulary: &Vocabulary, prefix: bool) -> Result<Vec<CaseStream>, String> {
    let solver = read_corpus_solver(corpus, id).map_err(|e| format!("the solver's files do not read: {e}"))?;
    let cases = resolve_cases(&solver, Registry::get());
    let clauses = SolverClauses::of_cases(&cases);
    let names = match wanted {
        WantedCases::Concept => decoded_cases(&cases, false),
        WantedCases::Cases => solver.case_names(Exclusion::WithoutExcluded),
        WantedCases::All => decoded_cases(&cases, true),
        WantedCases::Named(spelled) => {
            let found = cases.cases().find(|case| case_spelled(&case.case.name) == spelled).ok_or_else(|| format!("the solver has no case {spelled}"))?;
            vec![found.case.name.clone()]
        }
    };
    let programs = check_cases(&solver, &cases, &clauses, &mut CheckCache::default(), &|name| names.contains(name), prefix)?;
    let concept = &cases.concept().case.name;
    Ok(programs
        .iter()
        .map(|(name, program)| {
            let case = cases.cases().find(|case| case.case.name == *name).expect("a checked case is a case of the solver");
            let (stream, labels) = match named_case_stream(corpus, id, &solver, case, program, vocabulary, prefix) {
                Ok((stream, labels)) => (Ok(stream), labels),
                Err(fault) => (Err(fault), Vec::new()),
            };
            CaseStream { case: case_spelled(name), concept: name == concept, demonstrated: holds_demonstrated(program), stream, labels }
        })
        .collect())
}

/// The program that the files of a case under `cases/<id>/` of a corpus make:
/// the solver they read as, its resolved cases, whose concept case is the
/// program, and the program's checked form.
struct FilesProgram {
    solver: std::sync::Arc<Solver>,
    cases: ResolvedCases,
    checked: CheckedProgram,
}

/// The program of the files of the case `name` of the solver `id` of `corpus`,
/// `None` where it has no files, or the fault that the files stand in part, do
/// not read, or make a solver whose program the checker refuses.
fn files_program(corpus: &Path, id: &str, name: &CaseName, prefix: bool) -> Result<Option<FilesProgram>, String> {
    let Some(texts) = files::read_case_files(corpus, id, name)? else { return Ok(None) };
    let solver = read_solver_texts(corpus, id, &texts.arclog, &texts.arcdata).map_err(|e| format!("the case's files do not read: {e}"))?;
    let cases = resolve_cases(&solver, Registry::get());
    let clauses = SolverClauses::of_cases(&cases);
    let checked = check_case(&solver, cases.concept(), &clauses, &mut CheckCache::default(), "the case's files", prefix)?;
    Ok(Some(FilesProgram { solver, cases, checked }))
}

/// The token stream of `case`, a case of the solver `id` of `corpus`, whose
/// checked program is `checked`, or the writer's fault: where `corpus` holds,
/// under `cases/<id>/`, the files of the case as [`case_file_name`] names
/// them, the concept stream of the solver those two files make; otherwise
/// [`case_stream`]. Where only one of the two files stands, or they do not
/// read, or the solver they make has no stream, the fault. Where `prefix`,
/// the case's files are read as [`solver_streams`] reads them.
pub fn corpus_case_stream(corpus: &Path, id: &str, case: &ResolvedCase, checked: &CheckedProgram, vocabulary: &Vocabulary, prefix: bool) -> Result<WrittenStream, String> {
    match files_program(corpus, id, &case.case.name, prefix)? {
        None => case_stream(case, checked, vocabulary),
        Some(files) => case_stream(files.cases.concept(), &files.checked, vocabulary),
    }
}

/// The stream of [`corpus_case_stream`] for `case`, a case of `solver`, with
/// the names that the text of the program it writes gives its labels: the
/// text of `case` in `solver`, or the text of the concept case of the solver
/// that the case's files make.
fn named_case_stream(corpus: &Path, id: &str, solver: &Solver, case: &ResolvedCase, checked: &CheckedProgram, vocabulary: &Vocabulary, prefix: bool) -> Result<(WrittenStream, StreamLabels), String> {
    match files_program(corpus, id, &case.case.name, prefix)? {
        None => named_stream(solver, case, checked, vocabulary),
        Some(files) => named_stream(&files.solver, files.cases.concept(), &files.checked, vocabulary),
    }
}

/// The stream of `case`, a case of `solver`, as [`case_stream`] gives it,
/// with the name that [`case_layout`] of the case gives each label of each of
/// its forms. The name stands in the innermost node at or above the form's
/// path whose label names hold the label, since the names of the labels of a
/// claim's built forms stand at the claim's path. The reader names each label
/// it makes, and the layout of a built form names each label of the form, so
/// a label with no name is a fault of the engine.
fn named_stream(solver: &Solver, case: &ResolvedCase, checked: &CheckedProgram, vocabulary: &Vocabulary) -> Result<(WrittenStream, StreamLabels), String> {
    let stream = case_stream(case, checked, vocabulary)?;
    let layout = case_layout(solver, &case.case);
    let labels = stream
        .forms
        .iter()
        .map(|form| form.labels.iter().map(|&label| label_name_at(&layout, &form.path, label).expect("every label of the form is named").into()).collect())
        .collect();
    Ok((stream, labels))
}

/// The token stream of `case`, whose checked program is `checked`, or the
/// writer's fault.
///
/// A decoded program reads each of its `DET` forms as the program itself
/// derives what the form reads (`concept: None` in
/// `decode::interface::Decoder::inputs`, no stored value as
/// `docs/engine/synthesis.md` gives), so the stream of a case is the case
/// program read alone: the writer resolves the case as the decoder resolves
/// the program the stream decodes to. The concept program's derivation that
/// a `DET` of the concept program reads in the case is no part of the
/// stream. A case that takes no `DET` of the concept program, the concept
/// case among them, and whose program read alone is its case program
/// ([`crate::solver::Case::reads_alone_as_it_stands`]) has its checked
/// program written as it is. Every other case gets its stream from the
/// program read alone, which drops each column that is `0` in every clause
/// of its relation, whether or not the case takes a `DET` of the concept
/// program. A case where such a `DET` reads, directly or through other
/// relations, a relation that a block other than the concept program
/// derives has no stream, since the program read alone would give that
/// `DET` the block's derivation, and the concept program's derivation is
/// the one it reads in the case. A case that takes more than one `OUT` form
/// ([`crate::solver::Case::several_outs`]) has no stream either, since a
/// stream holds one.
pub fn case_stream(case: &ResolvedCase, checked: &CheckedProgram, vocabulary: &Vocabulary) -> Result<WrittenStream, String> {
    if let Some(fault) = case.case.several_outs() {
        return Err(format!("the writer gives no stream: {fault}"));
    }
    let written = |program: &CheckedProgram| written_stream(program, vocabulary).map_err(|diagnostic| format!("the writer gives no stream: {}", diagnostic.message));
    if case.case.reads_alone_as_it_stands() {
        return written(checked);
    }
    let resolved = resolve_alone(&case.case).map_err(|fault| format!("the writer gives no stream: {fault}"))?;
    let clauses = SolverClauses::of_shared_program(std::sync::Arc::clone(&resolved));
    let alone = check_shared_program(resolved, &clauses, Registry::get(), &mut CheckCache::default()).map_err(|refusals| {
        let messages: Vec<&str> = refusals.iter().map(|d| &*d.message).collect();
        format!("the writer gives no stream: the case program read alone is refused: {}", messages.join("; "))
    })?;
    written(&alone)
}

/// The program of `case` read alone, resolved, or the fault of
/// [`rederived_read`]: the program that [`case_stream`] checks and writes.
fn resolve_alone(case: &Case) -> Result<std::sync::Arc<ResolvedProgram>, String> {
    let resolved = std::sync::Arc::new(resolve(case.program_alone(), None, &SolverScope::default(), Registry::get()).value);
    match rederived_read(case, &resolved) {
        Some(fault) => Err(fault),
        None => Ok(resolved),
    }
}

/// The fault of `case` where a `DET` it takes from the concept program reads,
/// through the dependency graph of `alone`, the case program read alone, a
/// relation that a block other than the concept program derives, naming the
/// `DET` and the relation; `None` where no such read stands.
fn rederived_read(case: &Case, alone: &ResolvedProgram) -> Option<String> {
    let rederived = |node: GraphNodeIndex| alone.forms_of(node).iter().any(|form| case.rederived_forms().iter().any(|top| form.0.starts_with(&top.0)));
    let named = |node: GraphNodeIndex| match &alone.graph.nodes[node.0 as usize].kind {
        DependencyKind::Clause(relation) | DependencyKind::Parameter(relation) => relation_spelled(relation),
        DependencyKind::Chosen(name) => relation_spelled(&ProgramRelation::Declared(name.clone())),
        other => format!("{other:?}"),
    };
    for det in case.concept_determinations() {
        let mut seen: StableHashSet<GraphNodeIndex> = StableHashSet::default();
        let mut open: Vec<GraphNodeIndex> = alone.nodes_of(det).to_vec();
        while let Some(node) = open.pop() {
            if !seen.insert(node) {
                continue;
            }
            if rederived(node) {
                let roots = alone.nodes_of(det).first().map_or_else(String::new, |root| named(*root));
                return Some(format!("the `DET` of `{roots}` from the concept program reads `{}`, which a block of the case other than the concept program derives, so the case program read alone gives that `DET` another derivation", named(node)));
            }
            open.extend(alone.graph.reads[node.0 as usize].iter().copied());
        }
    }
    None
}

/// The line of a fault in the corpus report: of the case `case` of the
/// solver `task`, or, for `None`, of the whole solver.
pub fn fault_line(task: &str, case: Option<&str>, fault: &str) -> String {
    match case {
        Some(case) => format!("{task} {case}: {fault}"),
        None => format!("{task}: {fault}"),
    }
}

/// The id of each token of `stream` in `vocabulary`, with its emitter.
pub fn token_ids(stream: &[(Token, Emitter)], vocabulary: &Vocabulary) -> Vec<(u32, Emitter)> {
    stream.iter().map(|(token, emitter)| (vocabulary.id(token).expect("the writer gives only tokens of the vocabulary"), *emitter)).collect()
}

/// The names of the cases a replay command decodes: every case, or the
/// concept case.
pub fn decoded_cases(cases: &ResolvedCases, all: bool) -> Vec<CaseName> {
    if all { cases.cases().map(|case| case.case.name.clone()).collect() } else { vec![cases.concept().case.name.clone()] }
}

/// The name of a case as a line gives it: its alts, or `concept` for the
/// case that takes none.
pub fn case_spelled(name: &CaseName) -> String {
    if name.0.is_empty() { "concept".to_owned() } else { name.0.iter().map(|alt| &*alt.0).collect::<Vec<_>>().join(" ") }
}

/// The checked program of `case`, one of the cases of `solver` whose clauses
/// `clauses` index, checked with the files of `solver` that the checks
/// which read files read, or the checker's refusal of `what`, the case as a
/// line names it. Where `prefix`, the files hold a prefix of a solver, as
/// [`crate::check::CaseFiles::prefix`] gives it.
pub fn check_case(solver: &Solver, case: &ResolvedCase, clauses: &SolverClauses, cache: &mut CheckCache, what: &str, prefix: bool) -> Result<CheckedProgram, String> {
    let files = crate::check::CaseFiles { solver, case: &case.case, prefix };
    check_program_of_files(std::sync::Arc::clone(&case.resolved.value), clauses, Registry::get(), cache, Some(&files)).map_err(|refusals| {
        let messages: Vec<&str> = refusals.iter().map(|d| &*d.message).collect();
        format!("the checker refuses {what}: {}", messages.join("; "))
    })
}

/// The checked program of each case of `cases`, those of `solver`, whose
/// name `wanted` holds, in the order of the cases, or the first refusal, as
/// [`check_case`] gives it, with `prefix` as it reads it.
pub fn check_cases(solver: &Solver, cases: &ResolvedCases, clauses: &SolverClauses, cache: &mut CheckCache, wanted: &dyn Fn(&CaseName) -> bool, prefix: bool) -> Result<Vec<(CaseName, CheckedProgram)>, String> {
    let mut programs = Vec::new();
    for case in cases.cases().filter(|case| wanted(&case.case.name)) {
        let what = format!("the case {}", case_spelled(&case.case.name));
        programs.push((case.case.name.clone(), check_case(solver, case, clauses, cache, &what, prefix)?));
    }
    Ok(programs)
}
