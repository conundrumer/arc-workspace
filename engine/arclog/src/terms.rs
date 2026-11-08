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
    pub fn encoding(self) -> u32 {
        self.0
    }

    /// The term id whose 32 bits are `bits`.
    pub fn from_encoding(bits: u32) -> Self {
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

    /// The digit a task file writes for the color, for a reader or a writer
    /// of task files. The digit is the file's notation, and no order of
    /// colors.
    pub fn digit(self) -> u8 {
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

    /// The example's index in the task file.
    pub fn index(self) -> u16 {
        self.0
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
pub const ORIENTATION_TYPES: [OrientationType; 7] = [
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
    LibName(LibNameId),
}

/// A lib name: a constant with equality alone, such as a name of the lib or
/// the engine's identity of a table or a column. The group fixes it.
#[derive(Clone, Copy, PartialEq, Eq, Hash, Debug)]
pub struct LibNameId(u32);

/// The texts of the lib names of the process. An id depends on the order of
/// interning, so a lib name has no order and a writer writes its text.
#[derive(Default)]
struct LibNames {
    ids: std::collections::HashMap<std::sync::Arc<str>, u32>,
    texts: Vec<std::sync::Arc<str>>,
}

fn lib_names() -> &'static std::sync::RwLock<LibNames> {
    static NAMES: std::sync::OnceLock<std::sync::RwLock<LibNames>> = std::sync::OnceLock::new();
    NAMES.get_or_init(Default::default)
}

impl LibNameId {
    /// The lib name whose text is `text`.
    pub fn of(text: &str) -> LibNameId {
        if let Some(id) = lib_names().read().expect("a table that no panic poisoned").ids.get(text) {
            return LibNameId(*id);
        }
        let mut names = lib_names().write().expect("a table that no panic poisoned");
        if let Some(id) = names.ids.get(text) {
            return LibNameId(*id);
        }
        let id = u32::try_from(names.texts.len()).expect("fewer than 2^32 lib names");
        let held: std::sync::Arc<str> = text.into();
        names.texts.push(held.clone());
        names.ids.insert(held, id);
        LibNameId(id)
    }

    /// The name's text.
    pub fn text(self) -> std::sync::Arc<str> {
        lib_names().read().expect("a table that no panic poisoned").texts[self.0 as usize].clone()
    }
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
        // The bits that a margin takes, which is the extent of its signed byte; the counter
        // of the Box margin bound reads the largest of them ([`crate::eval::ambient`]).
        let extent = |margin: i32| (margin ^ (margin >> 31)) as u32;
        crate::eval::ambient::note_margin(extent(self.top).max(extent(self.bottom)).max(extent(self.left)).max(extent(self.right)));
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
/// and no order. A table export gives the content's member digest in place of
/// the number ([`InternTable::export_cell`]).
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
/// its id, which a construction of `arclog-constructions` takes, and
/// `Term::decode_number`, `Term::decode_box`, `Term::encode_number` and
/// `Term::encode_count` are the way for a `number` column, a Box column, a
/// number and a count.
impl Term {
    /// The term id of the term.
    ///
    /// Fails only for a Box with a margin outside a signed byte.
    pub fn encode(self) -> Result<TermId, ReachedMarginBound> {
        let bits = match self {
            Term::Number(Number(n)) => Term::encode_number(n).0,
            Term::Constant(Constant::Color(color)) => u32::from(color.0),
            Term::Constant(Constant::Example(example)) => u32::from(example.0),
            Term::Constant(Constant::Orientation(constant)) => constant.encoding(),
            Term::Constant(Constant::Unit) => 0,
            Term::Constant(Constant::LibName(name)) => name.0,
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
            ValueType::Int | ValueType::Nat => Term::Number(Number(Term::decode_number(id))),
            ValueType::Color => Term::Constant(Constant::Color(Color(bits as u8))),
            ValueType::Example => Term::Constant(Constant::Example(Example(bits as u16))),
            ValueType::Unit => Term::Constant(Constant::Unit),
            ValueType::LibName => Term::Constant(Constant::LibName(LibNameId(bits))),
            ty if ty.is_box() => Term::Box(Term::decode_box(id)),
            ValueType::Ident(_) => Term::Ident(Ident(bits)),
            ValueType::Pose(_) => Term::decode(id, &ValueType::D4),
            ValueType::Record(_) => panic!("a record's value takes one column per field"),
            orientation_type => orientation(
                orientation_type.orientation_types().expect("each type of no other arm is an orientation type"),
            ),
        }
    }

    /// The number that `id` stands for at a `number` column.
    pub fn decode_number(id: TermId) -> i32 {
        id.0 as i32
    }

    /// The margins that `id` stands for at a Box column.
    pub fn decode_box(id: TermId) -> Margins {
        Margins::unpack(id.0)
    }

    /// The term id of the number `n`.
    pub fn encode_number(n: i32) -> TermId {
        TermId(n as u32)
    }

    /// The term id of the count `n`.
    ///
    /// Panics where `n` exceeds an `i32`.
    pub fn encode_count(n: usize) -> TermId {
        let n = i32::try_from(n).expect("a count within an i32");
        Term::encode_number(n)
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
        ValueType::Ident(_) => {
            positions.push(start);
            1
        }
        ValueType::Record(fields) => {
            fields.iter().fold(0, |taken, (_, field)| taken + ident_columns(field, start + taken, positions))
        }
        _ => 1,
    }
}

/// The canonical order by content of two values of the columns `types`, one
/// type per column, as `docs/engine/cases.md#the-constraint-module` gives
/// it: column by column, a term by its encoding and an Ident by its
/// content in `table`, which is the order by which a writer numbers Idents
/// (`docs/engine/reader.md#terms`). An Ident read from a file comes before
/// every set, in the order of its written number. Two sets compare member
/// by member, each set's members in this order, from the inside out, and a
/// set that is a prefix of the other comes first.
pub(crate) fn content_order(types: &[ValueType], a: &[TermId], b: &[TermId], table: &InternTable) -> std::cmp::Ordering {
    use std::cmp::Ordering;
    for ((ty, x), y) in types.iter().zip(a).zip(b) {
        let order = match ty {
            ValueType::Ident(_) if x != y => ident_order(Ident(x.0), Ident(y.0), table),
            _ => x.0.cmp(&y.0),
        };
        if order != Ordering::Equal {
            return order;
        }
    }
    Ordering::Equal
}

/// The order of two Idents by their contents, as [`content_order`] gives it.
fn ident_order(a: Ident, b: Ident, table: &InternTable) -> std::cmp::Ordering {
    use std::cmp::Ordering;
    match (table.content(a), table.content(b)) {
        (Content::FromFile { written: x, .. }, Content::FromFile { written: y, .. }) => x.0.cmp(&y.0),
        (Content::FromFile { .. }, Content::Set(_)) => Ordering::Less,
        (Content::Set(_), Content::FromFile { .. }) => Ordering::Greater,
        (Content::Set(x), Content::Set(y)) => {
            let mut types = Vec::new();
            column_types(&x.member, &mut types);
            set_order(&types, x.each(), y.each(), table)
        }
    }
}

/// The order of two sets of rows whose columns take `types`: each set's
/// rows sorted by [`content_order`] and compared row by row, a set that is
/// a prefix of the other first.
pub(crate) fn set_order<'r>(
    types: &[ValueType],
    a: impl Iterator<Item = &'r [TermId]>,
    b: impl Iterator<Item = &'r [TermId]>,
    table: &InternTable,
) -> std::cmp::Ordering {
    let (mut a, mut b): (Vec<&[TermId]>, Vec<&[TermId]>) = (a.collect(), b.collect());
    a.sort_by(|x, y| content_order(types, x, y, table));
    b.sort_by(|x, y| content_order(types, x, y, table));
    a.iter().zip(&b).map(|(x, y)| content_order(types, x, y, table)).find(|order| order.is_ne()).unwrap_or_else(|| a.len().cmp(&b.len()))
}

/// Adds to `types` the type of each column a value of type `ty` takes: a
/// record's fields side by side in field order, at every depth.
fn column_types(ty: &ValueType, types: &mut Vec<ValueType>) {
    match ty {
        ValueType::Record(fields) => fields.iter().for_each(|(_, field)| column_types(field, types)),
        _ => types.push(ty.clone()),
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
/// infers.
pub fn encode_data_value(
    value: &crate::program::DataValue,
    ty: &ValueType,
    registry: &crate::registry::Registry,
    table: &mut InternTable,
) -> Result<Box<[TermId]>, DataValueError> {
    use crate::program::DataValue;
    let not_of_type = || DataValueError::NotOfType { value: value.clone(), ty: ty.clone() };
    let one = |term: Term| term.encode().map(|id| Box::from([id])).map_err(DataValueError::MarginBound);
    let orientation = |admitted: &dyn Fn(OrientationConstant) -> bool| match value {
        DataValue::Orientation(name) => match registry.orientation_constant(name) {
            Some(constant) if admitted(constant) => one(Term::Constant(Constant::Orientation(constant))),
            _ => Err(not_of_type()),
        },
        _ => Err(not_of_type()),
    };
    let of_type = |types: &'static [OrientationType]| move |constant: OrientationConstant| types.contains(&constant.ty());
    match (ty, value) {
        (ValueType::Record(fields), DataValue::List(values)) if values.len() == fields.len() => {
            let mut ids = Vec::new();
            for ((_, field), value) in fields.iter().zip(values.iter()) {
                ids.extend(encode_data_value(value, field, registry, table)?);
            }
            Ok(ids.into())
        }
        (ValueType::Nat, DataValue::Integer(n)) if *n >= 0 => one(Term::Number(Number(*n))),
        (ValueType::Int, DataValue::Integer(n)) => one(Term::Number(Number(*n))),
        (ValueType::Color, DataValue::Integer(n)) => {
            let color = u8::try_from(*n).ok().and_then(Color::from_digit).ok_or_else(not_of_type)?;
            one(Term::Constant(Constant::Color(color)))
        }
        (ValueType::Example, DataValue::Integer(n)) => {
            let index = u16::try_from(*n).map_err(|_| not_of_type())?;
            one(Term::Constant(Constant::Example(Example::at(index))))
        }
        (ty, DataValue::List(margins)) if ty.is_box() => match &margins[..] {
            [DataValue::Integer(top), DataValue::Integer(bottom), DataValue::Integer(left), DataValue::Integer(right)] => {
                one(Term::Box(Margins { top: *top, bottom: *bottom, left: *left, right: *right }))
            }
            _ => Err(not_of_type()),
        },
        (ValueType::Ident(_), DataValue::Integer(n)) => {
            let written = WrittenIdent(u32::try_from(*n).map_err(|_| not_of_type())?);
            one(Term::Ident(table.intern(Content::FromFile { ty: ValueType::OPEN_IDENT, written })))
        }
        (ValueType::C4, _) => orientation(&|constant| registry.c4_constants().contains(constant)),
        (ValueType::Pose(_), _) => orientation(&of_type(ValueType::D4.orientation_types().expect("D4 is an orientation type"))),
        (ty, _) => match ty.orientation_types() {
            Some(types) => orientation(&of_type(types)),
            None => Err(not_of_type()),
        },
    }
}

/// The rows of term ids of `value`, whose columns take `types` in order, for
/// the rows of a `param` form, of an `assign` form and of an input's default
/// alike, as `docs/arclog/arcdata.md#params` gives them. A grid's cell takes
/// as its Position the cell in the grid's own frame, of the grid's row
/// count and row length, and, in a grid with an anchor, as its Offset the
/// translation from the anchor to the cell. Each value takes its term ids
/// from [`encode_data_value`].
pub fn encode_param_value(
    value: &crate::program::ParamValue,
    types: &[ValueType],
    registry: &crate::registry::Registry,
    table: &mut InternTable,
) -> Result<crate::hash::StableHashSet<Box<[TermId]>>, DataValueError> {
    use crate::program::{DataValue, ParamValue};
    let mut rows = crate::hash::StableHashSet::default();
    let row_type = |types: &[ValueType]| {
        ValueType::Record(types.iter().enumerate().map(|(i, ty)| (crate::program::ColumnName::Slot(i as u32), ty.clone())).collect())
    };
    let values = |values: &[DataValue], types: &[ValueType], table: &mut InternTable| -> Result<Vec<TermId>, DataValueError> {
        if values.len() != types.len() {
            return Err(DataValueError::NotOfType { value: DataValue::List(values.into()), ty: row_type(types) });
        }
        let mut ids = Vec::new();
        for (value, ty) in values.iter().zip(types) {
            ids.extend(encode_data_value(value, ty, registry, table)?);
        }
        Ok(ids)
    };
    match value {
        ParamValue::Rows(written) => {
            for row in written.iter() {
                rows.insert(values(row, types, table)?.into());
            }
        }
        ParamValue::Grids(grids) => {
            for grid in grids.iter() {
                let at = grid.before.len();
                let (before, rest) = types.split_at(at.min(types.len()));
                let Some((_, after)) = rest.split_first().filter(|(ty, _)| ty.is_box()) else {
                    return Err(DataValueError::NotOfType { value: DataValue::List(grid.before.clone()), ty: row_type(types) });
                };
                let before = values(&grid.before, before, table)?;
                let height = grid.grid.rows.len();
                for (r, cells) in grid.grid.rows.iter().enumerate() {
                    for (c, cell) in cells.iter().enumerate() {
                        let Some(cell) = cell else { continue };
                        let margins = match grid.grid.anchor {
                            Some(anchor) => {
                                let (dr, dc) = (r as i32 - anchor.row as i32, c as i32 - anchor.column as i32);
                                Margins { top: dr, bottom: -dr, left: dc, right: -dc }
                            }
                            None => crate::task::cell_position(r, c, height, cells.len()),
                        };
                        let position = Term::Box(margins).encode().map_err(DataValueError::MarginBound)?;
                        let value = match (after, cell) {
                            ([], DataValue::Integer(1)) => Vec::new(),
                            ([], _) => return Err(DataValueError::NotOfType { value: cell.clone(), ty: ValueType::Int }),
                            ([ty], _) => encode_data_value(cell, ty, registry, table)?.into_vec(),
                            (_, DataValue::List(cell)) => values(cell, after, table)?,
                            (_, _) => return Err(DataValueError::NotOfType { value: cell.clone(), ty: row_type(after) }),
                        };
                        let row: Vec<TermId> = before.iter().copied().chain([position]).chain(value).collect();
                        rows.insert(row.into());
                    }
                }
            }
        }
    }
    Ok(rows)
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
/// used again in the session. It also keeps the member digest of each content,
/// which is the same in every session.
#[derive(Debug, Default)]
pub struct InternTable {
    /// The content of each number given, `None` once freed.
    contents: Vec<Option<Content>>,
    /// The member digest of each number given, as [`InternTable::digest`]
    /// gives it: zero where the content is freed.
    digests: Vec<StableHash>,
    /// The Idents of the contents of each hash.
    by_hash: crate::hash::StableHashMap<StableHash, Vec<Ident>>,
    /// The bytes of each set in `contents` plus the capacity in bytes of each
    /// `Vec<Ident>` in `by_hash`, kept in step by `intern` and set again by
    /// `free_unheld`.
    held_bytes: usize,
}

impl InternTable {
    /// The bytes of `contents` that its entries hold, apart from the
    /// capacity of `contents` itself.
    fn content_bytes(content: &Content) -> usize {
        match content {
            Content::Set(set) => set.bytes(),
            Content::FromFile { .. } => 0,
        }
    }

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
        let before = idents.capacity();
        idents.push(ident);
        let grown = (idents.capacity() - before) * std::mem::size_of::<Ident>();
        self.held_bytes += grown + Self::content_bytes(&content);
        let digest = self.digest_of(&content);
        self.digests.push(digest);
        self.contents.push(Some(content));
        ident
    }

    /// The member digest of `content`, which is the same in every process
    /// and session: a hash of the member type's column types and of the
    /// members, as a sum of the hash of each member. A member's hash holds
    /// its term ids, except that it holds the digest of each Ident in it in
    /// place of that Ident's number. Each Ident in a member is already
    /// interned, so the digest is built from the inside out. A content read
    /// from a file has the digest of its written number.
    fn digest_of(&self, content: &Content) -> StableHash {
        use std::hash::Hash;
        let mut hasher = crate::hash::StableHasher::new();
        match content {
            Content::FromFile { written, .. } => {
                0u8.hash(&mut hasher);
                written.0.hash(&mut hasher);
            }
            Content::Set(set) => {
                1u8.hash(&mut hasher);
                let mut types = Vec::new();
                column_types(&set.member, &mut types);
                for ty in &types {
                    ty.without_source().hash(&mut hasher);
                }
                let idents = set.ident_fields();
                let mut sum = 0u128;
                for member in set.each() {
                    let mut member_hasher = crate::hash::StableHasher::new();
                    for (field, id) in member.iter().enumerate() {
                        if idents.contains(&field) {
                            self.digests[id.0 as usize].0.hash(&mut member_hasher);
                        } else {
                            id.0.hash(&mut member_hasher);
                        }
                    }
                    sum = sum.wrapping_add(member_hasher.finish128().0);
                }
                sum.hash(&mut hasher);
                (set.members.len() as u64).hash(&mut hasher);
            }
        }
        hasher.finish128()
    }

    /// The member digest of `ident`'s content, as [`InternTable::intern`]
    /// computed it.
    pub fn digest(&self, ident: Ident) -> StableHash {
        self.digests[ident.0 as usize]
    }

    /// The cell that a table export gives `ident`: the first 32 bits of its
    /// digest. It is the same for equal contents in every process.
    pub fn export_cell(&self, ident: Ident) -> i32 {
        (self.digest(ident).0 >> 96) as u32 as i32
    }

    /// The content that `ident` labels. A freed Ident is a fault of its
    /// holder, so this panics on one.
    pub fn content(&self, ident: Ident) -> &Content {
        self.contents[ident.0 as usize].as_ref().expect("an Ident that is not freed")
    }

    /// Frees each entry whose Ident `held` lacks and that no kept entry's
    /// content holds: it keeps each Ident in `held`, and each member of a set
    /// of Idents that a kept entry's content holds, at every depth. `held` is
    /// every Ident that a cached relation, a decode state or a trace
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
                self.digests[number] = StableHash(0);
            }
        }
        let contents = &self.contents;
        self.by_hash.retain(|_, idents| {
            idents.retain(|ident| contents[ident.0 as usize].is_some());
            !idents.is_empty()
        });
        self.held_bytes = self
            .contents
            .iter()
            .flatten()
            .map(Self::content_bytes)
            .sum::<usize>()
            + self
                .by_hash
                .values()
                .map(|idents| idents.capacity() * std::mem::size_of::<Ident>())
                .sum::<usize>();
    }

    /// The bytes the table holds, which count toward the task session's
    /// bound. It runs in constant time.
    pub fn bytes(&self) -> usize {
        self.contents.capacity() * std::mem::size_of::<Option<Content>>()
            + self.digests.capacity() * std::mem::size_of::<StableHash>()
            + self.by_hash.capacity()
                * (std::mem::size_of::<StableHash>() + std::mem::size_of::<Vec<Ident>>())
            + self.held_bytes
    }
}
