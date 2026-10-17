//! Programs as values: the node kinds of an arclog file and of an arcdata
//! file, each an immutable value that holds its canonical hash.
//!
//! Implements `work/engine/reader.md`, Programs as values: "A program, a
//! clause, a body and an atom are immutable values." and "The reader, the
//! decoder and any search procedure build programs through these values and
//! edits. Evaluation takes a program value, not a file."
//!
//! A node holds its lists in source order. Its canonical hash leaves out
//! the order of the atoms of a body and of the branches of an `OR`, and
//! keeps the order of every other list, such as a parameter's columns, a
//! row's values or an output's path. A node holds no name of a label and no place in a file:
//! those stand beside it, in a [`crate::layout::Layout`]. The one exception
//! is the name of a column that a label gives a relation the program
//! declares, [`RelationColumn`], since a read names the column by it, as
//! `docs/arclog.md`, Sites, gives; the resolved content writes its position. A label is a
//! [`LabelId`] local to its scope, as [`LabelId`] gives, so a renaming of
//! labels gives an equal value.
//!
//! The node kinds follow the forms of `docs/arclog.md` and `docs/arcdata.md`.
//! The programs-as-values stage writes the bodies of this module and of its
//! submodules.

#![allow(unused_variables, dead_code)]

pub mod canonical;
pub mod edit;
pub mod path;

use std::sync::{Arc, OnceLock};

use crate::hash::StableHash;

/// A node value and the hash of its canonical form.
///
/// Two nodes whose hashes match are compared by canonical form, as Programs
/// as values gives. Cloning a `Node` shares the value and its hash. The hash
/// is computed on its first use, so that a reader or a decode that builds a
/// tree pays for no hash it does not read.
///
/// A node's equality is that of its canonical form, in which each name it
/// reads stands as the file writes it. The equality of resolved content,
/// "whatever file or decode they came from", is that of
/// [`crate::resolver::ResolvedContent`].
///
/// Implements `work/engine/reader.md`, Programs as values: "Each syntax node holds a hash of its canonical form, and two nodes whose hashes match are compared by canonical form."
#[derive(Debug)]
pub struct Node<T> {
    shared: Arc<Shared<T>>,
}

#[derive(Debug)]
struct Shared<T> {
    value: T,
    canonical_hash: OnceLock<(StableHash, bool)>,
}

impl<T> Clone for Node<T> {
    fn clone(&self) -> Self {
        todo!()
    }
}

impl<T: canonical::Canonical> Node<T> {
    /// The node of `value`.
    ///
    /// Implements `work/engine/reader.md`, Programs as values: "A program, a clause, a body and an atom are immutable values."
    pub fn new(value: T) -> Self {
        Node { shared: Arc::new(Shared { value, canonical_hash: OnceLock::new() }) }
    }

    /// Whether the search for the value's canonical form reached
    /// [`canonical::SEARCH_NODE_CAP`], an alert that the caller reports with
    /// the node, as Bounds gives.
    ///
    /// Implements `work/engine/reader.md`, How each decision can fail: "the cap reached is an alert".
    pub fn reached_search_cap(&self) -> bool {
        todo!()
    }

    /// The hash of the value's canonical form, as [`canonical`] gives it.
    ///
    /// Implements `work/engine/reader.md`, Programs as values: "Each syntax node holds a hash of its canonical form".
    pub fn canonical_hash(&self) -> StableHash {
        todo!()
    }
}

impl<T> Node<T> {
    /// The value.
    ///
    /// Implements `work/engine/reader.md`, Programs as values: "A program, a clause, a body and an atom are immutable values."
    pub fn value(&self) -> &T {
        &self.shared.value
    }
}

impl<T: canonical::Canonical> PartialEq for Node<T> {
    /// Equality of canonical forms: equal hashes, then equal canonical forms.
    fn eq(&self, other: &Self) -> bool {
        todo!()
    }
}

impl<T: canonical::Canonical> Eq for Node<T> {}

/// A name the program declares: as a file writes it, with its `&`, or, in a
/// decoded program, the slot the engine assigned at the declaration, which
/// the writer writes by its index.
///
/// Implements `docs/arclog.md`, Names: "A derived relation's name, an instance's name and a label are the renderer's ... the stream holds ids", and `work/engine/reader.md`, Solvers: "a relation slot is written by its index, since no token of a decode states what the relation means".
#[derive(Clone, PartialEq, Eq, Hash, Debug)]
pub enum DeclaredName {
    Written(Box<str>),
    Slot(u32),
}

