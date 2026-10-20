//! The determinations of a case program from the evidence, as
//! `docs/engine/determination.md#det` gives them: the `DET` nodes in
//! dependency order, and the domain of each, which an evaluation at
//! determined values reads.
//!
//! A `DET` reads a pick, or the relation of a `DEMONSTRATED` form, only
//! where that relation has one model, on each example where the read is
//! lifted, so the domains are computed outside any enumeration of
//! models.

use std::sync::Arc;

use super::driver::{derivation, Driver};
use super::join;
use super::{Evaluation, Outcome, RelationValue, RunFault, Stop};
use crate::check::CheckedProgram;
use crate::program::path::{node_at, NodePath, NodeRef};
use crate::program::{Clause, ClauseKeyword, ProgramRelation, RelationName};
use crate::registry::{LibEntry, Proposer, ProposerKind, Registry};
use crate::relations::{Relation, Row, RowSet};
use crate::resolver::{DependencyKind, GraphNodeIndex};
use crate::types::GraphRelation;

/// The domain of a `DET`, or the value of a read of its forms that is
/// `undefined` or stopped, as [`super::picks::Pick`] gives a pick's.
#[derive(Clone, Debug)]
pub enum Domain {
    /// Each value in the domain as rows of the `DET`'s relation, each once, in the
    /// canonical order by content of `crate::terms::content_order`.
    Rows(Vec<Arc<Relation>>),
    Undefined,
    Stopped(Stop),
}

/// The `DET` nodes of `program`, its [`DependencyKind::Parameter`] nodes and
/// the [`DependencyKind::Chosen`] nodes of a `DET` with `(ONE)`, each after
/// each such node it reads at any depth.
pub fn determinations(program: &CheckedProgram) -> Vec<GraphNodeIndex> {
    let program = &program.program;
    let graph = &program.graph;
    let mut done = vec![false; graph.nodes.len()];
    let mut order = Vec::new();
    for root in 0..graph.nodes.len() {
        let mut stack: Vec<(usize, usize)> = vec![(root, 0)];
        while let Some(&(node, next)) = stack.last() {
            if done[node] {
                stack.pop();
                continue;
            }
            match graph.reads[node].get(next) {
                Some(read) => {
                    stack.last_mut().expect("the stack holds `node`").1 += 1;
                    stack.push((read.0 as usize, 0));
                }
                None => {
                    done[node] = true;
                    order.push(GraphNodeIndex(node as u32));
                    stack.pop();
                }
            }
        }
    }
    order.retain(|&node| is_det(program, node));
    order
}

/// Whether `node` is a `DET` node: a parameter, or a chosen relation that a
/// `DET` with `(ONE)` gives.
fn is_det(program: &crate::resolver::ResolvedProgram, node: GraphNodeIndex) -> bool {
    match &program.graph.nodes[node.0 as usize].kind {
        DependencyKind::Parameter(_) => true,
        DependencyKind::Chosen(_) => {
            let root = NodeRef::Program(program.program.value());
            program.forms_of(node).iter().any(|at| matches!(node_at(root, at), Some(NodeRef::Clause(clause)) if clause.keyword == ClauseKeyword::Det))
        }
        _ => false,
    }
}

/// The relation of a `DET` node of kind `kind`, and whether it ends in
/// `(ONE)`, or `None` for a node of another kind.
pub fn det_relation(kind: &DependencyKind) -> Option<(ProgramRelation, bool)> {
    match kind {
        DependencyKind::Parameter(relation) => Some((relation.clone(), false)),
        DependencyKind::Chosen(name) => Some((ProgramRelation::Declared(name.clone()), true)),
        _ => None,
    }
}

/// The node of the `DET` of `relation` in `program`, or `None` where no
/// `DET` of `program` gives it.
pub fn det_node(program: &CheckedProgram, relation: &ProgramRelation) -> Option<GraphNodeIndex> {
    let mut nodes = program.program.graph.nodes.iter();
    let at = nodes.position(|node| det_relation(&node.kind).is_some_and(|(found, _)| found == *relation))?;
    Some(GraphNodeIndex(at as u32))
}

impl<'a> Evaluation<'a> {
    /// The evaluation of the concept program at these parameter values, and
    /// its node of the `DET` of `node`, where `node` is a `DET` node whose
    /// forms the case program takes from the concept program; `None` for
    /// any other node.
    pub(super) fn in_concept(&self, node: GraphNodeIndex) -> Option<(Evaluation<'a>, GraphNodeIndex)> {
        let concept = self.concept?;
        let program = &self.program.program;
        program.concept_path(program.form_of(node))?;
        let (relation, _) = det_relation(&program.graph.nodes[node.0 as usize].kind)?;
        let at = det_node(concept, &relation).expect("the concept program holds each `DET` a case takes from it");
        Some((Evaluation { program: concept, concept: None, ..*self }, at))
    }
}

