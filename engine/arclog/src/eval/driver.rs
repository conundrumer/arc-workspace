//! The driver of an evaluation: the evaluation of the entries one request
//! reaches, each entry once, by the parts of the evaluation, the relation
//! of a body from the entries of its parts, and the way into it of a form
//! over a lib component.

use std::cell::RefCell;
use std::sync::Arc;

use super::examples::{self, ExampleScope};
use super::ir::{self, Argument, Arguments, AtomSource, ClauseIr, CompiledBody, IrNode};
use super::join::{self, Budget, JoinInputs, NodeInput, Part};
use super::models::{self, Choice, Entry, Factor};
use super::determinations::Domain;
use super::{cache, instance, plan, proposers, rigid};
use super::{Evaluation, Outcome, ParameterSource, RelationValue, RunFault, Stop};
use crate::hash::StableHashMap;
use crate::program::path::{node_at, NodePath, NodeRef};
use crate::program::{Clause, ClauseKeyword, ProgramRelation};
use crate::relations::{ColumnIndex, Relation, RelationPart, RowSet};
use crate::resolver::ResolvedContent;
use crate::resolver::{DependencyKind, GraphNodeIndex};
use crate::terms::Example;
use crate::trace::{RunRecord, RunTrace};
use crate::types::GraphRelation;

/// The evaluation of the entries one request reaches, each entry once at
/// the current model.
pub(super) struct Driver<'e, 'a> {
    pub(super) evaluation: &'e Evaluation<'a>,
    pub(super) values: RefCell<StableHashMap<(GraphRelation, Option<Example>), RelationValue>>,
    /// The choice of the current model at each factor set, as
    /// [`models`] sets them.
    pub(super) model: RefCell<StableHashMap<Entry, Choice>>,
    /// In an enumeration of models, the factors met since [`models`] last
    /// took them, in the order they were met; `None` outside one.
    pub(super) met: RefCell<Option<Vec<Factor>>>,
    /// The `DET` node whose domain this driver evaluates, outside any
    /// enumeration of models, as [`Evaluation::domain`] gives it.
    pub(super) det: Option<GraphNodeIndex>,
    /// The run trace that each relation this driver evaluates appends a
    /// record to, where the request asked for one.
    pub(super) trace: Option<&'e RefCell<RunTrace>>,
    /// The `DET` relations whose values this driver has read.
    pub(super) determined: std::cell::Cell<u64>,
}

impl<'e, 'a> Driver<'e, 'a> {
    pub(super) fn new(evaluation: &'e Evaluation<'a>) -> Self {
        Driver { evaluation, values: RefCell::default(), model: RefCell::default(), met: RefCell::default(), det: None, trace: None, determined: std::cell::Cell::new(0) }
    }

    /// The driver of `evaluation`, a nested one of a driver that keeps
    /// `trace`, which its relations then append their records to.
    pub(super) fn nested(evaluation: &'e Evaluation<'a>, trace: Option<&'e RefCell<RunTrace>>) -> Self {
        Driver { trace, ..Driver::new(evaluation) }
    }

    /// The driver of the domain of the `DET` node `det`.
    pub(super) fn reading_det(evaluation: &'e Evaluation<'a>, det: GraphNodeIndex) -> Self {
        Driver { det: Some(det), ..Driver::new(evaluation) }
    }

