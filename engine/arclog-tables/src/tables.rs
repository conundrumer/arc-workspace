//! The tables of a decode's last step ([`step_tables`]), the input of the feature encoder:
//! where the step added a site or a conjunct to the body of the
//! clause in progress, the table of that body; where the step finished a
//! form, the table of each relation the form declares, except a relation that
//! gets no table: an input
//! written with a body of one positive atom and any number of `NOT` atoms, each
//! of a fact relation, a declared relation or an output, whose rows the tables
//! of those relations hold. Each table gives its
//! point, its relation's slot, its columns' names, types, slots and labels, and its rows on
//! every example at each assignment of the `DET`s it reads, at each model for
//! a relation with picks. Where a relation holds more rows on an example than
//! the projection cap of the decode settings, the table gives its projections in place of
//! its rows. Each evaluation reads the session's binding and row caps, and no
//! count sums evaluations across assignments or examples. A stopped assignment
//! gives no rows on that example; the walk keeps earlier rows and visits the
//! next assignment. The search for projections reads each value's rows under
//! the binding cap, and extents have an observation budget of their own.
//! The recording keeps every requested point,
//! and a caller that reads no body in progress asks for [`Points::Relations`],
//! so that no body table is evaluated.
//!
//! Each table also gives the sources of each column's values, its depth in
//! the dependency graph, its candidate keys, and, for each relation that an
//! atom of the `OUT` form at which the decode ended reads, the columns that
//! the form selects in it ([`record_step`]). A table that has a column of type
//! `Box` in a made frame also gives the extent of that frame at each of its
//! rows ([`crate::extents::table_extents`]), which [`step_tables`] computes from the tables
//! of the steps before.
//!
//! Beside the tables of a step, [`evidence_tables`] gives the evidence tables
//! of a task, `ex_input` and `ex_output`, which stand before the first step.
//! Each holds one entry for each example whose grid the fact relation holds,
//! so that no entry passes the 900 cells of a grid, and none is cut into
//! projections.

use std::ops::ControlFlow;
use std::sync::Arc;

use arclog::check::CheckedProgram;
use arclog::check::out::selected_sites;
use arclog::decode::{derived_at, projections, relation_dets, walked_dets, Assigned, Decoder, OpenClause, Projections, State};
use arclog::eval::determinations::relation_spelled;
use arclog::eval::examples::scope_of;
use arclog::eval::join::{each_row, Budget};
use arclog::eval::{BodyValue, Evaluation, ModelsEnd, Outcome, RelationValue, RunFault, TableWork};
use arclog::judge::determination::{Assignment, Det, End};
use arclog::program::path::{node_at, NodePath, NodeRef};
use arclog::program::{ClauseKeyword, ColumnName, Conjunct, FactRelation, LabelId, Negated, OutputOwner, OutputStep, Program, ProgramRelation, RelationRef};
use arclog::registry::Registry;
use arclog::relations::RowSet;
use arclog::resolver::registry_columns::component;
use arclog::resolver::{DependencyKind, GraphNodeIndex};
use arclog::task::Task;
use arclog::terms::{Constant, Example, Term};
use arclog::types::{GraphRelation, ValueType};
use arclog::stats::{self, Phase};
use arclog::write::label_names;

use crate::columns::{column_frames, fact_frames, names_of, TableNames};
use crate::extents::{table_extents_with_context, Extents};
#[path = "assignment_context.rs"]
pub mod assignment_context;
use assignment_context::{AssignmentContext, AssignmentLayout, HeldAssignments};
use crate::flows::{column_flows, column_placements, ColumnSource};

/// Canonical wire example axis shared by packing and native receipt maps.
pub(crate) fn example_axis(example: Option<Example>, train: usize) -> (u8, usize) {
    match example {
        None => (0, 0),
        Some(example) => {
            let index = usize::from(example.index());
            if index < train { (1, index) } else { (2, index - train) }
        }
    }
}

