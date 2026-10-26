//! The relations that the forms of a node of the dependency graph give it,
//! each with the labels written at its columns and the body that binds each
//! label, and the relation that a node stands for. The column flows of the
//! crate `arclog-tables` read these.

use std::sync::Arc;

use super::column_sources::{input_body, Listing, Source};
use super::columns::{Columns, Place, Slot};
use super::registry_columns;
use super::{form_columns, ColumnPosition, DependencyKind, GraphNodeIndex, ResolvedProgram};
use crate::program::path::{node_at, NodePath, NodeRef};
use crate::program::{written_inputs, LabelId, OutputName, OutputOwner, OutputStep, ProgramRelation, RelationRef};
use crate::registry::{is_key, ColumnType, LibName, Registry};

/// A label that a form writes at a column of a relation.
#[derive(Clone, Debug)]
pub struct GivenLabel {
    pub label: LabelId,
    /// The path below the form of the body that binds the label.
    pub body: NodePath,
    /// The row position of the column path the label stands at, where the
    /// relation's columns place it.
    pub place: Option<usize>,
}

/// One column of a relation that a form gives: the row positions it takes,
/// whether it is the `key` column, its declared type, and the labels written
/// at its paths.
#[derive(Clone, Debug)]
pub struct GivenSlot {
    pub is_key: bool,
    pub width: usize,
    pub declared: Option<ColumnType>,
    pub labels: Vec<GivenLabel>,
}

/// The relation that a node of the graph stands for, where a read names
/// it.
/// The relation that a node of the graph stands for, where a read names
/// it.
pub fn node_relation(kind: &DependencyKind) -> Option<RelationRef> {
    let of = |relation: &ProgramRelation| match relation {
        ProgramRelation::Declared(name) => RelationRef::Declared(name.clone()),
        ProgramRelation::Output(name) => RelationRef::Output(name.clone()),
    };
    let port = |instance: &crate::program::InstanceName, port: &crate::program::PortName| {
        RelationRef::Output(OutputName { of: OutputOwner::Instance(instance.clone()), path: Arc::from([OutputStep::Port(port.clone())]) })
    };
    match kind {
        DependencyKind::Fact(fact) => Some(RelationRef::Fact(*fact)),
        DependencyKind::Clause(relation) | DependencyKind::Parameter(relation) => Some(of(relation)),
        DependencyKind::Chosen(name) | DependencyKind::Demonstrated(name) => Some(RelationRef::Declared(name.clone())),
        DependencyKind::InstanceInput { instance, input: name } | DependencyKind::InstanceOutput { instance, output: name } => Some(port(instance, name)),
        DependencyKind::RigidAssembly(_) | DependencyKind::RecursiveInstance(_) => None,
    }
}

/// A relation that a form gives a node: the form's path, the relation's
/// path after the form's name where the form gives several, and its columns.
pub struct Given {
    pub form: NodePath,
    pub output: Option<Arc<[OutputStep]>>,
    pub slots: Vec<GivenSlot>,
    /// The lib name that gives the relation's rows where the form reads no
    /// program relation: the proposers of a clause, or the component of an
    /// instance.
    pub lib: Vec<LibName>,
    /// The index among the columns of its first one that a part site of a
    /// `RIGID_DET` assembly gives; the entries before are the key's and
    /// `:Pose`. Beyond the columns for any other relation.
    pub sites_from: usize,
    /// For an output port of a keyed instance, each `from-key` input that the
    /// instance writes no clause for, which the engine fills from the key:
    /// its index among the component's inputs, and the declared types of its
    /// columns other than `key`.
    pub filled: Vec<(usize, Vec<ColumnType>)>,
}

/// The columns of `listing`, each with its row positions and labels.
fn slots(listing: &Listing) -> Vec<GivenSlot> {
    let columns = listing.columns();
    listing
        .0
        .iter()
        .map(|listed| {
            let declared = listed.sources.iter().find_map(|(_, source)| match source {
                Source::Declared(ty) => Some(ty.clone()),
                Source::Label { .. } => None,
            });
            let labels = listed
                .sources
                .iter()
                .filter_map(|(path, source)| match source {
                    Source::Label { label, body } => Some(GivenLabel { label: *label, body: body.clone(), place: place(&columns, path) }),
                    Source::Declared(_) => None,
                })
                .collect();
            GivenSlot { is_key: listed.slot.name() == &super::columns::key(), width: slot_width(&listed.slot), declared, labels }
        })
        .collect()
}

impl ResolvedProgram {
    /// The width of the columns of `node` in row positions, with the
    /// relation `node` stands for, where the columns are known.
    pub fn node_width(&self, node: GraphNodeIndex) -> Option<(RelationRef, usize)> {
        let graph_node = &self.graph.nodes[node.0 as usize];
        let relation = node_relation(&graph_node.kind)?;
        let columns = self.names.columns(&graph_node.scope, &relation)?;
        Some((relation, columns.row_names().len()))
    }

