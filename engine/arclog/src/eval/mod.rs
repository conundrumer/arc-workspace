//! The evaluation of one checked case program at given parameter values, on
//! one task, in one task session: its entry points, its caps and its stops.
//!
//! The evaluation runs on demand: [`Evaluation::relation`] and
//! [`Evaluation::output`] evaluate the entries the request reaches and no
//! other. Each relation of the dependency graph is evaluated once from its
//! inputs, in topological order, since a checked case program is acyclic.
//!
//! The driver here calls each part through the functions of the part's own
//! file: [`ir`] and [`filters`] compile a body, [`plan`] orders its
//! variables, [`join`] evaluates it, [`examples`] gives the reads of a
//! relation per example and its lifted form, [`instance`], [`rigid`] and
//! [`unfold`] evaluate the forms over lib components, [`output`] reads the
//! grid, [`cache`] looks up and stores entries, and [`pool`] runs
//! independent entries in parallel.

pub mod cache;
pub mod examples;
pub mod filters;
pub mod instance;
pub mod ir;
pub mod join;
pub mod output;
pub mod plan;
pub mod pool;
pub mod rigid;
pub mod unfold;

use std::cell::RefCell;
use std::sync::Arc;
use std::sync::atomic::{AtomicBool, Ordering};

use crate::check::CheckedProgram;
use crate::diagnostic::{Diagnostic, DiagnosticKind, Location, Severity};
use crate::hash::StableHashMap;
use crate::program::path::NodePath;
use crate::program::{DeclaredName, ParamValue, ProgramRelation, RelationName};
use crate::registry::Registry;
use crate::relations::{Relation, RowSet};
use crate::resolver::{DependencyKind, GraphNodeIndex};
use crate::session::{ReachedSessionBound, TaskSession};
use crate::solver::CaseName;
use crate::task::{Grid, Task};
use crate::terms::{Example, ReachedMarginBound};
use crate::types::GraphRelation;
use examples::ExampleScope;
use ir::{AtomSource, ClauseIr, IrNode};
use join::{Budget, JoinInputs, NodeInput};

/// The two caps of an evaluation, both counts, so neither depends on the
/// machine. They are fixed for a task session, so a stop at either holds
/// for every later request of the same entry.
#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub struct Caps {
    /// The bindings a clause's join, or a native construction, may try.
    pub work: u64,
    /// The rows the parts of a relation may hold.
    pub rows: u64,
}

impl Caps {
    /// The caps of every task session, set from the engine's counts on the
    /// corpus.
    pub const PROVISIONAL: Caps = Caps { work: 1 << 32, rows: 1 << 24 };
}

/// The bound an evaluation reached.
#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub enum ReachedBound {
    /// The work cap, [`Caps::work`].
    Work { cap: u64 },
    /// The row cap, [`Caps::rows`].
    Rows { cap: u64 },
    /// A Box with a margin outside a signed byte.
    Margin(ReachedMarginBound),
    /// The task session's byte bound.
    SessionBytes(ReachedSessionBound),
    /// The deadline of the evaluation.
    Deadline,
    /// A cancellation of the evaluation.
    Cancelled,
}

impl ReachedBound {
    /// Whether a stop at this bound is the same at every later request of
    /// its entry, so the result cache stores it: a stop at a cap or at a
    /// margin. A stop at the session's byte bound, at the deadline or by a
    /// cancellation depends on the machine or the session's history, and is
    /// stored nowhere.
    pub fn is_stored(self) -> bool {
        match self {
            ReachedBound::Work { .. } | ReachedBound::Rows { .. } | ReachedBound::Margin(_) => true,
            ReachedBound::SessionBytes(_) | ReachedBound::Deadline | ReachedBound::Cancelled => false,
        }
    }

    /// The bound as a diagnostic's message names it.
    fn describe(self) -> String {
        match self {
            ReachedBound::Work { cap } => format!("the work cap of {cap} bindings"),
            ReachedBound::Rows { cap } => format!("the row cap of {cap} rows"),
            ReachedBound::Margin(reached) => format!("a Box margin outside a signed byte, {:?}", reached.margins),
            ReachedBound::SessionBytes(reached) => {
                format!("the session's byte bound of {} bytes, at {} bytes", reached.bound.bytes, reached.bytes)
            }
            ReachedBound::Deadline => "the deadline".to_owned(),
            ReachedBound::Cancelled => "a cancellation".to_owned(),
        }
    }
}

/// An evaluation that reached a bound: the bound, and the form of the
/// clause, the instance or the assembly that reached it. A stop is an alert
/// and no relation, so the case gives no output on the input it stopped
/// on.
#[derive(Clone, PartialEq, Eq, Debug)]
pub struct Stop {
    pub bound: ReachedBound,
    /// The path in the case program of the form that reached the bound.
    pub form: NodePath,
}

