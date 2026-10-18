//! A task: its train pairs and its test inputs, read from a task file of
//! `data/tasks/`, and the rows of the fact relations `input`, `ex_input`
//! and `ex_output` that it gives.
//!
//! The examples of a task are its train pairs, then its test inputs, each
//! at its position in the file, as [`crate::terms::Example`] numbers them.

#![allow(unused_variables, dead_code)]

use std::path::{Path, PathBuf};

use crate::program::FactRelation;
use crate::relations::Relation;
use crate::terms::{Color, Example};

/// A grid of colors: its rows, each of one length, at least one row and one
/// column.
#[derive(Clone, PartialEq, Eq, Hash, Debug)]
pub struct Grid {
    rows: Box<[Box<[Color]>]>,
}

impl Grid {
    /// The grid of `rows`, or `None` where the rows are empty or of unequal
    /// lengths.
    pub fn from_rows(rows: Box<[Box<[Color]>]>) -> Option<Grid> {
        todo!()
    }

    /// Each row, top to bottom.
    pub fn rows(&self) -> &[Box<[Color]>] {
        &self.rows
    }
}

/// A train pair: an input grid and its output grid.
#[derive(Clone, PartialEq, Eq, Debug)]
pub struct TrainPair {
    pub input: Grid,
    pub output: Grid,
}

/// A task: its train pairs and its test inputs, in the file's order.
#[derive(Clone, PartialEq, Eq, Debug)]
pub struct Task {
    pub train: Box<[TrainPair]>,
    /// The test inputs. A test output in the file is the judge's, and the
    /// evaluation reads none.
    pub test: Box<[Grid]>,
}

/// A fault of a task file: it cannot be read, it is no JSON, or its JSON
/// holds no task of the ARC form.
#[derive(Debug)]
pub enum TaskError {
    Unreadable { path: PathBuf, error: std::io::Error },
    Malformed { path: PathBuf, message: Box<str> },
}

/// The task of the file at `path`.
pub fn read_task(path: &Path) -> Result<Task, TaskError> {
    todo!()
}

impl Task {
    /// Each example: the train pairs, then the test inputs.
    pub fn examples(&self) -> impl Iterator<Item = Example> + '_ {
        let count = self.train.len() + self.test.len();
        (0..count).map(|index| Example::at(u16::try_from(index).expect("fewer than 2^16 examples in a task")))
    }

    /// The input grid of `example`.
    pub fn input(&self, example: Example) -> &Grid {
        todo!()
    }

    /// The rows of `fact`, typed as [`crate::registry::Registry::fact_columns`]
    /// gives: `input` on `example`, a cell's Position in the input's frame
    /// and its Color, and `ex_input` and `ex_output`, task-wide, the same
    /// over each train pair with its Example first. `example` is `Some` for
    /// `input` alone, and any other pairing is a fault of the caller, so
    /// this panics on one.
    pub fn fact_rows(&self, fact: FactRelation, example: Option<Example>) -> Relation {
        todo!()
    }
}
