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
//! | site | the field sites, where it reads a record |
//! | `INIT` form | the key clause where it has one, then the inputs after it |
//! | key clause | the body, then the inputs inside it |
//! | input | the head sites, then the body |
//! | `CHOOSE` form | the `for` body where it has one, the `from` body, the `never` bodies |
//! | `RIGID_DET` form | the `key` body, the `instance` body, each where it has one, then the parts |
//! | `DEMONSTRATED` form | the key clause where it has one, the inputs after it, the `DEMO_RULE` forms |
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
//!
//! The programs-as-values stage writes the bodies.

#![allow(unused_variables, dead_code)]

use super::{
    AltRecord, Alt, Alts, Arcdata, Atom, Body, Choose, Claim, Clause, Conjunct, DemoRule,
    Demonstrated, Exclude, Grid, InstanceInput, Instance, KeyClause, Node, Param, ParamValue, Program,
    Representative, RigidDet, Site, Slug, Witness, WitnessOutput, WitnessRecord, ProgramRelation,
};

/// One step of a path: the index of a node among its parent's children.
#[derive(Clone, Copy, PartialEq, Eq, Hash, Debug)]
pub struct PathStep(pub u32);

/// The path of a node: the index of its top-level form, then its index
/// among the children of each node below that form.
///
/// A path is relative to the node it starts from: a program's path starts
/// at the program, and the path of a [`crate::check::Refusal`] at the form
/// the check read.
#[derive(Clone, PartialEq, Eq, Hash, Debug, Default)]
pub struct NodePath(pub Box<[PathStep]>);

impl NodePath {
    /// The path of the node at `relative` below the node at `self`.
    pub fn join(&self, relative: &NodePath) -> NodePath {
        todo!()
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
}

impl<'a> NodeRef<'a> {
    /// The node's children, in the order of the module comment's table.
    pub fn children(self) -> Vec<NodeRef<'a>> {
        todo!()
    }
}

/// The node at `path` below `root`, or `None` where `path` names no node.
pub fn node_at<'a>(root: NodeRef<'a>, path: &NodePath) -> Option<NodeRef<'a>> {
    todo!()
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
        todo!()
    }
}

/// The node at `path` below `root`, or `None` where `path` names no node.
pub fn data_node_at<'a>(root: DataNodeRef<'a>, path: &NodePath) -> Option<DataNodeRef<'a>> {
    todo!()
}
