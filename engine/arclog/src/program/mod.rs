//! Programs as values: the node kinds of an arclog file and of an arcdata
//! file, each an immutable value that holds its canonical hash.
//!
//! Implements `work/engine/reader.md`, Programs as values: "A program, a
//! clause, a body and an atom are immutable values." and "The reader, the
//! decoder and any search procedure build programs through these values and
//! edits. Evaluation takes a program value, not a file."
//!
//! A node holds its lists in source order, and its canonical hash leaves
//! that order out. A node holds no name of a label and no place in a file:
//! those stand beside it, in a [`crate::layout::Layout`]. A label is a
//! [`LabelId`] local to its clause, so a renaming of labels gives an equal
//! value.
//!
//! The node kinds follow the forms of `docs/arclog.md` and `docs/arcdata.md`.
//! The programs-as-values stage writes the bodies of this module and of its
//! submodules.

#![allow(unused_variables, dead_code)]

pub mod canonical;
pub mod edit;
pub mod path;

use std::sync::Arc;

use crate::hash::StableHash;

/// A node value and the hash of its canonical form.
///
/// Two nodes whose hashes match are compared by canonical form, as Programs
/// as values gives. Cloning a `Node` shares the value.
///
/// Implements `work/engine/reader.md`, Programs as values: "Each syntax node holds a hash of its canonical form, and two nodes whose hashes match are compared by canonical form."
#[derive(Debug)]
pub struct Node<T> {
    value: Arc<T>,
    canonical_hash: StableHash,
}

impl<T> Clone for Node<T> {
    fn clone(&self) -> Self {
        todo!()
    }
}

impl<T: canonical::Canonical> Node<T> {
    /// The node of `value`, with its canonical hash computed once.
    ///
    /// Implements `work/engine/reader.md`, Programs as values: "Each syntax node holds a hash of its canonical form".
    pub fn new(value: T) -> Self {
        todo!()
    }
}

impl<T> Node<T> {
    /// The value.
    ///
    /// Implements `work/engine/reader.md`, Programs as values: "A program, a clause, a body and an atom are immutable values."
    pub fn value(&self) -> &T {
        todo!()
    }

    /// The hash of the value's canonical form, as [`canonical`] gives it.
    ///
    /// Implements `work/engine/reader.md`, Programs as values: "Each syntax node holds a hash of its canonical form".
    pub fn canonical_hash(&self) -> StableHash {
        todo!()
    }
}

impl<T: canonical::Canonical> PartialEq for Node<T> {
    /// Equality of canonical forms: equal hashes, then equal canonical forms.
    fn eq(&self, other: &Self) -> bool {
        todo!()
    }
}

impl<T: canonical::Canonical> Eq for Node<T> {}

/// A derived relation's, a chosen relation's or a demonstrated relation's
/// name as the file writes it, with its `&`: `&fg`, `&ties`, `&catalog`.
///
/// Implements `docs/arclog.md`, Names.
#[derive(Clone, PartialEq, Eq, Hash, Debug)]
pub struct RelationName(pub Box<str>);

/// An instance's name as the file writes it, with its `&`: `&comps`.
///
/// Implements `docs/arclog.md`, Names.
#[derive(Clone, PartialEq, Eq, Hash, Debug)]
pub struct InstanceName(pub Box<str>);

/// A column's name, without its leading colon: `P`, `Col1` for a column of a
/// fixed type, `key`, `t`, `item` for a column of a type parameter.
///
/// Implements `docs/arclog.md`, Names.
#[derive(Clone, PartialEq, Eq, Hash, Debug)]
pub struct ColumnName(pub Box<str>);

/// The name of an instance's input or output, as the component declares it:
/// `node`, `source`, `component`.
///
/// Implements `docs/arclog.md`, Names.
#[derive(Clone, PartialEq, Eq, Hash, Debug)]
pub struct PortName(pub Box<str>);

/// An `ALTS` form's or an alt's name, as the file writes it: `$locate`,
/// `$Box`, `&background=$Derived`.
///
/// Implements `docs/arclog.md`, Names.
#[derive(Clone, PartialEq, Eq, Hash, Debug)]
pub struct AltsName(pub Box<str>);

/// A claim's slug: `container`, `fill-interior`.
///
/// Implements `docs/arclog.md`, Names.
#[derive(Clone, PartialEq, Eq, Hash, Debug)]
pub struct Slug(pub Box<str>);

