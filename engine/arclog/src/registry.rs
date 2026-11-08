//! The lib registry: the names of the lib, and what each declares. It is
//! embedded from the registry file and the proposers file, as
//! [`REGISTRY_TEXT`] and [`PROPOSERS_TEXT`], when the engine is compiled, so
//! the wheel reads no file for it. A new lib element adds a
//! registry entry and changes no checker code.
//!
//! # The file
//!
//! The file is `engine/lib/registry.sexpr`. It is s-expressions, read by the
//! reader of [`crate::read::read_sexprs`], so the engine has one reader for
//! every s-expression file. `include_str!` puts its text into the compiled
//! crate, and [`Registry::get`] reads that text once, on first use. The test
//! `registry_file` under `engine/arclog/tests/integration/` parses both lib files, so a
//! fault of either fails `cargo test`.
//!
//! Each `;;;` comment line before a form, other than `;;; @rare`, is a line of its prose, the
//! user-facing text of what the form declares, which
//! `scripts/generate_study_meanings.py` writes into `docs/arclog/lib.md`, or
//! into `docs/arclog/lib-rare.md` where the block opens with `;;; @rare`, and
//! into `engine/lib/study-meanings.json`. The reader skips comments.
//!
//! Each top-level form declares one lib element, by its head:
//!
//! - `(refines <element> <item> ...)`: what a relation's type holds of its values at a lib element, a
//!   relation, a fact or `<component>.<output>`, for the feature encoder. A `<item>` is `(key <column> ...)`,
//!   `(at-least <column> <number>)`, `(each (<column> ...) <rows>)`, `(each-key)`, `(each-row <input>
//!   <column> ...)`, or a claim under a condition on the instance's inputs: `(covered <input> <claim>)`,
//!   `(single <input> <claim>)`, `(unbound (<input> ...) <claim>)`, `(tied <input> <column> <claim>)`. A
//!   `<claim>` is `(at-least <column> <number>)`, `(at-most <column> <number>)`, `(same-as <input>)` or `empty`.
//! - `(relation <name> (columns (<Column> <type>) ...) (modes (<Column> ...) ...) [<frames>] [<types>])`:
//!   an algebra relation, the group relations and `pose_difference`
//!   included. Each mode lists the columns, other than an orientation
//!   type's, that must be bound for the relation to bind the others; a
//!   relation over a finite domain has no `modes` form, and no mode is empty.
//!   `<frames>` is a `(frames ...)` form, as the section on frames gives it,
//!   and `<types>` a `(types ...)` form, as the section on type rules gives it.
//! - `(component <name> <construction|detector|task-structure> (type-parameters <t> ...)
//!   (inputs (<input> (<column> <type>) ... [(default <rows>)] [reads-outputs] [from-key] [required | one-of-<group> ...]) ...)
//!   (outputs (<output> (<column> <type>) ... [(copies <row> ...)] [<frames>]) ...))`: a construction, a
//!   detector or a task-structure component, its inputs in the order the component declares them. Each
//!   `<t>` is a parameter's name or `(<name> <type>)`, a parameter with a bound. An `INIT` form's binding of a
//!   bounded parameter is a type at or under the bound, a binding outside it is a type fault at the site that
//!   binds it, and a bounded parameter that no place of the form binds takes its bound. A bounded parameter binds to the join of the types of every projection onto it, and projections whose types have no join are a type fault at the first site that has none with the sites before it. A column of a parameter
//!   has a frame where a column of its bound's type has one. An
//!   input's `default` writes its rows as a `param` form writes them after
//!   its types (`docs/arclog/arcdata.md#params`). An input marked
//!   `reads-outputs` reads the instance's outputs, as `Unfold`'s `step`,
//!   `skip` and `take` do. An input marked `from-key`, which writes no
//!   `default`, is filled from the key where the instance writes no clause
//!   for it, as Cardinality's `domain`; an input with neither mark nor
//!   `default` holds no row there. An input marked `required` is one where
//!   the component gives no output while the input holds no row, as
//!   Connectivity's `node`. A mark `one-of-<group>` puts the input in the
//!   `one-of` group `<group>`, a name that tells the groups of one component
//!   apart. A group holds two inputs or more. The component gives no output
//!   while none of the inputs of one group holds a row, as Quotient's `equivalent`
//!   and `edge`, the group `pairs`, give. An input carries one mark for each
//!   group it belongs to, as Wallpaper's `period` does. An input takes
//!   `required` or group marks, not both. A mark is
//!   a bare symbol, since a list of two words in an input form is a column.
//!   The marks come last in the input's list, after `from-key`. An input with
//!   `default` rows takes no mark, and neither does an input marked
//!   `from-key` whose one column is `key`, since the instance fills each where
//!   it writes no clause for it. The stream's decoder refuses the `SKIP` that
//!   leaves a required input, or each input of a `one-of` group, with no row
//!   (`docs/engine/arclog-stream.md#token-stream`), and the text checker
//!   refuses an `INIT` form that leaves one so
//!   (`docs/arclog/arclog.md#instance`). An output may share its name with an input of
//!   the same form, as `Unfold`'s `take` does: an instance's output of that
//!   name, where the instance writes no clause for it, reads the input's
//!   relation. An output's `(copies <row> ...)` form declares the rows of the
//!   inputs of a group that the output's rows copy. A `<row>` is
//!   `(<input> (<input column> <output column>) ...)` or `(either <row> ...)`,
//!   whose rows are the alternatives of one row, each on an input, mapping the
//!   same output columns. A row names the output columns it copies and the
//!   input columns it copies them from, which have one type each, and names
//!   no `key` column: where the input and the output both have a `key`
//!   column, the output's copies the input's, since a group's rows share its
//!   key. Two rows on one input are two rows of it, which may differ, as
//!   `Order`'s `successor` takes `a` and `b` from two members. An output
//!   column that no row names claims no row, and an output with no
//!   `copies` form claims none. A declaration holds only what the
//!   construction guarantees in every group: each output row's values at the
//!   columns a row names are, at the input columns they are copied from,
//!   those of a row of that input in the group, or of an alternative's. A
//!   row that names an input or a column the component does not declare, a
//!   `key` column, an output column twice in an alternative, columns of
//!   different types, or alternatives that name different output columns is
//!   a fault of the file.
//! - `(proposer <name> native [domain] (columns (<Column> <type>) ...))`: a
//!   native proposer, marked `domain` where it is a type-domain proposer, as
//!   `docs/arclog/arclog.md#program` gives one.
//! - `(proposer <name> arclog (columns <Label> ...))`: a proposer written
//!   in arclog, whose clause stands in `engine/lib/proposers.arclog`. Its
//!   columns are the labels the form names, in the order the form gives.
//!   Each is a label that its clause keeps, and each other label of the
//!   clause is projected away. Each column has the type that
//!   [`macro_column_types`] gives a relation macro's column whose label is
//!   the column's, over the clause.
//! - `(constants <type> <NAME> ...)`: the constants of an orientation type,
//!   and `(constants C4 <NAME> ...)`: the D4 constants that are C4, the
//!   rotations.
//! - `(type <Name>)`: a type name of [`crate::program::TypeName`], in the
//!   spelling of `crate::read::spelling::TYPE_NAMES`. The file has one such
//!   form for each type name, and none for another name or twice for one: a
//!   fault of the file otherwise, so the registry's type names are
//!   `TypeName`'s.
//! - `(fact <name> (columns (<Column> <type>) ...))`: the columns of a fact
//!   relation, `input`, `ex_input` or `ex_output`, the Example column `E`
//!   first in the two of the examples.
//! - `(macro <name> (columns (<Column> <Label> <type>) ...) [(modes (<Column> ...) ...)] [<frames>] [<types>] <body>)`:
//!   a lib relation that the lib defines from other lib names, each column
//!   with the label of the definition it stands for and its type, and its
//!   definition. A `<type>` stands at or under the type the definition gives
//!   the column's label, and is the column's type. The `modes` form is
//!   written as a `relation` form's is, and a macro with no mode has no
//!   `modes` form. A [`Macro::Relation`]'s column types, modes and rules are
//!   the ones [`macro_column_types`] derives from the definition, so a
//!   column whose type, or a macro whose modes, the form declares otherwise
//!   is a fault of the file.
//!
//! # Frames
//!
//! A column of type `Position` or `Box` has values in a frame: the input
//! grid's, the output grid's, or a frame that a lib column makes. A
//! `(frames (<column> <rule>) ...)` form, in a `relation`, a `macro` or an
//! output of a `component`, gives the rule of each column it names, and the
//! forms of a `<rule>` are those of [`FrameRule`].
//!
//! A column a rule names is a column of the relation or the macro, and, in
//! an output, `<input>.<column>`, a column of one of the component's inputs.
//! A column of type `Position` or `Box` that no form names takes the rule
//! `(of <each column of that type that the mode binds>)` in a relation or a
//! macro, at each mode, and `(of <each column of that type, other than
//! `key`, of the component's inputs>)` in an output, or `(of <the input columns
//! that the rows copy into it>)` in an output column that a `copies` row maps.
//! [`Registry::relation_frame`] and [`Registry::output_frame`] give the rule of a
//! column. A rule on a
//! column of another type, a rule that names a column the element does not
//! declare, and a rule on an output column that a `copies` row maps (a
//! copied column has the frame of the column it copies) are faults of the
//! file.
//!
//! # Type rules
//!
//! A `(types <rule> ...)` form of a `relation` or a `macro` form narrows a
//! `Box` column at a site from the types of the labels at the site's other
//! columns, and from the grids of those labels. A rule is `(when
//! (<condition> ...) (<Column> <type>) ...)`, each `<type>` `Box`,
//! `Position` or `Offset`, and each condition `(<Column> <type>)` or
//! `(same-frame <Column> <Column>)`. The rule holds at a site where each
//! column of its `(<Column> <type>)` conditions has a label whose type
//! stands at or under the condition's type, and each `same-frame` condition
//! has labels at its two columns of which a grid holds, as the type check
//! gives the grids of a label (`check/frames.rs`). At a site, a column's
//! type is the meet of its declared type and of the types each rule that
//! holds gives it ([`ruled_type`]), so a rule that holds keeps holding as the
//! types of the labels narrow and their grids grow. A rule conditions columns
//! of a `Box` type and gives columns it has no condition on a type at or
//! under the declared type; no two rules that hold at one assignment of
//! `Box`, `Position` and `Offset` to the condition columns, with each
//! `same-frame` condition holding, give a column types with an empty meet. A
//! rule that breaks this is a fault of the file. A `same-frame` condition
//! names two distinct `Box` columns of a relation, and a macro's written
//! rule has none, since a macro's derivation sees no grids.
//!
//! A rule holds for every value its column can take; a rule whose reason
//! needs two labels in one frame holds where a grid holds of both, as the
//! type check gives the grids of a label. A `Position` is a box of extent 1
//! on both axes, with per-axis sums (the frame's extent minus the box's) that
//! a frame fixes, and an `Offset` has sums 0 in every frame. `compose` adds
//! margins and `relative` subtracts them, so the sums add and subtract. The
//! rules and their reasons:
//!
//! - `compose` (`Position`, `Offset`) and (`Offset`, `Position`) give `C`
//!   `Position`: its sums are the `Position`'s, in the frame `C` takes from
//!   the `Position`'s column. (`Offset`, `Offset`) gives `Offset`: 0 + 0 = 0.
//! - `relative` (`Offset`, `Offset`) gives `X_rel` `Offset`: 0 - 0 = 0.
//!   (`Offset`, `Position`) gives `Position`: `X_rel` has `X`'s sums, in the
//!   frame `(new (of Base))` makes. (`Position`, `Position`) with `Base` and
//!   `X` in one frame gives `Offset`: both have the sums of one frame's
//!   extent minus 1, so `X_rel` has sums (V - 1) - (V - 1) = 0 on each axis.
//!   A grid that holds of both labels is one frame of one extent, and the
//!   condition stays true as the labels narrow and their grids grow.
//! - `apply` `Offset` gives `Offset`: a permutation of margins that sum to 0
//!   on each axis sums to 0.
//! - `split` `Position` gives `Across` `Position`: `Across` is `P` with its
//!   two margins on axis `A` set to 0, so its sum along `A` is 0 and across
//!   `A` is `P`'s, a cell of the frame of one line across `A` that
//!   `(new (of P))` makes. `Offset` gives `Offset`.
//!
//! The rules of a macro are its written rules, then the rules
//! [`macro_column_types`] derives from its definition. A written rule stands
//! at or under the type the definition gives its column under the rule's
//! conditions, and is a fault otherwise.
//!
//! An atom of a body of either file reads a name that a form declares, at
//! columns that name declares: a lib name, a macro or a fact. An atom that
//! reads another name or column is a fault of the file.
//!
//! A `<type>` is a type name of [`crate::program::TypeName`], `Pose` for
//! the assembly the read names, `shared-pose` for one assembly's Pose type
//! at each such column of the relation, `(pose-or <type>)` for the type or
//! the Pose type of the label at the site, or a type parameter of its
//! component. A column is `Position` or `Offset` only where the lib fixes
//! its role, and `Box` where the lib's clauses take it in either role, so a
//! label at it narrows only where another site narrows it or where a type
//! rule narrows the column. This holds of a
//! macro's column, with the type it declares, and of a column of a type
//! parameter, with its bound. The file declares
//! no `representative`. The file and
//! `engine/lib/proposers.arclog` are named in diagnostics as
//! [`crate::layout::SourceFile::LibRegistry`] and
//! [`crate::layout::SourceFile::LibProposers`].
//!
//! # The modules
//!
//! The reader of the two files, the spellings of the registry file's forms, the records of a form the reader reads, the reader of the registry file's other
//! forms, the reader of its macro form, the reader of the proposers file's clauses, the check of the reads of their bodies, the derivation of the
//! macros' column types and type rules, the declaration of the macros and of the proposers written in arclog from it, the rule by which an `INIT` form binds its
//! component's type parameters, the frame rules, and the type rules, their reader and the type a column takes under them, each stand in a module of their own. The derivations take the forms as the reader gives them, and
//! read no file.
//!
//! `engine/lib/proposers.arclog` holds one form `(proposer <Name> <atom> ...)`
//! per proposer of the form `(proposer <name> arclog (columns ...))`, its name in the
//! spelling of a proposer, as `(proposer DominantColor ...)`, then the atoms
//! of its clause's body, which [`crate::read::read_body`] reads.

