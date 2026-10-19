//! Instances of lib components: the [`Construction`] trait, the table of
//! constructions by registry name, the evaluation of an `INIT` form, the
//! defaults of its inputs, and a `DET` whose proposer is a derivation.
//! The evaluation of an `INIT` form is in `init`.
//!
//! The constructions stand in the crate `arclog-constructions`, which
//! depends on this crate, so no code of this crate refers to them. An instance
//! finds its component's construction by its registry name in the
//! [`Constructions`] of its evaluation.
//!
//! A construction is evaluated over its inputs grouped by key, and gives
//! its outputs as sets: it reads no order of the rows it is given, and none
//! of its outputs depends on the order it built them in.

#![allow(unused_variables, dead_code)]

use std::sync::Arc;

use super::join::{self, Budget};
use super::{Evaluation, Outcome, ReachedBound, RelationValue, RunFault, Stop};
use crate::hash::StableHashMap;
use crate::program::path::NodePath;
use crate::program::ParamValue;
use crate::registry::{is_key, keyless, Column, ComponentKind, InputPort, InputSource, InstanceOutput, LibEntry, LibName};
use crate::relations::RowSet;
use crate::session::TaskSession;
use crate::terms::TermId;
use crate::types::ValueType;

/// The rows of one key group of an instance: for each input of the
/// component, in the order the registry declares its inputs, the rows of
/// that input at the group's key, with the key's columns left out, and the
/// type of each of those columns, the instance's binding of the component's
/// type parameters.
#[derive(Debug)]
pub struct GroupInputs<'a> {
    pub inputs: &'a [RowSet],
    pub types: &'a [Box<[ValueType]>],
}

/// The rows a construction gives for one key group: for each output of the
/// component, in the order the registry declares its outputs, its rows
/// with the key's columns left out, each output a set.
#[derive(Debug)]
pub struct GroupOutputs {
    pub outputs: Box<[RowSet]>,
}

/// What a construction may use beside its inputs: the task session, whose
/// intern table gives an Ident to a set, the registry, and the budget its
/// bindings and rows count against.
#[derive(Debug)]
pub struct ConstructionContext<'a, 'b> {
    pub session: &'a TaskSession,
    pub registry: &'a crate::registry::Registry,
    pub budget: &'b mut Budget<'a>,
}

/// A construction or a detector of the lib, native, evaluated on one key
/// group at a time.
pub trait Construction: Send + Sync {
    /// The component's name in the registry, such as `Quotient`.
    fn name(&self) -> &'static str;

    /// The outputs of the component on one key group. A bound reached
    /// while it builds them stops it.
    fn evaluate(
        &self,
        group: &GroupInputs<'_>,
        context: &mut ConstructionContext<'_, '_>,
    ) -> Result<GroupOutputs, ReachedBound>;
}

/// The constructions by their registry names.
pub struct Constructions {
    by_name: StableHashMap<LibName, Box<dyn Construction>>,
}

impl std::fmt::Debug for Constructions {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.debug_struct("Constructions").finish_non_exhaustive()
    }
}

/// A fault that keeps a table of constructions from being built: two
/// constructions of one name, or a name of no component of the registry.
#[derive(Clone, PartialEq, Eq, Debug)]
pub enum ConstructionsFault {
    Repeated(LibName),
    NotAComponent(LibName),
}

impl Constructions {
    /// The table of `constructions`. Each one's name is a name of
    /// `registry` that declares a component that is a construction or a
    /// detector.
    pub fn new(
        constructions: Vec<Box<dyn Construction>>,
        registry: &crate::registry::Registry,
    ) -> Result<Self, ConstructionsFault> {
        let mut by_name = StableHashMap::default();
        for construction in constructions {
            let name = LibName(construction.name().into());
            let declares = match registry.entry(&name) {
                Some(LibEntry::Component(component)) => {
                    matches!(component.kind, ComponentKind::Construction | ComponentKind::Detector)
                }
                Some(LibEntry::Relation(_) | LibEntry::Proposer(_) | LibEntry::Macro(_)) | None => false,
            };
            if !declares {
                return Err(ConstructionsFault::NotAComponent(name));
            }
            if by_name.contains_key(&name) {
                return Err(ConstructionsFault::Repeated(name));
            }
            by_name.insert(name, construction);
        }
        Ok(Constructions { by_name })
    }

    /// The construction of `name`, or `None` where the table has none.
    pub fn get(&self, name: &LibName) -> Option<&dyn Construction> {
        self.by_name.get(name).map(|construction| construction.as_ref())
    }
}


#[path = "instance_init.rs"]
mod init;

pub use init::evaluate_instance;

