//! The evaluation of an `INIT` form: each output of its instance, from the
//! key groups of its inputs, and each input as a clause reads it, each
//! input the rows of its clause, of the `DET` that stores it, or of its
//! default.

use std::sync::Arc;

use super::{ConstructionContext, GroupInputs};
use crate::eval::cache::{self, EntryContent, EntryRequest};
use crate::eval::copies::{self, CopyViolation};
use crate::eval::driver::record_whole;
use crate::eval::init_form::{grouped, instance_at, key_groups, key_read, rows_read, unevaluated, InstanceShape};
use crate::eval::join::{self, Budget};
use crate::eval::{Evaluation, FormBodies, Outcome, RelationValue, RunFault, Stop};
use crate::program::path::NodePath;
use crate::program::{Instance, PortName};
use crate::registry::{Component, ComponentKind, InputPort};
use crate::relations::{Relation, Row, RowSet};
use crate::resolver::DependencyKind;
use crate::terms::{Example, TermId};
use crate::types::GraphRelation;

/// The value of the output `asked` of the instance whose `INIT` form stands
/// at `form`, on `example`, or task-wide where it is `None`, from one run of
/// its component's construction over each key group of the instance's
/// inputs, each input's rows as `input_groups` gives them, with `bodies`
/// evaluating the form's bodies. A body whose value holds no rows gives that
/// value.
///
/// The value stands in the result cache as an entry of the output's node,
/// which reads the relation of the key clause and the relation of each
/// input in the order of the component's inputs, the relations of the
/// `DET`s that store inputs as parameters, and the example. A run of the
/// construction builds and stores the entry of `asked` and of each other
/// output whose node some node of the program's dependency graph reads.
/// It builds the rows of no other output, and stores no entry for one, so a
/// later request that asks for such an output runs the construction again.
/// An output whose node has no resolved content has no entry, and its value
/// is that of the run.
///
/// The key clause's rows are the groups, and an instance with no key
/// clause has one group, with no key column. A type parameter onto which no
/// place of the form projects is `Unit`, and each row of an input or an
/// output holds the one `Unit` term at each column of that parameter. A key
/// group whose inputs lie outside the construction's domain makes each
/// output undefined. A
/// component whose inputs read its outputs, a task-structure component and
/// a component the table of constructions lacks give a [`RunFault`] whose
/// message gives the component.
pub fn evaluate_instance<'a>(
    evaluation: &Evaluation<'a>,
    bodies: &FormBodies<'_>,
    form: &NodePath,
    example: Option<Example>,
    asked: &GraphRelation,
    budget: &mut Budget<'a>,
) -> Outcome<RelationValue> {
    let fault = |message: String| RunFault { message: message.into(), form: form.clone() };
    let (instance, component) = instance_at(evaluation, form)?;
    let unevaluated = || unevaluated(form, instance);
    if component.kind == ComponentKind::TaskStructure || component.reads_outputs() {
        return Err(unevaluated());
    }
    let construction = evaluation.constructions.get(&instance.component).ok_or_else(unevaluated)?;
    let relations = output_relations(evaluation, form, instance, component);
    let wanted = wanted_outputs(evaluation, &relations, asked);
    let built: Vec<&GraphRelation> = relations.iter().zip(&wanted).filter(|(_, wanted)| **wanted).map(|(relation, _)| relation).collect();
    let each = |value: RelationValue| built.iter().map(|relation| ((*relation).clone(), value.clone())).collect();
    let whole = |budget: &Budget<'_>, value: RelationValue| {
        record_whole(budget, [&value]);
        Ok(value)
    };
    let shape = InstanceShape::of(evaluation.program, form, instance, component);
    let (groups, key) = match key_read(evaluation, bodies, form, &shape, example)? {
        Ok(read) => read,
        Err(value) => return whole(budget, value),
    };

    let mut reads: Vec<Arc<Relation>> = key.into_iter().collect();
    let mut parameters: Vec<Arc<Relation>> = Vec::new();
    let mut group_inputs: Vec<Vec<RowSet>> = vec![Vec::with_capacity(component.inputs.len()); groups.len()];
    let mut types = Vec::with_capacity(component.inputs.len());
    let mut columns = Vec::with_capacity(component.inputs.len());
    for input in component.inputs.iter() {
        let (per_group, read) = match input_groups(evaluation, bodies, form, instance, &shape, input, &groups, example)? {
            Ok(read) => read,
            Err(value) => return whole(budget, value),
        };
        match read {
            InputRead::Clause(relation) => reads.push(relation),
            InputRead::Stored(relation) => parameters.push(relation),
            InputRead::Default => {}
        }
        for (inputs, rows) in group_inputs.iter_mut().zip(per_group) {
            inputs.push(rows);
        }
        types.push(shape.port_types(&input.port.columns).map_err(&fault)?);
        columns.push(shape.port_column_types(&input.port.columns).map_err(&fault)?);
    }

    let widths: Vec<Vec<Option<usize>>> = component.outputs.iter().map(|output| shape.widths(&output.columns)).collect::<Result<_, _>>().map_err(&fault)?;
    let construct = |budget: &mut Budget<'a>| -> Outcome<Vec<(GraphRelation, RelationValue)>> {
        let mut rows: Vec<RowSet> = widths.iter().map(|widths| RowSet::empty(shape.arity(widths) as u16)).collect();
        let mut context = ConstructionContext { session: evaluation.session, registry: evaluation.registry, budget };
        // The count of output rows that break each declared row, by output and declared row.
        let mut broken: std::collections::BTreeMap<(usize, usize), usize> = Default::default();
        for (key, inputs) in groups.iter().zip(&group_inputs) {
            let group = GroupInputs { inputs, types: &types, columns: &columns, wanted: &wanted };
            if construction.outside_domain(&group) {
                return Ok(each(RelationValue::Undefined));
            }
            let outputs = match construction.evaluate(&group, &mut context) {
                Ok(outputs) => outputs,
                Err(bound) => return Ok(each(RelationValue::Stopped(Stop { bound, form: form.clone() }))),
            };
            if evaluation.limits.copies.is_some() {
                for (output, row, rows) in copies::broken_rows(component, &group, &outputs, &widths) {
                    *broken.entry((output, row)).or_default() += rows;
                }
            }
            for (((rows, widths), values), wanted) in rows.iter_mut().zip(&widths).zip(&outputs.outputs).zip(&wanted) {
                if !wanted {
                    continue;
                }
                for values in values.rows() {
                    rows.insert(laid_out(widths, key, values));
                }
            }
        }
        if let Some(violations) = &evaluation.limits.copies {
            for ((output, row), rows) in broken {
                violations.report(CopyViolation { form: form.clone(), component: instance.component.clone(), output: component.outputs[output].name.clone(), row, rows });
            }
        }
        let values = rows.into_iter().zip(&wanted).filter(|(_, wanted)| **wanted).map(|(rows, _)| RelationValue::Rows(Arc::new(join::one_part(rows))));
        Ok(built.iter().map(|relation| (*relation).clone()).zip(values).collect())
    };
    let program = &evaluation.program.program;
    let session = evaluation.session;
    let run = |budget: &mut Budget<'a>, store: bool| -> Outcome<RelationValue> {
        let outputs = construct(budget)?;
        record_whole(budget, outputs.iter().map(|(_, value)| value));
        let mut found = None;
        for (output, value) in outputs {
            if output == *asked {
                found = Some(value);
            } else if let Some(content) = store.then(|| program.node_content(output.node)).flatten() {
                let request = EntryRequest { clause: EntryContent::Node(&content), reads: &reads, example, parameters: &parameters };
                cache::store(session, &request, &value);
            }
        }
        Ok(found.expect("the value of each output of the instance"))
    };
    match program.node_content(asked.node) {
        None => run(budget, false),
        Some(content) => {
            let request = EntryRequest { clause: EntryContent::Node(&content), reads: &reads, example, parameters: &parameters };
            bodies.cached(form, &request, || run(budget, true))
        }
    }
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
    let shape = InstanceShape::of(evaluation.program, form, instance, component);
    let groups = match key_groups(evaluation, bodies, form, &shape, example)? {
        Ok(groups) => groups,
        Err(value) => return Ok(value),
    };
    let per_group = match input_groups(evaluation, bodies, form, instance, &shape, input, &groups, example)? {
        Ok((per_group, _)) => per_group,
        Err(value) => return Ok(value),
    };
    let widths = shape.widths(&input.port.columns).map_err(&fault)?;
    let mut rows = RowSet::empty(shape.arity(&widths) as u16);
    for (key, group) in groups.iter().zip(&per_group) {
        for values in group.rows() {
            rows.insert(laid_out(&widths, key, values));
        }
    }
    Ok(RelationValue::Rows(Arc::new(join::one_part(rows))))
}

