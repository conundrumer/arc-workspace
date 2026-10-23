//! The replay of a case program's token stream through a decoder, which
//! `decode` and `tables` share: each token the model emits is checked
//! against the mask and stepped, each token the engine emits is checked
//! against the tokens the step before forced, and the caller's code runs
//! after each step of a token the model emits.

use std::ops::ControlFlow;
use std::time::Instant;

use arclog::check::CheckedProgram;
use arclog::decode::{Consistency, Decoder};
use arclog::resolver::DependencyKind;
use arclog::stream::{Emitter, Token};

/// The step of a token the model emitted.
pub struct Stepped<'a> {
    /// The token's index in the stream.
    pub index: usize,
    pub token: &'a Token,
    /// The consistency the step gives, if it ends a `RULE` clause.
    pub consistency: Option<Consistency>,
    /// The seconds of the token mask, and of the step.
    pub mask_seconds: f64,
    pub step_seconds: f64,
}

/// What a replay left: the tokens the engine forces after its last step.
pub struct Replayed {
    forced: Vec<Token>,
}

impl Replayed {
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
    let mut forced: Vec<Token> = Vec::new();
    for (index, (token, emitter)) in stream.iter().enumerate() {
        match emitter {
            Emitter::Engine => {
                if forced.first() == Some(token) {
                    forced.remove(0);
                } else {
                    return Err(format!("token {index} {token:?}: the engine emits it, and the step before forced {forced:?}"));
                }
            }
            Emitter::Model => {
                if !forced.is_empty() {
                    return Err(format!("token {index} {token:?}: the engine forces {forced:?} before it"));
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
                    Ok(_) => return Err(format!("token {index} {token:?}: the mask refuses it and the step takes it")),
                    Err(refusal) => return Err(format!("token {index} {token:?}: {refusal:?}")),
                };
                forced = step.forced.into();
                if after(decoder, Stepped { index, token, consistency: step.consistency, mask_seconds, step_seconds }).is_break() {
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
