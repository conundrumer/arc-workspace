//! The tables of a stream that ends at an `OUT` form mark the columns it
//! selects: the Position column in the table of the relation of the atom that
//! selects it, and the Color column in the table of the relation of the atom
//! that selects that, and no other table.

use arclog::eval::instance::Constructions;
use arclog::registry::Registry;
use arclog::stream::DecodeSettings;
use arclog_tables::columns::case_columns;
use arclog_tables::corpus::solver_tables;
use arclog_tables::tables::{evidence_tables, Points};

/// The `(output_position, output_color)` of each table of the concept case of
/// a solver of one train pair `1 1 -> 1 1`, whose arclog file is `arclog`.
fn marks(arclog: &str) -> Vec<(i32, i32)> {
    let dir = std::env::temp_dir().join(format!("arclog-output-marks-{}-{}", std::process::id(), arclog.len()));
    std::fs::create_dir_all(&dir).expect("a temporary directory");
    let pair = r#"{"input": [[1, 1]], "output": [[1, 1]]}"#;
    std::fs::write(dir.join("marks.arclog"), arclog).expect("the arclog file");
    std::fs::write(dir.join("marks.arcdata"), ";; marks\n").expect("the arcdata file");
    std::fs::write(dir.join("marks.json"), format!(r#"{{"train": [{pair}], "test": [{pair}]}}"#)).expect("the task file");
    let registry = Registry::get();
    let constructions = Constructions::new(Vec::new(), registry).expect("an empty table");
    let solver = solver_tables(&dir, &dir, "marks", false, Points::Relations, &constructions, &DecodeSettings::default());
    let (task, _) = arclog::decode::corpus::read_task_files(&dir, "marks").expect("the task reads");
    std::fs::remove_dir_all(&dir).ok();
    let solver = solver.expect("the solver's tables");
    let tables = solver.cases[0].tables.as_ref().expect("the case's tables");
    let columns = case_columns(&evidence_tables(&task, registry), tables, solver.train);
    columns.tables.output_position.iter().copied().zip(columns.tables.output_color.iter().copied()).collect()
}

#[test]
fn the_table_of_the_relation_of_each_atom_marks_the_column_it_selects() {
    // The evidence tables, then `&r`, which an `OUT` of one atom reads at both columns.
    assert_eq!(marks("(RULE &r (input *P *Col))\n(OUT (&r ^P ^Col))\n"), [(-1, -1), (-1, -1), (0, 1)]);
    // `&pos` and `&colr`, one atom each.
    assert_eq!(marks("(RULE &pos (input *P))\n(RULE &colr (input *Col))\n(OUT (&pos ^P) (&colr ^Col))\n"), [(-1, -1), (-1, -1), (0, -1), (-1, 0)]);
    // A relation that no table holds, `input`, marks none.
    assert_eq!(marks("(RULE &colr (input *Col))\n(OUT (input ^P) (&colr ^Col))\n"), [(-1, -1), (-1, -1), (-1, 0)]);
    // A relation that the `OUT` does not read marks none.
    assert_eq!(marks("(RULE &r (input *P *Col))\n(RULE &other (input *P *Col))\n(OUT (&r ^P ^Col))\n"), [(-1, -1), (-1, -1), (0, 1), (-1, -1)]);
}
