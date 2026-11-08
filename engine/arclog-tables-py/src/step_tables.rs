//! `step_tables`: the tables of the last step of a decode,
//! `successor_tables`: the tables after each of several tokens at a decode's
//! state, and `output_columns`: the columns that the `OUT` form at which the
//! decode ended selects.

use std::sync::Arc;

use arclog::stream::Emitter;
use arclog_bindings::PyDecoder;
use arclog_tables::columns::{step_case_columns_by_assignment_hashed, step_case_columns_by_assignment_in, step_case_columns_by_assignment_with, step_case_columns_in};
use arclog_tables::split::{self, Part};
use arclog_tables::summary::{train_pairs, Assemblies, DetFulls, SummaryCache};
use arclog::eval::join::Materializer;
use arclog_tables::columns::{CaseColumns, StreamTables};
use arclog_tables::tables::successors::{successor_tables as successors_of, SuccessorKind};
use arclog_tables::tables::{evidence_tables, input_table, mark_selected, selected_columns, step_tables as step_tables_of, Point, Points, Table};
use arclog::decode::{Decoder, LeftOut};
use arclog::program::Form;
use arclog::eval::copies::CopyViolation;
use pyo3::exceptions::{PyIndexError, PyRuntimeError, PyValueError};
use pyo3::prelude::*;
use pyo3::types::PyBytes;

use crate::case_tables::{Base, PyCaseTables, Step};
use crate::shapes::ShapeRuntime;

