//! The tables of a decode's last step, the input of the feature encoder:
//! where the step added a site or a conjunct to the body of the
//! clause in progress, the table of that body; where the step finished a
//! form, the table of each relation the form declares. Each table gives its
//! point, its relation's slot, its columns' names and types, and its rows on
//! every example at each assignment of the `DET`s it reads, at each model for
//! a relation with picks. Where a relation holds more rows on an example than
//! the projection cap of the decode settings, the table gives its projections in place of
//! its rows. The recording makes no choice among the points: it keeps each,
//! and a caller that reads no body in progress asks for [`Points::Relations`],
//! so that no body table is evaluated.
//!
//! Beside the tables of a step, [`evidence_tables`] gives the evidence tables
//! of a task, `ex_input` and `ex_output`, which stand before the first step.
//! Each holds one entry for each example whose grid the fact relation holds,
//! so that no entry passes the 900 cells of a grid, and none is cut into
//! projections.

use std::ops::ControlFlow;
use std::sync::Arc;

use super::interface::{derived_at, open_clause, relation_dets, walked_dets, Assigned, OpenClause};
use super::state::State;
use super::projections::{projections, Projections};
use super::Decoder;
use crate::check::CheckedProgram;
use crate::eval::examples::scope_of;
use crate::eval::join::Budget;
use crate::eval::{BodyValue, ModelsEnd, Outcome, RelationValue, RunFault};
use crate::eval::join::each_row;
use crate::judge::determination::{Assignment, Det, End};
use crate::program::path::{node_at, NodePath, NodeRef};
use crate::registry::Registry;
use crate::resolver::registry_columns::component;
use crate::program::{ColumnName, Conjunct, FactRelation, OutputOwner, OutputStep, ProgramRelation};
use crate::resolver::{DependencyKind, GraphNodeIndex};
use crate::relations::RowSet;
use crate::task::Task;
use crate::terms::{Constant, Example, Term};
use crate::types::{GraphRelation, ValueType};

/// Where in a form a table stands.
#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub enum Point {
    /// The body of the clause in progress, with its count of conjuncts and
    /// the count of sites of its open atom, none counting as zero.
    Body { conjuncts: u32, sites: u32 },
    /// A relation of a form that the step finished.
    Relation,
    /// A fact relation of the task, `ex_input` or `ex_output`, which stands
    /// before the first step and in no form.
    Evidence,
}

/// The points whose tables a caller wants.
#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub enum Points {
    /// Each point: the body in progress and the relations of a finished form.
    All,
    /// The relations of a finished form alone.
    Relations,
}

/// A column of a table: its name, `c<position>` where the program gives the
/// relation's columns no names, such as the relations of an instance, and
/// its type.
#[derive(Clone, Debug)]
pub struct TableColumn {
    pub name: String,
    pub ty: ValueType,
}

/// A `DET` that a table's relation reads, whose value an assignment gives:
/// its relation and its columns' types.
#[derive(Clone, Debug)]
pub struct TableDet {
    pub relation: ProgramRelation,
    pub types: Box<[ValueType]>,
}

/// The rows of a table on one example, or once for a task-wide relation:
/// at each assignment, in the order of the walk, the value at each model.
#[derive(Clone, Debug)]
pub struct ExampleRows {
    pub example: Option<Example>,
    pub rows: Outcome<Assigned<Vec<RelationValue>>>,
}

/// The relation of a table: a slot of the program, or a fact relation of the
/// task.
#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub enum TableRelation {
    Slot(u32),
    Fact(FactRelation),
}

/// What a table holds once its relation checks and its columns have types.
#[derive(Clone, Debug)]
pub struct Contents {
    pub relation: TableRelation,
    pub columns: Box<[TableColumn]>,
    /// The `DET`s of the assignments, in their order.
    pub dets: Box<[TableDet]>,
    pub examples: Box<[ExampleRows]>,
    /// The projections, in place of the rows, where a relation holds more rows on
    /// an example than the projection cap. The projections' rows follow the order of the
    /// models of `examples`, each example's, one entry for each model at
    /// each assignment.
    pub projections: Option<Projections>,
}

