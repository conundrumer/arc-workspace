//! The batch form of a decode's step, as
//! `docs/engine/synthesis.md#decode-interface` gives it: many decodes, each
//! stepped by its own token, at once on the thread pool.

use super::{Decoder, StepResult};
use crate::eval::pool::Pool;
use crate::stream::Token;

/// Steps each of `decoders` by the token at its index in `tokens`, on
/// `pool`, and gives what each step gives, in the order of `decoders`, as
/// [`Decoder::step`] gives it for each decode alone.
pub fn step_batch(pool: &Pool, decoders: &mut [Decoder<'_>], tokens: &[Token]) -> Box<[StepResult]> {
    assert_eq!(decoders.len(), tokens.len(), "one token per decode");
    let pairs: Vec<(&Decoder<'_>, &Token)> = decoders.iter().zip(tokens).collect();
    let advanced = pool.map(&pairs, |(decoder, token)| decoder.advance(token));
    decoders.iter_mut().zip(advanced).map(|(decoder, advanced)| decoder.apply(advanced)).collect()
}
