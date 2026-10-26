//! The task of one ARC JSON file, as Python gives it, and the world its
//! pairs are judged in.

use std::sync::Arc;

use arclog::judge::candidates::World;
use arclog::task::{read_judged_train_text, read_task_text, JudgedTask, Task, TaskError};
use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;

/// The world of a run: how the candidates of a pair are read.
#[pyclass(name = "World", eq, eq_int, frozen, module = "arclog")]
#[derive(Clone, Copy, PartialEq, Eq)]
pub(crate) enum PyWorld {
    /// The task data of this repository, whose pairs the judge reads in full.
    Closed,
    /// Kaggle's task data.
    Open,
}

impl From<PyWorld> for World {
    fn from(world: PyWorld) -> World {
        match world {
            PyWorld::Closed => World::Closed,
            PyWorld::Open => World::Open,
        }
    }
}

/// The task of one ARC JSON file and the judge's view of its train pairs.
pub(crate) struct TaskData {
    pub(crate) task: Task,
    pub(crate) judged: JudgedTask,
    pub(crate) world: World,
}

/// The train pairs and test inputs of one task, and its world.
#[pyclass(name = "Task", frozen, module = "arclog")]
pub(crate) struct PyTask {
    pub(crate) data: Arc<TaskData>,
}

fn read_task(text: &str, world: World) -> Result<TaskData, TaskError> {
    // A test output is the judge's, and Kaggle's files hold none.
    Ok(TaskData { task: read_task_text(text)?, judged: JudgedTask { train: read_judged_train_text(text)?, test: Box::new([]) }, world })
}

fn task_error(error: TaskError) -> PyErr {
    match error {
        TaskError::Malformed { message, .. } => PyValueError::new_err(format!("no ARC task: {message}")),
        TaskError::Unreadable { error, .. } => PyValueError::new_err(format!("no ARC task: {error}")),
    }
}

#[pymethods]
impl PyTask {
    /// The task of ARC's JSON `text`, under `world`.
    #[staticmethod]
    fn from_json(text: &str, world: PyWorld) -> PyResult<PyTask> {
        let data = read_task(text, world.into()).map_err(task_error)?;
        Ok(PyTask { data: Arc::new(data) })
    }

    #[getter]
    fn world(&self) -> PyWorld {
        match self.data.world {
            World::Closed => PyWorld::Closed,
            World::Open => PyWorld::Open,
        }
    }

    #[getter]
    fn train_count(&self) -> usize {
        self.data.task.train.len()
    }

    #[getter]
    fn test_count(&self) -> usize {
        self.data.task.test.len()
    }
}
