//! The orientation algebra's relations, each the fact set of its table in
//! [`super::tables`], read through the table's rows.

#![allow(unused_variables, dead_code)]

use super::Algebra;
use super::tables::OrientationTables;
use crate::registry::Registry;
use crate::terms::{ReachedMarginBound, TermId};

/// A relation of the orientation algebra: the table of its registry name.
#[derive(Clone, Copy, PartialEq, Eq, Hash, Debug)]
pub struct OrientationRelation {
    name: &'static str,
}

impl OrientationRelation {
    /// The relation of the table `name`, or `None` where `tables` has no
    /// table of that name.
    pub fn of(name: &str, tables: &'static OrientationTables) -> Option<OrientationRelation> {
        todo!()
    }
}

impl Algebra for OrientationRelation {
    fn name(&self) -> &'static str {
        self.name
    }

    /// Each row of the table that agrees with `bound`. A table holds no Box,
    /// so this never reaches the margin bound.
    fn evaluate(
        &self,
        bound: &[Option<TermId>],
        registry: &Registry,
        emit: &mut dyn FnMut(&[TermId]),
    ) -> Result<(), ReachedMarginBound> {
        todo!()
    }
}
