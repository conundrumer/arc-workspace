//! The evaluation of an `INIT` form: each output of its instance, from the
//! key groups of its inputs, and each input as a clause reads it, each
//! input the rows of its clause, of the `DET` that stores it, or of its
//! default. An evaluation reads the relations of the key and of the inputs
//! first, and groups their rows only where the result cache holds no entry.

use std::sync::Arc;

use super::{ConstructionContext, GroupInputs};
use crate::eval::cache::{self, EntryContent, EntryRequest};
use crate::eval::copies::{self, CopyViolation};
use crate::eval::driver::record_whole;
use crate::eval::init_form::{grouped, instance_at, key_group_rows, key_relation, relation_read, relation_rows, unevaluated, InputClause, InstanceShape};
use crate::eval::join::{self, Budget};
use crate::eval::{Evaluation, FormBodies, Outcome, RelationValue, RunFault, Stop};
use crate::program::path::NodePath;
use crate::program::{Instance, PortName};
use crate::registry::{Component, ComponentKind, InputPort};
use crate::relations::{Relation, Row, RowSet};
use crate::resolver::{DependencyKind, ResolvedContent};
use crate::terms::{Example, TermId};
use crate::types::{GraphRelation, ValueType};

/// The value of the output `asked` of the instance whose `INIT` form stands
/// at `form`, on `example`, or task-wide where it is `None`, from one run of
/// its component's construction over each key group of the instance's
/// inputs, each input's rows as `InputRead::grouped` gives them, with
/// `bodies` evaluating the form's bodies. A body whose value holds no rows
/// gives that value.
///
/// The value stands in the result cache as an entry of the output's node,
/// which reads the relation of the key clause and the relation of each
/// input in the order of the component's inputs, the relations of the
/// `DET`s that store inputs as parameters, and the example. The evaluation
/// reads those relations before it looks up the entry, and groups their
/// rows only where the entry is missing. A run of the construction builds
/// and stores the entry of `asked` and of each other output whose node some
/// node of the program's dependency graph reads.
/// It builds the rows of no other output, and stores no entry for one, so a
/// later request that asks for such an output runs the construction again.
/// An output whose node has no resolved content has no entry, and its value
/// is that of the run.
///
/// The key clause's rows are the groups, and an instance with no key
/// clause has one group, with no key column. A type parameter onto which no
/// place of the form projects and that has no bound is an empty record,
/// contributing zero positions to every input and output row. A key
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
    let key = match key_relation(evaluation, bodies, form, &shape.key_body, &shape.key_labels(), example)? {
        Ok(key) => key,
        Err(value) => return whole(budget, value),
    };

    let mut inputs = Vec::with_capacity(component.inputs.len());
    let mut columns = Vec::with_capacity(component.inputs.len());
    for input in component.inputs.iter() {
        let read = match read_input(evaluation, bodies, form, instance, &shape, input, example)? {
            Ok(read) => read,
            Err(value) => return whole(budget, value),
        };
        inputs.push(read);
        columns.push(shape.port_column_types(&input.port.columns).map_err(&fault)?);
    }

    let entry = EntryReads::of(key.as_ref(), &inputs);
    let widths: Vec<Vec<Option<usize>>> = component.outputs.iter().map(|output| shape.widths(&output.columns)).collect::<Result<_, _>>().map_err(&fault)?;
    let construct = |budget: &mut Budget<'a>, groups: &[Row], group_inputs: &[Vec<RowSet>]| -> Outcome<Vec<(GraphRelation, RelationValue)>> {
        let types: Vec<Box<[ValueType]>> = inputs.iter().map(|read| read.types.clone()).collect();
        let mut rows: Vec<RowSet> = widths.iter().map(|widths| RowSet::empty(shape.arity(widths) as u16)).collect();
        // The content of the construction: the rows of the inputs it reads, and below, the rows of the outputs it writes.
        let read: u64 = group_inputs.iter().flatten().map(|rows| rows.len() as u64).sum();
        if let Err(bound) = budget.charge_content(read) {
            return Ok(each(RelationValue::Stopped(Stop { bound, form: form.clone() })));
        }
        let mut context = ConstructionContext { session: evaluation.session, registry: evaluation.registry, budget };
        // The count of output rows that break each declared row, by output and declared row.
        let mut broken: std::collections::BTreeMap<(usize, usize), usize> = Default::default();
        for (key, inputs) in groups.iter().zip(group_inputs) {
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
                // In the order of encodings, so the rows' order does not follow a construction's hash maps.
                let mut found: Vec<&[TermId]> = values.rows().collect();
                found.sort_unstable_by(|a, b| crate::relations::encoding_order(a, b));
                for values in found {
                    rows.insert(laid_out(widths, key, values));
                }
            }
        }
        let written: u64 = rows.iter().zip(&wanted).filter(|(_, wanted)| **wanted).map(|(rows, _)| rows.len() as u64).sum();
        if let Err(bound) = context.budget.charge_content(written) {
            return Ok(each(RelationValue::Stopped(Stop { bound, form: form.clone() })));
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
        let (groups, group_inputs) = grouped_inputs(evaluation, &shape, key.as_deref(), &inputs).map_err(&fault)?;
        let outputs = construct(budget, &groups, &group_inputs)?;
        record_whole(budget, outputs.iter().map(|(_, value)| value));
        // Each output's entry costs what the construction charged: a request that reads one output makes the others.
        // The cost holds no bytes at its end: the other outputs' rows are held by the value of the output that was asked.
        let cost = if store {
            let mut spent = evaluation.limits.request.spent();
            spent.bytes.net = 0;
            spent
        } else {
            Default::default()
        };
        let mut found = None;
        for (output, value) in outputs {
            if output == *asked {
                found = Some(value);
            } else if let Some(content) = store.then(|| program.node_content(output.node)).flatten() {
                cache::store(session, &entry.request(&content, example), &value, cost);
            }
        }
        Ok(found.expect("the value of each output of the instance"))
    };
    match program.node_content(asked.node) {
        None => run(budget, false),
        Some(content) => bodies.cached(form, &entry.request(&content, example), || run(budget, true)),
    }
}

