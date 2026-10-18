//! The algebra relations and relation macros of the lib, native: the box
//! algebra in [`boxes`], and the orientation algebra in [`orientation`],
//! over the fact sets of [`tables`].
//!
//! An algebra relation is evaluated at a mode its bound columns satisfy, as
//! the registry's [`crate::registry::Mode`] gives, and a relation over a
//! finite domain at any binding. Each gives its rows as a set: a binding
//! has every row that holds it, so no relation chooses among them.

pub mod boxes;
pub mod orientation;
pub mod tables;

use crate::hash::StableHashMap;
use crate::registry::{AlgebraRelation, LibEntry, LibName, Macro, Registry};
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

/// The algebra relation or relation macro of `name`, or `None` where the
/// lib has none of that name.
pub fn algebra(name: &LibName) -> Option<&'static dyn Algebra> {
    static RELATIONS: std::sync::OnceLock<StableHashMap<LibName, &'static dyn Algebra>> = std::sync::OnceLock::new();
    // The first lookup of any relation reads the tables and checks them, so
    // a table that is not D4-invariant stops the first evaluation of a lib
    // atom before it starts.
    let relations = RELATIONS.get_or_init(|| {
        let boxes = boxes::BoxRelation::ALL.iter().map(|r| (LibName(r.name().into()), r as &'static dyn Algebra));
        let orientation = orientation::OrientationRelation::all().map(|(name, r)| (name.clone(), r as &'static dyn Algebra));
        boxes.chain(orientation).collect()
    });
    relations.get(name).copied()
}

/// The index in `relation`'s modes of the first mode whose columns are all
/// among the bound columns, `bound` one entry per column; `None` where none
/// is, or where the relation has no mode. A column of an orientation type
/// is bound by its finite domain, so a mode never lists one.
pub fn satisfied_mode(relation: &AlgebraRelation, bound: &[bool]) -> Option<usize> {
    let is_bound = |name: &crate::program::ColumnName| relation.columns.iter().position(|column| column.name == *name).is_some_and(|i| bound[i]);
    relation.modes.iter().position(|mode| mode.grounded.iter().all(is_bound))
}

/// The declaration of the algebra relation or relation macro `name`.
fn declaration<'r>(registry: &'r Registry, name: &str) -> &'r AlgebraRelation {
    match registry.entry(&LibName(name.into())) {
        Some(LibEntry::Relation(relation)) | Some(LibEntry::Macro(Macro::Relation { relation, .. })) => relation,
        _ => panic!("`{name}` is an algebra relation or a relation macro of the registry"),
    }
}
