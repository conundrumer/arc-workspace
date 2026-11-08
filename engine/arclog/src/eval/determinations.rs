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
use crate::registry::Registry;
use crate::resolver::registry_columns::{is_domain, proposer_columns};
use crate::relations::{Relation, Row, RowSet};
use crate::stats::{self, Phase};
use crate::resolver::{DependencyKind, GraphNodeIndex};
use crate::types::{GraphRelation, ValueType};

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

/// How many values the domain of a `DET` has, or the value of a read of its
/// forms that is `undefined` or stopped, as [`Domain`] gives it.
#[derive(Clone, Debug)]
pub enum DomainSize {
    Count(usize),
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

/// Whether `node` is a `DET` by its clauses: each of its forms is a `DET`
/// clause with a body, no proposer and no `ONE` mark.
pub(crate) fn is_by_clauses(program: &crate::resolver::ResolvedProgram, node: GraphNodeIndex) -> bool {
    let root = NodeRef::Program(program.program.value());
    let forms = program.forms_of(node);
    !forms.is_empty()
        && forms.iter().all(|at| {
            let Some(NodeRef::Clause(clause)) = node_at(root, at) else { return false };
            clause.keyword == ClauseKeyword::Det
                && !clause.body.value().conjuncts.is_empty()
                && clause.proposers.is_empty()
                && clause.ones.is_empty()
        })
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

impl super::ParameterValues {
    /// A digest for the statistics ([`crate::stats::seen`]) of the identity of
    /// the determined values: the same for the same `Arc`s under the same
    /// names, whatever the order of the map.
    fn stats_digest(&self) -> u64 {
        match &self.source {
            super::ParameterSource::Determined(values) => values.iter().fold(0, |sum: u64, (name, rows)| sum.wrapping_add(stats::digest(&(name, Arc::as_ptr(rows) as usize)))),
            super::ParameterSource::Stored { .. } => 0,
        }
    }
}

impl Evaluation<'_> {
    /// The rows of each `DET` of the program that no record gives at these
    /// values and that has one value here: a `DET` by its clauses, and a `DET`
    /// with no record. A `DET` that ends in `(ONE)`, or whose domain faults,
    /// stops or has no one value, has none.
    pub fn determination_rows(&self) -> Vec<(ProgramRelation, Arc<Relation>)> {
        let program = &self.program.program;
        let mut rows = Vec::new();
        for node in determinations(self.program) {
            let Some((relation, false)) = det_relation(&program.graph.nodes[node.0 as usize].kind) else { continue };
            if self.parameters.get(&relation).is_some() && !is_by_clauses(program, node) {
                continue;
            }
            if let Ok(Domain::Rows(values)) = self.domain(node) {
                if let [value] = &values[..] {
                    rows.push((relation, value.clone()));
                }
            }
        }
        rows
    }

    /// The domain of the `DET` node `node`, task-wide, at the values
    /// these parameter values give the `DET`s its forms read. A `DET` that
    /// the case program takes from the concept program is evaluated there.
    ///
    /// A form derives by the rule of `derivation`, which `Driver::clause`
    /// uses. A form with a body gives one value, its rows; a form with no
    /// body, by the proposer that rule gives, one value per row where the
    /// registry marks that proposer type-domain or the proposer has one
    /// column and the form carries no `(SET)` mark, and otherwise one value
    /// of the proposer's whole set of rows. A form with no body that names
    /// several proposers is a fault, as that rule gives: each stored reading
    /// of a `DET_OR_RULE` line with several names its own proposer alone. A
    /// `DET` of several forms has the values that each of its forms gives as
    /// its domain. A form with no body and no proposer is a fault of the
    /// conversion.
    pub fn domain(&self, node: GraphNodeIndex) -> Outcome<Domain> {
        let program = &self.program.program;
        assert!(is_det(program, node), "the node of a `DET`");
        if let Some((concept, node)) = self.in_concept(node) {
            return concept.domain(node);
        }
        let _timed = stats::span(Phase::EvalDomain);
        stats::seen(Phase::EvalDomain, || stats::digest(&(node.0, self.parameters.stats_digest())));
        let (mut kept, types) = match self.gather(node, Order::Content)? {
            Gathered::Sets { kept, types } => (kept, types),
            Gathered::Count(_) => unreachable!("a gather in content order reads the rows"),
            Gathered::Undefined => return Ok(Domain::Undefined),
            Gathered::Stopped(stop) => return Ok(Domain::Stopped(stop)),
        };
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

    /// The count of values in the domain of the `DET` node `node`: the length
    /// of the `Rows` that [`Evaluation::domain`] gives, or the `undefined` or
    /// the stop that it gives.
    ///
    /// The evaluation of the forms is that of `domain`. It makes the same
    /// lookups, ids and stores in the session and counts the same table work,
    /// and a fault or a stop comes at the same place. It skips the steps
    /// that `domain` takes after that, which read no session and count no
    /// work: the order of the values by content, and the build of the
    /// relation of each value. A walk asks for the count where no later step
    /// reads the values of the `DET` ([`crate::judge::determination::descend_unread`]),
    /// so no step reads the values that it skips.
    ///
    /// The count does not depend on the order of the rows. Each form gives
    /// its values as sets of rows with each row once, and the forms give a
    /// value where each gives the same rows, so the rows of a value stand in
    /// the order of their terms' encodings, which keeps equal rows equal.
    ///
    /// A `DET` of one form has the count of one, or of the rows of the form
    /// where it gives each row as a value, so its rows are not read out and
    /// not put in order.
    pub fn domain_size(&self, node: GraphNodeIndex) -> Outcome<DomainSize> {
        let program = &self.program.program;
        assert!(is_det(program, node), "the node of a `DET`");
        if let Some((concept, node)) = self.in_concept(node) {
            return concept.domain_size(node);
        }
        let _timed = stats::span(Phase::EvalDomain);
        stats::seen(Phase::EvalDomain, || stats::digest(&(node.0, self.parameters.stats_digest())));
        Ok(match self.gather(node, Order::Id)? {
            Gathered::Sets { kept, .. } => DomainSize::Count(kept.len()),
            Gathered::Count(count) => DomainSize::Count(count),
            Gathered::Undefined => DomainSize::Undefined,
            Gathered::Stopped(stop) => DomainSize::Stopped(stop),
        })
    }

    /// The values of the domain of the `DET` node `node` that has no concept
    /// program's form, each as its rows, each value once, in no order, with
    /// the columns' types. The rows of each value are in `order`, which is
    /// the same for each form, so that two values are equal where their rows
    /// are.
    fn gather(&self, node: GraphNodeIndex, order: Order) -> Outcome<Gathered<'_>> {
        let program = &self.program.program;
        let relation = GraphRelation { node, output: None };
        let types = self.program.types.columns(&relation).ok_or_else(|| RunFault {
            message: "the `DET`'s columns have no types".into(),
            form: program.form_of(node).clone(),
        })?;
        let driver = Driver::reading_det(self, node);
        let root = NodeRef::Program(program.program.value());
        let mut kept: Option<Vec<Vec<Row>>> = None;
        let single = matches!(order, Order::Id) && program.forms_of(node).len() == 1;
        for at in program.forms_of(node) {
            let Some(NodeRef::Clause(clause)) = node_at(root, at) else { panic!("a clause of a `DET`") };
            if let Some(fault) = conversion_fault(clause, at) {
                return Err(fault);
            }
            let fault = |message: String| RunFault { message: message.into(), form: at.clone() };
            let domain = derivation(clause, at)?.is_some_and(|index| per_row(self.registry, clause, &clause.proposers[index]));
            if single {
                // The values of the one form are its rows, each as a value of
                // its own where `domain`, and otherwise all as one value. A
                // relation holds each row once, so the count is that of its rows.
                let read = driver.clause(at, None)?;
                return match super::init_form::relation_read(self, at, read, types.len()).map_err(fault)? {
                    Ok(relation) => {
                        let rows = usize::try_from(relation.len()).unwrap_or(usize::MAX);
                        if stats::enabled() {
                            stats::units(Phase::EvalDomain, rows);
                        }
                        Ok(Gathered::Count(if domain { rows } else { 1 }))
                    }
                    Err(RelationValue::Undefined) => Ok(Gathered::Undefined),
                    Err(RelationValue::Stopped(stop)) => Ok(Gathered::Stopped(stop)),
                    Err(RelationValue::Rows(_)) => unreachable!("a value that holds no rows"),
                };
            }
            let mut rows = match super::init_form::rows_of(self, at, driver.clause(at, None)?, types.len()).map_err(fault)? {
                Ok(rows) => rows,
                Err(RelationValue::Undefined) => return Ok(Gathered::Undefined),
                Err(RelationValue::Stopped(stop)) => return Ok(Gathered::Stopped(stop)),
                Err(RelationValue::Rows(_)) => unreachable!("a value that holds no rows"),
            };
            match order {
                Order::Content => {
                    let table = self.session.intern.read().expect("an intern table that no panic poisoned");
                    rows.sort_by(|a, b| crate::terms::content_order(types, a, b, &table));
                }
                Order::Id => rows.sort_unstable_by(|a, b| a.iter().map(|term| term.encoding()).cmp(b.iter().map(|term| term.encoding()))),
            }
            rows.dedup();
            let found: Vec<Vec<Row>> = if domain { rows.into_iter().map(|row| vec![row]).collect() } else { vec![rows] };
            kept = Some(match kept {
                None => found,
                Some(kept) => kept.into_iter().filter(|value| found.contains(value)).collect(),
            });
        }
        let kept = kept.expect("a `DET` node with a form");
        if stats::enabled() {
            stats::units(Phase::EvalDomain, kept.iter().map(Vec::len).sum());
        }
        Ok(Gathered::Sets { kept, types })
    }
}

/// How the rows of one value are put in order, so that two values are
/// equal where their rows are.
#[derive(Clone, Copy)]
enum Order {
    /// By `crate::terms::content_order`, the order of a value's rows in a
    /// domain.
    Content,
    /// By the encodings of the terms, which needs no read of the intern
    /// table.
    Id,
}

/// What the forms of a `DET` give: the values of its domain, each as its
/// rows, in no order, each once, or the `undefined` or the stop of a read.
enum Gathered<'t> {
    Sets { kept: Vec<Vec<Row>>, types: &'t [ValueType] },
    /// The count of the values of a `DET` of one form, which a gather in
    /// the order of the encodings gives with no read of the rows.
    Count(usize),
    Undefined,
    Stopped(Stop),
}

/// The fault of the `DET` form `clause` at `form` where it has no body and no
/// proposer, `(DET &x)` or `(DET &x (ONE))`: such a form gives no value, and
/// is a fault of the conversion.
pub(crate) fn conversion_fault(clause: &Clause, form: &NodePath) -> Option<RunFault> {
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

/// Whether the form `clause` takes one value per row of its proposer `name`:
/// the registry marks the proposer type-domain, or the proposer has one
/// column and the form carries no `(SET)` mark.
fn per_row(registry: &Registry, clause: &Clause, name: &crate::registry::LibName) -> bool {
    is_domain(registry, name) || (!clause.set && proposer_columns(registry, name).is_some_and(|columns| columns.len() == 1))
}
