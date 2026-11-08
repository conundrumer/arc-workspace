//! Generic join over a clause's IR: it binds one variable at a time, in the
//! clause's variable order, by intersecting the atoms that hold it. It counts
//! the bindings it tries as effort, which only the effort guard of the request
//! bounds ([`Budget::charge_work`]), and the content of the evaluation against
//! the caps ([`Budget::charge_content`]): the sizes of the relations that the
//! evaluation reads and of the table it writes, which depend on the clause's
//! content alone and not on the order that it is written or searched in. A
//! body is joined part by part, as [`parts`] gives its parts, and its
//! relation is their product, which no join counts: a reader that indexes
//! or walks that product counts it as [`Budget::charge_product`] gives.
//!
//! An algebra relation is evaluated at the point in the order where one of
//! its modes is satisfied, and its outputs are variables that later atoms
//! join on through an index.
//!
//! The evaluation of one clause or part serves a lib atom, a filter and a
//! branch at bound values it has evaluated them at from its [`SearchMemo`],
//! with the counts of their evaluation, and builds the plan of each nested
//! clause once per set of bound variables.

use std::cell::RefCell;
use std::rc::Rc;
use std::sync::Arc;

use super::ir::{Argument, Arguments, ClauseIr, Comparison, Filter, IrNode, Operand, Variable};
pub(crate) mod branches;
mod spatial;

use super::plan::{
    algebra_relation, bound_variables, grounds, kept_nodes, mode_holds, values_first, variable_order, NodeSize, RelationSizes,
    VariableOrder,
};
use super::{Caps, Evaluation, Gauge, Limits, ReachedBound, Stop};
use crate::algebra::geometry::domain;
use crate::hash::StableHashMap;
use crate::program::path::NodePath;
use crate::program::ConstraintOp;
use crate::registry::{LibName, Registry};
use crate::relations::{ColumnIndex, ColumnOrder, Index, IndexNode, Relation, RelationPart, RowSet};
use crate::session::{Counts, TaskSession};
use crate::terms::{Term, TermId};
use crate::types::ValueType;

/// The bindings a [`Batch`] counts before it charges its budget.
const BATCH: u64 = 1024;

/// The bytes of an index build below which [`Budget::charge_index_build`]
/// takes no check of the session's bytes: a build this small adds less than
/// the next batch's check can miss, and nearly every build is under it.
pub const BUILD_CHECK_MIN: usize = 1 << 20;

/// The bytes that the build of an index over `rows` rows in an order of
/// `columns` columns holds: a cell for each column of each row, and a place
/// for each row.
pub fn index_bytes(rows: u64, columns: usize) -> u64 {
    rows.saturating_mul(columns.saturating_mul(std::mem::size_of::<TermId>()).saturating_add(std::mem::size_of::<u32>()) as u64)
}

/// The bytes that a row of `width` columns takes in a set of rows that an
/// evaluation holds: its cells, and its slot in the table that finds it.
pub fn row_bytes(width: usize) -> u64 {
    (width.saturating_mul(std::mem::size_of::<TermId>()) as u64).saturating_add(16)
}

/// The rows that the build of the index of `relation` in `order` walks, where
/// they are known before it: `work` where the build reads several parts,
/// which counts one row for each combination of their rows, and the rows of
/// the one part that it reads where all that part's columns are in `order`.
/// Zero otherwise, as for a part that the build reads by its distinct
/// projections, whose count the build alone gives.
fn index_rows(relation: &Relation, order: &ColumnOrder, work: u64) -> u64 {
    if work > 0 {
        return work;
    }
    if relation.is_empty() || order.0.is_empty() {
        return 0;
    }
    let mut read = relation.parts().iter().filter(|part| part.columns.iter().any(|column| order.0.contains(column)));
    match (read.next(), read.next()) {
        (Some(part), None) if part.columns.iter().all(|column| order.0.contains(column)) => part.rows.len() as u64,
        _ => 0,
    }
}

/// The counts of one evaluation against its caps and its other bounds: the
/// content counted (`bindings`, the units of [`Budget::charge_content`]) and
/// the rows held. The bindings that a search tries stand in the effort of the
/// request and in no count of the evaluation. The rows it counts are those
/// of the evaluation it stands for: an evaluation nested in a join counts its
/// own rows and adds none to the count around it, as [`Budget::nested`]
/// gives.
#[derive(Debug)]
pub struct Budget<'a> {
    limits: &'a Limits,
    session: &'a TaskSession,
    bindings: u64,
    rows: u64,
    /// The most rows a nested evaluation that gave a value held.
    nested_rows: u64,
    /// The charges made since [`Budget::logged`] began a log.
    log: Option<Charges>,
    /// The rows charged since the last check of the session's bytes in
    /// [`Budget::charge_rows`].
    unchecked: u64,
    /// The bytes of the rows that [`Budget::charge_rows_of`] counted and no
    /// charge of bytes has taken yet: [`Budget::charge_work`] takes them once
    /// per batch.
    pending_bytes: u64,
    /// The bytes that this budget holds in the request: those it charged and
    /// has not credited.
    held: u64,
    /// The most that `held` and the bytes held for a moment reached, since a
    /// log began ([`Budget::logged`]).
    high: u64,
}

impl<'a> Budget<'a> {
    /// A budget with no work and no rows counted, under `limits` and the
    /// caps of `session`.
    pub fn new(limits: &'a Limits, session: &'a TaskSession) -> Self {
        Budget { limits, session, bindings: 0, rows: 0, nested_rows: 0, log: None, unchecked: 0, pending_bytes: 0, held: 0, high: 0 }
    }

    /// The caps of the session.
    pub fn caps(&self) -> Caps {
        self.session.caps
    }

    /// Counts `bindings` more tried by a search, as effort of the request
    /// ([`RequestWork::charge_effort`]), and checks the row cap, the effort
    /// guard and the cancellation, and has the session evict its caches where
    /// it is past its byte bound.
    ///
    /// The effort bounds a runaway and decides no result, so the bindings add
    /// to no cap of the evaluation, of the request or of an observation: those
    /// count content ([`Budget::charge_content`]). A stop at the effort guard
    /// is a fault of the call.
    ///
    /// The bytes of the rows counted since the last batch are charged here
    /// ([`Budget::flush_bytes`]). The session's byte bound is checked here as
    /// [`TaskSession::relieve`] gives, once per call, and the session evicts
    /// where it is past: that stops nothing and changes no result. A
    /// caller charges once per [`BATCH`] bindings, and a walk of rows once per
    /// [`BATCH`] rows, so a check follows at most a
    /// batch of work, and its cost, a few loads and two short locks, stands
    /// against that work. A build that adds bytes in one piece, an index, is
    /// checked before it starts: [`Budget::charge_index_build`].
    pub fn charge_work(&mut self, bindings: u64) -> Result<(), ReachedBound> {
        let caps = self.session.caps;
        let gauges = self.limits.request.gauges();
        if self.rows > caps.rows {
            gauges.hit(Gauge::Rows, self.rows, caps.rows);
            return Err(ReachedBound::Rows { cap: caps.rows });
        }
        gauges.note(Gauge::Rows, self.rows, caps.rows);
        self.limits.request.charge_effort(bindings)?;
        self.flush_bytes()?;
        let bytes = self.session.relieve(&self.limits.heap_starts, self.limits.byte_bound, 0);
        gauges.note(Gauge::SessionBytes, bytes as u64, self.limits.byte_bound.unwrap_or(self.session.bound).bytes as u64);
        if self.limits.cancellation.is_cancelled() {
            return Err(ReachedBound::Cancelled);
        }
        Ok(())
    }

    /// Counts `units` of content: the rows that an evaluation reads from the
    /// relations of its nodes, or writes in the table it gives, or that a walk
    /// of a table visits. The units add to this evaluation's count, which the
    /// binding cap bounds, to the request's work and to the observation's
    /// count, and they depend on the content of the evaluation alone: no
    /// written order of a clause, order of the search, index or cache changes
    /// them. A cache hit charges the units that its entry recorded.
    pub fn charge_content(&mut self, units: u64) -> Result<(), ReachedBound> {
        if let Some(log) = &mut self.log {
            log.bindings = log.bindings.saturating_add(units);
        }
        self.bindings = self.bindings.saturating_add(units);
        let caps = self.session.caps;
        let gauges = self.limits.request.gauges();
        if self.bindings > caps.bindings {
            gauges.hit(Gauge::Bindings, self.bindings, caps.bindings);
            return Err(ReachedBound::Bindings { cap: caps.bindings });
        }
        gauges.note(Gauge::Bindings, self.bindings, caps.bindings);
        self.limits.request.charge(units)?;
        // The observation's count takes the units here, whether or not there is a count, so a cost holds them for a hit to charge.
        super::tally_table(units);
        match &self.limits.table_work {
            Some(work) => work.charge(units),
            None => Ok(()),
        }
    }

    /// Counts the content that the join of the nodes `nodes` reads: the rows
    /// of the relations that the nodes and the clauses nested in them read in
    /// `inputs` ([`read_size`]).
    pub fn charge_reads(&mut self, nodes: &[usize], inputs: &JoinInputs) -> Result<(), ReachedBound> {
        self.charge_content(read_size(nodes, inputs))
    }

    /// Counts the content of `relation`, the table that an evaluation writes:
    /// the rows that its parts hold ([`Relation::held_rows`]).
    pub fn charge_written(&mut self, relation: &Relation) -> Result<(), ReachedBound> {
        self.charge_content(relation.held_rows())
    }

    /// Charges `bytes` that an evaluation allocates and holds: to the cost of
    /// the measurement open, which a hit on its entry charges again, to the
    /// request's byte budget ([`RequestWork::charge_bytes`]) and to the byte
    /// budget of the assignment, where the evaluation is one assignment's own
    /// ([`TableWork::charge_bytes`]). The evaluation holds the bytes until it
    /// credits them ([`Budget::credit_bytes`]) or the measurement around it
    /// ends. The bytes held depend on the sites that charge and credit alone,
    /// and not on what the session held.
    pub fn charge_bytes(&mut self, bytes: u64) -> Result<(), ReachedBound> {
        self.held = self.held.saturating_add(bytes);
        self.high = self.high.max(self.held);
        let request = &self.limits.request;
        let charged = request.charge_bytes(bytes).and_then(|()| match &self.limits.table_work {
            Some(work) => work.charge_bytes(bytes).inspect_err(|_| request.credit_bytes(bytes)),
            None => Ok(()),
        });
        if charged.is_err() {
            self.held = self.held.saturating_sub(bytes);
        }
        charged
    }

    /// Charges `bytes` that an evaluation holds for a moment: the check of
    /// [`Budget::charge_bytes`], with the bytes freed again.
    pub fn charge_bytes_transient(&mut self, bytes: u64) -> Result<(), ReachedBound> {
        self.high = self.high.max(self.held.saturating_add(bytes));
        self.limits.request.charge_bytes_transient(bytes)?;
        match &self.limits.table_work {
            Some(work) => work.charge_bytes_transient(bytes),
            None => Ok(()),
        }
    }