/// The scope of a declared name: the program, or one `DEMO_RULE` form, by
/// its path. Each demonstrated rule declares its own `&prediction` and the
/// relations and instances it needs, so a name that a `DEMO_RULE` form
/// declares stands for its declaration within that form alone.
///
/// Implements `docs/arclog.md`, Demonstrated: "Each `DEMO_RULE` is a demonstrated rule: its name, ..., then the clauses that read what the rule needs from the input, and it derives `&prediction`".
#[derive(Clone, PartialEq, Eq, Hash, Debug)]
pub enum NameScope {
    Program,
    DemoRule(path::NodePath),
}

/// A derived relation's, a chosen relation's or a demonstrated relation's
/// name: `&fg`, `&ties`, `&catalog`.
///
/// Implements `docs/arclog.md`, Names.
#[derive(Clone, PartialEq, Eq, Hash, Debug)]
pub struct RelationName(pub DeclaredName);

/// An instance's name, the name of an `INIT` form: `&comps`.
///
/// Implements `docs/arclog.md`, Names.
#[derive(Clone, PartialEq, Eq, Hash, Debug)]
pub struct InstanceName(pub DeclaredName);

/// A `RIGID_DET` form's name: `&marker`.
///
/// Implements `docs/rigid.md`, Form, and `docs/arclog.md`, Names.
#[derive(Clone, PartialEq, Eq, Hash, Debug)]
pub struct RigidDetName(pub DeclaredName);

/// A column's name, without its leading colon: `P`, `Col1` for a column of a
/// fixed type, `key`, `t`, `item` for a column of a type parameter. In a
/// decoded program, a column of a relation the program declares is the slot
/// of its label among the relation's columns, since the stream holds ids.
///
/// Implements `docs/arclog.md`, Names, and Token stream: "column tokens: a relation's columns, which for a derived relation are the labels of its clause".
#[derive(Clone, PartialEq, Eq, Hash, Debug)]
pub enum ColumnName {
    Written(Box<str>),
    Slot(u32),
}

/// A column of a relation the program declares, which a label of its form
/// gives: the column's name, the label's name as the file writes it, and
/// the label. The names of the columns are the relation's interface, which a
/// read names and the resolver turns into positions; the label's other
/// names stay in the layout.
///
/// Implements `docs/arclog.md`, Sites: "A derived relation's columns are the labels of its clause, as written", and `work/engine/reader.md`, Programs as values: "the resolver turns each column name that a read gives into its position".
#[derive(Clone, PartialEq, Eq, Hash, Debug)]
pub struct RelationColumn {
    pub name: ColumnName,
    pub label: LabelId,
}

/// A key's body and its columns: the `^` labels of the body, in order of
/// appearance, each a column of the key.
///
/// Implements `docs/arclog.md`, Instance: "A label marked `^` in its body is a column of the key, and the key's columns are those labels in order of appearance".
#[derive(Clone, Debug)]
pub struct KeyBody {
    pub body: Node<Body>,
    pub columns: Arc<[RelationColumn]>,
}

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

/// A demonstrated rule's name, as its `DEMO_RULE` form writes it: `$Extend`,
/// `$Move`.
///
/// Implements `docs/arclog.md`, Names: "a demonstrated rule's name".
#[derive(Clone, PartialEq, Eq, Hash, Debug)]
pub struct DemoRuleName(pub Box<str>);

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

/// A label, local to its scope. A scope is a form that stands in a program,
/// a claim or an `ALT`, apart from a `DEMONSTRATED` form, whose key clause
/// and inputs are one scope and each of whose `DEMO_RULE` forms, with its
/// fields and its forms, is one scope. A label that one site of the scope
/// makes is the same id at each site of the scope that joins it: an
/// `INIT`'s key labels in its keyed inputs, a `RIGID_DET` key's labels in
/// its instance clause and parts, and a `DEMO_RULE`'s field labels in its
/// clauses. A label written fresh at two sites of one scope, as a key body's
/// local label and an input's, is two variables with two ids. Its name
/// stands in the
/// [`crate::layout::Layout`], so a renaming of labels leaves the value equal,
/// as "a renaming of its labels" gives.
///
/// Implements `work/engine/reader.md`, Programs as values: "a renaming of its labels".
#[derive(Clone, Copy, PartialEq, Eq, Hash, Debug)]
pub struct LabelId(pub u32);

