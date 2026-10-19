//! The evaluation of one checked case program at given parameter values, on
//! one task, in one task session: its inputs and its entry points, with its
//! driver in `driver`.
//!
//! The evaluation runs on demand: [`Evaluation::relation`] and
//! [`Evaluation::models`] evaluate the entries the request reaches and no
//! other. Each relation of the dependency graph is evaluated once from its
//! inputs, in topological order, since a checked case program is acyclic.
//!
//! The driver calls each part through the functions of the part's own
//! file: [`ir`] and [`filters`] compile a body, [`plan`] orders its
//! variables, [`join`] evaluates it, [`examples`] gives the reads of a
//! relation per example and its lifted form, [`instance`], [`rigid`] and
//! [`unfold`] evaluate the forms over lib components, [`cache`] looks up
//! and stores entries, and [`pool`] runs
//! independent entries in parallel, and [`lookup`] finds a relation of the
//! program by its name. [`values`] holds the values and the
//! bounds that the driver and the parts share. [`picks`] gives the options
//! of a pick through the driver's way into the bodies, and [`models`]
//! enumerates the models of a case on an input, through the driver.
//! [`output`] reads a grid from a relation, for the judge. [`proposers`]
//! gives the rows of a proposer over an evidence, which the driver reads for
//! a clause that derives by a proposer.

pub mod cache;
mod driver;
pub mod examples;
pub mod filters;
pub mod init_form;
pub mod instance;
pub mod ir;
pub mod join;
pub mod lookup;
pub mod models;
pub mod output;
pub mod picks;
pub mod plan;
pub mod pool;
pub mod proposers;
pub mod rigid;
pub mod unfold;
pub mod values;

pub use driver::FormBodies;
pub use lookup::{output_relation, relation_of};
pub use models::ModelsEnd;
pub use values::{Caps, Cancellation, GridValue, Limits, Outcome, ReachedBound, RelationValue, RunFault, Stop};

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
/// values on one task, in one task session, at the case's one model, or, by
/// [`Evaluation::models`], at each of its models. Several evaluations, on
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
    /// Where a pick or an `Unfold` instance that `relation` reads, at any
    /// depth, has more than one model, the case has more than one model,
    /// which [`Evaluation::models`] enumerates, so this gives a
    /// [`RunFault`] at that form.
    ///
    /// For a relation with no Example
    /// column, a task-wide relation such as a `DET`'s, `example` is `None`.
    /// A task-wide relation asked on an example, or a relation per example
    /// asked with `None`, is a fault of the caller, so this panics on one.
    pub fn relation(&self, relation: &GraphRelation, example: Option<Example>) -> Outcome<RelationValue> {
        Driver::new(self).value(relation, example)
    }
}
