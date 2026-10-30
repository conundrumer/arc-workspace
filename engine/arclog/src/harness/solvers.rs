//! The corpus's solvers on disk: the listing of the `.arclog` and `.arcdata`
//! file pairs of a corpus directory, and the read of a solver from its pair.

use std::path::{Path, PathBuf};

/// One solver of the corpus: its task id and its two files.
#[derive(Clone, PartialEq, Eq, Debug)]
pub struct CorpusSolver {
    pub task_id: String,
    pub arclog: PathBuf,
    pub arcdata: PathBuf,
}

/// A fault of the corpus directory: it cannot be read, or an `.arclog` file
/// has no `.arcdata` file beside it, or the reverse.
#[derive(Debug)]
pub enum CorpusError {
    Unreadable { path: PathBuf, error: std::io::Error },
    MissingFile { path: PathBuf },
}

/// The solvers of `dir`, in the order of their task ids: one for each
/// `.arclog` file, whose `.arcdata` file stands beside it. The listing
/// passes over each file of another extension.
pub fn corpus_solvers(dir: &Path) -> Result<Vec<CorpusSolver>, CorpusError> {
    let unreadable = |path: &Path, error| CorpusError::Unreadable { path: path.to_owned(), error };
    let mut arclog = std::collections::BTreeSet::new();
    let mut arcdata = std::collections::BTreeSet::new();
    for entry in std::fs::read_dir(dir).map_err(|e| unreadable(dir, e))? {
        let path = entry.map_err(|e| unreadable(dir, e))?.path();
        let (Some(stem), Some(extension)) = (path.file_stem().and_then(|s| s.to_str()), path.extension()) else {
            continue;
        };
        match extension.to_str() {
            Some("arclog") => arclog.insert(stem.to_owned()),
            Some("arcdata") => arcdata.insert(stem.to_owned()),
            _ => continue,
        };
    }
    let file = |task_id: &str, extension: &str| dir.join(format!("{task_id}.{extension}"));
    if let Some(task_id) = arclog.symmetric_difference(&arcdata).next() {
        let extension = if arclog.contains(task_id) { "arcdata" } else { "arclog" };
        return Err(CorpusError::MissingFile { path: file(task_id, extension) });
    }
    Ok(arclog
        .into_iter()
        .map(|task_id| CorpusSolver { arclog: file(&task_id, "arclog"), arcdata: file(&task_id, "arcdata"), task_id })
        .collect())
}

/// The extension of a solver's file that holds `file`: `None` for a lib file.
pub fn solver_file_extension(file: crate::layout::SourceFile) -> Option<&'static str> {
    use crate::layout::SourceFile;
    match file {
        SourceFile::Arclog => Some("arclog"),
        SourceFile::Arcdata => Some("arcdata"),
        SourceFile::LibRegistry | SourceFile::LibProposers => None,
    }
}

/// The solver of `task_id` read from its two files in `dir`, each solver a
/// `representative` line names read the same way. `Err` where a file does
/// not read, as `<path>: <io error>`, or as [`read_solver_texts`] gives.
pub fn read_corpus_solver(dir: &Path, task_id: &str) -> Result<std::sync::Arc<crate::solver::Solver>, String> {
    let read_file = |extension: &str| {
        let path = dir.join(format!("{task_id}.{extension}"));
        std::fs::read_to_string(&path).map_err(|e| format!("{}: {e}", path.display()))
    };
    read_solver_texts(dir, task_id, &read_file("arclog")?, &read_file("arcdata")?)
}

/// The solver of `task_id` from the texts of its two files, each solver a
/// `representative` line names read from `dir` by [`read_corpus_solver`].
/// `Err` where the read is refused or has a diagnostic of
/// [`crate::diagnostic::Severity::Error`]: each such diagnostic as
/// `<task_id>.<extension>:<line>: <message>` per place, or the message alone
/// at a path, joined by `; `. A solver whose `representative` line names a
/// solver that does not read gives the scope diagnostic of
/// [`crate::read::read_solver`].
pub fn read_solver_texts(dir: &Path, task_id: &str, arclog: &str, arcdata: &str) -> Result<std::sync::Arc<crate::solver::Solver>, String> {
    use crate::diagnostic::{Diagnostic, Location, Severity};
    let describe = |diagnostics: &[Diagnostic]| {
        let mut lines = Vec::new();
        for d in diagnostics.iter().filter(|d| d.severity == Severity::Error) {
            match &d.location {
                Location::Places(places) => {
                    for at in places.iter() {
                        let extension = solver_file_extension(at.place.file).unwrap_or("lib");
                        let id = at.task_id.as_deref().unwrap_or(task_id);
                        lines.push(format!("{id}.{extension}:{}: {}", at.place.line, d.message));
                    }
                }
                Location::Path(_) => lines.push(d.message.to_string()),
            }
        }
        lines.join("; ")
    };
    let read = crate::read::read_solver(task_id, arclog, arcdata, &|id| read_corpus_solver(dir, id).ok()).map_err(|d| describe(&d))?;
    if read.diagnostics.iter().any(|d| d.severity == Severity::Error) {
        return Err(describe(&read.diagnostics));
    }
    Ok(std::sync::Arc::new(read.value))
}