#![allow(unused_variables, dead_code)]

use crate::check::CheckId;
use crate::safety::{body_labels, bound_labels, own_labels};
use crate::hash::{StableHashMap, StableHashSet};
use crate::layout::{SourceFile, SourcePlace};
use crate::program::{
    Atom, Body, ColumnName, FactRelation, LabelId, Node, PortName, RelationRef, TypeName,
};
use crate::read::spelling;
use crate::read::{check_error, head_of, read_body, read_param_value, read_sexprs, SExpr};
use crate::terms::{OrientationConstant, OrientationType};
use crate::types::{each_atom, each_conjunct, label_type, ValueType};

/// The text of the registry file, which [`Registry::get`] reads.
pub const REGISTRY_TEXT: &str = include_str!("../../lib/registry.sexpr");

/// The text of the proposers file, read by
/// [`crate::read::read_sexprs`] with
/// [`crate::layout::SourceFile::LibProposers`] and [`crate::read::read_body`].
pub const PROPOSERS_TEXT: &str = include_str!("../../lib/proposers.arclog");

/// A name of the lib: a relation, a component, a proposer or a macro, as the file writes it: `margin`, `Connectivity`,
/// `DominantColor`, `Frame`. An orientation constant is named by
/// [`Registry::orientation_constant`] instead.
#[derive(Clone, PartialEq, Eq, Hash, Debug)]
pub struct LibName(pub Box<str>);

