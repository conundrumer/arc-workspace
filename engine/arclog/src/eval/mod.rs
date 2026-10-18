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

#![allow(unused_variables, dead_code)]

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

use std::sync::Arc;
use std::sync::atomic::{AtomicBool, Ordering};

use crate::check::CheckedProgram;
use crate::diagnostic::Diagnostic;
use crate::hash::StableHashMap;
use crate::program::path::NodePath;
use crate::program::{ParamValue, ProgramRelation};
use crate::registry::Registry;
use crate::relations::Relation;
use crate::session::{ReachedSessionBound, TaskSession};
use crate::solver::CaseName;
use crate::task::{Grid, Task};
use crate::terms::{Example, ReachedMarginBound};
use crate::types::GraphRelation;

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
        todo!()
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
        todo!()
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
        todo!()
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

/// The grid of `&output` on one example: the grid, `undefined`, or a stop.
/// A grid is undefined where the relation is, or where a cell of the grid
/// columns has no color or two, as `docs/arclog/constraints.md#the-output-set`
/// gives.
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
        todo!()
    }

    /// These values, with the values of each relation that a witness's
    /// `assign` gives in the place of its stored values.
    pub fn with_assigns(&self, assigns: &[(ProgramRelation, ParamValue)]) -> Self {
        todo!()
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
        todo!()
    }

    /// The grid of `&output` on `example`, read by `columns`, the grid
    /// columns of `&output`.
    pub fn output(&self, example: Example, columns: &output::GridColumns) -> Outcome<GridValue> {
        todo!()
    }

    /// The grid columns of `&output`, as
    /// `docs/arclog/constraints.md#the-output-set` defines them: the pair of
    /// a Position column and a Color column under which the output solves
    /// every train pair.
    ///
    /// Where several pairs solve every train pair and each two of them give
    /// equal grids on every input of the task, this gives the first of them
    /// by column position. Where two of them give different grids on an
    /// input of the task, the grid columns are undetermined, and this gives a
    /// [`RunFault`] at the form of `&output`, as an undetermined `DET` does.
    /// It gives `None` only where no pair solves every train pair.
    pub fn grid_columns(&self) -> Outcome<Option<output::GridColumns>> {
        todo!()
    }

    /// The grid of `&output` on each example of the task, train pairs then
    /// test inputs, by the grid columns that [`Evaluation::grid_columns`]
    /// gives; `None` where it gives none.
    pub fn outputs(&self) -> Outcome<Option<Box<[(Example, GridValue)]>>> {
        todo!()
    }
}