/// A table at a point of a form of the program.
#[derive(Clone, Debug)]
pub struct Table {
    pub form: NodePath,
    pub point: Point,
    /// The contents, or the fault of the relation's check or of its types.
    pub contents: Outcome<Contents>,
}

impl Decoder<'_> {
    /// The tables of the last step: none before the first, none where the
    /// step left the clause in progress as it was, such as a `*` before its
    /// echo, and none where no clause is in progress and no form finished;
    /// under [`Points::Relations`], none where no form finished, and no body
    /// table evaluated.
    pub fn tables(&self, points: Points) -> Vec<Table> {
        let Some(before) = &self.before else { return Vec::new() };
        if self.state.program().value().forms.len() > before.program().value().forms.len() {
            self.relation_tables(before)
        } else if points == Points::All {
            self.body_table(before).into_iter().collect()
        } else {
            Vec::new()
        }
    }

    /// The conjunct count and the open atom's site count of the clause in
    /// progress at `state`, none where no clause is in progress.
    fn body_point(&self, state: &State) -> Option<Point> {
        let (program, open) = state.partial()?;
        let open = open?;
        let (last, _) = program.value().forms.split_last().expect("a partial program with an open node holds its partial form");
        let OpenClause { clause, kept, open_at } = open_clause(last, &open, self.context.registry)?;
        let sites = match open_at.and_then(|at| clause.body.value().conjuncts.get(at)) {
            Some(Conjunct::Atom(atom)) => atom.value().sites.len(),
            _ => 0,
        };
        Some(Point::Body { conjuncts: u32::try_from(kept.len()).expect("fewer than 2^32 conjuncts"), sites: u32::try_from(sites).expect("fewer than 2^32 sites") })
    }

    /// The table of the sub-body of the clause in progress, where the step
    /// added a site or a conjunct to it.
    fn body_table(&self, before: &State) -> Option<Table> {
        let point = self.body_point(&self.state)?;
        if Some(point) == self.body_point(before) || point == (Point::Body { conjuncts: 0, sites: 0 }) {
            return None;
        }
        let sub = self.sub_body()?;
        let form = NodePath::top(self.state.program().value().forms.len() as u32);
        let contents = sub.map(|sub| {
            let relation = derived_at(&sub.program, &sub.form);
            let slot = self.state.open_slot();
            let examples = self.examples_of(sub.scope).into_iter().zip(self.values_of(&sub).into_vec()).map(|(example, rows)| ExampleRows { example, rows: rows.map(|rows| models_of_body(&rows)) }).collect();
            self.contents(&sub.program, &sub.form, &relation, slot, &walked_dets(&sub.program, relation.node), examples)
        });
        Some(Table { form, point, contents: contents.and_then(|contents| contents) })
    }

    /// The table of each relation the form that the step finished declares.
    fn relation_tables(&self, before: &State) -> Vec<Table> {
        let registry = self.context.registry;
        let program = self.state.program();
        let form = NodePath::top(program.value().forms.len() as u32 - 1);
        let checked = match self.finished_checked(before, &self.state) {
            Ok(checked) => checked,
            Err(fault) => return vec![Table { form, point: Point::Relation, contents: Err(fault.clone()) }],
        };
        self.state
            .declared_from(before.finished_slots())
            .map(|(slot, declared)| {
                let contents = match graph_relation(checked, registry, &form, declared) {
                    Some(relation) => {
                        let dets = relation_dets(checked, relation.node);
                        let examples = self
                            .examples_of(scope_of(checked, &relation))
                            .into_iter()
                            .map(|example| ExampleRows { example, rows: self.assigned(checked, relation.node, &dets, &mut |evaluation| models_at(evaluation, &relation, example)) })
                            .collect();
                        self.contents(checked, &form, &relation, slot, &dets, examples)
                    }
                    None => Err(RunFault { message: "the graph holds no node for a relation the form declares".into(), form: form.clone() }),
                };
                Table { form: form.clone(), point: Point::Relation, contents }
            })
            .collect()
    }

    /// The contents of the table of `relation` in `program`, from its rows
    /// on each example: its slot, its columns, its `DET`s, and its projections
    /// where a relation holds more rows than the projection cap.
    fn contents(&self, program: &CheckedProgram, form: &NodePath, relation: &GraphRelation, slot: u32, dets: &[Det], examples: Vec<ExampleRows>) -> Outcome<Contents> {
        let fault = |message: &str| RunFault { message: message.into(), form: form.clone() };
        let types = program.types.columns(relation).ok_or_else(|| fault("the columns of the relation have no types"))?;
        let names = match &relation.output {
            None => program.program.column_names(relation.node).filter(|names| names.len() == types.len()),
            Some(_) => None,
        };
        let names = names.unwrap_or_else(|| (0..types.len()).map(|index| format!("c{index}")).collect());
        let columns = names.into_iter().zip(types).map(|(name, ty)| TableColumn { name, ty: ty.clone() }).collect();
        let dets = dets
            .iter()
            .map(|det| {
                let types = program.types.columns(&GraphRelation { node: det.node, output: None }).ok_or_else(|| fault("the columns of a `DET` have no types"))?;
                Ok(TableDet { relation: det.relation.clone(), types: types.into() })
            })
            .collect::<Outcome<Box<[_]>>>()?;
        let cap = self.context.settings.projection_cap;
        let over = examples.iter().any(|example| example.rows.as_ref().is_ok_and(|rows| rows.at.iter().flat_map(|(_, models)| models).any(|model| matches!(model, RelationValue::Rows(rows) if rows.len() > cap))));
        let projections = over.then(|| self.projections_of(&examples, form)).flatten();
        Ok(Contents { relation: TableRelation::Slot(slot), columns, dets, examples: examples.into(), projections })
    }

    /// The projections of the rows of `examples`, none where an example gives a
    /// fault.
    fn projections_of(&self, examples: &[ExampleRows], form: &NodePath) -> Option<Projections> {
        let flat: Vec<Assigned<BodyValue>> = examples.iter().map(|example| example.rows.as_ref().ok().map(flatten)).collect::<Option<_>>()?;
        let limits = self.limits();
        let mut budget = Budget::new(&limits, self.session);
        let found = projections(&flat, self.context.settings.projection_cap, &mut budget, form);
        budget.record();
        Some(found)
    }
}

