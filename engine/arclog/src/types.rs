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

/// One `RIGID_DET` assembly of a case program, which has its own Pose type:
/// its form, by the form's name and canonical hash, and, for a keyed form,
/// its key row, by the labels that a read gives at the key's columns.
///
/// The form's name and hash stay the same in every case that holds the
/// form, so the cases that share a form that reads a pose share its types
/// and its check, whatever alts come before it, and two forms of one name
/// with different parts, in two programs of one task session, take two
/// types. Each key row is posed on its own, so two pose reads meet only
/// where they read the same key labels, and the type check refuses a join of
/// poses at different key labels. The key row is named as [`KeyRow`] gives.
///
/// Implements `work/engine/reader.md`: "each `RIGID_DET` assembly has its own Pose type", and `docs/rigid.md`, Form: "each key row is an independent assembly, aligned on its own and posed on its own".
#[derive(Clone, PartialEq, Eq, Hash, Debug)]
pub struct AssemblyId {
    pub name: crate::program::RigidDetName,
    pub canonical_hash: crate::hash::StableHash,
    /// The key row, or [`KeyRow::Unkeyed`] for a form with no key.
    pub key: KeyRow,
}

/// How a Pose type names its key row: in a scope, by the labels a read
/// gives at the key's columns; at a column of a derived relation or an
/// instance's input, by the positions of the relation's columns that hold
/// the key. A read of the relation maps the positions to the labels at
/// them, so a Pose type passes through a relation.
///
/// Implements `docs/rigid.md`, The pose: "A column of a derived relation or of an instance's input, which then takes the type", and Form: "each key row is an independent assembly".
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
    /// A record bound to a type parameter: by a projection of several sites,
    /// one field per site, or, for `Key`, by the key clause, one field per
    /// `^` label, as `docs/arclog.md`, Instance, gives. The engine has no
    /// record values, so each field takes a column of its own.
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
    /// Implements `work/engine/reader.md`: "A label's type is the meet of the types of its sites".
    pub fn meet(&self, other: &ValueType) -> Meet {
        todo!()
    }

    /// The join of two types: the type of a label that an `OR` or an `IF`
    /// exports from branches of these types, or `None` where no type is above
    /// both.
    ///
    /// Implements `work/engine/reader.md`: "a label that an `OR` or an `IF` exports takes the join over
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

/// The types the type check infers for the labels of one form, which the
/// check cache keeps beside the form's type check, so that the cases that
/// share a form share its types. In the check cache a label is its canonical
/// position, as `LabelId(position)`, and a key row's labels are the same;
/// [`crate::check::check_program`] maps them to each form's own labels
/// through [`crate::program::canonical::CanonicalOrder`], and
/// [`ProgramTypes`] holds the form's own labels.
///
/// Implements `work/engine/reader.md`, Checker: "so the cases that share a form share its check".
#[derive(Clone, Debug, Default)]
pub struct FormTypes {
    labels: crate::hash::StableHashMap<crate::program::LabelId, ValueType>,
}

impl FormTypes {
    /// The type of `label`.
    ///
    /// Implements `work/engine/reader.md`, Checker: "The type check infers each label's type over the lattice of the types".
    pub fn label(&self, label: crate::program::LabelId) -> Option<&ValueType> {
        todo!()
    }
}

/// A relation of a case program: the node of the dependency graph that holds
/// it, and, for an output of a node with several, such as an instance, a
/// `RIGID_DET` form or a recursive instance, the output's path. Two
/// relations of one name in two name scopes are two nodes.
///
/// Implements `work/engine/reader.md`, Terms: "Types are static: the checker holds them".
#[derive(Clone, PartialEq, Eq, Hash, Debug)]
pub struct GraphRelation {
    pub node: crate::resolver::GraphNodeIndex,
    pub output: Option<std::sync::Arc<[crate::program::OutputStep]>>,
}

/// The types the type check infers for a checked case program: the type of
/// each label of each clause, and the type of each column of each relation.
/// A row has no type tag, so the evaluator and the writer read each column's
/// interpretation here, through [`crate::terms::Term::decode`].
///
/// `0` takes the type of the label or the column it stands at, so it has no
/// entry of its own.
///
/// Implements `work/engine/reader.md`, Terms: "Types are static: the checker holds them, and a row has no type tag."
#[derive(Clone, Debug, Default)]
pub struct ProgramTypes {
    forms: crate::hash::StableHashMap<crate::program::path::NodePath, std::sync::Arc<FormTypes>>,
    columns: crate::hash::StableHashMap<GraphRelation, Box<[ValueType]>>,
}

impl ProgramTypes {
    /// The types of the labels of the scope at `form`, a form of the program
    /// or a `DEMO_RULE`, as [`crate::program::LabelId`] gives scopes.
    ///
    /// Implements `work/engine/reader.md`, Checker: "The type check infers each label's type over the lattice of the types".
    pub fn form(&self, form: &crate::program::path::NodePath) -> Option<&FormTypes> {
        todo!()
    }

    /// The type of each column of `relation`, one per column, a record's
    /// fields each a column of its own.
    ///
    /// Implements `work/engine/reader.md`, Terms: "Types are static: the checker holds them".
    pub fn columns(&self, relation: &GraphRelation) -> Option<&[ValueType]> {
        todo!()
    }
}