/// Where in a form a table stands.
#[derive(Clone, Copy, PartialEq, Eq, Hash, Debug)]
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
/// relation's columns no names, such as the relations of an instance, its
/// type, its slot in the relation's own column order, and the label that the
/// table's form writes at its position, as the label's id in the decoded
/// program and the name ([`arclog::write::label_names`]) that the decoded
/// program gives it. The slot is none where the form's columns reach no such
/// position, and the label is none there and where the form writes no label
/// at the position. The slot and the label of a table of a body in progress
/// are provisional: a later conjunct can give the label another slot or none.
#[derive(Clone, Debug)]
pub struct TableColumn {
    pub name: String,
    pub ty: ValueType,
    pub slot: Option<u32>,
    pub label_id: Option<LabelId>,
    pub label: Option<Box<str>>,
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
    /// Native assignment-order identity; this stores no evaluator or limits.
    pub assignment_layout: AssignmentLayout,
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
    /// The table's Name ([`crate::summary::TableSummary::name`]), as
    /// [`output_name`] gives it: empty for a table of no output and for an
    /// evidence table.
    pub output_name: String,
    /// The sources of each column's values ([`column_flows`]),
    /// none for an evidence table.
    pub flows: Box<[Vec<ColumnSource>]>,
    /// The path of each row position of the relation's columns
    /// ([`arclog::resolver::ResolvedProgram::row_paths`]), where the relation
    /// is a program node whose columns have as many positions as `columns`.
    pub rows: Option<Vec<Box<[ColumnName]>>>,
    /// For each column, every label that the table's form binds to it, the
    /// selected `label_id` of the column among them: a port column that the
    /// heads of several inputs write has a label for each. Empty where the
    /// table is not made from a relation's checked columns.
    pub bound_labels: Box<[Vec<LabelId>]>,
    /// The depth of the relation in the dependency graph ([`arclog::resolver::ResolvedProgram::depth`]).
    pub depth: u32,
    /// The candidate keys the program text gives, each as column positions.
    pub keys: Vec<Vec<u16>>,
    /// The columns of the relation that the `OUT` form at which the decode
    /// ended selects ([`record_step`]).
    pub selected: SelectedColumns,
    /// The frame of each column, empty for none (`column_frames`), computed
    /// once where the table is made, from the tables of the stream before it.
    /// Every reader of the table's frames reads this: the export's
    /// `column_frames` and `extent_columns`, the columns of `extents`, and the
    /// tables after this one that resolve a source's frame through it.
    pub frames: Vec<String>,
    /// The extents of the made frames of the table's `Box` columns
    /// ([`crate::extents::table_extents`]): none for a table that has no such column and an
    /// evidence table.
    pub extents: Option<Extents>,
}

/// The columns of a table's relation that an `OUT` form selects, each by its
/// position among the table's columns.
#[derive(Clone, Copy, PartialEq, Eq, Debug, Default)]
pub struct SelectedColumns {
    pub position: Option<u16>,
    pub color: Option<u16>,
}

/// A table at a point of a form of the program.
#[derive(Clone, Debug)]
pub struct Table {
    pub form: NodePath,
    pub point: Point,
    /// The contents, or the fault of the relation's check or of its types.
    pub contents: Outcome<Contents>,
}

/// Appends to `tables` the tables of the last step of `decoder`
/// ([`step_tables`]) at points `points`, each with the index of the step's
/// token, `index`. Where the step ended the decode at an `OUT` form, it also
/// marks ([`mark_selected`]) the columns that the form selects in the tables
/// of `tables`.
pub fn record_step(tables: &mut Vec<(usize, Table)>, decoder: &Decoder<'_>, index: usize, points: Points) {
    let seen: Vec<&Table> = tables.iter().map(|(_, table)| table).collect();
    let stepped = step_tables(decoder, points, &seen);
    tables.extend(stepped.into_iter().map(|table| (index, table)));
    mark_selected(decoder, tables.iter_mut().map(|(_, table)| table));
}

/// Marks, in the table of each relation an atom of the `OUT` form at which
/// `decoder` ended reads, among `tables`, the columns of that relation the
/// form selects: the Position column in the table of the relation of the atom
/// that selects it, and the Color column in the table of the relation of the
/// atom that selects that.
pub fn mark_selected<'t>(decoder: &Decoder<'_>, tables: impl Iterator<Item = &'t mut Table>) {
    let marks = selected_columns(decoder);
    for table in tables.filter(|table| table.point == Point::Relation) {
        let Ok(contents) = &mut table.contents else { continue };
        for (slot, selected) in &marks {
            if contents.relation == TableRelation::Slot(*slot) {
                contents.selected = SelectedColumns { position: selected.position.or(contents.selected.position), color: selected.color.or(contents.selected.color) };
            }
        }
    }
}