/// A quoted string of a file: a claim's text, a gloss, a reason.
///
/// Implements `docs/arclog.md`, Names.
#[derive(Clone, PartialEq, Eq, Hash, Debug)]
pub struct Text(pub Box<str>);

/// A label, local to its clause. Its name stands in the
/// [`crate::layout::Layout`], so a renaming of labels leaves the value equal,
/// as "a renaming of its labels" gives.
///
/// Implements `work/engine/reader.md`, Programs as values: "a renaming of its labels".
#[derive(Clone, Copy, PartialEq, Eq, Hash, Debug)]
pub struct LabelId(pub u32);

/// A whole arclog file, or a synthesized program: its forms.
///
/// Implements `docs/arclog.md`, Program: "`INPUT` and `OUTPUT` blocks in
/// dependency order, then `ALTS` forms, then the tail."
#[derive(Clone, Debug)]
pub struct Program {
    pub forms: Arc<[Form]>,
}

/// A top-level form, or a form inside a claim, an `ALT` or a `DEMO_RULE`.
///
/// Implements `docs/arclog.md`, Program.
#[derive(Clone, Debug)]
pub enum Form {
    Claim(Node<Claim>),
    Clause(Node<Clause>),
    Instance(Node<Instance>),
    Choose(Node<Choose>),
    RigidDet(Node<RigidDet>),
    Demonstrated(Node<Demonstrated>),
    Alts(Node<Alts>),
}

/// Whether a claim is about the input or the output.
///
/// Implements `docs/arclog.md`, Program.
#[derive(Clone, Copy, PartialEq, Eq, Hash, Debug)]
pub enum ClaimKind {
    Input,
    Output,
}

/// An `INPUT` or `OUTPUT` block: a claim, its slug, its text, then the forms
/// that serve it, as `docs/arclog.md`, Program, gives.
#[derive(Clone, Debug)]
pub struct Claim {
    pub kind: ClaimKind,
    pub slug: Slug,
    pub text: Text,
    /// The `APPROXIMATED` form's rule, where the program runs an
    /// approximation in place of the output claim.
    pub approximated: Option<Text>,
    pub forms: Arc<[Form]>,
}

/// The keyword of a clause form, as `docs/arclog.md`, Program, gives.
#[derive(Clone, Copy, PartialEq, Eq, Hash, Debug)]
pub enum ClauseKeyword {
    /// `RULE`: a program clause, per input.
    Rule,
    /// `DET`: a determination clause, task-wide.
    Det,
    /// `DET_OR_RULE`: an `ALTS` form on the relation, the stored reading
    /// first, as `docs/arclog.md`, The `ALTS` form, gives.
    DetOrRule,
    /// `RULE_OR_DET`: an `ALTS` form on the relation, the derived reading
    /// first.
    RuleOrDet,
}

/// The relation a clause form derives: a relation of its own, or, on a
/// `RULE_OR_DET` line, an output of an instance, as in `&ring.value`.
///
/// Implements `docs/arclog.md`, The `ALTS` form: "A `RULE_OR_DET` line on an output of an instance names the output as the program reads it".
#[derive(Clone, PartialEq, Eq, Hash, Debug)]
pub enum DerivedName {
    Relation(RelationName),
    Output(OutputName),
}

/// An output of an instance, `&comps.component`, or a part of a `RIGID_DET`
/// form, `&marker.glyph`, `&marker.bbox.box`: the instance, then the path of
/// names after it.
///
/// Implements `docs/arclog.md`, Instance: "The instance's outputs are read as `<name>.<output>`", and `docs/rigid.md`, Form.
#[derive(Clone, PartialEq, Eq, Hash, Debug)]
pub struct OutputName {
    pub instance: InstanceName,
    pub path: Arc<[PortName]>,
}

/// A clause form: its keyword, the relation's name, its proposers, its body
/// and its `ONE` marks.
///
/// Implements `docs/arclog.md`, Program. A clause with no body is a
/// fact, as `(RULE &live)`. A `DET` that names a proposer has the proposer in
/// `proposers`, and a `DET_OR_RULE` or `RULE_OR_DET` line holds its
/// proposers, then the body of the reading that has clauses of its own.
#[derive(Clone, Debug)]
pub struct Clause {
    pub keyword: ClauseKeyword,
    pub derives: DerivedName,
    pub gloss: Option<Text>,
    pub proposers: Arc<[crate::registry::LibName]>,
    pub body: Node<Body>,
    pub ones: Arc<[OneMark]>,
}

