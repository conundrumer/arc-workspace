//! The options of a pick: the rows of a chosen relation that a model keeps
//! or not, with its groups and its `never` pairs, as
//! `docs/engine/cases.md#the-constraint-module` gives them over
//! `docs/arclog/constraints.md#one` and `docs/arclog/constraints.md#choose`.
//!
//! A clause with `ONE` marks gives its rows, each grouped by each mark's
//! key. A `DET` with `(ONE)` gives at stored values the rows of its stored
//! `param` record. At determined values it gives assigned rows where an
//! assignment gives them, and otherwise its body's rows or its proposer's
//! open values. A
//! `CHOOSE` gives the `from` rows of each `for` row, grouped by row, and
//! its `never` pairs. The options stand in the canonical order by content
//! of `crate::terms::content_order_by`: the columns compare in the order of
//! the canonical labeling of the form under its resolved names, and the file
//! Idents by the rows that hold them, so a stop at a cap, and the first model,
//! depend on neither an encoding order, nor the written order of the columns,
//! nor the names that label the form, nor the numbers a file writes its Idents
//! with.

use super::ir::{ClauseIr, IrPaths};
use super::{ir, Evaluation, FormBodies, Outcome, ParameterSource, RelationValue, RunFault, Stop};
use crate::check::CheckedProgram;
use crate::hash::StableHashMap;
use crate::program::path::{node_at, NodePath, NodeRef};
use crate::program::{Body, Choose, ClauseKeyword, LabelId, ProgramRelation};
use crate::relations::Row;
use crate::resolver::{DependencyKind, GraphNodeIndex};
use crate::terms::{Example, TermId};
use crate::types::GraphRelation;
use ir::{Argument, AtomSource, IrNode};

/// The options of one pick, as the constraint module takes them.
#[derive(Clone, PartialEq, Eq, Debug)]
pub struct PickOptions {
    /// The row of the chosen relation that each option gives, each once, in
    /// the canonical order by content.
    pub rows: Vec<Row>,
    /// Each group, as the indexes into `rows` of its options, in ascending
    /// order; the groups stand in ascending order, each once.
    pub groups: Vec<Vec<usize>>,
    /// Each `never` pair, as two indexes into `rows`, the smaller first, in
    /// ascending order.
    pub never: Vec<(usize, usize)>,
}

/// The options of a pick, or the value of a read of its bodies that is
/// `undefined` or stopped, as a clause takes that value.
#[derive(Clone, Debug)]
pub enum Pick {
    Options(PickOptions),
    Undefined,
    Stopped(Stop),
}

