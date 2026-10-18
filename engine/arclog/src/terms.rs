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
        self.0
    }

    /// The term id whose 32 bits are `bits`.
    pub(crate) fn from_encoding(bits: u32) -> Self {
        TermId(bits)
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
        (digit <= 9).then_some(Color(digit))
    }

    /// The digit a task file writes for the color, for the crate's readers
    /// and writers alone, so no code outside the crate orders colors by it.
    pub(crate) fn digit(self) -> u8 {
        self.0
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
        Example(index)
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
        OrientationConstant { ty, index }
    }

    /// The constant's type.
    pub fn ty(self) -> OrientationType {
        self.ty
    }

    /// The constant's 16 bits: its type in the high byte and its index in the
    /// low byte, so a `Dir8` or an `Axis4` column, which holds the constants
    /// of two types, holds each with an id of its own.
    fn encoding(self) -> u32 {
        let ty = ORIENTATION_TYPES.iter().position(|&ty| ty == self.ty).expect("each orientation type");
        ((ty as u32) << 8) | u32::from(self.index)
    }

    /// The constant whose encoding the low 16 bits of `bits` are, read as a
    /// constant of one of `admitted`: of the type the high byte gives, where
    /// that is one of them, and otherwise of the first of them.
    fn decode(bits: u32, admitted: &[OrientationType]) -> Self {
        let ty = ORIENTATION_TYPES.get(((bits >> 8) & 0xff) as usize).copied();
        let ty = ty.filter(|ty| admitted.contains(ty)).unwrap_or(admitted[0]);
        OrientationConstant { ty, index: bits as u8 }
    }
}

/// Each orientation type, at the position that the high byte of its
/// constants' encodings gives.
const ORIENTATION_TYPES: [OrientationType; 7] = [
    OrientationType::Dir,
    OrientationType::DiagDir,
    OrientationType::Axis,
    OrientationType::DiagAxis,
    OrientationType::D4,
    OrientationType::Sym,
    OrientationType::Sense,
];

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

impl Margins {
    /// The margins packed as four signed bytes, t, b, l and r from the low
    /// byte up.
    fn pack(self) -> Result<u32, ReachedMarginBound> {
        let byte = |margin: i32| i8::try_from(margin).map(|m| u32::from(m as u8));
        match (byte(self.top), byte(self.bottom), byte(self.left), byte(self.right)) {
            (Ok(t), Ok(b), Ok(l), Ok(r)) => Ok(t | (b << 8) | (l << 16) | (r << 24)),
            _ => Err(ReachedMarginBound { margins: self }),
        }
    }

