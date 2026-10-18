//! The static types of columns and labels, and their lattice: `C4` under
//! `D4`, `Dir` and `DiagDir` under `Dir8`, `Axis` and `DiagAxis` under
//! `Axis4`, and `Position` and `Offset` as `Box`. A Pose type is below and
//! above no other type.
//!
//! The checker stage writes the bodies.

#![allow(unused_variables, dead_code)]

/// One `RIGID_DET` assembly of a case program, which has its own Pose type:
/// its form, by the form's name and canonical form, and, for a keyed form,
/// its key row, by the labels that a read gives at the key's columns. Two
/// ids are equal where their names, canonical forms and key rows are, so two
/// forms whose hashes collide take two types.
///
/// The form's name and canonical form stay the same in every case that
/// holds the form, so the cases that share a form that reads a pose share
/// its types and its check, whatever alts come before it, and two forms of
/// one name with different parts, in two programs of one task session, take
/// two types. Each key row is an assembly of its own, aligned and posed on its
/// own (`docs/arclog/rigid.md#form`), so two pose reads meet only where they
/// read the same key labels. The key row is named as [`KeyRow`] gives.
#[derive(Clone, PartialEq, Eq, Hash, Debug)]
pub struct AssemblyId {
    pub name: crate::program::RigidDetName,
    pub canonical_form: crate::program::canonical::CanonicalForm,
    /// The key row, or [`KeyRow::Unkeyed`] for a form with no key.
    pub key: KeyRow,
}

/// How a Pose type names its key row: in a scope, by the labels a read
/// gives at the key's columns; at a column of a derived relation or an
/// instance's input, by the positions of the relation's columns that hold
/// the key. A read of the relation maps the positions to the labels at
/// them, so a Pose type passes through a relation
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
    /// A record bound to a type parameter: by a projection of several sites,
    /// one field per site, or, for `Key`, by the key clause, one field per
    /// `^` label, as `docs/arclog/arclog.md#instance` gives. The engine has no
    /// record values, so each field takes a column of its own.
    Record(Box<[(FieldName, ValueType)]>),
}

/// The name of a record's field, PascalCase, as
/// `docs/arclog/arclog.md#sites` gives.
#[derive(Clone, PartialEq, Eq, Hash, Debug)]
pub struct FieldName(pub Box<str>);

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
        todo!()
    }

    /// The join of two types: the type of a label that an `OR` or an `IF`
    /// exports from branches of these types, or `None` where no type is above
    /// both.
    pub fn join(&self, other: &ValueType) -> Option<ValueType> {
        todo!()
    }

    /// Whether `<`, `<=`, `>` and `>=` may compare values of the type: true
    /// for `number` alone.
    pub fn admits_order(&self) -> bool {
        todo!()
    }
}

/// The types the type check infers for the labels of one form, which the
/// check cache keeps beside the form's type check, so that the cases that
/// share a form share its types. In the check cache a label is its canonical
/// position, as `LabelId(position)`, and a key row's labels are the same.
/// [`ProgramTypes`] holds the form's own labels.
#[derive(Clone, Debug, Default)]
pub struct FormTypes {
    labels: crate::hash::StableHashMap<crate::program::LabelId, ValueType>,
}

impl FormTypes {
    /// The type of `label`, or `None` where the form has no such label.
    pub fn label(&self, label: crate::program::LabelId) -> Option<&ValueType> {
        todo!()
    }
}

/// A relation of a case program: the node of the dependency graph that holds
/// it, and, for an output of a node with several, such as an instance, a
/// `RIGID_DET` form or a recursive instance, the output's path. Two
/// relations of one name in two name scopes are two nodes.
#[derive(Clone, PartialEq, Eq, Hash, Debug)]
pub struct GraphRelation {
    pub node: crate::resolver::GraphNodeIndex,
    pub output: Option<std::sync::Arc<[crate::program::OutputStep]>>,
}

/// The types the type check infers for a checked case program: the type of
/// each label of each clause, and the type of each column of each relation.
/// The types are static: a row has no type tag.
///
/// `0` takes the type of the label or the column it stands at, so it has no
/// entry of its own.
#[derive(Clone, Debug, Default)]
pub struct ProgramTypes {
    forms: crate::hash::StableHashMap<crate::program::path::NodePath, std::sync::Arc<FormTypes>>,
    columns: crate::hash::StableHashMap<GraphRelation, Box<[ValueType]>>,
}

impl ProgramTypes {
    /// The types of the labels of the scope at `form`, a form of the program
    /// or a `DEMO_RULE`, as [`crate::program::LabelId`] gives scopes.
    pub fn form(&self, form: &crate::program::path::NodePath) -> Option<&FormTypes> {
        todo!()
    }

    /// The type of each column of `relation`, one per column, a record's
    /// fields each a column of its own.
    pub fn columns(&self, relation: &GraphRelation) -> Option<&[ValueType]> {
        todo!()
    }
}
