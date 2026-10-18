//! Instances of lib components: the [`Construction`] trait, the table of
//! constructions by registry name, the evaluation of an `INIT` form, the
//! defaults of its inputs, and a `DET` whose proposer is a construction.
//!
//! The constructions stand in the crate `arclog-constructions`, which
//! depends on this crate, so no code of this crate refers to them. An instance
//! finds its component's construction by its registry name in the
//! [`Constructions`] of its evaluation.
//!
//! A construction is evaluated over its inputs grouped by key, and gives
//! its outputs as sets: it reads no order of the rows it is given, and none
//! of its outputs depends on the order it built them in.

#![allow(unused_variables, dead_code)]

use super::join::Budget;
use super::{Evaluation, Outcome, RelationValue, ReachedBound};
use crate::hash::StableHashMap;
use crate::program::path::NodePath;
use crate::registry::LibName;
use crate::relations::RowSet;
use crate::session::TaskSession;
use crate::types::{GraphRelation, ValueType};

/// The rows of one key group of an instance: for each input of the
/// component, in the order the registry declares its inputs, the rows of
/// that input at the group's key, with the key's columns left out, and the
/// type of each of those columns, the instance's binding of the component's
/// type parameters.
#[derive(Debug)]
pub struct GroupInputs<'a> {
    pub inputs: &'a [RowSet],
    pub types: &'a [Box<[ValueType]>],
}

/// The rows a construction gives for one key group: for each output of the
/// component, in the order the registry declares its outputs, its rows
/// with the key's columns left out, each output a set.
#[derive(Debug)]
pub struct GroupOutputs {
    pub outputs: Box<[RowSet]>,
}

/// What a construction may use beside its inputs: the task session, whose
/// intern table gives an Ident to a set, the registry, and the budget its
/// bindings and rows count against.
#[derive(Debug)]
pub struct ConstructionContext<'a, 'b> {
    pub session: &'a TaskSession,
    pub registry: &'a crate::registry::Registry,
    pub budget: &'b mut Budget<'a>,
}

/// A construction or a detector of the lib, native, evaluated on one key
/// group at a time.
pub trait Construction: Send + Sync {
    /// The component's name in the registry, such as `Quotient`.
    fn name(&self) -> &'static str;

    /// The outputs of the component on one key group. A bound reached
    /// while it builds them stops it.
    fn evaluate(
        &self,
        group: &GroupInputs<'_>,
        context: &mut ConstructionContext<'_, '_>,
    ) -> Result<GroupOutputs, ReachedBound>;
}

/// The constructions by their registry names.
pub struct Constructions {
    by_name: StableHashMap<LibName, Box<dyn Construction>>,
}

impl std::fmt::Debug for Constructions {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.debug_struct("Constructions").finish_non_exhaustive()
    }
}

/// A fault that keeps a table of constructions from being built: two
/// constructions of one name, or a name of no component of the registry.
#[derive(Clone, PartialEq, Eq, Debug)]
pub enum ConstructionsFault {
    Repeated(LibName),
    NotAComponent(LibName),
}

impl Constructions {
    /// The table of `constructions`. Each one's name is a name of
    /// `registry` that declares a construction or a detector: a component,
    /// or a derivation that a `DET` gives as its proposer, such as
    /// `Division`.
    pub fn new(
        constructions: Vec<Box<dyn Construction>>,
        registry: &crate::registry::Registry,
    ) -> Result<Self, ConstructionsFault> {
        todo!()
    }

    /// The construction of `name`, or `None` where the table has none.
    pub fn get(&self, name: &LibName) -> Option<&dyn Construction> {
        todo!()
    }
}

/// The value of `output`, an output of the instance whose `INIT` form
/// stands at `form`: its component's construction evaluated over each key
/// group of the instance's inputs, each input the rows its clause gives or,
/// where the instance writes none, the input's default rows.
pub fn evaluate_instance(
    evaluation: &Evaluation<'_>,
    form: &NodePath,
    output: &GraphRelation,
    budget: &mut Budget<'_>,
) -> Outcome<RelationValue> {
    todo!()
}

/// The value of a `DET` at `form` whose proposer is a construction, such as
/// `(DET &frame Frame)`: the construction evaluated over the inputs its
/// stored parameter gives, such as the extents of a Frame.
pub fn evaluate_det_construction(
    evaluation: &Evaluation<'_>,
    form: &NodePath,
    budget: &mut Budget<'_>,
) -> Outcome<RelationValue> {
    todo!()
}
