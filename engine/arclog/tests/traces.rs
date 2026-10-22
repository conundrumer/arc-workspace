//! The trace of a decode: one record per accepted token, rendered as the
//! trace form of `docs/arclog/arclog.md#trace-form`, with the top-k braces
//! under a flag; the stop of a decode counted under the bound it reached; and
//! the program form that `write_synthesized` gives.

use std::sync::Arc;

use arclog::check::{check_program, CheckCache, CheckedProgram, SolverClauses};
use arclog::decode::Decoder;
use arclog::eval::instance::Constructions;
use arclog::eval::values::Caps;
use arclog::eval::{relation_of, Cancellation, Evaluation, Limits, ParameterValues};
use arclog::program::{DeclaredName, ProgramRelation, RelationName};
use arclog::judge::candidates::{PairCandidates, Section, World};
use arclog::read::read_solver;
use arclog::registry::Registry;
use arclog::resolver::resolve;
use arclog::session::{SessionBound, TaskSession};
use arclog::stream::{token_stream, Control, DecodeSettings, Emitter, Token, Vocabulary};
use arclog::task::{Grid, JudgedPair, JudgedTask, Task, TrainPair};
use arclog::program::path::NodePath;
use arclog::program::{Node, Program};
use arclog::resolver::SolverScope;
use arclog::terms::{Color, Example};
use arclog::write::write_synthesized;
use arclog::trace::render::{stop_shares, trace_form, TraceFormOptions};
use arclog::trace::{DecodeTrace, RunTrace, Stop, TopK};

const BG: &str = "(RULE &bg (input (:Col *C)))\n";
const FG: &str = "(RULE &fg (input *P *Col) (&bg (:C *V)) (!= Col V))\n";
const COMPS: &str = "(INIT &comps Connectivity (node ((:P P)) (&fg *P)))\n";
const AXIS: &str = "(RULE &axis_len (input (:P *B)) (frame_extent (:P B) (:N *N)))\n(RULE &larger (&axis_len *B) (&axis_len (:B *B2)))\n";
const PRIOR: &str = "(RULE &prior (&axis_len *B *N) (&axis_len (:B *B2) (:N *N2)) (OR ((> N N2)) ((= N N2) (&larger B B2))))\n";

fn grid(colors: &[u8]) -> Grid {
    let rows: Box<[Box<[Color]>]> = Box::new([colors.iter().map(|&digit| Color::from_digit(digit).expect("a color")).collect()]);
    Grid::from_rows(rows).expect("a grid")
}

fn checked(arclog: &str) -> CheckedProgram {
    let solver = read_solver("trace", arclog, "", &|_| None).expect("the file reads").value;
    let registry = Registry::get();
    let program = resolve(&solver.concept_case().program, None, &solver.derived_relations(), registry).value;
    check_program(program, &SolverClauses::of(&solver, registry), registry, &mut CheckCache::default()).expect("every check passes")
}

/// A task of one train pair of one row of two cells, and what a decode runs on.
struct Inputs {
    task: Task,
    judged: JudgedTask,
    session: TaskSession,
    constructions: Constructions,
    settings: DecodeSettings,
}

fn inputs(output: &[u8], caps: Caps) -> Inputs {
    let task = Task { train: Box::new([TrainPair { input: grid(&[1, 2]), output: grid(output) }]), test: Box::new([]) };
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

fn walk(decoder: &mut Decoder<'_>, tokens: &[Token]) {
    for token in tokens {
        decoder.step(token.clone()).unwrap_or_else(|refusal| panic!("{token:?}: {refusal:?}"));
    }
}

fn rendered(arclog: &str, names: &[&str], top_k: bool) -> String {
    let inputs = inputs(&[3, 3], Caps::CORPUS);
    let mut decoder = decoder(&inputs);
    walk(&mut decoder, &model_tokens(arclog));
    let vocabulary = Vocabulary::new(Registry::get(), &DecodeSettings::default());
    let options = TraceFormOptions { top_k, relations: names.iter().map(|name| (*name).to_owned()).collect() };
    trace_form(decoder.trace(), &vocabulary, &options)
}

#[test]
fn a_decode_renders_the_trace_form_of_a_rule() {
    let text = rendered(&format!("{BG}{FG}"), &["&bg", "&fg"], false);
    let expected = "\
(RULE (input (:Col *[Col]))
      END)
[&bg]
(RULE (input (:P *[P]) (:Col *[Col]))
      (&bg (:Col *[Col2]))
      (!= Col Col2)
      END)
[&fg]
";
    assert_eq!(text, expected);
}