impl Stop {
    /// The stop as a diagnostic of kind
    /// [`crate::diagnostic::DiagnosticKind::Bound`], an alert at the form's
    /// path, in `cases`.
    pub fn diagnostic(&self, cases: &[CaseName]) -> Diagnostic {
        Diagnostic {
            kind: DiagnosticKind::Bound,
            severity: Severity::Alert,
            message: format!("the evaluation of the form reached {}", self.bound.describe()).into(),
            location: Location::Path(self.form.clone()),
            cases: cases.into(),
        }
    }
}

/// A fault of a run that is no bound, such as a parameter whose stored
/// rows its column types cannot read, or a lib name that the table of
/// constructions lacks.
#[derive(Clone, PartialEq, Eq, Debug)]
pub struct RunFault {
    pub message: Box<str>,
    /// The path in the case program of the form the fault stands at.
    pub form: NodePath,
}

impl RunFault {
    /// The fault as a diagnostic of kind
    /// [`crate::diagnostic::DiagnosticKind::Run`], an error at the form's
    /// path, in `cases`.
    pub fn diagnostic(&self, cases: &[CaseName]) -> Diagnostic {
        Diagnostic {
            kind: DiagnosticKind::Run,
            severity: Severity::Error,
            message: self.message.clone(),
            location: Location::Path(self.form.clone()),
            cases: cases.into(),
        }
    }
}

/// The value of a relation on a request: its rows, `undefined` where it
/// reads a relation that no block of the case derives
/// (`docs/arclog/arclog.md#alts`), or a stop.
#[derive(Clone, Debug)]
pub enum RelationValue {
    Rows(Arc<Relation>),
    Undefined,
    Stopped(Stop),
}

/// The outcome of a request: a value, or a fault of the run.
pub type Outcome<T> = Result<T, RunFault>;

/// The grid of `&output` on one example: the grid, `undefined`, or a stop. A
/// grid is undefined where the relation is, and where
/// `docs/arclog/constraints.md#the-output-set` gives.
#[derive(Clone, Debug)]
pub enum GridValue {
    Grid(Grid),
    Undefined,
    Stopped(Stop),
}

/// The values of the case program's parameters: the rows of each parameter
/// as an arcdata file writes them, typed only when a clause reads them, by
/// [`crate::terms::encode_param_value`].
#[derive(Clone, Debug, Default)]
pub struct ParameterValues {
    values: StableHashMap<ProgramRelation, ParamValue>,
}

impl ParameterValues {
    /// The values of the solver's stored `param` records.
    pub fn stored(arcdata: &crate::program::Arcdata) -> Self {
        let values = arcdata.params.iter().map(|param| (param.value().name.clone(), param.value().value.clone())).collect();
        ParameterValues { values }
    }

    /// These values, with the values of each relation that a witness's
    /// `assign` gives in the place of its stored values.
    pub fn with_assigns(&self, assigns: &[(ProgramRelation, ParamValue)]) -> Self {
        let mut values = self.values.clone();
        values.extend(assigns.iter().cloned());
        ParameterValues { values }
    }

    /// The written rows of `relation`, or `None` where no record gives it.
    pub fn get(&self, relation: &ProgramRelation) -> Option<&ParamValue> {
        self.values.get(relation)
    }
}

/// A flag that cancels the evaluations that share it. Clones share one
/// flag.
#[derive(Clone, Debug, Default)]
pub struct Cancellation(Arc<AtomicBool>);

impl Cancellation {
    /// Cancels each evaluation that holds this flag. An evaluation checks the
    /// flag per batch of bindings and stops with
    /// [`ReachedBound::Cancelled`].
    pub fn cancel(&self) {
        self.0.store(true, Ordering::Relaxed);
    }

    /// Whether [`Cancellation::cancel`] has been called on the flag.
    pub fn is_cancelled(&self) -> bool {
        self.0.load(Ordering::Relaxed)
    }
}

/// The bounds of one evaluation besides the session's: its caps, the
/// deadline where it has one, and its cancellation.
#[derive(Clone, Debug)]
pub struct Limits {
    pub caps: Caps,
    pub deadline: Option<std::time::Instant>,
    pub cancellation: Cancellation,
}