/// The columns that the `OUT` form at which `decoder` ended selects, by the
/// slot of the relation of the atom that selects each; none while the decode
/// has not ended. A column of a relation that no table holds, such as
/// `input`'s, has no slot.
pub fn selected_columns(decoder: &Decoder<'_>) -> Vec<(u32, SelectedColumns)> {
    let (Some(form), Some(before)) = (decoder.output(), decoder.before()) else { return Vec::new() };
    let Ok(checked) = decoder.finished_checked(before, decoder.state()) else { return Vec::new() };
    let Some(NodeRef::Out(out)) = node_at(NodeRef::Program(decoder.program().value()), form) else { return Vec::new() };
    let mut marks: Vec<(u32, SelectedColumns)> = Vec::new();
    for (selected, site) in selected_sites(out).into_iter().enumerate() {
        let relation = match &site.atom.relation {
            RelationRef::Declared(name) => ProgramRelation::Declared(name.clone()),
            RelationRef::Output(name) => ProgramRelation::Output(name.clone()),
            RelationRef::Fact(_) | RelationRef::Lib(_) | RelationRef::DefinedPort(_) => continue,
        };
        let (Some(slot), Some(column)) = (decoder.relation_slot(&relation), checked.program.column_position(&form.join(&site.at))) else { continue };
        let at = match marks.iter().position(|(held, _)| *held == slot) {
            Some(at) => at,
            None => {
                marks.push((slot, SelectedColumns::default()));
                marks.len() - 1
            }
        };
        let mark = &mut marks[at].1;
        match selected {
            0 => mark.position = Some(column.0),
            _ => mark.color = Some(column.0),
        }
    }
    marks
}

/// The tables of the last step of `decoder`: none before the first, none where
/// the step left the clause in progress as it was, such as a `*` before its
/// echo, and none where no clause is in progress and no form finished; under
/// [`Points::Relations`], none where no form finished, and no body table
/// evaluated. `earlier` are the tables of the stream before the step, in
/// order and without the evidence tables, which a table's frames and extents
/// read.
pub fn step_tables(decoder: &Decoder<'_>, points: Points, earlier: &[&Table]) -> Vec<Table> {
    let _timed = stats::span(Phase::TableStep);
    let Some(before) = decoder.before() else { return Vec::new() };
    if decoder.program().value().forms.len() > before.program().value().forms.len() {
        relation_tables(decoder, before, earlier)
    } else if points == Points::All {
        body_table(decoder, before, earlier).into_iter().collect()
    } else {
        Vec::new()
    }
}

/// The conjunct count and the open atom's site count of the clause in
/// progress at `state` of `decoder`, none where no clause is in progress.
pub(crate) fn body_point(decoder: &Decoder<'_>, state: &State) -> Option<Point> {
    let (program, open) = state.partial()?;
    let open = open?;
    // The point counts conjuncts and sites, which the keyword of an `INIT` form's clause leaves as they are.
    let OpenClause { clause, kept, open_at, .. } = decoder.open_clause_in(state, &program, &open, || Some(ClauseKeyword::Rule))?;
    let sites = match open_at.and_then(|at| clause.body.value().conjuncts.get(at)) {
        Some(Conjunct::Atom(atom)) => atom.value().sites.len(),
        _ => 0,
    };
    Some(Point::Body { conjuncts: u32::try_from(kept.len()).expect("fewer than 2^32 conjuncts"), sites: u32::try_from(sites).expect("fewer than 2^32 sites") })
}

/// The table of the sub-body of the clause in progress, where the step added a
/// site or a conjunct to it; `before` is the state before the step.
fn body_table(decoder: &Decoder<'_>, before: &State, earlier: &[&Table]) -> Option<Table> {
    let point = body_point(decoder, decoder.state())?;
    if Some(point) == body_point(decoder, before) || point == (Point::Body { conjuncts: 0, sites: 0 }) {
        return None;
    }
    let names = {
        let _timed = stats::span(Phase::TableNames);
        stats::units(Phase::TableNames, earlier.len());
        names_of(decoder.registry(), earlier)
    };
    body_table_at(decoder, point, earlier, &names)
}

/// The table of the body in progress at the state of `decoder`, as
/// [`step_tables`] gives it at a step that changes the body's point, whatever
/// the last step did; none where no clause is in progress or its body is
/// empty. `earlier` are as [`step_tables`] takes them.
pub fn body_now(decoder: &Decoder<'_>, earlier: &[&Table]) -> Option<Table> {
    let point = body_point(decoder, decoder.state()).filter(|point| *point != Point::Body { conjuncts: 0, sites: 0 })?;
    body_table_at(decoder, point, earlier, &names_of(decoder.registry(), earlier))
}

