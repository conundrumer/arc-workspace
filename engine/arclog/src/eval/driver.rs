//! The driver of an evaluation: the evaluation of the entries one request
//! reaches, each entry once, by the parts of the evaluation, and the way
//! into it of a form over a lib component.

use std::cell::RefCell;
use std::sync::Arc;

use super::examples::{self, ExampleScope};
use super::ir::{self, AtomSource, ClauseIr, IrNode};
use super::join::{self, Budget, JoinInputs, NodeInput};
use super::models::{self, Choice, Entry, Factor};
use super::{cache, instance, plan, proposers, rigid};
use super::{Evaluation, Outcome, RelationValue, RunFault, Stop};
use crate::hash::StableHashMap;
use crate::program::path::{node_at, NodePath, NodeRef};
use crate::program::{Clause, ClauseKeyword, ProgramRelation};
use crate::relations::{Relation, RowSet};
use crate::resolver::{DependencyKind, GraphNodeIndex};
use crate::terms::Example;
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
}

impl<'e, 'a> Driver<'e, 'a> {
    pub(super) fn new(evaluation: &'e Evaluation<'a>) -> Self {
        Driver { evaluation, values: RefCell::default(), model: RefCell::default(), met: RefCell::default() }
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
        let value = self.compute(relation, example)?;
        self.values.borrow_mut().insert(key, value.clone());
        Ok(value)
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

    /// The rows of a parameter at its stored values, typed by its columns.
    pub(super) fn parameter(&self, relation: &GraphRelation, name: &ProgramRelation) -> Outcome<RelationValue> {
        let evaluation = self.evaluation;
        let form = self.program().form_of(relation.node);
        let fault = |message: String| RunFault { message: message.into(), form: form.clone() };
        let value = evaluation.parameters.get(name).ok_or_else(|| fault("no stored record gives the parameter's rows".into()))?;
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
        Ok(RelationValue::Rows(union(relations)))
    }

    /// The relation of the clause at `form` on `example`: the rows of its
    /// proposer where it has no body and derives by one, as [`derivation`]
    /// gives, and otherwise its body's, by generic join.
    pub(super) fn clause(&self, form: &NodePath, example: Option<Example>) -> Outcome<RelationValue> {
        let program = self.program();
        let content = program.content(form).expect("the resolved content of each form");
        if let NodeRef::Clause(written) = node_at(NodeRef::Program(program.program.value()), form).expect("the path of a form of the program") {
            if let Some(index) = derivation(written, form)? {
                let request = cache::EntryRequest { clause: &content, reads: &[], example, parameters: &[] };
                return self.cached(form, &request, || self.proposed(form, written, index, example));
            }
        }
        let evaluation = self.evaluation;
        let clause = ir::compile_clause(evaluation.program, form)
            .map_err(|fault| RunFault { message: format!("the body does not compile: {fault:?}").into(), form: form.clone() })?;
        let mut reads = Vec::new();
        let mut parameters = Vec::new();
        let inputs = match self.inputs(&clause, scope_at(example), example, &mut reads, &mut parameters)? {
            Ok(inputs) => inputs,
            Err(value) => return Ok(value),
        };
        let read_refs: Vec<&Relation> = reads.iter().map(|r: &Arc<Relation>| &**r).collect();
        let parameter_refs: Vec<&Relation> = parameters.iter().map(|r: &Arc<Relation>| &**r).collect();
        let request = cache::EntryRequest { clause: &content, reads: &read_refs, example, parameters: &parameter_refs };
        self.cached(form, &request, || Ok(self.join(form, &clause, &inputs)))
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
    fn proposed(&self, form: &NodePath, clause: &Clause, index: usize, example: Option<Example>) -> Outcome<RelationValue> {
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
        let relation = match proposers::rows(self.evaluation, proposer, evidence, form)? {
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
    /// `example`, each relation read added to `reads` or, for a parameter,
    /// to `parameters`; or the clause's value where a read is `undefined`
    /// or stopped.
    fn inputs(
        &self,
        clause: &ClauseIr,
        scope: ExampleScope,
        example: Option<Example>,
        reads: &mut Vec<Arc<Relation>>,
        parameters: &mut Vec<Arc<Relation>>,
    ) -> Outcome<Result<JoinInputs, RelationValue>> {
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
                    let is_parameter = matches!(&atom.source, AtomSource::Relation(read)
                        if matches!(self.program().graph.nodes[read.node.0 as usize].kind, DependencyKind::Parameter(_)));
                    if is_parameter { parameters.push(relation.clone()) } else { reads.push(relation.clone()) }
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
                match self.inputs(body, scope, example, reads, parameters)? {
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
        match driver.inputs(clause, scope_at(example), example, &mut Vec::new(), &mut Vec::new())? {
            Ok(inputs) => Ok(driver.join(form, clause, &inputs)),
            Err(value) => Ok(value),
        }
    }
}

/// The index of the proposer that `clause`, at `form`, derives by, where it
/// has no body and names a proposer: its one proposer, or, in the derived
/// reading by a proposer other than its line's first, the second it holds,
/// as `crate::solver` reads a `DET_OR_RULE` or `RULE_OR_DET` line. A clause
/// with no body and several proposers in any other reading, the stored
/// reading of a line with several, is a fault.
fn derivation(clause: &Clause, form: &NodePath) -> Outcome<Option<usize>> {
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

/// The union of `relations`, of one arity: the one relation where there is
/// one, and otherwise their rows in one part.
fn union(mut relations: Vec<Arc<Relation>>) -> Arc<Relation> {
    if relations.len() == 1 {
        return relations.pop().expect("one relation");
    }
    let arity = relations.first().expect("a node with a form").arity();
    let mut rows = RowSet::empty(arity);
    for relation in &relations {
        join::each_row(relation, &mut |row| {
            rows.insert(row.into());
        });
    }
    Arc::new(join::one_part(rows))
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
