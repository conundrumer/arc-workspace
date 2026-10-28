//! Read an already complete stream with the decoder's grammar and binder.
//!
//! Online synthesis asks whether an unfinished prefix has some completion.
//! A complete-program reader instead builds that completion and submits it
//! to the whole-program checker. Re-running the prefix completion search
//! at every token is redundant and can be quadratic/exponential in the
//! prefix size. No grammar, label binding, cap, or engine-echo check is
//! omitted here. This reader returns an unchecked AST; StudyProgram checks
//! it and its derived interfaces before exposing a program handle.
use super::{Context, state::State};
use crate::program::{Node, Program};
use crate::registry::Registry;
use crate::stream::{DecodeSettings, Vocabulary};
use std::time::Instant;

/// One fixed registry/settings context; at most 64 parsed-prefix snapshots
/// from the preceding stream are retained. It holds no task/evaluation data.
pub struct ProgramReader<'r> {
    context: Context<'r>,
    ids: Vec<u32>,
    model: Vec<u8>,
    checkpoints: Vec<(usize, State)>,
}
impl<'r> ProgramReader<'r> {
    pub fn new(registry: &'r Registry, settings: DecodeSettings) -> Self {
        Self {
            context: Context {
                registry,
                settings,
                vocabulary: Vocabulary::new(registry, &settings),
            },
            ids: Vec::new(),
            model: Vec::new(),
            checkpoints: Vec::new(),
        }
    }
    pub fn read(&mut self, ids: &[u32], model: &[u8]) -> Result<Node<Program>, String> {
        if ids.len() != model.len() || model.iter().any(|flag| *flag > 1) {
            return Err("equal-length ids/model arrays and flags 0/1 required".into());
        }
        let common = ids
            .iter()
            .zip(model)
            .zip(self.ids.iter().zip(&self.model))
            .take_while(|(a, b)| a == b)
            .count();
        let mut snapshots: Vec<_> = self
            .checkpoints
            .iter()
            .filter(|(i, _)| *i <= common)
            .cloned()
            .collect();
        let (mut index, mut state) = snapshots
            .last()
            .cloned()
            .unwrap_or_else(|| (0, State::new()));
        let stride = ids.len().div_ceil(63).max(32);
        let mut checkpoint = index + stride;
        let started = Instant::now();
        while index < ids.len() {
            if self
                .context
                .settings
                .deadline
                .is_some_and(|limit| started.elapsed() >= limit)
            {
                return Err("program stream reader reached Deadline".into());
            }
            if model[index] != 1 {
                return Err(format!("unexpected engine token at {index}"));
            }
            let token = self
                .context
                .vocabulary
                .token(ids[index])
                .ok_or_else(|| format!("no vocabulary token {} at {index}", ids[index]))?;
            // This is the same resolver rule that the decoder uses to insert
            // a lifted Example column; no type/prefix-completion inference.
            let reads_example = |program: &Node<Program>,
                                 at: &crate::program::path::NodePath,
                                 _: &crate::program::RelationRef| {
                let earlier = state.resolved(self.context.registry);
                let resolved =
                    crate::resolver::resolve_last(&earlier, program, self.context.registry);
                crate::stream::write::reads_example_column(&resolved, at)
            };
            let (next, forced, _) = state
                .step(&self.context, token, &reads_example)
                .map_err(|e| format!("grammar at token {index}: {e}"))?;
            let end = index + 1 + forced.len();
            if end > ids.len() {
                return Err(format!("truncated engine echo at {index}"));
            }
            for (offset, expected) in forced.iter().enumerate() {
                let i = index + 1 + offset;
                if self.context.vocabulary.id(expected) != Some(ids[i]) || model[i] != 0 {
                    return Err(format!("engine echo mismatch after model token {index}"));
                }
            }
            state = next;
            index = end;
            if index >= checkpoint {
                snapshots.push((index, state.clone()));
                checkpoint = index + stride;
            }
        }
        if !matches!(state.partial(), Some((_, None))) {
            return Err("stream ends inside an unfinished program form".into());
        }
        let program = state.program().clone();
        if snapshots.len() > 64 {
            let step = snapshots.len().div_ceil(64);
            snapshots = snapshots.into_iter().step_by(step).collect();
        }
        self.ids = ids.to_vec();
        self.model = model.to_vec();
        self.checkpoints = snapshots;
        Ok(program)
    }
}
