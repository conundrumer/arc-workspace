//! The tables of a decode's last step ([`step_tables`]), the input of the feature encoder:
//! where the step added a site or a conjunct to the body of the
//! clause in progress, the table of that body; where the step finished a
//! form, the table of each relation the form declares, except a relation that
//! gets no table: an input
//! written with a body of one positive atom and any number of `NOT` atoms, each
//! of a fact relation, a declared relation or an output, whose rows the tables
//! of those relations hold, the `adjacent`
//! output of a Connectivity instance and the `predecessor` output of a
//! CellDistance instance, which no clause reads. Each table gives its
//! point, its relation's slot, its columns' names and types, and its rows on
//! every example at each assignment of the `DET`s it reads, at each model for
//! a relation with picks. Where a relation holds more rows on an example than
//! the projection cap of the decode settings, the table gives its projections in place of
//! its rows. Each table counts the bindings that all its evaluations try, over the
//! domains of its walk, its examples, assignments and models, and its projections.
//! The first batch that takes the count past the table work cap of the decode
//! settings stops the evaluation it is in with [`ReachedBound::TableWork`](arclog::eval::ReachedBound::TableWork),
//! and each later batch of the table stops at once. The table keeps the entries
//! found before, and records the stop as it records a stop at another bound.
//! No result-cache entry holds that stop. An evaluation that begins within the
//! cap and whose batches take the count past it is held, with its stop, in a store that
//! the tables of one case share ([`Decoder::table_work`]), and a later table of the case that
//! needs that evaluation, at the same result-cache key, records that stop at the
//! form that stopped and tries no binding for it. The recording makes no choice among the points: it keeps each,
//! and a caller that reads no body in progress asks for [`Points::Relations`],
//! so that no body table is evaluated.
//!
//! Each table also gives the sources of each column's values, its depth in
//! the dependency graph, its candidate keys, and, for the relation at which
//! the replay's consistency test found the grid columns, those columns.
//!
//! Beside the tables of a step, [`evidence_tables`] gives the evidence tables
//! of a task, `ex_input` and `ex_output`, which stand before the first step.
//! Each holds one entry for each example whose grid the fact relation holds,
//! so that no entry passes the 900 cells of a grid, and none is cut into
//! projections.

use std::ops::ControlFlow;
use std::sync::Arc;

use arclog::check::CheckedProgram;
use arclog::decode::{derived_at, open_clause, projections, relation_dets, walked_dets, Assigned, Decoder, OpenClause, Projections, State};
use arclog::eval::determinations::relation_spelled;
use arclog::eval::examples::scope_of;
use arclog::eval::join::{each_row, Budget};
use arclog::eval::output::GridColumns;
use arclog::eval::{BodyValue, Evaluation, ModelsEnd, Outcome, RelationValue, RunFault, TableWork};
use arclog::judge::determination::{Assignment, Det, End};
use arclog::program::path::{node_at, NodePath, NodeRef};
use arclog::program::{ColumnName, Conjunct, FactRelation, Negated, OutputOwner, OutputStep, Program, ProgramRelation, RelationRef};
use arclog::registry::Registry;
use arclog::relations::RowSet;
use arclog::resolver::registry_columns::component;
use arclog::resolver::{DependencyKind, GraphNodeIndex};
use arclog::task::Task;
use arclog::terms::{Constant, Example, Term};
use arclog::types::{GraphRelation, ValueType};

use crate::flows::{column_flows, ColumnSource};

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
/// its relation, its columns' types, and the path of each column, where the
/// program's reads name the columns of the relation and the count of their
/// paths is that of the types.
#[derive(Clone, Debug)]
pub struct TableDet {
    pub relation: ProgramRelation,
    pub types: Box<[ValueType]>,
    pub columns: Option<Box<[Box<[ColumnName]>]>>,
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
    /// The relation's name as the program spells it, empty for a body and
    /// for an evidence table, whose [`TableRelation::Fact`] names it.
    pub name: String,
    /// The sources of each column's values ([`column_flows`]),
    /// none for an evidence table.
    pub flows: Box<[Vec<ColumnSource>]>,
    /// The path of each row position of the relation's columns
    /// ([`arclog::resolver::ResolvedProgram::row_paths`]), where the relation
    /// is a program node whose columns have as many positions as `columns`.
    pub rows: Option<Vec<Box<[ColumnName]>>>,
    /// The depth of the relation in the dependency graph ([`arclog::resolver::ResolvedProgram::depth`]).
    pub depth: u32,
    /// The candidate keys the program text gives, each as column positions.
    pub keys: Vec<Vec<u16>>,
    /// The grid columns of the relation, where the replay's consistency test
    /// found them in it.
    pub grid: Option<GridColumns>,
}

/// A table at a point of a form of the program.
#[derive(Clone, Debug)]
pub struct Table {
    pub form: NodePath,
    pub point: Point,
    /// The contents, or the fault of the relation's check or of its types.
    pub contents: Outcome<Contents>,
}

