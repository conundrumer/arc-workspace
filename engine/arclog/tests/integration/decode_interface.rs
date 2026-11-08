//! At the `END` of an `OUT` form, a decode reports whether its relation
//! solves the train pairs, keeps the assignments of a `DET` under which it
//! does, and ends at a consistent `OUT` form; a prefix past the row cap
//! reports the stop and the cap; and a batch of decodes gives the results of
//! each decode stepped alone.

use std::sync::Arc;

use arclog::check::{check_program, CheckCache, CheckedProgram, SolverClauses};
use arclog::decode::{step_batch, Consistency, Decoder, Refusal, Projections};
use arclog::eval::instance::Constructions;
use arclog::eval::pool::Pool;
use arclog::eval::{Caps, Gauge, ReachedBound, RelationValue, RequestWork};
use arclog::judge::candidates::{PairCandidates, Section, World};
use arclog::program::ProgramRelation;
use arclog::relations::Relation;
use arclog::read::read_solver;
use arclog::registry::Registry;
use arclog::resolver::resolve;
use arclog::session::{SessionBound, TaskSession};
use arclog::stream::{token_stream, Control, DecodeSettings, Emitter, Token, Vocabulary, MEASURED_CAP};
use arclog::task::{Grid, JudgedPair, JudgedTask, Task, TrainPair};
use arclog::terms::{Color, Example};

type Assignment = (ProgramRelation, Arc<Relation>);

/// The input of the one train pair: one row of two cells.
const INPUT: &[u8] = &[1, 2];

const COPIES: &str = "(RULE &output (input *P *Col))\n";
const COPIES_OUT: &str = "(RULE &output (input *P *Col))\n(OUT (&output ^P ^Col))\n";

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
    inputs_under(output, DecodeSettings { caps, rule_tests: true, ..DecodeSettings::default() })
}

/// [`inputs`] under `settings`, whose caps are those of the session.
fn inputs_under(output: &[u8], settings: DecodeSettings) -> Inputs {
    let task = Task { train: Box::new([TrainPair { input: grid(INPUT), output: grid(output) }]), test: Box::new([]) };
    let judged = JudgedTask { train: Box::new([JudgedPair { output: grid(output), alt: None }]), test: Box::new([]) };
    let constructions = Constructions::new(Vec::new(), Registry::get()).expect("an empty table");
    let session = TaskSession::new(SessionBound { bytes: 1 << 26 }, settings.caps);
    Inputs { task, judged, session, constructions, settings }
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
/// gave at an `OUT` form.
fn walk(decoder: &mut Decoder<'_>, tokens: &[Token]) -> Option<Consistency> {
    walk_both(decoder, tokens).0
}

/// Steps `decoder` through `tokens`, and gives the last consistency a step
/// gave at an `OUT` form and the last it gave at a `RULE` clause, under the
/// rule tests.
fn walk_both(decoder: &mut Decoder<'_>, tokens: &[Token]) -> (Option<Consistency>, Option<Consistency>) {
    let (mut ended, mut rule) = (None, None);
    for token in tokens {
        let step = decoder.step(token.clone()).unwrap_or_else(|refusal| panic!("{token:?}: {refusal:?}"));
        ended = step.consistency.or(ended);
        rule = step.rule_test.or(rule);
    }
    (ended, rule)
}

#[test]
fn a_relation_that_solves_the_pairs_is_consistent_and_ends_the_decode() {
    let inputs = inputs(INPUT, Caps::CORPUS);
    let mut decoder = decoder(&inputs);
    let tokens = model_tokens(COPIES_OUT);
    let (ended, rule) = walk_both(&mut decoder, &tokens);
    assert!(matches!(ended, Some(Consistency::Consistent { .. })));
    assert!(matches!(rule, Some(Consistency::Consistent { .. })), "the rule test gives the verdict the clause's end gave");
    assert!(decoder.output().is_some());
    assert!(matches!(decoder.step(Token::Control(Control::Rule)), Err(Refusal::Grammar(_))), "the decode has ended");
}

#[test]
fn a_relation_that_does_not_solve_the_pairs_is_not_consistent() {
    let inputs = inputs(&[3, 3], Caps::CORPUS);
    let mut decoder = decoder(&inputs);
    let (ended, rule) = walk_both(&mut decoder, &model_tokens(COPIES_OUT));
    assert!(matches!(ended, Some(Consistency::NotConsistent)));
    assert!(matches!(rule, Some(Consistency::NotConsistent)));
    assert!(decoder.output().is_none());
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
    let rows = decoder.rows(Some(Example::at(0))).expect("a clause in progress").expect("the sub-body checks");
    let [(_, value)] = &rows.at[..] else { panic!("one entry: {rows:?}") };
    let RelationValue::Stopped(stop) = &value.0 else { panic!("a stop: {value:?}") };
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
            seen.push(format!("{:?}", result.as_ref().expect("no step panics")));
        }
    }
    let batched: Vec<String> = batched.into_iter().map(|steps| steps.join("\n")).collect();
    assert_eq!(batched, alone);
}

