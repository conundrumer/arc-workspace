//! The tables after each of several tokens at one state of a decode
//! ([`successor_tables`]): for each token, the tables that [`step_tables`]
//! gives at the decode that the token advances, and, for a token that leaves
//! the point of the body in progress as it was, the table of that body.
//!
//! A successor body is the body in progress with one more site or one more
//! conjunct. Its evaluation is the evaluator's own ([`Decoder::values_of`]):
//! a part of the body that the result cache does not hold is the join of its
//! last conjunct with the rows of the other parts, where the cache holds
//! them (`Driver::linked`). Before the tokens, the call evaluates the body in
//! progress and the body of its complete conjuncts, so that the cache holds
//! the parts that each successor body joins one conjunct to. Tokens whose
//! successor bodies are equal ([`Decoder::sub_body_key`]) share one
//! evaluation, and a successor body equal to the body in progress takes its
//! table. A successor whose tables equal those of an earlier one
//! ([`same_tables`]), or whose body and point are those of an earlier one,
//! names that one ([`Successor::same_as`]), so that a caller exports the
//! tables once.

use arclog::hash::StableHashMap;

use super::*;
use arclog::decode::{LeftOut, Refusal};
use arclog::relations::Relation;
use arclog::eval::{Gauge, Gauges, Limits};
use arclog::stream::Token;

/// What a token does to the body in progress, and so which tables are its.
#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub enum SuccessorKind {
    /// The token changes the body in progress: the tables hold the table of
    /// the successor body. Where the token leaves the point as it was, as a
    /// label or a constant that fills a site already open, [`step_tables`]
    /// gives no table, and this table is the one it would give at a point
    /// that differs.
    Body,
    /// The token changes the point of the body, and the successor body leaves
    /// out the conjunct in progress, as [`LeftOut`] gives: the tables hold
    /// the table at the new point, whose rows are those of the body without
    /// that conjunct.
    LeftOut(LeftOut),
    /// The token leaves the body in progress and its point as they were, as
    /// a token that opens a conjunct that the body leaves out at the same
    /// point: the tables hold the table of the
    /// body in progress, which [`step_tables`] does not give again.
    Unchanged,
    /// The token finishes the form in progress: the tables of the relations
    /// the form declares, as [`step_tables`] gives them, none for a form that
    /// declares none.
    Finished,
    /// After the token no clause is in progress, or its body is empty, and no
    /// form finished: no table.
    NoBody,
    /// The evaluation of the successor passed the work cap or the byte budget
    /// that each successor has of its own, or its export left out a table at
    /// a bound of its own evaluation: the successor has no tables, and the
    /// other successors went on ([`Successor::exhausted`]).
    Exhausted,
}

/// The decode after one token, and the tables after it.
pub struct Successor<'a> {
    pub decoder: Decoder<'a>,
    pub kind: SuccessorKind,
    pub tables: Vec<Table>,
    /// The place, among the successors of the call, of the first successor
    /// whose tables equal these ([`same_tables`]) or whose body and point are
    /// these, where that is an earlier one. Only a successor of the kind
    /// [`SuccessorKind::Body`], [`SuccessorKind::LeftOut`] or
    /// [`SuccessorKind::NoBody`], or of the
    /// kind [`SuccessorKind::Finished`] with no table, names one, and only
    /// such a successor is named.
    pub same_as: Option<usize>,
    /// The budget that the evaluation of this successor passed, where it
    /// passed one: the request work cap or the request byte budget of the
    /// successor's own request, which counts the successor's step, its
    /// consistency test included. Then `kind` is [`SuccessorKind::Exhausted`]
    /// and `tables` is empty.
    pub exhausted: Option<arclog::eval::ReachedBound>,
}

/// What [`successor_tables`] gives.
pub struct Successors<'a> {
    /// The table of the body in progress, none where no clause is in
    /// progress or its body is empty.
    pub current: Option<Table>,
    /// For each token, its successor, or the refusal that [`Decoder::step`]
    /// gives for it. Empty where `guard` is set.
    pub each: Vec<Result<Successor<'a>, Refusal>>,
    /// The work cap or the byte budget of the call's own request that the
    /// evaluations before the tokens passed, where they passed one. The call's
    /// request is a bound over the whole call: its stop is a fault of the call
    /// and cuts no successor's tables, so no successor is evaluated.
    pub guard: Option<arclog::eval::ReachedBound>,
}

