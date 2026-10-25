//! The D4 check of the orientation algebra's tables refuses a table that
//! the D4 action does not map onto itself.

use arclog::algebra::tables::{OrientationTables, TABLES_TEXT};
use arclog::registry::{LibName, Registry};

#[test]
fn a_table_that_is_not_invariant_refuses() {
    let registry = Registry::get();
    let tables = OrientationTables::parse(TABLES_TEXT, registry).expect("the tables file parses");
    assert_eq!(tables.check_invariance(registry), Ok(()));
    let written = "(table perp\n  (AXIS_V AXIS_H) (AXIS_H AXIS_V))";
    assert!(TABLES_TEXT.contains(written));
    let text = TABLES_TEXT.replacen(written, "(table perp\n  (AXIS_V AXIS_H))", 1);
    let tables = OrientationTables::parse(&text, registry).expect("the changed file parses");
    let fault = tables.check_invariance(registry).expect_err("`perp` with one row is not invariant");
    assert_eq!(fault.table, LibName("perp".into()));
}