/// The counts of the sub-body of the clause in progress after `tokens`, at
/// each assignment, with the assignments.
fn counts_after(inputs: &Inputs, tokens: &[Token]) -> Vec<(Vec<Assignment>, Option<u64>)> {
    let mut decoder = decoder(inputs);
    walk(&mut decoder, tokens);
    let counts = decoder.counts().expect("a clause in progress");
    let [counted] = &*counts else { panic!("one example: {counts:?}") };
    let counted = counted.as_ref().expect("the sub-body checks");
    assert!(counted.stop.is_none());
    counted.at.clone()
}

const BG: &str = "(RULE &bg (input (:Col *C)))\n";
const FG: &str = "(RULE &fg (input *P *Col) (&bg (:C *V)) (!= Col V))\n";

#[test]
fn a_prefix_that_reads_a_det_of_two_values_gives_its_rows_at_each_value() {
    let inputs = inputs(&[2, 2], Caps::CORPUS);
    let tokens = model_tokens("(DET &c ColorDomain)\n(RULE &output (input *P) (&c (:C *Col)))\n");
    let (_, prefix) = tokens.split_last().expect("a stream");
    let counted = counts_after(&inputs, prefix);
    let values: Vec<_> = counted.iter().map(|(assigned, _)| assigned.clone()).collect();
    assert_eq!(values.len(), 2, "one entry for each value of `&c`: {counted:?}");
    assert!(values.iter().all(|assigned| assigned.len() == 1));
    assert!(format!("{:?}", values[0][0].1) != format!("{:?}", values[1][0].1), "the two entries hold two values of `&c`");
    assert!(counted.iter().all(|(_, count)| count.is_some()));
    let mut decoder = decoder(&inputs);
    walk(&mut decoder, prefix);
    let rows = decoder.rows(Some(Example::at(0))).expect("a clause in progress").expect("the sub-body checks");
    assert_eq!(rows.at.len(), 2);
}

#[test]
fn a_prefix_that_reads_no_det_of_several_values_gives_one_entry() {
    let inputs = inputs(&[3, 3], Caps::CORPUS);
    let tokens = model_tokens(COPIES);
    let (_, prefix) = tokens.split_last().expect("a stream");
    let counted = counts_after(&inputs, prefix);
    assert!(matches!(&counted[..], [(assigned, _)] if assigned.is_empty()), "{counted:?}");
}

#[test]
fn det_admission_refuses_the_assignment_cap_before_a_later_read() {
    let caps = Caps { assignments: 1, ..Caps::CORPUS };
    let inputs = inputs(&[3, 3], caps);
    let mut decoder = decoder(&inputs);
    let tokens = model_tokens("(DET &c ColorDomain)\n");
    let (end, prefix) = tokens.split_last().expect("a stream");
    walk(&mut decoder, prefix);
    assert_eq!(*end, Token::Control(Control::End));
    assert_eq!(decoder.step(end.clone()).unwrap_err(), Refusal::DetAdmission(arclog::decode::DetRefusal::Bound(ReachedBound::Assignments { cap: 1 })));
}