    /// Frees `bytes` that [`Budget::charge_bytes`] held.
    pub fn credit_bytes(&mut self, bytes: u64) {
        self.held = self.held.saturating_sub(bytes);
        self.limits.request.credit_bytes(bytes);
        if let Some(work) = &self.limits.table_work {
            work.credit_bytes(bytes);
        }
    }

    /// Charges the bytes of the rows that [`Budget::charge_rows_of`] counted
    /// since the last charge. The rows are held by the evaluation that found
    /// them, and by the value that it gives.
    fn flush_bytes(&mut self) -> Result<(), ReachedBound> {
        match std::mem::take(&mut self.pending_bytes) {
            0 => Ok(()),
            bytes => self.charge_bytes(bytes),
        }
    }

    /// Counts `rows` more rows held, of `width` columns each, as
    /// [`Budget::charge_rows`] does, and counts their bytes for the next
    /// batch's charge ([`Budget::charge_work`]).
    pub fn charge_rows_of(&mut self, rows: u64, width: usize) -> Result<(), ReachedBound> {
        self.pending_bytes = self.pending_bytes.saturating_add(rows.saturating_mul(row_bytes(width)));
        self.charge_rows(rows)
    }

    /// Counts `units` of work in the request alone: the rows that a walk, a
    /// materialization or an index build visits, which no cap of this
    /// evaluation or of an observation counts. The charge is one add to the
    /// request's count ([`RequestWork::charge`]).
    pub fn charge_request(&mut self, units: u64) -> Result<(), ReachedBound> {
        if let Some(log) = &mut self.log {
            log.request = log.request.saturating_add(units);
        }
        self.limits.request.charge(units)
    }

    /// Counts the rows of the product of the parts of `relation` as content,
    /// where it holds more than one part, before a walk of its rows
    /// or an index builds them: the join of each part counted that part's
    /// rows, and no join counts their product. The count is one charge, so
    /// a product past a cap stops before any of its rows is built.
    pub fn charge_product(&mut self, relation: &Relation) -> Result<(), ReachedBound> {
        match relation.parts() {
            [] | [_] => Ok(()),
            _ => self.charge_content(relation.len()),
        }
    }

    /// Charges the index of `relation` in `order`, which this call finds not
    /// yet built, and has the session evict its caches where the build would
    /// take it past its byte bound. `work` is what [`Relation::index_work`]
    /// gives for `order`.
    ///
    /// A build walks the rows of the parts of `relation` that hold a column
    /// of `order`, as many as `work` counts where it reads several parts, and
    /// holds, until it ends, a cell for each column of
    /// `order` for each row, and a place for each row. The request and the
    /// assignment hold those bytes while the build runs
    /// ([`Budget::charge_bytes_transient`]), at each use, whether or not the
    /// relation held the index, so the bytes held do not depend on what an
    /// earlier use built.
    ///
    /// The call costs a sum of a few terms where the build is under
    /// [`BUILD_CHECK_MIN`] bytes, which are most builds. A larger build takes
    /// the check of [`TaskSession::relieve`] and a read of the relation's
    /// count of indexes, against the build's work of at least
    /// [`BUILD_CHECK_MIN`] bytes of writes. The call checks only while the
    /// relation holds no index, since a caller cannot read which orders it
    /// holds an index for.
    pub fn charge_index_build(&mut self, relation: &Relation, order: &ColumnOrder, work: u64) -> Result<(), ReachedBound> {
        let bytes = index_bytes(index_rows(relation, order, work), order.0.len());
        self.charge_bytes_transient(bytes)?;
        let bytes = usize::try_from(bytes).unwrap_or(usize::MAX);
        if bytes >= BUILD_CHECK_MIN && relation.index_bytes().0 == 0 {
            self.session.relieve(&self.limits.heap_starts, self.limits.byte_bound, bytes);
        }
        Ok(())
    }

    /// Admits a new full-row buffer. The compact parts of a relation have not
    /// paid for their Cartesian product; flat rows pay no binding work again.
    /// Output rows and their conservative byte size count as new held data:
    /// the request and the assignment hold the bytes until the returned
    /// allocation drops.
    pub fn materialize(&mut self, relation: &Relation, bytes_per_row: usize) -> Result<crate::session::SessionAllocation, ReachedBound> {
        self.charge_work(0)?;
        self.charge_product(relation)?;
        if relation.parts().len() < 2 {
            // A relation of several parts counted its rows as bindings above.
            self.charge_request(relation.len())?;
        }
        self.charge_rows(relation.len())?;
        let bytes = usize::try_from(relation.len()).unwrap_or(usize::MAX).saturating_mul(bytes_per_row);
        self.own(bytes.saturating_add(128))
    }

    /// An allocation of `bytes` of the session, which the request and the
    /// assignment hold until it drops. The session reserves the bytes whether
    /// or not it has room: it evicts its caches where it is past its bound.
    fn own(&mut self, bytes: usize) -> Result<crate::session::SessionAllocation, ReachedBound> {
        let owner = self.limits.hold_bytes_owned(u64::try_from(bytes).unwrap_or(u64::MAX))?;
        Ok(self.session.reserve(bytes, &self.limits.heap_starts, self.limits.byte_bound).owned_by(owner))
    }

    /// Walks admitted rows, checking the request's work, the cancellation and
    /// the session bound each batch. The rows add to the request's work, one
    /// unit each, and to no other count: their bindings were charged where a
    /// join found them.
    pub fn walk_rows(&mut self, relation: &Relation, visit: &mut dyn FnMut(&[TermId])) -> Result<(), ReachedBound> {
        let mut count = 0u64;
        try_each_row(relation, &mut |row| {
            if count % BATCH == 0 {
                self.charge_work(0)?;
                if count > 0 {
                    self.charge_request(BATCH)?;
                }
            }
            count += 1;
            visit(row);
            Ok(())
        })?;
        // The rows since the last full batch charged.
        let charged = if count == 0 { 0 } else { (count - 1) / BATCH * BATCH };
        self.charge_request(count - charged)
    }

    /// Counts `rows` more rows held, and checks the row cap. Once per
    /// [`BATCH`] rows it has the session evict its caches where it is past its
    /// byte bound ([`TaskSession::relieve`]).
    pub fn charge_rows(&mut self, rows: u64) -> Result<(), ReachedBound> {
        self.rows += rows;
        let cap = self.session.caps.rows;
        if self.rows > cap {
            self.limits.request.gauges().hit(Gauge::Rows, self.rows, cap);
            return Err(ReachedBound::Rows { cap });
        }
        // Rows accrue one at a time between the checks of a batch of bindings, so the bytes are checked here too.
        self.unchecked = self.unchecked.saturating_add(rows);
        if self.unchecked >= BATCH {
            self.unchecked = 0;
            self.session.relieve(&self.limits.heap_starts, self.limits.byte_bound, 0);
        }
        Ok(())
    }

    /// Runs `evaluate`, an evaluation nested in a join, and gives its result.
    /// The evaluation counts the rows it holds against the row cap on their
    /// own, from none, and adds none to the count around it, whether it gives
    /// a value or a stop. It adds each binding it tries to that count. The
    /// most rows a nested evaluation that gave a value held is recorded by
    /// [`Budget::record`] as the rows, where it exceeds the rows of the
    /// evaluation around it.
    pub fn nested<T>(&mut self, evaluate: impl FnOnce(&mut Self) -> Result<T, ReachedBound>) -> Result<T, ReachedBound> {
        let outer = std::mem::take(&mut self.rows);
        let result = evaluate(self);
        let held = std::mem::replace(&mut self.rows, outer);
        if result.is_ok() {
            self.nested_rows = self.nested_rows.max(held);
        }
        result
    }

    /// Runs `evaluate` as a nested evaluation ([`Budget::nested`]) and gives
    /// its result with the work it charged and the most bytes it held, so
    /// that [`Budget::replay`] charges them again. The bindings also stand in
    /// the log of an enclosing call. The nested evaluation holds its bytes
    /// while it runs: those it still holds at its end are freed, and a replay
    /// holds the most it held for a moment.
    fn logged<T>(&mut self, evaluate: impl FnOnce(&mut Self) -> Result<T, ReachedBound>) -> Result<(T, Charges), ReachedBound> {
        // The bytes of rows counted before belong to the charges around, and those counted inside to the log.
        self.flush_bytes()?;
        let outer = self.log.replace(Charges::default());
        let base = self.held;
        let outer_high = std::mem::replace(&mut self.high, base);
        let result = self.nested(evaluate);
        let result = match result {
            Ok(value) => self.flush_bytes().map(|()| value),
            Err(bound) => Err(bound),
        };
        let peak = self.high.saturating_sub(base);
        self.high = self.high.max(outer_high);
        if result.is_ok() {
            self.credit_bytes(self.held.saturating_sub(base));
        }
        let mut inner = std::mem::replace(&mut self.log, outer).expect("the log this call began");
        inner.bytes = peak;
        if let Some(outer) = &mut self.log {
            *outer = outer.saturating_add(inner);
        }
        Ok((result?, inner))
    }

    /// Runs `evaluate` as a nested evaluation ([`Budget::nested`]) and gives
    /// its result with what it did to the counts of this budget: the bindings
    /// it charged and the most rows that a nested evaluation in it held.
    /// [`Budget::replay_nested`] does the same to a budget without running
    /// the evaluation.
    fn counted<T>(&mut self, evaluate: impl FnOnce(&mut Self) -> Result<T, ReachedBound>) -> Result<(T, Counted), ReachedBound> {
        let outside = std::mem::take(&mut self.nested_rows);
        let result = self.logged(evaluate);
        let inside = std::mem::replace(&mut self.nested_rows, outside);
        self.nested_rows = outside.max(inside);
        let (value, bindings) = result?;
        Ok((value, Counted { bindings, rows: inside }))
    }

    /// Does to the counts of this budget what `counted` says an evaluation
    /// did to them, as [`Budget::counted`] gives it.
    fn replay_nested(&mut self, counted: Counted) -> Result<(), ReachedBound> {
        self.nested_rows = self.nested_rows.max(counted.rows);
        self.replay(counted.bindings)
    }

    /// Charges the `charges` of an evaluation that [`Budget::logged`] gave.
    /// A memo hit charges the bindings of the evaluation it stands for, and
    /// the units that only the request counts, and no row, since a nested
    /// evaluation adds none ([`Budget::nested`]) and the memo keeps only an
    /// evaluation that gave a value, so the counts of a search, and the place
    /// where it stops at a cap, are those of the search with no memo.
    fn replay(&mut self, charges: Charges) -> Result<(), ReachedBound> {
        self.charge_content(charges.bindings)?;
        self.charge_request(charges.request)?;
        self.charge_bytes_transient(charges.bytes)
    }

