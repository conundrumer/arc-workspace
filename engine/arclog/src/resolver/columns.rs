//! The columns of a relation's rows, as the sites of a read name them.

use std::sync::Arc;

use super::ColumnPosition;
use crate::hash::StableHashMap;
use crate::program::{
    ColumnName, DeclaredName, Demonstrated, Instance, InstanceName, KeyBody, OutputOwner, OutputStep,
    RelationName, RelationRef, RigidDet, RigidDetName, Site, SiteArg,
};
use crate::registry::{binding_sites, Column, ColumnType, Component, LibEntry, LibName, Macro, ParameterSite, Port, Proposer, Registry, TypeParameter};
use crate::relations::{ColumnGroup, ColumnIndex};

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
pub(super) fn key() -> ColumnName {
    written(KEY)
}

/// The name of the Example column of a lifted read.
pub(super) fn example() -> ColumnName {
    written(EXAMPLE)
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
pub(super) struct Columns(pub(super) Box<[Slot]>);

impl Columns {
    pub(super) fn of_names(names: impl IntoIterator<Item = ColumnName>) -> Columns {
        Columns(names.into_iter().map(Slot::Column).collect())
    }

    pub(super) fn names(&self) -> impl Iterator<Item = &ColumnName> + '_ {
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
                    out.column(name);
                }
                Slot::Record { name, fields } => {
                    out.write(&[1]);
                    out.column(name);
                    out.len(fields.len());
                    for field in fields.iter() {
                        out.column(field);
                    }
                }
            }
        }
    }
}

fn of_columns(columns: &[Column]) -> Columns {
    Columns::of_names(columns.iter().map(|column| column.name.clone()))
}

/// The columns of a lib relation or a proposer that an atom reads.
pub(super) fn lib_columns(registry: &Registry, name: &LibName) -> Option<Columns> {
    match registry.entry(name)? {
        LibEntry::Relation(relation) | LibEntry::Macro(Macro::Relation { relation, .. }) => Some(of_columns(&relation.columns)),
        LibEntry::Proposer(Proposer::Native { columns }) => Some(of_columns(columns)),
        LibEntry::Proposer(Proposer::Arclog { columns, .. }) => Some(Columns::of_names(columns.iter().cloned())),
        LibEntry::Component(_) => None,
    }
}

/// The names of `columns` of the type `Example`.
pub(super) fn examples(columns: &[Column]) -> impl Iterator<Item = ColumnName> + '_ {
    columns.iter().filter(|column| column.ty == ColumnType::Fixed(crate::types::ValueType::Example)).map(|column| column.name.clone())
}

/// The declared columns, with their types, of the fact, the lib
/// relation, the relation macro or the native proposer that `relation`
/// names.
pub(super) fn typed_columns<'r>(registry: &'r Registry, relation: &RelationRef) -> Option<&'r [Column]> {
    match relation {
        RelationRef::Fact(fact) => Some(registry.fact_columns(*fact)),
        RelationRef::Lib(name) => match registry.entry(name)? {
            LibEntry::Relation(relation) | LibEntry::Macro(Macro::Relation { relation, .. }) => Some(&relation.columns),
            LibEntry::Proposer(Proposer::Native { columns }) => Some(columns),
            LibEntry::Proposer(Proposer::Arclog { .. }) | LibEntry::Component(_) => None,
        },
        RelationRef::Declared(_) | RelationRef::Output(_) | RelationRef::DefinedPort(_) => None,
    }
}

/// The columns of a proposer or a fixed derivation that a `DET` names,
/// in the proposer's order.
pub(super) fn proposer_columns(registry: &Registry, name: &LibName) -> Option<Box<[ColumnName]>> {
    match registry.entry(name) {
        Some(LibEntry::Proposer(Proposer::Native { columns })) => Some(columns.iter().map(|c| c.name.clone()).collect()),
        Some(LibEntry::Proposer(Proposer::Arclog { columns, .. })) => Some(columns.clone()),
        _ => registry.derivation(name).map(|derivation| derivation.columns.iter().map(|c| c.name.clone()).collect()),
    }
}