/// A component's type parameter: its name, such as `t` or `key`, and the
/// type that bounds it, where it has one.
#[derive(Clone, PartialEq, Eq, Hash, Debug)]
pub struct TypeParameter {
    pub name: Box<str>,
    /// The type at or under which an `INIT` form binds the parameter, and
    /// which the parameter takes where no place of the form binds it.
    pub bound: Option<ValueType>,
}

/// Whether `ty` is `bound` or stands under it.
pub(crate) fn at_or_under(ty: &ValueType, bound: &ValueType) -> bool {
    ty.meet(bound) == crate::types::Meet::Type(ty.clone())
}

/// The type a lib column declares. A `:Pose` column has the type Pose of its
/// assembly.
#[derive(Clone, PartialEq, Eq, Hash, Debug)]
pub enum ColumnType {
    Fixed(ValueType),
    /// The Pose type of the assembly the read names.
    Pose,
    /// The Pose type of one assembly, the same at each column of the
    /// relation that declares it, as `pose_difference(a, b, d)` reads two
    /// poses of one assembly.
    SharedPose,
    /// The given type, or the Pose type of the label at the column's site, as
    /// `d4_elem`'s column is D4 or takes its label's Pose type
    /// (`docs/arclog/rigid.md#the-pose`).
    PoseOr(ValueType),
    /// A type parameter of the component, made concrete by an instance's
    /// binding.
    Parameter(TypeParameter),
}