    /// Whether [`Budget::replay`] of `charges` stays within the caps that its
    /// charges are counted against. A memo that outlives the evaluation
    /// computes the search again where they do not, so that the search stops
    /// at the charge that it stops at with no memo.
    fn can_replay(&self, charges: Charges) -> bool {
        let request = &self.limits.request;
        self.bindings.saturating_add(charges.bindings) <= self.session.caps.bindings
            && request.count().saturating_add(charges.bindings).saturating_add(charges.request) <= request.cap()
            && request.fits_bytes(charges.bytes)
            && self.limits.table_work.as_ref().is_none_or(|work| work.fits(charges.bindings) && work.fits_bytes(charges.bytes))
    }

    /// Records the budget's counts in its session, as
    /// [`TaskSession::record_counts`] gives.
    pub fn record(&self) {
        super::tally_gauges(self.bindings, self.rows.max(self.nested_rows));
        self.session.record_counts(Counts { bindings: self.bindings, rows: self.rows.max(self.nested_rows) });
    }
}

impl Drop for Budget<'_> {
    /// Notes the counts of the evaluation in the request's gauges: the rows
    /// that a batch had not yet shown, and the most that a nested evaluation
    /// held.
    fn drop(&mut self) {
        // The bytes of the rows not yet charged belong to this evaluation; a stop at a budget shows at the next charge.
        let _ = self.flush_bytes();
        let gauges = self.limits.request.gauges();
        let caps = self.session.caps;
        gauges.note(Gauge::Bindings, self.bindings, caps.bindings);
        gauges.note(Gauge::Rows, self.rows.max(self.nested_rows), caps.rows);
        super::tally_gauges(self.bindings, self.rows.max(self.nested_rows));
    }
}

/// What a nested evaluation did to the counts of the budget it ran in: the
/// bindings it charged, and the most rows that a nested evaluation in it held.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
struct Counted {
    bindings: Charges,
    rows: u64,
}

/// One operation's materialization policy. It borrows the current limits;
/// retained buffers own only their stable session byte reservations.
#[derive(Clone, Copy)]
pub struct Materializer<'a> {
    session: &'a TaskSession,
    limits: &'a Limits,
}

impl<'a> Materializer<'a> {
    /// Uses the caller's current operation, without starting another timer.
    pub fn new(session:&'a TaskSession, limits:&'a Limits)->Self { Self {session,limits} }

    /// The session whose limits this operation runs under.
    pub fn session(&self) -> &'a TaskSession {
        self.session
    }

    /// The limits this operation runs under.
    pub fn limits(&self) -> &'a Limits {
        self.limits
    }

    /// Conservative per-row owned storage, including hash/vector headers and
    /// allocator slack. Callers supply their actual scalar payload layout.
    /// The row's slot (a boxed slice or vector header, or a hash bucket at
    /// its load factor) takes at most 32 bytes, and each heap allocation adds
    /// at most 32 bytes of header and size-class slack.
    pub fn row_bytes(payload:usize, allocations:usize)->usize {
        payload.saturating_add(32).saturating_add(allocations.saturating_mul(32))
    }

    /// Admits all rows and returns the owner of their retained bytes. The
    /// request and the assignment hold those bytes until the owner drops.
    pub fn admit(&self,rows:&Relation,bytes_per_row:usize)->Result<Arc<crate::session::SessionAllocation>,ReachedBound> {
        Budget::new(self.limits,self.session).materialize(rows,bytes_per_row).map(Arc::new)
    }

    /// Admits `rows` new held rows of `bytes` in all that no walk of a
    /// product builds, such as rows kept per part of a relation, and returns
    /// the owner of their retained bytes.
    pub fn hold(&self,rows:u64,bytes:usize)->Result<Arc<crate::session::SessionAllocation>,ReachedBound> {
        let mut budget=Budget::new(self.limits,self.session);
        budget.charge_work(0)?;
        budget.charge_request(rows)?;
        budget.charge_rows(rows)?;
        budget.own(bytes.saturating_add(128)).map(Arc::new)
    }

    /// Admits a genuine copy of an existing buffer before cloning it.
    pub fn copy(&self,bytes:usize)->Result<Arc<crate::session::SessionAllocation>,ReachedBound> {
        let mut budget=Budget::new(self.limits,self.session);
        budget.charge_work(0)?;
        budget.own(bytes).map(Arc::new)
    }

    /// A zero-work check under this operation's existing request work and caps.
    pub fn check(&self)->Result<(),ReachedBound> {Budget::new(self.limits,self.session).charge_work(0)}

    /// Walks the admitted rows with periodic checks under these same limits.
    pub fn walk(&self,rows:&Relation,visit:&mut dyn FnMut(&[TermId]))->Result<(),ReachedBound> {
        Budget::new(self.limits,self.session).walk_rows(rows,visit)
    }
}

/// Counts the walk of the product of `relation`, read at `form` in
/// `evaluation`, in a budget of its own under the evaluation's limits, as
/// [`Budget::charge_product`] gives, and gives the stop where the count
/// passes a bound.
///
/// The walk also holds the bytes of the rows it makes, as [`row_bytes`] gives
/// them, while it runs: a caller of this function holds the rows of the product
/// it walks.
pub fn charge_walk(evaluation: &Evaluation<'_>, relation: &Relation, form: &NodePath) -> Result<(), Stop> {
    let mut budget = Budget::new(evaluation.limits, evaluation.session);
    budget
        .charge_product(relation)
        .and_then(|()| budget.charge_bytes_transient(relation.len().saturating_mul(row_bytes(usize::from(relation.arity())))))
        .map_err(|bound| Stop { bound, form: form.clone() })
}

/// The bindings one search has tried and not yet charged to its budget.
/// Each search holds its own, so no count passes from one join or
/// construction to the next.
#[derive(Debug, Default)]
pub struct Batch {
    pending: u64,
}

impl Batch {
    /// Counts `bindings` more tried, and charges `budget` with the whole
    /// count once it reaches a batch.
    pub fn count(&mut self, budget: &mut Budget<'_>, bindings: u64) -> Result<(), ReachedBound> {
        self.pending += bindings;
        if self.pending >= BATCH {
            budget.charge_work(std::mem::take(&mut self.pending))?;
        }
        Ok(())
    }

    /// Charges `budget` with the count not yet charged, at the end of the
    /// search.
    pub fn finish(&mut self, budget: &mut Budget<'_>) -> Result<(), ReachedBound> {
        budget.charge_work(std::mem::take(&mut self.pending))
    }
}

/// What each node of a clause reads, by the node's index in
/// [`ClauseIr::nodes`].
#[derive(Clone, Debug)]
pub struct JoinInputs(pub Box<[NodeInput]>);

/// What one node of a clause reads.
#[derive(Clone, Debug)]
pub enum NodeInput {
    /// No relation with rows: a comparison's, or an algebra relation's atom.
    Unread,
    /// The relation of an atom.
    Relation(Arc<Relation>),
    /// The inputs of the node's own clauses: a filter's body, or a union's
    /// branches, in the node's order.
    Clauses(Box<[JoinInputs]>),
}

/// The relation of `clause`: each binding of its variables that every node
/// passes, held as its parts, one per connected set of its variables, by
/// generic join in `order`.
pub fn join(
    clause: &ClauseIr,
    order: &VariableOrder,
    inputs: &JoinInputs,
    registry: &crate::registry::Registry,
    budget: &mut Budget<'_>,
) -> Result<Relation, ReachedBound> {
    join_at(clause, order, inputs, registry, &[], budget)
}

/// The relation of `clause` as [`join`] gives it, at the values `bound`
/// gives some of its variables before the search: the join of the rest of
/// `order`.
///
/// Once every variable left in the order is a variable that no column
/// holds, the first binding that passes ends the search over them, and the
/// search visits their values in their order as terms. At a variable of
/// type Ident, whose order as terms is the order of interning, the search
/// tries every value, so the work it counts does not depend on that order.
pub fn join_at(
    clause: &ClauseIr,
    order: &VariableOrder,
    inputs: &JoinInputs,
    registry: &crate::registry::Registry,
    bound: &[(Variable, TermId)],
    budget: &mut Budget<'_>,
) -> Result<Relation, ReachedBound> {
    join_in(&SearchMemo::default(), clause, order, inputs, registry, bound, budget)
}

/// The relation of `clause` as [`join_at`] gives it, in the evaluation whose
/// memo is `memo`.
pub fn join_in(
    memo: &SearchMemo,
    clause: &ClauseIr,
    order: &VariableOrder,
    inputs: &JoinInputs,
    registry: &crate::registry::Registry,
    bound: &[(Variable, TermId)],
    budget: &mut Budget<'_>,
) -> Result<Relation, ReachedBound> {
    join_ordered(memo, clause, &|_| (order.clone(), (0..clause.nodes.len()).collect()), inputs, registry, bound, budget)
}

/// The relation of `clause` as [`join_in`] gives it, in the order and over
/// the nodes that `order_at` gives at the variables `bound` binds, which is
/// called when the memo holds no plan for those variables. A column that no
/// node joined holds stands as a part of its own, whose values are the
/// column's type's constants where the type has them, and otherwise the zero
/// term.
fn join_ordered(
    memo: &SearchMemo,
    clause: &ClauseIr,
    order_at: &dyn Fn(&[Variable]) -> (VariableOrder, Vec<usize>),
    inputs: &JoinInputs,
    registry: &crate::registry::Registry,
    bound: &[(Variable, TermId)],
    budget: &mut Budget<'_>,
) -> Result<Relation, ReachedBound> {
    if bound.is_empty() {
        let (order,nodes)=order_at(&[]);
        if clause.columns.iter().all(|v|nodes.iter().any(|&node|node_variables(&clause.nodes[node]).contains(v))) {
            let columns:Vec<ColumnIndex>=(0..clause.columns.len()).map(|at|ColumnIndex(at as u16)).collect();
            if frame_split(clause,&nodes,&columns).is_some() {
                return search_part(clause,&nodes,order.0.to_vec(),inputs,registry,&columns,budget);
            }
        }
    }
    let plan = memo.plan(clause, order_at, inputs, bound, budget)?;
    let mut found = Vec::new();
    for part in &plan.parts {
        let rows = Search::new(clause, &part.plan, inputs, registry, memo, bound).run(&part.projected, budget)?;
        found.push((part.written, RelationPart { columns: part.columns.clone().into(), rows }));
    }
    // The parts are searched in the clause's canonical order. The relation lists
    // them in the order of the clause as compiled, which its readers follow.
    found.sort_by_key(|(written, _)| *written);
    let mut found: Vec<RelationPart> = found.into_iter().map(|(_, part)| part).collect();
    found.extend(unheld_parts(clause, &plan, registry));
    Ok(product(clause, found))
}