    /// The margins that `bits` packs, as [`Margins::pack`] packs them.
    fn unpack(bits: u32) -> Margins {
        let byte = |shift: u32| i32::from((bits >> shift) as u8 as i8);
        Margins { top: byte(0), bottom: byte(8), left: byte(16), right: byte(24) }
    }
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
        let bits = match self {
            Term::Number(Number(n)) => n as u32,
            Term::Constant(Constant::Color(color)) => u32::from(color.0),
            Term::Constant(Constant::Example(example)) => u32::from(example.0),
            Term::Constant(Constant::Orientation(constant)) => constant.encoding(),
            Term::Constant(Constant::Unit) => 0,
            Term::Box(margins) => margins.pack()?,
            Term::Ident(Ident(index)) => index,
        };
        Ok(TermId(bits))
    }

    /// The term that `id` stands for at a column of type `ty`.
    ///
    /// A row has no type tag, so the column's static type is the one source
    /// of the interpretation: at the type the checker gives the id's column,
    /// as [`crate::types::ProgramTypes`] holds it, the term is the one the id
    /// stands for, and at another type it is a term the id does not stand
    /// for, such as an encoding read as a `Number`.
    ///
    /// A record's value takes one column per field, so no one id stands for
    /// it, and this panics at a [`ValueType::Record`].
    pub fn decode(id: TermId, ty: &ValueType) -> Term {
        let bits = id.0;
        let orientation = |admitted: &[OrientationType]| {
            Term::Constant(Constant::Orientation(OrientationConstant::decode(bits, admitted)))
        };
        match ty {
            ValueType::Number => Term::Number(Number(bits as i32)),
            ValueType::Color => Term::Constant(Constant::Color(Color(bits as u8))),
            ValueType::Example => Term::Constant(Constant::Example(Example(bits as u16))),
            ValueType::Unit => Term::Constant(Constant::Unit),
            ValueType::Box => Term::Box(Margins::unpack(bits)),
            ValueType::Ident => Term::Ident(Ident(bits)),
            ValueType::C4 | ValueType::D4 | ValueType::Pose(_) => orientation(&[OrientationType::D4]),
            ValueType::Dir => orientation(&[OrientationType::Dir]),
            ValueType::DiagDir => orientation(&[OrientationType::DiagDir]),
            ValueType::Dir8 => orientation(&[OrientationType::Dir, OrientationType::DiagDir]),
            ValueType::Axis => orientation(&[OrientationType::Axis]),
            ValueType::DiagAxis => orientation(&[OrientationType::DiagAxis]),
            ValueType::Axis4 => orientation(&[OrientationType::Axis, OrientationType::DiagAxis]),
            ValueType::Sym => orientation(&[OrientationType::Sym]),
            ValueType::Sense => orientation(&[OrientationType::Sense]),
            ValueType::Record(_) => panic!("a record's value takes one column per field"),
        }
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
        WrittenIdent(number)
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
        let mut members: Vec<Box<[TermId]>> = members.into_iter().collect();
        members.sort_unstable_by(|a, b| MemberSet::order(a, b));
        members.dedup();
        MemberSet { member, members: members.into_boxed_slice() }
    }

    /// The canonical order of members: the lexicographic order of their
    /// encodings.
    fn order(a: &[TermId], b: &[TermId]) -> std::cmp::Ordering {
        a.iter().map(|id| id.0).cmp(b.iter().map(|id| id.0))
    }

    /// The type of the members.
    pub fn member_type(&self) -> &ValueType {
        &self.member
    }

    /// Whether `member`, one term id per field of the member type, is a
    /// member.
    pub fn contains(&self, member: &[TermId]) -> bool {
        self.members.binary_search_by(|m| MemberSet::order(m, member)).is_ok()
    }

    /// Each member, in an order of encodings and no order of the content.
    pub fn each(&self) -> impl Iterator<Item = &[TermId]> + '_ {
        self.members.iter().map(|m| &**m)
    }

    /// The positions within a member of the columns that hold an Ident.
    ///
    /// A field of a record type takes the columns of its own fields, side by
    /// side in field order, at every depth.
    fn ident_fields(&self) -> Vec<usize> {
        let mut positions = Vec::new();
        ident_columns(&self.member, 0, &mut positions);
        positions
    }

    /// The bytes the set holds on the heap.
    fn bytes(&self) -> usize {
        self.members
            .iter()
            .map(|m| std::mem::size_of::<Box<[TermId]>>() + std::mem::size_of_val(&**m))
            .sum()
    }
}

/// Adds to `positions` the columns from `start` on that hold an Ident in a
/// value of type `ty`, and gives the count of columns the value takes.
fn ident_columns(ty: &ValueType, start: usize, positions: &mut Vec<usize>) -> usize {
    match ty {
        ValueType::Ident => {
            positions.push(start);
            1
        }
        ValueType::Record(fields) => {
            fields.iter().fold(0, |taken, (_, field)| taken + ident_columns(field, start + taken, positions))
        }
        _ => 1,
    }
}

