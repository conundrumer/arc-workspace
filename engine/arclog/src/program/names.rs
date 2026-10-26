//! The names a file writes: the names a program declares, the names of
//! columns, ports, alts and demo rules, slugs, texts and label ids.

use std::sync::Arc;

use super::*;

/// A name the program declares: as a file writes it, with its `&`, or, in a
/// decoded program, the slot the engine assigned at the declaration, which
/// the writer writes by its index, since no token of a decode states what the
/// relation means (`docs/arclog/arclog.md#names`).
#[derive(Clone, PartialEq, Eq, Hash, Debug)]
pub enum DeclaredName {
    Written(Box<str>),
    Slot(u32),
}

/// `name` as a file writes it, or its slot.
pub(crate) fn declared_spelled(name: &DeclaredName) -> String {
    match name {
        DeclaredName::Written(text) => text.to_string(),
        DeclaredName::Slot(slot) => slot_spelled(*slot),
    }
}

/// `column` as a file writes it, or its slot.
pub fn column_spelled(column: &ColumnName) -> String {
    match column {
        ColumnName::Written(text) => text.to_string(),
        ColumnName::Slot(slot) => slot_spelled(*slot),
    }
}

fn slot_spelled(slot: u32) -> String {
    format!("slot {slot}")
}

/// The scope of a declared name: the program, or one `DEMO_RULE` form, by its
/// path. A name that a `DEMO_RULE` form declares stands for its declaration
/// within that form alone (`docs/arclog/arclog.md#demonstrated`).
#[derive(Clone, PartialEq, Eq, Hash, Debug)]
pub enum NameScope {
    Program,
    DemoRule(path::NodePath),
}

/// A derived relation's, a chosen relation's or a demonstrated relation's
/// name: `&fg`, `&ties`, `&catalog`. The names follow
/// `docs/arclog/arclog.md#names`.
#[derive(Clone, PartialEq, Eq, Hash, Debug)]
pub struct RelationName(pub DeclaredName);

/// An instance's name, the name of an `INIT` form: `&comps`.
#[derive(Clone, PartialEq, Eq, Hash, Debug)]
pub struct InstanceName(pub DeclaredName);

/// A `RIGID_DET` form's name: `&marker` (`docs/arclog/rigid.md#form`).
#[derive(Clone, PartialEq, Eq, Hash, Debug)]
pub struct RigidDetName(pub DeclaredName);

/// A column's name, without its leading colon: `P`, `Col1` for a column of a
/// fixed type, `key`, `t`, `item` for a column of a type parameter. In a
/// decoded program, a column of a relation the program declares is the slot
/// of its label among the relation's columns
/// (`docs/arclog/arclog.md#token-stream`).
#[derive(Clone, PartialEq, Eq, Hash, Debug)]
pub enum ColumnName {
    Written(Box<str>),
    Slot(u32),
}

/// A column of a relation the program declares, which a label of its form
/// gives (`docs/arclog/arclog.md#sites`): the column's name, the label's name
/// as the file writes it, and the label. The names of the columns are the
/// relation's interface, which a read names and the resolver turns into
/// positions; the label's other names stay in the layout.
#[derive(Clone, PartialEq, Eq, Hash, Debug)]
pub struct RelationColumn {
    pub name: ColumnName,
    pub label: LabelId,
}

/// A key's body and its columns, the `^` labels of the body
/// (`docs/arclog/arclog.md#instance`).
#[derive(Clone, Debug)]
pub struct KeyBody {
    pub body: Node<Body>,
    /// Edits: [`crate::program::Node::apply`].
    pub columns: Arc<[RelationColumn]>,
}

/// The name of an instance's input or output, as the component declares it:
/// `node`, `source`, `component`.
#[derive(Clone, PartialEq, Eq, Hash, Debug)]
pub struct PortName(pub Box<str>);

/// An `ALTS` form's or an alt's name, as the file writes it: `$locate`,
/// `$Box`, `&background=$Derived`.
#[derive(Clone, PartialEq, Eq, Hash, Debug)]
pub struct AltsName(pub Box<str>);

/// A demonstrated rule's name, as its `DEMO_RULE` form writes it: `$Extend`,
/// `$Move`.
#[derive(Clone, PartialEq, Eq, Hash, Debug)]
pub struct DemoRuleName(pub Box<str>);

/// A claim's slug: `container`, `fill-interior`.
#[derive(Clone, PartialEq, Eq, Hash, Debug)]
pub struct Slug(pub Box<str>);

/// A quoted string of a file: a claim's text, a gloss, a reason.
#[derive(Clone, PartialEq, Eq, Hash, Debug)]
pub struct Text(pub Box<str>);

/// A label, local to its scope. A scope is a form that stands in a program,
/// a claim or an `ALT`, apart from a `DEMONSTRATED` form, whose key clause
/// and inputs are one scope and each of whose `DEMO_RULE` forms, with its
/// fields and its own forms, is one scope. A form that an `ALT` gives a
/// `DEMO_RULE` of a case program is a scope of its own, as it is in its
/// `ALT`. A label that one site of the scope
/// makes is the same id at each site of the scope that joins it: an
/// `INIT`'s key labels in its keyed inputs, a `RIGID_DET` key's labels in
/// its instance clause and parts, and a `DEMO_RULE`'s field labels in its
/// clauses. A label written fresh at two sites of one scope, as a key body's
/// local label and an input's, is two variables with two ids. Its name
/// stands in the [`crate::layout::Layout`], and, for a
/// [`super::SiteArg::NamedLabel`], in the value too, so a renaming of label
/// ids leaves the value equal.
#[derive(Clone, Copy, PartialEq, Eq, Hash, Debug)]
pub struct LabelId(pub u32);