/// The options of the chosen relation of `node` on `example`, or task-wide
/// where `example` is `None`, with `bodies` evaluating the bodies of its
/// forms, or, for a `DET` that the case program takes from the concept
/// program, the options of that `DET` in the concept program.
pub fn pick_options(bodies: &FormBodies<'_>, node: GraphNodeIndex, example: Option<Example>) -> Outcome<Pick> {
    let driver = bodies.driver;
    let evaluation = driver.evaluation;
    if let Some((concept, node)) = evaluation.in_concept(node) {
        return pick_options(&super::driver::Driver::nested(&concept, driver.trace).bodies(), node, example);
    }
    let program = driver.program();
    let DependencyKind::Chosen(name) = &program.graph.nodes[node.0 as usize].kind else {
        panic!("the node of a chosen relation")
    };
    let relation = GraphRelation { node, output: None };
    let form = program.form_of(node);
    let fault = |message: String| RunFault { message: message.into(), form: form.clone() };
    let types = evaluation.program.types.columns(&relation).ok_or_else(|| fault("the chosen relation's columns have no types".into()))?;
    let root = NodeRef::Program(program.program.value());

    let mut rows: Vec<Row> = Vec::new();
    let mut keys: Vec<Vec<usize>> = Vec::new();
    let mut chooses: Vec<(&NodePath, &Choose, ChooseShape)> = Vec::new();
    let mut significance: Option<Vec<usize>> = None;
    for at in program.forms_of(node) {
        let shape = node_at(root, at).expect("the path of a form of the program");
        let order = column_significance(program, at, shape);
        significance = Some(match significance {
            Some(held) if held <= order => held,
            _ => order,
        });
        match shape {
            NodeRef::Clause(clause) => {
                let stored = evaluation.parameters.get(&ProgramRelation::Declared(name.clone())).is_some();
                let assigned = matches!(evaluation.parameters.source(), ParameterSource::Determined(values) if values.contains_key(&ProgramRelation::Declared(name.clone())));
                if let Some(fault) = super::determinations::conversion_fault(clause, at).filter(|_| !stored) {
                    return Err(fault);
                }
                let value = if clause.keyword == ClauseKeyword::Det && (stored || assigned || !clause.proposers.is_empty()) {
                    driver.parameter(&relation, &ProgramRelation::Declared(name.clone()))?
                } else {
                    driver.clause(at, example)?
                };
                match rows_of(evaluation, at, value, types.len(), &fault)? {
                    Ok(found) => rows.extend(found),
                    Err(pick) => return Ok(pick),
                }
                for mark in clause.ones.iter() {
                    let key = mark.key.iter().map(|label| column_index(driver, at, shape, *label));
                    let key: Option<Vec<usize>> = key.collect();
                    keys.push(key.ok_or_else(|| fault("the key of a `ONE` mark is no column of the chosen relation".into()))?);
                }
            }
            NodeRef::Choose(choose) => match choose_rows(bodies, at, choose, example)? {
                Ok((found, shape)) => {
                    rows.extend(found);
                    keys.push(shape.row_positions.clone());
                    chooses.push((at, choose, shape));
                }
                Err(pick) => return Ok(pick),
            },
            _ => panic!("a clause or a `CHOOSE` form of a chosen relation"),
        }
    }
    {
        let table = evaluation.session.intern.read().expect("an intern table that no panic poisoned");
        // The columns compare in the order of the canonical labeling, whatever order the relation lists them in, and
        // file Idents by the rows that hold them, whatever numbers the file writes them with.
        let mut order = significance.unwrap_or_default();
        let missing: Vec<usize> = (0..types.len()).filter(|column| !order.contains(column)).collect();
        order.extend(missing);
        let plain = crate::terms::IdentRanks::default();
        rows.sort_by(|a, b| crate::terms::content_order_by(types, Some(&order), a, b, &table, &plain));
        rows.dedup();
        let ranks = crate::terms::file_ident_ranks(types, &order, &rows, &table);
        if ranks.is_ranked() {
            rows.sort_by(|a, b| crate::terms::content_order_by(types, Some(&order), a, b, &table, &ranks));
        }
    }

    let mut groups: Vec<Vec<usize>> = keys.iter().flat_map(|key| by_columns(&rows, key).into_values()).collect();
    groups.sort();
    groups.dedup();

    let mut never = Vec::new();
    for (at, choose, shape) in &chooses {
        match never_pairs(bodies, at, choose, shape, &rows, example)? {
            Ok(pairs) => never.extend(pairs),
            Err(pick) => return Ok(pick),
        }
    }
    never.sort();
    never.dedup();
    Ok(Pick::Options(PickOptions { rows, groups, never }))
}

/// The `for` body of the `CHOOSE` form at `form`, with its path, where the
/// form has one.
fn for_body<'c>(choose: &'c Choose, form: &NodePath) -> Option<(&'c Body, NodePath)> {
    choose.rows.as_ref().map(|rows| (rows.body.value(), form.child(0)))
}

/// The labels of the columns of the `for` body of `choose`.
fn row_labels(choose: &Choose) -> Vec<LabelId> {
    choose.rows.iter().flat_map(|rows| rows.columns.iter().map(|column| column.label)).collect()
}

/// The labels of the candidate columns of `choose`.
fn candidate_labels(choose: &Choose) -> Vec<LabelId> {
    choose.candidate_columns.iter().map(|column| column.label).collect()
}

/// The clause of the `for` body of the `CHOOSE` form `choose` at `form`, with
/// the paths of its nodes: the one compile of the body, which the options of
/// the form and the column flows of its relation read. `None` where the form
/// has no `for` body.
pub(crate) fn for_pathed(program: &CheckedProgram, form: &NodePath, choose: &Choose) -> Result<Option<(ClauseIr, IrPaths)>, ir::CompileFault> {
    for_body(choose, form).map(|body| ir::compile_instance_pathed(program, form, &[body], &row_labels(choose))).transpose()
}

