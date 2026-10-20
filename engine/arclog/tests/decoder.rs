//! The decoder reads the token stream of a program into a program of the
//! same content, with each token the language model emits in its mask and
//! each token the engine emits among the tokens it forces, refuses a token
//! outside the mask, and forks a decode that leaves its source as it was.

use arclog::check::{check_program, CheckCache, CheckId, CheckedProgram, SolverClauses};
use arclog::decode::{Decoder, Refusal};
use arclog::eval::instance::Constructions;
use arclog::eval::values::Caps;
use arclog::program::path::NodePath;
use arclog::program::{FactRelation, Node, Program};
use arclog::read::read_solver;
use arclog::registry::{LibName, Registry};
use arclog::resolver::{resolve, SolverScope};
use arclog::session::{SessionBound, TaskSession};
use arclog::stream::{token_stream, Control, DecodeSettings, Emitter, Token, Vocabulary};
use arclog::task::Task;

/// The checked concept program of the arclog file `arclog`.
fn checked(arclog: &str) -> CheckedProgram {
    let solver = read_solver("decode", arclog, "", &|_| None).expect("the file reads").value;
    let registry = Registry::get();
    let program = resolve(&solver.concept_case().program, None, &solver.derived_relations(), registry).value;
    check_program(program, &SolverClauses::of(&solver, registry), registry, &mut CheckCache::default()).expect("every check passes")
}

/// `program`, a decoded program, checked.
fn checked_decoded(program: &Node<Program>) -> CheckedProgram {
    let registry = Registry::get();
    let resolved = resolve(program, None, &SolverScope::default(), registry).value;
    check_program(resolved.clone(), &SolverClauses::of_program(resolved), registry, &mut CheckCache::default()).expect("every check passes")
}

/// What a decode runs on.
struct Inputs {
    task: Task,
    session: TaskSession,
    constructions: Constructions,
}

fn inputs() -> Inputs {
    let constructions = Constructions::new(Vec::new(), Registry::get()).expect("an empty table");
    Inputs { task: Task { train: Box::new([]), test: Box::new([]) }, session: TaskSession::new(SessionBound { bytes: 1 << 26 }, Caps::CORPUS), constructions }
}

fn decoder(inputs: &Inputs) -> Decoder<'_> {
    Decoder::new(&inputs.task, &inputs.session, Registry::get(), &inputs.constructions, &DecodeSettings::default())
}

/// Steps `decoder` through `stream`: each token of the language model in
/// the mask, and each token of the engine the next of the tokens the step
/// before it forced.
fn walk(decoder: &mut Decoder<'_>, stream: &[(Token, Emitter)]) {
    let mut forced: Vec<Token> = Vec::new();
    for (index, (token, emitter)) in stream.iter().enumerate() {
        match emitter {
            Emitter::Engine => assert_eq!(Some(token), (!forced.is_empty()).then(|| forced.remove(0)).as_ref(), "the engine's token at {index}"),
            Emitter::Model => {
                assert!(forced.is_empty(), "the engine forces {forced:?} before the token at {index}");
                let id = decoder.vocabulary().id(token).expect("a token of the vocabulary");
                assert!(decoder.admissible().contains(id), "the mask admits {token:?} at {index}");
                forced = decoder.step(token.clone()).unwrap_or_else(|refusal| panic!("{token:?} at {index}: {refusal:?}")).into();
            }
        }
    }
    assert!(forced.is_empty(), "the engine forces {forced:?} after the stream");
}

/// The program written in `arclog`, checked, and the program that the
/// decode of its stream gives, checked, which gives the same stream.
fn round_trip(arclog: &str) -> (CheckedProgram, CheckedProgram) {
    let written = checked(arclog);
    let vocabulary = Vocabulary::new(Registry::get(), &DecodeSettings::default());
    let stream = token_stream(&written, &vocabulary).expect("the program has a stream");
    let inputs = inputs();
    let mut decoder = decoder(&inputs);
    walk(&mut decoder, &stream);
    let decoded = checked_decoded(decoder.program());
    assert_eq!(token_stream(&decoded, &vocabulary).expect("the decoded program has a stream"), stream);
    (written, decoded)
}

/// Asserts that the decode of the stream of `arclog` gives a program of
/// the content of the program written.
fn same_content(arclog: &str) {
    let (written, decoded) = round_trip(arclog);
    assert_eq!(decoded.program.content(&NodePath::default()), written.program.content(&NodePath::default()));
}