/// The tables of the last step of `decoder`, a `Decoder` at any state, a fork
/// included, for the case `case` of the task `task`, as `stream_tables` gives
/// that step of the same stream, with the token of the step as their token.
/// They are the table of each relation that the form the step ended declares,
/// with their rows on each example at each assignment, and, where `bodies` is
/// true, the table of the body in progress, as `bodies` is in `stream_tables`.
/// The call replays no token and writes no file, and runs with the GIL
/// released, but for the build of the `CaseTables`.
///
/// `before` is the `CaseTables` that `step_tables` gave at the decode's
/// previous model step, or, for a fork, at the last model step of the decode
/// it was forked from. With `before`, the result holds the step's own tables
/// alone, numbered from `k`, the count of the stream's tables before them, as a
/// case of `stream_tables` that has a base holds its own: `base` is `case`,
/// `base_tokens` the token of the step and `base_tables` is `k`. Each part of
/// the result equals that step's in `stream_tables` of the same stream, and
/// every table number in it is a number of the stream's whole list of tables:
/// the result's own tables are numbered from `k`, and a flow whose source is a
/// table of an earlier step gives that table's number, below `k`, in
/// `source_table` and the column's index in it in `source_column`. The frames,
/// extents, `DET` slots and labels resolve through the earlier tables.
/// Without `before`, the call is at the decode's first model step, and the
/// result is the two evidence tables and the step's tables, with no base. A
/// step that gives no table, such as a decode before its first step, a `*`
/// before its echo, or a step in a form with no relation, adds none.
///
/// `ValueError` is raised, before any evaluation, where `before` is `None` and
/// the decode has a model step before its last, and where `before` is no
/// result of `step_tables`, gives another task, another case or another
/// `bodies`, or gives a step at a token not below the step's. A `before` of a
/// decode before its first step has no step, and passes.
///
/// `RuntimeError` is raised where the export stops at a bound of the request,
/// such as the session's bytes or the deadline, before the result holds a
/// row of each table of the step: the message gives the bound and names
/// each table it left out, by its relation as the program spells it and the
/// path of its form. A stop inside a table's entries leaves the table in the
/// result, with those entries stopped, and raises nothing.
///
/// The `CaseTables` has the `task` and the `case` that the call gives, as a
/// `Decoder` holds neither. Its `relation_name` is the relation as the program
/// spells it, with the slot of a name a decode gives no text. Where the
/// settings check copies, the `copies` part holds the violations that the
/// decode found since the last call that took them, which this call takes.
///
/// With `by_assignment` (the default), the result has a row of `tables` for each table at
/// each of its assignments, and `assignments`, `example_keys` and the `tables`
/// columns `table`, `query`, `name`, `hash`, `hashed`, `capped` and `features` as
/// `arclog_tables::columns::step_case_columns_by_assignment_in` gives them; its
/// `assigned` is `None`, and `query` is the QueryHash of the table's query (`Decoder::query_hash`,
/// 16 bytes), with `has_query` 0 for a body table, which has none. `entries` gives the `hash` of its Rows,
/// has no Count entry, and gives each entry without rows as kind 6 (`NotExported`). The TableHash and the
/// `features` (named by `table_feature_names()`) are computed from the rows the engine holds, with
/// `rows` or without. With `rows`, `entries` holds the full Set of Rows of each row of `tables`, with no
/// count cap; without it, `entries` gives the count of rows alone and the call packs no row. Without
/// `by_assignment`, the result is the layout of `stream_tables`, as it was before `by_assignment`
/// existed, and `rows` has no effect.
///
/// With `summaries` false (and `by_assignment`), the call computes no summary of a table beyond its TableHash, and packs no row, whatever `rows` says.
/// The TableHash is a hash of a table's rows at an assignment, so the call still walks the rows of each table that has one. It leaves out the value hash
/// of each `DET`, the key of each example, the TableVector, and the entries with their rows. The result is the one that `summaries` true gives, but for these
/// parts:
///
/// - `tables` has a row for each table at each of its assignments, and none for a full value of a `DET` that the table reads through some of its
///   columns. A table of a finished query (`has_query` 1) and an evidence table have `hash`, `hashed` and `unhashed_reason` as with `summaries` true.
///   A body table has one row, with `hash` 0, `hashed` 0 and `unhashed_reason` `NotComputed`, and the call walks none of its rows. `capped` and `name` are
///   as with `summaries` true, and `features` is 0 at each feature, in every row. Each other column is as with `summaries` true, `query`, `has_query`,
///   `fault` and the columns' facts (`column_types`, `column_ident_sources`, `column_frames`, `column_slots`) among them;
/// - `assignments`, `example_keys`, `entries`, `projections` and `projection_rows` have no row, and `values` has no cell;
/// - `flows`, `copies` and the `step` that a later call takes as its `before` are as with `summaries` true.
///
/// `output_position` and `output_color` are -1 in each table, since the `OUT`
/// form that selects a column ends the decode at a step after the one that
/// gives that column's table: `output_columns` gives that selection.
#[pyfunction]
#[pyo3(signature = (decoder, task, case, bodies=false, before=None, by_assignment=true, rows=false, summaries=true))]
#[allow(clippy::too_many_arguments)]
pub(crate) fn step_tables(py: Python<'_>, decoder: PyRef<'_, PyDecoder>, task: String, case: String, bodies: bool, before: Option<PyRef<'_, PyCaseTables>>, by_assignment: bool, rows: bool, summaries: bool) -> PyResult<PyCaseTables> {
    let _timed = arclog::stats::span(arclog::stats::Phase::PyStepTables);
    let points = if bodies { Points::All } else { Points::Relations };
    let (engine, evidence) = (decoder.decoder(), decoder.task());
    // The evidence tables hold the task alone, so a session derives them once.
    let evidence_tables = decoder.derived(|| evidence_tables(evidence, engine.registry()));
    let cache = decoder.derived(SummaryCache::default);
    let train = decoder.derived(|| train_pairs(evidence));
    let shapes = decoder.derived(|| ShapeRuntime::new(evidence));
    // The indexes of the tokens the model wrote, which the engine's forced tokens follow in the trace. The last is the index `stream_tables` gives the step; a decode before its first step has none, and no table.
    let written: Vec<usize> = engine.trace().records().iter().enumerate().filter(|(_, record)| record.emitter == Emitter::Model).map(|(index, _)| index).collect();
    let index = written.last().copied();
    let earlier = check_before(before.as_deref(), &task, &case, bodies, &written)?;
    let (columns, stream, left) = py.detach(|| {
        // With the rows packed, the export reserves for each row at least what the packing
        // reserves: the cells of the row, at least one for each column, four times over, and
        // the row's own two slots.
        let limits=if by_assignment && summaries && rows {
            engine.limits().reserving_rows(arclog::eval::RowReserve {per_column:16,fixed:16})
        } else {
            engine.limits()
        };
        let operation=engine.clone().with_operation_limits(limits.clone());
        let engine=&operation;
        let tables: Vec<(usize, Table)> = match index {
            Some(index) => {
                let before = earlier.map_or_else(Vec::new, |step| step.stream.tables());
                let mut own = step_tables_of(engine, points, &before);
                mark_selected(engine, own.iter_mut());
                own.into_iter().map(|table| (index, table)).collect()
            }
            None => Vec::new(),
        };
        let materializer=Materializer::new(engine.evaluation_inputs().1,&limits);
        let (columns, stream) = if by_assignment {
            // The QueryHash of each table: the `query_hash` of its finished query; a body table has none.
            let query_of = |table: &Table| match table.point {
                Point::Relation => table.form.0.first().and_then(|top| engine.query_hash(top.0 as usize)),
                Point::Body { .. } | Point::Evidence => None,
            };
            let queries = {
                let _timed = split::span(Part::OwnQueryHash);
                tables.iter().map(|(_, table)| query_of(table)).collect()
            };
            let before = earlier.map(|step| &*step.stream);
            if summaries {
                step_case_columns_by_assignment_with(&materializer, before, &evidence_tables, tables, &train, queries, rows, &cache, assemblies(engine))
            } else {
                step_case_columns_by_assignment_hashed(&materializer, before, &evidence_tables, tables, &train, queries, &cache, assemblies(engine))
            }
        } else {
            step_case_columns_in(&materializer,earlier.map(|step| &*step.stream), &evidence_tables, tables, evidence.train.len())
        };
        (columns.with_copies(&engine.take_copy_violations()), stream, arclog::clock::Stopwatch::start())
    });
    if arclog::stats::enabled() {
        split::add(Part::GilWait, left.elapsed().nanos());
    }
    complete(&columns)?;
    let base = earlier.map(|step| Base { case: case.clone(), tokens: index.unwrap_or(0), tables: step.stream.count() });
    let _packing = arclog::stats::span(arclog::stats::Phase::PyPack);
    arclog::stats::units(arclog::stats::Phase::PyPack, columns.tables.token.len());
    let own = stream.count() - earlier.map_or(evidence_tables.len() as u32, |step| step.stream.count());
    Ok(PyCaseTables::of(py, task, case, false, engine.settings().projection_cap, columns, None, base)?.with_shapes(shapes).with_step(Step { stream: Arc::new(stream), bodies, token: index, own }))
}

