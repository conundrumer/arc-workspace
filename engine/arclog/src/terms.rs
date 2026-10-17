//! Column values: the term id and its interpretations, and the intern table
//! of Idents.
//!
//! Implements `work/engine/reader.md`, Terms. A row holds term ids with no
//! type tag, and the checker's static types give each column's
//! interpretation, so a term id is read only through the [`ValueType`] of its
//! column.
//!
//! # Order
//!
//! No type here but [`Number`] implements `PartialOrd` or `Ord`. The order
//! rule of the checker refuses `<`, `<=`, `>` and `>=` on every type but
//! `number`, as `work/engine/reader.md`, Checker, gives, and
//! `work/engine/equivariance.md`, "The types refuse order", makes that rule
//! hold by construction: a Color, an orientation value, an Ident, a Box or an
//! Example has no order an engine function could read. A writer that gives a
//! set in a fixed order of the encodings, as `work/engine/equivariance.md`,
//! Determinism, gives, reads `TermId::encoding`, which is crate-private.


#![allow(unused_variables, dead_code)]

use crate::hash::StableHash;
use crate::types::ValueType;

/// A column value: 32 bits whose meaning the column's type gives.
///
/// Implements "Every column value is a 32-bit term id".
#[derive(Clone, Copy, PartialEq, Eq, Hash, Debug)]
pub struct TermId(u32);

impl TermId {
    /// The 32 bits of the term id, for a writer's fixed order of encodings
    /// and for packing.
    ///
    /// Implements `work/engine/equivariance.md`, Determinism: "A writer gives a set in a fixed order of the encodings".
    pub(crate) fn encoding(self) -> u32 {
        todo!()
    }

    /// The term id whose 32 bits are `bits`.
    ///
    /// Implements `work/engine/reader.md`, Terms: "Every column value is a 32-bit term id".
    pub(crate) fn from_encoding(bits: u32) -> Self {
        todo!()
    }
}

/// A `number`: a count, as `docs/handbook/encoding.md`, Numbers, gives.
///
/// Implements "A number is its two's-complement value". The one column type
/// with an order.
#[derive(Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Hash, Debug)]
pub struct Number(pub i32);

/// A Color constant: one of the ten ARC colors, written `0` to `9`.
///
/// A color has identity and no other properties, as
/// `docs/handbook/principles.md`, Color, gives, so it has no order.
#[derive(Clone, Copy, PartialEq, Eq, Hash, Debug)]
pub struct Color(u8);

impl Color {
    /// The color written as `digit` in a task file, or `None` outside `0..=9`.
    ///
    /// Implements `docs/handbook/principles.md`, Color, and `work/engine/reader.md`, Terms: "A Color ... is its constant".
    pub fn from_digit(digit: u8) -> Option<Color> {
        todo!()
    }

    /// The digit a task file writes for the color.
    ///
    /// Implements `docs/handbook/principles.md`, Color, and `work/engine/reader.md`, Terms: "A Color ... is its constant".
    pub fn digit(self) -> u8 {
        todo!()
    }
}

/// An Example constant: the index of one example of the task, train or test,
/// as `docs/lib-spec.md`, Types, gives.
///
/// The index is the position of the example in the task file, an order of
/// the task file that no output may read, as `docs/handbook/encoding.md`,
/// Fidelity, gives, so it has no order.
#[derive(Clone, Copy, PartialEq, Eq, Hash, Debug)]
pub struct Example(u16);

impl Example {
    /// The example at `index` in the task file.
    ///
    /// Implements `docs/lib-spec.md`, Types: "`Example` the index of an example, train or test".
    pub fn at(index: u16) -> Example {
        todo!()
    }
}

/// The orientation types of `docs/lib-spec.md`, The orientation algebra, each
/// a type with a finite set of constants.
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
/// constant, so this crate fixes no list of them. The index is an encoding
/// and has no order.
///
/// Implements `docs/lib-spec.md`, The orientation algebra: "The constants of each type, `DIR_T` through `SYM_D4`."
#[derive(Clone, Copy, PartialEq, Eq, Hash, Debug)]
pub struct OrientationConstant {
    pub ty: OrientationType,
    pub index: u8,
}

/// A constant term: a Color, an Example, an orientation value, or the one
/// Unit value.
///
/// Implements "A Color, Example or orientation value is its constant. A pose
/// is the constant of its D4 element, which the pose rule of Checker keeps
/// from every read. The Unit value is one constant."
#[derive(Clone, Copy, PartialEq, Eq, Hash, Debug)]
pub enum Constant {
    Color(Color),
    Example(Example),
    Orientation(OrientationConstant),
    Unit,
}