/// A `ONE` mark: the key columns of the clause's relation for each value of
/// which a model keeps one row, as `docs/constraints.md`, One, gives. A mark
/// with no label, `(ONE)`, keeps one row of the whole relation.
#[derive(Clone, PartialEq, Eq, Hash, Debug)]
pub struct OneMark {
    pub key: Arc<[LabelId]>,
}

/// A body: a sequence of conjuncts, in source order.
///
/// Implements `docs/arclog.md`, Clause. The canonical form takes the
/// conjuncts under reorder, so their order is outside the hash.
#[derive(Clone, Debug)]
pub struct Body {
    pub conjuncts: Arc<[Conjunct]>,
}

/// One conjunct of a body: an atom, a negated atom, a constraint, or an
/// `OR`, `IF` or `ALL` form.
///
/// Implements `docs/arclog.md`, Clause.
#[derive(Clone, Debug)]
pub enum Conjunct {
    Atom(Node<Atom>),
    /// `NOT` before an atom: every site of the atom joins.
    Not(Node<Atom>),
    Constraint(Constraint),
    /// An `OR` form: its branches, as `docs/arclog.md`, Disjunction, gives.
    Or(Arc<[Node<Body>]>),
    /// An `IF` form: the test, the then and the else, as
    /// `docs/arclog.md`, Conditional, gives.
    If {
        test: Node<Body>,
        then: Node<Body>,
        otherwise: Node<Body>,
    },
    /// An `ALL` form: the domain, then what each member must satisfy, as
    /// `docs/arclog.md`, Universal, gives.
    All {
        domain: Node<Body>,
        body: Node<Body>,
    },
}

/// A constraint operator, as `docs/arclog.md`, Negation and constraints,
/// gives.
#[derive(Clone, Copy, PartialEq, Eq, Hash, Debug)]
pub enum ConstraintOp {
    Eq,
    Ne,
    Lt,
    Le,
    Gt,
    Ge,
}

/// The second operand of a constraint: a label, or the reserved label `0`.
///
/// Implements `docs/arclog.md`, Negation and constraints: "`0` is a reserved label usable as the second label of a constraint."
#[derive(Clone, Copy, PartialEq, Eq, Hash, Debug)]
pub enum Operand {
    Label(LabelId),
    Zero,
}

/// A constraint over two labels. `fresh` holds where `=` makes its first
/// label, `(= *X Y)`.
///
/// Implements `docs/arclog.md`, Negation and constraints.
#[derive(Clone, Copy, PartialEq, Eq, Hash, Debug)]
pub struct Constraint {
    pub op: ConstraintOp,
    pub first: LabelId,
    pub fresh: bool,
    pub second: Operand,
}

/// The relation an atom reads.
///
/// Implements `docs/arclog.md`, Clause: "An atom is a list whose head is a relation".
#[derive(Clone, PartialEq, Eq, Hash, Debug)]
pub enum RelationRef {
    /// `input`, `ex_input` or `ex_output`.
    Fact(FactRelation),
    /// A lib relation, or a proposer.
    Lib(crate::registry::LibName),
    /// A relation the program declares: a clause's, a chosen relation, a
    /// demonstrated relation.
    Derived(RelationName),
    Output(OutputName),
}

/// The fact relations, as `docs/arclog.md`, Program, gives.
#[derive(Clone, Copy, PartialEq, Eq, Hash, Debug)]
pub enum FactRelation {
    Input,
    ExInput,
    ExOutput,
}

/// An atom: a relation and its sites.
///
/// Implements `docs/arclog.md`, Clause.
#[derive(Clone, Debug)]
pub struct Atom {
    pub relation: RelationRef,
    pub sites: Arc<[Site]>,
}

/// A site: one column of the atom's relation and what stands at it, as
/// `docs/arclog.md`, Sites, gives. An elided site, `*P`, is the same value as
/// `(:P *P)`; the layout records the elision.
#[derive(Clone, PartialEq, Eq, Hash, Debug)]
pub struct Site {
    pub column: ColumnName,
    pub value: SiteValue,
}

/// What stands at a site.
///
/// Implements `docs/arclog.md`, Sites.
#[derive(Clone, PartialEq, Eq, Hash, Debug)]
pub enum SiteValue {
    /// One label or more, on a column of a fixed type or of a type parameter
    /// bound to one label's type, or on a key of several labels.
    Labels(Arc<[LabelUse]>),
    /// A site on each field of a record that the site reads.
    Fields(Arc<[Site]>),
}

