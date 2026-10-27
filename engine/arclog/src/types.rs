//! The static types of columns and labels, and their lattice: `C4` under
//! `D4`, `Dir` and `DiagDir` under `Dir8`, `Axis` and `DiagAxis` under
//! `Axis4`, and `Position` and `Offset` as `Box`. A Pose type is below and
//! above no other type. The type of a label over its scope is in the module
//! `label_walk`, the walks over a body's sites and conjuncts in `body_walks`,
//! and the types of a checked program, which the check hands on, in
//! `program_types`.

mod body_walks;
mod label_walk;
mod program_types;

pub use body_walks::{each_atom, each_conjunct, each_site_label, each_site_use, use_label};
pub(crate) use label_walk::{fresh_in_nested_form, label_fault_message, label_type_cached, list_class, meet, scope_lists, WalkCache, ZeroMade};
pub use label_walk::{label_type, label_type_keyed, LabelFault};
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

/// The type of a column or a label, which the type check infers for each
/// label over the lattice of the types.
///
/// `Position` and `Offset` are the type `Box`, so neither has a variant of
/// its own.
#[derive(Clone, PartialEq, Eq, Hash, Debug)]
pub enum ValueType {
    Number,
    Color,
    Example,
    Unit,
    Box,
    Ident,
    C4,
    D4,
    Dir,
    DiagDir,
    Dir8,
    Axis,
    DiagAxis,
    Axis4,
    Sym,
    Sense,
    /// The Pose type of one `RIGID_DET` assembly.
    Pose(AssemblyId),
    /// A record bound to a type parameter (`docs/arclog/arclog.md#instance`),
    /// each field by the column name of its site or of its key column: the
    /// name written, or, in a decoded program, the slot. The engine has no
    /// record values, so each field takes a column of its own.
    Record(Box<[(crate::program::ColumnName, ValueType)]>),
}

/// The result of the meet of two types.
#[derive(Clone, PartialEq, Eq, Debug)]
pub enum Meet {
    /// The greatest type below both.
    Type(ValueType),
    /// No type is below both, so a label of both types holds no value.
    Empty,
}

impl ValueType {
    /// The meet of two types: the type of a label with both types' sites.
    pub fn meet(&self, other: &ValueType) -> Meet {
        if self.is_below(other) {
            return Meet::Type(self.clone());
        }
        if other.is_below(self) {
            return Meet::Type(other.clone());
        }
        Meet::Empty
    }

    /// The join of two types: the type of a label that an `OR` or an `IF`
    /// exports from branches of these types, or `None` where no type is above
    /// both.
    pub fn join(&self, other: &ValueType) -> Option<ValueType> {
        if self.is_below(other) {
            return Some(other.clone());
        }
        if other.is_below(self) {
            return Some(self.clone());
        }
        match (self.parent(), other.parent()) {
            (Some(a), Some(b)) if a == b => Some(a),
            _ => None,
        }
    }

    /// Whether the type equals `other` or stands under it.
    fn is_below(&self, other: &ValueType) -> bool {
        self == other || self.parent().as_ref() == Some(other)
    }

    /// The type the type stands directly under, where it stands under one.
    fn parent(&self) -> Option<ValueType> {
        match self {
            ValueType::C4 => Some(ValueType::D4),
            ValueType::Dir | ValueType::DiagDir => Some(ValueType::Dir8),
            ValueType::Axis | ValueType::DiagAxis => Some(ValueType::Axis4),
            _ => None,
        }
    }

    /// The orientation types whose constants are the values of the type:
    /// its own, or the types a union such as `Dir8` unites, and `D4` for
    /// `C4`, whose constants are D4's. `None` for every other type, a Pose
    /// type among them.
    pub fn orientation_types(&self) -> Option<&'static [crate::terms::OrientationType]> {
        use crate::terms::OrientationType;
        Some(match self {
            ValueType::C4 | ValueType::D4 => &[OrientationType::D4],
            ValueType::Dir => &[OrientationType::Dir],
            ValueType::DiagDir => &[OrientationType::DiagDir],
            ValueType::Dir8 => &[OrientationType::Dir, OrientationType::DiagDir],
            ValueType::Axis => &[OrientationType::Axis],
            ValueType::DiagAxis => &[OrientationType::DiagAxis],
            ValueType::Axis4 => &[OrientationType::Axis, OrientationType::DiagAxis],
            ValueType::Sym => &[OrientationType::Sym],
            ValueType::Sense => &[OrientationType::Sense],
            ValueType::Number
            | ValueType::Color
            | ValueType::Example
            | ValueType::Unit
            | ValueType::Box
            | ValueType::Ident
            | ValueType::Pose(_)
            | ValueType::Record(_) => return None,
        })
    }

    /// Whether a D4 element moves a value of the type, as
    /// `docs/arclog/rigid.md#semantics` gives: true for `Box` and for the
    /// types of directions, axes and senses. A `RIGID_DET` pose leaves a
    /// value of every other type as it is.
    pub fn moved_by_d4(&self) -> bool {
        matches!(self, ValueType::Box | ValueType::Dir | ValueType::DiagDir | ValueType::Dir8 | ValueType::Axis | ValueType::DiagAxis | ValueType::Axis4 | ValueType::Sense)
    }

    /// Whether `<`, `<=`, `>` and `>=` may compare values of the type: true
    /// for `number` alone.
    pub fn admits_order(&self) -> bool {
        *self == ValueType::Number
    }
}