impl ColumnType {
    /// The type the column gives its site in every read: that of a
    /// `Fixed` or a `PoseOr` column.
    pub fn fixed(&self) -> Option<&ValueType> {
        match self {
            ColumnType::Fixed(ty) | ColumnType::PoseOr(ty) => Some(ty),
            ColumnType::Pose | ColumnType::SharedPose | ColumnType::Parameter(_) => None,
        }
    }
}

/// A declared column: its name and type.
#[derive(Clone, PartialEq, Eq, Hash, Debug)]
pub struct Column {
    pub name: ColumnName,
    pub ty: ColumnType,
}

/// Whether `column` is the `key` column of its port.
pub fn is_key(column: &Column) -> bool {
    column.name == crate::resolver::columns::key()
}

/// A mode of an algebra relation: the columns whose labels must be bound
/// for its other columns to be bound.
#[derive(Clone, PartialEq, Eq, Hash, Debug)]
pub struct Mode {
    pub bound: Box<[ColumnName]>,
}

/// An algebra relation, a relation of the box algebra or the orientation
/// algebra, with its columns, their types and its modes.
#[derive(Clone, Debug)]
pub struct AlgebraRelation {
    pub columns: Box<[Column]>,
    /// Empty for a relation over a finite domain.
    pub modes: Box<[Mode]>,
    /// The rule that the `frames` form declares for each column it names, in
    /// the order it names them; [`Registry::relation_frame`] gives the rule of
    /// any column.
    pub frames: Box<[(ColumnName, FrameRule)]>,
    /// The type rules of the relation's `types` form, then, for a relation
    /// macro, the rules [`macro_column_types`] derives.
    pub rules: Box<[TypeRule]>,
}

