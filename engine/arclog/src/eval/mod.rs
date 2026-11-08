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
//! of a pick through the driver's way into the bodies, `demonstrated` the
//! confirmed rules of a `DEMONSTRATED` form, and [`models`]
//! enumerates the models of a case on an input, through the driver.
//! [`mod@determinations`] gives the `DET` nodes in dependency order and the
//! domain of each, which an evaluation at determined values reads, and
//! [`body_ir`] gives the IR the driver joins for a body, for a reader of the
//! body's facts.
//! [`output`] reads a grid from a relation, for the judge. [`proposers`]
//! gives the rows of a proposer over an evidence, which the driver reads for
//! a clause that derives by a proposer. A request made with a
//! [`crate::trace::RunTrace`] appends one record to it for each relation the
//! driver evaluates.

pub mod body_ir;
pub mod body_view;
pub mod read_coordinates;
mod body_context;
pub mod cache;
pub mod carry;
pub mod copies;
pub mod determinations;
pub(crate) mod demonstrated;
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

pub use determinations::{Domain, DomainSize};
pub use driver::FormBodies;
pub use lookup::{input_relation, output_relation, relation_of};
pub use models::ModelsEnd;
pub(crate) use values::{tally_counts, tally_gauges, tally_table};
pub(crate) use values::{noting, once_noted, replay_notes, NoteId};
pub use values::{adopt_fault_sink, ambient, fault_sink, take_effort_fault, FaultSinkHandle, uncounted, unmetered_effort, AssignmentScope, BodyValue, ByteCaps, ByteSpan, Caps, Cancellation, Charged, Cost, EffortFault, Gauge, Gauges, GridValue, Hit, Limits, Outcome, ReachedBound, RelationValue, RequestWork, RunFault, Stop, TableWork, ASSIGNMENT_BYTES_CAP, CANDIDATE_BYTES_CAP, EFFORT_CAP, PREFIX_CONTENT_CAP, REQUEST_BYTES_CAP, REQUEST_WORK_CAP};

use crate::check::CheckedProgram;
use crate::hash::StableHashMap;
use crate::program::{ParamValue, ProgramRelation};
use crate::registry::Registry;
use crate::relations::Relation;
use std::sync::Arc;
use crate::session::TaskSession;
use crate::task::Task;
use crate::terms::Example;
use crate::types::GraphRelation;
use driver::Driver;

/// The values of the case program's parameters, from one source, so a run
/// reads either the stored records or the evidence and never a mix. The
/// stored records play the part of an assignment, except for a `DET` whose
/// every form is a `DET` clause with a body, no proposer and no `ONE` mark:
/// that `DET` reads the rows its clause gives, as a `DET` that an assignment
/// leaves out reads, and its record is compared at the End check alone. Any
/// other `DET` that a record gives reads its record, and a `DET` that no record
/// gives reads as a `DET` that an assignment leaves out. A witness's `assign`
/// of a `DET` gives its rows in place of both.
#[derive(Clone, Debug)]
pub struct ParameterValues {
    source: ParameterSource,
}

/// The source of the values of the case program's parameters.
#[derive(Clone, Debug)]
pub(super) enum ParameterSource {
    /// The rows of each parameter as an arcdata file writes them, typed only
    /// when a clause reads them, by [`crate::terms::encode_param_value`]:
    /// the `param` records, and the relations a witness's `assign` gives in
    /// their place. `held` gives a `DET` that an `assign` does not give the
    /// rows it had on the task ([`ParameterValues::with_held`]).
    Stored {
        records: StableHashMap<ProgramRelation, ParamValue>,
        assigns: StableHashMap<ProgramRelation, ParamValue>,
        held: StableHashMap<ProgramRelation, Arc<Relation>>,
    },
    /// The assignment that [`ParameterValues::determined`] takes.
    Determined(StableHashMap<ProgramRelation, Arc<Relation>>),
}

impl Default for ParameterValues {
    fn default() -> Self {
        ParameterValues { source: ParameterSource::Stored { records: StableHashMap::default(), assigns: StableHashMap::default(), held: StableHashMap::default() } }
    }
}

impl ParameterValues {
    /// The values of the solver's stored `param` records. A `DET` whose every
    /// form is a `DET` clause with a body, no proposer and no `ONE` mark reads
    /// the rows its clause gives, not its record. A `DET` with no record takes
    /// the value it takes at determined values that leave it out.
    pub fn stored(arcdata: &crate::program::Arcdata) -> Self {
        let records = arcdata.params.iter().map(|param| (param.value().name.clone(), param.value().value.clone())).collect();
        ParameterValues { source: ParameterSource::Stored { records, assigns: StableHashMap::default(), held: StableHashMap::default() } }
    }

    /// The values determined from the evidence at the assignment `rows`: the
    /// rows of the chosen value of each `DET` with several values in its domain,
    /// and of each `DET` with `(ONE)` that names a proposer the rows its open
    /// values give. A `DET` that `rows` leaves out takes its one value.
    pub fn determined(rows: impl IntoIterator<Item = (ProgramRelation, Arc<Relation>)>) -> Self {
        ParameterValues { source: ParameterSource::Determined(rows.into_iter().collect()) }
    }

