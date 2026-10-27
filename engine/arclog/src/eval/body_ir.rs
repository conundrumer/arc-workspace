//! The IR that the evaluator joins for a body of a form, read without the
//! evaluator's entry points: the compile of the body at a path below the form
//! of a [`Given`] relation, with the paths of its nodes. The column flows of
//! a relation read it, in the crate `arclog-tables`, so that the facts they
//! rest on are those of the IR the evaluator runs.

use std::sync::Arc;

use super::ir::{ClauseIr, CompiledBody, IrPaths};
use super::{demonstrated, driver, init_form, picks, rigid};
use crate::check::CheckedProgram;
use crate::program::path::{node_at, NodePath, NodeRef};
use crate::registry::Registry;
use crate::resolver::given::Given;
use crate::resolver::registry_columns;

/// The clause that the evaluator joins for a body, with the paths of its
/// nodes, and what holds them.
pub enum BodyIr {
    Body(Arc<CompiledBody>),
    Shared(Arc<ClauseIr>, Arc<IrPaths>),
    Own(ClauseIr, IrPaths),
}

impl BodyIr {
    /// The clause and the paths of its nodes.
    #[inline]
    pub fn parts(&self) -> (&ClauseIr, &IrPaths) {
        match self {
            BodyIr::Body(body) => (&body.clause, &body.paths),
            BodyIr::Shared(clause, paths) => (clause, paths),
            BodyIr::Own(clause, paths) => (clause, paths),
        }
    }

    /// The held clause of a compile, none where it faults.
    fn of<E>(found: Result<(ClauseIr, IrPaths), E>) -> Option<BodyIr> {
        found.ok().map(|(clause, paths)| BodyIr::Own(clause, paths))
    }
}

impl CheckedProgram {
    /// The IR that the evaluator joins for the body at `body`, a path below
    /// the form of `relation`, with the paths of its nodes; none where the
    /// form's body does not compile.
    pub fn body_ir(&self, registry: &Registry, relation: &Given, body: &NodePath) -> Option<BodyIr> {
        let form = &relation.form;
        let at = form.join(body);
        let root = NodeRef::Program(self.program.program.value());
        match node_at(root, form)? {
            NodeRef::Clause(clause) => driver::clause_body(self, form, clause).ok().map(BodyIr::Body),
            NodeRef::Choose(choose) => {
                if choose.rows.is_some() && *body == NodePath::default().child(0) {
                    picks::for_pathed(self, form, choose).ok().flatten().map(|(clause, paths)| BodyIr::Own(clause, paths))
                } else {
                    BodyIr::of(picks::from_pathed(self, form, choose))
                }
            }
            NodeRef::Demonstrated(demonstrated) => {
                let (clause, paths) = demonstrated::clause_at(self, demonstrated, form, &at)?.ok()?;
                Some(BodyIr::Shared(clause, paths))
            }
            NodeRef::Instance(instance) => {
                let component = registry_columns::component(registry, &instance.component)?;
                let shape = init_form::InstanceShape::of(self, form, instance, component);
                let (clause, paths) = shape.clause_at(self, form, component, &at)?.ok()?;
                Some(BodyIr::Shared(clause, paths))
            }
            NodeRef::Out(out) => {
                let (clause, paths, _) = init_form::out_clause(self, form, out).ok()?;
                Some(BodyIr::Shared(clause, paths))
            }
            NodeRef::RigidDet(rigid) => {
                let steps = relation.output.as_deref()?;
                BodyIr::of(rigid::output_clause(self, form, rigid, steps.first()?))
            }
            _ => None,
        }
    }
}
