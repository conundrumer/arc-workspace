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
        let dets = held_dets(program);
        let picks: Vec<_> = written.into_iter().filter(|det| det.pick).collect();
        // Keep this probe independent of prior cache contents, byte reservations,
        // cancellation, held stops and elapsed time. Its values never escape.
        // The probes of the task session share an intern table and the domains
        // they computed (`det_memo`). A probe whose session evicted or reached
        // the byte bound runs again in a session of its own.
        let scope = Scope {
            task: std::ptr::from_ref(self.task) as usize,
            registry: std::ptr::from_ref(self.context.registry) as usize,
            constructions: std::ptr::from_ref(self.constructions) as usize,
            table_work_cap: self.context.settings.table_work_cap,
        };
        let memo = self.session.det_probes().get_or_init(|| ProbeMemo::new(scope, self.session));
        if let Some(probe) = memo.probe(scope, self.session) {
            let domains = probe.domains(program, &dets);
            let verdict = self.live(program, &dets, &picks, root, &probe.session, Some(&domains));
            if !probe.session.results.evicted() && !matches!(verdict, Err(DetRefusal::Bound(ReachedBound::SessionBytes(_)))) {
                return verdict;
            }
        }
        let session = TaskSession::new(self.session.bound, self.session.caps);
        self.live(program, &dets, &picks, root, &session, None)
    }

    /// Whether some leaf of the walk of `dets` in `session` gives each of
    /// them a value and each of `picks` a model, with the domains from
    /// `domains` where it is given.
    #[allow(clippy::too_many_arguments)]
    fn live(&self, program: &CheckedProgram, dets: &[Det], picks: &[Det], root: GraphNodeIndex, session: &TaskSession, domains: Option<&dyn Domains>) -> Result<(), DetRefusal> {
        let limits = Limits::new(None, Cancellation::default())
            .counted_in(TableWork::new(self.context.settings.table_work_cap));
        let inputs = EvaluationInputs {
            program, concept: None, task: self.task, session,
            registry: self.context.registry, constructions: self.constructions, limits: &limits,
        };
        let mut live = false;
        let mut leaf = |evaluation: &crate::eval::Evaluation<'_>, assigned: &[_]| {
            // Undefined domains remain visible in the canonical walker as missing
            // bindings. A partial leaf cannot certify that the written DETs live.
            stats::units(Phase::DetLiveness, 1);
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
            Ok(()) if live => Ok(()),
            Ok(()) => Err(DetRefusal::NoLiveAssignment),
        }
    }
}
