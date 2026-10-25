//! The token streams of the cases of a solver of a corpus, and the helpers
//! that read, check and name those cases, which the `arclog-cli`
//! subcommands and the `arclog` Python package share.

use std::path::Path;

use crate::check::{check_shared_program, CheckCache, CheckedProgram, SolverClauses};
use crate::decode::replay::holds_demonstrated;
use crate::harness::read_corpus_solver;
use crate::registry::Registry;
use crate::resolver::{resolve, resolve_cases, ResolvedCase, ResolvedCases, SolverScope};
use crate::solver::CaseName;
use crate::stream::{token_stream, Emitter, Token, Vocabulary};

/// The cases of a solver whose streams are wanted.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum WantedCases<'a> {
    /// The concept case.
    Concept,
    /// Each case.
    All,
    /// The case that [`case_spelled`] spells as given.
    Named(&'a str),
}

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
    /// The case's token stream, or the writer's fault.
    pub stream: Result<Vec<(Token, Emitter)>, String>,
}

/// The stream of each wanted case of the solver `id` of `corpus`, in the
/// order of the cases, or the fault that stops the solver: its files do not
/// read, a wanted case is absent, or the checker refuses a wanted case.
pub fn solver_streams(corpus: &Path, id: &str, wanted: WantedCases<'_>, vocabulary: &Vocabulary) -> Result<Vec<CaseStream>, String> {
    let solver = read_corpus_solver(corpus, id).map_err(|e| format!("the solver's files do not read: {e}"))?;
    let cases = resolve_cases(&solver, Registry::get());
    let clauses = SolverClauses::of_cases(&cases);
    let names = match wanted {
        WantedCases::Concept => decoded_cases(&cases, false),
        WantedCases::All => decoded_cases(&cases, true),
        WantedCases::Named(spelled) => {
            let found = cases.cases().find(|case| case_spelled(&case.case.name) == spelled).ok_or_else(|| format!("the solver has no case {spelled}"))?;
            vec![found.case.name.clone()]
        }
    };
    let programs = check_cases(&cases, &clauses, &mut CheckCache::default(), &|name| names.contains(name))?;
    let concept = &cases.concept().case.name;
    Ok(programs
        .iter()
        .map(|(name, program)| {
            let case = cases.cases().find(|case| case.case.name == *name).expect("a checked case is a case of the solver");
            CaseStream {
                case: case_spelled(name),
                concept: name == concept,
                demonstrated: holds_demonstrated(program),
                stream: case_stream(case, name == concept, program, vocabulary),
            }
        })
        .collect())
}

/// The token stream of `case`, whose checked program is `checked` and which
/// is the solver's concept case where `concept` holds, or the writer's
/// fault.
///
/// A decoded program reads each of its `DET` forms as the program itself
/// derives what the form reads (`concept: None` in
/// `decode::interface::Decoder::inputs`, no stored value as
/// `docs/engine/synthesis.md` gives), so the stream of a case is the case
/// program read alone: the writer resolves the case as the decoder resolves
/// the program the stream decodes to. The concept program's derivation that
/// a `DET` of the concept program reads in the case is no part of the
/// stream. A case that takes no `DET` of the concept program copies nothing
/// from it, so its checked program is written as it is.
pub fn case_stream(case: &ResolvedCase, concept: bool, checked: &CheckedProgram, vocabulary: &Vocabulary) -> Result<Vec<(Token, Emitter)>, String> {
    let written = |program: &CheckedProgram| token_stream(program, vocabulary).map_err(|diagnostic| format!("the writer gives no stream: {}", diagnostic.message));
    if concept || case.case.concept_determinations().is_empty() {
        return written(checked);
    }
    let resolved = std::sync::Arc::new(resolve(&case.case.program, None, &SolverScope::default(), Registry::get()).value);
    let clauses = SolverClauses::of_shared_program(std::sync::Arc::clone(&resolved));
    let alone = check_shared_program(resolved, &clauses, Registry::get(), &mut CheckCache::default()).map_err(|refusals| {
        let messages: Vec<&str> = refusals.iter().map(|d| &*d.message).collect();
        format!("the writer gives no stream: the case program read alone is refused: {}", messages.join("; "))
    })?;
    written(&alone)
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

/// The checked program of `case`, one of the cases whose clauses `clauses`
/// index, or the checker's refusal of `what`, the case as a line names it.
pub fn check_case(case: &ResolvedCase, clauses: &SolverClauses, cache: &mut CheckCache, what: &str) -> Result<CheckedProgram, String> {
    check_shared_program(std::sync::Arc::clone(&case.resolved.value), clauses, Registry::get(), cache).map_err(|refusals| {
        let messages: Vec<&str> = refusals.iter().map(|d| &*d.message).collect();
        format!("the checker refuses {what}: {}", messages.join("; "))
    })
}

/// The checked program of each case of `cases` whose name `wanted` holds,
/// in the order of the cases, or the first refusal.
pub fn check_cases(cases: &ResolvedCases, clauses: &SolverClauses, cache: &mut CheckCache, wanted: &dyn Fn(&CaseName) -> bool) -> Result<Vec<(CaseName, CheckedProgram)>, String> {
    let mut programs = Vec::new();
    for case in cases.cases().filter(|case| wanted(&case.case.name)) {
        let what = format!("the case {}", case_spelled(&case.case.name));
        programs.push((case.case.name.clone(), check_case(case, clauses, cache, &what)?));
    }
    Ok(programs)
}
