//! The driver of an evaluation: the evaluation of the entries one request
//! reaches, each entry once, by the parts of the evaluation, the relation
//! of a body from the entries of its parts, and the way into it of a form
//! over a lib component.

use std::cell::{Cell, RefCell};
use std::convert::Infallible;
use std::sync::Arc;

use super::examples::{self, ExampleScope};
use super::ir::{self, AtomSource, ClauseIr, CompiledBody, IrNode};
use super::join::{self, Budget, JoinInputs, NodeInput, Part};
use super::models::{self, Choice, Entry, Factor};
use super::determinations::{self, Domain};
use super::{cache, carry, init_form, instance, plan, proposers, rigid};
use super::{Charged, Cost, Evaluation, Hit, Outcome, ParameterSource, ReachedBound, RelationValue, RunFault, Stop};
use crate::hash::{StableHash, StableHashMap};
use crate::program::path::{node_at, NodePath, NodeRef};
use crate::program::{Clause, ParamValue, ProgramRelation, RelationRef};
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
            DependencyKind::InstanceInput { input, .. } => instance::evaluate_input(evaluation, &self.bodies(), form, relation, input, example),
            DependencyKind::Parameter(name) => self.parameter(relation, name),
            DependencyKind::InstanceOutput { .. } => instance::evaluate_instance(evaluation, &self.bodies(), form, example, relation, &mut budget),
            DependencyKind::RigidAssembly(_) => {
                let output = relation.output.as_ref().and_then(|path| path.first()).expect("an output of the assembly");
                let value = rigid::evaluate_assembly(evaluation, &self.bodies(), form, output, example, &mut budget);
                recorded(&budget, value)
            }
            DependencyKind::RecursiveInstance(_) => models::walk_value(self, relation, example),
            DependencyKind::Chosen(_) => models::pick_value(self, relation, example),
            DependencyKind::Demonstrated(_) => models::demonstrated_value(self, relation, example),
            DependencyKind::Out(_) => self.out(form, example),
            DependencyKind::Fact(_) => unreachable!("an atom reads a fact relation from the task"),
        }
    }

    /// The relation of the `OUT` form at `form` on `example`: the rows of its
    /// body at its `^` labels, which are its two selected columns.
    fn out(&self, form: &NodePath, example: Option<Example>) -> Outcome<RelationValue> {
        let Some(NodeRef::Out(out)) = node_at(NodeRef::Program(self.program().program.value()), form) else { panic!("an `OUT` form at the form of an `OUT` node") };
        let (clause, _, _) = init_form::out_clause(self.evaluation.program, form, out)
            .map_err(|fault| RunFault { message: format!("the body of the `OUT` form does not compile: {fault:?}").into(), form: form.clone() })?;
        self.bodies().relation(form, &clause, example)
    }

    /// The rows of the `DET` relation `name`: the stored rows of its `assign`
    /// or of its record, typed by its columns, or the rows the assignment
    /// gives it. A `DET` that none of these gives takes its one value, as
    /// [`Driver::one_value`] gives it. A `DET` by its clauses
    /// ([`Driver::is_by_clauses`]) reads no record at stored records.
    pub(super) fn parameter(&self, relation: &GraphRelation, name: &ProgramRelation) -> Outcome<RelationValue> {
        self.determined.set(self.determined.get() + 1);
        let evaluation = self.evaluation;
        let form = self.program().form_of(relation.node);
        let fault = |message: String| RunFault { message: message.into(), form: form.clone() };
        let value = match evaluation.parameters.source() {
            ParameterSource::Stored { assigns, held, .. } if !assigns.contains_key(name) && held.contains_key(name) => {
                return Ok(RelationValue::Rows(held[name].clone()));
            }
            ParameterSource::Stored { .. } => match self.stored_value(relation, name) {
                Some(value) => value,
                None => {
                    self.refuse_assigned_port(relation)?;
                    return self.one_value(relation);
                }
            },
            ParameterSource::Determined(assigned) => {
                return match assigned.get(name) {
                    Some(rows) => {
                        // Held interventions use this program's checked row
                        // schema. A mutation can remove a globally unused
                        // column, so an original assignment is not necessarily
                        // a value of the mutant parameter. Never silently zip
                        // or truncate its cells into that new schema.
                        let types = evaluation.program.types.columns(relation)
                            .ok_or_else(|| fault("the parameter's columns have no types".into()))?;
                        if usize::from(rows.arity()) != types.len() {
                            return Err(fault(format!("determined parameter {name:?} has native arity {}, but its checked schema has {} columns", rows.arity(), types.len())));
                        }
                        Ok(RelationValue::Rows(rows.clone()))
                    },
                    None => self.one_value(relation),
                };
            }
        };
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

    /// The fault of a `DET` that reads an output of an instance that a
    /// witness's `assign` gives rows, where the `DET` has no `assign` of its own:
    /// it is the stored reading of that port, which takes an `assign` of its
    /// own name alone, so nothing in the case reads the assigned rows.
    fn refuse_assigned_port(&self, relation: &GraphRelation) -> Result<(), RunFault> {
        fn reads<'n>(node: NodeRef<'n>, found: &mut Vec<&'n crate::program::OutputName>) {
            if let Some(RelationRef::Output(output)) = node.atom().map(|atom| &atom.relation) {
                found.push(output);
            }
            for child in node.children() {
                reads(child, found);
            }
        }
        if !matches!(self.evaluation.parameters.source(), ParameterSource::Stored { assigns, .. } if !assigns.is_empty()) {
            return Ok(());
        }
        let program = self.program();
        let root = NodeRef::Program(program.program.value());
        for path in program.forms_of(relation.node) {
            let Some(node) = node_at(root, path) else { continue };
            let mut found = Vec::new();
            reads(node, &mut found);
            for output in found.into_iter().filter(|output| matches!(output.of, crate::program::OutputOwner::Instance(_))) {
                if self.evaluation.parameters.assigned(&ProgramRelation::Output(output.clone())).is_none() {
                    continue;
                }
                let text = crate::write::relation_ref(&RelationRef::Output(output.clone()), crate::write::declared);
                return Err(RunFault { message: format!("the `assign` of `{text}` takes no effect: the stored reading of the port takes an `assign` of its own `DET` alone").into(), form: path.clone() });
            }
        }
        Ok(())
    }

    /// The written rows that the stored records give the `DET` relation
    /// `name`: its `assign`, or else its record, which a `DET` by its clauses
    /// ([`Driver::is_by_clauses`]) does not read. `None` where neither gives
    /// it, and at values determined from the evidence.
    fn stored_value(&self, relation: &GraphRelation, name: &ProgramRelation) -> Option<&'a ParamValue> {
        let ParameterSource::Stored { records, assigns, .. } = self.evaluation.parameters.source() else { return None };
        let record = if self.is_by_clauses(relation) { None } else { records.get(name) };
        assigns.get(name).or(record)
    }

    /// Whether the stored records leave the relation `read` with no source of
    /// rows: it is a `DET` that is no `DET` by its clauses, and neither an
    /// `assign` nor a record gives it rows, so that [`Driver::parameter`]
    /// would take its one value, or fault where its domain holds several.
    /// False at values determined from the evidence.
    pub(super) fn lacks_stored_rows(&self, read: &RelationRef) -> bool {
        let (ParameterSource::Stored { .. }, RelationRef::Declared(name)) = (self.evaluation.parameters.source(), read) else { return false };
        let name = ProgramRelation::Declared(name.clone());
        let nodes = &self.program().graph.nodes;
        let Some(node) = nodes.iter().position(|node| matches!(&node.kind, DependencyKind::Parameter(found) if *found == name)) else { return false };
        let relation = GraphRelation { node: GraphNodeIndex(node as u32), output: None };
        let held = matches!(self.evaluation.parameters.source(), ParameterSource::Stored { held, .. } if held.contains_key(&name));
        !held && !self.is_by_clauses(&relation) && self.stored_value(&relation, &name).is_none()
    }

    /// Whether the node of `relation` is a `DET` by its clauses: each of its
    /// forms is a `DET` clause with a body, no proposer and no `ONE` mark, so
    /// that its rows are its clause's, as [`Evaluation::domain`] gives them.
    fn is_by_clauses(&self, relation: &GraphRelation) -> bool {
        determinations::is_by_clauses(self.program(), relation.node)
    }

    /// The one value in the domain of the `DET` relation `relation`, for a
    /// `DET` that no stored value and no assignment gives.
    fn one_value(&self, relation: &GraphRelation) -> Outcome<RelationValue> {
        let form = self.program().form_of(relation.node);
        let fault = |message: &str| RunFault { message: message.into(), form: form.clone() };
        match self.evaluation.domain(relation.node)? {
            Domain::Rows(mut values) if values.len() == 1 => Ok(RelationValue::Rows(values.pop().expect("one value in the domain"))),
            Domain::Rows(values) if values.is_empty() => Err(fault("the `DET` has an empty domain")),
            Domain::Rows(_) => Err(fault("the assignment gives no value to a `DET` with several values in its domain")),
            Domain::Undefined => Ok(RelationValue::Undefined),
            Domain::Stopped(stop) => Ok(RelationValue::Stopped(stop)),
        }
    }

    /// The relation of `node`, the union of the relations of its forms, each
    /// a clause evaluated by generic join. Where it has several forms, the
    /// walk of each form's product is counted as [`join::charge_walk`]
    /// gives, and the first stop is the value.
    fn clauses(&self, node: GraphNodeIndex, example: Option<Example>) -> Outcome<RelationValue> {
        let forms = self.program().forms_of(node);
        let mut relations = Vec::new();
        for form in forms {
            match self.clause(form, example)? {
                RelationValue::Rows(relation) => relations.push(relation),
                other => return Ok(other),
            }
        }
        if relations.len() > 1 {
            for (form, relation) in forms.iter().zip(&relations) {
                if let Err(stop) = join::charge_walk(self.evaluation, relation, form) {
                    return Ok(RelationValue::Stopped(stop));
                }
            }
        }
        if relations.len() > 1 {
            // The union walks the rows of each relation.
            let rows = relations.iter().map(|relation| relation.len()).fold(0u64, u64::saturating_add);
            if let Err(bound) = self.evaluation.limits.request.charge(rows) {
                return Ok(RelationValue::Stopped(Stop { bound, form: self.program().form_of(node).clone() }));
            }
        }
        Ok(RelationValue::Rows(join::union(relations)))
    }

    /// The relation of the clause at `form` on `example`: the rows of its
    /// proposer where it has no body and derives by one, as [`derivation`]
    /// gives, and otherwise its body's, by generic join.
    pub(super) fn clause(&self, form: &NodePath, example: Option<Example>) -> Outcome<RelationValue> {
        let program = self.program();
        let content = self.evaluation.program.content(form).expect("the resolved content of each form");
        let Some(NodeRef::Clause(written)) = node_at(NodeRef::Program(program.program.value()), form) else { panic!("the path of a clause of the program") };
        if let Some(index) = derivation(written, form)? {
            let request = cache::EntryRequest { clause: cache::EntryContent::Form(&content), reads: &[], example, parameters: &[] };
            return self.cached(form, &request, None, || self.proposed(form, written, index, example));
        }
        let (body, inputs) = match self.compiled(form, &every_conjunct(written), example)? {
            Ok(compiled) => compiled,
            Err(value) => return Ok(value),
        };
        let all: Vec<usize> = (0..body.clause.nodes.len()).collect();
        let reads = self.reads(&body.clause, &all, &inputs);
        let shape = || carry::body_shape(&body);
        let measured = ir::measures().then(|| (crate::clock::Stopwatch::start(), super::RequestWork::latest().map_or(0, |request| request.count())));
        let value = self.cached(form, &reads.request(&content, example), Some(&shape), || Ok(self.body_relation(form, &body, &inputs, example)));
        if let Some((start, before)) = measured {
            let work = super::RequestWork::latest().map_or(0, |request| request.count()).saturating_sub(before);
            if work > 0 {
                let path: Vec<String> = form.0.iter().map(|step| step.0.to_string()).collect();
                eprintln!("arclog-join-measure form={} nodes={} work={work} ns={}", path.join("."), body.clause.nodes.len(), start.elapsed().nanos());
            }
        }
        value
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
    /// `form`, with its nodes in canonical order
    /// ([`CheckedProgram::joined_body`]) and what they read on `example`, or
    /// the body's value where a read is `undefined` or stopped.
    fn compiled(&self, form: &NodePath, kept: &[u32], example: Option<Example>) -> Outcome<Result<(Arc<CompiledBody>, JoinInputs), RelationValue>> {
        let body = self
            .evaluation
            .program
            .joined_body(form, kept)
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
        let order = plan::variable_order(clause, &join::sizes(clause, inputs), &[]);
        let all: Vec<usize> = (0..clause.nodes.len()).collect();
        let mut placed: Vec<(u32, RelationPart)> = Vec::new();
        let mut value = None;
        let parts = join::parts(clause, &all, &|node| body.conjuncts[node]);
        for part in parts {
            let written = part.nodes.iter().map(|&node| clause.written[node]).min().unwrap_or(0);
            let entry = self.part_entry(form, body, &part, inputs);
            match self.part_value(form, body, &part, &entry, inputs, &order, example) {
                RelationValue::Rows(relation) => placed.extend(relation.parts().iter().map(|found| (written, RelationPart {
                    columns: found.columns.iter().map(|column| entry.columns[usize::from(column.0)]).collect(),
                    rows: found.rows.clone(),
                }))),
                other => {
                    value = Some(other);
                    break;
                }
            }
        }
        // The parts are joined in the clause's canonical order. The relation lists
        // them in the order of the clause as compiled, which its readers follow.
        placed.sort_by_key(|(written, _)| *written);
        value.unwrap_or_else(|| RelationValue::Rows(Arc::new(join::product(clause, placed.into_iter().map(|(_, part)| part).collect()))))
    }

    /// The value of `part`, a part of `body` whose entry `entry` gives: the
    /// value the result cache holds for it, or by generic join over the
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
        if let Some(found) = cache::lookup(evaluation.session, evaluation.limits, &request, form) {
            return found.value;
        }
        let compute = || {
            let limits = evaluation.limits;
            let (value, cost) = limits.request.measure_holding(|| {
                let mut budget = Budget::new(evaluation.limits, evaluation.session);
                let Ok(value) = self.holding_stops::<Infallible>(&request, || {
                    let relation = join::search_part(&body.clause, &part.nodes, part.order(order, &[]), inputs, evaluation.registry, &entry.columns, &mut budget);
                    Ok(match relation {
                        Ok(relation) => RelationValue::Rows(Arc::new(relation)),
                        Err(bound) => RelationValue::Stopped(Stop { bound, form: form.clone() }),
                    })
                });
                record_whole(&budget, [&value]);
                value
            }, cache::held_by);
            cache::store(evaluation.session, &request, &value, cost);
            Ok(value)
        };
        let shape = || carry::part_shape(&body.clause, part, order, &entry.columns);
        match self.carrying(form, &request, &shape, &Cell::new(Cost::default()), compute) {
            Ok(value) => value,
            Err(fault) => unreachable!("the evaluation of a part gives no fault: {fault:?}"),
        }
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
        let (content, ordered) = self.evaluation.program.part_content(form, &conjuncts, &labels).expect("the content of a part of a clause's body");
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
    /// stores. A fault of `compute` is given and not stored. Where `shape` is
    /// given, the computation is carried across the walks that carry one
    /// ([`Driver::carrying`]).
    ///
    /// A value that the cache holds charges the cost recorded in its entry
    /// ([`cache::lookup`]), and so does a value that another thread
    /// computed while this one waited for it, so the evaluation's counts are
    /// those of one that computed the entry. Where the recorded cost would
    /// not fit under a cap, the entry is computed here instead.
    fn cached(&self, form: &NodePath, request: &cache::EntryRequest<'_>, shape: Option<&dyn Fn() -> StableHash>, compute: impl FnOnce() -> Outcome<RelationValue>) -> Outcome<RelationValue> {
        let session = self.evaluation.session;
        let limits = self.evaluation.limits;
        if let Some(found) = cache::lookup(session, limits, request, form) {
            return Ok(found.value);
        }
        let compute = RefCell::new(Some(compute));
        let evaluate = || {
            let compute = compute.borrow_mut().take().expect("an entry is computed once");
            self.compute_entry(form, request, shape, compute)
        };
        let mut own = None;
        let key = cache::key(session, request);
        let shared = cache::in_flight(session).get_or_compute(key, || {
            // A computation that ended since the lookup above stored the entry.
            let (value, cost) = match cache::lookup(session, limits, request, form) {
                Some(found) => (Ok(found.value), found.cost),
                None => evaluate(),
            };
            let shared = value.as_ref().ok().and_then(cache::cached).map(|value| Hit::new(value, cost));
            own = Some(value);
            shared
        });
        own.unwrap_or_else(|| {
            let hit = shared.expect("a value from the computation another thread ended");
            match hit.charge(&limits.request, limits.table_work.as_ref(), session) {
                Charged::Value(value) => Ok(value.map_stop(|bound| Stop { bound, form: form.clone() })),
                Charged::Stopped(_, bound) => Ok(RelationValue::Stopped(Stop { bound, form: form.clone() })),
                Charged::Misfit => evaluate().0,
            }
        })
    }

    /// The value of `compute`, the evaluation of the entry `request`, with
    /// what it charged, as [`Driver::cached`] needs them. The value is stored
    /// in the cache with its cost, or is that of a kept computation
    /// ([`Driver::carrying`]).
    fn compute_entry(&self, form: &NodePath, request: &cache::EntryRequest<'_>, shape: Option<&dyn Fn() -> StableHash>, compute: impl FnOnce() -> Outcome<RelationValue>) -> (Outcome<RelationValue>, Cost) {
        let session = self.evaluation.session;
        let limits = self.evaluation.limits;
        let spent = Cell::new(Cost::default());
        let run = || {
            let (value, cost) = limits.request.measure_holding(|| self.holding_stops(request, compute), |value| value.as_ref().map_or(0, cache::held_by));
            spent.set(cost);
            if let Ok(value) = &value {
                cache::store(session, request, value, cost);
            }
            value
        };
        let value = match shape {
            Some(shape) => self.carrying(form, request, shape, &spent, run),
            None => run(),
        };
        (value, spent.get())
    }

    /// The value of `compute`, the evaluation of the entry `request` that
    /// the result cache holds no value of, which stores the value in the
    /// cache. Where the limits carry computations ([`carry`]) and bound the
    /// evaluation by nothing that depends on the time, the value is the one
    /// of a kept computation that replays, and otherwise `compute` is
    /// captured and kept. `shape` is the digest of what the search of the
    /// entry reads beside its request. `spent` takes the cost of a kept
    /// computation that replays; `compute` sets it itself.
    fn carrying(&self, form: &NodePath, request: &cache::EntryRequest<'_>, shape: &dyn Fn() -> StableHash, spent: &Cell<Cost>, compute: impl FnOnce() -> Outcome<RelationValue>) -> Outcome<RelationValue> {
        let limits = self.evaluation.limits;
        let (Some(carry), Some(_), None, None) = (&limits.carry, &limits.table_work, &limits.held_stops, &limits.copies) else {
            return compute();
        };
        let session = self.evaluation.session;
        let key = carry::CarryKey::new(request, shape());
        match carry.replay(limits, session, &key, form) {
            Some((value, cost)) => {
                spent.set(cost);
                Ok(value)
            }
            None => carry.capture(limits, session, key, form, compute),
        }
    }

    /// The value of `compute`, the evaluation of the entry `request`, where
    /// the evaluation runs for a decode, with the stops that the decode holds
    /// ([`super::values::HeldStops`]). The stop held for the entry is taken
    /// at the form that stopped, in place of an evaluation that tries
    /// bindings, where the evaluation runs for a bounded observation and the
    /// stop is at its table work cap.
    ///
    /// Otherwise the stop of `compute` is held: a stop at the table work cap
    /// where the evaluation began within the cap, which an evaluation that
    /// begins past the cap does not reach.
    fn holding_stops<E>(&self, request: &cache::EntryRequest<'_>, compute: impl FnOnce() -> Result<RelationValue, E>) -> Result<RelationValue, E> {
        let session = self.evaluation.session;
        let limits = self.evaluation.limits;
        let Some(held) = &limits.held_stops else { return compute() };
        // The count of one assignment starts from none, and an entry that stops it there stops
        // another assignment's count that began further on only by the work it did before.
        if !limits.table_work.as_ref().is_some_and(|work| work.is_capped() && !work.is_scoped()) {
            return compute();
        }
        let entry_key = || cache::key(session, request);
        if !held.is_empty() {
            if let Some(stop) = held.table_work_stop(&entry_key()) {
                return Ok(RelationValue::Stopped(stop));
            }
        }
        let began_within_cap = limits.table_work.as_ref().is_some_and(|work| !work.is_past_cap());
        let value = compute()?;
        if let RelationValue::Stopped(stop) = &value
            && matches!(stop.bound, ReachedBound::TableWork { .. })
            && began_within_cap
        {
            held.hold_table_work(entry_key(), stop.clone());
        }
        Ok(value)
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
        // The placing walks each row of the proposer's relation.
        if let Err(bound) = self.evaluation.limits.request.charge(relation.len()) {
            return Ok(RelationValue::Stopped(Stop { bound, form: form.clone() }));
        }
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
        let order = plan::variable_order(clause, &join::sizes(clause, inputs), &[]);
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
    /// stopped. A clause that names a relation no form declares is
    /// `undefined` whatever else it reads, so nothing is read for it. The
    /// reads stand in the order of the nodes, and the branches of a union in
    /// their canonical order, and the first read that is `undefined` or
    /// stopped gives the value.
    fn inputs(&self, clause: &ClauseIr, scope: ExampleScope, example: Option<Example>) -> Outcome<Result<JoinInputs, RelationValue>> {
        if names_undefined(clause) {
            return Ok(Err(RelationValue::Undefined));
        }
        self.read_inputs(clause, scope, example)
    }

    /// [`Driver::inputs`], for a clause that names no undeclared relation.
    fn read_inputs(&self, clause: &ClauseIr, scope: ExampleScope, example: Option<Example>) -> Outcome<Result<JoinInputs, RelationValue>> {
        let mut inputs = Vec::with_capacity(clause.nodes.len());
        for node in clause.nodes.iter() {
            let bodies: Vec<&ClauseIr> = match node {
                IrNode::Atom(atom) => {
                    let relation = match &atom.source {
                        AtomSource::Fact(fact) => {
                            let on = fact.per_example().then_some(example).flatten();
                            self.evaluation.session.fact_relation(&self.evaluation.task, *fact, on)
                        }
                        AtomSource::Undefined(_) => return Ok(Err(RelationValue::Undefined)),
                        AtomSource::Key(key) => match self.bodies().relation(&key.form, &key.clause, example)? {
                            RelationValue::Rows(relation) => relation,
                            other => return Ok(Err(other)),
                        },
                        AtomSource::Relation(read) => match self.read(read, scope, example, atom.train_only)? {
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
            let order: Vec<usize> = match node {
                IrNode::Or(union) => union.in_canonical_order().collect(),
                _ => (0..bodies.len()).collect(),
            };
            let mut nested: Vec<Option<JoinInputs>> = bodies.iter().map(|_| None).collect();
            for at in order {
                match self.read_inputs(bodies[at], scope, example)? {
                    Ok(body_inputs) => nested[at] = Some(body_inputs),
                    Err(value) => return Ok(Err(value)),
                }
            }
            inputs.push(NodeInput::Clauses(nested.into_iter().map(|found| found.expect("the inputs of each branch")).collect()));
        }
        Ok(Ok(JoinInputs(inputs.into())))
    }

    /// The value of `relation` as a clause of `scope` on `example` reads it:
    /// a task-wide relation once, a relation per example on the clause's
    /// own example, or, from a task-wide clause, in its lifted form.
    ///
    /// A lifted read with `train_only` lifts over the train examples alone,
    /// so its value is defined wherever the relation is defined on each of
    /// them, whatever its entry on a test example. The lift's walk of each
    /// example's product is counted as [`join::charge_walk`] gives, at the
    /// relation's form, and the first stop is the value.
    fn read(&self, relation: &GraphRelation, scope: ExampleScope, example: Option<Example>, train_only: bool) -> Outcome<RelationValue> {
        match (examples::scope_of(self.evaluation.program, relation), scope) {
            (ExampleScope::TaskWide, _) => self.value(relation, None),
            (ExampleScope::PerExample, ExampleScope::PerExample) => self.value(relation, example),
            (ExampleScope::PerExample, ExampleScope::TaskWide) => {
                let task = &self.evaluation.task;
                let lifted_over: Vec<Example> = if train_only { task.train_examples().collect() } else { task.examples().collect() };
                let per_example: Vec<(Example, RelationValue)> = lifted_over.into_iter().map(|e| Ok((e, self.value(relation, Some(e))?))).collect::<Outcome<_>>()?;
                let form = self.program().form_of(relation.node);
                for (_, value) in &per_example {
                    if let RelationValue::Rows(rows) = value
                        && let Err(stop) = join::charge_walk(self.evaluation, rows, form)
                    {
                        return Ok(RelationValue::Stopped(stop));
                    }
                }
                Ok(examples::lift(&per_example))
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
        let clause = clause.in_canonical_order();
        let inputs = match driver.inputs(clause, scope_at(example), example)? {
            Ok(inputs) => inputs,
            Err(value) => return Ok(value),
        };
        let session = driver.evaluation.session;
        let reads = driver.reads(clause, &(0..clause.nodes.len()).collect::<Vec<_>>(), &inputs);
        let request = cache::EntryRequest { clause: cache::EntryContent::Body(clause), reads: &reads.reads, example, parameters: &reads.parameters };
        let limits = driver.evaluation.limits;
        if let Some(found) = cache::lookup(session, limits, &request, form) {
            return Ok(found.value);
        }
        let (Ok(value), cost) = limits.request.measure_holding(|| driver.holding_stops::<Infallible>(&request, || Ok(driver.join(form, clause, &inputs))), |value| value.as_ref().map_or(0, cache::held_by));
        cache::store(session, &request, &value, cost);
        Ok(value)
    }

    /// A state-local body query at explicit key/cursor bindings. These
    /// bindings are part of the request, so it uses the bound native join
    /// rather than a cache key for an unbound body.
    pub(super) fn bound_relation(&self,form:&NodePath,clause:&ClauseIr,example:Option<Example>,bound:&[(ir::Variable,crate::terms::TermId)])->Outcome<RelationValue> {
        let clause=clause.in_canonical_order();
        let inputs=match self.driver.inputs(clause,scope_at(example),example)? {Ok(inputs)=>inputs,Err(value)=>return Ok(value)};
        let evaluation=self.driver.evaluation;
        let order=plan::variable_order(clause,&join::sizes(clause, &inputs),&bound.iter().map(|(v,_)|*v).collect::<Vec<_>>());
        let mut budget=Budget::new(evaluation.limits,evaluation.session);
        let value=match join::join_at(clause,&order,&inputs,evaluation.registry,bound,&mut budget) {Ok(rows)=>RelationValue::Rows(Arc::new(rows)),Err(bound)=>RelationValue::Stopped(Stop {bound,form:form.clone()})};
        record_whole(&budget,[&value]);Ok(value)
    }

    /// The value the result cache holds for `request`, made at `form`, or,
    /// where it holds none, the value of `compute`, which the cache then
    /// stores, as the driver does for a clause.
    pub fn cached(&self, form: &NodePath, request: &cache::EntryRequest<'_>, compute: impl FnOnce() -> Outcome<RelationValue>) -> Outcome<RelationValue> {
        self.driver.cached(form, request, None, compute)
    }
}

/// The index of the proposer that `clause`, at `form`, derives by, where it
/// has no body and names a proposer: its one proposer. A clause with no body
/// that names several proposers is a fault: a `DET` or `RULE` names one, and
/// each reading of a `DET_OR_RULE` or `RULE_OR_DET` line names the proposer
/// it is by alone, as `crate::solver` reads the line.
pub(super) fn derivation(clause: &Clause, form: &NodePath) -> Outcome<Option<usize>> {
    match (clause.body.value().conjuncts.is_empty(), clause.proposers.len()) {
        (false, _) | (true, 0) => Ok(None),
        (true, 1) => Ok(Some(0)),
        (true, _) => Err(RunFault { message: "a clause with no body names several proposers, and a `DET` or `RULE` names one".into(), form: form.clone() }),
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
/// A stop at the request work cap, at a byte budget or a cancellation leaves counts
/// that depend on the budget or the caller, a stop at a cap is the fault of its solver,
/// and a stop at a margin leaves the counts of an evaluation cut short.
pub(super) fn record_whole<'v>(budget: &Budget<'_>, values: impl IntoIterator<Item = &'v RelationValue>) {
    if values.into_iter().all(|value| matches!(value, RelationValue::Rows(_) | RelationValue::Undefined)) {
        budget.record();
    }
}

/// Whether `clause`, or a clause nested in one of its nodes, reads a relation
/// that no form declares.
fn names_undefined(clause: &ClauseIr) -> bool {
    clause.nodes.iter().any(|node| match node {
        IrNode::Atom(atom) => match &atom.source {
            AtomSource::Undefined(_) => true,
            AtomSource::Key(key) => names_undefined(&key.clause),
            _ => false,
        },
        IrNode::Not(filter) | IrNode::Counterexample(filter) => names_undefined(&filter.body),
        IrNode::Or(union) => union.branches.iter().any(names_undefined),
        IrNode::Lib(_) | IrNode::Comparison(_) => false,
    })
}

/// The indexes of each conjunct of the body of `clause`.
fn every_conjunct(clause: &crate::program::Clause) -> Vec<u32> {
    (0..clause.body.value().conjuncts.len() as u32).collect()
}

/// The IR that the evaluation joins for the whole body of `clause`, the
/// clause at `form`: the one compile of the body, which the clause's rows and
/// its column flows read.
pub(crate) fn clause_body(program: &crate::check::CheckedProgram, form: &NodePath, clause: &crate::program::Clause) -> Result<Arc<CompiledBody>, ir::CompileFault> {
    program.compiled_body(form, &every_conjunct(clause))
}
