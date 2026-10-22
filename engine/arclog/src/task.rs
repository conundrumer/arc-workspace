//! A task: its train pairs and its test inputs, read from a task file of
//! `data/tasks/`, and the rows of the fact relations `input`, `ex_input`
//! and `ex_output` that it gives; and the judged task, each pair's given
//! output and alt, which the judge reads from the same file.
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

/// The JSON of a task file, with the reader of its grids and pairs that
/// [`read_task`] and [`read_judged_task`] share.
struct TaskJson<'a> {
    path: &'a Path,
    json: serde_json::Value,
}

impl<'a> TaskJson<'a> {
    fn read(path: &'a Path) -> Result<TaskJson<'a>, TaskError> {
        let text = std::fs::read_to_string(path).map_err(|error| TaskError::Unreadable { path: path.to_owned(), error })?;
        TaskJson::parse(path, &text)
    }

    /// The JSON of `text`, which `path` names in a fault.
    fn parse(path: &'a Path, text: &str) -> Result<TaskJson<'a>, TaskError> {
        let json = serde_json::from_str(text).map_err(|error| malformed(path, &error.to_string()))?;
        Ok(TaskJson { path, json })
    }

    fn task(&self) -> Result<Task, TaskError> {
        let train = self
            .pairs("train")?
            .iter()
            .map(|pair| Ok(TrainPair { input: self.field(pair, "input")?, output: self.field(pair, "output")? }))
            .collect::<Result<Box<[TrainPair]>, TaskError>>()?;
        let test = self.pairs("test")?.iter().map(|pair| self.field(pair, "input")).collect::<Result<Box<[Grid]>, TaskError>>()?;
        Ok(Task { train, test })
    }

    /// The judge's view of the pairs under `key`.
    fn judged(&self, key: &str) -> Result<Box<[JudgedPair]>, TaskError> {
        self.pairs(key)?
            .iter()
            .map(|pair| Ok(JudgedPair { output: self.field(pair, "output")?, alt: self.alt(pair)? }))
            .collect()
    }

    fn malformed(&self, message: &str) -> TaskError {
        malformed(self.path, message)
    }

    fn grid(&self, value: &serde_json::Value) -> Result<Grid, TaskError> {
        let rows = value.as_array().ok_or_else(|| self.malformed("a grid that is no list of rows"))?;
        let rows = rows
            .iter()
            .map(|row| {
                let cells = row.as_array().ok_or_else(|| self.malformed("a row that is no list of cells"))?;
                cells
                    .iter()
                    .map(|cell| {
                        let digit = cell.as_u64().and_then(|d| u8::try_from(d).ok());
                        digit.and_then(Color::from_digit).ok_or_else(|| self.malformed("a cell that is no color"))
                    })
                    .collect::<Result<Box<[Color]>, TaskError>>()
            })
            .collect::<Result<Box<[Box<[Color]>]>, TaskError>>()?;
        Grid::from_rows(rows).ok_or_else(|| self.malformed("a grid that is empty or has rows of unequal lengths"))
    }

    fn pairs(&self, key: &str) -> Result<&[serde_json::Value], TaskError> {
        let pairs = self.json.get(key).and_then(|pairs| pairs.as_array());
        pairs.map(Vec::as_slice).ok_or_else(|| self.malformed(&format!("no list `{key}`")))
    }

    fn field(&self, pair: &serde_json::Value, key: &str) -> Result<Grid, TaskError> {
        self.grid(pair.get(key).ok_or_else(|| self.malformed(&format!("a pair with no `{key}`")))?)
    }

    /// The pair's `alt`, where it has one.
    fn alt(&self, pair: &serde_json::Value) -> Result<Option<Alt>, TaskError> {
        let Some(alt) = pair.get("alt") else { return Ok(None) };
        let kind = match alt.get("kind").and_then(|kind| kind.as_str()) {
            Some("rule") => AltKind::Rule,
            Some("tiebreak") => AltKind::Tiebreak,
            _ => return Err(self.malformed("an alt whose kind is neither `rule` nor `tiebreak`")),
        };
        Ok(Some(Alt { kind, grid: self.field(alt, "grid")? }))
    }
}

fn malformed(path: &Path, message: &str) -> TaskError {
    TaskError::Malformed { path: path.to_owned(), message: message.into() }
}

/// The task of the file at `path`.
pub fn read_task(path: &Path) -> Result<Task, TaskError> {
    TaskJson::read(path)?.task()
}

/// The path that a fault of a task read from text names.
const TEXT_PATH: &str = "<text>";

/// The task of the JSON `text`, in the ARC form of a task file.
pub fn read_task_text(text: &str) -> Result<Task, TaskError> {
    TaskJson::parse(Path::new(TEXT_PATH), text)?.task()
}

/// The kind of an alt output, as `docs/handbook/solver-file.md#alt-outputs`
/// gives.
#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub enum AltKind {
    Rule,
    Tiebreak,
}

/// The alt of a pair: its kind and its grid.
#[derive(Clone, PartialEq, Eq, Debug)]
pub struct Alt {
    pub kind: AltKind,
    pub grid: Grid,
}

/// A pair as the judge reads it: its given output, and its alt where the
/// file gives one.
#[derive(Clone, PartialEq, Eq, Debug)]
pub struct JudgedPair {
    pub output: Grid,
    pub alt: Option<Alt>,
}

/// The pairs of a task file as the judge reads them, as
/// `docs/engine/cases.md#candidates` gives: the train pairs, then the test
/// pairs, in the file's order.
#[derive(Clone, PartialEq, Eq, Debug)]
pub struct JudgedTask {
    pub train: Box<[JudgedPair]>,
    pub test: Box<[JudgedPair]>,
}

/// The judged task of the file at `path`.
pub fn read_judged_task(path: &Path) -> Result<JudgedTask, TaskError> {
    let file = TaskJson::read(path)?;
    Ok(JudgedTask { train: file.judged("train")?, test: file.judged("test")? })
}

/// The judged train pairs of the JSON `text`, which may hold no test
/// outputs, as Kaggle's task files hold none.
pub fn read_judged_train_text(text: &str) -> Result<Box<[JudgedPair]>, TaskError> {
    TaskJson::parse(Path::new(TEXT_PATH), text)?.judged("train")
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
    /// and its Color, and, task-wide with the Example first, `ex_input` the
    /// same over the input of each example, train and test, and `ex_output`
    /// over the output of each train pair. `example` is `Some` for
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
                let grids: Box<dyn Iterator<Item = (Example, &Grid)>> = if fact == FactRelation::ExInput {
                    Box::new(self.examples().map(|example| (example, self.input(example))))
                } else {
                    Box::new(self.train.iter().zip(0u16..).map(|(pair, index)| (Example::at(index), &pair.output)))
                };
                for (example, grid) in grids {
                    let example = encode(Term::Constant(Constant::Example(example)));
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