/// The value of a `DET` at `form` whose proposer is a derivation, such as
/// `(DET &frame Frame)`: the table that the derivation's instances give
/// over its stored parameter, such as the extents of a Frame, each instance
/// evaluated by its construction as the inputs of one instance with no key.
///
/// Each input of an instance holds the stored rows at the fields its source
/// gives, the rows of an earlier instance's output, or, where it has no
/// source, its default rows. The value is the derivation's table output at
/// the derivation's columns.
pub fn evaluate_det_construction<'a>(
    evaluation: &Evaluation<'a>,
    form: &NodePath,
    value: &ParamValue,
    budget: &mut Budget<'a>,
) -> Outcome<RelationValue> {
    let fault = |message: String| RunFault { message: message.into(), form: form.clone() };
    let registry = evaluation.registry;
    let ParamValue::Derivation { derivation, .. } = value else { panic!("a parameter's stored values of a derivation") };
    let declared = registry
        .derivation(derivation)
        .ok_or_else(|| fault(format!("the lib declares no derivation `{}`", derivation.0)))?;
    let field_types = fixed_types(&declared.fields).ok_or_else(|| fault("a field of the derivation has no fixed type".into()))?;
    let stored = {
        let mut table = evaluation.session.intern.write().expect("an intern table that no panic poisoned");
        crate::terms::encode_param_value(value, &field_types, registry, &mut table)
            .map_err(|error| fault(format!("the stored values do not read at the derivation's field types: {error:?}")))?
    };
    let mut evaluated: Vec<InstanceRows> = Vec::with_capacity(declared.instances.len());
    for instance in declared.instances.iter() {
        let unevaluated = || fault(format!("the engine does not evaluate the construction `{}`", instance.component.0));
        let Some(LibEntry::Component(component)) = registry.entry(&instance.component) else { return Err(unevaluated()) };
        let construction = evaluation.constructions.get(&instance.component).ok_or_else(unevaluated)?;
        let (inputs, types) = {
            let mut table = evaluation.session.intern.write().expect("an intern table that no panic poisoned");
            let mut inputs = Vec::with_capacity(component.inputs.len());
            let mut types = Vec::with_capacity(component.inputs.len());
            for (input, source) in component.inputs.iter().zip(&instance.inputs) {
                let (rows, input_types) = match source {
                    Some(InputSource::Fields(positions)) => Ok(stored_input(positions, &field_types, &stored)),
                    Some(InputSource::Output(output)) => instance_output(&evaluated, output),
                    None => default_input(input, registry, &mut table),
                }
                .map_err(|message| fault(format!("input `{}` of `{}`: {message}", input.port.name.0, instance.component.0)))?;
                inputs.push(rows);
                types.push(input_types);
            }
            (inputs, types)
        };
        let group = GroupInputs { inputs: &inputs, types: &types };
        let mut context = ConstructionContext { session: evaluation.session, registry, budget };
        match construction.evaluate(&group, &mut context) {
            Ok(outputs) => evaluated.push(InstanceRows { outputs: outputs.outputs, ports: &component.outputs }),
            Err(bound) => return Ok(RelationValue::Stopped(Stop { bound, form: form.clone() })),
        }
    }
    let (rows, _) = instance_output(&evaluated, &declared.table)
        .map_err(|message| fault(format!("the table of `{}`: {message}", derivation.0)))?;
    Ok(RelationValue::Rows(Arc::new(join::one_part(rows))))
}

/// The outputs that an instance of a derivation gave, and the component's
/// declarations of them.
struct InstanceRows<'r> {
    outputs: Box<[RowSet]>,
    ports: &'r [crate::registry::Port],
}

/// The type of each of `columns`, where each has a fixed type.
fn fixed_types<'c>(columns: impl IntoIterator<Item = &'c Column>) -> Option<Box<[ValueType]>> {
    columns.into_iter().map(|column| column.ty.fixed().cloned()).collect()
}

/// The rows of `stored`, whose columns are a derivation's fields typed by
/// `field_types`, at the fields at `positions`, and their types.
fn stored_input(
    positions: &[usize],
    field_types: &[ValueType],
    stored: &crate::hash::StableHashSet<Box<[TermId]>>,
) -> (RowSet, Box<[ValueType]>) {
    let mut rows = RowSet::empty(positions.len() as u16);
    for row in stored {
        rows.insert(positions.iter().map(|&position| row[position]).collect());
    }
    (rows, positions.iter().map(|&position| field_types[position].clone()).collect())
}

/// The rows of the output that `output` gives, of one of the instances
/// `evaluated`, at its columns, and their types.
fn instance_output(evaluated: &[InstanceRows<'_>], output: &InstanceOutput) -> Result<(RowSet, Box<[ValueType]>), String> {
    let instance = &evaluated[output.instance];
    let declared: Vec<&Column> = keyless(&instance.ports[output.output].columns).collect();
    let types = fixed_types(output.columns.iter().map(|&column| declared[column]))
        .ok_or("a column of the output it reads has no fixed type")?;
    let mut rows = RowSet::empty(output.columns.len() as u16);
    for row in instance.outputs[output.output].rows() {
        rows.insert(output.columns.iter().map(|&column| row[column]).collect());
    }
    Ok((rows, types))
}

/// The default rows of `input`, with the key's columns left out, and their
/// types.
fn default_input(
    input: &InputPort,
    registry: &crate::registry::Registry,
    table: &mut crate::terms::InternTable,
) -> Result<(RowSet, Box<[ValueType]>), String> {
    let columns: Vec<&Column> = keyless(&input.port.columns).collect();
    let mut rows = RowSet::empty(columns.len() as u16);
    let default = input.default.as_ref().ok_or("the derivation gives it no source, and it has no default")?;
    let types = fixed_types(columns.iter().copied()).ok_or("a column of its default rows has no fixed type")?;
    for row in default.rows(&types, registry, table).map_err(|error| format!("its default rows do not read: {error:?}"))? {
        rows.insert(row);
    }
    Ok((rows, types))
}