/// A whole arclog file, or a synthesized program: its forms. A program is
/// held as a `Node<Program>`, so it has a canonical hash and an equality as
/// each other node has.
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

/// A relation the program declares, as a clause form derives it or an
/// arcdata form stores it: a derived, chosen or demonstrated relation, or an
/// instance relation, as `&ring.value` on a `RULE_OR_DET` line, or an output
/// of a `RIGID_DET` form, as `&piece.member` in a `param` form.
///
/// Implements `docs/arclog.md`, The `ALTS` form: "A `RULE_OR_DET` line on an output of an instance names the output as the program reads it", and `docs/arcdata.md`: "A name is one the arclog file declares, in that file's spelling".
#[derive(Clone, PartialEq, Eq, Hash, Debug)]
pub enum ProgramRelation {
    Declared(RelationName),
    Output(OutputName),
}

/// An instance relation, `&comps.component`, or an output of a `RIGID_DET`
/// form, `&marker.glyph`, `&marker.bbox.box`, `&marker.pose`: the form,
/// then the path of names after it.
///
/// Implements `docs/arclog.md`, Instance: "The instance's outputs are read as `<name>.<output>`", and `docs/rigid.md`, Form.
#[derive(Clone, PartialEq, Eq, Hash, Debug)]
pub struct OutputName {
    pub of: OutputOwner,
    pub path: Arc<[OutputStep]>,
}

/// One step of the path of an [`OutputName`] after its form.
///
/// Implements `docs/rigid.md`, Form: "The program reads the part under the atom's relation name in the form's path: `&marker.glyph`, or `&marker.bbox.box` for a part that reads `&bbox.box`", and Semantics: "`&marker.pose`".
#[derive(Clone, PartialEq, Eq, Hash, Debug)]
pub enum OutputStep {
    /// An output of an instance, as its component declares it: `component`
    /// of `&comps.component`, `box` of `&marker.bbox.box`.
    Port(PortName),
    /// The relation or instance that a part of a `RIGID_DET` form reads, by
    /// its declared name as [`DeclaredName`] holds it, with its `&`, or its
    /// slot in a decode: `&glyph` for `&marker.glyph`, and `&bbox` for
    /// `&marker.bbox.box`. The file writes the step without its `&`.
    Part(DeclaredName),
    /// `pose` of `&marker.pose`.
    Pose,
}

/// The form whose outputs an [`OutputName`] reads.
///
/// Implements `docs/arclog.md`, Instance, and `docs/rigid.md`, Semantics: "The form has two kinds of output".
#[derive(Clone, PartialEq, Eq, Hash, Debug)]
pub enum OutputOwner {
    Instance(InstanceName),
    RigidDet(RigidDetName),
}

