//! The evaluation of an `INIT` form: each output of its instance, from the
//! key groups of its inputs, each input the rows of its clause, of the `DET`
//! that stores it, or of its default.

use std::sync::Arc;

use super::{is_key, ConstructionContext, GroupInputs};
use crate::check::instance_inputs::inputs_at;
use crate::eval::join::{self, Budget};
use crate::eval::{ir, Evaluation, FormBodies, Outcome, RelationValue, RunFault, Stop};
use crate::hash::StableHashMap;
use crate::program::path::{node_at, NodePath, NodeRef};
use crate::program::{Body, ColumnName, Instance, InstanceInput, LabelId, OutputStep, PortName, Site};
use crate::registry::{Column, ColumnType, Component, ComponentKind, InputPort, LibEntry, TypeParameter};
use crate::relations::{Row, RowSet};
use crate::resolver::columns::projection;
use crate::resolver::{DependencyKind, GraphNodeIndex};
use crate::terms::{Constant, Example, Term, TermId};
use crate::types::{each_site_label, use_label, FormTypes, GraphRelation, ValueType};

/// The value of `output`, an output of the instance whose `INIT` form
/// stands at `form`, on `example`, or task-wide where it is `None`: its
/// component's construction evaluated over each key group of the instance's
/// inputs, each input the rows its clause gives, or, where the instance
/// writes none and the input's node reads the parameter node of a `DET` of
/// the input, that parameter's rows, in the columns of the port, and
/// otherwise the input's default rows, with
/// `bodies` evaluating the form's bodies.
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
            None => match stored_input(evaluation, form, instance, &input.port.name) {
                Some(parameter) => {
                    let widths = shape.widths(&input.port.columns).map_err(&fault)?;
                    let arity = widths.iter().map(|width| width.unwrap_or(shape.key_width())).sum::<usize>();
                    let rows = match rows_of(evaluation.relation(&parameter, None)?, arity).map_err(&fault)? {
                        Ok(rows) => rows,
                        Err(value) => return Ok(value),
                    };
                    let prefix = if shape.key_body.is_some() { key_labels.len() } else { 0 };
                    grouped(&groups, prefix, input_types.len(), rows.iter().map(|row| shape.key_first(&widths, row)).collect())
                }
                None => shape.unwritten(input, &input_types, &groups, evaluation).map_err(&fault)?,
            },
        };
        for (inputs, rows) in group_inputs.iter_mut().zip(per_group) {
            inputs.push(rows);
        }
        types.push(input_types);
    }

    let widths = shape.widths(&component.outputs[output_index].columns).map_err(&fault)?;
    let unit = Term::Constant(Constant::Unit).encode().expect("a Unit has a term id");
    let arity = widths.iter().map(|width| width.unwrap_or(shape.key_width())).sum::<usize>();
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

/// The parameter node that the input `port` of `instance`, the `INIT` form
/// at `form`, reads, where a `DET` of the case stores that input, as
/// [`crate::resolver::DependencyKind::InstanceInput`] gives it.
fn stored_input(evaluation: &Evaluation<'_>, form: &NodePath, instance: &Instance, port: &PortName) -> Option<GraphRelation> {
    let program = &evaluation.program.program;
    let graph = &program.graph;
    let input = (0..graph.nodes.len()).map(|node| GraphNodeIndex(node as u32)).find(|node| {
        matches!(&graph.nodes[node.0 as usize].kind, DependencyKind::InstanceInput { instance: name, input } if *name == instance.name && input == port)
            && program.forms_of(*node).contains(form)
    })?;
    let parameter = graph.reads[input.0 as usize].iter().find(|read| matches!(graph.nodes[read.0 as usize].kind, DependencyKind::Parameter(_)))?;
    Some(GraphRelation { node: *parameter, output: None })
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
        let written = inputs_at(instance).into_iter().map(|(path, keyed, input)| (form.join(&path), keyed, input)).collect();
        let mut bindings = StableHashMap::default();
        for sites in crate::registry::binding_sites(instance, &component.inputs) {
            let binding = match sites.binding {
                crate::registry::ParameterSite::Key(_) => {
                    let fields = key_columns.iter().map(|(name, _)| name.clone()).collect();
                    (Some(fields), key_columns.iter().map(|(_, label)| *label).collect())
                }
                crate::registry::ParameterSite::Head { site, .. } => {
                    (projection(site), site_labels(site).into_iter().map(|(_, label)| label).collect())
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

    /// The number of row positions of each of `columns` in a port's rows,
    /// or `None` for its `key` column, which takes [`Self::key_width`]
    /// positions.
    fn widths(&self, columns: &[Column]) -> Result<Vec<Option<usize>>, String> {
        columns.iter().map(|column| if is_key(column) { Ok(None) } else { self.column_types(column).map(|types| Some(types.len())) }).collect()
    }

    /// The number of row positions of a port's `key` column: the key's
    /// labels where the form has a key clause, and one `Unit` where it has
    /// none.
    fn key_width(&self) -> usize {
        if self.key_body.is_some() { self.key_columns.len() } else { 1 }
    }

    /// `row`, a row of a port whose columns have `widths`, with the key's
    /// positions first where the form has a key clause, and left out where
    /// it has none.
    fn key_first(&self, widths: &[Option<usize>], row: &Row) -> Row {
        let (mut key, mut values) = (Vec::new(), Vec::new());
        let mut rest = &row[..];
        for width in widths {
            let (taken, after) = rest.split_at(width.unwrap_or(self.key_width()));
            if width.is_some() {
                values.extend_from_slice(taken);
            } else if self.key_body.is_some() {
                key.extend_from_slice(taken);
            }
            rest = after;
        }
        key.extend(values);
        key.into()
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
    /// `groups`: its default rows at each, or no row where the input is
    /// marked [`InputPort::explicit`], or the rows the key fills, or no
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
        if input.explicit {
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


/// The labels at `site`, each with its column path from the site's column.
fn site_labels(site: &Site) -> Vec<(Vec<ColumnName>, LabelId)> {
    let mut labels = Vec::new();
    each_site_label(site, &mut Vec::new(), &mut |use_, path| labels.extend(use_label(use_).map(|label| (path.to_vec(), label))));
    labels
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