/// The kind of a component: a construction, a detector or a task-structure
/// component. A task-structure component, `Choose` or
/// `DemonstrationConsistency`, is the component of a `CHOOSE` or a
/// `DEMONSTRATED` form, whose ports the registry declares as it declares a
/// construction's.
#[derive(Clone, Copy, PartialEq, Eq, Hash, Debug)]
pub enum ComponentKind {
    Construction,
    Detector,
    TaskStructure,
}

/// One input or output of a component.
#[derive(Clone, Debug)]
pub struct Port {
    pub name: PortName,
    pub columns: Box<[Column]>,
    /// The rows of the group's inputs that the rows of an output copy, in the
    /// order the file declares them; empty for an input and for an output
    /// that claims no row.
    pub copies: Box<[CopiedRow]>,
    /// The rule that the `frames` form of an output declares for each column
    /// it names, in the order it names them; empty for an input.
    /// [`Registry::output_frame`] gives the rule of any column.
    pub frames: Box<[(ColumnName, FrameRule)]>,
}

/// A declared row of an output: the row of an input of its group that the
/// output's rows copy, or one of several alternatives. Two declared rows on
/// one input are two rows of it, which may differ.
#[derive(Clone, Debug)]
pub struct CopiedRow {
    pub alternatives: Box<[CopiedFrom]>,
}

/// An alternative of a declared row: the input, as its index among the
/// component's inputs, and the pairs of a column of the input and the
/// column of the output that copies it, as indexes into the ports' columns.
/// The pairs hold no `key` column: the output's `key` copies the input's
/// where both ports have one, as [`CopiedFrom::column_pairs`] gives.
#[derive(Clone, Debug)]
pub struct CopiedFrom {
    pub input: usize,
    pub columns: Box<[(usize, usize)]>,
}

impl CopiedFrom {
    /// The pairs of a column of `input`, the port of the input this
    /// alternative names, and the column of `output` that copies it: the
    /// declared pairs, and the pair of the two `key` columns where both ports
    /// have one, since a group's rows share its key.
    pub fn column_pairs(&self, input: &Port, output: &Port) -> Vec<(usize, usize)> {
        let key = input.columns.iter().position(is_key).zip(output.columns.iter().position(is_key));
        key.into_iter().chain(self.columns.iter().copied()).collect()
    }
}

impl Port {
    /// The columns of the port at an instance that has a key clause where
    /// `keyed` holds, and otherwise those other than `key`.
    pub fn columns_at(&self, keyed: bool) -> impl Iterator<Item = &Column> + '_ {
        self.columns.iter().filter(move |column| keyed || !is_key(column))
    }

    /// The row positions that each column of the port takes, given the width
    /// of each column that `columns_at(keyed)` gives, in order: none for the
    /// `key` column where `keyed` does not hold.
    pub fn row_ranges(&self, keyed: bool, mut widths: impl Iterator<Item = usize>) -> Vec<Option<std::ops::Range<usize>>> {
        let mut start = 0usize;
        self.columns
            .iter()
            .map(|column| {
                if !keyed && is_key(column) {
                    return None;
                }
                let taken = widths.next().expect("a width for each column that the port has at the instance");
                start += taken;
                Some(start - taken..start)
            })
            .collect()
    }
}

/// An input of a component, with its default rows, which hold where the
/// instance writes no clause for the input.
#[derive(Clone, Debug)]
pub struct InputPort {
    pub port: Port,
    pub default: Option<DefaultRows>,
    /// Whether the input reads the instance's outputs, as `Unfold`'s `step`,
    /// `skip` and `take` do, through atoms whose every variable another atom
    /// of the clause binds.
    pub reads_outputs: bool,
    /// Whether the input, which then has no default, is filled from the
    /// key where the instance writes no clause for it, as Cardinality's
    /// `domain`.
    pub from_key: bool,
    /// What the component needs of the input to give any output, where the
    /// file marks it.
    pub need: Option<Need>,
}

/// What a component needs of an input to give any output, as the file marks
/// it on an input that has no default.
#[derive(Clone, PartialEq, Eq, Hash, Debug)]
pub enum Need {
    /// The input is marked `required`: the component gives no output where
    /// the input holds no row.
    Required,
    /// The input is marked `one-of-<name>`, once for each group it belongs
    /// to: for each such group, the component gives no output where none
    /// of the group's inputs holds a row.
    OneOf(Box<[GroupName]>),
}

/// The name of a `one-of` group of a component, the word after `one-of-` in
/// the mark. It tells the groups of one component apart, and means nothing
/// else.
#[derive(Clone, PartialEq, Eq, Hash, Debug)]
pub struct GroupName(pub Box<str>);

impl InputPort {
    /// The `one-of` groups that the input belongs to, in the order the file
    /// marks them.
    pub fn groups(&self) -> &[GroupName] {
        match &self.need {
            Some(Need::OneOf(groups)) => groups,
            Some(Need::Required) | None => &[],
        }
    }

