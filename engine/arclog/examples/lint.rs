//! The end check of the checker stage, and of step 1, over the corpus:
//! `cargo run --profile tool --example lint -- <dir> <report>`, with
//! `<dir>` the corpus directory, such as `programs/arclog/`, and `<report>`
//! the `--all` output of the Python lint over `<dir>`, read by
//! [`arclog::harness::LintReport`].
//!
//! The run lints each solver of `<dir>` with
//! [`arclog::harness::run_over_corpus`], prints each difference from the
//! Python lint by task id, and exits nonzero where a solver differs or the
//! directory is a fault, so the check passes where the engine and the
//! Python lint agree on `<dir>` for the checks the engine has.
//!
//! The two agree on a solver where each place of its files, as a file and a
//! line, has the same checks among the errors of the read and of
//! [`arclog::check::lint::lint`] as among the errors of the report that
//! [`check_of`] maps to a check. The report's other errors are left out,
//! and so are the errors of each check in the solvers where
//! [`LINT_FAULTS`] gives that the Python lint misses them.

use std::panic::{catch_unwind, AssertUnwindSafe};
use std::path::{Path, PathBuf};
use std::process::ExitCode;

use arclog::check::lint::lint;
use arclog::check::CheckId;
use arclog::diagnostic::{Diagnostic, DiagnosticKind, Location, Severity};
use arclog::hash::StableHashMap;
use arclog::harness::{print_ended, read_corpus_solver, require_optimized_build, solver_file_extension, run_over_corpus, CorpusSolver, LintCode, LintError, LintReport, SolverResult};
use arclog::layout::SourceFile;
use arclog::registry::Registry;

/// The engine's check that gives the errors of the Python lint's code
/// `code`, where the engine has that check.
fn check_of(code: LintCode) -> Option<CheckId> {
    use LintCode::*;
    Some(match code {
        Syntax | Form | Clause | Body | Atom | Site | Label | Constraint | Not | Or | If | All | Mark | Zero | Wildcard | Name | EqMark | Choose | Rigid => CheckId::Grammar,
        Undeclared | Relation | Component | ProposerUnknown => CheckId::Scope,
        Column | SiteTwice => CheckId::SiteColumns,
        EqMake | EqUnexported | RemadeExport => CheckId::MadeAndExportedLabels,
        Safety => CheckId::Safety,
        OwnRead => CheckId::UnfoldReads,
        Recursion => CheckId::Cycles,
        InitOrder | InputTwice => CheckId::InstanceInputs,
        Side => CheckId::PooledAndLiftedReads,
        HeadZero | ZeroSite | EqOrder | EqSite | EqSameList => CheckId::EqualityAndZero,
        FreshHere => CheckId::ConstraintMarks,
        ClauseTwice => CheckId::OneClause,
        BroadcastInside => CheckId::InstanceSites,
        Remade | LabelClash | Elide | FieldCase => CheckId::Spelling,
        One | OnePlace | ChooseNoNever | ChooseOne | NeverReads => CheckId::Picks,
        RigidPart | Proposer => CheckId::RigidPartsAndProposers,
        AltClaim | AltCols | AltCombination | AltSame | AltTail | Alts | AltsEmpty | Approximated | ArcdataHead | ArcdataName | ArcdataOrder |
        Assign | BareInit | Claim | ClaimText | ConceptEmpty | Count | CountPlace | Cycle | DemoRule |
        DetOrRule | EmptyGloss | Exclude | GridLayout | HeadSite | Input | Instance | KeyForm | KeyLocal | NoOutput | NotUndefined |
        OrImplied | OrLineTwice | Order | OutputPlace | OutputRestated | Param | ParamGrid | ParamTypes | Parse | ParseHead | RecordField |
        RecordPosition | Render | RenderHead | RenderPlace | RepeatForm | Representative | SceneAlts | SceneArclog | SceneBlock |
        SceneClaim | SceneForm | SceneParse | ScenePick | SceneTaskSide | SharedCols | Spelling | StandsUnder | TopOrder | Unbound | Witness |
        WitnessId | WitnessNoInput | WitnessNoSeparates | WitnessOther | WitnessRef => return None,
    })
}

