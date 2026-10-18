//! The filters of a clause: the compilation of `NOT`, `ALL`, `IF` and `OR`
//! into the IR, the probe of a filter, and the early stop of a search over
//! local labels.
//!
//! A negated atom, an `ALL`'s counterexample relation and an `IF` test are
//! filters: each is probed once its outer variables are bound, with those
//! bindings only, and none is evaluated alone, since a test that reads an
//! algebra relation through outer labels is no finite relation.
//!
//! Inside a filter or an `OR` branch, a label that the scope does not
//! export is local. Once every variable left in the order is local, the
//! first binding that passes ends the search over them. The search visits
//! values in their order as terms; a search over an Ident variable counts
//! toward the work cap every binding it would try, so the work it counts
//! does not depend on the order of interning.

#![allow(unused_variables, dead_code)]

use super::ReachedBound;
use super::ir::{CompileFault, Filter, IrBuilder};
use super::join::{Budget, JoinInputs};
use super::plan::VariableOrder;
use crate::program::path::NodePath;
use crate::program::{Body, Conjunct, Negated, Node};
use crate::terms::TermId;

/// Compiles a `NOT` at `path` into a [`super::ir::IrNode::Not`] of
/// `builder`'s clause.
pub fn compile_not(builder: &mut IrBuilder<'_>, negated: &Negated, path: &NodePath) -> Result<(), CompileFault> {
    todo!()
}

/// Compiles an `ALL` at `path` into the
/// [`super::ir::IrNode::Counterexample`] of
/// `docs/arclog/arclog.md#universal`: a member of `domain` that fails
/// `body`.
pub fn compile_all(
    builder: &mut IrBuilder<'_>,
    domain: &Node<Body>,
    body: &Node<Body>,
    path: &NodePath,
) -> Result<(), CompileFault> {
    todo!()
}

/// Compiles an `IF` at `path` into a [`super::ir::IrNode::If`], whose clauses
/// are those of `docs/arclog/arclog.md#conditional`.
pub fn compile_if(
    builder: &mut IrBuilder<'_>,
    test: &Node<Body>,
    then: &Node<Body>,
    otherwise: &Node<Body>,
    path: &NodePath,
) -> Result<(), CompileFault> {
    todo!()
}

/// Compiles an `OR` at `path` into a [`super::ir::IrNode::Or`], each branch
/// a clause that binds the variables the `OR` exports.
pub fn compile_or(builder: &mut IrBuilder<'_>, branches: &[Node<Body>], path: &NodePath) -> Result<(), CompileFault> {
    todo!()
}

/// The conjunct kinds this file compiles, for the dispatch of
/// [`IrBuilder::body`]: whether `conjunct` is a `NOT`, an `ALL`, an `IF` or
/// an `OR`.
pub fn is_filter_form(conjunct: &Conjunct) -> bool {
    matches!(conjunct, Conjunct::Not(_) | Conjunct::All { .. } | Conjunct::If { .. } | Conjunct::Or(_))
}

/// Whether `filter` holds a binding at `outer`, the values of its outer
/// variables in the order of [`Filter::outer`], over `inputs`, the inputs
/// of its body, searched in `order` with the early stop on local
/// variables.
pub fn probe(
    filter: &Filter,
    outer: &[TermId],
    order: &VariableOrder,
    inputs: &JoinInputs,
    registry: &crate::registry::Registry,
    budget: &mut Budget<'_>,
) -> Result<bool, ReachedBound> {
    todo!()
}
