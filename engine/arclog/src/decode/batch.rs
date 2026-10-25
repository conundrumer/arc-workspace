//! The batch form of a decode's step, as
//! `docs/engine/synthesis.md#decode-interface` gives it: many decodes, each
//! stepped by its own token, at once on the thread pool.

use std::panic::{catch_unwind, AssertUnwindSafe};

use super::{Advanced, Decoder, Refusal, StepResult};
use crate::eval::pool::Pool;
use crate::harness::panic_message;
use crate::stream::Token;

/// What a decode's step gives in [`step_batch`]: the [`StepResult`] of the
/// step, or, where the step panicked, the panic's message. A panic is no
/// [`Refusal`].
pub type BatchStep = Result<StepResult, String>;

/// Steps each of `decoders` by the token at its index in `tokens`, on
/// `pool`, and gives what each step gives, in the order of `decoders`, as
/// [`Decoder::step`] gives it for each decode alone.
///
/// A step that panics gives the panic's message in its decode's place and
/// leaves that decode at its state before the step; each other decode steps
/// as it would with no panic.
pub fn step_batch(pool: &Pool, decoders: &mut [Decoder<'_>], tokens: &[Token]) -> Box<[BatchStep]> {
    assert_eq!(decoders.len(), tokens.len(), "one token per decode");
    let pairs: Vec<(&Decoder<'_>, &Token)> = decoders.iter().zip(tokens).collect();
    let advanced: Vec<Result<Result<Advanced, Refusal>, String>> = pool.map(&pairs, |(decoder, token)| {
        catch_unwind(AssertUnwindSafe(|| decoder.advance(token))).map_err(|payload| panic_message(&*payload).unwrap_or("a payload that is not a message").to_string())
    });
    decoders.iter_mut().zip(advanced).map(|(decoder, advanced)| advanced.map(|advanced| decoder.apply(advanced))).collect()
}
