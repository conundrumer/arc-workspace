//! Instances of lib components: the [`Construction`] trait, the table of
//! constructions by registry name, the evaluation of an `INIT` form, the
//! defaults of its inputs, and a `DET` whose proposer is a construction.
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
use crate::registry::{Column, ComponentKind, InputPort, LibEntry, LibName};
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
    /// `registry` that declares a construction or a detector: a component,
    /// or a derivation that a `DET` gives as its proposer, such as
    /// `Division`.
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
                Some(LibEntry::Relation(_) | LibEntry::Proposer(_) | LibEntry::Macro(_)) | None => {
                    registry.derivation(&name).is_some()
                }
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

/// Whether `column` is the `key` column of its port.
fn is_key(column: &Column) -> bool {
    column.name == crate::resolver::columns::key()
}

#[path = "instance_init.rs"]
mod init;

pub use init::evaluate_instance;

/// The value of a `DET` at `form` whose proposer is a construction, such as
/// `(DET &frame Frame)`: the construction evaluated over the inputs its
/// stored parameter gives, such as the extents of a Frame, as the inputs of
/// one instance with no key.
///
/// Each input whose columns other than `key` are each a field of the
/// derivation takes the stored rows at those fields, and each other input
/// its default rows. The value is the output whose columns other than `key`
/// are the derivation's columns.
pub fn evaluate_det_construction<'a>(
    evaluation: &Evaluation<'a>,
    form: &NodePath,
    value: &ParamValue,
    budget: &mut Budget<'a>,
) -> Outcome<RelationValue> {
    let fault = |message: String| RunFault { message: message.into(), form: form.clone() };
    let registry = evaluation.registry;
    let ParamValue::Derivation { derivation, .. } = value else { panic!("a parameter's stored values of a derivation") };
    let unevaluated = || fault(format!("the engine does not evaluate the construction `{}`", derivation.0));
    let declared = registry.derivation(derivation).ok_or_else(unevaluated)?;
    let Some(LibEntry::Component(component)) = registry.entry(derivation) else { return Err(unevaluated()) };
    let construction = evaluation.constructions.get(derivation).ok_or_else(unevaluated)?;
    let field_types = fixed_types(&declared.fields).ok_or_else(|| fault("a field of the derivation has no fixed type".into()))?;
    let (inputs, types) = {
        let mut table = evaluation.session.intern.write().expect("an intern table that no panic poisoned");
        let stored = crate::terms::encode_param_value(value, &field_types, registry, &mut table)
            .map_err(|error| fault(format!("the stored values do not read at the derivation's field types: {error:?}")))?;
        let mut inputs = Vec::with_capacity(component.inputs.len());
        let mut types = Vec::with_capacity(component.inputs.len());
        for input in component.inputs.iter() {
            let (rows, input_types) = derivation_input(input, &declared.fields, &field_types, &stored, registry, &mut table)
                .map_err(|message| fault(format!("input `{:?}` of `{}`: {message}", input.port.name, derivation.0)))?;
            inputs.push(rows);
            types.push(input_types);
        }
        (inputs, types)
    };
    let output = component
        .outputs
        .iter()
        .position(|port| keyless(&port.columns).map(|column| &column.name).eq(declared.columns.iter().map(|column| &column.name)))
        .ok_or_else(|| fault(format!("no output of `{}` has the derivation's columns", derivation.0)))?;
    let group = GroupInputs { inputs: &inputs, types: &types };
    let mut context = ConstructionContext { session: evaluation.session, registry, budget };
    match construction.evaluate(&group, &mut context) {
        Ok(outputs) => {
            let rows = outputs.outputs.into_vec().swap_remove(output);
            Ok(RelationValue::Rows(Arc::new(join::one_part(rows))))
        }
        Err(bound) => Ok(RelationValue::Stopped(Stop { bound, form: form.clone() })),
    }
}

/// The columns of `columns` other than `key`.
fn keyless(columns: &[Column]) -> impl Iterator<Item = &Column> + '_ {
    columns.iter().filter(|column| !is_key(column))
}

/// The type of each of `columns`, where each has a fixed type.
fn fixed_types<'c>(columns: impl IntoIterator<Item = &'c Column>) -> Option<Box<[ValueType]>> {
    columns.into_iter().map(|column| column.ty.fixed().cloned()).collect()
}

/// The rows of `input` of a derivation's construction, with the key's
/// columns left out, and their types: `stored`, whose columns are `fields`
/// typed by `field_types`, at the fields that name the input's columns, or,
/// where a column names no field, the input's default rows.
fn derivation_input(
    input: &InputPort,
    fields: &[Column],
    field_types: &[ValueType],
    stored: &crate::hash::StableHashSet<Box<[TermId]>>,
    registry: &crate::registry::Registry,
    table: &mut crate::terms::InternTable,
) -> Result<(RowSet, Box<[ValueType]>), String> {
    let columns: Vec<&Column> = keyless(&input.port.columns).collect();
    let positions: Option<Vec<usize>> =
        columns.iter().map(|column| fields.iter().position(|field| field.name == column.name)).collect();
    let mut rows = RowSet::empty(columns.len() as u16);
    if let Some(positions) = positions {
        for row in stored {
            rows.insert(positions.iter().map(|&position| row[position]).collect());
        }
        return Ok((rows, positions.iter().map(|&position| field_types[position].clone()).collect()));
    }
    let default = input.default.as_ref().ok_or("the derivation's fields give no column of it, and it has no default")?;
    let types = fixed_types(columns.iter().copied()).ok_or("a column of its default rows has no fixed type")?;
    for row in default.rows(&types, registry, table).map_err(|error| format!("its default rows do not read: {error:?}"))? {
        rows.insert(row);
    }
    Ok((rows, types))
}
