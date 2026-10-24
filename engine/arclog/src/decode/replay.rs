//! The replay of a case program's token stream through a decoder, which
//! `arclog-cli decode` and the walk of [`super::corpus`] share: each token the model emits is checked
//! against the mask and stepped, each token the engine emits is checked
//! against the tokens the step before forced, and the caller's code runs
//! after each step of a token the model emits.

use std::ops::ControlFlow;
use std::time::Instant;

use super::{Consistency, Decoder, TokenMask};
use crate::check::CheckedProgram;
use crate::resolver::DependencyKind;
use crate::stream::{Emitter, Token};

/// The step of a token the model emitted.
pub struct Stepped<'a> {
    /// The token's index in the stream.
    pub index: usize,
    pub token: &'a Token,
    /// The tokens that were admissible before the step.
    pub mask: &'a TokenMask,
    /// The consistency the step gives, if it ends a `RULE` clause.
    pub consistency: Option<Consistency>,
    /// The seconds of the token mask, and of the step.
    pub mask_seconds: f64,
    pub step_seconds: f64,
}

/// The refusal that stops a replay: the index of the stream's token that the
/// decoder refuses, or that the engine emits against the tokens the step
/// before forced, with the line that says why.
#[derive(Clone, Debug)]
pub struct Refused {
    pub index: usize,
    pub message: String,
}

/// What a replay left: the tokens the engine forces after its last step.
pub struct Replayed {
    forced: Vec<Token>,
}

impl Replayed {
    /// The tokens the engine forces after the last step.
    pub fn forced(&self) -> &[Token] {
        &self.forced
    }

    /// The refusal where the replay ended while the engine forces tokens.
    pub fn unfinished(&self) -> Option<String> {
        (!self.forced.is_empty()).then(|| format!("the stream ends while the engine forces {:?}", self.forced))
    }
}

/// Steps `decoder` through `stream`, and calls `after` with the decoder and
/// the step, after each step of a token the model emits; the replay ends
/// early where `after` gives [`ControlFlow::Break`]. Gives the line of the
/// first token the decoder refuses, or that the engine emits against the
/// tokens the step before forced.
pub fn replay(decoder: &mut Decoder<'_>, stream: &[(Token, Emitter)], after: &mut dyn FnMut(&Decoder<'_>, Stepped<'_>) -> ControlFlow<()>) -> Result<Replayed, String> {
    replay_from(decoder, stream, 0, Vec::new(), after).map_err(|refused| refused.message)
}

/// As [`replay`], from the token at position `start` of `stream`, where
/// `decoder` has stepped the tokens before it and the engine still forces
/// `forced` there. The indices that `after` and the faults give are those
/// of `stream`, and the refusal gives the index of its token.
pub fn replay_from(
    decoder: &mut Decoder<'_>,
    stream: &[(Token, Emitter)],
    start: usize,
    forced: Vec<Token>,
    after: &mut dyn FnMut(&Decoder<'_>, Stepped<'_>) -> ControlFlow<()>,
) -> Result<Replayed, Refused> {
    let mut forced = forced;
    for (index, (token, emitter)) in stream.iter().enumerate().skip(start) {
        match emitter {
            Emitter::Engine => {
                if forced.first() == Some(token) {
                    forced.remove(0);
                } else {
                    return Err(Refused { index, message: format!("token {index} {token:?}: the engine emits it, and the step before forced {forced:?}") });
                }
            }
            Emitter::Model => {
                if !forced.is_empty() {
                    return Err(Refused { index, message: format!("token {index} {token:?}: the engine forces {forced:?} before it") });
                }
                let start = Instant::now();
                let mask = decoder.admissible();
                let mask_seconds = start.elapsed().as_secs_f64();
                let admitted = decoder.vocabulary().id(token).is_some_and(|id| mask.contains(id));
                let start = Instant::now();
                let stepped = decoder.step(token.clone());
                let step_seconds = start.elapsed().as_secs_f64();
                let step = match stepped {
                    Ok(step) if admitted => step,
                    Ok(_) => return Err(Refused { index, message: format!("token {index} {token:?}: the mask refuses it and the step takes it") }),
                    Err(refusal) => return Err(Refused { index, message: format!("token {index} {token:?}: {refusal:?}") }),
                };
                forced = step.forced.into();
                if after(decoder, Stepped { index, token, mask: &mask, consistency: step.consistency, mask_seconds, step_seconds }).is_break() {
                    break;
                }
            }
        }
    }
    Ok(Replayed { forced })
}

/// Whether `program` holds a `DEMONSTRATED` form, whose stream the
/// commands that replay do not decode.
pub fn holds_demonstrated(program: &CheckedProgram) -> bool {
    program.program.graph.nodes.iter().any(|node| matches!(node.kind, DependencyKind::Demonstrated(_)))
}
