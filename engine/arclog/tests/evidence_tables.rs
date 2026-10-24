//! The evidence tables of a task as the columns of a case: `ex_input` then
//! `ex_output`, at token 0 and point 2, with one entry for each example whose
//! grid the relation holds.

use arclog::decode::columns::{case_columns, PointKind, ValueKind};
use arclog::decode::evidence_tables;
use arclog::registry::Registry;
use arclog::task::read_task_text;

const TASK: &str = r#"{"train": [
    {"input": [[1, 2, 3], [4, 5, 6]], "output": [[7]]},
    {"input": [[0, 1], [2, 3], [4, 5]], "output": [[1, 2], [3, 4]]}],
  "test": [{"input": [[9, 8, 7, 6]]}]}"#;

/// The rows (example, top, bottom, left, right, color) of a grid, row by row.
fn grid_rows(example: i32, grid: &[&[i32]]) -> Vec<i32> {
    let (h, w) = (grid.len() as i32, grid[0].len() as i32);
    let mut rows = Vec::new();
    for (r, line) in grid.iter().enumerate() {
        for (c, &color) in line.iter().enumerate() {
            rows.extend([example, r as i32, h - 1 - r as i32, c as i32, w - 1 - c as i32, color]);
        }
    }
    rows
}

#[test]
fn the_evidence_tables_are_the_first_tables_of_a_case() {
    let task = read_task_text(TASK).expect("the task reads");
    let columns = case_columns(&evidence_tables(&task, Registry::get()), &[], 2);
    let tables = &columns.tables;
    assert_eq!(tables.fact, vec![Some("ex_input".to_owned()), Some("ex_output".to_owned())]);
    assert_eq!(tables.token, vec![0, 0]);
    assert_eq!(tables.point, vec![PointKind::Evidence as u8; 2]);
    assert_eq!(tables.form, vec![String::new(); 2]);
    assert_eq!(tables.relation, vec![-1, -1]);
    assert_eq!(tables.column_names, vec![vec!["E", "P", "Col"]; 2]);
    assert_eq!(tables.column_types, vec![vec!["Example", "Box", "Color"]; 2]);
    assert_eq!(tables.width, vec![6, 6]);
    assert_eq!(tables.views, vec![0, 0]);
    assert_eq!(tables.fault, vec![None, None]);

    let entries = &columns.entries;
    assert_eq!(entries.table, vec![0, 0, 0, 1, 1]);
    assert_eq!(entries.example_kind, vec![1, 1, 2, 1, 1]);
    assert_eq!(entries.example_index, vec![0, 1, 0, 0, 1]);
    assert_eq!(entries.kind, vec![ValueKind::Rows as u8; 5]);
    let grids: [(i32, &[&[i32]]); 5] = [
        (0, &[&[1, 2, 3], &[4, 5, 6]]),
        (1, &[&[0, 1], &[2, 3], &[4, 5]]),
        (2, &[&[9, 8, 7, 6]]),
        (0, &[&[7]]),
        (1, &[&[1, 2], &[3, 4]]),
    ];
    for (entry, (example, grid)) in grids.iter().enumerate() {
        let expected = grid_rows(*example, grid);
        let (count, offset) = (entries.rows[entry] as usize, entries.offset[entry] as usize);
        assert_eq!(count * 6, expected.len(), "the rows of entry {entry}");
        assert_eq!(columns.values[offset..offset + count * 6], expected[..], "the cells of entry {entry}");
    }
}