/// The point of a body with no conjunct and no site, which has no table.
const EMPTY: Point = Point::Body { conjuncts: 0, sites: 0 };

/// The successor of each of `tokens` at the state of `decoder`, and the
/// table of the body in progress. Each successor's decode is
/// [`Decoder::successor`]'s. The step of each successor, its consistency test
/// included, and the evaluation of its tables run under a request of its own,
/// with the work cap and the byte budget of `limits`
/// ([`Limits::for_candidate`]), so that a successor that passes one gets no
/// tables ([`SuccessorKind::Exhausted`]) and the other successors go on, and
/// no successor counts in the work of another. The evaluations before the
/// tokens run in `limits`, the request of the call; where they pass its work
/// cap or its byte budget, the call gives `guard` and no successor, since that
/// bound is over the whole call and cuts no successor's tables. Its tables are those that [`step_tables`] gives at that decode
/// with [`Points::All`], but for a token that leaves the point of the body as
/// it was, where they are the table of the successor body
/// ([`SuccessorKind::Body`]), or of the body in progress where the body is as
/// it was ([`SuccessorKind::Unchanged`]). `earlier` are the tables
/// of the stream up to the state of `decoder`, without the evidence tables,
/// and `held` is the table of the body in progress where the caller holds
/// it, as [`step_tables`] gave it at the decode's last step; a table at
/// another point or form is not taken.
pub fn successor_tables<'a>(decoder: &Decoder<'a>, limits: &Limits, tokens: Vec<Token>, earlier: &[&Table], held: Option<Table>) -> Successors<'a> {
    let operation = decoder.clone().with_operation_limits(limits.clone());
    let names = {
        let _timed = stats::span(Phase::TableNames);
        stats::units(Phase::TableNames, earlier.len());
        names_of(decoder.registry(), earlier)
    };
    let form = NodePath::top(decoder.program().value().forms.len() as u32);
    let point = body_point(decoder, decoder.state());
    let body = point.filter(|point| *point != EMPTY);
    // The parts of the complete conjuncts first, which the body in progress and each successor body join one conjunct to.
    if body.is_some() {
        if let Some(Ok(complete)) = operation.complete_sub_body() {
            let work = operation.query_work();
            drop(operation.values_of(&complete, Some(&work)));
        }
    }
    let current = body.and_then(|point| match held.filter(|table| table.point == point && table.form == form) {
        Some(table) => Some(table),
        None => body_table_at(&operation, point, earlier, &names),
    });
    // A successor whose body is the body in progress takes its table, so the table must not be one that the call's own bound cut.
    if let Some(guard) = exhaustion(limits) {
        return Successors { current, each: Vec::new(), guard: Some(guard) };
    }
    // The contents of each successor body evaluated so far, by its key; the body in progress first.
    let mut evaluated: StableHashMap<Vec<u8>, Outcome<Contents>> = StableHashMap::default();
    let own = decoder.sub_body_key().map(|key| key.source);
    if let (Some(table), Some(source)) = (&current, &own) {
        evaluated.insert(source.clone(), table.contents.clone());
    }
    let mut each: Vec<Result<Successor<'a>, Refusal>> = Vec::with_capacity(tokens.len());
    // The places in `each` of the successors that name no earlier one, and that a later one can name.
    let mut firsts: Vec<usize> = Vec::new();
    // For each successor body and point, the place in `each` of the successor that a later one of that body and point names. Both hold the contents of one evaluation, which `same_tables` takes as different where they hold extents.
    let mut held_at: StableHashMap<(Vec<u8>, Point), usize> = StableHashMap::default();
    for token in tokens {
        // The successor's step, its consistency test included, and its tables count in a request of the successor's own.
        let candidate = limits.for_candidate();
        let next = match decoder.clone().with_operation_limits(candidate.clone()).successor(token) {
            Ok(next) => next,
            Err(refusal) => {
                each.push(Err(refusal));
                continue;
            }
        };
        let before = next.before().expect("a successor has a step");
        let mut body_key = None;
        let (kind, tables) = if next.program().value().forms.len() > before.program().value().forms.len() {
            let mut tables = relation_tables(&next, before, earlier);
            mark_selected(&next, tables.iter_mut());
            (SuccessorKind::Finished, tables)
        } else {
            let key = next.sub_body_key();
            match body_point(&next, next.state()).filter(|point| *point != EMPTY) {
                None => (SuccessorKind::NoBody, Vec::new()),
                Some(after) if Some(after) == point && key.as_ref().map(|key| &key.source) == own.as_ref() => match &current {
                    Some(table) => (SuccessorKind::Unchanged, vec![table.clone()]),
                    None => (SuccessorKind::NoBody, Vec::new()),
                },
                Some(after) => {
                    let kind = key.as_ref().and_then(|key| key.left_out).map_or(SuccessorKind::Body, SuccessorKind::LeftOut);
                    body_key = key.as_ref().map(|key| (key.source.clone(), after));
                    let found = key.as_ref().and_then(|key| evaluated.get(&key.source));
                    let table = match found {
                        Some(contents) => Some(Table { form: form.clone(), point: after, contents: contents.clone() }),
                        None => {
                            let table = body_table_at(&next, after, earlier, &names);
                            // The contents of an evaluation that passed a budget are the successor's alone.
                            if let (Some(key), Some(table)) = (key, &table)
                                && exhaustion(&candidate).is_none()
                            {
                                evaluated.insert(key.source, table.contents.clone());
                            }
                            table
                        }
                    };
                    (kind, table.into_iter().collect())
                }
            }
        };
        // A successor whose evaluation passed a budget has no tables.
        let exhausted = exhaustion(&candidate);
        let (kind, tables) = if exhausted.is_some() { (SuccessorKind::Exhausted, Vec::new()) } else { (kind, tables) };
        // A caller exports a relation table with the QueryHash that the successor's own decode gives, and the table of an unchanged body with no step of its own, so neither takes part.
        let named = kind != SuccessorKind::Unchanged && kind != SuccessorKind::Exhausted && tables.iter().all(|table| matches!(table.point, Point::Body { .. }));
        let same_as = if named {
            let found = body_key.as_ref().and_then(|key| held_at.get(key).copied()).or_else(|| firsts.iter().copied().find(|&first| each[first].as_ref().is_ok_and(|first| same_tables(&first.tables, &tables, Compared { gauges: limits.request.gauges(), cap: decoder.settings().compared_rows_cap }))));
            if found.is_none() {
                firsts.push(each.len());
            }
            if let Some(key) = body_key {
                held_at.entry(key).or_insert(found.unwrap_or(each.len()));
            }
            found
        } else {
            None
        };
        each.push(Ok(Successor { decoder: next, kind, tables, same_as, exhausted }));
    }
    Successors { current, each, guard: None }
}

