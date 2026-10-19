//! The path by which an edit, a diagnostic or the layout names a node, and
//! the one walk from a path to its node. A path names a node by its form,
//! and its index in the source order of each list above it.
//!
//! # The children of a node
//!
//! A node here is any element a path names. A kind held as a
//! [`super::Node`] holds its canonical hash, and a conjunct, a site or an
//! arcdata record has its hash within the node that holds it, an arcdata
//! record within the `Node<Arcdata>` of its file.
//!
//! A path step is an index into the children of a node, which
//! [`NodeRef::children`] gives: the nodes it holds, in the order the file
//! writes them, each member of a list field counted in turn. [`node_at`] is
//! the one walk of an arclog path, and [`data_node_at`] the one walk of an
//! arcdata path, so the layout, the edits, the resolver and the case
//! programs number the children of a node alike.
//!
//! | Node | Children |
//! | --- | --- |
//! | program, claim, demonstrated rule | the forms |
//! | `ALTS` form | the `ALT` blocks |
//! | `ALT` block | the items, forms and nested `ALT` blocks |
//! | clause form | the body |
//! | body | the conjuncts |
//! | atom, negated atom | the sites |
//! | `NOT` over a form | the form |
//! | `OR` | the branches |
//! | `IF` | the test, the then, the else |
//! | `ALL` | the domain, the body |
//! | constraint | none |
//! | site | the arguments, each bare label and each field site, in source order |
//! | `INIT` form | the key clause where it has one, then the inputs after it |
//! | key clause | the body, then the inputs inside it |
//! | input | the head sites, then the body |
//! | `CHOOSE` form | the `for` body where it has one, the `from` body, the `never` bodies |
//! | `RIGID_DET` form | the `key` body, the `instance` body, each where it has one, then the parts |
//! | `DEMONSTRATED` form | the key clause where it has one, the inputs after it, the `DEMO_RULE` forms |
//!
//! A site's children are its arguments as written, whether or not it reads
//! a record, so argument `i` has path `i` under the site's path in each
//! spelling of one site: `(:key C A)` and `(:key (:C C) (:A A))` each have
//! two children. A bare-label argument is a [`NodeRef::Label`], with no
//! children.
//!
//! The arcdata file's nodes are numbered the same way, by
//! [`DataNodeRef::children`] and walked by [`data_node_at`]:
//!
//! | Node | Children |
//! | --- | --- |
//! | arcdata file | its top-level forms: the `representative` line where it has one, the `param` forms, the `exclude` forms, the `alts` and `approximated` forms |
//! | `alts` form | the `alt` forms |
//! | `alt` form | the witnesses, then the nested `alt` forms |
//! | `approximated` form | the witnesses |
//! | witness | the `relaxed` forms, the `assign` forms, the `input` grid, the `output` forms, where it has a body |
//!
//! A `param` form, an `exclude` form, a `representative` line, an `assign`
//! form, a grid and an `output` form have no children.

use super::{
    Alt, AltItem, AltRecord, Alts, Arcdata, Atom, Block, Body, Choose, ChoosePart, Claim, Clause, Conjunct, DemoRule, Demonstrated, DemonstratedPart,
    Exclude, Form, Grid, Instance, InstanceInput, InstanceInputPart, InstancePart, KeyClause, KeyClausePart, LabelUse, Negated, Node, Param, ParamValue, Program,
    ProgramRelation, Representative, RigidDet, RigidDetPart, Site, SiteArg, Slug, Witness, WitnessOutput, WitnessRecord,
};

/// One step of a path: the index of a node among its parent's children.
#[derive(Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Hash, Debug)]
pub struct PathStep(pub u32);

/// The path of a node: the index of its top-level form, then its index
/// among the children of each node below that form.
///
/// A path is relative to the node it starts from: a program's path starts
/// at the program, and the path of a [`crate::check::Refusal`] at the form
/// the check read.
#[derive(Clone, PartialEq, Eq, PartialOrd, Ord, Hash, Debug, Default)]
pub struct NodePath(pub Box<[PathStep]>);

impl NodePath {
    /// The path of the node at `relative` below the node at `self`.
    pub fn join(&self, relative: &NodePath) -> NodePath {
        NodePath(self.0.iter().chain(relative.0.iter()).copied().collect())
    }

    /// The path of the child at `index` of the node at `self`.
    pub fn child(&self, index: u32) -> NodePath {
        NodePath(self.0.iter().copied().chain(std::iter::once(PathStep(index))).collect())
    }

    /// The path of the top-level form at `index` of its file.
    pub fn top(index: u32) -> NodePath {
        NodePath(Box::new([PathStep(index)]))
    }
}

