//! The static types of columns and labels: the lattice of the types in the
//! module `lattice` (`C4` under `D4`, `Dir` and `DiagDir` under `Dir8`, `Axis`
//! and `DiagAxis` under `Axis4`, and `Position` and `Offset` under `Box`), and
//! the identity of the Pose type of a `RIGID_DET` assembly here. The type of a
//! label over its scope is in the module `label_walk`, the walks over a body's
//! sites and conjuncts in `body_walks`, and the types of a checked program,
//! which the check hands on, in `program_types`.

mod body_walks;
mod label_walk;
mod lattice;
mod program_types;

pub use body_walks::{each_atom, each_conjunct, each_site_label, each_site_use, use_label};
pub(crate) use body_walks::column_label;
pub(crate) use label_walk::{flat_label_types, fresh_in_nested_form, label_binding_type_cached, label_fault_message, label_type_cached, list_class, meet, scope_lists, settle_label_types, typed, TypedLabels, WalkCache, ZeroMade};
pub use label_walk::{label_type, label_type_keyed, LabelFault};
pub use lattice::{Meet, ValueType};
pub use program_types::{FormRelation, FormTypes, GraphRelation, ProgramTypes};

/// One `RIGID_DET` assembly of a case program, which has its own Pose type:
/// its form, by the form's name and canonical form, and, for a keyed form,
/// its key row, by the labels that a read gives at the key's columns. It
/// compares as a key of canonical parts does ([`crate::program`]).
///
/// The form's name and canonical form stay the same in every case that holds
/// the form, so the cases that share a form that reads a pose share its types
/// and its check, whatever alts come before it, and two forms of one name
/// with different parts, in two programs of one task session, take two types.
/// Two pose reads meet only where they read the same key labels
/// (`docs/arclog/rigid.md#form`). The key row is named as [`KeyRow`] gives.
#[derive(Clone, PartialEq, Eq, Hash, Debug)]
pub struct AssemblyId {
    pub name: crate::program::RigidDetName,
    pub canonical_form: crate::program::canonical::CanonicalForm,
    /// The key row, or [`KeyRow::Unkeyed`] for a form with no key.
    pub key: KeyRow,
}

/// How a Pose type names its key row: in a scope, by the labels a read gives
/// at the key's columns; at a column of a derived relation or an instance's
/// input, by the positions of the relation's columns that hold the key. A
/// read of the relation maps the positions to the labels at them
/// (`docs/arclog/rigid.md#the-pose`).
#[derive(Clone, PartialEq, Eq, Hash, Debug)]
pub enum KeyRow {
    Unkeyed,
    /// The labels at the key's columns, in the key's order, local to the
    /// scope of the reads, as [`crate::program::LabelId`] gives.
    Labels(Box<[crate::program::LabelId]>),
    /// The positions of the relation's columns that hold the key, in the
    /// key's order.
    Columns(Box<[u16]>),
}