    pub(super) fn program(&self) -> &'a crate::resolver::ResolvedProgram {
        &self.evaluation.program.program
    }

    /// The value of `relation` on `example`, as [`Evaluation::relation`]
    /// gives it.
    pub(super) fn value(&self, relation: &GraphRelation, example: Option<Example>) -> Outcome<RelationValue> {
        let scope = examples::scope_of(self.evaluation.program, relation);
        assert_eq!(scope == ExampleScope::PerExample, example.is_some(), "an example for a relation per example alone");
        let key = (relation.clone(), example);
        if let Some(value) = self.values.borrow().get(&key) {
            return Ok(value.clone());
        }
        let before = self.determined.get();
        let value = self.compute(relation, example)?;
        self.record_run(relation, example, &value, self.determined.get() - before);
        self.values.borrow_mut().insert(key, value.clone());
        Ok(value)
    }

    /// Appends the record of the evaluation of `relation` on `example`
    /// that gave `value`, where the driver keeps a run trace.
    fn record_run(&self, relation: &GraphRelation, example: Option<Example>, value: &RelationValue, determined: u64) {
        let Some(trace) = self.trace else { return };
        let (rows, stop) = match value {
            RelationValue::Rows(rows) => (Some(rows.len()), None),
            RelationValue::Undefined => (None, None),
            RelationValue::Stopped(stop) => (None, Some(stop.bound.into())),
        };
        trace.borrow_mut().push(RunRecord { relation: relation.clone(), example, rows, models: 1, values_determined: determined, stop });
    }

    fn compute(&self, relation: &GraphRelation, example: Option<Example>) -> Outcome<RelationValue> {
        let evaluation = self.evaluation;
        let program = self.program();
        let form = program.form_of(relation.node);
        let mut budget = Budget::new(evaluation.limits, evaluation.session);
        match &program.graph.nodes[relation.node.0 as usize].kind {
            DependencyKind::Clause(_) => self.clauses(relation.node, example),
            DependencyKind::InstanceInput { input, .. } => instance::evaluate_input(evaluation, &self.bodies(), form, input, example),
            DependencyKind::Parameter(name) => self.parameter(relation, name),
            DependencyKind::InstanceOutput { .. } => {
                let outputs = instance::evaluate_instance(evaluation, &self.bodies(), form, example, &mut budget)?;
                record_whole(&budget, outputs.iter().map(|(_, value)| value));
                let mut asked = None;
                let mut values = self.values.borrow_mut();
                for (output, value) in outputs {
                    if output == *relation {
                        asked = Some(value);
                    } else {
                        values.insert((output, example), value);
                    }
                }
                Ok(asked.expect("the value of each output of the instance"))
            }
            DependencyKind::RigidAssembly(_) => {
                let output = relation.output.as_ref().and_then(|path| path.first()).expect("an output of the assembly");
                let value = rigid::evaluate_assembly(evaluation, &self.bodies(), form, output, example, &mut budget);
                recorded(&budget, value)
            }
            DependencyKind::RecursiveInstance(_) => models::walk_value(self, relation, example),
            DependencyKind::Chosen(_) => models::pick_value(self, relation, example),
            DependencyKind::Demonstrated(_) => Err(RunFault {
                message: "a demonstrated relation, whose models this evaluation does not build".into(),
                form: form.clone(),
            }),
            DependencyKind::Fact(_) => unreachable!("an atom reads a fact relation from the task"),
        }
    }

    /// The rows of the `DET` relation `name`: at stored values its stored
    /// rows, typed by its columns; at determined values the rows the
    /// assignment gives it, or else its one value.
    pub(super) fn parameter(&self, relation: &GraphRelation, name: &ProgramRelation) -> Outcome<RelationValue> {
        self.determined.set(self.determined.get() + 1);
        let evaluation = self.evaluation;
        let form = self.program().form_of(relation.node);
        let fault = |message: String| RunFault { message: message.into(), form: form.clone() };
        let stored = match evaluation.parameters.source() {
            ParameterSource::Stored(stored) => stored,
            ParameterSource::Determined(assigned) => {
                if let Some(rows) = assigned.get(name) {
                    return Ok(RelationValue::Rows(rows.clone()));
                }
                return match evaluation.domain(relation.node)? {
                    Domain::Rows(mut values) if values.len() == 1 => Ok(RelationValue::Rows(values.pop().expect("one value in the domain"))),
                    Domain::Rows(values) if values.is_empty() => Err(fault("the `DET` has an empty domain".into())),
                    Domain::Rows(_) => Err(fault("the assignment gives no value to a `DET` with several values in its domain".into())),
                    Domain::Undefined => Ok(RelationValue::Undefined),
                    Domain::Stopped(stop) => Ok(RelationValue::Stopped(stop)),
                };
            }
        };
        let value = stored.get(name).ok_or_else(|| fault("no stored record gives the parameter's rows".into()))?;
        let types = evaluation.program.types.columns(relation).ok_or_else(|| fault("the parameter's columns have no types".into()))?;
        let mut table = evaluation.session.intern.write().expect("an intern table that no panic poisoned");
        let rows = crate::terms::encode_param_value(value, types, evaluation.registry, &mut table)
            .map_err(|error| fault(format!("the stored rows do not read at the parameter's column types: {error:?}")))?;
        let mut set = RowSet::empty(types.len() as u16);
        for row in rows {
            set.insert(row);
        }
        Ok(RelationValue::Rows(Arc::new(join::one_part(set))))
    }

    /// The relation of `node`, the union of the relations of its forms, each
    /// a clause evaluated by generic join.
    fn clauses(&self, node: GraphNodeIndex, example: Option<Example>) -> Outcome<RelationValue> {
        let mut relations = Vec::new();
        for form in self.program().forms_of(node) {
            match self.clause(form, example)? {
                RelationValue::Rows(relation) => relations.push(relation),
                other => return Ok(other),
            }
        }
        Ok(RelationValue::Rows(join::union(relations)))
    }

    /// The relation of the clause at `form` on `example`: the rows of its
    /// proposer where it has no body and derives by one, as [`derivation`]
    /// gives, and otherwise its body's, by generic join.
    pub(super) fn clause(&self, form: &NodePath, example: Option<Example>) -> Outcome<RelationValue> {
        let program = self.program();
        let content = program.content(form).expect("the resolved content of each form");
        let Some(NodeRef::Clause(written)) = node_at(NodeRef::Program(program.program.value()), form) else { panic!("the path of a clause of the program") };
        if let Some(index) = derivation(written, form)? {
            let request = cache::EntryRequest { clause: cache::EntryContent::Form(&content), reads: &[], example, parameters: &[] };
            return self.cached(form, &request, || self.proposed(form, written, index, example));
        }
        let kept: Vec<u32> = (0..written.body.value().conjuncts.len() as u32).collect();
        let (body, inputs) = match self.compiled(form, &kept, example)? {
            Ok(compiled) => compiled,
            Err(value) => return Ok(value),
        };
        let all: Vec<usize> = (0..body.clause.nodes.len()).collect();
        let reads = self.reads(&body.clause, &all, &inputs);
        self.cached(form, &reads.request(&content, example), || Ok(self.body_relation(form, &body, &inputs, example)))
    }

    /// The relation of the conjuncts at `kept` of the body of the clause at
    /// `form` on `example`, as [`Driver::body_relation`] gives it.
    pub(super) fn body(&self, form: &NodePath, kept: &[u32], example: Option<Example>) -> Outcome<RelationValue> {
        match self.compiled(form, kept, example)? {
            Ok((body, inputs)) => Ok(self.body_relation(form, &body, &inputs, example)),
            Err(value) => Ok(value),
        }
    }

    /// The IR of the conjuncts at `kept` of the body of the clause at
    /// `form`, with what its nodes read on `example`, or the body's value
    /// where a read is `undefined` or stopped.
    fn compiled(&self, form: &NodePath, kept: &[u32], example: Option<Example>) -> Outcome<Result<(CompiledBody, JoinInputs), RelationValue>> {
        let body = ir::compile_body(self.evaluation.program, form, kept)
            .map_err(|fault| RunFault { message: format!("the body does not compile: {fault:?}").into(), form: form.clone() })?;
        Ok(self.inputs(&body.clause, scope_at(example), example)?.map(|inputs| (body, inputs)))
    }

    /// The relation of `body`, conjuncts of the body of the clause at
    /// `form`, on `example`, over `inputs`: the product of its parts, each
    /// the value of its own entry in the result cache, as
    /// `docs/engine/synthesis.md#factorized-bodies` gives. The first part
    /// that stops stops the relation.
    fn body_relation(&self, form: &NodePath, body: &CompiledBody, inputs: &JoinInputs, example: Option<Example>) -> RelationValue {
        let clause = &body.clause;
        let order = plan::variable_order(clause, &join::sizes(inputs), &[]);
        let all: Vec<usize> = (0..clause.nodes.len()).collect();
        let mut placed = Vec::new();
        let mut value = None;
        for part in join::parts(clause, &all, &|node| body.conjuncts[node]) {
            let entry = self.part_entry(form, body, &part, inputs);
            match self.part_value(form, body, &part, &entry, inputs, &order, example) {
                RelationValue::Rows(relation) => placed.extend(relation.parts().iter().map(|found| RelationPart {
                    columns: found.columns.iter().map(|column| entry.columns[usize::from(column.0)]).collect(),
                    rows: found.rows.clone(),
                })),
                other => {
                    value = Some(other);
                    break;
                }
            }
        }
        value.unwrap_or_else(|| RelationValue::Rows(Arc::new(join::product(clause, placed))))
    }

    /// The value of `part`, a part of `body` whose entry `entry` gives: the
    /// value the result cache holds for it, or else its rows, from the
    /// entries of the parts that remain once one of its conjuncts is taken
    /// out, where [`Driver::linked`] finds them, or by generic join over the
    /// part alone, which the cache then stores. The part is an evaluation
    /// of its own, under the caps, so its value depends on its entry alone
    /// and on no other entry the cache holds.
    #[allow(clippy::too_many_arguments)]
    fn part_value(
        &self,
        form: &NodePath,
        body: &CompiledBody,
        part: &Part,
        entry: &PartEntry,
        inputs: &JoinInputs,
        order: &plan::VariableOrder,
        example: Option<Example>,
    ) -> RelationValue {
        let evaluation = self.evaluation;
        let request = entry.reads.request(&entry.content, example);
        if let Some(value) = cache::lookup(evaluation.session, &request, form) {
            return value;
        }
        let mut budget = Budget::new(evaluation.limits, evaluation.session);
        let rows = match self.linked(form, body, part, inputs, order, example, &entry.columns, &mut budget) {
            Some(rows) => rows,
            None => join::search(&body.clause, &part.nodes, &[], part.order(order, &[]), &[], inputs, evaluation.registry, &entry.columns, &mut budget),
        };
        let value = match rows {
            Ok(rows) => RelationValue::Rows(Arc::new(join::one_part(rows))),
            Err(bound) => RelationValue::Stopped(Stop { bound, form: form.clone() }),
        };
        record_whole(&budget, [&value]);
        cache::store(evaluation.session, &request, &value);
        value
    }

    /// The rows of `columns` of `part`, a part of `body` with no entry, from
    /// the entries of the parts that remain once one of its conjuncts is
    /// taken out, the last such conjunct first: the generic join of that
    /// conjunct's nodes and those parts' rows, from their indexes, where the
    /// result cache holds the rows of each of those parts and they hold
    /// each variable the conjunct shares with them. `None` where no
    /// conjunct of the part leaves such parts.
    #[allow(clippy::too_many_arguments)]
    fn linked(
        &self,
        form: &NodePath,
        body: &CompiledBody,
        part: &Part,
        inputs: &JoinInputs,
        order: &plan::VariableOrder,
        example: Option<Example>,
        columns: &[ColumnIndex],
        budget: &mut Budget<'_>,
    ) -> Option<Result<RowSet, crate::eval::ReachedBound>> {
        let clause = &body.clause;
        let mut conjuncts: Vec<u32> = part.nodes.iter().map(|&node| body.conjuncts[node]).collect();
        conjuncts.dedup();
        if conjuncts.len() < 2 {
            return None;
        }
        'conjunct: for &conjunct in conjuncts.iter().rev() {
            let (taken, rest): (Vec<usize>, Vec<usize>) = part.nodes.iter().partition(|&&node| body.conjuncts[node] == conjunct);
            let remaining = join::parts(clause, &rest, &|node| body.conjuncts[node]);
            if !remaining.iter().all(|other| other.links(clause, &taken)) {
                continue;
            }
            let mut found = Vec::with_capacity(remaining.len());
            for other in &remaining {
                let entry = self.part_entry(form, body, other, inputs);
                let Some(RelationValue::Rows(relation)) = cache::lookup(self.evaluation.session, &entry.reads.request(&entry.content, example), form) else {
                    continue 'conjunct;
                };
                let variables: Vec<ir::Variable> = entry.columns.iter().map(|column| clause.columns[usize::from(column.0)]).collect();
                let arguments = Arguments(variables.iter().zip(0u16..).map(|(&v, at)| (ColumnIndex(at), Argument::Variable(v))).collect());
                found.push(LinkedPart { relation, arguments, variables, columns: entry.columns });
            }
            return Some(self.link(clause, &taken, found, order, inputs, columns, budget));
        }
        None
    }

    /// The rows of `columns` over the nodes `taken` of `clause` and the
    /// rows of the parts `found` that they link: where every node of `taken` is an atom,
    /// each part's rows first filtered by a semi-join with those atoms, and
    /// then the generic join of `taken` and the rows that remain, in
    /// `order`.
    #[allow(clippy::too_many_arguments)]
    fn link(
        &self,
        clause: &ClauseIr,
        taken: &[usize],
        found: Vec<LinkedPart>,
        order: &plan::VariableOrder,
        inputs: &JoinInputs,
        columns: &[ColumnIndex],
        budget: &mut Budget<'_>,
    ) -> Result<RowSet, crate::eval::ReachedBound> {
        let registry = self.evaluation.registry;
        let own: Vec<ir::Variable> = taken.iter().flat_map(|&node| join::node_variables(&clause.nodes[node])).collect();
        let within = |held: &[ir::Variable]| -> Vec<ir::Variable> { order.0.iter().copied().filter(|v| own.contains(v) || held.contains(v)).collect() };
        let atoms = taken.iter().all(|&node| matches!(clause.nodes[node], IrNode::Atom(_)));
        let mut tries = Vec::with_capacity(found.len());
        let mut held = Vec::new();
        for LinkedPart { relation, arguments, variables, columns: part_columns } in found {
            let relation = if atoms {
                let trie = [(relation, arguments.clone())];
                Arc::new(join::one_part(join::search(clause, taken, &trie, within(&variables), &[], inputs, registry, &part_columns, budget)?))
            } else {
                relation
            };
            held.extend(variables);
            tries.push((relation, arguments));
        }
        join::search(clause, taken, &tries, within(&held), &[], inputs, registry, columns, budget)
    }

    /// The entry of `part`, a part of `body`, the conjuncts of the body of
    /// the clause at `form`, over `inputs`: the part's resolved content, the
    /// relations its nodes read, and the clause's columns that its rows
    /// hold, in their order.
    fn part_entry(&self, form: &NodePath, body: &CompiledBody, part: &Part, inputs: &JoinInputs) -> PartEntry {
        let mut conjuncts: Vec<u32> = part.nodes.iter().map(|&node| body.conjuncts[node]).collect();
        conjuncts.sort_unstable();
        conjuncts.dedup();
        let labels: Vec<crate::program::LabelId> = part.columns(&body.clause).iter().map(|column| body.columns[usize::from(column.0)]).collect();
        let (content, ordered) = self.program().part_content(form, &conjuncts, &labels).expect("the content of a part of a clause's body");
        let columns = ordered
            .iter()
            .map(|label| ColumnIndex(body.columns.iter().position(|found| found == label).expect("a column of the body") as u16))
            .collect();
        PartEntry { content, reads: self.reads(&body.clause, &part.nodes, inputs), columns }
    }

    /// The relations that the nodes `nodes` of `clause` read in `inputs`, a
    /// relation of a `DET` among the parameters and every other among the
    /// reads, each in the order of the nodes and, within a node, of its
    /// own clauses.
    fn reads(&self, clause: &ClauseIr, nodes: &[usize], inputs: &JoinInputs) -> Reads {
        fn walk(driver: &Driver<'_, '_>, node: &IrNode, input: &NodeInput, reads: &mut Reads) {
            match (node, input) {
                (IrNode::Atom(atom), NodeInput::Relation(relation)) => {
                    let is_parameter = matches!(&atom.source, AtomSource::Relation(read)
                        if matches!(driver.program().graph.nodes[read.node.0 as usize].kind, DependencyKind::Parameter(_)));
                    if is_parameter { reads.parameters.push(relation.clone()) } else { reads.reads.push(relation.clone()) }
                }
                (IrNode::Not(filter) | IrNode::Counterexample(filter), NodeInput::Clauses(bodies)) => {
                    for (node, input) in filter.body.nodes.iter().zip(bodies[0].0.iter()) {
                        walk(driver, node, input, reads);
                    }
                }
                (IrNode::Or(union), NodeInput::Clauses(bodies)) => {
                    for (branch, inputs) in union.branches.iter().zip(bodies.iter()) {
                        for (node, input) in branch.nodes.iter().zip(inputs.0.iter()) {
                            walk(driver, node, input, reads);
                        }
                    }
                }
                _ => {}
            }
        }
        let mut reads = Reads::default();
        for &node in nodes {
            walk(self, &clause.nodes[node], &inputs.0[node], &mut reads);
        }
        reads
    }

    /// The value the result cache holds for `request`, made at `form`, or,
    /// where it holds none, the value of `compute`, which the cache then
    /// stores. A fault of `compute` is given and not stored.
    fn cached(&self, form: &NodePath, request: &cache::EntryRequest<'_>, compute: impl FnOnce() -> Outcome<RelationValue>) -> Outcome<RelationValue> {
        let session = self.evaluation.session;
        if let Some(value) = cache::lookup(session, request, form) {
            return Ok(value);
        }
        let mut own = None;
        let key = cache::key(session, request);
        let shared = cache::in_flight(session).get_or_compute(key, || {
            // A computation that ended since the lookup above stored the entry.
            let value = match cache::lookup(session, request, form) {
                Some(value) => Ok(value),
                None => compute().inspect(|value| cache::store(session, request, value)),
            };
            let shared = value.as_ref().ok().and_then(cache::cached);
            own = Some(value);
            shared
        });
        own.unwrap_or_else(|| {
            let shared = shared.expect("a value from the computation another thread ended");
            Ok(shared.map_stop(|bound| Stop { bound, form: form.clone() }))
        })
    }

    /// The relation of `clause`, at `form`, that derives by its proposer at
    /// `index`: the proposer's rows over the task where `example` is `None`
    /// and over that input alone where it is `Some`, each column at the
    /// position of the clause's column that
    /// [`crate::resolver::ResolvedProgram::proposer_columns`] maps it onto,
    /// and `undefined` on an input where they are empty.
    pub(super) fn proposed(&self, form: &NodePath, clause: &Clause, index: usize, example: Option<Example>) -> Outcome<RelationValue> {
        let program = self.program();
        let fault = |message: &str| RunFault { message: message.into(), form: form.clone() };
        let proposer = &clause.proposers[index];
        let names = program.proposer_columns(form, index).ok_or_else(|| fault("the proposer's columns map onto no columns of the clause"))?;
        let positions: Vec<Option<usize>> = names
            .iter()
            .enumerate()
            .map(|(at, name)| match clause.columns.iter().find(|column| column.name == *name) {
                None if clause.columns.is_empty() => Some(at),
                found => found.and_then(|column| program.label_position(form, column.label)).map(|position| usize::from(position.0)),
            })
            .collect();
        let evidence = example.map_or(proposers::Evidence::Task, proposers::Evidence::Input);
        let relation = match proposers::rows(self.evaluation, self.trace, proposer, evidence, form)? {
            RelationValue::Rows(relation) => relation,
            other => return Ok(other),
        };
        if example.is_some() && relation.is_empty() {
            return Ok(RelationValue::Undefined);
        }
        let arity = positions.iter().flatten().count();
        let mut rows = RowSet::empty(arity as u16);
        join::each_row(&relation, &mut |row| {
            let mut placed = vec![row[0]; arity];
            for (&value, position) in row.iter().zip(&positions) {
                if let Some(position) = position {
                    placed[*position] = value;
                }
            }
            rows.insert(placed.into());
        });
        Ok(RelationValue::Rows(Arc::new(join::one_part(rows))))
    }

    /// The relation of `clause`, a clause of the form at `form`, by generic
    /// join over `inputs`, or the stop of the join at a bound.
    fn join(&self, form: &NodePath, clause: &ClauseIr, inputs: &JoinInputs) -> RelationValue {
        let evaluation = self.evaluation;
        let order = plan::variable_order(clause, &join::sizes(inputs), &[]);
        let mut budget = Budget::new(evaluation.limits, evaluation.session);
        let value = match join::join(clause, &order, inputs, evaluation.registry, &mut budget) {
            Ok(relation) => RelationValue::Rows(Arc::new(relation)),
            Err(bound) => RelationValue::Stopped(Stop { bound, form: form.clone() }),
        };
        record_whole(&budget, [&value]);
        value
    }

    /// The way into this driver of the forms over lib components.
    pub(super) fn bodies<'d>(&'d self) -> FormBodies<'d> {
        FormBodies { driver: self }
    }

    /// What each node of `clause` reads, in a clause of `scope` on
    /// `example`, or the clause's value where a read is `undefined` or
    /// stopped.
    fn inputs(&self, clause: &ClauseIr, scope: ExampleScope, example: Option<Example>) -> Outcome<Result<JoinInputs, RelationValue>> {
        let mut inputs = Vec::with_capacity(clause.nodes.len());
        for node in clause.nodes.iter() {
            let bodies: Vec<&ClauseIr> = match node {
                IrNode::Atom(atom) => {
                    let relation = match &atom.source {
                        AtomSource::Fact(fact) => {
                            let on = (*fact == crate::program::FactRelation::Input).then_some(example).flatten();
                            Arc::new(self.evaluation.task.fact_rows(*fact, on))
                        }
                        AtomSource::Undefined(_) => return Ok(Err(RelationValue::Undefined)),
                        AtomSource::Relation(read) => match self.read(read, scope, example)? {
                            RelationValue::Rows(relation) => relation,
                            other => return Ok(Err(other)),
                        },
                    };
                    inputs.push(NodeInput::Relation(relation));
                    continue;
                }
                IrNode::Lib(_) | IrNode::Comparison(_) => {
                    inputs.push(NodeInput::Unread);
                    continue;
                }
                IrNode::Not(filter) | IrNode::Counterexample(filter) => vec![&*filter.body],
                IrNode::Or(union) => union.branches.iter().collect(),
            };
            let mut nested = Vec::with_capacity(bodies.len());
            for body in bodies {
                match self.inputs(body, scope, example)? {
                    Ok(body_inputs) => nested.push(body_inputs),
                    Err(value) => return Ok(Err(value)),
                }
            }
            inputs.push(NodeInput::Clauses(nested.into()));
        }
        Ok(Ok(JoinInputs(inputs.into())))
    }

    /// The value of `relation` as a clause of `scope` on `example` reads it:
    /// a task-wide relation once, a relation per example on the clause's
    /// own example, or, from a task-wide clause, in its lifted form.
    fn read(&self, relation: &GraphRelation, scope: ExampleScope, example: Option<Example>) -> Outcome<RelationValue> {
        match (examples::scope_of(self.evaluation.program, relation), scope) {
            (ExampleScope::TaskWide, _) => self.value(relation, None),
            (ExampleScope::PerExample, ExampleScope::PerExample) => self.value(relation, example),
            (ExampleScope::PerExample, ExampleScope::TaskWide) => {
                let per_example: Outcome<Vec<(Example, RelationValue)>> =
                    self.evaluation.task.examples().map(|e| Ok((e, self.value(relation, Some(e))?))).collect();
                Ok(examples::lift(&per_example?))
            }
        }
    }
}