/// The tables of the last step of `decoder`: none before the first, none where
/// the step left the clause in progress as it was, such as a `*` before its
/// echo, and none where no clause is in progress and no form finished; under
/// [`Points::Relations`], none where no form finished, and no body table
/// evaluated.
pub fn step_tables(decoder: &Decoder<'_>, points: Points) -> Vec<Table> {
    let Some(before) = decoder.before() else { return Vec::new() };
    if decoder.program().value().forms.len() > before.program().value().forms.len() {
        relation_tables(decoder, before)
    } else if points == Points::All {
        body_table(decoder, before).into_iter().collect()
    } else {
        Vec::new()
    }
}

/// The conjunct count and the open atom's site count of the clause in
/// progress at `state` of `decoder`, none where no clause is in progress.
fn body_point(decoder: &Decoder<'_>, state: &State) -> Option<Point> {
    let (program, open) = state.partial()?;
    let open = open?;
    let (last, _) = program.value().forms.split_last().expect("a partial program with an open node holds its partial form");
    let OpenClause { clause, kept, open_at } = open_clause(last, &open, decoder.registry())?;
    let sites = match open_at.and_then(|at| clause.body.value().conjuncts.get(at)) {
        Some(Conjunct::Atom(atom)) => atom.value().sites.len(),
        _ => 0,
    };
    Some(Point::Body { conjuncts: u32::try_from(kept.len()).expect("fewer than 2^32 conjuncts"), sites: u32::try_from(sites).expect("fewer than 2^32 sites") })
}

/// The table of the sub-body of the clause in progress, where the step added a
/// site or a conjunct to it; `before` is the state before the step.
fn body_table(decoder: &Decoder<'_>, before: &State) -> Option<Table> {
    let point = body_point(decoder, decoder.state())?;
    if Some(point) == body_point(decoder, before) || point == (Point::Body { conjuncts: 0, sites: 0 }) {
        return None;
    }
    let sub = decoder.sub_body()?;
    let form = NodePath::top(decoder.program().value().forms.len() as u32);
    let contents = sub.map(|sub| {
        let relation = derived_at(&sub.program, &sub.form);
        let slot = decoder.state().open_slot();
        let work = decoder.table_work();
        let examples = decoder.examples_of(sub.scope).into_iter().zip(decoder.values_of(&sub, Some(&work)).into_vec()).map(|(example, rows)| ExampleRows { example, rows: rows.map(|rows| models_of_body(&rows)) }).collect();
        contents(decoder, &sub.program, &sub.form, &relation, slot, &walked_dets(&sub.program, relation.node), examples, &work)
    });
    Some(Table { form, point, contents: contents.and_then(|contents| contents) })
}

/// The table of each relation the form that the step finished declares, but
/// for each that gets no table ([`gives_no_table`]); `before` is the state
/// before the step.
fn relation_tables(decoder: &Decoder<'_>, before: &State) -> Vec<Table> {
    let registry = decoder.registry();
    let program = decoder.program();
    let form = NodePath::top(program.value().forms.len() as u32 - 1);
    let checked = match decoder.finished_checked(before, decoder.state()) {
        Ok(checked) => checked,
        Err(fault) => return vec![Table { form, point: Point::Relation, contents: Err(fault.clone()) }],
    };
    decoder
        .state()
        .declared_from(before.finished_slots())
        .filter(|(_, declared)| !gives_no_table(program.value(), &form, declared))
        .map(|(slot, declared)| {
            let contents = match graph_relation(checked, registry, &form, declared) {
                Some(relation) => {
                    let dets = relation_dets(checked, relation.node);
                    let work = decoder.table_work();
                    let examples = decoder
                        .examples_of(scope_of(checked, &relation))
                        .into_iter()
                        .map(|example| ExampleRows { example, rows: decoder.assigned(checked, relation.node, &dets, Some(&work), &mut |evaluation| models_at(evaluation, &relation, example)) })
                        .collect();
                    let grid = decoder.grid_columns().filter(|_| decoder.output() == Some(declared));
                    contents(decoder, checked, &form, &relation, slot, &dets, examples, &work).map(|contents| Contents { name: relation_spelled(declared), keys: checked.program.column_keys(relation.node), grid, ..contents })
                }
                None => Err(RunFault { message: "the graph holds no node for a relation the form declares".into(), form: form.clone() }),
            };
            Table { form: form.clone(), point: Point::Relation, contents }
        })
        .collect()
}