/// The base tables of the task of `decoder`: `input`, `ex_input` and
/// `ex_output`, numbered 0, 1 and 2, at token 0, with point 2, in the layout
/// of `step_tables` with `by_assignment=True`, and `rows` and `summaries` as
/// `step_tables` takes them. `input` has one entry for each example, train and test, which
/// holds the cells of the example's input grid, with no Example column, and
/// its TableVector and TableHash are those of those entries; `ex_input` and
/// `ex_output` are the evidence tables that the first result of `step_tables`
/// gives. The result has no `step`, and serves as no `before`. The call runs
/// with the GIL released, but for the build of the `CaseTables`.
/// `RuntimeError` is raised where the export leaves out a table, as in
/// `step_tables`.
#[pyfunction]
#[pyo3(signature = (decoder, task, case, rows=false, summaries=true))]
pub(crate) fn base_tables(py: Python<'_>, decoder: PyRef<'_, PyDecoder>, task: String, case: String, rows: bool, summaries: bool) -> PyResult<PyCaseTables> {
    let (engine, evidence) = (decoder.decoder(), decoder.task());
    let evidence_tables = decoder.derived(|| evidence_tables(evidence, engine.registry()));
    let train = decoder.derived(|| train_pairs(evidence));
    let shapes = decoder.derived(|| ShapeRuntime::new(evidence));
    let columns = py.detach(|| {
        let limits = engine.limits();
        let materializer = Materializer::new(engine.evaluation_inputs().1, &limits);
        let base: Vec<Table> = std::iter::once(input_table(evidence, engine.registry())).chain(evidence_tables.iter().cloned()).collect();
        // A cache of its own: the evidence tables' summaries are kept by their place, which differs here.
        if summaries {
            step_case_columns_by_assignment_in(&materializer, None, &base, Vec::new(), &train, Vec::new(), rows, &SummaryCache::default()).0
        } else {
            step_case_columns_by_assignment_hashed(&materializer, None, &base, Vec::new(), &train, Vec::new(), &SummaryCache::default(), Assemblies::default()).0
        }
    });
    complete(&columns)?;
    Ok(PyCaseTables::of(py, task, case, false, engine.settings().projection_cap, columns, None, None)?.with_shapes(shapes))
}

