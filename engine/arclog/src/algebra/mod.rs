//! The algebra relations of the lib, native: the box algebra in [`boxes`],
//! and the orientation algebra in [`orientation`], over the fact sets of
//! [`tables`].
//!
//! An algebra relation is evaluated at a mode its bound columns satisfy, as
//! the registry's [`crate::registry::Mode`] gives, and a relation over a
//! finite domain at any binding. Each gives its rows as a set: a binding
//! has every row that holds it, so no relation chooses among them.

#![allow(unused_variables, dead_code)]

pub mod boxes;
pub mod orientation;
pub mod tables;

use crate::registry::{AlgebraRelation, LibName, Registry};
use crate::terms::{ReachedMarginBound, TermId};

/// An algebra relation of the lib, evaluated natively.
pub trait Algebra: Send + Sync {
    /// The relation's name in the registry, such as `margin`.
    fn name(&self) -> &'static str;

    /// Calls `emit` on each row of the relation that agrees with `bound`,
    /// one entry per column, `Some` at each bound column. The bound columns
    /// satisfy a mode of the relation, or the relation has none. A Box with
    /// a margin outside a signed byte that would reach a row stops it.
    fn evaluate(
        &self,
        bound: &[Option<TermId>],
        registry: &Registry,
        emit: &mut dyn FnMut(&[TermId]),
    ) -> Result<(), ReachedMarginBound>;
}

/// The algebra relation of `name`, or `None` where the lib has none of that
/// name.
pub fn algebra(name: &LibName) -> Option<&'static dyn Algebra> {
    todo!()
}

/// The index in `relation`'s modes of the first mode whose columns are all
/// among the bound columns, `bound` one entry per column; `None` where none
/// is, or where the relation has no mode. A column of an orientation type
/// is bound by its finite domain, so a mode never lists one.
pub fn satisfied_mode(relation: &AlgebraRelation, bound: &[bool]) -> Option<usize> {
    todo!()
}