/// A part of one column for each column of `clause` that no part of `plan`
/// holds, as [`join_ordered`] gives.
fn unheld_parts(clause: &ClauseIr, plan: &ClausePlan, registry: &Registry) -> Vec<RelationPart> {
    let held: Vec<ColumnIndex> = plan.parts.iter().flat_map(|part| part.columns.iter().copied()).collect();
    let unheld = (0..clause.columns.len()).map(|c| ColumnIndex(c as u16)).filter(|column| !held.contains(column));
    unheld
        .map(|column| {
            let ty = &clause.variables[usize::from(clause.columns[usize::from(column.0)].0)].ty;
            let mut rows = RowSet::empty(1);
            for value in domain(registry, ty).unwrap_or_else(|| vec![TermId::from_encoding(0)]) {
                rows.insert([value].into());
            }
            RelationPart { columns: [column].into(), rows }
        })
        .collect()
}

/// The relation of `clause` whose parts are `parts`: their product. A part
/// that holds no column is left out where it holds a row, and where it holds
/// none it makes the relation empty.
pub fn product(clause: &ClauseIr, parts: Vec<RelationPart>) -> Relation {
    let parts: Vec<RelationPart> = parts.into_iter().filter(|part| !part.columns.is_empty() || part.rows.is_empty()).collect();
    Relation::from_parts(clause.columns.len() as u16, parts.into())
}

/// The rows of `columns`, columns of `clause`, over each binding of the
/// variables of `order` that passes every node of `nodes` and agrees with a
/// row of each relation of `tries`, by generic join in `order`, at the
/// values `bound` gives some of the clause's variables. A relation of
/// `tries` is read as an atom over its arguments. Where `clause` is one
/// union and `tries` and `bound` are empty, the rows are those of
/// `union_rows`.
#[allow(clippy::too_many_arguments)]
pub fn search(
    clause: &ClauseIr,
    nodes: &[usize],
    tries: &[(Arc<Relation>, Arguments)],
    order: Vec<Variable>,
    bound: &[(Variable, TermId)],
    inputs: &JoinInputs,
    registry: &Registry,
    columns: &[ColumnIndex],
    budget: &mut Budget<'_>,
) -> Result<RowSet, ReachedBound> {
    let projected: Vec<Variable> = columns.iter().map(|c| clause.columns[usize::from(c.0)]).collect();
    if tries.is_empty() && bound.is_empty() {
        if let Some(rows) = union_rows(clause, nodes, &projected, inputs, registry, budget) {
            return rows;
        }
    }
    let variables: Vec<Variable> = bound.iter().map(|&(variable, _)| variable).collect();
    let plan = Plan::new(clause, nodes, tries, order, &variables, inputs, budget)?;
    Search::new(clause, &plan, inputs, registry, &SearchMemo::default(), bound).run(&projected, budget)
}

/// The relation of `columns`, columns of `clause`, over the connected nodes
/// `nodes` in `order`, as [`search`] gives its rows, held in two parts where a
/// variable splits them. Such a variable is a Position column of `clause`
/// that each node holding it in one set of the nodes, the borrower, holds
/// only at columns that its algebra relation reads through the Position's
/// frame alone ([`crate::algebra::boxes::frame_columns`]), and that no other
/// node links to the rest, the lender. Where the lender's rows give the
/// variable values of one frame, the borrower's rows are the same at each of
/// them: the borrower is searched once, at the first, and the relation is the
/// product of the lender's rows and the borrower's.
///
/// The row cap counts the rows that each part holds, and no row of their
/// product is built. Where the values have several frames, or the lender's rows
/// alone pass the row cap, the nodes are searched at once.
#[allow(clippy::too_many_arguments)]
pub fn search_part(
    clause: &ClauseIr,
    nodes: &[usize],
    order: Vec<Variable>,
    inputs: &JoinInputs,
    registry: &Registry,
    columns: &[ColumnIndex],
    budget: &mut Budget<'_>,
) -> Result<Relation, ReachedBound> {
    if let Some(split) = frame_split(clause, nodes, columns) {
        let of = |part: &Part| -> (Vec<Variable>, Vec<ColumnIndex>, Vec<ColumnIndex>) {
            let order = order.iter().copied().filter(|v| part.variables.contains(v)).collect();
            let (held, local): (Vec<ColumnIndex>, Vec<ColumnIndex>) = columns
                .iter()
                .zip(0u16..)
                .filter(|(column, _)| part.variables.contains(&clause.columns[usize::from(column.0)]))
                .map(|(&column, at)| (column, ColumnIndex(at)))
                .unzip();
            (order, held, local)
        };
        let (lender_order, lender_columns, lender_local) = of(&split.lender);
        let (borrower_order, borrower_columns, borrower_local) = of(&split.borrower);
        let lent = budget.nested(|budget| search(clause, &split.lender.nodes, &[], lender_order, &[], inputs, registry, &lender_columns, budget));
        let lent = match lent {
            Ok(lent) => Some(lent),
            Err(ReachedBound::Rows { .. }) => None,
            Err(bound) => return Err(bound),
        };
        let at = lender_columns.iter().position(|column| clause.columns[usize::from(column.0)] == split.variable).expect("the lender holds the variable's column");
        let first = lent.as_ref().and_then(|lent| lent.rows().next().map(|row| row[at]));
        let one_frame = lent.as_ref().is_some_and(|lent| first.is_none_or(|first| lent.rows().all(|row| crate::algebra::boxes::frame_of(row[at]) == crate::algebra::boxes::frame_of(first))));
        if let (true, Some(lent)) = (one_frame, lent) {
            let borrowed = match first {
                Some(first) => search(clause, &split.borrower.nodes, &[], borrower_order, &[(split.variable, first)], inputs, registry, &borrower_columns, budget)?,
                None => RowSet::empty(borrower_columns.len() as u16),
            };
            let parts = [RelationPart { columns: lender_local.into(), rows: lent }, RelationPart { columns: borrower_local.into(), rows: borrowed }];
            return Ok(product_of(columns.len() as u16, parts.into()));
        }
    }
    search(clause, nodes, &[], order, &[], inputs, registry, columns, budget).map(one_part)
}

/// The relation of `arity` columns whose parts are `parts`, as [`product`]
/// gives it.
fn product_of(arity: u16, parts: Vec<RelationPart>) -> Relation {
    let parts: Vec<RelationPart> = parts.into_iter().filter(|part| !part.columns.is_empty() || part.rows.is_empty()).collect();
    Relation::from_parts(arity, parts.into())
}

/// The two sets of the connected nodes `nodes` of `clause` that a variable
/// splits, as [`search_part`] gives them, where one does: the first such
/// variable among the columns `columns`.
struct FrameSplit {
    variable: Variable,
    lender: Part,
    borrower: Part,
}

fn frame_split(clause: &ClauseIr, nodes: &[usize], columns: &[ColumnIndex]) -> Option<FrameSplit> {
    for column in columns {
        let variable = clause.columns[usize::from(column.0)];
        if clause.variables[usize::from(variable.0)].ty != ValueType::Position {
            continue;
        }
        let through_frame = |node: usize| match &clause.nodes[node] {
            IrNode::Lib(atom) => {
                let frame = crate::algebra::boxes::frame_columns(&atom.relation);
                let mut holds = atom.arguments.0.iter().filter(|(_, argument)| *argument == Argument::Variable(variable)).peekable();
                holds.peek().is_some() && holds.all(|(column, _)| frame.contains(&column.0))
            }
            _ => false,
        };
        if !nodes.iter().any(|&node| through_frame(node)) {
            continue;
        }
        let held = |node: usize| {
            let mut held = node_variables(&clause.nodes[node]);
            if through_frame(node) {
                held.retain(|v| *v != variable);
            }
            held
        };
        let mut split = parts_holding(nodes, &held);
        if split.len() != 2 {
            continue;
        }
        let at = split.iter().position(|part| part.variables.contains(&variable))?;
        let lender = split.swap_remove(at);
        let borrower = split.pop()?;
        if borrower.nodes.iter().any(|&node| through_frame(node)) {
            return Some(FrameSplit { variable, lender, borrower });
        }
    }
    None
}

/// The connected sets of `nodes`, two nodes connected where `held` gives
/// them a variable in common, in the order of their first nodes.
fn parts_holding(nodes: &[usize], held: &dyn Fn(usize) -> Vec<Variable>) -> Vec<Part> {
    let mut parts: Vec<Part> = Vec::new();
    for &node in nodes {
        let variables = held(node);
        let (linked, rest): (Vec<Part>, Vec<Part>) = std::mem::take(&mut parts).into_iter().partition(|part| variables.iter().any(|v| part.variables.contains(v)));
        parts = rest;
        let mut joined = Part { variables: Vec::new(), nodes: Vec::new() };
        for part in linked {
            joined.nodes.extend(part.nodes);
            joined.variables.extend(part.variables);
        }
        joined.nodes.push(node);
        for v in variables {
            if !joined.variables.contains(&v) {
                joined.variables.push(v);
            }
        }
        parts.push(joined);
    }
    parts.sort_by_key(|part| part.nodes.iter().copied().min());
    for part in &mut parts {
        part.nodes.sort_unstable();
    }
    parts
}

