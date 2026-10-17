//! The static types of columns and labels, and their lattice.
//!
//! Implements `work/engine/reader.md`, Checker: "The type check infers each
//! label's type over the lattice of the types: `C4` under `D4`, `Dir` and
//! `DiagDir` under `Dir8`, `Axis` and `DiagAxis` under `Axis4`, and `Position`
//! and `Offset` as `Box`." and "A Pose type is below and above no other
//! type".
//!
//! The checker stage writes the bodies.

#![allow(unused_variables, dead_code)]

/// One `RIGID_DET` assembly of a case program, which gives its own Pose type.
///
/// Implements "each `RIGID_DET` assembly has its own Pose type". The id is
/// the assembly's index in the resolved case program.
#[derive(Clone, Copy, PartialEq, Eq, Hash, Debug)]
pub struct AssemblyId(pub u32);

/// The type of a column or a label.
///
/// `Position` and `Offset` are the type `Box`, as "`Position` and `Offset` as
/// `Box`" gives, so neither has a variant of its own.
///
/// Implements `work/engine/reader.md`, Checker: "The type check infers each label's type over the lattice of the types".
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
    /// The Pose type of one `RIGID_DET` assembly, as
    /// `work/engine/equivariance.md`, The `RIGID_DET` frame, gives.
    Pose(AssemblyId),
    /// A record bound to a type parameter by a projection of several sites:
    /// one field per site, as `docs/arclog.md`, Instance, gives. The engine
    /// has no record values, so each field takes a column of its own.
    Record(Box<[(FieldName, ValueType)]>),
}

/// The name of a record's field, PascalCase, as `docs/arclog.md`, Sites,
/// gives.
#[derive(Clone, PartialEq, Eq, Hash, Debug)]
pub struct FieldName(pub Box<str>);

/// The result of the meet of two types.
///
/// Implements `work/engine/reader.md`, Checker: "a branch whose meet is empty is refused as well as a label whose meet is empty".
#[derive(Clone, PartialEq, Eq, Debug)]
pub enum Meet {
    /// The greatest type below both.
    Type(ValueType),
    /// No type is below both, so a label of both types holds no value.
    Empty,
}

impl ValueType {
    /// The meet of two types: the type of a label with both types' sites.
    ///
    /// Implements "A label's type is the meet of the types of its sites".
    pub fn meet(&self, other: &ValueType) -> Meet {
        todo!()
    }

    /// The join of two types: the type of a label that an `OR` or an `IF`
    /// exports from branches of these types, or `None` where no type is above
    /// both.
    ///
    /// Implements "a label that an `OR` or an `IF` exports takes the join over
    /// its branches".
    pub fn join(&self, other: &ValueType) -> Option<ValueType> {
        todo!()
    }

    /// Whether `<`, `<=`, `>` and `>=` may compare values of the type.
    ///
    /// Implements the order rule: true for `number` alone.
    pub fn admits_order(&self) -> bool {
        todo!()
    }
}
