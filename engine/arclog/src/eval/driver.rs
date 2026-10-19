//! The driver of an evaluation: the evaluation of the entries one request
//! reaches, each entry once, by the parts of the evaluation, and the way
//! into it of a form over a lib component.

use std::cell::RefCell;
use std::sync::Arc;

use super::examples::{self, ExampleScope};
use super::ir::{self, AtomSource, ClauseIr, IrNode};
use super::join::{self, Budget, JoinInputs, NodeInput};
use super::lookup::output_relation;
use super::{cache, instance, output, plan, rigid, unfold};
use super::{Evaluation, GridValue, NoGridColumns, Outcome, RelationValue, RunFault, Stop};
use crate::hash::StableHashMap;
use crate::program::path::NodePath;
use crate::program::ProgramRelation;
use crate::relations::{Relation, RowSet};
use crate::resolver::{DependencyKind, GraphNodeIndex};
use crate::terms::Example;
use crate::types::GraphRelation;

/// The evaluation of the entries one request reaches, each entry once.
pub(super) struct Driver<'e, 'a> {
    pub(super) evaluation: &'e Evaluation<'a>,
    pub(super) values: RefCell<StableHashMap<(GraphRelation, Option<Example>), RelationValue>>,
}

impl<'e, 'a> Driver<'e, 'a> {
    pub(super) fn new(evaluation: &'e Evaluation<'a>) -> Self {
        Driver { evaluation, values: RefCell::default() }
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
            DependencyKind::Clause(_) | DependencyKind::InstanceInput { .. } => self.clauses(relation.node, example),
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
            DependencyKind::RecursiveInstance(_) => {
                let values = unfold::evaluate_unfold(evaluation, &self.bodies(), form, relation, example, 2, &mut budget)?;
                let value = match <[RelationValue; 1]>::try_from(values) {
                    Ok([value]) => Ok(value),
                    Err(_) => Err(RunFault {
                        message: "the instance gives more than one value, so the case has more than one model".into(),
                        form: form.clone(),
                    }),
                };
                recorded(&budget, value)
            }
            DependencyKind::Chosen(_) | DependencyKind::Demonstrated(_) => Err(RunFault {
                message: "a chosen or demonstrated relation, whose models this evaluation does not build".into(),
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
    /// a clause or an instance input evaluated by generic join.
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

    /// The relation of the clause at `form` on `example`.
    pub(super) fn clause(&self, form: &NodePath, example: Option<Example>) -> Outcome<RelationValue> {
        let evaluation = self.evaluation;
        let clause = ir::compile_clause(evaluation.program, form)
            .map_err(|fault| RunFault { message: format!("the body does not compile: {fault:?}").into(), form: form.clone() })?;
        let mut reads = Vec::new();
        let mut parameters = Vec::new();
        let inputs = match self.inputs(&clause, scope_at(example), example, &mut reads, &mut parameters)? {
            Ok(inputs) => inputs,
            Err(value) => return Ok(value),
        };
        let content = self.program().content(form).expect("the resolved content of each form");
        let read_refs: Vec<&Relation> = reads.iter().map(|r: &Arc<Relation>| &**r).collect();
        let parameter_refs: Vec<&Relation> = parameters.iter().map(|r: &Arc<Relation>| &**r).collect();
        let request = cache::EntryRequest { clause: &content, reads: &read_refs, example, parameters: &parameter_refs };
        if let Some(value) = cache::lookup(evaluation.session, &request, form) {
            return Ok(value);
        }
        let mut own = None;
        let key = cache::key(evaluation.session, &request);
        let shared = cache::in_flight(evaluation.session).get_or_compute(key, || {
            // A computation that ended since the lookup above stored the entry.
            let value = match cache::lookup(evaluation.session, &request, form) {
                Some(value) => value,
                None => {
                    let value = self.join(form, &clause, &inputs);
                    cache::store(evaluation.session, &request, &value);
                    value
                }
            };
            let shared = cache::cached(&value);
            own = Some(value);
            shared
        });
        Ok(own.unwrap_or_else(|| {
            let shared = shared.expect("a value from the computation another thread ended");
            shared.map_stop(|bound| Stop { bound, form: form.clone() })
        }))
    }

    /// The relation of `clause`, a clause of the form at `form`, by generic
    /// join over `inputs`, or the stop of the join at a bound.
    fn join(&self, form: &NodePath, clause: &ClauseIr, inputs: &JoinInputs) -> RelationValue {
        let evaluation = self.evaluation;
        let order = plan::variable_order(clause, &join::sizes(inputs));
        let mut budget = Budget::new(evaluation.limits, evaluation.session);
        let value = match join::join(clause, &order, inputs, evaluation.registry, &mut budget) {
            Ok(relation) => RelationValue::Rows(Arc::new(relation)),
            Err(bound) => RelationValue::Stopped(Stop { bound, form: form.clone() }),
        };
        record_whole(&budget, [&value]);
        value
    }

    /// The way into this driver of the forms over lib components.
    fn bodies<'d>(&'d self) -> FormBodies<'d> {
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

    /// The relation of `&output`.
    fn output_relation(&self) -> GraphRelation {
        output_relation(self.evaluation.program).expect("a checked case program derives `&output`")
    }

    /// The grid of `&output` on `example` by `columns`.
    pub(super) fn grid(&self, example: Example, columns: output::GridColumns) -> Outcome<GridValue> {
        Ok(match self.value(&self.output_relation(), Some(example))? {
            RelationValue::Rows(relation) => output::read_grid(&relation, columns).map_or(GridValue::Undefined, GridValue::Grid),
            RelationValue::Undefined => GridValue::Undefined,
            RelationValue::Stopped(stop) => GridValue::Stopped(stop),
        })
    }

    /// The grid columns of `&output`, as [`Evaluation::grid_columns`] gives
    /// them.
    pub(super) fn grid_columns(&self) -> Outcome<Result<output::GridColumns, NoGridColumns>> {
        let relation = self.output_relation();
        let program = self.evaluation.program;
        let form = program.program.form_of(relation.node).clone();
        let types = program.types.columns(&relation).ok_or_else(|| RunFault {
            message: "the columns of `&output` have no types".into(),
            form: form.clone(),
        })?;
        let task = self.evaluation.task;
        let mut solving = Vec::new();
        for columns in output::candidate_columns(types) {
            let mut solves = true;
            for (pair, example) in task.train.iter().zip(task.examples()) {
                match self.grid(example, columns)? {
                    GridValue::Grid(grid) if grid == pair.output => {}
                    GridValue::Stopped(stop) => return Ok(Err(NoGridColumns::Stopped(stop))),
                    GridValue::Grid(_) | GridValue::Undefined => {
                        solves = false;
                        break;
                    }
                }
            }
            if solves {
                solving.push(columns);
            }
        }
        let Some((&first, rest)) = solving.split_first() else { return Ok(Err(NoGridColumns::NoPairSolves)) };
        for &other in rest {
            for example in task.examples() {
                let (a, b) = (self.grid(example, first)?, self.grid(example, other)?);
                if !same_grid(&a, &b) {
                    return Err(RunFault { message: "the grid columns of `&output` are underdetermined".into(), form });
                }
            }
        }
        Ok(Ok(first))
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

/// The scope of a clause evaluated on `example`, or task-wide where it is
/// `None`.
fn scope_at(example: Option<Example>) -> ExampleScope {
    if example.is_some() { ExampleScope::PerExample } else { ExampleScope::TaskWide }
}

/// Whether two grid values give one grid, or are both `undefined`.
fn same_grid(a: &GridValue, b: &GridValue) -> bool {
    match (a, b) {
        (GridValue::Grid(a), GridValue::Grid(b)) => a == b,
        (GridValue::Undefined, GridValue::Undefined) => true,
        _ => false,
    }
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
fn record_whole<'v>(budget: &Budget<'_>, values: impl IntoIterator<Item = &'v RelationValue>) {
    if values.into_iter().all(|value| matches!(value, RelationValue::Rows(_) | RelationValue::Undefined)) {
        budget.record();
    }
}
