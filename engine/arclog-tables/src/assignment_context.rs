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

/// One operation's full ordered interventions, gold origin and queried owner.
/// The owned receipt has a fresh identity; it is not a packed-row hash or a
/// reusable pointer to a dropped list. Its values use that operation's session.
#[derive(Debug)]
pub struct HeldAssignments {
    query: Arc<CheckedProgram>,
    origin: Arc<CheckedProgram>,
    values: Box<[Vec<Assignment>]>,
}

impl HeldAssignments {
    pub(crate) fn new(source: Arc<CheckedProgram>, origin: Arc<CheckedProgram>, values: &[Vec<Assignment>]) -> Outcome<Arc<Self>> {
        origin.check_held_det_interfaces(&source)?;
        // Validate carried identities as well as the full gold interface. The
        // untyped ParameterValues map cannot establish where rows originated.
        let names = arclog::decode::held_dets(&origin);
        for (name, _) in values.iter().flatten() {
            if !names.iter().any(|det| &det.relation == name) {
                origin.check_held_det_interface(&source, name)?;
            }
        }
        Ok(Arc::new(Self { query: source, origin, values: values.into() }))
    }

    pub(crate) fn parent_count(&self) -> usize { self.values.len() }

    fn validate(&self, target: &CheckedProgram) -> Outcome<()> {
        // The immutable queried owner was checked at construction. A query
        // against another program must establish the gold interface again.
        if !std::ptr::eq(self.query.as_ref(), target) {
            self.origin.check_held_det_interfaces(target)?;
        }
        Ok(())
    }
}

impl AssignmentLayout {
    pub(crate) fn full<'a>(&'a self, ordinal: usize, projected: &'a [Assignment]) -> Option<&'a [Assignment]> {
        match self { Self::Search => Some(projected), Self::Held(receipt) => receipt.values.get(ordinal).map(Vec::as_slice) }
    }

    /// Retained receipt bookkeeping, once per shared allocation. The source
    /// program and Relation allocations are already owned/accounted elsewhere.
    pub(crate) fn retained_bytes(&self, seen: &mut arclog::hash::StableHashSet<usize>) -> usize {
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
    examples_reusing(decoder, checked, scope, root, dets, work, context, None, at)
}

/// Reuse is admitted only by a caller with a complete native dependency
/// certificate. Held validation, limits and layout remain in this dispatcher.
pub(crate) fn examples_reusing(
    decoder: &Decoder<'_>, checked: &CheckedProgram, scope: arclog::eval::examples::ExampleScope,
    root: GraphNodeIndex, dets: &[Det], work: &TableWork, context: AssignmentContext<'_>,
    completed: Option<&[ExampleRows]>,
    at: &mut dyn FnMut(&Evaluation<'_>, Option<Example>) -> Result<Vec<RelationValue>, End>,
) -> Vec<ExampleRows> {
    let admission = match context {
        AssignmentContext::Search => Ok(()),
        AssignmentContext::Held {receipt, ..} => receipt.validate(checked),
    };
    decoder.examples_of(scope).into_iter().map(|example| {
        if let Err(fault) = &admission { return ExampleRows {example, rows: Err(fault.clone())}; }
        let rows = match context {
            AssignmentContext::Search => decoder.assigned(checked, root, dets, Some(work), &mut |evaluation| at(evaluation, example)),
            AssignmentContext::Held { receipt, limits, work } => {
                let (task, session, constructions) = decoder.evaluation_inputs();
                let limits = limits.clone().counted_in(work.clone());
                let form = checked.program.form_of(root);
                let mut found = Vec::new();
                let mut end = Ok(());
                let mut first_stop = None;
                for full in &receipt.values {
                    // Each assignment counts its work from none, and a stop of its own ends it alone.
                    let own = limits.for_assignment();
                    let mut budget = Budget::new(&own, session);
                    if let Err(bound) = budget.charge_work(0) {
                        end = Err(End::Stop(Stop { bound, form: form.clone() }));
                        break;
                    }
                    let projected = dets.iter().map(|det| {
                        full.iter().find(|(name, _)| name == &det.relation).cloned()
                            .ok_or_else(|| RunFault { message: format!("held assignment lacks required DET {:?}", det.relation).into(), form: form.clone() })
                    }).collect::<Outcome<Vec<_>>>();
                    let projected = match projected { Ok(values) => values, Err(fault) => { end = Err(End::Fault(fault)); break; } };
                    let reused = completed.and_then(|examples| examples.iter().find(|e| e.example == example))
                        .and_then(|example| example.rows.as_ref().ok())
                        .filter(|rows| rows.stop.is_none())
                        .and_then(|rows| completed_models(rows, &projected));
                    let value = reused.map_or_else(|| {
                        let parameters = ParameterValues::determined(full.clone());
                        let evaluation = Evaluation { program: checked, concept: None, task, session, constructions,
                            registry: decoder.registry(), parameters: &parameters, limits: &own };
                        at(&evaluation, example)
                    }, Ok);
                    match value {
                        Ok(value) => found.push((projected, value)),
                        Err(End::Stop(stop)) if stop.bound.is_assignment() => {
                            first_stop.get_or_insert_with(||stop.clone());
                            found.push((projected, vec![RelationValue::Stopped(stop)]));
                        }
                        Err(fault) => { end = Err(fault); break; }
                    }
                }
                match end {
                    Ok(()) => Ok(Assigned { at: found, stop: first_stop }),
                    Err(End::Stop(stop)) => Ok(Assigned { at: found, stop: Some(stop) }),
                    Err(End::Fault(fault)) => Err(fault),
                }
            }
        };
        ExampleRows { example, rows }
    }).collect()
}

// Compare the entire ordered model vector at every matching assignment. A
// stopped or contradictory candidate cannot certify the held query.
fn completed_models(rows: &Assigned<Vec<RelationValue>>, projected: &[Assignment]) -> Option<Vec<RelationValue>> {
    let mut matches = rows.at.iter().filter(|(assigned, _)| assigned.len() == projected.len()
        && assigned.iter().all(|(name, value)| projected.iter().find(|(held, _)| held == name)
            .is_some_and(|(_, held)| arclog::session::same_rows(value, held))));
    let (_, first) = matches.next()?;
    if first.iter().any(|value| matches!(value, RelationValue::Stopped(_))) { return None; }
    if !matches.all(|(_, models)| models.len() == first.len() && models.iter().zip(first).all(|(left, right)| match (left, right) {
        (RelationValue::Rows(left), RelationValue::Rows(right)) => arclog::session::same_rows(left, right),
        (RelationValue::Undefined, RelationValue::Undefined) => true,
        _ => false,
    })) { return None; }
    Some(first.clone())
}