    /// Whether the input holds no row for certain where an instance writes
    /// no clause for it: it has no default rows, and the key does not fill
    /// it, which the key does where the input is marked `from-key` and the
    /// instance's key has a column (`key_has_column`).
    pub fn holds_no_row_unwritten(&self, key_has_column: bool) -> bool {
        self.default.is_none() && !(self.from_key && key_has_column)
    }
}

/// The default rows of an input, as the file writes them, read by
/// [`crate::read::read_param_value`]. It gives its rows as a set, and no
/// position of a row, so no caller can pick one default by its place in the
/// file, and no lib interface makes a free choice.
#[derive(Clone, Debug)]
pub struct DefaultRows {
    written: crate::program::ParamValue,
}

impl DefaultRows {
    /// The default rows, typed by `types`, the types of the input's columns
    /// in order: [`crate::terms::encode_param_value`] of the default's
    /// value, with `table` interning an Ident's values.
    pub fn rows(
        &self,
        types: &[ValueType],
        registry: &Registry,
        table: &mut crate::terms::InternTable,
    ) -> Result<crate::hash::StableHashSet<Box<[crate::terms::TermId]>>, crate::terms::DataValueError> {
        crate::terms::encode_param_value(&self.written, types, registry, table)
    }
}

/// A construction or a detector: its type parameters, its inputs in the
/// order the component declares them, with their defaults, and its outputs.
#[derive(Clone, Debug)]
pub struct Component {
    pub kind: ComponentKind,
    pub type_parameters: Box<[TypeParameter]>,
    /// The inputs in the order the component declares them.
    pub inputs: Box<[InputPort]>,
    pub outputs: Box<[Port]>,
}

impl Component {
    /// Whether an input of the component reads the instance's outputs.
    pub fn reads_outputs(&self) -> bool {
        self.inputs.iter().any(|input| input.reads_outputs)
    }

    /// The ports that are relations of their own at an `INIT` form that
    /// writes the inputs `written`: each output, then each written input
    /// whose name no output shares.
    pub fn relation_ports<'c>(&'c self, written: &'c [&PortName]) -> impl Iterator<Item = &'c Port> + 'c {
        let shares_output = |port: &Port| self.outputs.iter().any(|output| output.name == port.name);
        let inputs = self.inputs.iter().map(|input| &input.port).filter(|port| written.contains(&&port.name));
        self.outputs.iter().chain(inputs.filter(move |port| !shares_output(port)))
    }

    /// The names of the component's `one-of` groups, each once, in the order
    /// of the marks of the inputs.
    pub fn groups(&self) -> Vec<&GroupName> {
        let mut groups: Vec<&GroupName> = Vec::new();
        for group in self.inputs.iter().flat_map(InputPort::groups) {
            if !groups.contains(&group) {
                groups.push(group);
            }
        }
        groups
    }

    /// The position, among the component's inputs, of the last input of
    /// `group`.
    pub fn last_of_group(&self, group: &GroupName) -> Option<usize> {
        self.inputs.iter().rposition(|input| input.groups().contains(group))
    }

    /// Whether, in an instance that writes the inputs `written`, no input of
    /// `group` holds a row for certain: each is unwritten and holds no row
    /// where the instance writes no clause for it
    /// ([`InputPort::holds_no_row_unwritten`]). `key_has_column` is whether
    /// the instance's key has a column.
    pub fn group_is_empty(&self, group: &GroupName, written: &[&PortName], key_has_column: bool) -> bool {
        let members = self.inputs.iter().filter(|input| input.groups().contains(group));
        members.into_iter().all(|input| !written.contains(&&input.port.name) && input.holds_no_row_unwritten(key_has_column))
    }
}

/// A proposer, native or written in arclog, and its columns with their
/// types.
#[derive(Clone, Debug)]
pub struct Proposer {
    pub columns: Box<[Column]>,
    pub kind: ProposerKind,
}

/// The kind of a proposer: native, a type-domain proposer or another, or written
/// in arclog with its clause.
#[derive(Clone, Debug)]
pub enum ProposerKind {
    Native { domain: bool },
    /// A proposer written in arclog and the body of its clause. Its columns
    /// are the labels its `(columns <Label> ...)` form names, in the order
    /// the form gives. Each is a label the clause keeps, and each other
    /// label of the clause is projected away.
    Arclog { body: Node<Body> },
}

/// What a lib name declares.
#[derive(Clone, Debug)]
pub enum LibEntry {
    Relation(AlgebraRelation),
    Component(Component),
    Proposer(Proposer),
    Macro(Macro),
}

/// A lib name that the lib defines from other lib names, with its
/// declaration and its definition. The checks read the declaration. A
/// relation macro's column types and modes are its definition's, as
/// [`macro_column_types`] gives them.
#[derive(Clone, Debug)]
pub enum Macro {
    /// A lib relation: its declaration, its columns, their types and its
    /// modes, the label of the definition that each of its columns stands
    /// for, in the order of the declaration's columns, and its definition.
    Relation {
        relation: AlgebraRelation,
        labels: Box<[crate::program::LabelId]>,
        definition: Node<Body>,
    },
}