/// The table of the sub-body of the clause in progress at the state of
/// `decoder`, at `point`, that state's point, as [`body_table`] makes it;
/// `names` are the names of `earlier` ([`names_of`]). None where no clause
/// is in progress.
pub(crate) fn body_table_at(decoder: &Decoder<'_>, point: Point, earlier: &[&Table], names: &TableNames) -> Option<Table> {
    let _timed = stats::span(Phase::TableBody);
    stats::seen(Phase::TableBody, || decoder.state().stats_digest());
    if let Point::Body { conjuncts, .. } = point {
        stats::units(Phase::TableBody, conjuncts as usize);
    }
    let sub = decoder.sub_body()?;
    let form = NodePath::top(decoder.program().value().forms.len() as u32);
    let contents = sub.map(|sub| {
        let relation = derived_at(&sub.program, &sub.form);
        let slot = decoder.state().open_slot();
        let work = decoder.query_work();
        let examples = decoder.examples_of(sub.scope).into_iter().zip(decoder.values_of(&sub, Some(&work)).into_vec()).map(|(example, rows)| ExampleRows { example, rows: rows.map(|rows| models_of_body(&rows)) }).collect();
        contents(decoder, &sub.program, &sub.form, &relation, slot, &walked_dets(&sub.program, relation.node), examples).map(|contents| made_named(decoder, names, earlier, &sub.program, &relation, contents))
    });
    Some(Table { form, point, contents: contents.and_then(|contents| contents) })
}

/// The table of each relation the form that the step finished declares, but
/// for each that gets no table ([`gives_no_table`]); `before` is the state
/// before the step, and `earlier` the tables of the steps before it.
pub(crate) fn relation_tables(decoder: &Decoder<'_>, before: &State, earlier: &[&Table]) -> Vec<Table> {
    let _timed = stats::span(Phase::TableRelation);
    let registry = decoder.registry();
    let program = decoder.program();
    let form = NodePath::top(program.value().forms.len() as u32 - 1);
    if decoder.state().declared_from(before.finished_slots()).next().is_none() {
        return Vec::new();
    }
    let checked = match decoder.finished_checked(before, decoder.state()) {
        Ok(checked) => checked,
        Err(fault) => return vec![Table { form, point: Point::Relation, contents: Err(fault.clone()) }],
    };
    let mut tables: Vec<Table> = Vec::new();
    for (slot, declared) in decoder.state().declared_from(before.finished_slots()).filter(|(_, declared)| !gives_no_table(program.value(), &form, declared)) {
        let contents = match graph_relation(checked, registry, &form, declared) {
            Some(relation) => {
                let dets = relation_dets(checked, relation.node);
                let work = decoder.query_work();
                let examples = relation_examples(decoder, checked, &relation, &dets, &work);
                contents(decoder, checked, &form, &relation, slot, &dets, examples).map(|contents| {
                    let contents = Contents { name: relation_spelled(declared), output_name: output_name(program.value(), &form, declared), keys: checked.program.column_keys(relation.node), ..contents };
                    let seen: Vec<&Table> = earlier.iter().copied().chain(&tables).collect();
                    made(decoder, &seen, checked, &relation, contents)
                })
            }
            None => Err(RunFault { message: "the graph holds no node for a relation the form declares".into(), form: form.clone() }),
        };
        tables.push(Table { form: form.clone(), point: Point::Relation, contents });
    }
    tables
}

/// `contents`, the contents of the table of `relation` in `checked`, with its
/// frames and then its extents, both computed from `seen`, the tables of the
/// stream before the table.
fn made(decoder: &Decoder<'_>, seen: &[&Table], checked: &CheckedProgram, relation: &GraphRelation, contents: Contents) -> Contents {
    made_with_context(decoder, seen, checked, relation, contents, AssignmentContext::Search)
}

/// [`made`], with `names`, the names of `seen` ([`names_of`]).
fn made_named(decoder: &Decoder<'_>, names: &TableNames, seen: &[&Table], checked: &CheckedProgram, relation: &GraphRelation, contents: Contents) -> Contents {
    named_with_context(decoder, names, seen, checked, relation, contents, AssignmentContext::Search)
}

fn made_with_context(decoder: &Decoder<'_>, seen: &[&Table], checked: &CheckedProgram, relation: &GraphRelation, contents: Contents, context: AssignmentContext<'_>) -> Contents {
    let names = {
        let _timed = stats::span(Phase::TableNames);
        stats::units(Phase::TableNames, seen.len());
        names_of(decoder.registry(), seen)
    };
    named_with_context(decoder, &names, seen, checked, relation, contents, context)
}

