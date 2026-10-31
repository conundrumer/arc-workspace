//! Admission of a completed DET or mark, using the determination's domain walk.
use std::ops::ControlFlow;

use super::det_memo::{ProbeMemo, Scope};
use super::{Decoder, Refusal, State};
use crate::check::CheckedProgram;
use crate::eval::{Cancellation, Limits, ModelsEnd, ReachedBound, RelationValue, TableWork};
use crate::judge::determination::{descend_with, held_dets, written_dets, Det, Domains, End, EvaluationInputs};
use crate::resolver::GraphNodeIndex;
use crate::session::TaskSession;
use crate::stats::{self, Phase};
use crate::stream::{Control, Token};
use crate::types::GraphRelation;

/// Why a closing DET token has no admission certificate.
#[derive(Clone, PartialEq, Eq, Debug)]
pub enum DetRefusal {
    /// No leaf gives every assignable DET a value and every pick a model.
    NoLiveAssignment,
    /// The native walk reached a deterministic resource bound.
    Bound(ReachedBound),
    /// A native check or evaluation failed.
    Fault(String),
}

impl Decoder<'_> {
    /// What the computation of a `DET`'s domain in this decode reads beside
    /// its key, for the memos of [`super::det_memo`].
    pub(super) fn det_scope(&self) -> Scope {
        Scope {
            task: std::ptr::from_ref(self.task) as usize,
            registry: std::ptr::from_ref(self.context.registry) as usize,
            constructions: std::ptr::from_ref(self.constructions) as usize,
            table_work_cap: self.context.settings.table_work_cap,
        }
    }

    pub(super) fn admit_written_dets(&self, token: &Token, after: &State) -> Result<(), Refusal> {
        if !matches!(token, Token::Control(Control::End | Control::Set | Control::One)) {
            return Ok(());
        }
        let Some(closed) = after.det_admission_state(&self.state, &self.context) else { return Ok(()) };
        let compute = || self.det_liveness(&closed).map_err(Refusal::DetAdmission);
        let form = closed.program().value().forms.last().expect("a closed DET");
        match super::prefix_key::key(form, None) {
            Some(key) => {
                let digest = stats::enabled().then(|| stats::digest(&key));
                self.state.cached_det_prefix(key, || {
                    stats::seen(Phase::DetLiveness, || digest.unwrap_or(0));
                    compute()
                })
            }
            None => compute(),
        }
    }

    fn det_liveness(&self, closed: &State) -> Result<(), DetRefusal> {
        let _timed = stats::span(Phase::DetLiveness);
        let program = self.finished_checked(&self.state, closed).as_ref()
            .map_err(|fault| DetRefusal::Fault(format!("{fault:?}")))?;
        let written = written_dets(program);
        let Some(root) = written.last().map(|det| det.node) else { return Ok(()) };
        if self.live_past_cap(program, &written, root) {
            return Ok(());
        }
        let dets = held_dets(program);
        let picks: Vec<_> = written.into_iter().filter(|det| det.pick).collect();
        self.walked(program, &dets, &picks, root).map(|_| ())
    }

    /// Whether the joint walk of `written`, the `DET`s of `program`, has
    /// more leaves than the assignment cap, and one of them is live.
    ///
    /// The parts of [`independent_parts`] read none of each other's values,
    /// so the leaves of the joint walk are the product of the leaves of the
    /// parts, and a live leaf of each part together make a live leaf of the
    /// joint walk. A joint walk with more leaves than the cap reaches no
    /// verdict but a refusal, so this gives `true` only for a program whose
    /// joint walk is refused, and every other program takes the verdict of
    /// the joint walk.
    fn live_past_cap(&self, program: &CheckedProgram, written: &[Det], root: GraphNodeIndex) -> bool {
        let parts = independent_parts(program, written);
        if parts.len() < 2 {
            return false;
        }
        let mut leaves: u64 = 1;
        for (dets, _) in &parts {
            let Ok(count) = self.walked(program, dets, &[], root) else { return false };
            leaves = leaves.saturating_mul(count);
        }
        leaves > self.context.settings.caps.assignments
            && parts.iter().all(|(dets, picks)| picks.is_empty() || self.walked(program, dets, picks, root).is_ok())
    }

    /// The leaves of the walk of `dets`, with a live leaf among them, as
    /// [`Self::live`] gives them.
    fn walked(&self, program: &CheckedProgram, dets: &[Det], picks: &[Det], root: GraphNodeIndex) -> Result<u64, DetRefusal> {
        // Keep this probe independent of prior cache contents, byte reservations,
        // cancellation, held stops and elapsed time. Its values never escape.
        // The probes of the task session share an intern table and the domains
        // they computed (`det_memo`). A probe whose session evicted or reached
        // the byte bound runs again in a session of its own.
        let scope = self.det_scope();
        let memo = self.session.det_probes().get_or_init(|| ProbeMemo::new(scope, self.session));
        if let Some(probe) = memo.probe(scope, self.session) {
            let domains = probe.domains(program, dets);
            let verdict = self.live(program, dets, picks, root, &probe.session, Some(&domains));
            if !probe.session.results.evicted() && !matches!(verdict, Err(DetRefusal::Bound(ReachedBound::SessionBytes(_)))) {
                return verdict;
            }
        }
        let session = TaskSession::new(self.session.bound, self.session.caps);
        self.live(program, dets, picks, root, &session, None)
    }

    /// The leaves of the walk of `dets` in `session`, where some leaf gives
    /// each of them a value and each of `picks` a model, with the domains
    /// from `domains` where it is given.
    #[allow(clippy::too_many_arguments)]
    fn live(&self, program: &CheckedProgram, dets: &[Det], picks: &[Det], root: GraphNodeIndex, session: &TaskSession, domains: Option<&dyn Domains>) -> Result<u64, DetRefusal> {
        let limits = Limits::new(None, Cancellation::default())
            .counted_in(TableWork::new(self.context.settings.table_work_cap));
        let inputs = EvaluationInputs {
            program, concept: None, task: self.task, session,
            registry: self.context.registry, constructions: self.constructions, limits: &limits,
        };
        let mut live = false;
        let mut leaves = 0;
        let mut leaf = |evaluation: &crate::eval::Evaluation<'_>, assigned: &[_]| {
            // Undefined domains remain visible in the canonical walker as missing
            // bindings. A partial leaf cannot certify that the written DETs live.
            stats::units(Phase::DetLiveness, 1);
            leaves += 1;
            if assigned.len() != dets.len() { return Ok(()); }
            for pick in picks {
                let mut found = false;
                let mut stop = None;
                let relation = GraphRelation { node: pick.node, output: None };
                let end = evaluation.models(&relation, None, &mut |value| {
                    match value {
                        RelationValue::Rows(_) => found = true,
                        RelationValue::Stopped(bound) => stop = Some(bound.clone()),
                        RelationValue::Undefined => {},
                    }
                    ControlFlow::Continue(())
                }).map_err(End::Fault)?;
                if let ModelsEnd::Stopped(bound) = end { stop = Some(bound); }
                if let Some(bound) = stop { return Err(End::Stop(bound)); }
                if !found { return Ok(()); }
            }
            live = true;
            Ok(())
        };
        match descend_with(inputs, dets, root, self.context.settings.caps.assignments, &mut leaf, domains).1 {
            Err(End::Fault(fault)) => Err(DetRefusal::Fault(format!("{fault:?}"))),
            Err(End::Stop(stop)) => Err(DetRefusal::Bound(stop.bound)),
            Ok(()) if live => Ok(leaves),
            Ok(()) => Err(DetRefusal::NoLiveAssignment),
        }
    }
}