/// The errors that the Python lint misses, by the code it would give them
/// and the task ids of the solvers it misses them in.
const LINT_FAULTS: &[(LintCode, &[&str])] = &[
    // The lint gives no columns to a `DET_OR_RULE` line with no body, nor to
    // a `DET` with no body and no proposer, so it checks no site of a read
    // of their relations.
    (
        LintCode::Column,
        &[
            "21897d95", "25094a63", "28a6681f", "351d6448", "71e489b6", "8e5a5113", "91714a58", "9b5080bb", "9d9215db", "9ddd00f0",
            "9def23fe", "a251c730", "a2d730bd", "a32d8b75", "a3325580", "a5f85a15", "a61f2674", "a64e4611", "a8d7556c", "aa300dc3",
            "aa62e3f4", "aab50785", "abc82100", "ac0c2ac3", "ad38a9d0", "ae58858e", "aee291af", "af24b4cc", "b0c4d837", "b15fca0b",
            "b2862040", "b457fec5", "b4a43f3b", "b527c5c6", "b548a754", "b5bb5719", "b7256dcd", "b7f8a4d8", "b942fd60", "b9630600",
            "ba9d41b8", "bc93ec48", "bd14c3bf", "bda2d7a6", "bf699163", "c0f76784", "c444b776", "c4d1a9ae", "c62e2108", "c8cbb738",
        ],
    ),
    // The lint takes a label that an `OR`'s first branch makes and that a
    // later branch names as named there, where another later branch does
    // not name it, so that the label is local to the first branch.
    (
        LintCode::Safety,
        &[
            "070dd51e", "0ca9ddb6", "0d87d2a6", "0f63c0b9", "1190bc91", "136b0064", "13713586", "16de56c4", "1f876c06", "28a6681f",
            "29700607", "29c11459", "2c608aff", "2ccd9fef", "35ab12c3", "3dc255db", "40853293", "4290ef0e", "505fff84", "538b439f",
            "5545f144", "692cd3b6", "696d4842", "6c434453", "6cdd2623", "6e4f6532", "72a961c9", "7acdf6d3", "7e576d6e", "8403a5d5",
            "855e0971", "88bcf3b4", "8b9c3697", "8ee62060", "a2d730bd", "a2fd1cf0", "ba9d41b8", "bf699163", "c61be7dc",
        ],
    ),
];

/// Whether [`LINT_FAULTS`] gives that the Python lint misses the errors of
/// `check` in the solver of `task_id`.
fn missed(task_id: &str, check: CheckId) -> bool {
    LINT_FAULTS.iter().any(|(code, task_ids)| check_of(*code) == Some(check) && task_ids.contains(&task_id))
}

/// An error at a place of a solver's files: the file, the line, and the
/// check.
type Place = (PathBuf, u32, CheckId);

/// The places of errors, each with the message of its first error.
type Places = StableHashMap<Place, String>;

/// The places of the report's errors in the files of `solver`, each of a
/// code that [`check_of`] maps to a check.
fn reported(solver: &CorpusSolver, report: &LintReport) -> std::io::Result<Places> {
    let files = [std::fs::canonicalize(&solver.arclog)?, std::fs::canonicalize(&solver.arcdata)?];
    let at = |error: &LintError| {
        let file = std::fs::canonicalize(&error.path).ok().filter(|file| files.contains(file))?;
        Some(((file, error.line, check_of(error.check)?), error.message.clone()))
    };
    let mut places = Places::default();
    for (place, message) in report.errors.iter().filter_map(at) {
        places.entry(place).or_insert(message);
    }
    Ok(places)
}

/// The places of the engine's errors in the files of `solver`: those of
/// the read, then those of the lint where the solver reads.
fn found(dir: &Path, solver: &CorpusSolver) -> Result<Places, String> {
    let text = |path: &Path| std::fs::read_to_string(path).map_err(|e| format!("{}: {e}", path.display()));
    let (arclog, arcdata) = (text(&solver.arclog)?, text(&solver.arcdata)?);
    let read = arclog::read::read_solver(&solver.task_id, &arclog, &arcdata, &|id| read_corpus_solver(dir, id).ok());
    let (diagnostics, solver_value) = match read {
        Err(diagnostics) => (diagnostics, None),
        Ok(read) if read.diagnostics.iter().any(|d| d.severity == Severity::Error) => (read.diagnostics, None),
        Ok(read) => (read.diagnostics, Some(read.value)),
    };
    let mut diagnostics = diagnostics;
    if let Some(value) = solver_value {
        diagnostics.extend(lint(&value, Registry::get()));
    }
    let mut places = Places::default();
    for diagnostic in diagnostics.iter().filter(|d| d.severity == Severity::Error) {
        for place in places_of(dir, diagnostic)? {
            places.entry(place).or_insert_with(|| diagnostic.message.to_string());
        }
    }
    Ok(places)
}

