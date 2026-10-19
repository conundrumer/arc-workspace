//! The columns of a relation's rows, as the sites of a read name them, and
//! the source of each column path of a relation. The columns that the
//! registry declares stand in [`super::registry_columns`], and the columns
//! that each kind of form gives its relation in [`super::form_columns`].

use super::ColumnPosition;
use crate::program::path::{child_index, node_at, NodePath, NodeRef};
use crate::program::{Choose, ColumnName, Demonstrated, Instance, InstanceInput, KeyBody, LabelId, RigidDet, Site, SiteArg};
use crate::registry::ColumnType;
use crate::relations::{ColumnGroup, ColumnIndex};
use crate::types::{each_site_label, use_label};

use crate::read::spelling::KEY;

/// The column of a `RIGID_DET` output that holds the pose,
/// `docs/arclog/rigid.md#semantics`.
const POSE: &str = "Pose";
/// The Example column of a lifted read, `docs/arclog/arclog.md#program`.
const EXAMPLE: &str = "E";

fn written(name: &str) -> ColumnName {
    ColumnName::Written(name.into())
}

/// The name of the key column of a keyed form's relation.
pub(crate) fn key() -> ColumnName {
    written(KEY)
}

/// The name of the Example column of a lifted read.
pub(crate) fn example() -> ColumnName {
    written(EXAMPLE)
}

/// The name of the column of a `RIGID_DET` output that holds the pose.
pub(crate) fn pose() -> ColumnName {
    written(POSE)
}

/// One column of a relation as a site names it: a column of one row
/// position, or a record, one row position per field.
#[derive(Clone, PartialEq, Eq, Debug)]
pub(super) enum Slot {
    Column(ColumnName),
    Record { name: ColumnName, fields: Box<[ColumnName]> },
}

impl Slot {
    fn name(&self) -> &ColumnName {
        match self {
            Slot::Column(name) | Slot::Record { name, .. } => name,
        }
    }

    fn width(&self) -> u16 {
        match self {
            Slot::Column(_) => 1,
            Slot::Record { fields, .. } => fields.len() as u16,
        }
    }

    /// The slot of the column `name` of a head site's port: a record
    /// where `record` gives its fields.
    pub(super) fn of(name: &ColumnName, record: Option<&[ColumnName]>) -> Slot {
        match record {
            Some(fields) => Slot::Record { name: name.clone(), fields: fields.into() },
            None => Slot::Column(name.clone()),
        }
    }
}

/// Where a column path stands in a relation's rows.
#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub(super) enum Place {
    Column(ColumnPosition),
    /// A record's columns, which a site on the record reads.
    Group(ColumnGroup),
    /// A field of a record.
    Field(ColumnPosition, ColumnGroup),
}

/// The columns of a relation, in the order of its rows.
#[derive(Clone, PartialEq, Eq, Debug, Default)]
pub(crate) struct Columns(pub(super) Box<[Slot]>);

impl Columns {
    pub(super) fn of_names(names: impl IntoIterator<Item = ColumnName>) -> Columns {
        Columns(names.into_iter().map(Slot::Column).collect())
    }