#[test]
fn a_decode_renders_the_trace_form_of_a_disjunction() {
    let text = rendered(&format!("{AXIS}{PRIOR}"), &["&axis_len", "&larger", "&prior"], false);
    let expected = "\
(RULE (input (:P *[P]))
      (frame_extent (:P P) (:N *[N]))
      END)
[&axis_len]
(RULE (&axis_len (:P *[P]))
      (&axis_len (:P *[P2]))
      END)
[&larger]
(RULE (&axis_len (:P *[P]) (:N *[N]))
      (&axis_len (:P *[P2]) (:N *[N2]))
      (OR ((> N N2))
          ALSO
          ((= N N2)
           (&larger (:P P) (:P2 P2)))
          END)
      END)
[&prior]
";
    assert_eq!(text, expected);
}

#[test]
fn a_decode_renders_the_trace_form_of_an_instance() {
    let names = ["&bg", "&fg", "&comps.component", "&comps.connected", "&comps.adjacent", "&comps.node", "&comps.step"];
    let text = rendered(&format!("{BG}{FG}{COMPS}"), &names, false);
    let instance: Vec<&str> = text.lines().skip(8).collect();
    let expected = "\
(INIT Connectivity
  [key] SKIP
  [node]
  ((&fg (:P *[P])) END
   [node key] (END)
   [node P] (P END))
  [step] SKIP
  [&comps.component &comps.connected &comps.adjacent &comps.node &comps.step])";
    assert_eq!(instance.join("\n"), expected);
}

/// The index in the trace of the `n`th record of the language model's `token`.
fn nth_record(decoder: &Decoder<'_>, token: &Token, n: usize) -> usize {
    let records = decoder.trace().records();
    let at = records.iter().enumerate().filter(|(_, record)| record.token == *token && record.emitter == Emitter::Model).nth(n);
    at.expect("the record").0
}

#[test]
fn top_k_tokens_attach_to_the_decision_they_show_and_render_in_braces() {
    let inputs = inputs(&[3, 3], Caps::CORPUS);
    let mut decoder = decoder(&inputs);
    walk(&mut decoder, &model_tokens(&format!("{BG}{FG}")));
    let fresh = nth_record(&decoder, &Token::Control(Control::Fresh), 2);
    let end = nth_record(&decoder, &Token::Control(Control::End), 1);
    let before = decoder.trace().clone();
    assert!(decoder.attach_top_k(fresh, TopK(vec![(Token::Control(Control::Fresh), 0.94), (Token::Label(0), 0.06)])));
    assert!(decoder.attach_top_k(end, TopK(vec![(Token::Control(Control::End), 0.83), (Token::Relation(0), 0.11)])));
    assert!(before.records().iter().all(|record| record.top_k.is_none()), "a trace taken before the attachment keeps its records");
    let vocabulary = Vocabulary::new(Registry::get(), &DecodeSettings::default());
    let options = |top_k| TraceFormOptions { top_k, relations: vec!["&bg".to_owned(), "&fg".to_owned()] };
    let plain = trace_form(&before, &vocabulary, &options(true));
    assert!(!plain.contains('{'));
    assert_eq!(trace_form(decoder.trace(), &vocabulary, &options(false)), plain);
    let braced = trace_form(decoder.trace(), &vocabulary, &options(true));
    assert!(braced.contains("(RULE (input (:P *[P]) (:Col *{* .94 P .06}[Col]))"), "{braced}");
    assert!(braced.contains("      END{END .83 &bg .11})"), "{braced}");
}

#[test]
fn a_forked_decode_keeps_its_own_observations() {
    let inputs = inputs(&[3, 3], Caps::CORPUS);
    let mut decoder = decoder(&inputs);
    walk(&mut decoder, &model_tokens(BG)[..2]);
    let mut fork = decoder.fork();
    fork.observe_counts().expect("a clause in progress");
    assert!(decoder.trace().records().iter().all(|record| record.counts.is_none()));
    assert!(fork.trace().records().last().expect("a record").counts.is_some());
}

/// The trace of a decode of one `RULE` clause over a task, which the row cap
/// of `caps` stops after the clause's last atom where it is `1`, and which is
/// cancelled before the clause's `END` where `cancel` says so.
fn stopped_decode(caps: Caps, cancel: bool) -> DecodeTrace {
    let inputs = inputs(&[1, 2], caps);
    let mut decoder = decoder(&inputs);
    let tokens = model_tokens("(RULE &output (input *P *Col))\n");
    let (end, prefix) = tokens.split_last().expect("a stream");
    walk(&mut decoder, prefix);
    if cancel {
        decoder.cancellation().cancel();
        decoder.step(end.clone()).expect("the end");
    } else if caps.rows == 1 {
        decoder.observe_rows(Some(Example::at(0))).expect("a clause in progress").expect("the sub-body checks");
    }
    decoder.trace().clone()
}

