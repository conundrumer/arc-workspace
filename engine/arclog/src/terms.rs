//! Column values: the term id and its interpretations, and the intern table
//! of Idents.
//!
//! Every column value is a 32-bit term id. A row holds term ids with no
//! type tag, and the checker's static types give each column's
//! interpretation, so a term id is read only through the [`ValueType`] of its
//! column.
//!
//! # Order
//!
//! No type here but [`Number`] implements `PartialOrd` or `Ord`. The order
//! rule of the checker refuses `<`, `<=`, `>` and `>=` on every type but
//! `number`, and the types make that rule hold by construction: a Color, an
//! orientation value, an Ident, a Box or an Example has no public order.
//! Within the crate, a writer that gives a set in a fixed order of the
//! encodings reads `TermId::encoding`, which is crate-private, as
//! `Color::digit` is.


#![allow(unused_variables, dead_code)]

use crate::hash::StableHash;
use crate::types::ValueType;

/// A column value: 32 bits whose meaning the column's type gives.
#[derive(Clone, Copy, PartialEq, Eq, Hash, Debug)]
pub struct TermId(u32);

impl TermId {
    /// The 32 bits of the term id, for a writer's fixed order of encodings
    /// and for packing.
    pub(crate) fn encoding(self) -> u32 {
        todo!()
    }

    /// The term id whose 32 bits are `bits`.
    pub(crate) fn from_encoding(bits: u32) -> Self {
        todo!()
    }
}

/// A `number`: a count, as `docs/handbook/encoding.md#numbers` gives, held
/// as its two's-complement value. The one column type with an order.
#[derive(Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Hash, Debug)]
pub struct Number(pub i32);

/// A Color constant: one of the ten ARC colors, written `0` to `9`.
///
/// A color has identity and no other properties, as
/// `docs/handbook/principles.md#color` gives, so it has no order.
#[derive(Clone, Copy, PartialEq, Eq, Hash, Debug)]
pub struct Color(u8);

impl Color {
    /// The color written as `digit` in a task file, or `None` outside `0..=9`.
    pub fn from_digit(digit: u8) -> Option<Color> {
        todo!()
    }

    /// The digit a task file writes for the color, for the crate's readers
    /// and writers alone, so no code outside the crate orders colors by it.
    pub(crate) fn digit(self) -> u8 {
        todo!()
    }
}

/// An Example constant: the index of one example of the task, train or
/// test.
///
/// The index is the position of the example in the task file, which is how
/// the task file encodes it and no part of the task's concept
/// (`docs/handbook/encoding.md#fidelity`), so an Example has equality and no
/// order.
#[derive(Clone, Copy, PartialEq, Eq, Hash, Debug)]
pub struct Example(u16);

impl Example {
    /// The example at `index` in the task file.
    pub fn at(index: u16) -> Example {
        todo!()
    }
}

/// The orientation types of the lib, each a type with a finite set of
/// constants.
///
/// `Dir8` and `Axis4` are unions of these types and hold no constant of their
/// own; `C4` is a subtype of `D4`, so a C4 value is a [`OrientationType::D4`]
/// constant.
#[derive(Clone, Copy, PartialEq, Eq, Hash, Debug)]
pub enum OrientationType {
    Dir,
    DiagDir,
    Axis,
    DiagAxis,
    D4,
    Sym,
    Sense,
}

/// One constant of an orientation type, such as `DIR_T` or `D4_LR`.
///
/// The constants and their names are the lib's: the registry
/// ([`crate::registry::Registry::orientation_constant`]) maps each name to its
/// constant, so this crate fixes no list of them. The index is an encoding,
/// private to the crate, so no code outside it can order constants by it.
#[derive(Clone, Copy, PartialEq, Eq, Hash, Debug)]
pub struct OrientationConstant {
    ty: OrientationType,
    index: u8,
}

impl OrientationConstant {
    /// The constant at `index` of `ty`, as the registry numbers them.
    pub(crate) fn new(ty: OrientationType, index: u8) -> Self {
        todo!()
    }

    /// The constant's type.
    pub fn ty(self) -> OrientationType {
        todo!()
    }
}

/// A constant term: a Color, an Example, an orientation value, or the one
/// Unit value. A pose is the constant of its D4 element, which the pose rule
/// of the checker keeps from every read.
#[derive(Clone, Copy, PartialEq, Eq, Hash, Debug)]
pub enum Constant {
    Color(Color),
    Example(Example),
    Orientation(OrientationConstant),
    Unit,
}

/// A Box: its four margins (t, b, l, r), packed as four signed bytes in one
/// term id. A Position and an Offset are Boxes. A Box has no order.
#[derive(Clone, Copy, PartialEq, Eq, Hash, Debug)]
pub struct Margins {
    pub top: i32,
    pub bottom: i32,
    pub left: i32,
    pub right: i32,
}

/// A Box with a margin outside a signed byte, which no term id holds: a
/// reached bound. An algebra relation computes in 32-bit integers and packs
/// only the Boxes it binds, so only a Box that reaches a row raises this.
#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub struct ReachedMarginBound {
    pub margins: Margins,
}

/// An Ident: the index of a content in the task session's [`InternTable`].
/// The number depends on the order of interning, so an Ident has equality
/// and no order.
#[derive(Clone, Copy, PartialEq, Eq, Hash, Debug)]
pub struct Ident(u32);

/// A term as its interpretation: what a [`TermId`] means at a column of a
/// given type.
#[derive(Clone, Copy, PartialEq, Eq, Hash, Debug)]
pub enum Term {
    Number(Number),
    Constant(Constant),
    Box(Margins),
    Ident(Ident),
}