#[test]
fn a_choose_form_with_its_from_clause_open_gives_the_rows_of_that_clause() {
    let inputs = inputs(&[3, 3], Caps::CORPUS);
    let pick = "(CHOOSE &pick (from (&fg *P *Col)) (never (&fg *P *Col) (&fg (:P *P2) Col) (!= P P2) (&bg (:C Col))))\n";
    let tokens = model_tokens(&format!("{BG}{FG}{pick}"));
    let at = tokens.iter().position(|token| *token == Token::Control(Control::Choose)).expect("a `CHOOSE` form");
    let written = counts_after(&inputs, &tokens[..at + 7]);
    let rule = model_tokens(&format!("{BG}{FG}(RULE &copy (&fg *P *Col))\n"));
    let (_, plain) = rule.split_last().expect("a stream");
    let expected = counts_after(&inputs, plain);
    let counts = |counted: &[(Vec<Assignment>, Option<u64>)]| counted.iter().map(|(_, count)| *count).collect::<Vec<_>>();
    assert_eq!(counts(&written), counts(&expected));
    assert!(written[0].1.is_some_and(|count| count > 0), "{written:?}");
}

#[test]
fn a_det_clause_in_progress_gives_the_rows_of_its_kept_conjuncts() {
    let inputs = inputs(&[3, 3], Caps::CORPUS);
    let tokens = model_tokens("(DET &cells (ex_input *E *P *Col))\n(RULE &output (input (:P *Q)) (&cells (:Col *Col)))\n");
    let at = tokens.iter().position(|token| *token == Token::Control(Control::Det)).expect("a `DET` form");
    let after = |count: usize| {
        let mut decoder = decoder(&inputs);
        walk(&mut decoder, &tokens[..count]);
        let counts = decoder.counts().expect("a clause in progress");
        let [counted] = &*counts else { panic!("a task-wide clause gives one entry: {counts:?}") };
        let counted = counted.as_ref().expect("the sub-body checks").at.clone();
        let rows = decoder.rows(None).expect("a clause in progress").expect("the sub-body checks");
        assert_eq!(rows.at.len(), 1, "the clause's own `DET` is not assigned");
        (counted, rows)
    };
    after(at + 1);
    let (counted, _) = after(at + 4);
    assert!(counted[0].1.is_some_and(|count| count > 0), "{counted:?}");
}

#[test]
fn a_body_under_the_projection_cap_is_its_one_projection_with_the_rows_of_the_body() {
    let inputs = inputs(&[3, 3], Caps::CORPUS);
    let tokens = model_tokens(COPIES);
    let (_, prefix) = tokens.split_last().expect("a stream");
    let mut decoder = decoder(&inputs);
    walk(&mut decoder, prefix);
    let Some(Ok(Projections::Found(found))) = decoder.projections() else { panic!("the projections of a clause in progress") };
    let [projection] = &found[..] else { panic!("one projection: {found:?}") };
    let rows = decoder.rows(Some(Example::at(0))).expect("a clause in progress").expect("the sub-body checks");
    let [(_, body)] = &rows.at[..] else { panic!("one entry: {rows:?}") };
    let RelationValue::Rows(body) = &body.0 else { panic!("rows: {body:?}") };
    assert_eq!(projection.columns.len(), usize::from(body.arity()));
    let [projected_example] = &projection.rows[..] else { panic!("one example: {projection:?}") };
    let [(_, Some(projected))] = &projected_example.at[..] else { panic!("one projection: {projected_example:?}") };
    assert_eq!((projected.arity(), projected.len()), (body.arity(), body.len()));
    assert!(self::decoder(&inputs).projections().is_none(), "no clause is in progress before the first token");
}

