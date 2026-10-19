//! The columns that the registry declares for a lib relation, a relation
//! macro, a proposer or a fact relation that a read names, with their
//! types, and the component an `INIT` form names.

use super::columns::Columns;
use crate::program::{ColumnName, RelationRef};
use crate::registry::{Column, ColumnType, Component, LibEntry, LibName, Macro, Registry};

fn of_columns(columns: &[Column]) -> Columns {
    Columns::of_names(columns.iter().map(|column| column.name.clone()))
}

/// The columns of a lib relation or a proposer that an atom reads.
pub(super) fn lib_columns(registry: &Registry, name: &LibName) -> Option<Columns> {
    match registry.entry(name)? {
        LibEntry::Relation(relation) | LibEntry::Macro(Macro::Relation { relation, .. }) => Some(of_columns(&relation.columns)),
        LibEntry::Proposer(proposer) => Some(of_columns(&proposer.columns)),
        LibEntry::Component(_) => None,
    }
}

/// Whether `ty` is the type `Example`.
pub(super) fn is_example(ty: &ColumnType) -> bool {
    *ty == ColumnType::Fixed(crate::types::ValueType::Example)
}

/// The names of `columns` of the type `Example`.
pub(super) fn examples(columns: &[Column]) -> impl Iterator<Item = ColumnName> + '_ {
    columns.iter().filter(|column| is_example(&column.ty)).map(|column| column.name.clone())
}

/// The declared columns, with their types, of the fact, the lib
/// relation, the relation macro or the proposer that `relation` names.
pub(crate) fn typed_columns<'r>(registry: &'r Registry, relation: &RelationRef) -> Option<&'r [Column]> {
    match relation {
        RelationRef::Fact(fact) => Some(registry.fact_columns(*fact)),
        RelationRef::Lib(name) => lib_typed_columns(registry, name),
        RelationRef::Declared(_) | RelationRef::Output(_) | RelationRef::DefinedPort(_) => None,
    }
}

/// The declared columns, with their types, of the lib relation, the
/// relation macro or the proposer `name`.
pub(crate) fn lib_typed_columns<'r>(registry: &'r Registry, name: &LibName) -> Option<&'r [Column]> {
    match registry.entry(name)? {
        LibEntry::Relation(relation) | LibEntry::Macro(Macro::Relation { relation, .. }) => Some(&relation.columns),
        LibEntry::Proposer(proposer) => Some(&proposer.columns),
        LibEntry::Component(_) => None,
    }
}

/// The columns of a proposer that a `DET` names, in the proposer's order.
pub(crate) fn proposer_columns(registry: &Registry, name: &LibName) -> Option<Box<[ColumnName]>> {
    match registry.entry(name) {
        Some(LibEntry::Proposer(proposer)) => Some(proposer.columns.iter().map(|c| c.name.clone()).collect()),
        _ => None,
    }
}

/// Whether `name` is a proposer that a `DET` can name.
pub(super) fn is_proposer(registry: &Registry, name: &LibName) -> bool {
    matches!(registry.entry(name), Some(LibEntry::Proposer(_)))
}

/// The component an `INIT` form names: a construction, a detector or a
/// task-structure component.
pub(crate) fn component<'r>(registry: &'r Registry, name: &LibName) -> Option<&'r Component> {
    match registry.entry(name)? {
        LibEntry::Component(component) => Some(component),
        LibEntry::Relation(_) | LibEntry::Proposer(_) | LibEntry::Macro(Macro::Relation { .. }) => None,
    }
}
