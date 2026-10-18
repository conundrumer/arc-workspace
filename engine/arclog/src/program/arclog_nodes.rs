//! The nodes of an arclog file, from the whole program down to its sites.

#![allow(unused_variables, dead_code)]

use std::sync::Arc;

use super::*;

/// A whole arclog file, or a synthesized program: its forms. A program is
/// held as a `Node<Program>`, so it has a canonical hash and an equality as
/// each other node has. The forms stand in the order
/// `docs/arclog/arclog.md#program` gives: `INPUT` and `OUTPUT` blocks in
/// dependency order, then `ALTS` forms, then the tail.
#[derive(Clone, Debug)]
pub struct Program {
    pub forms: Arc<[Form]>,
}

/// A top-level form, or a form inside a claim, an `ALT` or a `DEMO_RULE`.
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
#[derive(Clone, Copy, PartialEq, Eq, Hash, Debug)]
pub enum ClaimKind {
    Input,
    Output,
}

/// An `INPUT` or `OUTPUT` block: a claim, its slug, its text, then the forms
/// that serve it, as `docs/arclog/arclog.md#program` gives.
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

/// The keyword of a clause form, as `docs/arclog/arclog.md#program` gives.
#[derive(Clone, Copy, PartialEq, Eq, Hash, Debug)]
pub enum ClauseKeyword {
    /// `RULE`: a program clause, per input.
    Rule,
    /// `DET`: a determination clause, task-wide.
    Det,
    /// `DET_OR_RULE`: an `ALTS` form on the relation, the stored reading
    /// first, as `docs/arclog/arclog.md#the-alts-form` gives.
    DetOrRule,
    /// `RULE_OR_DET`: an `ALTS` form on the relation, the derived reading
    /// first.
    RuleOrDet,
}

/// A relation the program declares, as a clause form derives it or an
/// arcdata form stores it: a derived, chosen or demonstrated relation, or an
/// instance relation, as `&ring.value` on a `RULE_OR_DET` line, or an output
/// of a `RIGID_DET` form, as `&piece.member` in a `param` form. An arcdata
/// form names it in the arclog file's spelling.
#[derive(Clone, PartialEq, Eq, Hash, Debug)]
pub enum ProgramRelation {
    Declared(RelationName),
    Output(OutputName),
}

/// An instance relation, `&comps.component`, or an output of a `RIGID_DET`
/// form, `&marker.glyph`, `&marker.bbox.box`, `&marker.pose`: the form,
/// then the path of names after it (`docs/arclog/arclog.md#instance`,
/// `docs/arclog/rigid.md#form`).
#[derive(Clone, PartialEq, Eq, Hash, Debug)]
pub struct OutputName {
    pub of: OutputOwner,
    pub path: Arc<[OutputStep]>,
}

/// One step of the path of an [`OutputName`] after its form: a name, as
/// `glyph` in `&marker.glyph` or `bbox` and `box` in `&marker.bbox.box`, or
/// `pose` (`docs/arclog/rigid.md#semantics`).
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

/// The form whose outputs an [`OutputName`] reads: an instance, or a
/// `RIGID_DET` form.
#[derive(Clone, PartialEq, Eq, Hash, Debug)]
pub enum OutputOwner {
    Instance(InstanceName),
    RigidDet(RigidDetName),
}

/// A clause form: its keyword, the relation's name, its proposers, its body
/// and its `ONE` marks (`docs/arclog/arclog.md#program`). A clause with
/// nothing after its name is a fact, as `(RULE &live)`. A `DET` that names
/// a proposer, or a derivation in place of a proposer, as
/// `(DET &frame Frame)`, has that name in `proposers`, and a `DET_OR_RULE`
/// or `RULE_OR_DET` line holds its proposers, then the body of the reading
/// that has clauses of its own.
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
    /// and holds none here. So does a `DET_OR_RULE` or `RULE_OR_DET` line
    /// with proposers and no body: its relation has its proposers' columns,
    /// which map onto one another by position, each named as the line's
    /// first proposer names it. A line with no proposer and no body derives
    /// a fact, a relation of no columns.
    /// After an edit, the columns of the new body, as
    /// [`crate::program::Node::apply`] gives.
    pub columns: Arc<[RelationColumn]>,
}