fn named_with_context(decoder: &Decoder<'_>, names: &TableNames, seen: &[&Table], checked: &CheckedProgram, relation: &GraphRelation, contents: Contents, context: AssignmentContext<'_>) -> Contents {
    let frames = column_frames(names, &contents);
    let contents = Contents { frames, assignment_layout:context.layout(), ..contents };
    let extents = table_extents_with_context(decoder, seen, checked, relation, &contents, context);
    Contents { extents, ..contents }
}

/// The rows of `relation` in `checked` on each example it is evaluated on, at
/// each assignment of `dets` and each model, counted in `work`.
pub(crate) fn relation_examples(decoder: &Decoder<'_>, checked: &CheckedProgram, relation: &GraphRelation, dets: &[Det], work: &TableWork) -> Vec<ExampleRows> {
    relation_examples_with_context(decoder, checked, relation, dets, work, AssignmentContext::Search)
}

pub(crate) fn relation_examples_with_context(decoder: &Decoder<'_>, checked: &CheckedProgram, relation: &GraphRelation, dets: &[Det], work: &TableWork, context: AssignmentContext<'_>) -> Vec<ExampleRows> {
    assignment_context::examples(decoder, checked, scope_of(checked, relation), relation.node, dets, work, context,
        &mut |evaluation, example| models_at(evaluation, relation, example))
}

/// The assignments that one export of a program's tables has stopped at a cap on
/// a query's size. A reader of the export drops such an assignment whole, so a
/// later query at values that hold it takes its stop, and does not run.
#[derive(Default)]
pub(crate) struct TooLarge(std::cell::RefCell<Vec<(Vec<Assignment>, arclog::eval::Stop)>>);

/// [`relation_examples`], with the stops that `too_large` holds, and adding to it.
pub(crate) fn relation_examples_skipping(decoder: &Decoder<'_>, checked: &CheckedProgram, relation: &GraphRelation, dets: &[Det], work: &TableWork, too_large: &TooLarge) -> Vec<ExampleRows> {
    assignment_context::examples(decoder, checked, scope_of(checked, relation), relation.node, dets, work, AssignmentContext::Search, &mut |evaluation, example| {
        if let Some(stop) = too_large.0.borrow().iter().find(|(rows, _)| evaluation.parameters.holds(rows)).map(|(_, stop)| stop.clone()) {
            return Ok(vec![RelationValue::Stopped(stop)]);
        }
        let values = models_at(evaluation, relation, example)?;
        if let Some(stop) = values.iter().find_map(|value| match value { RelationValue::Stopped(stop) if stop.bound.is_size() => Some(stop.clone()), _ => None }) {
            too_large.0.borrow_mut().push((evaluation.parameters.determined_rows(), stop));
        }
        Ok(values)
    })
}

/// The contents of the table of `relation` in `program`, from its rows on each
/// example: its slot, its columns, its `DET`s, and its projections where a
/// relation holds more rows than the projection cap. The frames and extents are
/// those of `made`, which sets them.
fn contents(decoder: &Decoder<'_>, program: &CheckedProgram, form: &NodePath, relation: &GraphRelation, slot: u32, dets: &[Det], examples: Vec<ExampleRows>) -> Outcome<Contents> {
    let mut contents = relation_metadata(decoder.registry(), program, form, relation, slot, dets, examples)?;
    add_projections(decoder, &mut contents, form);
    Ok(contents)
}

/// The columns of the body that `relation` holds, by their types and the labels
/// at them, for a reader of its rows alone: it reads no name of a label, since
/// a body of a part of a form can join a label that another part of the form makes.
pub(crate) fn body_metadata(registry: &Registry, program: &CheckedProgram, form: &NodePath, relation: &GraphRelation, slot: u32, dets: &[Det], examples: Vec<ExampleRows>) -> Outcome<Contents> {
    let fault = |message: &str| RunFault { message: message.into(), form: form.clone() };
    let types = program.types.columns(relation).ok_or_else(|| fault("the columns of the relation have no types"))?;
    let placements = column_placements(program, relation.node, relation.output.as_deref(), form, types.len(), registry);
    let columns = types.iter().zip(placements).enumerate().map(|(at, (ty, placement))| {
        TableColumn { name: format!("c{at}"), ty: ty.clone(), slot: placement.map(|placed| placed.slot), label_id: placement.and_then(|placed| placed.label), label: None }
    }).collect();
    metadata(program, form, TableRelation::Slot(slot), columns, dets, examples, Box::default())
}