    /// The columns of `port`, an input of the component of the `INIT` form at
    /// `form`, as the instance's relation of the input lays them out whether
    /// the instance writes the input or not: none where `form` is no instance
    /// of a component of `registry`.
    pub fn instance_port_slots(&self, form: &NodePath, port: &crate::registry::Port, registry: &Registry) -> Option<Vec<GivenSlot>> {
        let NodeRef::Instance(instance) = node_at(NodeRef::Program(self.program.value()), form)? else { return None };
        let component = registry_columns::component(registry, &instance.component)?;
        let bindings = form_columns::bindings(instance, component);
        Some(slots(&form_columns::port_columns(port, &bindings, instance.key.is_some())))
    }

    /// The path below the `INIT` form at `form` of the body of each clause
    /// that the instance writes for its input `name`.
    pub fn input_bodies(&self, form: &NodePath, name: &crate::program::PortName) -> Vec<NodePath> {
        let Some(NodeRef::Instance(instance)) = node_at(NodeRef::Program(self.program.value()), form) else { return Vec::new() };
        written_inputs(instance.key.as_ref(), &instance.inputs).filter(|written| written.name == *name).map(|written| input_body(NodeRef::Instance(instance), written)).collect()
    }

    /// The relations that the forms of `node` give it, with their listings.
    pub fn given(&self, node: GraphNodeIndex, registry: &Registry) -> Vec<Given> {
        let root = NodeRef::Program(self.program.value());
        let mut given = Vec::new();
        for form in self.forms_of(node) {
            let Some(shape) = node_at(root, form) else { continue };
            let whole = |listing: Listing, lib: Vec<LibName>| Given { form: form.clone(), output: None, slots: slots(&listing), lib, sites_from: usize::MAX, filled: Vec::new() };
            match shape {
                NodeRef::Clause(clause) => given.push(whole(form_columns::form_listing(shape), clause.proposers.to_vec())),
                NodeRef::Choose(_) => given.push(whole(form_columns::form_listing(shape), Vec::new())),
                NodeRef::Demonstrated(demonstrated) => given.push(whole(form_columns::demonstrated_listing(demonstrated), Vec::new())),
                NodeRef::RigidDet(rigid) => {
                    for (steps, listing) in form_columns::rigid_listings(rigid) {
                        let pose = listing.0.iter().position(|listed| listed.sources.iter().any(|(_, source)| matches!(source, Source::Declared(ColumnType::Pose))));
                        let sites_from = if steps.as_ref() == [OutputStep::Pose] { usize::MAX } else { pose.map_or(usize::MAX, |pose| pose + 1) };
                        given.push(Given { form: form.clone(), output: Some(steps), slots: slots(&listing), lib: Vec::new(), sites_from, filled: Vec::new() });
                    }
                }
                NodeRef::Instance(instance) => {
                    let Some(component) = registry_columns::component(registry, &instance.component) else { continue };
                    let bindings = form_columns::bindings(instance, component);
                    let keyed = instance.key.is_some();
                    let written: Vec<_> = written_inputs(instance.key.as_ref(), &instance.inputs).collect();
                    let lib = vec![instance.component.clone()];
                    let filled: Vec<(usize, Vec<ColumnType>)> = component
                        .inputs
                        .iter()
                        .enumerate()
                        .filter(|(_, own)| keyed && own.from_key && own.port.columns.iter().any(is_key) && written.iter().all(|written| written.name != own.port.name))
                        .map(|(index, own)| (index, own.port.columns.iter().filter(|column| !is_key(column)).map(|column| column.ty.clone()).collect()))
                        .collect();
                    let mut port = |port: &crate::registry::Port, output: bool| {
                        let filled = if output { filled.clone() } else { Vec::new() };
                        let output = output.then(|| Arc::from([OutputStep::Port(port.name.clone())]));
                        given.push(Given { form: form.clone(), output, slots: slots(&form_columns::port_columns(port, &bindings, keyed)), lib: lib.clone(), sites_from: usize::MAX, filled });
                    };
                    match &self.graph.nodes[node.0 as usize].kind {
                        DependencyKind::InstanceInput { input, .. } => {
                            for own in component.inputs.iter().filter(|own| own.port.name == *input) {
                                for written in written.iter().filter(|written| written.name == *input) {
                                    let listing = form_columns::input_columns(&own.port, &bindings, keyed, instance, written);
                                    given.push(Given { form: form.clone(), output: None, slots: slots(&listing), lib: lib.clone(), sites_from: usize::MAX, filled: Vec::new() });
                                }
                            }
                        }
                        DependencyKind::InstanceOutput { output, .. } => {
                            for own in component.outputs.iter().filter(|own| own.name == *output) {
                                port(own, true);
                            }
                        }
                        DependencyKind::RecursiveInstance(_) => {
                            for own in component.outputs.iter() {
                                port(own, true);
                            }
                        }
                        _ => {}
                    }
                }
                _ => {}
            }
        }
        given
    }
}

/// The number of row positions that `slot` takes.
fn slot_width(slot: &Slot) -> usize {
    match slot {
        Slot::Column(_) => 1,
        Slot::Record { fields, .. } => fields.len(),
    }
}

/// The row position of the column at `path` of `columns`.
fn place(columns: &Columns, path: &[crate::program::ColumnName]) -> Option<usize> {
    match columns.place(path)? {
        Place::Column(ColumnPosition(position)) | Place::Field(ColumnPosition(position), _) => Some(usize::from(position)),
        Place::Group(_) => None,
    }
}