/// The contents of the table of `relation` in `program`, from its rows on each
/// example: its slot, its columns, its `DET`s, and its projections where a
/// relation holds more rows than the projection cap.
fn contents(decoder: &Decoder<'_>, program: &CheckedProgram, form: &NodePath, relation: &GraphRelation, slot: u32, dets: &[Det], examples: Vec<ExampleRows>, work: &TableWork) -> Outcome<Contents> {
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
            let columns = program.program.row_paths(det.node).filter(|paths| paths.len() == types.len());
            Ok(TableDet { relation: det.relation.clone(), types: types.into(), columns: columns.map(Vec::into_boxed_slice) })
        })
        .collect::<Outcome<Box<[_]>>>()?;
    let cap = decoder.settings().projection_cap;
    let over = examples.iter().any(|example| example.rows.as_ref().is_ok_and(|rows| rows.at.iter().flat_map(|(_, models)| models).any(|model| matches!(model, RelationValue::Rows(rows) if rows.len() > cap))));
    let projections = over.then(|| projections_of(decoder, &examples, form, work)).flatten();
    let flows = column_flows(program, relation.node, relation.output.as_deref(), &types, decoder.registry()).into();
    let depth = program.program.depth(relation.node);
    let rows = program.program.row_paths(relation.node).filter(|rows| relation.output.is_none() && rows.len() == types.len());
    Ok(Contents { relation: TableRelation::Slot(slot), columns, dets, examples: examples.into(), projections, name: String::new(), flows, rows, depth, keys: Vec::new(), grid: None })
}

/// The projections of the rows of `examples`, none where an example gives a
/// fault. Its search counts its bindings in `work`, the count of the table.
fn projections_of(decoder: &Decoder<'_>, examples: &[ExampleRows], form: &NodePath, work: &TableWork) -> Option<Projections> {
    let flat: Vec<Assigned<BodyValue>> = examples.iter().map(|example| example.rows.as_ref().ok().map(flatten)).collect::<Option<_>>()?;
    let limits = decoder.limits().counted_in(work.clone());
    let (_, session, _) = decoder.evaluation_inputs();
    let mut budget = Budget::new(&limits, session);
    let found = projections(&flat, decoder.settings().projection_cap, &mut budget, form);
    budget.record();
    Some(found)
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
        .map(|(example, rows)| ExampleRows { example: Some(example), rows: Ok(Assigned { at: vec![(Vec::new(), vec![RelationValue::Rows(Arc::new(arclog::eval::join::one_part(rows)))])], stop: None }) })
        .collect();
    Table { form: NodePath::default(), point: Point::Evidence, contents: Ok(Contents { relation: TableRelation::Fact(fact), columns, dets: Box::new([]), examples, projections: None, name: String::new(), flows: Box::new([]), rows: None, depth: 0, keys: vec![vec![0, 1]], grid: None }) }
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

/// Whether `declared`, a relation of the form at `form` of `program`, gets no
/// table: an input that the form writes, in its key clause or after it,
/// with a body of one positive atom and any number of `NOT` atoms, each of a
/// fact relation, a declared relation or an output, whose rows are those of
/// the positive atom with its columns renamed, dropped or joined, less the rows
/// that a negated atom matches; the `adjacent` output of a Connectivity instance and the
/// `predecessor` output of a CellDistance instance, which no clause reads.
pub fn gives_no_table(program: &Program, form: &NodePath, declared: &ProgramRelation) -> bool {
    let ProgramRelation::Output(name) = declared else { return false };
    let [OutputStep::Port(port)] = &name.path[..] else { return false };
    let Some(NodeRef::Instance(written)) = node_at(NodeRef::Program(program), form) else { return false };
    if matches!((written.component.0.as_ref(), port.0.as_ref()), ("Connectivity", "adjacent") | ("CellDistance", "predecessor")) {
        return true;
    }
    let keyed = written.key.iter().flat_map(|key| key.value().inputs.iter());
    keyed.chain(written.inputs.iter()).any(|input| {
        let input = input.value();
        input.name == *port && reads_one_positive_atom_and_not_atoms(input.body.value())
    })
}

/// Whether `body` is exactly one positive atom and any number of `NOT` atoms,
/// each of those atoms reading a fact relation, a relation the program
/// declares, or an output. Any other conjunct (a constraint, an `OR`, an `IF`,
/// an `ALL`, a `NOT` before a form) makes it false.
fn reads_one_positive_atom_and_not_atoms(body: &arclog::program::Body) -> bool {
    fn held(atom: &arclog::program::Node<arclog::program::Atom>) -> bool {
        matches!(atom.value().relation, RelationRef::Fact(_) | RelationRef::Declared(_) | RelationRef::Output(_))
    }
    let mut positive = 0;
    body.conjuncts.iter().all(|conjunct| match conjunct {
        Conjunct::Atom(atom) => {
            positive += 1;
            held(atom)
        }
        Conjunct::Not(Negated::Atom(atom)) => held(atom),
        _ => false,
    }) && positive == 1
}

/// A body's value at each assignment as the one model of that assignment.
fn models_of_body(rows: &Assigned<BodyValue>) -> Assigned<Vec<RelationValue>> {
    Assigned { at: rows.at.iter().map(|(assigned, value)| (assigned.clone(), vec![value.0.clone()])).collect(), stop: rows.stop.clone() }
}

/// The value of `relation` on `example` at each model, a stop of the
/// enumeration as a last, stopped model.
fn models_at(evaluation: &Evaluation<'_>, relation: &GraphRelation, example: Option<Example>) -> Result<Vec<RelationValue>, End> {
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