/// The constants of one orientation type, as a set: it gives membership
/// and each constant, and no position of a constant, so no caller can pick
/// one constant by its place in the file, and no lib interface makes a free
/// choice.
#[derive(Clone, Debug, Default)]
pub struct ConstantSet {
    constants: crate::hash::StableHashSet<OrientationConstant>,
}

impl ConstantSet {
    /// Whether `constant` is in the set.
    pub fn contains(&self, constant: OrientationConstant) -> bool {
        self.constants.contains(&constant)
    }

    /// Each constant of the set, in an order of encodings and no order of
    /// the content.
    pub fn each(&self) -> impl Iterator<Item = OrientationConstant> + '_ {
        self.constants.iter().copied()
    }
}

/// A fault of the registry file, reported when it is first read.
#[derive(Clone, Debug)]
pub struct RegistryError {
    pub diagnostics: Vec<crate::diagnostic::Diagnostic>,
}

/// The lib registry: the names of the lib, and what each declares.
#[derive(Debug)]
pub struct Registry {
    entries: StableHashMap<LibName, LibEntry>,
    /// The constants of each orientation type.
    constants: StableHashMap<OrientationType, TypeConstants>,
    c4: ConstantSet,
    facts: StableHashMap<crate::program::FactRelation, Box<[Column]>>,
    refines: StableHashMap<Box<str>, Box<[crate::read::SExpr]>>,
}

/// The constants of one orientation type: the name of each, at the index
/// [`OrientationConstant::new`] gives it, and the set of them.
#[derive(Debug)]
struct TypeConstants {
    names: Box<[Box<str>]>,
    set: ConstantSet,
}

impl TypeConstants {
    /// The constant written `name`, where the type has one.
    fn constant(&self, ty: OrientationType, name: &str) -> Option<OrientationConstant> {
        let index = self.names.iter().position(|n| &**n == name)?;
        Some(OrientationConstant::new(ty, index as u8))
    }
}

impl Registry {
    /// The registry of [`REGISTRY_TEXT`], read on first use.
    ///
    /// A fault of the file fails the test `registry_file`, so this panics on
    /// one.
    pub fn get() -> &'static Registry {
        static REGISTRY: std::sync::OnceLock<Registry> = std::sync::OnceLock::new();
        REGISTRY.get_or_init(|| match Registry::parse(REGISTRY_TEXT, PROPOSERS_TEXT) {
            Ok(registry) => registry,
            Err(error) => panic!("the lib files do not parse: {:?}", error.diagnostics),
        })
    }

    /// The registry that `text` declares, with the proposers that
    /// `proposers` writes in arclog, which are read with the entries of
    /// `text`. [`Registry::get`] gives it [`REGISTRY_TEXT`] and
    /// [`PROPOSERS_TEXT`].
    ///
    /// Fails with a diagnostic at the form of each fault of either file.
    pub fn parse(text: &str, proposers: &str) -> Result<Registry, RegistryError> {
        let mut reader = FileReader::default();
        for expr in reader.sexprs(text, SourceFile::LibRegistry) {
            reader.form(&expr);
        }
        let clauses = reader.sexprs(proposers, SourceFile::LibProposers);
        reader.proposer_clauses(&clauses);
        reader.check_reads();
        reader.check_rules();
        reader.declare_macros();
        reader.check_complete();
        reader.registry()
    }

    /// The name of each entry, in an order of encodings and no order of the
    /// content.
    pub fn names(&self) -> impl Iterator<Item = &LibName> + '_ {
        self.entries.keys()
    }

    /// The items of the `refines` form of a lib element: a relation, a fact, or `Component.output`.
    /// The feature encoder reads them, as
    /// `docs/feature-spec/feature-spec.md#size-and-the-encoder` gives, and the
    /// decoder's static prune reads their `(key ...)` items.
    pub fn refines(&self, name: &str) -> &[crate::read::SExpr] {
        self.refines.get(name).map_or(&[], |items| &items[..])
    }

    /// What `name` declares, or `None` where the lib has no such name.
    pub fn entry(&self, name: &LibName) -> Option<&LibEntry> {
        self.entries.get(name)
    }

    /// The declaration of the algebra relation or relation macro `name`, or
    /// `None` where the lib declares neither of that name.
    pub fn algebra_relation(&self, name: &LibName) -> Option<&AlgebraRelation> {
        match self.entry(name)? {
            LibEntry::Relation(relation) | LibEntry::Macro(Macro::Relation { relation, .. }) => Some(relation),
            _ => None,
        }
    }

    /// The orientation constant written `name`, such as `DIR_T`.
    pub fn orientation_constant(&self, name: &str) -> Option<OrientationConstant> {
        self.constants.iter().find_map(|(&ty, constants)| constants.constant(ty, name))
    }

    /// The name of `constant`, for a writer.
    pub fn constant_name(&self, constant: OrientationConstant) -> &str {
        let names = &self.type_constants(constant.ty()).names;
        let index = (0..names.len())
            .find(|&index| OrientationConstant::new(constant.ty(), index as u8) == constant)
            .expect("each orientation constant is one that the registry numbered");
        &names[index]
    }

    /// The constants of `ty`, for a type-domain proposer and for `<ty>_elem`.
    pub fn constants_of(&self, ty: OrientationType) -> &ConstantSet {
        &self.type_constants(ty).set
    }

    /// The D4 constants that are C4, the rotations, as `C4` stands under
    /// `D4`, for `c4_elem`.
    pub fn c4_constants(&self) -> &ConstantSet {
        &self.c4
    }

    /// The columns of `fact`, with their types, which the resolver turns a
    /// read's column names into positions by and the checker types by.
    pub fn fact_columns(&self, fact: crate::program::FactRelation) -> &[Column] {
        match fact {
            FactRelation::Output => self.fact_columns(FactRelation::Input),
            FactRelation::Program(program) => {
                let held = feature_fact_columns();
                &held.iter().find(|(own, _)| *own == Some(program)).expect("the columns of each program relation").1
            }
            FactRelation::Name(_) => &feature_fact_columns().iter().find(|(own, _)| own.is_none()).expect("the column of a lib name constant").1,
            FactRelation::Stored(name) => stored_tables().read().expect("a table that no panic poisoned").get(&name).expect("a stored table is declared before a form reads it").0,
            _ => self.facts.get(&fact).expect("`parse` fails on a fact relation with no `fact` form"),
        }
    }

    fn type_constants(&self, ty: OrientationType) -> &TypeConstants {
        self.constants.get(&ty).expect("`parse` fails on an orientation type with no `constants` form")
    }
}