/// The places of `diagnostic`, each file named by the task id of its place.
fn places_of(dir: &Path, diagnostic: &Diagnostic) -> Result<Vec<Place>, String> {
    let DiagnosticKind::Check(check) = diagnostic.kind else {
        return Err(format!("an error of no check: {}", diagnostic.message));
    };
    let Location::Places(places) = &diagnostic.location else {
        return Err(format!("{check:?}: an error at no place in the files: {}", diagnostic.message));
    };
    places
        .iter()
        .map(|at| {
            let Some(extension) = solver_file_extension(at.place.file) else {
                return Err(format!("{check:?}: an error in a lib file: {}", diagnostic.message));
            };
            let task_id = at.task_id.as_deref().ok_or_else(|| format!("{check:?}: an error in no solver's file: {}", diagnostic.message))?;
            let path = dir.join(format!("{task_id}.{extension}"));
            let path = std::fs::canonicalize(&path).map_err(|e| format!("{}: {e}", path.display()))?;
            Ok((path, at.place.line, check))
        })
        .collect()
}

fn check(dir: &Path, solver: &CorpusSolver, report: &LintReport) -> SolverResult {
    let reported = match reported(solver, report) {
        Ok(reported) => reported,
        Err(error) => return SolverResult::Fail(vec![error.to_string()]),
    };
    let found = match catch_unwind(AssertUnwindSafe(|| found(dir, solver))) {
        Ok(Ok(found)) => found,
        Ok(Err(fault)) => return SolverResult::Fail(vec![fault]),
        Err(_) => return SolverResult::Fail(vec!["the lint of the solver panicked".to_owned()]),
    };
    let only = |side: &'static str, these: &Places, other: &Places| {
        let only = these.iter().filter(|(place, _)| !other.contains_key(*place));
        only.map(|(place, message)| (side, place.clone(), message.clone())).collect::<Vec<_>>()
    };
    let compared = |places: Places| -> Places { places.into_iter().filter(|((_, _, check), _)| !missed(&solver.task_id, *check)).collect() };
    let (reported, found) = (compared(reported), compared(found));
    let mut differences = only("only the Python lint", &reported, &found);
    differences.extend(only("only the engine", &found, &reported));
    differences.sort();
    let line = |(side, (path, line, check), message): (&str, Place, String)| format!("{side}: {}:{line}: {check:?}: {message}", path.display());
    let differences: Vec<String> = differences.into_iter().map(line).collect();
    if differences.is_empty() { SolverResult::Pass } else { SolverResult::Fail(differences) }
}

fn main() -> ExitCode {
    if let Err(code) = require_optimized_build() {
        return code;
    }
    let args: Vec<String> = std::env::args().skip(1).collect();
    let [dir, report] = &args[..] else {
        eprintln!("usage: cargo run --profile tool --example lint -- <dir> <report>");
        return ExitCode::FAILURE;
    };
    let report = match LintReport::read(Path::new(report)) {
        Ok(report) => report,
        Err(error) => {
            eprintln!("{report}: {error}");
            return ExitCode::FAILURE;
        }
    };
    let dir = Path::new(dir);
    match run_over_corpus(dir, None, |solver| check(dir, solver, &report), print_ended) {
        Err(error) => {
            eprintln!("{}: {error:?}", dir.display());
            ExitCode::FAILURE
        }
        Ok(corpus) => {
            println!("{} solvers, {} differ", corpus.checked, corpus.failures.len());
            if corpus.failures.is_empty() { ExitCode::SUCCESS } else { ExitCode::FAILURE }
        }
    }
}