/// The rows of `projected`, variables of `clause`, where the one node of
/// `clause` is a union and `nodes` is that node: the rows of its branches,
/// each branch searched once at no bound value, with all its nodes, over the
/// columns of `projected` alone, as an evaluation nested in the union
/// ([`Budget::nested`]), and projected onto `projected`. A label local to a
/// branch is searched over and held in no row. The union charges one row for
/// each distinct row it holds. `None` where `clause` is anything else, or
/// where a branch leaves out a node at no bound value, or holds no variable
/// of `projected` among those its order binds; the generic join over `clause`
/// gives the rows then.
///
/// A union that is a clause's whole body is the union of its branches'
/// relations (`docs/arclog/arclog.md#disjunction`), so no branch is joined again
/// at the values bound so far, as [`Search::union_values`] joins a union
/// beside other conjuncts.
///
/// The branches are searched, and the rows they give are charged, in the
/// canonical order of the branches ([`super::ir::Union::canonical`]), so that
/// the work and the place of a stop follow the union's content. The rows of
/// the result stand in the order of the branches as written.
fn union_rows(
    clause: &ClauseIr,
    nodes: &[usize],
    projected: &[Variable],
    inputs: &JoinInputs,
    registry: &Registry,
    budget: &mut Budget<'_>,
) -> Option<Result<RowSet, ReachedBound>> {
    let ([IrNode::Or(union)], [0], Some(NodeInput::Clauses(bodies))) = (&*clause.nodes, nodes, inputs.0.first()) else { return None };
    let searches: Vec<(Vec<Variable>, Vec<ColumnIndex>)> = union
        .branches
        .iter()
        .zip(bodies.iter())
        .map(|(branch, inputs)| {
            let order = variable_order(branch, &sizes(branch, inputs), &[]).0.to_vec();
            let columns: Option<Vec<ColumnIndex>> = projected
                .iter()
                .map(|variable| {
                    let place = branch.columns.iter().position(|column| column == variable)?;
                    order.contains(variable).then_some(ColumnIndex(place as u16))
                })
                .collect();
            columns.filter(|_| kept_nodes(branch, &[]).len() == branch.nodes.len()).map(|columns| (order, columns))
        })
        .collect::<Option<_>>()?;
    let mut searches: Vec<Option<(Vec<Variable>, Vec<ColumnIndex>)>> = searches.into_iter().map(Some).collect();
    let mut held: Vec<Option<RowSet>> = searches.iter().map(|_| None).collect();
    let mut rows = RowSet::empty(projected.len() as u16);
    for index in union.in_canonical_order() {
        let (branch, inputs) = (&union.branches[index], &bodies[index]);
        let (order, columns) = searches[index].take().expect("a search of each branch");
        let nodes: Vec<usize> = (0..branch.nodes.len()).collect();
        let found = branches::rows(budget, branch, inputs, &columns, |budget| search(branch, &nodes, &[], order, &[], inputs, registry, &columns, budget));
        let found = match found {
            Ok(found) => found,
            Err(bound) => return Some(Err(bound)),
        };
        for row in found.rows() {
            if rows.insert_slice(row) {
                if let Err(bound) = budget.charge_rows_of(1, projected.len()) {
                    return Some(Err(bound));
                }
            }
        }
        held[index] = Some(found);
    }
    if union.is_written_order() {
        return Some(Ok(rows));
    }
    let mut listed = RowSet::empty(projected.len() as u16);
    for found in held.iter().flatten() {
        for row in found.rows() {
            listed.insert_slice(row);
        }
    }
    Some(Ok(listed))
}

/// The order and the nodes that the join of `branch`, a branch of a union
/// whose inputs are `inputs`, takes at the variables bound before it: the
/// variable order of the branch, and the nodes that [`kept_nodes`] leaves.
fn branch_order<'a>(branch: &'a ClauseIr, inputs: &'a JoinInputs) -> impl Fn(&[Variable]) -> (VariableOrder, Vec<usize>) + 'a {
    move |bound| (variable_order(branch, &sizes(branch, inputs), bound), kept_nodes(branch, bound))
}

/// Calls `visit` on each row of `relation`, the product of its parts, in an
/// order of encodings and no order of the content.
pub fn each_row(relation: &Relation, visit: &mut dyn FnMut(&[TermId])) {
    let result: Result<(), std::convert::Infallible> = try_each_row(relation, &mut |row| {
        visit(row);
        Ok(())
    });
    match result { Ok(()) => (), Err(never) => match never {} }
}

/// Visits the same product and order as [`each_row`], ending immediately at
/// the visitor's error. No later row is constructed after that error.
pub fn try_each_row<E>(relation: &Relation, visit: &mut dyn FnMut(&[TermId]) -> Result<(), E>) -> Result<(), E> {
    fn product<E>(parts: &[RelationPart], row: &mut [TermId], visit: &mut dyn FnMut(&[TermId]) -> Result<(), E>) -> Result<(), E> {
        let Some((part, rest)) = parts.split_first() else { return visit(row); };
        for part_row in part.rows.rows() {
            for (column, &value) in part.columns.iter().zip(part_row) {
                row[usize::from(column.0)] = value;
            }
            product(rest, row, visit)?;
        }
        Ok(())
    }
    let mut row = vec![TermId::from_encoding(0); usize::from(relation.arity())];
    product(relation.parts(), &mut row, visit)
}

/// The relation of one part that holds `rows`.
pub fn one_part(rows: RowSet) -> Relation {
    let arity = rows.arity();
    let columns = (0..arity).map(ColumnIndex).collect();
    Relation::from_parts(arity, Box::new([RelationPart { columns, rows }]))
}

/// The union of `relations`, of one arity: the one relation where there is
/// one, and otherwise their rows in one part.
pub fn union(mut relations: Vec<Arc<Relation>>) -> Arc<Relation> {
    if relations.len() == 1 {
        return relations.pop().expect("one relation");
    }
    let arity = relations.first().expect("a relation to unite").arity();
    let mut rows = RowSet::empty(arity);
    for relation in &relations {
        each_row(relation, &mut |row| {
            rows.insert_slice(row);
        });
    }
    Arc::new(one_part(rows))
}

/// The rows that the join of `nodes` reads: the rows that the relations of
/// the nodes hold, and of the nodes that the filters and unions among them
/// nest, in `inputs`. A relation counts the rows its parts hold
/// ([`Relation::held_rows`]), each time a node reads it. The size is a function
/// of the relations' content, and so of the clause, whatever order its nodes
/// are written in.
pub fn read_size(nodes: &[usize], inputs: &JoinInputs) -> u64 {
    fn of(input: &NodeInput) -> u64 {
        match input {
            NodeInput::Unread => 0,
            NodeInput::Relation(relation) => relation.held_rows(),
            NodeInput::Clauses(bodies) => bodies.iter().flat_map(|body| body.0.iter()).map(of).fold(0, u64::saturating_add),
        }
    }
    nodes.iter().map(|&node| of(&inputs.0[node])).fold(0, u64::saturating_add)
}

/// The row and distinct column counts of `inputs`, for [`variable_order`].
/// A unary index reads only the part that holds its column. The relation
/// caches it and includes its retained storage in the index byte ledger.
pub fn sizes(clause: &ClauseIr, inputs: &JoinInputs) -> RelationSizes {
    RelationSizes(clause.nodes.iter().zip(inputs.0.iter()).map(|(node, input)| match input {
        NodeInput::Relation(relation) => {
            let mut distinct = vec![relation.len(); relation.arity() as usize];
            if let IrNode::Atom(atom) = node {
                for (column, _) in &atom.arguments.0 {
                    // No budget stands here, so the rows of a build wait for the next charge of the request.
                    // They count at each use, whether or not the relation held the index.
                    let (index, _) = relation.index_built(&ColumnOrder(Box::new([*column])));
                    super::RequestWork::note_unbilled(index.walked());
                    distinct[column.0 as usize] = index.root().len() as u64;
                }
            }
            NodeSize::Columns {rows: relation.len(), distinct: distinct.into()}
        }
        NodeInput::Unread => NodeSize::Unread,
        NodeInput::Clauses(bodies) => NodeSize::Clauses(match node {
            IrNode::Or(union) => union.branches.iter().zip(bodies.iter()).map(|(branch, inputs)| sizes(branch, inputs)).collect(),
            IrNode::Not(filter) | IrNode::Counterexample(filter) => Box::new([sizes(&filter.body, &bodies[0])]),
            _ => unreachable!("nested clause inputs"),
        }),
    }).collect())
}

/// A part of a clause's body: a connected set of its nodes, two nodes
/// connected where they share a variable or stand in one group, as
/// [`parts`] gives the groups, with the variables they hold. A node with no
/// variable and no other node in its group is a part of its own.
#[derive(Clone, Debug)]
pub struct Part {
    pub variables: Vec<Variable>,
    pub nodes: Vec<usize>,
}

impl Part {
    /// The columns of `clause` that the part holds, in the clause's order.
    pub fn columns(&self, clause: &ClauseIr) -> Vec<ColumnIndex> {
        (0..clause.columns.len()).filter(|&i| self.variables.contains(&clause.columns[i])).map(|i| ColumnIndex(i as u16)).collect()
    }

    /// The variables of `order` that the part holds and `bound` leaves
    /// unbound, in their order.
    pub fn order(&self, order: &VariableOrder, bound: &[Variable]) -> Vec<Variable> {
        order.0.iter().copied().filter(|v| self.variables.contains(v) && !bound.contains(v)).collect()
    }

    /// Whether each variable that a node of `nodes` holds and the part
    /// holds too is one of the part's columns in `clause`, so that the
    /// part's rows link it to those nodes.
    pub fn links(&self, clause: &ClauseIr, nodes: &[usize]) -> bool {
        nodes
            .iter()
            .flat_map(|&node| node_variables(&clause.nodes[node]))
            .filter(|v| self.variables.contains(v))
            .all(|v| clause.columns.contains(&v))
    }
}

/// The variables a node joins in its clause: those it binds, the outer
/// variables of a filter, and the columns of a union's branches.
pub fn node_variables(node: &IrNode) -> Vec<Variable> {
    match node {
        IrNode::Not(filter) | IrNode::Counterexample(filter) => filter.outer.to_vec(),
        IrNode::Or(union) => union.branches.iter().flat_map(|branch| branch.columns.iter().copied()).collect(),
        _ => bound_variables(node),
    }
}

/// The parts of the nodes `nodes` of `clause`, the nodes to which `group`
/// gives one group standing in one part, in the order of their first nodes.
pub fn parts<G: Eq + Copy>(clause: &ClauseIr, nodes: &[usize], group: &dyn Fn(usize) -> G) -> Vec<Part> {
    let mut parent: Vec<usize> = (0..nodes.len()).collect();
    fn root(parent: &mut [usize], at: usize) -> usize {
        let mut r = at;
        while parent[r] != r {
            r = parent[r];
        }
        parent[at] = r;
        r
    }
    let variables: Vec<Vec<Variable>> = nodes.iter().map(|&node| node_variables(&clause.nodes[node])).collect();
    let mut holder: Vec<Option<usize>> = vec![None; clause.variables.len()];
    for (at, held) in variables.iter().enumerate() {
        let mut joined: Vec<usize> = held.iter().filter_map(|v| holder[usize::from(v.0)].replace(at)).collect();
        joined.extend((0..at).filter(|&other| group(nodes[other]) == group(nodes[at])).take(1));
        for other in joined {
            let (a, b) = (root(&mut parent, at), root(&mut parent, other));
            parent[a.max(b)] = a.min(b);
        }
    }
    let mut by_root: std::collections::BTreeMap<usize, Part> = std::collections::BTreeMap::new();
    for (at, held) in variables.iter().enumerate() {
        let r = root(&mut parent, at);
        let part = by_root.entry(r).or_insert_with(|| Part { variables: Vec::new(), nodes: Vec::new() });
        part.nodes.push(nodes[at]);
        for v in held {
            if !part.variables.contains(v) {
                part.variables.push(*v);
            }
        }
    }
    by_root.into_values().collect()
}

/// An atom's trie in the join's order: its relation's index over the
/// atom's columns, a term's column first, then the column of each variable
/// bound before the search, then each other variable's in the order it is
/// bound.
struct AtomTrie {
    index: Arc<Index>,
    levels: Vec<Argument>,
    /// Whether the relation holds no row, which its trie shows at a level
    /// only, and so shows for an atom that reads no column at none.
    empty: bool,
}

