//! Instances of lib components: the [`Construction`] trait, the table of
//! constructions by registry name, the evaluation of an `INIT` form, the
//! defaults of its inputs, and a `DET` whose proposer is a construction.
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
use super::{ir, Evaluation, FormBodies, Outcome, ReachedBound, RelationValue, RunFault, Stop};
use crate::hash::StableHashMap;
use crate::program::path::{node_at, NodePath, NodeRef};
use crate::program::{Body, ColumnName, Instance, InstanceInput, LabelId, OutputStep, ParamValue, Site, SiteArg};
use crate::registry::{Column, ColumnType, Component, ComponentKind, InputPort, LibEntry, LibName, TypeParameter};
use crate::relations::{Row, RowSet};
use crate::session::TaskSession;
use crate::terms::{Constant, Example, Term, TermId};
use crate::types::{each_site_label, use_label, FormTypes, GraphRelation, ValueType};

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

/// The value of `output`, an output of the instance whose `INIT` form
/// stands at `form`, on `example`, or task-wide where it is `None`: its
/// component's construction evaluated over each key group of the instance's
/// inputs, each input the rows its clause gives or, where the instance
/// writes none, the input's default rows, with `bodies` evaluating the
/// form's bodies.
///
/// The key clause's rows are the groups, and an instance with no key
/// clause has one group, at the `Unit` key. A keyed input is its body
/// joined with the key body, and a broadcast joins each group. An input
/// with no clause and no default whose every column other than `key` takes
/// the one key label of its type is filled from the key, and otherwise
/// holds no row. A component whose inputs read its outputs, a
/// task-structure component and a component the table of constructions
/// lacks give a [`RunFault`] that names the component.
pub fn evaluate_instance<'a>(
    evaluation: &Evaluation<'a>,
    bodies: &FormBodies<'_>,
    form: &NodePath,
    output: &GraphRelation,
    example: Option<Example>,
    budget: &mut Budget<'a>,
) -> Outcome<RelationValue> {
    let fault = |message: String| RunFault { message: message.into(), form: form.clone() };
    let root = NodeRef::Program(evaluation.program.program.program.value());
    let Some(NodeRef::Instance(instance)) = node_at(root, form) else { panic!("an `INIT` form at the form of an instance output") };
    let name = &instance.component;
    let unevaluated = || fault(format!("the engine does not evaluate the component `{}`", name.0));
    let Some(LibEntry::Component(component)) = evaluation.registry.entry(name) else { return Err(unevaluated()) };
    if component.kind == ComponentKind::TaskStructure || component.inputs.iter().any(|input| input.reads_outputs) {
        return Err(unevaluated());
    }
    let construction = evaluation.constructions.get(name).ok_or_else(unevaluated)?;
    let Some([OutputStep::Port(port)]) = output.output.as_deref() else { panic!("an instance output read by its port") };
    let output_index = component.outputs.iter().position(|declared| declared.name == *port).expect("an output the component declares");
    let shape = InstanceShape::of(evaluation, form, instance, component);

    let key_labels = shape.key_labels();
    let groups: Vec<Row> = match &shape.key_body {
        Some(key_body) => {
            let clause = ir::compile_instance_body(evaluation.program, form, &[key_body.clone()], &key_labels)
                .map_err(|compile| fault(format!("the key body does not compile: {compile:?}")))?;
            match rows_of(bodies.relation(form, &clause, example)?, key_labels.len()).map_err(&fault)? {
                Ok(rows) => rows,
                Err(value) => return Ok(value),
            }
        }
        None => vec![Row::default()],
    };

    let mut group_inputs: Vec<Vec<RowSet>> = vec![Vec::with_capacity(component.inputs.len()); groups.len()];
    let mut types = Vec::with_capacity(component.inputs.len());
    for input in component.inputs.iter() {
        let input_types = shape.port_types(&input.port.columns).map_err(&fault)?;
        let per_group = match shape.written(&input.port.name) {
            Some((input_path, keyed, written)) => {
                let head = shape.head_labels(written, &input.port.columns).map_err(&fault)?;
                let body = (written.body.value(), input_path.child(written.head.len() as u32));
                let (parts, prefix): (Vec<(&Body, NodePath)>, &[LabelId]) = match (&shape.key_body, keyed) {
                    (Some(key_body), true) => (vec![key_body.clone(), body], &key_labels),
                    _ => (vec![body], &[]),
                };
                let columns: Vec<LabelId> = prefix.iter().chain(&head).copied().collect();
                let clause = ir::compile_instance_body(evaluation.program, form, &parts, &columns)
                    .map_err(|compile| fault(format!("input `{}` does not compile: {compile:?}", input.port.name.0)))?;
                let rows = match rows_of(bodies.relation(form, &clause, example)?, columns.len()).map_err(&fault)? {
                    Ok(rows) => rows,
                    Err(value) => return Ok(value),
                };
                grouped(&groups, prefix.len(), head.len(), rows)
            }
            None => shape.unwritten(input, &input_types, &groups, evaluation).map_err(&fault)?,
        };
        for (inputs, rows) in group_inputs.iter_mut().zip(per_group) {
            inputs.push(rows);
        }
        types.push(input_types);
    }

    let output_columns = &component.outputs[output_index].columns;
    let widths: Vec<Option<usize>> = output_columns
        .iter()
        .map(|column| if is_key(column) { Ok(None) } else { shape.column_types(column).map(|types| Some(types.len())) })
        .collect::<Result<_, _>>()
        .map_err(&fault)?;
    let unit = Term::Constant(Constant::Unit).encode().expect("a Unit has a term id");
    let key_width = if shape.key_body.is_some() { key_labels.len() } else { 1 };
    let arity = widths.iter().map(|width| width.unwrap_or(key_width)).sum::<usize>();
    let mut rows = RowSet::empty(arity as u16);
    let mut context = ConstructionContext { session: evaluation.session, registry: evaluation.registry, budget };
    for (key, inputs) in groups.iter().zip(&group_inputs) {
        let group = GroupInputs { inputs, types: &types };
        let outputs = match construction.evaluate(&group, &mut context) {
            Ok(outputs) => outputs,
            Err(bound) => return Ok(RelationValue::Stopped(Stop { bound, form: form.clone() })),
        };
        for values in outputs.outputs[output_index].rows() {
            let mut row = Vec::with_capacity(arity);
            let mut rest = values;
            for width in &widths {
                match width {
                    None if shape.key_body.is_none() => row.push(unit),
                    None => row.extend_from_slice(key),
                    Some(width) => {
                        let (taken, after) = rest.split_at(*width);
                        row.extend_from_slice(taken);
                        rest = after;
                    }
                }
            }
            rows.insert(row.into());
        }
    }
    Ok(RelationValue::Rows(Arc::new(join::one_part(rows))))
}