/// What `successor_tables` gives for one id: the tables of its successor,
/// the result of an earlier id whose tables and copy violations are equal,
/// or, for the ids whose successor is the body in progress, the one result
/// they share.
enum Packed {
    /// The columns, the stream after the step, and the count of the step's own tables.
    Own(CaseColumns, StreamTables, u32),
    /// The place of that earlier id among the ids.
    Same(usize),
    Unchanged,
}

/// The tables after each token of `ids` at the state of `decoder`, a
/// `Decoder` at a writing point: for each id, what `step_tables` with
/// `bodies=True` and `by_assignment=True` gives at the decode that the id
/// advances (a fork of `decoder` that steps the id), with `before` the result
/// of `step_tables` at the last model step of `decoder` (made with
/// `bodies=True`), or `None` where `decoder` has no model step. `decoder`
/// stays as it was. Where `Decoder.admissible` has computed the mask at this
/// state, the state after each admitted id comes from the mask, and no check
/// runs again. The call runs with the GIL released, but for the build of the
/// `CaseTables`.
///
/// The result is `(current, results)`. `current` is a `CaseTables` that holds
/// the table of the body in progress at the state of `decoder`, numbered as a
/// successor's tables are, at the token of the decode's last model step, with
/// no `step`, or `None` where no clause is in progress or its body is empty.
/// `results` has one `(kind, note, tables)` for each id, in the order of
/// `ids`. `tables` is a `CaseTables` in the layout of `step_tables` with
/// `by_assignment=True`, with `rows` as `step_tables` takes it, numbered from
/// the count of the stream's tables before the step, at the token index of
/// the step; it serves as the `before` of `step_tables` at the decode that
/// steps the id. `kind` is
///
/// - `"body"`: the id changes the body in progress, and `tables` holds the
///   table of the successor body, the body with the id's site or conjunct.
///   Where the id leaves the point of the body as it was, as a label or a
///   constant that fills a site already open, `step_tables` gives no table,
///   and this is the table of the successor body as `step_tables` makes a
///   body table;
/// - `"left_out"`: the id changes the point of the body in progress (its count
///   of conjuncts or of sites), and the successor body leaves out the conjunct
///   in progress, as `note` says: an atom of a lib relation none of whose modes
///   has a site at each of its bound columns yet, or a conjunct that is no atom
///   (a `NOT`, an `OR`, an `IF`, an `ALL` or a constraint) before its end.
///   `tables` holds the table at the new point, whose rows are those of the
///   body without that conjunct, as `step_tables` gives it;
/// - `"unchanged"`: the id leaves the body in progress and its point as they
///   were, as an id that opens an atom of a lib relation that the body leaves out
///   at the same point. `tables` holds the
///   table of the body in progress, at the step's token, where `step_tables`
///   gives no table. Every such id shares one `CaseTables`;
/// - `"finished"`: the id finishes the form in progress, and `tables` holds the
///   tables of the relations the form declares, as `step_tables` gives them,
///   none for a form that declares none, such as an `OUT` form;
/// - `"none"`: after the id no clause is in progress, or its body is empty,
///   and no form finished, and `tables` holds no table;
/// - `"refused"`: the decode refuses the id, `note` gives the refusal, and
///   `tables` is `None`.
///
/// Ids whose `tables` would hold equal columns share one `CaseTables`: the ids
/// of `"unchanged"`, and ids of `"body"`, `"left_out"` and `"none"`, and of
/// `"finished"` with no table, whose successors' tables are equal
/// (`arclog_tables::tables::successors::same_tables`) or whose successors have
/// one body and point, and whose evaluations found the same copy violations.
///
/// Where a table of the result faulted, as a body that no check passes, `note`
/// also gives the fault, and the table's `fault` gives it as `step_tables`
/// does. A successor body is evaluated as the evaluator joins one conjunct to
/// the rows of the body's other parts (`arclog_tables::tables::successors`).
///
/// `IndexError` is raised for an id outside the vocabulary, `ValueError`
/// where `before` cannot stand before the step, and `RuntimeError` where the
/// export of a successor's tables leaves out a table, as `step_tables` raises
/// them.
#[pyfunction]
#[pyo3(signature = (decoder, ids, task, case, before=None, rows=false))]
#[allow(clippy::type_complexity)]
pub(crate) fn successor_tables(py: Python<'_>, decoder: PyRef<'_, PyDecoder>, ids: Vec<u32>, task: String, case: String, before: Option<PyRef<'_, PyCaseTables>>, rows: bool) -> PyResult<(Option<Py<PyCaseTables>>, Vec<(&'static str, String, Option<Py<PyCaseTables>>)>)> {
    let (engine, evidence) = (decoder.decoder(), decoder.task());
    let vocabulary = engine.vocabulary();
    let tokens = ids.iter().map(|&id| vocabulary.token(id).cloned().ok_or_else(|| PyIndexError::new_err(format!("no token with id {id}")))).collect::<PyResult<Vec<_>>>()?;
    let evidence_tables = decoder.derived(|| evidence_tables(evidence, engine.registry()));
    let summaries = decoder.derived(SummaryCache::default);
    let records = engine.trace().records();
    let mut written: Vec<usize> = records.iter().enumerate().filter(|(_, record)| record.emitter == Emitter::Model).map(|(index, _)| index).collect();
    let now = written.last().copied();
    // The token of each successor's step is the next record of the trace.
    let index = records.len();
    written.push(index);
    let earlier = check_before(before.as_deref(), &task, &case, true, &written)?;
    let train = decoder.derived(|| train_pairs(evidence));
    let shapes = decoder.derived(|| ShapeRuntime::new(evidence));
    let (current, each, unchanged) = py.detach(|| {
        let limits = engine.limits();
        let materializer = Materializer::new(engine.evaluation_inputs().1, &limits);
        let stream = earlier.map(|step| &*step.stream);
        let before_tables = stream.map_or_else(Vec::new, StreamTables::tables);
        // The table of the body in progress, where the call at the decode's last model step gave it as its one table.
        let held = earlier
            .filter(|step| step.token.is_some() && step.token == now && step.own == 1)
            .and_then(|step| step.stream.tables().last().filter(|table| matches!(table.point, Point::Body { .. })).map(|table| (*table).clone()));
        let found = {
            let _timed = split::span(Part::SuccessorTables);
            successors_of(engine, &limits, tokens, &before_tables, held)
        };
        let columns_of = |tables: Vec<(usize, Table)>, queries: Vec<Option<arclog::hash::StableHash>>, program: &Decoder<'_>| {
            let _timed = split::span(Part::SuccessorColumns);
            step_case_columns_by_assignment_with(&materializer, stream, &evidence_tables, tables, &train, queries, rows, &summaries, assemblies(program))
        };
        let current = found.current.as_ref().map(|table| columns_of(vec![(now.unwrap_or(0), table.clone())], vec![None], engine).0);
        let mut unchanged: Option<(CaseColumns, StreamTables)> = None;
        // The copy violations of each id's successor, empty for a refused id.
        let mut copies: Vec<Vec<CopyViolation>> = Vec::with_capacity(found.each.len());
        let mut each: Vec<Result<(&'static str, String, Packed), String>> = Vec::with_capacity(found.each.len());
        for successor in found.each {
            let successor = match successor {
                Ok(successor) => successor,
                Err(refusal) => {
                    copies.push(Vec::new());
                    each.push(Err(format!("{refusal:?}")));
                    continue;
                }
            };
            let mut notes: Vec<String> = Vec::new();
            let kind = match successor.kind {
                SuccessorKind::Body => "body",
                SuccessorKind::LeftOut(left_out) => {
                    notes.push(match left_out {
                        LeftOut::Atom => "the body leaves out the atom in progress: no mode of its relation has a site at each of its bound columns yet",
                        LeftOut::Conjunct => "the body leaves out the conjunct in progress: it is no atom, and it has not ended",
                    }.to_owned());
                    "left_out"
                }
                SuccessorKind::Unchanged => "unchanged",
                SuccessorKind::Finished => "finished",
                SuccessorKind::NoBody => "none",
            };
            notes.extend(successor.tables.iter().filter_map(|table| table.contents.as_ref().err()).map(|fault| format!("fault: {}", fault.message)));
            let note = notes.join("; ");
            let next = &successor.decoder;
            let violations = next.take_copy_violations();
            if successor.kind == SuccessorKind::Unchanged {
                if unchanged.is_none() {
                    let (columns, _) = columns_of(successor.tables.into_iter().map(|table| (index, table)).collect(), vec![None], next);
                    let (_, stream) = columns_of(Vec::new(), Vec::new(), next);
                    unchanged = Some((columns, stream));
                }
                copies.push(violations);
                each.push(Ok((kind, note, Packed::Unchanged)));
                continue;
            }
            if let Some(first) = successor.same_as.filter(|&first| copies[first] == violations) {
                copies.push(violations);
                each.push(Ok((kind, note, Packed::Same(first))));
                continue;
            }
            let queries = successor.tables.iter().map(|table| match table.point {
                Point::Relation => table.form.0.first().and_then(|top| next.query_hash(top.0 as usize)),
                Point::Body { .. } | Point::Evidence => None,
            }).collect();
            let own = u32::try_from(successor.tables.len()).expect("fewer than 2^32 tables");
            let (columns, stream) = columns_of(successor.tables.into_iter().map(|table| (index, table)).collect(), queries, next);
            let columns = columns.with_copies(&violations);
            copies.push(violations);
            each.push(Ok((kind, note, Packed::Own(columns, stream, own))));
        }
        (current, each, unchanged)
    });
    for columns in current.iter().chain(unchanged.as_ref().map(|(columns, _)| columns)).chain(each.iter().filter_map(|result| match result {
        Ok((_, _, Packed::Own(columns, _, _))) => Some(columns),
        _ => None,
    })) {
        complete(columns)?;
    }
    let _timed = split::span(Part::SuccessorObjects);
    let base = |tokens: usize| earlier.map(|step| Base { case: case.clone(), tokens, tables: step.stream.count() });
    let cap = engine.settings().projection_cap;
    let pack = |columns: CaseColumns, tokens: usize| PyCaseTables::of(py, task.clone(), case.clone(), false, cap, columns, None, base(tokens)).map(|tables| tables.with_shapes(Arc::clone(&shapes)));
    let current = current.map(|columns| Py::new(py, pack(columns, now.unwrap_or(0))?)).transpose()?;
    let unchanged = unchanged.map(|(columns, stream)| -> PyResult<Py<PyCaseTables>> { Py::new(py, pack(columns, index)?.with_step(Step { stream: Arc::new(stream), bodies: true, token: Some(index), own: 0 })) }).transpose()?;
    let mut results: Vec<(&'static str, String, Option<Py<PyCaseTables>>)> = Vec::with_capacity(each.len());
    for result in each {
        let result = match result {
            Err(refusal) => ("refused", refusal, None),
            Ok((kind, note, Packed::Unchanged)) => (kind, note, unchanged.as_ref().map(|shared| shared.clone_ref(py))),
            Ok((kind, note, Packed::Same(first))) => (kind, note, results[first].2.as_ref().map(|shared| shared.clone_ref(py))),
            Ok((kind, note, Packed::Own(columns, stream, own))) => (kind, note, Some(Py::new(py, pack(columns, index)?.with_step(Step { stream: Arc::new(stream), bodies: true, token: Some(index), own }))?)),
        };
        results.push(result);
    }
    Ok((current, results))
}

/// A `RuntimeError` where the packing of `columns` stopped and left out a
/// table, which names the stop and each table left out. The columns hold no
/// row of such a table, so a result made of them could not be told from the
/// result of a step that gives no table.
fn complete(columns: &CaseColumns) -> PyResult<()> {
    match (columns.left_out(), columns.packing_stop()) {
        ([], _) => Ok(()),
        (left_out, stop) => Err(PyRuntimeError::new_err(format!(
            "the export of the tables stopped{} and left out the table of {}",
            stop.map_or_else(String::new, |stop| format!(" at {:?}", stop.bound)),
            left_out.join(", ")
        ))),
    }
}

/// The `Step` of `before`, the `before` of a call of `step_tables` for `task`
/// and `case` under `bodies`, at the step of the last of the tokens `written`
/// by the model, or a `ValueError` where `before` cannot stand before that
/// step. It is `None` for the call at the first model step, which has no
/// `before`.
fn check_before<'b>(before: Option<&'b PyCaseTables>, task: &str, case: &str, bodies: bool, written: &[usize]) -> PyResult<Option<&'b Step>> {
    let index = written.last().copied();
    let Some(before) = before else {
        return if written.len() > 1 { Err(PyValueError::new_err(format!("the decode has {} model steps, and a call after its first takes the result of the call at the previous model step as `before`", written.len()))) } else { Ok(None) };
    };
    let Some(step) = before.step() else { return Err(PyValueError::new_err("`before` is no result of `step_tables`")) };
    if before.task != task || before.case != case {
        return Err(PyValueError::new_err(format!("`before` is of the task {} and the case {}, not of {task} and {case}", before.task, before.case)));
    }
    if step.bodies != bodies {
        return Err(PyValueError::new_err(format!("`before` was made with bodies={}, not bodies={bodies}", step.bodies)));
    }
    match (step.token, index) {
        (Some(token), Some(index)) if token >= index => Err(PyValueError::new_err(format!("`before` is the step at token {token}, not below the step at token {index}"))),
        (Some(token), None) => Err(PyValueError::new_err(format!("`before` is the step at token {token}, and the decode has no model step"))),
        _ => Ok(Some(step)),
    }
}

