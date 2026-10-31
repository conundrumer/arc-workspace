//! The statistics of `arclog::stats` count the phases of a decode when they
//! are on, and a decode gives the same masks and steps whether they are on or
//! off.

use std::collections::HashMap;
use std::sync::{Arc, Mutex};

use arclog::check::{check_program, CheckCache, SolverClauses};
use arclog::decode::{Decoder, TokenMask};
use arclog::eval::instance::Constructions;
use arclog::eval::Caps;
use arclog::judge::candidates::{PairCandidates, Section, World};
use arclog::read::read_solver;
use arclog::registry::Registry;
use arclog::resolver::resolve;
use arclog::session::{SessionBound, TaskSession};
use arclog::stats::{self, PhaseStats};
use arclog::stream::{token_stream, DecodeSettings, Emitter, Token, Vocabulary};
use arclog::task::{Grid, JudgedPair, JudgedTask, Task, TrainPair};
use arclog::terms::Color;

/// The tests that turn the statistics on or off and reset them run one at a time.
static SERIAL: Mutex<()> = Mutex::new(());

/// A program with a `DET`, so that the decode checks forms, closes a `DET`
/// and tests an `OUT` form over its values.
const PROGRAM: &str = "(DET &c ColorDomain)\n(RULE &output (input *P) (&c (:C *Col)))\n(OUT (&output ^P ^Col))\n";

fn grid(colors: &[u8]) -> Grid {
    let rows: Box<[Box<[Color]>]> = Box::new([colors.iter().map(|&digit| Color::from_digit(digit).expect("a color")).collect()]);
    Grid::from_rows(rows).expect("a grid")
}

fn model_tokens() -> Vec<Token> {
    let solver = read_solver("decode", PROGRAM, "", &|_| None).expect("the file reads").value;
    let registry = Registry::get();
    let program = resolve(&solver.concept_case().program, None, &solver.derived_relations(), registry).value;
    let checked = check_program(program, &SolverClauses::of(&solver, registry), registry, &mut CheckCache::default()).expect("every check passes");
    let vocabulary = Vocabulary::new(registry, &DecodeSettings::default());
    let stream = token_stream(&checked, &vocabulary).expect("the program has a stream");
    stream.into_iter().filter(|(_, emitter)| *emitter == Emitter::Model).map(|(token, _)| token).collect()
}

/// The mask before each step of the program, with what the step gives.
fn decode(tokens: &[Token]) -> Vec<(TokenMask, String)> {
    let task = Task { train: Box::new([TrainPair { input: grid(&[1, 2]), output: grid(&[2, 2]) }]), test: Box::new([]) };
    let judged = JudgedTask { train: Box::new([JudgedPair { output: grid(&[2, 2]), alt: None }]), test: Box::new([]) };
    let constructions = Constructions::new(Vec::new(), Registry::get()).expect("an empty table");
    let session = TaskSession::new(SessionBound { bytes: 1 << 26 }, Caps::CORPUS);
    let settings = DecodeSettings { caps: Caps::CORPUS, rule_tests: true, ..DecodeSettings::default() };
    let train: Arc<[PairCandidates<'_>]> = judged.train.iter().map(|pair| PairCandidates::of(pair, Section::Train, World::Closed)).collect();
    let mut decoder = Decoder::new(&task, &session, Registry::get(), &constructions, &settings).judging(train);
    tokens.iter().map(|token| (decoder.admissible(), format!("{:?}", decoder.step(token.clone())))).collect()
}

fn by_name(snapshot: &[PhaseStats]) -> HashMap<&'static str, PhaseStats> {
    snapshot.iter().map(|stat| (stat.phase.name(), *stat)).collect()
}

#[test]
fn the_counters_move_and_a_decode_gives_the_same_results_with_them_on_or_off() {
    let _serial = SERIAL.lock().unwrap_or_else(|poisoned| poisoned.into_inner());
    let before = stats::enabled();
    let tokens = model_tokens();

    stats::set_enabled(false);
    let off = decode(&tokens);

    stats::set_enabled(true);
    stats::snapshot(true);
    let on = decode(&tokens);
    let counted = by_name(&stats::snapshot(false));
    stats::set_enabled(before);

    assert_eq!(on, off, "the masks and the steps are the same whether the statistics are on or off");

    for name in ["decode.next", "decode.with_checks", "resolve.last", "check.program", "check.program_types", "prefix.check.grammar", "infer.form.open", "det.liveness"] {
        assert!(counted[name].calls > 0, "{name} counted no call: {counted:?}");
    }
    assert!(counted["check.program"].units > 0, "forms checked: {counted:?}");
    assert!(counted["decode.next"].new > 0, "decode.next counted a new state: {counted:?}");
    assert!(counted["decode.next"].ns > 0, "a span adds its time");
}

/// `snapshot(true)` gives the counters and starts them again from zero.
#[test]
fn a_reset_snapshot_gives_the_counters_and_clears_them() {
    let _serial = SERIAL.lock().unwrap_or_else(|poisoned| poisoned.into_inner());
    let before = stats::enabled();
    stats::set_enabled(true);
    stats::snapshot(true);
    drop(stats::span(stats::Phase::PyStep));
    stats::units(stats::Phase::PyStep, 3);
    stats::seen(stats::Phase::PyStep, || 7);
    stats::seen(stats::Phase::PyStep, || 7);
    let first = by_name(&stats::snapshot(true))["py.step"];
    let second = by_name(&stats::snapshot(false))["py.step"];
    stats::set_enabled(before);
    // Only the Python bindings run `py.step`, so no other test of this binary counts it.
    assert_eq!((first.calls, first.new, first.repeated, first.units), (1, 1, 1, 3));
    assert_eq!((second.calls, second.new, second.repeated, second.ns, second.units), (0, 0, 0, 0, 0), "a reset clears the counters");
}