/// One label at a site, with its mark.
///
/// Implements `docs/arclog.md`, Sites, and Instance for `^`.
#[derive(Clone, Copy, PartialEq, Eq, Hash, Debug)]
pub enum LabelUse {
    /// `*X`: the site introduces the variable.
    Fresh(LabelId),
    /// `X`: the site joins an existing variable.
    Join(LabelId),
    /// `^X`: a column of a key clause.
    Key(LabelId),
    /// `0`: the site joins the column to zero.
    Zero,
}

/// An `INIT` form: an instance of a lib component, as `docs/arclog.md`,
/// Instance, gives.
#[derive(Clone, Debug)]
pub struct Instance {
    pub name: InstanceName,
    pub component: crate::registry::LibName,
    pub key: Option<Node<KeyClause>>,
    /// The inputs that hold for every key, after the key clause.
    pub inputs: Arc<[Node<Input>]>,
}

/// A key clause, `(key (<body>) <inputs>)`: its body, whose `^` labels are
/// the key's columns in order of appearance, and the keyed inputs.
///
/// Implements `docs/arclog.md`, Instance.
#[derive(Clone, Debug)]
pub struct KeyClause {
    pub body: Node<Body>,
    pub inputs: Arc<[Node<Input>]>,
}

/// An input of an instance: its name, its head sites, its body.
///
/// Implements `docs/arclog.md`, Instance.
#[derive(Clone, Debug)]
pub struct Input {
    pub name: PortName,
    pub head: Arc<[Site]>,
    pub body: Node<Body>,
}

/// A `CHOOSE` form, as `docs/constraints.md`, Choose, gives.
#[derive(Clone, Debug)]
pub struct Choose {
    pub name: RelationName,
    /// The `for` clause, a key clause whose `^` labels are the row's columns.
    pub rows: Option<Node<Body>>,
    /// The `from` clause: inside `for` where it reads the row's labels.
    pub from: Node<Body>,
    pub from_inside_for: bool,
    pub never: Arc<[Node<Body>]>,
}

/// A `RIGID_DET` form, as `docs/rigid.md`, Form, gives.
#[derive(Clone, Debug)]
pub struct RigidDet {
    pub name: InstanceName,
    /// The `key` clause's body: each key row is an independent assembly.
    pub key: Option<Node<Body>>,
    /// The `instance` clause's body: one of its rows is one instance.
    pub instance: Option<Node<Body>>,
    /// The parts: each atom of the form, inside the `instance` clause where
    /// the form has one.
    pub parts: Arc<[Node<Atom>]>,
}

/// A `DEMONSTRATED` form, as `docs/arclog.md`, Demonstrated, gives.
#[derive(Clone, Debug)]
pub struct Demonstrated {
    pub name: RelationName,
    pub key: Option<Node<Body>>,
    /// The `value` and `demonstration` inputs.
    pub inputs: Arc<[Node<Input>]>,
    pub rules: Arc<[Node<DemoRule>]>,
}

/// A `DEMO_RULE` form: its name, its fields, its text, and its clauses.
///
/// Implements `docs/arclog.md`, Demonstrated.
#[derive(Clone, Debug)]
pub struct DemoRule {
    pub name: AltsName,
    pub fields: Arc<[LabelId]>,
    pub text: Option<Text>,
    pub forms: Arc<[Form]>,
}

/// An `ALTS` form, as `docs/arclog.md`, The `ALTS` form, gives: its name, its gloss,
/// the concept case's name, then an `ALT` block per alt.
#[derive(Clone, Debug)]
pub struct Alts {
    pub name: AltsName,
    pub gloss: Text,
    pub concept: AltsName,
    pub alts: Arc<[Node<Alt>]>,
}

/// An `ALT` block: the claims the alt reads differently or adds, the tail
/// forms it rederives, its nested `ALT` blocks for combinations, and an
/// `ALTS` form that exists only under this branch.
///
/// Implements `docs/arclog.md`, The `ALTS` form.
#[derive(Clone, Debug)]
pub struct Alt {
    pub name: AltsName,
    pub forms: Arc<[Form]>,
}

/// A whole arcdata file, its forms in the order `docs/arcdata.md` gives.
#[derive(Clone, Debug)]
pub struct Arcdata {
    pub representative: Option<Representative>,
    pub params: Arc<[Node<Param>]>,
    pub excludes: Arc<[Exclude]>,
    pub records: Arc<[Record]>,
}

/// `(representative <task_id> [<name>])`, as `docs/arcdata.md`, Header,
/// gives.
#[derive(Clone, Debug)]
pub struct Representative {
    pub task_id: Box<str>,
    pub case: Option<AltsName>,
}