/// Intersects sorted index runs by seeking past missing values. Values
/// excluded by another positive atom never become candidate bindings. This
/// avoids scanning and binding an entire phase class before another class
/// rejects most of its cells. The work of emitted bindings is charged by
/// the search; long runs still check the operation's other bounds here.
fn intersect_values(nodes: &[IndexNode<'_>], budget: &mut Budget<'_>) -> Result<Vec<TermId>, ReachedBound> {
    intersect_runs(nodes.iter().map(|node| node.values()).collect(), budget)
}

/// The count of values of `run`, a run in encoding order, whose encodings are
/// below `target`: where `run.partition_point` puts the first value at or
/// above it. The search doubles its step from the start of the run, so it
/// takes a few reads where the run's next value is near, as it is where runs
/// of many values are intersected.
fn below(run: &[TermId], target: u32) -> usize {
    match run.first() {
        None => return 0,
        Some(first) if first.encoding() >= target => return 0,
        Some(_) => {}
    }
    // The value at `low` is below `target`, and the value at `high`, if the run has one, is not.
    let (mut low, mut high) = (0, 1);
    while high < run.len() && run[high].encoding() < target {
        low = high;
        high *= 2;
    }
    low + 1 + run[low + 1..high.min(run.len())].partition_point(|value| value.encoding() < target)
}

fn intersect_runs(mut runs: Vec<&[TermId]>, budget: &mut Budget<'_>) -> Result<Vec<TermId>, ReachedBound> {
    let mut found = Vec::new();
    let Some(mut candidate) = runs.first().and_then(|run| run.first()).copied() else { return Ok(found) };
    let mut steps = 0usize;
    'seek: loop {
        if steps % BATCH as usize == 0 { budget.charge_work(0)?; }
        steps += 1;
        for run in &mut runs {
            *run = &run[below(run, candidate.encoding())..];
            let Some(&value) = run.first() else { return Ok(found) };
            if value != candidate {
                candidate = value;
                continue 'seek;
            }
        }
        found.push(candidate);
        runs[0] = &runs[0][1..];
        let Some(&next) = runs[0].first() else { return Ok(found) };
        candidate = next;
    }
}

/// What the search of one connected set of a clause's nodes builds that
/// depends on no bound value, for one set of variables bound before the
/// search.
struct Plan {
    order: Vec<Variable>,
    atoms: Vec<AtomTrie>,
    /// The nodes checked once the variable at each rank is bound, and, last,
    /// the nodes with no variable.
    checks: Vec<Vec<usize>>,
    /// The lib atoms that hold each variable, by the variable's index.
    libs: Vec<Vec<usize>>,
    /// The variable order of each filter's body, by its node.
    filter_orders: StableHashMap<usize, VariableOrder>,
    /// The nodes of the unions.
    unions: Vec<usize>,
    /// The rank from which no variable left in the order is projected,
    /// where the early stop of [`join_at`] begins.
    stop_from: usize,
}

impl Plan {
    /// The plan of the search of `nodes` and `tries` in `order`, with `bound`
    /// bound before it. The build of each atom's trie is effort in `budget`,
    /// charged before the trie is built.
    fn new(
        clause: &ClauseIr,
        nodes: &[usize],
        tries: &[(Arc<Relation>, Arguments)],
        order: Vec<Variable>,
        bound: &[Variable],
        inputs: &JoinInputs,
        budget: &mut Budget<'_>,
    ) -> Result<Self, ReachedBound> {
        let atoms: Vec<&Arguments> = tries.iter().map(|(_, arguments)| arguments).collect();
        let order = values_first(clause, nodes, &atoms, order, bound);
        let mut rank = vec![usize::MAX; clause.variables.len()];
        for (r, v) in order.iter().enumerate() {
            rank[usize::from(v.0)] = r;
        }
        let trie = |relation: &Relation, arguments: &Arguments, budget: &mut Budget<'_>| -> Result<AtomTrie,ReachedBound> {
            let mut columns: Vec<(ColumnIndex, Argument)> = arguments.0.iter().copied().collect();
            columns.sort_by_key(|(column, argument)| match argument {
                Argument::Variable(v) if !bound.contains(v) => (1 + rank[usize::from(v.0)], column.0 as usize),
                _ => (0, column.0 as usize),
            });
            let order=ColumnOrder(columns.iter().map(|(c, _)| *c).collect());
            let work = relation.index_work(&order);
            budget.charge_work(work)?;
            budget.charge_index_build(relation, &order, work)?;
            let (index, _) = relation.index_built(&order);
            // A build of one part walks that part's rows, which no count of bindings holds; a build of several parts was charged as `work` above.
            // Both are effort: which indexes a search builds depends on its variable order, and no result depends on it.
            if work == 0 {
                budget.charge_work(index.walked())?;
                // The bytes of a build that reads the part by its distinct projections are known when it ends.
                if index_rows(relation, &order, work) == 0 {
                    budget.charge_bytes(index_bytes(index.walked(), order.0.len()))?;
                }
            }
            Ok(AtomTrie { index, levels: columns.into_iter().map(|(_, a)| a).collect(), empty: relation.is_empty() })
        };
        let mut atoms: Vec<AtomTrie> = Vec::with_capacity(tries.len());
        for (relation, arguments) in tries {
            atoms.push(trie(relation, arguments, budget)?);
        }
        let mut checks = vec![Vec::new(); order.len() + 1];
        let mut libs = vec![Vec::new(); clause.variables.len()];
        let mut filter_orders = StableHashMap::default();
        let mut unions = Vec::new();
        for &node in nodes {
            let held = node_variables(&clause.nodes[node]);
            let last = held.iter().filter(|v| !bound.contains(v)).map(|v| rank[usize::from(v.0)]).max().unwrap_or(order.len());
            match &clause.nodes[node] {
                IrNode::Atom(atom) => {
                    let NodeInput::Relation(relation) = &inputs.0[node] else { panic!("the relation of each atom") };
                    atoms.push(trie(relation, &atom.arguments, budget)?);
                }
                IrNode::Lib(atom) => {
                    for v in super::plan::variables_of(&atom.arguments) {
                        libs[usize::from(v.0)].push(node);
                    }
                    checks[last].push(node);
                }
                IrNode::Not(filter) | IrNode::Counterexample(filter) => {
                    let NodeInput::Clauses(bodies) = &inputs.0[node] else { panic!("the inputs of each filter's body") };
                    filter_orders.insert(node, variable_order(&filter.body, &sizes(&filter.body, &bodies[0]), &filter.outer));
                    checks[last].push(node);
                }
                IrNode::Or(_) => {
                    unions.push(node);
                    checks[last].push(node);
                }
                IrNode::Comparison(_) => checks[last].push(node),
            }
        }
        for slot in &mut checks {
            slot.sort_by_key(|&node| (check_cost(&clause.nodes[node]), node));
        }
        let stop_from = order.len() - order.iter().rev().take_while(|v| !clause.columns.contains(v)).count();
        Ok(Plan { order, atoms, checks, libs, filter_orders, unions, stop_from })
    }
}

/// The place of a node among the nodes checked at one variable, cheapest
/// first: a comparison, an algebra relation, a filter's probe, a union's
/// branches. A check that fails ends the binding, so the order depends on
/// the kinds of the nodes and not on where they stand in the body.
fn check_cost(node: &IrNode) -> u8 {
    match node {
        IrNode::Comparison(_) => 0,
        IrNode::Lib(_) => 1,
        IrNode::Not(_) | IrNode::Counterexample(_) => 2,
        IrNode::Or(_) => 3,
        IrNode::Atom(_) => unreachable!("an atom is joined, not checked"),
    }
}

/// The plan of one part of a clause.
struct PartPlan {
    /// The least index in the clause as compiled of the part's nodes.
    written: u32,
    columns: Vec<ColumnIndex>,
    /// The variables of the part's columns.
    projected: Vec<Variable>,
    plan: Plan,
}

/// The plans of the parts of a clause, for one set of variables bound
/// before its search.
struct ClausePlan {
    parts: Vec<PartPlan>,
}

/// The bytes of entries that a [`SearchMemo`] takes, past which it takes no
/// new entry. A provisional bound, which changes no output.
const MEMO_BYTES: usize = 256 << 20;

/// What an evaluation charged: the bindings it charged to its budget, the
/// units it charged to the request alone ([`Budget::charge_request`]), and the
/// most bytes it held.
#[derive(Clone, Copy, Default, PartialEq, Eq, Debug)]
struct Charges {
    bindings: u64,
    request: u64,
    /// The most bytes it held at a time, from where it began
    /// ([`Budget::charge_bytes`]).
    bytes: u64,
}

impl Charges {
    fn saturating_add(self, other: Charges) -> Charges {
        Charges { bindings: self.bindings.saturating_add(other.bindings), request: self.request.saturating_add(other.request), bytes: self.bytes.max(other.bytes) }
    }
}

/// The rows of a lib atom's algebra relation at bound values.
type LibRows = Rc<Vec<Box<[TermId]>>>;

#[derive(Default)]
struct MemoTables {
    bytes: usize,
    plans: StableHashMap<(usize, Vec<Variable>), Rc<ClausePlan>>,
    libs: StableHashMap<LibName, StableHashMap<Vec<Option<TermId>>, LibRows>>,
    probes: StableHashMap<(usize, Vec<TermId>), (bool, Charges)>,
    branches: StableHashMap<(usize, Vec<(Variable, TermId)>), (Arc<Relation>, Charges)>,
    spatial: StableHashMap<(usize, usize, u8), Rc<spatial::DistanceIndex>>,
}

impl MemoTables {
    /// Takes `size` more bytes and gives whether the memo took them.
    fn take(&mut self, size: usize) -> bool {
        let fits = self.bytes.saturating_add(size) <= MEMO_BYTES;
        if fits {
            self.bytes += size;
        }
        fits
    }
}

/// What the evaluation of one clause or part keeps, for the searches it
/// starts: the rows of a lib atom, whether a filter holds and the relation
/// of an `OR` branch at the values they were evaluated at, with the counts
/// of a filter's and a branch's evaluation, and the plan of each nested
/// clause at each set of bound variables. A clause, a filter and a branch
/// stand in the memo by their address, and stand at one address in one
/// evaluation.
#[derive(Default)]
pub struct SearchMemo {
    tables: RefCell<MemoTables>,
}