/// The rows of the input `input` of the instance whose `INIT` form stands
/// at `form`, on `example`, or task-wide where it is `None`, as a clause
/// that reads that input reads them: the rows `InputRead::grouped` gives
/// each key group, in the columns of the port, the group's key at the `key`
/// column as an output row holds it, with `bodies` evaluating the form's
/// bodies. A body whose value holds no rows gives that value.
///
/// The value stands in the result cache as an entry of `relation`, the
/// input's node, which reads the relation of the key clause, the relation of
/// the input's clause, the `DET` that stores the input as a parameter, and
/// the example. The evaluation reads those relations before it looks up the
/// entry, and groups their rows only where the entry is missing. A node with
/// no resolved content has no entry.
pub fn evaluate_input(
    evaluation: &Evaluation<'_>,
    bodies: &FormBodies<'_>,
    form: &NodePath,
    relation: &GraphRelation,
    port: &PortName,
    example: Option<Example>,
) -> Outcome<RelationValue> {
    let fault = |message: String| RunFault { message: message.into(), form: form.clone() };
    let (instance, component) = instance_at(evaluation, form)?;
    let input = component.inputs.iter().find(|input| input.port.name == *port).expect("an input of the component at each instance input node");
    let shape = InstanceShape::of(evaluation.program, form, instance, component);
    let key = match key_relation(evaluation, bodies, form, &shape.key_body, &shape.key_labels(), example)? {
        Ok(key) => key,
        Err(value) => return Ok(value),
    };
    let read = match read_input(evaluation, bodies, form, instance, &shape, input, example)? {
        Ok(read) => read,
        Err(value) => return Ok(value),
    };
    let widths = shape.widths(&input.port.columns).map_err(&fault)?;
    let compute = || {
        let reads = std::slice::from_ref(&read);
        let (groups, per_group) = grouped_inputs(evaluation, &shape, key.as_deref(), reads).map_err(&fault)?;
        let mut rows = RowSet::empty(shape.arity(&widths) as u16);
        for (key, group) in groups.iter().zip(&per_group) {
            for values in group[0].rows() {
                rows.insert(laid_out(&widths, key, values));
            }
        }
        Ok(RelationValue::Rows(Arc::new(join::one_part(rows))))
    };
    match evaluation.program.program.node_content(relation.node) {
        None => compute(),
        Some(content) => {
            let entry = EntryReads::of(key.as_ref(), std::slice::from_ref(&read));
            bodies.cached(form, &entry.request(&content, example), compute)
        }
    }
}

/// What the relations of an input of an instance came from, read and not
/// yet grouped: the relation of its clause, the relation of the `DET` that
/// stores it, or its default.
enum InputSource {
    Clause { written: InputClause, relation: Arc<Relation> },
    /// The `DET`'s relation, the widths of the input's port and the count of
    /// key columns at the start of its rows.
    Stored { relation: Arc<Relation>, widths: Vec<Option<usize>>, key_columns: usize },
    Default,
}

/// An input of an instance with the relation its rows come from: the types
/// of its row positions other than `key`, and the source of its rows.
struct InputRead<'a> {
    input: &'a InputPort,
    types: Box<[ValueType]>,
    source: InputSource,
}