/// The checked schema/provenance of a relation, without evaluating projections
/// or extents. Recursive component ports use the same adapter as public tables.
pub(crate) fn relation_metadata(registry: &Registry, program: &CheckedProgram, form: &NodePath, relation: &GraphRelation, slot: u32, dets: &[Det], examples: Vec<ExampleRows>) -> Outcome<Contents> {
    let fault = |message: &str| RunFault { message: message.into(), form: form.clone() };
    let types = program.types.columns(relation).ok_or_else(|| fault("the columns of the relation have no types"))?;
    // An `Unfold` input outside the key clause has rows without the key columns
    // that its port declares. No extent or export of the table can read them.
    for model in examples.iter().filter_map(|example| example.rows.as_ref().ok()).flat_map(|rows| rows.at.iter()).flat_map(|(_, models)| models) {
        if let RelationValue::Rows(rows) = model {
            if usize::from(rows.arity()) != types.len() {
                return Err(fault(&format!("the relation has native arity {}, incompatible with its {} checked columns", rows.arity(), types.len())));
            }
        }
    }
    let names = match &relation.output {
        None => program.program.column_names(relation.node).filter(|names| names.len() == types.len()),
        Some(_) => None,
    };
    let names = names.unwrap_or_else(|| (0..types.len()).map(|index| format!("c{index}")).collect());
    let placements = column_placements(program, relation.node, relation.output.as_deref(), form, types.len(), registry);
    let top = form.0.first().expect("a table's form is a top-level form").0 as usize;
    let named = {
        let _timed = stats::span(Phase::TableLabelNames);
        stats::units(Phase::TableLabelNames, program.program.program.value().forms.len());
        label_names(&program.program.program, registry).swap_remove(top)
    };
    let label_text = |label: LabelId| named.iter().find(|(id, _)| *id == label).map(|(_, name)| name.clone()).expect("every label of the form is named");
    let columns = names
        .into_iter()
        .zip(types)
        .zip(placements)
        .map(|((name, ty), placement)| {
            let label_id = placement.and_then(|placed| placed.label);
            TableColumn { name, ty: ty.clone(), slot: placement.map(|placed| placed.slot), label_id, label: label_id.map(label_text) }
        })
        .collect();
    let flows = column_flows(program, relation.node, relation.output.as_deref(), &types, registry).into();
    let mut contents = metadata(program, form, TableRelation::Slot(slot), columns, dets, examples, flows)?;
    contents.bound_labels = program.program.column_bindings(relation.node, relation.output.as_deref(), form, types.len(), registry)
        .into_iter().map(|column| column.bindings.iter().map(|binding| binding.label).collect()).collect();
    contents.depth = program.program.depth(relation.node);
    contents.rows = program.program.row_paths(relation.node).filter(|rows| relation.output.is_none() && rows.len() == types.len());
    Ok(contents)
}

/// Common native schema and assignment contract, before any annotation queries.
/// Both the relation and IR adapters retain their original column order.
pub(crate) fn metadata(program: &CheckedProgram, form: &NodePath, relation: TableRelation,
    columns: Box<[TableColumn]>, dets: &[Det], examples: Vec<ExampleRows>, flows: Box<[Vec<ColumnSource>]>) -> Outcome<Contents> {
    let fault = |message: &str| RunFault { message: message.into(), form: form.clone() };
    let dets = dets.iter().map(|det| {
        let types = program.types.columns(&GraphRelation { node: det.node, output: None })
            .ok_or_else(|| fault("the columns of a DET have no types"))?;
        let paths = program.program.row_paths(det.node).filter(|paths| paths.len() == types.len());
        Ok(TableDet { relation: det.relation.clone(), types: types.into(), columns: paths.map(Vec::into_boxed_slice) })
    }).collect::<Outcome<Box<[_]>>>()?;
    for example in &examples { if let Ok(assigned) = &example.rows {
        for (values, _) in &assigned.at {
            if values.len() != dets.len() { return Err(fault("assignment DET count differs from its checked schema")); }
            for ((name, rows), det) in values.iter().zip(dets.iter()) {
                if name != &det.relation || usize::from(rows.arity()) != det.types.len() {
                    return Err(fault(&format!("assignment DET {name:?} has native arity {}, incompatible with checked DET {:?} ({} columns)", rows.arity(), det.relation, det.types.len())));
                }
            }
        }
    }}
    Ok(Contents { assignment_layout:AssignmentLayout::Search, relation, columns, dets, examples: examples.into(), projections: None, name: String::new(), output_name: String::new(), flows,
        rows: None, bound_labels: Box::default(), depth: 0, keys: Vec::new(), selected: SelectedColumns::default(), frames: Vec::new(), extents: None })
}

