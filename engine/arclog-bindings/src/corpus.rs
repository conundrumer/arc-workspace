//! What the corpus calls of the module share: the walk over the solvers of a
//! corpus, the progress of a replay and the callbacks that report the
//! solvers' units.

use std::path::Path;
use std::panic::{catch_unwind, AssertUnwindSafe};
use std::sync::Mutex;

use arclog::decode::corpus::ReplayProgress;
use arclog::harness::{panic_message, run_over_corpus, SolverResult};
use arclog::stream::corpus::fault_line;
use pyo3::prelude::*;

use crate::errors::Fault;

/// The model steps of a replay that `corpus_streams` or `corpus_tables` runs:
/// `total`, which is 0 until the call has cut its streams into units and then
/// the model steps of all the units, and `done`, the model steps replayed so
/// far, which never passes `total`. Both are read at any time, from any
/// thread, while the call runs.
#[pyclass(name = "ReplayProgress", frozen, module = "arclog")]
#[derive(Default)]
pub struct PyReplayProgress {
    /// The counts, which a replay of `arclog::decode::corpus` sets.
    pub inner: ReplayProgress,
}

#[pymethods]
impl PyReplayProgress {
    #[new]
    fn new() -> PyReplayProgress {
        PyReplayProgress::default()
    }

    #[getter]
    fn total(&self) -> usize {
        self.inner.total()
    }

    #[getter]
    fn done(&self) -> usize {
        self.inner.done()
    }
}

/// The cases and fault lines of each solver of `corpus` that `task_ids`
/// keeps (every solver where it is `None`), as `solver` gives them for the
/// solver's task id, in the order of the task ids. A solver whose `solver`
/// panics gives no cases and one fault line, `the walk of the solver
/// panicked: <message>`. The walk runs on the threads of the corpus harness
/// with the GIL released.
pub fn walk_corpus<C: Send>(
    py: Python<'_>,
    corpus: &str,
    task_ids: &Option<Vec<String>>,
    solver: impl Fn(&str) -> (Vec<C>, Vec<String>) + Sync,
) -> PyResult<Vec<(String, Vec<C>, Vec<String>)>> {
    let found: Mutex<Vec<(String, Vec<C>, Vec<String>)>> = Mutex::new(Vec::new());
    let selected: Option<std::collections::BTreeSet<String>> = task_ids.as_ref().map(|ids| ids.iter().cloned().collect());
    let walked = py.detach(|| {
        run_over_corpus(
            Path::new(corpus),
            selected.as_ref(),
            |corpus_solver| {
                let id = &corpus_solver.task_id;
                let (cases, faults) = catch_unwind(AssertUnwindSafe(|| solver(id))).unwrap_or_else(|payload| {
                    let message = panic_message(&*payload).unwrap_or("a payload that is not a message");
                    (Vec::new(), vec![fault_line(id, None, &format!("the walk of the solver panicked: {message}"))])
                });
                found.lock().unwrap_or_else(|poisoned| poisoned.into_inner()).push((corpus_solver.task_id.clone(), cases, faults));
                SolverResult::Pass
            },
            |_, _| {},
        )
    });
    walked.map_err(|error| Fault::new_err(format!("the corpus does not read: {error:?}")))?;
    let mut found = found.into_inner().unwrap_or_else(|poisoned| poisoned.into_inner());
    found.sort_by(|a, b| a.0.cmp(&b.0));
    Ok(found)
}

/// The progress callbacks of a replay, `started` and `ended`, each a Python
/// callable or `None`, with, for each solver, the count of its streams left
/// and whether `started` was called.
pub struct Progress<'a> {
    started: Option<&'a Py<PyAny>>,
    ended: Option<&'a Py<PyAny>>,
    tasks: Vec<&'a str>,
    streams_left: Vec<std::sync::atomic::AtomicUsize>,
    begun: Vec<std::sync::atomic::AtomicBool>,
}

impl<'a> Progress<'a> {
    /// The progress of solvers with the task ids `tasks`, of whom the solver at an index has `streams[index]` streams.
    pub fn new(started: Option<&'a Py<PyAny>>, ended: Option<&'a Py<PyAny>>, tasks: Vec<&'a str>, streams: Vec<usize>) -> Self {
        let streams_left = streams.into_iter().map(std::sync::atomic::AtomicUsize::new).collect();
        let begun = tasks.iter().map(|_| std::sync::atomic::AtomicBool::new(false)).collect();
        Self { started, ended, tasks, streams_left, begun }
    }

    /// Calls `callback`, holding the GIL, with the task id of `solver`; an exception it raises is printed and dropped.
    fn call(&self, callback: &Py<PyAny>, solver: usize) {
        Python::attach(|py| {
            if let Err(error) = callback.call1(py, (self.tasks[solver],)) {
                error.print(py);
            }
        });
    }

    /// A unit of `solver` starts: calls `started` for the first of its units.
    pub fn start(&self, solver: usize) {
        if let Some(callback) = self.started {
            if !self.begun[solver].swap(true, std::sync::atomic::Ordering::SeqCst) {
                self.call(callback, solver);
            }
        }
    }

    /// A stream of `solver` has ended: calls `ended` for the last of its streams.
    pub fn settle(&self, solver: usize) {
        if let Some(callback) = self.ended {
            if self.streams_left[solver].fetch_sub(1, std::sync::atomic::Ordering::SeqCst) == 1 {
                self.call(callback, solver);
            }
        }
    }
}