/// A `param` form: the parameter, its column types and its rows.
///
/// Implements `docs/arcdata.md`, Params.
#[derive(Clone, Debug)]
pub struct Param {
    pub name: RelationName,
    pub columns: Arc<[crate::types::ValueType]>,
    pub value: ParamValue,
}

/// The rows of a `param` form or an `assign` form, as `docs/arcdata.md`,
/// Params, gives.
#[derive(Clone, Debug)]
pub enum ParamValue {
    /// Rows written as lists of values.
    Rows(Arc<[Arc<[DataValue]>]>),
    /// Values before a grid, then the grid of a Position column.
    Grid {
        before: Arc<[DataValue]>,
        grid: Grid,
    },
    /// The values a table derives from, under the derivation's name: `Frame`
    /// or `Division`.
    Derivation {
        derivation: crate::registry::LibName,
        rows: Arc<[Arc<[Site]>]>,
    },
}

/// A value written in an arcdata file.
///
/// Implements `docs/arcdata.md`, Params.
#[derive(Clone, PartialEq, Eq, Hash, Debug)]
pub enum DataValue {
    Number(i32),
    /// A Color, written as its digit.
    Color(crate::terms::Color),
    /// An orientation constant, written by its name in the registry.
    Orientation(crate::terms::OrientationConstant),
    Ident(u32),
    /// A value written as a list, read into one column per member, as
    /// `work/engine/reader.md`, Terms, gives.
    List(Arc<[DataValue]>),
}

/// A grid of an arcdata file: one row per line, a cell `_` gives no row.
///
/// Implements `docs/arcdata.md`, Params.
#[derive(Clone, Debug)]
pub struct Grid {
    pub rows: Arc<[Arc<[Option<DataValue>]>]>,
}

/// An `exclude` form: the combination it leaves out, and its reason.
///
/// Implements `docs/arcdata.md`, Alts.
#[derive(Clone, Debug)]
pub struct Exclude {
    pub combination: Arc<[AltsName]>,
    pub reason: Text,
}

/// An `alts` form or an `approximated` form, with its witnesses.
///
/// Implements `docs/arcdata.md`, Alts.
#[derive(Clone, Debug)]
pub enum Record {
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
///
/// Implements `docs/arcdata.md`, Alts.
#[derive(Clone, Debug)]
pub struct AltRecord {
    pub name: AltsName,
    pub witnesses: Arc<[Witness]>,
    pub nested: Arc<[AltRecord]>,
}

/// A `witness` form, as `docs/arcdata.md`, Witnesses, gives. A witness with
/// no body refers to the witness of that id given in full under an earlier
/// alt.
#[derive(Clone, Debug)]
pub struct Witness {
    pub id: Box<str>,
    pub plausibility: Plausibility,
    pub verdict: Verdict,
    pub body: Option<WitnessBody>,
}

/// A witness's plausibility.
///
/// Implements `docs/arcdata.md`, Witnesses.
#[derive(Clone, Copy, PartialEq, Eq, Hash, Debug)]
pub enum Plausibility {
    Ordinary,
    Variant,
    Borderline,
    Foreign,
}

/// A witness's verdict.
///
/// Implements `docs/arcdata.md`, Witnesses.
#[derive(Clone, PartialEq, Eq, Hash, Debug)]
pub enum Verdict {
    Concept,
    Alt(AltsName),
    Any,
    Other,
}

/// The body of a witness given in full.
///
/// Implements `docs/arcdata.md`, Witnesses.
#[derive(Clone, Debug)]
pub struct WitnessBody {
    pub relaxed: Arc<[Slug]>,
    pub separates: Text,
    pub assigns: Arc<[(RelationName, ParamValue)]>,
    pub input: Grid,
    pub outputs: Arc<[WitnessOutput]>,
}

/// An `output` form of a witness.
///
/// Implements `docs/arcdata.md`, Witnesses.
#[derive(Clone, Debug)]
pub struct WitnessOutput {
    /// The names whose cases together give the output; empty for the one
    /// output of a witness with the verdict `other`. A name that fixes
    /// several alts is a list.
    pub names: Arc<[Arc<[AltsName]>]>,
    pub value: OutputValue,
}

/// The output of an `output` form.
///
/// Implements `docs/arcdata.md`, Witnesses.
#[derive(Clone, Debug)]
pub enum OutputValue {
    Undefined,
    /// One grid per model.
    Grids(Arc<[Grid]>),
}