/// The budget that `limits` passed: the request work cap, or the request byte
/// budget, or `None` where it passed neither.
pub fn exhaustion(limits: &Limits) -> Option<arclog::eval::ReachedBound> {
    let request = &limits.request;
    if request.count() > request.cap() {
        Some(arclog::eval::ReachedBound::RequestWork { cap: request.cap() })
    } else if request.is_past_byte_budget() {
        Some(arclog::eval::ReachedBound::RequestBytes { cap: request.byte_cap() })
    } else {
        None
    }
}

/// What the comparison of two successors' tables reads: the gauges to note
/// the rows compared in, and the most rows of a relation that [`same_relation`]
/// compares row by row (the setting `compared_rows_cap`); it takes two larger
/// relations that are no clones of one another as different.
#[derive(Clone, Copy)]
pub struct Compared<'g> {
    pub gauges: &'g Gauges,
    pub cap: u64,
}

/// Whether the tables `a` and `b` are equal, one by one, in each field that
/// an export reads: then they export the same columns after the same
/// stream. A table with projections or with extents is taken as different
/// from every other table.
pub fn same_tables(a: &[Table], b: &[Table], gauges: Compared<'_>) -> bool {
    a.len() == b.len() && a.iter().zip(b).all(|(a, b)| same_table(a, b, gauges))
}

fn same_table(a: &Table, b: &Table, gauges: Compared<'_>) -> bool {
    let Table { form, point, contents } = a;
    *form == b.form
        && *point == b.point
        && match (contents, &b.contents) {
            (Ok(a), Ok(b)) => same_contents(a, b, gauges),
            (Err(a), Err(b)) => a == b,
            _ => false,
        }
}