/// A clause form: its keyword, the relation's name, its proposers, its body
/// and its `ONE` marks.
///
/// Implements `docs/arclog.md`, Program. A clause with nothing after its
/// name is a fact, as `(RULE &live)`. A `DET` that names a proposer, or a
/// derivation in place of a proposer, as `(DET &frame Frame)`, has that
/// name in `proposers`, and a `DET_OR_RULE` or `RULE_OR_DET` line holds its
/// proposers, then the body of the reading that has clauses of its own.
#[derive(Clone, Debug)]
pub struct Clause {
    pub keyword: ClauseKeyword,
    pub derives: ProgramRelation,
    pub gloss: Option<Text>,
    pub proposers: Arc<[crate::registry::LibName]>,
    pub body: Node<Body>,
    pub ones: Arc<[OneMark]>,
    /// The relation's columns, in the order the clause gives them, which
    /// the resolved content replaces by the canonical positions of their
    /// labels: the labels the clause keeps, or the
    /// labels an `OR` that is the whole body exports. A `DET` with a proposer
    /// and no body takes the proposer's columns, which the registry gives,
    /// and holds none here.
    pub columns: Arc<[RelationColumn]>,
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
    /// `NOT` before an atom, where every site of the atom joins, or before a
    /// form, a second spelling that the lint never refuses, as
    /// `docs/arclog.md`, Second spellings, gives.
    Not(Negated),
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

/// What a `NOT` negates.
///
/// Implements `docs/arclog.md`, Negation and constraints, and Second spellings: "`NOT` over a form".
#[derive(Clone, Debug)]
pub enum Negated {
    Atom(Node<Atom>),
    /// An `OR`, `IF` or `ALL` form, or a `NOT`.
    Form(Arc<Conjunct>),
}

/// A label of a constraint, with whether the constraint makes it: `*X`.
///
/// Implements `docs/arclog.md`, Negation and constraints: "`=` may make its first label".
#[derive(Clone, Copy, PartialEq, Eq, Hash, Debug)]
pub struct ConstraintLabel {
    pub label: LabelId,
    pub fresh: bool,
}

/// The second operand of a constraint: a label, or the reserved label `0`.
///
/// Implements `docs/arclog.md`, Negation and constraints: "`0` is a reserved label usable as the second label of a constraint."
#[derive(Clone, Copy, PartialEq, Eq, Hash, Debug)]
pub enum Operand {
    Label(ConstraintLabel),
    Zero,
}

/// A constraint over two labels. `=` makes its first label in `(= *X Y)`,
/// and its second in `(= Y *X)`, a second spelling that the decoder blocks
/// and the lint never refuses.
///
/// Implements `docs/arclog.md`, Negation and constraints, and `work/engine/reader.md`, Checker: "The second spellings are suggestions and not rules of the language, so the lint never refuses them".
#[derive(Clone, Copy, PartialEq, Eq, Hash, Debug)]
pub struct Constraint {
    pub op: ConstraintOp,
    pub first: ConstraintLabel,
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
    /// A relation the program declares by its name: a derived relation, a
    /// chosen relation, a demonstrated relation.
    Declared(RelationName),
    Output(OutputName),
    /// In the definition of a cell instance in the registry, a read of an
    /// input port of the component the definition defines, which the
    /// expansion puts the instance's input in the place of. The registry file
    /// writes it `(self.<port> ...)`, and no arclog file holds it.
    DefinedPort(PortName),
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
    /// One label, on a column of a fixed type, or on a column of a type
    /// parameter, other than `key`, that the instance binds to one label's
    /// type.
    Label(LabelUse),
    /// A site on each field of a record that the site reads, in source
    /// order: each `(:<Field> <label>)` argument, and each bare label at a
    /// record's column, which is the site on the field the label names. So
    /// `(:key C A)` is the value of `(:key (:C C) (:A A))`, and the layout
    /// records the elision.
    ///
    /// `Key` is always a record, whose fields the key clause's `^` labels
    /// name, a key of one `^` label included, so `(:key *P_across)` is
    /// `(:key (:P_across *P_across))`. Another type parameter is a record
    /// where the instance binds it by a projection of several sites, as
    /// `docs/arclog.md`, Instance, gives. The reader reads that binding from
    /// the file's `INIT` forms and the key clauses of its `DEMONSTRATED` and
    /// `RIGID_DET` forms, which bind a key as an instance does, and which
    /// columns are of the parameter from the component's declaration in the
    /// registry.
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
    pub inputs: Arc<[Node<InstanceInput>]>,
}

/// A key clause, `(key (<body>) <inputs>)`: its body, whose `^` labels are
/// the key's columns in order of appearance, and the keyed inputs.
///
/// Implements `docs/arclog.md`, Instance.
#[derive(Clone, Debug)]
pub struct KeyClause {
    pub key: KeyBody,
    pub inputs: Arc<[Node<InstanceInput>]>,
}

/// An input of an instance: its name, its head sites, its body.
///
/// Implements `docs/arclog.md`, Instance.
#[derive(Clone, Debug)]
pub struct InstanceInput {
    pub name: PortName,
    pub head: Arc<[Site]>,
    pub body: Node<Body>,
}

/// A `CHOOSE` form, as `docs/constraints.md`, Choose, gives.
#[derive(Clone, Debug)]
pub struct Choose {
    pub name: RelationName,
    /// The `for` clause, a key clause whose `^` labels are the row's columns.
    pub rows: Option<KeyBody>,
    /// The candidate's columns, which follow the row's in the chosen
    /// relation.
    pub candidate_columns: Arc<[RelationColumn]>,
    /// The `from` clause: inside `for` where it reads the row's labels.
    pub from: Node<Body>,
    pub from_inside_for: bool,
    pub never: Arc<[Node<Body>]>,
}

/// A `RIGID_DET` form, as `docs/rigid.md`, Form, gives.
#[derive(Clone, Debug)]
pub struct RigidDet {
    pub name: RigidDetName,
    /// The `key` clause: each key row is an independent assembly.
    pub key: Option<KeyBody>,
    /// The `instance` clause, written as a key clause is: one of its rows is
    /// one instance, and its `^` labels are the instance's columns, which
    /// `.pose` holds.
    pub instance: Option<KeyBody>,
    /// The parts: each atom of the form, inside the `instance` clause where
    /// the form has one.
    pub parts: Arc<[Node<Atom>]>,
}

/// A `DEMONSTRATED` form, as `docs/arclog.md`, Demonstrated, gives.
#[derive(Clone, Debug)]
pub struct Demonstrated {
    pub name: RelationName,
    /// The key clause, with the inputs inside it, as an instance's is.
    pub key: Option<Node<KeyClause>>,
    /// The `value` and `demonstration` inputs that stand after the key
    /// clause, or every input where the form has no key.
    pub inputs: Arc<[Node<InstanceInput>]>,
    pub rules: Arc<[Node<DemoRule>]>,
}

/// A `DEMO_RULE` form: its name, its fields, its text, and its clauses.
///
/// Implements `docs/arclog.md`, Demonstrated.
#[derive(Clone, Debug)]
pub struct DemoRule {
    pub name: DemoRuleName,
    /// The rule's fields, each a column of its `&prediction`.
    pub fields: Arc<[RelationColumn]>,
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
/// `ALTS` form that exists only under this branch, in source order.
///
/// Implements `docs/arclog.md`, The `ALTS` form: "An `ALT` inside an `ALT` holds what the combination of the two alts rederives."
#[derive(Clone, Debug)]
pub struct Alt {
    pub name: AltsName,
    pub items: Arc<[AltItem]>,
}

/// One item of an `ALT` block: a form, or a nested `ALT` block. Only an
/// `ALT` block holds a nested `ALT`, so [`Form`] has no `ALT` variant.
///
/// Implements `docs/arclog.md`, The `ALTS` form: "An `ALT` inside an `ALT` holds what the combination of the two alts rederives."
#[derive(Clone, Debug)]
pub enum AltItem {
    Form(Form),
    Alt(Node<Alt>),
}

/// A whole arcdata file, its forms in the order `docs/arcdata.md` gives.
#[derive(Clone, Debug)]
pub struct Arcdata {
    pub representative: Option<Representative>,
    pub params: Arc<[Node<Param>]>,
    pub excludes: Arc<[Exclude]>,
    pub witness_records: Arc<[WitnessRecord]>,
}

/// `(representative <task_id> [<name>])`, as `docs/arcdata.md`, Header,
/// gives.
#[derive(Clone, Debug)]
pub struct Representative {
    pub task_id: Box<str>,
    /// The name of the case, one alt name, or a list of them where the case
    /// takes an alt at several `ALTS` forms, as an `output` form writes a
    /// name that fixes several alts.
    pub case: Option<Arc<[AltsName]>>,
}

/// A `param` form: the parameter, its column types and its rows. The
/// parameter is a relation of the arclog file, or an output that a
/// `RIGID_DET` or `RULE_OR_DET` form stores, as `&piece.member`.
///
/// Implements `docs/arcdata.md`, Params: "A form gives the parameter's column types after its name, one type or a list, and then its rows".
#[derive(Clone, Debug)]
pub struct Param {
    pub name: ProgramRelation,
    pub columns: Arc<[TypeName]>,
    pub value: ParamValue,
}

/// A type as a file writes it. `Position`, `Offset` and `Box` are one
/// [`crate::types::ValueType`], and the file keeps the name it writes.
///
/// Implements `docs/lib-spec.md`, Types: "Position and Offset are its two interpretations, aliases of one type", and `docs/arcdata.md`, Params.
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
    /// The type the name stands for.
    ///
    /// Implements `docs/lib-spec.md`, Types: "Position and Offset are its two interpretations, aliases of one type".
    pub fn value_type(self) -> crate::types::ValueType {
        todo!()
    }
}

/// The rows of a `param` form or an `assign` form, as `docs/arcdata.md`,
/// Params, gives.
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
///
/// Implements `docs/arcdata.md`, Params: "Each cell gives one row: its position, then its value. ... values before the grid fill the columns before the position."
#[derive(Clone, Debug)]
pub struct GridRows {
    pub before: Arc<[DataValue]>,
    pub grid: Grid,
}

/// One value of a derivation's row, under its column's name: `(:A AXIS_V)`,
/// `(:N 6)`.
///
/// Implements `docs/arcdata.md`, Params: "A frame of cells is its extent on each axis, and a frame cut into equal tiles is the tile count, tile size and gap on each axis".
#[derive(Clone, PartialEq, Eq, Hash, Debug)]
pub struct DataField {
    pub column: ColumnName,
    pub value: DataValue,
}

/// A value written in an arcdata file, held as the file writes it. Its typed
/// value, such as a Box or one column per member of a list, comes after the
/// type check, in one step for `param` rows and `assign` rows alike, by the
/// type of its column: the one the `param` form writes, or, for a relation
/// with no `param` form, such as a `RULE_OR_DET` relation, the one the type
/// check infers. A field of a derivation's row takes the type that the
/// registry's [`crate::registry::Derivation`] gives. That step is
/// [`crate::terms::encode_data_value`].
///
/// Implements `docs/arcdata.md`, Params.
#[derive(Clone, PartialEq, Eq, Hash, Debug)]
pub enum DataValue {
    /// An integer as the file writes it: a number, a Color's digit or an
    /// Ident's number, by the column's type.
    Integer(i32),
    /// An orientation constant, written by its name in the registry.
    Orientation(crate::terms::OrientationConstant),
    /// A value written as a list: a Box as its four margins, `(1 1 10 1)`,
    /// or the members of a column group of several fields, as
    /// `work/engine/reader.md`, Terms, gives.
    List(Arc<[DataValue]>),
}

/// A grid of an arcdata file: one row per line, a cell `_` gives no row.
///
/// Implements `docs/arcdata.md`, Params.
#[derive(Clone, Debug)]
pub struct Grid {
    pub rows: Arc<[Arc<[Option<DataValue>]>]>,
    /// The cell written with `@` before it, as `@_` or `@1`: the anchor of
    /// a grid of an Offset column, from which its cells' offsets count.
    pub anchor: Option<GridCell>,
}

/// A cell of a grid, by its row and its column, each counted from 0.
///
/// Implements `docs/arcdata.md`, Params: "A relation with a Position column is given as a grid, one row per line".
#[derive(Clone, Copy, PartialEq, Eq, Hash, Debug)]
pub struct GridCell {
    pub row: u32,
    pub column: u32,
}

/// An `exclude` form: the combination it leaves out, and its reason.
///
/// Implements `docs/arcdata.md`, Alts.
#[derive(Clone, Debug)]
pub struct Exclude {
    pub combination: Arc<[AltsName]>,
    pub reason: Option<Text>,
}

/// An `alts` form or an `approximated` form, with its witnesses.
///
/// Implements `docs/arcdata.md`, Alts.
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
    pub assigns: Arc<[(ProgramRelation, ParamValue)]>,
    pub input: Grid,
    pub outputs: Arc<[WitnessOutput]>,
}

/// A name in an `output` form: `concept`, the concept case, or an alt's name.
///
/// Implements `docs/arcdata.md`, Witnesses: "`output` gives each distinct output with the fewest names whose cases together give it".
#[derive(Clone, PartialEq, Eq, Hash, Debug)]
pub enum CaseRef {
    Concept,
    Alt(AltsName),
}

/// An `output` form of a witness.
///
/// Implements `docs/arcdata.md`, Witnesses.
#[derive(Clone, Debug)]
pub struct WitnessOutput {
    /// The names whose cases together give the output; empty for the one
    /// output of a witness with the verdict `other`. A name that fixes
    /// several alts is a list.
    pub names: Arc<[Arc<[CaseRef]>]>,
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
