//! The determinations of a case program from the evidence, as
//! `docs/engine/determination.md#det` gives them: the `DET` nodes in
//! dependency order, and the candidates of each, which an evaluation at
//! determined values reads.
//!
//! A `DET` reads a pick, or the relation of a `DEMONSTRATED` form, only
//! where that relation has one model, on each example where the read is
//! lifted, so the candidates are computed outside any enumeration of
//! models.

use std::sync::Arc;

use super::driver::{derivation, Driver};
use super::join;
use super::{Evaluation, Outcome, RelationValue, RunFault, Stop};
use crate::check::CheckedProgram;
use crate::program::path::{node_at, NodePath, NodeRef};
use crate::program::{Clause, ClauseKeyword, DeclaredName, ProgramRelation, RelationName};
use crate::registry::{LibEntry, Proposer, ProposerKind, Registry};
use crate::relations::{Relation, Row, RowSet};
use crate::resolver::{DependencyKind, GraphNodeIndex};
use crate::types::GraphRelation;

/// The candidates of a `DET`, or the value of a read of its forms that is
/// `undefined` or stopped, as [`super::picks::Pick`] gives a pick's.
#[derive(Clone, Debug)]
pub enum Candidates {
    /// Each candidate as rows of the `DET`'s relation, each once, in the
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

impl Evaluation<'_> {
    /// The candidates of the `DET` node `node`, task-wide, at the values
    /// these parameter values give the `DET`s its forms read.
    ///
    /// A form derives by the rule of `derivation`, which `Driver::clause`
    /// uses. A form with a body gives one candidate, its rows; a form with no
    /// body, by the proposer that rule gives, one candidate of the proposer's
    /// whole set of rows, or one candidate per row where the registry marks
    /// that proposer domain. A `DET` form with no body that names several
    /// proposers, the stored reading of a `DET_OR_RULE` line with several,
    /// gives the candidates of each proposer by that rule, its rows mapped by
    /// position onto the relation's columns. A `DET` of several forms has the
    /// candidates that each of its forms gives. A form with no body and no
    /// proposer is a fault of the conversion.
    pub fn candidates(&self, node: GraphNodeIndex) -> Outcome<Candidates> {
        let program = &self.program.program;
        assert!(is_det(program, node), "the node of a `DET`");
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
                    Err(RelationValue::Undefined) => return Ok(Candidates::Undefined),
                    Err(RelationValue::Stopped(stop)) => return Ok(Candidates::Stopped(stop)),
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
                Some(kept) => kept.into_iter().filter(|candidate| found.contains(candidate)).collect(),
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
        let candidates = kept.into_iter().map(|rows| {
            let mut set = RowSet::empty(types.len() as u16);
            for row in rows {
                set.insert(row);
            }
            Arc::new(join::one_part(set))
        });
        Ok(Candidates::Rows(candidates.collect()))
    }
}

/// The fault of the `DET` form `clause` at `form` where it has no body and no
/// proposer, `(DET &x)` or `(DET &x (ONE))`: such a form gives no value, and
/// is a fault of the conversion.
pub(super) fn conversion_fault(clause: &Clause, form: &NodePath) -> Option<RunFault> {
    let empty = clause.keyword == ClauseKeyword::Det && clause.proposers.is_empty() && clause.body.value().conjuncts.is_empty();
    empty.then(|| {
        let name = match &clause.derives {
            ProgramRelation::Declared(name) => spelled(name),
            ProgramRelation::Output(output) => format!("{output:?}"),
        };
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
    match &name.0 {
        DeclaredName::Written(text) => text.to_string(),
        DeclaredName::Slot(slot) => format!("slot {slot}"),
    }
}

/// Whether the registry marks the proposer `name` as a domain proposer.
fn is_domain(registry: &Registry, name: &crate::registry::LibName) -> bool {
    matches!(registry.entry(name), Some(LibEntry::Proposer(Proposer { kind: ProposerKind::Native { domain: true }, .. })))
}
