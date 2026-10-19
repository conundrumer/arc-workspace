//! The evaluation of one checked case program at given parameter values, on
//! one task, in one task session: its inputs and its entry points, with its
//! driver in `driver`.
//!
//! The evaluation runs on demand: [`Evaluation::relation`] and
//! [`Evaluation::output`] evaluate the entries the request reaches and no
//! other. Each relation of the dependency graph is evaluated once from its
//! inputs, in topological order, since a checked case program is acyclic.
//!
//! The driver calls each part through the functions of the part's own
//! file: [`ir`] and [`filters`] compile a body, [`plan`] orders its
//! variables, [`join`] evaluates it, [`examples`] gives the reads of a
//! relation per example and its lifted form, [`instance`], [`rigid`] and
//! [`unfold`] evaluate the forms over lib components, [`output`] reads the
//! grid, [`cache`] looks up and stores entries, and [`pool`] runs
//! independent entries in parallel, and [`lookup`] finds a relation of the
//! program by its name. [`values`] holds the values and the
//! bounds that the driver and the parts share. [`picks`] gives the options
//! of a pick through the driver's way into the bodies.

pub mod cache;
mod driver;
pub mod examples;
pub mod filters;
pub mod instance;
pub mod ir;
pub mod join;
pub mod lookup;
pub mod output;
pub mod picks;
pub mod plan;
pub mod pool;
pub mod rigid;
pub mod unfold;
pub mod values;

pub use driver::FormBodies;
pub use lookup::{output_relation, relation_of};
pub use values::{Caps, Cancellation, GridValue, Limits, NoGridColumns, Outcome, ReachedBound, RelationValue, RunFault, Stop};

use crate::check::CheckedProgram;
use crate::hash::StableHashMap;
use crate::program::{ParamValue, ProgramRelation};
use crate::registry::Registry;
use crate::session::TaskSession;
use crate::task::Task;
use crate::terms::Example;
use crate::types::GraphRelation;
use driver::Driver;

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
    /// input of the task, the grid columns are underdetermined, and this gives a
    /// [`RunFault`] at the form of `&output`, as an underdetermined `DET` does.
    /// Where `&output` stops on a train pair, this gives that stop.
    pub fn grid_columns(&self) -> Outcome<Result<output::GridColumns, NoGridColumns>> {
        Driver::new(self).grid_columns()
    }

    /// The grid of `&output` on each example of the task, train pairs then
    /// test inputs, by the grid columns that [`Evaluation::grid_columns`]
    /// gives, or why it gives none.
    pub fn outputs(&self) -> Outcome<Result<Box<[(Example, GridValue)]>, NoGridColumns>> {
        let driver = Driver::new(self);
        let columns = match driver.grid_columns()? {
            Ok(columns) => columns,
            Err(none) => return Ok(Err(none)),
        };
        let grids: Outcome<Box<[(Example, GridValue)]>> =
            self.task.examples().map(|example| Ok((example, driver.grid(example, columns)?))).collect();
        grids.map(Ok)
    }
}