/// A node of an arclog program, borrowed: any node a path can name.
#[derive(Clone, Copy, Debug)]
pub enum NodeRef<'a> {
    Program(&'a Program),
    Claim(&'a Claim),
    Clause(&'a Clause),
    Instance(&'a Instance),
    KeyClause(&'a KeyClause),
    InstanceInput(&'a InstanceInput),
    Choose(&'a Choose),
    RigidDet(&'a RigidDet),
    Demonstrated(&'a Demonstrated),
    DemoRule(&'a DemoRule),
    Alts(&'a Alts),
    Alt(&'a Alt),
    Body(&'a Body),
    Conjunct(&'a Conjunct),
    /// A part of a `RIGID_DET` form. An atom of a body is a
    /// [`NodeRef::Conjunct`].
    Atom(&'a Atom),
    Site(&'a Site),
    /// A bare-label argument of a site, a [`super::SiteArg::Label`] or a
    /// [`super::SiteArg::NamedLabel`].
    Label(&'a LabelUse),
}

impl<'a> From<&'a Form> for NodeRef<'a> {
    fn from(form: &'a Form) -> Self {
        match form {
            Form::Claim(claim) => NodeRef::Claim(claim.value()),
            Form::Clause(clause) => NodeRef::Clause(clause.value()),
            Form::Instance(instance) => NodeRef::Instance(instance.value()),
            Form::Choose(choose) => NodeRef::Choose(choose.value()),
            Form::RigidDet(rigid) => NodeRef::RigidDet(rigid.value()),
            Form::Demonstrated(demonstrated) => NodeRef::Demonstrated(demonstrated.value()),
            Form::Alts(alts) => NodeRef::Alts(alts.value()),
        }
    }
}

impl<'a> From<&'a AltItem> for NodeRef<'a> {
    fn from(item: &'a AltItem) -> Self {
        NodeRef::from(Block::from(item))
    }
}

impl<'a> From<Block<'a>> for NodeRef<'a> {
    fn from(block: Block<'a>) -> Self {
        match block {
            Block::Form(form) => NodeRef::from(form),
            Block::Alt(alt) => NodeRef::Alt(alt),
        }
    }
}

impl<'a> NodeRef<'a> {
    /// The atom that the node stands for: an atom, and the atom of a
    /// conjunct or of a negated conjunct; none for each other node.
    pub fn atom(self) -> Option<&'a Atom> {
        match self {
            NodeRef::Conjunct(conjunct) => conjunct.atom().map(Node::value),
            NodeRef::Atom(atom) => Some(atom),
            _ => None,
        }
    }

    /// The node's children, in the order of the module comment's table.
    pub fn children(self) -> Vec<NodeRef<'a>> {
        fn forms(forms: &[Form]) -> Vec<NodeRef<'_>> {
            forms.iter().map(NodeRef::from).collect()
        }
        fn sites(sites: &[Site]) -> Vec<NodeRef<'_>> {
            sites.iter().map(NodeRef::Site).collect()
        }
        fn bodies<'b>(bodies: impl IntoIterator<Item = &'b Node<Body>>) -> Vec<NodeRef<'b>> {
            bodies.into_iter().map(|body| NodeRef::Body(body.value())).collect()
        }
        match self {
            NodeRef::Program(program) => forms(&program.forms),
            NodeRef::Claim(claim) => claim.blocks().map(NodeRef::from).collect(),
            NodeRef::DemoRule(rule) => forms(&rule.forms),
            NodeRef::Alts(alts) => alts.blocks().map(NodeRef::from).collect(),
            NodeRef::Alt(alt) => alt.blocks().map(NodeRef::from).collect(),
            NodeRef::Clause(clause) => bodies([&clause.body]),
            NodeRef::Body(body) => body.conjuncts.iter().map(NodeRef::Conjunct).collect(),
            NodeRef::Conjunct(conjunct) => match conjunct {
                Conjunct::Atom(_) | Conjunct::Not(Negated::Atom(_)) => conjunct.atom().map_or_else(Vec::new, |atom| sites(&atom.value().sites)),
                Conjunct::Not(Negated::Form(form)) => vec![NodeRef::Conjunct(form)],
                Conjunct::Constraint(_) => Vec::new(),
                Conjunct::Or(branches) => bodies(branches.iter()),
                Conjunct::If { test, then, otherwise } => bodies([test, then, otherwise]),
                Conjunct::All { domain, body } => bodies([domain, body]),
            },
            NodeRef::Atom(atom) => sites(&atom.sites),
            NodeRef::Site(site) => site
                .value
                .args
                .iter()
                .map(|arg| match arg {
                    SiteArg::Label(label) | SiteArg::NamedLabel { label, .. } => NodeRef::Label(label),
                    SiteArg::Field(field) => NodeRef::Site(field),
                })
                .collect(),
            NodeRef::Label(_) => Vec::new(),
            NodeRef::Instance(instance) => instance
                .parts()
                .map(|part| match part {
                    InstancePart::Key => NodeRef::KeyClause(instance.key.as_ref().expect("the key clause of a part").value()),
                    InstancePart::Input(index) => NodeRef::InstanceInput(instance.inputs[index].value()),
                })
                .collect(),
            NodeRef::KeyClause(clause) => clause
                .parts()
                .map(|part| match part {
                    KeyClausePart::Body => NodeRef::Body(clause.key.body.value()),
                    KeyClausePart::Input(index) => NodeRef::InstanceInput(clause.inputs[index].value()),
                })
                .collect(),
            NodeRef::InstanceInput(input) => input
                .parts()
                .map(|part| match part {
                    InstanceInputPart::Head(index) => NodeRef::Site(&input.head[index]),
                    InstanceInputPart::Body => NodeRef::Body(input.body.value()),
                })
                .collect(),
            NodeRef::Choose(choose) => choose
                .parts()
                .map(|part| match part {
                    ChoosePart::For => NodeRef::Body(choose.rows.as_ref().expect("the `for` clause of a part").body.value()),
                    ChoosePart::From => NodeRef::Body(choose.from.value()),
                    ChoosePart::Never(index) => NodeRef::Body(choose.never[index].value()),
                })
                .collect(),
            NodeRef::RigidDet(rigid) => rigid
                .children()
                .map(|part| match part {
                    RigidDetPart::Key => NodeRef::Body(rigid.key.as_ref().expect("the `key` clause of a part").body.value()),
                    RigidDetPart::Instance => NodeRef::Body(rigid.instance.as_ref().expect("the `instance` clause of a part").body.value()),
                    RigidDetPart::Part(index) => NodeRef::Atom(rigid.parts[index].value()),
                })
                .collect(),
            NodeRef::Demonstrated(demonstrated) => demonstrated
                .parts()
                .map(|part| match part {
                    DemonstratedPart::Key => NodeRef::KeyClause(demonstrated.key.as_ref().expect("the key clause of a part").value()),
                    DemonstratedPart::Input(index) => NodeRef::InstanceInput(demonstrated.inputs[index].value()),
                    DemonstratedPart::Rule(index) => NodeRef::DemoRule(demonstrated.rules[index].value()),
                })
                .collect(),
        }
    }
}

/// The node at `path` below `root`, or `None` where `path` names no node.
pub fn node_at<'a>(root: NodeRef<'a>, path: &NodePath) -> Option<NodeRef<'a>> {
    descend(root, path)
}

/// The node at `path` below `root` of either file, by the children
/// [`PathNode::children`] gives, or `None` where `path` names no node.
fn descend<N: PathNode>(root: N, path: &NodePath) -> Option<N> {
    path.0.iter().try_fold(root, |node, step| node.children().get(step.0 as usize).copied())
}

/// A node kind a path walks: its children, as the tables of the module
/// comment give them, and the address of the value it borrows.
pub(crate) trait PathNode: Copy {
    fn children(self) -> Vec<Self>;
    fn address(self) -> *const ();
}

/// The address of `value`.
fn address_of<T>(value: &T) -> *const () {
    (value as *const T).cast()
}

/// The index of `child` among the children of `parent`: the child of its
/// variant at its address, or `None` where the children of `parent` do not
/// hold it.
pub(crate) fn child_index<N: PathNode>(parent: N, child: N) -> Option<u32> {
    index_among(&parent.children(), child)
}

/// The index of `child` among `children`, the children of one node: the
/// child of its variant at its address, or `None` where `children` do not
/// hold it.
pub(crate) fn index_among<N: PathNode>(children: &[N], child: N) -> Option<u32> {
    let same = |node: &N| std::mem::discriminant(node) == std::mem::discriminant(&child) && node.address() == child.address();
    children.iter().position(same).map(|index| index as u32)
}

impl PathNode for NodeRef<'_> {
    fn children(self) -> Vec<Self> {
        NodeRef::children(self)
    }

    fn address(self) -> *const () {
        match self {
            NodeRef::Program(node) => address_of(node),
            NodeRef::Claim(node) => address_of(node),
            NodeRef::Clause(node) => address_of(node),
            NodeRef::Instance(node) => address_of(node),
            NodeRef::KeyClause(node) => address_of(node),
            NodeRef::InstanceInput(node) => address_of(node),
            NodeRef::Choose(node) => address_of(node),
            NodeRef::RigidDet(node) => address_of(node),
            NodeRef::Demonstrated(node) => address_of(node),
            NodeRef::DemoRule(node) => address_of(node),
            NodeRef::Alts(node) => address_of(node),
            NodeRef::Alt(node) => address_of(node),
            NodeRef::Body(node) => address_of(node),
            NodeRef::Conjunct(node) => address_of(node),
            NodeRef::Atom(node) => address_of(node),
            NodeRef::Site(node) => address_of(node),
            NodeRef::Label(node) => address_of(node),
        }
    }
}

impl PathNode for DataNodeRef<'_> {
    fn children(self) -> Vec<Self> {
        DataNodeRef::children(self)
    }

    fn address(self) -> *const () {
        match self {
            DataNodeRef::Arcdata(node) => address_of(node),
            DataNodeRef::Representative(node) => address_of(node),
            DataNodeRef::Param(node) => address_of(node),
            DataNodeRef::Exclude(node) => address_of(node),
            DataNodeRef::WitnessRecord(node) => address_of(node),
            DataNodeRef::AltRecord(node) => address_of(node),
            DataNodeRef::Witness(node) => address_of(node),
            DataNodeRef::Relaxed(node) => address_of(node),
            DataNodeRef::Assign(node) => address_of(node),
            DataNodeRef::Grid(node) => address_of(node),
            DataNodeRef::WitnessOutput(node) => address_of(node),
        }
    }
}

/// A node of an arcdata file, borrowed: any node an arcdata path can name.
#[derive(Clone, Copy, Debug)]
pub enum DataNodeRef<'a> {
    Arcdata(&'a Arcdata),
    Representative(&'a Representative),
    Param(&'a Node<Param>),
    Exclude(&'a Exclude),
    WitnessRecord(&'a WitnessRecord),
    AltRecord(&'a AltRecord),
    Witness(&'a Witness),
    Relaxed(&'a Slug),
    Assign(&'a (ProgramRelation, ParamValue)),
    Grid(&'a Grid),
    WitnessOutput(&'a WitnessOutput),
}

impl<'a> DataNodeRef<'a> {
    /// The node's children, in the order of the module comment's table.
    pub fn children(self) -> Vec<DataNodeRef<'a>> {
        fn witnesses(witnesses: &[Witness]) -> impl Iterator<Item = DataNodeRef<'_>> {
            witnesses.iter().map(DataNodeRef::Witness)
        }
        match self {
            DataNodeRef::Arcdata(arcdata) => {
                let representative = arcdata.representative.iter().map(DataNodeRef::Representative);
                let params = arcdata.params.iter().map(DataNodeRef::Param);
                let excludes = arcdata.excludes.iter().map(DataNodeRef::Exclude);
                let records = arcdata.witness_records.iter().map(DataNodeRef::WitnessRecord);
                representative.chain(params).chain(excludes).chain(records).collect()
            }
            DataNodeRef::WitnessRecord(WitnessRecord::Alts { alts, .. }) => alts.iter().map(DataNodeRef::AltRecord).collect(),
            DataNodeRef::WitnessRecord(WitnessRecord::Approximated { witnesses: list, .. }) => witnesses(list).collect(),
            DataNodeRef::AltRecord(alt) => witnesses(&alt.witnesses).chain(alt.nested.iter().map(DataNodeRef::AltRecord)).collect(),
            DataNodeRef::Witness(Witness { body: Some(body), .. }) => {
                let relaxed = body.relaxed.iter().map(DataNodeRef::Relaxed);
                let assigns = body.assigns.iter().map(DataNodeRef::Assign);
                let outputs = body.outputs.iter().map(DataNodeRef::WitnessOutput);
                relaxed.chain(assigns).chain([DataNodeRef::Grid(&body.input)]).chain(outputs).collect()
            }
            DataNodeRef::Witness(Witness { body: None, .. })
            | DataNodeRef::Representative(_)
            | DataNodeRef::Param(_)
            | DataNodeRef::Exclude(_)
            | DataNodeRef::Relaxed(_)
            | DataNodeRef::Assign(_)
            | DataNodeRef::Grid(_)
            | DataNodeRef::WitnessOutput(_) => Vec::new(),
        }
    }
}

/// The node at `path` below `root`, or `None` where `path` names no node.
pub fn data_node_at<'a>(root: DataNodeRef<'a>, path: &NodePath) -> Option<DataNodeRef<'a>> {
    descend(root, path)
}