    pub(crate) fn names(&self) -> impl Iterator<Item = &ColumnName> + '_ {
        self.0.iter().map(Slot::name)
    }

    /// The place of the column at `path`: a column's name, then, on a
    /// record, a field's. A path past a column of one row position names
    /// that column, as the name of a bare label at a type parameter
    /// bound to one label does.
    pub(super) fn place(&self, path: &[ColumnName]) -> Option<Place> {
        let (first, rest) = path.split_first()?;
        let mut start = 0u16;
        for slot in self.0.iter() {
            if slot.name() == first {
                return match slot {
                    Slot::Column(_) => Some(Place::Column(ColumnPosition(start))),
                    Slot::Record { fields, .. } => {
                        let group = ColumnGroup { start: ColumnIndex(start), len: slot.width() };
                        match rest.first() {
                            None => Some(Place::Group(group)),
                            Some(field) => {
                                let index = fields.iter().position(|f| f == field)?;
                                Some(Place::Field(ColumnPosition(start + index as u16), group))
                            }
                        }
                    }
                };
            }
            start += slot.width();
        }
        None
    }

    /// The columns of the lifted relation, with the Example column
    /// first, as a `DET` reads a `RULE` relation.
    pub(super) fn lifted(&self) -> Columns {
        Columns(std::iter::once(Slot::Column(example())).chain(self.0.iter().cloned()).collect())
    }

    /// Writes the columns: each name, and each record's fields.
    pub(super) fn write(&self, out: &mut crate::program::canonical::CanonicalWriter) {
        out.len(self.0.len());
        for slot in self.0.iter() {
            match slot {
                Slot::Column(name) => {
                    out.write(&[0]);
                    out.name(name);
                }
                Slot::Record { name, fields } => {
                    out.write(&[1]);
                    out.name(name);
                    out.len(fields.len());
                    for field in fields.iter() {
                        out.name(field);
                    }
                }
            }
        }
    }
}

/// The fields of the record that the head site `site` projects onto
/// its column's type parameter, or `None` where it projects one label.
pub(crate) fn projection(site: &Site) -> Option<Box<[ColumnName]>> {
    match &site.value.args[..] {
        [SiteArg::Label(_) | SiteArg::NamedLabel { .. }] => None,
        args => Some(
            args.iter()
                .filter_map(|arg| match arg {
                    SiteArg::NamedLabel { name, .. } => Some(name.clone()),
                    SiteArg::Field(field) => Some(field.column.clone()),
                    SiteArg::Label(_) => None,
                })
                .collect(),
        ),
    }
}

pub(super) fn key_fields(key: &KeyBody) -> Box<[ColumnName]> {
    key.columns.iter().map(|column| column.name.clone()).collect()
}

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
    let first = NodePath::default().child(0);
    match form {
        NodeRef::Instance(Instance { key: Some(key), .. }) | NodeRef::Demonstrated(Demonstrated { key: Some(key), .. }) => {
            Some((&key.value().key, first.child(0)))
        }
        NodeRef::RigidDet(RigidDet { key: Some(key), .. }) | NodeRef::Choose(Choose { rows: Some(key), .. }) => Some((key, first)),
        _ => None,
    }
}

/// The sources of the fields of `key`, whose body is at `body`, each
/// path from the field's name.
pub(super) fn key_sources(key: &KeyBody, body: &NodePath) -> Vec<Sourced> {
    key.columns.iter().map(|column| (Box::from([column.name.clone()]), Source::Label { label: column.label, body: body.clone() })).collect()
}

/// The `key` slot of the relation of a keyed form: the record of its key
/// clause's fields, or one column where it has none.
pub(super) fn key_listed(key: Option<(&KeyBody, NodePath)>) -> Listed {
    match key {
        Some((key, body)) => Listed { slot: Slot::of(&self::key(), Some(&key_fields(key))), sources: below(&self::key(), key_sources(key, &body)) },
        None => Listed { slot: Slot::Column(self::key()), sources: Vec::new() },
    }
}

/// The path below `form` of the body of `input`, an input of `form`
/// written after the form's key clause or inside it.
pub(super) fn input_body(form: NodeRef<'_>, input: &InstanceInput) -> NodePath {
    let child = NodeRef::InstanceInput(input);
    let path = match child_index(form, child) {
        Some(index) => NodePath::default().child(index),
        None => {
            let key = NodePath::default().child(0);
            let clause = node_at(form, &key).expect("the key clause of a form whose input stands inside it");
            key.child(child_index(clause, child).expect("an input of the form, after its key clause or inside it"))
        }
    };
    path.child(u32::try_from(input.head.len()).expect("a head of fewer than 2^32 sites"))
}