impl SearchMemo {
    /// The plan of `clause` with `bound` bound before its search, made at
    /// its first use in the order, over the nodes, that `order_at` gives at
    /// the sorted variables of `bound`, and counted in `budget` as
    /// [`Plan::new`] gives.
    fn plan(
        &self,
        clause: &ClauseIr,
        order_at: &dyn Fn(&[Variable]) -> (VariableOrder, Vec<usize>),
        inputs: &JoinInputs,
        bound: &[(Variable, TermId)],
        budget: &mut Budget<'_>,
    ) -> Result<Rc<ClausePlan>, ReachedBound> {
        let mut variables: Vec<Variable> = bound.iter().map(|&(variable, _)| variable).collect();
        variables.sort_by_key(|variable| variable.0);
        let key = (std::ptr::from_ref(clause) as usize, variables);
        if let Some(plan) = self.tables.borrow().plans.get(&key) {
            return Ok(plan.clone());
        }
        let (order, nodes) = order_at(&key.1);
        let parts = parts(clause, &nodes, &|node| node)
            .into_iter()
            .map(|part| {
                Ok(PartPlan {
                    written: part.nodes.iter().map(|&node| clause.written[node]).min().unwrap_or(0),
                    columns: part.columns(clause),
                    projected: clause.columns.iter().copied().filter(|v| part.variables.contains(v)).collect(),
                    plan: Plan::new(clause, &part.nodes, &[], part.order(&order, &key.1), &key.1, inputs, budget)?,
                })
            })
            .collect::<Result<_, ReachedBound>>()?;
        let plan = Rc::new(ClausePlan { parts });
        self.tables.borrow_mut().plans.insert(key, plan.clone());
        Ok(plan)
    }

    /// The rows of the algebra relation `relation` at `bound`, if held.
    fn lib(&self, relation: &LibName, bound: &[Option<TermId>]) -> Option<LibRows> {
        self.tables.borrow().libs.get(relation)?.get(bound).cloned()
    }

    fn keep_lib(&self, relation: &LibName, bound: &[Option<TermId>], rows: &LibRows) {
        let mut tables = self.tables.borrow_mut();
        let size = 64 + bound.len() * 8 + rows.iter().map(|row| 24 + row.len() * 8).sum::<usize>();
        if tables.take(size) {
            tables.libs.entry(relation.clone()).or_default().insert(bound.to_vec(), rows.clone());
        }
    }

    /// Whether the filter at `key` holds, with the counts of its probe, if
    /// held.
    fn probe(&self, key: &(usize, Vec<TermId>)) -> Option<(bool, Charges)> {
        self.tables.borrow().probes.get(key).cloned()
    }

    fn keep_probe(&self, key: (usize, Vec<TermId>), entry: (bool, Charges)) {
        let mut tables = self.tables.borrow_mut();
        if tables.take(64 + key.1.len() * 8 + size_of::<Charges>()) {
            tables.probes.insert(key, entry);
        }
    }

    /// The relation of the branch at `key`, with the counts of its join, if
    /// held.
    fn branch(&self, key: &(usize, Vec<(Variable, TermId)>)) -> Option<(Arc<Relation>, Charges)> {
        self.tables.borrow().branches.get(key).cloned()
    }

    fn keep_branch(&self, key: (usize, Vec<(Variable, TermId)>), entry: (Arc<Relation>, Charges)) {
        let mut tables = self.tables.borrow_mut();
        let size = 96 + key.1.len() * 16 + size_of::<Charges>() + usize::from(entry.0.arity()) * 8 * (entry.0.len().min(1 << 20) as usize);
        if tables.take(size) {
            tables.branches.insert(key, entry);
        }
    }
}

/// The generic join of one connected set of a clause's nodes.
struct Search<'c> {
    clause: &'c ClauseIr,
    registry: &'c Registry,
    inputs: &'c JoinInputs,
    plan: &'c Plan,
    memo: &'c SearchMemo,
    binding: Vec<Option<TermId>>,
    /// The projected row of the binding at a leaf of the search, which
    /// `step` fills and adds to the rows, so a row takes no allocation.
    row: Vec<TermId>,
    tried: Batch,
    /// The projected rows of the leaves so far, row after row, while each leaf
    /// is known to give a row no other leaf gives ([`Search::flat_ok`]).
    flat: Vec<TermId>,
    /// Whether the projected rows are collected in `flat` and not in a set that
    /// tells equal rows apart. That holds while the projection holds every
    /// variable of the order, so that two leaves differ in the value of a
    /// variable, and `unique` held at each leaf so far.
    flat_ok: bool,
    /// Whether the values of each variable on the path to the current leaf
    /// came from a list that holds no value twice, so that this leaf differs
    /// from each other leaf in the value of some variable.
    unique: bool,
}

impl<'c> Search<'c> {
    /// The search over `plan` at the values `bound` gives some variables.
    fn new(
        clause: &'c ClauseIr,
        plan: &'c Plan,
        inputs: &'c JoinInputs,
        registry: &'c Registry,
        memo: &'c SearchMemo,
        bound: &[(Variable, TermId)],
    ) -> Self {
        let mut binding = vec![None; clause.variables.len()];
        for &(variable, value) in bound {
            binding[usize::from(variable.0)] = Some(value);
        }
        Search { clause, registry, inputs, plan, memo, binding, row: Vec::new(), tried: Batch::default(), flat: Vec::new(), flat_ok: false, unique: true }
    }

