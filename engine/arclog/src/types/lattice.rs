//! The static types of columns and labels, and their lattice: `Nat` under `Int`, `C4` under
//! `D4`, `Dir` and `DiagDir` under `Dir8`, `Axis` and `DiagAxis` under
//! `Axis4`, and `Position` and `Offset` under `Box`. A Pose type is below and
//! above no other type. The Ident type of one source stands under the Ident
//! type of no source, and is below and above no other source.

use super::ident_source::IdentSource;

/// The type of a column or a label, which the type check infers for each
/// label over the lattice of the types.
///
/// `Position` and `Offset` are the two interpretations of a `Box`, a cell and
/// a translation, and stand under it.
#[derive(Clone, PartialEq, Eq, Hash)]
pub enum ValueType {
    /// Signed 32-bit integer; the historical `number` spelling reads this type.
    Int,
    /// Nonnegative signed-32-bit integer, a subtype of Int.
    Nat,
    Color,
    Example,
    Unit,
    /// A lib name: equality alone, and every element of the group fixes it.
    LibName,
    Box,
    Position,
    Offset,
    /// An identity that a maker makes; the field is the maker. The Ident
    /// types of two makers have an empty meet. `Ident(IdentSource::Open)`
    /// stands above the Ident type of each maker.
    Ident(IdentSource),
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
    Pose(super::AssemblyId),
    /// A record bound to a type parameter (`docs/arclog/arclog.md#instance`),
    /// each field by the column name of its site or of its key column: the
    /// name written, or, in a decoded program, the slot. The engine has no
    /// record values, so each field takes a column of its own.
    Record(Box<[(crate::program::ColumnName, ValueType)]>),
}

impl std::fmt::Debug for ValueType {
    /// The type's name: `Ident` alone for an Ident of no source, and
    /// `Ident(<source>)` for an Ident of a source.
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        let name = match self {
            ValueType::Int => "Int",
            ValueType::Nat => "Nat",
            ValueType::Color => "Color",
            ValueType::Example => "Example",
            ValueType::Unit => "Unit",
            ValueType::LibName => "LibName",
            ValueType::Box => "Box",
            ValueType::Position => "Position",
            ValueType::Offset => "Offset",
            ValueType::Ident(IdentSource::Open) => "Ident",
            ValueType::Ident(IdentSource::Form(id)) => return write!(f, "Ident({id:?})"),
            ValueType::C4 => "C4",
            ValueType::D4 => "D4",
            ValueType::Dir => "Dir",
            ValueType::DiagDir => "DiagDir",
            ValueType::Dir8 => "Dir8",
            ValueType::Axis => "Axis",
            ValueType::DiagAxis => "DiagAxis",
            ValueType::Axis4 => "Axis4",
            ValueType::Sym => "Sym",
            ValueType::Sense => "Sense",
            ValueType::Pose(assembly) => return f.debug_tuple("Pose").field(assembly).finish(),
            ValueType::Record(fields) => return f.debug_tuple("Record").field(fields).finish(),
        };
        f.write_str(name)
    }
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
    /// The Ident type of no source.
    pub const OPEN_IDENT: ValueType = ValueType::Ident(IdentSource::Open);

    /// The type with the source of each Ident in it dropped, so that it
    /// prints and compares as the type of a column that an input names.
    pub fn without_source(&self) -> ValueType {
        match self {
            ValueType::Ident(_) => ValueType::OPEN_IDENT,
            ValueType::Record(fields) => ValueType::Record(fields.iter().map(|(name, field)| (name.clone(), field.without_source())).collect()),
            other => other.clone(),
        }
    }

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
        if let (ValueType::Ident(IdentSource::Form(a)), ValueType::Ident(IdentSource::Form(b))) = (self, other) {
            if a != b {
                return None;
            }
        }
        match (self.parent(), other.parent()) {
            (Some(a), Some(b)) if a == b => Some(a),
            _ => None,
        }
    }

    /// Whether the types have a type below both: the meet of the two is not
    /// [`Meet::Empty`].
    pub fn meets(&self, other: &ValueType) -> bool {
        self.meet(other) != Meet::Empty
    }

    /// Whether the type is a scalar: any type but `Unit`, a Pose type and a
    /// record type. The shortcuts of the decode's mask read only the columns
    /// of these types.
    pub fn is_scalar(&self) -> bool {
        !matches!(self, ValueType::Unit | ValueType::Pose(_) | ValueType::Record(_))
    }

    /// Whether the type is `Box` or stands under it: the types of a value
    /// that is four margins.
    pub fn is_box(&self) -> bool {
        self.is_below(&ValueType::Box)
    }

    /// Whether `0` has a value of the type: the number zero, or the zero box.
    pub fn has_zero(&self) -> bool {
        matches!(self, ValueType::Int | ValueType::Nat) || self.is_box()
    }

    /// Whether the type equals `other` or stands under it.
    pub fn is_below(&self, other: &ValueType) -> bool {
        self == other || self.parent().as_ref() == Some(other)
    }

    /// The type the type stands directly under, where it stands under one.
    fn parent(&self) -> Option<ValueType> {
        match self {
            ValueType::Nat => Some(ValueType::Int),
            ValueType::C4 => Some(ValueType::D4),
            ValueType::Dir | ValueType::DiagDir => Some(ValueType::Dir8),
            ValueType::Axis | ValueType::DiagAxis => Some(ValueType::Axis4),
            ValueType::Position | ValueType::Offset => Some(ValueType::Box),
            ValueType::Ident(IdentSource::Form(_)) => Some(ValueType::OPEN_IDENT),
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
            ValueType::Int
            | ValueType::Nat
            | ValueType::Color
            | ValueType::Example
            | ValueType::Unit
            | ValueType::LibName
            | ValueType::Box
            | ValueType::Position
            | ValueType::Offset
            | ValueType::Ident(_)
            | ValueType::Pose(_)
            | ValueType::Record(_) => return None,
        })
    }

    /// Whether a D4 element moves a value of the type, as
    /// `docs/arclog/rigid.md#semantics` gives: true for `Box` and the types
    /// under it, and for the types of directions, axes and senses. A `RIGID_DET` pose leaves a
    /// value of every other type as it is.
    pub fn moved_by_d4(&self) -> bool {
        self.is_box() || matches!(self, ValueType::Dir | ValueType::DiagDir | ValueType::Dir8 | ValueType::Axis | ValueType::DiagAxis | ValueType::Axis4 | ValueType::Sense)
    }

    /// Whether `<`, `<=`, `>` and `>=` may compare values of the type: true
    /// for Int and its Nat subtype.
    pub fn admits_order(&self) -> bool {
        matches!(self, ValueType::Int | ValueType::Nat)
    }
}
