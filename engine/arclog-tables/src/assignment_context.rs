//! Assignment selection for native relation and body queries.
//!
//! Search walks the decoder's domains. A held query evaluates the original
//! full assignments, in order, and only then exposes the query's DET projection.
use super::*;
use arclog::eval::{Limits, ParameterValues, Stop};

/// Identity of the assignment order of one native table. No operation limits
/// or evaluator references are retained with a table.
#[derive(Clone, Debug, Default)]
pub enum AssignmentLayout {
    #[default]
    Search,
    Held(Arc<HeldAssignments>),
}

/// One operation's full ordered interventions and their checked source owner.
/// The owned receipt has a fresh identity; it is not a packed-row hash or a
/// reusable pointer to a dropped list. Its values use that operation's session.
#[derive(Debug)]
pub struct HeldAssignments {
    _source: Arc<CheckedProgram>,
    values: Box<[Vec<Assignment>]>,
}

impl HeldAssignments {
    pub(crate) fn new(source: Arc<CheckedProgram>, values: &[Vec<Assignment>]) -> Arc<Self> {
        Arc::new(Self { _source: source, values: values.into() })
    }
}

impl AssignmentLayout {
    pub(crate) fn full<'a>(&'a self, ordinal: usize, projected: &'a [Assignment]) -> Option<&'a [Assignment]> {
        match self { Self::Search => Some(projected), Self::Held(receipt) => receipt.values.get(ordinal).map(Vec::as_slice) }
    }

    /// Retained receipt bookkeeping, once per shared allocation. The source
    /// program and Relation allocations are already owned/accounted elsewhere.
    pub(crate) fn retained_bytes(&self, seen: &mut std::collections::HashSet<usize>) -> usize {
        let Self::Held(receipt) = self else {return 0};
        if !seen.insert(Arc::as_ptr(receipt) as usize) {return 0;}
        std::mem::size_of::<HeldAssignments>().saturating_add(2 * std::mem::size_of::<usize>())
            .saturating_add(receipt.values.len().saturating_mul(std::mem::size_of::<Vec<Assignment>>()))
            .saturating_add(receipt.values.iter().map(|v|v.capacity().saturating_mul(std::mem::size_of::<Assignment>())).sum::<usize>())
    }

    /// Select proof entries by their actual producer layout. A held receipt
    /// authorizes ordinals only within that same receipt. A searched table can
    /// prove a held query only when all its DETs match the full intervention.
    pub(crate) fn select<T>(&self, ordinal: usize, projected: &[Assignment], other: &Self, values: &Assigned<T>) -> Vec<usize> {
        match (self, other) {
            (Self::Held(left), Self::Held(right)) => {
                if Arc::ptr_eq(left, right) && ordinal < left.values.len() && ordinal < values.at.len() { vec![ordinal] } else { Vec::new() }
            }
            (Self::Held(receipt), Self::Search) => {
                let Some(full) = receipt.values.get(ordinal) else { return Vec::new() };
                values.at.iter().enumerate().filter(|(_, (required, _))| required.iter().all(|(name, value)| {
                    full.iter().find(|(own, _)| own == name).is_some_and(|(_, held)| arclog::session::same_rows(held, value))
                })).map(|(i, _)| i).collect()
            }
            (Self::Search, Self::Search) => values.at.iter().enumerate().filter(|(_, (candidate, _))| consistent(projected, candidate)).map(|(i, _)| i).collect(),
            (Self::Search, Self::Held(_)) => Vec::new(),
        }
    }
}

fn consistent(left: &[Assignment], right: &[Assignment]) -> bool {
    left.iter().all(|(name, value)| right.iter().find(|(own, _)| own == name).is_none_or(|(_, held)| arclog::session::same_rows(held, value)))
}

#[derive(Clone, Copy)]
pub(crate) enum AssignmentContext<'a> {
    Search,
    Held {
        receipt: &'a Arc<HeldAssignments>,
        limits: &'a Limits,
        work: &'a TableWork,
    },
}

impl AssignmentContext<'_> {
    pub(crate) fn layout(self) -> AssignmentLayout {
        match self { Self::Search => AssignmentLayout::Search, Self::Held { receipt, .. } => AssignmentLayout::Held(Arc::clone(receipt)) }
    }
}

/// The native query on each example, either at decoder-domain assignments or
/// at the full held interventions. Missing required DETs are faults; there is
/// no search fallback for a held assignment. Query schemas retain DET order.
pub(crate) fn examples(
    decoder: &Decoder<'_>, checked: &CheckedProgram, scope: arclog::eval::examples::ExampleScope,
    root: GraphNodeIndex, dets: &[Det], work: &TableWork, context: AssignmentContext<'_>,
    at: &mut dyn FnMut(&Evaluation<'_>, Option<Example>) -> Result<Vec<RelationValue>, End>,
) -> Vec<ExampleRows> {
    decoder.examples_of(scope).into_iter().map(|example| {
        let rows = match context {
            AssignmentContext::Search => decoder.assigned(checked, root, dets, Some(work), &mut |evaluation| at(evaluation, example)),
            AssignmentContext::Held { receipt, limits, work } => {
                let (task, session, constructions) = decoder.evaluation_inputs();
                let limits = limits.clone().counted_in(work.clone());
                let form = checked.program.form_of(root);
                let mut budget = Budget::new(&limits, session);
                let mut found = Vec::new();
                let mut end = Ok(());
                for full in &receipt.values {
                    if let Err(bound) = budget.charge_work(0) {
                        end = Err(End::Stop(Stop { bound, form: form.clone() }));
                        break;
                    }
                    let projected = dets.iter().map(|det| {
                        full.iter().find(|(name, _)| name == &det.relation).cloned()
                            .ok_or_else(|| RunFault { message: format!("held assignment lacks required DET {:?}", det.relation).into(), form: form.clone() })
                    }).collect::<Outcome<Vec<_>>>();
                    let projected = match projected { Ok(values) => values, Err(fault) => { end = Err(End::Fault(fault)); break; } };
                    let parameters = ParameterValues::determined(full.clone());
                    let evaluation = Evaluation { program: checked, concept: None, task, session, constructions,
                        registry: decoder.registry(), parameters: &parameters, limits: &limits };
                    match at(&evaluation, example) {
                        Ok(value) => found.push((projected, value)),
                        Err(fault) => { end = Err(fault); break; }
                    }
                }
                match end {
                    Ok(()) => Ok(Assigned { at: found, stop: None }),
                    Err(End::Stop(stop)) => Ok(Assigned { at: found, stop: Some(stop) }),
                    Err(End::Fault(fault)) => Err(fault),
                }
            }
        };
        ExampleRows { example, rows }
    }).collect()
}
