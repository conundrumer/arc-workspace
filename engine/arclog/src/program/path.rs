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
//! writes them, each member of a list field counted in turn.
//! [`NodeRef::handles`] is the one walk of that order, which gives each
//! child as the handle the node holds it by, so that the walks over
//! borrowed nodes and over owned ones read it alike. [`node_at`] is
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

use std::ops::ControlFlow;

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
        self.handles().into_iter().map(Handle::node).collect()
    }

    /// The node's children, each by the handle the node holds it by, in the
    /// order of the module comment's table.
    pub fn handles(self) -> Vec<Handle<'a>> {
        let mut handles = Vec::new();
        self.each_handle(|handle| {
            handles.push(handle);
            ControlFlow::Continue(())
        });
        handles
    }

    /// The child at `index`, or `None` where the node has fewer children,
    /// reached without collecting the children.
    pub fn child_at(self, index: usize) -> Option<NodeRef<'a>> {
        nth_visited(index, |visit| self.each_handle(visit)).map(Handle::node)
    }

    /// Calls `visit` on each child's handle, in the order of the module
    /// comment's table, until it breaks.
    pub fn each_handle(self, mut visit: impl FnMut(Handle<'a>) -> ControlFlow<()>) {
        fn run<'b>(handles: impl Iterator<Item = Handle<'b>>, visit: &mut impl FnMut(Handle<'b>) -> ControlFlow<()>) {
            for handle in handles {
                if visit(handle).is_break() {
                    return;
                }
            }
        }
        fn forms<'b>(forms: &'b [Form], visit: &mut impl FnMut(Handle<'b>) -> ControlFlow<()>) {
            run(forms.iter().map(Handle::Form), visit);
        }
        fn sites<'b>(sites: &'b [Site], visit: &mut impl FnMut(Handle<'b>) -> ControlFlow<()>) {
            run(sites.iter().map(Handle::Site), visit);
        }
        fn bodies<'b>(bodies: impl IntoIterator<Item = &'b Node<Body>>, visit: &mut impl FnMut(Handle<'b>) -> ControlFlow<()>) {
            run(bodies.into_iter().map(Handle::Body), visit);
        }
        let visit = &mut visit;
        match self {
            NodeRef::Program(program) => forms(&program.forms, visit),
            NodeRef::Claim(claim) => forms(&claim.forms, visit),
            NodeRef::DemoRule(rule) => forms(&rule.forms, visit),
            NodeRef::Alts(alts) => run(alts.alts.iter().map(Handle::Alt), visit),
            NodeRef::Alt(alt) => run(
                alt.items.iter().map(|item| match item {
                    AltItem::Form(form) => Handle::Form(form),
                    AltItem::Alt(alt) => Handle::Alt(alt),
                }),
                visit,
            ),
            NodeRef::Clause(clause) => bodies([&clause.body], visit),
            NodeRef::Body(body) => run(body.conjuncts.iter().map(Handle::Conjunct), visit),
            NodeRef::Conjunct(conjunct) => match conjunct {
                Conjunct::Not(Negated::Form(form)) => run([Handle::Conjunct(form)].into_iter(), visit),
                Conjunct::Constraint(_) => {}
                Conjunct::Or(branches) => bodies(branches.iter(), visit),
                Conjunct::If { test, then, otherwise } => bodies([test, then, otherwise], visit),
                Conjunct::All { domain, body } => bodies([domain, body], visit),
                _ => {
                    if let Some(atom) = conjunct.atom() {
                        sites(&atom.value().sites, visit)
                    }
                }
            },
            NodeRef::Atom(atom) => sites(&atom.sites, visit),
            NodeRef::Site(site) => run(
                site.value.args.iter().map(|arg| match arg {
                    SiteArg::Label(_) | SiteArg::NamedLabel { .. } => Handle::Arg(arg),
                    SiteArg::Field(field) => Handle::Site(field),
                }),
                visit,
            ),
            NodeRef::Label(_) => {}
            NodeRef::Instance(instance) => run(
                instance.parts().map(|part| match part {
                    InstancePart::Key => Handle::KeyClause(instance.key.as_ref().expect("the key clause of a part")),
                    InstancePart::Input(index) => Handle::Input(&instance.inputs[index]),
                }),
                visit,
            ),
            NodeRef::KeyClause(clause) => run(
                clause.parts().map(|part| match part {
                    KeyClausePart::Body => Handle::Body(&clause.key.body),
                    KeyClausePart::Input(index) => Handle::Input(&clause.inputs[index]),
                }),
                visit,
            ),
            NodeRef::InstanceInput(input) => run(
                input.parts().map(|part| match part {
                    InstanceInputPart::Head(index) => Handle::Site(&input.head[index]),
                    InstanceInputPart::Body => Handle::Body(&input.body),
                }),
                visit,
            ),
            NodeRef::Choose(choose) => run(
                choose.parts().map(|part| match part {
                    ChoosePart::For => Handle::Body(&choose.rows.as_ref().expect("the `for` clause of a part").body),
                    ChoosePart::From => Handle::Body(&choose.from),
                    ChoosePart::Never(index) => Handle::Body(&choose.never[index]),
                }),
                visit,
            ),
            NodeRef::RigidDet(rigid) => run(
                rigid.children().map(|part| match part {
                    RigidDetPart::Key => Handle::Body(&rigid.key.as_ref().expect("the `key` clause of a part").body),
                    RigidDetPart::Instance => Handle::Body(&rigid.instance.as_ref().expect("the `instance` clause of a part").body),
                    RigidDetPart::Part(index) => Handle::Atom(&rigid.parts[index]),
                }),
                visit,
            ),
            NodeRef::Demonstrated(demonstrated) => run(
                demonstrated.parts().map(|part| match part {
                    DemonstratedPart::Key => Handle::KeyClause(demonstrated.key.as_ref().expect("the key clause of a part")),
                    DemonstratedPart::Input(index) => Handle::Input(&demonstrated.inputs[index]),
                    DemonstratedPart::Rule(index) => Handle::DemoRule(&demonstrated.rules[index]),
                }),
                visit,
            ),
        }
    }
}

