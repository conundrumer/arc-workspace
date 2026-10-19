//! The evaluation of an `INIT` form: each output of its instance, from the
//! key groups of its inputs, and each input as a clause reads it, each
//! input the rows of its clause, of the `DET` that stores it, or of its
//! default.

use std::sync::Arc;

use super::{ConstructionContext, GroupInputs};
use crate::eval::init_form::{grouped, instance_at, key_groups, rows_of, unevaluated, InstanceShape};
use crate::eval::join::{self, Budget};
use crate::eval::{Evaluation, FormBodies, Outcome, RelationValue, RunFault, Stop};
use crate::program::path::NodePath;
use crate::program::{Instance, PortName};
use crate::registry::{Component, ComponentKind, InputPort};
use crate::relations::{Row, RowSet};
use crate::resolver::DependencyKind;
use crate::terms::{Example, TermId};
use crate::types::GraphRelation;

/// The value of each output of the instance whose `INIT` form stands at
/// `form`, on `example`, or task-wide where it is `None`, with its relation,
/// from one run of its component's construction over each key group of
/// the instance's inputs, each input's rows as `input_groups` gives them,
/// with `bodies` evaluating the form's bodies. A body whose value holds no
/// rows gives that value to each output.
///
/// The key clause's rows are the groups, and an instance with no key
/// clause has one group, at the `Unit` key. A type parameter onto which no
/// place of the form projects is `Unit`, and each row of an input or an
/// output holds the one `Unit` term at each column of that parameter. A
/// component whose inputs read its outputs, a task-structure component and
/// a component the table of constructions lacks give a [`RunFault`] whose
/// message gives the component.
pub fn evaluate_instance<'a>(
    evaluation: &Evaluation<'a>,
    bodies: &FormBodies<'_>,
    form: &NodePath,
    example: Option<Example>,
    budget: &mut Budget<'a>,
) -> Outcome<Vec<(GraphRelation, RelationValue)>> {
    let fault = |message: String| RunFault { message: message.into(), form: form.clone() };
    let (instance, component) = instance_at(evaluation, form)?;
    let unevaluated = || unevaluated(form, instance);
    if component.kind == ComponentKind::TaskStructure || component.reads_outputs() {
        return Err(unevaluated());
    }
    let construction = evaluation.constructions.get(&instance.component).ok_or_else(unevaluated)?;
    let relations = output_relations(evaluation, form, instance, component);
    let each = |value: RelationValue| relations.iter().map(|relation| (relation.clone(), value.clone())).collect();
    let shape = InstanceShape::of(evaluation, form, instance, component);
    let groups = match key_groups(evaluation, bodies, form, &shape, example)? {
        Ok(groups) => groups,
        Err(value) => return Ok(each(value)),
    };

    let mut group_inputs: Vec<Vec<RowSet>> = vec![Vec::with_capacity(component.inputs.len()); groups.len()];
    let mut types = Vec::with_capacity(component.inputs.len());
    let mut columns = Vec::with_capacity(component.inputs.len());
    for input in component.inputs.iter() {
        let per_group = match input_groups(evaluation, bodies, form, instance, &shape, input, &groups, example)? {
            Ok(per_group) => per_group,
            Err(value) => return Ok(each(value)),
        };
        for (inputs, rows) in group_inputs.iter_mut().zip(per_group) {
            inputs.push(rows);
        }
        types.push(shape.port_types(&input.port.columns).map_err(&fault)?);
        columns.push(shape.port_column_types(&input.port.columns).map_err(&fault)?);
    }

    let widths: Vec<Vec<Option<usize>>> = component.outputs.iter().map(|output| shape.widths(&output.columns)).collect::<Result<_, _>>().map_err(&fault)?;
    let output_key = shape.output_key();
    let mut rows: Vec<RowSet> = widths.iter().map(|widths| RowSet::empty(shape.arity(widths) as u16)).collect();
    let mut context = ConstructionContext { session: evaluation.session, registry: evaluation.registry, budget };
    for (key, inputs) in groups.iter().zip(&group_inputs) {
        let group = GroupInputs { inputs, types: &types, columns: &columns };
        let outputs = match construction.evaluate(&group, &mut context) {
            Ok(outputs) => outputs,
            Err(bound) => return Ok(each(RelationValue::Stopped(Stop { bound, form: form.clone() }))),
        };
        let key_columns = output_key.columns(key);
        for ((rows, widths), values) in rows.iter_mut().zip(&widths).zip(&outputs.outputs) {
            for values in values.rows() {
                rows.insert(laid_out(widths, &key_columns, values));
            }
        }
    }
    let values = rows.into_iter().map(|rows| RelationValue::Rows(Arc::new(join::one_part(rows))));
    Ok(relations.into_iter().zip(values).collect())
}

