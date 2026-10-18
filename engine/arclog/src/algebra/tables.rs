//! The tables of the orientation algebra, the fact sets of
//! `docs/lib-spec.md#algebra`: fact relations embedded in this file when the
//! engine is compiled, as the lib registry is, and the check at startup
//! that each table is D4-invariant, that the D4 action on every column maps
//! its rows onto its rows.

#![allow(unused_variables, dead_code)]

use crate::hash::StableHashMap;
use crate::registry::{LibName, Registry};
use crate::relations::RowSet;

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
    /// The tables, read once, on first use, from the text of this file, each
    /// checked by [`OrientationTables::check_invariance`]. A fault of a table
    /// is a fault of the engine's build, so this panics on one.
    pub fn get() -> &'static OrientationTables {
        todo!()
    }

    /// The rows of the table `name`, or `None` where there is none.
    pub fn rows(&self, name: &LibName) -> Option<&RowSet> {
        self.by_name.get(name)
    }

    /// Whether each table is D4-invariant, the D4 elements and their action
    /// on each orientation type those of `registry`.
    pub fn check_invariance(&self, registry: &Registry) -> Result<(), NotInvariant> {
        todo!()
    }
}