/// Projection policy shared by both schema adapters.
pub(crate) fn add_projections(decoder: &Decoder<'_>, contents: &mut Contents, form: &NodePath) {
    let over = contents.examples.iter().any(|example| example.rows.as_ref().is_ok_and(|rows|
        rows.at.iter().flat_map(|(_, models)| models).any(|model|
            matches!(model, RelationValue::Rows(rows) if rows.len() > decoder.settings().projection_cap))));
    if over { contents.projections = projections_of(decoder, &contents.examples, form); }
}

/// The projections of the rows of `examples`, none where an example gives a
/// fault.
fn projections_of(decoder: &Decoder<'_>, examples: &[ExampleRows], form: &NodePath) -> Option<Projections> {
    let flat: Vec<Assigned<BodyValue>> = examples.iter().map(|example| example.rows.as_ref().ok().map(flatten)).collect::<Option<_>>()?;
    let limits = decoder.limits();
    let (_, session, _) = decoder.evaluation_inputs();
    Some(projections(&flat, decoder.settings().projection_cap, &limits, session, form))
}

/// The evidence tables of `task`, `ex_input` then `ex_output`, each with the
/// columns of the fact relation in `registry`, no `DET`s and no projections, and
/// one entry for each example whose grid the relation holds, in the order of
/// [`Task::examples`]: the rows of that example alone, at the one assignment,
/// as the one model. A grid holds at most 900 cells, so no entry passes a
/// projection cap of 900 or more, and the function applies no cap.
pub fn evidence_tables(task: &Task, registry: &Registry) -> Vec<Table> {
    let _timed = stats::span(Phase::TableEvidence);
    EVIDENCE_FACTS.into_iter().map(|fact| evidence_table(task, registry, fact)).collect()
}

/// The base table of `input` of `task`, with the columns of the fact relation
/// in `registry`, no `DET`s and no projections, and one entry for each example
/// of the task, in the order of [`Task::examples`]: the cells of the example's
/// input grid, at the one assignment, as the one model. Its key is `P`. No
/// step gives it, and [`evidence_tables`] does not hold it.
pub fn input_table(task: &Task, registry: &Registry) -> Table {
    let examples = task
        .examples()
        .map(|example| {
            let rows = task.fact_rows(FactRelation::Input, Some(example));
            ExampleRows { example: Some(example), rows: Ok(Assigned { at: vec![(Vec::new(), vec![RelationValue::Rows(Arc::new(rows))])], stop: None }) }
        })
        .collect();
    let mut table = evidence_table_of(registry, FactRelation::Input, examples);
    if let Ok(contents) = &mut table.contents {
        contents.keys = vec![vec![0]];
    }
    table
}

/// The fact relations of the evidence tables, in their order.
pub(crate) const EVIDENCE_FACTS: [FactRelation; 2] = [FactRelation::ExInput, FactRelation::ExOutput];

/// The evidence tables with no entries, in the order of [`evidence_tables`]:
/// the columns of each, for a reader that takes the frames of those columns.
pub(crate) fn evidence_shells(registry: &Registry) -> Vec<Table> {
    EVIDENCE_FACTS.into_iter().map(|fact| evidence_table_of(registry, fact, Box::new([]))).collect()
}

fn evidence_table(task: &Task, registry: &Registry, fact: FactRelation) -> Table {
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
    evidence_table_of(registry, fact, examples)
}

/// The evidence table of `fact` with the entries `examples`.
fn evidence_table_of(registry: &Registry, fact: FactRelation, examples: Box<[ExampleRows]>) -> Table {
    let columns: Box<[TableColumn]> = registry
        .fact_columns(fact)
        .iter()
        .enumerate()
        .map(|(index, column)| TableColumn {
            name: match &column.name {
                ColumnName::Written(text) => text.to_string(),
                ColumnName::Slot(_) => format!("c{index}"),
            },
            ty: column.ty.fixed().expect("a fact column has a fixed type").clone(),
            slot: Some(u32::try_from(index).expect("fewer than 2^32 columns")),
            label_id: None,
            label: None,
        })
        .collect();
    let frames = fact_frames(fact, &columns);
    Table { form: NodePath::default(), point: Point::Evidence, contents: Ok(Contents { assignment_layout:AssignmentLayout::Search, relation: TableRelation::Fact(fact), columns, dets: Box::new([]), examples, projections: None, name: String::new(), output_name: String::new(), flows: Box::new([]), rows: None, bound_labels: Box::default(), depth: 0, keys: vec![vec![0, 1]], selected: SelectedColumns::default(), frames, extents: None }) }
}