/// The rows of the input `port` of the instance whose `INIT` form stands
/// at `form`, on `example`, or task-wide where it is `None`, as a clause
/// that reads that input reads them: the rows `input_groups` gives each
/// key group, in the columns of the port, the group's key at the `key`
/// column as an output row holds it, with `bodies` evaluating the form's
/// bodies. A body whose value holds no rows gives that value.
pub fn evaluate_input(
    evaluation: &Evaluation<'_>,
    bodies: &FormBodies<'_>,
    form: &NodePath,
    port: &PortName,
    example: Option<Example>,
) -> Outcome<RelationValue> {
    let fault = |message: String| RunFault { message: message.into(), form: form.clone() };
    let (instance, component) = instance_at(evaluation, form)?;
    let input = component.inputs.iter().find(|input| input.port.name == *port).expect("an input of the component at each instance input node");
    let shape = InstanceShape::of(evaluation, form, instance, component);
    let groups = match key_groups(evaluation, bodies, form, &shape, example)? {
        Ok(groups) => groups,
        Err(value) => return Ok(value),
    };
    let per_group = match input_groups(evaluation, bodies, form, instance, &shape, input, &groups, example)? {
        Ok(per_group) => per_group,
        Err(value) => return Ok(value),
    };
    let widths = shape.widths(&input.port.columns).map_err(&fault)?;
    let output_key = shape.output_key();
    let mut rows = RowSet::empty(shape.arity(&widths) as u16);
    for (key, group) in groups.iter().zip(&per_group) {
        let key_columns = output_key.columns(key);
        for values in group.rows() {
            rows.insert(laid_out(&widths, &key_columns, values));
        }
    }
    Ok(RelationValue::Rows(Arc::new(join::one_part(rows))))
}

/// The rows of `input` of `instance`, the `INIT` form at `form` of `shape`,
/// at each of `groups`, in the order of its row positions other than
/// `key`: the rows its clause gives, or, where the instance writes none
/// and the input's node reads the parameter node of a `DET` of the input,
/// that parameter's rows, and otherwise the rows
/// [`InstanceShape::unwritten`] gives. A keyed input is its body joined
/// with the key body, and a broadcast joins each group. A body whose value
/// holds no rows gives that value.
#[allow(clippy::too_many_arguments)]
fn input_groups(
    evaluation: &Evaluation<'_>,
    bodies: &FormBodies<'_>,
    form: &NodePath,
    instance: &Instance,
    shape: &InstanceShape<'_>,
    input: &InputPort,
    groups: &[Row],
    example: Option<Example>,
) -> Outcome<Result<Vec<RowSet>, RelationValue>> {
    let fault = |message: String| RunFault { message: message.into(), form: form.clone() };
    let input_types = shape.port_types(&input.port.columns).map_err(&fault)?;
    match shape.input_clause(evaluation, form, input).map_err(&fault)? {
        Some(written) => Ok(rows_of(bodies.relation(form, &written.clause, example)?, written.arity()).map_err(&fault)?.map(|rows| written.grouped(groups, rows))),
        None => match stored_input(evaluation, form, instance, &input.port.name) {
            Some(parameter) => {
                let widths = shape.widths(&input.port.columns).map_err(&fault)?;
                let prefix = if shape.key_body.is_some() { shape.key_labels().len() } else { 0 };
                Ok(rows_of(evaluation.relation(&parameter, None)?, shape.arity(&widths))
                    .map_err(&fault)?
                    .map(|rows| grouped(groups, prefix, input_types.len(), rows.iter().map(|row| shape.key_first(&widths, row)).collect())))
            }
            None => Ok(Ok(shape.unwritten(input, &input_types, groups, evaluation).map_err(&fault)?)),
        },
    }
}

/// A row of a port whose columns have `widths`: `key_columns` at the `key`
/// column, and the positions of `values` in order at the others.
fn laid_out(widths: &[Option<usize>], key_columns: &[TermId], values: &[TermId]) -> Row {
    let mut row = Vec::with_capacity(values.len() + key_columns.len());
    let mut rest = values;
    for width in widths {
        match width {
            None => row.extend_from_slice(key_columns),
            Some(width) => {
                let (taken, after) = rest.split_at(*width);
                row.extend_from_slice(taken);
                rest = after;
            }
        }
    }
    row.into()
}

/// The relation of each output of `instance`, the `INIT` form at `form`, of
/// `component`, in the order the component declares its outputs: the node
/// of the output, as an atom that reads the output reads it.
fn output_relations(evaluation: &Evaluation<'_>, form: &NodePath, instance: &Instance, component: &Component) -> Vec<GraphRelation> {
    let program = &evaluation.program.program;
    let node_of = |port: &PortName| {
        let found = program.nodes_of(form).iter().find(|node| {
            matches!(&program.graph.nodes[node.0 as usize].kind, DependencyKind::InstanceOutput { instance: name, output } if *name == instance.name && output == port)
        });
        *found.expect("a node of each output of an instance")
    };
    component.outputs.iter().map(|output| GraphRelation { node: node_of(&output.name), output: None }).collect()
}

/// The parameter node that the input `port` of `instance`, the `INIT` form
/// at `form`, reads, where a `DET` of the case stores that input, as
/// [`crate::resolver::DependencyKind::InstanceInput`] gives it.
fn stored_input(evaluation: &Evaluation<'_>, form: &NodePath, instance: &Instance, port: &PortName) -> Option<GraphRelation> {
    let program = &evaluation.program.program;
    let graph = &program.graph;
    let input = program.nodes_of(form).iter().find(|node| {
        matches!(&graph.nodes[node.0 as usize].kind, DependencyKind::InstanceInput { instance: name, input } if *name == instance.name && input == port)
    })?;
    let parameter = graph.reads[input.0 as usize].iter().find(|read| matches!(graph.nodes[read.0 as usize].kind, DependencyKind::Parameter(_)))?;
    Some(GraphRelation { node: *parameter, output: None })
}