fn same_contents(a: &Contents, b: &Contents, gauges: Compared<'_>) -> bool {
    // Each field is named, so that a field added to `Contents` is compared here too.
    let Contents { assignment_layout, relation, columns, dets, examples, projections, name, output_name, flows, rows, bound_labels, depth, keys, selected, frames, extents } = a;
    let layout = match (assignment_layout, &b.assignment_layout) {
        (AssignmentLayout::Search, AssignmentLayout::Search) => true,
        (AssignmentLayout::Held(a), AssignmentLayout::Held(b)) => Arc::ptr_eq(a, b),
        _ => false,
    };
    layout
        && projections.is_none()
        && b.projections.is_none()
        && extents.is_none()
        && b.extents.is_none()
        && *relation == b.relation
        && *name == b.name
        && *output_name == b.output_name
        && *depth == b.depth
        && *keys == b.keys
        && *selected == b.selected
        && *frames == b.frames
        && *flows == b.flows
        && *bound_labels == b.bound_labels
        && *rows == b.rows
        && columns.len() == b.columns.len()
        && columns.iter().zip(b.columns.iter()).all(|(a, b)| same_column(a, b))
        && dets.len() == b.dets.len()
        && dets.iter().zip(b.dets.iter()).all(|(a, b)| same_det(a, b))
        && examples.len() == b.examples.len()
        && examples.iter().zip(b.examples.iter()).all(|(a, b)| same_example(a, b, gauges))
}

fn same_column(a: &TableColumn, b: &TableColumn) -> bool {
    let TableColumn { name, ty, slot, label_id, label } = a;
    *name == b.name && *ty == b.ty && *slot == b.slot && *label_id == b.label_id && *label == b.label
}

fn same_det(a: &TableDet, b: &TableDet) -> bool {
    let TableDet { relation, types, columns } = a;
    *relation == b.relation && *types == b.types && *columns == b.columns
}

fn same_example(a: &ExampleRows, b: &ExampleRows, gauges: Compared<'_>) -> bool {
    let ExampleRows { example, rows } = a;
    *example == b.example
        && match (rows, &b.rows) {
            (Ok(a), Ok(b)) => same_assigned(a, b, gauges),
            (Err(a), Err(b)) => a == b,
            _ => false,
        }
}

fn same_assigned(a: &Assigned<Vec<RelationValue>>, b: &Assigned<Vec<RelationValue>>, gauges: Compared<'_>) -> bool {
    let Assigned { at, stop } = a;
    *stop == b.stop
        && at.len() == b.at.len()
        && at.iter().zip(&b.at).all(|((assigned, values), (other_assigned, other_values))| {
            assigned.len() == other_assigned.len()
                && assigned.iter().zip(other_assigned).all(|((relation, rows), (other_relation, other_rows))| relation == other_relation && same_relation(rows, other_rows, gauges))
                && values.len() == other_values.len()
                && values.iter().zip(other_values).all(|(value, other)| match (value, other) {
                    (RelationValue::Rows(a), RelationValue::Rows(b)) => same_relation(a, b, gauges),
                    (RelationValue::Undefined, RelationValue::Undefined) => true,
                    (RelationValue::Stopped(a), RelationValue::Stopped(b)) => a == b,
                    _ => false,
                })
        })
}

/// Whether `a` and `b` hold the same rows in the same order of
/// [`each_row`], which every reader of a table's rows follows.
fn same_relation(a: &Arc<Relation>, b: &Arc<Relation>, compared: Compared<'_>) -> bool {
    if Arc::ptr_eq(a, b) {
        // Two relations that a cache gave twice are one allocation, and a comparison of two allocations of the same rows notes their count: so the gauge does not depend on what the cache held.
        if a.len() <= compared.cap {
            compared.gauges.note(Gauge::ComparedRows, a.len(), compared.cap);
        }
        return true;
    }
    if a.arity() != b.arity() || a.len() != b.len() {
        return false;
    }
    if a.len() > compared.cap {
        compared.gauges.hit(Gauge::ComparedRows, a.len(), compared.cap);
        return false;
    }
    compared.gauges.note(Gauge::ComparedRows, a.len(), compared.cap);
    let width = usize::from(a.arity());
    let mut cells: Vec<arclog::terms::TermId> = Vec::with_capacity(width.saturating_mul(a.len() as usize));
    each_row(a, &mut |row| cells.extend_from_slice(row));
    let (mut at, mut same) = (0, true);
    each_row(b, &mut |row| {
        if same {
            same = cells.get(at..at + width) == Some(row);
            at += width;
        }
    });
    same && at == cells.len()
}