/// What the `from` clause of a `CHOOSE` form joins: its parts, the `from`
/// body alone, or the `for` body then the `from` body where the `from` reads
/// inside the `for`, and the labels of the clause's columns.
struct FromBody<'c> {
    parts: Vec<(&'c Body, NodePath)>,
    columns: Vec<LabelId>,
    joined: bool,
}

/// The `from` clause's parts of `choose` at `form`.
fn from_body<'c>(choose: &'c Choose, form: &NodePath) -> FromBody<'c> {
    let from = (choose.from.value(), form.child(u32::from(choose.rows.is_some())));
    match for_body(choose, form) {
        Some(key_body) if choose.from_inside_for => {
            FromBody { parts: vec![key_body, from], columns: [&row_labels(choose)[..], &candidate_labels(choose)].concat(), joined: true }
        }
        _ => FromBody { parts: vec![from], columns: candidate_labels(choose), joined: false },
    }
}

/// The clause of the `from` body of `choose` at `form`, joined with the `for`
/// body where the `from` reads inside the `for`, with the paths of its nodes.
pub(crate) fn from_pathed(program: &CheckedProgram, form: &NodePath, choose: &Choose) -> Result<(ClauseIr, IrPaths), ir::CompileFault> {
    let FromBody { parts, columns, .. } = from_body(choose, form);
    ir::compile_instance_pathed(program, form, &parts, &columns)
}

/// What the groups and the `never` bodies of a `CHOOSE` form read of its
/// other bodies.
struct ChooseShape {
    /// The positions in the chosen relation of the row columns.
    row_positions: Vec<usize>,
    /// The relation of the `from` atom, and, for each of its columns that a
    /// row or candidate label stands at, the position of that label's
    /// column in the chosen relation.
    candidates: Option<(AtomSource, Vec<(crate::relations::ColumnIndex, usize)>)>,
}

/// The options of the `CHOOSE` form `choose` at `form`: each `for` row
/// with each of its candidates, as rows of the chosen relation, with the
/// shape its `never` bodies read; or the value of a read that is
/// `undefined` or stopped.
fn choose_rows(
    bodies: &FormBodies<'_>,
    form: &NodePath,
    choose: &Choose,
    example: Option<Example>,
) -> Outcome<Result<(Vec<Row>, ChooseShape), Pick>> {
    let driver = bodies.driver;
    let checked = driver.evaluation.program;
    let fault = |message: String| RunFault { message: message.into(), form: form.clone() };
    let shape = NodeRef::Choose(choose);
    let (row_labels, candidate_labels) = (row_labels(choose), candidate_labels(choose));
    let position = |label: &LabelId| column_index(driver, form, shape, *label).ok_or_else(|| fault("a column of the form is no column of its relation".into()));
    let row_positions: Vec<usize> = row_labels.iter().map(position).collect::<Outcome<_>>()?;
    let candidate_positions: Vec<usize> = candidate_labels.iter().map(position).collect::<Outcome<_>>()?;
    let arity = row_positions.len() + candidate_positions.len();

    let key_body = for_body(choose, form);
    let (key_rows, key_nodes) = match &key_body {
        Some(_) => {
            let (clause, _) = for_pathed(checked, form, choose)
                .map_err(|compile| fault(format!("the `for` body does not compile: {compile:?}")))?
                .expect("a `for` clause where the form has a `for` body");
            match rows_of(driver.evaluation, form, bodies.relation(form, &clause, example)?, row_labels.len(), &fault)? {
                Ok(rows) => (rows, clause.nodes.len()),
                Err(pick) => return Ok(Err(pick)),
            }
        }
        None => (vec![Row::default()], 0),
    };
    let FromBody { columns, joined, .. } = from_body(choose, form);
    let offset = if joined { key_nodes } else { 0 };
    let (from, _) = from_pathed(checked, form, choose).map_err(|compile| fault(format!("the `from` body does not compile: {compile:?}")))?;
    let from_rows = match rows_of(driver.evaluation, form, bodies.relation(form, &from, example)?, columns.len(), &fault)? {
        Ok(rows) => rows,
        Err(pick) => return Ok(Err(pick)),
    };

    let option = |row: &[TermId], candidate: &[TermId]| -> Row {
        let mut option = vec![TermId::from_encoding(0); arity];
        for (&position, &value) in row_positions.iter().zip(row).chain(candidate_positions.iter().zip(candidate)) {
            option[position] = value;
        }
        option.into()
    };
    let rows: Vec<Row> = if joined {
        from_rows.iter().map(|found| option(&found[..row_labels.len()], &found[row_labels.len()..])).collect()
    } else {
        key_rows.iter().flat_map(|row| from_rows.iter().map(|candidate| option(row, candidate))).collect()
    };

    let role: StableHashMap<ir::Variable, usize> = match joined {
        true => from.columns.iter().copied().zip(row_positions.iter().chain(&candidate_positions).copied()).collect(),
        false => from.columns.iter().copied().zip(candidate_positions.iter().copied()).collect(),
    };
    let candidates = from.nodes[offset..].iter().find_map(|node| match node {
        IrNode::Atom(atom) if matches!(atom.source, AtomSource::Relation(_)) => {
            let sites = atom.arguments.0.iter().filter_map(|(column, argument)| match argument {
                Argument::Variable(variable) => role.get(variable).map(|position| (*column, *position)),
                Argument::Term(_) => None,
            });
            Some((atom.source.clone(), sites.collect()))
        }
        _ => None,
    });
    Ok(Ok((rows, ChooseShape { row_positions, candidates })))
}