/// The evaluation of one checked case program at one set of parameter
/// values on one task, in one task session, at the case's one model. Several evaluations, on
/// several threads, share the session and its result cache.
#[derive(Clone, Copy, Debug)]
pub struct Evaluation<'a> {
    pub program: &'a CheckedProgram,
    pub task: &'a Task,
    pub parameters: &'a ParameterValues,
    pub session: &'a TaskSession,
    pub registry: &'a Registry,
    pub constructions: &'a instance::Constructions,
    pub limits: &'a Limits,
}

impl Evaluation<'_> {
    /// The value of `relation` on `example`, at the case's one model.
    ///
    /// Where an `Unfold` instance that `relation` reads, at any depth, gives
    /// more than one value, the case has more than one model, which this
    /// evaluation does not build, so this gives a [`RunFault`] at that
    /// instance's form, and [`Evaluation::output`] and
    /// [`Evaluation::outputs`] give it through this.
    ///
    /// For a relation with no Example
    /// column, a task-wide relation such as a `DET`'s, `example` is `None`.
    /// A task-wide relation asked on an example, or a relation per example
    /// asked with `None`, is a fault of the caller, so this panics on one.
    pub fn relation(&self, relation: &GraphRelation, example: Option<Example>) -> Outcome<RelationValue> {
        Driver::new(self).value(relation, example)
    }

    /// The grid of `&output` on `example`, read by `columns`, the grid
    /// columns of `&output`.
    pub fn output(&self, example: Example, columns: &output::GridColumns) -> Outcome<GridValue> {
        Driver::new(self).grid(example, *columns)
    }

    /// The grid columns of `&output`
    /// (`docs/arclog/constraints.md#the-output-set`).
    ///
    /// Where several pairs solve every train pair and each two of them give
    /// equal grids on every input of the task, this gives the first of them
    /// by column position. Where two of them give different grids on an
    /// input of the task, the grid columns are undetermined, and this gives a
    /// [`RunFault`] at the form of `&output`, as an undetermined `DET` does.
    /// It gives `None` only where no pair solves every train pair.
    pub fn grid_columns(&self) -> Outcome<Option<output::GridColumns>> {
        Driver::new(self).grid_columns()
    }

    /// The grid of `&output` on each example of the task, train pairs then
    /// test inputs, by the grid columns that [`Evaluation::grid_columns`]
    /// gives; `None` where it gives none.
    pub fn outputs(&self) -> Outcome<Option<Box<[(Example, GridValue)]>>> {
        let driver = Driver::new(self);
        let Some(columns) = driver.grid_columns()? else { return Ok(None) };
        let grids: Outcome<Box<[(Example, GridValue)]>> =
            self.task.examples().map(|example| Ok((example, driver.grid(example, columns)?))).collect();
        grids.map(Some)
    }
}

/// The evaluation of the entries one request reaches, each entry once.
struct Driver<'e, 'a> {
    evaluation: &'e Evaluation<'a>,
    values: RefCell<StableHashMap<(GraphRelation, Option<Example>), RelationValue>>,
}

impl<'e, 'a> Driver<'e, 'a> {
    fn new(evaluation: &'e Evaluation<'a>) -> Self {
        Driver { evaluation, values: RefCell::default() }
    }

