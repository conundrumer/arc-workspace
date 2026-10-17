//! The nodes of an arcdata file, from the whole file down to its values.

#![allow(unused_variables, dead_code)]

use std::sync::Arc;

use super::*;

/// A whole arcdata file, its forms in the order `docs/arclog/arcdata.md`
/// gives.
#[derive(Clone, Debug)]
pub struct Arcdata {
    pub representative: Option<Representative>,
    pub params: Arc<[Node<Param>]>,
    pub excludes: Arc<[Exclude]>,
    pub witness_records: Arc<[WitnessRecord]>,
}

/// `(representative <task_id> [<name>])`, as
/// `docs/arclog/arcdata.md#header` gives.
#[derive(Clone, Debug)]
pub struct Representative {
    pub task_id: Box<str>,
    /// The name of the case, one alt name, or a list of them where the case
    /// takes an alt at several `ALTS` forms, as an `output` form writes a
    /// name that fixes several alts.
    pub case: Option<Arc<[AltsName]>>,
}

/// A `param` form: the parameter, its column types, one type or a list,
/// and then its rows (`docs/arclog/arcdata.md#params`). The parameter is a
/// relation of the arclog file, or an output that a `RIGID_DET` or
/// `RULE_OR_DET` form stores, as `&piece.member`.
#[derive(Clone, Debug)]
pub struct Param {
    pub name: ProgramRelation,
    pub columns: Arc<[TypeName]>,
    pub value: ParamValue,
}

/// A type as a file writes it. `Position`, `Offset` and `Box` are one
/// [`crate::types::ValueType`], and the file keeps the name it writes.
#[derive(Clone, Copy, PartialEq, Eq, Hash, Debug)]
pub enum TypeName {
    Number,
    Color,
    Example,
    Unit,
    Box,
    Position,
    Offset,
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
}

impl TypeName {
    /// The type the name stands for, `Box` for `Position` and `Offset`.
    pub fn value_type(self) -> crate::types::ValueType {
        todo!()
    }
}

/// The rows of a `param` form or an `assign` form, as
/// `docs/arclog/arcdata.md#params` gives.
#[derive(Clone, Debug)]
pub enum ParamValue {
    /// Rows written as lists of values.
    Rows(Arc<[Arc<[DataValue]>]>),
    /// The rows of a relation with a Position column, written as grids: one
    /// [`GridRows`] per grid.
    Grids(Arc<[GridRows]>),
    /// The values a table derives from, under the derivation's name: `Frame`
    /// or `Division`.
    Derivation {
        derivation: crate::registry::LibName,
        rows: Arc<[Arc<[DataField]>]>,
    },
}

/// One grid of a `param` or `assign` form, with the values before it: each
/// cell gives one row, the values, then the cell's position, then its value.
/// A grid with no values before it is written bare, `(grid ...)`, and one
/// with values is written `(1 (grid ...))`.
#[derive(Clone, Debug)]
pub struct GridRows {
    pub before: Arc<[DataValue]>,
    pub grid: Grid,
}

/// One value of a derivation's row, under its column's name: `(:A AXIS_V)`,
/// `(:N 6)`, such as a frame's extent on one axis, or a tile count, tile
/// size or gap.
#[derive(Clone, PartialEq, Eq, Hash, Debug)]
pub struct DataField {
    pub column: ColumnName,
    pub value: DataValue,
}

/// A value written in an arcdata file, held as the file writes it, with no
/// type. [`crate::terms::encode_data_value`] gives its typed value, such as
/// a Box or one column per member of a list, by its column's type, for a
/// row of a `param` form and of an `assign` form alike: the type a `param`
/// form writes, or, for a relation that no `param` form gives, the type the
/// type check infers for the column, so the typed value follows the check.
#[derive(Clone, PartialEq, Eq, Hash, Debug)]
pub enum DataValue {
    /// An integer as the file writes it: a number, a Color's digit or an
    /// Ident's number, by the column's type.
    Integer(i32),
    /// An orientation constant, written by its name in the registry.
    Orientation(crate::terms::OrientationConstant),
    /// A value written as a list: a Box as its four margins, `(1 1 10 1)`,
    /// or the members of a column group of several fields, which are read
    /// into the same columns as the fields written apart.
    List(Arc<[DataValue]>),
}

/// A grid of an arcdata file: one row per line, a cell `_` gives no row.
#[derive(Clone, Debug)]
pub struct Grid {
    pub rows: Arc<[Arc<[Option<DataValue>]>]>,
    /// The cell written with `@` before it, as `@_` or `@1`: the anchor of
    /// a grid of an Offset column, from which its cells' offsets count.
    pub anchor: Option<GridCell>,
}

/// A cell of a grid, by its row and its column, each counted from 0.
#[derive(Clone, Copy, PartialEq, Eq, Hash, Debug)]
pub struct GridCell {
    pub row: u32,
    pub column: u32,
}

/// An `exclude` form: the combination it leaves out, and its reason.
#[derive(Clone, Debug)]
pub struct Exclude {
    pub combination: Arc<[AltsName]>,
    pub reason: Option<Text>,
}

/// An `alts` form or an `approximated` form, with its witnesses
/// (`docs/arclog/arcdata.md#alts`).
#[derive(Clone, Debug)]
pub enum WitnessRecord {
    Alts {
        name: AltsName,
        alts: Arc<[AltRecord]>,
    },
    Approximated {
        claim: Slug,
        witnesses: Arc<[Witness]>,
    },
}

/// An `alt` form: its witnesses, and a nested `alt` form per combination.
#[derive(Clone, Debug)]
pub struct AltRecord {
    pub name: AltsName,
    pub witnesses: Arc<[Witness]>,
    pub nested: Arc<[AltRecord]>,
}

/// A `witness` form, as `docs/arclog/arcdata.md#witnesses` gives. A witness
/// with no body refers to the witness of that id given in full under an
/// earlier alt.
#[derive(Clone, Debug)]
pub struct Witness {
    pub id: Box<str>,
    pub plausibility: Plausibility,
    pub verdict: Verdict,
    pub body: Option<WitnessBody>,
}

/// A witness's plausibility.
#[derive(Clone, Copy, PartialEq, Eq, Hash, Debug)]
pub enum Plausibility {
    Ordinary,
    Variant,
    Borderline,
    Foreign,
}

/// A witness's verdict.
#[derive(Clone, PartialEq, Eq, Hash, Debug)]
pub enum Verdict {
    Concept,
    Alt(AltsName),
    Any,
    Other,
}

/// The body of a witness given in full.
#[derive(Clone, Debug)]
pub struct WitnessBody {
    pub relaxed: Arc<[Slug]>,
    pub separates: Text,
    pub assigns: Arc<[(ProgramRelation, ParamValue)]>,
    pub input: Grid,
    pub outputs: Arc<[WitnessOutput]>,
}

/// A name in an `output` form: `concept`, the concept case, or an alt's
/// name. An `output` form gives each distinct output with the fewest names
/// whose cases together give it.
#[derive(Clone, PartialEq, Eq, Hash, Debug)]
pub enum CaseRef {
    Concept,
    Alt(AltsName),
}

/// An `output` form of a witness.
#[derive(Clone, Debug)]
pub struct WitnessOutput {
    /// The names whose cases together give the output; empty for the one
    /// output of a witness with the verdict `other`. A name that fixes
    /// several alts is a list.
    pub names: Arc<[Arc<[CaseRef]>]>,
    pub value: OutputValue,
}

/// The output of an `output` form.
#[derive(Clone, Debug)]
pub enum OutputValue {
    Undefined,
    /// One grid per model.
    Grids(Arc<[Grid]>),
}