/// The table of each candidate atom at the state of `decoder`: for each atom of
/// `atoms`, each a list of ids of tokens, the place of its table's summary among
/// the summaries, `None` where it has no table; each summary as whether it is
/// capped, the TableHash at each assignment, 16 bytes each and zero for none,
/// and the features at each assignment; the count of atoms that took a program
/// of their own, and the place in `atoms` of each atom whose work passed the
/// cap, which has no table. With `by_program` each atom takes a program. The
/// call is one request, under the request work cap.
#[pyfunction]
#[pyo3(signature = (decoder, atoms, task, case, before=None, by_program=false))]
#[allow(clippy::type_complexity)]
pub(crate) fn atom_tables<'py>(py: Python<'py>, decoder: PyRef<'py, PyDecoder>, atoms: Vec<Vec<u32>>, task: String, case: String, before: Option<PyRef<'py, PyCaseTables>>, by_program: bool) -> PyResult<(Vec<Option<u32>>, Vec<(bool, Bound<'py, PyBytes>, Bound<'py, PyBytes>)>, usize, Vec<u32>)> {
    let (engine, evidence) = (decoder.decoder(), decoder.task());
    let train = decoder.derived(|| train_pairs(evidence));
    let _ = (&task, &case);
    let stream = before.as_deref().and_then(|before| before.step()).map(|step| &*step.stream);
    let atoms: Vec<Box<[u32]>> = atoms.into_iter().map(Vec::into_boxed_slice).collect();
    let memo = decoder.derived(arclog_tables::tables::atom_tables::AtomTablesMemo::default);
    let key = if by_program { None } else { arclog_tables::tables::atom_tables::AtomTablesMemo::key(engine, &atoms) };
    let found = match key.and_then(|key| memo.get(key)) {
        Some(found) => found,
        None => {
            let found = std::sync::Arc::new(py.detach(|| {
                let limits = engine.limits();
                let operation = engine.clone().with_operation_limits(limits.clone());
                let materializer = Materializer::new(engine.evaluation_inputs().1, &limits);
                let tables = stream.map_or_else(Vec::new, StreamTables::tables);
                let fulls = DetFulls::new(tables).with_assemblies(assemblies(engine));
                arclog_tables::tables::atom_tables::atom_tables(&operation, &atoms, &materializer, &train, &fulls, by_program)
            }));
            if let Some(key) = key {
                memo.keep(key, std::sync::Arc::clone(&found));
            }
            found
        }
    };
    let summaries = found.summaries.iter().map(|summary| {
        let hashes: Vec<u8> = summary.assignments.iter().flat_map(|at| at.hash.map_or(0u128, |hash| hash.0).to_le_bytes()).collect();
        let features: Vec<u8> = summary.assignments.iter().flat_map(|at| at.features.iter().flat_map(|value| value.to_le_bytes())).collect();
        (summary.capped, PyBytes::new(py, &hashes), PyBytes::new(py, &features))
    }).collect();
    Ok((found.index.clone(), summaries, found.by_program, found.over_cap.clone()))
}