    /// The rows of `projected` over each binding that passes every node.
    fn run(mut self, projected: &[Variable], budget: &mut Budget<'_>) -> Result<RowSet, ReachedBound> {
        let mut rows = RowSet::empty(projected.len() as u16);
        let plan = self.plan;
        self.flat_ok = !projected.is_empty() && plan.order.iter().all(|variable| projected.contains(variable));
        let mut cursors: Vec<(IndexNode<'_>, usize)> = Vec::with_capacity(plan.atoms.len());
        for atom in &plan.atoms {
            if atom.empty {
                return Ok(rows);
            }
            let mut at = atom.index.root();
            let mut depth = 0;
            while let Some(&argument) = atom.levels.get(depth) {
                let term = match argument {
                    Argument::Term(term) => term,
                    Argument::Variable(v) => match self.binding[usize::from(v.0)] {
                        Some(term) => term,
                        None => break,
                    },
                };
                match at.child(term) {
                    Some(child) => at = child,
                    None => return Ok(rows),
                }
                depth += 1;
            }
            cursors.push((at, depth));
        }
        let unbound = plan.checks.len() - 1;
        if self.passes(unbound, None, budget)? {
            self.step(0, &plan.atoms, &mut cursors, projected, &mut rows, budget)?;
        }
        self.tried.finish(budget)?;
        if self.flat_ok && !self.flat.is_empty() {
            rows = RowSet::of_distinct_deferred(projected.len() as u16, std::mem::take(&mut self.flat));
        }
        Ok(rows)
    }

    /// Searches the variables of the order from `rank` on, and gives whether
    /// a binding passed.
    fn step<'t>(
        &mut self,
        rank: usize,
        atoms: &'t [AtomTrie],
        cursors: &mut Vec<(IndexNode<'t>, usize)>,
        projected: &[Variable],
        rows: &mut RowSet,
        budget: &mut Budget<'_>,
    ) -> Result<bool, ReachedBound> {
        let Some(&variable) = self.plan.order.get(rank) else {
            self.row.clear();
            self.row.extend(projected.iter().map(|v| self.binding[usize::from(v.0)].expect("a bound column")));
            if self.flat_ok && self.unique {
                self.flat.extend_from_slice(&self.row);
                budget.charge_rows(1)?;
                return Ok(true);
            }
            if self.flat_ok {
                // A leaf may repeat a row: the rows so far, distinct, go in the set.
                self.flat_ok = false;
                for row in self.flat.chunks_exact(self.row.len()) {
                    rows.insert_slice(row);
                }
                self.flat.clear();
            }
            if rows.insert_slice(&self.row) {
                budget.charge_rows_of(1, projected.len())?;
            }
            return Ok(true);
        };
        let at = |atom: &AtomTrie, depth: usize| matches!(atom.levels.get(depth), Some(Argument::Variable(v)) if *v == variable);
        let sources: Vec<usize> = (0..atoms.len()).filter(|&a| at(&atoms[a], cursors[a].1)).collect();
        let mut held_union = None;
        // Whether the candidates hold no value twice. Each list but a type's
        // domain is made of the distinct values of an index run, or is sorted
        // and deduplicated.
        let mut distinct = true;
        let candidates: Vec<TermId> = if let Some(value) = self.equal_value(variable) {
            vec![value]
        } else if let Some(&smallest) = sources.iter().min_by_key(|&&a| (cursors[a].0.len(), a)) {
            // A lib atom that a mode satisfies gives the values through the
            // atoms' indexes where it gives fewer than the smallest atom holds.
            if let Some(values) = self.lib_values(variable)?.filter(|values| values.len() < cursors[smallest].0.len()) {
                values
            } else if self.ready_union(variable) {
                self.union_values(variable, budget)?.expect("a ready union exports the variable").1
            } else if let Some(values) = self.spatial_values(variable, &atoms[smallest].index, cursors[smallest].0, budget)? {
                values
            } else if sources.len() > 1 {
                intersect_values(&sources.iter().map(|&a| cursors[a].0).collect::<Vec<_>>(), budget)?
            } else {
                cursors[smallest].0.values().to_vec()
            }
        } else if let Some(values) = self.lib_values(variable)? {
            values
        } else if let Some((node, values)) = self.union_values(variable, budget)? {
            held_union = Some(node);
            values
        } else {
            let ty = &self.clause.variables[usize::from(variable.0)].ty;
            let values = domain(self.registry, ty).ok_or(ReachedBound::NoValues)?;
            let mut sorted = values.clone();
            sorted.sort_unstable_by_key(|value| value.encoding());
            distinct = sorted.windows(2).all(|pair| pair[0] != pair[1]);
            values
        };
        let early = rank >= self.plan.stop_from;
        let mut candidates = candidates;
        if !sources.is_empty() {
            // Generated values are another index run: intersect them with
            // every positive atom before counting attempted bindings.
            candidates.sort_unstable_by_key(|value| value.encoding());
            let mut runs = vec![candidates.as_slice()];
            runs.extend(sources.iter().map(|&a| cursors[a].0.values()));
            candidates = intersect_runs(runs, budget)?;
        }
        if early {
            candidates.sort_by_key(|value| value.encoding());
        }
        let stops = early && !matches!(self.clause.variables[usize::from(variable.0)].ty, ValueType::Ident(_));
        let mut passed = false;
        let path_unique = self.unique;
        self.unique = path_unique && distinct;
        // Each value starts from these cursors, and puts them back after it.
        let saved: Vec<(usize, (IndexNode<'t>, usize))> = sources.iter().map(|&a| (a, cursors[a])).collect();
        for value in candidates {
            self.tried.count(budget, 1)?;
            let mut held = true;
            for &a in &sources {
                while held && at(&atoms[a], cursors[a].1) {
                    match cursors[a].0.child(value) {
                        Some(child) => cursors[a] = (child, cursors[a].1 + 1),
                        None => held = false,
                    }
                }
            }
            self.binding[usize::from(variable.0)] = Some(value);
            if held && self.passes(rank, held_union, budget)? {
                passed |= self.step(rank + 1, atoms, cursors, projected, rows, budget)?;
            }
            self.binding[usize::from(variable.0)] = None;
            for &(a, cursor) in &saved {
                cursors[a] = cursor;
            }
            if passed && stops {
                break;
            }
        }
        self.unique = path_unique;
        Ok(passed)
    }

    /// A union can narrow an atom's candidate run once its inputs are
    /// available. Keep its final check: another export may still be unbound.
    fn ready_union(&self, variable: Variable) -> bool {
        let placed: Vec<bool> = self.binding.iter().map(Option::is_some).collect();
        self.plan.unions.iter().any(|&node| matches!(&self.clause.nodes[node], IrNode::Or(union)
            if union.exported.contains(&variable) && grounds(union, &placed)))
    }

    /// The value an `=` gives `variable` from a bound variable or `0`.
    fn equal_value(&self, variable: Variable) -> Option<TermId> {
        self.plan.checks.iter().flatten().find_map(|&node| match &self.clause.nodes[node] {
            IrNode::Comparison(Comparison { op: ConstraintOp::Eq, first, second, .. }) => match (*first == variable, second) {
                (true, Operand::Zero) => Some(TermId::from_encoding(0)),
                (true, Operand::Variable(other)) => self.binding[usize::from(other.0)],
                (false, Operand::Variable(other)) if *other == variable => self.binding[usize::from(first.0)],
                _ => None,
            },
            _ => None,
        })
    }

    /// The values that a lib atom whose bound columns satisfy one of its
    /// modes gives `variable`, from the first such atom, or `None` where no
    /// lib atom that holds it is satisfied.
    fn lib_values(&self, variable: Variable) -> Result<Option<Vec<TermId>>, ReachedBound> {
        let bound: Vec<bool> = self.binding.iter().map(Option::is_some).collect();
        for &node in &self.plan.libs[usize::from(variable.0)] {
            let IrNode::Lib(atom) = &self.clause.nodes[node] else { unreachable!("a lib atom") };
            let relation = algebra_relation(self.registry, &atom.relation);
            if !mode_holds(relation, &atom.arguments, self.clause, &bound) {
                continue;
            }
            let columns: Vec<ColumnIndex> = atom
                .arguments
                .0
                .iter()
                .filter(|(_, argument)| *argument == Argument::Variable(variable))
                .map(|(column, _)| *column)
                .collect();
            let mut values = Vec::new();
            self.evaluate_lib(node, &mut |row| {
                let value = row[usize::from(columns[0].0)];
                if columns.iter().all(|c| row[usize::from(c.0)] == value) {
                    values.push(value);
                }
            })?;
            values.sort_by_key(|value| value.encoding());
            values.dedup();
            return Ok(Some(values));
        }
        Ok(None)
    }

    /// The node and the values of the first union that exports `variable`,
    /// each branch joined at the bound values of its columns, or `None`
    /// where no union exports it. Where a column of a branch is unbound, the
    /// branch is joined without the nodes that hold a column it does not
    /// ground, so the values are those of the branches at the bound columns:
    /// a superset of the union's values at a binding of its columns, which the
    /// union's check at the rank of the last of its columns holds to the whole
    /// branches. Where no column is unbound, each value is a row of a branch,
    /// so the union holds at it.
    fn union_values(&self, variable: Variable, budget: &mut Budget<'_>) -> Result<Option<(usize, Vec<TermId>)>, ReachedBound> {
        let placed: Vec<bool> = self.binding.iter().map(Option::is_some).collect();
        let ready = self.ready_union(variable);
        let found = self.plan.unions.iter().find_map(|&node| match &self.clause.nodes[node] {
            IrNode::Or(union) if union.exported.contains(&variable) && (!ready || grounds(union, &placed)) => Some((node, union)),
            _ => None,
        });
        let Some((node, union)) = found else { return Ok(None) };
        let mut values = Vec::new();
        for index in union.in_canonical_order() {
            let branch = &union.branches[index];
            let at = branch.columns.iter().position(|column| *column == variable).expect("each branch holds each export");
            each_row(&*self.branch(node, index, branch, budget)?, &mut |row| values.push(row[at]));
        }
        values.sort_by_key(|value| value.encoding());
        values.dedup();
        Ok(Some((node, values)))
    }

    /// Whether a branch of `union`, the union of the node at `node`, holds
    /// at the bound values of its columns.
    fn union_holds(&self, node: usize, union: &super::ir::Union, budget: &mut Budget<'_>) -> Result<bool, ReachedBound> {
        for index in union.in_canonical_order() {
            if !self.branch(node, index, &union.branches[index], budget)?.is_empty() {
                return Ok(true);
            }
        }
        Ok(false)
    }

    /// The relation of `branch`, the branch at `index` of the union of the
    /// node at `node`, at the bound values of its columns, without the nodes
    /// that [`kept_nodes`] leaves out. The memo serves a branch joined at
    /// those values before, and counts what its join counted.
    fn branch(&self, node: usize, index: usize, branch: &ClauseIr, budget: &mut Budget<'_>) -> Result<Arc<Relation>, ReachedBound> {
        let NodeInput::Clauses(bodies) = &self.inputs.0[node] else { unreachable!("the inputs of a union's branches") };
        let bound: Vec<(Variable, TermId)> =
            branch.columns.iter().filter_map(|&column| Some((column, self.binding[usize::from(column.0)]?))).collect();
        let key = (std::ptr::from_ref(branch) as usize, bound);
        if let Some((relation, charges)) = self.memo.branch(&key) {
            budget.replay(charges)?;
            return Ok(relation);
        }
        let order_at = branch_order(branch, &bodies[index]);
        let (relation, charges) = budget.logged(|budget| join_ordered(self.memo, branch, &order_at, &bodies[index], self.registry, &key.1, budget))?;
        let relation = Arc::new(relation);
        self.memo.keep_branch(key, (relation.clone(), charges));
        Ok(relation)
    }

    /// Calls `emit` on each row of the lib atom at `node` that agrees with
    /// the atom's terms and bound variables. The memo serves an atom
    /// evaluated at those values before.
    fn evaluate_lib(&self, node: usize, emit: &mut dyn FnMut(&[TermId])) -> Result<(), ReachedBound> {
        let IrNode::Lib(atom) = &self.clause.nodes[node] else { unreachable!("a lib atom") };
        let relation = algebra_relation(self.registry, &atom.relation);
        let mut bound = vec![None; relation.columns.len()];
        for (column, argument) in atom.arguments.0.iter() {
            bound[usize::from(column.0)] = match argument {
                Argument::Term(term) => Some(*term),
                Argument::Variable(v) => self.binding[usize::from(v.0)],
            };
        }
        // A ground predicate has no generated values to reuse. In a large
        // spatial join most such tuples are tested once; retaining a key,
        // a row and a vector for each tuple can dwarf the actual result.
        if bound.iter().all(Option::is_some) {
            let algebra=crate::algebra::algebra(&atom.relation).expect("a native form of each algebra relation");
            algebra.evaluate(&bound,self.registry,&mut |row| {
                if bound.iter().zip(row).all(|(b,value)|b==&Some(*value)) {emit(row);}
            }).map_err(ReachedBound::Margin)?;
            return Ok(());
        }
        let rows = match self.memo.lib(&atom.relation, &bound) {
            Some(rows) => rows,
            None => {
                let algebra = crate::algebra::algebra(&atom.relation).expect("a native form of each algebra relation");
                let mut found = Vec::new();
                algebra
                    .evaluate(&bound, self.registry, &mut |row| {
                        if bound.iter().zip(row).all(|(b, value)| b.is_none_or(|b| b == *value)) {
                            found.push(row.into());
                        }
                    })
                    .map_err(ReachedBound::Margin)?;
                let rows = Rc::new(found);
                self.memo.keep_lib(&atom.relation, &bound, &rows);
                rows
            }
        };
        for row in rows.iter() {
            emit(row);
        }
        Ok(())
    }

    /// Whether the binding passes each node checked at `rank`, other than
    /// `held_union`, the node of the union that gave the value of the
    /// variable at `rank`: that union is the last check of its variables, so
    /// the value is a row of one of its branches and the union holds.
    fn passes(&self, rank: usize, held_union: Option<usize>, budget: &mut Budget<'_>) -> Result<bool, ReachedBound> {
        for &node in self.plan.checks[rank].iter().filter(|&&node| Some(node) != held_union) {
            let holds = match &self.clause.nodes[node] {
                IrNode::Comparison(comparison) => self.compare(comparison),
                IrNode::Lib(_) => {
                    let mut found = false;
                    self.evaluate_lib(node, &mut |_| found = true)?;
                    found
                }
                IrNode::Not(filter) | IrNode::Counterexample(filter) => !self.probe(node, filter, budget)?,
                IrNode::Or(union) => self.union_holds(node, union, budget)?,
                IrNode::Atom(_) => unreachable!("an atom is joined, not checked"),
            };
            if !holds {
                return Ok(false);
            }
        }
        Ok(true)
    }

    /// Whether `filter`, the filter of the node at `node`, holds a binding
    /// at the bound values of its outer variables. The memo serves a filter
    /// probed at those values before, and counts what its probe counted.
    fn probe(&self, node: usize, filter: &Filter, budget: &mut Budget<'_>) -> Result<bool, ReachedBound> {
        let outer: Vec<TermId> = filter.outer.iter().map(|v| self.binding[usize::from(v.0)].expect("a bound outer variable")).collect();
        let key = (std::ptr::from_ref(filter) as usize, outer);
        if let Some((holds, charges)) = self.memo.probe(&key) {
            budget.replay(charges)?;
            return Ok(holds);
        }
        let NodeInput::Clauses(bodies) = &self.inputs.0[node] else { unreachable!("the inputs of a filter's body") };
        let (holds, charges) = budget
            .logged(|budget| super::filters::probe(self.memo, filter, &key.1, &self.plan.filter_orders[&node], &bodies[0], self.registry, budget))?;
        self.memo.keep_probe(key, (holds, charges));
        Ok(holds)
    }

    /// Whether the bound operands of `comparison` satisfy it. An order
    /// compares its operands as numbers.
    fn compare(&self, comparison: &Comparison) -> bool {
        let first = self.binding[usize::from(comparison.first.0)].expect("a bound operand");
        let second = match comparison.second {
            Operand::Variable(v) => self.binding[usize::from(v.0)].expect("a bound operand"),
            Operand::Zero => TermId::from_encoding(0),
        };
        match comparison.op {
            ConstraintOp::Eq => first == second,
            ConstraintOp::Ne => first != second,
            ConstraintOp::Lt => Term::decode_number(first) < Term::decode_number(second),
            ConstraintOp::Le => Term::decode_number(first) <= Term::decode_number(second),
            ConstraintOp::Gt => Term::decode_number(first) > Term::decode_number(second),
            ConstraintOp::Ge => Term::decode_number(first) >= Term::decode_number(second),
        }
    }
}