/// The item at `index` of the items that `each` gives to its visitor, where
/// `each` stops once the visitor breaks.
fn nth_visited<T>(index: usize, each: impl FnOnce(&mut dyn FnMut(T) -> ControlFlow<()>)) -> Option<T> {
    let mut remaining = index;
    let mut found = None;
    each(&mut |item| {
        if remaining == 0 {
            found = Some(item);
            return ControlFlow::Break(());
        }
        remaining -= 1;
        ControlFlow::Continue(())
    });
    found
}

/// A child of an arclog node, borrowed as the handle its parent holds it
/// by, as [`NodeRef::handles`] gives it.
#[derive(Clone, Copy, Debug)]
pub enum Handle<'a> {
    Form(&'a Form),
    Alt(&'a Node<Alt>),
    KeyClause(&'a Node<KeyClause>),
    Input(&'a Node<InstanceInput>),
    DemoRule(&'a Node<DemoRule>),
    Body(&'a Node<Body>),
    Conjunct(&'a Conjunct),
    /// A part of a `RIGID_DET` form.
    Atom(&'a Node<Atom>),
    Site(&'a Site),
    /// A [`SiteArg::Label`] or a [`SiteArg::NamedLabel`].
    Arg(&'a SiteArg),
}

impl<'a> Handle<'a> {
    /// The node the handle holds.
    pub fn node(self) -> NodeRef<'a> {
        match self {
            Handle::Form(form) => NodeRef::from(form),
            Handle::Alt(alt) => NodeRef::Alt(alt.value()),
            Handle::KeyClause(clause) => NodeRef::KeyClause(clause.value()),
            Handle::Input(input) => NodeRef::InstanceInput(input.value()),
            Handle::DemoRule(rule) => NodeRef::DemoRule(rule.value()),
            Handle::Body(body) => NodeRef::Body(body.value()),
            Handle::Conjunct(conjunct) => NodeRef::Conjunct(conjunct),
            Handle::Atom(atom) => NodeRef::Atom(atom.value()),
            Handle::Site(site) => NodeRef::Site(site),
            Handle::Arg(SiteArg::Label(label) | SiteArg::NamedLabel { label, .. }) => NodeRef::Label(label),
            Handle::Arg(SiteArg::Field(field)) => NodeRef::Site(field),
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
    path.0.iter().try_fold(root, |node, step| node.child_at(step.0 as usize))
}

/// A node kind a path walks: its children, as the tables of the module
/// comment give them, and the address of the value it borrows.
pub(crate) trait PathNode: Copy {
    fn children(self) -> Vec<Self>;
    /// The child at `index`, or `None` where there are fewer children.
    fn child_at(self, index: usize) -> Option<Self>;
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

    fn child_at(self, index: usize) -> Option<Self> {
        NodeRef::child_at(self, index)
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

    fn child_at(self, index: usize) -> Option<Self> {
        DataNodeRef::child_at(self, index)
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
        let mut children = Vec::new();
        self.each_child(|child| {
            children.push(child);
            ControlFlow::Continue(())
        });
        children
    }

    /// The child at `index`, or `None` where the node has fewer children,
    /// reached without collecting the children.
    pub fn child_at(self, index: usize) -> Option<DataNodeRef<'a>> {
        nth_visited(index, |visit| self.each_child(visit))
    }

    /// Calls `visit` on each child, in the order of the module comment's
    /// table, until it breaks.
    pub fn each_child(self, mut visit: impl FnMut(DataNodeRef<'a>) -> ControlFlow<()>) {
        let _ = self.children_while(&mut visit);
    }

    fn children_while(self, visit: &mut impl FnMut(DataNodeRef<'a>) -> ControlFlow<()>) -> ControlFlow<()> {
        fn witnesses(witnesses: &[Witness]) -> impl Iterator<Item = DataNodeRef<'_>> {
            witnesses.iter().map(DataNodeRef::Witness)
        }
        match self {
            DataNodeRef::Arcdata(arcdata) => {
                let representative = arcdata.representative.iter().map(DataNodeRef::Representative);
                let params = arcdata.params.iter().map(DataNodeRef::Param);
                let excludes = arcdata.excludes.iter().map(DataNodeRef::Exclude);
                let records = arcdata.witness_records.iter().map(DataNodeRef::WitnessRecord);
                representative.chain(params).chain(excludes).chain(records).try_for_each(visit)
            }
            DataNodeRef::WitnessRecord(WitnessRecord::Alts { alts, .. }) => alts.iter().map(DataNodeRef::AltRecord).try_for_each(visit),
            DataNodeRef::WitnessRecord(WitnessRecord::Approximated { witnesses: list, .. }) => witnesses(list).try_for_each(visit),
            DataNodeRef::AltRecord(alt) => witnesses(&alt.witnesses).chain(alt.nested.iter().map(DataNodeRef::AltRecord)).try_for_each(visit),
            DataNodeRef::Witness(Witness { body: Some(body), .. }) => {
                let relaxed = body.relaxed.iter().map(DataNodeRef::Relaxed);
                let assigns = body.assigns.iter().map(DataNodeRef::Assign);
                let outputs = body.outputs.iter().map(DataNodeRef::WitnessOutput);
                relaxed.chain(assigns).chain([DataNodeRef::Grid(&body.input)]).chain(outputs).try_for_each(visit)
            }
            DataNodeRef::Witness(Witness { body: None, .. })
            | DataNodeRef::Representative(_)
            | DataNodeRef::Param(_)
            | DataNodeRef::Exclude(_)
            | DataNodeRef::Relaxed(_)
            | DataNodeRef::Assign(_)
            | DataNodeRef::Grid(_)
            | DataNodeRef::WitnessOutput(_) => ControlFlow::Continue(()),
        }
    }
}

/// The node at `path` below `root`, or `None` where `path` names no node.
pub fn data_node_at<'a>(root: DataNodeRef<'a>, path: &NodePath) -> Option<DataNodeRef<'a>> {
    descend(root, path)
}
