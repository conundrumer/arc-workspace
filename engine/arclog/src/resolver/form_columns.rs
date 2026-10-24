//! The columns that each kind of form gives its relation, each slot with
//! the source of each column path at it: an `INIT` form's ports, a
//! `DEMONSTRATED` form's relation, a `RIGID_DET` form's outputs, and the
//! relation of a clause or a `CHOOSE` form.

use std::sync::Arc;

use super::column_sources::{below, input_body, key_clause, key_listed, key_sources, site_sources, Listed, Listing, Source, Sourced};
use super::columns::{key_fields, pose, projection, Columns, Slot};
use crate::hash::StableHashMap;
use crate::program::path::{NodePath, NodeRef};
use crate::program::{
    Choose, ChoosePart, ColumnName, DeclaredName, Demonstrated, Instance, InstanceName, OutputOwner, OutputStep, RelationColumn, RelationName, RelationRef,
    RigidDet, RigidDetName, Site, SiteArg,
};
use crate::registry::{binding_sites, ColumnType, Component, ParameterSite, Port, TypeParameter};
use crate::types::use_label;

/// The input of a `DEMONSTRATED` form whose head gives the relation's
/// columns after the key's, `docs/arclog/arclog.md#demonstrated`.
const VALUE: &str = "value";

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

/// The columns of `port` of an instance whose binding is `bindings`, with a
/// key clause where `keyed` holds and otherwise with no `key` column:
/// each column's declared type, and below a column of a type
/// parameter, the sources of the parameter's binding.
pub(super) fn port_columns(port: &Port, bindings: &Bindings, keyed: bool) -> Listing {
    let listed = port.columns_at(keyed).map(|column| {
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
    Listing(key.into_iter().chain(heads).collect())
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
/// clause has no `key` column.
pub(crate) fn rigid_outputs(form: &RigidDet) -> Vec<(Arc<[OutputStep]>, Columns)> {
    rigid_listings(form).into_iter().map(|(steps, listing)| (steps, listing.columns())).collect()
}

/// Whether `site`, a site of a part of `form`, holds a bare label of the
/// form's `instance` clause. Such a site selects the part's rows at an
/// instance, and the part's outputs have no column at it, as
/// `docs/arclog/rigid.md#semantics` gives.
pub(crate) fn at_instance(form: &RigidDet, site: &Site) -> bool {
    let [SiteArg::Label(label)] = &site.value.args[..] else { return false };
    let instance = form.instance.iter().flat_map(|instance| instance.columns.iter());
    use_label(*label).is_some_and(|label| instance.map(|column| column.label).any(|column| column == label))
}

/// The listing of each output of a `RIGID_DET` form, by its path after the
/// form's name: the `key` slot; for a part, `:Pose` and then the part's
/// columns other than those at a site that [`at_instance`] gives; for
/// `.pose`, the instance's columns and then `:Pose`. A label at a part's
/// site or among the instance's columns is bound by the form.
pub(super) fn rigid_listings(form: &RigidDet) -> Vec<(Arc<[OutputStep]>, Listing)> {
    let whole = NodePath::default();
    let key = key_listed(key_clause(NodeRef::RigidDet(form)));
    let pose = Listed { slot: Slot::Column(pose()), sources: vec![(Box::from([pose()]), Source::Declared(ColumnType::Pose))] };
    let mut outputs: Vec<(Arc<[OutputStep]>, Listing)> = form
        .parts
        .iter()
        .filter_map(|part| {
            let part = part.value();
            let steps = part_steps(&part.relation)?;
            let sites = part.sites.iter().filter(|site| !at_instance(form, site)).map(|site| Listed { slot: Slot::Column(site.column.clone()), sources: site_sources(site, true, &whole) });
            Some((steps.into(), Listing(key.iter().cloned().chain([pose.clone()]).chain(sites).collect())))
        })
        .collect();
    let instance = form.instance.iter().flat_map(|instance| instance.columns.iter()).map(|column| Listed {
        slot: Slot::Column(column.name.clone()),
        sources: vec![(Box::from([column.name.clone()]), Source::Label { label: column.label, body: whole.clone() })],
    });
    outputs.push((Arc::from([OutputStep::Pose]), Listing(key.into_iter().chain(instance).chain([pose]).collect())));
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
            let from = NodePath::default().child(choose.position(ChoosePart::From));
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