/// What one read of a pair in a `never` body gives at a column of the
/// chosen relation: the value of a column of the body's relation, or a
/// term.
#[derive(Clone, Copy)]
enum ReadValue {
    Column(usize),
    Term(TermId),
}

/// The `never` pairs of the `CHOOSE` form `choose` at `form`, of shape
/// `shape`, as indexes into `options`; or the value of a read that is
/// `undefined` or stopped.
fn never_pairs(
    bodies: &FormBodies<'_>,
    form: &NodePath,
    choose: &Choose,
    shape: &ChooseShape,
    options: &[Row],
    example: Option<Example>,
) -> Outcome<Result<Vec<(usize, usize)>, Pick>> {
    let checked = bodies.driver.evaluation.program;
    let fault = |message: String| RunFault { message: message.into(), form: form.clone() };
    let mut pairs = Vec::new();
    // Safety gives every never body the CHOOSE row and candidate labels.
    // Supply their domain as a projected key relation, rather than merging
    // the option body's local witnesses into the never body's scope.
    let mut context: Vec<(&Body, NodePath)> = for_body(choose, form).into_iter().collect();
    context.push((choose.from.value(), form.child(u32::from(choose.rows.is_some()))));
    let given = [row_labels(choose), candidate_labels(choose)].concat();
    let first_never = u32::from(choose.rows.is_some()) + 1;
    for (never, index) in choose.never.iter().zip(first_never..) {
        let Some((source, sites)) = &shape.candidates else {
            return Err(fault("the `from` body reads no candidate relation".into()));
        };
        let body = (never.value(), form.child(index));
        let mut labels: Vec<LabelId> = crate::safety::body_labels(never.value()).into_iter().collect();
        labels.sort_by_key(|label| label.0);
        let whole = ir::compile_ambient_body(checked, form, &context, &given, body.clone(), &labels)
            .map_err(|compile| fault(format!("a `never` body does not compile: {compile:?}")))?;
        let label_of: StableHashMap<ir::Variable, LabelId> = whole.columns.iter().copied().zip(labels.iter().copied()).collect();
        let reads: Vec<&ir::Arguments> = whole
            .nodes
            .iter()
            .filter_map(|node| match node {
                IrNode::Atom(atom) if atom.source == *source => Some(&atom.arguments),
                _ => None,
            })
            .take(2)
            .collect();
        let [first, second] = reads[..] else {
            return Err(fault("a `never` body reads the candidate relation fewer than twice".into()));
        };
        let mut columns: Vec<LabelId> = Vec::new();
        let mut spec = |arguments: &ir::Arguments| -> Vec<(usize, ReadValue)> {
            let mut read = Vec::new();
            for (column, position) in sites {
                let Some((_, argument)) = arguments.0.iter().find(|(at, _)| at == column) else { continue };
                let value = match argument {
                    Argument::Term(term) => ReadValue::Term(*term),
                    Argument::Variable(variable) => {
                        let label = label_of[variable];
                        let at = columns.iter().position(|held| *held == label).unwrap_or_else(|| {
                            columns.push(label);
                            columns.len() - 1
                        });
                        ReadValue::Column(at)
                    }
                };
                read.push((*position, value));
            }
            read
        };
        let reads = [spec(first), spec(second)];
        let clause = ir::compile_ambient_body(checked, form, &context, &given, body, &columns)
            .map_err(|compile| fault(format!("a `never` body does not compile: {compile:?}")))?;
        let found = match rows_of(bodies.driver.evaluation, form, bodies.relation(form, &clause, example)?, columns.len(), &fault)? {
            Ok(rows) => rows,
            Err(pick) => return Ok(Err(pick)),
        };
        let indexes = reads.each_ref().map(|read| by_columns(options, &read.iter().map(|(position, _)| *position).collect::<Vec<_>>()));
        for row in &found {
            let [a, b] = [0, 1].map(|at| {
                let value: Vec<TermId> = reads[at]
                    .iter()
                    .map(|(_, value)| match value {
                        ReadValue::Column(column) => row[*column],
                        ReadValue::Term(term) => *term,
                    })
                    .collect();
                indexes[at].get(&value).map_or(&[][..], |found| &found[..])
            });
            for &x in a {
                pairs.extend(b.iter().filter(|&&y| y != x).map(|&y| (x.min(y), x.max(y))));
            }
        }
    }
    Ok(Ok(pairs))
}