/// A `ONE` mark: the key columns of the clause's relation for each value of
/// which a model keeps one row, as `docs/arclog/constraints.md#one` gives. A
/// mark with no label, `(ONE)`, keeps one row of the whole relation.
#[derive(Clone, PartialEq, Eq, Hash, Debug)]
pub struct OneMark {
    pub key: Arc<[LabelId]>,
}

/// A body: a sequence of conjuncts, in source order
/// (`docs/arclog/arclog.md#clause`). The canonical form takes the conjuncts
/// under reorder, so their order is outside the hash.
#[derive(Clone, Debug)]
pub struct Body {
    pub conjuncts: Arc<[Conjunct]>,
}

/// One conjunct of a body: an atom, a negated atom, a constraint, or an
/// `OR`, `IF` or `ALL` form.
#[derive(Clone, Debug)]
pub enum Conjunct {
    Atom(Node<Atom>),
    /// `NOT` before an atom, where every site of the atom joins, or before a
    /// form, a second spelling, as `docs/arclog/arclog.md#second-spellings`
    /// gives.
    Not(Negated),
    Constraint(Constraint),
    /// An `OR` form: its branches, as `docs/arclog/arclog.md#disjunction`
    /// gives.
    Or(Arc<[Node<Body>]>),
    /// An `IF` form: the test, the then and the else, as
    /// `docs/arclog/arclog.md#conditional` gives.
    If {
        test: Node<Body>,
        then: Node<Body>,
        otherwise: Node<Body>,
    },
    /// An `ALL` form: the domain, then what each member must satisfy, as
    /// `docs/arclog/arclog.md#universal` gives.
    All {
        domain: Node<Body>,
        body: Node<Body>,
    },
}

/// A constraint operator, as `docs/arclog/arclog.md#negation-and-constraints`
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

/// What a `NOT` negates: an atom, or a form.
#[derive(Clone, Debug)]
pub enum Negated {
    Atom(Node<Atom>),
    /// An `OR`, `IF` or `ALL` form, or a `NOT`.
    Form(Arc<Conjunct>),
}

/// A label of a constraint, with whether the constraint makes it: `*X`.
#[derive(Clone, Copy, PartialEq, Eq, Hash, Debug)]
pub struct ConstraintLabel {
    pub label: LabelId,
    pub fresh: bool,
}

/// The second operand of a constraint: a label, or the reserved label `0`.
#[derive(Clone, Copy, PartialEq, Eq, Hash, Debug)]
pub enum Operand {
    Label(ConstraintLabel),
    Zero,
}

/// A constraint over two labels. `=` makes its first label in `(= *X Y)`,
/// and its second in `(= Y *X)`, a second spelling.
#[derive(Clone, Copy, PartialEq, Eq, Hash, Debug)]
pub struct Constraint {
    pub op: ConstraintOp,
    pub first: ConstraintLabel,
    pub second: Operand,
}

/// The relation an atom reads.
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

/// The fact relations, as `docs/arclog/arclog.md#program` gives.
#[derive(Clone, Copy, PartialEq, Eq, Hash, Debug)]
pub enum FactRelation {
    Input,
    ExInput,
    ExOutput,
}

/// An atom: a relation and its sites.
#[derive(Clone, Debug)]
pub struct Atom {
    pub relation: RelationRef,
    pub sites: Arc<[Site]>,
}

/// A site: one column of the atom's relation and what stands at it, as
/// `docs/arclog/arclog.md#sites` gives. An elided site, `*P`, is the same
/// value as `(:P *P)`; the layout records the elision.
#[derive(Clone, PartialEq, Eq, Hash, Debug)]
pub struct Site {
    pub column: ColumnName,
    pub value: SiteValue,
}

/// What stands at a site, as the file writes it: its arguments in source
/// order. `(:key C A)` and `(:key (:C C) (:A A))` are two values, and a
/// column of a type parameter is written alike whether it reads a record or
/// one label: whether it reads a record, and the resolved content of each
/// such site, are the resolver's. A bare label at a site on a column of a
/// type parameter is a [`SiteArg::NamedLabel`], and each other bare label a
/// [`SiteArg::Label`].
#[derive(Clone, PartialEq, Eq, Hash, Debug)]
pub struct SiteValue {
    /// Never empty.
    pub args: Arc<[SiteArg]>,
}