/// The verdicts that the process holds for the atoms of the lib's relations and
/// the fact relations, as bytes that `add_atom_verdicts` reads in a process of the
/// same extension and settings, so that its walks start warm.
#[pyfunction]
pub(crate) fn atom_verdicts<'py>(py: Python<'py>) -> Bound<'py, PyBytes> {
    PyBytes::new(py, &arclog::decode::atom_verdicts())
}

/// Adds the verdicts that `atom_verdicts` gave, and gives the count of them.
#[pyfunction]
pub(crate) fn add_atom_verdicts(bytes: &[u8]) -> PyResult<usize> {
    arclog::decode::add_atom_verdicts(bytes).ok_or_else(|| PyValueError::new_err("the atom verdicts are not whole, or another build of the engine gave them"))
}

/// The columns that the `OUT` form at which `decoder` ended selects: one
/// `(slot, position, color)` for each relation an atom of the form selects a
/// column of, with `slot` the `relation` of that relation's table in
/// `step_tables`, `position` the index of the Position column the form selects
/// there and `color` that of the Color column, and -1 for a column it does not
/// select there. They are the `output_position` and `output_color` of that
/// relation's table in `stream_tables` of the same stream. The list is empty
/// where the decode has not ended at an `OUT` form whose check holds.
#[pyfunction]
pub(crate) fn output_columns(py: Python<'_>, decoder: PyRef<'_, PyDecoder>) -> Vec<(u32, i32, i32)> {
    let engine = decoder.decoder();
    py.detach(|| selected_columns(engine).into_iter().map(|(slot, selected)| (slot, selected.position.map_or(-1, i32::from), selected.color.map_or(-1, i32::from))).collect())
}

