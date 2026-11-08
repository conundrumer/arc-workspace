//! The batch form of a decode's step, as
//! `docs/engine/synthesis.md#decode-interface` gives it: many decodes, each
//! stepped by its own token, at once on the thread pool.

use std::panic::{catch_unwind, AssertUnwindSafe};

use super::{Advanced, Decoder, Refusal, StepResult};
use crate::eval::pool::Pool;
use crate::eval::{take_effort_fault, EffortFault};
use crate::harness::panic_message;
use crate::stream::Token;

/// Why a decode's step gives no [`StepResult`] in [`step_batch`]. Neither is a
/// [`Refusal`].
#[derive(Clone, PartialEq, Eq, Debug)]
pub enum BatchFault {
    /// The step panicked: the panic's message.
    Panic(String),
    /// The request of the step passed its effort guard.
    Effort(EffortFault),
}

/// What a decode's step gives in [`step_batch`]: the [`StepResult`] of the
/// step, or, where the step panicked or its request passed the effort guard,
/// that fault.
pub type BatchStep = Result<StepResult, BatchFault>;

/// Steps each of `decoders` by the token at its index in `tokens`, on
/// `pool`, and gives what each step gives, in the order of `decoders`, as
/// [`Decoder::step`] gives it for each decode alone.
///
/// A step that panics gives the panic's message in its decode's place, and a
/// step whose request passes the effort guard gives that fault; each leaves
/// its decode at its state before the step, and each other decode steps as it
/// would with no panic.
pub fn step_batch(pool: &Pool, decoders: &mut [Decoder<'_>], tokens: &[Token]) -> Box<[BatchStep]> {
    assert_eq!(decoders.len(), tokens.len(), "one token per decode");
    let pairs: Vec<(&Decoder<'_>, &Token)> = decoders.iter().zip(tokens).collect();
    let advanced: Vec<Result<Result<Advanced, Refusal>, BatchFault>> = pool.map(&pairs, |(decoder, token)| {
        // A fault that an earlier task on this thread left belongs to that task.
        let _ = take_effort_fault();
        let advanced = catch_unwind(AssertUnwindSafe(|| decoder.advance(token, true)))
            .map_err(|payload| BatchFault::Panic(panic_message(&*payload).unwrap_or("a payload that is not a message").to_string()))?;
        take_effort_fault().map_or(Ok(advanced), |fault| Err(BatchFault::Effort(fault)))
    });
    decoders.iter_mut().zip(advanced).map(|(decoder, advanced)| advanced.map(|advanced| decoder.apply(advanced))).collect()
}