#[test]
fn a_decode_stopped_at_a_cap_or_cancelled_counts_under_that_bound() {
    let capped = stopped_decode(Caps { rows: 1, ..Caps::CORPUS }, false);
    let cancelled = stopped_decode(Caps::CORPUS, true);
    let finished = stopped_decode(Caps::CORPUS, false);
    assert_eq!(capped.records().iter().find_map(|record| record.stop), Some(Stop::Rows));
    assert_eq!(cancelled.records().iter().find_map(|record| record.stop), Some(Stop::Cancelled));
    let shares = stop_shares([&capped, &cancelled, &finished]);
    assert_eq!(shares.total, 3);
    assert_eq!(shares.stopped.get(&Stop::Rows), Some(&1));
    assert_eq!(shares.stopped.get(&Stop::Cancelled), Some(&1));
    assert!((shares.share(Stop::Rows) - 1.0 / 3.0).abs() < 1e-9);
}

#[test]
fn a_run_with_a_trace_records_each_relation_it_evaluates_and_a_run_without_one_none() {
    let solver = read_solver("runs", "(RULE &a (input *P *Col))\n(RULE &b (&a *P *Col) (!= Col 0))\n", "", &|_| None).expect("the file reads").value;
    let registry = Registry::get();
    let program = resolve(&solver.concept_case().program, None, &solver.derived_relations(), registry).value;
    let program = check_program(program, &SolverClauses::of(&solver, registry), registry, &mut CheckCache::default()).expect("every check passes");
    let task = Task { train: Box::new([TrainPair { input: grid(&[1, 2]), output: grid(&[1, 2]) }]), test: Box::new([]) };
    let parameters = ParameterValues::default();
    let session = TaskSession::new(SessionBound { bytes: 1 << 26 }, Caps::CORPUS);
    let limits = Limits { deadline: None, cancellation: Cancellation::default() };
    let constructions = Constructions::new(Vec::new(), registry).expect("an empty table");
    let evaluation = Evaluation { program: &program, concept: None, task: &task, parameters: &parameters, session: &session, registry, constructions: &constructions, limits: &limits };
    let name = |text: &str| relation_of(&program, &ProgramRelation::Declared(RelationName(DeclaredName::Written(text.into())))).expect("the relation");
    let mut trace = RunTrace::default();
    evaluation.relation_traced(&name("&b"), Some(Example::at(0)), &mut trace).expect("the run");
    let records = trace.records();
    assert_eq!(records.iter().map(|record| (record.relation.clone(), record.rows)).collect::<Vec<_>>(), vec![(name("&a"), Some(2)), (name("&b"), Some(2))]);
    assert!(records.iter().all(|record| record.models == 1 && record.values_determined == 0));
    assert!(records.iter().all(|record| record.example == Some(Example::at(0)) && record.stop.is_none()));
    let mut untraced = RunTrace::default();
    evaluation.relation(&name("&b"), Some(Example::at(0))).expect("the run");
    assert!(untraced.is_empty());
    untraced.push(records[0].clone());
    assert_eq!(untraced.len(), 1);
}

/// `program`, a decoded program, checked.
fn checked_decoded(program: &Node<Program>) -> CheckedProgram {
    let registry = Registry::get();
    let resolved = resolve(program, None, &SolverScope::default(), registry).value;
    check_program(resolved.clone(), &SolverClauses::of_program(resolved), registry, &mut CheckCache::default()).expect("every check passes")
}

/// Asserts that the program form of the decode of `arclog` reads back to the
/// content of the decoded program.
fn reads_back(arclog: &str) -> String {
    let inputs = inputs(&[3, 3], Caps::CORPUS);
    let mut decoder = decoder(&inputs);
    walk(&mut decoder, &model_tokens(arclog));
    let text = write_synthesized(decoder.program(), Registry::get());
    let read = checked(&text);
    let decoded = checked_decoded(decoder.program());
    assert_eq!(read.program.content(&NodePath::default()), decoded.program.content(&NodePath::default()), "{text}");
    text
}

#[test]
fn the_program_form_of_a_decode_reads_back_to_its_content() {
    let text = reads_back(&format!("{BG}{FG}"));
    assert_eq!(text, "(RULE &r0 (input (:Col *Col)))\n(RULE &r1 (input (:P *P) (:Col *Col)) (&r0 (:Col *Col2)) (!= Col Col2))\n");
    reads_back(&format!("{AXIS}{PRIOR}"));
    reads_back(&format!("{BG}{FG}{COMPS}"));
}
