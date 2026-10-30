//! The files of the cases of a solver, as Python gives them.

use std::path::Path;

use arclog::stream::corpus::{case_files as engine_case_files, CaseFiles};
use pyo3::prelude::*;

use crate::errors::Fault;

/// The files of one case of a solver: `case` is the case as `CaseStream.case`
/// names it, and `file` its file name, without the extensions
/// `.arclog` and `.arcdata`. `arclog` and `arcdata` hold the two texts, the
/// case program read alone and the records of the solver that it reads, which
/// read as a solver with no alts whose concept case is that program; both are
/// `None`, and `fault` holds why, where the case program has no files.
#[pyclass(name = "CaseFiles", frozen, get_all, module = "arclog")]
pub(crate) struct PyCaseFiles {
    case: String,
    file: String,
    concept: bool,
    arclog: Option<String>,
    arcdata: Option<String>,
    fault: Option<String>,
}

impl From<CaseFiles> for PyCaseFiles {
    fn from(files: CaseFiles) -> PyCaseFiles {
        let (texts, fault) = match files.texts {
            Ok(texts) => (Some(texts), None),
            Err(fault) => (None, Some(fault)),
        };
        PyCaseFiles {
            case: files.case,
            file: files.file,
            concept: files.concept,
            arclog: texts.as_ref().map(|texts| texts.arclog.clone()),
            arcdata: texts.map(|texts| texts.arcdata),
            fault,
        }
    }
}

/// The files of every case of the solver `task_id` given by its `.arclog` and
/// `.arcdata` texts, every combination of alts, the excluded ones included, in
/// the order of the cases. `corpus` is the directory that holds the files of
/// the solvers the `.arcdata` text names. Raises `Fault` where the texts do not
/// read as a solver.
#[pyfunction]
pub(crate) fn case_files(py: Python<'_>, task_id: &str, arclog: &str, arcdata: &str, corpus: &str) -> PyResult<Vec<PyCaseFiles>> {
    let files = py.detach(|| engine_case_files(task_id, arclog, arcdata, Path::new(corpus)));
    files.map(|files| files.into_iter().map(PyCaseFiles::from).collect()).map_err(Fault::new_err)
}