/// The declared stored tables, each with its columns and whether it has rows
/// on each example.
fn stored_tables() -> &'static std::sync::RwLock<crate::hash::StableHashMap<crate::terms::LibNameId, (&'static [Column], bool)>> {
    static TABLES: std::sync::OnceLock<std::sync::RwLock<crate::hash::StableHashMap<crate::terms::LibNameId, (&'static [Column], bool)>>> = std::sync::OnceLock::new();
    TABLES.get_or_init(Default::default)
}

/// Declares the stored table `name`, with `columns`. A session holds its rows
/// on each example where `per_input` holds, and otherwise once for the task. A
/// table declared again under one name keeps its first declaration, so a
/// caller gives a name of its own to each set of columns.
pub fn declare_stored_table(name: crate::terms::LibNameId, columns: &[(String, ValueType)], per_input: bool) {
    let mut tables = stored_tables().write().expect("a table that no panic poisoned");
    tables.entry(name).or_insert_with(|| {
        let columns: Box<[Column]> = columns.iter().map(|(column, ty)| Column { name: ColumnName::Written(column.as_str().into()), ty: ColumnType::Fixed(ty.clone()) }).collect();
        (Box::leak(columns), per_input)
    });
}

/// Whether the stored table `name` has rows on each example.
pub fn stored_table_per_input(name: crate::terms::LibNameId) -> bool {
    stored_tables().read().expect("a table that no panic poisoned").get(&name).is_some_and(|(_, per_input)| *per_input)
}

/// The columns of each program relation, and, with no relation, the column of
/// a lib name constant. Each holds a lib name.
fn feature_fact_columns() -> &'static [(Option<crate::program::ProgramFact>, Box<[Column]>)] {
    static COLUMNS: std::sync::OnceLock<Vec<(Option<crate::program::ProgramFact>, Box<[Column]>)>> = std::sync::OnceLock::new();
    COLUMNS.get_or_init(|| {
        let of = |names: &[&str]| -> Box<[Column]> {
            names.iter().map(|name| Column { name: ColumnName::Written((*name).into()), ty: ColumnType::Fixed(ValueType::LibName) }).collect()
        };
        let program = crate::program::ProgramFact::ALL.into_iter().map(|fact| (Some(fact), of(fact.columns())));
        program.chain(std::iter::once((None, of(&["Name"])))).collect()
    })
}

mod bindings;
mod column_types;
mod forms;
mod frames;
mod macro_declarations;
mod macro_forms;
mod proposer_clauses;
mod reader;
mod reads;
mod records;
mod spellings;
mod type_rules;
mod rule_forms;

pub(crate) use bindings::{binding_sites, unbound, ParameterSite};
pub use bindings::key_fill;
pub use column_types::{macro_column_types, LabelColumn, MacroDeclarations, RelationMacro};
pub use frames::{has_frame, FrameColumn, FrameRule, FrameSize};
pub use type_rules::{ruled_type, TypeRule};
use type_rules::rule_diagnostics;
use reader::FileReader;
