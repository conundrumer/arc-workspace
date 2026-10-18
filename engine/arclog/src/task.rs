//! A task: its train pairs and its test inputs, read from a task file of
//! `data/tasks/`, and the rows of the fact relations `input`, `ex_input`
//! and `ex_output` that it gives.
//!
//! The examples of a task are its train pairs, then its test inputs, each
//! at its position in the file, as [`crate::terms::Example`] numbers them.

use std::path::{Path, PathBuf};

use crate::program::FactRelation;
use crate::relations::{Relation, RowSet};
use crate::terms::{Color, Constant, Example, Margins, Term};

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
        let width = rows.first()?.len();
        (width > 0 && rows.iter().all(|row| row.len() == width)).then_some(Grid { rows })
    }

    /// Each cell's color, with its Position in the grid's frame.
    fn cells(&self) -> impl Iterator<Item = (Margins, Color)> + '_ {
        let height = self.rows.len();
        self.rows.iter().enumerate().flat_map(move |(r, row)| {
            row.iter().enumerate().map(move |(c, &color)| (cell_position(r, c, height, row.len()), color))
        })
    }

    /// Each row, top to bottom.
    pub fn rows(&self) -> &[Box<[Color]>] {
        &self.rows
    }
}

/// The Position of the cell at `row` and `column` of a frame of `height`
/// rows and `width` columns: its margins from the frame's four edges.
pub(crate) fn cell_position(row: usize, column: usize, height: usize, width: usize) -> Margins {
    let (r, c, h, w) = (row as i32, column as i32, height as i32, width as i32);
    Margins { top: r, bottom: h - 1 - r, left: c, right: w - 1 - c }
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
    let text = std::fs::read_to_string(path).map_err(|error| TaskError::Unreadable { path: path.to_owned(), error })?;
    let malformed = |message: &str| TaskError::Malformed { path: path.to_owned(), message: message.into() };
    let json: serde_json::Value = serde_json::from_str(&text).map_err(|error| malformed(&error.to_string()))?;
    let grid = |value: &serde_json::Value| -> Result<Grid, TaskError> {
        let rows = value.as_array().ok_or_else(|| malformed("a grid that is no list of rows"))?;
        let rows = rows
            .iter()
            .map(|row| {
                let cells = row.as_array().ok_or_else(|| malformed("a row that is no list of cells"))?;
                cells
                    .iter()
                    .map(|cell| {
                        let digit = cell.as_u64().and_then(|d| u8::try_from(d).ok());
                        digit.and_then(Color::from_digit).ok_or_else(|| malformed("a cell that is no color"))
                    })
                    .collect::<Result<Box<[Color]>, TaskError>>()
            })
            .collect::<Result<Box<[Box<[Color]>]>, TaskError>>()?;
        Grid::from_rows(rows).ok_or_else(|| malformed("a grid that is empty or has rows of unequal lengths"))
    };
    let pairs = |key: &str| -> Result<&Vec<serde_json::Value>, TaskError> {
        json.get(key).and_then(|pairs| pairs.as_array()).ok_or_else(|| malformed(&format!("no list `{key}`")))
    };
    let field = |pair: &'_ serde_json::Value, key: &str| -> Result<Grid, TaskError> {
        grid(pair.get(key).ok_or_else(|| malformed(&format!("a pair with no `{key}`")))?)
    };
    let train = pairs("train")?
        .iter()
        .map(|pair| Ok(TrainPair { input: field(pair, "input")?, output: field(pair, "output")? }))
        .collect::<Result<Box<[TrainPair]>, TaskError>>()?;
    let test = pairs("test")?.iter().map(|pair| field(pair, "input")).collect::<Result<Box<[Grid]>, TaskError>>()?;
    Ok(Task { train, test })
}

impl Task {
    /// Each example: the train pairs, then the test inputs.
    pub fn examples(&self) -> impl Iterator<Item = Example> + '_ {
        let count = self.train.len() + self.test.len();
        (0..count).map(|index| Example::at(u16::try_from(index).expect("fewer than 2^16 examples in a task")))
    }

    /// The input grid of `example`.
    pub fn input(&self, example: Example) -> &Grid {
        let index = Term::Constant(Constant::Example(example)).encode().expect("an Example's term id").encoding() as usize;
        match self.train.get(index) {
            Some(pair) => &pair.input,
            None => &self.test[index - self.train.len()],
        }
    }

    /// The rows of `fact`, typed as [`crate::registry::Registry::fact_columns`]
    /// gives: `input` on `example`, a cell's Position in the input's frame
    /// and its Color, and `ex_input` and `ex_output`, task-wide, the same
    /// over each train pair with its Example first. `example` is `Some` for
    /// `input` alone, and any other pairing is a fault of the caller, so
    /// this panics on one.
    pub fn fact_rows(&self, fact: FactRelation, example: Option<Example>) -> Relation {
        let encode = |term: Term| term.encode().expect("a cell's margins lie within a byte");
        let mut rows = RowSet::empty(match fact {
            FactRelation::Input => 2,
            FactRelation::ExInput | FactRelation::ExOutput => 3,
        });
        match (fact, example) {
            (FactRelation::Input, Some(example)) => {
                for (position, color) in self.input(example).cells() {
                    rows.insert(Box::new([encode(Term::Box(position)), encode(Term::Constant(Constant::Color(color)))]));
                }
            }
            (FactRelation::ExInput | FactRelation::ExOutput, None) => {
                for (pair, index) in self.train.iter().zip(0u16..) {
                    let grid = if fact == FactRelation::ExInput { &pair.input } else { &pair.output };
                    let example = encode(Term::Constant(Constant::Example(Example::at(index))));
                    for (position, color) in grid.cells() {
                        rows.insert(Box::new([example, encode(Term::Box(position)), encode(Term::Constant(Constant::Color(color)))]));
                    }
                }
            }
            _ => panic!("`input` on an example, and `ex_input` and `ex_output` task-wide"),
        }
        crate::eval::join::one_part(rows)
    }
}