/// The indexes into `options` of the options at each value of the columns
/// at `positions`, in the order of `positions`, each list ascending.
fn by_columns(options: &[Row], positions: &[usize]) -> StableHashMap<Vec<TermId>, Vec<usize>> {
    let mut index: StableHashMap<Vec<TermId>, Vec<usize>> = StableHashMap::default();
    for (at, option) in options.iter().enumerate() {
        index.entry(positions.iter().map(|position| option[*position]).collect()).or_default().push(at);
    }
    index
}

/// The columns of the relation of the form `shape` at `form`, a clause or a
/// `CHOOSE` form, as positions in the rows of the relation, in the order of
/// their labels in the canonical labeling of the form. That labeling writes
/// each relation the form reads by its content and each column by its place
/// ([`crate::resolver::ResolvedProgram::label_rank`]), so the order is the
/// same where a file names the labels and where a decode names them by slots.
/// A column whose label the labeling does not number follows those that it
/// numbers.
fn column_significance(program: &crate::resolver::ResolvedProgram, form: &NodePath, shape: NodeRef<'_>) -> Vec<usize> {
    let mut columns: Vec<(usize, usize)> = crate::resolver::form_columns::form_columns(shape)
        .filter_map(|column| {
            let position = program.label_position(form, column.label)?.0 as usize;
            Some((program.label_rank(form, column.label).map_or(usize::MAX, |rank| rank as usize), position))
        })
        .collect();
    columns.sort_unstable();
    columns.into_iter().map(|(_, position)| position).collect()
}

/// The position in the rows of the chosen relation of the column of
/// `label`, a column of the form `shape` at `form`.
fn column_index(driver: &super::driver::Driver<'_, '_>, form: &NodePath, shape: NodeRef<'_>, label: LabelId) -> Option<usize> {
    ir::relation_columns(driver.program(), form, shape).iter().position(|column| *column == label)
}

/// The rows of `value`, of `arity` columns, or the pick's value where it
/// holds no rows, as [`super::init_form::rows_of`] gives them.
fn rows_of(evaluation: &Evaluation<'_>, form: &NodePath, value: RelationValue, arity: usize, fault: &dyn Fn(String) -> RunFault) -> Outcome<Result<Vec<Row>, Pick>> {
    Ok(match super::init_form::rows_of(evaluation, form, value, arity).map_err(fault)? {
        Ok(rows) => Ok(rows),
        Err(RelationValue::Undefined) => Err(Pick::Undefined),
        Err(RelationValue::Stopped(stop)) => Err(Pick::Stopped(stop)),
        Err(RelationValue::Rows(_)) => unreachable!("a value that holds no rows"),
    })
}