/// The same refusal must protect callers that bypass mask construction or OUT tests.
fn det_admission_refusal(source: &str, inputs: &Inputs) -> Refusal {
    let mut decoder = decoder(inputs);
    let tokens = model_tokens(source);
    for token in tokens {
        let before = decoder.state().program().clone();
        if let Err(refusal) = decoder.forced(&token) {
            assert!(matches!(refusal, Refusal::DetAdmission(_)), "{token:?}: {refusal:?}");
            let id = decoder.vocabulary().id(&token).expect("a token");
            assert!(!decoder.admissible().contains(id));
            assert_eq!(decoder.step_untested(token.clone()).unwrap_err(), refusal);
            assert_eq!(decoder.step(token).unwrap_err(), refusal);
            assert_eq!(decoder.state().program(), &before);
            return refusal;
        }
        decoder.step_untested(token).expect("an admitted token");
    }
    panic!("a DET was expected to be refused");
}

#[test]
fn det_admission_refuses_an_empty_proposer_domain_and_allows_its_empty_set_value() {
    let inputs = inputs(&[3, 3], Caps::CORPUS);
    assert_eq!(det_admission_refusal("(DET &c UnchangedColor)\n", &inputs), Refusal::DetAdmission(arclog::decode::DetRefusal::NoLiveAssignment));
    let mut decoder = decoder(&inputs);
    walk(&mut decoder, &model_tokens("(DET &c UnchangedColor (SET))\n"));
}

#[test]
fn det_admission_checks_a_proposer_one_before_accepting_the_mark() {
    let inputs = inputs(&[3, 3], Caps::CORPUS);
    let mut decoder = decoder(&inputs);
    let tokens = model_tokens("(DET &c UnchangedColor (ONE))\n");
    for token in tokens {
        if token == Token::Control(Control::One) {
            assert_eq!(decoder.step(token).unwrap_err(), Refusal::DetAdmission(arclog::decode::DetRefusal::NoLiveAssignment));
            return;
        }
        decoder.step(token).expect("the proposer opens");
    }
    panic!("the ONE mark was expected");
}

#[test]
fn det_admission_keeps_a_keyed_model_pick_available() {
    let inputs = inputs(INPUT, Caps { models: 1, ..Caps::CORPUS });
    // The unkeyed ONE would have two models. Its open key must stay writable.
    let mut decoder = decoder(&inputs);
    walk(&mut decoder, &model_tokens("(DET &pick (ex_input *E *P *Col) (ONE E P))\n"));
}

/// Steps `decoder` through `tokens`, and asks for the mask before each token,
/// as a sampler does.
fn walk_masked(decoder: &mut Decoder<'_>, tokens: &[Token]) {
    for token in tokens {
        let _ = decoder.admissible();
        decoder.step(token.clone()).unwrap_or_else(|refusal| panic!("{token:?}: {refusal:?}"));
    }
}

/// The units of work that the request counts for the sub-body of the last
/// clause of `arclog`, whose tokens but the last the decode has stepped, with
/// the mask asked before each token where `masked`.
fn sub_body_work(arclog: &str, masked: bool) -> u64 {
    let inputs = inputs(INPUT, Caps::CORPUS);
    let mut decoder = decoder(&inputs);
    let tokens = model_tokens(arclog);
    let (end, prefix) = tokens.split_last().expect("a stream");
    assert_eq!(*end, Token::Control(Control::End));
    if masked {
        walk_masked(&mut decoder, prefix);
    } else {
        walk(&mut decoder, prefix);
    }
    decoder.counts().expect("a clause in progress");
    RequestWork::latest().expect("the request of the call").count()
}