/// The entry of a part of a body: its resolved content, the relations it
/// reads, and the columns of the body's clause that its rows hold, in the
/// order of the rows' columns.
struct PartEntry {
    content: ResolvedContent,
    reads: Reads,
    columns: Box<[ColumnIndex]>,
}

/// A part that a conjunct links, read as an atom: the rows of its entry,
/// the arguments that read them, the variables at the rows' columns, and
/// the clause's columns that the rows hold, in their order.
struct LinkedPart {
    relation: Arc<Relation>,
    arguments: Arguments,
    variables: Vec<ir::Variable>,
    columns: Box<[ColumnIndex]>,
}

/// The relations an entry reads: the relations of its `DET`s, its
/// parameters, and the other relations, its reads.
#[derive(Default)]
struct Reads {
    reads: Vec<Arc<Relation>>,
    parameters: Vec<Arc<Relation>>,
}

impl Reads {
    /// The request of the entry of `content` that reads these relations, on
    /// `example`.
    fn request<'r>(&'r self, content: &'r ResolvedContent, example: Option<Example>) -> cache::EntryRequest<'r> {
        cache::EntryRequest { clause: cache::EntryContent::Form(content), reads: &self.reads, example, parameters: &self.parameters }
    }
}

/// The way into the driver of a form over a lib component, such as an
/// `INIT` form: the relation of a clause compiled from the form's bodies,
/// with the reads of each body evaluated as the driver evaluates a
/// clause's.
pub struct FormBodies<'d> {
    pub(super) driver: &'d Driver<'d, 'd>,
}