impl Evaluation<'_> {
    /// The domain of the `DET` node `node`, task-wide, at the values
    /// these parameter values give the `DET`s its forms read. A `DET` that
    /// the case program takes from the concept program is evaluated there.
    ///
    /// A form derives by the rule of `derivation`, which `Driver::clause`
    /// uses. A form with a body gives one value, its rows; a form with no
    /// body, by the proposer that rule gives, one value of the proposer's
    /// whole set of rows, or one value per row where the registry marks
    /// that proposer type-domain. A `DET` form with no body that names several
    /// proposers, the stored reading of a `DET_OR_RULE` line with several,
    /// gives the domain of each proposer by that rule, its rows mapped by
    /// position onto the relation's columns. A `DET` of several forms has the
    /// values that each of its forms gives as its domain. A form with no body and no
    /// proposer is a fault of the conversion.
    pub fn domain(&self, node: GraphNodeIndex) -> Outcome<Domain> {
        let program = &self.program.program;
        assert!(is_det(program, node), "the node of a `DET`");
        if let Some((concept, node)) = self.in_concept(node) {
            return concept.domain(node);
        }
        let relation = GraphRelation { node, output: None };
        let types = self.program.types.columns(&relation).ok_or_else(|| RunFault {
            message: "the `DET`'s columns have no types".into(),
            form: program.form_of(node).clone(),
        })?;
        let driver = Driver::reading_det(self, node);
        let root = NodeRef::Program(program.program.value());
        let mut kept: Option<Vec<Vec<Row>>> = None;
        for at in program.forms_of(node) {
            let Some(NodeRef::Clause(clause)) = node_at(root, at) else { panic!("a clause of a `DET`") };
            if let Some(fault) = conversion_fault(clause, at) {
                return Err(fault);
            }
            let fault = |message: String| RunFault { message: message.into(), form: at.clone() };
            let several = clause.keyword == ClauseKeyword::Det && clause.proposers.len() > 1 && clause.body.value().conjuncts.is_empty();
            let sources: Vec<(Outcome<RelationValue>, bool)> = if several {
                let proposers = clause.proposers.iter().enumerate();
                proposers.map(|(index, proposer)| (driver.proposed(at, clause, index, None), is_domain(self.registry, proposer))).collect()
            } else {
                let domain = derivation(clause, at)?.is_some_and(|index| is_domain(self.registry, &clause.proposers[index]));
                vec![(driver.clause(at, None), domain)]
            };
            let mut found: Vec<Vec<Row>> = Vec::new();
            for (value, domain) in sources {
                let mut rows = match super::init_form::rows_of(value?, types.len()).map_err(fault)? {
                    Ok(rows) => rows,
                    Err(RelationValue::Undefined) => return Ok(Domain::Undefined),
                    Err(RelationValue::Stopped(stop)) => return Ok(Domain::Stopped(stop)),
                    Err(RelationValue::Rows(_)) => unreachable!("a value that holds no rows"),
                };
                {
                    let table = self.session.intern.read().expect("an intern table that no panic poisoned");
                    rows.sort_by(|a, b| crate::terms::content_order(types, a, b, &table));
                }
                rows.dedup();
                if domain { found.extend(rows.into_iter().map(|row| vec![row])) } else { found.push(rows) }
            }
            kept = Some(match kept {
                None => found,
                Some(kept) => kept.into_iter().filter(|value| found.contains(value)).collect(),
            });
        }
        let mut kept = kept.expect("a `DET` node with a form");
        {
            let table = self.session.intern.read().expect("an intern table that no panic poisoned");
            kept.sort_by(|a, b| {
                let rows = a.iter().zip(b).map(|(x, y)| crate::terms::content_order(types, x, y, &table));
                rows.fold(std::cmp::Ordering::Equal, std::cmp::Ordering::then).then(a.len().cmp(&b.len()))
            });
        }
        kept.dedup();
        let values = kept.into_iter().map(|rows| {
            let mut set = RowSet::empty(types.len() as u16);
            for row in rows {
                set.insert(row);
            }
            Arc::new(join::one_part(set))
        });
        Ok(Domain::Rows(values.collect()))
    }
}

/// The fault of the `DET` form `clause` at `form` where it has no body and no
/// proposer, `(DET &x)` or `(DET &x (ONE))`: such a form gives no value, and
/// is a fault of the conversion.
pub(super) fn conversion_fault(clause: &Clause, form: &NodePath) -> Option<RunFault> {
    let empty = clause.keyword == ClauseKeyword::Det && clause.proposers.is_empty() && clause.body.value().conjuncts.is_empty();
    empty.then(|| {
        let name = relation_spelled(&clause.derives);
        let written = if clause.ones.is_empty() { format!("(DET {name})") } else { format!("(DET {name} (ONE))") };
        RunFault { message: format!("`{written}` has no body and no proposer, so it gives no value: a fault of the conversion").into(), form: form.clone() }
    })
}

/// The message of the fault where the `DET` of `det` reads the pick of
/// `pick` and that pick has more than one model.
pub(super) fn many_models(driver: &Driver<'_, '_>, det: GraphNodeIndex, pick: &RelationName) -> String {
    let det = match &driver.program().graph.nodes[det.0 as usize].kind {
        DependencyKind::Parameter(ProgramRelation::Declared(name)) | DependencyKind::Chosen(name) => spelled(name),
        other => format!("{other:?}"),
    };
    format!("the `DET` of `{det}` reads the pick `{}`, which has more than one model, and a `DET` reads a pick only where the pick has one model", spelled(pick))
}

/// `name` as a file writes it, or its slot.
fn spelled(name: &RelationName) -> String {
    crate::program::declared_spelled(&name.0)
}

/// `relation` as a file writes it, `&marker.glyph` for an output, with a
/// slot for a name a decode gives no text.
pub fn relation_spelled(relation: &ProgramRelation) -> String {
    match relation {
        ProgramRelation::Declared(name) => spelled(name),
        ProgramRelation::Output(output) => crate::write::output_name(output, crate::program::declared_spelled),
    }
}

/// Whether the registry marks the proposer `name` as a type-domain proposer.
fn is_domain(registry: &Registry, name: &crate::registry::LibName) -> bool {
    matches!(registry.entry(name), Some(LibEntry::Proposer(Proposer { kind: ProposerKind::Native { domain: true }, .. })))
}
