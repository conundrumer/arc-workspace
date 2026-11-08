//! The decode keeps joint open assignments and gives no attempt for an
//! output with more than two grids, as `docs/engine/synthesis.md#open-parameters` gives.

use std::sync::Arc;

use arclog::check::{check_program, CheckCache, CheckedProgram, SolverClauses};
use arclog::decode::{Consistency, Decoder};
use arclog::eval::instance::Constructions;
use arclog::eval::Caps;
use arclog::judge::candidates::{PairCandidates, Section, World};
use arclog::read::read_solver;
use arclog::registry::Registry;
use arclog::resolver::resolve;
use arclog::session::{SessionBound, TaskSession};
use arclog::stream::{token_stream, DecodeSettings, Emitter, Token, Vocabulary};
use arclog::task::{Grid, JudgedPair, JudgedTask, Task, TrainPair};
use arclog::terms::Color;

/// The input of the one train pair: one row of two cells.
const INPUT: &[u8] = &[1, 2];


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
    let task = Task { train: Box::new([TrainPair { input: grid(INPUT), output: grid(output) }]), test: Box::new([grid(&[3, 4])]) };
    let judged = JudgedTask { train: Box::new([JudgedPair { output: grid(output), alt: None }]), test: Box::new([]) };
    let constructions = Constructions::new(Vec::new(), Registry::get()).expect("an empty table");
    let session = TaskSession::new(SessionBound { bytes: 1 << 26 }, caps);
    Inputs { task, judged, session, constructions, settings: DecodeSettings { caps, rule_tests: true, ..DecodeSettings::default() } }
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
/// gave at an `OUT` form and the last it gave at a `RULE` clause.
fn walk(decoder: &mut Decoder<'_>, tokens: &[Token]) -> (Option<Consistency>, Option<Consistency>) {
    let (mut ended, mut rule) = (None, None);
    for token in tokens {
        let step = decoder.step(token.clone()).unwrap_or_else(|refusal| panic!("{token:?}: {refusal:?}"));
        ended = step.consistency.or(ended);
        rule = step.rule_test.or(rule);
    }
    (ended, rule)
}

/// Steps `decoder` through the stream of `program`, whose `OUT` form is
/// consistent, as is, under the rule tests, the relation of its last `RULE`
/// clause.
fn walk_consistent(decoder: &mut Decoder<'_>, program: &str) {
    let (ended, rule) = walk(decoder, &model_tokens(program));
    assert!(matches!(ended, Some(Consistency::Consistent { .. })), "{ended:?}");
    assert!(matches!(rule, Some(Consistency::Consistent { .. })), "{rule:?}");
}

#[test]
fn open_proposers_keep_joint_assignments() {
    let inputs = inputs(INPUT, Caps::CORPUS);
    let mut decoder = decoder(&inputs);
    let program = "(DET &a ColorDomain (ONE))\n(DET &b ColorDomain (ONE))\n(RULE &output (input *P *Col) (&a (:C *A)) (&b (:C A)))\n(OUT (&output ^P ^Col))\n";
    walk_consistent(&mut decoder, program);
    assert_eq!(&*decoder.attempts().unwrap().unwrap(), &[arclog::judge::attempts::Attempts::One(grid(&[3, 4]))]);
}

#[test]
fn three_or_more_test_grids_give_no_attempt() {
    let inputs = inputs(INPUT, Caps::CORPUS);
    let program = "(DET &a ColorDomain (ONE))\n(RULE &output (input *P) (IF ((input (:Col *D)) (input (:Col *E)) (!= D E)) ((&a (:C *Col))) ((input P (:Col Col)))))\n(OUT (&output ^P ^Col))\n";
    let mut inputs = inputs;
    inputs.task.train[0] = TrainPair { input: grid(&[1, 1]), output: grid(&[1, 1]) };
    inputs.judged.train[0].output = grid(&[1, 1]);
    let mut decoder = self::decoder(&inputs);
    walk_consistent(&mut decoder, program);
    assert_eq!(&*decoder.attempts().unwrap().unwrap(), &[arclog::judge::attempts::Attempts::None]);
}

#[test]
fn a_single_assignment_gives_one_attempt() {
    let inputs = inputs(&[2, 2], Caps::CORPUS);
    let mut decoder = decoder(&inputs);
    let program = "(DET &a ColorDomain (ONE))\n(RULE &output (input *P) (&a (:C *Col)))\n(OUT (&output ^P ^Col))\n";
    walk_consistent(&mut decoder, program);
    assert_eq!(&*decoder.attempts().unwrap().unwrap(), &[arclog::judge::attempts::Attempts::One(grid(&[2, 2]))]);
}

/// A case whose pick has two models on each input, and whose output is the
/// input at each model, run under a model cap of one.
const PICKED_CELL: &str = "(RULE &pick (input *P *Col) (ONE))\n(RULE &output (input *P *Col) (&pick (:P *Q) (:Col *C)))\n(OUT (&output ^P ^Col))\n";

#[test]
fn a_case_at_the_model_cap_solves_a_train_pair_and_gives_attempts_from_the_models_up_to_it() {
    let inputs = inputs(INPUT, Caps { models: 1, ..Caps::CORPUS });
    let mut decoder = decoder(&inputs);
    walk_consistent(&mut decoder, PICKED_CELL);
    assert!(decoder.capped_sets() > 0, "the trace counts the sets that ended at the cap");
    let (attempts, capped) = decoder.attempts_counted().unwrap().unwrap();
    assert_eq!(&*attempts, &[arclog::judge::attempts::Attempts::One(grid(&[3, 4]))]);
    assert_eq!(capped, 1, "the one test input ended at the cap");
}