impl FormBodies<'_> {
    /// The relation of `clause`, compiled from bodies of the form at `form`,
    /// on `example`, or task-wide where `example` is `None`: its rows, or
    /// the value of a read of it that is `undefined` or stopped, or the stop
    /// of its join.
    pub fn relation(&self, form: &NodePath, clause: &ClauseIr, example: Option<Example>) -> Outcome<RelationValue> {
        let driver = self.driver;
        let inputs = match driver.inputs(clause, scope_at(example), example)? {
            Ok(inputs) => inputs,
            Err(value) => return Ok(value),
        };
        let session = driver.evaluation.session;
        let reads = driver.reads(clause, &(0..clause.nodes.len()).collect::<Vec<_>>(), &inputs);
        let request = cache::EntryRequest { clause: cache::EntryContent::Body(clause), reads: &reads.reads, example, parameters: &reads.parameters };
        if let Some(value) = cache::lookup(session, &request, form) {
            return Ok(value);
        }
        let value = driver.join(form, clause, &inputs);
        cache::store(session, &request, &value);
        Ok(value)
    }
}

/// The index of the proposer that `clause`, at `form`, derives by, where it
/// has no body and names a proposer: its one proposer, or, in the derived
/// reading by a proposer other than its line's first, the second it holds,
/// as `crate::solver` reads a `DET_OR_RULE` or `RULE_OR_DET` line. A clause
/// with no body and several proposers in any other reading, the stored
/// reading of a line with several, is a fault.
pub(super) fn derivation(clause: &Clause, form: &NodePath) -> Outcome<Option<usize>> {
    if !clause.body.value().conjuncts.is_empty() || clause.proposers.is_empty() {
        return Ok(None);
    }
    match (clause.keyword, clause.proposers.len()) {
        (_, 1) => Ok(Some(0)),
        (ClauseKeyword::Rule, 2) => Ok(Some(1)),
        _ => Err(RunFault { message: "a clause with no body that names several proposers derives by none of them".into(), form: form.clone() }),
    }
}

/// The scope of a clause evaluated on `example`, or task-wide where it is
/// `None`.
fn scope_at(example: Option<Example>) -> ExampleScope {
    if example.is_some() { ExampleScope::PerExample } else { ExampleScope::TaskWide }
}

/// `value`, the value of an evaluation under `budget`, once its session
/// records the budget's counts where the evaluation ended whole, as
/// [`record_whole`] gives. A fault records nothing.
fn recorded(budget: &Budget<'_>, value: Outcome<RelationValue>) -> Outcome<RelationValue> {
    if let Ok(whole) = &value {
        record_whole(budget, [whole]);
    }
    value
}

/// Records the counts of `budget` in its session where its evaluation,
/// which gave `values` and no fault, ended whole: where no value is a stop.
/// A stop at the byte bound, the deadline or a cancellation leaves counts
/// that depend on the machine, a stop at a cap is the fault of its solver,
/// and a stop at a margin leaves the counts of an evaluation cut short.
pub(super) fn record_whole<'v>(budget: &Budget<'_>, values: impl IntoIterator<Item = &'v RelationValue>) {
    if values.into_iter().all(|value| matches!(value, RelationValue::Rows(_) | RelationValue::Undefined)) {
        budget.record();
    }
}