    /// These stored values, with the values of each relation that a
    /// witness's `assign` gives in the place of its stored values or of its
    /// clause's rows. Values determined from the evidence take no `assign`, so
    /// this panics on them.
    pub fn with_assigns(&self, assigns: &[(ProgramRelation, ParamValue)]) -> Self {
        let ParameterSource::Stored { records, assigns: own, held } = &self.source else { panic!("an `assign` over stored values") };
        let mut own = own.clone();
        own.extend(assigns.iter().cloned());
        ParameterValues { source: ParameterSource::Stored { records: records.clone(), assigns: own, held: held.clone() } }
    }

    /// These stored values, with each `DET` of `rows` held at its rows there:
    /// a run on an input beyond the task reads them in the place of its
    /// clauses, as a stored value does not follow another relation's `assign`
    /// or a new input. An `assign` of the `DET` itself comes first. Values
    /// determined from the evidence hold none, so this panics on them.
    pub fn with_held(&self, rows: Vec<(ProgramRelation, Arc<Relation>)>) -> Self {
        let ParameterSource::Stored { records, assigns, held } = &self.source else { panic!("rows held over stored values") };
        let mut held = held.clone();
        held.extend(rows);
        ParameterValues { source: ParameterSource::Stored { records: records.clone(), assigns: assigns.clone(), held } }
    }

    /// The written rows of `relation`: its `assign` where one gives it, and
    /// otherwise its stored record, or `None` where neither gives it, as at
    /// values determined from the evidence.
    pub fn get(&self, relation: &ProgramRelation) -> Option<&ParamValue> {
        match &self.source {
            ParameterSource::Stored { records, assigns, .. } => assigns.get(relation).or_else(|| records.get(relation)),
            ParameterSource::Determined(_) => None,
        }
    }

    /// The written rows of the stored `param` record of `relation`, whatever
    /// a witness's `assign` gives it, or `None` where there is none, as at
    /// values determined from the evidence.
    pub fn recorded(&self, relation: &ProgramRelation) -> Option<&ParamValue> {
        match &self.source {
            ParameterSource::Stored { records, .. } => records.get(relation),
            ParameterSource::Determined(_) => None,
        }
    }

    /// The written rows that a witness's `assign` gives `relation`, or `None`
    /// where it gives none, as at values determined from the evidence.
    pub fn assigned(&self, relation: &ProgramRelation) -> Option<&ParamValue> {
        match &self.source {
            ParameterSource::Stored { assigns, .. } => assigns.get(relation),
            ParameterSource::Determined(_) => None,
        }
    }

    /// Whether these values, determined from the evidence, give each relation
    /// of `rows` its rows there.
    pub fn holds(&self, rows: &[(ProgramRelation, Arc<Relation>)]) -> bool {
        let ParameterSource::Determined(held) = &self.source else { return false };
        rows.iter().all(|(name, value)| held.get(name).is_some_and(|own| crate::session::same_rows(own, value)))
    }

    /// The rows of each relation at these values, determined from the
    /// evidence; none at stored values.
    pub fn determined_rows(&self) -> Vec<(ProgramRelation, Arc<Relation>)> {
        match &self.source {
            ParameterSource::Determined(held) => held.iter().map(|(name, rows)| (name.clone(), Arc::clone(rows))).collect(),
            ParameterSource::Stored { .. } => Vec::new(),
        }
    }

    pub(super) fn source(&self) -> &ParameterSource {
        &self.source
    }
}

/// The evaluation of one checked case program at one set of parameter
/// values on one task, in one task session, at the case's one model, or, by
/// [`Evaluation::models`], at each of its models. Several evaluations, on
/// several threads, share the session and its result cache.
#[derive(Clone, Copy, Debug)]
pub struct Evaluation<'a> {
    pub program: &'a CheckedProgram,
    /// The checked concept program, in which each `DET` that the case
    /// program takes from it is evaluated, as [`crate::solver::Case`]
    /// gives; `None` for a program that takes none, such as the concept
    /// case's.
    pub concept: Option<&'a CheckedProgram>,
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

    /// [`Evaluation::relation`], with a record appended to `trace` for each
    /// relation the request evaluates, in the order it evaluates them. An
    /// evaluation that keeps no trace appends none.
    pub fn relation_traced(&self, relation: &GraphRelation, example: Option<Example>, trace: &mut crate::trace::RunTrace) -> Outcome<RelationValue> {
        let cell = std::cell::RefCell::new(std::mem::take(trace));
        let value = Driver::nested(self, Some(&cell)).value(relation, example);
        *trace = cell.into_inner();
        value
    }

    /// The value of the conjuncts at `kept`, indexes into the body of the
    /// clause at `form`, on `example`, from the entries of its parts, as
    /// `docs/engine/synthesis.md#factorized-bodies` gives. The kept
    /// conjuncts' relation holds the clause's columns whose labels they
    /// hold, as [`ir::compile_conjuncts`] gives. Where the kept conjuncts do
    /// not compile, this gives a [`RunFault`] at `form`. A factor of more
    /// than one model that the body reads takes its first model.
    pub fn body(&self, form: &crate::program::path::NodePath, kept: &[u32], example: Option<Example>) -> Outcome<BodyValue> {
        Driver::taking_first_models(self).body(form, kept, example).map(BodyValue)
    }
}