/// `written`, the `DET`s of `program`, in parts, each with its `DET`s to walk
/// and its picks, in the order of `written`. Two `DET`s stand in one part
/// where one reads the other at any depth, so no `DET` of a part reads a
/// `DET` of another.
fn independent_parts(program: &CheckedProgram, written: &[Det]) -> Vec<(Vec<Det>, Vec<Det>)> {
    let mut part: Vec<usize> = (0..written.len()).collect();
    for (at, det) in written.iter().enumerate() {
        let reached = program.program.graph.reached(det.node);
        for (other, read) in written.iter().enumerate() {
            let (kept, merged) = (part[at], part[other]);
            if reached[read.node.0 as usize] && kept != merged {
                part.iter_mut().filter(|held| **held == merged).for_each(|held| *held = kept);
            }
        }
    }
    let mut parts: Vec<(usize, Vec<Det>, Vec<Det>)> = Vec::new();
    for (det, id) in written.iter().zip(part) {
        let at = parts.iter().position(|held| held.0 == id).unwrap_or_else(|| {
            parts.push((id, Vec::new(), Vec::new()));
            parts.len() - 1
        });
        if det.pick { parts[at].2.push(det.clone()) } else { parts[at].1.push(det.clone()) }
    }
    parts.into_iter().map(|(_, dets, picks)| (dets, picks)).collect()
}