/// A Box: its four margins (t, b, l, r), as `docs/lib-spec.md`, The box
/// algebra, gives. A Position and an Offset are Boxes.
///
/// Implements "A Box is its four margins, as four signed bytes in one term
/// id". A Box has no order.
#[derive(Clone, Copy, PartialEq, Eq, Hash, Debug)]
pub struct Margins {
    pub top: i32,
    pub bottom: i32,
    pub left: i32,
    pub right: i32,
}

/// A Box with a margin outside a signed byte, which no term id holds.
///
/// Implements "A margin outside a byte is a reached bound, as Bounds gives".
/// An algebra relation computes in 32-bit integers and packs only the Boxes
/// it binds, so only a Box that reaches a row raises this.
#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub struct ReachedMarginBound {
    pub margins: Margins,
}

/// An Ident: the index of a content in the task session's [`InternTable`].
///
/// Implements "An Ident is the index of the content it labels in the task
/// session's intern table ... The number depends on the order of interning,
/// and only equality on it reaches an output." So an Ident has equality and
/// no order.
#[derive(Clone, Copy, PartialEq, Eq, Hash, Debug)]
pub struct Ident(u32);

/// A term as its interpretation: what a [`TermId`] means at a column of a
/// given type.
///
/// Implements `work/engine/reader.md`, Terms: "Every column value is a 32-bit term id".
#[derive(Clone, Copy, PartialEq, Eq, Hash, Debug)]
pub enum Term {
    Number(Number),
    Constant(Constant),
    Box(Margins),
    Ident(Ident),
}

impl Term {
    /// The term id of the term.
    ///
    /// Fails only for a Box with a margin outside a signed byte.
    ///
    /// Implements `work/engine/reader.md`, Terms: "Every column value is a 32-bit term id".
    pub fn encode(self) -> Result<TermId, ReachedMarginBound> {
        todo!()
    }

    /// The term that `id` stands for at a column of type `ty`.
    ///
    /// A row has no type tag, so the column's static type is the one source
    /// of the interpretation, as "Types are static: the checker holds them,
    /// and a row has no type tag" gives.
    ///
    /// Implements `work/engine/reader.md`, Terms: "Every column value is a 32-bit term id".
    pub fn decode(id: TermId, ty: &ValueType) -> Term {
        todo!()
    }
}

/// What an Ident labels: a set of terms of one type, a constructed term such
/// as a tiebreak resolution, or a value read from a file.
///
/// Implements "keyed by the whole content with the type of its members, so
/// two contents never share an id, and neither do the colors `{1, 2}` and the
/// numbers `{1, 2}`" and "An Ident read from a file ... is interned by its
/// type and its written value".
#[derive(Clone, PartialEq, Eq, Hash, Debug)]
pub enum Content {
    /// A set of terms of the member type `member`. The members are held in
    /// one canonical order of their term ids, so that equal sets are equal
    /// contents.
    Set {
        member: ValueType,
        members: Box<[TermId]>,
    },
    /// A constructed term: its constructor's name in the registry, and its
    /// fields with their types.
    Constructed {
        constructor: crate::registry::LibName,
        fields: Box<[(ValueType, TermId)]>,
    },
    /// An Ident written in a file, such as one of an arcdata record: its type
    /// and its written number.
    Read { ty: ValueType, written: u32 },
}

/// The task session's table from contents to Idents.
///
/// Implements "The table finds a content by its hash, and compares contents
/// only where two hashes match." The table's bytes count toward the task
/// session's bound, and a freed number is not used again in the session, as
/// the first row of Reader and checker's "How each decision can fail" gives.
#[derive(Debug, Default)]
pub struct InternTable {
    contents: Vec<Content>,
    by_hash: crate::hash::StableHashMap<StableHash, Vec<Ident>>,
}

impl InternTable {
    /// The Ident of `content`, interned on first use.
    ///
    /// Implements `work/engine/reader.md`, Terms: "The table finds a content by its hash, and compares contents only where two hashes match."
    pub fn intern(&mut self, content: Content) -> Ident {
        todo!()
    }

    /// The content that `ident` labels.
    ///
    /// Implements `work/engine/reader.md`, Terms: "An Ident is the index of the content it labels in the task session's intern table".
    pub fn content(&self, ident: Ident) -> &Content {
        todo!()
    }

    /// The bytes the table holds, which count toward the task session's
    /// bound.
    ///
    /// Implements `work/engine/reader.md`, How each decision can fail: "the table's bytes count toward the session's bound".
    pub fn bytes(&self) -> usize {
        todo!()
    }
}
