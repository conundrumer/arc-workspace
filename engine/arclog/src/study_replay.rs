//! Exact historical mutation replay, always re-certified by the engine.
//! A runtime check must not substitute a fresh draw for a logged identity.
use super::*;

impl StudyProgram {
    /// Replay uses the exact-source identity reader and certificate. Keep the
    /// supplied gold handle: decode-source recovery belongs to presentation
    /// reconstruction and cannot silently change the evaluator's gold owner.
    pub fn replay_spec(&self, identity: &Value, registry: &Registry, settings: &DecodeSettings) -> Result<MutationSpec, String> {
        let mutant = self.construct_identity_at_source(identity, registry, settings)?;
        mutant.audit()?;
        Ok(mutant.spec)
    }
}