/// Whether `name` is a proposer or a fixed derivation that a `DET` can
/// name.
pub(super) fn is_proposer(registry: &Registry, name: &LibName) -> bool {
    matches!(registry.entry(name), Some(LibEntry::Proposer(_))) || registry.derivation(name).is_some()
}

/// The component an `INIT` form names: a construction, a detector or a
/// task-structure component.
pub(super) fn component<'r>(registry: &'r Registry, name: &LibName) -> Option<&'r Component> {
    match registry.entry(name)? {
        LibEntry::Component(component) => Some(component),
        LibEntry::Relation(_) | LibEntry::Proposer(_) | LibEntry::Macro(Macro::Relation { .. }) => None,
    }
}

/// The fields of the record that the head site `site` projects onto
/// its column's type parameter, or `None` where it projects one label.
pub(super) fn projection(site: &Site) -> Option<Box<[ColumnName]>> {
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

/// The record of fields that an `INIT` form binds each type parameter
/// of its component to, at the place that
/// [`crate::registry::binding_sites`] gives. A parameter that the map
/// leaves out takes one column.
pub(super) struct Bindings(StableHashMap<TypeParameter, Box<[ColumnName]>>);

pub(super) fn bindings(instance: &Instance, component: &Component) -> Bindings {
    let records = binding_sites(instance, &component.inputs).into_iter().filter_map(|sites| {
        let fields = match sites.binding {
            ParameterSite::Key(key) => key_fields(&key.key),
            ParameterSite::Head { site, .. } => projection(site)?,
        };
        Some((sites.parameter.clone(), fields))
    });
    Bindings(records.collect())
}

/// The columns of `port` of an instance whose binding is `bindings`.
pub(super) fn port_columns(port: &Port, bindings: &Bindings) -> Columns {
    Columns(
        port.columns
            .iter()
            .map(|column| match &column.ty {
                ColumnType::Parameter(parameter) => Slot::of(&column.name, bindings.0.get(parameter).map(|f| &f[..])),
                _ => Slot::Column(column.name.clone()),
            })
            .collect(),
    )
}

fn key_slot(key: Option<&KeyBody>) -> Slot {
    Slot::of(&self::key(), key.map(key_fields).as_deref())
}

/// The columns of a `DEMONSTRATED` form's relation,
/// `docs/arclog/arclog.md#demonstrated`.
pub(super) fn demonstrated_columns(form: &Demonstrated) -> Columns {
    let key = key_slot(form.key.as_ref().map(|key| &key.value().key));
    let heads = demonstrated_value(form).into_iter().flat_map(|input| input.head.iter()).map(|site| Slot::of(&site.column, projection(site).as_deref()));
    Columns(std::iter::once(key).chain(heads).collect())
}

/// The `value` input of a `DEMONSTRATED` form, whose head names the
/// relation's columns after the key's.
pub(super) fn demonstrated_value(form: &Demonstrated) -> Option<&crate::program::InstanceInput> {
    crate::program::written_inputs(form.key.as_ref(), &form.inputs).find(|input| *input.name.0 == *VALUE)
}

/// The path after the form's name of the output of a `RIGID_DET` form
/// for the part that reads `relation`: `&marker.glyph` for a part that
/// reads `&glyph`, `&marker.bbox.box` for one that reads `&bbox.box`.
fn part_steps(relation: &RelationRef) -> Option<Vec<OutputStep>> {
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
pub(super) fn rigid_outputs(form: &RigidDet) -> Vec<(Arc<[OutputStep]>, Columns)> {
    let key = key_slot(form.key.as_ref());
    let pose = Slot::Column(written(POSE));
    let mut outputs: Vec<(Arc<[OutputStep]>, Columns)> = form
        .parts
        .iter()
        .filter_map(|part| {
            let part = part.value();
            let steps = part_steps(&part.relation)?;
            let sites = part.sites.iter().map(|site| Slot::Column(site.column.clone()));
            Some((steps.into(), Columns([key.clone(), pose.clone()].into_iter().chain(sites).collect())))
        })
        .collect();
    let instance = form.instance.iter().flat_map(|instance| instance.columns.iter()).map(|column| Slot::Column(column.name.clone()));
    outputs.push((Arc::from([OutputStep::Pose]), Columns(std::iter::once(key).chain(instance).chain([pose]).collect())));
    outputs
}
