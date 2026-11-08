//! The replay of a case program's token stream through a decoder, which
//! `arclog-cli decode` and the walk of [`super::corpus`] share: each token the model emits is checked
//! against the mask, where the replay computes it, and stepped, each token the engine emits is checked
//! against the tokens the step before forced, and the caller's code runs
//! after each step of a token the model emits.

use std::ops::ControlFlow;
use crate::clock::Stopwatch;

use super::{Consistency, Decoder, TokenMask};
use crate::check::CheckedProgram;
use crate::resolver::DependencyKind;
use crate::stream::{Emitter, Token};

/// The step of a token the model emitted.
pub struct Stepped<'a> {
    /// The token's index in the stream.
    pub index: usize,
    pub token: &'a Token,
    /// The tokens that were admissible before the step, where the replay
    /// computes the mask.
    pub mask: Option<Masked<'a>>,
    /// The consistency the step gives, if it ends an `OUT` form.
    pub consistency: Option<Consistency>,
    /// The consistency of the relation of the `RULE` clause the step ends,
    /// where the settings run the rule tests.
    pub rule_test: Option<Consistency>,
    /// The seconds of the step.
    pub step_seconds: f64,
}

/// The token mask before a step, with the seconds that computing it took.
pub struct Masked<'a> {
    pub mask: &'a TokenMask,
    pub seconds: f64,
}

/// The refusal that stops a replay: the index of the stream's token that the
/// decoder refuses, or that the engine emits against the tokens the step
/// before forced, with the line that says why.
#[derive(Clone, Debug)]
pub struct Refused {
    pub index: usize,
    pub message: String,
}

/// What a replay left: the tokens the engine forces after its last step, and
/// the end of the program the decode reads.
pub struct Replayed {
    forced: Vec<Token>,
    end: usize,
}

impl Replayed {
    /// The index in the stream where the program the decode reads ends: the
    /// index of the first token the model emits after the decode has ended
    /// at its `OUT` form, or the stream's length where the replay reads the
    /// whole stream. Where `after` broke the replay, the index after the
    /// token it broke at.
    pub fn end(&self) -> usize {
        self.end
    }

    /// The tokens the engine forces after the last step.
    pub fn forced(&self) -> &[Token] {
        &self.forced
    }

    /// The refusal where the replay ended while the engine forces tokens.
    pub fn unfinished(&self) -> Option<String> {
        (!self.forced.is_empty()).then(|| format!("the stream ends while the engine forces {:?}", self.forced))
    }
}

/// Steps `decoder` through `stream`, computing the token mask before each
/// step where `masked` holds, and calls `after` with the decoder and
/// the step, after each step of a token the model emits; the replay ends
/// early where `after` gives [`ControlFlow::Break`]. Gives the line of the
/// first token the decoder refuses, or that the engine emits against the
/// tokens the step before forced. The replay ends with no refusal at the
/// first token the model emits after the decode has ended at its `OUT` form,
/// once the engine forces no token there, and the tokens from there on are no
/// part of the program the decode reads ([`Replayed::end`]). A token the mask refuses is a token the
/// step refuses, so a replay with no mask refuses the same tokens.
pub fn replay(decoder: &mut Decoder<'_>, stream: &[(Token, Emitter)], masked: bool, after: &mut dyn FnMut(&Decoder<'_>, Stepped<'_>) -> ControlFlow<()>) -> Result<Replayed, String> {
    replay_from(decoder, stream, masked, 0, Vec::new(), None, after).map_err(|refused| refused.message)
}

/// As [`replay`], from the token at position `start` of `stream`, where
/// `decoder` has stepped the tokens before it and the engine still forces
/// `forced` there. The indices that `after` and the faults give are those
/// of `stream`, and the refusal gives the index of its token. The replay ends
/// as [`replay`] gives. The step of the token at the index `untested` of
/// `stream`, a token the model emits, is [`Decoder::step_untested`]: the
/// caller's `consistency` and `rule_test` there are `None`.
pub fn replay_from(
    decoder: &mut Decoder<'_>,
    stream: &[(Token, Emitter)],
    masked: bool,
    start: usize,
    forced: Vec<Token>,
    untested: Option<usize>,
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
                if decoder.output().is_some() {
                    return Ok(Replayed { forced, end: index });
                }
                let mask = masked.then(|| {
                    let start = Stopwatch::start();
                    let mask = decoder.admissible();
                    (mask, start.elapsed().seconds())
                });
                let admitted = mask.as_ref().is_none_or(|(mask, _)| decoder.vocabulary().id(token).is_some_and(|id| mask.contains(id)));
                let start = Stopwatch::start();
                let stepped = if untested == Some(index) { decoder.step_untested(token.clone()) } else { decoder.step(token.clone()) };
                let step_seconds = start.elapsed().seconds();
                let step = match stepped {
                    Ok(step) if admitted => step,
                    Ok(_) => return Err(Refused { index, message: format!("token {index} {token:?}: the mask refuses it and the step takes it") }),
                    Err(refusal) => return Err(Refused { index, message: format!("token {index} {token:?}: {refusal:?}") }),
                };
                forced = step.forced.into();
                let (consistency, rule_test) = (step.consistency, step.rule_test);
                let mask = mask.as_ref().map(|(mask, seconds)| Masked { mask, seconds: *seconds });
                if after(decoder, Stepped { index, token, mask, consistency, rule_test, step_seconds }).is_break() {
                    return Ok(Replayed { forced, end: index + 1 });
                }
            }
        }
    }
    Ok(Replayed { forced, end: stream.len() })
}

/// Whether `program` holds a `DEMONSTRATED` form.
pub fn holds_demonstrated(program: &CheckedProgram) -> bool {
    program.program.graph.nodes.iter().any(|node| matches!(node.kind, DependencyKind::Demonstrated(_)))
}