/// What the rows of an input came from: the relation of its clause, the
/// relation of the `DET` that stores it, or its default.
enum InputRead {
    Clause(Arc<Relation>),
    Stored(Arc<Relation>),
    Default,
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
) -> Outcome<Result<(Vec<RowSet>, InputRead), RelationValue>> {
    let fault = |message: String| RunFault { message: message.into(), form: form.clone() };
    let input_types = shape.port_types(&input.port.columns).map_err(&fault)?;
    match shape.input_clause(evaluation.program, form, input).map_err(&fault)? {
        Some(written) => Ok(rows_read(evaluation, form, bodies.relation(form, &written.clause, example)?, written.arity())
            .map_err(&fault)?
            .map(|(rows, relation)| (written.grouped(groups, rows), InputRead::Clause(relation)))),
        None => match stored_input(evaluation, form, instance, &input.port.name) {
            Some(parameter) => {
                let widths = shape.widths(&input.port.columns).map_err(&fault)?;
                let prefix = if shape.key_body.is_some() { shape.key_labels().len() } else { 0 };
                Ok(rows_read(evaluation, form, evaluation.relation(&parameter, None)?, shape.arity(&widths))
                    .map_err(&fault)?
                    .map(|(rows, relation)| {
                        let per_group = grouped(groups, prefix, input_types.len(), rows.iter().map(|row| shape.key_first(&widths, row)).collect());
                        (per_group, InputRead::Stored(relation))
                    }))
            }
            None => Ok(Ok((shape.unwritten(input, &input_types, groups, evaluation).map_err(&fault)?, InputRead::Default))),
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

/// For each of `relations`, the outputs of an instance in the order its
/// component declares them, whether the caller needs its rows: it is `asked`,
/// or some node of the program's dependency graph reads its node.
fn wanted_outputs(evaluation: &Evaluation<'_>, relations: &[GraphRelation], asked: &GraphRelation) -> Vec<bool> {
    let mut wanted: Vec<bool> = relations.iter().map(|relation| relation == asked).collect();
    for read in evaluation.program.program.graph.reads.iter().flat_map(|reads| reads.iter()) {
        for (relation, wanted) in relations.iter().zip(&mut wanted) {
            *wanted |= relation.node == *read;
        }
    }
    wanted
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