const BG: &str = "(RULE &bg (input (:Col *C)))\n";
const FG: &str = "(RULE &fg (input *P *Col) (&bg (:C *V)) (!= Col V))\n";
const COMPS: &str = "(INIT &comps Connectivity (node ((:P P)) (&fg *P)))\n";
const AXIS: &str = "(RULE &axis_len (input (:P *B)) (frame_extent (:P B) (:N *N)))\n(RULE &larger (&axis_len *B) (&axis_len (:B *B2)))\n";
const PRIOR: &str = "(RULE &prior (&axis_len *B *N) (&axis_len (:B *B2) (:N *N2)) (OR ((> N N2)) ((= N N2) (&larger B B2))))\n";

#[test]
fn the_programs_of_the_trace_form_decode_to_their_content() {
    same_content(&format!("{BG}{FG}"));
    same_content(&format!("{BG}{FG}{COMPS}"));
    same_content(&format!("{AXIS}{PRIOR}"));
}

#[test]
fn a_negation_an_if_an_all_and_a_constraint_on_zero_decode_to_their_content() {
    let lists = "(RULE &lists (input *P *Col) (NOT (&fg P)) (IF ((&bg (:C Col))) ((= *K 0)) ((input P (:Col *D)) (= *K 0))) (ALL ((input (:P *Q) (:Col Col))) ((&fg (:P Q)))))\n";
    same_content(&format!("{BG}{FG}{lists}"));
}

#[test]
fn a_det_by_a_proposer_and_a_one_mark_decode_to_their_content() {
    same_content("(DET &arr_dim ScaleRatio)\n(RULE &cell (input *P *Col) (ONE P))\n");
}

/// The names of a key's columns are a part of the content of its instance,
/// and a decoded program names them by slot, so the decode of a keyed
/// instance gives its stream again and not its content.
#[test]
fn a_keyed_instance_decodes_to_its_stream() {
    let boxes = "(INIT &boxes BoundingBox (key ((&comps.component ^Id)) (cell (P) (&comps.component *P Id))))\n";
    round_trip(&format!("{BG}{FG}{COMPS}{boxes}"));
}

/// A decode stepped through the stream of `arclog`.
fn decoded<'i>(inputs: &'i Inputs, arclog: &str) -> Decoder<'i> {
    let vocabulary = Vocabulary::new(Registry::get(), &DecodeSettings::default());
    let stream = token_stream(&checked(arclog), &vocabulary).expect("the program has a stream");
    let mut decoder = decoder(inputs);
    walk(&mut decoder, &stream);
    decoder
}

#[test]
fn a_token_outside_the_mask_is_refused() {
    let inputs = inputs();
    let mut decoder = decoded(&inputs, BG);
    assert!(matches!(decoder.step(Token::Label(0)), Err(Refusal::Grammar(_))));
    assert!(matches!(decoder.step(Token::Relation(1)), Err(Refusal::Grammar(_))));
    for token in [Token::Control(Control::Rule), Token::Fact(FactRelation::Input), Token::Column(1), Token::Control(Control::Fresh)] {
        decoder.step(token).expect("a site of `input` at a fresh label");
    }
    for token in [Token::Lib(LibName("dir_elem".into())), Token::Column(0)] {
        decoder.step(token).expect("a site of `dir_elem`");
    }
    let id = decoder.vocabulary().id(&Token::Label(0)).expect("a label slot");
    assert!(!decoder.admissible().contains(id));
    assert!(matches!(decoder.step(Token::Label(0)), Err(Refusal::Check { check: CheckId::Types, .. })));
}

#[test]
fn a_fork_stepped_apart_leaves_its_source_as_it_was() {
    let inputs = inputs();
    let decoder = decoded(&inputs, BG);
    let mask = decoder.admissible();
    let mut fork = decoder.fork();
    for token in [Token::Control(Control::Rule), Token::Relation(0), Token::Column(0), Token::Control(Control::Fresh), Token::Control(Control::End)] {
        fork.step(token).expect("a clause that reads `&bg`");
    }
    assert_eq!(fork.program().value().forms.len(), 2);
    assert_eq!(decoder.program().value().forms.len(), 1);
    assert_eq!(decoder.admissible(), mask);
}