/// The relation of the graph that the form at `form` of `program` declares as
/// `declared`: the node of a clause, a parameter, a chosen relation, a
/// `DEMONSTRATED` relation or an instance port, and the output of a shared
/// node by its path. A chosen
/// relation stands before the clause of its `ONE` marks. A shared node gives
/// only the outputs it has: for an instance, the outputs of its component
/// in `registry`, and for an assembly, the relations of its own name.
pub(crate) fn graph_relation(program: &CheckedProgram, registry: &Registry, form: &NodePath, declared: &ProgramRelation) -> Option<GraphRelation> {
    let nodes = program.program.nodes_of(form);
    let kind = |node: &GraphNodeIndex| &program.program.graph.nodes[node.0 as usize].kind;
    let chosen = nodes.iter().find(|node| matches!(kind(node), DependencyKind::Chosen(name) if ProgramRelation::Declared(name.clone()) == *declared));
    let plain = nodes.iter().find(|node| match (kind(node), declared) {
        (DependencyKind::Clause(relation) | DependencyKind::Parameter(relation), declared) => relation == declared,
        (DependencyKind::Demonstrated(name), ProgramRelation::Declared(declared)) => name == declared,
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
            name.of == OutputOwner::Instance(instance.clone()) && component.zip(port).is_some_and(|(component, port)| component.relation_ports(&component.inputs.iter().map(|i|&i.port.name).collect::<Vec<_>>()).any(|output| output.name == *port))
        }
        _ => false,
    })?;
    Some(GraphRelation { node: *shared, output: Some(Arc::clone(&name.path)) })
}

/// The Name of the table of `declared`, a relation of the form at `form` of
/// `program`: the path after the form's name of an instance's output or
/// input (`component`), the Name that [`arclog::program::rigid_output_name`]
/// gives an output of a `RIGID_DET` form, by the index of its part (`slot 0`,
/// `pose`), and empty for a relation of no output.
pub(crate) fn output_name(program: &Program, form: &NodePath, declared: &ProgramRelation) -> String {
    let ProgramRelation::Output(output) = declared else { return String::new() };
    match (&output.of, node_at(NodeRef::Program(program), form)) {
        (OutputOwner::RigidDet(_), Some(NodeRef::RigidDet(rigid))) => {
            arclog::program::rigid_output_name(rigid, &output.path, |part| part as u32).expect("an output of a `RIGID_DET` form is its pose or a part's")
        }
        _ => arclog::program::output_path_spelled(&output.path),
    }
}

/// Export order shared by study collection and compile-only inventory.
pub(crate) fn materialized_slots<'a>(program:&'a Program,written:&'a arclog::stream::WrittenStream,form:&'a arclog::stream::write::WrittenForm)->impl Iterator<Item=usize>+'a {
    form.readable.iter().copied().filter(move|slot|!gives_no_table(program,&form.path,&written.relations[*slot]))
}

/// Whether `declared`, a relation of the form at `form` of `program`, gets no
/// table: an input that the form writes, in its key clause or after it,
/// with a body of one positive atom and any number of `NOT` atoms, each of a
/// fact relation, a declared relation or an output, whose rows are those of
/// the positive atom with its columns renamed, dropped or joined, less the rows
/// that a negated atom matches.
pub fn gives_no_table(program: &Program, form: &NodePath, declared: &ProgramRelation) -> bool {
    let ProgramRelation::Output(name) = declared else { return false };
    let [OutputStep::Port(port)] = &name.path[..] else { return false };
    let Some(NodeRef::Instance(written)) = node_at(NodeRef::Program(program), form) else { return false };
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

#[path = "study_pair.rs"] pub mod study_pair;
#[path = "study_render.rs"] pub mod study_render;
#[path = "body_tables.rs"] pub(crate) mod body_tables;
#[path = "successors.rs"] pub mod successors;
#[path = "atom_tables.rs"] pub mod atom_tables;

#[cfg(test)]
#[path = "gold_normalization_audit.rs"]
mod gold_normalization_audit;