/// `Term::encode` and `Term::decode` are the public way between a term and
/// its id, which a construction of `arclog-constructions` takes.
impl Term {
    /// The term id of the term.
    ///
    /// Fails only for a Box with a margin outside a signed byte.
    pub fn encode(self) -> Result<TermId, ReachedMarginBound> {
        todo!()
    }

    /// The term that `id` stands for at a column of type `ty`.
    ///
    /// A row has no type tag, so the column's static type is the one source
    /// of the interpretation: at the type the checker gives the id's column,
    /// as [`crate::types::ProgramTypes`] holds it, the term is the one the id
    /// stands for, and at another type it is a term the id does not stand
    /// for, such as an encoding read as a `Number`.
    pub fn decode(id: TermId, ty: &ValueType) -> Term {
        todo!()
    }
}

/// What an Ident labels: a set of terms of one type, or a value read from a
/// file. A content is keyed whole, with the type of its members, so two
/// contents never share an Ident, and neither do the colors `{1, 2}` and
/// the numbers `{1, 2}`. A value read from a file is keyed by its type and
/// its written value.
#[derive(Clone, PartialEq, Eq, Hash, Debug)]
pub enum Content {
    /// A set of terms of one member type.
    Set(MemberSet),
    /// An Ident written in a file, such as one of an arcdata record: its type
    /// and its written number.
    FromFile { ty: ValueType, written: WrittenIdent },
}

/// The number a file writes for an Ident, as an arcdata record does. It has
/// equality and no public order and no public value, so no code outside the
/// crate orders Idents by the file's numbers.
#[derive(Clone, Copy, PartialEq, Eq, Hash, Debug)]
pub struct WrittenIdent(pub(crate) u32);

impl WrittenIdent {
    /// The Ident a file writes as `number`.
    pub fn new(number: u32) -> Self {
        todo!()
    }
}

/// A set of terms of one member type, the content of an Ident. It holds its
/// members in one canonical order of their term ids, so that equal sets are
/// equal contents, and that order is private: the set gives membership and
/// each member, as [`MemberSet::each`] gives them.
#[derive(Clone, PartialEq, Eq, Hash, Debug)]
pub struct MemberSet {
    member: ValueType,
    members: Box<[Box<[TermId]>]>,
}

impl MemberSet {
    /// The set of `members`, values of type `member`. A member is one term
    /// id, or, where `member` is a record, one term id per field, as the
    /// record's column group holds it.
    pub fn new(member: ValueType, members: impl IntoIterator<Item = Box<[TermId]>>) -> Self {
        todo!()
    }

    /// The type of the members.
    pub fn member_type(&self) -> &ValueType {
        todo!()
    }

    /// Whether `member`, one term id per field of the member type, is a
    /// member.
    pub fn contains(&self, member: &[TermId]) -> bool {
        todo!()
    }

    /// Each member, in an order of encodings and no order of the content.
    #[allow(unreachable_code)]
    pub fn each(&self) -> impl Iterator<Item = &[TermId]> + '_ {
        todo!();
        std::iter::empty()
    }
}

/// The term ids of `value` at a column of type `ty`: one term id, or, at a
/// record's column group, one per field, so a value written as a list is
/// read into the same columns. A Color's digit, a number and a
/// Box's margins are encoded as `ty` reads them, and an Ident's written
/// number is interned in `table` as a [`Content::FromFile`]. `registry`
/// gives which constants a type such as `C4` admits.
///
/// This is the one step from a written value to its term ids, after the type
/// check, for `param` rows and `assign` rows alike. `ty` is the type of the
/// value's column: the one the `param` form writes, or, for a relation with
/// no `param` form, such as a `RULE_OR_DET` relation, the one the type check
/// infers. A field of a derivation's row takes the type that the registry's
/// [`crate::registry::Derivation`] gives.
pub fn encode_data_value(
    value: &crate::program::DataValue,
    ty: &ValueType,
    registry: &crate::registry::Registry,
    table: &mut InternTable,
) -> Result<Box<[TermId]>, DataValueError> {
    todo!()
}

/// An arcdata value that its column's type cannot read, such as a digit
/// outside `0..=9` at a Color column or a list of three at a Box column, or
/// a Box whose margin lies outside a byte, which is a reached bound.
#[derive(Clone, PartialEq, Eq, Debug)]
pub enum DataValueError {
    NotOfType { value: crate::program::DataValue, ty: ValueType },
    MarginBound(ReachedMarginBound),
}

/// The task session's table from contents to Idents. It finds a content by
/// its hash, and compares contents only where two hashes match. The table's
/// bytes count toward the task session's bound, and a freed number is not
/// used again in the session.
#[derive(Debug, Default)]
pub struct InternTable {
    /// The content of each number given, `None` once freed.
    contents: Vec<Option<Content>>,
    /// The Idents of the contents of each hash.
    by_hash: crate::hash::StableHashMap<StableHash, Vec<Ident>>,
}

impl InternTable {
    /// The Ident of `content`, interned on first use.
    pub fn intern(&mut self, content: Content) -> Ident {
        todo!()
    }

    /// The content that `ident` labels. A freed Ident is a fault of its
    /// holder, so this panics on one.
    pub fn content(&self, ident: Ident) -> &Content {
        todo!()
    }

    /// Frees each entry whose Ident `held` lacks and that no kept entry's
    /// content holds: it keeps each Ident in `held`, and each member of a set
    /// of Idents that a kept entry's content holds, at every depth. `held` is
    /// every Ident that a cached relation, a decode state or an event log
    /// holds. A freed number is not given again in the session.
    pub fn free_unheld(&mut self, held: &crate::hash::StableHashSet<Ident>) {
        todo!()
    }

    /// The bytes the table holds, which count toward the task session's
    /// bound.
    pub fn bytes(&self) -> usize {
        todo!()
    }
}
