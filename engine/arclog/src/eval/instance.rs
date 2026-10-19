//! Instances of lib components: the [`Construction`] trait, the table of
//! constructions by registry name, the evaluation of an `INIT` form and the
//! defaults of its inputs. The evaluation of an `INIT` form is in `init`.
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
use super::ReachedBound;
use crate::hash::StableHashMap;
use crate::registry::{is_key, ComponentKind, LibEntry, LibName};
use crate::relations::RowSet;
use crate::session::TaskSession;
use crate::types::ValueType;

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
    /// `registry` that declares a component that is a construction or a
    /// detector.
    pub fn new(
        constructions: Vec<Box<dyn Construction>>,
        registry: &crate::registry::Registry,
    ) -> Result<Self, ConstructionsFault> {
        let mut by_name = StableHashMap::default();
        for construction in constructions {
            let name = LibName(construction.name().into());
            let declares = match registry.entry(&name) {
                Some(LibEntry::Component(component)) => {
                    matches!(component.kind, ComponentKind::Construction | ComponentKind::Detector)
                }
                Some(LibEntry::Relation(_) | LibEntry::Proposer(_) | LibEntry::Macro(_)) | None => false,
            };
            if !declares {
                return Err(ConstructionsFault::NotAComponent(name));
            }
            if by_name.contains_key(&name) {
                return Err(ConstructionsFault::Repeated(name));
            }
            by_name.insert(name, construction);
        }
        Ok(Constructions { by_name })
    }

    /// The construction of `name`, or `None` where the table has none.
    pub fn get(&self, name: &LibName) -> Option<&dyn Construction> {
        self.by_name.get(name).map(|construction| construction.as_ref())
    }
}


#[path = "instance_init.rs"]
mod init;

pub use init::evaluate_instance;
