//! The source of each column path of a relation: the label that a form
//! writes at the path and the body that binds it, or the column's declared
//! type, and the slots of a relation's columns, each with its sources.

use super::columns::{self, key_fields, Columns, Slot};
use crate::program::path::{child_index, NodePath, NodeRef};
use crate::program::{
    Choose, ChoosePart, ColumnName, Demonstrated, DemonstratedPart, Instance, InstanceInput, InstanceInputPart, InstancePart, KeyBody, KeyClause,
    KeyClausePart, LabelId, Node, RigidDet, RigidDetPart, Site,
};
use crate::registry::ColumnType;
use crate::types::{each_site_label, use_label};

/// What gives the value at a column path of a relation.
#[derive(Clone, Debug)]
pub(super) enum Source {
    /// A label that the form giving the relation writes at the path,
    /// which the body at `body`, a path below the form, binds.
    Label { label: LabelId, body: NodePath },
    /// The column's declared type.
    Declared(ColumnType),
}

/// A column path of a relation, from a column's name, with its source.
pub(super) type Sourced = (Box<[ColumnName]>, Source);

/// One slot of a relation's columns, with the source of each column
/// path at it or below it.
#[derive(Clone, Debug)]
pub(super) struct Listed {
    pub(super) slot: Slot,
    pub(super) sources: Vec<Sourced>,
}

/// The slots of a relation's columns, in the order of its rows, each
/// with its sources. The relation's [`Columns`] derive from it.
#[derive(Clone, Debug)]
pub(super) struct Listing(pub(super) Vec<Listed>);

impl Listing {
    pub(super) fn columns(&self) -> Columns {
        Columns(self.0.iter().map(|listed| listed.slot.clone()).collect())
    }

    pub(super) fn sources(&self) -> impl Iterator<Item = &Sourced> + '_ {
        self.0.iter().flat_map(|listed| listed.sources.iter())
    }
}

/// `sources` below the column `column`.
pub(super) fn below(column: &ColumnName, sources: impl IntoIterator<Item = Sourced>) -> Vec<Sourced> {
    sources.into_iter().map(|(path, source)| (std::iter::once(column.clone()).chain(path).collect(), source)).collect()
}

/// The labels at the site `site`, each with its column path from the
/// site's column, or with the site's column alone where `whole` holds,
/// bound by the body at `body`.
pub(super) fn site_sources(site: &Site, whole: bool, body: &NodePath) -> Vec<Sourced> {
    let mut found = Vec::new();
    each_site_label(site, &mut Vec::new(), &mut |use_, path| {
        if let Some(label) = use_label(use_) {
            let path: Box<[ColumnName]> = if whole { Box::from([site.column.clone()]) } else { path.into() };
            found.push((path, Source::Label { label, body: body.clone() }));
        }
    });
    found
}

/// The key clause of the form `form`, with the path below the form of
/// the body whose `^` labels are its columns: the `key` of an `INIT`, a
/// `DEMONSTRATED` or a `RIGID_DET` form, or the `for` of a `CHOOSE`
/// form; none where the form has no key clause.
pub(crate) fn key_clause(form: NodeRef<'_>) -> Option<(&KeyBody, NodePath)> {
    /// The body of `clause`, the child at `position` of the form, with its path.
    fn clause(clause: &Node<KeyClause>, position: u32) -> (&KeyBody, NodePath) {
        (&clause.value().key, NodePath::default().child(position).child(clause.value().position(KeyClausePart::Body)))
    }
    let at = NodePath::default();
    match form {
        NodeRef::Instance(instance @ Instance { key: Some(key), .. }) => Some(clause(key, instance.position(InstancePart::Key))),
        NodeRef::Demonstrated(demonstrated @ Demonstrated { key: Some(key), .. }) => Some(clause(key, demonstrated.position(DemonstratedPart::Key))),
        NodeRef::RigidDet(rigid @ RigidDet { key: Some(key), .. }) => Some((key, at.child(rigid.position(RigidDetPart::Key)))),
        NodeRef::Choose(choose @ Choose { rows: Some(rows), .. }) => Some((rows, at.child(choose.position(ChoosePart::For)))),
        _ => None,
    }
}

/// The sources of the fields of `key`, whose body is at `body`, each
/// path from the field's name.
pub(super) fn key_sources(key: &KeyBody, body: &NodePath) -> Vec<Sourced> {
    key.columns.iter().map(|column| (Box::from([column.name.clone()]), Source::Label { label: column.label, body: body.clone() })).collect()
}

/// The `key` slot of the relation of a keyed form: the record of its key
/// clause's fields, and none where it has no key clause.
pub(super) fn key_listed(key: Option<(&KeyBody, NodePath)>) -> Option<Listed> {
    key.map(|(key, body)| Listed { slot: Slot::of(&columns::key(), Some(&key_fields(key))), sources: below(&columns::key(), key_sources(key, &body)) })
}

/// The path below `form` of the body of `input`, an input of `form`
/// written after the form's key clause or inside it.
pub(super) fn input_body(form: NodeRef<'_>, input: &InstanceInput) -> NodePath {
    let child = NodeRef::InstanceInput(input);
    let path = match child_index(form, child) {
        Some(index) => NodePath::default().child(index),
        None => {
            let children = form.children();
            let key = children.iter().position(|node| matches!(node, NodeRef::KeyClause(_))).expect("the key clause of a form whose input stands inside it");
            let inner = child_index(children[key], child).expect("an input of the form, after its key clause or inside it");
            NodePath::default().child(u32::try_from(key).expect("a form of fewer than 2^32 children")).child(inner)
        }
    };
    path.child(input.position(InstanceInputPart::Body))
}
