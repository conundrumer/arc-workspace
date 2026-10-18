//! The columns of a relation's rows, as the sites of a read name them, and
//! the source of each column path of a relation. The columns that the
//! registry declares stand in [`super::registry_columns`].

use std::sync::Arc;

use super::ColumnPosition;
use crate::hash::StableHashMap;
use crate::program::path::{child_index, node_at, NodePath, NodeRef};
use crate::program::{
    Choose, ColumnName, DeclaredName, Demonstrated, Instance, InstanceInput, InstanceName, KeyBody, LabelId, OutputOwner,
    OutputStep, RelationColumn, RelationName, RelationRef, RigidDet, RigidDetName, Site, SiteArg,
};
use crate::registry::{binding_sites, ColumnType, Component, ParameterSite, Port, TypeParameter};
use crate::relations::{ColumnGroup, ColumnIndex};
use crate::types::{each_site_label, use_label};

use crate::read::spelling::KEY;

/// The column of a `RIGID_DET` output that holds the pose,
/// `docs/arclog/rigid.md#semantics`.
const POSE: &str = "Pose";
/// The Example column of a lifted read, `docs/arclog/arclog.md#program`.
const EXAMPLE: &str = "E";
/// The input of a `DEMONSTRATED` form whose head gives the relation's
/// columns after the key's, `docs/arclog/arclog.md#demonstrated`.
const VALUE: &str = "value";

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
    fn of(name: &ColumnName, record: Option<&[ColumnName]>) -> Slot {
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

fn key_fields(key: &KeyBody) -> Box<[ColumnName]> {
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
    slot: Slot,
    sources: Vec<Sourced>,
}

/// The slots of a relation's columns, in the order of its rows, each
/// with its sources. The relation's [`Columns`] derive from it.
#[derive(Clone, Debug)]
pub(super) struct Listing(Vec<Listed>);

impl Listing {
    pub(super) fn columns(&self) -> Columns {
        Columns(self.0.iter().map(|listed| listed.slot.clone()).collect())
    }

    pub(super) fn sources(&self) -> impl Iterator<Item = &Sourced> + '_ {
        self.0.iter().flat_map(|listed| listed.sources.iter())
    }
}

/// `sources` below the column `column`.
fn below(column: &ColumnName, sources: impl IntoIterator<Item = Sourced>) -> Vec<Sourced> {
    sources.into_iter().map(|(path, source)| (std::iter::once(column.clone()).chain(path).collect(), source)).collect()
}

