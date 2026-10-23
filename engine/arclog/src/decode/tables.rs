//! The tables of a decode's last step, the input of the feature encoder:
//! where the step added a site or a conjunct to the body of the
//! clause in progress, the table of that body; where the step finished a
//! form, the table of each relation the form declares. Each table gives its
//! point, its relation's slot, its columns' names and types, and its rows on
//! every example at each assignment of the `DET`s it reads, at each model for
//! a relation with picks. Where a relation holds more rows on an example than
//! the view cap of the decode settings, the table gives its views in place of
//! its rows. The recording makes no choice among the points: it keeps each.

use std::ops::ControlFlow;
use std::sync::Arc;

use super::interface::{derived_at, open_clause, walked_dets, Assigned, OpenClause};
use super::state::State;
use super::views::{views, Views};
use super::Decoder;
use crate::check::CheckedProgram;
use crate::eval::examples::scope_of;
use crate::eval::join::Budget;
use crate::eval::{BodyValue, ModelsEnd, Outcome, RelationValue, RunFault};
use crate::judge::determination::{Assignment, End};
use crate::program::path::NodePath;
use crate::program::{Conjunct, OutputOwner, OutputStep, ProgramRelation};
use crate::resolver::{resolve_last, DependencyKind, GraphNodeIndex};
use crate::terms::Example;
use crate::types::{GraphRelation, ValueType};

/// Where in a form a table stands.
#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub enum Point {
    /// The body of the clause in progress, with its count of conjuncts and
    /// the count of sites of its open atom, none counting as zero.
    Body { conjuncts: u32, sites: u32 },
    /// A relation of a form that the step finished.
    Relation,
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

/// What a table holds once its relation checks and its columns have types.
#[derive(Clone, Debug)]
pub struct Contents {
    /// The slot of the relation.
    pub relation: u32,
    pub columns: Box<[TableColumn]>,
    /// The `DET`s of the assignments, in their order.
    pub dets: Box<[TableDet]>,
    pub examples: Box<[ExampleRows]>,
    /// The views, in place of the rows, where a relation holds more rows on
    /// an example than the view cap. The views' rows follow the order of the
    /// models of `examples`, each example's, one entry for each model at
    /// each assignment.
    pub views: Option<Views>,
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
    /// echo, and none where no clause is in progress and no form finished.
    pub fn tables(&self) -> Vec<Table> {
        let Some(before) = &self.before else { return Vec::new() };
        if self.state.program().value().forms.len() > before.program().value().forms.len() {
            self.relation_tables(before)
        } else {
            self.body_table(before).into_iter().collect()
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
            self.contents(&sub.program, &sub.form, &relation, slot, examples)
        });
        Some(Table { form, point, contents: contents.and_then(|contents| contents) })
    }

    /// The table of each relation the form that the step finished declares.
    fn relation_tables(&self, before: &State) -> Vec<Table> {
        let registry = self.context.registry;
        let program = self.state.program();
        let form = NodePath::top(program.value().forms.len() as u32 - 1);
        let resolved = Arc::new(resolve_last(&before.resolved(registry), program, registry));
        let checked = match self.checked(resolved, &form) {
            Ok(checked) => checked,
            Err(fault) => return vec![Table { form, point: Point::Relation, contents: Err(fault) }],
        };
        self.state
            .declared_from(before.finished_slots())
            .map(|(slot, declared)| {
                let contents = match graph_relation(&checked, &form, declared) {
                    Some(relation) => {
                        let examples = self
                            .examples_of(scope_of(&checked, &relation))
                            .into_iter()
                            .map(|example| ExampleRows { example, rows: self.assigned(&checked, relation.node, &mut |evaluation| models_at(evaluation, &relation, example)) })
                            .collect();
                        self.contents(&checked, &form, &relation, slot, examples)
                    }
                    None => Err(RunFault { message: "the graph holds no node for a relation the form declares".into(), form: form.clone() }),
                };
                Table { form: form.clone(), point: Point::Relation, contents }
            })
            .collect()
    }

    /// The contents of the table of `relation` in `program`, from its rows
    /// on each example: its slot, its columns, its `DET`s, and its views
    /// where a relation holds more rows than the view cap.
    fn contents(&self, program: &CheckedProgram, form: &NodePath, relation: &GraphRelation, slot: u32, examples: Vec<ExampleRows>) -> Outcome<Contents> {
        let fault = |message: &str| RunFault { message: message.into(), form: form.clone() };
        let types = program.types.columns(relation).ok_or_else(|| fault("the columns of the relation have no types"))?;
        let names = match &relation.output {
            None => program.program.column_names(relation.node).filter(|names| names.len() == types.len()),
            Some(_) => None,
        };
        let names = names.unwrap_or_else(|| (0..types.len()).map(|index| format!("c{index}")).collect());
        let columns = names.into_iter().zip(types).map(|(name, ty)| TableColumn { name, ty: ty.clone() }).collect();
        let dets = walked_dets(program, relation.node)
            .into_iter()
            .map(|det| {
                let types = program.types.columns(&GraphRelation { node: det.node, output: None }).ok_or_else(|| fault("the columns of a `DET` have no types"))?;
                Ok(TableDet { relation: det.relation, types: types.into() })
            })
            .collect::<Outcome<Box<[_]>>>()?;
        let cap = self.context.settings.view_cap;
        let over = examples.iter().any(|example| example.rows.as_ref().is_ok_and(|rows| rows.at.iter().flat_map(|(_, models)| models).any(|model| matches!(model, RelationValue::Rows(rows) if rows.len() > cap))));
        let views = over.then(|| self.views_of(&examples, form)).flatten();
        Ok(Contents { relation: slot, columns, dets, examples: examples.into(), views })
    }

    /// The views of the rows of `examples`, none where an example gives a
    /// fault.
    fn views_of(&self, examples: &[ExampleRows], form: &NodePath) -> Option<Views> {
        let flat: Vec<Assigned<BodyValue>> = examples.iter().map(|example| example.rows.as_ref().ok().map(flatten)).collect::<Option<_>>()?;
        let limits = self.limits();
        let mut budget = Budget::new(&limits, self.session);
        let found = views(&flat, self.context.settings.view_cap, &mut budget, form);
        budget.record();
        Some(found)
    }
}

/// The relation of the graph that the form at `form` of `program` declares as
/// `declared`: the node of a clause, a parameter, a chosen relation or an
/// instance port, and the output of a shared node by its path. A chosen
/// relation stands before the clause of its `ONE` marks.
fn graph_relation(program: &CheckedProgram, form: &NodePath, declared: &ProgramRelation) -> Option<GraphRelation> {
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
    let shared = nodes.iter().find(|node| matches!(kind(node), DependencyKind::RecursiveInstance(_) | DependencyKind::RigidAssembly(_)))?;
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