/// The evidence tables of `task`, `ex_input` then `ex_output`, each with the
/// columns of the fact relation in `registry`, no `DET`s and no projections, and
/// one entry for each example whose grid the relation holds, in the order of
/// [`Task::examples`]: the rows of that example alone, at the one assignment,
/// as the one model. A grid holds at most 900 cells, so no entry passes a
/// projection cap of 900 or more, and the function applies no cap.
pub fn evidence_tables(task: &Task, registry: &Registry) -> Vec<Table> {
    [FactRelation::ExInput, FactRelation::ExOutput].into_iter().map(|fact| evidence_table(task, registry, fact)).collect()
}

fn evidence_table(task: &Task, registry: &Registry, fact: FactRelation) -> Table {
    let columns = registry
        .fact_columns(fact)
        .iter()
        .enumerate()
        .map(|(index, column)| TableColumn {
            name: match &column.name {
                ColumnName::Written(text) => text.to_string(),
                ColumnName::Slot(_) => format!("c{index}"),
            },
            ty: column.ty.fixed().expect("a fact column has a fixed type").clone(),
        })
        .collect();
    let counts = match fact {
        FactRelation::ExOutput => task.train.len(),
        _ => task.train.len() + task.test.len(),
    };
    let mut held: Vec<RowSet> = (0..counts).map(|_| RowSet::empty(3)).collect();
    each_row(&task.fact_rows(fact, None), &mut |row| {
        let Term::Constant(Constant::Example(example)) = Term::decode(row[0], &ValueType::Example) else { unreachable!("the first column of an evidence row is an Example") };
        held[usize::from(example.index())].insert(row.into());
    });
    let examples = task
        .examples()
        .zip(held)
        .map(|(example, rows)| ExampleRows { example: Some(example), rows: Ok(Assigned { at: vec![(Vec::new(), vec![RelationValue::Rows(Arc::new(crate::eval::join::one_part(rows)))])], stop: None }) })
        .collect();
    Table { form: NodePath::default(), point: Point::Evidence, contents: Ok(Contents { relation: TableRelation::Fact(fact), columns, dets: Box::new([]), examples, projections: None }) }
}