    fn program(&self) -> &'a crate::resolver::ResolvedProgram {
        &self.evaluation.program.program
    }

    /// The value of `relation` on `example`, as [`Evaluation::relation`]
    /// gives it.
    fn value(&self, relation: &GraphRelation, example: Option<Example>) -> Outcome<RelationValue> {
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
        let budget = || Budget::new(evaluation.limits, evaluation.session);
        match &program.graph.nodes[relation.node.0 as usize].kind {
            DependencyKind::Clause(_) | DependencyKind::InstanceInput { .. } => self.clauses(relation.node, example),
            DependencyKind::Parameter(name) => self.parameter(relation, name),
            DependencyKind::InstanceOutput { .. } => instance::evaluate_instance(evaluation, form, relation, &mut budget()),
            DependencyKind::RigidAssembly(_) => {
                let output = relation.output.as_ref().and_then(|path| path.first()).expect("an output of the assembly");
                rigid::evaluate_assembly(evaluation, form, output, &mut budget())
            }
            DependencyKind::RecursiveInstance(_) => {
                let values = unfold::evaluate_unfold(evaluation, form, relation, 2, &mut budget())?;
                match <[RelationValue; 1]>::try_from(values) {
                    Ok([value]) => Ok(value),
                    Err(_) => Err(RunFault {
                        message: "the instance gives more than one value, so the case has more than one model".into(),
                        form: form.clone(),
                    }),
                }
            }
            DependencyKind::Chosen(_) | DependencyKind::Demonstrated(_) => Err(RunFault {
                message: "a chosen or demonstrated relation, whose models this evaluation does not build".into(),
                form: form.clone(),
            }),
            DependencyKind::Fact(_) => unreachable!("an atom reads a fact relation from the task"),
        }
    }

    /// The rows of a parameter at its stored values: its rows typed by its
    /// columns, or, for the values of a derivation, the table its
    /// construction derives from them.
    fn parameter(&self, relation: &GraphRelation, name: &ProgramRelation) -> Outcome<RelationValue> {
        let evaluation = self.evaluation;
        let form = self.program().form_of(relation.node);
        let fault = |message: String| RunFault { message: message.into(), form: form.clone() };
        let value = evaluation.parameters.get(name).ok_or_else(|| fault("no stored record gives the parameter's rows".into()))?;
        if let ParamValue::Derivation { .. } = value {
            return instance::evaluate_det_construction(evaluation, form, &mut Budget::new(evaluation.limits, evaluation.session));
        }
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
    fn clause(&self, form: &NodePath, example: Option<Example>) -> Outcome<RelationValue> {
        let evaluation = self.evaluation;
        let clause = ir::compile_clause(evaluation.program, form)
            .map_err(|fault| RunFault { message: format!("the body does not compile: {fault:?}").into(), form: form.clone() })?;
        let scope = if example.is_some() { ExampleScope::PerExample } else { ExampleScope::TaskWide };
        let mut reads = Vec::new();
        let mut parameters = Vec::new();
        let inputs = match self.inputs(&clause, scope, example, &mut reads, &mut parameters)? {
            Ok(inputs) => inputs,
            Err(value) => return Ok(value),
        };
        let content = self.program().content(form).expect("the resolved content of each form");
        let read_refs: Vec<&Relation> = reads.iter().map(|r: &Arc<Relation>| &**r).collect();
        let parameter_refs: Vec<&Relation> = parameters.iter().map(|r: &Arc<Relation>| &**r).collect();
        let request = cache::EntryRequest { clause: &content, reads: &read_refs, example, parameters: &parameter_refs };
        if let Some(value) = cache::lookup(evaluation.session, &request) {
            return Ok(value);
        }
        let order = plan::variable_order(&clause, &join::sizes(&inputs));
        let mut budget = Budget::new(evaluation.limits, evaluation.session);
        let value = match join::join(&clause, &order, &inputs, evaluation.registry, &mut budget) {
            Ok(relation) => RelationValue::Rows(Arc::new(relation)),
            Err(bound) => RelationValue::Stopped(Stop { bound, form: form.clone() }),
        };
        cache::store(evaluation.session, &request, &value);
        Ok(value)
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
                IrNode::If(conditional) => vec![&*conditional.test.body, &*conditional.then, &*conditional.otherwise],
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
        let output = ProgramRelation::Declared(RelationName(DeclaredName::Written("&output".into())));
        relation_of(self.evaluation.program, &output).expect("a checked case program derives `&output`")
    }

    /// The grid of `&output` on `example` by `columns`.
    fn grid(&self, example: Example, columns: output::GridColumns) -> Outcome<GridValue> {
        Ok(match self.value(&self.output_relation(), Some(example))? {
            RelationValue::Rows(relation) => output::read_grid(&relation, columns).map_or(GridValue::Undefined, GridValue::Grid),
            RelationValue::Undefined => GridValue::Undefined,
            RelationValue::Stopped(stop) => GridValue::Stopped(stop),
        })
    }

    /// The grid columns of `&output`, as [`Evaluation::grid_columns`] gives
    /// them.
    fn grid_columns(&self) -> Outcome<Option<output::GridColumns>> {
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
                if !matches!(self.grid(example, columns)?, GridValue::Grid(grid) if grid == pair.output) {
                    solves = false;
                    break;
                }
            }
            if solves {
                solving.push(columns);
            }
        }
        let Some((&first, rest)) = solving.split_first() else { return Ok(None) };
        for &other in rest {
            for example in task.examples() {
                let (a, b) = (self.grid(example, first)?, self.grid(example, other)?);
                if !same_grid(&a, &b) {
                    return Err(RunFault { message: "the grid columns of `&output` are undetermined".into(), form });
                }
            }
        }
        Ok(Some(first))
    }
}

/// The relation that a clause derives or a parameter stores as `name` in
/// `program`, or `None` where no clause or parameter gives it.
pub fn relation_of(program: &CheckedProgram, name: &ProgramRelation) -> Option<GraphRelation> {
    let node = program.program.graph.nodes.iter().position(|node| match &node.kind {
        DependencyKind::Clause(relation) | DependencyKind::Parameter(relation) => relation == name,
        _ => false,
    })?;
    Some(GraphRelation { node: GraphNodeIndex(node as u32), output: None })
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
