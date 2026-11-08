//! Admission of a completed DET or mark, using the determination's domain walk.
use std::ops::ControlFlow;

use super::det_memo::{part_key, PartWalk, ProbeMemo, Scope};
use super::{Decoder, Refusal, State};
use crate::check::CheckedProgram;
use crate::eval::carry::Carry;
use crate::eval::{Cancellation, Charged, Limits, ModelsEnd, ReachedBound, RelationValue, TableWork};
use crate::judge::determination::{descend_unread, held_dets, written_dets, Det, Domains, End, EvaluationInputs};
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
    /// The native walk reached a deterministic resource bound that the
    /// consistency test reads too.
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
            prefix_content_cap: self.context.settings.prefix_content_cap,
        }
    }

    pub(super) fn admit_written_dets(&self, token: &Token, after: &State) -> Result<(), Refusal> {
        if !matches!(token, Token::Control(Control::End | Control::Set | Control::One)) {
            return Ok(());
        }
        let Some(closed) = after.det_admission_state(&self.state, &self.context) else { return Ok(()) };
        let work = self.request_work();
        // The admission of a written `DET` is a prefix check: it runs in the scope where no count that cuts a result holds its work.
        let compute = || crate::eval::uncounted(|| self.det_liveness(&closed)).map_err(Refusal::DetAdmission);
        let form = closed.program().value().forms.last().expect("a closed DET");
        match super::prefix_key::key(form, None) {
            Some(key) => {
                let digest = stats::enabled().then(|| stats::digest(&key));
                self.state.cached_det_prefix(key, &|| !work.is_past_cap(), &work, self.session, || {
                    stats::seen(Phase::DetLiveness, || digest.unwrap_or(0));
                    compute()
                })
            }
            None => compute(),
        }
    }

    /// The verdict on the `DET`s of `closed`: a fault where the finished
    /// program does not check, and else, where the decode evaluates, the
    /// liveness walk's.
    fn det_liveness(&self, closed: &State) -> Result<(), DetRefusal> {
        let _timed = stats::span(Phase::DetLiveness);
        let program = self.finished_checked(&self.state, closed).as_ref()
            .map_err(|fault| DetRefusal::Fault(format!("{fault:?}")))?;
        if !self.evaluates {
            return Ok(());
        }
        let written = written_dets(program);
        let Some(root) = written.last().map(|det| det.node) else { return Ok(()) };
        if let Some(verdict) = self.verdict_past_cap(program, &written, root) {
            return verdict;
        }
        let dets = held_dets(program);
        let picks: Vec<_> = written.into_iter().filter(|det| det.pick).collect();
        match self.walked(program, &dets, &picks, root).1 {
            // These bounds limit the walk's time, its rows and its bytes.
            // Reaching one establishes no property of the program, so the
            // token is admitted and the decision falls to the form's end.
            // The assignment cap is the consistency test's cap too, and an
            // effort stop is a fault of the call, so both stand.
            Err(DetRefusal::Bound(bound)) if bound.is_resource() => Ok(()),
            verdict => verdict,
        }
    }

    /// The verdict on a program whose joint walk is larger than the
    /// assignment cap, from the walks of its parts, or `None` for a program
    /// that the joint walk must decide.
    ///
    /// The parts of [`independent_parts`] read none of each other's values,
    /// so the leaves of the joint walk are the product of the leaves of the
    /// parts, and a live leaf of each part together make a live leaf of the
    /// joint walk. A joint walk with a part with no leaf has no live leaf,
    /// and one with more leaves than the cap reaches no verdict but a
    /// refusal. The size of the walk is the product over the parts of the
    /// leaves of each, or one for a part with none: the joint walk of a part
    /// with no leaf counts no leaf toward the cap, and goes through each
    /// assignment of the `DET`s before it.
    fn verdict_past_cap(&self, program: &CheckedProgram, written: &[Det], root: GraphNodeIndex) -> Option<Result<(), DetRefusal>> {
        let parts = independent_parts(program, written);
        if parts.len() < 2 {
            return None;
        }
        let cap = self.context.settings.caps.assignments;
        let past = Err(DetRefusal::Bound(ReachedBound::Assignments { cap }));
        let acyclic = program.program.graph.find_cycle().is_none();
        let (mut size, mut stopped, mut empty, mut live): (u64, bool, bool, bool) = (1, false, false, true);
        for (dets, _) in &parts {
            match self.part(program, dets, &[], root, acyclic) {
                PartWalk::PastCap => return Some(past),
                PartWalk::Stopped => stopped = true,
                PartWalk::Ended { leaves, live: found } => {
                    size = size.saturating_mul(leaves.max(1));
                    empty |= leaves == 0;
                    live &= found;
                }
            }
        }
        if stopped || size <= cap {
            return None;
        }
        if empty {
            return Some(Err(DetRefusal::NoLiveAssignment));
        }
        let picked = |(dets, picks): &(Vec<Det>, Vec<Det>)| {
            picks.is_empty() || matches!(self.part(program, dets, picks, root, acyclic), PartWalk::Ended { live: true, .. })
        };
        Some(if live && parts.iter().all(picked) { Ok(()) } else { past })
    }

    /// What the walk of a part gives: its `DET`s `dets`, with `picks`. The
    /// memo keeps it for a program with no cycle, so that a form leaves the
    /// walks of the parts it does not touch to their first results.
    fn part(&self, program: &CheckedProgram, dets: &[Det], picks: &[Det], root: GraphNodeIndex, acyclic: bool) -> PartWalk {
        let scope = self.det_scope();
        let memo = self.session.det_probes().get_or_init(|| ProbeMemo::new(scope, self.session));
        let key = acyclic.then(|| part_key(program, dets, picks, self.context.settings.caps.assignments)).flatten();
        let work = self.request_work();
        // A kept walk charges the cost of the walk that was kept, unless that cost would pass the request's cap, where the part is walked again and stops where it stops with empty caches.
        if let Some(hit) = key.as_ref().and_then(|key| memo.part(scope, key)) {
            match hit.charge(&work, None, self.session) {
                Charged::Value(walk) => return walk,
                Charged::Stopped(..) => return PartWalk::Stopped,
                Charged::Misfit => {}
            }
        }
        // The admission of a written `DET` is a prefix check: its work counts as effort, and a hit on its walk charges its bytes and its effort alone, and notes again the content that the walk counted.
        let (walk, cost) = work.measure_owning(true, || crate::eval::uncounted(|| match self.walked(program, dets, picks, root) {
            (leaves, Ok(())) => PartWalk::Ended { leaves, live: true },
            (leaves, Err(DetRefusal::NoLiveAssignment)) => PartWalk::Ended { leaves, live: false },
            (_, Err(DetRefusal::Bound(ReachedBound::Assignments { .. }))) => PartWalk::PastCap,
            (_, Err(_)) => PartWalk::Stopped,
        }));
        let cost = cost.without_counts();
        // A walk that a stop at the request cap cut short is no walk of the part.
        if let Some(key) = key.filter(|_| !work.is_past_cap()) {
            memo.keep_part(scope, key, walk, cost);
        }
        walk
    }

    /// The leaves of the walk of `dets`, as [`Self::live`] gives them, and
    /// its verdict.
    fn walked(&self, program: &CheckedProgram, dets: &[Det], picks: &[Det], root: GraphNodeIndex) -> (u64, Result<(), DetRefusal>) {
        // Keep this probe independent of prior cache contents, byte reservations,
        // cancellation, held stops and elapsed time. Its values never escape.
        // The probes of the task session share an intern table and the domains
        // they computed (`det_memo`). A probe whose session evicted runs again
        // in a session of its own.
        let scope = self.det_scope();
        let memo = self.session.det_probes().get_or_init(|| ProbeMemo::new(scope, self.session));
        if let Some(probe) = memo.probe(scope, self.session) {
            let domains = probe.domains(program, dets);
            let walked = self.live(program, dets, picks, root, &probe.session, Some(&domains), Some(probe.carry()));
            if !probe.session.results.evicted() {
                return walked;
            }
        }
        let session = TaskSession::new(self.session.bound, self.session.caps);
        self.live(program, dets, picks, root, &session, None, None)
    }

    /// The leaves that the walk of `dets` in `session` reached, and its
    /// verdict: whether some leaf gives each of them a value and each of
    /// `picks` a model, with the domains from `domains` where it is given,
    /// and the computations of entries from `carry` where it is given.
    #[allow(clippy::too_many_arguments)]
    fn live(&self, program: &CheckedProgram, dets: &[Det], picks: &[Det], root: GraphNodeIndex, session: &TaskSession, domains: Option<&dyn Domains>, carry: Option<Carry>) -> (u64, Result<(), DetRefusal>) {
        let request = self.request_work();
        // The check counts its content under a cap of its own, inside the uncounted scope, where no other count adds.
        let prefix = TableWork::prefix(self.context.settings.prefix_content_cap, &request);
        let limits = Limits::new(None, Cancellation::default()).in_request(request).counted_in(prefix);
        let limits = match carry {
            Some(carry) => limits.carrying(carry),
            None => limits,
        };
        let inputs = EvaluationInputs {
            program, concept: None, task: self.task, session,
            registry: self.context.registry, constructions: self.constructions, limits: &limits,
        };
        let mut live = false;
        let mut leaf = |evaluation: &crate::eval::Evaluation<'_>, assigned: &[_], unassigned: usize| {
            // Undefined domains remain visible in the canonical walker as missing
            // bindings. A partial leaf cannot certify that the written DETs live.
            // A DET whose values no pick reads is left out of `assigned`, and
            // the walk counts it in `unassigned`.
            stats::units(Phase::DetLiveness, 1);
            if assigned.len() + unassigned != dets.len() { return Ok(()); }
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
        let (_, end, stop, leaves) = descend_unread(inputs, dets, picks, root, self.context.settings.caps.assignments, &mut leaf, domains);
        let verdict = match end {
            Err(End::Fault(fault)) => Err(DetRefusal::Fault(format!("{fault:?}"))),
            Err(End::Stop(found)) if matches!(found.bound, ReachedBound::Assignments { .. }) => Err(DetRefusal::Bound(found.bound)),
            _ if live => Ok(()),
            Ok(()) if stop.is_some() => Err(DetRefusal::Bound(stop.expect("a recorded stop").bound)),
            Err(End::Stop(found)) => Err(DetRefusal::Bound(if matches!(found.bound, ReachedBound::TableWork {..} | ReachedBound::RequestWork {..} | ReachedBound::RequestBytes {..}) {found.bound} else {stop.as_ref().map_or(found.bound, |stop|stop.bound)})),
            Ok(()) => Err(DetRefusal::NoLiveAssignment),
        };
        (leaves, verdict)
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