/// The labels at the site `site`, each with its column path from the
/// site's column, or with the site's column alone where `whole` holds,
/// bound by the body at `body`.
fn site_sources(site: &Site, whole: bool, body: &NodePath) -> Vec<Sourced> {
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
fn key_sources(key: &KeyBody, body: &NodePath) -> Vec<Sourced> {
    key.columns.iter().map(|column| (Box::from([column.name.clone()]), Source::Label { label: column.label, body: body.clone() })).collect()
}

/// The `key` slot of the relation of a keyed form: the record of its key
/// clause's fields, or one column where it has none.
fn key_listed(key: Option<(&KeyBody, NodePath)>) -> Listed {
    match key {
        Some((key, body)) => Listed { slot: Slot::of(&self::key(), Some(&key_fields(key))), sources: below(&self::key(), key_sources(key, &body)) },
        None => Listed { slot: Slot::Column(self::key()), sources: Vec::new() },
    }
}

/// The path below `form` of the body of `input`, an input of `form`
/// written after the form's key clause or inside it.
fn input_body(form: NodeRef<'_>, input: &InstanceInput) -> NodePath {
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

/// What an `INIT` form binds a type parameter of its component to: the
/// record of fields of a column of the parameter, where it has one, and
/// the source of each path below such a column.
struct Binding {
    record: Option<Box<[ColumnName]>>,
    sources: Vec<Sourced>,
}

/// What an `INIT` form binds each type parameter of its component to,
/// at the place that [`crate::registry::binding_sites`] gives. A
/// parameter that the map leaves out takes one column, with no source
/// below it.
pub(super) struct Bindings(StableHashMap<TypeParameter, Binding>);

pub(super) fn bindings(instance: &Instance, component: &Component) -> Bindings {
    let form = NodeRef::Instance(instance);
    let records = binding_sites(instance, &component.inputs).into_iter().map(|sites| {
        let binding = match sites.binding {
            ParameterSite::Key(_) => {
                let (key, body) = key_clause(form).expect("the key clause of an `INIT` form whose key binds a parameter");
                Binding { record: Some(key_fields(key)), sources: key_sources(key, &body) }
            }
            ParameterSite::Head { input, site } => {
                let record = projection(site);
                let sources = site_sources(site, record.is_none(), &input_body(form, input));
                Binding { record, sources: sources.into_iter().map(|(path, source)| (path[1..].into(), source)).collect() }
            }
        };
        (sites.parameter.clone(), binding)
    });
    Bindings(records.collect())
}

/// The columns of `port` of an instance whose binding is `bindings`:
/// each column's declared type, and below a column of a type
/// parameter, the sources of the parameter's binding.
pub(super) fn port_columns(port: &Port, bindings: &Bindings) -> Listing {
    let listed = port.columns.iter().map(|column| {
        let binding = match &column.ty {
            ColumnType::Parameter(parameter) => bindings.0.get(parameter),
            _ => None,
        };
        let mut sources = vec![(Box::from([column.name.clone()]), Source::Declared(column.ty.clone()))];
        sources.extend(binding.into_iter().flat_map(|binding| below(&column.name, binding.sources.iter().cloned())));
        Listed { slot: Slot::of(&column.name, binding.and_then(|binding| binding.record.as_deref())), sources }
    });
    Listing(listed.collect())
}

/// The columns of a `DEMONSTRATED` form's relation,
/// `docs/arclog/arclog.md#demonstrated`.
pub(crate) fn demonstrated_columns(form: &Demonstrated) -> Columns {
    demonstrated_listing(form).columns()
}

/// The listing of a `DEMONSTRATED` form's relation: the `key` slot, then
/// a slot per head site of the `value` input, with the labels the site
/// writes, which the input's body binds.
pub(super) fn demonstrated_listing(form: &Demonstrated) -> Listing {
    let at = NodeRef::Demonstrated(form);
    let key = key_listed(key_clause(at));
    let heads = demonstrated_value(form).into_iter().flat_map(|input| {
        let body = input_body(at, input);
        input.head.iter().map(move |site| {
            let record = projection(site);
            let sources = site_sources(site, record.is_none(), &body);
            Listed { slot: Slot::of(&site.column, record.as_deref()), sources }
        })
    });
    Listing(std::iter::once(key).chain(heads).collect())
}

/// The `value` input of a `DEMONSTRATED` form, whose head names the
/// relation's columns after the key's.
pub(crate) fn demonstrated_value(form: &Demonstrated) -> Option<&crate::program::InstanceInput> {
    crate::program::written_inputs(form.key.as_ref(), &form.inputs).find(|input| *input.name.0 == *VALUE)
}

/// The path after the form's name of the output of a `RIGID_DET` form
/// for the part that reads `relation`: `&marker.glyph` for a part that
/// reads `&glyph`, `&marker.bbox.box` for one that reads `&bbox.box`.
pub(crate) fn part_steps(relation: &RelationRef) -> Option<Vec<OutputStep>> {
    let (owner, rest): (&DeclaredName, &[OutputStep]) = match relation {
        RelationRef::Declared(RelationName(name)) => (name, &[]),
        RelationRef::Output(output) => match &output.of {
            OutputOwner::Instance(InstanceName(name)) | OutputOwner::RigidDet(RigidDetName(name)) => (name, &output.path[..]),
        },
        RelationRef::Fact(_) | RelationRef::Lib(_) | RelationRef::DefinedPort(_) => return None,
    };
    Some(std::iter::once(OutputStep::Part(owner.clone())).chain(rest.iter().cloned()).collect())
}

/// Each output of a `RIGID_DET` form, by its path after the form's name, with
/// its columns, as `docs/arclog/rigid.md#semantics` gives. A form with no key
/// clause has one `key` column, as an instance with no key clause has.
pub(crate) fn rigid_outputs(form: &RigidDet) -> Vec<(Arc<[OutputStep]>, Columns)> {
    rigid_listings(form).into_iter().map(|(steps, listing)| (steps, listing.columns())).collect()
}

/// The listing of each output of a `RIGID_DET` form, by its path after the
/// form's name: the `key` slot; for a part, `:Pose` and then the part's
/// columns; for `.pose`, the instance's columns and then `:Pose`. A label
/// at a part's site or among the instance's columns is bound by the form.
pub(super) fn rigid_listings(form: &RigidDet) -> Vec<(Arc<[OutputStep]>, Listing)> {
    let whole = NodePath::default();
    let key = key_listed(key_clause(NodeRef::RigidDet(form)));
    let pose = Listed { slot: Slot::Column(self::pose()), sources: vec![(Box::from([self::pose()]), Source::Declared(ColumnType::Pose))] };
    let mut outputs: Vec<(Arc<[OutputStep]>, Listing)> = form
        .parts
        .iter()
        .filter_map(|part| {
            let part = part.value();
            let steps = part_steps(&part.relation)?;
            let sites = part.sites.iter().map(|site| Listed { slot: Slot::Column(site.column.clone()), sources: site_sources(site, true, &whole) });
            Some((steps.into(), Listing([key.clone(), pose.clone()].into_iter().chain(sites).collect())))
        })
        .collect();
    let instance = form.instance.iter().flat_map(|instance| instance.columns.iter()).map(|column| Listed {
        slot: Slot::Column(column.name.clone()),
        sources: vec![(Box::from([column.name.clone()]), Source::Label { label: column.label, body: whole.clone() })],
    });
    outputs.push((Arc::from([OutputStep::Pose]), Listing(std::iter::once(key).chain(instance).chain([pose]).collect())));
    outputs
}

/// The columns that `form` gives the rows of its node, each with the path
/// below the form of the body that binds its label: a clause's, or a
/// `CHOOSE` form's row columns and then its candidate's.
fn bound_columns(form: NodeRef<'_>) -> Vec<(&RelationColumn, NodePath)> {
    match form {
        NodeRef::Clause(clause) => clause.columns.iter().map(|column| (column, NodePath::default().child(0))).collect(),
        NodeRef::Choose(choose) => {
            let rows = key_clause(form).into_iter().flat_map(|(rows, body)| rows.columns.iter().map(move |column| (column, body.clone())));
            let from = NodePath::default().child(u32::from(choose.rows.is_some()));
            rows.chain(choose.candidate_columns.iter().map(|column| (column, from.clone()))).collect()
        }
        _ => Vec::new(),
    }
}

/// The columns that `form` gives the rows of its node, as
/// [`bound_columns`] gives them.
pub(crate) fn form_columns<'f>(form: NodeRef<'f>) -> Box<dyn Iterator<Item = &'f RelationColumn> + 'f> {
    Box::new(bound_columns(form).into_iter().map(|(column, _)| column))
}

/// The listing of the relation of a clause or a `CHOOSE` form: a column per
/// column that [`form_columns`] gives, with its label.
pub(super) fn form_listing(form: NodeRef<'_>) -> Listing {
    let listed = bound_columns(form).into_iter().map(|(column, body)| Listed {
        slot: Slot::Column(column.name.clone()),
        sources: vec![(Box::from([column.name.clone()]), Source::Label { label: column.label, body })],
    });
    Listing(listed.collect())
}

/// The row columns of a chosen relation, in the order of the `for`
/// clause, which come before the candidate's.
pub(super) fn row_columns(choose: &Choose) -> impl Iterator<Item = &RelationColumn> + '_ {
    choose.rows.iter().flat_map(|rows| rows.columns.iter())
}
