//! At the `END` of a `RULE` clause, a decode reports whether the relation,
//! read as `&output`, solves the train pairs, keeps the assignments of a
//! `DET` under which it does, and ends at a consistent relation; a prefix
//! past the row cap reports the stop and the cap; and a batch of decodes
//! gives the results of each decode stepped alone.

use std::sync::Arc;

use arclog::check::{check_program, CheckCache, CheckedProgram, SolverClauses};
use arclog::decode::{step_batch, Consistency, Decoder, Refusal};
use arclog::eval::instance::Constructions;
use arclog::eval::pool::Pool;
use arclog::eval::{Caps, ReachedBound, RelationValue};
use arclog::judge::candidates::{PairCandidates, Section, World};
use arclog::read::read_solver;
use arclog::registry::Registry;
use arclog::resolver::resolve;
use arclog::session::{SessionBound, TaskSession};
use arclog::stream::{token_stream, Control, DecodeSettings, Emitter, Token, Vocabulary};
use arclog::task::{Grid, JudgedPair, JudgedTask, Task, TrainPair};
use arclog::terms::{Color, Example};

/// The input of the one train pair: one row of two cells.
const INPUT: &[u8] = &[1, 2];

const COPIES: &str = "(RULE &output (input *P *Col))\n";

fn grid(colors: &[u8]) -> Grid {
    let rows: Box<[Box<[Color]>]> = Box::new([colors.iter().map(|&digit| Color::from_digit(digit).expect("a color")).collect()]);
    Grid::from_rows(rows).expect("a grid")
}

/// The checked concept program of `arclog`.
fn checked(arclog: &str) -> CheckedProgram {
    let solver = read_solver("decode", arclog, "", &|_| None).expect("the file reads").value;
    let registry = Registry::get();
    let program = resolve(&solver.concept_case().program, None, &solver.derived_relations(), registry).value;
    check_program(program, &SolverClauses::of(&solver, registry), registry, &mut CheckCache::default()).expect("every check passes")
}

/// What a decode runs on: a task of one train pair whose output is
/// `output`, under `caps`.
struct Inputs {
    task: Task,
    judged: JudgedTask,
    session: TaskSession,
    constructions: Constructions,
    settings: DecodeSettings,
}

fn inputs(output: &[u8], caps: Caps) -> Inputs {
    let task = Task { train: Box::new([TrainPair { input: grid(INPUT), output: grid(output) }]), test: Box::new([]) };
    let judged = JudgedTask { train: Box::new([JudgedPair { output: grid(output), alt: None }]), test: Box::new([]) };
    let constructions = Constructions::new(Vec::new(), Registry::get()).expect("an empty table");
    let session = TaskSession::new(SessionBound { bytes: 1 << 26 }, caps);
    Inputs { task, judged, session, constructions, settings: DecodeSettings { caps, ..DecodeSettings::default() } }
}

fn decoder(inputs: &Inputs) -> Decoder<'_> {
    let train: Arc<[PairCandidates<'_>]> = inputs.judged.train.iter().map(|pair| PairCandidates::of(pair, Section::Train, World::Closed)).collect();
    Decoder::new(&inputs.task, &inputs.session, Registry::get(), &inputs.constructions, &inputs.settings).judging(train)
}

/// The tokens of the language model in the stream of `arclog`.
fn model_tokens(arclog: &str) -> Vec<Token> {
    let vocabulary = Vocabulary::new(Registry::get(), &DecodeSettings::default());
    let stream = token_stream(&checked(arclog), &vocabulary).expect("the program has a stream");
    stream.into_iter().filter(|(_, emitter)| *emitter == Emitter::Model).map(|(token, _)| token).collect()
}

/// Steps `decoder` through `tokens`, and gives the last consistency a step
/// gave.
fn walk(decoder: &mut Decoder<'_>, tokens: &[Token]) -> Option<Consistency> {
    let mut last = None;
    for token in tokens {
        let step = decoder.step(token.clone()).unwrap_or_else(|refusal| panic!("{token:?}: {refusal:?}"));
        last = step.consistency.or(last);
    }
    last
}

#[test]
fn a_relation_that_solves_the_pairs_is_consistent_and_ends_the_decode() {
    let inputs = inputs(INPUT, Caps::CORPUS);
    let mut decoder = decoder(&inputs);
    let tokens = model_tokens(COPIES);
    assert!(matches!(walk(&mut decoder, &tokens), Some(Consistency::Consistent { .. })));
    assert!(decoder.output().is_some());
    assert!(matches!(decoder.step(Token::Control(Control::Rule)), Err(Refusal::Grammar(_))), "the decode has ended");
}

#[test]
fn a_relation_that_does_not_solve_the_pairs_is_not_consistent() {
    let inputs = inputs(&[3, 3], Caps::CORPUS);
    let mut decoder = decoder(&inputs);
    assert!(matches!(walk(&mut decoder, &model_tokens(COPIES)), Some(Consistency::NotConsistent)));
    assert!(decoder.output().is_none());
}

#[test]
fn a_det_of_two_values_keeps_the_assignment_that_solves_the_pairs() {
    let inputs = inputs(&[2, 2], Caps::CORPUS);
    let mut decoder = decoder(&inputs);
    let program = "(DET &c ColorDomain)\n(RULE &output (input *P) (&c (:C *Col)))\n";
    let Some(Consistency::Consistent { assignments }) = walk(&mut decoder, &model_tokens(program)) else { panic!("a consistent relation") };
    assert_eq!(assignments.len(), 1, "one value of `&c` paints the output: {assignments:?}");
}

#[test]
fn a_prefix_past_the_row_cap_is_stopped_at_the_cap() {
    let caps = Caps { rows: 1, ..Caps::CORPUS };
    let inputs = inputs(INPUT, caps);
    let mut decoder = decoder(&inputs);
    let tokens = model_tokens(COPIES);
    let (end, prefix) = tokens.split_last().expect("a stream");
    assert_eq!(*end, Token::Control(Control::End));
    walk(&mut decoder, prefix);
    let value = decoder.rows(Some(Example::at(0))).expect("a clause in progress").expect("the sub-body checks");
    let RelationValue::Stopped(stop) = value.0 else { panic!("a stop: {value:?}") };
    assert_eq!(stop.bound, ReachedBound::Rows { cap: 1 });
}

#[test]
fn a_batch_of_decodes_gives_the_results_of_each_decode_alone() {
    let consistent = inputs(INPUT, Caps::CORPUS);
    let inconsistent = inputs(&[3, 3], Caps::CORPUS);
    let tokens = model_tokens(COPIES);
    let alone: Vec<String> = [&consistent, &inconsistent]
        .iter()
        .map(|inputs| {
            let mut decoder = decoder(inputs);
            tokens.iter().map(|token| format!("{:?}", decoder.step(token.clone()))).collect::<Vec<_>>().join("\n")
        })
        .collect();
    let pool = Pool::new(Some(2));
    let mut decoders = [decoder(&consistent), decoder(&inconsistent)];
    let mut batched = vec![Vec::new(); 2];
    for token in &tokens {
        let results = step_batch(&pool, &mut decoders, &[token.clone(), token.clone()]);
        for (seen, result) in batched.iter_mut().zip(results.iter()) {
            seen.push(format!("{result:?}"));
        }
    }
    let batched: Vec<String> = batched.into_iter().map(|steps| steps.join("\n")).collect();
    assert_eq!(batched, alone);
}