/// The relation of the graph that the form at `form` of `program` declares as
/// `declared`: the node of a clause, a parameter, a chosen relation or an
/// instance port, and the output of a shared node by its path. A chosen
/// relation stands before the clause of its `ONE` marks. A shared node gives
/// only the outputs it has: for an instance, the outputs of its component
/// in `registry`, and for an assembly, the relations of its own name.
fn graph_relation(program: &CheckedProgram, registry: &Registry, form: &NodePath, declared: &ProgramRelation) -> Option<GraphRelation> {
    let nodes = program.program.nodes_of(form);
    let kind = |node: &GraphNodeIndex| &program.program.graph.nodes[node.0 as usize].kind;
    let chosen = nodes.iter().find(|node| matches!(kind(node), DependencyKind::Chosen(name) if ProgramRelation::Declared(name.clone()) == *declared));
    let plain = nodes.iter().find(|node| match (kind(node), declared) {
        (DependencyKind::Clause(relation) | DependencyKind::Parameter(relation), declared) => relation == declared,
        (DependencyKind::InstanceInput { instance, input: port } | DependencyKind::InstanceOutput { instance, output: port }, ProgramRelation::Output(name)) => {
            name.of == OutputOwner::Instance(instance.clone()) && *name.path == [OutputStep::Port(port.clone())]
        }
        _ => false,
    });
    if let Some(&node) = chosen.or(plain) {
        return Some(GraphRelation { node, output: None });
    }
    let ProgramRelation::Output(name) = declared else { return None };
    let shared = nodes.iter().find(|node| match kind(node) {
        DependencyKind::RigidAssembly(rigid) => name.of == OutputOwner::RigidDet(rigid.clone()),
        DependencyKind::RecursiveInstance(instance) => {
            let root = NodeRef::Program(program.program.program.value());
            let component = match node_at(root, form) {
                Some(NodeRef::Instance(written)) => component(registry, &written.component),
                _ => None,
            };
            let port = match &name.path[..] {
                [OutputStep::Port(port)] => Some(port),
                _ => None,
            };
            name.of == OutputOwner::Instance(instance.clone()) && component.zip(port).is_some_and(|(component, port)| component.outputs.iter().any(|output| output.name == *port))
        }
        _ => false,
    })?;
    Some(GraphRelation { node: *shared, output: Some(Arc::clone(&name.path)) })
}

/// A body's value at each assignment as the one model of that assignment.
fn models_of_body(rows: &Assigned<BodyValue>) -> Assigned<Vec<RelationValue>> {
    Assigned { at: rows.at.iter().map(|(assigned, value)| (assigned.clone(), vec![value.0.clone()])).collect(), stop: rows.stop.clone() }
}

/// The value of `relation` on `example` at each model, a stop of the
/// enumeration as a last, stopped model.
fn models_at(evaluation: &crate::eval::Evaluation<'_>, relation: &GraphRelation, example: Option<Example>) -> Result<Vec<RelationValue>, End> {
    let mut values = Vec::new();
    let end = evaluation
        .models(relation, example, &mut |value| {
            values.push(value.clone());
            ControlFlow::Continue(())
        })
        .map_err(End::Fault)?;
    if let ModelsEnd::Stopped(stop) = end {
        values.push(RelationValue::Stopped(stop));
    }
    Ok(values)
}

/// `rows` with one entry for each model at each assignment, in the order of
/// the models.
fn flatten(rows: &Assigned<Vec<RelationValue>>) -> Assigned<BodyValue> {
    let at = rows.at.iter().flat_map(|(assigned, models): &(Vec<Assignment>, _)| models.iter().map(move |model| (assigned.clone(), BodyValue(model.clone())))).collect();
    Assigned { at, stop: rows.stop.clone() }
}
