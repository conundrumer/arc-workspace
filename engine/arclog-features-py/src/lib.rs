//! The Python extension module `arclog_features`: the features of a table at
//! one assignment, on rows that Python stored. It links `arclog-features` alone
//! and holds one function, [`features`]. The module's constants are
//! `FEATURES_VERSION` (the hash of the feature names) and `TYPE_NAMES` (the
//! names of the column types that have a feature `t_<name>` of their own).

use std::collections::BTreeMap;

use arclog_features::{cell_width, type_code, Grid, Input, Pair, TableRows, EXAMPLE};
use pyo3::buffer::PyBuffer;
use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;

/// The grid of `rows`, each a list of color digits.
fn grid(rows: Vec<Vec<u8>>) -> PyResult<Grid> {
    let width = rows.first().map_or(0, Vec::len);
    if rows.iter().any(|row| row.len() != width) {
        return Err(PyValueError::new_err("the rows of a grid have unequal lengths"));
    }
    Ok(Grid { height: rows.len(), width, cells: rows.into_iter().flatten().collect() })
}

/// The features of a table at one assignment: `(names, values)`, one value for
/// each name, in the order of the names.
///
/// - `types`: the type of each column, as `ValueType`'s `Debug` spells it, without the Ident source.
/// - `cells`: an `int32` buffer of the rows' cells in the export's own encoding,
///   row by row, a row being as wide as the types say (a Box, Position or Offset
///   has four cells, any other column one).
/// - `example_column`: the index of the Example column of the rows, or None where the Type has none. Without it,
///   `bounds` and `examples` are required, and each TableRows is at the example that `examples` gives.
/// - `train`: the task's train pairs, each `(input, output)`, a grid being a list of rows of color digits. Pass them for
///   a task-level table too.
/// - `task_level`: whether the table is task-level, with no train example in it.
/// - `capped`: whether the table's own state sequence stopped at the 256 cap.
/// - `bounds`: the index of the first row of each TableRows, in non-decreasing order,
///   from 0. A TableRows that ends where the next starts (or at the last row) is an
///   empty TableRows: it has 0 rows and counts as a TableRows of its example. With none,
///   the rows of one Example value are one TableRows.
/// - `examples`: with `bounds`, the example of each TableRows, as the index among the
///   train examples and then the test examples. A non-empty TableRows is at its rows'
///   Example value, so this gives the example of an empty TableRows, and is required
///   where `bounds` has one.
///
/// A train example with no TableRows has 0 rows.
#[pyfunction]
#[pyo3(signature = (types, cells, example_column, train, bounds=None, examples=None, task_level=false, capped=false))]
fn features(py: Python<'_>, types: Vec<String>, cells: PyBuffer<i32>, example_column: Option<usize>, train: Vec<(Vec<Vec<u8>>, Vec<Vec<u8>>)>, bounds: Option<Vec<usize>>, examples: Option<Vec<u32>>, task_level: bool, capped: bool) -> PyResult<(Vec<&'static str>, Vec<f32>)> {
    let cells = cells.to_vec(py)?;
    let codes: Vec<u8> = types.iter().map(|name| type_code(name)).collect();
    let width: usize = codes.iter().map(|&code| cell_width(code)).sum();
    if width == 0 || cells.len() % width != 0 {
        return Err(PyValueError::new_err(format!("{} cells are no whole count of rows of {width} cells", cells.len())));
    }
    if example_column.is_some_and(|column| codes.get(column) != Some(&EXAMPLE)) {
        return Err(PyValueError::new_err("`example_column` is no column of type Example"));
    }
    if example_column.is_none() && (bounds.is_none() || examples.is_none()) {
        return Err(PyValueError::new_err("without `example_column`, `bounds` and `examples` are required"));
    }
    let at: usize = example_column.map_or(0, |column| codes[..column].iter().map(|&code| cell_width(code)).sum());
    let count = cells.len() / width;
    let pairs = train.into_iter().map(|(input, output)| Ok(Pair { input: grid(input)?, output: grid(output)? })).collect::<PyResult<Vec<_>>>()?;
    let mut pieces: Vec<(u32, usize, Vec<i32>)> = Vec::new();
    match bounds {
        Some(starts) => {
            if starts.windows(2).any(|pair| pair[0] > pair[1]) || starts.last().is_some_and(|&last| last > count) || starts.first().is_some_and(|&first| first != 0) {
                return Err(PyValueError::new_err("`bounds` must not decrease, must start at 0 and must not pass the count of rows"));
            }
            if examples.as_ref().is_some_and(|examples| examples.len() != starts.len()) {
                return Err(PyValueError::new_err("`examples` must give one example for each of `bounds`"));
            }
            for (place, &start) in starts.iter().enumerate() {
                let end = starts.get(place + 1).copied().unwrap_or(count);
                let example = match (&examples, end == start) {
                    (Some(examples), _) => examples[place],
                    (None, false) => cells[start * width + at] as u32, // example_column is Some here
                    (None, true) => return Err(PyValueError::new_err("`examples` is required where `bounds` has an empty TableRows")),
                };
                pieces.push((example, end - start, cells[start * width..end * width].to_vec()));
            }
        }
        None => {
            // `example_column` is Some where `bounds` is None.
            let mut grouped: BTreeMap<i32, Vec<i32>> = BTreeMap::new();
            for row in cells.chunks_exact(width) {
                grouped.entry(row[at]).or_default().extend_from_slice(row);
            }
            pieces.extend(grouped.into_iter().map(|(example, group)| (example as u32, group.len() / width, group)));
        }
    }
    let rows: Vec<TableRows<'_>> = pieces.iter().map(|(example, count, cells)| TableRows { example: *example, count: *count, cells }).collect();
    let names: Vec<&str> = types.iter().map(String::as_str).collect();
    let input = Input { types: &names, example_column, rows: &rows, train: &pairs, capped, task_level };
    Ok((arclog_features::names().collect(), arclog_features::vector(&input)))
}

#[pymodule]
#[pyo3(name = "arclog_features")]
fn features_module(module: &Bound<'_, PyModule>) -> PyResult<()> {
    module.add_function(wrap_pyfunction!(features, module)?)?;
    module.add("FEATURES_VERSION", arclog_features::version())?;
    module.add("TYPE_NAMES", arclog_features::TYPE_NAMES.to_vec())
}