/// What an `INIT` form gives the evaluation of its instance: its key body
/// and key columns, the inputs it writes with their paths, the types of
/// its labels, and its binding of each type parameter of its component.
struct InstanceShape<'p> {
    /// The key body with its path, where the form has a key clause.
    key_body: Option<(&'p Body, NodePath)>,
    key_columns: Vec<(ColumnName, LabelId)>,
    /// Each input the form writes, with its path and whether it stands in
    /// the key clause.
    written: Vec<(NodePath, bool, &'p InstanceInput)>,
    types: &'p FormTypes,
    /// The fields of the record each type parameter is bound to, or `None`
    /// for one label, with the labels of its binding, by which its types
    /// are given.
    bindings: StableHashMap<&'p TypeParameter, (Option<Box<[ColumnName]>>, Vec<LabelId>)>,
}

impl<'p> InstanceShape<'p> {
    /// The shape of `instance`, the `INIT` form at `form`, of `component`.
    fn of(
        evaluation: &Evaluation<'p>,
        form: &NodePath,
        instance: &'p Instance,
        component: &'p Component,
    ) -> Self {
        let key = instance.key.as_ref().map(|key| key.value());
        let key_body = key.map(|key| (key.key.body.value(), form.child(0).child(0)));
        let key_columns = key.map_or_else(Vec::new, |key| key.key.columns.iter().map(|column| (column.name.clone(), column.label)).collect());
        let mut written = Vec::new();
        if let Some(key) = key {
            written.extend(key.inputs.iter().zip(1u32..).map(|(input, index)| (form.child(0).child(index), true, input.value())));
        }
        let first = u32::from(key.is_some());
        written.extend(instance.inputs.iter().zip(first..).map(|(input, index)| (form.child(index), false, input.value())));
        let mut bindings = StableHashMap::default();
        for sites in crate::registry::binding_sites(instance, &component.inputs) {
            let binding = match sites.binding {
                crate::registry::ParameterSite::Key(_) => {
                    let fields = key_columns.iter().map(|(name, _)| name.clone()).collect();
                    (Some(fields), key_columns.iter().map(|(_, label)| *label).collect())
                }
                crate::registry::ParameterSite::Head { site, .. } => {
                    let labels = site_labels(site);
                    let fields = record_fields(site).then(|| labels.iter().map(|(path, _)| path.last().expect("a field's path").clone()).collect());
                    (fields, labels.into_iter().map(|(_, label)| label).collect())
                }
            };
            bindings.insert(sites.parameter, binding);
        }
        let types = ir::label_types(evaluation.program, form);
        InstanceShape { key_body, key_columns, written, types, bindings }
    }

    /// The key's labels, in the order of its columns.
    fn key_labels(&self) -> Vec<LabelId> {
        self.key_columns.iter().map(|(_, label)| *label).collect()
    }

    /// The input the form writes of name `name`.
    fn written(&self, name: &crate::program::PortName) -> Option<(&NodePath, bool, &'p InstanceInput)> {
        self.written.iter().find(|(_, _, input)| input.name == *name).map(|(path, keyed, input)| (path, *keyed, *input))
    }

    /// The type of `label`.
    fn label_type(&self, label: LabelId) -> Result<ValueType, String> {
        self.types.label(label).cloned().ok_or_else(|| format!("the label {label:?} has no type"))
    }

    /// The types of the row positions of `column`: its fixed type, or the
    /// types of its type parameter's binding.
    fn column_types(&self, column: &Column) -> Result<Vec<ValueType>, String> {
        match &column.ty {
            ColumnType::Parameter(parameter) => {
                let (_, labels) = self.bindings.get(parameter).ok_or_else(|| format!("the type parameter `{}` is bound by no site", parameter.0))?;
                labels.iter().map(|&label| self.label_type(label)).collect()
            }
            ty => ty.fixed().cloned().map(|ty| vec![ty]).ok_or_else(|| format!("the column {:?} has no type of its own", column.name)),
        }
    }

    /// The types of the row positions of `columns` other than `key`.
    fn port_types(&self, columns: &[Column]) -> Result<Box<[ValueType]>, String> {
        let mut types = Vec::new();
        for column in columns.iter().filter(|column| !is_key(column)) {
            types.extend(self.column_types(column)?);
        }
        Ok(types.into())
    }

    /// The labels of the head sites of `input` at the row positions of
    /// `columns` other than `key`, a record's in the order of its binding's
    /// fields.
    fn head_labels(&self, input: &InstanceInput, columns: &[Column]) -> Result<Vec<LabelId>, String> {
        let mut labels = Vec::new();
        for column in columns.iter().filter(|column| !is_key(column)) {
            let site = input.head.iter().find(|site| site.column == column.name);
            let site = site.ok_or_else(|| format!("input `{}` writes no head site on column {:?}", input.name.0, column.name))?;
            let at_site = site_labels(site);
            let fields = match &column.ty {
                ColumnType::Parameter(parameter) => self.bindings.get(parameter).and_then(|(fields, _)| fields.as_deref()),
                _ => None,
            };
            match (fields, &at_site[..]) {
                (None, [(_, label)]) => labels.push(*label),
                (Some(fields), _) => {
                    for field in fields {
                        let found = at_site.iter().find(|(path, _)| path.last() == Some(field) && path.len() > 1);
                        let (_, label) = found.ok_or_else(|| format!("head site {:?} of input `{}` gives no label of field {field:?}", column.name, input.name.0))?;
                        labels.push(*label);
                    }
                }
                (None, _) => return Err(format!("head site {:?} of input `{}` holds other than one label", column.name, input.name.0)),
            }
        }
        Ok(labels)
    }

    /// The rows of `input`, which the form does not write, at each of
    /// `groups`: its default rows at each, or the rows the key fills, or no
    /// row.
    fn unwritten(
        &self,
        input: &InputPort,
        types: &[ValueType],
        groups: &[Row],
        evaluation: &Evaluation<'_>,
    ) -> Result<Vec<RowSet>, String> {
        let mut rows = RowSet::empty(types.len() as u16);
        if let Some(default) = &input.default {
            let mut table = evaluation.session.intern.write().expect("an intern table that no panic poisoned");
            for row in default.rows(types, evaluation.registry, &mut table).map_err(|error| format!("the default rows of input `{}` do not read: {error:?}", input.port.name.0))? {
                rows.insert(row);
            }
            return Ok(vec![rows; groups.len()]);
        }
        let Some(filled) = self.key_filled(input, types)? else { return Ok(vec![rows; groups.len()]) };
        Ok(groups
            .iter()
            .map(|key| {
                let mut rows = RowSet::empty(types.len() as u16);
                rows.insert(filled.iter().map(|&position| key[position]).collect());
                rows
            })
            .collect())
    }

    /// The position in the key of each row position of `input`, where the
    /// input has a `key` column and each of its other positions takes the
    /// one key label of its type.
    fn key_filled(&self, input: &InputPort, types: &[ValueType]) -> Result<Option<Vec<usize>>, String> {
        if !input.port.columns.iter().any(is_key) {
            return Ok(None);
        }
        let key_types: Vec<ValueType> = self.key_labels().into_iter().map(|label| self.label_type(label)).collect::<Result<_, _>>()?;
        let mut positions = Vec::with_capacity(types.len());
        for ty in types {
            let mut matching = key_types.iter().enumerate().filter(|(_, key)| *key == ty).map(|(position, _)| position);
            match (matching.next(), matching.next()) {
                (Some(position), None) => positions.push(position),
                _ => return Ok(None),
            }
        }
        Ok(Some(positions))
    }
}

/// Whether `column` is the `key` column of its port.
fn is_key(column: &Column) -> bool {
    column.name == crate::resolver::columns::key()
}

/// The labels at `site`, each with its column path from the site's column.
fn site_labels(site: &Site) -> Vec<(Vec<ColumnName>, LabelId)> {
    let mut labels = Vec::new();
    each_site_label(site, &mut Vec::new(), &mut |use_, path| labels.extend(use_label(use_).map(|label| (path.to_vec(), label))));
    labels
}

/// Whether the head site `site` projects a record onto its column's type
/// parameter, and not one label (`docs/arclog/arclog.md#instance`).
fn record_fields(site: &Site) -> bool {
    !matches!(&site.value.args[..], [SiteArg::Label(_) | SiteArg::NamedLabel { .. }])
}

/// The rows of `value`, of `arity` columns, or the value where it holds no
/// rows.
fn rows_of(value: RelationValue, arity: usize) -> Result<Result<Vec<Row>, RelationValue>, String> {
    let RelationValue::Rows(relation) = value else { return Ok(Err(value)) };
    if relation.arity() as usize != arity {
        return Err(format!("a body gives {} columns, where {arity} are read", relation.arity()));
    }
    let mut rows = Vec::new();
    join::each_row(&relation, &mut |row| rows.push(row.into()));
    Ok(Ok(rows))
}

/// `rows`, whose first `key` columns are a key and whose other `width`
/// columns are an input's, split into the rows of each of `groups` with
/// the key's columns left out; with no key columns, every row in each
/// group.
fn grouped(groups: &[Row], key: usize, width: usize, rows: Vec<Row>) -> Vec<RowSet> {
    if key == 0 {
        let mut all = RowSet::empty(width as u16);
        for row in rows {
            all.insert(row);
        }
        return vec![all; groups.len()];
    }
    let mut by_key: StableHashMap<&[TermId], RowSet> = StableHashMap::default();
    for row in &rows {
        let (at, values) = row.split_at(key);
        by_key.entry(at).or_insert_with(|| RowSet::empty(width as u16)).insert(values.into());
    }
    groups.iter().map(|group| by_key.remove(&group[..]).unwrap_or_else(|| RowSet::empty(width as u16))).collect()
}

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