/// The term ids of `value` at a column of type `ty`: one term id, or, at a
/// record's column group, one per field, so a value written as a list is
/// read into the same columns. A Color's digit, a number and a
/// Box's margins are encoded as `ty` reads them, and an Ident's written
/// number is interned in `table` as a [`Content::FromFile`]. An
/// orientation name maps to its constant by
/// [`crate::registry::Registry::orientation_constant`], and a name the
/// registry declares no constant of is a [`DataValueError::NotOfType`].
/// `registry` gives which constants a type such as `C4` admits.
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

/// The rows of term ids of `value`, whose columns take `types` in order, for
/// the rows of a `param` form, of an `assign` form and of an input's default
/// alike, as `docs/arclog/arcdata.md#params` gives them, a grid's cells as
/// Position rows or, in a grid with an anchor, as Offset rows. A
/// derivation's values give the rows of the table the
/// registry's [`crate::registry::Derivation`] derives from them. Each value
/// takes its term ids from [`encode_data_value`].
pub fn encode_param_value(
    value: &crate::program::ParamValue,
    types: &[ValueType],
    registry: &crate::registry::Registry,
    table: &mut InternTable,
) -> Result<crate::hash::StableHashSet<Box<[TermId]>>, DataValueError> {
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
        let hash = {
            let mut hasher = crate::hash::StableHasher::new();
            std::hash::Hash::hash(&content, &mut hasher);
            hasher.finish128()
        };
        let idents = self.by_hash.entry(hash).or_default();
        if let Some(&ident) =
            idents.iter().find(|ident| self.contents[ident.0 as usize].as_ref() == Some(&content))
        {
            return ident;
        }
        let number = u32::try_from(self.contents.len()).expect("fewer than 2^32 Idents in a session");
        let ident = Ident(number);
        self.contents.push(Some(content));
        idents.push(ident);
        ident
    }

    /// The content that `ident` labels. A freed Ident is a fault of its
    /// holder, so this panics on one.
    pub fn content(&self, ident: Ident) -> &Content {
        self.contents[ident.0 as usize].as_ref().expect("an Ident that is not freed")
    }

    /// Frees each entry whose Ident `held` lacks and that no kept entry's
    /// content holds: it keeps each Ident in `held`, and each member of a set
    /// of Idents that a kept entry's content holds, at every depth. `held` is
    /// every Ident that a cached relation, a decode state or an event log
    /// holds. A freed number is not given again in the session.
    pub fn free_unheld(&mut self, held: &crate::hash::StableHashSet<Ident>) {
        let mut kept = vec![false; self.contents.len()];
        let mut pending: Vec<Ident> = held.iter().copied().collect();
        while let Some(ident) = pending.pop() {
            if std::mem::replace(&mut kept[ident.0 as usize], true) {
                continue;
            }
            if let Content::Set(set) = self.content(ident) {
                for field in set.ident_fields() {
                    pending.extend(set.each().map(|member| Ident(member[field].0)));
                }
            }
        }
        for (number, keep) in kept.into_iter().enumerate() {
            if !keep {
                self.contents[number] = None;
            }
        }
        let contents = &self.contents;
        self.by_hash.retain(|_, idents| {
            idents.retain(|ident| contents[ident.0 as usize].is_some());
            !idents.is_empty()
        });
    }

    /// The bytes the table holds, which count toward the task session's
    /// bound.
    pub fn bytes(&self) -> usize {
        let contents = self.contents.capacity() * std::mem::size_of::<Option<Content>>()
            + self
                .contents
                .iter()
                .flatten()
                .map(|content| match content {
                    Content::Set(set) => set.bytes(),
                    Content::FromFile { .. } => 0,
                })
                .sum::<usize>();
        let by_hash = self.by_hash.capacity()
            * (std::mem::size_of::<StableHash>() + std::mem::size_of::<Vec<Ident>>())
            + self
                .by_hash
                .values()
                .map(|idents| idents.capacity() * std::mem::size_of::<Ident>())
                .sum::<usize>();
        contents + by_hash
    }
}