/// One argument of a site.
#[derive(Clone, PartialEq, Eq, Hash, Debug)]
pub enum SiteArg {
    /// A bare label with its mark at a site on a fixed-type column or on a
    /// field, `*V` of `(:C *V)`, whose name stands only in the layout, or
    /// `0` at any site.
    Label(LabelUse),
    /// A bare label with its mark at a site on a column of a type
    /// parameter, `A` of `(:key C A)`, with the name the file writes for it,
    /// `A`. Where the column holds a record, the label is the elided field
    /// site `(:A A)` (`docs/arclog/arclog.md#sites`), and its name is the
    /// field it reads.
    NamedLabel { name: ColumnName, label: LabelUse },
    /// A site on a field of a record, `(:<Field> ...)`: `(:A *A1)` of
    /// `(:key (:C C) (:A *A1))`.
    Field(Site),
}

impl SiteArg {
    /// The label of a bare-label argument of either kind.
    pub fn label(&self) -> Option<LabelUse> {
        match self {
            SiteArg::Label(label) | SiteArg::NamedLabel { label, .. } => Some(*label),
            SiteArg::Field(_) => None,
        }
    }
}

/// One label at a site, with its mark.
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

/// An `INIT` form: an instance of a lib component, as
/// `docs/arclog/arclog.md#instance` gives.
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
#[derive(Clone, Debug)]
pub struct KeyClause {
    pub key: KeyBody,
    pub inputs: Arc<[Node<InstanceInput>]>,
}

/// The inputs an `INIT` or a `DEMONSTRATED` form writes: the keyed
/// inputs, then the others.
pub fn written_inputs<'a>(key: Option<&'a Node<KeyClause>>, inputs: &'a [Node<InstanceInput>]) -> impl Iterator<Item = &'a InstanceInput> + Clone {
    key.into_iter().flat_map(|key| key.value().inputs.iter()).chain(inputs.iter()).map(|input| input.value())
}

/// An input of an instance: its name, its head sites, its body.
#[derive(Clone, Debug)]
pub struct InstanceInput {
    pub name: PortName,
    pub head: Arc<[Site]>,
    pub body: Node<Body>,
}

/// A `CHOOSE` form, as `docs/arclog/constraints.md#choose` gives.
#[derive(Clone, Debug)]
pub struct Choose {
    pub name: RelationName,
    /// The `for` clause, a key clause whose `^` labels are the row's columns.
    pub rows: Option<KeyBody>,
    /// The candidate's columns, which follow the row's in the chosen
    /// relation.
    /// After an edit, the columns of the new body, as
    /// [`crate::program::Node::apply`] gives.
    pub candidate_columns: Arc<[RelationColumn]>,
    /// The `from` clause: inside `for` where it reads the row's labels.
    pub from: Node<Body>,
    pub from_inside_for: bool,
    pub never: Arc<[Node<Body>]>,
}

/// A `RIGID_DET` form, as `docs/arclog/rigid.md#form` gives. Where the form
/// has a `key` clause, the rest of the form stands inside it after its body,
/// as the keyed inputs of an `INIT` do: the `instance` clause where the form
/// has one, and the parts otherwise.
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

/// A `DEMONSTRATED` form, as `docs/arclog/arclog.md#demonstrated` gives.
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
#[derive(Clone, Debug)]
pub struct DemoRule {
    pub name: DemoRuleName,
    /// The rule's fields, each a column of its `&prediction`.
    /// After an edit, the columns of the new body, as
    /// [`crate::program::Node::apply`] gives.
    pub fields: Arc<[RelationColumn]>,
    pub text: Option<Text>,
    pub forms: Arc<[Form]>,
}

/// An `ALTS` form, as `docs/arclog/arclog.md#the-alts-form` gives: its
/// name, its gloss, the concept case's name, then an `ALT` block per alt.
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
#[derive(Clone, Debug)]
pub struct Alt {
    pub name: AltsName,
    pub items: Arc<[AltItem]>,
}

/// One item of an `ALT` block: a form, or a nested `ALT` block, which holds
/// what the combination of the two alts rederives. Only an `ALT` block
/// holds a nested `ALT`, so [`Form`] has no `ALT` variant.
#[derive(Clone, Debug)]
pub enum AltItem {
    Form(Form),
    Alt(Node<Alt>),
}