impl InputRead<'_> {
    /// The rows of the input at each of `groups`, in the order of its row
    /// positions other than `key`: the rows its clause gives, or that of the
    /// `DET` that stores it, or the rows [`InstanceShape::unwritten`] gives.
    /// A keyed input is its body joined with the key body, and a broadcast
    /// joins each group.
    fn grouped(&self, shape: &InstanceShape<'_>, groups: &[Row], evaluation: &Evaluation<'_>) -> Result<Vec<RowSet>, String> {
        match &self.source {
            InputSource::Clause { written, relation } => Ok(written.grouped(groups, relation_rows(relation))),
            InputSource::Stored { relation, widths, key_columns } => {
                let rows = relation_rows(relation).iter().map(|row| shape.key_first(widths, row)).collect();
                Ok(grouped(groups, *key_columns, self.types.len(), rows))
            }
            InputSource::Default => shape.unwritten(self.input, &self.types, groups, evaluation),
        }
    }
}

/// The relations an entry of an instance's node reads, as
/// [`EntryRequest`] gives them.
struct EntryReads {
    reads: Vec<Arc<Relation>>,
    parameters: Vec<Arc<Relation>>,
}

impl EntryReads {
    /// The reads of an entry of an instance whose key clause has the
    /// relation `key` and whose inputs are `inputs`, in the order of the
    /// component's inputs.
    fn of(key: Option<&Arc<Relation>>, inputs: &[InputRead<'_>]) -> Self {
        let mut entry = EntryReads { reads: key.into_iter().cloned().collect(), parameters: Vec::new() };
        for input in inputs {
            match &input.source {
                InputSource::Clause { relation, .. } => entry.reads.push(relation.clone()),
                InputSource::Stored { relation, .. } => entry.parameters.push(relation.clone()),
                InputSource::Default => {}
            }
        }
        entry
    }

    /// The request for the entry of the node whose content is `content`.
    fn request<'a>(&'a self, content: &'a ResolvedContent, example: Option<Example>) -> EntryRequest<'a> {
        EntryRequest { clause: EntryContent::Node(content), reads: &self.reads, example, parameters: &self.parameters }
    }
}

/// The key groups of the instance of `shape`, whose key clause has the
/// relation `key`, with the rows of each of `inputs` at each of them, by
/// group. The fault is that of [`InputRead::grouped`].
fn grouped_inputs(evaluation: &Evaluation<'_>, shape: &InstanceShape<'_>, key: Option<&Relation>, inputs: &[InputRead<'_>]) -> Result<(Vec<Row>, Vec<Vec<RowSet>>), String> {
    let groups = key_group_rows(key);
    let mut by_group: Vec<Vec<RowSet>> = vec![Vec::with_capacity(inputs.len()); groups.len()];
    for read in inputs {
        for (group, rows) in by_group.iter_mut().zip(read.grouped(shape, &groups, evaluation)?) {
            group.push(rows);
        }
    }
    Ok((groups, by_group))
}

/// The relation of `input` of `instance`, the `INIT` form at `form` of
/// `shape`, as it is read: the relation its clause gives, or, where the
/// instance writes none and the input's node reads the parameter node of a
/// `DET` of the input, that parameter's, and otherwise its default. A body
/// whose value holds no rows gives that value.
fn read_input<'a>(
    evaluation: &Evaluation<'_>,
    bodies: &FormBodies<'_>,
    form: &NodePath,
    instance: &Instance,
    shape: &InstanceShape<'_>,
    input: &'a InputPort,
    example: Option<Example>,
) -> Outcome<Result<InputRead<'a>, RelationValue>> {
    let fault = |message: String| RunFault { message: message.into(), form: form.clone() };
    let types = shape.port_types(&input.port.columns).map_err(&fault)?;
    let source = match shape.input_clause(evaluation.program, form, input).map_err(&fault)? {
        Some(written) => match relation_read(evaluation, form, bodies.relation(form, &written.clause, example)?, written.arity()).map_err(&fault)? {
            Ok(relation) => InputSource::Clause { written, relation },
            Err(value) => return Ok(Err(value)),
        },
        None => match stored_input(evaluation, form, instance, &input.port.name) {
            Some(parameter) => {
                let widths = shape.widths(&input.port.columns).map_err(&fault)?;
                let key_columns = if shape.key_body.is_some() { shape.key_labels().len() } else { 0 };
                match relation_read(evaluation, form, evaluation.relation(&parameter, None)?, shape.arity(&widths)).map_err(&fault)? {
                    Ok(relation) => InputSource::Stored { relation, widths, key_columns },
                    Err(value) => return Ok(Err(value)),
                }
            }
            None => InputSource::Default,
        },
    };
    Ok(Ok(InputRead { input, types, source }))
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