#[test]
fn the_work_of_a_form_alone_is_its_work_in_the_stream() {
    const FIRST: &str = "(RULE &first (input *P *Col))\n";
    const UNRELATED: &str = "(RULE &unrelated (input *P *Col) (input (:P *Q) Col))\n";
    const SECOND: &str = "(RULE &second (&first *P *Col))\n";
    // Each form with the streams that hold it: the forms it reads, then it, alone, and a stream with a form it does not read, with the mask asked at each token.
    let cases = [
        (format!("{FIRST}(RULE &output (&first *P *Col))\n"), format!("{FIRST}{UNRELATED}(RULE &output (&first *P *Col))\n")),
        (format!("{FIRST}{SECOND}(RULE &output (&second *P *Col))\n"), format!("{FIRST}{UNRELATED}{SECOND}(RULE &output (&second *P *Col))\n")),
        (format!("{FIRST}(RULE &output (&first *P *Col) (&first (:P *Q) Col))\n"), format!("{UNRELATED}{FIRST}(RULE &output (&first *P *Col) (&first (:P *Q) Col))\n")),
    ];
    for (alone, stream) in &cases {
        let alone_work = sub_body_work(alone, false);
        assert!(alone_work > 0, "the form counts some work: {alone}");
        assert_eq!(sub_body_work(stream, true), alone_work, "the work of the form in its stream: {stream}");
    }
}

#[test]
fn the_work_of_a_body_is_the_same_in_any_written_order_of_its_conjuncts() {
    const READS: &str = "(RULE &first (input *P *Col))\n(RULE &second (&first *P *Col))\n";
    let orders = [
        "(RULE &output (&first *P *Col) (&second P Col) (input P Col))\n",
        "(RULE &output (input *P *Col) (&second P Col) (&first P Col))\n",
        "(RULE &output (&second *P *Col) (input P Col) (&first P Col))\n",
    ];
    let works: Vec<u64> = orders.iter().map(|order| sub_body_work(&format!("{READS}{order}"), false)).collect();
    assert!(works[0] > 0, "the body counts some work");
    assert!(works.iter().all(|work| *work == works[0]), "the work of each written order of one body: {works:?}");
}

/// The largest value and the cap of each gauge of the request that the last
/// call began on this thread, but for the session's own ledger, which depends
/// on the machine's heap, and the labeling nodes, which are the process's.
fn request_gauges() -> Vec<(&'static str, u64, u64)> {
    let request = RequestWork::latest().expect("the request of the call");
    request.all_gauges().into_iter().filter(|(gauge, ..)| !matches!(gauge, Gauge::SessionBytes | Gauge::LabelingNodes)).map(|(gauge, max, cap, _)| (gauge.name(), max, cap)).collect()
}

/// The gauges of the request that `admits` of every token of the vocabulary
/// begins at the state after all tokens but the last of `arclog`, where the
/// decode has the caches of the state filled by another request first if
/// `warm`.
fn gauges_of_admits(arclog: &str, warm: bool) -> Vec<(&'static str, u64, u64)> {
    let inputs = inputs(INPUT, Caps::CORPUS);
    let mut decoder = decoder(&inputs);
    let tokens = model_tokens(arclog);
    let (end, prefix) = tokens.split_last().expect("a stream");
    assert_eq!(*end, Token::Control(Control::End));
    walk(&mut decoder, prefix);
    let ids: Vec<u32> = (0..u32::try_from(decoder.vocabulary().len()).expect("fewer than 2^32 tokens")).collect();
    if warm {
        let _ = decoder.fork().admits(&ids);
    }
    let _ = decoder.admits(&ids);
    request_gauges()
}

/// The gauges whose cap is no setting of `DecodeSettings`: a constant of the engine.
const CONSTANT_CAP_GAUGES: [&str; 6] = ["box_margin", "projection_steps", "atom_states", "study_row_work", "compared_rows", "column_search_work"];

