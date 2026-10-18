//! The tables of the orientation algebra, the fact sets of
//! `docs/lib-spec.md#algebra`: fact relations embedded from
//! `engine/lib/tables.sexpr` when the engine is compiled, as the lib
//! registry is, and the check at startup that each table is D4-invariant,
//! that the D4 action on every column maps its rows onto its rows.
//!
//! The file holds one form `(table <name> (<constant> ...) ...)` per table:
//! a relation that the registry declares, then each of its rows, one
//! constant per column of the relation, in the order of its columns, each a
//! constant of its column's type.

use super::orientation::Geometry;
use crate::check::CheckId;
use crate::diagnostic::Diagnostic;
use crate::hash::StableHashMap;
use crate::layout::SourceFile;
use crate::program::DataValue;
use crate::read::{check_error, read_sexprs, SExpr};
use crate::registry::{LibEntry, LibName, Registry};
use crate::relations::RowSet;
use crate::terms::{encode_data_value, InternTable, Term};
use crate::types::ValueType;

/// The text of the tables file, which [`OrientationTables::get`] reads.
pub const TABLES_TEXT: &str = include_str!("../../../lib/tables.sexpr");

/// The tables of the orientation algebra, by their registry names, each its
/// rows as term ids.
#[derive(Debug, Default)]
pub struct OrientationTables {
    by_name: StableHashMap<LibName, RowSet>,
}

/// A table whose rows the D4 action does not map onto its rows: one of its
/// rows, under one D4 element, lands on no row of the table.
#[derive(Clone, PartialEq, Eq, Debug)]
pub struct NotInvariant {
    pub table: LibName,
    pub element: crate::terms::OrientationConstant,
}

impl OrientationTables {
    /// The tables, read once, on first use, from [`TABLES_TEXT`], each
    /// checked by [`OrientationTables::check_invariance`]. A fault of a table
    /// is a fault of the engine's build, so this panics on one.
    pub fn get() -> &'static OrientationTables {
        static TABLES: std::sync::OnceLock<OrientationTables> = std::sync::OnceLock::new();
        TABLES.get_or_init(|| {
            let registry = Registry::get();
            let tables = match OrientationTables::parse(TABLES_TEXT, registry) {
                Ok(tables) => tables,
                Err(diagnostics) => panic!("the tables file does not parse: {diagnostics:?}"),
            };
            if let Err(fault) = tables.check_invariance(registry) {
                panic!("the table {} is not invariant under {}", fault.table.0, registry.constant_name(fault.element));
            }
            tables
        })
    }

    /// The tables that `text` writes, in the form of the module comment, over
    /// the relations and constants of `registry`.
    ///
    /// Fails with a diagnostic at each fault of the text.
    pub fn parse(text: &str, registry: &Registry) -> Result<OrientationTables, Vec<Diagnostic>> {
        let (forms, _) = read_sexprs(text, SourceFile::LibRegistry)?;
        let mut tables = OrientationTables::default();
        let mut faults = Vec::new();
        let mut interned = InternTable::default();
        let mut fault = |message: String, expr: &SExpr| faults.push(check_error(CheckId::Grammar, message, expr.place()));
        for form in &forms {
            let SExpr::List { items, .. } = form else {
                fault("a table is a list".into(), form);
                continue;
            };
            let (Some(SExpr::Symbol { text: head, .. }), Some(SExpr::Symbol { text: name, .. })) = (items.first(), items.get(1)) else {
                fault("a table is `(table <name> <row> ...)`".into(), form);
                continue;
            };
            let name = LibName(name.clone());
            let Some(LibEntry::Relation(relation)) = registry.entry(&name).filter(|_| &**head == "table") else {
                fault(format!("`{}` is no `(table <name> ...)` of a relation of the registry", name.0), form);
                continue;
            };
            let types: Vec<ValueType> =
                relation.columns.iter().map(|column| column.ty.fixed().cloned().expect("a table's column of a fixed type")).collect();
            let mut rows = RowSet::empty(types.len() as u16);
            for row in &items[2..] {
                match encode_row(row, &types, registry, &mut interned) {
                    Ok(ids) => {
                        rows.insert(ids.into());
                    }
                    Err(message) => fault(message, row),
                }
            }
            if tables.by_name.insert(name.clone(), rows).is_some() {
                fault(format!("a second table `{}`", name.0), form);
            }
        }
        if faults.is_empty() { Ok(tables) } else { Err(faults) }
    }

    /// The rows of the table `name`, or `None` where there is none.
    pub fn rows(&self, name: &LibName) -> Option<&RowSet> {
        self.by_name.get(name)
    }

    /// The name of each table.
    pub fn names(&self) -> impl Iterator<Item = &LibName> + '_ {
        self.by_name.keys()
    }

    /// Whether each table is D4-invariant, the D4 elements and their action
    /// on each orientation type those of `registry`.
    pub fn check_invariance(&self, registry: &Registry) -> Result<(), NotInvariant> {
        let geometry = Geometry::of(registry);
        for (table, rows) in &self.by_name {
            for &element in geometry.domain(&ValueType::D4) {
                let g = geometry.element(element);
                let lands = rows.rows().all(|row| {
                    let image: Vec<_> = row.iter().map(|&value| geometry.under(g, value)).collect();
                    rows.contains(&image)
                });
                if !lands {
                    let Term::Constant(crate::terms::Constant::Orientation(element)) = Term::decode(element, &ValueType::D4) else {
                        unreachable!("a D4 constant")
                    };
                    return Err(NotInvariant { table: table.clone(), element });
                }
            }
        }
        Ok(())
    }
}

/// The term ids of the row `row`, whose columns take `types` in order.
fn encode_row(
    row: &SExpr,
    types: &[ValueType],
    registry: &Registry,
    interned: &mut InternTable,
) -> Result<Vec<crate::terms::TermId>, String> {
    let SExpr::List { items, .. } = row else { return Err("a row is a list of constants".into()) };
    if items.len() != types.len() {
        return Err(format!("a row of {} constants, for {} columns", items.len(), types.len()));
    }
    let mut ids = Vec::with_capacity(types.len());
    for (item, ty) in items.iter().zip(types) {
        let SExpr::Symbol { text, .. } = item else { return Err("a row's value is a constant".into()) };
        let value = DataValue::Orientation(text.clone());
        let encoded = encode_data_value(&value, ty, registry, interned)
            .map_err(|_| format!("`{text}` is no constant of {ty:?}"))?;
        ids.extend(encoded.iter().copied());
    }
    Ok(ids)
}