/// The time spent in the parts of the export by assignment that `engine_stats` has no phase for, as `(part, calls, seconds)`: the QueryHash of the step's tables, the look-up of a `DET`'s QueryHash, the summary look-ups that found a summary and those that built one, the columns of the step's tables, their regrouping by assignment, and the wait to hold the GIL again after a call's work. A part's time includes the parts inside it. The counters are zero unless the environment variable `ARCLOG_STATS` is set; with `reset` they start again from zero after they are read.
#[pyfunction]
#[pyo3(signature = (reset=false))]
pub(crate) fn step_tables_split(reset: bool) -> Vec<(&'static str, u64, f64)> {
    split::snapshot(reset).into_iter().map(|(name, calls, nanos)| (name, calls, nanos as f64 / 1e9)).collect()
}

/// The QueryHash of each finished `RIGID_DET` form of the program of `decoder`,
/// by the form's name, by which the hashes of a step name each Pose type.
fn assemblies(decoder: &Decoder<'_>) -> Assemblies {
    decoder
        .program()
        .value()
        .forms
        .iter()
        .enumerate()
        .filter_map(|(position, form)| match form {
            Form::RigidDet(rigid) => Some((rigid.value().name.clone(), decoder.query_hash(position)?)),
            _ => None,
        })
        .collect()
}