/// What the decode of `COPIES_OUT` gave under `settings`: the verdict of every token of the vocabulary
/// before the last token, the verdicts of the `RULE` end and of the `OUT` end, whether the decode ended,
/// and the gauges of the request that checked the vocabulary.
struct Decoded {
    admitted: Vec<bool>,
    rule: String,
    ended: String,
    output: bool,
    gauges: Vec<(&'static str, u64, u64)>,
}

fn verdict(consistency: &Option<Consistency>) -> String {
    match consistency {
        None => "none".into(),
        Some(Consistency::Consistent { assignments, stop }) => format!("consistent {} {}", assignments.len(), stop.is_some()),
        Some(Consistency::NotConsistent) => "not consistent".into(),
        Some(Consistency::SeveralValues { values, .. }) => format!("several {}", values.len()),
        Some(Consistency::Fault(_)) => "fault".into(),
        Some(Consistency::Stopped(_)) => "stopped".into(),
    }
}

fn decode_under(settings: DecodeSettings) -> Decoded {
    let inputs = inputs_under(INPUT, DecodeSettings { rule_tests: true, ..settings });
    let mut decoder = decoder(&inputs);
    let tokens = model_tokens(COPIES_OUT);
    let (last, prefix) = tokens.split_last().expect("a stream");
    let (_, rule) = walk_both(&mut decoder, prefix);
    let ids: Vec<u32> = (0..u32::try_from(decoder.vocabulary().len()).expect("fewer than 2^32 tokens")).collect();
    let admitted = decoder.admits(&ids);
    let gauges = request_gauges();
    let step = decoder.step(last.clone()).unwrap_or_else(|refusal| panic!("{last:?}: {refusal:?}"));
    Decoded { admitted, rule: verdict(&rule), ended: verdict(&step.consistency), output: decoder.output().is_some(), gauges }
}

#[test]
fn a_program_decodes_under_the_measurement_profile_as_under_the_default_settings() {
    let default = decode_under(DecodeSettings::default());
    let measured = decode_under(DecodeSettings::measurement());
    assert_eq!(default.admitted, measured.admitted, "the verdicts of the vocabulary");
    assert_eq!((&default.rule, &default.ended, default.output), (&measured.rule, &measured.ended, measured.output));
    assert!(default.output, "the program solves the pair and ends the decode");
    assert!(default.admitted.iter().any(|admitted| *admitted), "the vocabulary has an admitted token");
}

#[test]
fn the_measurement_profile_gives_every_gauge_a_cap_of_2_to_the_48_but_the_constant_ones() {
    let default = decode_under(DecodeSettings::default());
    let measured = decode_under(DecodeSettings::measurement());
    assert_eq!(default.gauges.iter().map(|gauge| gauge.0).collect::<Vec<_>>(), measured.gauges.iter().map(|gauge| gauge.0).collect::<Vec<_>>());
    // A default cap of u64::MAX is a count with no cap, which no setting gives.
    for ((name, _, default_cap), (_, _, cap)) in default.gauges.iter().zip(&measured.gauges) {
        if CONSTANT_CAP_GAUGES.contains(name) {
            assert_eq!(cap, default_cap, "the constant cap of {name}");
        } else if *default_cap != 0 && *default_cap != u64::MAX {
            assert_eq!(*cap, MEASURED_CAP, "the cap of {name}");
        }
    }
    assert!(measured.gauges.iter().any(|(name, _, cap)| !CONSTANT_CAP_GAUGES.contains(name) && *cap == MEASURED_CAP), "some gauge ran under the profile: {:?}", measured.gauges);
}

#[test]
fn the_gauges_of_a_request_are_the_same_with_cold_caches_and_with_caches_another_request_filled() {
    for arclog in ["(DET &pick (ex_input *E *P *Col) (ONE E P))\n", "(RULE &output (input *P *Col) (input P Col))\n"] {
        let cold = gauges_of_admits(arclog, false);
        let warm = gauges_of_admits(arclog, true);
        assert_eq!(cold, warm, "the gauges of a request on {arclog}");
    }
}
